"""A caching gateway in front of a local LLM.

Every question is checked against the Redis semantic cache first. A close enough
match comes back in milliseconds and never touches the model. A new question
goes to the model once, and the answer is cached for next time. Each client is
also rate limited in Redis.
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import models
import store
from ratelimit import RateLimiter

app = FastAPI(title="LLM Cache Gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_r = store.client()
cache = store.SemanticCache(_r)
limiter = RateLimiter(_r)


class Ask(BaseModel):
    question: str


def _client_id(request: Request) -> str:
    return request.headers.get("X-Client-Id") or (request.client.host if request.client else "anon")


@app.get("/health")
def health() -> dict:
    try:
        _r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok", "redis": redis_ok, "embed_model": models.EMBED_MODEL, "answer_model": models.ANSWER_MODEL}


@app.post("/ask")
async def ask(body: Ask, request: Request):
    question = body.question.strip()
    if not question:
        return JSONResponse(status_code=400, content={"detail": "Ask something."})

    client = _client_id(request)
    allowed, count, limit = limiter.check(client)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit reached ({limit} per minute). Slow down a touch."},
            headers={"Retry-After": "5"},
        )

    t0 = time.perf_counter()
    embedding = models.embed(question)
    hit = cache.lookup(embedding)
    if hit:
        ms = (time.perf_counter() - t0) * 1000
        return {
            "answer": hit["answer"],
            "cached": True,
            "similarity": round(hit["similarity"], 4),
            "matched_question": hit["matched_question"],
            "latency_ms": round(ms, 1),
            "requests_this_minute": count,
            "rate_limit": limit,
        }

    reply = models.answer(question)
    cache.store(question, embedding, reply, models.ANSWER_MODEL)
    ms = (time.perf_counter() - t0) * 1000
    return {
        "answer": reply,
        "cached": False,
        "similarity": None,
        "matched_question": None,
        "latency_ms": round(ms, 1),
        "requests_this_minute": count,
        "rate_limit": limit,
    }


@app.get("/stats")
def stats() -> dict:
    return cache.stats()


@app.get("/recent")
def recent() -> dict:
    return {"recent": cache.recent(8)}


@app.post("/clear")
def clear() -> dict:
    cache.clear()
    return {"cleared": True}
