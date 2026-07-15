from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.backend.rei.evaluation.integrated_benchmark import (
    C7_ABLATION_FAMILIES,
    C7_METRIC_DIMENSIONS,
    C7_REPORT_FILENAMES,
    C7IntegratedBenchmarkReport,
    C7ReportExistsError,
    C7ReportMismatchError,
    check_c7_report,
    evaluate_c7_integrated_benchmark,
    load_c7_manifest,
    render_c7_report,
    validate_c7_imported_evidence,
    verify_c7_source_artifacts,
    write_c7_report,
)
from app.backend.rei.ids import content_id, sha256_hex


REPO_ROOT = Path(__file__).parents[2]
MANIFEST_PATH = (
    REPO_ROOT
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "c7_integrated"
    / "manifest.json"
)
RUNNER = REPO_ROOT / "scripts" / "run_rei_integrated_benchmark.py"

EXPECTED_REPORT_FILENAMES = (
    "integrated_benchmark.json",
    "controlled_profile.json",
    "person_causality.json",
    "ablations.json",
    "failures.jsonl",
    "dimensions.md",
    "provenance.json",
)
EXPECTED_ABLATION_ARMS = {
    "racio_provider": ("deterministic", "qwen3.5_27b_v5"),
    "emocio_cognition_mode": (
        "structured_only",
        "render_observe",
        "visual_cognition",
    ),
    "instinkt_effect_source": ("manual_effects", "auto_mapper"),
    "interpreter_input_mode": ("structured_only", "vlm"),
    "ego_motif_mode": ("structured_motif", "semantic_motif_hypothesis"),
    "acceptance_mode": ("accepting", "mixed", "conflicted"),
}
EXPECTED_METRIC_DIMENSIONS = (
    "processor_route_identity",
    "source_grounding",
    "option_choice",
    "abstention",
    "translation_fidelity",
    "character_causality",
    "conscious_behavior_divergence",
    "spoznanje",
    "cross_language_consistency",
    "visual_robustness",
    "body_mapper_agreement",
    "longitudinal_motif_precision",
    "latency",
    "vram",
    "ram",
    "artifact_size",
    "failure_mode",
)
EXPECTED_BLOCKER_CODES = (
    "c3_model_quality_gate_failed",
    "c4_semantic_visual_gate_open",
    "vlm_interpreter_arm_not_executed",
    "semantic_motif_arm_not_executed",
    "uniform_resource_telemetry_missing",
)


@pytest.fixture(scope="module")
def report() -> C7IntegratedBenchmarkReport:
    return evaluate_c7_integrated_benchmark(REPO_ROOT)


def _rehash_report(payload: dict[str, object]) -> None:
    base = {
        key: value
        for key, value in payload.items()
        if key not in {"report_id", "report_hash"}
    }
    payload["report_id"] = content_id("c7_integrated_benchmark", base)
    payload["report_hash"] = sha256_hex(
        {"report_id": payload["report_id"], **base}
    )


def _rehash_failure(payload: dict[str, object], index: int) -> None:
    failure = payload["failures"][index]
    base = {
        key: value
        for key, value in failure.items()
        if key not in {"failure_id", "failure_hash"}
    }
    failure["failure_id"] = content_id("c7_failure", base)
    failure["failure_hash"] = sha256_hex(
        {"failure_id": failure["failure_id"], **base}
    )


def _rehash_person(payload: dict[str, object]) -> None:
    person = payload["person_causality"]
    base = {
        key: value
        for key, value in person.items()
        if key not in {"report_id", "report_hash"}
    }
    person["report_id"] = content_id("person_causality_report", base)
    person["report_hash"] = sha256_hex(
        {"report_id": person["report_id"], **base}
    )


