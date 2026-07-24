from __future__ import annotations

from pathlib import Path

from app.backend.rei.providers.ollama import (
    OllamaApiClient,
    OllamaRacioSettings,
    OllamaRuntimeModel,
)
from app.backend.rei.providers.ollama_en import (
    OllamaRacioNativeEnTriadProvider,
)
from app.backend.rei.research.triad_iso_e2 import (
    E2_EFFECT_RULES,
    EXPECTED_R2_CANDIDATE_SHA256,
    LOCAL_EVIDENCE_ID,
    LOCAL_FACT_EN,
    LOCAL_FACT_SL,
    UTILITY_CASE_ORDER,
    corrected_candidate_v3,
    deterministic_references,
    model_free_preflight,
)
from app.backend.rei.research.triad_s2 import (
    EXPECTED_MODEL_DIGEST,
    MODEL_PROFILE,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _offline_provider() -> OllamaRacioNativeEnTriadProvider:
    return OllamaRacioNativeEnTriadProvider(
        client=OllamaApiClient(),
        runtime=OllamaRuntimeModel(
            server_version="offline-seal-preflight",
            model=MODEL_PROFILE["model"],
            digest=EXPECTED_MODEL_DIGEST,
            size_bytes=1,
            quantization_level="Q4_K_M",
            context_length=131072,
            capabilities=("completion",),
        ),
        settings=OllamaRacioSettings(
            model=MODEL_PROFILE["model"],
            seed=MODEL_PROFILE["seed"],
            temperature=MODEL_PROFILE["temperature"],
            num_ctx=MODEL_PROFILE["num_ctx"],
            num_gpu=MODEL_PROFILE["num_gpu"],
            num_predict=MODEL_PROFILE["num_predict"],
            require_full_gpu=True,
        ),
        expected_digest=EXPECTED_MODEL_DIGEST,
        top_p=MODEL_PROFILE["top_p"],
        top_k=MODEL_PROFILE["top_k"],
    )


def _index(candidate: dict) -> dict[str, dict]:
    return {case["case_id"]: case for case in candidate["cases"]}


def test_v3_completes_local_cost_without_mutating_r2() -> None:
    source = (
        REPOSITORY_ROOT
        / "Docs/evals/semantic_lab_v1/"
        "triad-route-isolation-e1r2-2026-07-24/corrected_candidate_v2.json"
    )
    import hashlib

    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        EXPECTED_R2_CANDIDATE_SHA256
    )
    candidate = corrected_candidate_v3(REPOSITORY_ROOT)
    index = _index(candidate)
    for case_id in UTILITY_CASE_ORDER:
        case = index[case_id]
        sl = {item["evidence_id"]: item["text"] for item in case["canonical_sl"]["facts"]}
        en = {
            item["evidence_id"]: item["text"]
            for item in case["operational_en"]["facts"]
        }
        assert sl[LOCAL_EVIDENCE_ID] == LOCAL_FACT_SL
        assert en[LOCAL_EVIDENCE_ID] == LOCAL_FACT_EN
        assert LOCAL_EVIDENCE_ID in case["route_packets"]["racio"]["facts"]
        local = next(
            item
            for item in case["route_packets"]["racio"][
                "material_strategic_consequences"
            ]
            if item["option_id"] == "utility_trip_local"
        )
        assert "EUR 480" in local["consequence"]
        assert "10 percent" in local["consequence"]


def test_typed_instinkt_hypothesis_is_monotone_and_grounded() -> None:
    candidate = corrected_candidate_v3(REPOSITORY_ROOT)
    for case_id in UTILITY_CASE_ORDER:
        mapping = _index(candidate)[case_id]["route_packets"]["instinkt"][
            "typed_effect_mapping_v1"
        ]
        local = next(
            item
            for item in mapping["option_effects"]
            if item["option_id"] == "utility_trip_local"
        )
        local_category = next(
            item
            for item in local["categories"]
            if item["semantic_predicate"]
            == "discretionary_resource_commitment_10"
        )
        assert local_category["supporting_evidence_ids"] == [LOCAL_EVIDENCE_ID]
        book = next(
            item
            for item in mapping["option_effects"]
            if item["option_id"] == "utility_trip_book"
        )
        predicates = {item["semantic_predicate"] for item in book["categories"]}
        assert "verified_provider_support" in predicates
        assert "verified_return_support" in predicates
        local_predicates = {
            item["semantic_predicate"] for item in local["categories"]
        }
        assert "verified_provider_support" not in local_predicates
        assert "verified_return_support" not in local_predicates
    assert (
        E2_EFFECT_RULES["discretionary_resource_commitment_10"][
            "resource_security"
        ]
        > E2_EFFECT_RULES["discretionary_resource_commitment_25"][
            "resource_security"
        ]
        > -0.20
    )


def test_e_and_i_deterministic_references_remain_pair_stable() -> None:
    references = deterministic_references(
        REPOSITORY_ROOT, corrected_candidate_v3(REPOSITORY_ROOT)
    )
    first, second = (
        references["cases"][case_id] for case_id in UTILITY_CASE_ORDER
    )
    assert first["emocio"]["valuation_vectors"] == second["emocio"][
        "valuation_vectors"
    ]
    assert first["instinkt"]["option_results"] == second["instinkt"][
        "option_results"
    ]
    assert references["native_processor_executions"] == {"E": 0, "I": 0}
    assert references["model_calls"] == 0


def test_model_free_preflight_and_protective_reuse_pass() -> None:
    report = model_free_preflight(
        REPOSITORY_ROOT,
        corrected_candidate_v3(REPOSITORY_ROOT),
        _offline_provider(),
    )
    assert report["status"] == "passed"
    assert all(report["checks"].values())
    assert report["protective_reuse"]["status"] == "passed"
    assert report["protective_reuse"]["protective_model_calls"] == 0
    assert report["model_calls"] == 0
