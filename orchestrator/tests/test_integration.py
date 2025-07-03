import pytest
from unittest.mock import patch
from src.orchestrator.planning import answer


@pytest.fixture(autouse=True)
def mock_configurations(monkeypatch):
    """Mock configurations to avoid file system operations during tests."""
    monkeypatch.setattr(
        "src.orchestrator.planning.prepare_prompt",
        lambda template, **kwargs: "mocked_prompt_content",
    )


class TestIntegrationFlow:
    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.reason")
    @patch("src.orchestrator.planning.act")
    async def test_full_reasoning_to_action_easy(
        self,
        mock_act,
        mock_reason,
        sample_chatbot_query,
        sample_reasoning_outcome_easy,
        mock_kafka_producer,
        mock_redis_client,
        mock_groq_client,
    ):
        mock_llm, _ = mock_groq_client
        mock_reason.return_value = sample_reasoning_outcome_easy
        mock_act.return_value = None

        # Simulate what handle_request does
        outcome = await mock_reason(sample_chatbot_query, mock_llm)
        await mock_act(
            outcome,
            sample_chatbot_query,
            mock_kafka_producer,
            mock_redis_client,
            mock_llm,
        )

        mock_reason.assert_called_once_with(sample_chatbot_query, mock_llm)
        mock_act.assert_called_once_with(
            sample_reasoning_outcome_easy,
            sample_chatbot_query,
            mock_kafka_producer,
            mock_redis_client,
            mock_llm,
        )

    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.fetch_chat_history_for_user")
    @patch("src.orchestrator.planning.generate_answer")
    async def test_end_to_end_easy_query(
        self,
        mock_generate_answer,
        mock_fetch_history,
        sample_conversation_history,
        sample_chatbot_query,
        mock_groq_client,
        mock_redis_client,
    ):
        """Test end-to-end flow for EASY query from reasoning to Redis streaming."""
        mock_llm, _ = mock_groq_client
        mock_fetch_history.return_value = sample_conversation_history
        mock_generate_answer.return_value = None
        await answer(sample_chatbot_query, mock_llm, mock_redis_client)
        mock_fetch_history.assert_called_once_with(sample_chatbot_query.user_id)
        mock_generate_answer.assert_called_once_with(
            sample_chatbot_query,
            sample_conversation_history,
            mock_llm,
            mock_redis_client,
        )
