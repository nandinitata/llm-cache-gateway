"""Show what the cache buys you.

Sends a batch of questions where many are repeats or rewordings of each other.
Reports the hit rate, the average latency for cache hits vs model calls, and the
wall-clock time saved versus going to the model every time.

Run (Redis + Ollama up):
    python bench/benchmark.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models  # noqa: E402
import store  # noqa: E402

# the same few questions, asked in different words -> should mostly hit after the first of each
QUESTIONS = [
    "What is the capital of France?",
    "Which city is the capital of France?",
    "Tell me the capital city of France.",
    "What is the capital of Japan?",
    "What's Japan's capital city?",
    "Explain what a hash map is in one sentence.",
    "In one sentence, what is a hash map?",
    "What is the capital of France?",
    "How does a hash map work, briefly?",
    "What is the capital of Japan?",
]


def main():
    r = store.client()
    cache = store.SemanticCache(r)
    cache.clear()

    hit_ms, miss_ms = [], []
    for q in QUESTIONS:
        t0 = time.perf_counter()
        emb = models.embed(q)
        hit = cache.lookup(emb)
        if hit:
            hit_ms.append((time.perf_counter() - t0) * 1000)
            print(f"  HIT  ({hit['similarity']:.3f})  {q}")
        else:
            models_answer = models.answer(q)
            cache.store(q, emb, models_answer, models.ANSWER_MODEL)
            miss_ms.append((time.perf_counter() - t0) * 1000)
            print(f"  miss          {q}")

    n = len(QUESTIONS)
    hits = len(hit_ms)
    avg_hit = sum(hit_ms) / len(hit_ms) if hit_ms else 0
    avg_miss = sum(miss_ms) / len(miss_ms) if miss_ms else 0
    # time saved = hits that would otherwise have cost a model call
    saved_ms = hits * avg_miss - sum(hit_ms)

    print("\n" + "=" * 54)
    print(f"questions:        {n}")
    print(f"cache hit rate:   {hits}/{n} = {hits / n:.0%}")
    print(f"avg hit latency:  {avg_hit:6.1f} ms")
    print(f"avg model call:   {avg_miss:6.1f} ms")
    if avg_hit:
        print(f"hits are ~{avg_miss / avg_hit:.0f}x faster than a model call")
    print(f"wall-clock saved: {saved_ms / 1000:.1f} s over this batch")


if __name__ == "__main__":
    main()
