"""Read-only LPWM gate: approved bytes, exact environment, and CUDA smoke."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


def _run(args: list[str], *, cwd: Path | None = None, timeout: int = 30) -> tuple[int, str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    return completed.returncode, (completed.stdout or completed.stderr).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_exact_environment_manifest(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    expected_commit: str,
) -> list[str]:
    problems: list[str] = []
    required = set(contract["required_fields"])
    if manifest.get("schema_version") != contract["required_manifest_schema"]:
        problems.append("environment_manifest_schema_mismatch")
    if not required.issubset(manifest):
        problems.append("environment_manifest_required_fields_missing")
    if manifest.get("lpwm_source_commit") != expected_commit:
        problems.append("environment_manifest_source_commit_mismatch")
    inventory = manifest.get("package_inventory")
    if (
        not isinstance(inventory, list)
        or inventory != sorted(inventory, key=str.casefold)
        or len(inventory) != len(set(inventory))
        or any(not isinstance(item, str) or "==" not in item for item in inventory)
    ):
        problems.append("environment_package_inventory_not_exact")
    smoke = manifest.get("cuda_smoke")
    if not isinstance(smoke, dict) or smoke.get("passed") is not True:
        problems.append("recorded_cuda_smoke_not_passed")
    return problems


def inspect_lpwm_execution_gate(spec_root: Path) -> dict[str, Any]:
    """Inspect without installing, downloading, training, or loading a checkpoint."""

    pin = _load(spec_root / "lpwm_pin.json")
    approvals = _load(spec_root / pin["required_checkpoint_approval_file"])
    contract = _load(spec_root / "environment_manifest_contract.json")
    root_value = os.environ.get(pin["required_root_env"])
    root = Path(root_value).expanduser().resolve() if root_value else None
    checkpoint_value = os.environ.get(pin["required_checkpoint_env"])
    checkpoint = Path(checkpoint_value).expanduser().resolve() if checkpoint_value else None
    env_value = os.environ.get(pin["required_environment_manifest_env"])
    environment_manifest_path = Path(env_value).expanduser().resolve() if env_value else None
    blockers: list[str] = []
    result: dict[str, Any] = {
        "schema_version": "rei-emocio-lpwm-execution-gate-v2",
        "expected_source_commit": pin["commit"],
        "source": {"explicit": root is not None, "present": False, "commit": None, "pin_match": False},
        "checkpoint": {"explicit": checkpoint is not None, "present": False, "sha256": None, "approved": False},
        "environment_manifest": {"explicit": environment_manifest_path is not None, "present": False, "sha256": None, "approved": False, "contract_valid": False},
        "live_cuda_smoke": {"attempted": False, "passed": False, "record": None},
        "hardware_discovery": {"available": False, "description": None},
        "automatic_source_download_attempted": False,
        "automatic_weight_download_attempted": False,
        "environment_install_attempted": False,
        "environment_status": "blocked",
        "execution_status": "not_started",
        "model_fit_status": "not_assessed",
        "ready_for_first_model_call": False,
        "blockers": blockers,
    }
    if root is None:
        blockers.append("explicit_lpwm_root_missing")
    elif root.is_dir():
        result["source"]["present"] = True
        code, commit = _run(["git", "rev-parse", "HEAD"], cwd=root)
        if code == 0:
            result["source"]["commit"] = commit
            result["source"]["pin_match"] = commit == pin["commit"]
        if not result["source"]["pin_match"]:
            blockers.append("lpwm_source_pin_mismatch")
    else:
        blockers.append("explicit_lpwm_root_not_found")

    if checkpoint is None:
        blockers.append("explicit_checkpoint_missing")
    elif checkpoint.is_file():
        result["checkpoint"]["present"] = True
        checkpoint_hash = _sha256(checkpoint)
        result["checkpoint"]["sha256"] = checkpoint_hash
        result["checkpoint"]["approved"] = checkpoint_hash in approvals["approved_checkpoint_sha256"]
        if not result["checkpoint"]["approved"]:
            blockers.append("checkpoint_sha256_not_approved")
    else:
        blockers.append("explicit_checkpoint_not_found")

    parsed_environment: dict[str, Any] | None = None
    if environment_manifest_path is None:
        blockers.append("explicit_environment_manifest_missing")
    elif environment_manifest_path.is_file():
        result["environment_manifest"]["present"] = True
        manifest_hash = _sha256(environment_manifest_path)
        result["environment_manifest"]["sha256"] = manifest_hash
        result["environment_manifest"]["approved"] = manifest_hash in approvals["approved_environment_manifest_sha256"]
        if not result["environment_manifest"]["approved"]:
            blockers.append("environment_manifest_sha256_not_approved")
        try:
            parsed_environment = _load(environment_manifest_path)
            problems = _validate_exact_environment_manifest(parsed_environment, contract, pin["commit"])
            result["environment_manifest"]["contract_valid"] = not problems
            blockers.extend(problems)
        except (OSError, json.JSONDecodeError):
            blockers.append("environment_manifest_unreadable")
    else:
        blockers.append("explicit_environment_manifest_not_found")

    code, hardware = _run([
        "nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"
    ])
    if code == 0 and hardware:
        result["hardware_discovery"] = {"available": True, "description": hardware.splitlines()[0]}
    else:
        blockers.append("cuda_hardware_not_discovered")

    prerequisites = (
        root is not None
        and result["source"]["pin_match"]
        and result["checkpoint"]["approved"]
        and result["environment_manifest"]["approved"]
        and result["environment_manifest"]["contract_valid"]
        and parsed_environment is not None
    )
    if prerequisites:
        assert root is not None
        python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.is_file():
            blockers.append("pinned_environment_python_missing")
        else:
            result["live_cuda_smoke"]["attempted"] = True
            smoke_code = (
                "import json,torch;"
                "assert torch.cuda.is_available();"
                "a=torch.arange(16,dtype=torch.float32,device='cuda:0').reshape(4,4);"
                "b=a@a.T;torch.cuda.synchronize();"
                "print(json.dumps({'passed':bool(torch.isfinite(b).all().item()),"
                "'device':torch.cuda.get_device_name(0),"
                "'capability':list(torch.cuda.get_device_capability(0)),"
                "'torch':torch.__version__,'cuda':torch.version.cuda}))"
            )
            code, output = _run([str(python), "-c", smoke_code], timeout=60)
            if code == 0:
                smoke_record = json.loads(output)
                result["live_cuda_smoke"] = {
                    "attempted": True,
                    "passed": smoke_record.get("passed") is True,
                    "record": smoke_record,
                }
                if smoke_record.get("passed") is not True:
                    blockers.append("live_cuda_smoke_failed")
            else:
                blockers.append("live_cuda_smoke_failed")
    else:
        blockers.append("live_cuda_smoke_not_authorized_by_prerequisites")

    result["blockers"] = sorted(set(blockers))
    result["ready_for_first_model_call"] = not result["blockers"]
    result["environment_status"] = "ready" if result["ready_for_first_model_call"] else "blocked"
    return result


__all__ = ["inspect_lpwm_execution_gate"]
