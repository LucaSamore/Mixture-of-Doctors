from kafka import KafkaConsumer
from ollama import Client
from dotenv import load_dotenv
import redis
import os
import json
import string


load_dotenv()

consumer = KafkaConsumer(
    bootstrap_servers=os.getenv("KAFKA_BROKER"),
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    group_id="group-synthesizer",
    enable_auto_commit=False,
)
consumer.subscribe(["synthesizer"])


cluster_host = os.getenv("CLUSTER_HOST")
cluster_port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))
llm = Client(host=f"http://{cluster_host}:{cluster_port}")


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)


redis_password = os.getenv("REDIS_PASSWORD")
redis_port = (lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT"))
redis_client = redis.Redis(
    host="localhost", port=redis_port, password=redis_password, decode_responses=True
)
