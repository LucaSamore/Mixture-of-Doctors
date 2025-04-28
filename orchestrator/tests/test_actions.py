import pytest
from unittest.mock import patch, MagicMock

from src.orchestrator.planning import (
    answer,
    ask_single_doctor,
    ask_many_doctors,
    generate_answer,
    DiseaseSpecificQuestion,
)


@pytest.fixture(autouse=True)
def mock_configurations(monkeypatch):
    """Mock configurations to avoid file system operations during tests."""
    monkeypatch.setattr("src.orchestrator.planning.redis_client", MagicMock())
    monkeypatch.setattr("src.orchestrator.planning.kafka_producer", MagicMock())
    monkeypatch.setattr(
        "src.orchestrator.planning.prepare_prompt",
        lambda template, **kwargs: "mocked_prompt_content",
    )


class TestAnswer:
    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.fetch_chat_history_for_user")
    @patch("src.orchestrator.planning.generate_answer")
    async def test_answer_flow(
        self,
        mock_generate_answer,
        mock_fetch_history,
        sample_chatbot_query,
        sample_conversation_history,
    ):
        """Test the answer flow from fetching history to generating answer."""
        mock_fetch_history.return_value = sample_conversation_history
        mock_generate_answer.return_value = None
        await answer(sample_chatbot_query)
        mock_fetch_history.assert_called_once_with(sample_chatbot_query.user_id)
        mock_generate_answer.assert_called_once_with(
            sample_chatbot_query, sample_conversation_history
        )


class TestGenerateAnswer:
    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.prepare_prompt")
    async def test_generate_answer(
        self,
        mock_prepare_prompt,
        sample_chatbot_query,
        sample_conversation_history,
        mock_groq_client,
        mock_redis_client,
    ):
        mock_llm, _ = mock_groq_client
        mock_prepare_prompt.return_value = "Test prompt content"
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [
            MagicMock(delta=MagicMock(content="This is "), finish_reason=None)
        ]
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [
            MagicMock(delta=MagicMock(content="a test response."), finish_reason="stop")
        ]
        mock_llm.chat.completions.create.return_value = [mock_chunk1, mock_chunk2]
        with patch("src.orchestrator.planning.llm_groq", mock_llm):
            with patch("src.orchestrator.planning.redis_client", mock_redis_client):
                await generate_answer(sample_chatbot_query, sample_conversation_history)
                mock_llm.chat.completions.create.assert_called_once()
                assert mock_redis_client.xadd.call_count == 2
                # Check content of first redis add
                first_call_args = mock_redis_client.xadd.call_args_list[0]
                assert first_call_args[1]["name"] == sample_chatbot_query.user_id
                assert first_call_args[1]["fields"]["response"] == "This is "
                assert first_call_args[1]["fields"]["done"] == "None"
                # Check content of second redis add (should show completion)
                second_call_args = mock_redis_client.xadd.call_args_list[1]
                assert second_call_args[1]["fields"]["response"] == "a test response."
                assert second_call_args[1]["fields"]["done"] == "stop"


class TestRagModuleInteractions:
    @pytest.mark.asyncio
    async def test_ask_single_doctor(self, sample_chatbot_query, mock_kafka_producer):
        """Test sending a query to a single RAG module."""
        disease = "diabetes"
        with patch("src.orchestrator.planning.kafka_producer", mock_kafka_producer):
            with patch(
                "src.orchestrator.planning.uuid.uuid4", return_value="test-uuid"
            ):
                await ask_single_doctor(sample_chatbot_query, disease)
                mock_kafka_producer.send.assert_called_once()
                call_args = mock_kafka_producer.send.call_args
                assert call_args[1]["topic"] == "rag-module-diabetes"
                message_value = call_args[1]["value"]
                assert message_value["user_id"] == sample_chatbot_query.user_id
                assert message_value["query_id"] == "test-uuid"
                assert message_value["original_query"] == sample_chatbot_query.query
                assert message_value["rag_query"] == sample_chatbot_query.query
                assert message_value["stream"] is True
                assert message_value["number"] == 1
                assert message_value["total"] == 1

    @pytest.mark.asyncio
    @patch("src.orchestrator.planning.len")
    async def test_ask_many_doctors(
        self, mock_len, sample_chatbot_query, mock_kafka_producer
    ):
        """Test sending queries to multiple RAG modules."""
        mock_len.return_value = 3  # Simulate 3 diseases in config
        disease_questions = [
            DiseaseSpecificQuestion(disease="diabetes", question="About diabetes"),
            DiseaseSpecificQuestion(
                disease="hypertension", question="About hypertension"
            ),
        ]
        with patch("src.orchestrator.planning.kafka_producer", mock_kafka_producer):
            with patch(
                "src.orchestrator.planning.uuid.uuid4", return_value="test-uuid"
            ):
                await ask_many_doctors(sample_chatbot_query, disease_questions)
                assert mock_kafka_producer.send.call_count == 2
                # Check first call (diabetes)
                first_call_args = mock_kafka_producer.send.call_args_list[0]
                assert first_call_args[1]["topic"] == "rag-module-diabetes"
                message1 = first_call_args[1]["value"]
                assert message1["user_id"] == sample_chatbot_query.user_id
                assert message1["query_id"] == "test-uuid"
                assert message1["rag_query"] == "About diabetes"
                assert message1["stream"] is False
                assert message1["number"] == 1
                assert message1["total"] == 3
                # Check second call (hypertension)
                second_call_args = mock_kafka_producer.send.call_args_list[1]
                assert second_call_args[1]["topic"] == "rag-module-hypertension"
                message2 = second_call_args[1]["value"]
                assert message2["user_id"] == sample_chatbot_query.user_id
                assert message2["query_id"] == "test-uuid"
                assert message2["rag_query"] == "About hypertension"
                assert message2["number"] == 2
                assert message2["total"] == 3
