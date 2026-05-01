from __future__ import annotations

from typing import Mapping, Optional


DEFAULT_PROFILE = "R=E=I"

PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    "R>(E=I)": {"racio": 0.50, "emocio": 0.25, "instinkt": 0.25},
    "E>(R=I)": {"racio": 0.25, "emocio": 0.50, "instinkt": 0.25},
    "I>(R=E)": {"racio": 0.25, "emocio": 0.25, "instinkt": 0.50},
    "(R=E)>I": {"racio": 0.40, "emocio": 0.40, "instinkt": 0.20},
    "(R=I)>E": {"racio": 0.40, "emocio": 0.20, "instinkt": 0.40},
    "(E=I)>R": {"racio": 0.20, "emocio": 0.40, "instinkt": 0.40},
    "R>E>I": {"racio": 0.50, "emocio": 0.30, "instinkt": 0.20},
    "R>I>E": {"racio": 0.50, "emocio": 0.20, "instinkt": 0.30},
    "E>R>I": {"racio": 0.30, "emocio": 0.50, "instinkt": 0.20},
    "E>I>R": {"racio": 0.20, "emocio": 0.50, "instinkt": 0.30},
    "I>R>E": {"racio": 0.30, "emocio": 0.20, "instinkt": 0.50},
    "I>E>R": {"racio": 0.20, "emocio": 0.30, "instinkt": 0.50},
    "R=E=I": {"racio": 1 / 3, "emocio": 1 / 3, "instinkt": 1 / 3},
}

PROFILE_ALIASES = {
    "R": "R>(E=I)",
    "E": "E>(R=I)",
    "I": "I>(R=E)",
    "RE": "(R=E)>I",
    "RI": "(R=I)>E",
    "EI": "(E=I)>R",
    "REI": "R=E=I",
    "R>E=I": "R>(E=I)",
    "E>R=I": "E>(R=I)",
    "I>R=E": "I>(R=E)",
    "R=E>I": "(R=E)>I",
    "R=I>E": "(R=I)>E",
    "E=I>R": "(E=I)>R",
}


def normalize_profile(profile: Optional[str]) -> str:
    raw = (profile or DEFAULT_PROFILE).strip()
    compact = "".join(raw.split())
    return PROFILE_ALIASES.get(compact, compact if compact in PROFILE_WEIGHTS else DEFAULT_PROFILE)


def profile_weights(profile: Optional[str]) -> tuple[str, dict[str, float]]:
    normalized = normalize_profile(profile)
    return normalized, dict(PROFILE_WEIGHTS[normalized])


def strongest_mind(weights: Mapping[str, float]) -> str:
    return max(weights, key=weights.get)


def weakest_mind(weights: Mapping[str, float]) -> str:
    return min(weights, key=weights.get)
