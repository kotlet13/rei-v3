from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.backend.rei.governance.fixtures import load_governance_fixture
from app.backend.rei.models.character import CHARACTER_PROFILE_ORDER
from app.backend.rei.providers.language_policy import (
    LocalModelLanguagePolicyError,
    require_english_local_model_payload,
)
from app.backend.rei.providers.ollama import (
    OllamaApiClient,
    OllamaRacioSettings,
    OllamaRuntimeModel,
    inspect_ollama_runtime,
)
from app.backend.rei.providers.ollama_en import (
    OLLAMA_EN_TRIAD_PROVIDER_REVISION,
    OllamaRacioNativeEnTriadProvider,
)
from app.backend.rei.triad_screen import (
    EXPECTED_CASE_IDS,
    EXPECTED_MODEL_DIGEST,
    MODEL_PROFILE,
    SCREEN_RELATIVE_PATH,
    cold_verify_screen,
    prepare_corpus,
    replay_profiles,
    validate_corpus,
    verify_pre_call_screen,
)


REPOSITORY_ROOT = Path(__file__).parents[2]
SCREEN_ROOT = REPOSITORY_ROOT / SCREEN_RELATIVE_PATH
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "native_bundles"


def _corpus() -> dict:
    return json.loads((SCREEN_ROOT / "corpus.json").read_text(encoding="utf-8"))


def _provider(packet):
    del packet
    settings = OllamaRacioSettings(
        model="gemma4:31b",
        seed=314159,
        temperature=0.0,
        num_ctx=65536,
        num_gpu=999,
        require_full_gpu=True,
    )
    runtime = OllamaRuntimeModel(
        server_version="test",
        model=settings.model,
        digest=EXPECTED_MODEL_DIGEST,
        size_bytes=100,
        quantization_level="Q4_K_M",
        context_length=131072,
        capabilities=("completion",),
    )
    return OllamaRacioNativeEnTriadProvider(
        client=OllamaApiClient(),
        runtime=runtime,
        settings=settings,
        expected_digest=EXPECTED_MODEL_DIGEST,
        top_p=0.95,
        top_k=64,
    )


def test_corpus_is_exact_bilingual_profile_blind_eight_case_scope() -> None:
    corpus = _corpus()
    validate_corpus(corpus)
    prepared = prepare_corpus(corpus)

    assert tuple(item.case_id for item in prepared) == EXPECTED_CASE_IDS
    assert len(prepared) == 8
    assert all(item.racio_packet.language == "en" for item in prepared)
    assert all(item.emocio_packet.allowed_option_ids for item in prepared)
    assert all(item.instinkt_packet.cue_evidence_bindings for item in prepared)
    assert all(
        len(item.instinkt_predictions) == len(item.scene.options)
        and not any(value.abstains for value in item.instinkt_predictions)
        for item in prepared
    )


@pytest.mark.parametrize(
    "leak",
    (
        {"expected_option_id": "forbidden"},
        {"character_profile": "R>E>I"},
        {"gold_route": "R"},
    ),
)
def test_model_free_leakage_audit_rejects_processor_hints(leak: dict) -> None:
    corpus = _corpus()
    mutant = copy.deepcopy(corpus)
    mutant["cases"][0]["racio_input"].update(leak)

    with pytest.raises(ValueError, match="leakage key"):
        validate_corpus(mutant)


def test_shared_english_gate_rejects_source_fields_before_transport() -> None:
    with pytest.raises(LocalModelLanguagePolicyError) as caught:
        require_english_local_model_payload(
            declared_language="en",
            provider_payload={
                "presentation_mode": "operational_en_only",
                "nested": {"canonical_sl": "private source"},
            },
        )

    assert caught.value.failure_code == "non_english_field"
    assert "private source" not in str(caught.value)


