"""Seal the completed E2R run after its post-budget packaging-only failure.

This utility never trains, samples, selects, or recomputes hard gates. It
preserves the failed packaging attempt, verifies the completed frozen run and
existing evaluated artifacts, loads the final checkpoint only to create the
pre-registered particle/mask/reconstruction diagnostics, and seals the bundle.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import time
import warnings


os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

REPO_ROOT = Path(__file__).resolve().parents[1]
E2R_PACKAGE_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e2r" / "python"
E2_PACKAGE_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e2" / "python"
import sys
sys.path.insert(0, str(E2_PACKAGE_ROOT))
sys.path.insert(0, str(E2R_PACKAGE_ROOT))

from emocio_vwm_mvp_e2.artifacts import sha256, write_json  # noqa: E402
from emocio_vwm_mvp_e2.boundary import validate_mp4, validate_png  # noqa: E402
from emocio_vwm_mvp_e2.model_adapter import (  # noqa: E402
    build_model, canonical_state_hash, seed_everything,
)
from emocio_vwm_mvp_e2.runner import _route_index  # noqa: E402
from emocio_vwm_mvp_e2.visual_dataset import load_episode, opaque_episode_dirs  # noqa: E402
from emocio_vwm_mvp_e2r.runner import (  # noqa: E402
    _blind_material, _diagnostic_evidence, _seal_result,
)


PROTOCOL_SHA = "b01e95ded1a4e990cd29ece4753ea04d41c5c091"
ENVIRONMENT_SHA = "2f88a3f694eed8c7af84959e0a53db09a41d10614bcf423b8a100186497dcfc2"
DATASET_SHA = "f84bcb3f93734b99d5ebb62a3c02718b14f713b4265d006635770daf3d1e7991"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--lpwm-root", required=True)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--external-run-root", required=True)
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--metric-weights-manifest", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    lpwm = Path(args.lpwm_root).resolve()
    dataset = Path(args.dataset_root).resolve()
    external = Path(args.external_run_root).resolve()
    result = Path(args.result_root).resolve()
    e2 = repo / "research" / "emocio_vwm_mvp_e2"
    e2r = repo / "research" / "emocio_vwm_mvp_e2r"
    payload = external / "result_payload"
    archive = e2r / "post_execution" / "bundle_attempt_1_failure"
    if archive.exists():
        raise RuntimeError("bundle attempt archive already exists")
    failure = read(result / "failure.json")
    if failure.get("stage") != "bundle" or failure.get("message") != "'lpwm_smoke'":
        raise RuntimeError("unexpected E2R packaging failure; refusing correction")
    shutil.move(result, archive)

    training = read(external / "measured_training_record.json")
    smoke_1 = read(external / "smokes" / "run_1" / "execution_record.json")
    smoke_2 = read(external / "smokes" / "run_2" / "execution_record.json")
    comparison = read(external / "smokes" / "comparison.json")
    sampling = read(external / "sampling_run.json")
    environment = read(external / "environment_manifest.json")
    cuda_smoke = read(external / "cuda_smoke.json")
    verdict = read(archive / "partial_lineage" / "verdict.json")
    preflight = read(archive / "partial_lineage" / "preflight.json")
    determinism = read(archive / "partial_lineage" / "determinism_policy.json")
    metric_weights = read(Path(args.metric_weights_manifest).resolve())
    selected_metrics = read(payload / "metrics" / "selected_visual_metrics.json")

    if training["status"] != "completed" or training["optimizer_steps_completed"] != 1200:
        raise RuntimeError("frozen measured budget is incomplete")
    if training["initial_state_sha256"] != smoke_1["initial_state_sha256"]:
        raise RuntimeError("measured and smoke initialization hashes differ")
    if smoke_1["initial_state_sha256"] != smoke_2["initial_state_sha256"]:
        raise RuntimeError("smoke initialization hashes differ")
    if not comparison["initial_state_hashes_equal"]:
        raise RuntimeError("smoke comparison did not pass")
    if verdict["verdict"] != "model_fit_failed" or verdict["hard_gates"]["all_passed"]:
        raise RuntimeError("canonical completed-budget verdict is not model_fit_failed")
    if selected_metrics["hard_gates"] != verdict["hard_gates"]:
        raise RuntimeError("selected hard gates differ from frozen verdict")
    if preflight["protocol_commit_sha"] != PROTOCOL_SHA:
        raise RuntimeError("E2R protocol lineage differs")
    if preflight["dataset"]["dataset_tree_sha256"] != DATASET_SHA:
        raise RuntimeError("dataset lineage differs")
    if sha256(external / "environment_manifest.json") != ENVIRONMENT_SHA:
        raise RuntimeError("environment manifest differs")

    write_json(payload / "verdict.json", verdict)
    write_json(payload / "lineage" / "preflight.json", preflight)
    write_json(payload / "lineage" / "environment_manifest.json", environment)
    write_json(payload / "lineage" / "cuda_smoke.json", cuda_smoke)
    write_json(payload / "lineage" / "determinism_policy.json", determinism)
    write_json(payload / "lineage" / "smoke_1.json", smoke_1)
    write_json(payload / "lineage" / "smoke_2.json", smoke_2)
    write_json(payload / "lineage" / "smoke_comparison.json", comparison)
    write_json(payload / "lineage" / "measured_training.json", training)
    write_json(payload / "lineage" / "sampling_run.json", sampling)
    write_json(payload / "lineage" / "metric_weights.json", metric_weights)
    write_json(payload / "lineage" / "packaging_correction.json", {
        "schema_version": "rei-emocio-vwm-e2r-packaging-correction-v1",
        "attempt_1_failure_preserved_at": "post_execution/bundle_attempt_1_failure",
        "failure_stage": "bundle_after_completed_budget_and_evaluation",
        "failure_type": "KeyError",
        "failure_message": "'lpwm_smoke'",
        "classification": "post_budget_packaging_defect_not_model_execution_failure",
        "measured_run_reexecuted": False,
        "optimizer_steps_added": 0,
        "samples_regenerated": False,
        "hard_gates_recomputed": False,
        "verdict_changed_by_correction": False,
    })
    write_json(payload / "model_outputs" / "selected_visual_path.json", {
        "schema_version": "rei-emocio-vwm-e2r-selected-visual-path-v1",
        "native_output_is_natural_language": False,
        "selected_seed": verdict["selected_visual_sample_seed"],
        "opaque_episode_ids": sorted(path.name for path in (payload / "samples" / "selected").iterdir() if path.is_dir()),
        "key_mosaic": "contact_sheets/selected_key_mosaic.png",
        "terminal_mosaic": "contact_sheets/selected_terminal_mosaic.png",
    })

    import torch
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device("cuda:0")
    config = read(e2 / "specs" / "model_config.json")
    seed_everything(73013)
    model = build_model(lpwm, config, device)
    final_checkpoint = external / training["final_checkpoint"]["external_relative_path"]
    if sha256(final_checkpoint) != training["final_checkpoint"]["sha256"]:
        raise RuntimeError("final checkpoint hash differs")
    model.load_state_dict(torch.load(final_checkpoint, map_location=device, weights_only=True))
    if canonical_state_hash(model) != training["final_state_sha256"]:
        raise RuntimeError("loaded final model state differs")
    episodes = {path.name: load_episode(path) for path in opaque_episode_dirs(dataset)}
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        _diagnostic_evidence(torch, model, episodes, dataset, payload, config, training["precision"])
    write_json(payload / "lineage" / "diagnostic_postprocess.json", {
        "schema_version": "rei-emocio-vwm-e2r-diagnostic-postprocess-v1",
        "purpose": "pre_registered_particle_mask_reconstruction_evidence_only",
        "optimizer_steps": 0,
        "sample_selection": False,
        "hard_gate_evaluation": False,
        "loaded_state_sha256": training["final_state_sha256"],
        "duration_seconds": time.perf_counter() - started,
        "warnings": [
            {"category": item.category.__name__, "message": str(item.message)}
            for item in captured
        ],
        "peak_allocated_vram_bytes": int(torch.cuda.max_memory_allocated(device)),
        "peak_reserved_vram_bytes": int(torch.cuda.max_memory_reserved(device)),
    })
    del model
    torch.cuda.empty_cache()

    _blind_material(payload, e2 / "templates" / "blind_visual_review.md")
    png_files = sorted((payload / "samples" / "selected").rglob("*.png"))
    mp4_files = sorted((payload / "samples").rglob("*.mp4"))
    for path in png_files:
        validate_png(path, width=128, height=128)
    for path in mp4_files:
        validate_mp4(path, width=128, height=128, fps=6, frame_count=24)
    write_json(payload / "metrics" / "generated_media_boundary_audit.json", {
        "schema_version": "rei-emocio-vwm-e2r-generated-media-boundary-v1",
        "status": "passed",
        "png_files_checked": len(png_files),
        "mp4_files_checked": len(mp4_files),
        "ffprobe_stream_and_metadata_validation": "passed",
    })
    _seal_result(payload, result)
    print(json.dumps({
        "verdict": verdict["verdict"],
        "optimizer_steps": training["optimizer_steps_completed"],
        "result_root": str(result),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
