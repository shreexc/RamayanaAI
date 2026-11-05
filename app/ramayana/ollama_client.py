"""Small, bounded Ollama client helpers."""

from __future__ import annotations

import os
import urllib.request

import ollama


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")


def client() -> ollama.Client:
    return ollama.Client(host=OLLAMA_URL, timeout=90)


def available() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2):
            return True
    except OSError:
        return False


def embed_text(text: str, model: str) -> list[float] | None:
    if not available():
        return None
    try:
        result = client().embed(model=model, input=text)
        embeddings = result.get("embeddings", [])
        return embeddings[0] if embeddings else None
    except Exception:
        return None


def generate(prompt: str, model: str, max_tokens: int = 128) -> str | None:
    if not available():
        return None
    try:
        result = client().generate(
            model=model,
            prompt=prompt,
            stream=False,
            options={"num_predict": max_tokens, "num_ctx": 3072, "temperature": 0.1, "num_thread": 8},
        )
        return result.response.strip() or None
    except Exception:
        return None
