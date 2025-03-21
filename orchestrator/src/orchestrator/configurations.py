import json
import os
import string

from enum import Enum

import redis
from kafka import KafkaProducer
from loguru import logger
from ollama import Client

LOG_FILE_PATH = "/app/logs/orchestrator.log"
logger.add(LOG_FILE_PATH, rotation="10 MB")


class PromptTemplate(Enum):
    """Enumeration of available prompt templates."""
    PLANNING = "./prompts/planning.md"
    EASY_QUERIES = "./prompts/easy_queries.md"


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)


# LLM client configuration
cluster_host = os.getenv("CLUSTER_HOST")
cluster_port = os.getenv("CLUSTER_PORT")
llm = Client(host=f"http://{cluster_host}:{cluster_port}")


# Redis client configuration
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"), 
    port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")), 
    password=os.getenv("REDIS_PASSWORD", "redispassword"), 
    decode_responses=True
)

# Kafka producer configuration
kafka_producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BROKER"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    retries=5,
    retry_backoff_ms=1000,
    reconnect_backoff_ms=1000,
    reconnect_backoff_max_ms=10_000,
)

chat_history_url = os.getenv("CHAT_HISTORY_URL")


diseases = ["diabetes", "multiple-sclerosis", "hypertension"]