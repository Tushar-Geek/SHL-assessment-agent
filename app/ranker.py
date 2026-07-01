from __future__ import annotations

import re
from collections import Counter

from app.models import Assessment, RankedAssessment
from app.vector_store import SearchHit

_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+")


class AssessmentRanker:
    def rank(self, query: str, hits: list[SearchHit], constraints: dict[str, object], limit: int = 10) -> list[RankedAssessment]:
        query_tokens = Counter(_tokens(query))
        ranked: list[RankedAssessment] = []
        for hit in hits:
            metadata_score, reasons = self._metadata_score(hit.assessment, constraints)
            skill_score, skill_reasons = self._skill_overlap(query_tokens, hit.assessment)
            description_score = self._description_overlap(query_tokens, hit.assessment)
            score = (0.55 * hit.score) + (0.2 * skill_score) + (0.15 * metadata_score) + (0.1 * description_score)
            ranked.append(
                RankedAssessment(
                    assessment=hit.assessment,
                    score=round(float(score), 4),
                    reasons=(skill_reasons + reasons)[:4],
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[: max(1, min(limit, 10))]

    def _metadata_score(self, assessment: Assessment, constraints: dict[str, object]) -> tuple[float, list[str]]:
        if not constraints:
            return 0.5, []
        total = 0
        matched = 0
        reasons: list[str] = []
        if "remote_testing" in constraints:
            total += 1
            if assessment.remote_testing is constraints["remote_testing"]:
                matched += 1
                reasons.append("supports remote testing")
        max_duration = constraints.get("max_duration")
        if isinstance(max_duration, int):
            total += 1
            if assessment.duration is not None and assessment.duration <= max_duration:
                matched += 1
                reasons.append(f"fits the {max_duration} minute limit")
        levels = constraints.get("job_level")
        if isinstance(levels, list) and levels:
            total += 1
            assessment_levels = {level.lower() for level in assessment.job_level}
            if assessment_levels.intersection(str(level).lower() for level in levels):
                matched += 1
                reasons.append("matches requested seniority")
        return (matched / total if total else 0.5), reasons

    def _skill_overlap(self, query_tokens: Counter[str], assessment: Assessment) -> tuple[float, list[str]]:
        skill_tokens = set()
        for skill in assessment.skills_measured:
            skill_tokens.update(_tokens(skill))
        overlap = set(query_tokens).intersection(skill_tokens)
        reasons = []
        if overlap:
            shown = ", ".join(sorted(overlap)[:3])
            reasons.append(f"skill overlap: {shown}")
        return min(1.0, len(overlap) / max(1, min(len(skill_tokens), 8))), reasons

    def _description_overlap(self, query_tokens: Counter[str], assessment: Assessment) -> float:
        description_tokens = set(_tokens(assessment.description + " " + assessment.test_type + " " + assessment.assessment_family))
        overlap = set(query_tokens).intersection(description_tokens)
        return min(1.0, len(overlap) / max(1, min(len(description_tokens), 12)))


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]
