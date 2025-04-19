from kafka import KafkaConsumer, KafkaProducer
import os
import json
from pydantic import BaseModel
from loguru import logger
from typing import TypeAlias

Query: TypeAlias = str

SYNTHESIZER_TOPIC = os.environ.get("KAFKA_PRODUCER_TOPIC")
DOMAIN = os.environ.get("RAG_DOMAIN", "")


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
        self.topic = f"rag-module-{DOMAIN}"
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
            return RAGModuleMessage.model_validate(msg.value)
        return None

    async def send_message_to_queue(
        self, stream, incoming_message: RAGModuleMessage
    ) -> None:
        logger.info(f"Sending stream message to {SYNTHESIZER_TOPIC}")
        async for chunk in stream:
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
