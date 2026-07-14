from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.backend.rei.evaluation.report as report_module
from app.backend.rei.evaluation.human_review import (
    REVIEW_FACETS,
    ReviewerAgreement,
    commit_review_material,
    prepare_blind_review,
    record_final_review,
    record_first_pass,
    reveal_review_context,
    reviewer_agreement,
)
from app.backend.rei.evaluation.models import (
    EvaluatedProviderProvenance,
    EvaluationIssue,
    EvaluationMetric,
    EvaluationResultContext,
    SemanticEvaluationResult,
    SemanticEvaluationRun,
)
from app.backend.rei.evaluation.report import (
    REPORT_FILENAMES,
    EvaluationReportError,
    EvaluationReportExistsError,
    render_evaluation_report,
    write_evaluation_report,
)
from app.backend.rei.ids import canonical_json_bytes


EXPECTED_REPORT_FILENAMES = (
    "summary.md",
    "metrics.json",
    "failures.jsonl",
    "confusion_matrices.json",
    "bilingual_consistency.json",
    "human_review_summary.md",
)


def _evaluation_run() -> SemanticEvaluationRun:
    native_result = SemanticEvaluationResult.create(
        subject_id="native-route-case",
        subject_kind="native_route",
        family_id="family-native",
        variant_id="variant-sl",
        mind="R",
        expected_label="racio-route",
        observed_label="racio-route",
        metrics=(
            EvaluationMetric(
                metric_id="native-route-match",
                dimension="native_route_semantics",
                status="passed",
                policy_id="native-route-policy-v1",
                value=True,
                threshold=True,
                detail="The native route matches the expected Racio route.",
            ),
        ),
        issues=(),
        evaluator_policies=("native-route-policy-v1",),
        evidence_artifact_ids=("native-route-evidence",),
        context=EvaluationResultContext(
            source_locator_refs=("native-route-source",),
            language="sl",
            expected_route_ids=("racio-route",),
            actual_route_ids=("racio-route",),
            cognition_mode="structured",
            provider_provenance=EvaluatedProviderProvenance(
                provider_id="local-ollama",
                provider_revision="0.12.0",
                model_id="granite4.1-30b",
                model_revision="sha256-native-model",
                seed=17,
            ),
            replay_artifact_ids=("native-route-replay",),
        ),
    )
    bilingual_result = SemanticEvaluationResult.create(
        subject_id="bilingual-pair-case",
        subject_kind="bilingual_pair",
        family_id="family-bilingual",
        variant_id="variant-sl-en",
        expected_label="consistent",
        observed_label="semantic-drift",
        metrics=(
            EvaluationMetric(
                metric_id="bilingual-signature-match",
                dimension="bilingual_consistency",
                status="failed",
                policy_id="bilingual-policy-v1",
                value=0.4,
                threshold=0.9,
                detail="The English gloss changes one canonical concept.",
            ),
            EvaluationMetric(
                metric_id="slovenian-term-match",
                dimension="slovenian_terminology",
                status="passed",
                policy_id="terminology-policy-v1",
                value=True,
                threshold=True,
                detail="The authoritative Slovenian term is preserved.",
            ),
        ),
        issues=(
            EvaluationIssue(
                issue_code="bilingual-semantic-drift",
                dimension="bilingual_consistency",
                severity="error",
                detail="The operational English gloss is not semantically aligned.",
                evidence_refs=("bilingual-diff-evidence",),
            ),
        ),
        evaluator_policies=(
            "bilingual-policy-v1",
            "terminology-policy-v1",
        ),
        evidence_artifact_ids=("bilingual-diff-evidence",),
        context=EvaluationResultContext(
            source_locator_refs=("bilingual-source-sl", "bilingual-source-en"),
            language="en",
            review_status="reviewed",
            reviewer_agreement_id="review-record-1",
            provider_provenance=EvaluatedProviderProvenance(
                provider_id="local-deterministic-evaluator",
                provider_revision="c2-v1",
                model_id="semantic-comparator",
                model_revision="fixture-v1",
                seed=23,
            ),
            replay_artifact_ids=("bilingual-replay",),
        ),
    )
    return SemanticEvaluationRun(
        run_id="semantic-evaluation-run",
        source_manifest_hash="a" * 64,
        results=(bilingual_result, native_result),
        manually_reviewed_case_ids=("bilingual-pair-case", "native-route-case"),
        ablation_ids=("ablation-z", "ablation-a"),
        resource_telemetry_artifact_ids=("telemetry-z", "telemetry-a"),
    )


def _json_artifact(artifacts: dict[str, bytes], filename: str) -> dict:
    return json.loads(artifacts[filename].decode("utf-8"))


