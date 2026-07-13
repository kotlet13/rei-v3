"""Lazy local Diffusers adapter behind the provider-neutral B7 contract.

Importing this module never imports Torch, loads model weights, or touches a
device.  The optional stack is imported only when ``LazyDiffusersBackend`` is
actually asked to render.
"""

from __future__ import annotations

import hashlib
import io
import re
import threading
from collections.abc import Mapping
from typing import Literal, Protocol, runtime_checkable

from ..ids import canonical_json_bytes, content_id, utc_now
from ..models.common import FrozenModel, NonEmptyText
from ..models.emocio import ImageArtifact
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderIdentity,
    ProviderParameter,
    ensure_call_contract,
)
from ..models.rendering import (
    ImagePipelineSpec,
    ImageRenderItemOutcome,
    ImageRenderMode,
    ImageRenderRequest,
)
from .artifacts import LocalPngArtifactStore, inspect_png


@runtime_checkable
class DiffusionBackend(Protocol):
    """Minimal byte-returning seam used by deterministic tests and Diffusers."""

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes: ...


class DiffusersRuntimeConfig(FrozenModel):
    """Explicit local execution settings; no model is selected here."""

    device: NonEmptyText
    torch_dtype: Literal["float16", "bfloat16", "float32"]
    local_files_only: Literal[True]
    variant: NonEmptyText | None = None
    enable_attention_slicing: bool

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec:
        pipeline = (
            "diffusers.AutoPipelineForText2Image"
            if mode == "text_to_image"
            else "diffusers.AutoPipelineForImage2Image"
        )
        values = {
            "device": self.device,
            "enable_attention_slicing": self.enable_attention_slicing,
            "local_files_only": self.local_files_only,
            "torch_dtype": self.torch_dtype,
            "use_safetensors": True,
            "variant": self.variant,
        }
        return ImagePipelineSpec(
            implementation=pipeline,
            implementation_revision="0.39.0",
            parameters=tuple(
                ProviderParameter(
                    name=name,
                    canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
                )
                for name, value in sorted(values.items())
            ),
        )


class LazyDiffusersBackend:
    """Load exact-revision Diffusers pipelines only on the first real call."""

    def __init__(self, config: DiffusersRuntimeConfig) -> None:
        self._config = config
        self._pipelines: dict[tuple[str, str, str], object] = {}
        self._lock = threading.RLock()

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec:
        return self._config.pipeline_spec(mode)

    def _pipeline(self, request: ImageRenderRequest) -> tuple[object, object, object]:
        if not request.provider.uses_model:
            raise ValueError("Diffusers requires a model-backed provider identity")
        model = request.provider.model
        revision = request.provider.model_revision
        if model is None or revision is None:
            raise ValueError("Diffusers requires an exact model and revision")

        expected_pipeline = self.pipeline_spec(request.mode)
        if request.pipeline != expected_pipeline:
            raise ValueError("Render request pipeline differs from Diffusers runtime")

        try:
            from importlib.metadata import version

            import torch
            from diffusers import (
                AutoPipelineForImage2Image,
                AutoPipelineForText2Image,
            )
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "Install app/backend/requirements-renderer.txt before rendering"
            ) from exc

        installed_diffusers = version("diffusers")
        if installed_diffusers != expected_pipeline.implementation_revision:
            raise RuntimeError(
                "Installed Diffusers version differs from approved pipeline revision"
            )

        cache_key = (model, revision, expected_pipeline.content_hash())
        pipeline = self._pipelines.get(cache_key)
        if pipeline is None:
            dtype = getattr(torch, self._config.torch_dtype)
            pipeline_type = (
                AutoPipelineForText2Image
                if request.mode == "text_to_image"
                else AutoPipelineForImage2Image
            )
            load_options: dict[str, object] = {
                "revision": revision,
                "torch_dtype": dtype,
                "use_safetensors": True,
                "local_files_only": self._config.local_files_only,
            }
            if self._config.variant is not None:
                load_options["variant"] = self._config.variant
            pipeline = pipeline_type.from_pretrained(model, **load_options)
            pipeline = pipeline.to(self._config.device)
            if self._config.enable_attention_slicing:
                pipeline.enable_attention_slicing()
            self._pipelines[cache_key] = pipeline
        return pipeline, torch, Image

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes:
        with self._lock:
            pipeline, torch, image_module = self._pipeline(request)
            generator = torch.Generator(device=self._config.device).manual_seed(
                request.seed
            )
            options: dict[str, object] = {
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "num_inference_steps": request.num_inference_steps,
                "guidance_scale": request.guidance_scale,
                "generator": generator,
            }
            if request.mode == "text_to_image":
                if source_png is not None:
                    raise ValueError("text_to_image backend call received source bytes")
                options.update(width=request.width, height=request.height)
            else:
                if source_png is None or request.strength is None:
                    raise ValueError("image_to_image backend call requires source bytes")
                with image_module.open(io.BytesIO(source_png)) as opened:
                    source_image = opened.convert("RGB").copy()
                options.update(image=source_image, strength=request.strength)

            result = pipeline(**options)
            images = getattr(result, "images", None)
            if not images:
                raise RuntimeError("Diffusers returned no image")
            output = io.BytesIO()
            images[0].save(output, format="PNG")
            return output.getvalue()


