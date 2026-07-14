"""Strict, model-free contracts used by the C2 semantic evaluator."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, Self, cast

from pydantic import Field, model_validator

from ..ids import content_id
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    MindId,
    NonEmptyId,
    NonEmptyText,
    Score01,
)


EvaluationDimension = Literal[
    "schema_validity",
    "provenance_completeness",
    "allowed_option_validity",
    "source_evidence_coverage",
    "unsupported_claims",
    "profile_leakage",
    "hidden_ground_truth_leakage",
    "confidence_calibration",
    "abstention_correctness",
    "slovenian_terminology",
    "native_route_semantics",
    "communication_fidelity",
    "bilingual_consistency",
    "ego_longitudinal",
    "option_choice",
    "character_causality",
    "conscious_behavior_divergence",
    "spoznanje",
    "visual_robustness",
    "body_mapper_agreement",
    "longitudinal_motif_precision",
    "latency",
    "vram",
    "ram",
    "artifact_size",
    "failure_mode",
]
EvaluationSubjectKind = Literal[
    "native_route",
    "interpretation",
    "bilingual_pair",
    "ego_sequence",
]
InterpretationClass = Literal[
    "accurate",
    "partial",
    "omission",
    "rationalization",
    "minimization",
    "projection",
    "misclassification",
    "unknown",
]
MetricStatus = Literal["passed", "failed", "not_applicable"]
ProvenanceKind = Literal[
    "supplied",
    "world_projection",
    "visible_manifestation",
    "renderer_added_ungrounded",
    "candidate_inference",
]


class EvaluationMetric(FrozenModel):
    metric_id: NonEmptyId
    dimension: EvaluationDimension
    status: MetricStatus
    policy_id: NonEmptyId
    value: float | int | str | bool | None
    threshold: float | int | str | bool | None = None
    detail: NonEmptyText

    @model_validator(mode="after")
    def validate_applicability(self) -> Self:
        if self.status == "not_applicable":
            if self.value is not None or self.threshold is not None:
                raise ValueError("Not-applicable metrics cannot carry value/threshold")
        elif self.value is None:
            raise ValueError("Applicable metrics require a value")
        if isinstance(self.value, float) and not (float("-inf") < self.value < float("inf")):
            raise ValueError("Metric values must be finite")
        return self

    @property
    def passed(self) -> bool:
        return self.status != "failed"


class EvaluationIssue(FrozenModel):
    issue_code: NonEmptyId
    dimension: EvaluationDimension
    severity: Literal["warning", "error"]
    detail: NonEmptyText
    evidence_refs: tuple[NonEmptyId, ...] = ()


class CandidateClaim(FrozenModel):
    claim_id: NonEmptyId
    facet: NonEmptyId
    value: NonEmptyText
    source_claim_ids: tuple[NonEmptyId, ...] = ()
    evidence_ids: tuple[NonEmptyId, ...] = ()
    observation_ids: tuple[NonEmptyId, ...] = ()
    provenance_kind: ProvenanceKind

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if len(set(self.source_claim_ids)) != len(self.source_claim_ids):
            raise ValueError("Source claim IDs must be unique")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Claim evidence IDs must be unique")
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("Claim observation IDs must be unique")
        return self


class InputExposureRecord(FrozenArtifactModel):
    """Trusted record of what an interpreter/provider actually received."""

    schema_version: Literal["rei-semantic-input-exposure-v1"] = (
        "rei-semantic-input-exposure-v1"
    )
    exposure_id: NonEmptyId
    subject_id: NonEmptyId
    allowed_artifact_ids: tuple[NonEmptyId, ...]
    actual_input_artifact_ids: tuple[NonEmptyId, ...]
    visible_observation_ids: tuple[NonEmptyId, ...] = ()
    visible_evidence_ids: tuple[NonEmptyId, ...] = ()
    visible_option_ids: tuple[NonEmptyId, ...] = ()
    forbidden_artifact_ids: tuple[NonEmptyId, ...] = ()
    profile_artifact_ids: tuple[NonEmptyId, ...] = ()
    evaluator_truth_artifact_ids: tuple[NonEmptyId, ...] = ()
    cognition_mode: Literal["structured", "visual", "motor", "body", "mixed"] = (
        "structured"
    )
    visual_artifact_ids: tuple[NonEmptyId, ...] = ()
    body_prediction_artifact_ids: tuple[NonEmptyId, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        subject_id: str,
        allowed_artifact_ids: Sequence[str],
        actual_input_artifact_ids: Sequence[str],
        visible_observation_ids: Sequence[str] = (),
        visible_evidence_ids: Sequence[str] = (),
        visible_option_ids: Sequence[str] = (),
        forbidden_artifact_ids: Sequence[str] = (),
        profile_artifact_ids: Sequence[str] = (),
        evaluator_truth_artifact_ids: Sequence[str] = (),
        cognition_mode: Literal[
            "structured", "visual", "motor", "body", "mixed"
        ] = "structured",
        visual_artifact_ids: Sequence[str] = (),
        body_prediction_artifact_ids: Sequence[str] = (),
    ) -> "InputExposureRecord":
        base = {
            "schema_version": "rei-semantic-input-exposure-v1",
            "subject_id": subject_id,
            "allowed_artifact_ids": tuple(allowed_artifact_ids),
            "actual_input_artifact_ids": tuple(actual_input_artifact_ids),
            "visible_observation_ids": tuple(visible_observation_ids),
            "visible_evidence_ids": tuple(visible_evidence_ids),
            "visible_option_ids": tuple(visible_option_ids),
            "forbidden_artifact_ids": tuple(forbidden_artifact_ids),
            "profile_artifact_ids": tuple(profile_artifact_ids),
            "evaluator_truth_artifact_ids": tuple(evaluator_truth_artifact_ids),
            "cognition_mode": cognition_mode,
            "visual_artifact_ids": tuple(visual_artifact_ids),
            "body_prediction_artifact_ids": tuple(body_prediction_artifact_ids),
        }
        return cls(exposure_id=content_id("input_exposure", base), **base)

    @model_validator(mode="after")
    def validate_sets(self) -> Self:
        for field_name in (
            "allowed_artifact_ids",
            "actual_input_artifact_ids",
            "visible_observation_ids",
            "visible_evidence_ids",
            "visible_option_ids",
            "forbidden_artifact_ids",
            "profile_artifact_ids",
            "evaluator_truth_artifact_ids",
            "visual_artifact_ids",
            "body_prediction_artifact_ids",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        if set(self.allowed_artifact_ids) & set(self.forbidden_artifact_ids):
            raise ValueError("Allowed and forbidden exposure sets must be disjoint")
        expected_id = content_id(
            "input_exposure",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"exposure_id"},
            ),
        )
        if self.exposure_id != expected_id:
            raise ValueError("Input exposure ID differs from canonical content")
        return self


class TerminologyUse(FrozenModel):
    terminology_id: NonEmptyId
    language: Literal["sl", "en"]
    surface_form: NonEmptyText


class NativeRouteEvaluationCase(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-native-route-case-v1"] = (
        "rei-semantic-native-route-case-v1"
    )
    case_id: NonEmptyId
    family_id: NonEmptyId
    variant_id: NonEmptyId
    expected_route_id: NonEmptyId
    mind: MindId
    allowed_option_ids: tuple[NonEmptyId, ...]
    grounded_evidence_ids: tuple[NonEmptyId, ...]
    allowed_observation_ids: tuple[NonEmptyId, ...] = ()
    canonical_claim_ids: tuple[NonEmptyId, ...]
    expected_evidence_ids: tuple[NonEmptyId, ...]
    expected_route_tags: tuple[NonEmptyId, ...]
    expected_option_id: NonEmptyId | None
    expected_decisive_representation: NonEmptyText
    expected_abstention: bool = False
    required_terminology_ids: tuple[NonEmptyId, ...]
    source_locator_refs: tuple[NonEmptyId, ...] = ()
    language: Literal["sl", "en"] = "sl"
    calibration_max_brier: float = Field(default=0.25, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_case(self) -> Self:
        for field_name in (
            "allowed_option_ids",
            "grounded_evidence_ids",
            "allowed_observation_ids",
            "canonical_claim_ids",
            "expected_evidence_ids",
            "expected_route_tags",
            "required_terminology_ids",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        if not set(self.expected_evidence_ids).issubset(self.grounded_evidence_ids):
            raise ValueError("Expected evidence must be grounded evidence")
        if self.expected_abstention != (self.expected_option_id is None):
            raise ValueError("Case abstention must correspond to a null expected option")
        if self.expected_option_id is not None and self.expected_option_id not in self.allowed_option_ids:
            raise ValueError("Expected option must be in allowed option scope")
        return self


class CandidateNativeRoute(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-candidate-native-route-v1"] = (
        "rei-semantic-candidate-native-route-v1"
    )
    candidate_route_id: NonEmptyId
    family_id: NonEmptyId
    variant_id: NonEmptyId
    mind: MindId
    claims: tuple[CandidateClaim, ...]
    route_tags: tuple[NonEmptyId, ...]
    option_id: NonEmptyId | None
    decisive_representation: NonEmptyText
    short_decision_bridge_sl: NonEmptyText
    terminology_uses: tuple[TerminologyUse, ...]
    visual_embedding_artifact_ids: tuple[NonEmptyId, ...] = ()
    valuation_artifact_ids: tuple[NonEmptyId, ...] = ()
    effect_source: Literal["manual_fixture", "rule_based", "model_backed"] | None = None
    body_prediction_artifact_ids: tuple[NonEmptyId, ...] = ()
    effect_evidence_ids: tuple[NonEmptyId, ...] = ()
    confidence: Score01
    abstains: bool = False
    uncertainty: NonEmptyText

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if self.abstains != (self.option_id is None):
            raise ValueError("Candidate must abstain exactly when option is null")
        for values, label in (
            (tuple(claim.claim_id for claim in self.claims), "claim IDs"),
            (self.route_tags, "route tags"),
            (
                tuple(item.terminology_id for item in self.terminology_uses),
                "terminology IDs",
            ),
            (self.visual_embedding_artifact_ids, "visual embedding IDs"),
            (self.valuation_artifact_ids, "valuation artifact IDs"),
            (self.body_prediction_artifact_ids, "body prediction IDs"),
            (self.effect_evidence_ids, "effect evidence IDs"),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"Candidate {label} must be unique")
        return self


class InterpretationDistortionEvidence(FrozenModel):
    evidence_kind: Literal[
        "supported_visible_match",
        "supported_facet_with_explicit_omission",
        "no_substantive_interpretation",
        "self_justification_without_visible_support",
        "visible_signal_downscaled_without_support",
        "self_state_attributed_to_source_without_visible_support",
        "structured_option_and_motive_conflict",
        "insufficient_evidence_for_specific_label",
    ]
    visible_support_ids: tuple[NonEmptyId, ...]
    candidate_claim_ids: tuple[NonEmptyId, ...]
    contradicted_claim_ids: tuple[NonEmptyId, ...]
    expected_label: InterpretationClass

    @model_validator(mode="after")
    def validate_evidence_ids(self) -> Self:
        for field_name in (
            "visible_support_ids",
            "candidate_claim_ids",
            "contradicted_claim_ids",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        if not set(self.contradicted_claim_ids).issubset(self.candidate_claim_ids):
            raise ValueError("Contradicted claims must be in candidate claim scope")
        return self


class InterpretationEvaluationCase(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-interpretation-case-v1"] = (
        "rei-semantic-interpretation-case-v1"
    )
    case_id: NonEmptyId
    family_id: NonEmptyId
    variant_id: NonEmptyId
    source_mind: Literal["E", "I"]
    visible_manifestation_ids: tuple[NonEmptyId, ...]
    visible_observation_ids: tuple[NonEmptyId, ...]
    allowed_option_ids: tuple[NonEmptyId, ...]
    canonical_claim_ids: tuple[NonEmptyId, ...]
    expected_option_id: NonEmptyId | None
    expected_motive_class: NonEmptyId | None
    expected_action_tendency: NonEmptyId | None = None
    expected_interpretation_class: InterpretationClass
    distortion_evidence: InterpretationDistortionEvidence
    evaluator_truth_artifact_ids: tuple[NonEmptyId, ...]

    @model_validator(mode="after")
    def validate_distortion_evidence(self) -> Self:
        evidence = self.distortion_evidence
        if evidence.expected_label != self.expected_interpretation_class:
            raise ValueError("Distortion evidence label differs from evaluator truth")
        if not set(evidence.visible_support_ids).issubset(
            self.visible_observation_ids
        ):
            raise ValueError("Distortion evidence cites an invisible observation")
        return self


class CandidateInterpretation(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-candidate-interpretation-v1"] = (
        "rei-semantic-candidate-interpretation-v1"
    )
    candidate_interpretation_id: NonEmptyId
    family_id: NonEmptyId
    variant_id: NonEmptyId
    source_mind: Literal["E", "I"]
    claims: tuple[CandidateClaim, ...]
    cited_observation_ids: tuple[NonEmptyId, ...]
    route_tags: tuple[NonEmptyId, ...]
    inferred_option_id: NonEmptyId | None
    inferred_motive_class: NonEmptyId | None
    inferred_action_tendency: NonEmptyId | None = None
    reasoning_operation: Literal[
        "direct_inference",
        "omit_signal",
        "downscale_signal",
        "transfer_self_motive",
        "self_justify",
        "alternative_hypothesis",
        "insufficient_information",
    ]
    justification_kind: Literal[
        "visible_evidence",
        "alternative_hypothesis",
        "self_justification",
        "omitted",
    ]
    alternative_hypotheses: tuple[NonEmptyText, ...] = ()
    unresolved_ambiguity: NonEmptyText | None = None
    confidence: Score01
    uncertainty: NonEmptyText

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        claim_ids = tuple(claim.claim_id for claim in self.claims)
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("Interpretation claim IDs must be unique")
        if len(set(self.cited_observation_ids)) != len(self.cited_observation_ids):
            raise ValueError("Cited observation IDs must be unique")
        if len(set(self.route_tags)) != len(self.route_tags):
            raise ValueError("Interpretation route tags must be unique")
        return self


class TrustedSemanticSignature(FrozenModel):
    concept_ids: tuple[NonEmptyId, ...]
    route_ids: tuple[NonEmptyId, ...]
    option_ids: tuple[NonEmptyId, ...]


class BilingualEvaluationCase(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-bilingual-case-v1"] = (
        "rei-semantic-bilingual-case-v1"
    )
    case_id: NonEmptyId
    family_id: NonEmptyId
    trusted_signature: TrustedSemanticSignature
    required_terminology_ids: tuple[NonEmptyId, ...]


class BilingualCandidatePair(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-bilingual-candidate-v1"] = (
        "rei-semantic-bilingual-candidate-v1"
    )
    pair_id: NonEmptyId
    family_id: NonEmptyId
    sl_variant_id: NonEmptyId
    en_variant_id: NonEmptyId
    sl_text: NonEmptyText
    en_text: NonEmptyText
    sl_signature: TrustedSemanticSignature
    en_signature: TrustedSemanticSignature
    terminology_uses: tuple[TerminologyUse, ...]


class EgoMotifCandidate(FrozenModel):
    motif_id: NonEmptyId
    motif_kind: Literal[
        "identity",
        "conflict",
        "translation_gap",
        "unresolved_tension",
    ]
    supporting_measure_ids: tuple[NonEmptyId, ...]


def _ego_projection_facet_minds(
    projection_facets: tuple[str, ...],
) -> tuple[MindId, ...]:
    """Validate and return the explicit ``<mind>:<facet>`` owners."""

    minds: list[MindId] = []
    for projection_facet in projection_facets:
        mind, separator, facet = projection_facet.partition(":")
        if not separator or mind not in {"R", "E", "I"} or not facet.strip():
            raise ValueError(
                "Projection facets must use the explicit '<R|E|I>:<facet>' form"
            )
        minds.append(cast(MindId, mind))
    return tuple(minds)


class EgoEvaluationCase(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-ego-case-v1"] = "rei-semantic-ego-case-v1"
    case_id: NonEmptyId
    sequence_id: NonEmptyId
    measure_ids: tuple[NonEmptyId, ...]
    expected_motif_ids: tuple[NonEmptyId, ...]
    expected_translation_gap_ids: tuple[NonEmptyId, ...]
    expected_unresolved_tension_ids: tuple[NonEmptyId, ...]
    expected_projection_facets: tuple[NonEmptyId, ...]
    required_projection_minds: tuple[MindId, ...] = ("R", "E", "I")
    minimum_motif_support_measures: int = Field(default=2, ge=2)

    @model_validator(mode="after")
    def validate_trusted_ego_scope(self) -> Self:
        for field_name in (
            "measure_ids",
            "expected_motif_ids",
            "expected_translation_gap_ids",
            "expected_unresolved_tension_ids",
            "expected_projection_facets",
            "required_projection_minds",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        facet_minds = _ego_projection_facet_minds(self.expected_projection_facets)
        if set(facet_minds) != set(self.required_projection_minds):
            raise ValueError(
                "Expected projection facets must cover exactly the trusted projection minds"
            )
        return self


class EgoEvaluationSample(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-ego-evaluation-sample-v1"] = (
        "rei-semantic-ego-evaluation-sample-v1"
    )
    sample_id: NonEmptyId
    sequence_id: NonEmptyId
    measure_ids: tuple[NonEmptyId, ...]
    motifs: tuple[EgoMotifCandidate, ...]
    recurring_translation_gap_ids: tuple[NonEmptyId, ...]
    unresolved_tension_ids: tuple[NonEmptyId, ...]
    projection_evidence: tuple[tuple[MindId, tuple[NonEmptyId, ...]], ...]
    projection_facets: tuple[NonEmptyId, ...]
    self_narrative_artifact_ids: tuple[NonEmptyId, ...]
    composition_artifact_ids: tuple[NonEmptyId, ...]

    @model_validator(mode="after")
    def validate_candidate_ego_scope(self) -> Self:
        for field_name in (
            "measure_ids",
            "recurring_translation_gap_ids",
            "unresolved_tension_ids",
            "projection_facets",
            "self_narrative_artifact_ids",
            "composition_artifact_ids",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        if not self.self_narrative_artifact_ids or not self.composition_artifact_ids:
            raise ValueError(
                "Candidate must explicitly identify self-narrative and composition artifacts"
            )

        motif_ids = tuple(motif.motif_id for motif in self.motifs)
        if len(set(motif_ids)) != len(motif_ids):
            raise ValueError("Ego motif IDs must be unique")

        projection_minds = tuple(mind for mind, _ in self.projection_evidence)
        if len(set(projection_minds)) != len(projection_minds):
            raise ValueError("Candidate projection evidence minds must be unique")
        for _, evidence_measure_ids in self.projection_evidence:
            if len(set(evidence_measure_ids)) != len(evidence_measure_ids):
                raise ValueError(
                    "Candidate projection evidence measure IDs must be unique"
                )

        facet_minds = _ego_projection_facet_minds(self.projection_facets)
        if set(facet_minds) != set(projection_minds):
            raise ValueError(
                "Candidate projection facets must cover exactly its projection evidence minds"
            )
        return self


class EvaluatedProviderProvenance(FrozenModel):
    provider_id: NonEmptyId
    provider_revision: NonEmptyText
    model_id: NonEmptyId | None = None
    model_revision: NonEmptyText | None = None
    seed: int | None = None

    @model_validator(mode="after")
    def validate_model_revision(self) -> Self:
        if (self.model_id is None) != (self.model_revision is None):
            raise ValueError("Evaluated model ID and revision must be recorded together")
        return self


class EvaluationResultContext(FrozenModel):
    source_locator_refs: tuple[NonEmptyId, ...] = ()
    language: Literal["sl", "en"] | None = None
    review_status: NonEmptyId | None = None
    reviewer_agreement_id: NonEmptyId | None = None
    expected_route_ids: tuple[NonEmptyId, ...] = ()
    actual_route_ids: tuple[NonEmptyId, ...] = ()
    sequence_id: NonEmptyId | None = None
    step_id: NonEmptyId | None = None
    measure_ids: tuple[NonEmptyId, ...] = ()
    ablation_id: NonEmptyId | None = None
    cognition_mode: NonEmptyId | None = None
    provider_provenance: EvaluatedProviderProvenance | None = None
    candidate_content_hash: HashDigest | None = None
    replay_artifact_ids: tuple[NonEmptyId, ...] = ()


class SemanticEvaluationResult(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-evaluation-result-v1"] = (
        "rei-semantic-evaluation-result-v1"
    )
    result_id: NonEmptyId
    subject_id: NonEmptyId
    subject_kind: EvaluationSubjectKind
    family_id: NonEmptyId | None = None
    variant_id: NonEmptyId | None = None
    mind: MindId | None = None
    expected_label: NonEmptyId
    observed_label: NonEmptyId
    passed: bool
    metrics: tuple[EvaluationMetric, ...]
    issues: tuple[EvaluationIssue, ...]
    evaluator_policies: tuple[NonEmptyId, ...]
    evidence_artifact_ids: tuple[NonEmptyId, ...] = ()
    context: EvaluationResultContext = EvaluationResultContext()
    evaluator_model_calls: Literal[0] = 0

    @classmethod
    def create(
        cls,
        *,
        subject_id: str,
        subject_kind: EvaluationSubjectKind,
        expected_label: str,
        observed_label: str,
        metrics: tuple[EvaluationMetric, ...],
        issues: tuple[EvaluationIssue, ...],
        evaluator_policies: tuple[str, ...],
        family_id: str | None = None,
        variant_id: str | None = None,
        mind: MindId | None = None,
        evidence_artifact_ids: tuple[str, ...] = (),
        context: EvaluationResultContext | None = None,
    ) -> "SemanticEvaluationResult":
        passed = all(metric.passed for metric in metrics) and not any(
            item.severity == "error" for item in issues
        )
        base: dict[str, Any] = {
            "schema_version": "rei-semantic-evaluation-result-v1",
            "subject_id": subject_id,
            "subject_kind": subject_kind,
            "family_id": family_id,
            "variant_id": variant_id,
            "mind": mind,
            "expected_label": expected_label,
            "observed_label": observed_label,
            "passed": passed,
            "metrics": metrics,
            "issues": issues,
            "evaluator_policies": evaluator_policies,
            "evidence_artifact_ids": evidence_artifact_ids,
            "context": context or EvaluationResultContext(),
            "evaluator_model_calls": 0,
        }
        return cls(result_id=content_id("semantic_eval", base), **base)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        metric_ids = tuple(metric.metric_id for metric in self.metrics)
        if not self.metrics or len(set(metric_ids)) != len(metric_ids):
            raise ValueError("Evaluation metrics must be non-empty and unique")
        replay = all(metric.passed for metric in self.metrics) and not any(
            item.severity == "error" for item in self.issues
        )
        if self.passed != replay:
            raise ValueError("Result pass state must replay from metrics and issues")
        expected_id = content_id(
            "semantic_eval",
            self.model_dump(mode="python", round_trip=True, exclude={"result_id"}),
        )
        if self.result_id != expected_id:
            raise ValueError("Semantic result ID does not match canonical content")
        return self


class SemanticEvaluationRun(FrozenArtifactModel):
    schema_version: Literal["rei-semantic-evaluation-run-v1"] = (
        "rei-semantic-evaluation-run-v1"
    )
    run_id: NonEmptyId
    source_manifest_hash: HashDigest
    evaluator_version: Literal["c2-v1"] = "c2-v1"
    results: tuple[SemanticEvaluationResult, ...] = Field(min_length=1)
    manually_reviewed_case_ids: tuple[NonEmptyId, ...] = ()
    ablation_ids: tuple[NonEmptyId, ...] = ()
    resource_telemetry_artifact_ids: tuple[NonEmptyId, ...] = ()
    evaluator_model_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_run_scope(self) -> Self:
        result_ids = tuple(result.result_id for result in self.results)
        if len(set(result_ids)) != len(result_ids):
            raise ValueError("Semantic evaluation result IDs must be unique")
        for field_name in (
            "manually_reviewed_case_ids",
            "ablation_ids",
            "resource_telemetry_artifact_ids",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        return self


# Backward-compatible name for the public package export while callers migrate
# to the explicit candidate-pair contract.
BilingualEvaluationSample = BilingualCandidatePair


__all__ = [
    "BilingualCandidatePair",
    "BilingualEvaluationCase",
    "BilingualEvaluationSample",
    "CandidateClaim",
    "CandidateInterpretation",
    "CandidateNativeRoute",
    "EgoEvaluationCase",
    "EgoEvaluationSample",
    "EgoMotifCandidate",
    "EvaluatedProviderProvenance",
    "EvaluationDimension",
    "EvaluationIssue",
    "EvaluationMetric",
    "EvaluationResultContext",
    "InputExposureRecord",
    "InterpretationClass",
    "InterpretationDistortionEvidence",
    "InterpretationEvaluationCase",
    "MetricStatus",
    "NativeRouteEvaluationCase",
    "ProvenanceKind",
    "SemanticEvaluationResult",
    "SemanticEvaluationRun",
    "TerminologyUse",
    "TrustedSemanticSignature",
]
