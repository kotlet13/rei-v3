"""Content-addressed B7 contracts for optional Emocio image rendering.

These artifacts describe presentation work only.  They never become inputs to
the structured Emocio policy and never carry grounded event evidence.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id
from .common import (
    ArtifactRelativePath,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from .emocio import ImageArtifact, ImageMediaType, VisualSceneSpec
from .provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderIdentity,
    ProviderParameter,
    ensure_call_record_contract,
)


ImageRenderMode = Literal["text_to_image", "image_to_image"]
ImageRenderBatchStatus = Literal["disabled", "succeeded", "partial", "failed"]
NonNegativeFinite = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class ImageSourceReference(FrozenArtifactModel):
    """Immutable byte-level reference used by an image-to-image request."""

    schema_version: Literal["rei-native-image-source-reference-v1"] = (
        "rei-native-image-source-reference-v1"
    )
    image_id: NonEmptyId
    content_sha256: HashDigest
    media_type: ImageMediaType
    path: ArtifactRelativePath
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    grounded: bool

    @classmethod
    def from_artifact(cls, artifact: ImageArtifact) -> ImageSourceReference:
        return cls(
            image_id=artifact.image_id,
            content_sha256=artifact.content_sha256,
            media_type=artifact.media_type,
            path=artifact.path,
            width=artifact.width,
            height=artifact.height,
            grounded=artifact.grounded,
        )


class ImagePipelineSpec(FrozenModel):
    """Exact pipeline implementation and load/runtime settings for replay."""

    implementation: NonEmptyText
    implementation_revision: NonEmptyText
    parameters: tuple[ProviderParameter, ...] = ()

    @model_validator(mode="after")
    def validate_parameters(self) -> Self:
        names = tuple(item.name for item in self.parameters)
        if len(set(names)) != len(names):
            raise ValueError("Image pipeline parameter names must be unique")
        if names != tuple(sorted(names)):
            raise ValueError("Image pipeline parameters must use canonical name order")
        return self


class ImageRenderRequest(FrozenArtifactModel):
    """Exact, replayable renderer input approved before provider execution."""

    schema_version: Literal["rei-native-image-render-request-v1"] = (
        "rei-native-image-render-request-v1"
    )
    request_id: NonEmptyId
    mode: ImageRenderMode
    source_spec_id: NonEmptyId
    source_spec_hash: HashDigest
    provider: ProviderIdentity
    pipeline: ImagePipelineSpec
    seed: int
    prompt: NonEmptyText
    negative_prompt: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    num_inference_steps: int = Field(gt=0)
    guidance_scale: NonNegativeFinite
    source_image: ImageSourceReference | None = None
    strength: Score01 | None = None

    @classmethod
    def create(
        cls,
        *,
        mode: ImageRenderMode,
        source_spec: VisualSceneSpec,
        provider: ProviderIdentity,
        pipeline: ImagePipelineSpec,
        seed: int,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        num_inference_steps: int,
        guidance_scale: float,
        source_image: ImageSourceReference | None = None,
        strength: float | None = None,
    ) -> ImageRenderRequest:
        payload = {
            "schema_version": "rei-native-image-render-request-v1",
            "mode": mode,
            "source_spec_id": source_spec.scene_id,
            "source_spec_hash": source_spec.content_hash(),
            "provider": provider,
            "pipeline": pipeline,
            "seed": seed,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "source_image": source_image,
            "strength": strength,
        }
        return cls(
            request_id=content_id("image_request", payload),
            **payload,
        )

    @property
    def input_artifact_ids(self) -> tuple[NonEmptyId, ...]:
        if self.source_image is None:
            return (self.source_spec_id,)
        return (self.source_spec_id, self.source_image.image_id)

    @property
    def provider_parameters(self) -> tuple[ProviderParameter, ...]:
        """Expose the replay-critical request settings in a call manifest."""

        source_digest = (
            self.source_image.content_sha256 if self.source_image is not None else None
        )
        values = {
            "guidance_scale": self.guidance_scale,
            "height": self.height,
            "mode": self.mode,
            "num_inference_steps": self.num_inference_steps,
            "pipeline": self.pipeline.implementation,
            "pipeline_revision": self.pipeline.implementation_revision,
            "pipeline_spec_hash": self.pipeline.content_hash(),
            "request_hash": self.content_hash(),
            "source_image_sha256": source_digest,
            "strength": self.strength,
            "width": self.width,
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
            for parameter in self.pipeline.parameters
        )
        return tuple(sorted(parameters, key=lambda item: item.name))

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.provider.kind != "image_renderer":
            raise ValueError("Image render requests require an image_renderer provider")
        if self.mode == "text_to_image":
            if self.source_image is not None or self.strength is not None:
                raise ValueError(
                    "text_to_image requests cannot carry source image or strength"
                )
        elif self.source_image is None or self.strength is None:
            raise ValueError("image_to_image requests require source image and strength")
        elif (self.width, self.height) != (
            self.source_image.width,
            self.source_image.height,
        ):
            raise ValueError(
                "B7 image_to_image requests preserve source image dimensions"
            )
        expected = content_id(
            "image_request",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"request_id"},
            ),
        )
        if self.request_id != expected:
            raise ValueError("Image render request ID does not match canonical content")
        return self

    def validate_source_spec(self, source_spec: VisualSceneSpec) -> Self:
        if self.source_spec_id != source_spec.scene_id:
            raise ValueError("Image render request cites another scene spec")
        if self.source_spec_hash != source_spec.content_hash():
            raise ValueError("Image render request source spec hash differs")
        return self


class ImageRenderItemOutcome(FrozenArtifactModel):
    """One attempted scene render with its complete approved/executed call."""

    schema_version: Literal["rei-native-image-render-outcome-v1"] = (
        "rei-native-image-render-outcome-v1"
    )
    outcome_id: NonEmptyId
    request: ImageRenderRequest
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord
    artifact: ImageArtifact | None = None
    failure_code: NonEmptyId | None = None
    failure_message: NonEmptyText | None = None

    @classmethod
    def create(
        cls,
        *,
        request: ImageRenderRequest,
        call_spec: ProviderCallSpec,
        call_record: ProviderCallRecord,
        artifact: ImageArtifact | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> ImageRenderItemOutcome:
        payload = {
            "schema_version": "rei-native-image-render-outcome-v1",
            "request": request,
            "call_spec": call_spec,
            "call_record": call_record,
            "artifact": artifact,
            "failure_code": failure_code,
            "failure_message": failure_message,
        }
        return cls(
            outcome_id=content_id("render_outcome", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        ensure_call_record_contract(self.call_spec, self.call_record)
        request = self.request
        if (
            self.call_spec.request_id != request.request_id
            or self.call_spec.provider != request.provider
            or self.call_spec.seed != request.seed
            or self.call_spec.input_artifact_ids != request.input_artifact_ids
            or self.call_spec.parameters != request.provider_parameters
        ):
            raise ValueError("Renderer call spec differs from its immutable request")
        succeeded = self.call_record.status in {"succeeded", "fell_back"}
        if succeeded != (self.artifact is not None):
            raise ValueError(
                "Successful renderer calls require an artifact and failed calls forbid one"
            )
        if succeeded:
            if self.failure_code is not None or self.failure_message is not None:
                raise ValueError("Successful renderer outcomes cannot claim a failure")
            if self.call_record.output_artifact_ids != (self.artifact.image_id,):
                raise ValueError("Renderer call output must be the returned image artifact")
        elif self.failure_code is None or self.failure_message is None:
            raise ValueError("Failed renderer outcomes require structured failure details")
        expected = content_id(
            "render_outcome",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"outcome_id"},
            ),
        )
        if self.outcome_id != expected:
            raise ValueError("Renderer outcome ID does not match canonical content")
        return self


class ImageRenderPreparationFailure(FrozenArtifactModel):
    """A scene that failed before an approved provider call could be formed."""

    schema_version: Literal["rei-native-image-render-preparation-failure-v1"] = (
        "rei-native-image-render-preparation-failure-v1"
    )
    failure_id: NonEmptyId
    source_spec_id: NonEmptyId
    source_spec_hash: HashDigest
    failure_code: NonEmptyId
    failure_message: NonEmptyText

    @classmethod
    def create(
        cls,
        *,
        source_spec: VisualSceneSpec,
        failure_code: str,
        failure_message: str,
    ) -> ImageRenderPreparationFailure:
        sanitized = " ".join(failure_message.split())[:500] or failure_code
        payload = {
            "schema_version": "rei-native-image-render-preparation-failure-v1",
            "source_spec_id": source_spec.scene_id,
            "source_spec_hash": source_spec.content_hash(),
            "failure_code": failure_code,
            "failure_message": sanitized,
        }
        return cls(
            failure_id=content_id("render_preparation_failure", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_failure_id(self) -> Self:
        expected = content_id(
            "render_preparation_failure",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"failure_id"},
            ),
        )
        if self.failure_id != expected:
            raise ValueError("Render preparation failure ID differs from content")
        return self


class ImageRenderBatchOutcome(FrozenArtifactModel):
    """Aggregate optional-render status kept separate from native Emocio state."""

    schema_version: Literal["rei-native-image-render-batch-v1"] = (
        "rei-native-image-render-batch-v1"
    )
    batch_id: NonEmptyId
    source_spec_ids: tuple[NonEmptyId, ...]
    root_seed: int
    status: ImageRenderBatchStatus
    items: tuple[ImageRenderItemOutcome, ...] = ()
    preparation_failures: tuple[ImageRenderPreparationFailure, ...] = ()
    warnings: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        source_spec_ids: tuple[str, ...],
        root_seed: int,
        status: ImageRenderBatchStatus,
        items: tuple[ImageRenderItemOutcome, ...] = (),
        preparation_failures: tuple[ImageRenderPreparationFailure, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> ImageRenderBatchOutcome:
        payload = {
            "schema_version": "rei-native-image-render-batch-v1",
            "source_spec_ids": source_spec_ids,
            "root_seed": root_seed,
            "status": status,
            "items": items,
            "preparation_failures": preparation_failures,
            "warnings": warnings,
        }
        return cls(batch_id=content_id("render_batch", payload), **payload)

    @property
    def artifacts(self) -> tuple[ImageArtifact, ...]:
        return tuple(item.artifact for item in self.items if item.artifact is not None)

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        if len(set(self.source_spec_ids)) != len(self.source_spec_ids):
            raise ValueError("Renderer batch source spec IDs must be unique")
        item_spec_ids = tuple(item.request.source_spec_id for item in self.items)
        if len(set(item_spec_ids)) != len(item_spec_ids):
            raise ValueError("Renderer batch can attempt each scene only once")
        preparation_spec_ids = tuple(
            item.source_spec_id for item in self.preparation_failures
        )
        if len(set(preparation_spec_ids)) != len(preparation_spec_ids):
            raise ValueError("Renderer batch preparation failures must be unique")
        covered_ids = item_spec_ids + preparation_spec_ids
        if len(set(covered_ids)) != len(covered_ids):
            raise ValueError("Each renderer batch scene must have exactly one outcome")
        successes = len(self.artifacts)
        if self.status == "disabled":
            if self.items or self.preparation_failures:
                raise ValueError("A disabled renderer batch cannot contain attempts")
        else:
            if set(covered_ids) != set(self.source_spec_ids):
                raise ValueError("Renderer batch must cover every frozen source scene")
            source_order = {
                scene_id: index for index, scene_id in enumerate(self.source_spec_ids)
            }
            if tuple(source_order[item] for item in item_spec_ids) != tuple(
                sorted(source_order[item] for item in item_spec_ids)
            ):
                raise ValueError("Renderer call outcomes must preserve source order")
            if tuple(source_order[item] for item in preparation_spec_ids) != tuple(
                sorted(source_order[item] for item in preparation_spec_ids)
            ):
                raise ValueError("Renderer preparation failures must preserve source order")
        failures = len(covered_ids) - successes
        if self.status == "succeeded":
            if successes != len(self.source_spec_ids) or failures:
                raise ValueError("A succeeded renderer batch requires all items to succeed")
        elif self.status == "partial":
            if successes == 0 or failures == 0:
                raise ValueError("A partial renderer batch requires mixed outcomes")
        elif self.status == "failed" and (not covered_ids or successes != 0):
            raise ValueError("A failed renderer batch requires only failed attempts")
        expected = content_id(
            "render_batch",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"batch_id"},
            ),
        )
        if self.batch_id != expected:
            raise ValueError("Renderer batch ID does not match canonical content")
        return self


__all__ = [
    "ImageRenderBatchOutcome",
    "ImageRenderBatchStatus",
    "ImageRenderItemOutcome",
    "ImageRenderMode",
    "ImageRenderPreparationFailure",
    "ImageRenderRequest",
    "ImagePipelineSpec",
    "ImageSourceReference",
]
