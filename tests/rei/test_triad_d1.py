from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.backend.rei.emocio.policy import (
    EmocioPolicyDecision,
    OptionAggregateScore,
)
from app.backend.rei.governance.fixtures import load_governance_fixture
from app.backend.rei.providers.deterministic import (
    DeterministicEmocioNativeProvider,
    DeterministicInstinktNativeProvider,
)
from app.backend.rei.providers.ollama import (
    RACIO_CONTRACT_FAILURE_CODES,
    OllamaRacioNativeProvider,
    build_racio_failed_output_diagnostic,
    classify_racio_contract_failure,
)
from app.backend.rei.racio.contracts import RacioStructuredOutput
from app.backend.rei.research.triad_d1 import (
    S2_CASE_IDS,
    TRIAD_S1_RELATIVE_PATH,
    TRIAD_S2_RELATIVE_PATH,
    VALID_S1_CASE_IDS,
    audit_expected_answer_leakage,
    build_expected_call_ledger,
    build_s1_route_audit,
    build_s2_candidate,
    model_free_projection,
    native_artifact_id_projection,
    preflight_s2_candidate,
    verify_frozen_s1_bytes,
)
from app.backend.rei.triad_screen import prepare_corpus, replay_profiles


REPOSITORY_ROOT = Path(__file__).parents[2]
S1_ROOT = REPOSITORY_ROOT / TRIAD_S1_RELATIVE_PATH
S2_ROOT = REPOSITORY_ROOT / TRIAD_S2_RELATIVE_PATH
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "native_bundles"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_structured_output():
    corpus = _json(S1_ROOT / "corpus.json")
    packet = prepare_corpus(corpus)[0].racio_packet
    output = RacioStructuredOutput(
        option_id=packet.allowed_option_ids[0],
        facts_used=(packet.explicit_facts[0],),
        evidence_ids_used=(packet.evidence_ids[0],),
        unknowns=(packet.explicit_unknowns[0],),
        causal_sequence=("The cited observation constrains the option comparison.",),
        utility_structure=("Compare bounded process and resource consequences.",),
        explicit_goal="Choose within the supplied option scope.",
        main_objection="The conflicting sensor remains unresolved.",
        confidence=0.5,
        abstains=False,
        uncertainty="The supplied unknown remains open.",
    )
    output.validate_against(packet)
    return packet, output


def test_every_pre_d1_frozen_s1_byte_matches_the_accepted_head() -> None:
    verify_frozen_s1_bytes(REPOSITORY_ROOT)


def test_family_projection_separates_conclusion_and_processing_result_ids() -> None:
    call_record = _json(S1_ROOT / "cases/family_relocation/call_record.json")
    compact_output = _json(
        S1_ROOT / "cases/family_relocation/native_outputs.json"
    )

    projected = native_artifact_id_projection(call_record)

    assert projected == {
        "racio_conclusion_id": (
            "racio_conclusion_dc3c16c8beca6f7d6ef8d56507d7f8f2"
        ),
        "emocio_conclusion_id": (
            "emocio_conclusion_97884bbcaccb21b35b6fc80e661fa1f4"
        ),
        "emocio_processing_result_id": (
            "emocio_processing_result_8c4b04055e56b80de892fa4e3af892e8"
        ),
        "instinkt_conclusion_id": (
            "instinkt_conclusion_63a26e9d2caf926d102bcebe12bc248d"
        ),
    }
    assert projected["emocio_processing_result_id"] in (
        compact_output["observed_conclusion_ids"]
    )
    assert projected["emocio_conclusion_id"] not in (
        compact_output["observed_conclusion_ids"]
    )
    assert projected["emocio_processing_result_id"] not in {
        projected["racio_conclusion_id"],
        projected["emocio_conclusion_id"],
        projected["instinkt_conclusion_id"],
    }


def test_model_free_projection_serializes_emocio_dataclass() -> None:
    decision = EmocioPolicyDecision(
        selected=None,
        aggregate_scores=(
            OptionAggregateScore(option_id="option_a", score=0.5),
        ),
        tied_option_ids=("option_a",),
    )

    projected = model_free_projection(decision)

    assert projected == {
        "selected": None,
        "aggregate_scores": [{"option_id": "option_a", "score": 0.5}],
        "tied_option_ids": ["option_a"],
    }


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ({"option_id": "unknown_option_id"}, "unknown_option"),
        ({"facts_used": ("Invented fact.",)}, "hallucinated_fact"),
        ({"unknowns": ("Invented unknown.",)}, "unknown_claim"),
        ({"evidence_ids_used": ("outside_evidence",)}, "evidence_out_of_scope"),
        ({"evidence_ids_used": ()}, "missing_fact_citation"),
    ),
)
def test_bounded_racio_failure_categories(
    mutation: dict,
    expected_code: str,
) -> None:
    packet, output = _valid_structured_output()
    mutant = output.model_copy(update=mutation)

    assert classify_racio_contract_failure(mutant, packet) == expected_code
    diagnostic = build_racio_failed_output_diagnostic(
        structured=mutant,
        packet=packet,
    )
    projection = json.loads(diagnostic.canonical_json_projection)

    assert diagnostic.accepted is False
    assert diagnostic.failure_code == expected_code
    assert diagnostic.validation_stage == (
        "racio_structured_output_packet_contract"
    )
    assert "thinking" not in projection
    assert "traceback" not in projection
    assert "character" not in projection
    assert "gold" not in projection


