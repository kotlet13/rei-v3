"""Content-addressed runtime contracts for configured Emocio execution.

This module deliberately sits above the structured processor.  It freezes the
otherwise live renderer/encoder dependencies into one pre-approval artifact,
and provides a serializable envelope for the complete processing result.  It
does not execute providers or persist files; those responsibilities remain at
the provider and engine boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, TypeAdapter, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    ArtifactRelativePath,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
)
from ..models.emocio import (
    EmocioCognitionMode,
    EmocioCognitionTrace,
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioOptionValuation,
    EmocioVisualState,
    EmocioWorld,
    ImageArtifact,
)
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderIdentity,
    ProviderParameter,
    ensure_call_record_contract,
)
from ..models.rendering import ImageRenderBatchOutcome, ImageSourceReference
from ..models.scene import SceneEvent
from ..providers.protocols import (
    ImageEncodingRequest,
    ImageEncodingSpec,
    VerifiedImageEncoder,
    build_image_encoding_call_spec,
)
from .artifacts import inspect_png
from .current_first_renderer import (
    CurrentFirstEmocioRenderer,
    CurrentFirstRendererRuntimeBinding,
)
from .policy import EmocioPolicyDecision, OptionAggregateScore
from .prompting import BilingualStructuredScenePromptCompiler
from .processor import DeterministicEmocioProcessor, EmocioProcessingResult
from .renderer import (
    StructuredScenePromptCompiler,
    build_render_call_spec,
    redact_render_batch_diagnostics,
)
from .vector_encoding import (
    normalized_float32_le_bytes,
    verified_float32_le_vector,
)
from .visual_integration import (
    PinnedVisualInfluenceAuthority,
    VisualCognitionFailure,
    VisualNativeInfluenceApproval,
)
from .visual_policy_config import VisualValuationPolicyConfig
from .visual_valuation import BoundVisualEmbedding, VisualValuationResult
from .visual_world_memory import VisualWorldMemoryRecord


_PATH_ADAPTER = TypeAdapter(ArtifactRelativePath)
_HASH_ADAPTER = TypeAdapter(HashDigest)
_ID_ADAPTER = TypeAdapter(NonEmptyId)
_FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


def _parameter(name: str, value: object) -> ProviderParameter:
    return ProviderParameter(
        name=name,
        canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
    )


class EmocioProcessorRuntimeConfig(FrozenArtifactModel):
    """Exact processor dependencies approved before one outer Emocio call.

    ``structured_only`` intentionally carries no inactive rendering fields.
    Rendering modes instead close over the complete current-first binding.
    Visual cognition additionally freezes the encoder feature space, policy,
    and (when supplied) the paired approval and trust authority identities.
    """

    schema_version: Literal["rei-native-emocio-processor-runtime-config-v1"] = (
        "rei-native-emocio-processor-runtime-config-v1"
    )
    config_id: NonEmptyId
    cognition_mode: EmocioCognitionMode
    render_seed: int | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    encoding_timeout_seconds: float | None = Field(
        default=None,
        gt=0.0,
        allow_inf_nan=False,
        exclude_if=lambda value: value is None,
    )
    renderer_binding: CurrentFirstRendererRuntimeBinding | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    encoder_identity: ProviderIdentity | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    encoder_spec: ImageEncodingSpec | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_policy_config_id: NonEmptyId | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_policy_config_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_approval_id: NonEmptyId | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_approval_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_authority_id: NonEmptyId | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_authority_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @classmethod
    def from_processor(
        cls,
        processor: DeterministicEmocioProcessor,
    ) -> EmocioProcessorRuntimeConfig:
        """Freeze one processor instance, rejecting ambiguous live dependencies."""

        if type(processor) is not DeterministicEmocioProcessor:
            raise TypeError(
                "Emocio runtime configuration requires the exact "
                "DeterministicEmocioProcessor"
            )
        mode: EmocioCognitionMode = processor.cognition_mode or (
            "render_observe" if processor.renderer is not None else "structured_only"
        )
        payload: dict[str, object] = {
            "schema_version": "rei-native-emocio-processor-runtime-config-v1",
            "cognition_mode": mode,
        }

        visual_dependencies = (
            processor.image_encoder,
            processor.visual_policy_config,
            processor.visual_influence_approval,
            processor.visual_influence_authority,
        )
        if mode == "structured_only":
            if processor.renderer is not None or any(
                item is not None for item in visual_dependencies
            ):
                raise ValueError(
                    "structured_only processor cannot carry rendering or visual "
                    "cognition dependencies"
                )
            return cls._from_payload(payload)

        renderer = processor.renderer
        if type(renderer) is not CurrentFirstEmocioRenderer:
            raise ValueError(
                "Rendering cognition requires the exact current-first renderer"
            )
        try:
            binding_value = renderer.runtime_binding()
            renderer_binding = CurrentFirstRendererRuntimeBinding.model_validate(
                binding_value.model_dump(mode="python", round_trip=True)
            )
        except Exception as exc:
            raise ValueError(
                "Current-first renderer runtime binding failed closed"
            ) from exc
        payload.update(
            render_seed=processor.render_seed,
            renderer_binding=renderer_binding,
        )

        if mode == "render_observe":
            if any(item is not None for item in visual_dependencies):
                raise ValueError(
                    "render_observe processor cannot carry encoder, policy, approval "
                    "or authority dependencies"
                )
            return cls._from_payload(payload)

        encoder = processor.image_encoder
        if encoder is None or not isinstance(encoder, VerifiedImageEncoder):
            raise ValueError(
                "visual_cognition requires an exact verified image encoder"
            )
        try:
            encoder_identity = ProviderIdentity.model_validate(
                encoder.identity.model_dump(mode="python", round_trip=True)
            )
            encoder_spec = ImageEncodingSpec.model_validate(
                encoder.encoding_spec().model_dump(mode="python", round_trip=True)
            )
        except Exception as exc:
            raise ValueError(
                "Visual encoder identity or encoding spec failed closed"
            ) from exc
        if encoder_identity.kind != "image_encoder":
            raise ValueError("Visual cognition encoder must be an image_encoder")

        policy_value = processor.visual_policy_config
        if policy_value is None:
            raise ValueError(
                "visual_cognition requires a content-addressed visual policy config"
            )
        try:
            policy = VisualValuationPolicyConfig.model_validate(
                policy_value.model_dump(mode="python", round_trip=True)
            )
        except Exception as exc:
            raise ValueError("Visual policy config failed closed") from exc

        approval_value = processor.visual_influence_approval
        authority_value = processor.visual_influence_authority
        if (approval_value is None) != (authority_value is None):
            raise ValueError(
                "Visual influence approval and authority must be supplied together"
            )

        payload.update(
            encoding_timeout_seconds=processor.encoding_timeout_seconds,
            encoder_identity=encoder_identity,
            encoder_spec=encoder_spec,
            visual_policy_config_id=policy.config_id,
            visual_policy_config_hash=policy.content_hash(),
        )
        if approval_value is not None and authority_value is not None:
            try:
                approval = VisualNativeInfluenceApproval.model_validate(
                    approval_value.model_dump(mode="python", round_trip=True)
                )
                authority = PinnedVisualInfluenceAuthority.model_validate(
                    authority_value.model_dump(mode="python", round_trip=True)
                )
            except Exception as exc:
                raise ValueError(
                    "Visual influence approval or authority failed closed"
                ) from exc
            payload.update(
                visual_influence_approval_id=approval.approval_id,
                visual_influence_approval_hash=approval.content_hash(),
                visual_influence_authority_id=authority.authority_id,
                visual_influence_authority_hash=authority.content_hash(),
            )
        return cls._from_payload(payload)

    @classmethod
    def _from_payload(
        cls,
        payload: dict[str, object],
    ) -> EmocioProcessorRuntimeConfig:
        return cls(
            config_id=content_id("emocio_processor_runtime", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_runtime_config(self) -> Self:
        renderer_present = self.renderer_binding is not None
        encoder_pair = (self.encoder_identity, self.encoder_spec)
        policy_pair = (
            self.visual_policy_config_id,
            self.visual_policy_config_hash,
        )
        approval_pair = (
            self.visual_influence_approval_id,
            self.visual_influence_approval_hash,
        )
        authority_pair = (
            self.visual_influence_authority_id,
            self.visual_influence_authority_hash,
        )
        for label, pair in (
            ("encoder", encoder_pair),
            ("visual policy", policy_pair),
            ("visual approval", approval_pair),
            ("visual authority", authority_pair),
        ):
            if any(item is not None for item in pair) != all(
                item is not None for item in pair
            ):
                raise ValueError(f"Emocio runtime {label} lineage must be paired")
        if any(item is not None for item in approval_pair) != any(
            item is not None for item in authority_pair
        ):
            raise ValueError(
                "Visual influence approval and authority lineage must be paired"
            )

        if self.cognition_mode == "structured_only":
            if (
                self.render_seed is not None
                or self.encoding_timeout_seconds is not None
                or renderer_present
                or any(item is not None for item in (*encoder_pair, *policy_pair))
                or any(item is not None for item in (*approval_pair, *authority_pair))
            ):
                raise ValueError(
                    "structured_only runtime must exclude all inactive dependencies"
                )
        elif self.cognition_mode == "render_observe":
            if self.render_seed is None or not renderer_present:
                raise ValueError(
                    "render_observe runtime requires renderer binding and seed"
                )
            if (
                self.encoding_timeout_seconds is not None
                or any(item is not None for item in (*encoder_pair, *policy_pair))
                or any(item is not None for item in (*approval_pair, *authority_pair))
            ):
                raise ValueError(
                    "render_observe runtime cannot carry visual cognition dependencies"
                )
        else:
            if (
                self.render_seed is None
                or self.encoding_timeout_seconds is None
                or not renderer_present
                or not all(item is not None for item in encoder_pair)
                or not all(item is not None for item in policy_pair)
            ):
                raise ValueError(
                    "visual_cognition runtime requires renderer, seed, encoder, "
                    "timeout and policy"
                )
            assert self.encoder_identity is not None
            if self.encoder_identity.kind != "image_encoder":
                raise ValueError(
                    "visual_cognition runtime requires an image_encoder identity"
                )

        expected_id = content_id(
            "emocio_processor_runtime",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"config_id"},
            ),
        )
        if self.config_id != expected_id:
            raise ValueError(
                "Emocio processor runtime config ID differs from canonical content"
            )
        return self

    @property
    def provider_parameters(self) -> tuple[ProviderParameter, ...]:
        """Canonical outer-call parameters, including explicit absent bindings."""

        values: dict[str, object] = {
            "emocio.cognition_mode": self.cognition_mode,
            "emocio.encoding_timeout_seconds": self.encoding_timeout_seconds,
            "emocio.encoder_provider_id": (
                None
                if self.encoder_identity is None
                else self.encoder_identity.provider_id
            ),
            "emocio.encoder_spec_hash": (
                None if self.encoder_spec is None else self.encoder_spec.content_hash()
            ),
            "emocio.processor_runtime_config_hash": self.content_hash(),
            "emocio.processor_runtime_config_id": self.config_id,
            "emocio.render_seed": self.render_seed,
            "emocio.renderer_binding_hash": (
                None
                if self.renderer_binding is None
                else self.renderer_binding.content_hash()
            ),
            "emocio.renderer_binding_id": (
                None
                if self.renderer_binding is None
                else self.renderer_binding.binding_id
            ),
            "emocio.visual_influence_approval_hash": (
                self.visual_influence_approval_hash
            ),
            "emocio.visual_influence_approval_id": (
                self.visual_influence_approval_id
            ),
            "emocio.visual_influence_authority_hash": (
                self.visual_influence_authority_hash
            ),
            "emocio.visual_influence_authority_id": (
                self.visual_influence_authority_id
            ),
            "emocio.visual_policy_config_hash": self.visual_policy_config_hash,
            "emocio.visual_policy_config_id": self.visual_policy_config_id,
        }
        return tuple(
            _parameter(name, value) for name, value in sorted(values.items())
        )

    @property
    def outer_call_parameters(self) -> tuple[ProviderParameter, ...]:
        """Explicit alias used by native provider adapters."""

        return self.provider_parameters

    @property
    def input_artifact_ids(self) -> tuple[NonEmptyId, ...]:
        """Content-addressed configuration artifacts admitted by the outer call."""

        values = [self.config_id]
        if self.renderer_binding is not None:
            values.append(self.renderer_binding.binding_id)
        for value in (
            self.visual_policy_config_id,
            self.visual_influence_approval_id,
            self.visual_influence_authority_id,
        ):
            if value is not None:
                values.append(value)
        if len(set(values)) != len(values):
            raise ValueError("Emocio runtime input artifact IDs must be unique")
        return tuple(sorted(values))

    @property
    def outer_call_input_artifact_ids(self) -> tuple[NonEmptyId, ...]:
        """Explicit alias used by native provider adapters."""

        return self.input_artifact_ids

    def outer_timeout_seconds_for(self, *, scene_count: int) -> float:
        """Return the closed aggregate budget for one configured outer call.

        The outer provider performs the deterministic processing envelope in
        addition to every approved render and encoding attempt.  Its timeout
        therefore cannot reuse one nested timeout: it must cover the complete
        scene fan-out plus a fixed processor/replay allowance.
        """

        if type(scene_count) is not int or scene_count <= 0:
            raise ValueError("Emocio outer timeout requires a positive scene count")
        processor_allowance = 30.0
        if self.renderer_binding is None:
            return processor_allowance
        timeout = (
            processor_allowance
            + self.renderer_binding.render_settings.timeout_seconds * scene_count
        )
        if self.encoding_timeout_seconds is not None:
            timeout += self.encoding_timeout_seconds * scene_count
        return float(timeout)


class _OptionAggregateScoreArtifact(FrozenModel):
    option_id: NonEmptyId
    score: _FiniteFloat


class _EmocioPolicyDecisionArtifact(FrozenModel):
    selected: EmocioOptionValuation | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    aggregate_scores: tuple[_OptionAggregateScoreArtifact, ...] = ()
    tied_option_ids: tuple[NonEmptyId, ...] = ()

    @classmethod
    def from_decision(
        cls,
        decision: EmocioPolicyDecision,
    ) -> _EmocioPolicyDecisionArtifact:
        if not isinstance(decision, EmocioPolicyDecision):
            raise TypeError("Emocio processing policy must be EmocioPolicyDecision")
        return cls(
            selected=decision.selected,
            aggregate_scores=tuple(
                _OptionAggregateScoreArtifact(
                    option_id=item.option_id,
                    score=item.score,
                )
                for item in decision.aggregate_scores
            ),
            tied_option_ids=decision.tied_option_ids,
        )

    @model_validator(mode="after")
    def validate_policy_shape(self) -> Self:
        score_ids = tuple(item.option_id for item in self.aggregate_scores)
        if len(set(score_ids)) != len(score_ids):
            raise ValueError("Emocio policy aggregate option IDs must be unique")
        if len(set(self.tied_option_ids)) != len(self.tied_option_ids):
            raise ValueError("Emocio policy tied option IDs must be unique")
        if not set(self.tied_option_ids).issubset(score_ids):
            raise ValueError("Emocio policy tie cites an unscored option")
        if self.selected is not None and self.selected.option_id not in score_ids:
            raise ValueError("Emocio policy selection must have an aggregate score")
        if self.selected is not None and self.tied_option_ids:
            raise ValueError("Emocio policy cannot select through an explicit tie")
        return self

    def to_decision(self) -> EmocioPolicyDecision:
        return EmocioPolicyDecision(
            selected=self.selected,
            aggregate_scores=tuple(
                OptionAggregateScore(
                    option_id=item.option_id,
                    score=item.score,
                )
                for item in self.aggregate_scores
            ),
            tied_option_ids=self.tied_option_ids,
        )


class EmocioProcessingArtifact(FrozenArtifactModel):
    """Canonical, replayable envelope for one complete processing result."""

    schema_version: Literal["rei-native-emocio-processing-result-v1"] = (
        "rei-native-emocio-processing-result-v1"
    )
    result_id: NonEmptyId
    source_scene_hash: HashDigest
    source_world_id: NonEmptyId
    source_world_hash: HashDigest
    packet: EmocioInputPacket
    visual_state: EmocioVisualState
    structured_native_conclusion: EmocioNativeConclusion
    native_conclusion: EmocioNativeConclusion
    policy: _EmocioPolicyDecisionArtifact
    cognition_trace: EmocioCognitionTrace
    rendered_images: tuple[ImageArtifact, ...] = ()
    render_batch: ImageRenderBatchOutcome | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    render_seed: int | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    renderer_warning: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_policy_config: VisualValuationPolicyConfig | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_observations: tuple[BoundVisualEmbedding, ...] = ()
    visual_valuation: VisualValuationResult | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_memories: tuple[VisualWorldMemoryRecord, ...] = ()
    visual_influence_approval: VisualNativeInfluenceApproval | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_authority: PinnedVisualInfluenceAuthority | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_failure: VisualCognitionFailure | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_warning: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    stage_order: tuple[NonEmptyText, ...]

    @classmethod
    def create(cls, result: EmocioProcessingResult) -> EmocioProcessingArtifact:
        if not isinstance(result, EmocioProcessingResult):
            raise TypeError(
                "Emocio processing artifact requires EmocioProcessingResult"
            )
        payload = {
            "schema_version": "rei-native-emocio-processing-result-v1",
            "source_scene_hash": result.source_scene_hash,
            "source_world_id": result.source_world_id,
            "source_world_hash": result.source_world_hash,
            "packet": result.packet,
            "visual_state": result.visual_state,
            "structured_native_conclusion": result.structured_native_conclusion,
            "native_conclusion": result.native_conclusion,
            "policy": _EmocioPolicyDecisionArtifact.from_decision(result.policy),
            "cognition_trace": result.cognition_trace,
            "rendered_images": result.rendered_images,
            "render_batch": result.render_batch,
            "render_seed": result.render_seed,
            "renderer_warning": result.renderer_warning,
            "visual_policy_config": result.visual_policy_config,
            "visual_observations": result.visual_observations,
            "visual_valuation": result.visual_valuation,
            "visual_memories": result.visual_memories,
            "visual_influence_approval": result.visual_influence_approval,
            "visual_influence_authority": result.visual_influence_authority,
            "visual_failure": result.visual_failure,
            "visual_warning": result.visual_warning,
            "stage_order": result.stage_order,
        }
        candidate = cls.model_construct(
            result_id="emocio_processing_result_pending",
            **payload,
        )
        identity_payload = candidate.model_dump(
            mode="python",
            round_trip=True,
            exclude={"result_id"},
        )
        return cls(
            result_id=content_id("emocio_processing_result", identity_payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_result_id(self) -> Self:
        expected_id = content_id(
            "emocio_processing_result",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"result_id"},
            ),
        )
        if self.result_id != expected_id:
            raise ValueError(
                "Emocio processing result ID differs from canonical content"
            )
        return self

    def to_result(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
    ) -> EmocioProcessingResult:
        """Rebuild the historical dataclass and execute its exact replay checks."""

        validated = type(self).model_validate(
            self.model_dump(mode="python", round_trip=True)
        )
        result = EmocioProcessingResult(
            source_scene_hash=validated.source_scene_hash,
            source_world_id=validated.source_world_id,
            source_world_hash=validated.source_world_hash,
            packet=validated.packet,
            visual_state=validated.visual_state,
            structured_native_conclusion=validated.structured_native_conclusion,
            native_conclusion=validated.native_conclusion,
            policy=validated.policy.to_decision(),
            cognition_trace=validated.cognition_trace,
            rendered_images=validated.rendered_images,
            render_batch=validated.render_batch,
            render_seed=validated.render_seed,
            renderer_warning=validated.renderer_warning,
            visual_policy_config=validated.visual_policy_config,
            visual_observations=validated.visual_observations,
            visual_valuation=validated.visual_valuation,
            visual_memories=validated.visual_memories,
            visual_influence_approval=validated.visual_influence_approval,
            visual_influence_authority=validated.visual_influence_authority,
            visual_failure=validated.visual_failure,
            visual_warning=validated.visual_warning,
            stage_order=validated.stage_order,
        )
        result.validate_against(scene, world)
        return result


@dataclass(frozen=True, slots=True)
class EmocioBinarySnapshot:
    """Verified ephemeral bytes handed from a provider to engine persistence."""

    artifact_id: str
    role: Literal["image", "vector"]
    relative_path: str
    content_sha256: str
    content: bytes
    dimensions: int | None = None
    width: int | None = None
    height: int | None = None

    def __post_init__(self) -> None:
        artifact_id = _ID_ADAPTER.validate_python(self.artifact_id, strict=True)
        relative_path = _PATH_ADAPTER.validate_python(
            self.relative_path,
            strict=True,
        )
        digest = _HASH_ADAPTER.validate_python(
            self.content_sha256,
            strict=True,
        )
        if type(self.content) is not bytes or not self.content:
            raise ValueError("Emocio binary snapshot content must be non-empty bytes")
        if hashlib.sha256(self.content).hexdigest() != digest:
            raise ValueError("Emocio binary snapshot SHA-256 differs from its bytes")

        if self.role == "image":
            if (
                len(relative_path.split("/")) != 3
                or not relative_path.startswith("emocio/images/")
                or not relative_path.endswith(".png")
                or relative_path.endswith("/.png")
                or self.dimensions is not None
                or self.width is None
                or self.height is None
                or self.width <= 0
                or self.height <= 0
            ):
                raise ValueError(
                    "Image snapshot requires positive width/height and no dimensions"
                )
            if inspect_png(self.content) != (self.width, self.height):
                raise ValueError("Image snapshot dimensions differ from its PNG bytes")
        elif self.role == "vector":
            if (
                len(relative_path.split("/")) != 3
                or not relative_path.startswith("emocio/embeddings/")
                or not relative_path.endswith(".f32")
                or relative_path.endswith("/.f32")
                or self.dimensions is None
                or self.dimensions <= 0
                or self.width is not None
                or self.height is not None
                or len(self.content) != self.dimensions * 4
            ):
                raise ValueError(
                    "Vector snapshot requires exact float32 dimensions and no image size"
                )
            _, vector_digest = verified_float32_le_vector(
                self.content,
                expected_dimensions=self.dimensions,
            )
            if vector_digest != digest:
                raise ValueError(
                    "Vector snapshot hash differs from canonical float32 bytes"
                )
        else:
            raise ValueError("Unknown Emocio binary snapshot role")

        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "relative_path", relative_path)
        object.__setattr__(self, "content_sha256", digest)


def binary_snapshots_from_processing(
    result: EmocioProcessingResult,
    processor: DeterministicEmocioProcessor,
) -> tuple[EmocioBinarySnapshot, ...]:
    """Materialize exact image/vector bytes without touching run persistence."""

    if not isinstance(result, EmocioProcessingResult):
        raise TypeError("Binary snapshots require EmocioProcessingResult")
    config = EmocioProcessorRuntimeConfig.from_processor(processor)
    if result.cognition_trace.requested_mode != config.cognition_mode:
        raise ValueError(
            "Processing result mode differs from its processor runtime config"
        )
    if config.cognition_mode == "structured_only":
        if result.rendered_images or result.visual_observations:
            raise ValueError("structured_only result cannot publish binary artifacts")
        return ()

    renderer = processor.renderer
    reader = getattr(renderer, "read_artifact_bytes", None)
    if not callable(reader):
        raise ValueError(
            "Configured renderer cannot return verified image artifact bytes"
        )

    path_contents: dict[str, EmocioBinarySnapshot] = {}
    snapshots_by_artifact_id: dict[str, EmocioBinarySnapshot] = {}

    def admit(snapshot: EmocioBinarySnapshot) -> None:
        previous_path = path_contents.get(snapshot.relative_path)
        if previous_path is not None and (
            previous_path.content_sha256 != snapshot.content_sha256
            or previous_path.content != snapshot.content
            or previous_path.role != snapshot.role
            or previous_path.dimensions != snapshot.dimensions
            or previous_path.width != snapshot.width
            or previous_path.height != snapshot.height
        ):
            raise ValueError(
                "Emocio binary artifact path maps to conflicting content"
            )
        path_contents.setdefault(snapshot.relative_path, snapshot)

        previous_artifact = snapshots_by_artifact_id.get(snapshot.artifact_id)
        if previous_artifact is not None:
            if previous_artifact != snapshot:
                raise ValueError(
                    "Emocio binary artifact ID maps to conflicting content"
                )
            return
        # Preserve every logical output even when several encodings safely alias
        # the same immutable vector path/hash. Persistence may deduplicate bytes
        # by path, while the manifest retains every encoding artifact ID.
        snapshots_by_artifact_id[snapshot.artifact_id] = snapshot

    for image in result.rendered_images:
        try:
            content = reader(image)
        except Exception as exc:
            raise ValueError(
                "Renderer image artifact bytes failed closed"
            ) from exc
        admit(
            EmocioBinarySnapshot(
                artifact_id=image.image_id,
                role="image",
                relative_path=image.path,
                content_sha256=image.content_sha256,
                content=content,
                width=image.width,
                height=image.height,
            )
        )

    for observation in result.visual_observations:
        encoding = observation.encoding
        content = normalized_float32_le_bytes(
            observation.vector,
            expected_dimensions=encoding.dimensions,
        )
        if hashlib.sha256(content).hexdigest() != encoding.vector_hash:
            raise ValueError(
                "Visual observation vector bytes differ from encoding provenance"
            )
        admit(
            EmocioBinarySnapshot(
                artifact_id=encoding.encoding_id,
                role="vector",
                relative_path=encoding.vector_ref,
                content_sha256=encoding.vector_hash,
                content=content,
                dimensions=encoding.dimensions,
            )
        )

    return tuple(
        sorted(
            snapshots_by_artifact_id.values(),
            key=lambda item: (item.relative_path, item.artifact_id),
        )
    )


def nested_provider_calls(
    result: EmocioProcessingResult,
) -> tuple[
    tuple[ProviderCallSpec, ...],
    tuple[ProviderCallRecord, ...],
    tuple[NonEmptyId, ...],
    tuple[NonEmptyId, ...],
]:
    """Flatten exact renderer/encoder attempts in deterministic process order."""

    if not isinstance(result, EmocioProcessingResult):
        raise TypeError("Nested provider calls require EmocioProcessingResult")

    ordered: list[tuple[ProviderCallSpec, ProviderCallRecord, str]] = []
    renderer_call_ids: list[NonEmptyId] = []
    encoder_call_ids: list[NonEmptyId] = []

    if result.render_batch is not None:
        item_by_scene_id = {
            item.request.source_spec_id: item for item in result.render_batch.items
        }
        if len(item_by_scene_id) != len(result.render_batch.items):
            raise ValueError("Render batch contains duplicate scene attempts")
        for scene_id in result.render_batch.source_spec_ids:
            item = item_by_scene_id.get(scene_id)
            if item is None:
                continue
            ordered.append((item.call_spec, item.call_record, "renderer"))
            renderer_call_ids.append(item.call_spec.call_id)

    for observation in result.visual_observations:
        ordered.append(
            (
                observation.encoding.call_spec,
                observation.encoding.call,
                "encoder",
            )
        )
        encoder_call_ids.append(observation.encoding.call_spec.call_id)

    failure = result.visual_failure
    if failure is not None and failure.stage == "encoding":
        failed_spec = failure.attempted_call_spec
        failed_record = getattr(failure, "attempted_call_record", None)
        if (failed_spec is None) != (failed_record is None):
            raise ValueError(
                "Failed visual encoding must close its call spec and record together"
            )
        if failed_spec is not None and failed_record is not None:
            failed_record = ProviderCallRecord.model_validate(
                failed_record.model_dump(mode="python", round_trip=True)
            )
            ordered.append((failed_spec, failed_record, "encoder"))
            encoder_call_ids.append(failed_spec.call_id)

    specs: list[ProviderCallSpec] = []
    records: list[ProviderCallRecord] = []
    seen: dict[str, tuple[bytes, bytes]] = {}
    for raw_spec, raw_record, role in ordered:
        spec = ProviderCallSpec.model_validate(
            raw_spec.model_dump(mode="python", round_trip=True)
        )
        record = ProviderCallRecord.model_validate(
            raw_record.model_dump(mode="python", round_trip=True)
        )
        ensure_call_record_contract(spec, record)
        expected_kind = "image_renderer" if role == "renderer" else "image_encoder"
        if spec.provider.kind != expected_kind:
            raise ValueError(
                f"Nested {role} call uses another provider capability"
            )
        pair_bytes = (spec.canonical_json_bytes(), record.canonical_json_bytes())
        previous = seen.get(spec.call_id)
        if previous is not None:
            if previous != pair_bytes:
                raise ValueError(
                    "Nested provider call ID maps to conflicting canonical bytes"
                )
            raise ValueError("Nested provider call ID is duplicated")
        seen[spec.call_id] = pair_bytes
        specs.append(spec)
        records.append(record)

    if len(set(renderer_call_ids)) != len(renderer_call_ids):
        raise ValueError("Renderer call IDs must be unique")
    if len(set(encoder_call_ids)) != len(encoder_call_ids):
        raise ValueError("Encoder call IDs must be unique")
    if set(renderer_call_ids).intersection(encoder_call_ids):
        raise ValueError("Renderer and encoder call IDs must be disjoint")
    return (
        tuple(specs),
        tuple(records),
        tuple(renderer_call_ids),
        tuple(encoder_call_ids),
    )


def validate_processing_runtime_closure(
    config: EmocioProcessorRuntimeConfig,
    result: EmocioProcessingResult,
) -> tuple[
    tuple[ProviderCallSpec, ...],
    tuple[ProviderCallRecord, ...],
    tuple[NonEmptyId, ...],
    tuple[NonEmptyId, ...],
]:
    """Bind a replayed result to every dependency frozen in its runtime config."""

    config = EmocioProcessorRuntimeConfig.model_validate(
        config.model_dump(mode="python", round_trip=True)
    )
    if not isinstance(result, EmocioProcessingResult):
        raise TypeError("Runtime closure requires EmocioProcessingResult")
    if result.cognition_trace.requested_mode != config.cognition_mode:
        raise ValueError("Configured Emocio cognition mode differs from replay")
    if result.render_seed != config.render_seed:
        raise ValueError("Configured Emocio render seed differs from replay")
    if result.render_batch is not None and (
        result.render_batch.root_seed != config.render_seed
    ):
        raise ValueError("Emocio render batch seed differs from its config")

    nested = nested_provider_calls(result)
    nested_specs, _, _, _ = nested
    renderer_specs = tuple(
        spec for spec in nested_specs if spec.provider.kind == "image_renderer"
    )
    renderer_binding = config.renderer_binding
    if renderer_binding is None:
        if renderer_specs or result.render_batch is not None or result.rendered_images:
            raise ValueError("Unconfigured renderer appears in Emocio replay")
    else:
        if any(
            spec.provider != renderer_binding.provider_identity
            for spec in renderer_specs
        ):
            raise ValueError("Renderer identity differs from runtime binding")
        if result.render_batch is None and result.rendered_images:
            raise ValueError(
                "Configured renderer cannot publish images without a render batch"
            )
        if result.render_batch is not None:
            if (
                redact_render_batch_diagnostics(result.render_batch)
                != result.render_batch
            ):
                raise ValueError("Renderer diagnostics are not canonically redacted")
            settings = renderer_binding.render_settings
            rollout = renderer_binding.rollout_config
            scene_by_id = {
                item.scene_id: item
                for item in (
                    result.visual_state.current_scene,
                    result.visual_state.desired_scene,
                    result.visual_state.broken_scene,
                    *result.visual_state.option_rollouts,
                )
            }
            current_images = tuple(
                image
                for image in result.rendered_images
                if image.source_spec_id
                == result.visual_state.current_scene.scene_id
            )
            for item in result.render_batch.items:
                request = item.request
                source_scene = scene_by_id.get(request.source_spec_id)
                if source_scene is None:
                    raise ValueError("Render request cites an absent visual scene")
                expected_mode = (
                    "image_to_image"
                    if source_scene.scene_kind == "option_rollout"
                    else "text_to_image"
                )
                expected_pipeline = (
                    renderer_binding.text_to_image_pipeline
                    if expected_mode == "text_to_image"
                    else renderer_binding.image_to_image_pipeline
                )
                if (
                    request.mode != expected_mode
                    or request.provider != renderer_binding.provider_identity
                    or request.pipeline != expected_pipeline
                    or request.width != settings.width
                    or request.height != settings.height
                    or request.num_inference_steps
                    != settings.num_inference_steps
                    or request.guidance_scale != settings.guidance_scale
                    or request.negative_prompt != settings.negative_prompt
                    or item.call_spec
                    != build_render_call_spec(
                        request,
                        timeout_seconds=settings.timeout_seconds,
                    )
                    or item.call_record.fallback is not None
                ):
                    raise ValueError("Render call differs from runtime binding")
                if request.mode == "image_to_image":
                    if len(current_images) != 1:
                        raise ValueError("Rollout requires one exact current image")
                    expected_source = (
                        ImageSourceReference.from_artifact_with_scene_lineage(
                            current_images[0]
                        )
                    )
                    if (
                        request.source_image != expected_source
                        or request.conditioning_method
                        != rollout.conditioning_method
                        or request.strength != rollout.classic_strength
                    ):
                        raise ValueError(
                            "Rollout request differs from runtime binding"
                        )
                compiler = renderer_binding.prompt_compiler_binding
                profile = compiler.prompt_profile
                if profile is None:
                    prompt_compiler = StructuredScenePromptCompiler()
                    provenance_matches = (
                        request.prompt_language is None
                        and request.style_id is None
                        and request.profile_hash is None
                    )
                else:
                    prompt_compiler = BilingualStructuredScenePromptCompiler(profile)
                    provenance_matches = (
                        request.prompt_language == profile.language
                        and request.style_id == profile.style_id
                        and request.profile_hash == profile.content_hash()
                    )
                if (
                    not provenance_matches
                    or request.prompt != prompt_compiler.compile(source_scene)
                ):
                    raise ValueError("Render prompt differs from runtime binding")

    encoder_specs = tuple(
        spec for spec in nested_specs if spec.provider.kind == "image_encoder"
    )
    if config.encoder_identity is None:
        failure_spec = (
            None
            if result.visual_failure is None
            else result.visual_failure.attempted_call_spec
        )
        if encoder_specs or result.visual_observations or failure_spec is not None:
            raise ValueError("Unconfigured encoder appears in Emocio replay")
    else:
        if config.encoder_spec is None or config.encoding_timeout_seconds is None:
            raise ValueError("Configured encoder closure is incomplete")
        if any(
            spec.provider != config.encoder_identity for spec in encoder_specs
        ):
            raise ValueError("Encoder identity differs from runtime config")
        for observation in result.visual_observations:
            encoding = observation.encoding
            if (
                encoding.request.provider != config.encoder_identity
                or encoding.request.spec != config.encoder_spec
                or encoding.call_spec
                != build_image_encoding_call_spec(
                    encoding.request,
                    timeout_seconds=config.encoding_timeout_seconds,
                )
                or encoding.call.fallback is not None
                or encoding.call.warnings
            ):
                raise ValueError("Visual encoding differs from runtime config")
        failure = result.visual_failure
        if failure is not None and failure.stage == "encoding":
            failed_spec = failure.attempted_call_spec
            if failed_spec is not None:
                referenced_images = tuple(
                    image
                    for image in result.rendered_images
                    if image.image_id in failed_spec.input_artifact_ids
                )
                if len(referenced_images) != 1:
                    raise ValueError(
                        "Failed encoding must cite one rendered image"
                    )
                expected_request = ImageEncodingRequest.create(
                    image=referenced_images[0],
                    provider=config.encoder_identity,
                    spec=config.encoder_spec,
                )
                if failed_spec != build_image_encoding_call_spec(
                    expected_request,
                    timeout_seconds=config.encoding_timeout_seconds,
                ):
                    raise ValueError(
                        "Failed encoding call differs from runtime config"
                    )

    policy_stage_reached = "visual_encoding" in result.stage_order
    if config.visual_policy_config_id is None:
        if result.visual_policy_config is not None:
            raise ValueError("Unconfigured visual policy appears in replay")
    elif policy_stage_reached:
        if (
            result.visual_policy_config is None
            or result.visual_policy_config.config_id
            != config.visual_policy_config_id
            or result.visual_policy_config.content_hash()
            != config.visual_policy_config_hash
        ):
            raise ValueError("Visual policy differs from runtime config")
    elif result.visual_policy_config is not None:
        raise ValueError("Visual policy appears before its processing stage")

    approval_stage_reached = "visual_approval" in result.stage_order
    for value, expected_id, expected_hash, label in (
        (
            result.visual_influence_approval,
            config.visual_influence_approval_id,
            config.visual_influence_approval_hash,
            "approval",
        ),
        (
            result.visual_influence_authority,
            config.visual_influence_authority_id,
            config.visual_influence_authority_hash,
            "authority",
        ),
    ):
        if expected_id is None:
            if value is not None:
                raise ValueError(
                    f"Unconfigured visual influence {label} appears in replay"
                )
        elif approval_stage_reached:
            if (
                value is None
                or getattr(value, f"{label}_id") != expected_id
                or value.content_hash() != expected_hash
            ):
                raise ValueError(
                    f"Visual influence {label} differs from runtime config"
                )
        elif value is not None:
            raise ValueError(
                f"Visual influence {label} appears before approval stage"
            )
    return nested


def validate_binary_snapshots_against_processing(
    result: EmocioProcessingResult,
    snapshots: tuple[EmocioBinarySnapshot, ...],
) -> None:
    """Require exact metadata and bytes for every replayed binary output."""

    if not isinstance(result, EmocioProcessingResult):
        raise TypeError("Binary closure requires EmocioProcessingResult")
    if type(snapshots) is not tuple or any(
        type(snapshot) is not EmocioBinarySnapshot for snapshot in snapshots
    ):
        raise TypeError("Binary closure requires exact EmocioBinarySnapshot values")
    if tuple(
        (item.relative_path, item.artifact_id) for item in snapshots
    ) != tuple(
        sorted((item.relative_path, item.artifact_id) for item in snapshots)
    ):
        raise ValueError("Emocio binary snapshots must use canonical order")
    if len({item.artifact_id for item in snapshots}) != len(snapshots):
        raise ValueError("Emocio binary snapshot artifact IDs must be unique")

    expected: dict[str, tuple[object, ...]] = {}
    for image in result.rendered_images:
        expected[image.image_id] = (
            "image",
            image.path,
            image.content_sha256,
            None,
            image.width,
            image.height,
            None,
        )
    for observation in result.visual_observations:
        encoding = observation.encoding
        vector_bytes = normalized_float32_le_bytes(
            observation.vector,
            expected_dimensions=encoding.dimensions,
        )
        expected[encoding.encoding_id] = (
            "vector",
            encoding.vector_ref,
            encoding.vector_hash,
            encoding.dimensions,
            None,
            None,
            vector_bytes,
        )
    if {item.artifact_id for item in snapshots} != set(expected):
        raise ValueError("Emocio binary snapshots differ from processing outputs")

    paths: dict[str, EmocioBinarySnapshot] = {}
    for snapshot in snapshots:
        role, path, digest, dimensions, width, height, exact_bytes = expected[
            snapshot.artifact_id
        ]
        if (
            snapshot.role != role
            or snapshot.relative_path != path
            or snapshot.content_sha256 != digest
            or snapshot.dimensions != dimensions
            or snapshot.width != width
            or snapshot.height != height
            or (exact_bytes is not None and snapshot.content != exact_bytes)
        ):
            raise ValueError(
                "Emocio binary snapshot differs from processing provenance"
            )
        previous = paths.setdefault(snapshot.relative_path, snapshot)
        if (
            previous.content_sha256 != snapshot.content_sha256
            or previous.content != snapshot.content
            or previous.role != snapshot.role
        ):
            raise ValueError("One Emocio binary path maps to conflicting bytes")


__all__ = [
    "EmocioBinarySnapshot",
    "EmocioProcessingArtifact",
    "EmocioProcessorRuntimeConfig",
    "binary_snapshots_from_processing",
    "nested_provider_calls",
    "validate_binary_snapshots_against_processing",
    "validate_processing_runtime_closure",
]
