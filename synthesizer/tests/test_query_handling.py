import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from synthesizer.synthesis import RAGResponse

# Import with mocks to prevent actual client instantiation
with (
    patch("aiokafka.AIOKafkaConsumer", MagicMock()),
    patch("groq.AsyncGroq", MagicMock()),
    patch("redis.asyncio.Redis", MagicMock()),
):
    from synthesizer.synthesis import handle_response, is_query_complete, active_queries


# Import with mocks to prevent actual client instantiation
with (
    patch("aiokafka.AIOKafkaConsumer", MagicMock()),
    patch("groq.AsyncGroq", MagicMock()),
    patch("redis.asyncio.Redis", MagicMock()),
):
    from synthesizer.synthesis import handle_response, is_query_complete, active_queries


class TestQueryTracking:
    """Tests for tracking incoming responses and user queries"""

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.synthesize_and_send_response")
    async def test_first_response_tracking(self, mock_synthesize, sample_rag_response):
        """Test that first response is correctly tracked in active queries"""
        mock_kafka_consumer = MagicMock()
        mock_kafka_consumer.commit = AsyncMock()
        mock_redis_client = MagicMock()
        mock_groq_client = MagicMock()

        await handle_response(
            sample_rag_response,
            mock_kafka_consumer,
            mock_redis_client,
            mock_groq_client,
        )

        assert "test_query_id" in active_queries
        assert "diabetes" in active_queries["test_query_id"].responses
        assert active_queries["test_query_id"].received_numbers == {1}
        assert active_queries["test_query_id"].total == 2

        mock_synthesize.assert_not_called()
        mock_kafka_consumer.commit.assert_not_called()

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.synthesize_and_send_response")
    async def test_full_response_set_triggers_synthesis(
        self, mock_synthesize, sample_rag_response
    ):
        """Test that completing full response set triggers synthesis"""
        mock_kafka_consumer = MagicMock()
        mock_kafka_consumer.commit = AsyncMock()
        mock_redis_client = MagicMock()
        mock_groq_client = MagicMock()

        # First response
        await handle_response(
            sample_rag_response,
            mock_kafka_consumer,
            mock_redis_client,
            mock_groq_client,
        )
        query_id = sample_rag_response.query_id

        # Second response completes the set
        second_response = RAGResponse(
            user_id=sample_rag_response.user_id,
            query_id=query_id,
            disease="hypertension",
            original_query=sample_rag_response.original_query,
            response="Hypertension often coexists with diabetes.",
            stream=True,
            number=2,
            total=2,
        )
        await handle_response(
            second_response, mock_kafka_consumer, mock_redis_client, mock_groq_client
        )

        mock_kafka_consumer.commit.assert_called_once()
        mock_synthesize.assert_called_once()

        # Check cleanup occurred
        assert "test_query_id" not in active_queries

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.synthesize_and_send_response")
    async def test_duplicate_response_handling(
        self, mock_synthesize, sample_rag_response
    ):
        """Test handling of duplicate response numbers"""
        mock_kafka_consumer = MagicMock()
        mock_kafka_consumer.commit = AsyncMock()
        mock_redis_client = MagicMock()
        mock_groq_client = MagicMock()

        await handle_response(
            sample_rag_response,
            mock_kafka_consumer,
            mock_redis_client,
            mock_groq_client,
        )
        query_id = sample_rag_response.query_id

        # Duplicate response with same number
        duplicate = RAGResponse(
            user_id=sample_rag_response.user_id,
            query_id=query_id,
            disease="diabetes",
            original_query=sample_rag_response.original_query,
            response="Updated diabetes information.",
            stream=True,
            number=1,
            total=2,
        )

        await handle_response(
            duplicate, mock_kafka_consumer, mock_redis_client, mock_groq_client
        )

        # Should still be waiting for response #2
        assert active_queries["test_query_id"].received_numbers == {1}
        mock_synthesize.assert_not_called()
        mock_kafka_consumer.commit.assert_not_called()


class TestQueryCompletion:
    """Tests for query completion verification"""

    def test_identifies_incomplete_response_set(self, incomplete_query_data):
        """Test detection of incomplete response sets"""
        result = is_query_complete(incomplete_query_data)
        assert result is False

    def test_identifies_complete_response_set(self, complete_query_data):
        """Test detection of complete response sets"""
        result = is_query_complete(complete_query_data)
        assert result is True
