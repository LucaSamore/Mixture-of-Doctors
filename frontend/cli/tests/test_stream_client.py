import pytest
from unittest.mock import patch, MagicMock
import json
from redis import RedisError

from src.cli.stream_client import StreamClient


@pytest.fixture
def mock_print_fn():
    return MagicMock()


@pytest.fixture
def stream_client():
    return StreamClient()


class TestRedisConnection:
    @patch("src.cli.stream_client.Redis")
    def test_create_redis_connection_success(self, mock_redis, stream_client):
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        result = stream_client.create_redis_connection()

        mock_redis.assert_called_once()
        mock_redis_instance.ping.assert_called_once()
        assert result == mock_redis_instance

    @patch("src.cli.stream_client.Redis")
    def test_create_redis_connection_failure(self, mock_redis, stream_client):
        mock_instance = MagicMock()
        mock_instance.ping.side_effect = ConnectionError("Connection failed")
        mock_redis.return_value = mock_instance

        result = stream_client.create_redis_connection()

        assert result is None


class TestSendRequest:
    @patch("requests.post")
    def test_send_request_success(self, mock_post, stream_client, mock_print_fn):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        user_id = "test_user"
        query = "test query"

        def fake_update(*args, **kwargs):
            pass

        def fake_read_from_stream(*args, **kwargs):
            pass

        with patch.object(stream_client, "_update_last_message_id", new=fake_update):
            with patch.object(
                stream_client, "read_from_stream", new=fake_read_from_stream
            ):
                mock_print_fn("Request accepted, waiting for response...")

                stream_client.send_request(query, user_id, mock_print_fn)

                mock_post.assert_called_once_with(
                    stream_client.orchestrator_url,
                    json={"query": query, "user_id": user_id, "plain_text": True},
                    timeout=stream_client.request_timeout,
                )

    @patch("requests.post")
    def test_send_request_server_error(self, mock_post, stream_client, mock_print_fn):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        with patch.object(stream_client, "_update_last_message_id"):
            stream_client.send_request("query", "user_id", mock_print_fn)

            mock_print_fn.assert_called_once_with(
                "The server encountered a problem. Status code: 500", "error"
            )

    @patch("requests.post")
    def test_send_request_unexpected_status(
        self, mock_post, stream_client, mock_print_fn
    ):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        with patch.object(stream_client, "_update_last_message_id"):
            stream_client.send_request("query", "user_id", mock_print_fn)

            mock_print_fn.assert_called_once_with(
                "Unexpected response (status 400)", "warning"
            )

    @patch("requests.post")
    def test_send_request_timeout(self, mock_post, stream_client, mock_print_fn):
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout("Request timed out")

        with patch.object(stream_client, "_update_last_message_id"):
            stream_client.send_request("query", "user_id", mock_print_fn)

            mock_print_fn.assert_called_once_with(
                "Request timed out. Please try again later.", "error"
            )

    @patch("requests.post")
    def test_send_request_exception(self, mock_post, stream_client, mock_print_fn):
        from requests.exceptions import RequestException

        mock_post.side_effect = RequestException("Network error")

        with patch.object(stream_client, "_update_last_message_id"):
            stream_client.send_request("query", "user_id", mock_print_fn)

            mock_print_fn.assert_called_once_with(
                "Failed to send request: Network error", "error"
            )


class TestStartingPoint:
    def test_starting_point_with_empty_last_processed(self, stream_client):
        stream_client.last_message_processed_id = ""
        mock_redis = MagicMock()
        assert stream_client.starting_point("test_user", mock_redis) == "0"

    def test_starting_point_with_last_processed(self, stream_client):
        stream_client.last_message_processed_id = "1234-0"
        mock_redis = MagicMock()
        mock_redis.xrange.return_value = []
        assert stream_client.starting_point("test_user", mock_redis) == "$"


class TestFormatIsValid:
    def test_format_is_valid_true(self, stream_client, mock_print_fn):
        stream_client.format_is_valid(True, "test_object", "test_name", mock_print_fn)
        mock_print_fn.assert_not_called()

    def test_format_is_valid_false(self, stream_client, mock_print_fn):
        with pytest.raises(ValueError) as context:
            stream_client.format_is_valid(
                False, "test_object", "test_name", mock_print_fn
            )

        assert "Invalid test_name format" in str(context.value)
        mock_print_fn.assert_not_called()


class TestProcessMessage:
    @patch("src.cli.stream_client.Response.model_validate_json")
    def test_process_valid_message(
        self, mock_validate_json, stream_client, mock_print_fn
    ):
        mock_response = MagicMock()
        mock_response.response = "Test response"
        mock_validate_json.return_value = mock_response
        message_data = json.dumps(
            {"query": "test", "response": "Test response", "done": "true"}
        )

        stream_client.process_message("1234-0", message_data, mock_print_fn)

        mock_print_fn.assert_called_once_with("Test response", end="")

    @patch("src.cli.stream_client.Response.model_validate_json")
    def test_process_invalid_message(
        self, mock_validate_json, stream_client, mock_print_fn
    ):
        mock_validate_json.side_effect = Exception("Validation failed")
        message_data = "invalid data"

        stream_client.process_message("1234-0", message_data, mock_print_fn)

        mock_print_fn.assert_called_once_with("\nMessage: invalid data", "error")


