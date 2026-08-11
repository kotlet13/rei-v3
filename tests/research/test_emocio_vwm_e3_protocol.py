from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
import numpy as np
REPO=Path(__file__).resolve().parents[2];E3=REPO/"research"/"emocio_vwm_mvp_e3";sys.path.insert(0,str(E3/"python"))
from emocio_vwm_mvp_e3.metrics import HARD_GATES,aggregate,evaluate_gates,frame_metrics
from emocio_vwm_mvp_e3.packaging import seal

def load(name):return json.loads((E3/"specs"/name).read_text(encoding="utf-8"))
def test_dataset_freeze_and_visual_boundary():
    f=load("dataset_freeze.json");m=load("frozen_dataset_manifest.json");assert f["episodes"]==256 and f["splits"]=={"train":192,"validation":32,"holdout":32};assert m["model_visible"]["content"]=="opaque_rgb_png_frames_only";assert m["evaluator_only"]["never_model_visible"] is True
    assert all(x["kind"]=="rgb" and x["path"].startswith("model_visible/") or x["kind"]!="rgb" and x["path"].startswith("evaluator_only/") for e in m["episodes_manifest"] for x in e["frames"])
def test_metric_fake_fixture_and_gates():
    truth=np.zeros((8,8));truth[2:6,2:6]=1;alpha=np.zeros((2,8,8));alpha[0,2:6,2:6]=1
    x=frame_metrics(np.array([.9,.1]),alpha,truth,[truth],.2,.5);a=aggregate([x]);a["foreground_lpips"]=.1;g=evaluate_gates(a)
    assert x.active_count==1 and x.recall==x.precision==1 and x.person_covered==1 and x.bypass==.6
    assert g["active_particle_count_mean"]["passed"] is False and HARD_GATES["classification"]==("!=","collapsed_objectness")
def test_packaging_fixture_has_no_legacy_key_dependency(tmp_path):
    src=tmp_path/"src";src.mkdir();(src/"verdict.json").write_text("{}")
    m=seal(src,tmp_path/"sealed",("verdict.json",));assert m["files"][0]["path"]=="verdict.json"
def test_protocol_fixes_upstream_and_target_contracts():
    p=load("e3_protocol_freeze.json");assert p["lineage"]["e2r_result_sha"]=="36853bc1b1487e380daf1fb3618370720190aaad";assert p["model"]["lpwm_source_sha"]=="4cf53c403433e64c01652ac2adbec66231a46dea";assert p["target"]["optimizer_steps"]==2400;assert p["target"]["warmup_entire_run"] is True;assert p["target"]["measured_runs"]==1;assert p["scope"]["social_model_fit"] is False
def test_protocol_lineage_matches_every_frozen_file():
    lineage=json.loads((E3/"protocol_lineage.json").read_text())
    for item in lineage["files"]:
        p=REPO/item["path"];assert p.stat().st_size==item["bytes"];assert hashlib.sha256(p.read_bytes()).hexdigest()==item["sha256"]
