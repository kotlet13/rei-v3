"""Preflight or execute controlled LongCat/FireRed C4 editor screen work.

The default mode is preflight-only and never imports Torch or Diffusers.  Real
GPU inference requires the explicit ``--execute`` flag.  The caller must also
select ``cell``, single-editor ``smoke`` or the explicit 24-editor-cell
``matrix`` mode.  No mode can grant semantic or production authority.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.emocio.artifacts import LocalPngArtifactStore, inspect_png  # noqa: E402
from rei.emocio.composite_editor import (  # noqa: E402
    CompositeEditorMember,
    CompositeEditorMemberResult,
    CompositeEditorRuntimeConfig,
    CompositeEditorScreenResult,
    LazyLocalCompositeEditorBackend,
    VerifiedEditorSnapshot,
    build_editor_renderer,
    render_composite_editor_screen,
    render_editor_member_screen,
)
from rei.emocio.firered_editor import (  # noqa: E402
    FIRERED_MODEL_ID,
    FIRERED_MODEL_REVISION,
    FireRedImageEditorBackend,
    firered_editor_runtime_config,
)
from rei.emocio.longcat_editor import (  # noqa: E402
    LONGCAT_MODEL_ID,
    LONGCAT_MODEL_REVISION,
    LongCatImageEditorBackend,
    longcat_editor_runtime_config,
)
from rei.emocio.packets import build_emocio_packet  # noqa: E402
from rei.emocio.prompting import (  # noqa: E402
    BilingualStructuredScenePromptCompiler,
    VisualPromptProfile,
)
from rei.emocio.renderer import RenderSettings, derive_scene_seed  # noqa: E402
from rei.emocio.scene_graph import compile_emocio_scenes  # noqa: E402
from rei.ids import canonical_json_bytes  # noqa: E402
from rei.models.emocio import EmocioWorld, ImageArtifact  # noqa: E402
from rei.models.rendering import (  # noqa: E402
    ImageRenderBatchOutcome,
    ImageSourceReference,
)
from rei.models.scene import (  # noqa: E402
    DecisionOption,
    EvidenceItem,
    SceneEvent,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STYLE_DIRECTIVES = {
    "documentary_cinematic_v1": (
        "Documentary cinematic still, restrained natural colors, stable identity "
        "and composition. No text, labels, logos, crowns, weapons, or extra people."
    ),
    "graphic_novel_v1": (
        "Restrained contemporary graphic-novel frame, clear spatial staging, stable "
        "identity and composition. No text, labels, logos, crowns, weapons, or extra "
        "people."
    ),
}
_MATRIX_SEEDS = (424240, 424241, 424242)
_MATRIX_LANGUAGES = ("en",)
_MATRIX_OPTION_ORDERS = ("canonical", "reversed")
_COMPACT_PROMPT_POLICY = "c4_editor_compact_v1"
_COMPACT_PROMPT_PREFIXES = (
    "evidence_boundary=",
    "language_gloss=",
    "localized_boundary=",
    "style_id=",
    "style_directive=",
    "style_basis=",
    "scene_data_boundary=",
    "PRIMARY IMAGE EDIT[",
    "primary_edit_execution=",
    "desired_scene_boundary=",
    "scene_kind[",
    "option_id[",
    "entities[",
    "composition[",
    "grounded_evidence_ids[",
    "inferred_elements[",
    "final_evidence_boundary=",
)
_PINNED_LONGCAT_PROMPT_TOKEN_AUDIT = {
    (
        "sl|documentary_cinematic_v1|"
        "visual_scene_acbc451d7b30336076e5c1e5bd31e02b"
    ): ("674270f5b12d8152ba299562d5445d67ab4605cc66af5dabde2ae694eabf710b", 489),
    (
        "sl|documentary_cinematic_v1|"
        "visual_scene_12e01b7dc48013135871ba28868f8180"
    ): ("4457c12722b635fa22724d032cbca4308bd3d56a93510e62c25046c8e302ebd3", 492),
    (
        "sl|graphic_novel_v1|visual_scene_acbc451d7b30336076e5c1e5bd31e02b"
    ): ("37d6ef9980bb1ebaab95a1ff57daade4628261a7ed5a7b75f83c29e5a872e3b9", 491),
    (
        "sl|graphic_novel_v1|visual_scene_12e01b7dc48013135871ba28868f8180"
    ): ("d554a4575db04f14b0f06bee1fc0762221a1e71538b9f02f341a509ed34260e8", 494),
    (
        "en|documentary_cinematic_v1|"
        "visual_scene_acbc451d7b30336076e5c1e5bd31e02b"
    ): ("3c046f45c9c66bc35e6c1b4890f24cc021e6c692d5ca6b7288951db6d2c54cba", 359),
    (
        "en|documentary_cinematic_v1|"
        "visual_scene_12e01b7dc48013135871ba28868f8180"
    ): ("a92224abe970e7deafef346085bc8751d76aea1d484f4268c66131a05c25c25e", 362),
    (
        "en|graphic_novel_v1|visual_scene_acbc451d7b30336076e5c1e5bd31e02b"
    ): ("0a5ca917cb44a1181cb045e36ba0623dad17179a2717638be64b829f29c6bd36", 361),
    (
        "en|graphic_novel_v1|visual_scene_12e01b7dc48013135871ba28868f8180"
    ): ("753f948e0d0b6a8815a47180584f1f5dbcfbcc4ff455080be05404b442da6f8e", 364),
}


class C4EditorScreenPromptCompiler(BilingualStructuredScenePromptCompiler):
    """Deterministic complete-segment prompt budget for the pinned editor screen."""

    def compile(self, scene) -> str:
        full_prompt = super().compile(scene)
        segments = full_prompt.split("; ")
        selected = tuple(
            segment
            for segment in segments
            if segment.startswith(_COMPACT_PROMPT_PREFIXES)
        )
        if len(selected) != len(_COMPACT_PROMPT_PREFIXES):
            raise ValueError("C4 compact prompt is missing a required semantic segment")
        final_boundary = selected[-1]
        return "; ".join(
            (
                *selected[:-1],
                f"prompt_budget_policy={_COMPACT_PROMPT_POLICY}",
                final_boundary,
            )
        )


def _verify_pinned_prompt_token_audit(compiled) -> tuple[dict[str, object], ...]:
    """Freeze the exact prompts whose pinned LongCat tokenizer counts were audited."""

    scenes = {scene.scene_id: scene for scene in compiled.option_rollouts}
    records: list[dict[str, object]] = []
    for key, (expected_sha256, token_count) in sorted(
        _PINNED_LONGCAT_PROMPT_TOKEN_AUDIT.items()
    ):
        language, style_id, scene_id = key.split("|", 2)
        scene = scenes.get(scene_id)
        if scene is None:
            raise ValueError("C4 prompt-token audit refers to an unknown rollout scene")
        _, compiler = _prompt_compiler(language, style_id)
        prompt = compiler.compile(scene)
        actual_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if actual_sha256 != expected_sha256 or token_count > 512:
            raise ValueError(
                "C4 compact prompt changed after its pinned tokenizer audit"
            )
        records.append(
            {
                "language": language,
                "style_id": style_id,
                "scene_id": scene_id,
                "prompt_sha256": actual_sha256,
                "token_count": token_count,
            }
        )
    return tuple(records)


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


def _print_utf8(value: str) -> None:
    sys.stdout.buffer.write(value.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def _sha256(value: str, field: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(f"{field} must be lowercase 64-hex SHA-256")
    return value


def _load_source_artifact(
    provenance_path: Path,
    *,
    expected_content_sha256: str,
) -> tuple[ImageArtifact, str]:
    """Load one canonical artifact or render batch and select the exact PNG."""

    provenance_bytes = provenance_path.read_bytes()
    try:
        schema_version = json.loads(provenance_bytes)["schema_version"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Source provenance JSON is invalid") from exc
    if schema_version == "rei-native-image-artifact-v1":
        artifact = ImageArtifact.model_validate_json(provenance_bytes)
        canonical = canonical_json_bytes(artifact)
    elif schema_version == "rei-native-image-render-batch-v1":
        batch = ImageRenderBatchOutcome.model_validate_json(provenance_bytes)
        canonical = canonical_json_bytes(batch)
        matches = tuple(
            artifact
            for artifact in batch.artifacts
            if artifact.content_sha256 == expected_content_sha256
        )
        if len(matches) != 1:
            raise ValueError("Source render batch must contain one exact PNG artifact")
        artifact = matches[0]
    else:
        raise ValueError("Source provenance JSON uses an unsupported schema")
    if provenance_bytes != canonical:
        raise ValueError("Source provenance JSON is not canonical")
    if artifact.content_sha256 != expected_content_sha256:
        raise ValueError("Source artifact SHA-256 differs from the explicit CLI pin")
    return artifact, hashlib.sha256(provenance_bytes).hexdigest()


def _ordered_rollouts(compiled, option_order: str):
    rollouts = compiled.option_rollouts
    return tuple(reversed(rollouts)) if option_order == "reversed" else rollouts


def _prompt_compiler(language: str, style_id: str):
    profile = VisualPromptProfile.create(
        language=language,
        style_id=style_id,
        style_directive=_STYLE_DIRECTIVES[style_id],
    )
    return profile, C4EditorScreenPromptCompiler(profile)


def _matrix_cells(compiled):
    for seed in _MATRIX_SEEDS:
        for language in _MATRIX_LANGUAGES:
            for style_id in _STYLE_DIRECTIVES:
                for option_order in _MATRIX_OPTION_ORDERS:
                    profile, compiler = _prompt_compiler(language, style_id)
                    rollouts = _ordered_rollouts(compiled, option_order)
                    key = (
                        f"seed-{seed}__lang-{language}__style-{style_id}"
                        f"__order-{option_order}"
                    )
                    yield (
                        key,
                        seed,
                        language,
                        style_id,
                        option_order,
                        profile,
                        compiler,
                        rollouts,
                    )


def _runtime_payload(torch, *, peak_gpu_memory_bytes: int) -> dict[str, object]:
    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "diffusers": importlib.metadata.version("diffusers"),
        "transformers": importlib.metadata.version("transformers"),
        "accelerate": importlib.metadata.version("accelerate"),
        "safetensors": importlib.metadata.version("safetensors"),
        "pillow": importlib.metadata.version("Pillow"),
        "cuda_runtime": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "gpu_compute_capability": tuple(torch.cuda.get_device_capability(0)),
        "peak_gpu_memory_bytes": peak_gpu_memory_bytes,
    }


def _run_member_cell(
    *,
    torch,
    cell_root: Path,
    config: CompositeEditorRuntimeConfig,
    snapshot: VerifiedEditorSnapshot,
    backend: LazyLocalCompositeEditorBackend,
    source_scene,
    source_artifact: ImageArtifact,
    source_png: bytes,
    option_rollouts,
    root_seed: int,
    prompt_compiler: BilingualStructuredScenePromptCompiler,
    num_inference_steps: int,
    guidance_scale: float,
    negative_prompt: str,
    timeout_seconds: float,
    cell_kind: str,
) -> tuple[CompositeEditorMemberResult, dict[str, object]]:
    if cell_root.exists():
        raise FileExistsError("Editor member cell directory already exists")
    store = LocalPngArtifactStore(cell_root / "artifacts")
    renderer = build_editor_renderer(
        config,
        backend=backend,
        artifact_store=store,
    )
    member = CompositeEditorMember(
        config=config,
        snapshot=snapshot,
        renderer=renderer,
        artifact_store=store,
    )
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    result = render_editor_member_screen(
        member=member,
        source_scene=source_scene,
        source_artifact=source_artifact,
        option_rollouts=option_rollouts,
        source_png=source_png,
        root_seed=root_seed,
        prompt_compiler=prompt_compiler,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        negative_prompt=negative_prompt,
        timeout_seconds=timeout_seconds,
    )
    elapsed_seconds = round(time.perf_counter() - started, 6)
    peak_gpu_memory_bytes = torch.cuda.max_memory_allocated()
    evidence = {
        "schema_version": "rei-c4-editor-member-cell-evidence-v1",
        "cell_kind": cell_kind,
        "technical_execution_passed": result.batch.status == "succeeded",
        "semantic_review_status": "requires_human_review",
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "provider_fallback_allowed": False,
        "elapsed_seconds": elapsed_seconds,
        "runtime": _runtime_payload(
            torch,
            peak_gpu_memory_bytes=peak_gpu_memory_bytes,
        ),
        "result": result,
    }
    _write_new(cell_root / "member_result.json", canonical_json_bytes(result))
    _write_new(cell_root / "execution_evidence.json", canonical_json_bytes(evidence))
    _print_utf8(
        json.dumps(
            {
                "cell_kind": cell_kind,
                "editor_id": result.editor_id,
                "root_seed": root_seed,
                "option_order": result.batch.source_spec_ids,
                "status": result.batch.status,
                "elapsed_seconds": elapsed_seconds,
                "peak_gpu_memory_bytes": peak_gpu_memory_bytes,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    return result, evidence


def _first_failure_code(result: CompositeEditorMemberResult) -> str | None:
    for item in result.batch.items:
        if item.failure_code is not None:
            return item.failure_code
    for item in result.batch.preparation_failures:
        return item.failure_code
    return None


def _matrix_failure(
    *,
    phase: str,
    editor: str | None,
    cell_key: str | None,
    failure_code: str,
    exception_type: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "rei-c4-editor-matrix-failure-v1",
        "phase": phase,
        "editor": editor,
        "cell_key": cell_key,
        "failure_code": failure_code,
        "exception_type": exception_type,
        "failure_message": f"C4 editor matrix failed closed ({failure_code})",
        "provider_fallback_allowed": False,
        "semantic_review_status": "requires_human_review",
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
    }


def _execute_matrix(
    *,
    torch,
    output: Path,
    source_scene,
    source_artifact: ImageArtifact,
    source_png: bytes,
    compiled,
    longcat_config: CompositeEditorRuntimeConfig,
    longcat_snapshot: VerifiedEditorSnapshot,
    longcat_backend: LazyLocalCompositeEditorBackend,
    firered_config: CompositeEditorRuntimeConfig,
    firered_snapshot: VerifiedEditorSnapshot,
    firered_backend: LazyLocalCompositeEditorBackend,
    settings: RenderSettings,
) -> int:
    cells = tuple(_matrix_cells(compiled))
    if len(cells) * 2 != 24:
        raise RuntimeError("Active English C4 matrix does not contain 24 editor cells")
    editor_results: dict[str, dict[str, CompositeEditorMemberResult]] = {}
    cell_evidence: list[dict[str, object]] = []
    editor_definitions = (
        ("longcat", longcat_config, longcat_snapshot, longcat_backend),
        ("firered", firered_config, firered_snapshot, firered_backend),
    )
    for editor_label, config, snapshot, backend in editor_definitions:
        results: dict[str, CompositeEditorMemberResult] = {}
        current_cell_key: str | None = None
        try:
            for (
                cell_key,
                seed,
                _language,
                _style_id,
                _option_order,
                _profile,
                compiler,
                rollouts,
            ) in cells:
                current_cell_key = cell_key
                result, evidence = _run_member_cell(
                    torch=torch,
                    cell_root=output / "members" / editor_label / cell_key,
                    config=config,
                    snapshot=snapshot,
                    backend=backend,
                    source_scene=source_scene,
                    source_artifact=source_artifact,
                    source_png=source_png,
                    option_rollouts=rollouts,
                    root_seed=seed,
                    prompt_compiler=compiler,
                    num_inference_steps=settings.num_inference_steps,
                    guidance_scale=settings.guidance_scale,
                    negative_prompt=settings.negative_prompt,
                    timeout_seconds=settings.timeout_seconds,
                    cell_kind="matrix",
                )
                results[cell_key] = result
                cell_evidence.append(evidence)
                if result.batch.status != "succeeded":
                    failure = _matrix_failure(
                        phase="editor_execution",
                        editor=editor_label,
                        cell_key=cell_key,
                        failure_code=(
                            _first_failure_code(result)
                            or "renderer_batch_failed"
                        ),
                    )
                    _write_new(
                        output / "matrix_failure.json",
                        canonical_json_bytes(failure),
                    )
                    return 1
        except Exception as exc:
            failure = _matrix_failure(
                phase="editor_execution",
                editor=editor_label,
                cell_key=current_cell_key,
                failure_code="editor_matrix_orchestration_failure",
                exception_type=type(exc).__name__,
            )
            _write_new(
                output / "matrix_failure.json",
                canonical_json_bytes(failure),
            )
            return 1
        finally:
            backend.release_pipeline()
            gc.collect()
            torch.cuda.empty_cache()
            _print_utf8(
                json.dumps(
                    {
                        "editor": editor_label,
                        "event": "pipeline_released",
                        "completed_cells": len(results),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        editor_results[editor_label] = results

    composite_records: list[dict[str, object]] = []
    source = ImageSourceReference.from_artifact_with_scene_lineage(source_artifact)
    try:
        for (
            cell_key,
            seed,
            language,
            style_id,
            option_order,
            profile,
            _compiler,
            rollouts,
        ) in cells:
            screen = CompositeEditorScreenResult.create(
                source=source,
                source_artifact=source_artifact,
                source_scene=source_scene,
                root_seed=seed,
                prompt_profile=profile,
                option_order=tuple(scene.scene_id for scene in rollouts),
                members=(
                    editor_results["longcat"][cell_key],
                    editor_results["firered"][cell_key],
                ),
            )
            cell_root = output / "composite" / cell_key
            evidence = {
                "schema_version": "rei-c4-composite-editor-matrix-cell-v1",
                "cell_key": cell_key,
                "language": language,
                "style_id": style_id,
                "option_order_mode": option_order,
                "technical_execution_passed": screen.technical_execution_passed,
                "semantic_review_status": "requires_human_review",
                "semantic_quality_gate_passed": False,
                "production_authority_granted": False,
                "generated_images_are_external_evidence": False,
                "result": screen,
            }
            _write_new(cell_root / "screen_result.json", canonical_json_bytes(screen))
            _write_new(cell_root / "execution_evidence.json", canonical_json_bytes(evidence))
            composite_records.append(
                {
                    "cell_key": cell_key,
                    "screen_id": screen.screen_id,
                    "root_seed": seed,
                    "language": language,
                    "style_id": style_id,
                    "option_order_mode": option_order,
                    "option_order": screen.option_order,
                    "member_batch_ids": tuple(
                        member.batch.batch_id for member in screen.members
                    ),
                    "result_path": (
                        Path("composite") / cell_key / "screen_result.json"
                    ).as_posix(),
                }
            )
    except Exception as exc:
        failure = _matrix_failure(
            phase="composite_validation",
            editor=None,
            cell_key=(cell_key if "cell_key" in locals() else None),
            failure_code="composite_matrix_validation_failure",
            exception_type=type(exc).__name__,
        )
        _write_new(output / "matrix_failure.json", canonical_json_bytes(failure))
        return 1

    peak_gpu_memory_bytes = max(
        int(item["runtime"]["peak_gpu_memory_bytes"])
        for item in cell_evidence
    )
    manifest = {
        "schema_version": "rei-c4-composite-editor-matrix-v1",
        "technical_execution_passed": True,
        "composite_cell_count": len(composite_records),
        "editor_cell_count": sum(
            len(results) for results in editor_results.values()
        ),
        "required_editor_cell_count": 24,
        "model_call_count": sum(
            len(result.batch.items)
            for results in editor_results.values()
            for result in results.values()
        ),
        "full_robustness_matrix_executed": True,
        "factors": {
            "editors": ("longcat", "firered"),
            "seeds": _MATRIX_SEEDS,
            "languages": _MATRIX_LANGUAGES,
            "styles": tuple(_STYLE_DIRECTIVES),
            "option_orders": _MATRIX_OPTION_ORDERS,
        },
        "prompt_budget_policy": _COMPACT_PROMPT_POLICY,
        "longcat_token_budget": 512,
        "source_artifact": source_artifact,
        "source": source,
        "cells": tuple(composite_records),
        "runtime": _runtime_payload(
            torch,
            peak_gpu_memory_bytes=peak_gpu_memory_bytes,
        ),
        "torch_dtype": "bfloat16",
        "model_cpu_offload_required": True,
        "local_files_only": True,
        "provider_fallback_allowed": False,
        "semantic_review_status": "requires_human_review",
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
    }
    _write_new(output / "matrix_manifest.json", canonical_json_bytes(manifest))
    _print_utf8((output / "matrix_manifest.json").read_text(encoding="utf-8"))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-png", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--source-provenance-json", type=Path, required=True)
    parser.add_argument("--longcat-snapshot-directory", type=Path, required=True)
    parser.add_argument("--longcat-snapshot-manifest-sha256", required=True)
    parser.add_argument("--firered-snapshot-directory", type=Path, required=True)
    parser.add_argument("--firered-snapshot-manifest-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--language", choices=("en",), default="en")
    parser.add_argument(
        "--style-id",
        choices=tuple(_STYLE_DIRECTIVES),
        default="documentary_cinematic_v1",
    )
    parser.add_argument(
        "--option-order",
        choices=("canonical", "reversed"),
        default="canonical",
    )
    parser.add_argument("--seed", type=int, default=424242)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--guidance-scale", type=float, default=4.5)
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help=(
            "Cooperative soft deadline checked around load/inference; it cannot "
            "hard-cancel a running Diffusers call. Explicitly required for matrix "
            "execution."
        ),
    )
    parser.add_argument(
        "--screen-mode",
        choices=("cell", "smoke", "matrix"),
        default="cell",
        help=(
            "Run one ordinary composite cell, one single-editor/one-option smoke, "
            "or the active English-only 24-editor-cell matrix."
        ),
    )
    parser.add_argument(
        "--smoke-editor",
        choices=("longcat", "firered"),
        help="Required only for --screen-mode smoke.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the selected GPU mode after preflight (default: no inference).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.screen_mode == "smoke" and args.smoke_editor is None:
        raise ValueError("--screen-mode smoke requires --smoke-editor")
    if args.screen_mode != "smoke" and args.smoke_editor is not None:
        raise ValueError("--smoke-editor is valid only with --screen-mode smoke")
    if args.execute and args.screen_mode == "matrix" and args.timeout_seconds is None:
        raise ValueError(
            "Matrix execution requires an explicit cooperative --timeout-seconds"
        )
    timeout_seconds = (
        3600.0 if args.timeout_seconds is None else args.timeout_seconds
    )
    expected_source_sha = _sha256(args.source_sha256, "source-sha256")
    longcat_manifest_sha = _sha256(
        args.longcat_snapshot_manifest_sha256,
        "longcat-snapshot-manifest-sha256",
    )
    firered_manifest_sha = _sha256(
        args.firered_snapshot_manifest_sha256,
        "firered-snapshot-manifest-sha256",
    )
    output = args.output_directory.expanduser().resolve()
    if output.exists():
        raise FileExistsError("Editor screen output directory already exists (create-only)")

    source_path = args.source_png.expanduser().resolve(strict=True)
    source_png = source_path.read_bytes()
    actual_source_sha = hashlib.sha256(source_png).hexdigest()
    if actual_source_sha != expected_source_sha:
        raise ValueError("Source PNG SHA-256 differs from the explicit CLI pin")
    source_width, source_height = inspect_png(source_png)
    provenance_path = args.source_provenance_json.expanduser().resolve(strict=True)
    source_artifact, source_provenance_sha = _load_source_artifact(
        provenance_path,
        expected_content_sha256=expected_source_sha,
    )
    settings = RenderSettings(
        width=source_width,
        height=source_height,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance_scale,
        negative_prompt=args.negative_prompt,
        timeout_seconds=timeout_seconds,
    )

    longcat_config = longcat_editor_runtime_config(
        snapshot_path=args.longcat_snapshot_directory,
        snapshot_manifest_sha256=longcat_manifest_sha,
    )
    firered_config = firered_editor_runtime_config(
        snapshot_path=args.firered_snapshot_directory,
        snapshot_manifest_sha256=firered_manifest_sha,
    )
    longcat_backend = LongCatImageEditorBackend(longcat_config)
    firered_backend = FireRedImageEditorBackend(firered_config)
    longcat_snapshot = longcat_backend.verify_snapshot()
    firered_snapshot = firered_backend.verify_snapshot()

    scene = _scene()
    world = _world()
    packet = build_emocio_packet(scene)
    compiled = compile_emocio_scenes(scene, packet, world)
    prompt_token_audit = _verify_pinned_prompt_token_audit(compiled)
    if (
        source_artifact.media_type != "image/png"
        or source_artifact.grounded is not False
        or (source_artifact.width, source_artifact.height)
        != (source_width, source_height)
        or source_artifact.source_spec_id != compiled.current_scene.scene_id
        or source_artifact.input_spec_hash != compiled.current_scene.content_hash()
    ):
        raise ValueError("Source artifact differs from the frozen current scene")
    rollouts = _ordered_rollouts(compiled, args.option_order)
    profile, compiler = _prompt_compiler(args.language, args.style_id)
    preflight_rollouts = rollouts[:1] if args.screen_mode == "smoke" else rollouts
    matrix_composite_cell_count = len(tuple(_matrix_cells(compiled)))
    matrix_editor_cell_count = matrix_composite_cell_count * 2
    matrix_model_call_count = matrix_editor_cell_count * len(rollouts)
    execution_cell_count = (
        matrix_editor_cell_count if args.screen_mode == "matrix" else 1
    )

    preflight = {
        "schema_version": "rei-c4-composite-editor-preflight-v1",
        "passed": True,
        "screen_mode": args.screen_mode,
        "smoke_editor": args.smoke_editor,
        "execution_requested": args.execute,
        "execution_cell_count": execution_cell_count,
        "full_robustness_matrix_required_cells": matrix_editor_cell_count,
        "full_robustness_matrix_executed": False,
        "source": {
            "artifact": source_artifact,
            "content_sha256": actual_source_sha,
            "width": source_width,
            "height": source_height,
            "scene_spec_id": compiled.current_scene.scene_id,
            "scene_spec_hash": compiled.current_scene.content_hash(),
            "provenance_container_sha256": source_provenance_sha,
        },
        "models": (
            {
                "model": LONGCAT_MODEL_ID,
                "revision": LONGCAT_MODEL_REVISION,
                "runtime": longcat_config,
                "snapshot": longcat_snapshot,
            },
            {
                "model": FIRERED_MODEL_ID,
                "revision": FIRERED_MODEL_REVISION,
                "runtime": firered_config,
                "snapshot": firered_snapshot,
            },
        ),
        "cell": {
            "root_seed": args.seed,
            "language": args.language,
            "style_id": args.style_id,
            "profile_hash": profile.content_hash(),
            "option_order_mode": args.option_order,
            "option_order": tuple(scene.option_id for scene in preflight_rollouts),
            "scene_seeds": tuple(
                derive_scene_seed(args.seed, rollout.scene_id)
                for rollout in preflight_rollouts
            ),
            "prompts": tuple(
                compiler.compile(rollout) for rollout in preflight_rollouts
            ),
            "prompt_character_counts": tuple(
                len(compiler.compile(rollout))
                for rollout in preflight_rollouts
            ),
            "render_settings": settings,
        },
        "prompt_budget_policy": _COMPACT_PROMPT_POLICY,
        "longcat_token_budget": 512,
        "pinned_longcat_prompt_token_audit": prompt_token_audit,
        "pinned_longcat_prompt_token_audit_hash": hashlib.sha256(
            canonical_json_bytes(prompt_token_audit)
        ).hexdigest(),
        "timeout_enforcement_mode": (
            "cooperative_before_and_after_load_and_inference_no_hard_cancellation"
        ),
        "matrix": (
            {
                "editor_cell_count": matrix_editor_cell_count,
                "composite_cell_count": matrix_composite_cell_count,
                "model_call_count": matrix_model_call_count,
                "seeds": _MATRIX_SEEDS,
                "languages": _MATRIX_LANGUAGES,
                "styles": tuple(_STYLE_DIRECTIVES),
                "option_orders": _MATRIX_OPTION_ORDERS,
            }
            if args.screen_mode == "matrix"
            else None
        ),
        "torch_dtype": "bfloat16",
        "model_cpu_offload_required": True,
        "local_files_only": True,
        "provider_fallback_allowed": False,
        "semantic_review_status": "requires_human_review",
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
    }
    output.mkdir(parents=True)
    _write_new(output / "preflight.json", canonical_json_bytes(preflight))
    _write_new(output / "scene.json", canonical_json_bytes(scene))
    _write_new(output / "emocio_world.json", canonical_json_bytes(world))
    _write_new(output / "emocio_packet.json", canonical_json_bytes(packet))
    _write_new(output / "compiled_scenes.json", canonical_json_bytes(compiled.all_scenes))

    if not args.execute:
        _print_utf8((output / "preflight.json").read_text(encoding="utf-8"))
        return 0

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("C4 editor screen execution requires a CUDA device")

    if args.screen_mode == "smoke":
        if args.smoke_editor == "longcat":
            smoke_config = longcat_config
            smoke_snapshot = longcat_snapshot
            smoke_backend = longcat_backend
        else:
            smoke_config = firered_config
            smoke_snapshot = firered_snapshot
            smoke_backend = firered_backend
        smoke_result, smoke_evidence = _run_member_cell(
            torch=torch,
            cell_root=output / args.smoke_editor,
            config=smoke_config,
            snapshot=smoke_snapshot,
            backend=smoke_backend,
            source_scene=compiled.current_scene,
            source_artifact=source_artifact,
            source_png=source_png,
            option_rollouts=rollouts[:1],
            root_seed=args.seed,
            prompt_compiler=compiler,
            num_inference_steps=settings.num_inference_steps,
            guidance_scale=settings.guidance_scale,
            negative_prompt=settings.negative_prompt,
            timeout_seconds=settings.timeout_seconds,
            cell_kind="fail_fast_smoke",
        )
        smoke_backend.release_pipeline()
        gc.collect()
        torch.cuda.empty_cache()
        summary = {
            "schema_version": "rei-c4-editor-fail-fast-smoke-v1",
            "editor": args.smoke_editor,
            "technical_execution_passed": smoke_result.batch.status == "succeeded",
            "failure_code": _first_failure_code(smoke_result),
            "semantic_review_status": "requires_human_review",
            "semantic_quality_gate_passed": False,
            "production_authority_granted": False,
            "generated_images_are_external_evidence": False,
            "provider_fallback_allowed": False,
            "execution": smoke_evidence,
        }
        _write_new(output / "smoke_result.json", canonical_json_bytes(summary))
        _print_utf8((output / "smoke_result.json").read_text(encoding="utf-8"))
        return 0 if smoke_result.batch.status == "succeeded" else 1

    if args.screen_mode == "matrix":
        return _execute_matrix(
            torch=torch,
            output=output,
            source_scene=compiled.current_scene,
            source_artifact=source_artifact,
            source_png=source_png,
            compiled=compiled,
            longcat_config=longcat_config,
            longcat_snapshot=longcat_snapshot,
            longcat_backend=longcat_backend,
            firered_config=firered_config,
            firered_snapshot=firered_snapshot,
            firered_backend=firered_backend,
            settings=settings,
        )

    torch.cuda.reset_peak_memory_stats()
    longcat_store = LocalPngArtifactStore(output / "longcat" / "artifacts")
    firered_store = LocalPngArtifactStore(output / "firered" / "artifacts")
    longcat_renderer = build_editor_renderer(
        longcat_config,
        backend=longcat_backend,
        artifact_store=longcat_store,
    )
    firered_renderer = build_editor_renderer(
        firered_config,
        backend=firered_backend,
        artifact_store=firered_store,
    )
    started = time.perf_counter()
    result = render_composite_editor_screen(
        members=(
            CompositeEditorMember(
                config=longcat_config,
                snapshot=longcat_snapshot,
                renderer=longcat_renderer,
                artifact_store=longcat_store,
            ),
            CompositeEditorMember(
                config=firered_config,
                snapshot=firered_snapshot,
                renderer=firered_renderer,
                artifact_store=firered_store,
            ),
        ),
        source_scene=compiled.current_scene,
        source_artifact=source_artifact,
        option_rollouts=rollouts,
        source_png=source_png,
        root_seed=args.seed,
        prompt_compiler=compiler,
        num_inference_steps=settings.num_inference_steps,
        guidance_scale=settings.guidance_scale,
        negative_prompt=settings.negative_prompt,
        timeout_seconds=settings.timeout_seconds,
    )
    elapsed_seconds = round(time.perf_counter() - started, 6)
    evidence = {
        "schema_version": "rei-c4-composite-editor-execution-evidence-v1",
        "technical_execution_passed": result.technical_execution_passed,
        "semantic_review_status": "requires_human_review",
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "full_robustness_matrix_executed": False,
        "elapsed_seconds": elapsed_seconds,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "diffusers": importlib.metadata.version("diffusers"),
            "transformers": importlib.metadata.version("transformers"),
            "accelerate": importlib.metadata.version("accelerate"),
            "safetensors": importlib.metadata.version("safetensors"),
            "pillow": importlib.metadata.version("Pillow"),
            "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "gpu_compute_capability": tuple(torch.cuda.get_device_capability(0)),
            "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(),
        },
        "result": result,
    }
    _write_new(output / "editor_screen_result.json", canonical_json_bytes(result))
    _write_new(output / "execution_evidence.json", canonical_json_bytes(evidence))
    _print_utf8((output / "execution_evidence.json").read_text(encoding="utf-8"))
    return 0 if result.technical_execution_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
