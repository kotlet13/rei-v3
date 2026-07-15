from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from app.backend.rei.evaluation.person_causality_eval import (
    DEFAULT_PERSON_CAUSALITY_CORPUS_PATH,
    NativeSemanticFingerprint,
    PersonCausalityEvaluationReport,
    SimulatorOutcomeTransition,
    evaluate_person_causality,
)
from app.backend.rei.ids import content_id, sha256_hex


@pytest.fixture(scope="module")
def report() -> PersonCausalityEvaluationReport:
    return evaluate_person_causality()


def _by_id(
    report: PersonCausalityEvaluationReport,
) -> dict[str, object]:
    return {item.case_id: item for item in report.cases}


def _readdress(
    payload: dict[str, object],
    *,
    id_field: str,
    hash_field: str,
    prefix: str,
) -> dict[str, object]:
    base = {
        key: value
        for key, value in payload.items()
        if key not in {id_field, hash_field}
    }
    artifact_id = content_id(prefix, base)
    envelope = {id_field: artifact_id, **base}
    return {**envelope, hash_field: sha256_hex(envelope)}


def test_person_causality_gate_preserves_bounded_authority_scope(
    report: PersonCausalityEvaluationReport,
) -> None:
    assert report.gate_passed is True
    assert report.case_count == report.passing_case_count == 4
    assert report.positive_case_count == report.control_case_count == 2
    assert report.shared_initial_condition_case_count == 4
    assert report.initial_native_invariance_case_count == 4
    assert report.fixed_world_character_invariance_case_count == 4
    assert report.positive_world_mediation_case_count == 2
    assert report.literal_character_leakage_count == 0

    assert report.gate_kind == "bounded_simulator_causal_contract"
    assert report.review_status == "internal_non_blind"
    assert report.gold_status == "implementation_hypothesis"
    assert report.person_causality_scope == "deterministic_simulator_only"
    assert report.semantic_authority_granted is False
    assert (
        report.full_history_character_noninterference
        == "not_claimed_lineage_ids_character_dependent"
    )
    assert report.measured_body_outcome_status == "open_no_verified_c5_replay"
    assert report.measured_body_signal_cycle_count == 0
    assert (
        report.instinkt_learning_scope
        == "prediction_sidecar_only_world_mutation_open_until_verified_c5_replay"
    )
    assert "aggregate_score" not in type(report).model_fields
    assert report.source_corpus_sha256 == hashlib.sha256(
        DEFAULT_PERSON_CAUSALITY_CORPUS_PATH.read_bytes()
    ).hexdigest()


def test_positive_and_control_pairs_have_expected_observable_actions(
    report: PersonCausalityEvaluationReport,
) -> None:
    cases = _by_id(report)
    assert tuple(cases) == (
        "equal_action_e_vs_i",
        "identity_sham_r_top",
        "positive_r_vs_e",
        "positive_r_vs_i",
    )

    for case_id in ("positive_r_vs_e", "positive_r_vs_i"):
        case = cases[case_id]
        assert case.control_kind == "positive"
        assert case.initial_condition_equal is True
        assert case.initial_native_surface_equal is True
        assert case.initial_behavior_statuses == ("executed", "executed")
        assert case.initial_behavior_option_ids == (
            "option_leave",
            "option_restore",
        )
        assert case.behavior_diverged is True
        assert case.simulator_outcomes_diverged is True
        assert case.passes is True

    equal_action = cases["equal_action_e_vs_i"]
    assert equal_action.profile_ids == ("E>R>I", "I>R>E")
    assert equal_action.initial_behavior_option_ids == (
        "option_restore",
        "option_restore",
    )
    assert equal_action.behavior_diverged is False

    identity_sham = cases["identity_sham_r_top"]
    assert identity_sham.profile_ids == ("R>E>I", "R>E>I")
    assert identity_sham.character_ids[0] != identity_sham.character_ids[1]
    assert identity_sham.initial_behavior_option_ids == (
        "option_leave",
        "option_leave",
    )
    assert identity_sham.behavior_diverged is False


def test_transition_is_character_blind_generated_simulator_provenance(
    report: PersonCausalityEvaluationReport,
) -> None:
    assert not {
        "character",
        "character_id",
        "profile_id",
        "governance",
    } & set(SimulatorOutcomeTransition.model_fields)

    for case in report.cases:
        for transition in case.transitions:
            evidence = transition.generated_evidence
            outcome = transition.simulator_outcome
            assert transition.causality_scope == "deterministic_simulator_only"
            assert evidence.modality == "simulator"
            assert evidence.provenance_kind == "generated"
            assert evidence.grounded is False
            assert evidence.inferred_by == transition.policy_id
            assert outcome.source == "simulator"
            assert outcome.observed_effects == (transition.observed_effect,)
            assert outcome.evidence_ids == (evidence.evidence_id,)
            assert transition.source_action.behavior_status == "executed"
            assert transition.source_action.option_id in {
                "option_leave",
                "option_restore",
            }
            semantic_transition = json.dumps(
                {
                    "code": transition.observation_code,
                    "effect": transition.observed_effect,
                    "evidence": evidence.content,
                },
                ensure_ascii=False,
            ).casefold()
            assert all(
                token.casefold() not in semantic_transition
                for token in (*case.character_ids, *case.profile_ids)
            )


