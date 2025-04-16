import asyncio
from loguru import logger
from synthesizer.synthesis import start_consumer


async def main() -> None:
    await start_consumer()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down synthesizer service...")
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise
