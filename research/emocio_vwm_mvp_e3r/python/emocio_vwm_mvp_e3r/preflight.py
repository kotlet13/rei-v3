"""Fail-closed E3R checks executed before Torch or LPWM import."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

LPWM_SHA = "4cf53c403433e64c01652ac2adbec66231a46dea"
CHECKPOINT_SHA = "6d62bf5a2f8977c8e4cea10250ac73fea4dbe61dad997607e7df959a0a9aa731"
HPARAMS_SHA = "70f413905ed6295dc7e1f47f30ac52dcffee416b1311e7e97f85e9bc41514c44"
SUBSET_SHA = "6026ac8102403a014a8ea14e0e9ca0ee8fa3391889524ce70aeb32842a73b8f6"
DATASET_SHA = "c8f953d7190bbe133851de40ba6cb93770947f1c2ed8471c4389c6cf35aeb87e"
MODEL_CONFIG_SHA = "30c96f5e521b0025e6fc62fa0d3a230448f5cf680aefc4727d6162711b09ca07"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(
    repo: Path,
    lpwm: Path,
    dataset: Path,
    checkpoint: Path,
    hparams: Path,
    sketchy_subset: Path,
    protocol_sha: str,
) -> dict:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    remote = subprocess.check_output(
        ["git", "rev-parse", "origin/codex/emocio-visual-world-model-mvp"], cwd=repo, text=True
    ).strip()
    if head != protocol_sha or remote != head:
        raise RuntimeError("E3R requires the exact pushed protocol commit")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=lpwm, text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=lpwm, text=True
    ).strip()
    if source != LPWM_SHA or dirty:
        raise RuntimeError("LPWM source pin/cleanliness failure")
    if sha(checkpoint) != CHECKPOINT_SHA:
        raise RuntimeError("official checkpoint hash mismatch")
    if sha(hparams) != HPARAMS_SHA:
        raise RuntimeError("official hparams hash mismatch")

    acquisition = json.loads(
        (repo / "research/emocio_vwm_mvp_e3/result/lineage/acquisition_manifest.json").read_text()
    )
    files = acquisition["dataset"]["files"]
    if len(files) != 21:
        raise RuntimeError("frozen Sketchy subset manifest must contain 21 frames")
    tree_material = ""
    for item in files:
        path = sketchy_subset / item["name"]
        if path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            raise RuntimeError(f"Sketchy subset mismatch: {item['name']}")
        tree_material += f"{item['name']}\0{item['bytes']}\0{item['sha256']}\n"
    if hashlib.sha256(tree_material.encode()).hexdigest() != SUBSET_SHA:
        raise RuntimeError("Sketchy subset tree hash mismatch")

    freeze = json.loads((repo / "research/emocio_vwm_mvp_e3/specs/dataset_freeze.json").read_text())
    if freeze["dataset_tree_sha256"] != DATASET_SHA:
        raise RuntimeError("frozen target dataset pin mismatch")
    if sha(repo / "research/emocio_vwm_mvp_e3/specs/model_config.json") != MODEL_CONFIG_SHA:
        raise RuntimeError("frozen target model config hash mismatch")
    if sha(dataset / "dataset_manifest.json") != freeze["dataset_manifest_sha256"]:
        raise RuntimeError("target dataset manifest mismatch")
    return {
        "protocol_commit_sha": head,
        "lpwm_source_sha": source,
        "official_checkpoint_sha256": CHECKPOINT_SHA,
        "official_hparams_sha256": HPARAMS_SHA,
        "official_subset_tree_sha256": SUBSET_SHA,
        "target_dataset_tree_sha256": DATASET_SHA,
        "target_model_config_sha256": MODEL_CONFIG_SHA,
    }
