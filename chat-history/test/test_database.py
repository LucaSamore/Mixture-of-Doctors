from contextlib import asynccontextmanager
from datetime import datetime

import pytest
import pytest_asyncio
from pydantic import ValidationError
from unittest.mock import AsyncMock, Mock

from chat_history.services import ConversationService
from chat_history.collection_model import ConversationItem


@asynccontextmanager
async def async_mock_context():
    """Simulate a transaction-like async context manager."""
    yield


@pytest_asyncio.fixture
async def conversation_service_setup():
    """
    Create a complete mock setup for ConversationService.

    Returns:
        Tuple containing mocked service, collection, client
    """
    mock_client = AsyncMock()
    mock_db = AsyncMock()
    mock_db.client = mock_client

    mock_collection = AsyncMock()
    mock_db.conversations = mock_collection

    service = ConversationService(mock_db)
    return service, mock_collection, mock_client


class TestConversationService:
    @pytest.mark.asyncio
    async def test_add_conversation_item(self, conversation_service_setup):
        """Test successful addition of a conversation item."""
        service, mock_collection, mock_client = conversation_service_setup

        mock_session = Mock()
        mock_session.start_transaction.return_value = async_mock_context()

        mock_client.start_session.return_value.__aenter__.return_value = mock_session

        username = "test_user"
        conversation_item = ConversationItem(
            question="Hello?", answer="Hi there!", timestamp=datetime.now()
        )

        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.update_one = AsyncMock()

        result = await service.add_conversation_item(username, conversation_item)

        assert result.username == username
        assert len(result.conversation) == 1
        assert result.conversation[0].question == "Hello?"
        assert result.conversation[0].answer == "Hi there!"

        mock_client.start_session.assert_called_once()
        mock_session.start_transaction.assert_called_once()
        mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrong_add_conversation_item(self, conversation_service_setup):
        """Test adding an invalid conversation item raises ValidationError."""
        service, _, _ = conversation_service_setup
        username = "test_user"

        with pytest.raises(ValidationError, match="string_too_short"):
            invalid_item = ConversationItem(question="", answer="")
            await service.add_conversation_item(username, invalid_item)

    @pytest.mark.asyncio
    async def test_get_existing_conversation(self, conversation_service_setup):
        """Test retrieving an existing conversation."""
        service, mock_collection, _ = conversation_service_setup
        username = "test_user"

        mock_conversation_data = {
            "username": username,
            "conversation": [
                {
                    "question": "First question",
                    "answer": "First answer",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }
        mock_collection.find_one = AsyncMock(return_value=mock_conversation_data)

        result = await service.get_conversation_by_username(username)

        assert result is not None
        assert result.username == username
        assert len(result.conversation) == 1
        assert result.conversation[0].question == "First question"
        assert result.conversation[0].answer == "First answer"
        mock_collection.find_one.assert_called_once_with({"username": username})

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, conversation_service_setup):
        """Test retrieving a non-existent conversation returns None."""
        service, mock_collection, _ = conversation_service_setup
        username = "nonexistent_user"

        mock_collection.find_one = AsyncMock(return_value=None)

        result = await service.get_conversation_by_username(username)

        assert result is None
        mock_collection.find_one.assert_called_once_with({"username": username})

    @pytest.mark.asyncio
    async def test_delete_existing_conversation(self, conversation_service_setup):
        """Test successful deletion of an existing conversation."""
        service, mock_collection, _ = conversation_service_setup
        username = "test_user"

        mock_collection.delete_one = AsyncMock(return_value=Mock(deleted_count=1))

        result = await service.delete_conversation_by_username(username)

        assert result is True
        mock_collection.delete_one.assert_called_once_with({"username": username})

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, conversation_service_setup):
        """Test deletion of a non-existent conversation."""
        service, mock_collection, _ = conversation_service_setup
        username = "nonexistent_user"

        mock_collection.delete_one = AsyncMock(return_value=Mock(deleted_count=0))

        result = await service.delete_conversation_by_username(username)

        assert result is False
        mock_collection.delete_one.assert_called_once_with({"username": username})
