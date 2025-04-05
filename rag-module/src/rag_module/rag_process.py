from .kafka_client import KafkaClient, RAGModuleMessage
from qdrant_client import QdrantClient
from qdrant_client.http.models import Payload
from sentence_transformers import SentenceTransformer
from typing import List
from loguru import logger
from datetime import datetime
from pydantic import BaseModel
import os
import json
import httpx
import string
import redis
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

PROMPT_FILE = "./prompts/rag_module.md"
DOMAIN = os.environ.get("RAG_DOMAIN", "neurological")
CHAT_HISTORY_URL = os.getenv("CHAT_HISTORY_URL")

type Query = str
type Prompt = str

kafka_client = KafkaClient()
# Vector store client configuration (qdrant)
port = (lambda p: int(p) if p else 6333)(os.getenv("QDRANT_PORT"))
qdrant_client = QdrantClient(host=os.getenv("QDRANT_HOST"), port=port)
# LLM client configuration (groq)
llm_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# Redis client configuration
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD", "redispassword"),
    decode_responses=True,
)


class ConversationItem(BaseModel):
    question: str
    answer: str
    timestamp: datetime = datetime.now()


class ConversationModel(BaseModel):
    username: str
    created_at: datetime
    conversation: List[ConversationItem]


# retrieve, augment, generate
async def handle_incoming_message() -> None:
    message = kafka_client.get_message_from_queue()
    if message is None:
        return
    else:
        embeddings = retrieve(message.rag_query)
        # Create prompt combining both user query and embeddings
        prompt = await augment(embeddings, message.rag_query, message.user_id)
        generate(prompt, message)


def retrieve(query: Query) -> List[Payload]:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_vector = model.encode(query).tolist()
    hits = qdrant_client.search(
        collection_name=f"{DOMAIN}_docs", query_vector=query_vector, limit=5
    )
    return [hit.payload for hit in hits if hit.payload is not None]


async def augment(embeddings: List[Payload], query: Query, user_id: str) -> Prompt:
    conversation = await fetch_chat_history_for_user(user_id)
    context = json.dumps([item.model_dump_json() for item in conversation], indent=4)
    logger.info(f"Context: {context}")

    extracted_embeddings = [
        {
            "title": payload.get("title"),
            "source": payload.get("source"),
            "text": payload.get("text"),
        }
        for payload in embeddings
    ]
    embeddings_context = json.dumps(extracted_embeddings, indent=4)
    logger.info(f"Embeddings Context: {embeddings_context}")

    combined_context = f"Chat History:\n{context}\n\nEmbeddings:\n{embeddings_context}"

    params = {"query": query, "context": combined_context}
    prompt = prepare_prompt(template=PROMPT_FILE, **params)
    return prompt


def generate(prompt: Prompt, incoming_message: RAGModuleMessage) -> None:
    stream = llm_groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": incoming_message.rag_query},
        ],
        model="llama-3.3-70b-versatile",
        stream=True,
    )
    if incoming_message.total == 1:
        for chunk in stream:
            content = chunk.choices[0].delta.content
            redis_client.xadd(
                name=incoming_message.user_id,
                fields={
                    "query": incoming_message.original_query,  # TODO: check it
                    "response": str(content),
                    "done": str(
                        chunk.choices[0].finish_reason
                    ),  # finish_reason will be equal to "stop" when stream is done
                },
            )
    else:
        kafka_client.send_message_to_queue(stream, incoming_message)


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)


async def fetch_chat_history_for_user(user_id: str) -> List[ConversationItem]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CHAT_HISTORY_URL}/{user_id}")
        response.raise_for_status()
        model = ConversationModel.model_validate(response.json())
    return model.conversation
