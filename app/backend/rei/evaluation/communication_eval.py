"""Evaluator-only communication fidelity and distortion classification."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from ..ids import sha256_hex
from .models import (
    CandidateInterpretation,
    EvaluationResultContext,
    InputExposureRecord,
    InterpretationClass,
    InterpretationEvaluationCase,
    SemanticEvaluationResult,
)
from .native_routes import (
    boolean_metric,
    issue,
    not_applicable_metric,
    numeric_metric,
)


COMMUNICATION_POLICY = "c2-structured-communication-fidelity-policy-v1"
DISTORTION_POLICY = "c2-explicit-distortion-evidence-policy-v1"

_OPERATION_LABELS: dict[str, InterpretationClass] = {
    "omit_signal": "omission",
    "downscale_signal": "minimization",
    "transfer_self_motive": "projection",
    "self_justify": "rationalization",
    "alternative_hypothesis": "partial",
    "insufficient_information": "unknown",
}
_EVIDENCE_LABELS: dict[str, InterpretationClass] = {
    "supported_visible_match": "accurate",
    "supported_facet_with_explicit_omission": "partial",
    "no_substantive_interpretation": "omission",
    "self_justification_without_visible_support": "rationalization",
    "visible_signal_downscaled_without_support": "minimization",
    "self_state_attributed_to_source_without_visible_support": "projection",
    "structured_option_and_motive_conflict": "misclassification",
    "insufficient_evidence_for_specific_label": "unknown",
}


def _candidate_operation_class(
    case: InterpretationEvaluationCase,
    candidate: CandidateInterpretation,
) -> InterpretationClass:
    if candidate.reasoning_operation in _OPERATION_LABELS:
        return _OPERATION_LABELS[candidate.reasoning_operation]
    if candidate.inferred_option_id is None and candidate.inferred_motive_class is None:
        return "unknown"
    exact = (
        candidate.inferred_option_id == case.expected_option_id
        and candidate.inferred_motive_class == case.expected_motive_class
        and candidate.inferred_action_tendency == case.expected_action_tendency
    )
    return "accurate" if exact else "misclassification"


def classify_interpretation(
    case: InterpretationEvaluationCase,
    candidate: CandidateInterpretation,
) -> InterpretationClass:
    """Classify from trusted structured evidence, never candidate prose/keywords."""

    evidence = case.distortion_evidence
    candidate_claim_ids = {claim.claim_id for claim in candidate.claims}
    evidence_claim_ids = set(evidence.candidate_claim_ids)
    evidence_binds = evidence_claim_ids.issubset(candidate_claim_ids) and set(
        evidence.contradicted_claim_ids
    ).issubset(candidate_claim_ids)
    if not evidence_binds:
        return "unknown"
    return _EVIDENCE_LABELS[evidence.evidence_kind]


def evaluate_interpretation_payload(
    *,
    case: InterpretationEvaluationCase,
    payload: Mapping[str, Any],
    trusted_exposure: InputExposureRecord,
) -> SemanticEvaluationResult:
    try:
        candidate = CandidateInterpretation.model_validate_json(
            json.dumps(payload, ensure_ascii=False)
        )
    except ValidationError as exc:
        return SemanticEvaluationResult.create(
            subject_id=f"{case.case_id}__invalid_payload",
            subject_kind="interpretation",
            family_id=case.family_id,
            variant_id=case.variant_id,
            mind=case.source_mind,
            expected_label=case.expected_interpretation_class,
            observed_label="invalid_schema",
            metrics=(
                boolean_metric(
                    "schema_validity",
                    "schema_validity",
                    False,
                    "Interpretation failed the strict C2 schema.",
                    policy_id=COMMUNICATION_POLICY,
                ),
            ),
            issues=(
                issue(
                    "schema_invalid",
                    "schema_validity",
                    f"Interpretation validation failed with {exc.error_count()} error(s).",
                ),
            ),
            evaluator_policies=(COMMUNICATION_POLICY,),
            evidence_artifact_ids=(trusted_exposure.exposure_id,),
            context=EvaluationResultContext(
                language="sl",
                review_status="canon_approved",
                cognition_mode=trusted_exposure.cognition_mode,
                candidate_content_hash=sha256_hex(payload),
                replay_artifact_ids=(trusted_exposure.exposure_id,),
            ),
        )
    return evaluate_interpretation(
        case=case,
        candidate=candidate,
        trusted_exposure=trusted_exposure,
    )


def evaluate_interpretation(
    *,
    case: InterpretationEvaluationCase,
    candidate: CandidateInterpretation,
    trusted_exposure: InputExposureRecord,
) -> SemanticEvaluationResult:
    observed = classify_interpretation(case, candidate)
    exposure_binding_ok = (
        trusted_exposure.subject_id == candidate.candidate_interpretation_id
    )
    identity_ok = (
        candidate.family_id == case.family_id
        and candidate.variant_id == case.variant_id
        and candidate.source_mind == case.source_mind
    )
    actual_inputs = set(trusted_exposure.actual_input_artifact_ids)
    allowed_artifacts = set(case.visible_manifestation_ids)
    visible_scope_ok = (
        exposure_binding_ok
        and actual_inputs.issubset(trusted_exposure.allowed_artifact_ids)
        and actual_inputs == allowed_artifacts
        and set(candidate.cited_observation_ids).issubset(case.visible_observation_ids)
        and set(candidate.cited_observation_ids).issubset(
            trusted_exposure.visible_observation_ids
        )
    )
    claims_required = observed not in {"omission", "unknown"}

    def claim_supported(claim: Any) -> bool:
        return (
            bool(claim.source_claim_ids)
            and set(claim.source_claim_ids).issubset(case.canonical_claim_ids)
            and bool(claim.observation_ids)
            and set(claim.observation_ids).issubset(candidate.cited_observation_ids)
            and set(claim.observation_ids).issubset(case.visible_observation_ids)
            and set(claim.observation_ids).issubset(
                trusted_exposure.visible_observation_ids
            )
            and claim.provenance_kind
            not in {"renderer_added_ungrounded", "world_projection"}
        )

    unsupported_claim_ids = tuple(
        claim.claim_id for claim in candidate.claims if not claim_supported(claim)
    )
    claims_present_ok = bool(candidate.claims) or not claims_required
    provenance_ok = (
        identity_ok
        and visible_scope_ok
        and claims_present_ok
        and not unsupported_claim_ids
    )
    profile_refs = actual_inputs & set(trusted_exposure.profile_artifact_ids)
    hidden_refs = actual_inputs & (
        set(trusted_exposure.evaluator_truth_artifact_ids)
        | set(case.evaluator_truth_artifact_ids)
        | set(trusted_exposure.forbidden_artifact_ids)
    )
    profile_ok = not profile_refs
    hidden_ok = not hidden_refs
    classification_ok = observed == case.expected_interpretation_class
    inference_absent = (
        candidate.inferred_option_id is None
        and candidate.inferred_motive_class is None
        and candidate.inferred_action_tendency is None
    )
    option_not_applicable = (
        case.expected_option_id is None and candidate.inferred_option_id is None
    )
    motive_not_applicable = (
        case.expected_motive_class is None
        and candidate.inferred_motive_class is None
    )
    action_not_applicable = (
        case.expected_action_tendency is None
        and candidate.inferred_action_tendency is None
    )
    motive_ok = motive_not_applicable or (
        candidate.inferred_motive_class == case.expected_motive_class
    )
    action_ok = action_not_applicable or (
        candidate.inferred_action_tendency == case.expected_action_tendency
    )
    operation_consistency = {
        "direct_inference": (
            candidate.justification_kind == "visible_evidence"
            and not inference_absent
        ),
        "omit_signal": (
            candidate.justification_kind == "omitted" and inference_absent
        ),
        "downscale_signal": candidate.justification_kind == "visible_evidence",
        "transfer_self_motive": candidate.justification_kind
        in {"visible_evidence", "self_justification"},
        "self_justify": candidate.justification_kind == "self_justification",
        "alternative_hypothesis": candidate.justification_kind
        in {"visible_evidence", "alternative_hypothesis"},
        "insufficient_information": (
            candidate.justification_kind in {"omitted", "alternative_hypothesis"}
            and (
                candidate.inferred_option_id is None
                or candidate.inferred_motive_class is None
                or candidate.inferred_action_tendency is None
            )
        ),
    }[candidate.reasoning_operation] and (
        _candidate_operation_class(case, candidate) == observed
    )
    fidelity_ok = (
        classification_ok
        and observed == "accurate"
        and identity_ok
        and provenance_ok
        and operation_consistency
    )
    alternatives_ok = (
        observed == "accurate"
        or bool(candidate.alternative_hypotheses or candidate.unresolved_ambiguity)
    )
    calibration_target = 1.0 if observed == "accurate" else 0.0
    brier = (candidate.confidence - calibration_target) ** 2
    calibration_ok = brier <= 0.25

    if option_not_applicable:
        option_metric = not_applicable_metric(
            "communication_option_inference",
            "communication_fidelity",
            "Option comparison is not applicable because both values are null.",
            policy_id=COMMUNICATION_POLICY,
        )
        option_ok = True
    else:
        option_ok = (
            candidate.inferred_option_id == case.expected_option_id
            and candidate.inferred_option_id in case.allowed_option_ids
            and candidate.inferred_option_id in trusted_exposure.visible_option_ids
        )
        option_metric = boolean_metric(
            "communication_option_inference",
            "communication_fidelity",
            option_ok,
            "Inferred option matches trusted truth and was visible to the interpreter.",
            policy_id=COMMUNICATION_POLICY,
        )

    if motive_not_applicable:
        motive_metric = not_applicable_metric(
            "communication_motive_class",
            "communication_fidelity",
            "Motive comparison is not applicable because both values are null.",
            policy_id=COMMUNICATION_POLICY,
        )
    else:
        motive_metric = boolean_metric(
            "communication_motive_class",
            "communication_fidelity",
            motive_ok,
            "Inferred motive class matches evaluator truth.",
            policy_id=COMMUNICATION_POLICY,
        )

    if action_not_applicable:
        action_metric = not_applicable_metric(
            "communication_action_tendency",
            "communication_fidelity",
            "Action comparison is not applicable because both values are null.",
            policy_id=COMMUNICATION_POLICY,
        )
    else:
        action_metric = boolean_metric(
            "communication_action_tendency",
            "communication_fidelity",
            action_ok,
            "Inferred action tendency matches evaluator truth when applicable.",
            policy_id=COMMUNICATION_POLICY,
        )

    metrics = (
        boolean_metric(
            "schema_validity",
            "schema_validity",
            True,
            "Interpretation passed the strict C2 schema.",
            policy_id=COMMUNICATION_POLICY,
        ),
        boolean_metric(
            "interpretation_identity",
            "communication_fidelity",
            identity_ok,
            "Candidate family, variant and source mind match evaluator truth.",
            policy_id=COMMUNICATION_POLICY,
        ),
        boolean_metric(
            "visible_scope_fidelity",
            "communication_fidelity",
            visible_scope_ok,
            "Every cited observation and actual artifact was in the conscious-access scope.",
            policy_id=COMMUNICATION_POLICY,
        ),
        boolean_metric(
            "interpretation_provenance",
            "provenance_completeness",
            provenance_ok,
            "Trusted exposure, candidate identity and claim lineage are complete.",
            policy_id=COMMUNICATION_POLICY,
        ),
        numeric_metric(
            "interpretation_unsupported_claim_count",
            "unsupported_claims",
            len(unsupported_claim_ids),
            0,
            not unsupported_claim_ids,
            "Every substantive interpretation claim cites visible observations and canonical source claims.",
            policy_id=COMMUNICATION_POLICY,
        ),
        option_metric,
        motive_metric,
        action_metric,
        boolean_metric(
            "reasoning_operation_consistency",
            "communication_fidelity",
            operation_consistency,
            "Typed reasoning operation, justification and emitted inference fields agree.",
            policy_id=DISTORTION_POLICY,
        ),
        boolean_metric(
            "distortion_classifier_correctness",
            "communication_fidelity",
            classification_ok,
            "Typed distortion classifier matches the reviewed case label.",
            policy_id=DISTORTION_POLICY,
        ),
        boolean_metric(
            "interpretation_accuracy",
            "communication_fidelity",
            fidelity_ok,
            "Interpretation classification matches a reviewed acceptable case and is not a reviewed distortion.",
            policy_id=DISTORTION_POLICY,
        ),
        numeric_metric(
            "profile_leakage_count",
            "profile_leakage",
            len(profile_refs),
            0,
            profile_ok,
            "Actual interpreter input contains no profile artifact.",
            policy_id=COMMUNICATION_POLICY,
        ),
        numeric_metric(
            "hidden_ground_truth_leakage_count",
            "hidden_ground_truth_leakage",
            len(hidden_refs),
            0,
            hidden_ok,
            "Actual interpreter input contains no evaluator-only native truth.",
            policy_id=COMMUNICATION_POLICY,
        ),
        boolean_metric(
            "alternative_hypotheses_or_ambiguity",
            "communication_fidelity",
            alternatives_ok,
            "Non-accurate interpretations retain an alternative or explicit ambiguity.",
            policy_id=COMMUNICATION_POLICY,
        ),
        numeric_metric(
            "confidence_brier",
            "confidence_calibration",
            brier,
            0.25,
            calibration_ok,
            "Confidence is low for distortions/unknowns and high for accurate cases.",
            policy_id="c2-per-case-brier-threshold-v1",
        ),
    )

    issues = []
    checks = (
        (identity_ok, "interpretation_identity_mismatch", "communication_fidelity", ()),
        (visible_scope_ok, "citation_outside_visible_scope", "communication_fidelity", ()),
        (
            provenance_ok,
            "incomplete_or_out_of_scope_provenance",
            "provenance_completeness",
            (trusted_exposure.exposure_id,),
        ),
        (
            not unsupported_claim_ids,
            "unsupported_claim",
            "unsupported_claims",
            unsupported_claim_ids,
        ),
        (profile_ok, "profile_leakage", "profile_leakage", tuple(sorted(profile_refs))),
        (
            hidden_ok,
            "hidden_ground_truth_leakage",
            "hidden_ground_truth_leakage",
            tuple(sorted(hidden_refs)),
        ),
        (option_ok, "option_misclassification", "communication_fidelity", ()),
        (motive_ok, "motive_misclassification", "communication_fidelity", ()),
        (action_ok, "action_misclassification", "communication_fidelity", ()),
        (
            operation_consistency,
            "reasoning_operation_inconsistent",
            "communication_fidelity",
            (),
        ),
        (
            classification_ok,
            "distortion_classifier_mismatch",
            "communication_fidelity",
            (),
        ),
        (alternatives_ok, "missing_alternative_hypothesis", "communication_fidelity", ()),
        (calibration_ok, "overconfident_interpretation", "confidence_calibration", ()),
    )
    for passed, code, dimension, refs in checks:
        if not passed:
            issues.append(
                issue(
                    code,
                    dimension,
                    f"Communication evaluation failed: {code}.",
                    refs=refs,
                )
            )
    if observed != "accurate":
        issues.append(
            issue(
                f"{observed}_detected",
                "communication_fidelity",
                f"Typed evidence classifies this interpretation as {observed}.",
                severity="error",
            )
        )

    return SemanticEvaluationResult.create(
        subject_id=candidate.candidate_interpretation_id,
        subject_kind="interpretation",
        family_id=case.family_id,
        variant_id=case.variant_id,
        mind=case.source_mind,
        expected_label=case.expected_interpretation_class,
        observed_label=observed,
        metrics=metrics,
        issues=tuple(issues),
        evaluator_policies=(
            COMMUNICATION_POLICY,
            DISTORTION_POLICY,
            "c2-per-case-brier-threshold-v1",
        ),
        evidence_artifact_ids=(trusted_exposure.exposure_id,),
        context=EvaluationResultContext(
            language="sl",
            review_status="canon_approved",
            cognition_mode=trusted_exposure.cognition_mode,
            candidate_content_hash=candidate.content_hash(),
            replay_artifact_ids=(trusted_exposure.exposure_id,),
        ),
    )


__all__ = [
    "COMMUNICATION_POLICY",
    "DISTORTION_POLICY",
    "classify_interpretation",
    "evaluate_interpretation",
    "evaluate_interpretation_payload",
]
