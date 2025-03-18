import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.cli.chat_history_client import (
    ChatHistoryClient,
    ConversationModel,
)


@pytest.fixture
def mock_print_fn():
    return MagicMock()


@pytest.fixture
def chat_history_client():
    return ChatHistoryClient()


@pytest.fixture
def mock_response():
    mock = MagicMock()
    mock.status_code = 200

    mock.json.return_value = {
        "username": "test_user",
        "created_at": datetime.now().isoformat(),
        "conversation": [
            {
                "question": "Test question",
                "answer": "Test answer",
                "timestamp": datetime.now().isoformat(),
            }
        ],
    }
    return mock


@patch("requests.post")
def test_create_or_update_chat_success(mock_post, chat_history_client, mock_response):
    mock_post.return_value = mock_response

    result = chat_history_client.create_or_update_chat(
        "test_user", "Test question", "Test answer", mock_print_fn
    )

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs["params"] == {"username": "test_user"}

    assert isinstance(result, ConversationModel)
    assert result.username == "test_user"
    assert len(result.conversation) == 1
    assert result.conversation[0].question == "Test question"


@patch("requests.post")
def test_create_or_update_chat_error(mock_post, chat_history_client, mock_print_fn):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response

    result = chat_history_client.create_or_update_chat(
        "test_user", "Test question", "Test answer", mock_print_fn
    )

    assert result is None
    mock_print_fn.assert_called_once()


@patch("requests.post")
def test_create_or_update_chat_exception(mock_post, chat_history_client, mock_print_fn):
    mock_post.side_effect = Exception("Connection error")

    result = chat_history_client.create_or_update_chat(
        "test_user", "Test question", "Test answer", mock_print_fn
    )

    assert result is None
    mock_print_fn.assert_called_once()


@patch("requests.get")
def test_get_chat_history_success(
    mock_get, chat_history_client, mock_response, mock_print_fn
):
    mock_get.return_value = mock_response

    result = chat_history_client.get_chat_history("test_user", mock_print_fn)
    mock_get.assert_called_once_with(
        f"{chat_history_client.base_url}/requests/test_user"
    )

    assert isinstance(result, ConversationModel)
    assert result.username == "test_user"
    assert len(result.conversation) == 1


@patch("requests.get")
def test_get_chat_history_not_found(mock_get, chat_history_client, mock_print_fn):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_get.return_value = mock_response

    result = chat_history_client.get_chat_history("nonexistent_user", mock_print_fn)

    assert result is None


@patch("requests.get")
def test_get_chat_history_error(mock_get, chat_history_client, mock_print_fn):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_get.return_value = mock_response

    result = chat_history_client.get_chat_history("test_user", mock_print_fn)

    assert result is None
    mock_print_fn.assert_called_once()


@patch("requests.get")
def test_get_chat_history_exception(mock_get, chat_history_client, mock_print_fn):
    mock_get.side_effect = Exception("Connection error")

    result = chat_history_client.get_chat_history("test_user", mock_print_fn)

    assert result is None
    mock_print_fn.assert_called_once()


@patch("requests.delete")
def test_delete_chat_history_success(mock_delete, chat_history_client, mock_print_fn):
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_delete.return_value = mock_response

    result = chat_history_client.delete_chat_history("test_user", mock_print_fn)

    mock_delete.assert_called_once_with(
        f"{chat_history_client.base_url}/requests/test_user"
    )

    assert result is True


@patch("requests.delete")
def test_delete_chat_history_error(mock_delete, chat_history_client, mock_print_fn):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_delete.return_value = mock_response

    result = chat_history_client.delete_chat_history("test_user", mock_print_fn)

    assert result is False
    mock_print_fn.assert_called_once()


@patch("requests.delete")
def test_delete_chat_history_exception(mock_delete, chat_history_client, mock_print_fn):
    mock_delete.side_effect = Exception("Connection error")

    result = chat_history_client.delete_chat_history("test_user", mock_print_fn)

    assert result is False
    mock_print_fn.assert_called_once()
