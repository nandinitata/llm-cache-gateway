"""Local model calls through Ollama: one to embed, one to answer. Both open."""
from __future__ import annotations

import os

import requests

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "llama3")


def embed(text: str) -> list[float]:
    r = requests.post(f"{OLLAMA}/api/embeddings", json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    r.raise_for_status()
    return r.json()["embedding"]


def answer(question: str, timeout: float = 120.0) -> str:
    r = requests.post(
        f"{OLLAMA}/api/generate",
        json={"model": ANSWER_MODEL, "prompt": question, "stream": False, "options": {"temperature": 0.2}},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json().get("response", "").strip()
