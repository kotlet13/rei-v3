from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
E3R = REPO / "research/emocio_vwm_mvp_e3r"
sys.path.insert(0, str(E3R / "python"))

from emocio_vwm_mvp_e3r.evaluator import evaluate_and_package
from emocio_vwm_mvp_e3r.model_adapter import official_constructor_config
from emocio_vwm_mvp_e3r.shape_contract import ShapeContractError, normalize_lpwm_output_shapes


def outputs(batch=1, timesteps=21, height=8, width=8, k_enc=64, k_dec=30):
    return {
        "rec_rgb": np.zeros((batch * timesteps, 3, height, width), np.float32),
        "bg_rgb": np.zeros((batch, timesteps, 3, height, width), np.float32),
        "dec_objects": np.zeros((batch * timesteps, 3, height, width), np.float32),
        "alpha_masks": np.zeros((batch * timesteps, k_dec, 1, height, width), np.float32),
        "obj_on": np.zeros((batch, timesteps, k_enc, 1), np.float32),
        "mu_tot": np.zeros((batch, timesteps, k_enc, 2), np.float32),
    }


def test_observed_official_shapes_are_normalized_without_time_duplication():
    normalized, manifest = normalize_lpwm_output_shapes(outputs(), 1, 21)
    assert normalized["obj_on"].shape == (1, 21, 64, 1)
    assert normalized["rec_rgb"].shape == (1, 21, 3, 8, 8)
    assert normalized["alpha_masks"].shape == (1, 21, 30, 1, 8, 8)
    assert normalized["mu_tot"].shape == (1, 21, 64, 2)
    assert manifest["particle_axes"] == {
        "K_enc": 64,
        "K_dec": 30,
        "equality_required": False,
        "active_particle_metrics_axis": "K_enc",
        "mask_coverage_metrics_axis": "K_dec",
    }


def test_batch_two_flat_and_shaped_variants():
    value = outputs(batch=2)
    value["bg_rgb"] = value["bg_rgb"].reshape(42, 3, 8, 8)
    value["alpha_masks"] = value["alpha_masks"].reshape(2, 21, 30, 1, 8, 8)
    value["obj_on"] = value["obj_on"].reshape(42, 64, 1)
    value["mu_tot"] = value["mu_tot"].reshape(42, 64, 2)
    normalized, _ = normalize_lpwm_output_shapes(value, 2, 21)
    assert all(tensor.shape[:2] == (2, 21) for tensor in normalized.values())


@pytest.mark.parametrize(
    "name,value",
    [
        ("wrong_time", lambda x: x.update(obj_on=np.zeros((1, 20, 64, 1), np.float32))),
        ("missing_background", lambda x: x.pop("bg_rgb")),
        ("legacy_background", lambda x: (x.pop("bg_rgb"), x.update(bg_rec=np.zeros((21, 3, 8, 8))))),
    ],
)
def test_fail_closed_contract_cases(name, value):
    broken = outputs()
    value(broken)
    with pytest.raises(ShapeContractError):
        normalize_lpwm_output_shapes(broken, 1, 21)


def test_wrong_reported_element_count_fails_closed():
    class BadElements:
        shape = (21, 3, 8, 8)

        def numel(self):
            return 1

    broken = outputs()
    broken["rec_rgb"] = BadElements()
    with pytest.raises(ShapeContractError, match="element count"):
        normalize_lpwm_output_shapes(broken, 1, 21)


def test_fake_end_to_end_target_evaluator_fixture(tmp_path):
    value = outputs(timesteps=2, k_enc=4, k_dec=3)
    value["rec_rgb"] += 0.3
    value["dec_objects"] += 0.2
    value["alpha_masks"][:, 0] = 0.8
    value["obj_on"][:, :, 0] = 0.9
    value["mu_tot"][:, :, 0] = (0.0, 0.0)
    manifest = evaluate_and_package(value, 1, 2, tmp_path / "fixture")
    assert manifest["verdict"]["verdict"] == "fixture_passed"
    assert manifest["metrics"]["active_particle_count_mean"] == 1
    assert {item["path"].split("/")[0] for item in manifest["files"]} >= {
        "full", "background", "foreground", "mask_union", "particles"
    }


def test_official_hparams_mapping_and_rollout_are_upstream_faithful():
    target = json.loads((REPO / "research/emocio_vwm_mvp_e3/specs/model_config.json").read_text())
    hparams = dict(target["architecture"])
    hparams["ch"] = hparams.pop("cdim")
    hparams["context_dist"] = hparams.pop("ctx_dist")
    hparams["num_static_frames"] = hparams.pop("n_static_frames")
    hparams["normalize_rgb"] = target["loss"]["normalize_rgb"]
    constructor = official_constructor_config(hparams)
    assert constructor["cdim"] == hparams["ch"]
    assert constructor["ctx_dist"] == hparams["context_dist"]
    assert constructor["n_static_frames"] == hparams["num_static_frames"]
    assert constructor["n_views"] == 1
    assert constructor["language_condition"] is False
    assert constructor["img_goal_condition"] is False
    runner = (E3R / "python/emocio_vwm_mvp_e3r/runner.py").read_text()
    adapter = (E3R / "python/emocio_vwm_mvp_e3r/model_adapter.py").read_text()
    assert "sample_from_x" in adapter and "cond_steps=6" in adapter and "num_steps=15" in adapter
    assert "rollout_nonempty" not in runner
    assert not re.search(r"\[\s*['\"]bg_rec['\"]\s*\]", runner)


def test_frozen_protocol_preserves_e3_target_and_verdict_boundaries():
    protocol = json.loads((E3R / "specs/e3r_protocol_freeze.json").read_text())
    assert protocol["direct_parent"] == "3d56eeaad45ce21eae36049b9bfe63cc3b52b045"
    assert protocol["pins"]["target_model_config_sha256"] == "30c96f5e521b0025e6fc62fa0d3a230448f5cf680aefc4727d6162711b09ca07"
    assert protocol["target"]["optimizer_steps"] == 2400
    assert protocol["target"]["seed"] == 73013
    assert protocol["positive_control"]["must_pass_before_target"] is True
    assert protocol["scope"]["active_rei_runtime_modified"] is False
    taxonomy = protocol["verdict_taxonomy"]
    assert "adapter" in taxonomy["not_executed_resource_block"]
    assert "complete harness" in taxonomy["positive_control_failed"]


def test_protocol_lineage_matches_every_frozen_file():
    lineage = json.loads((E3R / "protocol_lineage.json").read_text())
    for item in lineage["files"]:
        path = REPO / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
