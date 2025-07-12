from aiokafka import AIOKafkaConsumer
from loguru import logger
from groq import AsyncGroq
from dotenv import load_dotenv
import redis.asyncio as redis
import os
import json
import string


load_dotenv()


async def init_kafka_consumer() -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        os.getenv("KAFKA_TOPIC", "synthesizer"),
        bootstrap_servers=os.getenv("KAFKA_BROKER", "localhost:9092"),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id=os.getenv("KAFKA_CONSUMER_GROUP", "group-synthesizer"),
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )


async def init_redis_client() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD"),
        decode_responses=True,
    )


async def init_groq_client() -> AsyncGroq:
    return AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


def prepare_prompt(template_path: str, **kwargs: str) -> str:
    try:
        with open(template_path, "r") as file:
            content = file.read()
        return string.Template(content).substitute(kwargs)
    except Exception as e:
        logger.error(f"Error while preparing prompt: {e}")
        return ""
