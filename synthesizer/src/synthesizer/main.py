import asyncio
from .synthesis import process_incoming_disease_specific_responses
from .utilities import init_kafka_consumer, init_groq_client, init_redis_client
from loguru import logger


async def main() -> None:
    kafka_client = await init_kafka_consumer()
    redis_client = await init_redis_client()
    groq_client = await init_groq_client()

    await kafka_client.start()

    while True:
        try:
            await process_incoming_disease_specific_responses(
                kafka_client, redis_client, groq_client
            )
        except Exception as e:
            logger.error(f"Error processing incoming responses: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
