from aiokafka import AIOKafkaConsumer
from groq import AsyncGroq
from loguru import logger
from pydantic import BaseModel
from typing import Any, Dict, Set
from .utilities import prepare_prompt
import redis.asyncio as redis
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYNTHESIZE_PROMPT_PATH = os.path.join(BASE_DIR, "prompts/synth_prompt.md")


class RAGResponse(BaseModel):
    user_id: str
    query_id: str
    disease: str
    original_query: str
    response: str
    stream: bool
    number: int
    total: int
    plain_text: bool = False


class QueryData(BaseModel):
    query_id: str
    user_id: str
    original_query: str
    responses: Dict[str, str] = {}
    received_numbers: Set[int] = set()
    total: int
    stream: bool
    plain_text: bool


# [query_id, query_data]
active_queries: Dict[str, QueryData] = {}


async def process_incoming_disease_specific_responses(
    kafka_consumer: AIOKafkaConsumer, redis_client: redis.Redis, groq_client: AsyncGroq
) -> None:
    async for message in kafka_consumer:
        response = RAGResponse.model_validate(message.value)
        await handle_response(response, kafka_consumer, redis_client, groq_client)


async def handle_response(
    response: RAGResponse,
    kafka_consumer: AIOKafkaConsumer,
    redis_client: redis.Redis,
    groq_client: AsyncGroq,
) -> None:
    query_id = response.query_id
    if query_id not in active_queries:
        active_queries[query_id] = QueryData(
            query_id=query_id,
            user_id=response.user_id,
            original_query=response.original_query,
            total=response.total,
            stream=response.stream,
            plain_text=response.plain_text,
        )
    query_data = active_queries[query_id]
    query_data.responses[response.disease] = response.response
    query_data.received_numbers.add(response.number)
    if not is_query_complete(query_data):
        return
    logger.info(
        f"All {query_data.total} responses received for user {response.user_id}"
    )
    await kafka_consumer.commit()
    await synthesize_and_send_response(query_data, redis_client, groq_client)
    del active_queries[query_id]


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


async def synthesize_and_send_response(
    query_data: QueryData, redis_client: redis.Redis, groq_client: AsyncGroq
) -> None:
    try:
        disease_responses = []
        for disease, response in query_data.responses.items():
            disease_responses.append(f"### {disease.upper()} | RESPONSE:\n{response}")
        formatted_responses = "\n\n".join(disease_responses)
        logger.info(f"Responses to synthesize: {formatted_responses}")
        stream = await synthesize(
            query_data.original_query,
            formatted_responses,
            query_data.stream,
            query_data.plain_text,
            groq_client,
        )
        if stream is not None:
            await send_response(
                query_data.user_id, query_data.original_query, stream, redis_client
            )
    except Exception as e:
        logger.error(f"Error during synthesis and response: {e}")


async def synthesize(
    original_query: str,
    formatted_responses: str,
    stream: bool,
    plain_text: bool,
    groq_client: AsyncGroq,
) -> Any:
    if plain_text:
        output_format = "Please provide your response in plain text format without any Markdown formatting."
    else:
        output_format = "Structure your answer with appropriate headings and sections."
    params = {
        "original_query": original_query,
        "responses": formatted_responses,
        "output_format": output_format,
    }
    try:
        prompt = prepare_prompt(template_path=SYNTHESIZE_PROMPT_PATH, **params)
        logger.info(f"Synthesizing response for query: {original_query}")
        return await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt}],
            stream=stream,
        )
    except Exception as e:
        logger.error(f"Error synthesizing responses: {e}")
        return None


async def send_response(
    user_id: str, query: str, response_stream: Any, redis_client: redis.Redis
) -> None:
    try:
        async for chunk in response_stream:
            content = chunk.choices[0].delta.content
            logger.info(f"Sending chunk {content}")
            await redis_client.xadd(
                name=user_id,
                fields={
                    "query": query,
                    "response": str(content),
                    "done": str(chunk.choices[0].finish_reason),
                },
            )
    except Exception as e:
        logger.error(f"Error sending response to Redis: {e}")
