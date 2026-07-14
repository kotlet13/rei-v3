"""Safe manifestation-to-Racio vertical with optional C3 provider evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..models.common import LanguageCode, NonEmptyId
from ..models.communication import (
    AcceptanceFidelityAssessment,
    AcceptanceState,
    EmocioManifestation,
    InstinktManifestation,
    ManifestationObservation,
    ObservableManifestationView,
    RacioInterpretation,
    RacioInterpreterRequest,
    TranslationGap,
)
from .acceptance import assess_acceptance_fidelity
from .conscious_view import build_observable_manifestation_view
from .fake_vlm import EmocioVlmEnrichment, renderer_observations_from_vlm
from .interpreter import (
    RacioInterpreter,
    validate_interpretation_attribution,
    validate_interpretation_replay,
)
from .translation_gap import NativeConclusion, evaluate_translation_gap
from .structured_interpreter import (
    StructuredLLMRacioInterpreter,
    StructuredRacioInterpretationResult,
)


TrustedManifestation = EmocioManifestation | InstinktManifestation


@dataclass(frozen=True, slots=True)
class CommunicationInterpretationResult:
    """The exact trusted request, interpretation, and optional C3 evidence."""

    request: RacioInterpreterRequest
    interpretation: RacioInterpretation
    c3_result: StructuredRacioInterpretationResult | None = None


@dataclass(frozen=True, slots=True)
class CommunicationProcessResult:
    """Complete B9 output; diagnostic native truth stays outside the interpreter."""

    request: RacioInterpreterRequest
    interpretation: RacioInterpretation
    translation_gap: TranslationGap
    acceptance_fidelity: AcceptanceFidelityAssessment
    c3_result: StructuredRacioInterpretationResult | None = None


def _build_trusted_views(
    *,
    manifestations: tuple[TrustedManifestation, ...],
    vlm_enrichments: tuple[EmocioVlmEnrichment, ...],
) -> tuple[
    tuple[ObservableManifestationView, ...],
    dict[str, tuple[ManifestationObservation, ...]],
]:
    enrichment_by_id = {
        enrichment.manifestation_id: enrichment for enrichment in vlm_enrichments
    }
    if len(enrichment_by_id) != len(vlm_enrichments):
        raise ValueError("VLM enrichment manifestation IDs must be unique")
    manifestation_ids = {item.manifestation_id for item in manifestations}
    if not set(enrichment_by_id).issubset(manifestation_ids):
        raise ValueError("VLM enrichment cites an unknown manifestation")

    views: list[ObservableManifestationView] = []
    renderer_by_manifestation: dict[
        str, tuple[ManifestationObservation, ...]
    ] = {}
    for manifestation in manifestations:
        enrichment = enrichment_by_id.get(manifestation.manifestation_id)
        if enrichment is None:
            views.append(build_observable_manifestation_view(manifestation))
            continue
        if not isinstance(manifestation, EmocioManifestation):
            raise ValueError("Only Emocio manifestations may receive VLM enrichment")
        renderer_observations = renderer_observations_from_vlm(
            manifestation=manifestation,
            request=enrichment.request,
            result=enrichment.result,
        )
        views.append(
            ObservableManifestationView.create_with_renderer_observations(
                manifestation=manifestation,
                renderer_observations=renderer_observations,
            )
        )
        renderer_by_manifestation[manifestation.manifestation_id] = (
            renderer_observations
        )
    return tuple(views), renderer_by_manifestation


def interpret_manifestations(
    *,
    manifestations: tuple[TrustedManifestation, ...],
    allowed_option_ids: tuple[NonEmptyId, ...],
    acceptance_state: AcceptanceState,
    interpreter: RacioInterpreter,
    vlm_enrichments: tuple[EmocioVlmEnrichment, ...] = (),
    language: LanguageCode | None = None,
    option_descriptions: Mapping[str, str] | None = None,
) -> CommunicationInterpretationResult:
    """Build views internally so callers cannot inject a handcrafted observable view."""

    if not manifestations:
        raise ValueError("Communication interpretation requires manifestations")
    canonical_manifestations = tuple(
        sorted(manifestations, key=lambda item: item.manifestation_id)
    )
    views, renderer_by_manifestation = _build_trusted_views(
        manifestations=canonical_manifestations,
        vlm_enrichments=vlm_enrichments,
    )
    request = RacioInterpreterRequest.create(
        views=views,
        allowed_option_ids=allowed_option_ids,
        acceptance_state=acceptance_state,
    )
    request.validate_against(
        manifestations=canonical_manifestations,
        acceptance_state=acceptance_state,
        renderer_observations_by_manifestation=renderer_by_manifestation,
    )
    c3_result: StructuredRacioInterpretationResult | None = None
    if isinstance(interpreter, StructuredLLMRacioInterpreter):
        c3_result = interpreter.interpret_with_evidence(
            request,
            language=language,
            option_descriptions=option_descriptions,
        )
        interpretation = c3_result.interpretation
    else:
        interpretation = interpreter.interpret(request)
    validate_interpretation_attribution(
        interpreter=interpreter,
        request=request,
        interpretation=interpretation,
    )
    if getattr(interpreter, "replay_safe", False) is True:
        validate_interpretation_replay(
            interpreter=interpreter,
            request=request,
            interpretation=interpretation,
        )
    return CommunicationInterpretationResult(
        request=request,
        interpretation=interpretation,
        c3_result=c3_result,
    )


def process_communication(
    *,
    conclusion: NativeConclusion,
    manifestations: tuple[TrustedManifestation, ...],
    allowed_option_ids: tuple[NonEmptyId, ...],
    acceptance_state: AcceptanceState,
    interpreter: RacioInterpreter,
    vlm_enrichments: tuple[EmocioVlmEnrichment, ...] = (),
    language: LanguageCode | None = None,
    option_descriptions: Mapping[str, str] | None = None,
) -> CommunicationProcessResult:
    """Run the complete B9 vertical while keeping native truth evaluator-only."""

    interpreted = interpret_manifestations(
        manifestations=manifestations,
        allowed_option_ids=allowed_option_ids,
        acceptance_state=acceptance_state,
        interpreter=interpreter,
        vlm_enrichments=vlm_enrichments,
        language=language,
        option_descriptions=option_descriptions,
    )
    gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=manifestations,
        interpretation=interpreted.interpretation,
    )
    assessment = assess_acceptance_fidelity(
        acceptance_state=acceptance_state,
        gap=gap,
    )
    return CommunicationProcessResult(
        request=interpreted.request,
        interpretation=interpreted.interpretation,
        translation_gap=gap,
        acceptance_fidelity=assessment,
        c3_result=interpreted.c3_result,
    )


__all__ = [
    "CommunicationInterpretationResult",
    "CommunicationProcessResult",
    "EmocioVlmEnrichment",
    "TrustedManifestation",
    "interpret_manifestations",
    "process_communication",
]
