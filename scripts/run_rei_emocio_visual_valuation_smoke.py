"""Encode one verified renderer batch and run the narrow C4 visual valuation.

The command is create-only and offline. It consumes the canonical output of
``run_rei_emocio_visual_smoke.py`` and never downloads model files. The caller
must supply an existing DINOv2 snapshot and its exact REI manifest SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.emocio.artifacts import LocalPngArtifactStore  # noqa: E402
from rei.emocio.dinov2_encoder import (  # noqa: E402
    DinoV2BaseImageEncoder,
    DinoV2RuntimeConfig,
    LocalFloat32VectorStore,
)
from rei.emocio.diffusers_renderer import (  # noqa: E402
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
)
from rei.emocio.packets import build_emocio_packet  # noqa: E402
from rei.emocio.renderer import validate_render_batch  # noqa: E402
from rei.emocio.scene_graph import compile_emocio_scenes  # noqa: E402
from rei.emocio.valuation import build_emocio_visual_state  # noqa: E402
from rei.emocio.visual_policy_config import (  # noqa: E402
    load_visual_valuation_policy_config,
)
from rei.emocio.visual_valuation import (  # noqa: E402
    BoundVisualEmbedding,
    evaluate_visual_valuation,
)
from rei.emocio.visual_world_memory import (  # noqa: E402
    build_visual_world_memory_record,
)
from rei.ids import canonical_json_bytes, content_id  # noqa: E402
from rei.models.emocio import (  # noqa: E402
    EmocioInputPacket,
    EmocioWorld,
    GroundedVisualRepresentation,
    ImaginedVisualArtifact,
    VisualSceneSpec,
)
from rei.models.rendering import ImageRenderBatchOutcome  # noqa: E402
from rei.models.scene import SceneEvent  # noqa: E402


_SCENE_TUPLE = TypeAdapter(tuple[VisualSceneSpec, ...])
RUNNER_IMPLEMENTATION_REVISION = "c4-dinov2-visual-valuation-smoke-v2"


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_canonical_model(path: Path, model: type[Any]) -> Any:
    payload = path.read_bytes()
    value = model.model_validate_json(payload, strict=False)
    if canonical_json_bytes(value) != payload:
        raise ValueError(f"Stored smoke artifact is not canonical JSON: {path.name}")
    return value


def _load_canonical_scenes(path: Path) -> tuple[VisualSceneSpec, ...]:
    payload = path.read_bytes()
    scenes = _SCENE_TUPLE.validate_json(payload, strict=False)
    if canonical_json_bytes(scenes) != payload:
        raise ValueError("Stored compiled scenes are not canonical JSON")
    return scenes


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renderer-output-directory", type=Path, required=True)
    parser.add_argument("--snapshot-directory", type=Path, required=True)
    parser.add_argument("--snapshot-manifest-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--expected-render-batch-id", required=True)
    parser.add_argument("--expected-render-batch-hash", required=True)
    parser.add_argument("--expected-root-seed", type=int, required=True)
    parser.add_argument("--expected-renderer-provider-id", required=True)
    parser.add_argument("--expected-renderer-model", required=True)
    parser.add_argument("--expected-renderer-revision", required=True)
    parser.add_argument("--expected-prompt-profile-hash", required=True)
    parser.add_argument("--policy-config", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Cooperative deadline; it cannot cancel a blocked CUDA kernel.",
    )
    return parser.parse_args(argv)


def _run_smoke(args: argparse.Namespace, *, output: Path) -> int:
    renderer_output = args.renderer_output_directory.expanduser().resolve(
        strict=True
    )
    snapshot = args.snapshot_directory.expanduser().resolve(strict=True)
    manifest_path = snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != args.snapshot_manifest_sha256:
        raise ValueError("DINOv2 snapshot manifest SHA-256 differs from the CLI pin")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"

    scene = _load_canonical_model(renderer_output / "scene.json", SceneEvent)
    world = _load_canonical_model(
        renderer_output / "emocio_world.json",
        EmocioWorld,
    )
    packet = _load_canonical_model(
        renderer_output / "emocio_packet.json",
        EmocioInputPacket,
    )
    stored_scenes = _load_canonical_scenes(
        renderer_output / "compiled_scenes.json"
    )
    render_batch = _load_canonical_model(
        renderer_output / "render_batch.json",
        ImageRenderBatchOutcome,
    )
    if render_batch.batch_id != args.expected_render_batch_id:
        raise ValueError("Render batch ID differs from the explicit CLI pin")
    if render_batch.content_hash() != args.expected_render_batch_hash:
        raise ValueError("Render batch content hash differs from the explicit CLI pin")
    if render_batch.root_seed != args.expected_root_seed:
        raise ValueError("Render batch root seed differs from the explicit CLI pin")

    packet.validate_against(scene)
    if packet != build_emocio_packet(scene):
        raise ValueError("Smoke packet differs from the deterministic scene packet")
    compiled = compile_emocio_scenes(scene, packet, world)
    if compiled.all_scenes != stored_scenes:
        raise ValueError("Stored scene specs differ from deterministic compilation")
    visual_state = build_emocio_visual_state(
        scene=scene,
        packet=packet,
        world=world,
        compiled=compiled,
    )
    validate_render_batch(
        render_batch,
        compiled.all_scenes,
        expected_seed=args.expected_root_seed,
    )
    if render_batch.status != "succeeded":
        raise ValueError("Visual valuation smoke requires a successful render batch")
    renderer_identities = {item.request.provider for item in render_batch.items}
    if len(renderer_identities) != 1:
        raise ValueError("Render batch must use one exact renderer identity")
    renderer_identity = next(iter(renderer_identities))
    if (
        renderer_identity.provider_id != args.expected_renderer_provider_id
        or renderer_identity.model != args.expected_renderer_model
        or renderer_identity.model_revision != args.expected_renderer_revision
    ):
        raise ValueError("Renderer identity differs from the explicit CLI pins")
    if any(
        item.request.profile_hash != args.expected_prompt_profile_hash
        for item in render_batch.items
    ):
        raise ValueError("Prompt profile hash differs from the explicit CLI pin")

    policy_config = load_visual_valuation_policy_config(args.policy_config)
    source_image_store = LocalPngArtifactStore(renderer_output / "artifacts")
    encoder = DinoV2BaseImageEncoder(
        runtime=DinoV2RuntimeConfig(
            local_snapshot_path=str(snapshot),
            expected_snapshot_manifest_sha256=manifest_sha256,
            device=args.device,
        ),
        image_store=source_image_store,
        vector_store=LocalFloat32VectorStore(output / "artifacts"),
    )

    item_by_scene = {item.request.source_spec_id: item for item in render_batch.items}
    expected_scene_ids = {item.scene_id for item in compiled.all_scenes}
    if set(item_by_scene) != expected_scene_ids:
        raise ValueError("Render batch does not contain exactly one item per scene")

    grounded = GroundedVisualRepresentation(
        source_evidence_ids=compiled.current_scene.grounded_evidence_ids,
        scene_spec_id=compiled.current_scene.scene_id,
    ).validate_against(compiled.current_scene, scene)

    imagined_artifacts: list[ImaginedVisualArtifact] = []
    encodings = []
    observations: list[BoundVisualEmbedding] = []
    started = time.perf_counter()
    for scene_spec in compiled.all_scenes:
        item = item_by_scene[scene_spec.scene_id]
        image = item.artifact
        if image is None:
            raise ValueError("Successful render item has no image artifact")
        imagined = ImaginedVisualArtifact(
            artifact_id=image.image_id,
            originating_scene_spec_id=scene_spec.scene_id,
            option_id=scene_spec.option_id,
            seed=image.seed,
            model_identity=item.request.provider,
            ungrounded_elements=image.generated_only_elements,
        )
        imagined.validate_against(image, scene_spec)
        call_spec = encoder.build_call_spec(
            image,
            timeout_seconds=args.timeout_seconds,
        )
        encoding = encoder.encode(image, call=call_spec)
        observation = BoundVisualEmbedding.create(
            role=scene_spec.scene_kind,
            evaluation_seed=render_batch.root_seed,
            render_batch=render_batch,
            scene_spec=scene_spec,
            image=image,
            imagined=imagined,
            encoding=encoding,
            vector=encoder.read_vector(encoding),
        )
        imagined_artifacts.append(imagined)
        encodings.append(encoding)
        observations.append(observation)

    valuation = evaluate_visual_valuation(
        policy=policy_config.policy,
        visual_state=visual_state,
        observations=tuple(observations),
    )
    valuation.validate_against(
        visual_state=visual_state,
        observations=tuple(observations),
    )
    memories = tuple(
        build_visual_world_memory_record(
            observation=observation,
            valuation=valuation,
            visual_state=visual_state,
            observations=tuple(observations),
        )
        for observation in observations
        if observation.role == "option_rollout"
    )
    elapsed_seconds = round(time.perf_counter() - started, 6)

    import torch

    runtime = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torchvision": importlib.metadata.version("torchvision"),
        "pillow": importlib.metadata.version("Pillow"),
        "transformers": importlib.metadata.version("transformers"),
        "cuda_runtime": torch.version.cuda,
        "cudnn_runtime": torch.backends.cudnn.version(),
        "deterministic_algorithms": (
            torch.are_deterministic_algorithms_enabled()
        ),
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "device": args.device,
        "gpu": (
            torch.cuda.get_device_name(0)
            if args.device == "cuda" and torch.cuda.is_available()
            else None
        ),
    }
    evidence = {
        "schema_version": "rei-c4-real-visual-valuation-smoke-v2",
        "runner_implementation_revision": RUNNER_IMPLEMENTATION_REVISION,
        "implementation_file_sha256": {
            "dinov2_encoder.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "emocio" / "dinov2_encoder.py"
            ),
            "vector_encoding.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "emocio" / "vector_encoding.py"
            ),
            "visual_valuation.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "emocio" / "visual_valuation.py"
            ),
            "visual_world_memory.py": _file_sha256(
                ROOT
                / "app"
                / "backend"
                / "rei"
                / "emocio"
                / "visual_world_memory.py"
            ),
            "emocio_models.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "models" / "emocio.py"
            ),
            "provider_models.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "models" / "provider.py"
            ),
            "rendering_models.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "models" / "rendering.py"
            ),
            "provider_protocols.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "providers" / "protocols.py"
            ),
            "renderer_validation.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "emocio" / "renderer.py"
            ),
            "structured_valuation.py": _file_sha256(
                ROOT / "app" / "backend" / "rei" / "emocio" / "valuation.py"
            ),
            "runner": _file_sha256(Path(__file__)),
            "policy_config": _file_sha256(
                args.policy_config.resolve(strict=True)
                if args.policy_config is not None
                else ROOT / "config" / "emocio_visual_valuation_v1.json"
            ),
        },
        "technical_passed": True,
        "pass_scope": "encoder_lineage_visual_comparison_and_collapse_gate",
        "semantic_quality_gate_passed": False,
        "semantic_review_status": "requires_human_review",
        "valuation_technically_usable_for_this_batch": (
            valuation.integration_disposition == "usable"
        ),
        "approved_for_native_influence": False,
        "native_influence_approval_reason": (
            "Full seed/style/language/renderer robustness and human review are open"
        ),
        "source_render_batch_id": render_batch.batch_id,
        "source_render_batch_hash": render_batch.content_hash(),
        "source_root_seed": render_batch.root_seed,
        "source_visual_state_id": visual_state.visual_state_id,
        "source_visual_state_hash": visual_state.content_hash(),
        "source_renderer": renderer_identity,
        "source_prompt_profile_hash": args.expected_prompt_profile_hash,
        "encoder": encoder.identity,
        "snapshot_manifest_sha256": manifest_sha256,
        "policy_config_id": policy_config.config_id,
        "policy_id": policy_config.policy.policy_id,
        "valuation_result_id": valuation.result_id,
        "integration_disposition": valuation.integration_disposition,
        "action_collapse": valuation.action_collapse,
        "encoding_ids": tuple(item.encoding_id for item in encodings),
        "vector_hashes": tuple(item.vector_hash for item in encodings),
        "generated_images_are_external_evidence": False,
        "offline_environment": {
            "HF_HUB_OFFLINE": os.environ["HF_HUB_OFFLINE"],
            "TRANSFORMERS_OFFLINE": os.environ["TRANSFORMERS_OFFLINE"],
        },
        "runtime": runtime,
        "elapsed_seconds": elapsed_seconds,
        "timeout_enforcement": {
            "mode": "cooperative_monotonic_deadline",
            "hard_cancellation": False,
        },
        "bundle_manifest_filename": "bundle_manifest.json",
    }

    _write_new(
        output / "grounded_visual_representation.json",
        canonical_json_bytes(grounded),
    )
    _write_new(
        output / "emocio_visual_state.json",
        canonical_json_bytes(visual_state),
    )
    _write_new(
        output / "imagined_visual_artifacts.json",
        canonical_json_bytes(tuple(imagined_artifacts)),
    )
    _write_new(
        output / "image_encodings.json",
        canonical_json_bytes(tuple(encodings)),
    )
    _write_new(
        output / "bound_visual_observations.json",
        canonical_json_bytes(tuple(observations)),
    )
    _write_new(
        output / "visual_valuation.json",
        canonical_json_bytes(valuation),
    )
    _write_new(
        output / "visual_world_memory.json",
        canonical_json_bytes(memories),
    )
    _write_new(
        output / "smoke_evidence.json",
        canonical_json_bytes(evidence),
    )
    for source_name in (
        "scene.json",
        "emocio_world.json",
        "emocio_packet.json",
        "compiled_scenes.json",
        "render_batch.json",
        "smoke_evidence.json",
    ):
        _write_new(
            output / "source_renderer" / source_name,
            (renderer_output / source_name).read_bytes(),
        )
    for observation in observations:
        _write_new(
            output / "artifacts" / observation.image.path,
            source_image_store.verify_artifact(observation.image),
        )

    files = tuple(
        {
            "relative_path": path.relative_to(output).as_posix(),
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(item for item in output.rglob("*") if item.is_file())
    )
    manifest_payload = {
        "schema_version": "rei-c4-visual-valuation-bundle-manifest-v2",
        "runner_implementation_revision": RUNNER_IMPLEMENTATION_REVISION,
        "source_render_batch_id": render_batch.batch_id,
        "source_render_batch_hash": render_batch.content_hash(),
        "valuation_result_id": valuation.result_id,
        "files": files,
    }
    bundle_manifest = {
        "manifest_id": content_id("visual_valuation_bundle", manifest_payload),
        **manifest_payload,
    }
    _write_new(
        output / "bundle_manifest.json",
        canonical_json_bytes(bundle_manifest),
    )
    print((output / "smoke_evidence.json").read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output_directory.expanduser().resolve()
    if output.exists():
        raise FileExistsError("Valuation smoke output already exists (create-only)")
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = f".{output.name}.tmp-"
    working = Path(
        tempfile.mkdtemp(prefix=prefix, dir=output.parent)
    ).resolve(strict=True)
    if working.parent != output.parent or not working.name.startswith(prefix):
        raise RuntimeError("Temporary smoke path escaped the output parent")
    try:
        result = _run_smoke(args, output=working)
        working.rename(output)
    except BaseException:
        if (
            working.exists()
            and working.parent == output.parent
            and working.name.startswith(prefix)
        ):
            shutil.rmtree(working)
        raise
    return result


if __name__ == "__main__":
    raise SystemExit(main())