def _reviewer_agreement() -> ReviewerAgreement:
    case_id = "review-case"
    subject_id = "review-subject"
    commitment = commit_review_material(
        authority_id="trusted-report-test-authority",
        source_manifest_hash="b" * 64,
        case_id=case_id,
        subject_id=subject_id,
        blind_presented_text="Nevtralen opis za slepo presojo.",
        language="sl",
        route_ids=("review-route",),
        source_excerpts=(("review-source", "Pregledani povzetek vira."),),
        grounded_scene_text="Utemeljena scena za presojo.",
    )
    packet = prepare_blind_review(commitment)

    def final_review(
        reviewer_id: str,
        *,
        selected_mind: str,
        reasoning_quality: int,
        translation_quality: int,
        uncertainty: int,
    ):
        session = record_first_pass(
            packet,
            reviewer_id=reviewer_id,
            selected_mind="R",
            selected_route_id=packet.blind_route_ids[0],
            reasoning_quality=4,
            translation_quality=4,
            uncertainty=2,
        )
        revealed = reveal_review_context(
            session,
            material_commitment=commitment,
        )
        return record_final_review(
            revealed,
            selected_mind=selected_mind,
            selected_route_id=packet.blind_route_ids[0],
            reasoning_quality=reasoning_quality,
            translation_quality=translation_quality,
            uncertainty=uncertainty,
        )

    return reviewer_agreement(
        (
            final_review(
                "reviewer-b",
                selected_mind="E",
                reasoning_quality=3,
                translation_quality=4,
                uncertainty=2,
            ),
            final_review(
                "reviewer-a",
                selected_mind="R",
                reasoning_quality=5,
                translation_quality=4,
                uncertainty=1,
            ),
        )
    )


def test_render_has_exact_contract_and_deterministic_canonical_bytes() -> None:
    run = _evaluation_run()
    reordered_run = run.model_copy(
        update={
            "results": tuple(reversed(run.results)),
            "manually_reviewed_case_ids": tuple(
                reversed(run.manually_reviewed_case_ids)
            ),
            "ablation_ids": tuple(reversed(run.ablation_ids)),
            "resource_telemetry_artifact_ids": tuple(
                reversed(run.resource_telemetry_artifact_ids)
            ),
        }
    )

    first = render_evaluation_report(run)
    second = render_evaluation_report(run)
    reordered = render_evaluation_report(reordered_run)

    assert REPORT_FILENAMES == EXPECTED_REPORT_FILENAMES
    assert tuple(first) == EXPECTED_REPORT_FILENAMES
    assert len(first) == 6
    assert all(isinstance(content, bytes) for content in first.values())
    assert first == second == reordered
    for filename in (
        "metrics.json",
        "confusion_matrices.json",
        "bilingual_consistency.json",
    ):
        payload = _json_artifact(first, filename)
        assert first[filename] == canonical_json_bytes(payload)


def test_metrics_keep_dimensions_separate_without_global_score() -> None:
    metrics = _json_artifact(
        render_evaluation_report(_evaluation_run()),
        "metrics.json",
    )

    assert metrics["report_policy"] == {
        "dimensions_preserved_separately": True,
        "global_rei_score": False,
        "single_cross_dimension_rank": False,
    }
    assert not {"score", "rei_score", "aggregate_score"} & metrics.keys()
    dimensions = metrics["dimensions"]
    assert dimensions["native_route_semantics"]["metric_count"] == 1
    assert dimensions["native_route_semantics"]["status_counts"] == {
        "failed": 0,
        "not_applicable": 0,
        "passed": 1,
    }
    assert dimensions["bilingual_consistency"]["metric_count"] == 1
    assert dimensions["bilingual_consistency"]["status_counts"] == {
        "failed": 1,
        "not_applicable": 0,
        "passed": 0,
    }
    assert dimensions["slovenian_terminology"]["metric_count"] == 1
    assert dimensions["allowed_option_validity"]["metric_count"] == 0


def test_failures_jsonl_contains_only_failures_with_full_provenance() -> None:
    run = _evaluation_run()
    artifacts = render_evaluation_report(run)
    raw = artifacts["failures.jsonl"]
    records = [json.loads(line) for line in raw.splitlines()]

    assert raw.endswith(b"\n")
    assert len(records) == 1
    failure = records[0]
    failed_result = next(result for result in run.results if not result.passed)
    assert failure["result_id"] == failed_result.result_id
    assert failure["failed_dimensions"] == ["bilingual_consistency"]
    assert [item["metric_id"] for item in failure["failed_metrics"]] == [
        "bilingual-signature-match"
    ]
    assert failure["issues"][0]["issue_code"] == "bilingual-semantic-drift"
    assert failure["context"]["source_locator_refs"] == [
        "bilingual-source-sl",
        "bilingual-source-en",
    ]
    assert failure["context"]["provider_provenance"] == {
        "model_id": "semantic-comparator",
        "model_revision": "fixture-v1",
        "provider_id": "local-deterministic-evaluator",
        "provider_revision": "c2-v1",
        "seed": 23,
    }
    assert failure["evaluator_model_calls"] == 0
    assert canonical_json_bytes(failure) + b"\n" == raw


