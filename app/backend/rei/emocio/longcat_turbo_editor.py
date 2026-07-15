"""Exact LongCat-Image-Edit-Turbo adapter for the frozen C4 Stage 1 screen."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import io
import os
import platform
from pathlib import Path
from types import ModuleType
from typing import Any

from ..ids import content_id
from ..models.emocio import VisualSceneSpec
from ..models.provider import ProviderIdentity
from ..models.rendering import (
    ImagePipelineSpec,
    ImageRenderRequest,
    ImageSourceReference,
)
from .c4_stage1_editor import (
    C4_STAGE1_SOURCE_HEIGHT,
    C4_STAGE1_SOURCE_WIDTH,
    C4Stage1ChildRuntimeProvenance,
    C4Stage1EditorOutput,
    C4Stage1EditorSpec,
    C4Stage1ImageEvidence,
    C4Stage1LocalSnapshotBinding,
    C4Stage1WorkerRequest,
    C4Stage1WorkerExecution,
    VerifiedC4Stage1Snapshot,
    canonical_provider_parameters,
    inspect_c4_stage1_png_bytes,
    verify_c4_stage1_snapshot,
)


LONGCAT_TURBO_MODEL_ID = "meituan-longcat/LongCat-Image-Edit-Turbo"
LONGCAT_TURBO_MODEL_REVISION = "6a7262de5549f0bf0ec54c08ef7d283ef41f3214"
LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256 = (
    "4a447342e10a7b214f43818e666af6a25b8c757650f7f8b6ff4317fca0f24783"
)
LONGCAT_TURBO_SNAPSHOT_FILE_COUNT = 37
LONGCAT_TURBO_SNAPSHOT_TOTAL_BYTES = 29_322_428_829
LONGCAT_TURBO_PIPELINE_CLASS = "LongCatImageEditPipeline"
LONGCAT_TURBO_INFERENCE_STEPS = 8
LONGCAT_TURBO_GUIDANCE_SCALE = 1.0


def longcat_turbo_provider_identity() -> ProviderIdentity:
    payload = {
        "schema_version": "rei-native-provider-identity-v1",
        "kind": "image_renderer",
        "implementation": (
            "app.backend.rei.emocio.longcat_turbo_editor.run_longcat_turbo_stage1_lazy"
        ),
        "implementation_revision": "c4-stage1-v1;diffusers=0.39.0",
        "uses_model": True,
        "model": LONGCAT_TURBO_MODEL_ID,
        "model_revision": LONGCAT_TURBO_MODEL_REVISION,
    }
    return ProviderIdentity(
        provider_id=content_id("provider", payload),
        **payload,
    )


def longcat_turbo_pipeline_spec(
    snapshot_manifest_sha256: str,
) -> ImagePipelineSpec:
    """Return the path-free exact LongCat load, call and output policy."""

    parameters = canonical_provider_parameters(
        {
            "call.generator_device": "cpu",
            "call.guidance_scale": LONGCAT_TURBO_GUIDANCE_SCALE,
            "call.image": "verified_rgb_source",
            "call.negative_prompt": "",
            "call.num_images_per_prompt": 1,
            "call.num_inference_steps": LONGCAT_TURBO_INFERENCE_STEPS,
            "call.output_type": "pil",
            "call.prompt": "exact_c4_editor_compact_v1_prompt",
            "call.return_dict": True,
            "fallback": "none",
            "load.enable_model_cpu_offload": True,
            "load.local_files_only": True,
            "load.offline_environment": True,
            "load.placement": "model_cpu_offload",
            "load.remote_code_allowed": False,
            "load.snapshot_manifest_sha256": snapshot_manifest_sha256,
            "load.source": "verified_local_snapshot_via_runtime_binding",
            "load.torch_dtype": "bfloat16",
            "load.use_safetensors": True,
            "output.best_of_n_allowed": False,
            "output.direct_rgb_png_evidence": True,
            "output.normalization": "rgb_then_pillow_lanczos_1024x768",
            "output.publish_in_child": False,
            "timeout.enforcement": "parent_process_tree_hard_wall",
            "timeout.seconds": 180.0,
        }
    )
    return ImagePipelineSpec(
        implementation="diffusers.LongCatImageEditPipeline",
        implementation_revision="0.39.0;c4-stage1-exact-v1",
        parameters=parameters,
    )


def longcat_turbo_stage1_spec(
    snapshot_manifest_sha256: str = LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256,
) -> C4Stage1EditorSpec:
    if snapshot_manifest_sha256 != LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256:
        raise ValueError(
            "LongCat Stage 1 snapshot manifest differs from the frozen pin"
        )
    return C4Stage1EditorSpec.create(
        editor_role="primary",
        provider=longcat_turbo_provider_identity(),
        pipeline=longcat_turbo_pipeline_spec(snapshot_manifest_sha256),
        repo_id=LONGCAT_TURBO_MODEL_ID,
        revision=LONGCAT_TURBO_MODEL_REVISION,
        license_spdx="Apache-2.0",
        snapshot_manifest_sha256=snapshot_manifest_sha256,
        snapshot_file_count=LONGCAT_TURBO_SNAPSHOT_FILE_COUNT,
        snapshot_total_bytes=LONGCAT_TURBO_SNAPSHOT_TOTAL_BYTES,
    )


def build_longcat_turbo_worker_request(
    *,
    editor_spec: C4Stage1EditorSpec,
    verified_snapshot: VerifiedC4Stage1Snapshot,
    scene: VisualSceneSpec,
    source_image: ImageSourceReference,
    seed: int,
    prompt: str,
    profile_hash: str,
) -> C4Stage1WorkerRequest:
    request = ImageRenderRequest.create(
        mode="image_to_image",
        source_spec=scene,
        provider=editor_spec.provider,
        pipeline=editor_spec.pipeline,
        seed=seed,
        prompt=prompt,
        negative_prompt="",
        width=C4_STAGE1_SOURCE_WIDTH,
        height=C4_STAGE1_SOURCE_HEIGHT,
        num_inference_steps=LONGCAT_TURBO_INFERENCE_STEPS,
        guidance_scale=LONGCAT_TURBO_GUIDANCE_SCALE,
        source_image=source_image,
        strength=None,
        conditioning_method="reference_image",
        prompt_language="en",
        style_id="documentary_cinematic_v1",
        profile_hash=profile_hash,
    )
    return C4Stage1WorkerRequest.create(
        editor_spec=editor_spec,
        verified_snapshot=verified_snapshot,
        render_request=request,
    )


def _validate_exact_request(
    editor_spec: C4Stage1EditorSpec,
    request: C4Stage1WorkerRequest,
) -> ImageRenderRequest:
    if request.editor_spec != editor_spec:
        raise ValueError("LongCat worker request uses another editor spec")
    expected_provider = longcat_turbo_provider_identity()
    expected_pipeline = longcat_turbo_pipeline_spec(
        editor_spec.snapshot_manifest_sha256
    )
    if (
        editor_spec.provider != expected_provider
        or editor_spec.pipeline != expected_pipeline
    ):
        raise ValueError("LongCat editor spec differs from the frozen exact adapter")
    if editor_spec.repo_id != LONGCAT_TURBO_MODEL_ID or (
        editor_spec.revision != LONGCAT_TURBO_MODEL_REVISION
    ):
        raise ValueError("LongCat editor spec differs from its exact model pin")
    render = request.render_request
    if render.negative_prompt != "":
        raise ValueError("LongCat Stage 1 requires the exact empty negative prompt")
    if render.num_inference_steps != LONGCAT_TURBO_INFERENCE_STEPS:
        raise ValueError("LongCat Stage 1 inference steps differ")
    if render.guidance_scale != LONGCAT_TURBO_GUIDANCE_SCALE:
        raise ValueError("LongCat Stage 1 guidance scale differs")
    return render


def _source_rgb(
    source_png: bytes,
    source_reference: ImageSourceReference,
    image_module: ModuleType | Any,
):
    dimensions = inspect_c4_stage1_png_bytes(source_png)
    if dimensions != (source_reference.width, source_reference.height):
        raise ValueError("LongCat source PNG dimensions differ from provenance")
    if dimensions != (C4_STAGE1_SOURCE_WIDTH, C4_STAGE1_SOURCE_HEIGHT):
        raise ValueError("LongCat source PNG must be exactly 1024x768")
    if hashlib.sha256(source_png).hexdigest() != source_reference.content_sha256:
        raise ValueError("LongCat source PNG digest differs from provenance")
    with image_module.open(io.BytesIO(source_png)) as source:
        rgb = source.convert("RGB")
        rgb.load()
        return rgb.copy()


def _encode_rgb_png(image: Any) -> bytes:
    if getattr(image, "mode", None) != "RGB":
        raise ValueError("Stage 1 PNG encoder requires an RGB image")
    target = io.BytesIO()
    image.save(target, format="PNG", optimize=False, compress_level=9)
    payload = target.getvalue()
    inspect_c4_stage1_png_bytes(payload)
    return payload


def execute_longcat_turbo_stage1(
    request: C4Stage1WorkerRequest,
    source_png: bytes,
    *,
    pipeline: Any,
    torch_module: ModuleType | Any,
    image_module: ModuleType | Any,
) -> C4Stage1EditorOutput:
    """Execute the exact call against an injected, already-loaded pipeline."""

    render = _validate_exact_request(request.editor_spec, request)
    if render.source_image is None:  # guarded by the shared worker schema
        raise ValueError("LongCat Stage 1 source image is missing")
    source = _source_rgb(source_png, render.source_image, image_module)
    generator = torch_module.Generator(device="cpu").manual_seed(render.seed)
    result = pipeline(
        image=source,
        prompt=render.prompt,
        negative_prompt="",
        num_inference_steps=LONGCAT_TURBO_INFERENCE_STEPS,
        guidance_scale=LONGCAT_TURBO_GUIDANCE_SCALE,
        num_images_per_prompt=1,
        generator=generator,
        output_type="pil",
        return_dict=True,
    )
    images = getattr(result, "images", None)
    if not isinstance(images, (list, tuple)) or len(images) != 1:
        raise ValueError("LongCat Stage 1 must return exactly one PIL image")
    native = images[0]
    direct_image = native.convert("RGB")
    direct_image.load()
    direct_png = _encode_rgb_png(direct_image)
    if tuple(direct_image.size) == (
        C4_STAGE1_SOURCE_WIDTH,
        C4_STAGE1_SOURCE_HEIGHT,
    ):
        staged_image = direct_image.copy()
    else:
        staged_image = direct_image.resize(
            (C4_STAGE1_SOURCE_WIDTH, C4_STAGE1_SOURCE_HEIGHT),
            resample=image_module.Resampling.LANCZOS,
        )
    staged_png = _encode_rgb_png(staged_image)
    evidence = C4Stage1ImageEvidence.create(
        direct_png=direct_png,
        staged_png=staged_png,
        normalization_policy="longcat_rgb_lanczos_1024x768",
    )
    return C4Stage1EditorOutput(
        direct_png=direct_png,
        staged_png=staged_png,
        evidence=evidence,
    )


def _require_exact_dependencies(spec: C4Stage1EditorSpec) -> None:
    actual = {
        "python": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
        "torch": importlib.metadata.version("torch"),
        "diffusers": importlib.metadata.version("diffusers"),
        "transformers": importlib.metadata.version("transformers"),
        "accelerate": importlib.metadata.version("accelerate"),
        "safetensors": importlib.metadata.version("safetensors"),
        "pillow": importlib.metadata.version("Pillow"),
    }
    expected = spec.dependencies.model_dump(mode="python")
    if actual != expected:
        raise RuntimeError("C4 Stage 1 dependency versions differ from the exact pin")


def _enable_offline_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["DIFFUSERS_OFFLINE"] = "1"


def run_longcat_turbo_stage1_lazy(
    request: C4Stage1WorkerRequest,
    source_png: bytes,
    *,
    binding: C4Stage1LocalSnapshotBinding,
) -> C4Stage1WorkerExecution:
    """Verify, lazy-import, load offline, reverify and execute one exact call."""

    spec = request.editor_spec
    if spec.editor_role != "primary":
        raise ValueError("Real LongCat execution requires the primary exact spec")
    _validate_exact_request(spec, request)
    loaded: dict[str, Any] = {}

    def load_after_full_verification() -> None:
        _enable_offline_environment()
        _require_exact_dependencies(spec)
        torch_module = importlib.import_module("torch")
        diffusers_module = importlib.import_module("diffusers")
        image_module = importlib.import_module("PIL.Image")
        torch_module.cuda.reset_peak_memory_stats()
        pipeline_class = getattr(diffusers_module, LONGCAT_TURBO_PIPELINE_CLASS)
        snapshot_root = Path(binding.snapshot_path).resolve(strict=True)
        pipeline = pipeline_class.from_pretrained(
            str(snapshot_root),
            local_files_only=True,
            use_safetensors=True,
            torch_dtype=torch_module.bfloat16,
        )
        pipeline.enable_model_cpu_offload()
        loaded.update(
            pipeline=pipeline,
            torch_module=torch_module,
            image_module=image_module,
        )

    verified = verify_c4_stage1_snapshot(
        spec,
        binding,
        after_verification=load_after_full_verification,
    )
    if verified != request.verified_snapshot:
        raise ValueError(
            "LongCat runtime snapshot proof differs from the worker request"
        )
    verify_c4_stage1_snapshot(spec, binding)
    output = execute_longcat_turbo_stage1(
        request,
        source_png,
        pipeline=loaded["pipeline"],
        torch_module=loaded["torch_module"],
        image_module=loaded["image_module"],
    )
    torch_module = loaded["torch_module"]
    runtime_provenance = C4Stage1ChildRuntimeProvenance.create(
        request,
        pipeline_class="LongCatImageEditPipeline",
        placement="model_cpu_offload",
        model_cpu_offload_enabled=True,
        torch_peak_allocated_bytes=int(torch_module.cuda.max_memory_allocated()),
        torch_peak_reserved_bytes=int(torch_module.cuda.max_memory_reserved()),
    )
    return C4Stage1WorkerExecution(
        request=request,
        output=output,
        runtime_provenance=runtime_provenance,
    )


__all__ = [
    "LONGCAT_TURBO_GUIDANCE_SCALE",
    "LONGCAT_TURBO_INFERENCE_STEPS",
    "LONGCAT_TURBO_MODEL_ID",
    "LONGCAT_TURBO_MODEL_REVISION",
    "LONGCAT_TURBO_PIPELINE_CLASS",
    "LONGCAT_TURBO_SNAPSHOT_FILE_COUNT",
    "LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256",
    "LONGCAT_TURBO_SNAPSHOT_TOTAL_BYTES",
    "build_longcat_turbo_worker_request",
    "execute_longcat_turbo_stage1",
    "longcat_turbo_pipeline_spec",
    "longcat_turbo_provider_identity",
    "longcat_turbo_stage1_spec",
    "run_longcat_turbo_stage1_lazy",
]
