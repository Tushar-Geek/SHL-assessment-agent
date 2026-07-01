from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

import httpx
import numpy as np

from app.config import Settings

_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+")


class EmbeddingProvider:
    async def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


@dataclass
class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embeddings for tests and offline development."""

    dimensions: int = 512

    async def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimensions), dtype="float32")
        for row, text in enumerate(texts):
            for token in _tokens(text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                matrix[row, index] += sign
            norm = math.sqrt(float(np.dot(matrix[row], matrix[row])))
            if norm > 0:
                matrix[row] /= norm
        return matrix


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI-compatible embeddings")
        self.settings = settings

    async def embed(self, texts: list[str]) -> np.ndarray:
        url = f"{self.settings.openai_base_url.rstrip('/')}/embeddings"
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(
                url,
                headers=headers,
                json={"model": self.settings.embedding_model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
        vectors = [item["embedding"] for item in payload["data"]]
        matrix = np.array(vectors, dtype="float32")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return matrix / norms


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.openai_api_key:
        return OpenAICompatibleEmbeddingProvider(settings)
    return HashingEmbeddingProvider()


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]
