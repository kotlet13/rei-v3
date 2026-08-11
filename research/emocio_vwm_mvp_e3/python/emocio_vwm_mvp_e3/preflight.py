"""Fail-closed E3 checks executed before Torch or LPWM import."""
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
LPWM_SHA="4cf53c403433e64c01652ac2adbec66231a46dea"
DATASET_SHA="c8f953d7190bbe133851de40ba6cb93770947f1c2ed8471c4389c6cf35aeb87e"
ENV_SHA="2f88a3f694eed8c7af84959e0a53db09a41d10614bcf423b8a100186497dcfc2"
def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def check(repo:Path,lpwm:Path,dataset:Path,protocol_sha:str)->dict:
 head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
 if head!=protocol_sha:raise RuntimeError("E3 execution requires the exact pushed protocol commit")
 remote=subprocess.check_output(["git","rev-parse","origin/codex/emocio-visual-world-model-mvp"],cwd=repo,text=True).strip()
 if remote!=head:raise RuntimeError("E3 protocol commit is not yet pushed")
 source=subprocess.check_output(["git","rev-parse","HEAD"],cwd=lpwm,text=True).strip()
 dirty=subprocess.check_output(["git","status","--porcelain"],cwd=lpwm,text=True).strip()
 if source!=LPWM_SHA or dirty:raise RuntimeError("LPWM source pin/cleanliness failure")
 freeze=json.loads((repo/"research/emocio_vwm_mvp_e3/specs/dataset_freeze.json").read_text())
 manifest=json.loads((dataset/"dataset_manifest.json").read_text())
 if freeze["dataset_manifest_sha256"]!=sha(dataset/"dataset_manifest.json"):raise RuntimeError("dataset manifest hash mismatch")
 if manifest["episodes"]!=256 or manifest["splits"]!={"train":192,"validation":32,"holdout":32}:raise RuntimeError("dataset structure mismatch")
 for ep in manifest["episodes_manifest"]:
  for item in ep["frames"]:
   if sha(dataset/item["path"])!=item["sha256"]:raise RuntimeError(f"dataset file mismatch: {item['path']}")
 return{"protocol_commit_sha":head,"lpwm_source_sha":source,"dataset_tree_sha256":DATASET_SHA,"dataset_manifest_sha256":freeze["dataset_manifest_sha256"],"environment_manifest_sha256":ENV_SHA}
