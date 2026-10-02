"""API tests. Validation + the 429 path run without a model. The live /ask
path (embed + answer) needs Ollama, so it's gated behind GATEWAY_RUN_LIVE=1."""
import os

import pytest
from fastapi.testclient import TestClient

import main
from ratelimit import RateLimiter

client = TestClient(main.app)


def test_health(r):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["redis"] is True


def test_empty_question_is_rejected(r):
    assert client.post("/ask", json={"question": "  "}).status_code == 400


def test_rate_limit_returns_429(r, monkeypatch):
    # a zero-limit limiter rejects before any model call, so no Ollama needed
    monkeypatch.setattr(main, "limiter", RateLimiter(r, limit=0, window_s=60))
    resp = client.post("/ask", json={"question": "anything"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_stats_endpoint(r):
    body = client.get("/stats").json()
    assert set(["hits", "misses", "total", "hit_rate", "entries"]).issubset(body)


@pytest.mark.skipif(os.environ.get("GATEWAY_RUN_LIVE") != "1", reason="needs Ollama")
def test_ask_caches_the_second_time(r, monkeypatch):
    monkeypatch.setattr(main, "limiter", RateLimiter(r, limit=100, window_s=60))
    q = {"question": "What is 2 plus 2?"}
    first = client.post("/ask", json=q).json()
    second = client.post("/ask", json=q).json()
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["latency_ms"] < first["latency_ms"]
