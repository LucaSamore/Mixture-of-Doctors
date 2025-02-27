import json
import pytest
from unittest.mock import AsyncMock, patch
from connection import connect


@pytest.mark.asyncio
async def test_successful_response():
    """Tests receiving a valid response from the WebSocket"""
    mock_websocket = AsyncMock()
    mock_websocket.__aenter__.return_value = mock_websocket
    mock_websocket.__aiter__.return_value = [  # Simulate WebSocket messages
        json.dumps(
            {
                "model": "qwen2.5:72b",
                "created_at": "2025-02-16T11:17:26.823023438Z",
                "response": "Hello!",
                "done": True,
            }
        )
    ]

    with patch("websockets.connect", return_value=mock_websocket):
        responses = [resp async for resp in connect("test_user", "Hello?")]

    assert len(responses) == 1
    assert responses[0].response == "Hello!"
    assert responses[0].done is True


@pytest.mark.asyncio
async def test_invalid_json_response():
    """Tests handling of an invalid JSON message"""
    mock_websocket = AsyncMock()
    mock_websocket.__aenter__.return_value = mock_websocket
    mock_websocket.__aiter__.return_value = [
        "invalid_json",  # Invalid message
        json.dumps(
            {
                "model": "qwen2.5:72b",
                "created_at": "2025-02-16T11:17:26.823023438Z",
                "response": "Valid message",
                "done": True,
            }
        ),
    ]

    with patch("websockets.connect", return_value=mock_websocket):
        responses = [resp async for resp in connect("test_user", "Hello?")]

    assert (
        len(responses) == 1
    )  # Should ignore the invalid message and process the second one
    assert responses[0].response == "Valid message"


@pytest.mark.asyncio
async def test_missing_fields_in_response():
    """Tests handling of a JSON message with missing fields"""
    mock_websocket = AsyncMock()
    mock_websocket.__aenter__.return_value = mock_websocket
    mock_websocket.__aiter__.return_value = [
        json.dumps(
            {
                "model": "qwen2.5:72b",
                "created_at": "2025-02-16T11:17:26.823023438Z",
                "done": True,
            }
        )  # Missing "response" field
    ]

    with patch("websockets.connect", return_value=mock_websocket):
        responses = [resp async for resp in connect("test_user", "Hello?")]

    assert len(responses) == 0  # The message shouldn't be processed


@pytest.mark.asyncio
async def test_websocket_connection_error():
    """Tests handling of a WebSocket connection error"""
    with patch("websockets.connect", side_effect=Exception("Connection failed")):
        responses = [resp async for resp in connect("test_user", "Hello?")]

    assert responses == []  # If connection fails, no responses should be received
