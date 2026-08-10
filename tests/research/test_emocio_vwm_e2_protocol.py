from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[2]
E2 = REPO / "research" / "emocio_vwm_mvp_e2"
E1R_SHA = "01aa8d3e10c04275e528fd45796d0c4c5bb4ac0b"
LPWM_SHA = "4cf53c403433e64c01652ac2adbec66231a46dea"
DATASET_SHA = "f84bcb3f93734b99d5ebb62a3c02718b14f713b4265d006635770daf3d1e7991"


def load(relative: str) -> dict:
    return json.loads((E2 / relative).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def test_e1r_medium_pass_is_narrow_and_exact() -> None:
    review = load("specs/e1r_prerequisite_review.json")
    assert review["attempt"] == 3
    assert review["e1r_commit_sha"] == E1R_SHA
    assert review["medium_status"] == "passed"
    assert review["model_fit_claim"] is False


def test_lpwm_source_and_from_scratch_policy_are_frozen() -> None:
    source = load("specs/lpwm_source_pin.json")
    protocol = load("specs/e2_protocol_freeze.json")
    assert source["expected_commit_sha"] == LPWM_SHA
    assert source["core_modifications_allowed"] is False
    assert source["model_substitution_allowed"] is False
    assert source["weights"] == {
        "acquisition_allowed": False,
        "initialization": "from_scratch",
        "pretrained_checkpoint": None,
    }
    assert protocol["lpwm"]["pretrained_checkpoint_sha256"] is None
    assert protocol["e1r_prerequisite"]["commit_sha"] == E1R_SHA


def test_static_lpwm_interface_audit_matches_frozen_calls() -> None:
    audit = load("specs/lpwm_interface_audit.json")
    config = load("specs/model_config.json")["architecture"]
    assert audit["source_commit_sha"] == LPWM_SHA
    assert audit["static_source_audit_status"] == "passed_before_first_lpwm_import"
    assert set(audit["constructor_required_frozen_arguments"]).issubset(config)
    assert {"x", "x_goal", "cond_steps", "return_z"}.issubset(audit["sample_from_x_arguments"])


def test_dataset_manifest_is_complete_opaque_and_external() -> None:
    frozen = load("dataset/frozen_dataset_manifest.json")
    checksums = load("dataset/dataset_checksums.json")
    audit = load("dataset/dataset_boundary_audit.json")
    assert frozen["dataset_tree_sha256"] == DATASET_SHA
    assert frozen["file_count"] == len(checksums["files"]) == 313
    assert frozen["total_bytes"] == sum(record["bytes"] for record in checksums["files"])
    assert not Path(frozen["environment_relative_root"]).is_absolute()
    paths = [record["path"] for record in checksums["files"]]
    assert len(paths) == len(set(paths))
    assert all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in paths)
    visible = [path for path in paths if path.startswith("model_visible/")]
    assert len(visible) == 300
    pattern = re.compile(r"^model_visible/[0-9a-f]{24}/[0-9]{6}\.(png|mp4)$")
    assert all(pattern.fullmatch(path) for path in visible)
    assert audit["model_visible_json_files"] == 0
    assert audit["mp4_ffprobe_stream_and_metadata_validation"] == "passed"
    payload = json.dumps(checksums["files"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == DATASET_SHA


def test_generator_hash_matches_frozen_dataset() -> None:
    frozen = load("dataset/frozen_dataset_manifest.json")
    assert digest(E2 / "tools" / "render_frozen_dataset.mjs") == frozen["generator_source_sha256"]
    assert frozen["rerender_after_protocol_freeze_allowed"] is False


def test_model_visible_contract_is_rgb_only() -> None:
    contract = load("specs/model_visible_contract.json")
    config = load("specs/model_config.json")
    assert contract["allowed_model_inputs"] == ["rgb_observation_prefix", "rgb_image_goal"]
    assert contract["conditioning_frames"] == 6
    assert contract["goal_frame"] == 23
    assert contract["dedicated_self_reference"] == {
        "status": "unsupported_by_unmodified_lpwm",
        "ablation_status": "not_tested",
        "synthetic_replacement_allowed": False,
    }
    architecture = config["architecture"]
    assert architecture["action_condition"] is False
    assert architecture["random_action_condition"] is False
    assert architecture["language_condition"] is False
    assert architecture["img_goal_condition"] is True


def test_visual_adapter_has_no_semantic_sidecar_dependency() -> None:
    path = E2 / "python" / "emocio_vwm_mvp_e2" / "visual_dataset.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_literals = {
        "scenario_text", "path_name", "role_name", "entity_id", "option_description",
        "option_id", "scene_graph", "evidence_class", "character", "semantic_action",
    }
    assert forbidden_literals.isdisjoint(set(re.findall(r"[a-z_]+", source)))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert any(isinstance(call.func, ast.Attribute) and call.func.attr == "convert" for call in calls)
    assert "model_visible" in source
    assert ".json" not in source


def test_no_lpwm_or_torch_import_precedes_runtime_preflight() -> None:
    runner = (E2 / "python" / "emocio_vwm_mvp_e2" / "runner.py").read_text(encoding="utf-8")
    assert runner.index("preflight(repo_root") < runner.index("import torch")
    for relative in ("runner.py", "model_adapter.py", "visual_dataset.py"):
        tree = ast.parse((E2 / "python" / "emocio_vwm_mvp_e2" / relative).read_text(encoding="utf-8"))
        top_imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        names = {
            alias.name.split(".")[0]
            for node in top_imports
            for alias in node.names
        }
        assert "torch" not in names
        assert "models" not in names


def test_optimizer_budget_seed_and_oom_fallback_are_exact() -> None:
    plan = load("specs/execution_plan.json")
    assert plan["measured_run_count"] == 1
    assert plan["optimizer_steps"] == 1200
    assert plan["determinism"]["seed"] == 73013
    assert plan["early_stop"]["enabled"] is False
    assert plan["optimizer"] == {
        "betas": [0.9, 0.999],
        "eps": 1e-06,
        "gradient_accumulation_steps": 1,
        "learning_rate": 8e-05,
        "name": "Adam",
        "scheduler": None,
        "weight_decay": 0.0,
    }
    assert plan["oom_fallback"]["allowed_only_before_first_optimizer_step"] is True
    assert plan["oom_fallback"]["second_failure_verdict"] == "not_executed_resource_block"


def test_hard_gates_and_verdicts_are_immutable_and_distinct() -> None:
    acceptance = load("specs/acceptance.json")
    verdicts = load("specs/verdict_taxonomy.json")
    assert acceptance["hard_gates"] == {
        "duplicate_person_rate_max": 0.01,
        "foreground_lpips_max": 0.18,
        "goal_marker_accuracy_min": 0.9,
        "identity_stability_min": 0.98,
        "person_count_accuracy_min": 0.98,
    }
    assert acceptance["numeric_threshold_changes_after_freeze_allowed"] is False
    assert verdicts["precedence"] == [
        "medium_failed", "not_executed_resource_block", "model_fit_failed", "model_fit_promising",
    ]
    assert "full run" in verdicts["model_fit_failed"]
    assert "Environment" in verdicts["not_executed_resource_block"]


def test_sampling_is_preregistered_without_manual_selection() -> None:
    sampling = load("specs/sampling_plan.json")
    assert sampling["repeat_sample_seeds"] == [83001, 83001]
    assert sampling["distinct_sample_seeds"] == list(range(83011, 83019))
    assert sampling["selection_rule"]["manual_selection_allowed"] is False
    assert sampling["goal_sensitivity"]["model_inputs_remain_visual_only"] is True


def test_environment_is_exact_and_blackwell_capable() -> None:
    dependency = load("specs/dependency_manifest.json")
    overlay = load("specs/compatibility_overlay.json")
    assert dependency["install_after_protocol_push_only"] is True
    assert dependency["packages"]["torch"] == "2.11.0"
    assert dependency["packages"]["torchvision"] == "0.26.0"
    assert dependency["pytorch_index_url"].endswith("/cu130")
    smoke = overlay["cuda_smoke_requirements"]
    assert smoke["torch_arch_list_contains"] == "sm_120"
    assert smoke["device_name_contains"] == "NVIDIA GeForce RTX 5090"


def test_metric_definition_requires_explicit_hashed_weights_and_generated_pixels() -> None:
    metric = load("specs/metric_config.json")
    acceptance = load("specs/acceptance.json")
    weights = metric["foreground_lpips"]["network_weights"]
    assert weights["automatic_download_during_evaluation_allowed"] is False
    assert weights["hashes_recorded_before_metric_use"] is True
    assert acceptance["metric_source"] == "generated_model_visuals_against_evaluator_only_gold"
    assert acceptance["particle_diagnostics"]["numeric_pass_thresholds"] is None


def test_protocol_lineage_is_complete_and_byte_exact() -> None:
    lineage = load("protocol_lineage.json")
    records = lineage["files"]
    assert lineage["file_count"] == len(records)
    assert any(record["path"] == "python/emocio_vwm_mvp_e2/runner.py" for record in records)
    assert any(record["path"] == "scripts/run_emocio_vwm_e2.py" for record in records)
    assert any(record["path"] == "tests/research/test_emocio_vwm_e2_protocol.py" for record in records)
    for record in records:
        base = E2 if record["root"] == "e2" else REPO
        path = base / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert digest(path) == record["sha256"]
        assert not record["path"].startswith("app/backend/rei/")
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == lineage["protocol_tree_sha256"]


def test_python_sources_compile_without_importing_lpwm() -> None:
    for path in sorted((E2 / "python").rglob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    for path in (
        REPO / "scripts" / "freeze_emocio_vwm_e2_dataset.py",
        REPO / "scripts" / "run_emocio_vwm_e2.py",
        REPO / "scripts" / "seal_emocio_vwm_e2_protocol.py",
    ):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_optional_local_external_dataset_matches_every_frozen_byte() -> None:
    value = os.environ.get("EMOCIO_E2_DATASET_ROOT")
    if not value:
        return
    root = Path(value)
    checksums = load("dataset/dataset_checksums.json")
    actual = [path.relative_to(root).as_posix() for path in sorted(root.rglob("*")) if path.is_file()]
    assert actual == [record["path"] for record in checksums["files"]]
    for record in checksums["files"]:
        path = root / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert digest(path) == record["sha256"]
