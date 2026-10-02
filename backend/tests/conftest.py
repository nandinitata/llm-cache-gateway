"""Point every test at Redis db 15 before anything imports the app or store."""
import os

os.environ["REDIS_URL"] = "redis://localhost:6379/15"

import pytest  # noqa: E402
import redis  # noqa: E402

import store  # noqa: E402


@pytest.fixture
def r():
    try:
        conn = store.client()
        conn.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip("Redis isn't running")
    conn.flushdb()
    yield conn
    conn.flushdb()
