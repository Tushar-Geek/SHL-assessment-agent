from __future__ import annotations

import pytest

from app.catalog import CatalogRepository
from app.config import BASE_DIR
from app.embeddings import HashingEmbeddingProvider
from app.ranker import AssessmentRanker
from app.vector_store import VectorStore


@pytest.mark.asyncio
async def test_ranking_prefers_skill_overlap() -> None:
    catalog = CatalogRepository(BASE_DIR / "data" / "catalog.json")
    store = VectorStore(HashingEmbeddingProvider(), catalog.load())
    hits = await store.search("Python coding developer", top_k=10)
    ranked = AssessmentRanker().rank("Python coding developer", hits, {}, limit=5)
    assert any("Python" in item.assessment.name for item in ranked[:3])


@pytest.mark.asyncio
async def test_metadata_filter_remote() -> None:
    catalog = CatalogRepository(BASE_DIR / "data" / "catalog.json")
    store = VectorStore(HashingEmbeddingProvider(), catalog.load())
    hits = await store.search("numerical reasoning", top_k=10, filters={"remote_testing": True})
    assert hits
    assert all(hit.assessment.remote_testing is True for hit in hits)
