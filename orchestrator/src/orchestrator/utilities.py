from typing import List
from dotenv import load_dotenv
from loguru import logger
from enum import Enum
from fastapi import Request
from aiokafka import AIOKafkaProducer
from groq import AsyncGroq
import redis.asyncio as redis
import json
import os
import string

load_dotenv()

CHAT_HISTORY_URL = os.getenv("CHAT_HISTORY_URL")
CONFIG_FILE_PATH = "/app/config.json"


class PromptTemplate(Enum):
    PLANNING = "./prompts/planning.md"
    EASY_QUERIES = "./prompts/easy_queries.md"


def prepare_prompt(template: str, **kwargs) -> str:
    try:
        with open(template, "r") as f:
            content = f.read()
        return string.Template(content).substitute(kwargs)
    except Exception as e:
        logger.error(e)
        return ""


def get_diseases_from_config_file() -> List[str]:
    try:
        with open(CONFIG_FILE_PATH, "r") as f:
            config = json.load(f)
        return config["rag_modules"]
    except Exception as e:
        logger.error(e)
        return []


async def init_kafka_producer() -> AIOKafkaProducer:
    return AIOKafkaProducer(
        bootstrap_servers=os.getenv("KAFKA_BROKER", "localhost:9092"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


async def init_redis_client() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", "redispassword"),
        decode_responses=True,
    )


async def init_groq_client() -> AsyncGroq:
    return AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


def get_kafka_producer(request: Request) -> AIOKafkaProducer:
    if not hasattr(request.app.state, "kafka_producer"):
        raise RuntimeError("Kafka producer is not initialized")
    return request.app.state.kafka_producer


def get_redis_client(request: Request) -> redis.Redis:
    if not hasattr(request.app.state, "redis_client"):
        raise RuntimeError("Redis client is not initialized")
    return request.app.state.redis_client


def get_llm_groq(request: Request) -> AsyncGroq:
    if not hasattr(request.app.state, "llm_groq"):
        raise RuntimeError("LLM Groq client is not initialized")
    return request.app.state.llm_groq
