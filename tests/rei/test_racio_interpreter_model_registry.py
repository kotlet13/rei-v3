from __future__ import annotations

import inspect
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.backend.rei import communication
from app.backend.rei.communication.model_registry import (
    RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
    RacioInterpreterModelRegistry,
    load_racio_interpreter_model_registry,
    require_racio_interpreter_model_candidate,
)


GRANITE_DIGEST = (
    "3f3e5df8a021439fd6f867a0e526bdc303cac79c811201cb6bac193298cb9fcd"
)
QWEN_VL_DIGEST = (
    "2f09e811cc16c59001b2cacae2974b3b62c7f17a2dcb43a7bfad4e924bf2f268"
)
QWEN_35_DIGEST = (
    "7653528ba5cba4dd8e19da24aaddc7f4d0b5ecd93571c0825dfd4137958ec06e"
)


def _registry_payload() -> dict[str, object]:
    return json.loads(
        RACIO_INTERPRETER_MODEL_REGISTRY_PATH.read_text(encoding="utf-8")
    )


def _validate(payload: dict[str, object]) -> RacioInterpreterModelRegistry:
    return RacioInterpreterModelRegistry.model_validate_json(
        json.dumps(payload, ensure_ascii=False)
    )


def test_json_compatible_yaml_registry_loads_three_unselected_candidates() -> None:
    payload = _registry_payload()
    registry = load_racio_interpreter_model_registry()

    assert payload["schema_version"] == "rei-racio-interpreter-model-registry-v1"
    assert registry.registry_version == "c3-v2"
    assert tuple(candidate.model_id for candidate in registry.candidates) == (
        "granite4.1:30b",
        "qwen2.5vl:32b",
        "qwen3.5:27b",
    )
    assert {
        "default_model_id",
        "selected_model_id",
        "production_model_id",
    }.isdisjoint(payload)
    assert {
        "default_model_id",
        "selected_model_id",
        "production_model_id",
    }.isdisjoint(RacioInterpreterModelRegistry.model_fields)


def test_registry_api_is_public_without_selecting_or_loading_a_model() -> None:
    assert communication.RacioInterpreterModelRegistry is RacioInterpreterModelRegistry
    assert callable(communication.load_racio_interpreter_model_registry)
    assert callable(communication.require_racio_interpreter_model_candidate)


def test_registry_records_required_candidate_metadata() -> None:
    registry = load_racio_interpreter_model_registry()
    granite, qwen_vl, qwen_35 = registry.candidates

    assert granite.model_digest == GRANITE_DIGEST
    assert granite.runtime == "ollama"
    assert granite.modality_support == ("structured_text",)
    assert granite.slovenian_baseline == "not_benchmarked"
    assert granite.max_context == 131072
    assert granite.hardware_requirements.minimum_vram_gib == 24
    assert granite.license == "Apache-2.0"
    assert granite.benchmark_status == "c3_candidate"

    assert qwen_vl.model_digest == QWEN_VL_DIGEST
    assert qwen_vl.runtime == "ollama"
    assert qwen_vl.modality_support == ("structured_text", "vision")
    assert qwen_vl.slovenian_baseline == "not_benchmarked"
    assert qwen_vl.max_context == 128000
    assert qwen_vl.hardware_requirements.minimum_vram_gib == 24
    assert qwen_vl.license == "Apache-2.0"
    assert qwen_vl.benchmark_status == "vlm_adapter_candidate"

    assert qwen_35.model_digest == QWEN_35_DIGEST
    assert qwen_35.runtime == "ollama"
    assert qwen_35.modality_support == ("structured_text", "vision")
    assert qwen_35.slovenian_baseline == "not_benchmarked"
    assert qwen_35.max_context == 262144
    assert qwen_35.hardware_requirements.minimum_vram_gib == 24
    assert qwen_35.license == "Apache-2.0"
    assert qwen_35.benchmark_status == "c3_candidate"


def test_lookup_requires_exact_explicit_model_id_and_digest() -> None:
    registry = load_racio_interpreter_model_registry()
    signature = inspect.signature(require_racio_interpreter_model_candidate)

    assert signature.parameters["model_id"].default is inspect.Parameter.empty
    assert signature.parameters["digest"].default is inspect.Parameter.empty
    assert require_racio_interpreter_model_candidate(
        registry,
        model_id="granite4.1:30b",
        digest=GRANITE_DIGEST,
    ) == registry.candidates[0]

    with pytest.raises(LookupError, match="model ID and digest"):
        require_racio_interpreter_model_candidate(
            registry,
            model_id="granite4.1:30b",
            digest=QWEN_VL_DIGEST,
        )
    with pytest.raises(LookupError, match="model ID and digest"):
        require_racio_interpreter_model_candidate(
            registry,
            model_id="unregistered:latest",
            digest=GRANITE_DIGEST,
        )


@pytest.mark.parametrize("digest", ("abc", "A" * 64, "0" * 63, "0" * 65))
def test_lookup_rejects_noncanonical_or_incomplete_digest(digest: str) -> None:
    registry = load_racio_interpreter_model_registry()

    with pytest.raises(ValueError, match="64-hex digest"):
        registry.require_candidate(model_id="granite4.1:30b", digest=digest)


@pytest.mark.parametrize("field_name", ("default_model_id", "selected_model_id"))
def test_registry_rejects_default_or_selected_model_fields(field_name: str) -> None:
    payload = _registry_payload()
    payload[field_name] = "granite4.1:30b"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _validate(payload)


@pytest.mark.parametrize("duplicate_field", ("model_id", "model_digest"))
def test_registry_rejects_duplicate_identity_values(duplicate_field: str) -> None:
    payload = deepcopy(_registry_payload())
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    candidates[1][duplicate_field] = candidates[0][duplicate_field]

    with pytest.raises(ValidationError, match="must be unique"):
        _validate(payload)


def test_registry_rejects_unsorted_or_incompatible_modalities() -> None:
    payload = deepcopy(_registry_payload())
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    candidates[1]["modality_support"] = ["vision", "structured_text"]
    with pytest.raises(ValidationError, match="canonically sorted"):
        _validate(payload)

    payload = deepcopy(_registry_payload())
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    candidates[1]["modality_support"] = ["structured_text"]
    with pytest.raises(ValidationError, match="must declare vision support"):
        _validate(payload)


def test_registry_rejects_non_json_yaml_and_malformed_digest(tmp_path) -> None:
    yaml_only = tmp_path / "registry.yaml"
    yaml_only.write_text(
        "schema_version: rei-racio-interpreter-model-registry-v1\n",
        encoding="utf-8",
    )
    with pytest.raises(json.JSONDecodeError):
        load_racio_interpreter_model_registry(yaml_only)

    payload = _registry_payload()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    candidates[0]["model_digest"] = "not-a-full-digest"
    with pytest.raises(ValidationError):
        _validate(payload)
