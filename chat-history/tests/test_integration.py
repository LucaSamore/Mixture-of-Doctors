import pytest
from unittest.mock import Mock

from chat_history.collection_model import ConversationItem


@pytest.mark.asyncio
async def test_add_and_retrieve_conversation(setup_service, mock_transaction):
    """Test the full flow of adding and then retrieving a conversation."""
    conversation_service, mock_model, mock_db_client = setup_service

    mock_db_session = Mock()
    mock_db_session.start_transaction.return_value = mock_transaction
    mock_db_client.start_session.return_value.__aenter__.return_value = mock_db_session

    # First call returns None (no existing conversation)
    # Second call returns the saved conversation
    mock_model.find_one.side_effect = [
        None,
        {
            "username": "test_user",
            "conversation": [
                {
                    "question": "Hello",
                    "answer": "Hi there!",
                    "timestamp": "2024-04-16T14:00:00",
                }
            ],
            "created_at": "2024-04-16T14:00:00",
        },
    ]

    # Create conversation item and add it
    test_conversation_item = ConversationItem(question="Hello", answer="Hi there!")
    await conversation_service.add_conversation_item(
        "test_user", test_conversation_item
    )

    retrieved_conversation = await conversation_service.get_conversation_by_username(
        "test_user"
    )

    assert retrieved_conversation.username == "test_user"
    assert len(retrieved_conversation.conversation) == 1
    assert retrieved_conversation.conversation[0].question == "Hello"
    assert retrieved_conversation.conversation[0].answer == "Hi there!"

    assert mock_model.find_one.call_count == 2
    assert mock_model.update_one.call_count == 1


@pytest.mark.asyncio
async def test_full_conversation_lifecycle(setup_service, mock_transaction):
    """Test the full lifecycle: create, add items, retrieve, delete."""
    conversation_service, mock_model, mock_db_client = setup_service

    mock_db_session = Mock()
    mock_db_session.start_transaction = Mock(side_effect=lambda: mock_transaction)
    mock_db_client.start_session.return_value.__aenter__.return_value = mock_db_session

    # Attended behavior for find_one:
    mock_model.find_one.side_effect = [
        None,
        {
            "username": "test_user",
            "conversation": [
                {"question": "Q1", "answer": "A1", "timestamp": "2024-04-16T14:00:00"}
            ],
            "created_at": "2024-04-16T14:00:00",
        },
        {
            "username": "test_user",
            "conversation": [
                {"question": "Q1", "answer": "A1", "timestamp": "2024-04-16T14:00:00"},
                {"question": "Q2", "answer": "A2", "timestamp": "2024-04-16T14:05:00"},
            ],
            "created_at": "2024-04-16T14:00:00",
        },
    ]

    # Delete one item (mocking the delete operation)
    mock_model.delete_one.return_value = Mock(deleted_count=1)

    # Add first item
    first_conversation_item = ConversationItem(question="Q1", answer="A1")
    await conversation_service.add_conversation_item(
        "test_user", first_conversation_item
    )

    # Add second item
    second_conversation_item = ConversationItem(question="Q2", answer="A2")
    await conversation_service.add_conversation_item(
        "test_user", second_conversation_item
    )

    # Retrieve conversation
    retrieved_conversation = await conversation_service.get_conversation_by_username(
        "test_user"
    )

    # Verify the conversation
    assert retrieved_conversation is not None
    assert retrieved_conversation.username == "test_user"
    assert len(retrieved_conversation.conversation) == 2

    assert retrieved_conversation.conversation[0].question == "Q1"
    assert retrieved_conversation.conversation[0].answer == "A1"
    assert retrieved_conversation.conversation[1].question == "Q2"
    assert retrieved_conversation.conversation[1].answer == "A2"

    # Delete conversation
    deletion_success = await conversation_service.delete_conversation_by_username(
        "test_user"
    )
    assert deletion_success is True

    # Verify database interactions
    assert mock_model.find_one.call_count == 3
    assert mock_model.update_one.call_count == 2
    mock_model.delete_one.assert_called_once_with({"username": "test_user"})
