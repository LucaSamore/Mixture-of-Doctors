import pytest
from unittest.mock import MagicMock, patch
from src.cli.stream_client import StreamClient


class MockRedis:
    """Mock Redis class for testing."""

    def __init__(self, host=None, port=None, password=None, decode_responses=None):
        self.host = host
        self.port = port
        self.password = password
        self.decode_responses = decode_responses
        self.xread = MagicMock()
        self.ping = MagicMock()
        self.xrevrange = MagicMock(return_value=[])
        self.xrange = MagicMock(return_value=[])


@pytest.fixture
def mock_redis_class(monkeypatch):
    mock_redis = MagicMock()
    monkeypatch.setattr("redis.Redis", mock_redis)
    return mock_redis


@pytest.fixture
def mock_redis_instance():
    mock_redis = MockRedis()
    return mock_redis


@pytest.fixture
def stream_client(mock_redis_instance):
    with patch("src.cli.stream_client.Redis", return_value=mock_redis_instance):
        client = StreamClient()

        original_create_redis = client.create_redis_connection
        client.create_redis_connection = lambda: mock_redis_instance

        yield client

        client.create_redis_connection = original_create_redis
