"""Provider-neutral B2 contracts with explicit provenance and fallbacks."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import Field, model_validator

from ..models.common import (
    ArtifactModel,
    ArtifactRelativePath,
    FrozenArtifactModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
)
from ..models.ego import EgoCorrectionEvent, EgoMeasure, EgoTrace
from ..models.emocio import ImageArtifact, VisualSceneSpec
from ..models.instinkt import BodyState, InstinktOptionRollout
from ..models.provider import (
    PositiveSeconds,
    ProviderAttemptStatus,
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderCallStatus,
    ProviderFallbackPlan,
    ProviderFallbackPolicy,
    ProviderFallbackRecord,
    ProviderFallbackStatus,
    ProviderIdentity,
    ProviderKind,
    ProviderParameter,
    ensure_call_contract,
    ensure_call_record_contract,
)


def _validate_result_lineage(
    call_spec: ProviderCallSpec,
    call: ProviderCallRecord,
    *,
    request_id: NonEmptyId,
    result_id: NonEmptyId,
    expected_kind: ProviderKind,
) -> None:
    ensure_call_record_contract(call_spec, call)
    if call_spec.provider.kind != expected_kind:
        raise ValueError("Provider result was produced by the wrong capability kind")
    if call.status not in {"succeeded", "fell_back"}:
        raise ValueError("Provider results require a successful final call outcome")
    if call.request_id != request_id:
        raise ValueError("Result and provider call must reference the same request")
    if result_id not in call.output_artifact_ids:
        raise ValueError("Provider call must list the returned artifact ID")


class TextReasoningRequest(FrozenArtifactModel):
    schema_version: Literal["rei-native-text-reasoning-request-v1"] = (
        "rei-native-text-reasoning-request-v1"
    )
    request_id: NonEmptyId
    instruction: NonEmptyText
    input_text: str
    language: LanguageCode
    evidence_ids: tuple[NonEmptyId, ...] = ()


class TextReasoningResult(FrozenArtifactModel):
    schema_version: Literal["rei-native-text-reasoning-result-v1"] = (
        "rei-native-text-reasoning-result-v1"
    )
    result_id: NonEmptyId
    request_id: NonEmptyId
    text: str
    supporting_evidence_ids: tuple[NonEmptyId, ...] = ()
    call_spec: ProviderCallSpec
    call: ProviderCallRecord

    @model_validator(mode="after")
    def validate_lineage(self) -> TextReasoningResult:
        _validate_result_lineage(
            self.call_spec,
            self.call,
            request_id=self.request_id,
            result_id=self.result_id,
            expected_kind="text_reasoner",
        )
        if not set(self.supporting_evidence_ids).issubset(
            self.call.input_artifact_ids
        ):
            raise ValueError("Text evidence must be recorded as provider call input")
        return self


class VisionLanguageRequest(FrozenArtifactModel):
    schema_version: Literal["rei-native-vlm-request-v1"] = "rei-native-vlm-request-v1"
    request_id: NonEmptyId
    artifact_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    question: NonEmptyText
    language: LanguageCode


class VisionLanguageResult(FrozenArtifactModel):
    schema_version: Literal["rei-native-vlm-result-v1"] = "rei-native-vlm-result-v1"
    result_id: NonEmptyId
    request_id: NonEmptyId
    interpretation: str
    inferred_claims: tuple[str, ...] = ()
    source_artifact_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    call_spec: ProviderCallSpec
    call: ProviderCallRecord

    @model_validator(mode="after")
    def validate_lineage(self) -> VisionLanguageResult:
        _validate_result_lineage(
            self.call_spec,
            self.call,
            request_id=self.request_id,
            result_id=self.result_id,
            expected_kind="vision_language",
        )
        if not set(self.source_artifact_ids).issubset(self.call.input_artifact_ids):
            raise ValueError("VLM source artifacts must be recorded as call inputs")
        return self


class ImageEncoding(FrozenArtifactModel):
    schema_version: Literal["rei-native-image-encoding-v1"] = (
        "rei-native-image-encoding-v1"
    )
    encoding_id: NonEmptyId
    request_id: NonEmptyId
    image_id: NonEmptyId
    vector_ref: NonEmptyText
    dimensions: int = Field(gt=0)
    call_spec: ProviderCallSpec
    call: ProviderCallRecord

    @model_validator(mode="after")
    def validate_lineage(self) -> ImageEncoding:
        _validate_result_lineage(
            self.call_spec,
            self.call,
            request_id=self.request_id,
            result_id=self.encoding_id,
            expected_kind="image_encoder",
        )
        if self.image_id not in self.call.input_artifact_ids:
            raise ValueError("Encoded image must be recorded as a call input")
        return self


class VisualWorldModelResult(FrozenArtifactModel):
    schema_version: Literal["rei-native-visual-world-result-v1"] = (
        "rei-native-visual-world-result-v1"
    )
    result_id: NonEmptyId
    request_id: NonEmptyId
    source_scene_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    predicted_scene_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    call_spec: ProviderCallSpec
    call: ProviderCallRecord

    @model_validator(mode="after")
    def validate_lineage(self) -> VisualWorldModelResult:
        _validate_result_lineage(
            self.call_spec,
            self.call,
            request_id=self.request_id,
            result_id=self.result_id,
            expected_kind="visual_world_model",
        )
        if not set(self.source_scene_ids).issubset(self.call.input_artifact_ids):
            raise ValueError("Source scenes must be recorded as call inputs")
        return self


class BodyDynamicsResult(FrozenArtifactModel):
    schema_version: Literal["rei-native-body-dynamics-result-v1"] = (
        "rei-native-body-dynamics-result-v1"
    )
    result_id: NonEmptyId
    request_id: NonEmptyId
    option_id: NonEmptyId
    initial_body_state: BodyState
    rollout: InstinktOptionRollout
    call_spec: ProviderCallSpec
    call: ProviderCallRecord

    @model_validator(mode="after")
    def validate_lineage(self) -> BodyDynamicsResult:
        _validate_result_lineage(
            self.call_spec,
            self.call,
            request_id=self.request_id,
            result_id=self.result_id,
            expected_kind="body_dynamics",
        )
        if self.rollout.option_id != self.option_id:
            raise ValueError("Body rollout must use the result option")
        if self.rollout.trajectory[0] != self.initial_body_state:
            raise ValueError("Body rollout must start from initial_body_state")
        if self.initial_body_state.body_state_id not in self.call.input_artifact_ids:
            raise ValueError("Initial body state must be recorded as a call input")
        return self


class StoredArtifact(FrozenArtifactModel):
    schema_version: Literal["rei-native-stored-artifact-v1"] = (
        "rei-native-stored-artifact-v1"
    )
    storage_id: NonEmptyId
    run_id: NonEmptyId
    relative_path: ArtifactRelativePath
    content_sha256: HashDigest
    size_bytes: int = Field(ge=0)


def validate_rendered_image(
    artifact: ImageArtifact,
    *,
    source_spec: VisualSceneSpec,
    identity: ProviderIdentity,
    call_spec: ProviderCallSpec,
    call_record: ProviderCallRecord,
    seed: int,
) -> None:
    """Bind renderer output to its source, approved call, execution, and model."""

    ensure_call_contract(
        identity,
        call_spec,
        request_id=artifact.request_id,
        expected_kind="image_renderer",
        required_input_artifact_ids=(source_spec.scene_id,),
    )
    ensure_call_record_contract(call_spec, call_record)
    if call_record.status not in {"succeeded", "fell_back"}:
        raise ValueError("Rendered images require a successful final call outcome")
    if artifact.render_call_id != call_spec.call_id:
        raise ValueError("Image artifact must reference the renderer call_id")
    if artifact.source_spec_id != source_spec.scene_id:
        raise ValueError("Image artifact must reference the rendered scene spec")
    actual_provider = (
        call_record.fallback.provider
        if call_record.fallback is not None
        else identity
    )
    actual_seed = (
        call_record.fallback.seed
        if call_record.fallback is not None
        else call_spec.seed
    )
    if actual_seed is None:
        raise ValueError("Image rendering requires an explicit seed")
    if seed != actual_seed:
        raise ValueError("Validated renderer seed differs from execution provenance")
    if artifact.provider_id != actual_provider.provider_id:
        raise ValueError("Image artifact provider differs from renderer identity")
    if artifact.input_spec_hash != source_spec.content_hash():
        raise ValueError("Image artifact input hash differs from the source spec")
    if artifact.seed != seed:
        raise ValueError("Image artifact seed differs from renderer provenance")
    if actual_provider.uses_model:
        if (
            artifact.model != actual_provider.model
            or artifact.model_revision != actual_provider.model_revision
        ):
            raise ValueError("Image artifact model differs from renderer identity")
    elif artifact.model is not None or artifact.model_revision is not None:
        raise ValueError("Non-model renderer artifacts cannot claim model provenance")
    if artifact.image_id not in call_record.output_artifact_ids:
        raise ValueError("Renderer record must list the image artifact ID")


@runtime_checkable
class TextReasoner(Protocol):
    """Provider implementations must call :func:`ensure_call_contract`."""

    @property
    def identity(self) -> ProviderIdentity: ...

    def reason(
        self,
        request: TextReasoningRequest,
        *,
        call: ProviderCallSpec,
    ) -> TextReasoningResult: ...


@runtime_checkable
class VisionLanguageInterpreter(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def interpret(
        self,
        request: VisionLanguageRequest,
        *,
        call: ProviderCallSpec,
    ) -> VisionLanguageResult: ...


@runtime_checkable
class ImageRenderer(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def render(
        self,
        spec: VisualSceneSpec,
        *,
        seed: int,
        call: ProviderCallSpec,
    ) -> ImageArtifact: ...


@runtime_checkable
class ImageEncoder(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def encode(
        self,
        image: ImageArtifact,
        *,
        call: ProviderCallSpec,
    ) -> ImageEncoding: ...


@runtime_checkable
class VisualWorldModel(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def predict(
        self,
        scenes: tuple[VisualSceneSpec, ...],
        *,
        call: ProviderCallSpec,
    ) -> VisualWorldModelResult: ...


@runtime_checkable
class BodyDynamicsModel(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def rollout(
        self,
        body_state: BodyState,
        option_id: NonEmptyId,
        *,
        call: ProviderCallSpec,
    ) -> BodyDynamicsResult: ...


@runtime_checkable
class ArtifactStore(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def write_json(
        self,
        run_id: NonEmptyId,
        relative_path: ArtifactRelativePath,
        artifact: ArtifactModel | FrozenArtifactModel,
        *,
        overwrite: bool = False,
    ) -> StoredArtifact: ...

    def write_bytes(
        self,
        run_id: NonEmptyId,
        relative_path: ArtifactRelativePath,
        content: bytes,
        *,
        overwrite: bool = False,
    ) -> StoredArtifact: ...

    def read_bytes(self, storage_id: NonEmptyId) -> bytes: ...


@runtime_checkable
class EgoTraceStore(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def append_measure(
        self,
        ego_id: NonEmptyId,
        measure: EgoMeasure,
        *,
        expected_trace_hash: HashDigest | None = None,
    ) -> None: ...

    def append_correction(
        self,
        ego_id: NonEmptyId,
        correction: EgoCorrectionEvent,
        *,
        expected_trace_hash: HashDigest | None = None,
    ) -> None: ...

    def load_trace(self, ego_id: NonEmptyId) -> EgoTrace: ...


__all__ = [
    "ArtifactStore",
    "BodyDynamicsModel",
    "BodyDynamicsResult",
    "EgoTraceStore",
    "ImageEncoder",
    "ImageEncoding",
    "ImageRenderer",
    "PositiveSeconds",
    "ProviderAttemptStatus",
    "ProviderCallRecord",
    "ProviderCallSpec",
    "ProviderCallStatus",
    "ProviderFallbackPlan",
    "ProviderFallbackPolicy",
    "ProviderFallbackRecord",
    "ProviderFallbackStatus",
    "ProviderIdentity",
    "ProviderKind",
    "ProviderParameter",
    "StoredArtifact",
    "TextReasoner",
    "TextReasoningRequest",
    "TextReasoningResult",
    "VisionLanguageInterpreter",
    "VisionLanguageRequest",
    "VisionLanguageResult",
    "VisualWorldModel",
    "VisualWorldModelResult",
    "ensure_call_contract",
    "ensure_call_record_contract",
    "validate_rendered_image",
]
