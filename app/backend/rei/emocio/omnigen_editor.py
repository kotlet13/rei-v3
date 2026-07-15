"""Exact OmniGen-v1 Diffusers adapter for the frozen C4 Stage 1 screen."""

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


OMNIGEN_MODEL_ID = "Shitao/OmniGen-v1-diffusers"
OMNIGEN_MODEL_REVISION = "016e2f61d12a98303f6bbdf122687694d7984268"
OMNIGEN_SNAPSHOT_MANIFEST_SHA256 = (
    "3522d2bb368a4a304045432d6641abb69a4b73d876d8f904d36efe9458998bce"
)
OMNIGEN_SNAPSHOT_FILE_COUNT = 11
OMNIGEN_SNAPSHOT_TOTAL_BYTES = 8_088_956_424
OMNIGEN_PIPELINE_CLASS = "OmniGenPipeline"
OMNIGEN_PROMPT_PREFIX = "<img><|image_1|></img>\n"
OMNIGEN_INFERENCE_STEPS = 50
OMNIGEN_GUIDANCE_SCALE = 2.0
OMNIGEN_IMAGE_GUIDANCE_SCALE = 1.6


def omnigen_provider_identity() -> ProviderIdentity:
    payload = {
        "schema_version": "rei-native-provider-identity-v1",
        "kind": "image_renderer",
        "implementation": (
            "app.backend.rei.emocio.omnigen_editor.run_omnigen_stage1_lazy"
        ),
        "implementation_revision": "c4-stage1-v1;diffusers=0.39.0",
        "uses_model": True,
        "model": OMNIGEN_MODEL_ID,
        "model_revision": OMNIGEN_MODEL_REVISION,
    }
    return ProviderIdentity(
        provider_id=content_id("provider", payload),
        **payload,
    )


def omnigen_pipeline_spec(snapshot_manifest_sha256: str) -> ImagePipelineSpec:
    """Return the path-free exact OmniGen load, call and output policy."""

    parameters = canonical_provider_parameters(
        {
            "call.generator_device": "cpu",
            "call.guidance_scale": OMNIGEN_GUIDANCE_SCALE,
            "call.height": None,
            "call.img_guidance_scale": OMNIGEN_IMAGE_GUIDANCE_SCALE,
            "call.input_images": ["verified_rgb_source"],
            "call.latents": None,
            "call.max_input_image_size": 1024,
            "call.negative_prompt_argument": False,
            "call.num_images_per_prompt": 1,
            "call.num_inference_steps": OMNIGEN_INFERENCE_STEPS,
            "call.output_type": "pil",
            "call.prompt_prefix": OMNIGEN_PROMPT_PREFIX,
            "call.return_dict": True,
            "call.timesteps": None,
            "call.use_input_image_size_as_output": True,
            "call.width": None,
            "fallback": "none",
            "load.enable_model_cpu_offload": False,
            "load.local_files_only": True,
            "load.offline_environment": True,
            "load.placement": "direct_cuda",
            "load.remote_code_allowed": False,
            "load.snapshot_manifest_sha256": snapshot_manifest_sha256,
            "load.source": "verified_local_snapshot_via_runtime_binding",
            "load.torch_dtype": "bfloat16",
            "load.use_safetensors": True,
            "output.best_of_n_allowed": False,
            "output.normalization": "strict_identity_rgb_1024x768_no_resize_no_crop",
            "output.publish_in_child": False,
            "timeout.enforcement": "parent_process_tree_hard_wall",
            "timeout.seconds": 180.0,
        }
    )
    return ImagePipelineSpec(
        implementation="diffusers.OmniGenPipeline",
        implementation_revision="0.39.0;c4-stage1-exact-v1",
        parameters=parameters,
    )


