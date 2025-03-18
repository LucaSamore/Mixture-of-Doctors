from loguru import logger
from enum import Enum
from dotenv import load_dotenv
from kafka import KafkaProducer
from ollama import Client
import os
import json
import string
import redis

load_dotenv()


class PromptTemplate(Enum):
    PLANNING = "./prompts/planning.md"
    EASY_QUERIES = "./prompts/easy_queries.md"


logger.add("/app/logs/orchestrator.log", rotation="10 MB")


cluster_host = os.getenv("CLUSTER_HOST")
cluster_port = os.getenv("CLUSTER_PORT", 11434)
llm = Client(host=f"http://{cluster_host}:{cluster_port}")


redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = (lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT"))
redis_password = os.getenv("REDIS_PASSWORD")
redis_client = redis.Redis(
    host=redis_host, port=redis_port, password=redis_password, decode_responses=True
)


producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BROKER"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

chat_history_url = os.getenv("CHAT_HISTORY_URL", "http://localhost:8089")

# should read from config.json
diseases = ["diabetes", "multiple sclerosis", "hypertension"]


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)