def _sanitized_failure(exc: Exception) -> tuple[str, str]:
    code = type(exc).__name__ or "RendererFailure"
    message = " ".join(str(exc).split())[:500]
    return code, message or code


class DiffusersImageRenderer:
    """Provider implementation that returns auditable success/failure outcomes."""

    def __init__(
        self,
        *,
        identity: ProviderIdentity,
        backend: DiffusionBackend,
        artifact_store: LocalPngArtifactStore,
        pipeline_specs: Mapping[ImageRenderMode, ImagePipelineSpec] | None = None,
    ) -> None:
        if identity.kind != "image_renderer" or not identity.uses_model:
            raise ValueError(
                "DiffusersImageRenderer requires a model-backed image_renderer identity"
            )
        if identity.model_revision is None or re.fullmatch(
            r"[0-9a-f]{40}", identity.model_revision
        ) is None:
            raise ValueError(
                "Diffusers model_revision must be an immutable 40-hex Hub commit"
            )
        self._identity = identity
        self._backend = backend
        self._artifact_store = artifact_store
        if pipeline_specs is None:
            resolver = getattr(backend, "pipeline_spec", None)
            if callable(resolver):
                pipeline_specs = {
                    mode: resolver(mode)
                    for mode in ("text_to_image", "image_to_image")
                }
            else:
                pipeline_specs = {
                    mode: ImagePipelineSpec(
                        implementation=identity.implementation,
                        implementation_revision=identity.implementation_revision,
                    )
                    for mode in ("text_to_image", "image_to_image")
                }
        if set(pipeline_specs) != {"text_to_image", "image_to_image"}:
            raise ValueError("Renderer requires exact T2I and img2img pipeline specs")
        self._pipeline_specs = dict(pipeline_specs)

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec:
        return self._pipeline_specs[mode]

    def _validate_call(
        self,
        request: ImageRenderRequest,
        call: ProviderCallSpec,
    ) -> None:
        ensure_call_contract(
            self.identity,
            call,
            request_id=request.request_id,
            seed=request.seed,
            expected_kind="image_renderer",
            required_input_artifact_ids=request.input_artifact_ids,
        )
        if call.input_artifact_ids != request.input_artifact_ids:
            raise ValueError("Renderer call must exactly close request input artifacts")
        if call.parameters != request.provider_parameters:
            raise ValueError("Renderer call parameters differ from approved request")
        if request.pipeline != self.pipeline_spec(request.mode):
            raise ValueError("Renderer request pipeline differs from provider runtime")
        if call.fallback_policy.mode != "none":
            raise ValueError(
                "This local adapter does not execute implicit provider fallbacks"
            )

    def render(
        self,
        request: ImageRenderRequest,
        *,
        call: ProviderCallSpec,
    ) -> ImageRenderItemOutcome:
        self._validate_call(request, call)
        started_at = utc_now()
        try:
            source_png = (
                self._artifact_store.read_verified_source(request.source_image)
                if request.source_image is not None
                else None
            )
            png_bytes = self._backend.render(request, source_png=source_png)
            width, height = inspect_png(png_bytes)
            if (width, height) != (request.width, request.height):
                raise ValueError(
                    "Renderer output dimensions differ from approved request"
                )
            content_sha256 = hashlib.sha256(png_bytes).hexdigest()
            image_id = content_id(
                "image",
                {
                    "request_id": request.request_id,
                    "content_sha256": content_sha256,
                },
            )
            relative_path = f"emocio/images/{image_id}.png"
            artifact = ImageArtifact(
                image_id=image_id,
                request_id=request.request_id,
                render_call_id=call.call_id,
                source_spec_id=request.source_spec_id,
                provider_id=self.identity.provider_id,
                model=self.identity.model,
                model_revision=self.identity.model_revision,
                seed=request.seed,
                input_spec_hash=request.source_spec_hash,
                content_sha256=content_sha256,
                media_type="image/png",
                grounded=False,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                path=relative_path,
                width=width,
                height=height,
                generated_only_elements=("unverified_renderer_details",),
                grounded_mask_path=None,
            )
            stored = self._artifact_store.persist_png(
                relative_path,
                png_bytes,
                expected_width=width,
                expected_height=height,
            )
            if stored.content_sha256 != artifact.content_sha256:
                raise ValueError("Stored image hash differs from image artifact")
            finished_at = utc_now()
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
                status="succeeded",
                primary_status="succeeded",
                fallback=None,
                output_artifact_ids=(artifact.image_id,),
                warnings=(),
                safety_notice=call.safety_notice,
            )
            return ImageRenderItemOutcome.create(
                request=request,
                call_spec=call,
                call_record=record,
                artifact=artifact,
            )
        except Exception as exc:
            finished_at = utc_now()
            code, message = _sanitized_failure(exc)
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
                warnings=(message,),
                safety_notice=call.safety_notice,
            )
            return ImageRenderItemOutcome.create(
                request=request,
                call_spec=call,
                call_record=record,
                failure_code=code,
                failure_message=message,
            )


__all__ = [
    "DiffusersImageRenderer",
    "DiffusersRuntimeConfig",
    "DiffusionBackend",
    "LazyDiffusersBackend",
]
