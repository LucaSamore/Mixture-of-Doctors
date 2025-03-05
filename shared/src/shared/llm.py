from dotenv import load_dotenv
from ollama import Client
import string
import os

load_dotenv()

host = os.getenv("CLUSTER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))

llm = Client(host=f"http://{host}:{port}")


def build_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)
