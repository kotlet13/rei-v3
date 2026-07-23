from __future__ import annotations

import json
from pathlib import Path

from app.backend.rei.emocio.policy import choose_native_option
from app.backend.rei.emocio.valuation import build_emocio_visual_state
from app.backend.rei.providers.ollama import (
    OllamaApiClient,
    OllamaRacioSettings,
    OllamaRuntimeModel,
)
from app.backend.rei.providers.ollama_en import (
    OLLAMA_EN_TRIAD_PROVIDER_REVISION,
    OllamaRacioNativeEnTriadProvider,
)
from app.backend.rei.research.triad_d1 import TRIAD_S2_RELATIVE_PATH
from app.backend.rei.research.triad_s2 import (
    EXECUTION_POLICY,
    EXPECTED_MODEL_DIGEST,
    MODEL_PROFILE,
    _expected_call_ledger,
    _human_review_fields,
    prepare_cases,
)


REPOSITORY_ROOT = Path(__file__).parents[2]
CANDIDATE_ROOT = REPOSITORY_ROOT / TRIAD_S2_RELATIVE_PATH


def _candidate():
    return json.loads(
        (CANDIDATE_ROOT / "corpus_candidate.json").read_text(encoding="utf-8")
    )


def _provider():
    settings = OllamaRacioSettings(
        model=MODEL_PROFILE["model"],
        seed=MODEL_PROFILE["seed"],
        temperature=MODEL_PROFILE["temperature"],
        num_ctx=MODEL_PROFILE["num_ctx"],
        num_gpu=MODEL_PROFILE["num_gpu"],
        num_predict=MODEL_PROFILE["num_predict"],
        require_full_gpu=True,
    )
    runtime = OllamaRuntimeModel(
        server_version="test",
        model=settings.model,
        digest=EXPECTED_MODEL_DIGEST,
        size_bytes=100,
        quantization_level="Q4_K_M",
        context_length=262144,
        capabilities=("completion",),
    )
    return OllamaRacioNativeEnTriadProvider(
        client=OllamaApiClient(),
        runtime=runtime,
        settings=settings,
        expected_digest=EXPECTED_MODEL_DIGEST,
        top_p=MODEL_PROFILE["top_p"],
        top_k=MODEL_PROFILE["top_k"],
    )


def test_sealed_candidate_prepares_exact_four_profile_blind_call_contracts() -> None:
    prepared = prepare_cases(_candidate(), _provider())

    assert tuple(item.case_id for item in prepared) == (
        "factory_overtemperature",
        "loan_to_friend",
        "public_credit_conflict",
        "spontaneous_trip",
    )
    assert len({item.racio_call_spec.call_id for item in prepared}) == 4
    assert all(item.racio_packet.language == "en" for item in prepared)
    assert all(item.candidate["profile_blind"] for item in prepared)
    assert all(
        item.racio_call_spec.provider.implementation_revision.startswith(
            OLLAMA_EN_TRIAD_PROVIDER_REVISION
        )
        for item in prepared
    )
    assert all(
        "canonical_sl" not in json.dumps(item.racio_request_payload)
        for item in prepared
    )
    assert all(
        {
            evidence_id
            for counterfactual in item.candidate["emocio_input"][
                "option_counterfactuals"
            ]
            for evidence_id in counterfactual["evidence_basis_ids"]
        }.issubset(item.emocio_packet.evidence_ids)
        for item in prepared
    )
    assert all(item.emocio_packet.source_scene_hash is None for item in prepared)


def test_actual_counterfactual_valuation_vectors_have_capacity_to_differ() -> None:
    for item in prepare_cases(_candidate(), _provider()):
        visual_state = build_emocio_visual_state(
            scene=item.scene,
            packet=item.emocio_packet,
            world=item.emocio_world,
            compiled=item.emocio_compiled,
        )
        vectors = {
            tuple((dimension.name, dimension.score) for dimension in value.dimensions)
            for value in visual_state.option_valuations
        }
        policy = choose_native_option(visual_state.option_valuations)

        assert len({value.scene_id for value in visual_state.option_rollouts}) == 3
        assert len(vectors) >= 2
        assert policy.selected is not None or policy.tied_option_ids


def test_instinkt_effects_are_option_specific_grounded_and_distinct() -> None:
    for item in prepare_cases(_candidate(), _provider()):
        effect_by_option = {
            effect.option_id: effect for effect in item.instinkt_effects
        }
        signatures = {
            value["effect_signature"] for value in item.instinkt_effect_lineage
        }

        assert len(signatures) == 3
        assert not item.instinkt_packet.cue_evidence_bindings
        assert all(
            effect_by_option[value["option_id"]].triggering_evidence_ids
            == tuple(value["source_evidence_ids"])
            for value in item.instinkt_effect_lineage
        )
        assert all(value["consequence_facts"] for value in item.instinkt_effect_lineage)


def test_expected_ledger_precommits_rejection_policy_and_zero_retry() -> None:
    ledger = _expected_call_ledger(prepare_cases(_candidate(), _provider()))

    assert ledger["expected"] == {
        "model_calls": 4,
        "retries": 0,
        "fallbacks": 0,
        "maximum_native_bundles": 4,
        "maximum_character_replay_rows": 52,
    }
    assert EXECUTION_POLICY[
        "execute_emocio_after_racio_contract_rejection"
    ] is True
    assert EXECUTION_POLICY[
        "execute_instinkt_after_racio_contract_rejection"
    ] is True
    assert EXECUTION_POLICY["stop_after_non_contract_provider_failure"] is True


def test_model_profile_and_human_review_fields_are_frozen_and_empty() -> None:
    assert MODEL_PROFILE == {
        "model": "gemma4:31b",
        "model_digest": EXPECTED_MODEL_DIGEST,
        "seed": 314159,
        "temperature": 0.0,
        "top_p": 0.95,
        "top_k": 64,
        "num_ctx": 65536,
        "num_gpu": 999,
        "num_predict": 1536,
        "retry": 0,
        "fallback": "none",
        "require_full_gpu": True,
        "thinking_persisted": False,
    }
    fields = _human_review_fields()
    assert all(
        line.endswith(": ")
        for line in fields
        if line.startswith("- ")
    )
