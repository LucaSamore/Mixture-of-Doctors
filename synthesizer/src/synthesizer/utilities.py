from kafka import KafkaConsumer

# from ollama import Client
from loguru import logger
from groq import Groq
from dotenv import load_dotenv
from typing import Any, Dict
import redis
import os
import json
import string

load_dotenv()


class KafkaClient:
    def __init__(self, topic="synthesizer", group_id="group-synthesizer"):
        self.consumer = KafkaConsumer(
            bootstrap_servers=os.getenv("KAFKA_BROKER"),
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            group_id=group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        self.consumer.subscribe([topic])
        logger.info(f"Kafka consumer initialized for topic: {topic}")

    def get_consumer(self) -> KafkaConsumer:
        return self.consumer

    def commit(self) -> bool:
        try:
            self.consumer.commit()
            return True
        except Exception as e:
            logger.error(f"Error committing offsets: {e}")
            return False

    def close(self) -> None:
        self.consumer.close()


class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True,
        )
        logger.info("Redis client initialized")

    def stream_message(self, stream_id: str, fields: Dict[str, Any]) -> None:
        self.client.xadd(name=stream_id, fields=fields)  # type: ignore


# cluster_host = os.getenv("CLUSTER_HOST")
# cluster_port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))
class LLMClient:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"
        logger.info(f"LLM client initialized with model: {self.model}")

    async def generate(self, prompt: str, stream: bool = True) -> Any:
        return self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt}],
            stream=stream,
        )


def prepare_prompt(template_path: str, **kwargs: str) -> str:
    with open(template_path, "r") as file:
        content = file.read()
    return string.Template(content).substitute(kwargs)