def test_bilingual_payload_preserves_authority_metrics_and_provenance() -> None:
    payload = _json_artifact(
        render_evaluation_report(_evaluation_run()),
        "bilingual_consistency.json",
    )

    assert payload["slovenian_is_authoritative"] is True
    assert payload["english_is_operational_gloss"] is True
    assert payload["model_judge_calls"] == 0
    assert payload["result_count"] == 1
    assert payload["metric_status_counts"] == {
        "failed": 1,
        "not_applicable": 0,
        "passed": 1,
    }
    case = payload["cases"][0]
    assert case["subject_id"] == "bilingual-pair-case"
    assert {metric["dimension"] for metric in case["metrics"]} == {
        "bilingual_consistency",
        "slovenian_terminology",
    }
    assert case["context"]["review_status"] == "reviewed"
    assert (
        case["context"]["provider_provenance"]["provider_id"]
        == "local-deterministic-evaluator"
    )


@pytest.mark.parametrize(
    "review_summary",
    (
        None,
        {"reviewer_count": 0, "agreement": 0.0},
        {"reviewer_ids": ["reviewer-a"], "agreement": 1.0},
        {
            "reviews": [
                {"reviewer_id": "reviewer-a", "verdict": "accepted"},
            ],
            "agreement_status": "complete",
        },
    ),
)
def test_human_review_agreement_is_not_applicable_below_two_reviewers(
    review_summary: object | None,
) -> None:
    human_review = render_evaluation_report(
        _evaluation_run(),
        human_review_summary=review_summary,
    )["human_review_summary.md"].decode("utf-8")

    assert "Reviewer agreement: `not_applicable`" in human_review
    if review_summary is not None:
        assert "not reviewer-agreement evidence" in human_review


def test_human_review_renders_only_replay_valid_typed_agreement() -> None:
    agreement = _reviewer_agreement()

    first = render_evaluation_report(
        _evaluation_run(),
        human_review_summary=agreement,
    )["human_review_summary.md"]
    second = render_evaluation_report(
        _evaluation_run(),
        human_review_summary=agreement,
    )["human_review_summary.md"]
    rendered = first.decode("utf-8")

    assert first == second
    assert "Reviewer agreement: `reported_by_facet`" in rendered
    assert f"Agreement artifact ID: `{agreement.agreement_id}`" in rendered
    assert "Reviewer IDs: `reviewer-a`, `reviewer-b`" in rendered
    assert "Replay-validated facet agreement" in rendered
    assert all(f"| `{facet}` |" in rendered for facet in REVIEW_FACETS)
    assert (
        "| `reviewer-a` | `reviewer-b` | `mind` | 1 | 0 | 0.0 | "
        "0.0 | 0.0 | defined |"
    ) in rendered
    assert '"agreement_id": ' in rendered


def test_untyped_multi_reviewer_agreement_claim_is_rejected(
    tmp_path: Path,
) -> None:
    untyped_claim = {
        "reviewer_count": 2,
        "reviewer_ids": [],
        "agreement": "perfect",
    }

    with pytest.raises(EvaluationReportError, match="ReviewerAgreement"):
        render_evaluation_report(
            _evaluation_run(),
            human_review_summary=untyped_claim,
        )

    output_root = tmp_path / "invalid-untyped-agreement"
    with pytest.raises(EvaluationReportError, match="ReviewerAgreement"):
        write_evaluation_report(
            _evaluation_run(),
            output_root,
            human_review_summary=untyped_claim,
        )
    assert not output_root.exists()


def test_writer_is_create_only_and_cleans_partial_report_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _evaluation_run()
    existing_root = tmp_path / "existing"
    existing_root.mkdir()
    sentinel = existing_root / "summary.md"
    sentinel.write_bytes(b"user-owned")

    with pytest.raises(EvaluationReportExistsError, match="create-only"):
        write_evaluation_report(run, existing_root)

    assert sentinel.read_bytes() == b"user-owned"
    assert tuple(path.name for path in existing_root.iterdir()) == ("summary.md",)

    failed_root = tmp_path / "failed"
    failed_root.mkdir()
    unrelated = failed_root / "keep.txt"
    unrelated.write_bytes(b"keep")
    real_fsync = report_module.os.fsync
    fsync_calls = 0

    def fail_third_fsync(descriptor: int) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 3:
            raise OSError("simulated fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(report_module.os, "fsync", fail_third_fsync)
    with pytest.raises(OSError, match="simulated fsync failure"):
        write_evaluation_report(run, failed_root)

    assert fsync_calls == 3
    assert unrelated.read_bytes() == b"keep"
    assert not any((failed_root / name).exists() for name in REPORT_FILENAMES)
