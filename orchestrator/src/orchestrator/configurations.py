import json
import os
import string

from enum import Enum

import sys
import redis
from groq import Groq
from typing import List
from kafka import KafkaProducer
from loguru import logger

is_test = "pytest" in sys.modules

if is_test:
    from dotenv import load_dotenv

    load_dotenv()
    CONFIG_FILE_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "config.json"
    )
    LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_FILE_PATH = os.path.join(LOG_DIR, "orchestrator.log")
else:
    CONFIG_FILE_PATH = "/app/config.json"
    LOG_FILE_PATH = "/app/logs/orchestrator.log"

logger.add(LOG_FILE_PATH, rotation="10 MB")


def get_diseases_from_config_file() -> List[str]:
    try:
        with open(CONFIG_FILE_PATH, "r") as f:
            config = json.load(f)
        return config["rag_modules"]
    except FileNotFoundError:
        # Fallback for tests if config file doesn't exist
        if is_test:
            return ["diabetes", "multiple-sclerosis", "hypertension"]
        raise


class PromptTemplate(Enum):
    """Enumeration of available prompt templates."""

    PLANNING = "./prompts/planning.md"
    EASY_QUERIES = "./prompts/easy_queries.md"


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)


# LLM client configuration (ollama)
"""
cluster_host = os.getenv("CLUSTER_HOST")
cluster_port = os.getenv("CLUSTER_PORT")
llm = Client(host=f"http://{cluster_host}:{cluster_port}")
"""


# LLM client configuration (groq)
llm_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))


# Redis client configuration
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD", "redispassword"),
    decode_responses=True,
)

# Kafka producer configuration
if is_test:
    kafka_producer = None
else:
    kafka_producer = KafkaProducer(
        bootstrap_servers=os.getenv("KAFKA_BROKER"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        retries=5,
        retry_backoff_ms=1000,
        reconnect_backoff_ms=1000,
        reconnect_backoff_max_ms=10_000,
    )


chat_history_url = os.getenv("CHAT_HISTORY_URL")
