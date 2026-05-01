from __future__ import annotations

import json
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first valid JSON object from model output."""
    source = text.strip()
    if not source:
        raise ValueError("No JSON object found in empty text")

    try:
        parsed = json.loads(source)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    start = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(source):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidate = source[start : index + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    start = None
                    continue
                if isinstance(parsed, dict):
                    return parsed
                start = None

    raise ValueError("No valid JSON object found in model output")


def validate_required_keys(obj: dict[str, Any], required: list[str]) -> list[str]:
    """Return required keys missing from a JSON object."""
    return [key for key in required if key not in obj]


def safe_fallback(agent_name: str, missing_or_error: str) -> dict[str, Any]:
    """Return a minimal safe fallback object if model JSON fails."""
    return {
        "agent": agent_name,
        "error": missing_or_error,
        "confidence": 0.0,
        "uncertainty": "The model output could not be validated, so this fallback avoids overclaiming.",
        "safety_flags": ["invalid_json_fallback"],
    }
