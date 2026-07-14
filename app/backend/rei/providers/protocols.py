"""Provider-neutral B2 contracts with explicit provenance and fallbacks."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    ArtifactModel,
    ArtifactRelativePath,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    SafetyNotice,
)
from ..models.ego import EgoCorrectionEvent, EgoMeasure, EgoTrace
from ..models.emocio import (
    ImageArtifact,
    ImageMediaType,
    VerifiedVisualEmbeddingArtifact,
    VisualSceneSpec,
)
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
from ..models.rendering import (
    ImagePipelineSpec,
    ImageRenderItemOutcome,
    ImageRenderMode,
    ImageRenderRequest,
)


IMAGE_ENCODER_NO_FALLBACK_REASON = (
    "Visual feature extraction fails closed; another encoder cannot silently "
    "replace the pinned visual feature space"
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


class ImageEncodingSpec(FrozenModel):
    """Exact feature extraction and canonical-vector representation contract."""

    implementation: NonEmptyText
    implementation_revision: NonEmptyText
    dimensions: int = Field(gt=0)
    pooling: Literal["cls_token"] = "cls_token"
    normalization: Literal["l2"] = "l2"
    vector_encoding: Literal["float32-little-endian"] = "float32-little-endian"
    parameters: tuple[ProviderParameter, ...] = ()

    @model_validator(mode="after")
    def validate_parameters(self) -> ImageEncodingSpec:
        names = tuple(item.name for item in self.parameters)
        if len(set(names)) != len(names):
            raise ValueError("Image encoding parameter names must be unique")
        if names != tuple(sorted(names)):
            raise ValueError("Image encoding parameters must use canonical order")
        return self


class ImageEncodingRequest(FrozenArtifactModel):
    """Content-addressed image bytes and encoder settings approved for encoding."""

    schema_version: Literal["rei-native-image-encoding-request-v1"] = (
        "rei-native-image-encoding-request-v1"
    )
    request_id: NonEmptyId
    image_id: NonEmptyId
    image_content_sha256: HashDigest
    media_type: ImageMediaType
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    provider: ProviderIdentity
    spec: ImageEncodingSpec

    @classmethod
    def create(
        cls,
        *,
        image: ImageArtifact,
        provider: ProviderIdentity,
        spec: ImageEncodingSpec,
    ) -> ImageEncodingRequest:
        payload = {
            "schema_version": "rei-native-image-encoding-request-v1",
            "image_id": image.image_id,
            "image_content_sha256": image.content_sha256,
            "media_type": image.media_type,
            "width": image.width,
            "height": image.height,
            "provider": provider,
            "spec": spec,
        }
        return cls(
            request_id=content_id("image_encoding_request", payload),
            **payload,
        )

    @property
    def provider_parameters(self) -> tuple[ProviderParameter, ...]:
        values = {
            "dimensions": self.spec.dimensions,
            "image_content_sha256": self.image_content_sha256,
            "image_height": self.height,
            "image_width": self.width,
            "normalization": self.spec.normalization,
            "pooling": self.spec.pooling,
            "spec_hash": self.spec.content_hash(),
            "vector_encoding": self.spec.vector_encoding,
        }
        parameters = [
            ProviderParameter(
                name=name,
                canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
            )
            for name, value in sorted(values.items())
        ]
        parameters.extend(
            ProviderParameter(
                name=f"runtime.{parameter.name}",
                canonical_json_value=parameter.canonical_json_value,
            )
            for parameter in self.spec.parameters
        )
        return tuple(sorted(parameters, key=lambda item: item.name))

    @model_validator(mode="after")
    def validate_request(self) -> ImageEncodingRequest:
        if self.provider.kind != "image_encoder":
            raise ValueError("Image encoding requests require an image_encoder provider")
        expected = content_id(
            "image_encoding_request",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"request_id"},
            ),
        )
        if self.request_id != expected:
            raise ValueError("Image encoding request ID differs from canonical content")
        return self

    def validate_image(self, image: ImageArtifact) -> ImageEncodingRequest:
        if (
            self.image_id != image.image_id
            or self.image_content_sha256 != image.content_sha256
            or self.media_type != image.media_type
            or self.width != image.width
            or self.height != image.height
        ):
            raise ValueError("Image encoding request differs from its source artifact")
        return self


def build_image_encoding_call_spec(
    request: ImageEncodingRequest,
    *,
    timeout_seconds: PositiveSeconds,
) -> ProviderCallSpec:
    """Build the one canonical, direct call contract for verified encoders."""

    request = ImageEncodingRequest.model_validate(
        request.model_dump(mode="python", round_trip=True)
    )
    payload = {
        "schema_version": "rei-native-provider-call-spec-v1",
        "request_id": request.request_id,
        "input_artifact_ids": (request.image_id,),
        "provider": request.provider,
        "seed": 0,
        "parameters": request.provider_parameters,
        "timeout_seconds": timeout_seconds,
        "fallback_policy": ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason=IMAGE_ENCODER_NO_FALLBACK_REASON,
        ),
        "safety_notice": SafetyNotice(),
    }
    return ProviderCallSpec(
        call_id=content_id("image_encoding_call", payload),
        **payload,
    )


class ImageEncoding(FrozenArtifactModel):
    """Historical B2 vector-reference result retained byte-for-byte as v1."""

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


class VerifiedImageEncoding(FrozenArtifactModel):
    """C4 byte-verifiable, internal-only float32 visual encoding result."""

    schema_version: Literal["rei-native-image-encoding-v2"] = (
        "rei-native-image-encoding-v2"
    )
    encoding_id: NonEmptyId
    request_id: NonEmptyId
    image_id: NonEmptyId
    request: ImageEncodingRequest
    vector_ref: ArtifactRelativePath
    vector_hash: HashDigest
    dimensions: int = Field(gt=0)
    vector_encoding: Literal["float32-little-endian"] = "float32-little-endian"
    normalization: Literal["l2"] = "l2"
    internal_only: Literal[True] = True
    external_evidence: Literal[False] = False
    semantic_interpretation: Literal["none"] = "none"
    call_spec: ProviderCallSpec
    call: ProviderCallRecord

    @staticmethod
    def derive_id(
        *,
        request: ImageEncodingRequest,
        vector_ref: str,
        vector_hash: str,
        dimensions: int,
    ) -> str:
        identity_payload = {
            "schema_version": "rei-native-image-encoding-v2",
            "request_id": request.request_id,
            "image_id": request.image_id,
            "vector_ref": vector_ref,
            "vector_hash": vector_hash,
            "dimensions": dimensions,
            "vector_encoding": request.spec.vector_encoding,
            "normalization": request.spec.normalization,
            "internal_only": True,
            "external_evidence": False,
            "semantic_interpretation": "none",
        }
        return content_id("image_encoding", identity_payload)

    @classmethod
    def create(
        cls,
        *,
        request: ImageEncodingRequest,
        vector_ref: str,
        vector_hash: str,
        dimensions: int,
        call_spec: ProviderCallSpec,
        call: ProviderCallRecord,
    ) -> VerifiedImageEncoding:
        return cls(
            encoding_id=cls.derive_id(
                request=request,
                vector_ref=vector_ref,
                vector_hash=vector_hash,
                dimensions=dimensions,
            ),
            request_id=request.request_id,
            image_id=request.image_id,
            request=request,
            vector_ref=vector_ref,
            vector_hash=vector_hash,
            dimensions=dimensions,
            vector_encoding=request.spec.vector_encoding,
            normalization=request.spec.normalization,
            call_spec=call_spec,
            call=call,
        )

    @model_validator(mode="after")
    def validate_lineage(self) -> VerifiedImageEncoding:
        validated_request = ImageEncodingRequest.model_validate(
            self.request.model_dump(mode="python", round_trip=True)
        )
        validated_call_spec = ProviderCallSpec.model_validate(
            self.call_spec.model_dump(mode="python", round_trip=True)
        )
        validated_call = ProviderCallRecord.model_validate(
            self.call.model_dump(mode="python", round_trip=True)
        )
        _validate_result_lineage(
            validated_call_spec,
            validated_call,
            request_id=self.request_id,
            result_id=self.encoding_id,
            expected_kind="image_encoder",
        )
        if self.image_id not in validated_call.input_artifact_ids:
            raise ValueError("Encoded image must be recorded as a call input")
        if self.request_id != validated_request.request_id:
            raise ValueError("Image encoding result cites another immutable request")
        if self.image_id != validated_request.image_id:
            raise ValueError("Image encoding result cites another image")
        if validated_call_spec.provider != validated_request.provider:
            raise ValueError("Image encoding request and call provider differ")
        if validated_call_spec.parameters != validated_request.provider_parameters:
            raise ValueError("Image encoding call parameters differ from its request")
        if self.dimensions != validated_request.spec.dimensions:
            raise ValueError("Image encoding dimensions differ from its request")
        if (
            self.vector_encoding != validated_request.spec.vector_encoding
            or self.normalization != validated_request.spec.normalization
        ):
            raise ValueError("Image vector representation differs from its request")
        identity_payload = self.model_dump(
            mode="python",
            round_trip=True,
            include={
                "schema_version",
                "request_id",
                "image_id",
                "vector_ref",
                "vector_hash",
                "dimensions",
                "vector_encoding",
                "normalization",
                "internal_only",
                "external_evidence",
                "semantic_interpretation",
            },
        )
        expected_id = content_id("image_encoding", identity_payload)
        if self.encoding_id != expected_id:
            raise ValueError("Image encoding ID differs from canonical vector identity")
        return self

    def to_visual_embedding(self) -> VerifiedVisualEmbeddingArtifact:
        """Project feature identity without inventing semantics or external facts."""

        validated = type(self).model_validate(
            self.model_dump(mode="python", round_trip=True)
        )
        return VerifiedVisualEmbeddingArtifact(
            source_artifact_id=validated.image_id,
            encoder_identity=validated.call.provider,
            vector_hash=validated.vector_hash,
            dimensions=validated.dimensions,
            vector_encoding=validated.vector_encoding,
            normalization=validated.normalization,
            internal_only=validated.internal_only,
            external_evidence=validated.external_evidence,
            semantic_interpretation=validated.semantic_interpretation,
        )


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
    request: ImageRenderRequest | None = None,
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
    if request is not None:
        request.validate_source_spec(source_spec)
        if request.request_id != artifact.request_id:
            raise ValueError("Image artifact belongs to another render request")
        if request.provider != call_spec.provider:
            raise ValueError("Image request provider differs from its call spec")
        if request.seed != call_spec.seed:
            raise ValueError("Image request seed differs from approved primary call")
        if request.input_artifact_ids != call_spec.input_artifact_ids:
            raise ValueError("Image request inputs differ from its approved call")
        if request.provider_parameters != call_spec.parameters:
            raise ValueError("Image request parameters differ from its approved call")
        if (
            artifact.prompt != request.prompt
            or artifact.negative_prompt != request.negative_prompt
            or artifact.width != request.width
            or artifact.height != request.height
        ):
            raise ValueError("Image artifact differs from approved prompt or dimensions")
        expected_image_id = content_id(
            "image",
            {
                "request_id": request.request_id,
                "content_sha256": artifact.content_sha256,
            },
        )
        if artifact.image_id != expected_image_id:
            raise ValueError("Image artifact ID does not match request and byte digest")


def validate_image_render_outcome(
    outcome: ImageRenderItemOutcome,
    *,
    source_spec: VisualSceneSpec,
) -> None:
    """Validate a complete B7 attempt, including structured failure records."""

    request = outcome.request.validate_source_spec(source_spec)
    ensure_call_contract(
        request.provider,
        outcome.call_spec,
        request_id=request.request_id,
        seed=request.seed,
        expected_kind="image_renderer",
        required_input_artifact_ids=request.input_artifact_ids,
    )
    ensure_call_record_contract(outcome.call_spec, outcome.call_record)
    if outcome.artifact is None:
        if outcome.call_record.status in {"succeeded", "fell_back"}:
            raise ValueError("Successful renderer outcome is missing its artifact")
        return
    validate_rendered_image(
        outcome.artifact,
        source_spec=source_spec,
        identity=request.provider,
        call_spec=outcome.call_spec,
        call_record=outcome.call_record,
        seed=outcome.artifact.seed,
        request=request,
    )


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

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec: ...

    def render(
        self,
        request: ImageRenderRequest,
        *,
        call: ProviderCallSpec,
    ) -> ImageRenderItemOutcome: ...


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
class VerifiedImageEncoder(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def encoding_spec(self) -> ImageEncodingSpec: ...

    def request_for(self, image: ImageArtifact) -> ImageEncodingRequest: ...

    def build_call_spec(
        self,
        image: ImageArtifact,
        *,
        timeout_seconds: PositiveSeconds,
    ) -> ProviderCallSpec: ...

    def encode(
        self,
        image: ImageArtifact,
        *,
        call: ProviderCallSpec,
    ) -> VerifiedImageEncoding: ...

    def read_vector(
        self,
        encoding: VerifiedImageEncoding,
    ) -> tuple[float, ...]: ...


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
    "IMAGE_ENCODER_NO_FALLBACK_REASON",
    "ImageEncoding",
    "ImageEncodingRequest",
    "ImageEncodingSpec",
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
    "VerifiedImageEncoder",
    "VerifiedImageEncoding",
    "build_image_encoding_call_spec",
    "ensure_call_contract",
    "ensure_call_record_contract",
    "validate_rendered_image",
    "validate_image_render_outcome",
]
