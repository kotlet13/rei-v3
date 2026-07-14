from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.backend.rei.emocio.visual_policy_config import (
    VISUAL_VALUATION_POLICY_CONFIG_PATH,
    VisualValuationPolicyConfig,
    load_visual_valuation_policy,
    load_visual_valuation_policy_config,
)
from app.backend.rei.emocio.visual_valuation import (
    ImplementationHypothesisWeight,
)


EXPECTED_CONFIG_ID = "visual_policy_config_6515948ecb9889666d1dd0dc2e741d42"
EXPECTED_POLICY_ID = "visual_valuation_policy_d0f88857d195481f576fb414838ab873"


def _payload() -> dict[str, Any]:
    decoded = json.loads(
        VISUAL_VALUATION_POLICY_CONFIG_PATH.read_text(encoding="utf-8")
    )
    assert isinstance(decoded, dict)
    return decoded


def _write_payload(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "visual-policy.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def test_default_visual_policy_config_is_explicit_and_content_addressed() -> None:
    config = load_visual_valuation_policy_config()
    policy = load_visual_valuation_policy()

    assert config.schema_version == "rei-native-visual-valuation-policy-config-v1"
    assert config.config_version == "c4-v1"
    assert config.config_id == EXPECTED_CONFIG_ID
    assert config.basis == "implementation_hypothesis"
    assert config.policy == policy
    assert policy.policy_id == EXPECTED_POLICY_ID
    assert policy.schema_version == "rei-native-visual-valuation-policy-v1"
    assert (
        policy.structured_weight,
        policy.desired_similarity_weight,
        policy.broken_avoidance_weight,
        policy.seed_consistency_penalty,
        policy.uncertainty_penalty,
    ) == tuple(
        ImplementationHypothesisWeight(value=value)
        for value in (0.4, 0.4, 0.2, 0.15, 0.1)
    )
    assert policy.action_collapse_epsilon == 0.01
    assert policy.selection_tie_epsilon == 0.000001
    assert policy.basis == "implementation_hypothesis"


def test_json_object_order_does_not_change_semantic_identity(tmp_path: Path) -> None:
    payload = _payload()
    policy = payload["policy"]
    assert isinstance(policy, dict)
    reordered = dict(reversed(tuple(payload.items())))
    reordered["policy"] = dict(reversed(tuple(policy.items())))

    loaded = load_visual_valuation_policy_config(
        _write_payload(tmp_path, reordered)
    )

    assert loaded.config_id == EXPECTED_CONFIG_ID
    assert loaded.policy.policy_id == EXPECTED_POLICY_ID


@pytest.mark.parametrize(
    ("scope", "field_name"),
    (
        ("config", "basis"),
        ("policy", "selection_tie_epsilon"),
        ("weight", "basis"),
    ),
)
def test_loader_rejects_missing_explicit_semantics(
    tmp_path: Path,
    scope: str,
    field_name: str,
) -> None:
    payload = deepcopy(_payload())
    if scope == "config":
        del payload[field_name]
    elif scope == "policy":
        del payload["policy"][field_name]
    else:
        del payload["policy"]["structured_weight"][field_name]

    with pytest.raises(ValueError, match="missing required keys"):
        load_visual_valuation_policy_config(_write_payload(tmp_path, payload))


@pytest.mark.parametrize("scope", ("config", "policy", "weight"))
def test_loader_rejects_unknown_semantics(tmp_path: Path, scope: str) -> None:
    payload = deepcopy(_payload())
    if scope == "config":
        payload["production_model_id"] = "forbidden"
    elif scope == "policy":
        payload["policy"]["renderer_model_id"] = "forbidden"
    else:
        payload["policy"]["structured_weight"]["empirical_basis"] = False

    with pytest.raises(ValueError, match="contains unknown keys"):
        load_visual_valuation_policy_config(_write_payload(tmp_path, payload))


def test_loader_rejects_duplicate_json_keys_at_any_depth(tmp_path: Path) -> None:
    top_level = tmp_path / "duplicate-top.json"
    top_level.write_text(
        '{"schema_version":"one","schema_version":"two"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        load_visual_valuation_policy_config(top_level)

    nested = tmp_path / "duplicate-nested.json"
    nested.write_text(
        '{"policy":{"basis":"one","basis":"two"}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        load_visual_valuation_policy_config(nested)


def test_loader_rejects_nonstandard_json_numbers(tmp_path: Path) -> None:
    raw = VISUAL_VALUATION_POLICY_CONFIG_PATH.read_text(encoding="utf-8")
    invalid = tmp_path / "nan-policy.json"
    invalid.write_text(raw.replace('"value": 0.4', '"value": NaN', 1))

    with pytest.raises(ValueError, match="Non-standard JSON number"):
        load_visual_valuation_policy_config(invalid)


def test_loader_rejects_stale_content_identities(tmp_path: Path) -> None:
    payload = deepcopy(_payload())
    payload["config_id"] = "visual_policy_config_stale"
    with pytest.raises(ValidationError, match="config ID differs"):
        load_visual_valuation_policy_config(_write_payload(tmp_path, payload))

    payload = deepcopy(_payload())
    payload["policy"]["policy_id"] = "visual_valuation_policy_stale"
    with pytest.raises(ValidationError, match="policy ID differs"):
        load_visual_valuation_policy_config(_write_payload(tmp_path, payload))


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        ("schema_version", "rei-native-visual-valuation-policy-config-v2"),
        ("config_version", "c4-v2"),
        ("basis", "empirical_fact"),
    ),
)
def test_loader_rejects_unrecognized_config_contract_values(
    tmp_path: Path,
    field_name: str,
    replacement: str,
) -> None:
    payload = deepcopy(_payload())
    payload[field_name] = replacement

    with pytest.raises(ValidationError):
        load_visual_valuation_policy_config(_write_payload(tmp_path, payload))


def test_config_model_requires_no_runtime_or_model_selection_fields() -> None:
    assert {
        "model_id",
        "model_digest",
        "renderer_model_id",
        "encoder_model_id",
        "production_model_id",
    }.isdisjoint(VisualValuationPolicyConfig.model_fields)
    assert {
        "model_id",
        "model_digest",
        "renderer_model_id",
        "encoder_model_id",
        "production_model_id",
    }.isdisjoint(_payload())