def _run_cli(output_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--repository-root",
            str(REPO_ROOT),
            "--manifest-path",
            str(MANIFEST_PATH),
            "--output-root",
            str(output_root),
            *extra_args,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_report_has_exact_six_ablations_and_seventeen_dimensions(
    report: C7IntegratedBenchmarkReport,
) -> None:
    assert C7_REPORT_FILENAMES == EXPECTED_REPORT_FILENAMES
    assert C7_ABLATION_FAMILIES == tuple(EXPECTED_ABLATION_ARMS)
    assert C7_METRIC_DIMENSIONS == EXPECTED_METRIC_DIMENSIONS
    assert report.manifest.required_ablation_families == tuple(
        EXPECTED_ABLATION_ARMS
    )
    assert report.manifest.required_metric_dimensions == EXPECTED_METRIC_DIMENSIONS

    assert tuple(item.family for item in report.ablations) == tuple(
        EXPECTED_ABLATION_ARMS
    )
    assert {
        item.family: tuple(arm.arm_id for arm in item.arms)
        for item in report.ablations
    } == EXPECTED_ABLATION_ARMS
    assert len(report.ablations) == 6
    assert sum(len(item.arms) for item in report.ablations) == 14
    assert all(
        arm.current_model_call_count == 0
        for item in report.ablations
        for arm in item.arms
    )
    assert all(item.interaction_effects_measured is False for item in report.ablations)

    assert tuple(item.dimension for item in report.metrics) == (
        EXPECTED_METRIC_DIMENSIONS
    )
    assert len(report.metrics) == 17
    assert (
        report.passed_metric_count,
        report.blocked_metric_count,
        report.observed_metric_count,
        report.not_measured_metric_count,
    ) == (7, 6, 3, 1)


def test_report_preserves_model_free_blocked_authority_boundaries_and_cohorts(
    report: C7IntegratedBenchmarkReport,
) -> None:
    assert report.manifest.current_model_calls_allowed is False
    assert report.current_model_call_count == 0
    assert report.historical_model_call_count == 32
    assert report.technical_contract_passed is True
    assert report.research_quality_status == "blocked"
    assert report.research_quality_status == (
        report.manifest.expected_research_quality_status
    )
    assert report.research_readiness_blocker_codes == EXPECTED_BLOCKER_CODES
    assert tuple(item.blocker_code for item in report.failures) == (
        EXPECTED_BLOCKER_CODES
    )

    assert report.aggregate_score_present is False
    assert report.interaction_effects_measured is False
    assert report.semantic_authority_granted is False
    assert report.production_authority_granted is False
    assert report.manifest.semantic_authority_granted is False
    assert report.manifest.production_authority_granted is False
    assert "score" not in type(report).model_fields

    controlled = report.controlled_profile
    assert (
        controlled.fixture_count,
        controlled.profile_count,
        controlled.mode_count,
        controlled.total_row_count,
    ) == (12, 13, 3, 468)
    assert controlled.native_processor_executions == 0
    assert controlled.semantic_authority_granted is False

    person = report.person_causality
    assert person.case_count == 4
    assert person.passing_case_count == 4
    assert person.shared_initial_condition_case_count == 4
    assert person.initial_native_invariance_case_count == 4
    assert person.fixed_world_character_invariance_case_count == 4
    assert person.literal_character_leakage_count == 0
    assert person.gate_passed is True
    assert person.semantic_authority_granted is False


def test_cold_source_validation_replays_the_pinned_evidence(
    report: C7IntegratedBenchmarkReport,
) -> None:
    manifest, manifest_sha256 = load_c7_manifest(MANIFEST_PATH)
    refs, payloads = verify_c7_source_artifacts(
        repository_root=REPO_ROOT,
        manifest=manifest,
    )
    imported, resources = validate_c7_imported_evidence(
        repository_root=REPO_ROOT,
        payloads=payloads,
    )

    assert manifest == report.manifest
    assert manifest_sha256 == report.manifest_sha256
    assert manifest_sha256 == hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    assert refs == report.source_artifacts
    assert imported == report.imported_evidence
    assert resources == report.resource_observations
    assert len(refs) == 11
    assert all(item.cold_verified is True for item in refs)


def test_cold_source_validation_rejects_a_tampered_pin(tmp_path: Path) -> None:
    manifest, _ = load_c7_manifest(MANIFEST_PATH)
    tampered_root = tmp_path / "tampered-repository"
    for index, spec in enumerate(manifest.source_artifacts):
        source = REPO_ROOT / spec.path
        destination = tampered_root / spec.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = source.read_bytes()
        if index == 0:
            payload = bytes([payload[0] ^ 1]) + payload[1:]
        destination.write_bytes(payload)

    with pytest.raises(ValueError, match="C7 pinned evidence differs"):
        verify_c7_source_artifacts(
            repository_root=tampered_root,
            manifest=manifest,
        )


def test_manifest_rejects_relabelled_historical_evidence_scope(
    tmp_path: Path,
) -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["source_artifacts"][2]["evidence_scope"] = "current_tree_model_free"
    tampered_manifest_path = tmp_path / "manifest-scope.json"
    tampered_manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="paths or scopes differ"):
        load_c7_manifest(tampered_manifest_path)


