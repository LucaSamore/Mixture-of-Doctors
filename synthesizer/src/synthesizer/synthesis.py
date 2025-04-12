from loguru import logger
from pydantic import BaseModel
from typing import Dict
from .utilities import llm_groq, consumer, prepare_prompt, redis_client
import asyncio
import os

active_queries: Dict[str, Dict] = {}
consumer_task = None
PROMPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(PROMPT_DIR, "./prompt/synth_prompt.md")


class RagResponse(BaseModel):
    user_id: str
    disease: str
    original_query: str
    response: str
    stream: bool
    number: int
    total: int


async def start_consumer():
    global consumer_task
    consumer_task = asyncio.create_task(run_reader())
    logger.info("Consumer started")


async def run_reader():
    try:
        logger.info("Starting Kafka message polling...")
        while True:
            for msg in consumer:
                logger.info(f"Received message: {msg.value}")
                response = RagResponse(**msg.value)
                await handle_response(response)
    except Exception as e:
        consumer.close()
        logger.error(f"Consumer error: {e}")
    finally:
        consumer.close()
        logger.info("Consumer stopped")


async def handle_response(response: RagResponse):
    user_id = response.user_id

    if user_id not in active_queries:
        active_queries[user_id] = {
            "user_id": user_id,
            "original_query": response.original_query,
            "responses": {},
            "received_numbers": set(),
            "total": response.total,
            "stream": response.stream,
        }
    query_data = active_queries[user_id]
    query_data["responses"][response.disease] = response.response
    query_data["received_numbers"].add(response.number)

    if not _is_query_complete(user_id, query_data):
        return

    logger.info(f"All {query_data['total']} sub-queries received for user {user_id}")

    _commit_query(user_id)
    await synthesize_response(query_data)
    del active_queries[user_id]


def _is_query_complete(user_id, query_data):
    received_count = len(query_data["received_numbers"])
    total_expected = query_data["total"]

    if received_count < total_expected:
        return False

    expected_numbers = set(range(1, total_expected + 1))
    if query_data["received_numbers"] != expected_numbers:
        logger.warning(
            f"Missing responses for user {user_id}. "
            f"Expected: {expected_numbers}, Got: {query_data['received_numbers']}"
        )
        return False

    return True


def _commit_query(user_id):
    try:
        consumer.commit()
        logger.info(f"Successfully committed offsets for user {user_id}")
    except Exception as e:
        logger.error(f"Error committing offsets: {e}")


async def synthesize_response(query_data: Dict):
    try:
        diseases_responses = []
        for disease, response in query_data["responses"].items():
            diseases_responses.append(f"### {disease.upper()} | RESPONSE:\n{response}")
        responses = "\n\n".join(diseases_responses)

        logger.info(f"Responses to synthesize: {responses}")
        response = await generate_synthesis(
            query_data["original_query"], responses, query_data["stream"]
        )

        logger.info(f"Response generated: {response}")

        await stream_to_redis(
            query_data["user_id"], query_data["original_query"], response
        )

    except Exception as e:
        logger.error(f"Error during synthesis: {e}")


async def generate_synthesis(
    original_query: str, formatted_responses: str, stream: bool
):
    params = {"original_query": original_query, "responses": formatted_responses}
    prompt = prepare_prompt(template=SCRIPT, **params)
    # response = llm.generate(model="llama3.3:latest", prompt=prompt, stream=stream)
    response = llm_groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": prompt}],
        stream=stream,
    )
    logger.info(f"Response synthesized {response}")
    return response


async def stream_to_redis(user_id: str, query: str, response):
    for chunk in response:
        content = chunk.choices[0].delta.content
        logger.info(content)
        redis_client.xadd(
            name=user_id,
            fields={
                "query": query,
                "response": str(content),
                "done": True if content == "" else False,
            },
        )
