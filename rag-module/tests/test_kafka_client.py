from unittest.mock import MagicMock, patch
from rag_module.kafka_client import KafkaClient, RAGModuleMessage, SynthesizerMessage


class TestKafkaClient:
    def test_init(self):
        with (
            patch("rag_module.kafka_client.KafkaConsumer") as mock_consumer,
            patch("rag_module.kafka_client.KafkaProducer") as mock_producer,
        ):
            mock_consumer.assert_called_once()
            mock_producer.assert_called_once()
            assert mock_consumer.return_value.subscribe.called

    def test_get_message_from_queue(self, mock_kafka_client, sample_rag_message):
        mock_kafka_client.consumer.poll = MagicMock(
            return_value={
                "topic": [MagicMock(value=sample_rag_message.model_dump_json())]
            }
        )
        original_method = KafkaClient.get_message_from_queue
        mock_kafka_client.get_message_from_queue = lambda: original_method(
            mock_kafka_client
        )

        message_mock = MagicMock()
        message_mock.value = sample_rag_message.model_dump_json()
        mock_kafka_client.consumer.__iter__ = MagicMock(
            return_value=iter([message_mock])
        )

        result = mock_kafka_client.get_message_from_queue()
        assert result is not None
        assert isinstance(result, RAGModuleMessage)
        assert result.user_id == sample_rag_message.user_id
        assert result.original_query == sample_rag_message.original_query

    def test_create_synthesizer_message(self, mock_kafka_client, sample_rag_message):
        response = "Test response"
        result = mock_kafka_client.create_synthesizer_message(
            sample_rag_message, response
        )

        assert isinstance(result, SynthesizerMessage)
        assert result.user_id == sample_rag_message.user_id
        assert result.original_query == sample_rag_message.original_query
        assert result.response == response
        assert result.stream == sample_rag_message.stream