def test_fact_evidence_mismatch_has_its_own_failure_code() -> None:
    packet, output = _valid_structured_output()
    mutant = output.model_copy(
        update={"evidence_ids_used": (packet.evidence_ids[1],)}
    )

    assert classify_racio_contract_failure(mutant, packet) == (
        "fact_evidence_mismatch"
    )
    assert RACIO_CONTRACT_FAILURE_CODES == (
        "unknown_option",
        "hallucinated_fact",
        "unknown_claim",
        "evidence_out_of_scope",
        "missing_fact_citation",
        "fact_evidence_mismatch",
        "other_contract_validation",
    )


def test_s1_route_audit_confirms_emocio_capacity_collapse_and_instinkt_scope() -> None:
    audit = build_s1_route_audit(REPOSITORY_ROOT)

    assert tuple(case["case_id"] for case in audit["cases"]) == (
        VALID_S1_CASE_IDS
    )
    assert all(
        case["emocio"]["valuation_vectors_identical"]
        and not case["emocio"]["full_rollout_inputs_identical"]
        and len(case["emocio"]["dimensions_equal_for_all_options"]) == 11
        and not case["emocio"]["dimensions_differing_between_options"]
        for case in audit["cases"]
    )
    assert all(
        "missing option-specific consequence"
        in case["instinkt"]["classifications"]
        and case["instinkt"]["legitimate_protective_ambiguity"]
        == "not_established"
        for case in audit["cases"]
    )
    assert audit["model_calls"] == 0
    assert audit["global_score_computed"] is False


def test_s2_candidate_has_distinguishable_emocio_and_instinkt_signatures() -> None:
    candidate = _json(S2_ROOT / "corpus_candidate.json")
    report = preflight_s2_candidate(candidate)

    assert tuple(case["case_id"] for case in candidate["cases"]) == S2_CASE_IDS
    assert candidate == build_s2_candidate(REPOSITORY_ROOT)
    assert report["passed"] is True
    assert all(
        case["emocio"]["unique_signature_count"] >= 2
        and case["instinkt"]["unique_signature_count"] >= 2
        and case["instinkt"]["every_effect_has_option_specific_evidence"]
        for case in report["cases"]
    )


def test_s2_preflight_is_option_order_invariant() -> None:
    candidate = build_s2_candidate(REPOSITORY_ROOT)
    reversed_candidate = copy.deepcopy(candidate)
    for case in reversed_candidate["cases"]:
        case["emocio_input"]["option_counterfactuals"].reverse()
        case["instinkt_input"]["option_consequences"].reverse()

    assert preflight_s2_candidate(reversed_candidate) == (
        preflight_s2_candidate(candidate)
    )


def test_s2_leakage_audit_rejects_expected_answer_and_remains_profile_blind() -> None:
    candidate = build_s2_candidate(REPOSITORY_ROOT)
    report = audit_expected_answer_leakage(candidate)
    assert report["expected_answer_leakage_found"] is False
    assert report["profile_blind"] is True

    mutant = copy.deepcopy(candidate)
    mutant["cases"][0]["instinkt_input"]["expected_option_id"] = (
        "factory_shutdown"
    )
    with pytest.raises(ValueError, match="expected-answer leakage"):
        preflight_s2_candidate(mutant)


def test_character_replay_does_not_execute_any_native_processor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("native processor/provider executed during replay")

    monkeypatch.setattr(DeterministicEmocioNativeProvider, "execute", forbidden)
    monkeypatch.setattr(DeterministicInstinktNativeProvider, "execute", forbidden)
    monkeypatch.setattr(OllamaRacioNativeProvider, "execute", forbidden)
    fixture = load_governance_fixture(sorted(FIXTURE_ROOT.glob("*.json"))[0])
    before = fixture.native_bundle.immutable_hash

    rows = replay_profiles(fixture.native_bundle)

    assert len(rows) == 13
    assert fixture.native_bundle.immutable_hash == before


def test_precommitted_s2_projection_is_model_free_and_unsealed() -> None:
    candidate = build_s2_candidate(REPOSITORY_ROOT)
    report = preflight_s2_candidate(candidate)
    leakage = audit_expected_answer_leakage(candidate)
    ledger = build_expected_call_ledger()

    assert _json(S2_ROOT / "corpus_candidate.json") == candidate
    assert _json(S2_ROOT / "distinguishability_report.json") == report
    assert _json(S2_ROOT / "leakage_report.json") == leakage
    assert _json(S2_ROOT / "expected_call_ledger.json") == ledger
    assert candidate["execution_seal_created"] is False
    assert candidate["model_calls_performed"] == 0
    assert ledger["triad_d1_actual"] == {
        "scope": "s2_candidate_preparation_and_preflight_only",
        "model_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "native_processor_calls": 0,
        "character_replay_rows": 0,
    }
    assert not (S2_ROOT / "pre_call_seal.json").exists()
