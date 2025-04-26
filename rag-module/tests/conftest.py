import pytest
from unittest.mock import MagicMock, patch

patch("kafka.KafkaConsumer", MagicMock()).start()
patch("kafka.KafkaProducer", MagicMock()).start()
patch("groq.Groq", MagicMock()).start()
patch("redis.Redis", MagicMock()).start()
patch("qdrant_client.QdrantClient", MagicMock()).start()

# ruff: noqa: E402
from datetime import datetime
from rag_module.kafka_client import RAGModuleMessage, SynthesizerMessage
from rag_module.rag_process import ConversationItem


@pytest.fixture
def mock_kafka_client():
    from rag_module.kafka_client import KafkaClient

    with (
        patch("rag_module.kafka_client.KafkaConsumer"),
        patch("rag_module.kafka_client.KafkaProducer"),
    ):
        client = KafkaClient()
        client.get_message_from_queue = MagicMock()
        client.send_message_to_queue = MagicMock()
        yield client


@pytest.fixture
def sample_rag_message():
    return RAGModuleMessage(
        user_id="test_user_123",
        query_id="test_query_id_456",
        original_query="What are the symptoms of multiple sclerosis?",
        rag_query="Symptoms of multiple sclerosis",
        stream=True,
        number=1,
        total=1,
    )


@pytest.fixture
def sample_synthesizer_message(sample_rag_message):
    return SynthesizerMessage(
        user_id=sample_rag_message.user_id,
        query_id=sample_rag_message.query_id,
        disease="neurological",
        original_query=sample_rag_message.original_query,
        response="Symptoms of multiple sclerosis include...",
        stream=True,
        number=sample_rag_message.number,
        total=sample_rag_message.total,
    )


@pytest.fixture
def sample_conversation_items():
    return [
        ConversationItem(
            question="What are the symptoms of multiple sclerosis?",
            answer="The main symptoms include fatigue, vision problems, weakness...",
            timestamp=datetime.now(),
        ),
        ConversationItem(
            question="How is multiple sclerosis diagnosed?",
            answer="Diagnosis is made through neurological testing, MRI...",
            timestamp=datetime.now(),
        ),
    ]


@pytest.fixture
def mock_qdrant_client():
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_groq_client():
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_redis_client():
    mock = MagicMock()
    return mock
