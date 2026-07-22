from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.backend.rei.providers.ollama_gemma4_epistemic_en_explained import (
    GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION,
)
from scripts import run_gemma4_racio_english_shadow_smoke as base
from scripts import run_gemma4_racio_observable_shadow_smoke as smoke


_CONFIGURED_NAMES = (
    "IMPLEMENTATION_COMMIT",
    "PHASE",
    "EVENT_ID",
    "RUN_ID",
    "EGO_ID",
    "SEAL_PATH",
    "OUTPUT_ROOT",
    "RECEIPT_PATH",
    "EXPECTED_OUTPUT_ROOT",
    "PROVIDER_REVISION",
    "INSTRUCTION_SHA256",
    "DRAFT_SCHEMA_SHA256",
    "DRAFT_MODEL_SCHEMA_SHA256",
    "RUNNER_PATH",
    "RUNNER_RELATIVE_PATH",
    "FOCUSED_TEST_RELATIVE_PATH",
    "SEALED_SOURCE_PATHS",
    "MANIFEST_ID_PREFIX",
    "RECEIPT_ID_PREFIX",
    "ALLOW_PRESERVED_VALIDATION_FAILURE",
)


def _configured_snapshot() -> dict[str, object]:
    return {name: getattr(base, name) for name in _CONFIGURED_NAMES}


def _restore(values: dict[str, object]) -> None:
    for name, value in values.items():
        setattr(base, name, value)


def test_importing_en3_runner_does_not_mutate_historical_profile() -> None:
    assert base.PHASE == "EN1"
    assert base.ALLOW_PRESERVED_VALIDATION_FAILURE is False
    assert smoke.IMPLEMENTATION_COMMIT == (
        "97c9f499e81422769d67760e23390c5fd83f6301"
    )


def test_en3_configuration_builds_same_two_english_packets_without_model_calls(
    tmp_path: Path,
) -> None:
    original = _configured_snapshot()
    try:
        smoke._configure_base()
        assert base.PHASE == "EN3"
        assert base.PROVIDER_REVISION == (
            GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION
        )
        assert base.ALLOW_PRESERVED_VALIDATION_FAILURE is True
        assert base.EXPECTED_CALLS == 2
        request = base._build_request()
        assert request.run_id == "en3-gemma4-observable-shadow-cycle"
        assert request.scene.language == "en"
        control = base._run_cycle(tmp_path / "control", request)
        packets = base._packet_pair(control)
        assert tuple(packet.source_mind for packet in packets) == ("E", "I")
        assert all(packet.language == "en" for packet in packets)
    finally:
        _restore(original)


def test_en3_observability_accepts_success_or_preserved_validation_failure() -> None:
    success = SimpleNamespace(
        result=SimpleNamespace(status="succeeded", failure_stage=None),
        response_evidence=object(),
        failure_evidence=None,
    )
    preserved_failure = SimpleNamespace(
        result=SimpleNamespace(
            status="failed",
            failure_stage="draft_v3_validation",
        ),
        response_evidence=None,
        failure_evidence=object(),
    )
    count, observable = base._shadow_observability(
        (preserved_failure, success)
    )
    assert count == 1
    assert observable is True

    lost_failure = SimpleNamespace(
        result=SimpleNamespace(status="failed", failure_stage="transport"),
        response_evidence=None,
        failure_evidence=None,
    )
    assert base._shadow_observability((lost_failure, success)) == (0, False)


def test_en3_paths_and_content_id_prefixes_are_distinct_and_bounded() -> None:
    assert len(smoke.MANIFEST_ID_PREFIX) <= 32
    assert len(smoke.RECEIPT_ID_PREFIX) <= 32
    assert smoke.OUTPUT_ROOT != base.OUTPUT_ROOT
    assert smoke.RECEIPT_PATH != base.RECEIPT_PATH
    assert smoke.SEAL_PATH != base.SEAL_PATH
