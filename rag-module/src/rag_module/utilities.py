from pydantic import BaseModel
from typing import List
from .kafka_client import KafkaClient
from groq import AsyncGroq
from qdrant_client import AsyncQdrantClient
from sentence_transformers import SentenceTransformer
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
import os
import redis.asyncio as redis
import string
import httpx

load_dotenv()

CHAT_HISTORY_URL = os.getenv("CHAT_HISTORY_URL")


class ConversationItem(BaseModel):
    question: str
    answer: str
    timestamp: datetime = datetime.now()


class ConversationModel(BaseModel):
    username: str
    created_at: datetime
    conversation: List[ConversationItem]


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


def prepare_prompt(template: str, **kwargs) -> str:
    try:
        with open(template, "r") as f:
            content = f.read()
        return string.Template(content).substitute(kwargs)
    except Exception as e:
        logger.error(f"Error while preparing prompt: {e}")
        return ""


async def init_kafka_client() -> KafkaClient:
    logger.info("Initializing Kafka client")
    return await KafkaClient.create()


async def init_qdrant_client() -> AsyncQdrantClient:
    logger.info("Initializing Qdrant client")
    port = (lambda p: int(p) if p else 6333)(os.getenv("QDRANT_PORT", 6333))
    return AsyncQdrantClient(url=f"http://{os.getenv('QDRANT_HOST')}:{port}")


async def init_groq_client() -> AsyncGroq:
    logger.info("Initializing Groq client")
    return AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


async def init_redis_client() -> redis.Redis:
    logger.info("Initializing Redis client")
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")),
        password=os.getenv("REDIS_PASSWORD"),
        decode_responses=True,
    )


async def init_embedding_model() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2")
