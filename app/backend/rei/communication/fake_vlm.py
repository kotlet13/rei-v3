"""Deterministic no-model VisionLanguageInterpreter for visible Emocio images."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..ids import content_id
from ..models.common import LanguageCode, NonEmptyId, NonEmptyText
from ..models.communication import (
    CommunicationArtifactRef,
    EmocioManifestation,
    ManifestationObservation,
    ObservableManifestationView,
)
from ..models.provider import ProviderCallRecord, ProviderCallSpec, ProviderIdentity
from ..providers.protocols import VisionLanguageRequest, VisionLanguageResult
from ..models.provider import ensure_call_contract


def build_emocio_vlm_request(
    *,
    manifestation: EmocioManifestation,
    question: NonEmptyText,
    language: LanguageCode,
) -> VisionLanguageRequest:
    """Build a VLM request from visible E image IDs, never from native truth."""

    if manifestation.manifestation_status != "derived_b9":
        raise ValueError("VLM observation requires a verified Emocio manifestation")
    if not manifestation.visible_image_artifact_ids:
        raise ValueError("VLM observation requires at least one visible Emocio image")
    base = {
        "manifestation_id": manifestation.manifestation_id,
        "manifestation_hash": manifestation.content_hash(),
        "artifact_ids": manifestation.visible_image_artifact_ids,
        "question": question,
        "language": language,
    }
    return VisionLanguageRequest(
        request_id=content_id("emocio_vlm_request", base),
        artifact_ids=manifestation.visible_image_artifact_ids,
        question=question,
        language=language,
    )


def validate_emocio_vlm_request(
    *,
    manifestation: EmocioManifestation,
    request: VisionLanguageRequest,
) -> VisionLanguageRequest:
    expected = build_emocio_vlm_request(
        manifestation=manifestation,
        question=request.question,
        language=request.language,
    )
    if request != expected:
        raise ValueError("VLM request differs from visible Emocio manifestation replay")
    return request


@dataclass(frozen=True, slots=True)
class FakeVisionLanguageInterpreter:
    """Existing VLM protocol implementation that invokes no provider or model."""

    interpretation: str = "fake_visible_image_interpretation"
    inferred_claims: tuple[str, ...] = ()
    completed_at: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)

    @property
    def identity(self) -> ProviderIdentity:
        return ProviderIdentity(
            provider_id="b9_fake_vision_language_interpreter",
            kind="vision_language",
            implementation="rei.communication.FakeVisionLanguageInterpreter",
            implementation_revision="1",
            uses_model=False,
        )

    def interpret(
        self,
        request: VisionLanguageRequest,
        *,
        call: ProviderCallSpec,
    ) -> VisionLanguageResult:
        if len(set(request.artifact_ids)) != len(request.artifact_ids):
            raise ValueError("VLM request image IDs must be unique")
        ensure_call_contract(
            self.identity,
            call,
            request_id=request.request_id,
            expected_kind="vision_language",
            required_input_artifact_ids=request.artifact_ids,
        )
        if call.input_artifact_ids != request.artifact_ids:
            raise ValueError("Fake VLM call inputs must exactly match visible image IDs")
        result_base = {
            "request_id": request.request_id,
            "request_hash": request.content_hash(),
            "interpretation": self.interpretation,
            "inferred_claims": self.inferred_claims,
            "source_artifact_ids": request.artifact_ids,
            "provider": self.identity,
            "call_spec_hash": call.content_hash(),
            "completed_at": self.completed_at,
        }
        result_id = content_id("vlm_result", result_base)
        record = ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=call.request_id,
            input_artifact_ids=call.input_artifact_ids,
            provider=call.provider,
            seed=call.seed,
            parameters=call.parameters,
            timeout_seconds=call.timeout_seconds,
            started_at=self.completed_at,
            primary_finished_at=self.completed_at,
            finished_at=self.completed_at,
            status="succeeded",
            primary_status="succeeded",
            fallback=None,
            output_artifact_ids=(result_id,),
            warnings=("deterministic fake; no model invoked",),
            safety_notice=call.safety_notice,
        )
        return VisionLanguageResult(
            result_id=result_id,
            request_id=request.request_id,
            interpretation=self.interpretation,
            inferred_claims=self.inferred_claims,
            source_artifact_ids=request.artifact_ids,
            call_spec=call,
            call=record,
        )


@dataclass(frozen=True, slots=True)
class EmocioVlmEnrichment:
    """Trusted orchestration input for one visible Emocio manifestation."""

    manifestation_id: NonEmptyId
    request: VisionLanguageRequest
    result: VisionLanguageResult


def renderer_observations_from_vlm(
    *,
    manifestation: EmocioManifestation,
    request: VisionLanguageRequest,
    result: VisionLanguageResult,
) -> tuple[ManifestationObservation, ...]:
    """Bind fake/provider text to visible E images as explicitly ungrounded content."""

    validate_emocio_vlm_request(manifestation=manifestation, request=request)
    if result.request_id != request.request_id or result.call_spec.request_id != request.request_id:
        raise ValueError("VLM result belongs to another visible-image request")
    if result.call_spec.input_artifact_ids != request.artifact_ids:
        raise ValueError("VLM result consumed artifacts outside the visible image request")
    if result.source_artifact_ids != request.artifact_ids:
        raise ValueError("VLM result source images differ from its request")
    refs = {
        ref.artifact_id: ref for ref in manifestation.visible_image_artifact_hashes
    }
    if set(refs) != set(request.artifact_ids):
        raise ValueError("Emocio image hash lineage differs from the VLM request")
    manifestation_hash = manifestation.content_hash()
    return tuple(
        ManifestationObservation.create_renderer_interpretation(
            manifestation_id=manifestation.manifestation_id,
            manifestation_hash=manifestation_hash,
            image_ref=CommunicationArtifactRef(
                artifact_id=image_id,
                artifact_hash=refs[image_id].artifact_hash,
            ),
            provider_result_id=result.result_id,
            provider_result_hash=result.content_hash(),
            interpretation=result.interpretation,
            inferred_claims=result.inferred_claims,
        )
        for image_id in request.artifact_ids
    )


def build_vlm_enriched_view(
    *,
    manifestation: EmocioManifestation,
    request: VisionLanguageRequest,
    result: VisionLanguageResult,
) -> ObservableManifestationView:
    """Create the content-addressed E view after validating exact VLM lineage."""

    observations = renderer_observations_from_vlm(
        manifestation=manifestation,
        request=request,
        result=result,
    )
    return ObservableManifestationView.create_with_renderer_observations(
        manifestation=manifestation,
        renderer_observations=observations,
    )


__all__ = [
    "EmocioVlmEnrichment",
    "FakeVisionLanguageInterpreter",
    "build_emocio_vlm_request",
    "build_vlm_enriched_view",
    "renderer_observations_from_vlm",
    "validate_emocio_vlm_request",
]
