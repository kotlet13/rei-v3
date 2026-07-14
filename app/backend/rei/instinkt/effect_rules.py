"""Strict loader for the canonical C5 Instinkt body-effect rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..models.instinkt_effects import (
    CueConflictPair,
    EmbodiedCueRule,
    InstinktEffectRuleSet,
)


DEFAULT_EFFECT_RULES_PATH = (
    Path(__file__).resolve().parents[4]
    / "knowledge"
    / "canon_v2"
    / "instinkt_effect_rules.yaml"
)
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "revision",
        "canonical_source_status",
        "minimum_association_score",
        "rules",
        "conflict_pairs",
    }
)


class EffectRuleConfigurationError(ValueError):
    """Raised when effect-rule configuration is malformed or incomplete."""


def _object_list(value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise EffectRuleConfigurationError(f"{field_name} must be a JSON array of objects")
    return value


def load_instinkt_effect_rules(
    path: str | Path = DEFAULT_EFFECT_RULES_PATH,
) -> InstinktEffectRuleSet:
    """Load JSON-syntax YAML with no implicit YAML coercion or hidden defaults."""

    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EffectRuleConfigurationError(
            f"Cannot load Instinkt effect rules from {source_path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise EffectRuleConfigurationError("Effect-rule document must be a JSON object")
    if frozenset(raw) != _TOP_LEVEL_KEYS:
        missing = sorted(_TOP_LEVEL_KEYS - frozenset(raw))
        extra = sorted(frozenset(raw) - _TOP_LEVEL_KEYS)
        raise EffectRuleConfigurationError(
            f"Effect-rule top-level keys differ; missing={missing}, extra={extra}"
        )
    if raw["schema_version"] != "rei-native-instinkt-effect-rules-v1":
        raise EffectRuleConfigurationError("Unsupported effect-rule schema_version")
    if raw["canonical_source_status"] != "implementation_hypothesis":
        raise EffectRuleConfigurationError(
            "Effect rules must declare implementation_hypothesis status"
        )
    try:
        rules = tuple(
            EmbodiedCueRule.model_validate_json(json.dumps(item))
            for item in _object_list(raw["rules"], field_name="rules")
        )
        conflict_pairs = tuple(
            CueConflictPair.model_validate_json(json.dumps(item))
            for item in _object_list(raw["conflict_pairs"], field_name="conflict_pairs")
        )
        ruleset = InstinktEffectRuleSet.create(
            revision=raw["revision"],
            minimum_association_score=raw["minimum_association_score"],
            rules=rules,
            conflict_pairs=conflict_pairs,
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise EffectRuleConfigurationError(
            f"Invalid Instinkt effect-rule contract: {exc}"
        ) from exc
    return InstinktEffectRuleSet.model_validate(
        ruleset.model_dump(mode="python", round_trip=True)
    )


__all__ = [
    "DEFAULT_EFFECT_RULES_PATH",
    "EffectRuleConfigurationError",
    "load_instinkt_effect_rules",
]
