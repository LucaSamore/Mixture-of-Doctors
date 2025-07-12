import pytest
from unittest.mock import patch, AsyncMock, MagicMock

with (
    patch("aiokafka.AIOKafkaConsumer") as MockKafkaConsumer,
    patch("redis.asyncio.Redis") as MockRedisClient,
    patch("groq.AsyncGroq") as MockGroqClient,
):
    from synthesizer.synthesis import synthesize, synthesize_and_send_response


with (
    patch("aiokafka.AIOKafkaConsumer") as MockKafkaConsumer,
    patch("redis.asyncio.Redis") as MockRedisClient,
    patch("groq.AsyncGroq") as MockGroqClient,
):
    from synthesizer.synthesis import (
        synthesize,
        synthesize_and_send_response,
        SYNTHESIZE_PROMPT_PATH,
    )


class TestResponseSynthesis:
    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.synthesize")
    @patch("synthesizer.synthesis.send_response")
    async def test_formatting_and_synthesis(
        self, mock_send, mock_synthesize, complete_query_data
    ):
        """Test formatting responses and calling synthesis"""
        mock_stream = MagicMock()
        mock_synthesize.return_value = mock_stream
        mock_redis_client = MagicMock()
        mock_groq_client = MagicMock()

        await synthesize_and_send_response(
            complete_query_data, mock_redis_client, mock_groq_client
        )

        mock_synthesize.assert_called_once()
        query, formatted_responses, stream_flag, plain_text_flag, groq_client = (
            mock_synthesize.call_args[0]
        )

        assert query == complete_query_data.original_query
        assert "### DIABETES | RESPONSE:" in formatted_responses
        assert "Diabetes is a chronic condition." in formatted_responses
        assert "### HYPERTENSION | RESPONSE:" in formatted_responses
        assert "Hypertension is high blood pressure." in formatted_responses
        assert stream_flag is True
        assert plain_text_flag is True

        # Check send_response was called with correct parameters
        mock_send.assert_called_once_with(
            complete_query_data.user_id,
            complete_query_data.original_query,
            mock_stream,
            mock_redis_client,
        )

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.synthesize")
    @patch("synthesizer.synthesis.send_response")
    @patch("synthesizer.synthesis.logger.error")
    async def test_error_handling(
        self, mock_logger, mock_send, mock_synthesize, complete_query_data
    ):
        """Test error handling during synthesis"""
        mock_synthesize.side_effect = Exception("LLM API Error")
        mock_redis_client = MagicMock()
        mock_groq_client = MagicMock()

        # The function should not raise an exception, but should log the error
        await synthesize_and_send_response(
            complete_query_data, mock_redis_client, mock_groq_client
        )

        mock_synthesize.assert_called_once()
        mock_send.assert_not_called()
        # Check that the error was logged
        mock_logger.assert_called_once()
        assert "Error during synthesis and response" in str(mock_logger.call_args)

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.prepare_prompt")
    async def test_llm_interaction(self, mock_prepare_prompt):
        """Test interaction with LLM service"""
        mock_groq_client = MagicMock()
        mock_completion = MagicMock()
        mock_groq_client.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        mock_prepare_prompt.return_value = "Formatted prompt content"

        result = await synthesize(
            "What is diabetes?",
            "### DIABETES | RESPONSE:\nDiabetes info...",
            True,
            True,
            mock_groq_client,
        )

        # Verify prompt preparation
        mock_prepare_prompt.assert_called_once()
        assert (
            mock_prepare_prompt.call_args.kwargs["template_path"]
            == SYNTHESIZE_PROMPT_PATH
        )
        assert (
            "What is diabetes?"
            == mock_prepare_prompt.call_args.kwargs["original_query"]
        )
        assert (
            "### DIABETES | RESPONSE:"
            in mock_prepare_prompt.call_args.kwargs["responses"]
        )
        assert (
            "plain text format" in mock_prepare_prompt.call_args.kwargs["output_format"]
        )

        mock_groq_client.chat.completions.create.assert_called_once()

        assert result == mock_completion
