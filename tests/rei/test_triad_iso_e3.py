from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from app.backend.rei.providers.ollama import (
    OllamaApiClient,
    OllamaRacioSettings,
    OllamaRuntimeModel,
)
from app.backend.rei.providers.ollama_en import (
    OllamaRacioNativeEnTriadProvider,
)
from app.backend.rei.research.triad_iso_e3 import (
    CASE_ORDER,
    EXPECTED_BASE_COMMIT,
    EXPECTED_SOURCE_CANDIDATE_SHA256,
    PAIR_CASES,
    PAIR_ORDER,
    SOURCE_CANDIDATE_RELATIVE_PATH,
    _packet_explicit_goal,
    _pair_observations,
    _render_report,
    _shared_preparations,
    deterministic_references,
    execution_candidate,
    model_free_preflight,
    run_next,
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
            server_version="offline-e3-preflight",
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


def test_e3_uses_only_the_frozen_six_case_source_projection() -> None:
    source_path = REPOSITORY_ROOT / SOURCE_CANDIDATE_RELATIVE_PATH
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == (
        EXPECTED_SOURCE_CANDIDATE_SHA256
    )
    candidate = execution_candidate(REPOSITORY_ROOT)

    assert candidate["source_candidate"]["sha256"] == (
        EXPECTED_SOURCE_CANDIDATE_SHA256
    )
    assert tuple(candidate["pair_order"]) == PAIR_ORDER
    assert tuple(candidate["case_order"]) == CASE_ORDER
    assert len(candidate["pairs"]) == 3
    assert sum(len(pair["variants"]) for pair in candidate["pairs"]) == 6
    assert EXPECTED_BASE_COMMIT == (
        "429d80ad3dbc6aaecdf6e42b0872011abee3eaa9"
    )


def test_pair_shared_racio_packets_are_identical_and_route_scoped() -> None:
    prepared = _shared_preparations(
        execution_candidate(REPOSITORY_ROOT), _offline_provider()
    )
    indexed = {item["pair_id"]: item for item in prepared}

    for pair_id in PAIR_ORDER:
        pair = indexed[pair_id]
        assert pair["variants"][0]["packet"].content_hash() == pair[
            "variants"
        ][1]["packet"].content_hash()
        assert pair["variants"][0]["request_payload"] == pair["variants"][1][
            "request_payload"
        ]

    packets = {
        pair_id: json.dumps(
            indexed[pair_id]["request_payload"],
            ensure_ascii=False,
        ).casefold()
        for pair_id in PAIR_ORDER
    }
    assert all(
        token not in packets["public_credit_audience"]
        for token in ("six project-team", "wider audience", "publicly recognized")
    )
    assert all(
        token not in packets["loan_attachment_distance"]
        for token in ("friend", "acquaintance", "attachment", "care")
    )
    assert all(
        token not in packets["factory_public_status"]
        for token in ("competency review", "recognition", "status")
    )
    assert (
        _packet_explicit_goal(indexed["public_credit_audience"]["packet"])
        == "Preserve accurate and enforceable authorship attribution in the "
        "official record while controlling interruption and uncertainty."
    )
    assert (
        _packet_explicit_goal(indexed["loan_attachment_distance"]["packet"])
        == "Protect self's liquidity, ownership of funds, and enforceable "
        "repayment position while responding to the request."
    )
    assert (
        _packet_explicit_goal(indexed["factory_public_status"]["packet"])
        == "Minimize expected technical and financial loss under the "
        "three-minute decision boundary while retaining stated uncertainty."
    )


def test_manual_e_and_i_references_have_required_route_distinctions() -> None:
    references = deterministic_references(execution_candidate(REPOSITORY_ROOT))
    cases = references["cases"]

    assert references["native_processor_executions"] == {"E": 0, "I": 0}
    assert references["model_calls"] == 0
    assert all(
        value["emocio"]["manual_annotation"]
        and not value["emocio"]["processor_capability_claimed"]
        and value["emocio"]["evidence_closure"] == "passed"
        and value["instinkt"]["typed_mapping"]
        and not value["instinkt"]["processor_capability_claimed"]
        and value["instinkt"]["category_evidence_closure"] == "passed"
        for value in cases.values()
    )

    public_a, public_b = PAIR_CASES["public_credit_audience"]
    loan_a, loan_b = PAIR_CASES["loan_attachment_distance"]
    factory_a, factory_b = PAIR_CASES["factory_public_status"]
    assert cases[public_a]["emocio"]["valuation_vectors"] != cases[public_b][
        "emocio"
    ]["valuation_vectors"]
    assert cases[loan_a]["instinkt"]["option_results"] != cases[loan_b][
        "instinkt"
    ]["option_results"]
    assert cases[factory_a]["emocio"]["valuation_vectors"] != cases[factory_b][
        "emocio"
    ]["valuation_vectors"]
    assert cases[loan_a]["emocio"]["valuation_vectors"] == cases[loan_b][
        "emocio"
    ]["valuation_vectors"]
    assert cases[factory_a]["instinkt"]["option_results"] == cases[factory_b][
        "instinkt"
    ]["option_results"]


def test_model_free_preflight_proves_opaque_and_order_invariance() -> None:
    report = model_free_preflight(
        execution_candidate(REPOSITORY_ROOT), _offline_provider()
    )

    assert report["status"] == "passed"
    assert all(report["checks"].values())
    assert all(report["opaque_order_checks"].values())
    assert len(report["opaque_order_checks"]) == 6
    assert report["model_calls"] == 0
    assert report["native_processor_executions"] == {"E": 0, "I": 0}


def test_execution_path_has_one_dispatch_and_no_native_e_i_replay() -> None:
    source = inspect.getsource(run_next)

    assert source.count("provider.execute(") == 1
    assert "character" not in source
    assert "choose_native_option" not in source
    assert "project_emocio_typed_valuations" not in source
    assert "project_instinkt_typed_sensitivity" not in source


def test_report_keeps_required_human_fields_blank() -> None:
    candidate = execution_candidate(REPOSITORY_ROOT)
    references = deterministic_references(candidate)
    prepared = _shared_preparations(candidate, _offline_provider())
    conclusion = {
        "option_id": None,
        "facts_used": [],
        "unknowns": [],
        "explicit_goal": "Grounded test goal.",
        "causal_sequence": ["Retain uncertainty."],
        "utility_structure": ["No expected option is asserted."],
        "main_objection": "Human review remains required.",
    }
    outputs = {
        pair_id: {
            "status": "accepted",
            "packet_hash": next(
                item["packet"].content_hash()
                for item in prepared
                if item["pair_id"] == pair_id
            ),
            "conclusion": conclusion,
            "failure": None,
        }
        for pair_id in PAIR_ORDER
    }
    report = _render_report(
        {
            "seal_sha256": "0" * 64,
            "model_digest": EXPECTED_MODEL_DIGEST,
        },
        outputs,
        references,
        _pair_observations(references),
        candidate,
        prepared,
    )

    assert "Racio pair isolation: [ ] passed [ ] failed [ ] uncertain" in report
    assert (
        "Emocio route fidelity: [ ] plausible [ ] implausible [ ] uncertain"
        in report
    )
    assert "Instinkt pair isolation: [ ] passed [ ] failed [ ] uncertain" in report
    assert "Option change required: no" in report
    assert "No human-review field was completed by Codex." in report
