from kafka import KafkaConsumer, KafkaProducer
import os
import json
from pydantic import BaseModel
from loguru import logger
from typing import TypeAlias, Optional
import uuid
from dotenv import load_dotenv

load_dotenv()

Query: TypeAlias = str

KAFKA_BROKER = os.getenv("KAFKA_BROKER")
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
    DEFAULT_RETRY_ATTEMPTS = 5
    DEFAULT_RETRY_BACKOFF_MS = 1000
    DEFAULT_RECONNECT_BACKOFF_MS = 1000
    DEFAULT_RECONNECT_BACKOFF_MAX_MS = 10_000

    def __init__(self):
        self.topic = f"rag-module-{DOMAIN}"
        self._setup_consumer()
        self._setup_producer()

    def _setup_consumer(self) -> None:
        if not KAFKA_BROKER:
            logger.error("KAFKA_BROKER environment variable not set")
            raise ValueError("KAFKA_BROKER environment variable not set")

        self.consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        self.consumer.subscribe([self.topic])
        logger.info(f"Kafka consumer subscribed to topic: {self.topic}")

    def _setup_producer(self) -> None:
        if not KAFKA_BROKER:
            logger.error("KAFKA_BROKER environment variable not set")
            raise ValueError("KAFKA_BROKER environment variable not set")

        # Use custom encoder for JSON serialization that can handle datetime objects
        def value_serializer(v):
            from rag_module.rag_process import DateTimeEncoder

            return json.dumps(v, cls=DateTimeEncoder).encode("utf-8")

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            key_serializer=str.encode,
            value_serializer=value_serializer,
            retries=self.DEFAULT_RETRY_ATTEMPTS,
            retry_backoff_ms=self.DEFAULT_RETRY_BACKOFF_MS,
            reconnect_backoff_ms=self.DEFAULT_RECONNECT_BACKOFF_MS,
            reconnect_backoff_max_ms=self.DEFAULT_RECONNECT_BACKOFF_MAX_MS,
        )
        logger.info("Kafka producer initialized")

    def get_message_from_queue(self) -> Optional[RAGModuleMessage]:
        logger.info(f"Reading message from {self.topic}")
        try:
            for msg in self.consumer:
                return RAGModuleMessage.model_validate(msg.value)
        except Exception as e:
            logger.error(f"Error reading message from Kafka: {str(e)}")
        return None

    def send_message_to_queue(
        self, chat_completion, incoming_message: RAGModuleMessage
    ) -> None:
        if not SYNTHESIZER_TOPIC:
            logger.error("KAFKA_PRODUCER_TOPIC environment variable not set")
            raise ValueError("KAFKA_PRODUCER_TOPIC environment variable not set")

        logger.info(f"Sending stream message to {SYNTHESIZER_TOPIC}")

        try:
            content = chat_completion.choices[0].message.content
            logger.info(f"Chat completion content: {content}")

            synthesizer_message = self.create_synthesizer_message(
                incoming_message=incoming_message, response=content
            )
            logger.info(f"Synthesizer message: {synthesizer_message}")

            query_id = str(uuid.uuid4())

            self.producer.send(
                topic=SYNTHESIZER_TOPIC,
                key=query_id,
                value=synthesizer_message.model_dump(),
            )
            logger.info(f"Message sent to synthesizer topic with query_id: {query_id}")
        except Exception as e:
            logger.error(f"Error sending message to Kafka: {str(e)}")
            raise

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
