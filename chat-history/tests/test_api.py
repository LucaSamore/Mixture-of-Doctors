from unittest.mock import MagicMock
from datetime import datetime


class TestChatHistoryAPI:
    def test_get_conversation(
        self, mock_database_app, mock_conversation_service, sample_conversation_model
    ):
        """Test API endpoint for retrieving a conversation."""
        test_http_client, _ = mock_database_app
        test_username = "test_user"
        mock_conversation_service.get_conversation_by_username.return_value = (
            sample_conversation_model
        )

        api_response = test_http_client.get(f"/requests/{test_username}")

        assert api_response.status_code == 200
        response_data = api_response.json()
        assert response_data["username"] == test_username
        assert len(response_data["conversation"]) == 1
        mock_conversation_service.get_conversation_by_username.assert_called_once_with(
            test_username
        )

    def test_get_nonexistent_conversation(
        self, mock_database_app, mock_conversation_service
    ):
        """Test API endpoint for retrieving a non-existent conversation."""
        test_http_client, _ = mock_database_app
        nonexistent_username = "nonexistent_user"
        mock_conversation_service.get_conversation_by_username.return_value = None

        api_response = test_http_client.get(f"/requests/{nonexistent_username}")

        assert api_response.status_code == 404
        mock_conversation_service.get_conversation_by_username.assert_called_once_with(
            nonexistent_username
        )

    def test_add_conversation_item(
        self, mock_database_app, mock_conversation_service, sample_conversation_model
    ):
        """Test API endpoint for adding a conversation item."""
        test_http_client, _ = mock_database_app
        test_username = "test_user"
        new_conversation_item = {"question": "New question", "answer": "New answer"}

        mock_updated_conversation = MagicMock()
        mock_updated_conversation.username = test_username
        mock_updated_conversation.created_at = datetime.now()
        mock_updated_conversation.conversation = [
            MagicMock(
                question="Test question", answer="Test answer", timestamp=datetime.now()
            ),
            MagicMock(
                question="New question", answer="New answer", timestamp=datetime.now()
            ),
        ]
        mock_updated_conversation.model_dump.return_value = {
            "username": test_username,
            "conversation": [
                {
                    "question": "Test question",
                    "answer": "Test answer",
                    "timestamp": "2024-04-16T14:00:00",
                },
                {
                    "question": "New question",
                    "answer": "New answer",
                    "timestamp": "2024-04-16T14:05:00",
                },
            ],
            "created_at": "2024-04-16T14:00:00",
        }
        mock_conversation_service.add_conversation_item.return_value = (
            mock_updated_conversation
        )

        api_response = test_http_client.post(
            f"/requests/?username={test_username}", json=new_conversation_item
        )

        assert api_response.status_code == 200
        response_data = api_response.json()
        assert response_data["username"] == test_username
        assert len(response_data["conversation"]) == 2
        mock_conversation_service.add_conversation_item.assert_called_once()

    def test_delete_conversation(self, mock_database_app, mock_conversation_service):
        """Test API endpoint for deleting a conversation."""
        test_http_client, _ = mock_database_app
        test_username = "test_user"
        mock_conversation_service.delete_conversation_by_username.return_value = True

        api_response = test_http_client.delete(f"/requests/{test_username}")

        assert api_response.status_code == 204
        mock_conversation_service.delete_conversation_by_username.assert_called_once_with(
            test_username
        )

    def test_delete_nonexistent_conversation(
        self, mock_database_app, mock_conversation_service
    ):
        """Test API endpoint for deleting a non-existent conversation."""
        test_http_client, _ = mock_database_app
        nonexistent_username = "nonexistent_user"
        mock_conversation_service.delete_conversation_by_username.return_value = False

        api_response = test_http_client.delete(f"/requests/{nonexistent_username}")

        assert api_response.status_code == 404
        mock_conversation_service.delete_conversation_by_username.assert_called_once_with(
            nonexistent_username
        )
