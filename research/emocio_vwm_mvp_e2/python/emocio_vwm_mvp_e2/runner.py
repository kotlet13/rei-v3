"""One-shot execution of the frozen LPWM E2 technical-overfit protocol."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import traceback
from typing import Any

from .artifacts import (
    artifact_tree, artifact_tree_hash, copy_tree_exact, encode_mp4, make_contact_sheet,
    save_sequence_png, sha256, write_json,
)
from .preflight import preflight


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _installed_environment(torch: object, frozen: dict[str, str]) -> dict[str, Any]:
    versions: dict[str, str] = {}
    for package in frozen:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError(f"required package is absent: {package}") from exc
    for package, expected in frozen.items():
        actual = versions[package]
        if package in {"torch", "torchvision"}:
            if not actual.startswith(expected):
                raise RuntimeError(f"{package} {actual} differs from frozen {expected}")
        elif actual != expected:
            raise RuntimeError(f"{package} {actual} differs from frozen {expected}")
    freeze = subprocess.run(
        [os.fspath(Path(os.sys.executable)), "-m", "pip", "freeze", "--all"],
        capture_output=True, text=True, check=False, timeout=120,
    )
    if freeze.returncode != 0:
        raise RuntimeError("pip freeze failed before model construction")
    return {
        "schema_version": "rei-emocio-vwm-e2-exact-environment-v1",
        "python": os.sys.version,
        "executable": os.fspath(Path(os.sys.executable).resolve()),
        "packages": versions,
        "pip_freeze": sorted(line for line in freeze.stdout.splitlines() if line.strip()),
        "torch_version": torch.__version__,
        "torchvision_version": versions["torchvision"],
        "cuda_runtime": torch.version.cuda,
    }


def _cuda_smoke(torch: object) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    device = torch.device("cuda:0")
    name = torch.cuda.get_device_name(device)
    architectures = list(torch.cuda.get_arch_list())
    if "NVIDIA GeForce RTX 5090" not in name:
        raise RuntimeError(f"unexpected CUDA device: {name}")
    if "sm_120" not in architectures:
        raise RuntimeError(f"PyTorch architecture list lacks sm_120: {architectures}")
    torch.cuda.reset_peak_memory_stats(device)
    x = torch.randn(2, 3, 32, 32, device=device, requires_grad=True)
    conv = torch.nn.Conv2d(3, 8, 3, padding=1).to(device)
    optimizer = torch.optim.Adam(conv.parameters(), lr=1e-3)
    loss = conv(x).square().mean()
    if not bool(torch.isfinite(loss)):
        raise RuntimeError("CUDA convolution smoke loss is non-finite")
    loss.backward()
    optimizer.step()
    free_bytes, total_bytes = torch.cuda.mem_get_info(device)
    return {
        "schema_version": "rei-emocio-vwm-e2-cuda-smoke-v1",
        "status": "passed",
        "cuda_available": True,
        "device_name": name,
        "device_capability": list(torch.cuda.get_device_capability(device)),
        "torch_arch_list": architectures,
        "tensor": "passed",
        "convolution": "passed",
        "backward": "passed",
        "optimizer_step": "passed",
        "finite_loss": float(loss.detach().cpu().item()),
        "free_vram_bytes_after_smoke": free_bytes,
        "total_vram_bytes": total_bytes,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
    }


def _autocast(torch: object, precision: str) -> object:
    if precision == "bfloat16":
        return torch.autocast(device_type="cuda", dtype=torch.bfloat16)
    return nullcontext()


def _optimizer(torch: object, model: object, plan: dict[str, Any]) -> object:
    spec = plan["optimizer"]
    return torch.optim.Adam(
        model.parameters(), lr=spec["learning_rate"], betas=tuple(spec["betas"]),
        eps=spec["eps"], weight_decay=spec["weight_decay"],
    )


def _lpwm_smoke(
    torch: object, lpwm_root: Path, config: dict[str, Any], plan: dict[str, Any], precision: str,
) -> dict[str, Any]:
    from .model_adapter import build_model, canonical_state_hash, seed_everything, training_call

    device = torch.device("cuda:0")
    seed_everything(plan["determinism"]["seed"])
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    model = build_model(lpwm_root, config, device)
    initial_hash = canonical_state_hash(model)
    optimizer = _optimizer(torch, model, plan)
    sequence = torch.zeros((1, 24, 3, 128, 128), device=device)
    goal = torch.zeros((1, 3, 128, 128), device=device)
    with _autocast(torch, precision):
        output = training_call(model, sequence, goal, config["loss"])
        loss = output["loss_dict"]["loss"]
    if not bool(torch.isfinite(loss)):
        raise RuntimeError("LPWM synthetic smoke loss is non-finite")
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()
    record = {
        "schema_version": "rei-emocio-vwm-e2-lpwm-smoke-v1",
        "status": "passed",
        "precision": precision,
        "model_constructed": True,
        "synthetic_forward": "passed",
        "synthetic_loss": float(loss.detach().cpu().item()),
        "backward": "passed",
        "optimizer_step": "passed",
        "finite": True,
        "initial_state_sha256": initial_hash,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
    }
    del output, loss, optimizer, model, sequence, goal
    torch.cuda.empty_cache()
    return record


def _load_episodes(dataset_root: Path) -> dict[str, object]:
    from .visual_dataset import load_episode, opaque_episode_dirs

    return {path.name: load_episode(path) for path in opaque_episode_dirs(dataset_root)}


def _train(
    torch: object,
    lpwm_root: Path,
    dataset_root: Path,
    external_run_root: Path,
    config: dict[str, Any],
    plan: dict[str, Any],
    precision: str,
) -> tuple[object, dict[str, object], dict[str, Any]]:
    from .model_adapter import build_model, canonical_state_hash, seed_everything, training_call
    from .visual_dataset import frozen_training_order

    device = torch.device("cuda:0")
    seed = plan["determinism"]["seed"]
    seed_everything(seed)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    model = build_model(lpwm_root, config, device)
    initial_hash = canonical_state_hash(model)
    optimizer = _optimizer(torch, model, plan)
    episodes = _load_episodes(dataset_root)
    order = frozen_training_order(
        dataset_root, seed=seed, optimizer_steps=plan["optimizer_steps"],
    )
    measurements: list[dict[str, Any]] = []
    best_loss = None
    best_step = None
    best_path = external_run_root / "checkpoints" / "best_state_dict.pt"
    best_path.parent.mkdir(parents=True, exist_ok=True)
    steps_completed = 0
    model.train()
    for step, episode_dir in enumerate(order, start=1):
        episode = episodes[episode_dir.name]
        sequence = episode.sequence.unsqueeze(0).to(device, non_blocking=False)
        goal = episode.image_goal.unsqueeze(0).to(device, non_blocking=False)
        optimizer.zero_grad(set_to_none=True)
        with _autocast(torch, precision):
            output = training_call(model, sequence, goal, config["loss"])
            loss = output["loss_dict"]["loss"]
        if not bool(torch.isfinite(loss)):
            raise RuntimeError(f"non-finite training objective at optimizer step {step}")
        loss.backward()
        optimizer.step()
        steps_completed = step
        loss_value = float(loss.detach().cpu().item())
        if step == 1 or step % plan["evaluation_every_steps"] == 0:
            measurement = {
                "step": step,
                "opaque_episode_id": episode.opaque_id,
                "loss": loss_value,
                "psnr": float(output["loss_dict"]["psnr"].detach().cpu().item()),
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
            }
            measurements.append(measurement)
        if step % plan["evaluation_every_steps"] == 0 and (best_loss is None or loss_value < best_loss):
            best_loss = loss_value
            best_step = step
            torch.save(model.state_dict(), best_path)
        del output, loss, sequence, goal

    final_path = external_run_root / "checkpoints" / "final_state_dict.pt"
    torch.save(model.state_dict(), final_path)
    if best_step is None:
        raise RuntimeError("no frozen measurement boundary produced a best checkpoint")
    return model, episodes, {
        "schema_version": "rei-emocio-vwm-e2-training-run-v1",
        "status": "completed",
        "measured_run_count": 1,
        "seed": seed,
        "precision": precision,
        "optimizer_steps_required": plan["optimizer_steps"],
        "optimizer_steps_completed": steps_completed,
        "initial_state_sha256": initial_hash,
        "final_state_sha256": canonical_state_hash(model),
        "best_step": best_step,
        "best_measurement_loss": best_loss,
        "checkpoint_files": {
            "best": {"external_relative_path": "checkpoints/best_state_dict.pt", "sha256": sha256(best_path), "bytes": best_path.stat().st_size},
            "final": {"external_relative_path": "checkpoints/final_state_dict.pt", "sha256": sha256(final_path), "bytes": final_path.stat().st_size},
        },
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "measurements": measurements,
    }


def _sample_sequence(
    torch: object,
    model: object,
    episode: object,
    seed: int,
    deterministic: bool,
    *,
    goal_override: object | None = None,
) -> tuple[object, dict[str, Any]]:
    from .model_adapter import sample_call, seed_everything

    seed_everything(seed)
    device = torch.device("cuda:0")
    sequence = episode.sequence.unsqueeze(0).to(device)
    goal_source = episode.image_goal if goal_override is None else goal_override
    goal = goal_source.unsqueeze(0).to(device)
    with torch.no_grad():
        prediction, latents = sample_call(model, sequence, goal, deterministic=deterministic)
    return prediction[0].detach().cpu(), latents


def _route_index(dataset_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    records = [
        _read_json(path) for path in sorted((dataset_root / "evaluator" / "episodes").glob("*.json"))
    ]
    by_id = {record["episode_id"]: record for record in records}
    canonical: dict[str, str] = {}
    for route in ("public_reclaim", "private_evidence", "no_response"):
        options = sorted(
            record["episode_id"] for record in records
            if record["route"] == route and record["layout_variant"] == 0
        )
        canonical[route] = options[0]
    return by_id, canonical


def _generate_samples(
    torch: object,
    model: object,
    episodes: dict[str, object],
    dataset_root: Path,
    external_run_root: Path,
    sampling: dict[str, Any],
) -> tuple[dict[int, Path], dict[str, Any]]:
    model.eval()
    seed_roots: dict[int, Path] = {}
    for seed in sampling["distinct_sample_seeds"]:
        root = external_run_root / "samples" / f"seed_{seed}"
        for episode_id in sorted(episodes):
            sequence, _ = _sample_sequence(torch, model, episodes[episode_id], seed, False)
            save_sequence_png(sequence, root / episode_id)
        seed_roots[seed] = root

    _, canonical = _route_index(dataset_root)
    repeat_roots = []
    for repeat_index, seed in enumerate(sampling["repeat_sample_seeds"]):
        root = external_run_root / "repeat" / f"run_{repeat_index}"
        for episode_id in canonical.values():
            sequence, _ = _sample_sequence(torch, model, episodes[episode_id], seed, False)
            save_sequence_png(sequence, root / episode_id)
        repeat_roots.append(root)
    repeat_trees = [artifact_tree(root) for root in repeat_roots]
    repeat_equal = repeat_trees[0] == repeat_trees[1]
    if not repeat_equal:
        raise RuntimeError("fixed-seed repeat artifact trees differ")

    deterministic_root = external_run_root / "deterministic_goal"
    latent_records: dict[str, Any] = {}
    import numpy as np
    latent_arrays: dict[str, object] = {}
    for route, episode_id in canonical.items():
        sequence, latents = _sample_sequence(torch, model, episodes[episode_id], 83001, True)
        save_sequence_png(sequence, deterministic_root / episode_id)
        context = latents.get("z_context")
        obj_on = latents.get("z_obj_on")
        positions = latents.get("z_pos")
        if context is not None:
            array = context.detach().float().cpu().numpy()
            latent_arrays[f"{episode_id}_z_context"] = array
        active = None if obj_on is None else float((obj_on > 0.5).float().sum(-2).mean().cpu().item())
        coverage = None
        displacement = None
        if positions is not None:
            pos = positions.detach().float()
            coverage = float((pos.amax(dim=(-3, -2)) - pos.amin(dim=(-3, -2))).mean().cpu().item())
            displacement = float((pos[:, 1:] - pos[:, :-1]).square().sum(-1).sqrt().mean().cpu().item())
        latent_records[route] = {
            "opaque_episode_id": episode_id,
            "active_particle_count_mean": active,
            "particle_position_coverage": coverage,
            "particle_temporal_displacement": displacement,
            "particle_objectness_mean": None if obj_on is None else float(obj_on.float().mean().cpu().item()),
            "particle_objectness_std": None if obj_on is None else float(obj_on.float().std().cpu().item()),
            "latent_context_variance": None if context is None else float(context.float().var().cpu().item()),
        }
    latent_path = external_run_root / "latent_actions.npz"
    np.savez_compressed(latent_path, **latent_arrays)

    sensitivity_root = external_run_root / "goal_sensitivity"
    source_id = canonical["public_reclaim"]
    for goal_route, goal_id in canonical.items():
        source = episodes[source_id]
        sequence, _ = _sample_sequence(
            torch, model, source, 83021, False, goal_override=episodes[goal_id].image_goal,
        )
        save_sequence_png(sequence, sensitivity_root / goal_id)

    from PIL import Image
    import itertools
    def terminal_array(path: Path) -> object:
        return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    diversity: dict[str, Any] = {}
    for route, episode_id in canonical.items():
        terminals = [
            terminal_array(seed_roots[seed] / episode_id / "000023.png")
            for seed in sampling["distinct_sample_seeds"]
        ]
        distances = [float(np.abs(left - right).mean()) for left, right in itertools.combinations(terminals, 2)]
        diversity[route] = {
            "pair_count": len(distances),
            "mean_terminal_rgb_l1": float(np.mean(distances)),
            "min_terminal_rgb_l1": float(np.min(distances)),
            "max_terminal_rgb_l1": float(np.max(distances)),
        }
    sensitivity_terminals = [
        terminal_array(sensitivity_root / episode_id / "000023.png") for episode_id in canonical.values()
    ]
    sensitivity_distances = [
        float(np.abs(left - right).mean())
        for left, right in itertools.combinations(sensitivity_terminals, 2)
    ]

    return seed_roots, {
        "schema_version": "rei-emocio-vwm-e2-sampling-execution-v1",
        "distinct_seeds": sampling["distinct_sample_seeds"],
        "repeat_seeds": sampling["repeat_sample_seeds"],
        "fixed_seed_repeat_artifact_trees_equal": repeat_equal,
        "repeat_tree_hashes": [artifact_tree_hash(tree) for tree in repeat_trees],
        "canonical_episode_by_evaluator_route": canonical,
        "latent_action_external": {"path": "latent_actions.npz", "sha256": sha256(latent_path), "bytes": latent_path.stat().st_size},
        "particle_diagnostics": latent_records,
        "goal_sensitivity_source_episode": source_id,
        "goal_sensitivity_goal_episodes": canonical,
        "stochastic_diversity_diagnostics": diversity,
        "image_goal_sensitivity_diagnostics": {
            "pair_count": len(sensitivity_distances),
            "mean_terminal_rgb_l1": float(np.mean(sensitivity_distances)),
            "min_terminal_rgb_l1": float(np.min(sensitivity_distances)),
            "max_terminal_rgb_l1": float(np.max(sensitivity_distances)),
            "numeric_acceptance_threshold": None,
        },
        "self_anchor_ablation": "not_tested_unmodified_lpwm_has_no_dedicated_self_reference_slot",
    }


def _selection_objective(metrics: dict[str, float], gates: dict[str, float]) -> float:
    deficits = [
        max(0.0, (gates["identity_stability_min"] - metrics["identity_stability"]) / gates["identity_stability_min"]),
        max(0.0, (gates["person_count_accuracy_min"] - metrics["person_count_accuracy"]) / gates["person_count_accuracy_min"]),
        max(0.0, (metrics["duplicate_person_rate"] - gates["duplicate_person_rate_max"]) / gates["duplicate_person_rate_max"]),
        max(0.0, (metrics["foreground_lpips"] - gates["foreground_lpips_max"]) / gates["foreground_lpips_max"]),
        max(0.0, (gates["goal_marker_accuracy_min"] - metrics["goal_marker_accuracy"]) / gates["goal_marker_accuracy_min"]),
    ]
    return sum(deficits) + metrics["foreground_lpips"] / gates["foreground_lpips_max"]


def _evaluate_and_select(
    torch: object,
    dataset_root: Path,
    seed_roots: dict[int, Path],
    acceptance: dict[str, Any],
    external_run_root: Path,
) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    from .evaluator import evaluate_samples, hard_gate_results

    records = []
    for seed, root in sorted(seed_roots.items()):
        result = evaluate_samples(dataset_root, root, torch.device("cuda:0"))
        objective = _selection_objective(result["metrics"], acceptance["hard_gates"])
        records.append({"seed": seed, "objective": objective, "metrics": result["metrics"]})
        write_json(external_run_root / "seed_metrics" / f"{seed}.json", result)
    selected = min(records, key=lambda item: (item["objective"], item["seed"]))
    selected_result = _read_json(external_run_root / "seed_metrics" / f"{selected['seed']}.json")
    selected_result["hard_gates"] = hard_gate_results(selected_result["metrics"], acceptance)
    return selected["seed"], selected_result, records


def _build_payload(
    dataset_root: Path,
    external_run_root: Path,
    payload_root: Path,
    selected_seed: int,
    metrics: dict[str, Any],
    selection: list[dict[str, Any]],
    records: dict[str, Any],
) -> None:
    selected_source = external_run_root / "samples" / f"seed_{selected_seed}"
    copy_tree_exact(selected_source, payload_root / "samples" / "selected")
    _, canonical = _route_index(dataset_root)
    for episode_id in sorted(p.name for p in (payload_root / "samples" / "selected").iterdir() if p.is_dir()):
        encode_mp4(
            payload_root / "samples" / "selected" / episode_id,
            payload_root / "samples" / "selected_videos" / f"{episode_id}.mp4",
        )
    for seed in records["sampling"]["distinct_seeds"]:
        for episode_id in canonical.values():
            encode_mp4(
                external_run_root / "samples" / f"seed_{seed}" / episode_id,
                payload_root / "samples" / "stochastic_videos" / str(seed) / f"{episode_id}.mp4",
            )
    for goal_id in canonical.values():
        encode_mp4(
            external_run_root / "goal_sensitivity" / goal_id,
            payload_root / "samples" / "goal_sensitivity_videos" / f"{goal_id}.mp4",
        )
    terminal_images = [
        payload_root / "samples" / "selected" / episode_id / "000023.png"
        for episode_id in sorted(records["episodes"])
    ]
    make_contact_sheet(terminal_images, payload_root / "contact_sheets" / "selected_terminal_mosaic.png", columns=4)
    key_images = [
        payload_root / "samples" / "selected" / episode_id / f"{frame:06d}.png"
        for episode_id in canonical.values() for frame in (0, 5, 11, 17, 23)
    ]
    make_contact_sheet(key_images, payload_root / "contact_sheets" / "selected_key_mosaic.png", columns=5)
    stochastic_images = [
        external_run_root / "samples" / f"seed_{seed}" / episode_id / "000023.png"
        for seed in records["sampling"]["distinct_seeds"] for episode_id in canonical.values()
    ]
    make_contact_sheet(stochastic_images, payload_root / "contact_sheets" / "stochastic_terminal_mosaic.png", columns=3)
    deterministic_images = [
        external_run_root / "deterministic_goal" / episode_id / "000023.png" for episode_id in canonical.values()
    ]
    make_contact_sheet(deterministic_images, payload_root / "contact_sheets" / "image_goal_terminal_mosaic.png", columns=3)
    sensitivity_images = [
        external_run_root / "goal_sensitivity" / episode_id / "000023.png" for episode_id in canonical.values()
    ]
    make_contact_sheet(sensitivity_images, payload_root / "contact_sheets" / "goal_sensitivity_mosaic.png", columns=3)
    (payload_root / "model_outputs").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(external_run_root / "latent_actions.npz", payload_root / "model_outputs" / "latent_actions.npz")
    write_json(payload_root / "metrics" / "selected_visual_metrics.json", metrics)
    write_json(payload_root / "metrics" / "seed_selection_metrics.json", {
        "schema_version": "rei-emocio-vwm-e2-seed-selection-v1",
        "manual_selection": False,
        "selected_seed": selected_seed,
        "rule": "lowest mean normalized hard-gate deficit plus foreground_lpips; lowest seed tie-break",
        "candidates": selection,
    })
    write_json(payload_root / "metrics" / "particle_diagnostics.json", {
        "schema_version": "rei-emocio-vwm-e2-particle-diagnostics-v1",
        "numeric_acceptance_thresholds": None,
        "routes": records["sampling"]["particle_diagnostics"],
    })
    write_json(payload_root / "lineage" / "preflight.json", records["preflight"])
    write_json(payload_root / "lineage" / "environment_manifest.json", records["environment"])
    write_json(payload_root / "lineage" / "cuda_smoke.json", records["cuda_smoke"])
    write_json(payload_root / "lineage" / "lpwm_smoke.json", records["lpwm_smoke"])
    write_json(payload_root / "lineage" / "training_run.json", records["training"])
    write_json(payload_root / "lineage" / "sampling_run.json", records["sampling"])
    write_json(payload_root / "lineage" / "metric_weights.json", records["metric_weights"])
    write_json(payload_root / "model_outputs" / "selected_visual_path.json", {
        "schema_version": "rei-emocio-vwm-e2-selected-visual-path-v1",
        "native_output_is_natural_language": False,
        "selected_seed": selected_seed,
        "opaque_episode_ids": sorted(records["episodes"]),
        "key_mosaic": "contact_sheets/selected_key_mosaic.png",
        "terminal_mosaic": "contact_sheets/selected_terminal_mosaic.png",
    })
    from .boundary import validate_mp4, validate_png
    png_files = sorted((payload_root / "samples" / "selected").rglob("*.png"))
    mp4_files = sorted((payload_root / "samples").rglob("*.mp4"))
    for path in png_files:
        validate_png(path, width=128, height=128)
    for path in mp4_files:
        validate_mp4(path, width=128, height=128, fps=6, frame_count=24)
    write_json(payload_root / "metrics" / "generated_media_boundary_audit.json", {
        "schema_version": "rei-emocio-vwm-e2-generated-media-boundary-v1",
        "status": "passed",
        "png_files_checked": len(png_files),
        "mp4_files_checked": len(mp4_files),
        "ffprobe_stream_and_metadata_validation": "passed",
    })
    write_json(payload_root / "verdict.json", records["verdict"])


def _seal_result(payload_root: Path, result_root: Path) -> dict[str, Any]:
    if result_root.exists():
        raise RuntimeError("result root already exists; refusing to overwrite")
    with tempfile.TemporaryDirectory(prefix="emocio-e2-determinism-") as temporary:
        temp = Path(temporary)
        first = temp / "run_a"
        second = temp / "run_b"
        copy_tree_exact(payload_root, first)
        copy_tree_exact(payload_root, second)
        first_tree = artifact_tree(first)
        second_tree = artifact_tree(second)
        equal = first_tree == second_tree
        if not equal:
            raise RuntimeError("two-run artifact-tree determinism comparison failed")
        copy_tree_exact(first, result_root)
    comparison = {
        "schema_version": "rei-emocio-vwm-e2-artifact-tree-determinism-v1",
        "status": "passed",
        "runs": 2,
        "byte_identical": equal,
        "file_count_each": len(first_tree),
        "tree_sha256_a": artifact_tree_hash(first_tree),
        "tree_sha256_b": artifact_tree_hash(second_tree),
        "files": first_tree,
    }
    write_json(result_root / "artifact_tree_determinism.json", comparison)
    final_tree = artifact_tree(result_root)
    write_json(result_root / "result_bundle_manifest.json", {
        "schema_version": "rei-emocio-vwm-e2-result-bundle-v1",
        "file_count_before_manifest": len(final_tree),
        "bytes_before_manifest": sum(item["bytes"] for item in final_tree),
        "tree_sha256_before_manifest": artifact_tree_hash(final_tree),
    })
    return comparison


def _metric_weights(manifest_path: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    if manifest.get("acquisition") != "explicit_after_protocol_push" or len(manifest.get("files", [])) != 2:
        raise RuntimeError("metric weight manifest is absent or not explicitly acquired")
    cache = Path(os.environ.get("TORCH_HOME", "")) / "hub" / "checkpoints"
    for record in manifest["files"]:
        path = cache / record["name"]
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise RuntimeError(f"metric weight differs from explicit manifest: {record['name']}")
    return manifest


def execute(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    lpwm_root = Path(args.lpwm_root).resolve()
    dataset_root = Path(args.dataset_root).resolve()
    external_run_root = Path(args.external_run_root).resolve()
    result_root = Path(args.result_root).resolve()
    e2_root = repo_root / "research" / "emocio_vwm_mvp_e2"
    if repo_root not in result_root.parents:
        raise RuntimeError("result bundle must be inside the repository")
    if repo_root == external_run_root or repo_root in external_run_root.parents:
        raise RuntimeError("weights and raw execution must remain outside the repository")
    external_run_root.mkdir(parents=True, exist_ok=False)

    records: dict[str, Any] = {}
    stage = "preflight"
    try:
        records["preflight"] = preflight(repo_root, lpwm_root, dataset_root, args.protocol_commit)
        config = _read_json(e2_root / "specs" / "model_config.json")
        plan = _read_json(e2_root / "specs" / "execution_plan.json")
        sampling = _read_json(e2_root / "specs" / "sampling_plan.json")
        acceptance = _read_json(e2_root / "specs" / "acceptance.json")
        dependencies = _read_json(e2_root / "specs" / "dependency_manifest.json")

        stage = "environment_import"
        import torch
        records["environment"] = _installed_environment(torch, dependencies["packages"])
        write_json(external_run_root / "environment_manifest.json", records["environment"])
        stage = "cuda_smoke"
        records["cuda_smoke"] = _cuda_smoke(torch)
        write_json(external_run_root / "cuda_smoke.json", records["cuda_smoke"])
        torch.use_deterministic_algorithms(True)

        stage = "lpwm_smoke"
        precision = "float32"
        try:
            records["lpwm_smoke"] = _lpwm_smoke(torch, lpwm_root, config, plan, precision)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            precision = "bfloat16"
            records["lpwm_smoke"] = _lpwm_smoke(torch, lpwm_root, config, plan, precision)
            records["lpwm_smoke"]["oom_fallback_used"] = True
        write_json(external_run_root / "lpwm_smoke.json", records["lpwm_smoke"])

        stage = "measured_training"
        try:
            model, episodes, records["training"] = _train(
                torch, lpwm_root, dataset_root, external_run_root, config, plan, precision,
            )
        except torch.cuda.OutOfMemoryError:
            if precision == "float32":
                torch.cuda.empty_cache()
                precision = "bfloat16"
                model, episodes, records["training"] = _train(
                    torch, lpwm_root, dataset_root, external_run_root, config, plan, precision,
                )
                records["training"]["oom_fallback_used"] = True
            else:
                raise
        write_json(external_run_root / "training_run.json", records["training"])

        stage = "sampling"
        seed_roots, records["sampling"] = _generate_samples(
            torch, model, episodes, dataset_root, external_run_root, sampling,
        )
        write_json(external_run_root / "sampling_run.json", records["sampling"])

        stage = "metric_weights"
        records["metric_weights"] = _metric_weights(Path(args.metric_weights_manifest).resolve())
        stage = "evaluation"
        selected_seed, selected_metrics, selection = _evaluate_and_select(
            torch, dataset_root, seed_roots, acceptance, external_run_root,
        )
        records["episodes"] = sorted(episodes)
        all_passed = selected_metrics["hard_gates"]["all_passed"]
        records["verdict"] = {
            "schema_version": "rei-emocio-vwm-e2-verdict-v1",
            "verdict": "model_fit_promising" if all_passed else "model_fit_failed",
            "claim_scope": "technical_overfit_only",
            "full_frozen_budget_completed": True,
            "model_substitution": False,
            "threshold_changes": False,
            "lpwm_model_fit_beyond_e2_claimed": False,
            "working_emocio_claimed": False,
            "selected_seed": selected_seed,
            "hard_gates": selected_metrics["hard_gates"],
        }
        stage = "bundle"
        payload_root = external_run_root / "result_payload"
        _build_payload(
            dataset_root, external_run_root, payload_root, selected_seed,
            selected_metrics, selection, records,
        )
        _seal_result(payload_root, result_root)
        return 0
    except Exception as exc:
        failure_payload = external_run_root / "failure_payload"
        write_json(failure_payload / "verdict.json", {
            "schema_version": "rei-emocio-vwm-e2-verdict-v1",
            "verdict": "not_executed_resource_block",
            "claim_scope": "technical_overfit_only",
            "failed_stage": stage,
            "model_fit_failure_claimed": False,
            "medium_failure_claimed": False,
        })
        write_json(failure_payload / "failure.json", {
            "schema_version": "rei-emocio-vwm-e2-execution-failure-v1",
            "classification": "environment_or_execution_failure",
            "stage": stage,
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })
        for name, value in records.items():
            if isinstance(value, dict):
                write_json(failure_payload / "partial_lineage" / f"{name}.json", value)
        _seal_result(failure_payload, result_root)
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--lpwm-root", required=True)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--external-run-root", required=True)
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--protocol-commit", required=True)
    parser.add_argument("--metric-weights-manifest", required=True)
    return execute(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
