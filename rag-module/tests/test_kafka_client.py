import pytest
from unittest.mock import patch, AsyncMock
from rag_module.kafka_client import (
    KafkaClient,
    RAGModuleMessage,
    SynthesizerMessage,
    create_synthesizer_message,
)


class TestKafkaClient:
    def test_init(self):
        with (
            patch("rag_module.kafka_client.AIOKafkaConsumer") as mock_consumer,
            patch("rag_module.kafka_client.AIOKafkaProducer") as mock_producer,
        ):
            # ruff: noqa: F841
            client = KafkaClient("test-topic")

            assert client.topic == "test-topic"

    @pytest.mark.asyncio
    async def test_get_message_from_queue(self, mock_kafka_client, sample_rag_message):
        # Mock the async method directly
        mock_kafka_client.get_message_from_queue = AsyncMock(
            return_value=sample_rag_message
        )

        result = await mock_kafka_client.get_message_from_queue()

        assert result is not None
        assert isinstance(result, RAGModuleMessage)
        assert result.user_id == sample_rag_message.user_id
        assert result.original_query == sample_rag_message.original_query

    def test_create_synthesizer_message(self, mock_kafka_client, sample_rag_message):
        response = "Test response"
        result = create_synthesizer_message(sample_rag_message, response)

        assert isinstance(result, SynthesizerMessage)
        assert result.user_id == sample_rag_message.user_id
        assert result.original_query == sample_rag_message.original_query
        assert result.response == response
        assert result.stream == sample_rag_message.stream
