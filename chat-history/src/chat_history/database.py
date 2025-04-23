from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv
import os

load_dotenv()

mongodb_url = os.getenv("MONGODB_URL")
database_name = os.getenv("MONGODB_DB")

client: AsyncIOMotorClient
database = None


async def get_database():
    global database

    if database is None:
        logger.info("Database connection not initialized, connecting now")
        await connect_to_mongodb()

    return database


async def connect_to_mongodb():
    global client, database
    logger.info(f"Connecting to MongoDB at {mongodb_url}")
    client = AsyncIOMotorClient(mongodb_url)

    if database_name is None:
        logger.error("DATABASE_NAME environment variable is not set")
        raise ValueError("DATABASE_NAME environment variable is not set")

    database = client[database_name]

    try:
        await client.admin.command("ping")
        logger.success(f"Connected to MongoDB at {mongodb_url}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongodb_connection():
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")
