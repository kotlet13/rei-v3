from __future__ import annotations
import json
from pathlib import Path
REPO=Path(__file__).resolve().parents[2];RESULT=REPO/"research/emocio_vwm_mvp_e3/result"
def load(name):return json.loads((RESULT/name).read_text(encoding="utf-8-sig"))
def test_e3_stops_as_positive_control_failed_without_target_training():
 v=load("verdict.json");f=load("forensic_summary.json");assert v["verdict"]=="positive_control_failed";assert v["checkpoint_loaded"] is True and v["forward_inference_completed"] is True;assert v["target_training_started"] is False and v["target_optimizer_steps"]==0 and v["target_model_fit_failure_claimed"] is False;assert f["target"]["model_constructed"] is False
def test_official_control_and_dataset_lineage_are_exact():
 a=load("lineage/acquisition_manifest.json");assert a["checkpoint"]["sha256"]=="6d62bf5a2f8977c8e4cea10250ac73fea4dbe61dad997607e7df959a0a9aa731";assert a["dataset"]["revision"]=="2a152aa6361587b1a50db2ff2c05c31488a49c33";assert a["dataset"]["tree_sha256"]=="6026ac8102403a014a8ea14e0e9ca0ee8fa3391889524ce70aeb32842a73b8f6";assert a["dataset"]["file_count"]==21
def test_failure_is_exact_adapter_node_not_model_fit():
 r=load("positive_control/record.json");f=load("forensic_summary.json");assert r["status"]=="failed";assert "shape '[1, 21, 21, 64, 1]' is invalid" in r["exception"]["message"];assert f["positive_control"]["failure_node"]=="positive_control.obj_on_reshape";assert f["target_model_fit_failure_claimed"] is False
def test_environment_and_runtime_governance_are_preserved():
 e=load("lineage/environment_manifest.json");f=load("forensic_summary.json");assert e["torch_version"]=="2.11.0+cu130";assert f["social_model_fit_started"] is False;assert f["dynamics_gate_started"] is False;assert f["active_rei_runtime_modified"] is False
