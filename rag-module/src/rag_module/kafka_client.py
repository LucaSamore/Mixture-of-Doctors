from kafka import KafkaConsumer, KafkaProducer
import os
import json
from pydantic import BaseModel
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

type Query = str

SYNTHESIZER_TOPIC = "synthesizer"
DOMAIN = os.environ.get("RAG_DOMAIN", "neurological")


class RAGModuleMessage(BaseModel):
    user_id: str
    original_query: str
    rag_query: str
    stream: bool
    number: int
    total: int


class SynthesizerMessage(BaseModel):
    user_id: str
    disease: str
    original_query: str
    response: str
    stream: bool
    number: int
    total: int


class KafkaClient:
    def __init__(self):
        self.topic = os.getenv("KAFKA_CONSUMER_TOPIC", "rag-module-disease")
        if "disease" not in self.topic:
            raise ValueError("Invalid consumer topic format")
        else:
            self.topic = self.topic.replace("disease", DOMAIN)

        self.consumer = KafkaConsumer(
            bootstrap_servers=os.getenv("KAFKA_BROKER"),
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        self.consumer.subscribe([self.topic])

        self.producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BROKER"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            retries=5,
            retry_backoff_ms=1000,
            reconnect_backoff_ms=1000,
            reconnect_backoff_max_ms=10_000,
        )

    def get_message_from_queue(self) -> RAGModuleMessage | None:
        logger.info(f"Reading message from {self.topic}")
        for msg in self.consumer:
            return RAGModuleMessage.model_validate_json(msg.value)
        return None

    def send_message_to_queue(self, stream, incoming_message: RAGModuleMessage) -> None:
        logger.info(f"Sending stream message to {SYNTHESIZER_TOPIC}")
        for chunk in stream:
            content = chunk.choices[0].delta.content
            synthesizer_message = self.create_synthesizer_message(
                incoming_message=incoming_message, response=content
            )
            key = synthesizer_message.original_query  # TODO: convert to query_id
            self.producer.send(
                SYNTHESIZER_TOPIC, key, synthesizer_message.model_dump_json()
            )

    def create_synthesizer_message(
        self, incoming_message: RAGModuleMessage, response: str
    ) -> SynthesizerMessage:
        return SynthesizerMessage(
            user_id=incoming_message.user_id,
            disease=DOMAIN,
            original_query=incoming_message.original_query,
            response=response,
            stream=True,
            number=incoming_message.number,
            total=incoming_message.total,
        )
