"""Pure diagnostic replay of Racio translation against frozen native truth."""

from __future__ import annotations

from ..ids import content_id, sha256_hex
from ..models.communication import (
    B9_EXACT_ACTION_FIDELITY_POLICY,
    B9_EXACT_DISTORTION_POLICY,
    CommunicationArtifactRef,
    DistortionType,
    EmocioManifestation,
    FidelityComponent,
    InstinktManifestation,
    RacioInterpretation,
    TranslationGap,
)
from ..models.emocio import EmocioNativeConclusion
from ..models.instinkt import InstinktNativeConclusion


NativeConclusion = EmocioNativeConclusion | InstinktNativeConclusion
TrustedManifestation = EmocioManifestation | InstinktManifestation


def _source_mind(conclusion: NativeConclusion) -> str:
    return "E" if isinstance(conclusion, EmocioNativeConclusion) else "I"


def _distortion_type(
    *,
    conclusion: NativeConclusion,
    interpretation: RacioInterpretation,
    action_score: float,
) -> DistortionType:
    if interpretation.interpretation_status in {"omitted_b9", "unavailable_b9"}:
        return "omission"
    if conclusion.option_id is None and interpretation.inferred_option_id is None:
        return "unknown"
    if conclusion.option_id != interpretation.inferred_option_id or action_score == 0.0:
        return "misclassification"
    if action_score == 1.0:
        return "none"
    return "unknown"


def evaluate_translation_gap(
    *,
    conclusion: NativeConclusion,
    manifestations: tuple[TrustedManifestation, ...],
    interpretation: RacioInterpretation,
) -> TranslationGap:
    """Compare exact typed action/option fields without keywords, fuzzy text, or LLMs."""

    if interpretation.interpretation_status == "unverified_contract":
        raise ValueError("B9 translation evaluation requires a verified interpretation")
    source_mind = _source_mind(conclusion)
    if interpretation.source_mind != source_mind:
        raise ValueError("Native conclusion and interpretation source minds differ")
    if not manifestations:
        raise ValueError("Translation evaluation requires trusted manifestations")
    canonical_manifestations = tuple(
        sorted(manifestations, key=lambda item: item.manifestation_id)
    )
    expected_type = EmocioManifestation if source_mind == "E" else InstinktManifestation
    for manifestation in canonical_manifestations:
        if not isinstance(manifestation, expected_type):
            raise ValueError("Translation manifestations use the wrong source mind")
        if manifestation.manifestation_status == "unverified_contract":
            raise ValueError("Translation evaluation requires verified manifestations")
        if (
            manifestation.source_conclusion_id != conclusion.conclusion_id
            or manifestation.source_conclusion_hash != conclusion.content_hash()
        ):
            raise ValueError("Manifestation belongs to another native conclusion")
    expected_refs = tuple(
        CommunicationArtifactRef(
            artifact_id=manifestation.manifestation_id,
            artifact_hash=manifestation.content_hash(),
        )
        for manifestation in canonical_manifestations
    )
    if interpretation.source_manifestation_hashes != expected_refs:
        raise ValueError("Interpretation does not close the trusted manifestations")

    native_action = conclusion.action_tendency
    interpreted_action = interpretation.inferred_action_tendency
    action_score = 1.0 if native_action == interpreted_action else 0.0
    component = FidelityComponent(
        facet="action_tendency",
        native_value=native_action,
        interpreted_value=interpreted_action,
        score=action_score,
        weight=1.0,
    )
    native_summary = (
        conclusion.desired_transformation
        if isinstance(conclusion, EmocioNativeConclusion)
        else conclusion.minimum_safety_condition
    )
    if not native_summary.strip():
        native_summary = "unknown"
    base: dict[str, object] = {
        "schema_version": "rei-native-translation-gap-v1",
        "gap_status": "derived_b9",
        "source_mind": source_mind,
        "source_conclusion_id": conclusion.conclusion_id,
        "source_conclusion_hash": conclusion.content_hash(),
        "interpretation_id": interpretation.interpretation_id,
        "source_interpretation_hash": interpretation.content_hash(),
        "interpretation_status": interpretation.interpretation_status,
        "native_option_id": conclusion.option_id,
        "interpreted_option_id": interpretation.inferred_option_id,
        "native_action_tendency": native_action,
        "native_motive_summary": native_summary,
        "interpreted_motive": interpretation.inferred_motive,
        "option_match": conclusion.option_id == interpretation.inferred_option_id,
        "option_comparison_applicable": (
            conclusion.option_id is not None
            and interpretation.inferred_option_id is not None
        ),
        "motive_fidelity": action_score,
        "distortion_type": _distortion_type(
            conclusion=conclusion,
            interpretation=interpretation,
            action_score=action_score,
        ),
        "fidelity_components": (component,),
        "metric_policy": B9_EXACT_ACTION_FIDELITY_POLICY,
        "metric_basis": "implementation_hypothesis",
        "distortion_policy": B9_EXACT_DISTORTION_POLICY,
    }
    if interpreted_action is not None:
        base["interpreted_action_tendency"] = interpreted_action
    gap_id = content_id("translation_gap", base)
    payload = {"translation_gap_id": gap_id, **base}
    return TranslationGap(**payload, translation_gap_hash=sha256_hex(payload))


def validate_translation_gap_replay(
    *,
    gap: TranslationGap,
    conclusion: NativeConclusion,
    manifestations: tuple[TrustedManifestation, ...],
    interpretation: RacioInterpretation,
) -> TranslationGap:
    """Reject a rehashed diagnostic that differs from the pure evaluator."""

    expected = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=manifestations,
        interpretation=interpretation,
    )
    if gap != expected:
        raise ValueError("TranslationGap differs from native/interpretation replay")
    return gap


__all__ = [
    "NativeConclusion",
    "TrustedManifestation",
    "evaluate_translation_gap",
    "validate_translation_gap_replay",
]
