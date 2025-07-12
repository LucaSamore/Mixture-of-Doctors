import pytest
from unittest.mock import MagicMock, patch, AsyncMock


with (
    patch("aiokafka.AIOKafkaConsumer", MagicMock()),
    patch("groq.AsyncGroq", MagicMock()),
    patch("redis.asyncio.Redis", MagicMock()),
):
    from synthesizer.synthesis import RAGResponse, QueryData


@pytest.fixture
def mock_kafka_client():
    mock = MagicMock()
    mock.commit = MagicMock(return_value=True)
    mock.get_consumer = MagicMock(return_value=MagicMock())
    return mock


@pytest.fixture
def mock_redis_client():
    mock = MagicMock()
    mock.stream_message = MagicMock()
    return mock


@pytest.fixture
def mock_llm_client():
    mock = MagicMock()
    mock.generate = AsyncMock()
    return mock


@pytest.fixture(autouse=True)
def mock_services():
    """Automatically mock all external services for every test"""
    # These patches are removed since the corresponding attributes don't exist in synthesis.py
    # The individual test files now handle their own mocking
    yield


@pytest.fixture
def reset_active_queries():
    """Reset active queries between tests to avoid interference"""
    from synthesizer.synthesis import active_queries

    active_queries.clear()
    yield
    active_queries.clear()


@pytest.fixture
def sample_rag_response():
    """Create a sample response from a disease-specific RAG module"""
    return RAGResponse(
        user_id="test_user",
        query_id="test_query_id",
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
        query_id="test_query_id",
        user_id="test_user",
        original_query="What is diabetes?",
        responses={"diabetes": "Diabetes is a chronic condition."},
        received_numbers={1},
        total=2,
        stream=True,
        plain_text=True,
    )


@pytest.fixture
def complete_query_data():
    """Query data with complete set of responses"""
    return QueryData(
        query_id="test_query_id",
        user_id="test_user",
        original_query="What is diabetes and hypertension?",
        responses={
            "diabetes": "Diabetes is a chronic condition.",
            "hypertension": "Hypertension is high blood pressure.",
        },
        received_numbers={1, 2},
        total=2,
        stream=True,
        plain_text=True,
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

    async def mock_stream():
        yield mock_chunk1
        yield mock_chunk2

    mock_gen = AsyncMock()
    mock_gen.return_value = mock_stream()
    return mock_gen
