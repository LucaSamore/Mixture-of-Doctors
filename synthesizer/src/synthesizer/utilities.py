from kafka import KafkaConsumer

# from ollama import Client
from dotenv import load_dotenv
import redis
import os
import json
import string
from groq import Groq

load_dotenv()

consumer = KafkaConsumer(
    bootstrap_servers=os.getenv("KAFKA_BROKER"),
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    group_id="group-synthesizer",
    enable_auto_commit=False,
    auto_offset_reset="earliest",
)
consumer.subscribe(["synthesizer"])


# cluster_host = os.getenv("CLUSTER_HOST")
# cluster_port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))
llm_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)


redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
)
