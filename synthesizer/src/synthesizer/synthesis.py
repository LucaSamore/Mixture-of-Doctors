from loguru import logger
from pydantic import BaseModel
from typing import Any, AsyncIterator, Dict, Set
from .utilities import LLMClient, KafkaClient, RedisClient, prepare_prompt
import asyncio
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYNTHESIS_PROMPT_PATH = os.path.join(BASE_DIR, "prompts/synth_prompt.md")

kafka = KafkaClient()
redis = RedisClient()
llm = LLMClient()


class RagResponse(BaseModel):
    user_id: str
    disease: str
    original_query: str
    response: str
    stream: bool
    number: int
    total: int


class QueryData(BaseModel):
    user_id: str
    original_query: str
    responses: Dict[str, str] = {}
    received_numbers: Set[int] = set()
    total: int
    stream: bool


# [user_id, query_data]
active_queries: Dict[str, QueryData] = {}


async def start_consumer() -> None:
    try:
        asyncio.create_task(run_reader())
        logger.info("Consumer started")
    except Exception as e:
        logger.error(f"Error starting consumer: {e}")
        raise


async def run_reader() -> None:
    consumer = kafka.get_consumer()

    try:
        while True:
            for message in consumer:
                logger.info(f"Received message: {message.value}")
                try:
                    response = RagResponse(**message.value)
                    await handle_response(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
    except Exception as e:
        logger.error(f"Consumer error: {e}")
    finally:
        kafka.close()
        logger.info("Response processor stopped")


async def handle_response(response: RagResponse) -> None:
    user_id = response.user_id

    if user_id not in active_queries:
        active_queries[user_id] = QueryData(
            user_id=user_id,
            original_query=response.original_query,
            total=response.total,
            stream=response.stream,
        )

    query_data = active_queries[user_id]
    query_data.responses[response.disease] = response.response
    query_data.received_numbers.add(response.number)

    if not is_query_complete(query_data):
        return

    logger.info(f"All {query_data.total} responses received for user {user_id}")

    try:
        kafka.commit()
    except Exception as e:
        logger.error(f"Error committing offsets: {e}")

    await synthesize_and_send_response(query_data)

    del active_queries[user_id]


def is_query_complete(query_data: QueryData) -> bool:
    received_count = len(query_data.received_numbers)
    total_expected = query_data.total

    if received_count < total_expected:
        return False

    expected_numbers = set(range(1, total_expected + 1))
    if query_data.received_numbers != expected_numbers:
        logger.warning(
            f"Missing responses for user {query_data.user_id}. "
            f"Expected: {expected_numbers}, Got: {query_data.received_numbers}"
        )
        return False

    return True


async def synthesize_and_send_response(query_data: QueryData) -> None:
    try:
        disease_responses = []
        for disease, response in query_data.responses.items():
            disease_responses.append(f"### {disease.upper()} | RESPONSE:\n{response}")

        formatted_responses = "\n\n".join(disease_responses)
        logger.info(f"Responses to synthesize: {formatted_responses}")

        synthesis_stream = await generate_synthesis(
            query_data.original_query, formatted_responses, query_data.stream
        )

        await send_response(
            query_data.user_id, query_data.original_query, synthesis_stream
        )

    except Exception as e:
        logger.error(f"Error during synthesis: {e}")


async def generate_synthesis(
    original_query: str, formatted_responses: str, stream: bool
) -> AsyncIterator[Any]:
    prompt = prepare_prompt(
        SYNTHESIS_PROMPT_PATH,
        original_query=original_query,
        responses=formatted_responses,
    )

    try:
        response = await llm.generate(prompt, stream=stream)
        logger.success("Response synthesis completed")
    except Exception as e:
        logger.error(f"Error generating synthesis: {e}")
        raise

    return response


async def send_response(user_id: str, query: str, response_stream: Any) -> None:
    """Sends the synthesized response to Redis."""
    try:
        for chunk in response_stream:
            content = chunk.choices[0].delta.content

            logger.debug(f"Streaming chunk: {content}")

            redis.stream_message(
                stream_id=user_id,
                fields={
                    "query": query,
                    "response": str(content),
                    "done": str(chunk.choices[0].finish_reason),
                },
            )
    except Exception as e:
        logger.error(f"Error sending to Redis: {e}")
