import pytest
from unittest.mock import patch, MagicMock
import json
from redis import RedisError

from src.cli.stream_client import (
    create_redis_connection,
    send_request,
    read_from_stream,
    starting_point,
    process_redis_response,
    format_is_valid,
    process_message,
    ORCHESTRATOR_URL,
)


@pytest.fixture
def mock_print_fn():
    return MagicMock()


@patch("src.cli.stream_client.Redis")
def test_create_redis_connection_success(mock_redis):
    mock_redis_instance = MagicMock()
    mock_redis.return_value = mock_redis_instance

    result = create_redis_connection()

    mock_redis.assert_called_once()
    mock_redis_instance.ping.assert_called_once()
    assert result == mock_redis_instance


@patch("src.cli.stream_client.Redis")
def test_create_redis_connection_failure(mock_redis):
    mock_instance = MagicMock()
    mock_instance.ping.side_effect = ConnectionError("Connection failed")
    mock_redis.return_value = mock_instance

    result = create_redis_connection()

    assert result is None


@patch("src.cli.stream_client.requests.post")
@patch("src.cli.stream_client.read_from_stream")
def test_send_request_success(mock_read_from_stream, mock_post, mock_print_fn):
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_post.return_value = mock_response
    user_id = "test_user"
    query = "test query"

    send_request(query, user_id, mock_print_fn)

    mock_post.assert_called_once_with(
        ORCHESTRATOR_URL, json={"query": query, "user_id": user_id}, timeout=30
    )
    mock_read_from_stream.assert_called_once_with(user_id, mock_print_fn)
    mock_print_fn.assert_called_once_with("Request accepted, waiting for response...")


@patch("src.cli.stream_client.requests.post")
def test_send_request_server_error(mock_post, mock_print_fn):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response

    send_request("query", "user_id", mock_print_fn)

    mock_print_fn.assert_called_once_with(
        "The server encountered a problem. Status code: 500", "error"
    )


@patch("src.cli.stream_client.requests.post")
def test_send_request_unexpected_status(mock_post, mock_print_fn):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_post.return_value = mock_response

    send_request("query", "user_id", mock_print_fn)

    mock_print_fn.assert_called_once_with("Unexpected response (status 400)", "warning")


@patch("src.cli.stream_client.requests.post")
def test_send_request_timeout(mock_post, mock_print_fn):
    from requests.exceptions import Timeout

    mock_post.side_effect = Timeout("Request timed out")

    send_request("query", "user_id", mock_print_fn)

    mock_print_fn.assert_called_once_with(
        "Request timed out. Please try again later.", "error"
    )


@patch("src.cli.stream_client.requests.post")
def test_send_request_request_exception(mock_post, mock_print_fn):
    from requests.exceptions import RequestException

    mock_post.side_effect = RequestException("Network error")

    send_request("query", "user_id", mock_print_fn)

    mock_print_fn.assert_called_once_with(
        "Failed to send request: Network error", "error"
    )


def test_starting_point_empty_last_message():
    import src.cli.stream_client as stream_client

    stream_client.LAST_MESSAGE_PROCESSED_ID = ""

    assert starting_point() == "0"


def test_starting_point_with_last_message():
    import src.cli.stream_client as stream_client

    stream_client.LAST_MESSAGE_PROCESSED_ID = "1234-0"

    assert starting_point() == "1234-0"

    stream_client.LAST_MESSAGE_PROCESSED_ID = ""


def test_format_is_valid_valid_condition(mock_print_fn):
    format_is_valid(True, "test_object", "test_name", mock_print_fn)
    mock_print_fn.assert_not_called()


def test_format_is_valid_invalid_condition(mock_print_fn):
    with pytest.raises(Exception) as context:
        format_is_valid(False, "test_object", "test_name", mock_print_fn)

    assert str(context.value) == "Invalid format"
    mock_print_fn.assert_called_once_with("Received message in unknown format", "error")


@patch("src.cli.stream_client.Response.model_validate_json")
def test_process_message_success(mock_validate_json, mock_print_fn):
    mock_response = MagicMock()
    mock_response.response = "Test response"
    mock_validate_json.return_value = mock_response
    message_data = json.dumps(
        {"query": "test", "response": "Test response", "done": "true"}
    )

    process_message("1234-0", message_data, mock_print_fn)

    mock_print_fn.assert_called_once_with("Test response")


@patch("src.cli.stream_client.Response.model_validate_json")
def test_process_message_failure(mock_validate_json, mock_print_fn):
    mock_validate_json.side_effect = Exception("Validation failed")
    message_data = "invalid data"

    process_message("1234-0", message_data, mock_print_fn)

    mock_print_fn.assert_called_once_with("\nMessage: invalid data", "error")


