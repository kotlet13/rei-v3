"""Run one create-only, offline FLUX.2 Klein current-first Emocio smoke batch.

This command never downloads weights.  The operator must supply an existing
snapshot directory and the SHA-256 of its canonical REI snapshot manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import platform
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.emocio.artifacts import LocalPngArtifactStore  # noqa: E402
from rei.emocio.current_first_renderer import (  # noqa: E402
    CurrentFirstEmocioRenderer,
    CurrentFirstRolloutConfig,
)
from rei.emocio.diffusers_renderer import (  # noqa: E402
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersImageRenderer,
    DiffusersRuntimeConfig,
    LazyDiffusersBackend,
)
from rei.emocio.packets import build_emocio_packet  # noqa: E402
from rei.emocio.prompting import (  # noqa: E402
    BilingualStructuredScenePromptCompiler,
    VisualPromptProfile,
)
from rei.emocio.renderer import RenderSettings  # noqa: E402
from rei.emocio.scene_graph import compile_emocio_scenes  # noqa: E402
from rei.ids import canonical_json_bytes, content_id  # noqa: E402
from rei.models.emocio import EmocioWorld  # noqa: E402
from rei.models.provider import ProviderIdentity  # noqa: E402
from rei.models.scene import (  # noqa: E402
    DecisionOption,
    EvidenceItem,
    SceneEvent,
)


MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
MODEL_REVISION = "e7b7dc27f91deacad38e78976d1f2b499d76a294"


def _scene() -> SceneEvent:
    return SceneEvent(
        event_id="c4_real_smoke_scene",
        raw_input=(
            "Self stands at the edge of a small studio gathering and chooses "
            "whether to enter the shared circle or remain at the doorway."
        ),
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="c4_smoke_grounded_visual",
                modality="image",
                content="self at a studio doorway facing a small group",
                grounded=True,
                source_ref="synthetic:c4-smoke-fixture",
                confidence=1.0,
            ),
        ),
        options=(
            DecisionOption(
                option_id="enter_circle",
                label="enter the shared circle",
                description=(
                    "the same central self visibly crosses the threshold and stands "
                    "one meter inside the room among the collaborative group"
                ),
            ),
            DecisionOption(
                option_id="remain_edge",
                label="remain at the doorway",
                description=(
                    "the same central self remains fully visible at the same foreground "
                    "spot with both feet outside and behind the threshold"
                ),
            ),
        ),
        actors=("self", "small_group"),
        constraints=("preserve the same self and studio layout",),
        unknowns=("how the group will respond",),
    )


def _world() -> EmocioWorld:
    return EmocioWorld(
        world_id="c4_real_smoke_world",
        visual_memories=("dim studio doorway", "small collaborative group"),
        desired_scenes=(
            "self visibly included in a welcoming collaborative circle",
            "warm shared light",
        ),
        broken_scenes=(
            "self isolated outside the group in shadow",
            "closed social distance",
        ),
        social_identity_motifs=("visible belonging among peers",),
        attraction_patterns=("warm shared light", "open group composition"),
        motor_patterns=("one deliberate step toward the group",),
    )


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())


def _provider_identity() -> ProviderIdentity:
    payload = {
        "schema_version": "rei-native-provider-identity-v1",
        "kind": "image_renderer",
        "implementation": "rei.emocio.DiffusersImageRenderer",
        "implementation_revision": "c4-flux2-klein-v1;diffusers=0.39.0",
        "uses_model": True,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
    }
    return ProviderIdentity(
        provider_id=content_id("provider", payload),
        **payload,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-directory", type=Path, required=True)
    parser.add_argument("--snapshot-manifest-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=424242)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--model-cpu-offload",
        action="store_true",
        help="Enable Diffusers model CPU offload and a CPU generator.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot = args.snapshot_directory.expanduser().resolve(strict=True)
    manifest_path = snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    manifest_bytes = manifest_path.read_bytes()
    actual_manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if actual_manifest_sha256 != args.snapshot_manifest_sha256:
        raise ValueError("Snapshot manifest SHA-256 differs from the CLI pin")

    output = args.output_directory.expanduser().resolve()
    if output.exists():
        raise FileExistsError("Smoke output directory already exists (create-only)")
    output.mkdir(parents=True)

    # Defense in depth: the provider also enforces local_files_only and loads the
    # verified absolute snapshot path rather than a Hub repository identifier.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("The real C4 smoke requires a CUDA device")
    torch.cuda.reset_peak_memory_stats()

    identity = _provider_identity()
    runtime = DiffusersRuntimeConfig(
        device="cuda",
        torch_dtype="bfloat16",
        local_files_only=True,
        variant=None,
        enable_attention_slicing=False,
        enable_model_cpu_offload=args.model_cpu_offload,
        pipeline_family="flux2_klein",
        local_snapshot_path=str(snapshot),
        expected_snapshot_manifest_sha256=actual_manifest_sha256,
    )
    backend = LazyDiffusersBackend(runtime)
    artifact_store = LocalPngArtifactStore(output / "artifacts")
    provider = DiffusersImageRenderer(
        identity=identity,
        backend=backend,
        artifact_store=artifact_store,
    )
    settings = RenderSettings(
        width=args.width,
        height=args.height,
        num_inference_steps=args.steps,
        guidance_scale=1.0,
        negative_prompt="",
        timeout_seconds=args.timeout_seconds,
    )
    prompt_profile = VisualPromptProfile.create(
        language="en",
        style_id="documentary_cinematic_v1",
        style_directive=(
            "Documentary cinematic still, restrained natural colors, stable identity "
            "and composition. No text, labels, logos, crowns, weapons, or extra people."
        ),
    )
    renderer = CurrentFirstEmocioRenderer(
        provider=provider,
        settings=settings,
        prompt_compiler=BilingualStructuredScenePromptCompiler(prompt_profile),
        rollout=CurrentFirstRolloutConfig(conditioning_method="reference_image"),
    )

    scene = _scene()
    world = _world()
    packet = build_emocio_packet(scene)
    compiled = compile_emocio_scenes(scene, packet, world)
    started = time.perf_counter()
    batch = renderer.render(compiled.all_scenes, seed=args.seed)
    elapsed_seconds = round(time.perf_counter() - started, 6)

    current_items = tuple(
        item
        for item in batch.items
        if item.request.source_spec_id == compiled.current_scene.scene_id
    )
    if len(current_items) != 1 or current_items[0].artifact is None:
        raise RuntimeError("Smoke did not produce the one current-scene artifact")
    current_artifact = current_items[0].artifact
    rollout_items = tuple(
        item
        for item in batch.items
        if item.request.mode == "image_to_image"
    )
    expected_rollouts = len(compiled.option_rollouts)
    lineage_ok = (
        len(rollout_items) == expected_rollouts
        and all(
            item.request.conditioning_method == "reference_image"
            and item.request.strength is None
            and item.request.source_image is not None
            and item.request.source_image.image_id == current_artifact.image_id
            and item.request.source_image.content_sha256
            == current_artifact.content_sha256
            and item.request.source_image.originating_scene_spec_id
            == compiled.current_scene.scene_id
            and item.request.source_image.originating_scene_spec_hash
            == compiled.current_scene.content_hash()
            for item in rollout_items
        )
    )
    prompt_provenance_ok = (
        len(batch.items) == len(compiled.all_scenes)
        and all(
            item.request.prompt_language == prompt_profile.language
            and item.request.style_id == prompt_profile.style_id
            and item.request.profile_hash == prompt_profile.content_hash()
            for item in batch.items
        )
    )
    technical_success = (
        batch.status == "succeeded"
        and len(batch.artifacts) == len(compiled.all_scenes)
        and lineage_ok
        and prompt_provenance_ok
    )

    evidence = {
        "schema_version": "rei-c4-real-renderer-smoke-v2",
        "passed": technical_success,
        "pass_scope": "technical_renderer_lineage_and_provenance_only",
        "technical_passed": technical_success,
        "semantic_review_status": "requires_human_review",
        "semantic_quality_gate_passed": False,
        "semantic_review_required_for": (
            "current_desired_broken_plausibility",
            "option_rollout_action_distinction",
            "source_subject_preservation",
        ),
        "offline_environment": {
            "HF_HUB_OFFLINE": os.environ["HF_HUB_OFFLINE"],
            "TRANSFORMERS_OFFLINE": os.environ["TRANSFORMERS_OFFLINE"],
        },
        "provider": identity,
        "pipeline_specs": {
            "text_to_image": backend.pipeline_spec("text_to_image"),
            "image_to_image": backend.pipeline_spec("image_to_image"),
        },
        "snapshot_manifest_sha256": actual_manifest_sha256,
        "snapshot_manifest_file_count": len(
            __import__("json").loads(manifest_bytes)["files"]
        ),
        "root_seed": args.seed,
        "settings": settings,
        "prompt_profile": prompt_profile,
        "batch_id": batch.batch_id,
        "batch_status": batch.status,
        "artifact_ids": tuple(item.image_id for item in batch.artifacts),
        "artifact_hashes": tuple(item.content_sha256 for item in batch.artifacts),
        "current_source_reused_for_every_rollout": lineage_ok,
        "prompt_provenance_matches_every_request": prompt_provenance_ok,
        "generated_images_are_external_evidence": False,
        "production_authority_granted": False,
        "model_cpu_offload_enabled": args.model_cpu_offload,
        "elapsed_seconds": elapsed_seconds,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "diffusers": importlib.metadata.version("diffusers"),
            "transformers": importlib.metadata.version("transformers"),
            "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "gpu_compute_capability": tuple(torch.cuda.get_device_capability(0)),
            "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(),
        },
    }
    _write_new(output / "scene.json", canonical_json_bytes(scene))
    _write_new(output / "emocio_world.json", canonical_json_bytes(world))
    _write_new(output / "emocio_packet.json", canonical_json_bytes(packet))
    _write_new(
        output / "compiled_scenes.json",
        canonical_json_bytes(compiled.all_scenes),
    )
    _write_new(output / "render_batch.json", canonical_json_bytes(batch))
    _write_new(output / "smoke_evidence.json", canonical_json_bytes(evidence))
    print((output / "smoke_evidence.json").read_text(encoding="utf-8"))
    return 0 if technical_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
