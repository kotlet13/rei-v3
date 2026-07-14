"""Longitudinal Ego evaluation without mutating the production trace."""

from __future__ import annotations

from .models import (
    EgoEvaluationCase,
    EgoEvaluationSample,
    EvaluationResultContext,
    SemanticEvaluationResult,
)
from .native_routes import boolean_metric, issue, not_applicable_metric, numeric_metric


EGO_POLICY = "c2-longitudinal-ego-evaluation-policy-v1"


def _facet_minds(projection_facets: tuple[str, ...]) -> tuple[str, ...] | None:
    """Parse facet ownership defensively, including unchecked model mutations."""

    minds: list[str] = []
    for projection_facet in projection_facets:
        mind, separator, facet = projection_facet.partition(":")
        if not separator or mind not in {"R", "E", "I"} or not facet.strip():
            return None
        minds.append(mind)
    return tuple(minds)


def evaluate_ego_sequence(
    *,
    case: EgoEvaluationCase,
    candidate: EgoEvaluationSample,
) -> SemanticEvaluationResult:
    measure_ok = (
        candidate.sequence_id == case.sequence_id
        and candidate.measure_ids == case.measure_ids
    )
    candidate_motif_ids = {motif.motif_id for motif in candidate.motifs}
    expected_motifs = set(case.expected_motif_ids)
    true_positive = len(candidate_motif_ids & expected_motifs)
    precision = (
        true_positive / len(candidate_motif_ids) if candidate_motif_ids else None
    )
    precision_ok = precision is None or precision == 1.0
    recall = true_positive / len(expected_motifs) if expected_motifs else 1.0
    support_ok = all(
        len(set(motif.supporting_measure_ids)) >= case.minimum_motif_support_measures
        and set(motif.supporting_measure_ids).issubset(case.measure_ids)
        for motif in candidate.motifs
    )
    gaps_ok = set(candidate.recurring_translation_gap_ids) == set(
        case.expected_translation_gap_ids
    )
    tensions_ok = set(candidate.unresolved_tension_ids) == set(
        case.expected_unresolved_tension_ids
    )
    projection_minds = tuple(mind for mind, _ in candidate.projection_evidence)
    projection_map = dict(candidate.projection_evidence)
    trusted_projection_minds = set(case.required_projection_minds)
    projection_evidence_ok = (
        len(set(projection_minds)) == len(projection_minds)
        and set(projection_minds) == trusted_projection_minds
        and all(
            bool(projection_map[mind])
            and len(set(projection_map[mind])) == len(projection_map[mind])
            and set(projection_map[mind]).issubset(case.measure_ids)
            for mind in case.required_projection_minds
        )
    )
    facet_minds = _facet_minds(candidate.projection_facets)
    projection_facets_ok = (
        len(set(candidate.projection_facets)) == len(candidate.projection_facets)
        and set(candidate.projection_facets) == set(case.expected_projection_facets)
        and facet_minds is not None
        and set(facet_minds) == trusted_projection_minds
    )
    projections_ok = projection_evidence_ok and projection_facets_ok
    narrative_ok = (
        bool(candidate.self_narrative_artifact_ids)
        and bool(candidate.composition_artifact_ids)
        and not (
            set(candidate.self_narrative_artifact_ids)
            & set(candidate.composition_artifact_ids)
        )
    )

    precision_metric = (
        not_applicable_metric(
            "ego_motif_precision",
            "longitudinal_motif_precision",
            "False-motif precision is not applicable when no motif is emitted.",
            policy_id=EGO_POLICY,
        )
        if precision is None
        else numeric_metric(
            "ego_motif_precision",
            "longitudinal_motif_precision",
            precision,
            1.0,
            precision_ok,
            "False motif rate is zero for the reviewed C2 sequence.",
            policy_id=EGO_POLICY,
        )
    )

    metrics = (
        boolean_metric(
            "ego_measure_scope",
            "ego_longitudinal",
            measure_ok,
            "Candidate uses the exact trusted longitudinal sequence and measure order.",
            policy_id=EGO_POLICY,
        ),
        precision_metric,
        numeric_metric(
            "ego_motif_recall",
            "ego_longitudinal",
            recall,
            1.0,
            recall == 1.0,
            "Missed motif rate is zero for the reviewed C2 sequence.",
            policy_id=EGO_POLICY,
        ),
        boolean_metric(
            "ego_motif_multi_measure_support",
            "ego_longitudinal",
            support_ok,
            "Every recurring motif is supported by the configured minimum distinct measures.",
            policy_id=EGO_POLICY,
        ),
        boolean_metric(
            "ego_translation_gap_continuity",
            "ego_longitudinal",
            gaps_ok,
            "Recurring translation gaps match trusted longitudinal truth.",
            policy_id=EGO_POLICY,
        ),
        boolean_metric(
            "ego_unresolved_tension_continuity",
            "ego_longitudinal",
            tensions_ok,
            "Unresolved tensions remain continuous across measures.",
            policy_id=EGO_POLICY,
        ),
        boolean_metric(
            "ego_modality_projection_evidence",
            "ego_longitudinal",
            projection_evidence_ok,
            "Candidate projection minds exactly match trusted scope and cite trusted sequence measures.",
            policy_id=EGO_POLICY,
        ),
        boolean_metric(
            "ego_modality_projection_facets",
            "ego_longitudinal",
            projection_facets_ok,
            "Candidate modality-owned facets exactly match trusted Racio, Emocio and Instinkt facets.",
            policy_id=EGO_POLICY,
        ),
        boolean_metric(
            "ego_narrative_composition_separation",
            "ego_longitudinal",
            narrative_ok,
            "Racio self-narrative artifacts are distinct from Ego composition artifacts.",
            policy_id=EGO_POLICY,
        ),
    )
    issues = []
    for passed, code in (
        (measure_ok, "ego_measure_scope_mismatch"),
        (precision_ok, "false_motif"),
        (recall == 1.0, "missed_motif"),
        (support_ok, "motif_without_multi_measure_support"),
        (gaps_ok, "translation_gap_continuity_mismatch"),
        (tensions_ok, "unresolved_tension_continuity_mismatch"),
        (projections_ok, "modality_projection_mismatch"),
        (narrative_ok, "self_narrative_composition_conflation"),
    ):
        if not passed:
            issues.append(
                issue(
                    code,
                    "ego_longitudinal",
                    f"Longitudinal Ego evaluation failed: {code}.",
                )
            )
    passed = all(metric.passed for metric in metrics)
    return SemanticEvaluationResult.create(
        subject_id=candidate.sample_id,
        subject_kind="ego_sequence",
        expected_label="longitudinal_consistent",
        observed_label=(
            "longitudinal_consistent" if passed else "longitudinal_inconsistent"
        ),
        metrics=metrics,
        issues=tuple(issues),
        evaluator_policies=(EGO_POLICY,),
        context=EvaluationResultContext(
            sequence_id=case.sequence_id,
            measure_ids=case.measure_ids,
            review_status="canon_approved",
            candidate_content_hash=candidate.content_hash(),
            replay_artifact_ids=candidate.composition_artifact_ids,
        ),
    )


__all__ = ["EGO_POLICY", "evaluate_ego_sequence"]
