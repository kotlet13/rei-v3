"""One-shot execution of the frozen LPWM E2R remediation protocol."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
import traceback
from typing import Any
import warnings

# This assignment executes before any Torch or LPWM import in this module.
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

from emocio_vwm_mvp_e2.artifacts import (
    artifact_tree, artifact_tree_hash, copy_tree_exact, make_contact_sheet,
    save_sequence_png, sha256, write_json,
)
from emocio_vwm_mvp_e2.runner import (
    _autocast, _build_payload, _cuda_smoke, _evaluate_and_select,
    _generate_samples, _installed_environment, _load_episodes, _metric_weights,
    _optimizer, _route_index,
)

from .preflight import DATASET_TREE_SHA, ENVIRONMENT_SHA, preflight


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _warning_records(captured: list[object]) -> list[dict[str, Any]]:
    values = Counter(
        (item.category.__name__, str(item.message))  # type: ignore[attr-defined]
        for item in captured
    )
    return [
        {"category": category, "message": message, "count": count}
        for (category, message), count in sorted(values.items())
    ]


def _memory(torch: object, device: object) -> tuple[int, int]:
    return (
        int(torch.cuda.max_memory_allocated(device)),
        int(torch.cuda.max_memory_reserved(device)),
    )


def _gradient_norm(model: object) -> float:
    total = 0.0
    for parameter in model.parameters():
        if parameter.grad is not None:
            norm = float(parameter.grad.detach().float().norm(2).cpu().item())
            total += norm * norm
    return math.sqrt(total)


def _parameter_delta_norm(model: object, initial: dict[str, object]) -> float:
    total = 0.0
    for name, parameter in model.named_parameters():
        delta = parameter.detach().float().cpu() - initial[name]
        norm = float(delta.norm(2).item())
        total += norm * norm
    return math.sqrt(total)


def _run_smoke(
    torch: object,
    lpwm_root: Path,
    output_root: Path,
    config: dict[str, Any],
    plan: dict[str, Any],
    precision: str,
    smoke_index: int,
) -> dict[str, Any]:
    from emocio_vwm_mvp_e2.model_adapter import (
        build_model, canonical_state_hash, seed_everything, training_call,
    )

    output_root.mkdir(parents=True, exist_ok=False)
    record_path = output_root / "execution_record.json"
    device = torch.device("cuda:0")
    started = time.perf_counter()
    captured: list[object] = []
    model = None
    record: dict[str, Any] = {
        "schema_version": "rei-emocio-vwm-e2r-reproducibility-smoke-v1",
        "smoke_index": smoke_index,
        "evaluation_role": "non_evaluative_execution_smoke",
        "stage": "before_model_construction",
        "status": "running",
        "seed": plan["determinism"]["seed"],
        "precision": precision,
        "model_config_sha256": _json_hash(config),
        "environment_manifest_sha256": ENVIRONMENT_SHA,
        "dataset_tree_sha256": DATASET_TREE_SHA,
        "initial_state_sha256": None,
        "forward_status": "not_started",
        "finite_loss": None,
        "initial_loss": None,
        "backward_status": "not_started",
        "gradient_norm": None,
        "optimizer_step_count": 0,
        "post_step_state_sha256": None,
        "parameter_delta_norm": None,
        "captured_warnings": [],
        "peak_allocated_vram_bytes": 0,
        "peak_reserved_vram_bytes": 0,
        "exception": None,
    }
    write_json(record_path, record)
    try:
        seed_everything(record["seed"])
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        model = build_model(lpwm_root, config, device)
        initial_hash = canonical_state_hash(model)
        record.update(stage="model_constructed", initial_state_sha256=initial_hash)
        write_json(record_path, record)

        initial_parameters = {
            name: parameter.detach().float().cpu().clone()
            for name, parameter in model.named_parameters()
        }
        optimizer = _optimizer(torch, model, plan)
        sequence = torch.zeros((1, 24, 3, 128, 128), device=device)
        goal = torch.zeros((1, 3, 128, 128), device=device)
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")
            captured = warning_list
            record["stage"] = "forward"
            with _autocast(torch, precision):
                output = training_call(model, sequence, goal, config["loss"])
                loss = output["loss_dict"]["loss"]
            finite = bool(torch.isfinite(loss))
            record.update(
                stage="forward_complete",
                forward_status="passed",
                finite_loss=finite,
                initial_loss=float(loss.detach().float().cpu().item()),
            )
            write_json(record_path, record)
            if not finite:
                raise RuntimeError("LPWM E2R smoke loss is non-finite")

            optimizer.zero_grad(set_to_none=True)
            record["stage"] = "backward"
            write_json(record_path, record)
            loss.backward()
            record.update(stage="backward_complete", backward_status="passed")
            record["gradient_norm"] = _gradient_norm(model)
            write_json(record_path, record)

            record["stage"] = "optimizer_step"
            optimizer.step()
            record["optimizer_step_count"] = 1
            record["parameter_delta_norm"] = _parameter_delta_norm(model, initial_parameters)
            record["post_step_state_sha256"] = canonical_state_hash(model)
            checkpoint = output_root / "post_step_state_dict.pt"
            torch.save(model.state_dict(), checkpoint)
            record["post_step_checkpoint"] = {
                "external_relative_path": f"smokes/run_{smoke_index}/post_step_state_dict.pt",
                "bytes": checkpoint.stat().st_size,
                "sha256": sha256(checkpoint),
            }
            record.update(stage="completed", status="passed")
        return record
    except Exception as exc:
        record.update(
            status="failed",
            exception={
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        raise
    finally:
        record["captured_warnings"] = _warning_records(captured)
        record["duration_seconds"] = time.perf_counter() - started
        record["peak_allocated_vram_bytes"], record["peak_reserved_vram_bytes"] = _memory(torch, device)
        write_json(record_path, record)
        if model is not None:
            del model
        torch.cuda.empty_cache()


def _compare_smokes(torch: object, root: Path, first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    if first["initial_state_sha256"] != second["initial_state_sha256"]:
        raise RuntimeError("E2R smoke initial state hashes differ")
    for record in (first, second):
        if record["status"] != "passed" or record["backward_status"] != "passed":
            raise RuntimeError("E2R smoke backward did not pass")
        if record["optimizer_step_count"] != 1:
            raise RuntimeError("E2R smoke did not complete exactly one optimizer step")
        if not record["finite_loss"] or not math.isfinite(record["gradient_norm"]):
            raise RuntimeError("E2R smoke loss or gradient is non-finite")

    left = torch.load(root / "run_1" / "post_step_state_dict.pt", map_location="cpu", weights_only=True)
    right = torch.load(root / "run_2" / "post_step_state_dict.pt", map_location="cpu", weights_only=True)
    sum_sq = 0.0
    max_abs = 0.0
    compared = 0
    for name in sorted(left):
        if not left[name].is_floating_point():
            continue
        delta = left[name].float() - right[name].float()
        sum_sq += float(delta.square().sum().item())
        max_abs = max(max_abs, float(delta.abs().max().item()))
        compared += int(delta.numel())
    comparison = {
        "schema_version": "rei-emocio-vwm-e2r-smoke-comparison-v1",
        "status": "passed",
        "initial_state_hashes_equal": True,
        "post_step_hashes_equal": first["post_step_state_sha256"] == second["post_step_state_sha256"],
        "post_step_byte_identity_required": False,
        "numeric_difference": {
            "initial_loss_absolute": abs(first["initial_loss"] - second["initial_loss"]),
            "gradient_norm_absolute": abs(first["gradient_norm"] - second["gradient_norm"]),
            "parameter_delta_norm_absolute": abs(first["parameter_delta_norm"] - second["parameter_delta_norm"]),
            "post_step_state_l2": math.sqrt(sum_sq),
            "post_step_state_max_abs": max_abs,
            "floating_values_compared": compared,
        },
        "used_for_selection": False,
    }
    write_json(root / "comparison.json", comparison)
    del left, right
    return comparison


def _train(
    torch: object,
    lpwm_root: Path,
    dataset_root: Path,
    external_run_root: Path,
    config: dict[str, Any],
    plan: dict[str, Any],
    precision: str,
) -> tuple[object, dict[str, object], dict[str, Any]]:
    from emocio_vwm_mvp_e2.model_adapter import (
        build_model, canonical_state_hash, seed_everything, training_call,
    )
    from emocio_vwm_mvp_e2.visual_dataset import frozen_training_order

    device = torch.device("cuda:0")
    record_path = external_run_root / "measured_training_record.json"
    seed = plan["determinism"]["seed"]
    started = time.perf_counter()
    captured: list[object] = []
    model = None
    record: dict[str, Any] = {
        "schema_version": "rei-emocio-vwm-e2r-measured-training-v1",
        "stage": "before_model_construction",
        "status": "running",
        "measured_run_count": 1,
        "seed": seed,
        "precision": precision,
        "model_config_sha256": _json_hash(config),
        "environment_manifest_sha256": ENVIRONMENT_SHA,
        "dataset_tree_sha256": DATASET_TREE_SHA,
        "initial_state_sha256": None,
        "forward_status": "not_started",
        "finite_loss": None,
        "optimizer_steps_required": plan["optimizer_steps"],
        "optimizer_steps_completed": 0,
        "captured_warnings": [],
        "peak_allocated_vram_bytes": 0,
        "peak_reserved_vram_bytes": 0,
        "exception": None,
        "measurements": [],
        "checkpoints": [],
    }
    write_json(record_path, record)
    try:
        seed_everything(seed)
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        model = build_model(lpwm_root, config, device)
        record.update(stage="model_constructed", initial_state_sha256=canonical_state_hash(model))
        write_json(record_path, record)

        optimizer = _optimizer(torch, model, plan)
        episodes = _load_episodes(dataset_root)
        order = frozen_training_order(dataset_root, seed=seed, optimizer_steps=plan["optimizer_steps"])
        checkpoint_root = external_run_root / "checkpoints"
        checkpoint_root.mkdir(parents=True, exist_ok=True)
        best_loss = None
        best_step = None
        best_record = None
        model.train()
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")
            captured = warning_list
            for step, episode_dir in enumerate(order, start=1):
                episode = episodes[episode_dir.name]
                sequence = episode.sequence.unsqueeze(0).to(device, non_blocking=False)
                goal = episode.image_goal.unsqueeze(0).to(device, non_blocking=False)
                optimizer.zero_grad(set_to_none=True)
                record["stage"] = f"forward_step_{step}"
                with _autocast(torch, precision):
                    output = training_call(model, sequence, goal, config["loss"])
                    loss = output["loss_dict"]["loss"]
                finite = bool(torch.isfinite(loss))
                record.update(forward_status="passed", finite_loss=finite)
                if step == 1:
                    record["initial_loss"] = float(loss.detach().float().cpu().item())
                    write_json(record_path, record)
                if not finite:
                    raise RuntimeError(f"non-finite E2R training objective at optimizer step {step}")
                record["stage"] = f"backward_step_{step}"
                loss.backward()
                record["stage"] = f"optimizer_step_{step}"
                optimizer.step()
                record["optimizer_steps_completed"] = step
                loss_value = float(loss.detach().float().cpu().item())
                if step % plan["evaluation_every_steps"] == 0:
                    checkpoint = checkpoint_root / f"step_{step:04d}_state_dict.pt"
                    torch.save(model.state_dict(), checkpoint)
                    checkpoint_record = {
                        "step": step,
                        "external_relative_path": f"checkpoints/{checkpoint.name}",
                        "sha256": sha256(checkpoint),
                        "bytes": checkpoint.stat().st_size,
                    }
                    measurement = {
                        "step": step,
                        "opaque_episode_id": episode.opaque_id,
                        "loss": loss_value,
                        "psnr": float(output["loss_dict"]["psnr"].detach().float().cpu().item()),
                        "checkpoint_sha256": checkpoint_record["sha256"],
                        "peak_allocated_vram_bytes": int(torch.cuda.max_memory_allocated(device)),
                        "peak_reserved_vram_bytes": int(torch.cuda.max_memory_reserved(device)),
                    }
                    record["measurements"].append(measurement)
                    record["checkpoints"].append(checkpoint_record)
                    if best_loss is None or loss_value < best_loss:
                        best_loss, best_step, best_record = loss_value, step, checkpoint_record
                    record["captured_warnings"] = _warning_records(captured)
                    write_json(record_path, record)
                del output, loss, sequence, goal

        if record["optimizer_steps_completed"] != plan["optimizer_steps"]:
            raise RuntimeError("E2R measured run ended before the frozen budget")
        final_record = record["checkpoints"][-1]
        record.update(
            stage="completed",
            status="completed",
            final_state_sha256=canonical_state_hash(model),
            best_step=best_step,
            best_measurement_loss=best_loss,
            best_checkpoint=best_record,
            final_checkpoint=final_record,
        )
        return model, episodes, record
    except Exception as exc:
        record.update(
            status="failed",
            exception={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
        )
        if model is not None:
            del model
            model = None
        torch.cuda.empty_cache()
        raise
    finally:
        record["captured_warnings"] = _warning_records(captured)
        record["training_duration_seconds"] = time.perf_counter() - started
        record["peak_allocated_vram_bytes"], record["peak_reserved_vram_bytes"] = _memory(torch, device)
        write_json(record_path, record)


def _diagnostic_evidence(
    torch: object,
    model: object,
    episodes: dict[str, object],
    dataset_root: Path,
    payload_root: Path,
    config: dict[str, Any],
    precision: str,
) -> None:
    from emocio_vwm_mvp_e2.model_adapter import seed_everything, training_call
    from PIL import Image, ImageDraw
    import numpy as np

    _, canonical = _route_index(dataset_root)
    reconstruction_images: list[Path] = []
    mask_images: list[Path] = []
    particle_images: list[Path] = []
    model.eval()
    for route_index, episode_id in enumerate(canonical.values()):
        episode = episodes[episode_id]
        seed_everything(84001 + route_index)
        sequence = episode.sequence.unsqueeze(0).to("cuda:0")
        goal = episode.image_goal.unsqueeze(0).to("cuda:0")
        with torch.no_grad(), _autocast(torch, precision):
            output = training_call(model, sequence, goal, config["loss"])
        reconstruction = output["rec_rgb"]
        if reconstruction.ndim == 4:
            reconstruction = reconstruction.reshape(1, 24, *reconstruction.shape[1:])
        reconstruction = reconstruction[0]
        reconstruction_root = payload_root / "diagnostics" / "reconstruction" / episode_id
        save_sequence_png(reconstruction, reconstruction_root)

        alpha = output["alpha_masks"]
        if alpha.ndim == 5:
            alpha = alpha.reshape(1, 24, *alpha.shape[1:])
        union = alpha[0].amax(dim=1)
        union = torch.nn.functional.interpolate(
            union, size=(128, 128), mode="bilinear", align_corners=False,
        ).repeat(1, 3, 1, 1)
        mask_root = payload_root / "diagnostics" / "masks" / episode_id
        save_sequence_png(union, mask_root)

        positions = output["mu_tot"][0].detach().float().cpu().numpy()
        source = episode.sequence.detach().float().cpu().permute(0, 2, 3, 1).numpy()
        particle_root = payload_root / "diagnostics" / "particles" / episode_id
        particle_root.mkdir(parents=True, exist_ok=True)
        for frame_index in range(24):
            image = Image.fromarray(np.rint(np.clip(source[frame_index], 0, 1) * 255).astype(np.uint8), mode="RGB")
            draw = ImageDraw.Draw(image)
            for x_value, y_value in positions[frame_index]:
                x = int(round((float(x_value) + 1.0) * 63.5))
                y = int(round((float(y_value) + 1.0) * 63.5))
                if 0 <= x < 128 and 0 <= y < 128:
                    draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(255, 40, 180))
            image.save(particle_root / f"{frame_index:06d}.png", optimize=False)

        for frame_index in (0, 5, 11, 17, 23):
            reconstruction_images.append(reconstruction_root / f"{frame_index:06d}.png")
            mask_images.append(mask_root / f"{frame_index:06d}.png")
            particle_images.append(particle_root / f"{frame_index:06d}.png")
        del output, sequence, goal, reconstruction, alpha, union
    make_contact_sheet(reconstruction_images, payload_root / "contact_sheets" / "reconstruction_mosaic.png", columns=5)
    make_contact_sheet(mask_images, payload_root / "contact_sheets" / "mask_mosaic.png", columns=5)
    make_contact_sheet(particle_images, payload_root / "contact_sheets" / "particle_mosaic.png", columns=5)


def _blind_material(payload_root: Path, template: Path) -> None:
    source = payload_root / "samples" / "selected_videos"
    videos = sorted(source.glob("*.mp4"), key=lambda path: hashlib.sha256(f"91017:{path.name}".encode()).hexdigest())
    clips = []
    for index, video in enumerate(videos):
        target = payload_root / "blind_review" / "clips" / f"clip_{index:03d}.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(video, target)
        clips.append({"clip": target.name, "bytes": target.stat().st_size, "sha256": sha256(target)})
    shutil.copyfile(template, payload_root / "blind_review" / "review_form.md")
    write_json(payload_root / "blind_review" / "review_material_manifest.json", {
        "schema_version": "rei-emocio-vwm-e2r-blind-review-material-v1",
        "sealed": True,
        "route_mapping_in_review_material": False,
        "clips": clips,
    })


def _seal_result(payload_root: Path, result_root: Path) -> dict[str, Any]:
    if result_root.exists():
        raise RuntimeError("E2R result root already exists; refusing to overwrite")
    with tempfile.TemporaryDirectory(prefix="emocio-e2r-determinism-") as temporary:
        first = Path(temporary) / "run_a"
        second = Path(temporary) / "run_b"
        copy_tree_exact(payload_root, first)
        copy_tree_exact(payload_root, second)
        first_tree = artifact_tree(first)
        second_tree = artifact_tree(second)
        if first_tree != second_tree:
            raise RuntimeError("E2R two-run artifact-tree comparison failed")
        copy_tree_exact(first, result_root)
    comparison = {
        "schema_version": "rei-emocio-vwm-e2r-artifact-tree-determinism-v1",
        "status": "passed",
        "runs": 2,
        "byte_identical": True,
        "scope": "evaluator_and_media_artifact_pipeline_not_model_optimization",
        "file_count_each": len(first_tree),
        "tree_sha256_a": artifact_tree_hash(first_tree),
        "tree_sha256_b": artifact_tree_hash(second_tree),
        "files": first_tree,
    }
    write_json(result_root / "artifact_tree_determinism.json", comparison)
    final_tree = artifact_tree(result_root)
    write_json(result_root / "result_bundle_manifest.json", {
        "schema_version": "rei-emocio-vwm-e2r-result-bundle-v1",
        "file_count_before_manifest": len(final_tree),
        "bytes_before_manifest": sum(item["bytes"] for item in final_tree),
        "tree_sha256_before_manifest": artifact_tree_hash(final_tree),
    })
    return comparison


def _failure_payload(external_run_root: Path, stage: str, exc: Exception, records: dict[str, Any]) -> Path:
    payload = external_run_root / "failure_payload"
    write_json(payload / "verdict.json", {
        "schema_version": "rei-emocio-vwm-e2r-verdict-v1",
        "verdict": "not_executed_resource_block",
        "claim_scope": "technical_overfit_only",
        "failed_stage": stage,
        "full_frozen_budget_completed": False,
        "model_fit_failure_claimed": False,
        "medium_failure_claimed": False,
    })
    write_json(payload / "failure.json", {
        "schema_version": "rei-emocio-vwm-e2r-execution-failure-v1",
        "classification": "environment_or_execution_failure",
        "stage": stage,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    })
    for name, value in records.items():
        if isinstance(value, dict):
            write_json(payload / "partial_lineage" / f"{name}.json", value)
    for relative in (
        "environment_manifest.json", "cuda_smoke.json", "smokes/run_1/execution_record.json",
        "smokes/run_2/execution_record.json", "smokes/comparison.json", "measured_training_record.json",
    ):
        source = external_run_root / relative
        if source.is_file():
            target = payload / "execution_evidence" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    return payload


def execute(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    lpwm_root = Path(args.lpwm_root).resolve()
    dataset_root = Path(args.dataset_root).resolve()
    external_run_root = Path(args.external_run_root).resolve()
    result_root = Path(args.result_root).resolve()
    e2_root = repo_root / "research" / "emocio_vwm_mvp_e2"
    if repo_root not in result_root.parents:
        raise RuntimeError("E2R result bundle must be inside the repository")
    if repo_root == external_run_root or repo_root in external_run_root.parents:
        raise RuntimeError("weights and raw E2R execution must remain outside the repository")
    external_run_root.mkdir(parents=True, exist_ok=False)

    records: dict[str, Any] = {}
    stage = "preflight"
    try:
        records["preflight"] = preflight(repo_root, lpwm_root, dataset_root, args.protocol_commit)
        config = _read_json(e2_root / "specs" / "model_config.json")
        plan = _read_json(repo_root / "research" / "emocio_vwm_mvp_e2r" / "specs" / "execution_plan.json")
        sampling = _read_json(e2_root / "specs" / "sampling_plan.json")
        acceptance = _read_json(e2_root / "specs" / "acceptance.json")
        dependencies = _read_json(e2_root / "specs" / "dependency_manifest.json")

        stage = "environment_import"
        if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
            raise RuntimeError("CUBLAS_WORKSPACE_CONFIG was not set before Torch import")
        import torch
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        records["determinism_policy"] = {
            "schema_version": "rei-emocio-vwm-e2r-determinism-policy-v1",
            "CUBLAS_WORKSPACE_CONFIG": os.environ["CUBLAS_WORKSPACE_CONFIG"],
            "torch_deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "warn_only": True,
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "grid_sample_backward_potentially_nondeterministic": True,
            "bitwise_model_optimization_reproducibility_claimed": False,
        }
        environment = _installed_environment(torch, dependencies["packages"])
        executable = Path(environment["executable"]).resolve()
        environment["executable"] = executable.relative_to(lpwm_root).as_posix()
        environment["executable_scope"] = "external_lpwm_environment_relative"
        records["environment"] = environment
        environment_path = external_run_root / "environment_manifest.json"
        write_json(environment_path, environment)
        if sha256(environment_path) != ENVIRONMENT_SHA:
            raise RuntimeError("exact E2 environment manifest hash differs")

        stage = "cuda_smoke"
        records["cuda_smoke"] = _cuda_smoke(torch)
        write_json(external_run_root / "cuda_smoke.json", records["cuda_smoke"])

        stage = "reproducibility_smokes"
        precision = "float32"
        try:
            first = _run_smoke(torch, lpwm_root, external_run_root / "smokes" / "run_1", config, plan, precision, 1)
        except torch.cuda.OutOfMemoryError:
            precision = "bfloat16"
            fallback = external_run_root / "smokes" / "float32_oom_attempt"
            (external_run_root / "smokes" / "run_1").rename(fallback)
            first = _run_smoke(torch, lpwm_root, external_run_root / "smokes" / "run_1", config, plan, precision, 1)
        second = _run_smoke(torch, lpwm_root, external_run_root / "smokes" / "run_2", config, plan, precision, 2)
        records["smoke_1"] = first
        records["smoke_2"] = second
        records["smoke_comparison"] = _compare_smokes(torch, external_run_root / "smokes", first, second)

        stage = "measured_training"
        try:
            model, episodes, records["training"] = _train(
                torch, lpwm_root, dataset_root, external_run_root, config, plan, precision,
            )
        except torch.cuda.OutOfMemoryError:
            partial = _read_json(external_run_root / "measured_training_record.json")
            if precision != "float32" or partial["optimizer_steps_completed"] != 0:
                raise
            failed = external_run_root / "float32_oom_measured_training_record.json"
            shutil.move(external_run_root / "measured_training_record.json", failed)
            torch.cuda.empty_cache()
            precision = "bfloat16"
            model, episodes, records["training"] = _train(
                torch, lpwm_root, dataset_root, external_run_root, config, plan, precision,
            )
            records["training"]["oom_fallback_used"] = True
        if records["training"]["optimizer_steps_completed"] != 1200:
            raise RuntimeError("E2R measured run did not complete all 1200 optimizer steps")
        if records["training"]["initial_state_sha256"] != first["initial_state_sha256"]:
            raise RuntimeError("measured model initial state differs from frozen smoke initialization")

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
            "schema_version": "rei-emocio-vwm-e2r-verdict-v1",
            "verdict": "model_fit_promising" if all_passed else "model_fit_failed",
            "claim_scope": "technical_overfit_only",
            "full_frozen_budget_completed": True,
            "model_substitution": False,
            "threshold_changes": False,
            "social_model_fit_started": False,
            "working_emocio_claimed": False,
            "selected_visual_sample_seed": selected_seed,
            "hard_gates": selected_metrics["hard_gates"],
        }

        stage = "bundle"
        payload_root = external_run_root / "result_payload"
        _build_payload(
            dataset_root, external_run_root, payload_root, selected_seed,
            selected_metrics, selection, records,
        )
        write_json(payload_root / "verdict.json", records["verdict"])
        write_json(payload_root / "lineage" / "determinism_policy.json", records["determinism_policy"])
        write_json(payload_root / "lineage" / "smoke_1.json", first)
        write_json(payload_root / "lineage" / "smoke_2.json", second)
        write_json(payload_root / "lineage" / "smoke_comparison.json", records["smoke_comparison"])
        write_json(payload_root / "lineage" / "measured_training.json", records["training"])
        _diagnostic_evidence(torch, model, episodes, dataset_root, payload_root, config, precision)
        _blind_material(payload_root, e2_root / "templates" / "blind_visual_review.md")
        _seal_result(payload_root, result_root)
        return 0
    except Exception as exc:
        payload = _failure_payload(external_run_root, stage, exc, records)
        _seal_result(payload, result_root)
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