def test_thin_english_wrapper_reuses_transport_and_freezes_screen_profile() -> None:
    prepared = prepare_corpus(_corpus())[0]
    provider = _provider(prepared.racio_packet)
    payload = provider.request_payload(prepared.racio_packet)
    serialized = json.dumps(payload, ensure_ascii=False)
    parameters = {
        item.name: json.loads(item.canonical_json_value)
        for item in provider.parameters
    }

    assert provider.client.__class__ is OllamaApiClient
    assert OLLAMA_EN_TRIAD_PROVIDER_REVISION in (
        provider.identity.implementation_revision
    )
    assert payload["model"] == MODEL_PROFILE["model"]
    assert payload["options"]["seed"] == MODEL_PROFILE["seed"]
    assert payload["options"]["num_ctx"] == MODEL_PROFILE["num_ctx"]
    assert payload["options"]["num_gpu"] == MODEL_PROFILE["num_gpu"]
    assert payload["options"]["top_p"] == MODEL_PROFILE["top_p"]
    assert payload["options"]["top_k"] == MODEL_PROFILE["top_k"]
    assert payload["think"] is False
    assert "canonical_sl" not in serialized
    assert "notes_sl" not in serialized
    assert "prompt_sl" not in serialized
    assert parameters["source_provider_revision"].startswith(
        "rei-native-ollama-racio-b14"
    )
    assert parameters["local_model_language_policy_id"] == (
        "rei-local-model-english-only-v1"
    )


def test_runtime_accepts_tag_capability_subset_reported_by_current_ollama() -> None:
    class MetadataClient:
        def version(self):
            return "0.12.10"

        def model_entry(self, model):
            return {
                "name": model,
                "digest": EXPECTED_MODEL_DIGEST,
                "size": 100,
                "details": {"quantization_level": "Q4_K_M"},
                "capabilities": ["completion", "tools", "thinking"],
            }

        def show(self, model):
            del model
            return {
                "details": {"quantization_level": "Q4_K_M"},
                "capabilities": ["completion", "vision", "tools", "thinking"],
                "model_info": {
                    "general.architecture": "gemma4",
                    "gemma4.context_length": 131072,
                },
            }

    runtime = inspect_ollama_runtime(
        MetadataClient(),
        "gemma4:31b",
        expected_digest=EXPECTED_MODEL_DIGEST,
    )

    assert runtime.digest == EXPECTED_MODEL_DIGEST
    assert runtime.capabilities == ("completion", "thinking", "tools", "vision")


def test_pre_call_seal_and_all_case_input_hashes_verify_cold() -> None:
    prepared = verify_pre_call_screen(REPOSITORY_ROOT)
    seal = json.loads(
        (SCREEN_ROOT / "pre_call_seal.json").read_text(encoding="utf-8")
    )
    ledger = json.loads(
        (SCREEN_ROOT / "call_ledger.json").read_text(encoding="utf-8")
    )

    assert len(prepared) == 8
    assert seal["declarations"]["corpus_frozen_before_calls"] is True
    assert seal["declarations"]["untouched_holdout"] is False
    assert seal["declarations"]["promotion_evidence"] is False
    assert seal["declarations"]["training_data"] is False
    assert ledger["expected"] == {
        "model_calls": 8,
        "retries": 0,
        "fallbacks": 0,
    }
    if ledger["state"] == "sealed_before_calls":
        assert ledger["actual"]["model_calls"] == 0
    else:
        assert 0 < ledger["actual"]["model_calls"] <= 8
        assert ledger["actual"]["retries"] == 0
        assert ledger["actual"]["fallbacks"] == 0


def test_character_replay_uses_one_frozen_bundle_for_exact_thirteen_profiles() -> None:
    fixture = load_governance_fixture(sorted(FIXTURE_ROOT.glob("*.json"))[0])
    bundle = fixture.native_bundle
    before = bundle.immutable_hash

    rows = replay_profiles(bundle)

    assert len(rows) == 13
    assert tuple(row.profile_id for row in rows) == CHARACTER_PROFILE_ORDER
    assert {row.native_bundle_id for row in rows} == {bundle.bundle_id}
    assert {row.native_bundle_hash for row in rows} == {before}
    assert bundle.immutable_hash == before


def test_compact_executed_evidence_is_cold_verifiable_when_present() -> None:
    if not (SCREEN_ROOT / "summary.json").exists():
        pytest.skip("TRIAD-S1 model calls have not been executed yet")

    summary = cold_verify_screen(REPOSITORY_ROOT)

    assert summary["model_calls"] == 8
    assert summary["retries"] == 0
    assert summary["fallbacks"] == 0
    assert summary["case_target"] == 8
    assert summary["native_conclusion_target"] == 24
    assert summary["character_replay_target"] == 104
    assert summary["compact_validated_native_conclusions"] == (
        summary["fully_evidenced_cases"] * 3
    )
    assert summary["character_replay_rows"] == (
        summary["fully_evidenced_cases"] * 13
    )
