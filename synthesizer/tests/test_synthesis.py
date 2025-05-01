import pytest
from unittest.mock import patch, AsyncMock

with (
    patch("synthesizer.utilities.KafkaClient") as MockKafkaClient,
    patch("synthesizer.utilities.RedisClient") as MockRedisClient,
    patch("synthesizer.utilities.LLMClient") as MockLLMClient,
):
    from synthesizer.synthesis import generate_synthesis, synthesize_and_send_response


class TestResponseSynthesis:
    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.generate_synthesis")
    @patch("synthesizer.synthesis.send_response")
    async def test_formatting_and_synthesis(
        self, mock_send, mock_generate, complete_query_data, mock_llm_response_stream
    ):
        """Test formatting responses and calling synthesis"""
        mock_generate.return_value = mock_llm_response_stream

        await synthesize_and_send_response(complete_query_data)

        mock_generate.assert_called_once()
        query, formatted_responses, stream_flag = mock_generate.call_args[0]

        assert query == complete_query_data.original_query

        assert "### DIABETES | RESPONSE:" in formatted_responses
        assert "Diabetes is a chronic condition." in formatted_responses
        assert "### HYPERTENSION | RESPONSE:" in formatted_responses
        assert "Hypertension is high blood pressure." in formatted_responses
        assert stream_flag is True

        # Check send_response was called with correct parameters
        mock_send.assert_called_once_with(
            complete_query_data.query_id,
            complete_query_data.original_query,
            mock_llm_response_stream,
        )

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.generate_synthesis")
    @patch("synthesizer.synthesis.send_response")
    @patch("synthesizer.synthesis.logger.error")
    async def test_error_handling(
        self, mock_logger, mock_send, mock_generate, complete_query_data
    ):
        """Test error handling during synthesis"""
        mock_generate.side_effect = Exception("LLM API Error")

        await synthesize_and_send_response(complete_query_data)

        mock_generate.assert_called_once()
        assert "Error during synthesis" in mock_logger.call_args[0][0]
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.prepare_prompt")
    @patch("synthesizer.synthesis.llm.generate")
    async def test_llm_interaction(
        self, mock_llm_generate, mock_prepare_prompt, mock_llm_response_stream
    ):
        """Test interaction with LLM service"""
        async_mock = AsyncMock()
        async_mock.return_value = mock_llm_response_stream
        mock_llm_generate.return_value = async_mock()
        mock_prepare_prompt.return_value = "Formatted prompt content"

        result = await generate_synthesis(
            "What is diabetes?", "### DIABETES | RESPONSE:\nDiabetes info...", True
        )

        # Verify prompt preparation
        mock_prepare_prompt.assert_called_once()
        assert "synth_prompt.md" in mock_prepare_prompt.call_args[0][0]
        assert "What is diabetes?" in mock_prepare_prompt.call_args[1]["original_query"]
        assert (
            "### DIABETES | RESPONSE:" in mock_prepare_prompt.call_args[1]["responses"]
        )

        mock_llm_generate.assert_called_once_with(
            "Formatted prompt content", stream=True
        )

        assert result == mock_llm_response_stream
