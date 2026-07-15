from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil

import pytest

from app.backend.rei.ids import canonical_json_bytes, content_id, sha256_hex
from app.gui.semantic_lab import (
    SEMANTIC_LAB_SCHEMA_VERSION,
    SemanticLabIntegrityError,
    _attach_c2_results,
    _confined_file,
    _load_c2_run,
    build_semantic_lab_view,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def semantic_lab_payload() -> dict[str, object]:
    return build_semantic_lab_view(REPOSITORY_ROOT)


def _family(payload: dict[str, object], family_id: str) -> dict[str, object]:
    return next(
        item for item in payload["families"] if item["family_id"] == family_id
    )


def _variant(family: dict[str, object], mode: str) -> dict[str, object]:
    return next(item for item in family["variants"] if item["mode"] == mode)


def _copy_projection_tree(destination: Path) -> Path:
    root = destination / "repository"
    c1_manifest_path = Path("tests/fixtures/semantic_lab_v1/manifest.json")
    c1_manifest = json.loads((REPOSITORY_ROOT / c1_manifest_path).read_bytes())
    relative_paths = [
        Path("knowledge/canon_v2/semantic_lab_v1/c7_integrated/manifest.json"),
        c1_manifest_path,
        Path(
            "Docs/evals/semantic_lab_v1/c2-deterministic-2026-07-14/metrics.json"
        ),
        Path(
            "Docs/evals/semantic_lab_v1/c7-integrated-2026-07-15/"
            "integrated_benchmark.json"
        ),
        *(
            Path("tests/fixtures/semantic_lab_v1") / item["path"]
            for item in c1_manifest["files"]
        ),
    ]
    for relative in relative_paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / relative, target)
    return root


def test_projection_has_exact_counts_order_and_content_hashes(
    semantic_lab_payload: dict[str, object],
) -> None:
    payload = semantic_lab_payload
    assert payload["schema_version"] == SEMANTIC_LAB_SCHEMA_VERSION
    assert payload["corpus"] == {
        "lab_id": "rei-semantic-lab-v1",
        "family_count": 24,
        "variant_count": 192,
        "reviewer_status": "canon_approved",
    }
    family_ids = [item["family_id"] for item in payload["families"]]
    assert family_ids == sorted(family_ids)
    assert len(family_ids) == len(set(family_ids)) == 24
    assert sum(len(item["variants"]) for item in payload["families"]) == 192

    identified = {key: value for key, value in payload.items() if key != "view_hash"}
    assert payload["view_hash"] == sha256_hex(identified)
    base = {
        key: value
        for key, value in payload.items()
        if key not in {"view_id", "view_hash"}
    }
    assert payload["view_id"] == content_id("semantic_lab_workbench", base)
    assert canonical_json_bytes(payload) == canonical_json_bytes(
        build_semantic_lab_view(REPOSITORY_ROOT)
    )


def test_projection_exposes_source_scene_routes_truth_and_bilingual_text(
    semantic_lab_payload: dict[str, object],
) -> None:
    family = _family(semantic_lab_payload, "sf_new_year_resolution")
    assert family["reviewer_status"] == "canon_approved"
    assert family["source_locators"]
    assert family["source_locators"][0]["claim_ids"]
    assert family["grounded_scene"]["event_id"] == "sf_new_year_resolution_event"
    assert family["grounded_scene"]["raw_input"]

    canonical = _variant(family, "sl_canonical")
    assert canonical["language"] == "sl"
    assert canonical["input_text"]
    assert {item["mind"] for item in canonical["expected_routes"]} == {
        "R",
        "E",
        "I",
    }
    assert {item["source_mind"] for item in canonical["expected_interpretation_truth"]} == {
        "E",
        "I",
    }
    assert canonical["side_by_side"]["sl"] == canonical["input_text"]
    assert canonical["side_by_side"]["en"] == _variant(
        family, "en_operational_gloss"
    )["input_text"]
    assert canonical["evaluation"]["status"] == "executed"
    assert "candidate_racio_complete" in canonical["evaluation"][
        "actual_route_ids"
    ]
    assert "accurate" in canonical["evaluation"]["actual_labels"]
    assert canonical["evaluation"]["results"][0]["expected_label"]
    assert canonical["failure_tags"]


def test_projection_marks_absent_c2_execution_without_inventing_results(
    semantic_lab_payload: dict[str, object],
) -> None:
    family = _family(semantic_lab_payload, "sf_new_year_resolution")
    paraphrase = _variant(family, "sl_paraphrase")
    assert paraphrase["evaluation"] == {
        "status": "not_executed",
        "reason": "no_c2_result_for_variant",
        "actual_route_ids": [],
        "actual_labels": [],
        "reviewer_statuses": [],
        "failure_tags": ["c2_not_executed"],
        "results": [],
    }
    assert paraphrase["failure_tags"] == ["c2_not_executed"]
    assert semantic_lab_payload["c2_evaluation"]["executed_variant_count"] == 12
    assert semantic_lab_payload["c2_evaluation"]["not_executed_variant_count"] == 180


