from __future__ import annotations

from pathlib import Path

from app.backend.rei.providers.ollama_gemma4_epistemic_en_explained import (
    GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION,
)
from scripts import run_gemma4_racio_english_shadow_smoke as base
from scripts import run_gemma4_racio_explained_shadow_smoke as smoke


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
)


def _configured_snapshot() -> dict[str, object]:
    return {name: getattr(base, name) for name in _CONFIGURED_NAMES}


def _restore(values: dict[str, object]) -> None:
    for name, value in values.items():
        setattr(base, name, value)


def test_importing_en2_runner_does_not_mutate_historical_en1_profile() -> None:
    assert base.PHASE == "EN1"
    assert base.PROVIDER_REVISION == "rei-racio-gemma4-epistemic-v3-en-chat-v1"
    assert base.OUTPUT_ROOT.name == "en1-gemma4-text-shadow-2026-07-20"


def test_en2_configuration_builds_exact_english_packets_without_model_calls(
    tmp_path: Path,
) -> None:
    original = _configured_snapshot()
    try:
        smoke._configure_base()
        assert base.PHASE == "EN2"
        assert base.PROVIDER_REVISION == (
            GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION
        )
        assert base.EXPECTED_CALLS == 2
        request = base._build_request()
        assert request.run_id == "en2-gemma4-explained-shadow-cycle"
        assert request.scene.language == "en"
        assert request.scene.raw_input == (
            "Decide whether to restore the shared workshop or leave it closed."
        )
        control = base._run_cycle(tmp_path / "control", request)
        packets = base._packet_pair(control)
        assert tuple(packet.source_mind for packet in packets) == ("E", "I")
        assert all(packet.language == "en" for packet in packets)
        assert all(packet.provider_payload()["language"] == "en" for packet in packets)
    finally:
        _restore(original)


def test_en2_identifiers_are_bounded_and_create_only_paths_are_distinct() -> None:
    assert len(smoke.MANIFEST_ID_PREFIX) <= 32
    assert len(smoke.RECEIPT_ID_PREFIX) <= 32
    assert smoke.OUTPUT_ROOT != base.OUTPUT_ROOT
    assert smoke.RECEIPT_PATH != base.RECEIPT_PATH
    assert smoke.SEAL_PATH != base.SEAL_PATH
