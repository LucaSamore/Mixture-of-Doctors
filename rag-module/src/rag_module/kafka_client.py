from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import BaseModel
from loguru import logger
from typing import TypeAlias, Optional
from datetime import datetime
from dotenv import load_dotenv
import os
import json

load_dotenv()

Query: TypeAlias = str

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
SYNTHESIZER_TOPIC = os.environ.get("KAFKA_PRODUCER_TOPIC")
DOMAIN = os.environ.get("RAG_DOMAIN", "")


class RAGModuleMessage(BaseModel):
    user_id: str
    query_id: str
    original_query: str
    rag_query: str
    stream: bool
    number: int
    total: int
    plain_text: bool = False


class SynthesizerMessage(BaseModel):
    user_id: str
    query_id: str
    disease: str
    original_query: str
    response: str
    stream: bool
    number: int
    total: int
    plain_text: bool = False


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def create_synthesizer_message(
    incoming_message: RAGModuleMessage, response: str
) -> SynthesizerMessage:
    return SynthesizerMessage(
        user_id=incoming_message.user_id,
        query_id=incoming_message.query_id,
        disease=DOMAIN,
        original_query=incoming_message.original_query,
        response=response,
        stream=True,
        number=incoming_message.number,
        total=incoming_message.total,
        plain_text=incoming_message.plain_text,
    )


class KafkaClient:
    consumer: AIOKafkaConsumer
    producer: AIOKafkaProducer

    def __init__(self, topic: str):
        self.topic = topic

    @classmethod
    async def create(cls):
        topic = f"rag-module-{DOMAIN}"
        self = cls(topic)
        await self._setup_consumer()
        await self._setup_producer()
        return self

    async def get_message_from_queue(self) -> Optional[RAGModuleMessage]:
        logger.info(f"Reading message from {self.topic}")
        try:
            """
            msg = await self.consumer.getone()
            logger.info(f"Message received: {msg.value}")
            return RAGModuleMessage.model_validate(msg.value)
            """
            async for msg in self.consumer:
                return RAGModuleMessage.model_validate(msg.value)
        except Exception as e:
            logger.error(f"Error reading message from Kafka: {str(e)}")
        return None

    async def send_message_to_queue(
        self, chat_completion, incoming_message: RAGModuleMessage
    ) -> None:
        if not SYNTHESIZER_TOPIC:
            logger.error("KAFKA_PRODUCER_TOPIC environment variable not set")
            raise ValueError("KAFKA_PRODUCER_TOPIC environment variable not set")
        logger.info(f"Sending stream message to {SYNTHESIZER_TOPIC}")
        try:
            content = chat_completion.choices[0].message.content
            logger.info(f"Chat completion content: {content}")
            synthesizer_message = create_synthesizer_message(incoming_message, content)
            logger.info(f"Synthesizer message: {synthesizer_message}")
            await self.producer.send_and_wait(
                topic=SYNTHESIZER_TOPIC,
                key=incoming_message.query_id,
                value=synthesizer_message.model_dump(),
            )
            logger.info(
                f"Message sent to synthesizer topic with query_id: {incoming_message.query_id}"
            )
        except Exception as e:
            logger.error(f"Error sending message to Kafka: {e}")
            raise

    async def _setup_consumer(self) -> None:
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await self.consumer.start()
        logger.info("Kafka consumer initialized")
        logger.info(f"Kafka consumer subscribed to topic: {self.topic}")

    async def _setup_producer(self) -> None:
        def value_serializer(v):
            return json.dumps(v, cls=DateTimeEncoder).encode("utf-8")

        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            key_serializer=str.encode,
            value_serializer=value_serializer,
        )
        await self.producer.start()
        logger.info("Kafka producer initialized")
