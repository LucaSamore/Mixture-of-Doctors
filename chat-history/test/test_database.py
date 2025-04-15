from contextlib import asynccontextmanager
from datetime import datetime
from pydantic import ValidationError
from unittest.mock import AsyncMock, Mock
from chat_history.services import ConversationService
from chat_history.collection_model import ConversationItem, ConversationModel
import pytest
import pytest_asyncio


@asynccontextmanager
async def mock_transaction():
    """Simulate an async transaction context manager."""
    yield


@pytest_asyncio.fixture
async def setup_service():
    """Set up mocked service, collection and client."""
    mock_client = AsyncMock()
    mock_db = AsyncMock()
    mock_db.client = mock_client
    mock_db.conversations = AsyncMock()

    service = ConversationService(mock_db)
    return service, mock_db.conversations, mock_client


@pytest.mark.asyncio
async def test_add_new_conversation(setup_service):
    """Test adding a conversation for a new user."""
    service, mock_collection, mock_client = setup_service

    mock_session = Mock()
    mock_session.start_transaction.return_value = mock_transaction()
    mock_client.start_session.return_value.__aenter__.return_value = mock_session
    mock_collection.find_one.return_value = None

    username = "new_user"
    conv_item = ConversationItem(question="Question", answer="Answer")

    result = await service.add_conversation_item(username, conv_item)

    assert result.username == username
    assert len(result.conversation) == 1
    assert result.conversation[0].question == "Question"
    mock_collection.update_one.assert_called_once()
    mock_session.start_transaction.assert_called_once()


@pytest.mark.asyncio
async def test_add_conversation_without_item(setup_service):
    """Test creating a conversation without adding a conversation item."""
    service, mock_collection, mock_client = setup_service

    mock_session = Mock()
    mock_session.start_transaction.return_value = mock_transaction()
    mock_client.start_session.return_value.__aenter__.return_value = mock_session
    mock_collection.find_one.return_value = None

    username = "new_user_no_conversation"

    result = await service.add_conversation_item(username, None)

    assert result.username == username
    assert len(result.conversation) == 0
    mock_collection.update_one.assert_called_once()
    mock_session.start_transaction.assert_called_once()


@pytest.mark.asyncio
async def test_add_to_existing_conversation(setup_service):
    """Test adding an item to an existing conversation."""
    service, mock_collection, mock_client = setup_service

    mock_session = Mock()
    mock_session.start_transaction.return_value = mock_transaction()
    mock_client.start_session.return_value.__aenter__.return_value = mock_session

    username = "existing_user"
    existing_item = ConversationItem(
        question="First question", answer="First answer", timestamp=datetime.now()
    )

    existing_conversation = ConversationModel(
        username=username, conversation=[existing_item], created_at=datetime.now()
    )

    mock_collection.find_one.return_value = existing_conversation.model_dump()

    new_item = ConversationItem(question="Second question", answer="Second answer")
    result = await service.add_conversation_item(username, new_item)

    assert result.username == username
    assert len(result.conversation) == 2
    assert result.conversation[0].question == "First question"
    assert result.conversation[1].question == "Second question"
    mock_collection.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_invalid_conversation_item(setup_service):
    """Test validation of an invalid conversation item."""
    service, _, _ = setup_service

    with pytest.raises(ValidationError):
        invalid_item = ConversationItem(question="", answer="")
        await service.add_conversation_item("user", invalid_item)


@pytest.mark.asyncio
async def test_get_existing_conversation(setup_service):
    """Test retrieving an existing conversation."""
    service, mock_collection, _ = setup_service

    username = "test_user"
    mock_data = {
        "username": username,
        "conversation": [
            {"question": "Question", "answer": "Answer", "timestamp": datetime.now()}
        ],
        "created_at": datetime.now(),
    }

    mock_collection.find_one.return_value = mock_data

    result = await service.get_conversation_by_username(username)

    assert result is not None
    assert result.username == username
    assert len(result.conversation) == 1
    mock_collection.find_one.assert_called_once_with({"username": username})


@pytest.mark.asyncio
async def test_get_nonexistent_conversation(setup_service):
    """Test retrieving a non-existent conversation."""
    service, mock_collection, _ = setup_service

    username = "nonexistent_user"
    mock_collection.find_one.return_value = None

    result = await service.get_conversation_by_username(username)

    assert result is None
    mock_collection.find_one.assert_called_once_with({"username": username})


@pytest.mark.asyncio
async def test_delete_existing_conversation(setup_service):
    """Test deleting an existing conversation."""
    service, mock_collection, _ = setup_service

    username = "user_to_delete"
    mock_collection.delete_one.return_value = Mock(deleted_count=1)

    result = await service.delete_conversation_by_username(username)

    assert result is True
    mock_collection.delete_one.assert_called_once_with({"username": username})


@pytest.mark.asyncio
async def test_delete_nonexistent_conversation(setup_service):
    """Test deleting a non-existent conversation."""
    service, mock_collection, _ = setup_service

    username = "nonexistent_user"
    mock_collection.delete_one.return_value = Mock(deleted_count=0)

    result = await service.delete_conversation_by_username(username)

    assert result is False
    mock_collection.delete_one.assert_called_once_with({"username": username})