class TestProcessRedisResponse:
    def test_process_redis_response_valid_format(self, stream_client, mock_print_fn):
        stream_client.last_message_processed_id = ""
        valid_data = json.dumps(
            {"query": "test", "response": "Test response", "done": "true"}
        )
        mock_response = [["stream_name", [("1234-0", valid_data)]]]

        with patch.object(stream_client, "process_message") as mock_process_message:
            stream_client.process_redis_response(mock_response, mock_print_fn)

            mock_process_message.assert_called_once_with(
                "1234-0", valid_data, mock_print_fn
            )
            assert stream_client.last_message_processed_id == "1234-0"

    def test_process_redis_response_invalid_format_response_level(
        self, stream_client, mock_print_fn
    ):
        with pytest.raises(ValueError):
            stream_client.process_redis_response("not_a_list", mock_print_fn)

        mock_print_fn.assert_called_with(
            "Error processing message: Invalid response format", "error"
        )

    def test_process_redis_response_invalid_format_stream_entry_level(
        self, stream_client, mock_print_fn
    ):
        with pytest.raises(ValueError):
            stream_client.process_redis_response([123], mock_print_fn)

        mock_print_fn.assert_called_with(
            "Error processing message: Invalid stream_entry format", "error"
        )

    def test_process_redis_response_invalid_format_messages_level(
        self, stream_client, mock_print_fn
    ):
        with pytest.raises(ValueError):
            stream_client.process_redis_response(
                [["stream_name", "not_a_list"]], mock_print_fn
            )

        mock_print_fn.assert_called_with(
            "Error processing message: Invalid messages format", "error"
        )

    def test_process_redis_response_invalid_format_message_level(
        self, stream_client, mock_print_fn
    ):
        with pytest.raises(ValueError):
            stream_client.process_redis_response(
                [["stream_name", [123]]], mock_print_fn
            )

        mock_print_fn.assert_called_with(
            "Error processing message: Invalid message format", "error"
        )

    def test_process_redis_response_invalid_format_message_level_missing_index(
        self, stream_client, mock_print_fn
    ):
        with pytest.raises(ValueError):
            stream_client.process_redis_response(
                [["stream_name", [["message_id"]]]], mock_print_fn
            )

        mock_print_fn.assert_called_with(
            "Error processing message: Invalid message format", "error"
        )

    def test_process_redis_exception(self, stream_client, mock_print_fn):
        with patch.object(stream_client, "format_is_valid") as mock_format_validator:
            mock_format_validator.side_effect = Exception("Test exception")

            stream_client.process_redis_response([["test"]], mock_print_fn)

            assert mock_print_fn.call_count == 1
            args = mock_print_fn.call_args[0]
            assert "Error processing message" in args[0]
            assert args[1] == "error"


class TestReadFromStream:
    @patch("src.cli.stream_client.StreamClient.create_redis_connection")
    def test_read_from_stream_no_redis(
        self, mock_create_connection, stream_client, mock_print_fn
    ):
        mock_create_connection.return_value = None

        stream_client.read_from_stream("test_user", mock_print_fn)

        mock_print_fn.assert_not_called()

    @patch("src.cli.stream_client.StreamClient.create_redis_connection")
    def test_read_from_stream_redis_error(
        self, mock_create_connection, stream_client, mock_print_fn
    ):
        mock_redis = MagicMock()
        mock_redis.xread.side_effect = RedisError("Redis error")
        mock_create_connection.return_value = mock_redis

        stream_client.read_from_stream("test_user", mock_print_fn)

        mock_print_fn.assert_called_once_with(
            "Error connecting to message stream: Redis error", "error"
        )

    @patch("src.cli.stream_client.StreamClient.create_redis_connection")
    def test_read_from_stream_success(
        self, mock_create_connection, stream_client, mock_print_fn
    ):
        mock_redis = MagicMock()

        mock_redis.xread.side_effect = [
            [
                ["stream_name", [["1234-0", "message_data"]]]
            ],  # First call: return message
            [],  # Second call: no messages
            Exception("Test loop break"),  # Break the infinite loop for testing
        ]

        mock_create_connection.return_value = mock_redis

        with patch.object(stream_client, "process_redis_response") as mock_process:
            try:
                stream_client.read_from_stream("test_user", mock_print_fn)
            except Exception as e:
                assert str(e) == "Test loop break"

            mock_process.assert_called_once()
