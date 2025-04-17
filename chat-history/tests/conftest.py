import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient

from chat_history.collection_model import ConversationItem, ConversationModel


class MockAsyncContextManager:
    """Implemnt a mock async context manager."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass


@pytest_asyncio.fixture
async def mock_transaction():
    """Return a mock transaction context manager."""
    return MockAsyncContextManager()


@pytest_asyncio.fixture
async def setup_service():
    """Set up mocked service, collection and client."""
    mock_client = AsyncMock()
    mock_db = AsyncMock()
    mock_db.client = mock_client
    mock_db.conversations = AsyncMock()

    from chat_history.services import ConversationService

    service = ConversationService(mock_db)
    return service, mock_db.conversations, mock_client


@pytest_asyncio.fixture
async def mock_db():
    """Set up mocked database and client."""
    mock_client = AsyncMock()
    mock_db = AsyncMock()
    mock_db.client = mock_client
    mock_db.conversations = AsyncMock()

    # Setup session for transactions
    mock_session = Mock()
    mock_session.start_transaction.return_value = MockAsyncContextManager()
    mock_client.start_session.return_value.__aenter__.return_value = mock_session

    return mock_db, mock_client, mock_session


@pytest.fixture
def sample_username():
    return "test_user"


@pytest.fixture
def sample_conversation_item_dict():
    """Return a conversation item as a dictionary (not an object)"""
    return {
        "question": "Test question",
        "answer": "Test answer",
        "timestamp": datetime.now(),
    }


@pytest.fixture
def sample_conversation_item():
    """Return a conversation item as an object"""
    return ConversationItem(
        question="Test question", answer="Test answer", timestamp=datetime.now()
    )


@pytest.fixture
def sample_conversation_model(sample_username, sample_conversation_item_dict):
    """Create a conversation model with a dictionary in the conversation list"""
    return ConversationModel(
        username=sample_username,
        conversation=[sample_conversation_item_dict],
        created_at=datetime.now(),
    )


@pytest.fixture
def empty_conversation_model(sample_username):
    return ConversationModel(
        username=sample_username, conversation=[], created_at=datetime.now()
    )


@pytest.fixture(scope="module")
def mock_database_app():
    """Setup mocked database and patches for API tests."""
    # Create a mock database for testing
    mock_db = AsyncMock()
    mock_db.conversations = AsyncMock()

    # Define a custom get_database function to use for testing
    async def mock_get_database():
        return mock_db

    # Apply all patches at the module level
    patches = [
        patch("chat_history.database.get_database", mock_get_database),
        patch("chat_history.api.get_database", mock_get_database),
        patch("chat_history.database.connect_to_mongodb", AsyncMock()),
        patch("chat_history.database.close_mongodb_connection", AsyncMock()),
    ]

    # Start all the patches
    for p in patches:
        p.start()

    # Now import the app after ALL patches are applied
    from chat_history.main import app

    # Create test client
    client = TestClient(app)

    yield client, mock_db

    # Stop all patches after tests
    for p in patches:
        p.stop()


@pytest.fixture
def mock_conversation_service():
    """Mock the ConversationService for API tests."""
    with patch("chat_history.api.ConversationService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        yield mock_service
