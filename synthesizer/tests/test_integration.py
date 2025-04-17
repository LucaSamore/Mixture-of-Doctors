import pytest
from unittest.mock import patch

with (
    patch("synthesizer.utilities.KafkaClient") as MockKafkaClient,
    patch("synthesizer.utilities.RedisClient") as MockRedisClient,
    patch("synthesizer.utilities.LLMClient") as MockLLMClient,
):
    from synthesizer.synthesis import handle_response, RagResponse, send_response


class TestIntegrationFlow:
    """End-to-end test flows for the synthesizer component"""

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.prepare_prompt")
    @patch("synthesizer.synthesis.redis.stream_message")
    @patch("synthesizer.synthesis.llm.generate")
    async def test_complete_synthesis_flow(
        self,
        mock_llm_generate,
        mock_redis_stream,
        mock_prepare_prompt,
        mock_llm_response_stream,
        sample_rag_response,
        reset_active_queries,
    ):
        """Test full flow from receiving responses to synthesis to streaming"""
        mock_prepare_prompt.return_value = "Formatted prompt"
        mock_llm_generate.return_value = (
            await mock_llm_response_stream()
        )  # Use the result of calling the mock

        # First response
        await handle_response(sample_rag_response)

        mock_prepare_prompt.assert_not_called()
        mock_llm_generate.assert_not_called()
        mock_redis_stream.assert_not_called()

        second_response = RagResponse(
            user_id="test_user",
            disease="hypertension",
            original_query="What is diabetes?",
            response="Hypertension is high blood pressure.",
            stream=True,
            number=2,
            total=2,
        )

        await handle_response(second_response)

        mock_prepare_prompt.assert_called_once()
        assert "synth_prompt.md" in mock_prepare_prompt.call_args[0][0]

        mock_llm_generate.assert_called_once()

        await send_response(
            second_response.user_id,
            second_response.original_query,
            await mock_llm_response_stream(),
        )

        assert mock_redis_stream.call_count == 2

        first_call = mock_redis_stream.call_args_list[0]
        assert first_call[1]["stream_id"] == "test_user"
        assert first_call[1]["fields"]["query"] == "What is diabetes?"
        assert first_call[1]["fields"]["response"] == "Diabetes is "
        assert first_call[1]["fields"]["done"] == "False"

        final_call = mock_redis_stream.call_args_list[1]
        assert final_call[1]["fields"]["response"] == "a chronic condition."
        assert final_call[1]["fields"]["done"] == "True"

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
            user_id="test_user",
            disease="hypertension",
            response="Hypertension information",
            original_query="What is diabetes?",
            stream=True,
            number=2,
            total=2,
        )

        await handle_response(second_response)

        mock_kafka_commit.assert_called_once()

        # Should log error
        mock_logger.assert_called_once()
        assert "Error during synthesis" in mock_logger.call_args[0][0]
