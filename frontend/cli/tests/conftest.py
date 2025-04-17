import pytest
from unittest.mock import MagicMock


class MockRedis:
    """Mock Redis class for testing."""

    def __init__(self, host=None, port=None, password=None, decode_responses=None):
        self.host = host
        self.port = port
        self.password = password
        self.decode_responses = decode_responses
        self.xread = MagicMock()
        self.ping = MagicMock()


@pytest.fixture
def mock_redis_class(monkeypatch):
    """Mock Redis class for dependency injection."""
    mock_redis = MagicMock()
    monkeypatch.setattr("redis.Redis", mock_redis)
    return mock_redis
