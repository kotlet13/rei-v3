"""TRIAD-VIS-O1 frozen Emocio render-observe evidence screen.

This research-only module freezes and renders four already approved E3 Emocio
route cases.  Rendered images are imagined artifacts only: they never enter
native valuation, a native conclusion, character replay, or governance.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from PIL import Image, ImageDraw

from ..emocio.artifacts import LocalPngArtifactStore
from ..emocio.diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersImageRenderer,
    DiffusersRuntimeConfig,
    LazyDiffusersBackend,
)
from ..emocio.prompting import (
    BilingualStructuredScenePromptCompiler,
    VisualPromptProfile,
)
from ..emocio.renderer import build_render_call_spec
from ..ids import canonical_json_bytes, content_id
from ..models.emocio import AttentionWeight, ImageArtifact, VisualSceneSpec
from ..models.provider import ProviderIdentity
from ..models.rendering import (
    ImageRenderBatchOutcome,
    ImageRenderRequest,
    ImageSourceReference,
)


EXPECTED_BASE_COMMIT: Final = "f416d4dc1a54a14fc29a4b94baf224c95feef7be"
SOURCE_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-e3-2026-07-24/"
    "execution_candidate.json"
)
EXPECTED_SOURCE_SHA256: Final = (
    "fb6ff1ed96b61ffedb6b4a2680e1b167cbc1384577862aa1f34c5be10d29739e"
)
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-o1-2026-07-24"
)
MODEL_ID: Final = "black-forest-labs/FLUX.2-klein-4B"
MODEL_REVISION: Final = "e7b7dc27f91deacad38e78976d1f2b499d76a294"
SNAPSHOT_MANIFEST_SHA256: Final = (
    "fb1ecb3a4d7fe439949b83f0e183438ab35a6df2bc01d66c5d3cd9966a4c7183"
)
CASE_ORDER: Final = (
    "public_credit_audience_visible",
    "public_credit_audience_absent",
    "factory_public_status_visible",
    "factory_public_status_anonymous",
)
PAIR_ORDER: Final = (
    (
        "public_credit_audience",
        "public_credit_audience_visible",
        "public_credit_audience_absent",
    ),
    (
        "factory_public_status",
        "factory_public_status_visible",
        "factory_public_status_anonymous",
    ),
)
SCENE_SEEDS: Final = {
    "current": 314159,
    "desired": 314160,
    "broken": 314161,
    "option_0": 314162,
    "option_1": 314163,
    "option_2": 314164,
}
WIDTH: Final = 512
HEIGHT: Final = 512
STEPS: Final = 4
GUIDANCE: Final = 1.0
TIMEOUT_SECONDS: Final = 600.0
NEGATIVE_PROMPT: Final = ""
STYLE_ID: Final = "documentary_cinematic_v1"
STYLE_DIRECTIVE: Final = (
    "Documentary cinematic still, restrained natural colors, stable identity "
    "and composition. No text, labels, logos, crowns, weapons, or extra people."
)
BANNED_PROMPT_TERMS: Final = (
    "expected option",
    "expected_option",
    "preferred",
    "safest",
    "winner",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _replace_json(path: Path, value: Any) -> None:
    payload = canonical_json_bytes(value)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


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


def _prompt_profile() -> VisualPromptProfile:
    return VisualPromptProfile.create(
        language="en",
        style_id=STYLE_ID,
        style_directive=STYLE_DIRECTIVE,
    )


def _runtime(snapshot: Path) -> DiffusersRuntimeConfig:
    return DiffusersRuntimeConfig(
        device="cuda",
        torch_dtype="bfloat16",
        local_files_only=True,
        variant=None,
        enable_attention_slicing=False,
        enable_model_cpu_offload=False,
        pipeline_family="flux2_klein",
        local_snapshot_path=str(snapshot),
        expected_snapshot_manifest_sha256=SNAPSHOT_MANIFEST_SHA256,
    )


def _load_cases(repository_root: Path) -> tuple[Mapping[str, Any], ...]:
    source_path = repository_root / SOURCE_RELATIVE_PATH
    if _file_sha256(source_path) != EXPECTED_SOURCE_SHA256:
        raise ValueError("Frozen E3 execution candidate SHA-256 changed")
    source = _json(source_path)
    observed: dict[str, Mapping[str, Any]] = {}
    for pair in source["pairs"]:
        for case in pair["variants"]:
            if case["case_id"] in CASE_ORDER:
                observed[case["case_id"]] = case
    if tuple(case_id for case_id in CASE_ORDER if case_id in observed) != CASE_ORDER:
        raise ValueError("Frozen E3 candidate does not contain the exact O1 cases")
    return tuple(observed[case_id] for case_id in CASE_ORDER)


def _attention(
    case_id: str,
    scene_key: str,
    option_id: str | None,
) -> tuple[AttentionWeight, ...]:
    public_credit = case_id.startswith("public_credit")
    visible = case_id.endswith("visible")
    if public_credit:
        values: dict[str, float]
        if scene_key == "current":
            values = {"colleague": 0.75, "self": 0.25}
        elif scene_key == "desired":
            values = {"colleague": 0.20, "self": 0.80}
        elif scene_key == "broken":
            values = {"colleague": 0.85, "self": 0.15}
        elif option_id == "credit_public_confront":
            values = {"colleague": 0.15, "repository_record": 0.35, "self": 0.70}
        elif option_id == "credit_private_evidence":
            values = {"leader": 0.45, "repository_record": 0.30, "self": 0.55}
        else:
            values = {"colleague": 0.80, "self": 0.20}
        if visible:
            values["project_team"] = 0.35
    else:
        if scene_key == "current":
            values = {"process_warning": 0.65, "self": 0.45}
        elif scene_key == "desired":
            values = {"process_controls": 0.45, "self": 0.70}
        elif scene_key == "broken":
            values = {"process_warning": 0.85, "self": 0.20}
        elif option_id == "factory_shutdown":
            values = {"self": 0.65, "stopped_process": 0.50}
        elif option_id == "factory_verify":
            values = {"conflicting_displays": 0.60, "self": 0.50}
        else:
            values = {"active_process": 0.65, "self": 0.45}
        if visible:
            values["shift_audience"] = 0.35
    return tuple(
        AttentionWeight(target=target, score=score)
        for target, score in sorted(values.items())
    )


def _entities(case_id: str) -> tuple[str, ...]:
    if case_id == "public_credit_audience_visible":
        return (
            "colleague",
            "leader",
            "repository record",
            "self",
            "shared projection",
            "six project-team members",
        )
    if case_id == "public_credit_audience_absent":
        return (
            "colleague",
            "leader",
            "repository record",
            "self",
            "shared projection",
        )
    if case_id == "factory_public_status_visible":
        return (
            "conflicting displays",
            "control console",
            "eight shift members",
            "plant manager",
            "rising gauge",
            "self",
        )
    return (
        "conflicting displays",
        "control console",
        "rising gauge",
        "self",
    )


def _scene_evidence_ids(
    case_id: str,
    scene_key: str,
    option: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if option is not None:
        return tuple(sorted(option["evidence_ids"]))
    if case_id.startswith("public_credit"):
        mapping = {
            "current": ("credit_ev_audience", "credit_ev_claim", "credit_ev_positions"),
            "desired": (
                "credit_ev_audience",
                "credit_ev_positions",
                "credit_ev_recognition",
                "credit_ev_record",
            ),
            "broken": ("credit_ev_claim", "credit_ev_positions"),
        }
    else:
        mapping = {
            "current": (
                "factory_ev_audience",
                "factory_ev_sensor",
                "factory_ev_status",
                "factory_ev_temperature",
            ),
            "desired": (
                "factory_ev_audience",
                "factory_ev_damage",
                "factory_ev_status",
            ),
            "broken": (
                "factory_ev_audience",
                "factory_ev_damage",
                "factory_ev_sensor",
                "factory_ev_temperature",
            ),
        }
    return tuple(sorted(mapping[scene_key]))


def _make_scene(
    case: Mapping[str, Any],
    *,
    scene_key: str,
    option: Mapping[str, Any] | None = None,
) -> VisualSceneSpec:
    case_id = case["case_id"]
    route = case["route_packets"]["emocio"]
    option_id = option["option_id"] if option is not None else None
    scene_kind = "option_rollout" if option is not None else scene_key
    if option is None:
        scene_text = route[f"{scene_key}_scene"]
    else:
        scene_text = option["change"]
    if scene_key == "current":
        self_position = route["self_position"]
    elif scene_key == "desired":
        self_position = "Self is centered within the explicitly envisioned desired scene."
    elif scene_key == "broken":
        self_position = "Self remains visible but displaced by the explicitly described obstacle."
    else:
        self_position = (
            f"Option-specific imagined placement only: {scene_text}"
        )
    attraction = route["attraction_enjoyment"]
    evidence_ids = _scene_evidence_ids(case_id, scene_key, option)
    payload = {
        "schema_version": "rei-native-visual-scene-spec-v1",
        "scene_kind": scene_kind,
        "option_id": option_id,
        "entities": _entities(case_id),
        "self_position": self_position,
        "attention_structure": _attention(case_id, scene_key, option_id),
        "group_belonging": route["audience"],
        "status_relations": (route["attention_recognition"],),
        "movement": (scene_text if option is not None else route["movement_immediacy"],),
        "composition": (scene_text,),
        "attraction_markers": () if attraction == "not_relevant" else (attraction,),
        "obstacle_markers": (route["rival_or_obstacle"],),
        "grounded_evidence_ids": evidence_ids,
        "inferred_elements": (scene_text,),
    }
    scene_id = content_id(
        "triad_vis_scene",
        {"case_id": case_id, "scene_key": scene_key, **payload},
    )
    return VisualSceneSpec(scene_id=scene_id, **payload)


def build_scene_plan(
    repository_root: Path,
) -> tuple[Mapping[str, Any], ...]:
    plan: list[Mapping[str, Any]] = []
    for case in _load_cases(repository_root):
        route = case["route_packets"]["emocio"]
        option_changes = {
            item["option_id"]: item for item in route["option_visible_changes"]
        }
        source_option_ids = tuple(
            sorted(item["option_id"] for item in case["operational_en"]["options"])
        )
        if tuple(sorted(option_changes)) != source_option_ids:
            raise ValueError("Emocio route does not cover canonical public option IDs")
        roles: list[tuple[str, VisualSceneSpec, int]] = [
            ("current", _make_scene(case, scene_key="current"), SCENE_SEEDS["current"]),
            ("desired", _make_scene(case, scene_key="desired"), SCENE_SEEDS["desired"]),
            ("broken", _make_scene(case, scene_key="broken"), SCENE_SEEDS["broken"]),
        ]
        for index, option_id in enumerate(source_option_ids):
            roles.append(
                (
                    f"option_{index}",
                    _make_scene(
                        case,
                        scene_key="option_rollout",
                        option=option_changes[option_id],
                    ),
                    SCENE_SEEDS[f"option_{index}"],
                )
            )
        for role, scene, seed in roles:
            plan.append(
                {
                    "case_id": case["case_id"],
                    "role": role,
                    "option_id": scene.option_id,
                    "seed": seed,
                    "scene": scene,
                }
            )
    if len(plan) != 24:
        raise ValueError("TRIAD-VIS-O1 requires exactly 24 frozen scenes")
    return tuple(plan)


def _prompt_trace(
    prompt: str,
    scene: VisualSceneSpec,
) -> tuple[Mapping[str, Any], ...]:
    items: list[Mapping[str, Any]] = []
    for fragment in prompt.split("; "):
        field = fragment.split("[", 1)[0].split("=", 1)[0]
        if field in {"style_id", "style_directive", "style_basis"}:
            status = "implementation_hypothesis"
            evidence_ids: tuple[str, ...] = ()
        elif field in {
            "entities",
            "self_position",
            "attention_structure",
            "group_belonging",
            "status_relations",
            "movement",
            "composition",
            "attraction_markers",
            "obstacle_markers",
            "inferred_elements",
            "PRIMARY IMAGE EDIT",
            "FINAL PRIMARY IMAGE EDIT",
        }:
            status = "inferred_from_frozen_emocio_route"
            evidence_ids = scene.grounded_evidence_ids
        elif field == "grounded_evidence_ids":
            status = "direct_source_evidence_identifiers"
            evidence_ids = scene.grounded_evidence_ids
        else:
            status = "implementation_neutral_render_contract"
            evidence_ids = ()
        items.append(
            {
                "scene_field": field,
                "prompt_fragment": fragment,
                "source_status": status,
                "source_evidence_ids": evidence_ids,
            }
        )
    if "; ".join(item["prompt_fragment"] for item in items) != prompt:
        raise ValueError("Prompt trace does not reconstruct the exact positive prompt")
    return tuple(items)


def _prior_evidence_inventory(repository_root: Path) -> tuple[Mapping[str, Any], ...]:
    root = repository_root / "Docs/evals/semantic_lab_v1"
    files: list[Mapping[str, Any]] = []
    for directory in sorted(root.glob("triad-*")):
        if directory.name == OUTPUT_RELATIVE_PATH.name:
            continue
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            files.append(
                {
                    "path": path.relative_to(repository_root).as_posix(),
                    "sha256": _file_sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    if not files:
        raise ValueError("No prior TRIAD evidence was found to freeze")
    return tuple(files)


def _validate_prior_inventory(
    repository_root: Path,
    inventory: Sequence[Mapping[str, Any]],
) -> None:
    for entry in inventory:
        path = repository_root / entry["path"]
        if (
            not path.is_file()
            or path.stat().st_size != entry["size_bytes"]
            or _file_sha256(path) != entry["sha256"]
        ):
            raise ValueError(f"Prior TRIAD evidence changed: {entry['path']}")


def _request_template(
    item: Mapping[str, Any],
    *,
    provider: ProviderIdentity,
    pipeline: Any,
    profile: VisualPromptProfile,
    prompt: str,
) -> Mapping[str, Any]:
    scene: VisualSceneSpec = item["scene"]
    mode = "text_to_image" if item["role"] == "current" else "image_to_image"
    payload = {
        "mode": mode,
        "source_spec_id": scene.scene_id,
        "source_spec_hash": scene.content_hash(),
        "provider": provider,
        "pipeline": pipeline,
        "seed": item["seed"],
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "width": WIDTH,
        "height": HEIGHT,
        "num_inference_steps": STEPS,
        "guidance_scale": GUIDANCE,
        "conditioning_method": "none" if mode == "text_to_image" else "reference_image",
        "source_image_binding": (
            None
            if mode == "text_to_image"
            else "exact_current_artifact_from_same_case_with_scene_lineage"
        ),
        "strength": None,
        "prompt_language": profile.language,
        "style_id": profile.style_id,
        "profile_hash": profile.content_hash(),
    }
    return {
        **payload,
        "template_hash": _sha256_bytes(canonical_json_bytes(payload)),
    }


def _portable_manifest_has_no_forbidden_prompt_terms(
    prompts: Sequence[Mapping[str, Any]],
) -> None:
    for item in prompts:
        lowered = item["positive_prompt"].lower()
        hits = tuple(term for term in BANNED_PROMPT_TERMS if term in lowered)
        if hits:
            raise ValueError(
                f"Prompt contains forbidden outcome language for {item['case_id']}: {hits}"
            )


def _render_components(
    snapshot: Path,
    artifact_root: Path,
) -> tuple[DiffusersImageRenderer, VisualPromptProfile]:
    runtime = _runtime(snapshot)
    backend = LazyDiffusersBackend(runtime)
    provider = DiffusersImageRenderer(
        identity=_provider_identity(),
        backend=backend,
        artifact_store=LocalPngArtifactStore(artifact_root),
    )
    return provider, _prompt_profile()


def seal(
    repository_root: Path,
    *,
    snapshot_directory: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    snapshot = snapshot_directory.resolve(strict=True)
    if subprocess.run(
        (
            "git",
            "merge-base",
            "--is-ancestor",
            EXPECTED_BASE_COMMIT,
            "HEAD",
        ),
        cwd=repository_root,
        check=False,
    ).returncode != 0:
        raise ValueError("Approved E3 HEAD is not an ancestor of the seal")
    if _git(repository_root, "status", "--short"):
        raise ValueError("TRIAD-VIS-O1 seal requires a clean worktree")
    output = repository_root / OUTPUT_RELATIVE_PATH
    if output.exists():
        raise FileExistsError("TRIAD-VIS-O1 output root already exists")
    manifest_path = snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    if _file_sha256(manifest_path) != SNAPSHOT_MANIFEST_SHA256:
        raise ValueError("Pinned FLUX.2 snapshot manifest SHA-256 changed")
    snapshot_manifest = _json(manifest_path)
    if (
        snapshot_manifest.get("repo_id") != MODEL_ID
        or snapshot_manifest.get("revision") != MODEL_REVISION
    ):
        raise ValueError("Pinned FLUX.2 snapshot identity changed")

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("TRIAD-VIS-O1 requires a CUDA renderer")
    runtime = _runtime(snapshot)
    if runtime.conditioning_method("image_to_image") != "reference_image":
        raise ValueError("Pinned renderer does not support repository-approved img2img")
    provider = _provider_identity()
    profile = _prompt_profile()
    compiler = BilingualStructuredScenePromptCompiler(profile)
    plan = build_scene_plan(repository_root)
    prompt_items: list[Mapping[str, Any]] = []
    expected: list[Mapping[str, Any]] = []
    for index, item in enumerate(plan, start=1):
        scene: VisualSceneSpec = item["scene"]
        prompt = compiler.compile(scene)
        mode = "text_to_image" if item["role"] == "current" else "image_to_image"
        pipeline = runtime.pipeline_spec(mode)
        template = _request_template(
            item,
            provider=provider,
            pipeline=pipeline,
            profile=profile,
            prompt=prompt,
        )
        prompt_items.append(
            {
                "call_index": index,
                "case_id": item["case_id"],
                "role": item["role"],
                "option_id": item["option_id"],
                "seed": item["seed"],
                "scene_spec": scene,
                "prompt_compilation_trace": _prompt_trace(prompt, scene),
                "positive_prompt": prompt,
                "negative_prompt": NEGATIVE_PROMPT,
                "prompt_language": profile.language,
                "style_id": profile.style_id,
                "profile_hash": profile.content_hash(),
                "request_template": template,
            }
        )
        expected.append(
            {
                "call_index": index,
                "case_id": item["case_id"],
                "role": item["role"],
                "option_id": item["option_id"],
                "seed": item["seed"],
                "mode": mode,
                "source_binding": template["source_image_binding"],
                "status": "expected_not_started",
            }
        )
    _portable_manifest_has_no_forbidden_prompt_terms(prompt_items)
    prior = _prior_evidence_inventory(repository_root)

    output.mkdir(parents=True)
    _write_new(
        output / "scene_prompt_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o1-scene-prompt-manifest-v1",
                "phase": "TRIAD-VIS-O1",
                "status": "frozen_before_first_render",
                "items": prompt_items,
            }
        ),
    )
    _write_new(
        output / "expected_call_ledger.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o1-expected-call-ledger-v1",
                "expected_calls": 24,
                "retries": 0,
                "fallbacks": 0,
                "entries": expected,
            }
        ),
    )
    _write_new(
        output / "prior_evidence_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o1-prior-evidence-manifest-v1",
                "items": prior,
            }
        ),
    )
    prompt_manifest_sha = _file_sha256(output / "scene_prompt_manifest.json")
    ledger_sha = _file_sha256(output / "expected_call_ledger.json")
    prior_sha = _file_sha256(output / "prior_evidence_manifest.json")
    seal_payload = {
        "schema_version": "triad-vis-o1-pre-call-seal-v1",
        "phase": "TRIAD-VIS-O1",
        "mode": "render_observe",
        "base_commit": EXPECTED_BASE_COMMIT,
        "seal_code_commit": _git(repository_root, "rev-parse", "HEAD"),
        "source_candidate_path": SOURCE_RELATIVE_PATH.as_posix(),
        "source_candidate_sha256": EXPECTED_SOURCE_SHA256,
        "case_order": CASE_ORDER,
        "scene_order_per_case": (
            "current",
            "desired",
            "broken",
            "option_0",
            "option_1",
            "option_2",
        ),
        "seed_schedule": SCENE_SEEDS,
        "scene_prompt_manifest_sha256": prompt_manifest_sha,
        "expected_call_ledger_sha256": ledger_sha,
        "prior_evidence_manifest_sha256": prior_sha,
        "all_prompts_frozen_before_first_render": True,
        "prompt_change_after_first_render_allowed": False,
        "provider": provider,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "snapshot_manifest_sha256": SNAPSHOT_MANIFEST_SHA256,
        "snapshot_manifest_file_count": len(snapshot_manifest["files"]),
        "pipeline_specs": {
            "text_to_image": runtime.pipeline_spec("text_to_image"),
            "image_to_image": runtime.pipeline_spec("image_to_image"),
        },
        "prompt_profile": profile,
        "render_parameters": {
            "width": WIDTH,
            "height": HEIGHT,
            "num_inference_steps": STEPS,
            "guidance_scale": GUIDANCE,
            "negative_prompt": NEGATIVE_PROMPT,
            "timeout_seconds": TIMEOUT_SECONDS,
            "current_conditioning": "none",
            "downstream_conditioning": "reference_image",
            "downstream_source": "exact_current_artifact_from_same_case",
            "strength": None,
        },
        "execution_policy": {
            "image_render_calls": 24,
            "text_model_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "character_replay": 0,
            "native_decision_influence": 0,
            "visual_valuation_authority": False,
            "image_selection": False,
        },
        "output_root": OUTPUT_RELATIVE_PATH.as_posix(),
        "private_thinking_persisted": False,
        "generated_images_are_external_evidence": False,
        "runtime_preflight": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "diffusers": importlib.metadata.version("diffusers"),
            "transformers": importlib.metadata.version("transformers"),
            "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "cuda_available": True,
            "model_cpu_offload": False,
        },
        "first_render_started": False,
    }
    _write_new(output / "pre_call_seal.json", canonical_json_bytes(seal_payload))
    return {
        "status": "sealed",
        "pre_call_seal_sha256": _file_sha256(output / "pre_call_seal.json"),
        "prompt_count": len(prompt_items),
        "image_render_calls_started": 0,
    }


def verify_seal(
    repository_root: Path,
    *,
    snapshot_directory: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    snapshot = snapshot_directory.resolve(strict=True)
    output = repository_root / OUTPUT_RELATIVE_PATH
    seal_value = _json(output / "pre_call_seal.json")
    if seal_value["base_commit"] != EXPECTED_BASE_COMMIT:
        raise ValueError("Unexpected TRIAD-VIS-O1 seal base")
    checks = {
        "source": _file_sha256(repository_root / SOURCE_RELATIVE_PATH)
        == EXPECTED_SOURCE_SHA256,
        "snapshot_manifest": _file_sha256(
            snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
        )
        == SNAPSHOT_MANIFEST_SHA256,
        "prompt_manifest": _file_sha256(output / "scene_prompt_manifest.json")
        == seal_value["scene_prompt_manifest_sha256"],
        "expected_ledger": _file_sha256(output / "expected_call_ledger.json")
        == seal_value["expected_call_ledger_sha256"],
        "prior_manifest": _file_sha256(output / "prior_evidence_manifest.json")
        == seal_value["prior_evidence_manifest_sha256"],
    }
    prior = _json(output / "prior_evidence_manifest.json")["items"]
    _validate_prior_inventory(repository_root, prior)
    prompts = _json(output / "scene_prompt_manifest.json")["items"]
    _portable_manifest_has_no_forbidden_prompt_terms(prompts)
    if len(prompts) != 24:
        raise ValueError("Seal does not freeze exactly 24 prompts")
    if not all(checks.values()):
        raise ValueError(f"TRIAD-VIS-O1 seal verification failed: {checks}")
    return {"status": "verified", "checks": checks, "prior_files": len(prior)}


def _request_from_manifest(
    prompt_item: Mapping[str, Any],
    *,
    provider: DiffusersImageRenderer,
    profile: VisualPromptProfile,
    source_image: ImageSourceReference | None,
) -> ImageRenderRequest:
    scene = VisualSceneSpec.model_validate(prompt_item["scene_spec"])
    mode = "text_to_image" if prompt_item["role"] == "current" else "image_to_image"
    request = ImageRenderRequest.create(
        mode=mode,
        source_spec=scene,
        provider=provider.identity,
        pipeline=provider.pipeline_spec(mode),
        seed=prompt_item["seed"],
        prompt=prompt_item["positive_prompt"],
        negative_prompt=prompt_item["negative_prompt"],
        width=WIDTH,
        height=HEIGHT,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE,
        source_image=source_image,
        strength=None,
        conditioning_method="none" if mode == "text_to_image" else "reference_image",
        prompt_language=profile.language,
        style_id=profile.style_id,
        profile_hash=profile.content_hash(),
    )
    request.validate_source_spec(scene)
    return request


def _ledger_entry(
    prompt_item: Mapping[str, Any],
    *,
    request: ImageRenderRequest,
    call: Any,
    status: str,
    outcome: Any | None = None,
    final_path: str | None = None,
) -> Mapping[str, Any]:
    value: dict[str, Any] = {
        "call_index": prompt_item["call_index"],
        "case_id": prompt_item["case_id"],
        "role": prompt_item["role"],
        "option_id": prompt_item["option_id"],
        "seed": prompt_item["seed"],
        "request_id": request.request_id,
        "request_hash": request.content_hash(),
        "call_id": call.call_id,
        "call_spec_hash": call.content_hash(),
        "status": status,
    }
    if outcome is not None:
        value["outcome"] = outcome
    if final_path is not None:
        value["repository_image_path"] = final_path
    return value


def _sheet(
    image_paths: Sequence[tuple[str, Path]],
    destination: Path,
    *,
    columns: int,
) -> None:
    cell_width = 256
    image_height = 256
    label_height = 30
    rows = (len(image_paths) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * cell_width, rows * (image_height + label_height)), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (label, path) in enumerate(image_paths):
        with Image.open(path) as source:
            rendered = source.convert("RGB").resize((cell_width, image_height))
        x = (index % columns) * cell_width
        y = (index // columns) * (image_height + label_height)
        canvas.paste(rendered, (x, y))
        draw.text((x + 6, y + image_height + 7), label, fill="black")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Contact sheet already exists: {destination}")
    canvas.save(destination, format="PNG", optimize=True)


def _report(
    manifest: Sequence[Mapping[str, Any]],
    pair_sheets: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# TRIAD-VIS-O1 — frozen Emocio render-observe evidence screen",
        "",
        "Status: **render-observe evidence only; awaiting human visual review**.",
        "",
        "The 24 images below are unselected imagined artifacts. They do not add "
        "grounded external facts, do not alter an Emocio conclusion, and had zero "
        "native-decision, character, governance, or Racio-vision influence. This is "
        "not a visual-valuation result, holdout, promotion result, G4 result, or "
        "image-native semantic acceptance.",
        "",
        "- Text-model calls: `0`",
        "- Image-render calls: `24`",
        "- Retries: `0`",
        "- Fallbacks: `0`",
        "- Character replay: `0`",
        "- Native decision influence: `0`",
        "- `private_thinking_persisted = false`",
        "",
        "Current scenes were rendered text-to-image. Desired, broken, and all three "
        "option-rollout scenes were rendered image-to-image from the exact current "
        "artifact of the same case using repository-pinned `reference_image` "
        "conditioning. Option A/B/C follows canonical option-ID order.",
        "",
        "## Pair comparison sheets",
        "",
    ]
    for pair in pair_sheets:
        lines.extend(
            [
                f"### {pair['pair_id']}",
                "",
                f"![{pair['pair_id']} comparison]({pair['path']})",
                "",
                f"- SHA-256: `{pair['sha256']}`",
                "",
            ]
        )
    by_case: dict[str, list[Mapping[str, Any]]] = {}
    for item in manifest:
        by_case.setdefault(item["case_id"], []).append(item)
    for case_id in CASE_ORDER:
        items = sorted(by_case[case_id], key=lambda value: value["call_index"])
        lines.extend(
            [
                f"## {case_id}",
                "",
                f"![{case_id} contact sheet](sheets/{case_id}.png)",
                "",
            ]
        )
        for item in items:
            title = item["role"]
            if item["option_id"] is not None:
                title += f" — `{item['option_id']}`"
            lines.extend(
                [
                    f"### {title}",
                    "",
                    f"![{case_id} {item['role']}]({item['repository_image_path_from_report']})",
                    "",
                    f"- Seed: `{item['seed']}`",
                    f"- Mode: `{item['mode']}`",
                    f"- Image SHA-256: `{item['final_image_sha256']}`",
                    f"- Image ID: `{item['image_id']}`",
                    f"- Request ID/hash: `{item['request_id']}` / `{item['request_hash']}`",
                    f"- Call ID: `{item['call_id']}`",
                    f"- Source image ID/hash: `{item['source_image_id'] or 'none'}` / "
                    f"`{item['source_image_sha256'] or 'none'}`",
                    f"- Conditioning: `{item['conditioning_method']}`; strength: "
                    f"`{item['strength']}`",
                    f"- Generated-only elements: `{', '.join(item['generated_only_elements'])}`",
                    f"- Grounded mask: `{item['grounded_mask_path'] or 'none'}`",
                    "",
                    "Human review (leave blank until reviewer assessment):",
                    "",
                    "- Scene fidelity — pass / fail / uncertain: ",
                    "- Self position correct: ",
                    "- Audience correct: ",
                    "- Attention correct: ",
                    "- Obstacle state correct: ",
                    "- Desired/broken distinction visible: ",
                    "- Option consequence visible: ",
                    "- Unsupported generated element: ",
                    "- Prompt predetermines option: ",
                    "- Image introduces cross-mind content: ",
                    "- Usable for later Racio vision screen: ",
                    "",
                ]
            )
    return "\n".join(lines)


def execute(
    repository_root: Path,
    *,
    snapshot_directory: Path,
    runtime_artifact_root: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    snapshot = snapshot_directory.resolve(strict=True)
    runtime_root = runtime_artifact_root.resolve()
    if runtime_root.exists():
        raise FileExistsError("Runtime artifact root must be create-only")
    if _git(repository_root, "status", "--short"):
        raise ValueError("Execution requires the committed, clean pre-call seal")
    verify_seal(repository_root, snapshot_directory=snapshot)
    output = repository_root / OUTPUT_RELATIVE_PATH
    prompts = _json(output / "scene_prompt_manifest.json")["items"]
    provider, profile = _render_components(snapshot, runtime_root)
    ledger_path = output / "call_ledger.json"
    _write_new(
        ledger_path,
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o1-call-ledger-v1",
                "expected_calls": 24,
                "attempted_calls": 0,
                "retries": 0,
                "fallbacks": 0,
                "entries": [],
            }
        ),
    )
    outcomes_by_case: dict[str, list[Any]] = {case_id: [] for case_id in CASE_ORDER}
    current_by_case: dict[str, ImageArtifact] = {}
    image_manifest: list[Mapping[str, Any]] = []
    for prompt_item in prompts:
        case_id = prompt_item["case_id"]
        current = current_by_case.get(case_id)
        source_reference = (
            None
            if prompt_item["role"] == "current"
            else ImageSourceReference.from_artifact_with_scene_lineage(current)
            if current is not None
            else None
        )
        if prompt_item["role"] != "current" and source_reference is None:
            raise RuntimeError("Current render failed; downstream img2img cannot be formed")
        request = _request_from_manifest(
            prompt_item,
            provider=provider,
            profile=profile,
            source_image=source_reference,
        )
        call = build_render_call_spec(request, timeout_seconds=TIMEOUT_SECONDS)
        ledger = _json(ledger_path)
        ledger["attempted_calls"] += 1
        ledger["entries"].append(
            _ledger_entry(
                prompt_item,
                request=request,
                call=call,
                status="started",
            )
        )
        _replace_json(ledger_path, ledger)
        outcome = provider.render(request, call=call)
        final_path: str | None = None
        if outcome.artifact is not None:
            artifact_bytes = provider.read_artifact_bytes(outcome.artifact)
            option_suffix = (
                f"_{prompt_item['option_id']}" if prompt_item["option_id"] else ""
            )
            relative = Path("images") / case_id / (
                f"{prompt_item['role']}{option_suffix}.png"
            )
            destination = output / relative
            _write_new(destination, artifact_bytes)
            if _file_sha256(destination) != outcome.artifact.content_sha256:
                raise ValueError("Copied repository image differs from provider artifact")
            final_path = (OUTPUT_RELATIVE_PATH / relative).as_posix()
            manifest_item = {
                "call_index": prompt_item["call_index"],
                "case_id": case_id,
                "role": prompt_item["role"],
                "option_id": prompt_item["option_id"],
                "scene_spec": prompt_item["scene_spec"],
                "prompt_compilation_trace": prompt_item["prompt_compilation_trace"],
                "positive_prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "prompt_language": request.prompt_language,
                "style_id": request.style_id,
                "profile_hash": request.profile_hash,
                "provider": request.provider,
                "pipeline": request.pipeline,
                "seed": request.seed,
                "width": request.width,
                "height": request.height,
                "num_inference_steps": request.num_inference_steps,
                "guidance_scale": request.guidance_scale,
                "mode": request.mode,
                "source_image_id": (
                    request.source_image.image_id if request.source_image else None
                ),
                "source_image_sha256": (
                    request.source_image.content_sha256 if request.source_image else None
                ),
                "source_image_scene_spec_id": (
                    request.source_image.originating_scene_spec_id
                    if request.source_image
                    else None
                ),
                "source_image_scene_spec_hash": (
                    request.source_image.originating_scene_spec_hash
                    if request.source_image
                    else None
                ),
                "conditioning_method": request.conditioning_method,
                "strength": request.strength,
                "request_id": request.request_id,
                "request_hash": request.content_hash(),
                "call_id": call.call_id,
                "call_spec_hash": call.content_hash(),
                "call_record": outcome.call_record,
                "image_id": outcome.artifact.image_id,
                "final_image_sha256": outcome.artifact.content_sha256,
                "repository_image_path": final_path,
                "repository_image_path_from_report": relative.as_posix(),
                "size_bytes": len(artifact_bytes),
                "generated_only_elements": outcome.artifact.generated_only_elements,
                "grounded_mask_path": outcome.artifact.grounded_mask_path,
                "generated_images_are_external_evidence": False,
                "native_decision_influence": 0,
            }
            image_manifest.append(manifest_item)
            if prompt_item["role"] == "current":
                current_by_case[case_id] = outcome.artifact
        outcomes_by_case[case_id].append(outcome)
        ledger = _json(ledger_path)
        ledger["entries"][-1] = _ledger_entry(
            prompt_item,
            request=request,
            call=call,
            status=outcome.call_record.status,
            outcome=outcome,
            final_path=final_path,
        )
        _replace_json(ledger_path, ledger)

    if len(image_manifest) != 24:
        raise RuntimeError("TRIAD-VIS-O1 did not produce all 24 actual images")
    for case_id in CASE_ORDER:
        items = tuple(outcomes_by_case[case_id])
        status = "succeeded" if all(item.artifact is not None for item in items) else "partial"
        batch = ImageRenderBatchOutcome.create(
            source_spec_ids=tuple(item.request.source_spec_id for item in items),
            root_seed=SCENE_SEEDS["current"],
            status=status,
            items=items,
            warnings=(
                "render_observe_only",
                "zero_native_decision_influence",
            ),
        )
        _write_new(
            output / "cases" / case_id / "render_batch.json",
            canonical_json_bytes(batch),
        )

    _write_new(
        output / "image_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o1-image-manifest-v1",
                "image_count": 24,
                "selection_performed": False,
                "private_thinking_persisted": False,
                "items": image_manifest,
            }
        ),
    )
    for case_id in CASE_ORDER:
        case_items = sorted(
            (item for item in image_manifest if item["case_id"] == case_id),
            key=lambda value: value["call_index"],
        )
        _sheet(
            tuple(
                (
                    item["role"]
                    if item["option_id"] is None
                    else f"{item['role']}: {item['option_id']}",
                    repository_root / item["repository_image_path"],
                )
                for item in case_items
            ),
            output / "sheets" / f"{case_id}.png",
            columns=3,
        )
    pair_sheets: list[Mapping[str, Any]] = []
    for pair_id, left, right in PAIR_ORDER:
        ordered: list[tuple[str, Path]] = []
        for case_id in (left, right):
            case_items = sorted(
                (item for item in image_manifest if item["case_id"] == case_id),
                key=lambda value: value["call_index"],
            )
            ordered.extend(
                (
                    f"{case_id}: {item['role']}",
                    repository_root / item["repository_image_path"],
                )
                for item in case_items
            )
        relative = Path("sheets") / f"{pair_id}_comparison.png"
        _sheet(ordered, output / relative, columns=6)
        pair_sheets.append(
            {
                "pair_id": pair_id,
                "path": relative.as_posix(),
                "sha256": _file_sha256(output / relative),
            }
        )
    _write_new(
        output / "sheet_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o1-sheet-manifest-v1",
                "case_sheet_count": 4,
                "pair_sheet_count": 2,
                "pair_sheets": pair_sheets,
                "case_sheets": [
                    {
                        "case_id": case_id,
                        "path": f"sheets/{case_id}.png",
                        "sha256": _file_sha256(
                            output / "sheets" / f"{case_id}.png"
                        ),
                    }
                    for case_id in CASE_ORDER
                ],
            }
        ),
    )
    _write_new(
        output / "report.md",
        _report(image_manifest, pair_sheets).encode("utf-8"),
    )
    summary = {
        "schema_version": "triad-vis-o1-summary-v1",
        "phase": "TRIAD-VIS-O1",
        "status": "complete_render_observe_screen_awaiting_human_review",
        "image_render_calls": 24,
        "successful_images": 24,
        "retries": 0,
        "fallbacks": 0,
        "text_model_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "visual_valuation_authority": False,
        "image_selection_performed": False,
        "private_thinking_persisted": False,
        "prior_evidence_unchanged": True,
        "all_prompts_frozen_before_first_render": True,
        "prompt_changed_after_first_render": False,
        "report_path": (OUTPUT_RELATIVE_PATH / "report.md").as_posix(),
    }
    _write_new(output / "summary.json", canonical_json_bytes(summary))
    return summary


def _contains_absolute_path(value: str) -> bool:
    return bool(
        re.search(r"(?:[A-Za-z]:[\\/]|/home/|/Users/|\\\\Users\\\\)", value)
    )


def _walk_private_keys(value: Any, path: str = "$") -> tuple[str, ...]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"thinking", "thoughts", "reasoning_content", "chain_of_thought"}:
                hits.append(f"{path}.{key}")
            hits.extend(_walk_private_keys(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_walk_private_keys(item, f"{path}[{index}]"))
    return tuple(hits)


def cold_verify(
    repository_root: Path,
    *,
    snapshot_directory: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    output = repository_root / OUTPUT_RELATIVE_PATH
    verify_seal(repository_root, snapshot_directory=snapshot_directory)
    ledger = _json(output / "call_ledger.json")
    manifest_value = _json(output / "image_manifest.json")
    items = manifest_value["items"]
    if ledger["attempted_calls"] != 24 or len(ledger["entries"]) != 24:
        raise ValueError("Cold verification requires exactly 24 render attempts")
    if len(items) != 24 or manifest_value["selection_performed"]:
        raise ValueError("Cold verification requires all 24 unselected images")
    prompt_manifest = {
        item["call_index"]: item
        for item in _json(output / "scene_prompt_manifest.json")["items"]
    }
    for item in items:
        path = repository_root / item["repository_image_path"]
        if _file_sha256(path) != item["final_image_sha256"]:
            raise ValueError(f"Image hash mismatch: {item['repository_image_path']}")
        frozen = prompt_manifest[item["call_index"]]
        if item["positive_prompt"] != frozen["positive_prompt"]:
            raise ValueError("Executed positive prompt differs from pre-call seal")
        if item["negative_prompt"] != frozen["negative_prompt"]:
            raise ValueError("Executed negative prompt differs from pre-call seal")
        if item["seed"] != frozen["seed"]:
            raise ValueError("Executed seed differs from pre-call seal")
        if item["role"] != "current":
            current = next(
                candidate
                for candidate in items
                if candidate["case_id"] == item["case_id"]
                and candidate["role"] == "current"
            )
            if (
                item["source_image_id"] != current["image_id"]
                or item["source_image_sha256"] != current["final_image_sha256"]
                or item["source_image_scene_spec_id"]
                != current["scene_spec"]["scene_id"]
            ):
                raise ValueError("Downstream image lacks exact current-scene lineage")
    for path in output.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".md"}:
            text = path.read_text(encoding="utf-8")
            if _contains_absolute_path(text):
                raise ValueError(f"Local absolute path persisted in {path.name}")
            if path.suffix.lower() == ".json":
                private_hits = _walk_private_keys(json.loads(text))
                if private_hits:
                    raise ValueError(f"Raw private-thinking keys persisted: {private_hits}")
    prior = _json(output / "prior_evidence_manifest.json")["items"]
    _validate_prior_inventory(repository_root, prior)
    summary = _json(output / "summary.json")
    expected_summary = {
        "image_render_calls": 24,
        "retries": 0,
        "fallbacks": 0,
        "text_model_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "private_thinking_persisted": False,
        "all_prompts_frozen_before_first_render": True,
        "prompt_changed_after_first_render": False,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            raise ValueError(f"Summary invariant failed: {key}")
    sheet_manifest = _json(output / "sheet_manifest.json")
    if (
        sheet_manifest["case_sheet_count"] != 4
        or sheet_manifest["pair_sheet_count"] != 2
    ):
        raise ValueError("Contact/comparison sheet coverage is incomplete")
    return {
        "status": "passed",
        "image_render_attempts": 24,
        "successful_images": 24,
        "text_model_calls": 0,
        "native_decision_influence": 0,
        "prior_evidence_files_verified": len(prior),
        "absolute_paths_found": 0,
        "raw_private_thinking_keys_found": 0,
    }


__all__ = [
    "CASE_ORDER",
    "EXPECTED_BASE_COMMIT",
    "EXPECTED_SOURCE_SHA256",
    "OUTPUT_RELATIVE_PATH",
    "SCENE_SEEDS",
    "build_scene_plan",
    "cold_verify",
    "execute",
    "seal",
    "verify_seal",
]