def test_c7_technical_research_and_authority_statuses_remain_separate(
    semantic_lab_payload: dict[str, object],
) -> None:
    status = semantic_lab_payload["benchmark_status"]
    assert status["report_id"] == (
        "c7_integrated_benchmark_57c1db13906284edd641ac7cfbc6f5dc"
    )
    assert status["report_hash"] == (
        "fb96308989974776e29fbe8c7e1e185211f77155d4726a453e1158b5a3c16adc"
    )
    assert status["technical"] == {"contract_passed": True}
    assert status["research"]["quality_status"] == "blocked"
    assert [item["code"] for item in status["research"]["blockers"]] == [
        "c3_model_quality_gate_failed",
        "c4_semantic_visual_gate_open",
        "vlm_interpreter_arm_not_executed",
        "semantic_motif_arm_not_executed",
        "uniform_resource_telemetry_missing",
    ]
    assert status["authority"] == {
        "semantic_granted": False,
        "production_granted": False,
    }
    assert status["model_calls"] == {"current": 0, "historical": 32}
    assert status["aggregate_score_present"] is False
    assert "aggregate_score" not in status


def test_c2_variant_cannot_be_bound_to_another_family(
    semantic_lab_payload: dict[str, object],
) -> None:
    metrics = (
        REPOSITORY_ROOT
        / "Docs/evals/semantic_lab_v1/c2-deterministic-2026-07-14/metrics.json"
    ).read_bytes()
    _document, run = _load_c2_run(metrics)
    indexed_result = next(item for item in run.results if item.variant_id is not None)
    wrong_family_id = next(
        family["family_id"]
        for family in semantic_lab_payload["families"]
        if family["family_id"] != indexed_result.family_id
    )
    forged_result = indexed_result.model_copy(
        update={"family_id": wrong_family_id}
    )
    forged_run = run.model_copy(
        update={
            "results": tuple(
                forged_result if item is indexed_result else item
                for item in run.results
            )
        }
    )

    with pytest.raises(SemanticLabIntegrityError, match="family and variant"):
        _attach_c2_results(
            copy.deepcopy(semantic_lab_payload["families"]),
            run=forged_run,
        )


def test_projection_is_model_free_and_cannot_export_training_data(
    semantic_lab_payload: dict[str, object],
) -> None:
    assert semantic_lab_payload["execution_policy"] == {
        "read_only": True,
        "model_calls": 0,
        "training_export": False,
        "model_generated_gold": False,
        "aggregate_rei_score": False,
    }
    assert semantic_lab_payload["c2_evaluation"]["evaluator_model_calls"] == 0
    assert semantic_lab_payload["source_integrity"]["c1_manifest"] == {
        "path": "tests/fixtures/semantic_lab_v1/manifest.json",
        "size_bytes": 5975,
        "sha256": "c22a299afc3063d7edf338d738396c18ca9298081d17374e4a1b153b3fad606e",
    }
    assert semantic_lab_payload["source_integrity"]["c2_metrics"] == {
        "path": (
            "Docs/evals/semantic_lab_v1/c2-deterministic-2026-07-14/metrics.json"
        ),
        "size_bytes": 350293,
        "sha256": "3cb01e0914919c6d266bbfc8572049108f51e9884246b66564ded52ce3bfc1c5",
    }
    assert semantic_lab_payload["source_integrity"]["c7_report"] == {
        "path": (
            "Docs/evals/semantic_lab_v1/c7-integrated-2026-07-15/"
            "integrated_benchmark.json"
        ),
        "size_bytes": 1156993,
        "sha256": "64224a6c0e9615e7ff1981c334bc97182110014bcc77a1297bc272c311c47394",
        "report_id": (
            "c7_integrated_benchmark_57c1db13906284edd641ac7cfbc6f5dc"
        ),
        "report_hash": (
            "fb96308989974776e29fbe8c7e1e185211f77155d4726a453e1158b5a3c16adc"
        ),
    }


@pytest.mark.parametrize(
    "relative_path",
    (
        "knowledge/canon_v2/semantic_lab_v1/c7_integrated/manifest.json",
        "tests/fixtures/semantic_lab_v1/manifest.json",
        "tests/fixtures/semantic_lab_v1/sf_new_year_resolution.json",
        "Docs/evals/semantic_lab_v1/c2-deterministic-2026-07-14/metrics.json",
        (
            "Docs/evals/semantic_lab_v1/c7-integrated-2026-07-15/"
            "integrated_benchmark.json"
        ),
    ),
)
def test_projection_rejects_tampered_pinned_or_typed_evidence(
    tmp_path: Path,
    relative_path: str,
) -> None:
    root = _copy_projection_tree(tmp_path)
    target = root / relative_path
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(SemanticLabIntegrityError):
        build_semantic_lab_view(root)


def test_repository_path_confinement_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(SemanticLabIntegrityError, match="escaped"):
        _confined_file(tmp_path, "../outside.json", label="test evidence")
    with pytest.raises(SemanticLabIntegrityError, match="portable"):
        _confined_file(tmp_path, "..\\outside.json", label="test evidence")


def test_projection_rejects_symlink_or_windows_reparse_fixture(tmp_path: Path) -> None:
    root = _copy_projection_tree(tmp_path)
    fixture = root / "tests/fixtures/semantic_lab_v1/sf_new_year_resolution.json"
    outside = tmp_path / "outside-family.json"
    shutil.copyfile(fixture, outside)
    fixture.unlink()
    try:
        fixture.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable in this environment: {exc}")
    with pytest.raises(SemanticLabIntegrityError, match="link or reparse point"):
        build_semantic_lab_view(root)
