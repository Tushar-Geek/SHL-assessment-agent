from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from app.catalog import CatalogRepository
from app.config import get_settings
from app.embeddings import get_embedding_provider
from app.ranker import AssessmentRanker
from app.vector_store import VectorStore

EVAL_QUERIES = [
    {"query": "Python developer coding assessment under 45 minutes", "expected": ["Python"]},
    {"query": "numerical reasoning test for graduate analyst remote", "expected": ["Numerical"]},
    {"query": "personality questionnaire for managers", "expected": ["OPQ"]},
]


async def main() -> None:
    settings = get_settings()
    catalog = CatalogRepository(settings.catalog_path)
    store = VectorStore(get_embedding_provider(settings), catalog.load())
    ranker = AssessmentRanker()
    results = []
    recalls = []
    precisions = []
    latencies = []
    hallucination_flags = []
    catalog_urls = {str(item.catalog_url) for item in catalog.load()}
    for case in EVAL_QUERIES:
        start = time.perf_counter()
        hits = await store.search(case["query"], top_k=10)
        ranked = ranker.rank(case["query"], hits, {}, limit=10)
        latency = time.perf_counter() - start
        names = [item.assessment.name for item in ranked]
        urls = [str(item.assessment.catalog_url) for item in ranked]
        expected_hits = [needle for needle in case["expected"] if any(needle.lower() in name.lower() for name in names)]
        recall = len(expected_hits) / len(case["expected"])
        precision = len(expected_hits) / max(1, len(names))
        hallucinated = any(url not in catalog_urls for url in urls)
        recalls.append(recall)
        precisions.append(precision)
        latencies.append(latency)
        hallucination_flags.append(hallucinated)
        results.append({"query": case["query"], "top_names": names, "latency_seconds": latency, "recall": recall, "precision": precision})
    report = {
        "recall_at_10": sum(recalls) / len(recalls),
        "precision": sum(precisions) / len(precisions),
        "average_latency_seconds": sum(latencies) / len(latencies),
        "hallucination_rate": sum(1 for flag in hallucination_flags if flag) / len(hallucination_flags),
        "conversation_turns_supported": ["clarification", "recommendation", "refinement", "comparison", "refusal"],
        "response_quality_notes": "Quality is estimated with expected-name matches and URL grounding; expand EVAL_QUERIES with assignment gold cases for production scoring.",
        "cases": results,
    }
    output = Path("evaluation_report.json")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
