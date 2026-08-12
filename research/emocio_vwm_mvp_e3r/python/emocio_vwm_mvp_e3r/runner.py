"""E3R official positive control followed, only on pass, by the frozen E3 target."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"  # before Torch import

from .evaluator import evaluate_and_package
from .model_adapter import (
    build,
    inference,
    official_constructor_config,
    rollout,
    state_hash,
    strict_load_checkpoint,
)
from .preflight import check, sha
from .shape_contract import normalize_lpwm_output_shapes


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def image_tensor(paths, torch, device):
    import numpy as np
    from PIL import Image

    data = np.stack(
        [np.asarray(Image.open(path).convert("RGB"), dtype=np.float32).transpose(2, 0, 1) / 255 for path in paths]
    )
    return torch.from_numpy(data).to(device)


def save_png(tensor, path: Path) -> None:
    import numpy as np
    from PIL import Image

    value = tensor.detach().float().cpu().clamp(0, 1).numpy()
    value = np.rint(value.transpose(1, 2, 0) * 255).astype("uint8")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(value).save(path, optimize=False)


def make_video(frames: Path, pattern: str, target: Path) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", "6", "-i", str(frames / pattern),
            "-frames:v", "21", "-map_metadata", "-1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target),
        ],
        check=True,
    )
    probe = json.loads(
        subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                "-show_entries", "stream=codec_type,codec_name,width,height,nb_read_frames,r_frame_rate",
                "-of", "json", str(target),
            ],
            text=True,
        )
    )
    streams = probe.get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_type") != "video" or int(streams[0]["nb_read_frames"]) != 21:
        raise RuntimeError(f"invalid 21-frame MP4: {target}")
    return {"path": str(target), "sha256": sha(target), "bytes": target.stat().st_size, "ffprobe": probe}


def tree_manifest(root: Path) -> dict:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        files.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    tree = canonical_hash(files)
    return {"algorithm": "sha256", "file_count": len(files), "files": files, "tree_sha256": tree}


def _rollout_frames(value, torch, destination: Path) -> tuple[dict, list]:
    import numpy as np

    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise RuntimeError("sample_from_x must return decoded frames and latent particles")
    frames, latent = value
    shape = tuple(int(x) for x in frames.shape)
    if len(shape) == 4 and shape[0] == 21:
        frames = frames.reshape((1, 21, *shape[1:]))
    elif len(shape) != 5 or shape[:2] != (1, 21):
        raise RuntimeError(f"rollout frames violate [1,21,C,H,W]: {shape}")
    for index in range(21):
        save_png(frames[0, index], destination / "frames" / f"{index:06d}.png")
    arrays = {}
    values = latent if isinstance(latent, dict) else {"latent": latent}
    for key, item in sorted(values.items()):
        if hasattr(item, "detach"):
            arrays[key] = item.detach().float().cpu().numpy()
        elif isinstance(item, np.ndarray):
            arrays[key] = item
    if not arrays:
        raise RuntimeError("rollout returned no serializable latent particle outputs")
    latent_path = destination / "latent_particles.npz"
    latent_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(latent_path, **arrays)
    latent_manifest = [{"name": key, "shape": list(value.shape), "dtype": str(value.dtype)} for key, value in arrays.items()]
    return make_video(destination / "frames", "%06d.png", destination / "rollout.mp4"), latent_manifest


def positive_control(torch, args, device) -> dict:
    out = Path(args.output) / "positive_control"
    out.mkdir(parents=True, exist_ok=False)
    record = {"schema_version": "rei-emocio-vwm-e3r-positive-control-v1", "status": "running"}
    write(out / "record.json", record)
    try:
        hparams_path = Path(args.sketchy_hparams)
        hparams = json.loads(hparams_path.read_text(encoding="utf-8"))
        constructor = official_constructor_config(hparams)
        hparams_record = {
            "official_hparams_sha256": sha(hparams_path),
            "constructor_config": constructor,
            "constructor_config_sha256": canonical_hash(constructor),
        }
        write(out / "official_hparams_manifest.json", hparams_record)
        model = build(Path(args.lpwm), constructor, device)
        load_record = strict_load_checkpoint(model, Path(args.sketchy_checkpoint), torch)
        load_record["checkpoint_sha256"] = sha(Path(args.sketchy_checkpoint))
        load_record["model_state_sha256"] = state_hash(model)
        write(out / "checkpoint_load.json", load_record)
        if load_record["missing_keys"] or load_record["unexpected_keys"]:
            raise RuntimeError("strict checkpoint load reported incompatible keys")

        source_paths = [Path(args.sketchy_data) / f"ep000179_t{index:03d}_fl_full.png" for index in range(21)]
        if not all(path.is_file() for path in source_paths):
            raise RuntimeError("exact ep000179 frames 000-020 are incomplete")
        x = image_tensor(source_paths, torch, device).unsqueeze(0)
        model.eval()
        with torch.no_grad():
            raw = inference(model, x)
        normalized, shape_manifest = normalize_lpwm_output_shapes(raw, 1, 21)
        write(out / "tensor_shapes.json", shape_manifest)
        for index, source in enumerate(source_paths):
            target = out / "source" / f"{index:06d}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        evidence = evaluate_and_package(raw, 1, 21, out / "evidence")
        videos = {
            "reconstruction": make_video(out / "evidence/full", "b00_t%06d.png", out / "reconstruction.mp4"),
            "mask": make_video(out / "evidence/mask_union", "b00_t%06d.png", out / "mask.mp4"),
            "particles": make_video(out / "evidence/particles", "b00_t%06d.png", out / "particles.mp4"),
        }
        with torch.no_grad():
            sampled = rollout(model, x)
        rollout_video, latent_manifest = _rollout_frames(sampled, torch, out / "rollout")
        metrics = evidence["metrics"]
        complete = (
            metrics["reconstruction_std"] > 0
            and metrics["mask_union_max"] > 0
            and metrics["active_particle_count_mean"] > 0
        )
        record.update(
            status="passed" if complete else "model_failed",
            sequence="ep000179 frames 000-020",
            source_frame_count=21,
            shape_manifest=shape_manifest,
            checkpoint_load=load_record,
            metrics=metrics,
            videos=videos,
            rollout={"video": rollout_video, "latent_manifest": latent_manifest},
        )
        write(out / "record.json", record)
        first = tree_manifest(out)
        second = tree_manifest(out)
        determinism = {"run_1": first, "run_2": second, "identical": first == second}
        write(out / "artifact_tree_determinism.json", determinism)
        if not determinism["identical"]:
            raise RuntimeError("two-run artifact-tree manifest comparison differed")
        record["artifact_tree_sha256"] = tree_manifest(out)["tree_sha256"]
        write(out / "record.json", record)
        return record
    except Exception as exc:
        record.update(
            status="technical_failure",
            exception={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
        )
        write(out / "record.json", record)
        raise


def evaluate_target(torch, model, dataset: Path, cfg: dict, lossfn, device, result: Path):
    import numpy as np
    from PIL import Image

    repo = Path(__file__).resolve().parents[4]
    e3_python = repo / "research/emocio_vwm_mvp_e3/python"
    if str(e3_python) not in sys.path:
        sys.path.insert(0, str(e3_python))
    from emocio_vwm_mvp_e3.metrics import aggregate, evaluate_gates, frame_metrics
    from emocio_vwm_mvp_e3.model_adapter import call
    from emocio_vwm_mvp_e3.runner import batch, episodes

    all_splits = {}
    model.eval()
    for split in ("train", "validation", "holdout"):
        selected = episodes(dataset, split) if split == "validation" else episodes(dataset, split)[:12]
        frames, lpips_values = [], []
        for episode_index, episode in enumerate(selected):
            x = batch(dataset, [episode], torch, device)
            with torch.no_grad():
                raw = call(model, x, cfg["loss"], lossfn, True)
            normalized, _ = normalize_lpwm_output_shapes(raw, 1, 21)
            rec = normalized["rec_rgb"][0]
            bg = normalized["bg_rgb"][0]
            alpha = normalized["alpha_masks"][0]
            if int(alpha.shape[2]) != 1:
                raise RuntimeError("alpha singleton channel validation failed")
            alpha = alpha[:, :, 0, :, :]
            obj = normalized["obj_on"][0, :, :, 0]
            for index in range(21):
                label_path = dataset / "evaluator_only" / split / episode.name / f"labels_{index:06d}.png"
                labels = np.asarray(Image.open(label_path).convert("RGB"))[:, :, 0]
                union = (labels > 0).astype(np.float32)
                people = json.loads(
                    (dataset / "evaluator_only" / split / episode.name / "scene.json").read_text()
                )["people"]
                person_masks = [(labels == person["id"]).astype(np.float32) for person in people]
                foreground = torch.from_numpy(union).to(device)
                denominator = max(1, union.sum()) * 3
                full_error = float((((rec[index] - x[0, index]) ** 2) * foreground).sum().cpu() / denominator)
                bg_error = float((((bg[index] - x[0, index]) ** 2) * foreground).sum().cpu() / denominator)
                frames.append(
                    frame_metrics(
                        obj[index].detach().float().cpu().numpy(),
                        alpha[index].detach().float().cpu().numpy(),
                        union,
                        person_masks,
                        full_error,
                        bg_error,
                    )
                )
                lpips_values.append(
                    float(
                        lossfn(
                            x[0, index : index + 1] * foreground,
                            rec[index : index + 1] * foreground,
                        ).mean().cpu()
                    )
                )
            if split == "validation" and episode_index < 12:
                package = result / "artifacts" / episode.name
                evaluate_and_package(raw, 1, 21, package)
                for index in range(21):
                    target = package / "source" / f"b00_t{index:06d}.png"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(dataset / "model_visible" / split / episode.name / f"{index:06d}.png", target)
                for kind in ("full", "background", "foreground", "mask_union", "particles"):
                    make_video(package / kind, "b00_t%06d.png", result / "videos" / f"{episode.name}_{kind}.mp4")
        metrics = aggregate(frames)
        metrics["foreground_lpips"] = float(np.mean(lpips_values))
        all_splits[split] = metrics
        write(result / "metrics" / f"{split}.json", metrics)
    gates = evaluate_gates(all_splits["validation"])
    write(result / "metrics/validation_gates.json", gates)
    return all_splits, gates


def execute(args) -> int:
    root, out = Path(args.repo).resolve(), Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = "preflight"
    target_started = False
    try:
        preflight = check(
            root, Path(args.lpwm), Path(args.dataset), Path(args.sketchy_checkpoint),
            Path(args.sketchy_hparams), Path(args.sketchy_data), args.protocol_sha,
        )
        write(out / "lineage/preflight.json", preflight)
        stage = "torch_import"
        import torch

        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable")
        device = torch.device("cuda:0")
        stage = "positive_control"
        control = positive_control(torch, args, device)
        if control["status"] == "model_failed":
            write(out / "verdict.json", {"verdict": "positive_control_failed", "target_started": False})
            return 3
        if control["status"] != "passed":
            raise RuntimeError("positive-control harness did not complete")

        stage = "target_training"
        target_started = True
        e3_python = root / "research/emocio_vwm_mvp_e3/python"
        if str(e3_python) not in sys.path:
            sys.path.insert(0, str(e3_python))
        from emocio_vwm_mvp_e3.runner import config, target

        cfg = config(root, "model_config.json")
        plan = config(root, "execution_plan.json")
        model, lossfn, training = target(torch, args, root, cfg, plan, device)
        stage = "target_evaluation"
        _, gates = evaluate_target(torch, model, Path(args.dataset), cfg, lossfn, device, out)
        passed = all(gate["passed"] for gate in gates.values())
        verdict = "candidate_objectness_promising" if passed else "candidate_objectness_failed"
        write(
            out / "verdict.json",
            {
                "verdict": verdict,
                "target_started": True,
                "target_optimizer_steps": training["optimizer_steps_completed"],
                "validation_hard_gates": gates,
                "social_model_fit_started": False,
                "active_rei_runtime_modified": False,
            },
        )
        manifest_1 = tree_manifest(out)
        manifest_2 = tree_manifest(out)
        write(out / "artifact_tree_determinism.json", {"run_1": manifest_1, "run_2": manifest_2, "identical": manifest_1 == manifest_2})
        return 0 if passed else 4
    except Exception as exc:
        write(
            out / "failure.json",
            {"stage": stage, "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
        )
        write(
            out / "verdict.json",
            {
                "verdict": "not_executed_resource_block",
                "failed_stage": stage,
                "target_started": target_started,
                "model_fit_failure_claimed": False,
            },
        )
        return 2


def parser():
    value = argparse.ArgumentParser()
    value.add_argument("--repo", required=True)
    value.add_argument("--lpwm", required=True)
    value.add_argument("--dataset", required=True)
    value.add_argument("--sketchy-checkpoint", required=True)
    value.add_argument("--sketchy-hparams", required=True)
    value.add_argument("--sketchy-data", required=True)
    value.add_argument("--external", required=True)
    value.add_argument("--output", required=True)
    value.add_argument("--protocol-sha", required=True)
    return value


def main() -> int:
    return execute(parser().parse_args())