def test_outcome_is_applied_after_native_cycle_then_diverges_world_probe(
    report: PersonCausalityEvaluationReport,
) -> None:
    for case in report.cases:
        # The simulator outcome belongs to cycle 1's Ego measure. It is learned
        # only by the post-cycle updater, so native cycle-1 semantics stay equal.
        assert case.cycle1_native_semantics_equal is True
        assert case.fixed_world_character_invariance is True
        assert all(row[0] == row[1] for row in case.probe_native_surface_hashes)

        if case.control_kind == "positive":
            assert case.racio_world_diverged is True
            assert case.emocio_world_diverged is True
            assert case.instinkt_world_diverged is False
            assert case.world_mediation_semantic_divergence is True
            assert all(
                case.probe_native_semantics[0][column]
                != case.probe_native_semantics[1][column]
                for column in range(2)
            )
            first_facts = case.probe_native_semantics[0][0].racio.facts_used
            second_facts = case.probe_native_semantics[1][0].racio.facts_used
            assert "workshop remained closed after option_leave" in first_facts
            assert "workshop reopened after option_restore" in second_facts
        else:
            assert case.racio_world_diverged is False
            assert case.emocio_world_diverged is False
            assert case.instinkt_world_diverged is False
            assert case.world_mediation_semantic_divergence is False
            assert all(
                case.probe_native_semantics[0][column]
                == case.probe_native_semantics[1][column]
                for column in range(2)
            )


def test_native_semantic_fingerprint_has_no_lineage_or_artifact_dimensions(
    report: PersonCausalityEvaluationReport,
) -> None:
    assert set(NativeSemanticFingerprint.model_fields) == {
        "schema_version",
        "fingerprint_id",
        "racio",
        "emocio",
        "instinkt",
        "fingerprint_hash",
    }
    for case in report.cases:
        for fingerprint in (
            *case.cycle1_native_semantics,
            *(item for row in case.probe_native_semantics for item in row),
        ):
            semantic = fingerprint.model_dump(
                mode="json",
                exclude={"fingerprint_id", "fingerprint_hash"},
            )
            serialized = json.dumps(semantic, sort_keys=True).casefold()
            for forbidden in (
                "association_match_id",
                "projection_id",
                "artifact_id",
                "measure_id",
                "bundle_id",
                "provider_call",
            ):
                assert forbidden not in serialized


def test_content_addressed_models_reject_forged_and_readdressed_mutants(
    report: PersonCausalityEvaluationReport,
) -> None:
    transition_payload = report.cases[0].transitions[0].model_dump(
        mode="python", round_trip=True
    )
    transition_payload["observed_effect"] = "forged simulator effect"
    with pytest.raises(ValidationError, match="depend only on behavior"):
        SimulatorOutcomeTransition.model_validate(transition_payload)

    fingerprint_payload = report.cases[0].cycle1_native_semantics[0].model_dump(
        mode="python", round_trip=True
    )
    fingerprint_payload["racio"]["facts_used"] = ("forged fact",)
    with pytest.raises(ValidationError, match="ID differs from its content"):
        NativeSemanticFingerprint.model_validate(fingerprint_payload)

    case_payload = report.cases[0].model_dump(mode="python", round_trip=True)
    case_payload["passes"] = not case_payload["passes"]
    readdressed_case = _readdress(
        case_payload,
        id_field="case_result_id",
        hash_field="result_hash",
        prefix="person_causality_case",
    )
    with pytest.raises(ValidationError, match="replayed metrics"):
        type(report.cases[0]).model_validate(readdressed_case)

    report_payload = report.model_dump(mode="python", round_trip=True)
    report_payload["passing_case_count"] = 0
    readdressed_report = _readdress(
        report_payload,
        id_field="report_id",
        hash_field="report_hash",
        prefix="person_causality_report",
    )
    with pytest.raises(ValidationError, match="replayed aggregates"):
        PersonCausalityEvaluationReport.model_validate(readdressed_report)


def test_report_is_cold_validatable_and_deterministically_reproducible(
    report: PersonCausalityEvaluationReport,
) -> None:
    cold = PersonCausalityEvaluationReport.model_validate_json(
        report.model_dump_json(round_trip=True)
    )
    assert cold == report

    repeated = evaluate_person_causality()
    assert repeated == report
    assert repeated.report_id == report.report_id
    assert repeated.report_hash == report.report_hash