def omnigen_stage1_spec(
    snapshot_manifest_sha256: str = OMNIGEN_SNAPSHOT_MANIFEST_SHA256,
) -> C4Stage1EditorSpec:
    if snapshot_manifest_sha256 != OMNIGEN_SNAPSHOT_MANIFEST_SHA256:
        raise ValueError(
            "OmniGen Stage 1 snapshot manifest differs from the frozen pin"
        )
    return C4Stage1EditorSpec.create(
        editor_role="alternate",
        provider=omnigen_provider_identity(),
        pipeline=omnigen_pipeline_spec(snapshot_manifest_sha256),
        repo_id=OMNIGEN_MODEL_ID,
        revision=OMNIGEN_MODEL_REVISION,
        license_spdx="MIT",
        snapshot_manifest_sha256=snapshot_manifest_sha256,
        snapshot_file_count=OMNIGEN_SNAPSHOT_FILE_COUNT,
        snapshot_total_bytes=OMNIGEN_SNAPSHOT_TOTAL_BYTES,
    )


def build_omnigen_worker_request(
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
        num_inference_steps=OMNIGEN_INFERENCE_STEPS,
        guidance_scale=OMNIGEN_GUIDANCE_SCALE,
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
        raise ValueError("OmniGen worker request uses another editor spec")
    expected_provider = omnigen_provider_identity()
    expected_pipeline = omnigen_pipeline_spec(editor_spec.snapshot_manifest_sha256)
    if (
        editor_spec.provider != expected_provider
        or editor_spec.pipeline != expected_pipeline
    ):
        raise ValueError("OmniGen editor spec differs from the frozen exact adapter")
    if editor_spec.repo_id != OMNIGEN_MODEL_ID or (
        editor_spec.revision != OMNIGEN_MODEL_REVISION
    ):
        raise ValueError("OmniGen editor spec differs from its exact model pin")
    render = request.render_request
    if render.negative_prompt != "":
        raise ValueError("OmniGen request provenance requires an empty placeholder")
    if render.num_inference_steps != OMNIGEN_INFERENCE_STEPS:
        raise ValueError("OmniGen Stage 1 inference steps differ")
    if render.guidance_scale != OMNIGEN_GUIDANCE_SCALE:
        raise ValueError("OmniGen Stage 1 guidance scale differs")
    return render


def _source_rgb(
    source_png: bytes,
    source_reference: ImageSourceReference,
    image_module: ModuleType | Any,
):
    dimensions = inspect_c4_stage1_png_bytes(source_png)
    if dimensions != (source_reference.width, source_reference.height):
        raise ValueError("OmniGen source PNG dimensions differ from provenance")
    if dimensions != (C4_STAGE1_SOURCE_WIDTH, C4_STAGE1_SOURCE_HEIGHT):
        raise ValueError("OmniGen source PNG must be exactly 1024x768")
    if hashlib.sha256(source_png).hexdigest() != source_reference.content_sha256:
        raise ValueError("OmniGen source PNG digest differs from provenance")
    with image_module.open(io.BytesIO(source_png)) as source:
        rgb = source.convert("RGB")
        rgb.load()
        return rgb.copy()


def _encode_rgb_png(image: Any) -> bytes:
    if getattr(image, "mode", None) != "RGB":
        raise ValueError("OmniGen Stage 1 output must already be RGB")
    target = io.BytesIO()
    image.save(target, format="PNG", optimize=False, compress_level=9)
    payload = target.getvalue()
    inspect_c4_stage1_png_bytes(payload)
    return payload


def execute_omnigen_stage1(
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
        raise ValueError("OmniGen Stage 1 source image is missing")
    source = _source_rgb(source_png, render.source_image, image_module)
    generator = torch_module.Generator(device="cpu").manual_seed(render.seed)
    result = pipeline(
        prompt=OMNIGEN_PROMPT_PREFIX + render.prompt,
        input_images=[source],
        height=None,
        width=None,
        num_inference_steps=OMNIGEN_INFERENCE_STEPS,
        max_input_image_size=1024,
        timesteps=None,
        guidance_scale=OMNIGEN_GUIDANCE_SCALE,
        img_guidance_scale=OMNIGEN_IMAGE_GUIDANCE_SCALE,
        use_input_image_size_as_output=True,
        num_images_per_prompt=1,
        generator=generator,
        latents=None,
        output_type="pil",
        return_dict=True,
    )
    images = getattr(result, "images", None)
    if not isinstance(images, (list, tuple)) or len(images) != 1:
        raise ValueError("OmniGen Stage 1 must return exactly one PIL image")
    native = images[0]
    if getattr(native, "mode", None) != "RGB":
        raise ValueError("OmniGen Stage 1 output must already be RGB")
    if tuple(getattr(native, "size", ())) != (
        C4_STAGE1_SOURCE_WIDTH,
        C4_STAGE1_SOURCE_HEIGHT,
    ):
        raise ValueError("OmniGen Stage 1 output must already be exactly 1024x768")
    native.load()
    staged_png = _encode_rgb_png(native)
    evidence = C4Stage1ImageEvidence.create(
        direct_png=staged_png,
        staged_png=staged_png,
        normalization_policy="omnigen_strict_identity_rgb_1024x768",
    )
    return C4Stage1EditorOutput(
        direct_png=staged_png,
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
    if actual != spec.dependencies.model_dump(mode="python"):
        raise RuntimeError("C4 Stage 1 dependency versions differ from the exact pin")


def _enable_offline_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["DIFFUSERS_OFFLINE"] = "1"


def run_omnigen_stage1_lazy(
    request: C4Stage1WorkerRequest,
    source_png: bytes,
    *,
    binding: C4Stage1LocalSnapshotBinding,
) -> C4Stage1WorkerExecution:
    """Verify, lazy-import, load offline, reverify and execute one exact call."""

    spec = request.editor_spec
    if spec.editor_role != "alternate":
        raise ValueError("Real OmniGen execution requires the alternate exact spec")
    _validate_exact_request(spec, request)
    loaded: dict[str, Any] = {}

    def load_after_full_verification() -> None:
        _enable_offline_environment()
        _require_exact_dependencies(spec)
        torch_module = importlib.import_module("torch")
        diffusers_module = importlib.import_module("diffusers")
        image_module = importlib.import_module("PIL.Image")
        torch_module.cuda.reset_peak_memory_stats()
        pipeline_class = getattr(diffusers_module, OMNIGEN_PIPELINE_CLASS)
        snapshot_root = Path(binding.snapshot_path).resolve(strict=True)
        pipeline = pipeline_class.from_pretrained(
            str(snapshot_root),
            local_files_only=True,
            use_safetensors=True,
            torch_dtype=torch_module.bfloat16,
        )
        pipeline.to("cuda")
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
        raise ValueError("OmniGen runtime snapshot proof differs from worker request")
    verify_c4_stage1_snapshot(spec, binding)
    output = execute_omnigen_stage1(
        request,
        source_png,
        pipeline=loaded["pipeline"],
        torch_module=loaded["torch_module"],
        image_module=loaded["image_module"],
    )
    torch_module = loaded["torch_module"]
    runtime_provenance = C4Stage1ChildRuntimeProvenance.create(
        request,
        pipeline_class="OmniGenPipeline",
        placement="direct_cuda",
        model_cpu_offload_enabled=False,
        torch_peak_allocated_bytes=int(torch_module.cuda.max_memory_allocated()),
        torch_peak_reserved_bytes=int(torch_module.cuda.max_memory_reserved()),
    )
    return C4Stage1WorkerExecution(
        request=request,
        output=output,
        runtime_provenance=runtime_provenance,
    )


__all__ = [
    "OMNIGEN_GUIDANCE_SCALE",
    "OMNIGEN_IMAGE_GUIDANCE_SCALE",
    "OMNIGEN_INFERENCE_STEPS",
    "OMNIGEN_MODEL_ID",
    "OMNIGEN_MODEL_REVISION",
    "OMNIGEN_PIPELINE_CLASS",
    "OMNIGEN_PROMPT_PREFIX",
    "OMNIGEN_SNAPSHOT_FILE_COUNT",
    "OMNIGEN_SNAPSHOT_MANIFEST_SHA256",
    "OMNIGEN_SNAPSHOT_TOTAL_BYTES",
    "build_omnigen_worker_request",
    "execute_omnigen_stage1",
    "omnigen_pipeline_spec",
    "omnigen_provider_identity",
    "omnigen_stage1_spec",
    "run_omnigen_stage1_lazy",
]
