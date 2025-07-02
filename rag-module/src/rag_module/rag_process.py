from .kafka_client import KafkaClient, RAGModuleMessage
from .utilities import (
    DateTimeEncoder,
    ConversationItem,
    ConversationModel,
    prepare_prompt,
)
from groq import AsyncGroq
from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import ScoredPoint, QueryResponse
from sentence_transformers import SentenceTransformer
from typing import List, TypeAlias
import asyncio
import httpx
import os
import redis
import json


PROMPT_FILE = "/app/prompts/rag_module.md"
DOMAIN = os.getenv("RAG_DOMAIN")
CHAT_HISTORY_URL = os.getenv("CHAT_HISTORY_URL")

Query: TypeAlias = str
Prompt: TypeAlias = str


kafka_client = KafkaClient()

port = (lambda p: int(p) if p else 6333)(os.getenv("QDRANT_PORT", 6333))
qdrant_client = AsyncQdrantClient(url=f"http://{os.getenv('QDRANT_HOST')}:{port}")

llm_groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


async def fetch_chat_history_for_user(user_id: str) -> List[ConversationItem]:
    logger.info(f"Fetching chat history for user: {user_id}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{CHAT_HISTORY_URL}/{user_id}")
            response.raise_for_status()
            model = ConversationModel.model_validate(response.json())
            logger.info("Chat history fetched successfully")
            return model.conversation
    except httpx.HTTPError as e:
        logger.error(f"HTTP error while fetching chat history: {e}")
        return []


async def retrieve(query: Query) -> List[dict]:
    logger.info(f"Retrieving context for query: {query}")
    query_vector = embedding_model.encode(query).tolist()
    logger.info("Doing vector search...")
    search_result = await qdrant_client.query_points(
        collection_name=f"{DOMAIN}_docs", query=query_vector, limit=5
    )

    logger.info(f"Retrieved search results: {search_result}")

    results = []
    if isinstance(search_result, QueryResponse) and hasattr(search_result, "points"):
        scored_points = search_result.points

        for point in scored_points:
            if isinstance(point, ScoredPoint) and hasattr(point, "payload"):
                results.append(point.payload)
            else:
                logger.warning(f"Skipping point without payload: {point}")

        logger.info(f"Extracted {len(results)} payloads from search results")
    else:
        logger.warning(f"Unexpected search_result format: {search_result}")

    return results


async def augment(embeddings: List[dict], user_id: str, plain_text: bool) -> Prompt:
    conversation = await fetch_chat_history_for_user(user_id)

    conversation_data = [item.model_dump() for item in conversation]
    context = json.dumps(conversation_data, indent=4, cls=DateTimeEncoder)
    logger.info(f"Context: {context}")

    extracted_embeddings = []
    for payload in embeddings:
        if isinstance(payload, dict):
            extracted_embeddings.append(
                {
                    "title": payload.get("title", ""),
                    "source": payload.get("source", ""),
                    "text": payload.get("text", ""),
                }
            )
        else:
            logger.warning(f"Skipping payload with unexpected type: {type(payload)}")

    embeddings_context = json.dumps(extracted_embeddings, indent=4, cls=DateTimeEncoder)
    logger.info(f"Embeddings Context: {embeddings_context}")

    combined_context = f"Chat History:\n{context}\n\nEmbeddings:\n{embeddings_context}"

    if plain_text:
        output_format = "Please provide your response in plain text format without any Markdown formatting."
    else:
        output_format = "Structure your answer with appropriate headings and sections."

    params = {
        "domain": DOMAIN,
        "context": combined_context,
        "output_format": output_format,
    }
    return prepare_prompt(template=PROMPT_FILE, **params)


async def handle_stream_response(
    prompt: Prompt, incoming_message: RAGModuleMessage
) -> None:
    stream = await llm_groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": incoming_message.rag_query},
        ],
        model="llama-3.3-70b-versatile",
        stream=True,
    )
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        redis_client.xadd(
            name=incoming_message.user_id,
            fields={
                "query": incoming_message.original_query,  # TODO: check it
                "response": str(content),
                "done": str(chunk.choices[0].finish_reason),
            },
        )


async def handle_batch_response(
    prompt: Prompt, incoming_message: RAGModuleMessage
) -> None:
    chat_completion = await llm_groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": incoming_message.rag_query},
        ],
        model="llama-3.3-70b-versatile",
        max_completion_tokens=1024,
        stream=False,
    )
    kafka_client.send_message_to_queue(chat_completion, incoming_message)


async def generate(prompt: Prompt, incoming_message: RAGModuleMessage) -> None:
    logger.info(f"Generating response for query:\n{incoming_message}")

    if incoming_message.total == 1:
        await handle_stream_response(prompt, incoming_message)
    else:
        await handle_batch_response(prompt, incoming_message)


async def handle_incoming_message() -> None:
    message = kafka_client.get_message_from_queue()
    if message is not None:
        logger.info(f"Received message: {message}")
        try:
            context = await retrieve(message.rag_query)
            prompt = await augment(context, message.user_id, message.plain_text)
            logger.info(f"Generated prompt: {prompt}")
            await generate(prompt, message)
        except Exception as e:
            logger.error(f"Error processing message: {e}")


async def main():
    logger.info(f"RAG process initialized with domain: {DOMAIN}")
    logger.info("Waiting for incoming messages...")
    while True:
        try:
            await handle_incoming_message()
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in main processing loop: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
