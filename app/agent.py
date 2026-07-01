from __future__ import annotations

from app.catalog import CatalogRepository
from app.config import Settings
from app.llm import LLMClient
from app.query import is_vague, parse_intent
from app.ranker import AssessmentRanker
from app.safety import refusal_reason
from app.schemas import ChatMessage, ChatResponse, RecommendationOut
from app.vector_store import VectorStore


class SHLRecommendationAgent:
    def __init__(
        self,
        settings: Settings,
        catalog: CatalogRepository,
        vector_store: VectorStore,
        ranker: AssessmentRanker,
        llm_client: LLMClient,
    ):
        self.settings = settings
        self.catalog = catalog
        self.vector_store = vector_store
        self.ranker = ranker
        self.llm_client = llm_client

    async def chat(self, messages: list[ChatMessage]) -> ChatResponse:
        history = [message.model_dump() for message in messages]
        latest_user = next(message.content for message in reversed(messages) if message.role == "user")
        refusal = refusal_reason(latest_user)
        if refusal:
            return ChatResponse(reply=refusal, recommendations=[], end_of_conversation=False)
        if is_vague(latest_user, self.settings.min_query_chars):
            return ChatResponse(
                reply="What role, skills, seniority level, and time limit should I optimize the SHL assessment recommendations for?",
                recommendations=[],
                end_of_conversation=False,
            )
        intent = parse_intent(history)
        if intent.action == "compare":
            return await self._compare(latest_user, history)
        return await self._recommend(intent.query, intent.constraints, history)

    async def _recommend(self, query: str, constraints: dict[str, object], history: list[dict[str, str]]) -> ChatResponse:
        filters = _filters_from_constraints(constraints)
        hits = await self.vector_store.search(query, top_k=self.settings.top_k, filters=filters)
        ranked = self.ranker.rank(query, hits, constraints, limit=self.settings.top_k)
        if not ranked and filters:
            hits = await self.vector_store.search(query, top_k=self.settings.top_k)
            ranked = self.ranker.rank(query, hits, constraints, limit=self.settings.top_k)
        if not ranked:
            return ChatResponse(
                reply="I could not find a matching SHL catalog assessment from the loaded catalog. Try adding the role, skills, or assessment type.",
                recommendations=[],
                end_of_conversation=False,
            )
        recs = [
            RecommendationOut(name=item.assessment.name, url=str(item.assessment.catalog_url), test_type=item.assessment.test_type)
            for item in ranked
        ]
        reply = self._recommendation_reply(ranked)
        llm_reply = await self.llm_client.complete([*history, {"role": "assistant", "content": "Catalog recommendations: " + reply}])
        return ChatResponse(reply=llm_reply or reply, recommendations=recs, end_of_conversation=False)

    async def _compare(self, latest_user: str, history: list[dict[str, str]]) -> ChatResponse:
        mentioned = self.catalog.find_mentions(latest_user)
        if len(mentioned) < 2:
            hits = await self.vector_store.search(latest_user, top_k=4)
            mentioned = [hit.assessment for hit in hits[:2]]
        if len(mentioned) < 2:
            return ChatResponse(
                reply="Which two SHL assessments should I compare? Please provide their catalog names.",
                recommendations=[],
                end_of_conversation=False,
            )
        left, right = mentioned[0], mentioned[1]
        reply = (
            f"{left.name} is a {left.test_type} assessment in the {left.assessment_family} family. "
            f"It measures {', '.join(left.skills_measured) or 'catalog-listed skills'} and takes {left.duration or 'an unspecified number of'} minutes. "
            f"{right.name} is a {right.test_type} assessment in the {right.assessment_family} family. "
            f"It measures {', '.join(right.skills_measured) or 'catalog-listed skills'} and takes {right.duration or 'an unspecified number of'} minutes. "
            "Choose the assessment whose catalog skills and job level are closer to the hiring need."
        )
        recs = [RecommendationOut(name=item.name, url=str(item.catalog_url), test_type=item.test_type) for item in (left, right)]
        llm_reply = await self.llm_client.complete([*history, {"role": "assistant", "content": reply}])
        return ChatResponse(reply=llm_reply or reply, recommendations=recs, end_of_conversation=False)

    def _recommendation_reply(self, ranked) -> str:
        lines = ["Based on the loaded SHL catalog, I recommend:"]
        for index, item in enumerate(ranked, start=1):
            assessment = item.assessment
            reason = "; ".join(item.reasons) if item.reasons else assessment.description[:140]
            duration = f", {assessment.duration} minutes" if assessment.duration else ""
            lines.append(f"{index}. {assessment.name} ({assessment.test_type}{duration}) - {reason}. Catalog: {assessment.catalog_url}")
        return "\n".join(lines)


def _filters_from_constraints(constraints: dict[str, object]) -> dict[str, object]:
    filters: dict[str, object] = {}
    if "remote_testing" in constraints:
        filters["remote_testing"] = constraints["remote_testing"]
    if "job_level" in constraints:
        filters["job_level"] = constraints["job_level"]
    return filters
