from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import numpy as np

from app.embeddings import EmbeddingProvider
from app.models import Assessment

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    assessment: Assessment
    score: float


class VectorStore:
    """FAISS-backed semantic search with a NumPy fallback for local tests."""

    def __init__(self, embedding_provider: EmbeddingProvider, assessments: list[Assessment]):
        self.embedding_provider = embedding_provider
        self.assessments = assessments
        self._matrix: np.ndarray | None = None
        self._faiss_index = None

    async def build(self) -> None:
        texts = [assessment.search_text for assessment in self.assessments]
        self._matrix = await self.embedding_provider.embed(texts)
        try:
            import faiss  # type: ignore

            index = faiss.IndexFlatIP(self._matrix.shape[1])
            index.add(self._matrix)
            self._faiss_index = index
            logger.info("Built FAISS index with %s records", len(self.assessments))
        except Exception as exc:  # pragma: no cover
            self._faiss_index = None
            logger.warning("FAISS unavailable, using NumPy vector search: %s", exc)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, object] | None = None,
    ) -> list[SearchHit]:
        if self._matrix is None:
            await self.build()
        assert self._matrix is not None
        query_vector = (await self.embedding_provider.embed([query]))[0]
        k = min(max(top_k * 3, top_k), len(self.assessments))
        if self._faiss_index is not None:
            scores, indexes = self._faiss_index.search(np.array([query_vector], dtype="float32"), k)
            raw_hits = [(int(idx), float(score)) for idx, score in zip(indexes[0], scores[0]) if idx >= 0]
        else:
            sims = self._matrix @ query_vector
            indexes = np.argsort(-sims)[:k]
            raw_hits = [(int(idx), float(sims[idx])) for idx in indexes]
        hits = [SearchHit(self.assessments[idx], score) for idx, score in raw_hits]
        filtered = [hit for hit in hits if _matches_filters(hit.assessment, filters or {})]
        return filtered[:top_k]

    def search_sync(self, query: str, top_k: int = 10, filters: dict[str, object] | None = None) -> list[SearchHit]:
        return asyncio.run(self.search(query, top_k=top_k, filters=filters))


def _matches_filters(assessment: Assessment, filters: dict[str, object]) -> bool:
    for key, expected in filters.items():
        if expected in (None, "", [], {}):
            continue
        value = getattr(assessment, key, assessment.structured_metadata.get(key))
        if isinstance(value, list):
            values = {str(item).lower() for item in value}
            if isinstance(expected, list):
                if not values.intersection(str(item).lower() for item in expected):
                    return False
            elif str(expected).lower() not in values:
                return False
        elif isinstance(value, bool):
            if bool(expected) is not value:
                return False
        elif str(expected).lower() not in str(value).lower():
            return False
    return True
