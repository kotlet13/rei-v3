"""Fail-closed provenance checks that execute before any LPWM or torch import."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


E1R_SHA = "01aa8d3e10c04275e528fd45796d0c4c5bb4ac0b"
LPWM_SHA = "4cf53c403433e64c01652ac2adbec66231a46dea"
DATASET_TREE_SHA = "f84bcb3f93734b99d5ebb62a3c02718b14f713b4265d006635770daf3d1e7991"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_git(checkout: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=checkout, capture_output=True, text=True, check=False, timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git provenance check failed")
    return completed.stdout.strip()


def verify_protocol_tree(e2_root: Path) -> dict[str, Any]:
    lineage_path = e2_root / "protocol_lineage.json"
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    for record in lineage["files"]:
        base = e2_root if record["root"] == "e2" else e2_root.parents[1]
        path = base / record["path"]
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise RuntimeError(f"protocol file differs from freeze: {record['path']}")
    return lineage


def verify_dataset(dataset_root: Path, e2_root: Path) -> dict[str, Any]:
    frozen = json.loads((e2_root / "dataset" / "frozen_dataset_manifest.json").read_text(encoding="utf-8"))
    checksums = json.loads((e2_root / "dataset" / "dataset_checksums.json").read_text(encoding="utf-8"))
    if frozen["dataset_tree_sha256"] != DATASET_TREE_SHA or frozen["source_e1r_sha"] != E1R_SHA:
        raise RuntimeError("frozen dataset lineage constants differ")
    actual_paths = tuple(
        path.relative_to(dataset_root).as_posix()
        for path in sorted(dataset_root.rglob("*")) if path.is_file()
    )
    expected_paths = tuple(record["path"] for record in checksums["files"])
    if actual_paths != expected_paths:
        raise RuntimeError("external dataset file tree differs from freeze")
    for record in checksums["files"]:
        path = dataset_root / record["path"]
        if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise RuntimeError(f"dataset byte mismatch: {record['path']}")
    payload = json.dumps(checksums["files"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(payload).hexdigest() != DATASET_TREE_SHA:
        raise RuntimeError("dataset tree digest differs from freeze")
    return frozen


def verify_lpwm_source(lpwm_root: Path) -> dict[str, Any]:
    head = _run_git(lpwm_root, "rev-parse", "HEAD")
    if head != LPWM_SHA:
        raise RuntimeError(f"LPWM checkout must be exact {LPWM_SHA}")
    tracked_status = _run_git(lpwm_root, "status", "--porcelain", "--untracked-files=no")
    if tracked_status:
        raise RuntimeError("LPWM tracked source is modified")
    return {"repository_commit_sha": head, "tracked_source_clean": True}


def verify_protocol_commit(repo_root: Path, protocol_commit: str) -> None:
    head = _run_git(repo_root, "rev-parse", "HEAD")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", protocol_commit, head], cwd=repo_root, check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("requested E2 protocol commit is not an ancestor of HEAD")
    parent = _run_git(repo_root, "rev-parse", f"{protocol_commit}^")
    if parent != E1R_SHA:
        raise RuntimeError("E2 protocol commit must be the direct child of sealed E1R")


def preflight(repo_root: Path, lpwm_root: Path, dataset_root: Path, protocol_commit: str) -> dict[str, Any]:
    e2_root = repo_root / "research" / "emocio_vwm_mvp_e2"
    verify_protocol_commit(repo_root, protocol_commit)
    return {
        "schema_version": "rei-emocio-vwm-e2-preflight-v1",
        "status": "passed",
        "protocol_commit_sha": protocol_commit,
        "protocol": verify_protocol_tree(e2_root),
        "lpwm": verify_lpwm_source(lpwm_root),
        "dataset": verify_dataset(dataset_root, e2_root),
    }


__all__ = ["DATASET_TREE_SHA", "E1R_SHA", "LPWM_SHA", "preflight", "sha256"]