def test_report_is_content_addressed_and_rehashed_tampering_is_rejected(
    report: C7IntegratedBenchmarkReport,
) -> None:
    assert report.report_id == (
        "c7_integrated_benchmark_57c1db13906284edd641ac7cfbc6f5dc"
    )
    assert report.report_hash == (
        "fb96308989974776e29fbe8c7e1e185211f77155d4726a453e1158b5a3c16adc"
    )
    cold = C7IntegratedBenchmarkReport.model_validate_json(
        report.canonical_json_bytes()
    )
    assert cold == report
    assert cold.canonical_json_bytes() == report.canonical_json_bytes()

    bad_hash = report.model_dump(mode="python", round_trip=True)
    bad_hash["report_hash"] = "0" * 64
    with pytest.raises(ValueError, match="report hash differs from content"):
        C7IntegratedBenchmarkReport.model_validate(bad_hash)

    rehashed_tamper = report.model_dump(mode="python", round_trip=True)
    rehashed_tamper["ablations"][0]["arms"][0]["current_model_call_count"] = 1
    _rehash_report(rehashed_tamper)
    with pytest.raises(ValueError, match="model-call count differs from its arms"):
        C7IntegratedBenchmarkReport.model_validate(rehashed_tamper)


def test_rehashed_metric_failure_ablation_and_corpus_relabels_are_rejected(
    report: C7IntegratedBenchmarkReport,
) -> None:
    metric_tamper = report.model_dump(mode="python", round_trip=True)
    metric_tamper["metrics"][0]["numerator"] = 1
    _rehash_report(metric_tamper)
    with pytest.raises(ValueError, match="metrics differ from their source-derived"):
        C7IntegratedBenchmarkReport.model_validate(metric_tamper)

    failure_tamper = report.model_dump(mode="python", round_trip=True)
    failure_tamper["failures"][0]["detail"] = "relabelled blocker detail"
    _rehash_failure(failure_tamper, 0)
    _rehash_report(failure_tamper)
    with pytest.raises(ValueError, match="failure records differ"):
        C7IntegratedBenchmarkReport.model_validate(failure_tamper)

    ablation_tamper = report.model_dump(mode="python", round_trip=True)
    ablation_tamper["ablations"][0]["arms"][0]["limitation"] = (
        "relabelled deterministic evidence"
    )
    _rehash_report(ablation_tamper)
    with pytest.raises(ValueError, match="ablations differ"):
        C7IntegratedBenchmarkReport.model_validate(ablation_tamper)

    corpus_tamper = report.model_dump(mode="python", round_trip=True)
    corpus_tamper["person_causality"]["source_corpus_sha256"] = "1" * 64
    _rehash_person(corpus_tamper)
    _rehash_report(corpus_tamper)
    with pytest.raises(ValueError, match="technical inputs"):
        C7IntegratedBenchmarkReport.model_validate(corpus_tamper)


