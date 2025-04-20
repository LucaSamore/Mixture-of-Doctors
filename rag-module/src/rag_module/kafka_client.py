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

    def send_message_to_queue(
        self, chat_completion, incoming_message: RAGModuleMessage
    ) -> None:
        logger.info(f"Sending stream message to {SYNTHESIZER_TOPIC}")
        content = chat_completion.choices[0].message.content
        logger.info(f"Chat completion content: {content}")
        synthesizer_message = self.create_synthesizer_message(
            incoming_message=incoming_message, response=content
        )
        logger.info(f"Synthesizer message: {synthesizer_message}")
        key = synthesizer_message.original_query  # TODO: convert to query_id
        try:
            self.producer.send(
                topic=SYNTHESIZER_TOPIC,
                key=key,
                value=synthesizer_message.model_dump_json(),
            )
        except Exception as e:
            logger.error(f"Error sending message to synthesizer topic: {e}")
            raise
        logger.info("Message sent to synthesizer topic")

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
