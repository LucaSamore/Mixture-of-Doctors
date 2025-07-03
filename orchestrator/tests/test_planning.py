import pytest
from unittest.mock import patch, MagicMock
from src.orchestrator.planning import reason, act
from src.orchestrator.exceptions import ReasoningException, ActingException


@pytest.fixture(autouse=True)
def mock_configurations(monkeypatch):
    """Mock configurations to avoid file system operations during tests."""
    monkeypatch.setattr(
        "src.orchestrator.planning.prepare_prompt",
        lambda template, **kwargs: "mocked_prompt_content",
    )


class TestReasoning:
    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.prepare_prompt")
    async def test_reason_success(
        self, mock_prepare_prompt, sample_chatbot_query, mock_groq_client
    ):
        mock_llm, mock_completion = mock_groq_client
        mock_prepare_prompt.return_value = "Test prompt content"
        mock_message = MagicMock()
        mock_message.content = (
            '{"classification": "EASY", "diseases": [], "reasoning": "Test reasoning"}'
        )
        mock_completion.choices = [MagicMock(message=mock_message)]
        mock_llm.chat.completions.create.return_value = mock_completion
        result = await reason(sample_chatbot_query, mock_llm)
        assert result.classification.value == "EASY"
        assert result.diseases == []
        assert result.reasoning == "Test reasoning"
        mock_llm.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.prepare_prompt")
    async def test_reason_retry_success(
        self, mock_prepare_prompt, sample_chatbot_query, mock_groq_client
    ):
        """Test reasoning with retry after initial failure."""
        mock_llm, _ = mock_groq_client
        mock_prepare_prompt.return_value = "Test prompt content"
        # Configure mock to fail on first attempt, succeed on second
        success_completion = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"classification": "MEDIUM", "diseases": [{"disease": "diabetes", "question": "What is diabetes?"}], "reasoning": "Test reasoning"}'
                    )
                )
            ]
        )
        side_effects = [
            Exception("API Error"),
            success_completion,
        ]
        mock_llm.chat.completions.create.side_effect = side_effects
        result = await reason(sample_chatbot_query, mock_llm)
        assert result.classification.value == "MEDIUM"
        assert len(result.diseases) == 1
        assert result.diseases[0].disease == "diabetes"
        assert mock_llm.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.prepare_prompt")
    async def test_reason_all_attempts_fail(
        self, mock_prepare_prompt, sample_chatbot_query, mock_groq_client
    ):
        mock_llm, _ = mock_groq_client
        mock_prepare_prompt.return_value = "Test prompt content"
        mock_llm.chat.completions.create.side_effect = Exception("API Error")
        with patch("src.orchestrator.planning.REASONING_ATTEMPTS", 3):
            with pytest.raises(ReasoningException) as excinfo:
                await reason(sample_chatbot_query, mock_llm)
            assert "Could not reason after 3 attempt(s)" in str(excinfo.value)
            assert mock_llm.chat.completions.create.call_count == 3


class TestAct:
    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.answer")
    async def test_act_easy(
        self,
        mock_answer,
        sample_chatbot_query,
        sample_reasoning_outcome_easy,
        mock_kafka_producer,
        mock_redis_client,
        mock_groq_client,
    ):
        mock_llm, _ = mock_groq_client
        mock_answer.return_value = None
        await act(
            sample_reasoning_outcome_easy,
            sample_chatbot_query,
            mock_kafka_producer,
            mock_redis_client,
            mock_llm,
        )
        mock_answer.assert_called_once_with(
            sample_chatbot_query, mock_llm, mock_redis_client
        )

    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.ask_single_doctor")
    async def test_act_medium(
        self,
        mock_ask_single_doctor,
        sample_chatbot_query,
        sample_reasoning_outcome_medium,
        mock_kafka_producer,
        mock_redis_client,
        mock_groq_client,
    ):
        mock_llm, _ = mock_groq_client
        mock_ask_single_doctor.return_value = None
        await act(
            sample_reasoning_outcome_medium,
            sample_chatbot_query,
            mock_kafka_producer,
            mock_redis_client,
            mock_llm,
        )
        mock_ask_single_doctor.assert_called_once_with(
            sample_chatbot_query,
            sample_reasoning_outcome_medium.diseases[0].disease,
            mock_kafka_producer,
        )

    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.ask_many_doctors")
    async def test_act_hard(
        self,
        mock_ask_many_doctors,
        sample_chatbot_query,
        sample_reasoning_outcome_hard,
        mock_kafka_producer,
        mock_redis_client,
        mock_groq_client,
    ):
        mock_llm, _ = mock_groq_client
        mock_ask_many_doctors.return_value = None
        await act(
            sample_reasoning_outcome_hard,
            sample_chatbot_query,
            mock_kafka_producer,
            mock_redis_client,
            mock_llm,
        )
        mock_ask_many_doctors.assert_called_once_with(
            sample_chatbot_query,
            sample_reasoning_outcome_hard.diseases,
            mock_kafka_producer,
        )

    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.answer")
    async def test_act_exception(
        self,
        mock_answer,
        sample_chatbot_query,
        sample_reasoning_outcome_easy,
        mock_kafka_producer,
        mock_redis_client,
        mock_groq_client,
    ):
        mock_llm, _ = mock_groq_client
        mock_answer.side_effect = Exception("Test exception")
        with pytest.raises(ActingException) as excinfo:
            await act(
                sample_reasoning_outcome_easy,
                sample_chatbot_query,
                mock_kafka_producer,
                mock_redis_client,
                mock_llm,
            )
        assert "Action not performed" in str(excinfo.value)