def test_render_is_deterministic_dimension_preserving_and_exact(
    report: C7IntegratedBenchmarkReport,
) -> None:
    first = render_c7_report(report)
    second = render_c7_report(
        C7IntegratedBenchmarkReport.model_validate_json(
            report.canonical_json_bytes()
        )
    )

    assert first == second
    assert tuple(first) == EXPECTED_REPORT_FILENAMES
    assert all(first[name] for name in EXPECTED_REPORT_FILENAMES)
    assert C7IntegratedBenchmarkReport.model_validate_json(
        first["integrated_benchmark.json"]
    ) == report

    ablations = json.loads(first["ablations.json"])
    assert ablations["aggregate_score_present"] is False
    assert ablations["interaction_effects_measured"] is False
    assert len(ablations["ablations"]) == 6
    assert len(first["failures.jsonl"].splitlines()) == 5

    dimensions = first["dimensions.md"].decode("utf-8")
    assert "Aggregate REI score: **absent by contract**" in dimensions
    assert all(f"`{dimension}`" in dimensions for dimension in EXPECTED_METRIC_DIMENSIONS)

    provenance = json.loads(first["provenance.json"])
    assert provenance["report_id"] == report.report_id
    assert provenance["report_hash"] == report.report_hash
    assert provenance["current_model_call_count"] == 0
    assert provenance["research_quality_status"] == "blocked"
    assert provenance["semantic_authority_granted"] is False
    assert provenance["production_authority_granted"] is False


def test_writer_is_create_only_and_checker_requires_exact_bytes_and_file_set(
    report: C7IntegratedBenchmarkReport,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "c7-report"
    paths = write_c7_report(report, output_root)

    assert tuple(path.name for path in paths) == EXPECTED_REPORT_FILENAMES
    assert check_c7_report(report, output_root) == paths
    with pytest.raises(C7ReportExistsError, match="create-only"):
        write_c7_report(report, output_root)

    dimensions_path = output_root / "dimensions.md"
    original_dimensions = dimensions_path.read_bytes()
    dimensions_path.write_bytes(original_dimensions + b"tampered\n")
    with pytest.raises(C7ReportMismatchError, match="bytes differ: dimensions.md"):
        check_c7_report(report, output_root)

    dimensions_path.write_bytes(original_dimensions)
    extra_path = output_root / "unexpected.txt"
    extra_path.write_text("unexpected", encoding="utf-8")
    with pytest.raises(C7ReportMismatchError, match="artifact set differs"):
        check_c7_report(report, output_root)

    contaminated_root = tmp_path / "contaminated-report"
    contaminated_root.mkdir()
    (contaminated_root / "unexpected.txt").write_text(
        "unexpected",
        encoding="utf-8",
    )
    with pytest.raises(C7ReportExistsError, match="already exists"):
        write_c7_report(report, contaminated_root)


def test_cli_create_check_and_require_research_ready_exit_contract(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "cli-report"

    created = _run_cli(output_root)
    assert created.returncode == 0, created.stderr
    assert created.stderr == ""
    created_summary = json.loads(created.stdout)
    assert created_summary["action"] == "created"
    assert created_summary["technical_contract_passed"] is True
    assert created_summary["research_quality_status"] == "blocked"
    assert created_summary["current_model_call_count"] == 0
    assert created_summary["controlled_profile_row_count"] == 468
    assert created_summary["person_causality_case_count"] == 4
    assert tuple(sorted(path.name for path in output_root.iterdir())) == tuple(
        sorted(EXPECTED_REPORT_FILENAMES)
    )

    checked = _run_cli(output_root, "--check")
    assert checked.returncode == 0, checked.stderr
    assert checked.stderr == ""
    checked_summary = json.loads(checked.stdout)
    assert checked_summary["action"] == "checked"
    assert checked_summary["report_id"] == created_summary["report_id"]
    assert checked_summary["report_hash"] == created_summary["report_hash"]

    research_gate = _run_cli(
        output_root,
        "--check",
        "--require-research-ready",
    )
    assert research_gate.returncode == 2, research_gate.stderr
    assert research_gate.stderr == ""
    research_summary = json.loads(research_gate.stdout)
    assert research_summary["action"] == "checked"
    assert research_summary["research_quality_status"] == "blocked"
    assert research_summary["semantic_authority_granted"] is False
    assert research_summary["production_authority_granted"] is False
    assert research_summary["aggregate_score_present"] is False