def test_process_redis_response_valid_format(mock_print_fn):
    import src.cli.stream_client as stream_client

    stream_client.LAST_MESSAGE_PROCESSED_ID = ""

    valid_data = json.dumps(
        {"query": "test", "response": "Test response", "done": "true"}
    )
    mock_response = [["stream_name", [["1234-0", valid_data]]]]

    with patch("src.cli.stream_client.process_message") as mock_process_message:
        process_redis_response(mock_response, mock_print_fn)

        mock_process_message.assert_called_once_with(
            "1234-0", valid_data, mock_print_fn
        )
        assert stream_client.LAST_MESSAGE_PROCESSED_ID == "1234-0"


def test_process_redis_response_not_a_list(mock_print_fn):
    process_redis_response("not_a_list", mock_print_fn)

    # Verify that print_fn was called twice:
    # 1. From format_is_valid with "Received message in unknown format"
    # 2. From the exception handler with "Error processing message: Invalid format"
    assert mock_print_fn.call_count == 2

    first_call = mock_print_fn.call_args_list[0]
    assert first_call[0][0] == "Received message in unknown format"
    assert first_call[0][1] == "error"

    second_call = mock_print_fn.call_args_list[1]
    assert "Error processing message" in second_call[0][0]
    assert "Invalid format" in second_call[0][0]
    assert second_call[0][1] == "error"


def test_process_redis_response_invalid_stream_entry(mock_print_fn):
    process_redis_response([123], mock_print_fn)

    assert mock_print_fn.call_count == 2

    first_call = mock_print_fn.call_args_list[0]
    assert first_call[0][0] == "Received message in unknown format"
    assert first_call[0][1] == "error"

    second_call = mock_print_fn.call_args_list[1]
    assert "Error processing message" in second_call[0][0]
    assert "Invalid format" in second_call[0][0]
    assert second_call[0][1] == "error"


def test_process_redis_response_invalid_messages(mock_print_fn):
    process_redis_response([["stream_name", "not_a_list"]], mock_print_fn)

    assert mock_print_fn.call_count == 2

    first_call = mock_print_fn.call_args_list[0]
    assert first_call[0][0] == "Received message in unknown format"
    assert first_call[0][1] == "error"

    second_call = mock_print_fn.call_args_list[1]
    assert "Error processing message" in second_call[0][0]
    assert second_call[0][1] == "error"


def test_process_redis_response_invalid_message_entry(mock_print_fn):
    process_redis_response([["stream_name", [123]]], mock_print_fn)

    assert mock_print_fn.call_count == 2

    first_call = mock_print_fn.call_args_list[0]
    assert first_call[0][0] == "Received message in unknown format"
    assert first_call[0][1] == "error"

    second_call = mock_print_fn.call_args_list[1]
    assert "Error processing message" in second_call[0][0]
    assert second_call[0][1] == "error"


def test_process_redis_response_invalid_message_format(mock_print_fn):
    process_redis_response([["stream_name", [["message_id"]]]], mock_print_fn)

    assert mock_print_fn.call_count == 2

    first_call = mock_print_fn.call_args_list[0]
    assert first_call[0][0] == "Received message in unknown format"
    assert first_call[0][1] == "error"

    second_call = mock_print_fn.call_args_list[1]
    assert "Error processing message" in second_call[0][0]
    assert second_call[0][1] == "error"


@patch("src.cli.stream_client.create_redis_connection")
def test_read_from_stream_redis_error(mock_create_connection, mock_print_fn):
    mock_redis = MagicMock()
    mock_redis.xread.side_effect = RedisError("Redis error")
    mock_create_connection.return_value = mock_redis

    read_from_stream("test_user", mock_print_fn)

    mock_print_fn.assert_called_once_with(
        "Error connecting to message stream: Redis error", "error"
    )


@patch("src.cli.stream_client.create_redis_connection")
def test_read_from_stream_no_redis_connection(mock_create_connection, mock_print_fn):
    mock_create_connection.return_value = None

    read_from_stream("test_user", mock_print_fn)

    mock_print_fn.assert_not_called()


@patch("src.cli.stream_client.create_redis_connection")
def test_read_from_stream_with_messages(mock_create_connection, mock_print_fn):
    mock_redis = MagicMock()

    # Set up mock to return data on first call, then empty list, then raise exception
    # to break out of the infinite loop
    mock_redis.xread.side_effect = [
        [["stream_name", [["1234-0", "message_data"]]]],  # First call: return message
        [],  # Second call: no messages
        Exception("Test loop break"),  # Break the infinite loop for testing
    ]

    mock_create_connection.return_value = mock_redis

    # Mock process_redis_response to avoid actual processing
    with patch("src.cli.stream_client.process_redis_response") as mock_process:
        # Execute - this should eventually raise our test exception
        try:
            read_from_stream("test_user", mock_print_fn)
        except Exception as e:
            assert str(e) == "Test loop break"

        # Verify process_redis_response was called once with the message data
        mock_process.assert_called_once()
