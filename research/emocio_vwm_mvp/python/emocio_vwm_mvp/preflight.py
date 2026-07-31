"""Read-only preflight for the separately pinned LPWM environment."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


def _run(args: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return completed.returncode, (completed.stdout or completed.stderr).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_lpwm_environment(pin_path: Path) -> dict[str, Any]:
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    config = pin["external_environment"]
    root_value = os.environ.get(config["required_root_env"], config["local_example_root"])
    root = Path(root_value).expanduser().resolve()
    checkpoint_value = os.environ.get(config["required_checkpoint_env"])
    checkpoint = (
        Path(checkpoint_value).expanduser().resolve()
        if checkpoint_value
        else None
    )
    result: dict[str, Any] = {
        "schema_version": "rei-emocio-lpwm-preflight-v1",
        "source_root": str(root),
        "expected_commit": pin["commit"],
        "source_present": root.is_dir(),
        "source_commit": None,
        "source_pin_match": False,
        "venv_python_present": False,
        "dependencies": {},
        "checkpoint": {
            "explicit": checkpoint is not None,
            "present": bool(checkpoint and checkpoint.is_file()),
            "sha256": None,
        },
        "gpu": {"available": False, "description": None},
        "automatic_download_attempted": False,
        "ready": False,
        "blockers": [],
    }
    if root.is_dir():
        code, commit = _run(["git", "rev-parse", "HEAD"], cwd=root)
        if code == 0:
            result["source_commit"] = commit
            result["source_pin_match"] = commit == pin["commit"]
    if not result["source_present"]:
        result["blockers"].append("pinned_source_missing")
    elif not result["source_pin_match"]:
        result["blockers"].append("source_pin_mismatch")
    python = root / config["repo_relative_venv"] / "Scripts" / "python.exe"
    if os.name != "nt":
        python = root / config["repo_relative_venv"] / "bin" / "python"
    result["venv_python_present"] = python.is_file()
    modules = ("torch", "torchvision", "numpy", "cv2", "PIL")
    if python.is_file():
        probe = (
            "import importlib.util,json;"
            f"print(json.dumps({{m:bool(importlib.util.find_spec(m)) for m in {modules!r}}}))"
        )
        code, output = _run([str(python), "-c", probe])
        if code == 0:
            result["dependencies"] = json.loads(output)
    if not python.is_file():
        result["blockers"].append("lpwm_venv_python_missing")
    missing = sorted(name for name in modules if not result["dependencies"].get(name))
    if missing:
        result["blockers"].append(f"lpwm_dependencies_missing:{','.join(missing)}")
    if checkpoint and checkpoint.is_file():
        result["checkpoint"]["sha256"] = _sha256(checkpoint)
    else:
        result["blockers"].append("explicit_checkpoint_missing")
    code, gpu = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    if code == 0 and gpu:
        result["gpu"] = {"available": True, "description": gpu.splitlines()[0]}
    else:
        result["blockers"].append("cuda_gpu_missing")
    result["ready"] = not result["blockers"]
    return result


__all__ = ["inspect_lpwm_environment"]
