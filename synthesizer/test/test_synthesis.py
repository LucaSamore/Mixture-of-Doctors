import pytest
from unittest.mock import MagicMock, patch

with (
    patch("synthesizer.utilities.KafkaClient") as MockKafkaClient,
    patch("synthesizer.utilities.RedisClient") as MockRedisClient,
    patch("synthesizer.utilities.LLMClient") as MockLLMClient,
):
    MockKafkaClient.return_value = MagicMock()
    MockRedisClient.return_value = MagicMock()
    MockLLMClient.return_value = MagicMock()

    from synthesizer.synthesis import (
        RagResponse,
        QueryData,
        active_queries,
        handle_response,
        is_query_complete,
        synthesize_and_send_response,
        generate_synthesis,
        send_response,
    )


@pytest.fixture
def reset_active_queries():
    """Reset active queries between tests to avoid interference"""
    active_queries.clear()
    yield
    active_queries.clear()


@pytest.fixture
def sample_rag_response():
    """Create a sample response from a disease-specific RAG module"""
    return RagResponse(
        user_id="test_user",
        disease="diabetes",
        original_query="What is diabetes?",
        response="Diabetes is a chronic condition affecting blood sugar levels.",
        stream=True,
        number=1,
        total=2,
    )


@pytest.fixture
def incomplete_query_data():
    """Query data with incomplete responses"""
    return QueryData(
        user_id="test_user",
        original_query="What is diabetes?",
        responses={"diabetes": "Diabetes is a chronic condition."},
        received_numbers={1},
        total=2,
        stream=True,
    )


@pytest.fixture
def complete_query_data():
    """Query data with complete set of responses"""
    return QueryData(
        user_id="test_user",
        original_query="What is diabetes and hypertension?",
        responses={
            "diabetes": "Diabetes is a chronic condition.",
            "hypertension": "Hypertension is high blood pressure.",
        },
        received_numbers={1, 2},
        total=2,
        stream=True,
    )


@pytest.fixture
def mock_llm_response_stream():
    """Simulate a stream of responses from an LLM"""
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [
        MagicMock(delta=MagicMock(content="Diabetes is "), finish_reason=None)
    ]

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [
        MagicMock(delta=MagicMock(content="a chronic condition."), finish_reason="stop")
    ]

    return [mock_chunk1, mock_chunk2]


class TestQueryManagement:
    """Tests for user query management and tracking"""

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.synthesize_and_send_response")
    @patch("synthesizer.synthesis.kafka.commit")
    async def test_first_response_is_tracked_correctly(
        self,
        mock_kafka_commit,
        mock_synthesize,
        sample_rag_response,
        reset_active_queries,
    ):
        await handle_response(sample_rag_response)

        assert "test_user" in active_queries
        assert "diabetes" in active_queries["test_user"].responses
        assert active_queries["test_user"].received_numbers == {1}

        mock_synthesize.assert_not_called()
        mock_kafka_commit.assert_not_called()

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.synthesize_and_send_response")
    @patch("synthesizer.synthesis.kafka.commit")
    async def test_final_response_triggers_synthesis_and_cleanup(
        self,
        mock_kafka_commit,
        mock_synthesize,
        sample_rag_response,
        reset_active_queries,
    ):
        # First response
        await handle_response(sample_rag_response)

        second_response = RagResponse(
            user_id="test_user",
            disease="hypertension",
            original_query="What is diabetes?",
            response="Hypertension often coexists with diabetes.",
            stream=True,
            number=2,
            total=2,
        )

        await handle_response(second_response)

        mock_kafka_commit.assert_called_once()
        mock_synthesize.assert_called_once()
        assert "test_user" not in active_queries


class TestQueryCompletion:
    """Tests for query completion verification"""

    def test_identifies_incomplete_response_set(self, incomplete_query_data):
        result = is_query_complete(incomplete_query_data)
        assert result is False

    def test_identifies_complete_response_set(self, complete_query_data):
        result = is_query_complete(complete_query_data)
        assert result is True


class TestResponseSynthesis:
    """Tests for synthesizing responses from multiple sources"""

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.generate_synthesis")
    @patch("synthesizer.synthesis.send_response")
    async def test_formatting_and_synthesis_of_responses(
        self, mock_send, mock_generate, complete_query_data, mock_llm_response_stream
    ):
        mock_generate.return_value = mock_llm_response_stream

        await synthesize_and_send_response(complete_query_data)

        mock_generate.assert_called_once()
        _, formatted_responses, _ = mock_generate.call_args[0]

        assert "### DIABETES | RESPONSE:" in formatted_responses
        assert "### HYPERTENSION | RESPONSE:" in formatted_responses

        mock_send.assert_called_once_with(
            complete_query_data.user_id,
            complete_query_data.original_query,
            mock_llm_response_stream,
        )

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.generate_synthesis")
    @patch("synthesizer.synthesis.send_response")
    async def test_error_handling_during_synthesis(
        self, mock_send, mock_generate, complete_query_data
    ):
        """Verify error handling during the synthesis process"""
        mock_generate.side_effect = Exception("LLM API Error")

        await synthesize_and_send_response(complete_query_data)

        mock_generate.assert_called_once()
        mock_send.assert_not_called()


class TestLLMInteraction:
    """Tests for interaction with the LLM service"""

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.prepare_prompt")
    @patch("synthesizer.synthesis.llm.generate")
    async def test_llm_call_and_result(
        self, mock_llm_generate, mock_prepare_prompt, mock_llm_response_stream
    ):
        async def mock_generate(*args, **kwargs):
            return mock_llm_response_stream

        mock_llm_generate.side_effect = mock_generate

        mock_prepare_prompt.return_value = "Input of llm generator (prompt content)"

        result = await generate_synthesis(
            "What is diabetes and hypertension?",
            "### DIABETES | RESPONSE:\nDiabets ...",
            True,
        )

        mock_prepare_prompt.assert_called_once()
        assert "synth_prompt.md" in mock_prepare_prompt.call_args[0][0]
        assert (
            "What is diabetes and hypertension?"
            in mock_prepare_prompt.call_args[1]["original_query"]
        )
        assert (
            "### DIABETES | RESPONSE:\nDiabets ..."
            in mock_prepare_prompt.call_args[1]["responses"]
        )

        mock_llm_generate.assert_called_once_with(
            "Input of llm generator (prompt content)", stream=True
        )

        assert result == mock_llm_response_stream


class TestRedisStreaming:
    """Tests for streaming results to Redis"""

    @pytest.mark.asyncio
    @patch("synthesizer.synthesis.redis.stream_message")
    async def test_streaming_responses_to_redis(
        self, mock_redis_stream, mock_llm_response_stream
    ):
        user_id = "test_user"
        query = "What is diabetes?"

        await send_response(user_id, query, mock_llm_response_stream)

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
    @patch("synthesizer.synthesis.redis.stream_message")
    async def test_handling_empty_content_in_stream(self, mock_redis_stream):
        empty_chunk = MagicMock()
        empty_chunk.choices = [
            MagicMock(delta=MagicMock(content=None), finish_reason=None)
        ]

        await send_response("test_user", "What is diabetes?", [empty_chunk])

        mock_redis_stream.assert_not_called()
