import pytest
from unittest.mock import MagicMock, patch, AsyncMock

with (
    patch("aiokafka.AIOKafkaConsumer") as MockKafkaConsumer,
    patch("redis.asyncio.Redis") as MockRedisClient,
    patch("groq.AsyncGroq") as MockGroqClient,
):
    from synthesizer.synthesis import (
        RAGResponse,
        handle_response,
    )


class TestIntegrationFlow:
    """End-to-end test flows for the synthesizer component"""

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.send_response")
    @patch("synthesizer.synthesis.synthesize")
    async def test_complete_synthesis_flow(
        self,
        mock_synthesize,
        mock_send_response,
        reset_active_queries,
    ):
        """Test the full synthesis flow from multiple disease-specific responses to a combined answer"""
        # Configure the mock to simulate LLM response streaming
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [
            MagicMock(delta=MagicMock(content="Diabetes is "), finish_reason=None)
        ]

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [
            MagicMock(
                delta=MagicMock(content="a chronic condition."), finish_reason="stop"
            )
        ]

        mock_synthesize.return_value = [mock_chunk1, mock_chunk2]

        # Setup mock clients
        mock_kafka_consumer = MagicMock()
        mock_kafka_consumer.commit = AsyncMock()
        mock_redis_client = MagicMock()
        mock_groq_client = MagicMock()

        # Create a sample query and response
        original_query = "What is diabetes and hypertension?"
        query_id = "test_query_id"

        # Create the first response (for diabetes)
        diabetes_response = RAGResponse(
            user_id="test_user",
            query_id=query_id,
            disease="diabetes",
            original_query=original_query,
            response="Diabetes is a chronic condition that affects how your body processes blood sugar.",
            stream=True,
            number=1,
            total=2,
        )
        await handle_response(
            diabetes_response, mock_kafka_consumer, mock_redis_client, mock_groq_client
        )

        # Verify that the response was not sent to synthesis yet
        mock_synthesize.assert_not_called()
        mock_send_response.assert_not_called()

        hypertension_response = RAGResponse(
            user_id="test_user",
            query_id=query_id,
            disease="hypertension",
            original_query=original_query,
            response="Hypertension, or high blood pressure, is a condition where blood pressure is consistently too high.",
            stream=True,
            number=2,
            total=2,
        )
        await handle_response(
            hypertension_response,
            mock_kafka_consumer,
            mock_redis_client,
            mock_groq_client,
        )

        mock_synthesize.assert_called_once()
        mock_send_response.assert_called_once()

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.synthesize_and_send_response")
    @patch("synthesizer.synthesis.logger.error")
    async def test_error_recovery(
        self,
        mock_logger,
        mock_synthesize_and_send,
        sample_rag_response,
        reset_active_queries,
    ):
        """Test recovery from LLM errors during integration flow"""
        # Mock the function to not raise an exception, just log the error
        mock_synthesize_and_send.return_value = None

        # Setup mock clients
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

        second_response = RAGResponse(
            user_id="test_user",
            query_id="test_query_id",
            disease="hypertension",
            original_query="What is diabetes?",
            response="Hypertension is high blood pressure.",
            stream=True,
            number=2,
            total=2,
        )

        await handle_response(
            second_response, mock_kafka_consumer, mock_redis_client, mock_groq_client
        )

        mock_kafka_consumer.commit.assert_called_once()
        mock_synthesize_and_send.assert_called_once()
