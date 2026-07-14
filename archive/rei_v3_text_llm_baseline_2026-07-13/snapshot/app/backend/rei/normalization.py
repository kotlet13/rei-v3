from __future__ import annotations

import re
from typing import Any


MIND_ALIASES = {
    "r": "racio",
    "racio": "racio",
    "rational": "racio",
    "reason": "racio",
    "reasoning": "racio",
    "e": "emocio",
    "emocio": "emocio",
    "emotion": "emocio",
    "emotional": "emocio",
    "i": "instinkt",
    "instinkt": "instinkt",
    "instinct": "instinkt",
    "instinctive": "instinkt",
}

EXTENDED_ALIASES = {
    **MIND_ALIASES,
    "mixed": "mixed",
    "tie": "tie",
    "unknown": "unknown",
    "none": "unknown",
    "null": "unknown",
    "": "unknown",
}


def normalize_mind_name(value: Any, extended: bool = True) -> str:
    raw = str(value or "").strip().lower()
    aliases = EXTENDED_ALIASES if extended else MIND_ALIASES
    if raw in aliases:
        return aliases[raw]
    tokens = [token for token in re.split(r"[^a-z]+", raw) if token]
    mapped = [MIND_ALIASES[token] for token in tokens if token in MIND_ALIASES]
    unique = []
    for mind in mapped:
        if mind not in unique:
            unique.append(mind)
    if extended and len(unique) > 1:
        return "mixed"
    if unique:
        return unique[0]
    return "unknown" if extended else "racio"


def normalize_mind_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str) and value.strip():
        raw_items = re.split(r"[,/+&]|\band\b|\bin\b", value, flags=re.IGNORECASE)
    else:
        raw_items = []

    normalized: list[str] = []
    for item in raw_items:
        mind = normalize_mind_name(item, extended=False)
        if mind not in normalized:
            normalized.append(mind)
    return normalized
