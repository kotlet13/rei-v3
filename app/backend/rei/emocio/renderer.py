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
    ImageConditioningMethod,
    ImageRenderBatchOutcome,
    ImageRenderItemOutcome,
    ImageRenderPreparationFailure,
    ImageRenderRequest,
    ImageSourceReference,
)
from ..providers.protocols import ImageRenderer, validate_image_render_outcome
from .prompting import VisualPromptProfile


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


@runtime_checkable
class MaterializedEmocioRenderer(EmocioRenderer, Protocol):
    """Renderer whose published image bytes can be re-read and verified exactly."""

    def read_artifact_bytes(self, image: ImageArtifact) -> bytes: ...


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


def build_render_call_spec(
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


def _safe_exception_code(
    error: Exception,
    *,
    fallback: str,
) -> str:
    return "renderer_timeout" if isinstance(error, TimeoutError) else fallback


def _fixed_failure_message(scope: str, code: str) -> str:
    return f"{scope} failed closed ({code})"


def _redact_provider_outcome(
    item: ImageRenderItemOutcome,
) -> ImageRenderItemOutcome:
    """Remove provider-controlled diagnostics while preserving exact execution."""

    if item.artifact is not None:
        safe_warnings = tuple(
            warning
            for warning in item.call_record.warnings
            if warning == "cache_hit_verified"
        )
        if safe_warnings == item.call_record.warnings:
            return item
        record = item.call_record.model_copy(update={"warnings": safe_warnings})
        return ImageRenderItemOutcome.create(
            request=item.request,
            call_spec=item.call_spec,
            call_record=record,
            artifact=item.artifact,
        )

    code = (
        "renderer_timeout"
        if item.call_record.status == "timed_out"
        else "renderer_provider_failure"
    )
    message = _fixed_failure_message("Image renderer provider", code)
    record = item.call_record.model_copy(update={"warnings": (message,)})
    return ImageRenderItemOutcome.create(
        request=item.request,
        call_spec=item.call_spec,
        call_record=record,
        failure_code=code,
        failure_message=message,
    )


def redact_render_batch_diagnostics(
    batch: ImageRenderBatchOutcome,
) -> ImageRenderBatchOutcome:
    """Canonicalize all renderer-controlled diagnostics before persistence."""

    validated = ImageRenderBatchOutcome.model_validate(
        batch.model_dump(mode="python", round_trip=True)
    )
    items = tuple(_redact_provider_outcome(item) for item in validated.items)
    preparation_failures: list[ImageRenderPreparationFailure] = []
    for failure in validated.preparation_failures:
        code = "render_preparation_failure"
        message = _fixed_failure_message("Image render preparation", code)
        payload = {
            "schema_version": "rei-native-image-render-preparation-failure-v1",
            "source_spec_id": failure.source_spec_id,
            "source_spec_hash": failure.source_spec_hash,
            "failure_code": code,
            "failure_message": message,
        }
        preparation_failures.append(
            ImageRenderPreparationFailure(
                failure_id=content_id("render_preparation_failure", payload),
                **payload,
            )
        )
    warnings = tuple(
        dict.fromkeys(
            (
                *(
                    failure.failure_message
                    for failure in preparation_failures
                ),
                *(
                    item.failure_message
                    for item in items
                    if item.failure_message is not None
                ),
            )
        )
    )
    return ImageRenderBatchOutcome.create(
        source_spec_ids=validated.source_spec_ids,
        root_seed=validated.root_seed,
        status=validated.status,
        items=items,
        preparation_failures=tuple(preparation_failures),
        warnings=warnings,
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
        image_to_image_conditioning: (
            Mapping[str, ImageConditioningMethod] | None
        ) = None,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._prompt_compiler = prompt_compiler or StructuredScenePromptCompiler()
        prompt_profile = getattr(self._prompt_compiler, "prompt_profile", None)
        if prompt_profile is not None and not isinstance(
            prompt_profile, VisualPromptProfile
        ):
            raise TypeError(
                "A provenanced scene prompt compiler must expose VisualPromptProfile"
            )
        self._prompt_profile = prompt_profile
        self._sources = dict(image_to_image_sources or {})
        self._strengths = dict(image_to_image_strengths or {})
        requested_conditioning = dict(image_to_image_conditioning or {})
        if not set(self._strengths).issubset(self._sources):
            raise ValueError("Image-to-image strength mapping cites no source image")
        if not set(requested_conditioning).issubset(self._sources):
            raise ValueError(
                "Image-to-image conditioning mapping cites no source image"
            )
        self._conditioning: dict[str, ImageConditioningMethod] = {}
        for scene_id in self._sources:
            method = requested_conditioning.get(scene_id)
            if method is None:
                if scene_id not in self._strengths:
                    raise ValueError(
                        "Every image-to-image source requires explicit conditioning"
                    )
                method = "classic_strength"
            if method == "none":
                raise ValueError("Image-to-image sources cannot use none conditioning")
            if method == "classic_strength" and scene_id not in self._strengths:
                raise ValueError("classic_strength conditioning requires strength")
            if method == "reference_image" and scene_id in self._strengths:
                raise ValueError(
                    "reference_image conditioning cannot carry classic strength"
                )
            self._conditioning[scene_id] = method

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
                    conditioning_method=(
                        self._conditioning.get(scene.scene_id)
                        if source is not None
                        else "none"
                    ),
                    prompt_language=(
                        self._prompt_profile.language
                        if self._prompt_profile is not None
                        else None
                    ),
                    style_id=(
                        self._prompt_profile.style_id
                        if self._prompt_profile is not None
                        else None
                    ),
                    profile_hash=(
                        self._prompt_profile.content_hash()
                        if self._prompt_profile is not None
                        else None
                    ),
                )
                call = build_render_call_spec(
                    request,
                    timeout_seconds=self._settings.timeout_seconds,
                )
            except Exception as exc:
                code = _safe_exception_code(
                    exc,
                    fallback="RenderPreparationFailure",
                )
                message = _fixed_failure_message(
                    "Image render preparation",
                    code,
                )
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
                if item.request != request or item.call_spec != call:
                    raise ValueError(
                        "Renderer returned another pre-approved request or call spec"
                    )
                item = _redact_provider_outcome(item)
            except Exception as exc:
                code = _safe_exception_code(
                    exc,
                    fallback="RendererProviderFailure",
                )
                item = _failed_outcome(
                    request,
                    call,
                    started_at=started_at,
                    code="invalid_or_failed_provider_outcome",
                    message=_fixed_failure_message(
                        "Image renderer provider outcome",
                        code,
                    ),
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
    "build_render_call_spec",
    "EmocioRenderer",
    "LocalEmocioRenderer",
    "MaterializedEmocioRenderer",
    "NullRenderer",
    "RenderSettings",
    "ScenePromptCompiler",
    "StructuredScenePromptCompiler",
    "derive_scene_seed",
    "redact_render_batch_diagnostics",
    "validate_render_batch",
    "validate_renderer_outputs",
]
