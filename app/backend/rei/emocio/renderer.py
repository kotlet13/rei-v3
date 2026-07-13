"""Optional B7 presentation rendering with complete request/call provenance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Protocol, runtime_checkable

from pydantic import Field

from ..ids import content_id, sha256_hex, utc_now
from ..models.common import FrozenModel, SafetyNotice, UtcTimestamp
from ..models.emocio import ImageArtifact, VisualSceneSpec
from ..models.provider import (
    PositiveSeconds,
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
)
from ..models.rendering import (
    ImageRenderBatchOutcome,
    ImageRenderItemOutcome,
    ImageRenderPreparationFailure,
    ImageRenderRequest,
    ImageSourceReference,
)
from ..providers.protocols import ImageRenderer, validate_image_render_outcome


class RenderSettings(FrozenModel):
    """Explicit rendering settings; B7 intentionally defines no hidden defaults."""

    width: Annotated[int, Field(gt=0)]
    height: Annotated[int, Field(gt=0)]
    num_inference_steps: Annotated[int, Field(gt=0)]
    guidance_scale: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    negative_prompt: str
    timeout_seconds: PositiveSeconds


@runtime_checkable
class ScenePromptCompiler(Protocol):
    def compile(self, scene: VisualSceneSpec) -> str: ...


class StructuredScenePromptCompiler:
    """Deterministically expose structured scene fields without semantic scoring."""

    def compile(self, scene: VisualSceneSpec) -> str:
        def joined(values: tuple[str, ...]) -> str:
            return ", ".join(values) if values else "none"

        attention = tuple(
            f"{item.target}:{item.score:.6f}" for item in scene.attention_structure
        )
        return "; ".join(
            (
                f"scene_kind={scene.scene_kind}",
                f"entities={joined(scene.entities)}",
                f"self_position={scene.self_position}",
                f"attention={joined(attention)}",
                f"group_belonging={scene.group_belonging}",
                f"status_relations={joined(scene.status_relations)}",
                f"movement={joined(scene.movement)}",
                f"composition={joined(scene.composition)}",
                f"attraction_markers={joined(scene.attraction_markers)}",
                f"obstacle_markers={joined(scene.obstacle_markers)}",
                f"inferred_elements={joined(scene.inferred_elements)}",
            )
        )


@runtime_checkable
class EmocioRenderer(Protocol):
    """Render frozen scene specs without participating in native valuation."""

    def render(
        self,
        scenes: tuple[VisualSceneSpec, ...],
        *,
        seed: int,
    ) -> ImageRenderBatchOutcome: ...


class NullRenderer:
    """Pure no-op renderer used by deterministic tests and headless runs."""

    def render(
        self,
        scenes: tuple[VisualSceneSpec, ...],
        *,
        seed: int,
    ) -> ImageRenderBatchOutcome:
        return ImageRenderBatchOutcome.create(
            source_spec_ids=tuple(scene.scene_id for scene in scenes),
            root_seed=seed,
            status="disabled",
        )


def derive_scene_seed(root_seed: int, source_spec_id: str) -> int:
    """Derive one stable non-negative 63-bit seed per frozen scene."""

    digest = sha256_hex(
        {
            "algorithm": "rei-emocio-scene-seed-v1",
            "root_seed": root_seed,
            "source_spec_id": source_spec_id,
        }
    )
    return int(digest[:16], 16) & ((1 << 63) - 1)


def _call_spec_for(
    request: ImageRenderRequest,
    *,
    timeout_seconds: float,
) -> ProviderCallSpec:
    fallback = ProviderFallbackPolicy(
        mode="none",
        no_fallback_reason=(
            "Optional rendering may fail without changing the frozen native conclusion"
        ),
    )
    safety_notice = SafetyNotice()
    payload = {
        "schema_version": "rei-native-provider-call-spec-v1",
        "request_id": request.request_id,
        "input_artifact_ids": request.input_artifact_ids,
        "provider": request.provider,
        "seed": request.seed,
        "parameters": request.provider_parameters,
        "timeout_seconds": timeout_seconds,
        "fallback_policy": fallback,
        "safety_notice": safety_notice,
    }
    return ProviderCallSpec(
        call_id=content_id("render_call", payload),
        **payload,
    )


def _failed_outcome(
    request: ImageRenderRequest,
    call: ProviderCallSpec,
    *,
    started_at: UtcTimestamp,
    code: str,
    message: str,
) -> ImageRenderItemOutcome:
    finished_at = utc_now()
    sanitized = " ".join(message.split())[:500] or code
    record = ProviderCallRecord(
        call_id=call.call_id,
        spec_hash=call.content_hash(),
        request_id=call.request_id,
        input_artifact_ids=call.input_artifact_ids,
        provider=call.provider,
        seed=call.seed,
        parameters=call.parameters,
        timeout_seconds=call.timeout_seconds,
        started_at=started_at,
        primary_finished_at=finished_at,
        finished_at=finished_at,
        status="failed",
        primary_status="failed",
        fallback=None,
        output_artifact_ids=(),
        warnings=(sanitized,),
        safety_notice=call.safety_notice,
    )
    return ImageRenderItemOutcome.create(
        request=request,
        call_spec=call,
        call_record=record,
        failure_code=code,
        failure_message=sanitized,
    )


class LocalEmocioRenderer:
    """Batch coordinator around the provider-neutral per-image protocol."""

    def __init__(
        self,
        *,
        provider: ImageRenderer,
        settings: RenderSettings,
        prompt_compiler: ScenePromptCompiler | None = None,
        image_to_image_sources: Mapping[str, ImageSourceReference] | None = None,
        image_to_image_strengths: Mapping[str, float] | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._prompt_compiler = prompt_compiler or StructuredScenePromptCompiler()
        self._sources = dict(image_to_image_sources or {})
        self._strengths = dict(image_to_image_strengths or {})
        if set(self._sources) != set(self._strengths):
            raise ValueError(
                "Every image-to-image source requires exactly one explicit strength"
            )

    def render(
        self,
        scenes: tuple[VisualSceneSpec, ...],
        *,
        seed: int,
    ) -> ImageRenderBatchOutcome:
        scene_ids = tuple(scene.scene_id for scene in scenes)
        if not scene_ids:
            raise ValueError("Renderer requires at least one frozen scene spec")
        if len(set(scene_ids)) != len(scene_ids):
            raise ValueError("Renderer input scene IDs must be unique")
        if not set(self._sources).issubset(scene_ids):
            raise ValueError("Image-to-image source mapping cites an absent scene")

        items: list[ImageRenderItemOutcome] = []
        preparation_failures: list[ImageRenderPreparationFailure] = []
        warnings: list[str] = []
        for scene in scenes:
            try:
                source = self._sources.get(scene.scene_id)
                mode = "image_to_image" if source is not None else "text_to_image"
                request = ImageRenderRequest.create(
                    mode=mode,
                    source_spec=scene,
                    provider=self._provider.identity,
                    pipeline=self._provider.pipeline_spec(mode),
                    seed=derive_scene_seed(seed, scene.scene_id),
                    prompt=self._prompt_compiler.compile(scene),
                    negative_prompt=self._settings.negative_prompt,
                    width=self._settings.width,
                    height=self._settings.height,
                    num_inference_steps=self._settings.num_inference_steps,
                    guidance_scale=self._settings.guidance_scale,
                    source_image=source,
                    strength=(
                        self._strengths.get(scene.scene_id)
                        if source is not None
                        else None
                    ),
                )
                call = _call_spec_for(
                    request,
                    timeout_seconds=self._settings.timeout_seconds,
                )
            except Exception as exc:
                code = type(exc).__name__ or "RenderPreparationFailure"
                message = " ".join(str(exc).split())[:500] or code
                preparation_failures.append(
                    ImageRenderPreparationFailure.create(
                        source_spec=scene,
                        failure_code=code,
                        failure_message=message,
                    )
                )
                warnings.append(message)
                continue

            started_at = utc_now()
            try:
                item = self._provider.render(request, call=call)
                validate_image_render_outcome(item, source_spec=scene)
            except Exception as exc:
                item = _failed_outcome(
                    request,
                    call,
                    started_at=started_at,
                    code="invalid_or_failed_provider_outcome",
                    message=str(exc) or type(exc).__name__,
                )
            items.append(item)
            if item.failure_message is not None:
                warnings.append(item.failure_message)

        successes = sum(item.artifact is not None for item in items)
        if successes == 0:
            status = "failed"
        elif successes == len(scenes):
            status = "succeeded"
        else:
            status = "partial"
        return ImageRenderBatchOutcome.create(
            source_spec_ids=scene_ids,
            root_seed=seed,
            status=status,
            items=tuple(items),
            preparation_failures=tuple(preparation_failures),
            warnings=tuple(warnings),
        )


def validate_render_batch(
    batch: ImageRenderBatchOutcome,
    scenes: tuple[VisualSceneSpec, ...],
    *,
    expected_seed: int | None = None,
) -> None:
    """Close every batch attempt while preserving disabled/failed outcomes."""

    scene_by_id = {scene.scene_id: scene for scene in scenes}
    if batch.source_spec_ids != tuple(scene_by_id):
        raise ValueError("Renderer batch scene order differs from frozen visual state")
    if expected_seed is not None and batch.root_seed != expected_seed:
        raise ValueError("Renderer batch root seed differs from requested seed")
    for item in batch.items:
        source_scene = scene_by_id.get(item.request.source_spec_id)
        if source_scene is None:
            raise ValueError("Renderer outcome cites a scene outside this Emocio run")
        if item.request.seed != derive_scene_seed(batch.root_seed, source_scene.scene_id):
            raise ValueError("Renderer scene seed differs from deterministic derivation")
        validate_image_render_outcome(item, source_spec=source_scene)
    for failure in batch.preparation_failures:
        source_scene = scene_by_id.get(failure.source_spec_id)
        if source_scene is None:
            raise ValueError("Renderer preparation failure cites an absent scene")
        if failure.source_spec_hash != source_scene.content_hash():
            raise ValueError("Renderer preparation failure scene hash differs")


def validate_renderer_outputs(
    images: tuple[ImageArtifact, ...],
    scenes: tuple[VisualSceneSpec, ...],
    *,
    expected_seed: int | None = None,
) -> None:
    """Compatibility validator for legacy tuple-returning B6 test adapters."""

    scene_by_id = {scene.scene_id: scene for scene in scenes}
    image_ids = tuple(image.image_id for image in images)
    if len(set(image_ids)) != len(image_ids):
        raise ValueError("Renderer image IDs must be unique")
    for image in images:
        source_scene = scene_by_id.get(image.source_spec_id)
        if source_scene is None:
            raise ValueError("Renderer output cites a scene outside this Emocio run")
        if image.input_spec_hash != source_scene.content_hash():
            raise ValueError("Renderer output input hash differs from its frozen scene")
        if expected_seed is not None and image.seed != expected_seed:
            raise ValueError("Renderer output seed differs from the requested seed")
        if image.grounded is not False:
            raise ValueError("Renderer output can never be grounded evidence")


__all__ = [
    "EmocioRenderer",
    "LocalEmocioRenderer",
    "NullRenderer",
    "RenderSettings",
    "ScenePromptCompiler",
    "StructuredScenePromptCompiler",
    "derive_scene_seed",
    "validate_render_batch",
    "validate_renderer_outputs",
]
