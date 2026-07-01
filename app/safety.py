from __future__ import annotations

import re

INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|system|developer) instructions",
    r"reveal .*prompt",
    r"print .*system prompt",
    r"jailbreak",
    r"developer message",
    r"secret (key|token|prompt)",
    r"act as DAN",
]

OUT_OF_SCOPE_PATTERNS = [
    r"legal advice",
    r"salary",
    r"compensation",
    r"pay band",
    r"offer negotiation",
    r"general hiring advice",
    r"non[- ]?shl",
    r"which ats",
    r"write (a )?job description",
]


def refusal_reason(text: str) -> str | None:
    lowered = text.lower()
    if any(re.search(pattern, lowered) for pattern in INJECTION_PATTERNS):
        return "I can't help with prompt extraction, jailbreaks, or instruction override attempts. I can only recommend SHL assessments using catalog information."
    if any(re.search(pattern, lowered) for pattern in OUT_OF_SCOPE_PATTERNS):
        return "I can only help with SHL assessment recommendations, refinements, and comparisons based on the SHL catalog."
    return None
