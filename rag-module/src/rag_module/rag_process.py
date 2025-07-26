from .kafka_client import RAGModuleMessage, KafkaClient, DateTimeEncoder
from .utilities import fetch_chat_history_for_user, prepare_prompt
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import ScoredPoint, QueryResponse
from groq import AsyncGroq
from loguru import logger
from typing import List
import redis.asyncio as redis
import os
import json


PROMPT_FILE = "/app/prompts/rag_module.md"
DOMAIN = os.getenv("RAG_DOMAIN")


async def process_incoming_query(
    kafka_client: KafkaClient,
    embedding_model: SentenceTransformer,
    qdrant_client: AsyncQdrantClient,
    groq_client: AsyncGroq,
    redis_client: redis.Redis,
) -> None:
    message = await kafka_client.get_message_from_queue()
    if message is not None:
        logger.info(f"Received message: {message}")
        try:
            context = await retrieve(message.rag_query, embedding_model, qdrant_client)
            prompt = await augment(context, message.user_id, message.plain_text)
            await generate(prompt, message, groq_client, redis_client, kafka_client)
        except Exception as e:
            logger.error(f"Error processing message: {e}")


async def retrieve(
    query: str, embedding_model: SentenceTransformer, qdrant_client: AsyncQdrantClient
) -> List[dict]:
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


async def augment(embeddings: List[dict], user_id: str, plain_text: bool) -> str:
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


async def generate(
    prompt: str,
    incoming_message: RAGModuleMessage,
    groq_client: AsyncGroq,
    redis_client: redis.Redis,
    kafka_client: KafkaClient,
) -> None:
    logger.info(f"Generating response for query:\n{incoming_message}")
    if incoming_message.total == 1:
        await handle_stream_response(
            prompt, incoming_message, groq_client, redis_client
        )
    else:
        await handle_batch_response(prompt, incoming_message, groq_client, kafka_client)


async def handle_stream_response(
    prompt: str,
    incoming_message: RAGModuleMessage,
    groq_client: AsyncGroq,
    redis_client: redis.Redis,
) -> None:
    stream = await groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": incoming_message.rag_query},
        ],
        model="llama-3.3-70b-versatile",
        stream=True,
    )
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        await redis_client.xadd(
            name=incoming_message.user_id,
            fields={
                "query": incoming_message.original_query,
                "response": str(content),
                "done": str(chunk.choices[0].finish_reason),
            },
        )


async def handle_batch_response(
    prompt: str,
    incoming_message: RAGModuleMessage,
    groq_client: AsyncGroq,
    kafka_client: KafkaClient,
) -> None:
    chat_completion = await groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": incoming_message.rag_query},
        ],
        model="llama-3.3-70b-versatile",
        max_completion_tokens=1024,
        stream=False,
    )
    await kafka_client.send_message_to_queue(chat_completion, incoming_message)
