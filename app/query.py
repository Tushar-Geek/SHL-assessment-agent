from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class QueryIntent:
    action: str
    query: str
    constraints: dict[str, object] = field(default_factory=dict)


TECH_SKILLS = {
    "python", "java", "javascript", "sql", "excel", "data", "analytics", "coding",
    "developer", "software", "numerical", "deductive", "inductive", "verbal",
    "sales", "customer", "service", "leadership", "personality", "motivation",
}


def parse_intent(messages: list[dict[str, str]]) -> QueryIntent:
    latest_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    full_context = "\n".join(m["content"] for m in messages if m["role"] in {"user", "assistant"})
    lowered = latest_user.lower()
    action = "recommend"
    if any(word in lowered for word in ("compare", "difference", "versus", " vs ")):
        action = "compare"
    elif any(word in lowered for word in ("instead", "refine", "change", "shorter", "longer", "only", "exclude")):
        action = "refine"
    constraints: dict[str, object] = {}
    duration = _duration_limit(lowered)
    if duration:
        constraints["max_duration"] = duration
    if "remote" in lowered:
        constraints["remote_testing"] = True
    for level in ("entry", "graduate", "professional", "manager", "leader", "executive"):
        if level in lowered:
            constraints.setdefault("job_level", []).append(level)
    return QueryIntent(action=action, query=full_context, constraints=constraints)


def is_vague(text: str, min_chars: int) -> bool:
    lowered = text.lower().strip()
    tokens = re.findall(r"[a-zA-Z0-9+#.]+", lowered)
    skill_hits = TECH_SKILLS.intersection(tokens)
    role_words = {"hire", "hiring", "candidate", "role", "job", "assessment", "test"}.intersection(tokens)
    return len(lowered) < min_chars or (len(tokens) < 5 and not skill_hits and not role_words)


def _duration_limit(text: str) -> int | None:
    match = re.search(r"(?:under|less than|within|max(?:imum)?|<=?)\s*(\d{1,3})\s*(?:min|mins|minutes)?", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d{1,3})\s*(?:min|mins|minutes)", text)
    if match and any(word in text for word in ("under", "less", "within", "short", "max")):
        return int(match.group(1))
    return None
