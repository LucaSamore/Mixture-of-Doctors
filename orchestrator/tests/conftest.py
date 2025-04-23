import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.orchestrator.planning import (
    ChatbotQuery,
    ConversationItem,
    ReasoningOutcome,
    Grade,
    DiseaseSpecificQuestion,
)


@pytest.fixture
def mock_redis_client():
    mock = MagicMock()
    mock.xadd = MagicMock()
    return mock


@pytest.fixture
def mock_kafka_producer():
    mock = MagicMock()
    mock.send = MagicMock()
    return mock


@pytest.fixture
def mock_groq_client():
    mock = MagicMock()
    mock_completion = MagicMock()
    mock.chat.completions.create = MagicMock(return_value=mock_completion)
    return mock, mock_completion


@pytest.fixture
def mock_response():
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = AsyncMock()
    mock.json = AsyncMock(
        return_value={
            "username": "test_user",
            "created_at": datetime.now().isoformat(),
            "conversation": [
                {
                    "question": "Previous question",
                    "answer": "Previous answer",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }
    )
    return mock


@pytest.fixture
def mock_httpx_client():
    mock = AsyncMock()
    return mock


@pytest.fixture
def sample_chatbot_query():
    return ChatbotQuery(user_id="test_user", query="What is diabetes?")


@pytest.fixture
def sample_reasoning_outcome_easy():
    return ReasoningOutcome(
        classification=Grade.EASY,
        diseases=[],
        reasoning="This is a general medical question.",
    )


@pytest.fixture
def sample_reasoning_outcome_medium():
    return ReasoningOutcome(
        classification=Grade.MEDIUM,
        diseases=[
            DiseaseSpecificQuestion(disease="diabetes", question="What is diabetes?")
        ],
        reasoning="This question is specifically about diabetes.",
    )


@pytest.fixture
def sample_reasoning_outcome_hard():
    return ReasoningOutcome(
        classification=Grade.HARD,
        diseases=[
            DiseaseSpecificQuestion(
                disease="diabetes", question="How does diabetes affect blood sugar?"
            ),
            DiseaseSpecificQuestion(
                disease="hypertension",
                question="How is hypertension related to diabetes?",
            ),
        ],
        reasoning="This question involves multiple diseases.",
    )


@pytest.fixture
def sample_conversation_history():
    return [
        ConversationItem(
            question="Previous question",
            answer="Previous answer",
            timestamp=datetime.now(),
        )
    ]


@pytest.fixture
def mock_get_diseases():
    with patch("src.orchestrator.planning.get_diseases_from_config_file") as mock:
        mock.return_value = ["diabetes", "hypertension", "multiple-sclerosis"]
        yield mock
