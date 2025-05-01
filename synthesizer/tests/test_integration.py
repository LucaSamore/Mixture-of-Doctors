import pytest
from unittest.mock import patch

with (
    patch("synthesizer.utilities.KafkaClient") as MockKafkaClient,
    patch("synthesizer.utilities.RedisClient") as MockRedisClient,
    patch("synthesizer.utilities.LLMClient") as MockLLMClient,
):
    from synthesizer.synthesis import (
        RagResponse,
        ChatbotQuery,
        handle_response,
    )


class TestIntegrationFlow:
    """End-to-end test flows for the synthesizer component"""

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.redis.stream_message")
    @patch("synthesizer.synthesis.generate_synthesis")
    async def test_complete_synthesis_flow(
        self,
        mock_generate_synthesis,
        mock_redis_stream,
        mock_llm_response_stream,
        reset_active_queries,
    ):
        """Test the full synthesis flow from multiple disease-specific responses to a combined answer"""
        # Configure the mock to simulate LLM response streaming
        mock_generate_synthesis.return_value = await mock_llm_response_stream()

        # Create a sample query and response
        original_query = "What is diabetes and hypertension?"
        query_id = "test_query_id"

        # Create the first response (for diabetes)
        diabetes_response = RagResponse(
            chatbot_query=ChatbotQuery(user_id="test_user", query=original_query),
            query_id=query_id,
            disease="diabetes",
            original_query=original_query,
            response="Diabetes is a chronic condition that affects how your body processes blood sugar.",
            stream=True,
            number=1,
            total=2,
        )
        await handle_response(diabetes_response)

        # Verify that the response was not sent to synthesis yet
        mock_generate_synthesis.assert_not_called()
        mock_redis_stream.assert_not_called()

        hypertension_response = RagResponse(
            chatbot_query=ChatbotQuery(user_id="test_user", query=original_query),
            query_id=query_id,
            disease="hypertension",
            original_query=original_query,
            response="Hypertension, or high blood pressure, is a condition where blood pressure is consistently too high.",
            stream=True,
            number=2,
            total=2,
        )
        await handle_response(hypertension_response)

        mock_generate_synthesis.assert_called_once()

        # Verify that the synthesis response was sent to Redis for both chunks
        assert mock_redis_stream.call_count == 2

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.llm.generate")
    @patch("synthesizer.synthesis.kafka.commit")
    @patch("synthesizer.synthesis.logger.error")
    async def test_error_recovery(
        self,
        mock_logger,
        mock_kafka_commit,
        mock_llm_generate,
        sample_rag_response,
        reset_active_queries,
    ):
        """Test recovery from LLM errors during integration flow"""
        mock_llm_generate.side_effect = Exception("LLM API error")

        await handle_response(sample_rag_response)

        second_response = RagResponse(
            chatbot_query=ChatbotQuery(user_id="test_user", query="What is diabetes?"),
            query_id="test_query_id",
            disease="hypertension",
            original_query="What is diabetes?",
            response="Hypertension is high blood pressure.",
            stream=True,
            number=2,
            total=2,
        )

        await handle_response(second_response)

        mock_kafka_commit.assert_called_once()

        # Should log error
        assert mock_logger.call_count == 2
        assert "Error generating synthesis" in mock_logger.call_args_list[0][0][0]
        assert "Error during synthesis" in mock_logger.call_args_list[1][0][0]
