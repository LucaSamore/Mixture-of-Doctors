from loguru import logger
from enum import Enum
from dotenv import load_dotenv
from kafka import KafkaProducer
from ollama import Client
import os
import json
import string

load_dotenv()


class PromptTemplate(Enum):
    PLANNING = "./orchestrator/src/orchestrator/prompts/planning.md"


logger.add("./orchestrator/logs/orchestrator.log", rotation="10 MB")

host = os.getenv("CLUSTER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))

llm = Client(host=f"http://{host}:{port}")

producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BROKER"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)


def build_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)
