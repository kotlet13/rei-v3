from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
E2 = REPO / "research" / "emocio_vwm_mvp_e2"
E2R = REPO / "research" / "emocio_vwm_mvp_e2r"
E1R_SHA = "01aa8d3e10c04275e528fd45796d0c4c5bb4ac0b"
E2_PROTOCOL_SHA = "e409ecbdebd220db9da934827f2b1e0a7d73b65c"
E2_RESULT_SHA = "d1415007b97e651e59953bbdf093d64516603365"
LPWM_SHA = "4cf53c403433e64c01652ac2adbec66231a46dea"
DATASET_SHA = "f84bcb3f93734b99d5ebb62a3c02718b14f713b4265d006635770daf3d1e7991"
ENVIRONMENT_SHA = "2f88a3f694eed8c7af84959e0a53db09a41d10614bcf423b8a100186497dcfc2"


def load(relative: str) -> dict:
    return json.loads((E2R / relative).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def test_e2_is_frozen_as_execution_block_with_zero_steps() -> None:
    protocol = load("specs/e2r_protocol_freeze.json")
    assert protocol["e2_frozen"] == {
        "protocol_commit_sha": E2_PROTOCOL_SHA,
        "result_commit_sha": E2_RESULT_SHA,
        "verdict": "not_executed_resource_block",
        "optimizer_steps_completed": 0,
        "failure_evidence_mutation_allowed": False,
    }


def test_immutable_model_dataset_environment_and_e1r_lineage() -> None:
    lineage = load("specs/e2r_protocol_freeze.json")["immutable_lineage"]
    assert lineage == {
        "lpwm_source_sha": LPWM_SHA,
        "e1r_commit_sha": E1R_SHA,
        "dataset_tree_sha256": DATASET_SHA,
        "environment_manifest_sha256": ENVIRONMENT_SHA,
    }
    assert json.loads((E2 / "specs" / "model_config.json").read_text())["initialization"]["checkpoint"] is None


def test_warn_only_policy_is_exact_and_cublas_precedes_torch_import() -> None:
    policy = load("specs/e2r_protocol_freeze.json")["determinism_policy"]
    assert policy["before_torch_import"] == {"CUBLAS_WORKSPACE_CONFIG": ":4096:8"}
    assert policy["torch"] == {
        "use_deterministic_algorithms": True,
        "warn_only": True,
        "cudnn_benchmark": False,
        "cudnn_deterministic": True,
    }
    assert policy["bitwise_model_optimization_reproducibility_claimed"] is False
    runner = (E2R / "python" / "emocio_vwm_mvp_e2r" / "runner.py").read_text(encoding="utf-8")
    entry = (REPO / "scripts" / "run_emocio_vwm_e2r.py").read_text(encoding="utf-8")
    assert runner.index('os.environ["CUBLAS_WORKSPACE_CONFIG"]') < runner.index("import torch")
    assert entry.index('os.environ["CUBLAS_WORKSPACE_CONFIG"]') < entry.index("from emocio_vwm_mvp_e2r.runner")
    assert "torch.use_deterministic_algorithms(True, warn_only=True)" in runner
    assert "torch.backends.cudnn.benchmark = False" in runner
    assert "torch.backends.cudnn.deterministic = True" in runner


def test_preflight_precedes_torch_and_lpwm_import() -> None:
    runner = (E2R / "python" / "emocio_vwm_mvp_e2r" / "runner.py").read_text(encoding="utf-8")
    assert runner.index("preflight(repo_root") < runner.index("import torch")
    for relative in ("runner.py", "preflight.py"):
        tree = ast.parse((E2R / "python" / "emocio_vwm_mvp_e2r" / relative).read_text(encoding="utf-8"))
        names = {
            alias.name.split(".")[0]
            for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert "torch" not in names
        assert "models" not in names


def test_smokes_are_two_fresh_non_evaluative_one_step_runs() -> None:
    smoke = load("specs/e2r_protocol_freeze.json")["reproducibility_smokes"]
    assert smoke["count"] == 2
    assert smoke["measured_model_fit_runs"] is False
    assert smoke["fresh_from_scratch_model_each"] is True
    assert smoke["same_seed"] == 73013
    assert smoke["backward_per_smoke"] == smoke["optimizer_steps_per_smoke"] == 1
    assert smoke["initial_state_hashes_must_match"] is True
    assert smoke["post_step_state_hashes_must_match"] is False
    assert smoke["selection_use_forbidden"] is True


def test_optimizer_budget_and_oom_fallback_match_e2() -> None:
    e2_plan = json.loads((E2 / "specs" / "execution_plan.json").read_text(encoding="utf-8"))
    plan = load("specs/execution_plan.json")
    assert plan["batch_size"] == 1
    assert plan["optimizer_steps"] == e2_plan["optimizer_steps"] == 1200
    assert plan["optimizer"] == e2_plan["optimizer"]
    assert plan["oom_fallback"] == e2_plan["oom_fallback"]
    assert plan["determinism"]["seed"] == e2_plan["determinism"]["seed"] == 73013
    assert plan["evaluation_every_steps"] == 100
    assert plan["early_stop"]["enabled"] is False


def test_e2r_changes_execution_policy_only() -> None:
    protocol = load("specs/e2r_protocol_freeze.json")
    assert protocol["e2r"] == {
        "phase": "E2R_LPWM_determinism_compatibility_remediation",
        "research_question_changed": False,
        "model_changed": False,
        "dataset_changed": False,
        "hard_gates_changed": False,
        "execution_policy_change_only": True,
    }
    assert "no social model-fit" in protocol["unchanged_constraints"]
    assert "no active REI runtime modification" in protocol["unchanged_constraints"]


def test_evidence_is_persisted_before_backward_and_try_finally_is_present() -> None:
    runner = (E2R / "python" / "emocio_vwm_mvp_e2r" / "runner.py").read_text(encoding="utf-8")
    smoke_start = runner.index("def _run_smoke")
    smoke_end = runner.index("def _compare_smokes")
    smoke = runner[smoke_start:smoke_end]
    assert smoke.index("initial_state_sha256=initial_hash") < smoke.index("loss.backward()")
    assert smoke.index("write_json(record_path, record)") < smoke.index("loss.backward()")
    assert "finally:" in smoke
    for field in (
        "stage", "initial_state_sha256", "forward_status", "finite_loss",
        "captured_warnings", "peak_allocated_vram_bytes", "peak_reserved_vram_bytes",
        "exception", "optimizer_step_count",
    ):
        assert field in smoke


def test_verdicts_preserve_execution_vs_model_fit_boundary() -> None:
    policy = load("specs/e2r_protocol_freeze.json")["verdict_policy"]
    assert policy["backward_or_execution_block_before_budget"] == "not_executed_resource_block"
    assert policy["completed_budget_with_any_hard_gate_failure"] == "model_fit_failed"
    assert policy["completed_budget_with_all_hard_gates_passed"] == "model_fit_promising"
    assert policy["model_fit_promising_scope"] == "technical_overfit_only"


def test_protocol_lineage_is_complete_and_byte_exact() -> None:
    lineage = load("protocol_lineage.json")
    records = lineage["files"]
    assert lineage["file_count"] == len(records)
    assert any(record["path"] == "python/emocio_vwm_mvp_e2r/runner.py" for record in records)
    assert any(record["path"] == "scripts/run_emocio_vwm_e2r.py" for record in records)
    for record in records:
        base = E2R if record["root"] == "e2r" else REPO
        path = base / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert digest(path) == record["sha256"]
        assert not record["path"].startswith("app/backend/rei/")
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == lineage["protocol_tree_sha256"]


def test_python_sources_compile_without_importing_lpwm() -> None:
    for path in sorted((E2R / "python").rglob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    for path in (REPO / "scripts" / "run_emocio_vwm_e2r.py", REPO / "scripts" / "seal_emocio_vwm_e2r_protocol.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
