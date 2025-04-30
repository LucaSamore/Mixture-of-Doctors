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
import redis
import json
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


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)


class RAGClients:
    kafka_client: KafkaClient
    qdrant_client: AsyncQdrantClient
    llm_groq_client: AsyncGroq
    redis_client: redis.Redis
    embedding_model: SentenceTransformer

    @classmethod
    async def create(cls) -> "RAGClients":
        self = cls()
        await self._init_kafka_client()
        await self._init_qdrant_client()
        self._init_groq_client()
        self._init_redis_client()
        self._init_embedding_model()
        return self

    async def _init_kafka_client(self) -> None:
        self.kafka_client = await KafkaClient.create()

    async def _init_qdrant_client(self) -> None:
        port = (lambda p: int(p) if p else 6333)(os.getenv("QDRANT_PORT", 6333))
        self.qdrant_client = AsyncQdrantClient(
            url=f"http://{os.getenv('QDRANT_HOST')}:{port}"
        )

    def _init_groq_client(self) -> None:
        self.llm_groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

    def _init_redis_client(self) -> None:
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True,
        )

    def _init_embedding_model(self) -> None:
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
