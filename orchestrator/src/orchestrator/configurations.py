from typing import List
from dotenv import load_dotenv
from loguru import logger
from enum import Enum
from groq import AsyncGroq
from aiokafka import AIOKafkaProducer
import redis.asyncio as redis
import json
import os
import string

load_dotenv()

CHAT_HISTORY_URL = os.getenv("CHAT_HISTORY_URL")
CONFIG_FILE_PATH = "/app/config.json"
LOG_FILE_PATH = "/app/logs/orchestrator.log"


logger.add(LOG_FILE_PATH, rotation="10 MB")


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


llm_groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


kafka_producer = AIOKafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BROKER", "localhost:9092"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)


redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD", "redispassword"),
    decode_responses=True,
)
