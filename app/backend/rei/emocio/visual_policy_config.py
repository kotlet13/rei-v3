"""Strict data-only loader for the C4 visual valuation policy.

The configuration selects no renderer or encoder model.  It only records
auditable implementation-hypothesis coefficients and diagnostic thresholds.
JSON object order is non-semantic; content identities use the repository's
canonical JSON representation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import model_validator

from ..ids import content_id
from ..models.common import FrozenArtifactModel, NonEmptyId
from .visual_valuation import VisualValuationPolicy


VISUAL_VALUATION_POLICY_CONFIG_SCHEMA_VERSION = (
    "rei-native-visual-valuation-policy-config-v1"
)
VISUAL_VALUATION_POLICY_CONFIG_VERSION = "c4-v1"
VISUAL_VALUATION_POLICY_CONFIG_PATH = (
    Path(__file__).resolve().parents[4]
    / "config"
    / "emocio_visual_valuation_v1.json"
)

_CONFIG_KEYS = frozenset(
    {
        "schema_version",
        "config_version",
        "config_id",
        "basis",
        "policy",
    }
)
_POLICY_KEYS = frozenset(
    {
        "schema_version",
        "policy_id",
        "structured_weight",
        "desired_similarity_weight",
        "broken_avoidance_weight",
        "seed_consistency_penalty",
        "uncertainty_penalty",
        "action_collapse_epsilon",
        "selection_tie_epsilon",
        "basis",
    }
)
_WEIGHT_KEYS = frozenset({"value", "basis"})
_WEIGHT_FIELDS = (
    "structured_weight",
    "desired_similarity_weight",
    "broken_avoidance_weight",
    "seed_consistency_penalty",
    "uncertainty_penalty",
)


class VisualValuationPolicyConfig(FrozenArtifactModel):
    """One versioned, content-addressed visual valuation configuration."""

    schema_version: Literal[
        "rei-native-visual-valuation-policy-config-v1"
    ]
    config_version: Literal["c4-v1"]
    config_id: NonEmptyId
    basis: Literal["implementation_hypothesis"]
    policy: VisualValuationPolicy

    @classmethod
    def create(
        cls,
        *,
        policy: VisualValuationPolicy,
    ) -> VisualValuationPolicyConfig:
        payload = {
            "schema_version": VISUAL_VALUATION_POLICY_CONFIG_SCHEMA_VERSION,
            "config_version": VISUAL_VALUATION_POLICY_CONFIG_VERSION,
            "basis": "implementation_hypothesis",
            "policy": policy,
        }
        return cls(
            config_id=content_id("visual_policy_config", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_content_identity(self) -> Self:
        expected_id = content_id(
            "visual_policy_config",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"config_id"},
            ),
        )
        if self.config_id != expected_id:
            raise ValueError(
                "Visual valuation policy config ID differs from canonical content"
            )
        return self


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise ValueError(f"Duplicate JSON object key is forbidden: {key}")
        decoded[key] = value
    return decoded


def _reject_nonstandard_number(value: str) -> None:
    raise ValueError(f"Non-standard JSON number is forbidden: {value}")


def _require_exact_keys(
    value: object,
    *,
    expected: frozenset[str],
    context: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must contain one JSON object")
    actual = frozenset(value)
    missing = tuple(sorted(expected - actual))
    unknown = tuple(sorted(actual - expected))
    if missing:
        raise ValueError(
            f"{context} is missing required keys: {', '.join(missing)}"
        )
    if unknown:
        raise ValueError(
            f"{context} contains unknown keys: {', '.join(unknown)}"
        )
    return value


def _require_explicit_semantics(payload: object) -> Mapping[str, object]:
    config = _require_exact_keys(
        payload,
        expected=_CONFIG_KEYS,
        context="Visual valuation policy config",
    )
    policy = _require_exact_keys(
        config["policy"],
        expected=_POLICY_KEYS,
        context="Visual valuation policy",
    )
    for field_name in _WEIGHT_FIELDS:
        _require_exact_keys(
            policy[field_name],
            expected=_WEIGHT_KEYS,
            context=f"Visual valuation policy {field_name}",
        )
    return config


def load_visual_valuation_policy_config(
    path: str | Path | None = None,
) -> VisualValuationPolicyConfig:
    """Load one exact JSON policy config and reject ambiguous semantics."""

    source = (
        VISUAL_VALUATION_POLICY_CONFIG_PATH
        if path is None
        else Path(path).expanduser()
    ).resolve(strict=True)
    if not source.is_file():
        raise ValueError("Visual valuation policy config must be a regular file")
    payload = json.loads(
        source.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonstandard_number,
    )
    explicit = _require_explicit_semantics(payload)
    return VisualValuationPolicyConfig.model_validate_json(
        json.dumps(
            explicit,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    )


def load_visual_valuation_policy(
    path: str | Path | None = None,
) -> VisualValuationPolicy:
    """Load only the policy while retaining config validation at the boundary."""

    return load_visual_valuation_policy_config(path).policy


__all__ = [
    "VISUAL_VALUATION_POLICY_CONFIG_PATH",
    "VISUAL_VALUATION_POLICY_CONFIG_SCHEMA_VERSION",
    "VISUAL_VALUATION_POLICY_CONFIG_VERSION",
    "VisualValuationPolicyConfig",
    "load_visual_valuation_policy",
    "load_visual_valuation_policy_config",
]
