from kafka import KafkaConsumer
from ollama import Client
from dotenv import load_dotenv
import os
import json
import string


load_dotenv()

consumer = KafkaConsumer(
    bootstrap_servers=os.getenv("KAFKA_BROKER"),
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
)


cluster_host = os.getenv("CLUSTER_HOST")
cluster_port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))
llm = Client(host=f"http://{cluster_host}:{cluster_port}")


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)