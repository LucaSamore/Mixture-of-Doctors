import pytest
from datetime import datetime
from pydantic import ValidationError
from unittest.mock import MagicMock

from chat_history.services import ConversationService
from chat_history.collection_model import ConversationItem


class TestConversationService:
    @pytest.mark.asyncio
    async def test_add_new_conversation_with_item(
        self, setup_service, sample_conversation_item_dict
    ):
        """Test creating a conversation for a new user with one item."""
        conversation_service, mock_db_collection, mock_db_client = setup_service

        # Mock session and transaction
        mock_db_session = MagicMock()
        mock_transaction = MagicMock()
        mock_db_session.start_transaction.return_value = mock_transaction
        mock_db_client.start_session.return_value.__aenter__.return_value = (
            mock_db_session
        )

        # No existing conversation found
        mock_db_collection.find_one.return_value = None

        test_username = "new_user_with_item"
        item = ConversationItem(**sample_conversation_item_dict)

        created_conversation = await conversation_service.add_conversation_item(
            test_username, item
        )

        assert created_conversation.username == test_username
        assert len(created_conversation.conversation) == 1
        assert created_conversation.conversation[0] == item
        mock_db_collection.update_one.assert_called_once()
        mock_db_session.start_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_new_conversation_without_item(self, setup_service):
        """Test creating a conversation for a new user with no items."""
        conversation_service, mock_db_collection, mock_db_client = setup_service

        mock_db_session = MagicMock()
        mock_transaction = MagicMock()
        mock_db_session.start_transaction.return_value = mock_transaction
        mock_db_client.start_session.return_value.__aenter__.return_value = (
            mock_db_session
        )

        mock_db_collection.find_one.return_value = None

        test_username = "new_user_no_item"
        created_conversation = await conversation_service.add_conversation_item(
            test_username, None
        )

        assert created_conversation.username == test_username
        assert len(created_conversation.conversation) == 0
        mock_db_collection.update_one.assert_called_once()
        mock_db_session.start_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_existing_conversation(self, setup_service, mock_transaction):
        """Test adding an item to an existing conversation."""
        conversation_service, mock_db_collection, mock_db_client = setup_service

        mock_db_session = MagicMock()
        mock_db_session.start_transaction.return_value = mock_transaction
        mock_db_client.start_session.return_value.__aenter__.return_value = (
            mock_db_session
        )

        test_username = "existing_user"
        existing_conversation_item = ConversationItem(
            question="First question", answer="First answer", timestamp=datetime.now()
        )
        existing_conversation_data = {
            "username": test_username,
            "conversation": [existing_conversation_item.model_dump()],
            "created_at": datetime.now(),
        }

        # Setup the find_one to return this conversation
        mock_db_collection.find_one.return_value = existing_conversation_data

        # Add a new item
        new_conversation_item = ConversationItem(
            question="Second question", answer="Second answer"
        )
        updated_conversation = await conversation_service.add_conversation_item(
            test_username, new_conversation_item
        )

        assert updated_conversation.username == test_username
        assert len(updated_conversation.conversation) == 2
        assert updated_conversation.conversation[0].question == "First question"
        assert updated_conversation.conversation[1].question == "Second question"
        mock_db_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_conversation_item(self, mock_db, sample_username):
        """Test validation of an invalid conversation item."""
        mock_database_client, _, _ = mock_db
        conversation_service = ConversationService(mock_database_client)

        with pytest.raises(ValidationError):
            invalid_conversation_item = ConversationItem(question="", answer="")
            await conversation_service.add_conversation_item(
                sample_username, invalid_conversation_item
            )


class TestConversationRetrieval:
    @pytest.mark.asyncio
    async def test_get_existing_conversation(self, setup_service):
        """Test retrieving an existing conversation."""
        conversation_service, mock_db_collection, _ = setup_service

        test_username = "test_user"
        mock_stored_conversation = {
            "username": test_username,
            "conversation": [
                {
                    "question": "Question",
                    "answer": "Answer",
                    "timestamp": datetime.now(),
                }
            ],
            "created_at": datetime.now(),
        }

        mock_db_collection.find_one.return_value = mock_stored_conversation

        retrieved_conversation = (
            await conversation_service.get_conversation_by_username(test_username)
        )

        assert retrieved_conversation is not None
        assert retrieved_conversation.username == test_username
        assert len(retrieved_conversation.conversation) == 1
        mock_db_collection.find_one.assert_called_once_with({"username": test_username})

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, setup_service):
        """Test retrieving a non-existent conversation."""
        conversation_service, mock_db_collection, _ = setup_service

        nonexistent_username = "nonexistent_user"
        mock_db_collection.find_one.return_value = None

        retrieved_conversation = (
            await conversation_service.get_conversation_by_username(
                nonexistent_username
            )
        )

        assert retrieved_conversation is None
        mock_db_collection.find_one.assert_called_once_with(
            {"username": nonexistent_username}
        )


class TestConversationDeletion:
    @pytest.mark.asyncio
    async def test_delete_existing_conversation(self, setup_service):
        """Test deleting an existing conversation."""
        conversation_service, mock_db_collection, _ = setup_service

        test_username = "user_to_delete"
        mock_db_collection.delete_one.return_value = MagicMock(deleted_count=1)

        deletion_successful = (
            await conversation_service.delete_conversation_by_username(test_username)
        )

        assert deletion_successful is True
        mock_db_collection.delete_one.assert_called_once_with(
            {"username": test_username}
        )

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, setup_service):
        """Test deleting a non-existent conversation."""
        conversation_service, mock_db_collection, _ = setup_service

        nonexistent_username = "nonexistent_user"
        mock_db_collection.delete_one.return_value = MagicMock(deleted_count=0)

        deletion_successful = (
            await conversation_service.delete_conversation_by_username(
                nonexistent_username
            )
        )

        assert deletion_successful is False
        mock_db_collection.delete_one.assert_called_once_with(
            {"username": nonexistent_username}
        )
