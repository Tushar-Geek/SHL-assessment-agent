from __future__ import annotations

from functools import lru_cache

from app.agent import SHLRecommendationAgent
from app.catalog import CatalogRepository
from app.config import get_settings
from app.embeddings import get_embedding_provider
from app.llm import LLMClient
from app.ranker import AssessmentRanker
from app.vector_store import VectorStore


@lru_cache
def get_agent() -> SHLRecommendationAgent:
    settings = get_settings()
    catalog = CatalogRepository(settings.catalog_path)
    assessments = catalog.load()
    embeddings = get_embedding_provider(settings)
    vector_store = VectorStore(embeddings, assessments)
    return SHLRecommendationAgent(settings, catalog, vector_store, AssessmentRanker(), LLMClient(settings))
