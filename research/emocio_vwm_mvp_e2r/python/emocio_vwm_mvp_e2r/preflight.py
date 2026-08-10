"""Fail-closed E2R provenance checks that precede Torch and LPWM imports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from emocio_vwm_mvp_e2.preflight import verify_dataset, verify_lpwm_source


E1R_SHA = "01aa8d3e10c04275e528fd45796d0c4c5bb4ac0b"
E2_PROTOCOL_SHA = "e409ecbdebd220db9da934827f2b1e0a7d73b65c"
E2_RESULT_SHA = "d1415007b97e651e59953bbdf093d64516603365"
LPWM_SHA = "4cf53c403433e64c01652ac2adbec66231a46dea"
DATASET_TREE_SHA = "f84bcb3f93734b99d5ebb62a3c02718b14f713b4265d006635770daf3d1e7991"
ENVIRONMENT_SHA = "2f88a3f694eed8c7af84959e0a53db09a41d10614bcf423b8a100186497dcfc2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(checkout: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=checkout, capture_output=True, text=True, check=False, timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git provenance check failed")
    return completed.stdout.strip()


def verify_protocol_commit(repo_root: Path, protocol_commit: str) -> None:
    head = _git(repo_root, "rev-parse", "HEAD")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", protocol_commit, head], cwd=repo_root, check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("requested E2R protocol commit is not an ancestor of HEAD")
    if _git(repo_root, "rev-parse", f"{protocol_commit}^") != E2_RESULT_SHA:
        raise RuntimeError("E2R protocol commit must be the direct child of frozen E2 result")
    if _git(repo_root, "rev-parse", E2_RESULT_SHA) != E2_RESULT_SHA:
        raise RuntimeError("frozen E2 result commit is unavailable")


def verify_e2_immutable(repo_root: Path) -> None:
    paths = (
        "research/emocio_vwm_mvp_e2",
        "scripts/run_emocio_vwm_e2.py",
        "scripts/seal_emocio_vwm_e2_protocol.py",
        "tests/research/test_emocio_vwm_e2_protocol.py",
        "tests/research/test_emocio_vwm_e2_result.py",
    )
    completed = subprocess.run(
        ["git", "diff", "--quiet", E2_RESULT_SHA, "HEAD", "--", *paths],
        cwd=repo_root, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("frozen E2 code or evidence differs from d1415007")


def verify_protocol_tree(e2r_root: Path) -> dict[str, Any]:
    lineage = json.loads((e2r_root / "protocol_lineage.json").read_text(encoding="utf-8"))
    for record in lineage["files"]:
        base = e2r_root if record["root"] == "e2r" else e2r_root.parents[1]
        path = base / record["path"]
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise RuntimeError(f"E2R protocol file differs from freeze: {record['path']}")
    return lineage


def preflight(
    repo_root: Path, lpwm_root: Path, dataset_root: Path, protocol_commit: str,
) -> dict[str, Any]:
    e2_root = repo_root / "research" / "emocio_vwm_mvp_e2"
    e2r_root = repo_root / "research" / "emocio_vwm_mvp_e2r"
    verify_protocol_commit(repo_root, protocol_commit)
    verify_e2_immutable(repo_root)
    return {
        "schema_version": "rei-emocio-vwm-e2r-preflight-v1",
        "status": "passed",
        "protocol_commit_sha": protocol_commit,
        "frozen_e2_protocol_sha": E2_PROTOCOL_SHA,
        "frozen_e2_result_sha": E2_RESULT_SHA,
        "e1r_sha": E1R_SHA,
        "protocol": verify_protocol_tree(e2r_root),
        "lpwm": verify_lpwm_source(lpwm_root),
        "dataset": verify_dataset(dataset_root, e2_root),
        "expected_environment_manifest_sha256": ENVIRONMENT_SHA,
    }


__all__ = [
    "DATASET_TREE_SHA", "E2_PROTOCOL_SHA", "E2_RESULT_SHA", "ENVIRONMENT_SHA",
    "LPWM_SHA", "preflight", "sha256",
]
