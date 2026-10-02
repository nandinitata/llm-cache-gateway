"""Redis-backed semantic cache.

Repeat and reworded questions should not hit the model twice. Each question is
embedded once; the embedding goes into a Redis Vector Set. A new question is
matched against that set with VSIM, and if something close enough is already
there, the stored answer comes straight back from Redis.

Redis is doing the real work here: the nearest-neighbour search (VADD/VSIM),
the answer store (hashes), and the counters.
"""
from __future__ import annotations

import os
import time

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
VEC_KEY = "cache:vec"
# VSIM similarity runs 0..1, 1 being identical. Above this we call it the same question.
SIM_THRESHOLD = float(os.environ.get("CACHE_SIM_THRESHOLD", "0.93"))


def client(url: str | None = None) -> redis.Redis:
    return redis.from_url(url or REDIS_URL, decode_responses=True)


def _fmt(vec) -> list[str]:
    # fixed-point, so no scientific notation sneaks into the command
    return [f"{float(x):.6f}" for x in vec]


class SemanticCache:
    def __init__(self, r: redis.Redis, threshold: float = SIM_THRESHOLD):
        self.r = r
        self.threshold = threshold

    def lookup(self, embedding) -> dict | None:
        """Return the cached answer for the closest past question, or None."""
        res = self.r.execute_command(
            "VSIM", VEC_KEY, "VALUES", len(embedding), *_fmt(embedding),
            "WITHSCORES", "COUNT", 1,
        )
        if not res:
            self._incr("misses")
            return None
        elem, score = res[0], float(res[1])
        if score < self.threshold:
            self._incr("misses")
            return None
        item = self.r.hgetall(f"cache:item:{elem}")
        if not item:
            self._incr("misses")
            return None
        self._incr("hits")
        return {
            "answer": item["answer"],
            "matched_question": item.get("question"),
            "similarity": score,
            "id": elem,
        }

    def store(self, question: str, embedding, answer: str, model: str) -> str:
        seq = self.r.incr("cache:seq")
        elem = f"q{seq}"
        self.r.execute_command("VADD", VEC_KEY, "VALUES", len(embedding), *_fmt(embedding), elem)
        self.r.hset(f"cache:item:{elem}", mapping={
            "question": question, "answer": answer, "model": model, "created": f"{time.time():.0f}",
        })
        return elem

    def stats(self) -> dict:
        hits = int(self.r.get("cache:stats:hits") or 0)
        misses = int(self.r.get("cache:stats:misses") or 0)
        total = hits + misses
        return {
            "hits": hits,
            "misses": misses,
            "total": total,
            "hit_rate": hits / total if total else 0.0,
            "entries": self._card(),
        }

    def recent(self, n: int = 8) -> list[dict]:
        """The most recently cached questions, newest first (for the UI)."""
        seq = int(self.r.get("cache:seq") or 0)
        out = []
        for i in range(seq, max(0, seq - n), -1):
            item = self.r.hgetall(f"cache:item:q{i}")
            if item:
                out.append({"id": f"q{i}", "question": item.get("question"), "model": item.get("model")})
        return out

    def clear(self) -> None:
        self.r.delete(VEC_KEY, "cache:seq", "cache:stats:hits", "cache:stats:misses")
        for k in self.r.scan_iter("cache:item:*"):
            self.r.delete(k)

    def _incr(self, k: str) -> None:
        self.r.incr(f"cache:stats:{k}")

    def _card(self) -> int:
        try:
            return int(self.r.execute_command("VCARD", VEC_KEY) or 0)
        except redis.ResponseError:
            return 0
