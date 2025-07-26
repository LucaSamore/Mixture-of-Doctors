from .kafka_client import DOMAIN
from .utilities import (
    init_kafka_client,
    init_qdrant_client,
    init_groq_client,
    init_redis_client,
    init_embedding_model,
)
from .rag_process import process_incoming_query
from loguru import logger
import asyncio


async def main() -> None:
    logger.info(f"RAG module initialized with domain: {DOMAIN}")
    logger.info("Setting up clients...")

    kafka_client = await init_kafka_client()
    qdrant_client = await init_qdrant_client()
    groq_client = await init_groq_client()
    redis_client = await init_redis_client()
    embedding_model = await init_embedding_model()

    logger.info("Clients initialized successfully")
    logger.info("Waiting for incoming messages...")

    while True:
        try:
            await process_incoming_query(
                kafka_client, embedding_model, qdrant_client, groq_client, redis_client
            )
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in main processing loop: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
