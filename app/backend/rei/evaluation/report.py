"""Deterministic, dimension-preserving reports for C2 semantic evaluation.

The reporter is deliberately model-free.  It renders one frozen
``SemanticEvaluationRun`` into the six artifacts required by the C2 plan and
writes them with exclusive-create semantics.  No cross-dimension score is
computed: each metric remains attached to its declared evaluation dimension.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, get_args

from pydantic import BaseModel

from ..ids import canonical_json_bytes
from .human_review import REVIEW_FACETS, ReviewerAgreement
from .models import (
    EvaluationDimension,
    SemanticEvaluationResult,
    SemanticEvaluationRun,
)


REPORT_FILENAMES: Final[tuple[str, ...]] = (
    "summary.md",
    "metrics.json",
    "failures.jsonl",
    "confusion_matrices.json",
    "bilingual_consistency.json",
    "human_review_summary.md",
)

_DIMENSIONS: Final[tuple[str, ...]] = tuple(get_args(EvaluationDimension))


class EvaluationReportError(RuntimeError):
    """Base class for semantic evaluation report failures."""


class EvaluationReportExistsError(EvaluationReportError):
    """A create-only report artifact already exists."""


def _result_sort_key(result: SemanticEvaluationResult) -> tuple[str, ...]:
    return (
        result.subject_kind,
        result.family_id or "",
        result.variant_id or "",
        result.mind or "",
        result.subject_id,
        result.result_id,
    )


def _ordered_results(
    run: SemanticEvaluationRun,
) -> tuple[SemanticEvaluationResult, ...]:
    return tuple(sorted(run.results, key=_result_sort_key))


def _run_metadata(run: SemanticEvaluationRun) -> dict[str, Any]:
    """Return shared report metadata without inventing an aggregate score."""

    return {
        "run_id": run.run_id,
        "source_manifest_hash": run.source_manifest_hash,
        "evaluator_version": run.evaluator_version,
        "evaluator_model_calls": run.evaluator_model_calls,
        "manually_reviewed_case_ids": tuple(
            sorted(run.manually_reviewed_case_ids)
        ),
        "ablation_ids": tuple(sorted(run.ablation_ids)),
        "resource_telemetry_artifact_ids": tuple(
            sorted(run.resource_telemetry_artifact_ids)
        ),
    }


def _status_counts(statuses: Sequence[str]) -> dict[str, int]:
    counts = Counter(statuses)
    return {
        "passed": counts["passed"],
        "failed": counts["failed"],
        "not_applicable": counts["not_applicable"],
    }


def _result_record(result: SemanticEvaluationResult) -> dict[str, Any]:
    """Preserve the complete result, including context and provenance."""

    return result.model_dump(mode="python", round_trip=True)


def _metrics_payload(run: SemanticEvaluationRun) -> dict[str, Any]:
    results = _ordered_results(run)
    dimensions: dict[str, dict[str, Any]] = {}
    for dimension in _DIMENSIONS:
        observations: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        for result in results:
            for metric in result.metrics:
                if metric.dimension != dimension:
                    continue
                observations.append(
                    {
                        "result_id": result.result_id,
                        "subject_id": result.subject_id,
                        "subject_kind": result.subject_kind,
                        "family_id": result.family_id,
                        "variant_id": result.variant_id,
                        "mind": result.mind,
                        "metric": metric,
                    }
                )
            for issue in result.issues:
                if issue.dimension != dimension:
                    continue
                issues.append(
                    {
                        "result_id": result.result_id,
                        "subject_id": result.subject_id,
                        "issue": issue,
                    }
                )
        dimensions[dimension] = {
            "metric_count": len(observations),
            "status_counts": _status_counts(
                [item["metric"].status for item in observations]
            ),
            "issue_count": len(issues),
            "observations": observations,
            "issues": issues,
        }

    return {
        "schema_version": "rei-semantic-metrics-report-v1",
        **_run_metadata(run),
        "report_policy": {
            "dimensions_preserved_separately": True,
            "global_rei_score": False,
            "single_cross_dimension_rank": False,
        },
        "result_count": len(results),
        "results": [_result_record(result) for result in results],
        "dimensions": dimensions,
    }


def _failure_records(run: SemanticEvaluationRun) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for result in _ordered_results(run):
        if result.passed:
            continue
        failed_metrics = tuple(
            metric for metric in result.metrics if metric.status == "failed"
        )
        failed_dimensions = tuple(
            sorted(
                {
                    *(metric.dimension for metric in failed_metrics),
                    *(
                        issue.dimension
                        for issue in result.issues
                        if issue.severity == "error"
                    ),
                }
            )
        )
        failures.append(
            {
                "schema_version": "rei-semantic-failure-record-v1",
                "run_id": run.run_id,
                "source_manifest_hash": run.source_manifest_hash,
                "evaluator_version": run.evaluator_version,
                "result_id": result.result_id,
                "subject_id": result.subject_id,
                "subject_kind": result.subject_kind,
                "family_id": result.family_id,
                "variant_id": result.variant_id,
                "mind": result.mind,
                "expected_label": result.expected_label,
                "observed_label": result.observed_label,
                "failed_dimensions": failed_dimensions,
                "failed_metrics": failed_metrics,
                "issues": result.issues,
                "evaluator_policies": result.evaluator_policies,
                "evidence_artifact_ids": result.evidence_artifact_ids,
                "context": result.context,
                "evaluator_model_calls": result.evaluator_model_calls,
            }
        )
    return failures


def _failures_jsonl(run: SemanticEvaluationRun) -> bytes:
    records = _failure_records(run)
    if not records:
        return b""
    return b"\n".join(canonical_json_bytes(record) for record in records) + b"\n"


def _confusion_payload(run: SemanticEvaluationRun) -> dict[str, Any]:
    grouped: dict[
        tuple[str, str | None], list[SemanticEvaluationResult]
    ] = defaultdict(list)
    for result in _ordered_results(run):
        grouped[(result.subject_kind, result.mind)].append(result)

    matrices: list[dict[str, Any]] = []
    for (subject_kind, mind), results in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        labels = tuple(
            sorted(
                {
                    *(result.expected_label for result in results),
                    *(result.observed_label for result in results),
                }
            )
        )
        cell_counts = Counter(
            (result.expected_label, result.observed_label) for result in results
        )
        ids_by_cell: dict[tuple[str, str], list[str]] = defaultdict(list)
        for result in results:
            ids_by_cell[(result.expected_label, result.observed_label)].append(
                result.result_id
            )
        matrices.append(
            {
                "matrix_id": f"{subject_kind}:{mind or 'all'}",
                "subject_kind": subject_kind,
                "mind": mind,
                "labels": labels,
                "counts": tuple(
                    tuple(cell_counts[(expected, observed)] for observed in labels)
                    for expected in labels
                ),
                "cells": tuple(
                    {
                        "expected_label": expected,
                        "observed_label": observed,
                        "count": cell_counts[(expected, observed)],
                        "result_ids": tuple(
                            sorted(ids_by_cell[(expected, observed)])
                        ),
                    }
                    for expected in labels
                    for observed in labels
                    if cell_counts[(expected, observed)]
                ),
                "result_count": len(results),
            }
        )

    return {
        "schema_version": "rei-semantic-confusion-matrices-v1",
        **_run_metadata(run),
        "matrix_count": len(matrices),
        "matrices": matrices,
    }


def _bilingual_payload(run: SemanticEvaluationRun) -> dict[str, Any]:
    results = tuple(
        result
        for result in _ordered_results(run)
        if result.subject_kind == "bilingual_pair"
    )
    cases: list[dict[str, Any]] = []
    statuses: list[str] = []
    for result in results:
        metrics = tuple(
            metric
            for metric in result.metrics
            if metric.dimension
            in {"bilingual_consistency", "slovenian_terminology"}
        )
        statuses.extend(metric.status for metric in metrics)
        cases.append(
            {
                "result_id": result.result_id,
                "subject_id": result.subject_id,
                "family_id": result.family_id,
                "variant_id": result.variant_id,
                "expected_label": result.expected_label,
                "observed_label": result.observed_label,
                "passed": result.passed,
                "metrics": metrics,
                "issues": result.issues,
                "evidence_artifact_ids": result.evidence_artifact_ids,
                "context": result.context,
                "evaluator_policies": result.evaluator_policies,
            }
        )
    return {
        "schema_version": "rei-semantic-bilingual-consistency-v1",
        **_run_metadata(run),
        "slovenian_is_authoritative": True,
        "english_is_operational_gloss": True,
        "model_judge_calls": 0,
        "result_count": len(results),
        "metric_status_counts": _status_counts(statuses),
        "cases": cases,
    }


def _table_text(value: Any) -> str:
    if value is None:
        rendered = "—"
    elif isinstance(value, str):
        rendered = value
    else:
        rendered = canonical_json_bytes(value).decode("utf-8")
    return " ".join(rendered.split()).replace("|", "\\|")


def _summary_markdown(run: SemanticEvaluationRun) -> bytes:
    results = _ordered_results(run)
    failed_results = tuple(result for result in results if not result.passed)
    dimension_rows: list[str] = []
    for dimension in _DIMENSIONS:
        metrics = tuple(
            metric
            for result in results
            for metric in result.metrics
            if metric.dimension == dimension
        )
        counts = _status_counts([metric.status for metric in metrics])
        issue_count = sum(
            1
            for result in results
            for issue in result.issues
            if issue.dimension == dimension
        )
        dimension_rows.append(
            f"| `{dimension}` | {len(metrics)} | {counts['passed']} | "
            f"{counts['failed']} | {counts['not_applicable']} | {issue_count} |"
        )

    issue_rows = [
        "| Result | Dimension | Severity | Code | Detail |"
        "\n|---|---|---|---|---|"
    ]
    for result in results:
        for issue in result.issues:
            issue_rows.append(
                f"| `{_table_text(result.result_id)}` | `{issue.dimension}` | "
                f"{issue.severity} | `{_table_text(issue.issue_code)}` | "
                f"{_table_text(issue.detail)} |"
            )
    if len(issue_rows) == 1:
        issue_rows.append("| — | — | — | — | No issues recorded. |")

    provenance_rows = [
        "| Result | Provider | Provider revision | Model | Model revision | Seed |"
        "\n|---|---|---|---|---|---:|"
    ]
    for result in results:
        provenance = result.context.provider_provenance
        if provenance is None:
            continue
        provenance_rows.append(
            f"| `{_table_text(result.result_id)}` | "
            f"`{_table_text(provenance.provider_id)}` | "
            f"`{_table_text(provenance.provider_revision)}` | "
            f"`{_table_text(provenance.model_id)}` | "
            f"`{_table_text(provenance.model_revision)}` | "
            f"{_table_text(provenance.seed)} |"
        )
    if len(provenance_rows) == 1:
        provenance_rows.append("| — | — | — | — | — | — |")

    lines = [
        "# C2 semantic evaluation summary",
        "",
        f"- Run ID: `{run.run_id}`",
        f"- Source manifest SHA-256: `{run.source_manifest_hash}`",
        f"- Evaluator version: `{run.evaluator_version}`",
        f"- Evaluator model calls: `{run.evaluator_model_calls}`",
        f"- Results: `{len(results)}`",
        f"- Passing results: `{len(results) - len(failed_results)}`",
        f"- Failing results: `{len(failed_results)}`",
        f"- Manually reviewed cases: `{len(run.manually_reviewed_case_ids)}`",
        "",
        "> Metrics remain separated by dimension. This report does not compute "
        "a global REI score or a cross-dimension rank.",
        "",
        "## Metrics by dimension",
        "",
        "| Dimension | Metrics | Passed | Failed | N/A | Issues |",
        "|---|---:|---:|---:|---:|---:|",
        *dimension_rows,
        "",
        "## Issues",
        "",
        *issue_rows,
        "",
        "## Evaluated provider provenance",
        "",
        *provenance_rows,
        "",
        "## Artifacts",
        "",
        *(f"- `{filename}`" for filename in REPORT_FILENAMES),
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _normalize_human_review(value: object) -> object:
    if isinstance(value, str):
        value = {"summary": value}
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python", round_trip=True)
    # Round-trip through the canonical serializer to validate the complete
    # caller-supplied structure and normalize tuples/enums/timestamps.
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


def _pretty_canonical_json(value: object) -> str:
    normalized = _normalize_human_review(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    )


def _untyped_reviewer_counts(value: Mapping[str, object]) -> tuple[int, ...]:
    """Extract every independently declared count from untyped metadata."""

    counts: list[int] = []
    if "reviewer_count" in value:
        raw_count = value["reviewer_count"]
        if (
            not isinstance(raw_count, int)
            or isinstance(raw_count, bool)
            or raw_count < 0
        ):
            raise EvaluationReportError(
                "Untyped human-review metadata has an invalid reviewer_count"
            )
        counts.append(raw_count)

    for key in ("reviewer_ids", "reviewers"):
        reviewers = value.get(key)
        if isinstance(reviewers, list):
            counts.append(
                len(set(canonical_json_bytes(item) for item in reviewers))
            )

    for key in ("reviews", "records"):
        records = value.get(key)
        if not isinstance(records, list):
            continue
        reviewer_ids = {
            record.get("reviewer_id")
            for record in records
            if isinstance(record, Mapping)
            and isinstance(record.get("reviewer_id"), str)
        }
        if records or reviewer_ids:
            counts.append(len(reviewer_ids))
    return tuple(counts)


def _typed_reviewer_agreement(
    value: object | None,
) -> ReviewerAgreement | None:
    """Accept multi-reviewer evidence only as a replay-valid typed artifact."""

    if value is None:
        return None
    if isinstance(value, ReviewerAgreement):
        # Revalidate even model-constructed instances so content IDs, canonical
        # ordering, marginals and facet kappas all replay before reporting.
        return ReviewerAgreement.model_validate(
            value.model_dump(mode="python", round_trip=True)
        )

    normalized = _normalize_human_review(value)
    if not isinstance(normalized, Mapping):
        return None
    counts = _untyped_reviewer_counts(normalized)
    facet_claim = normalized.get("facet_agreements")
    claims_typed_evidence = isinstance(facet_claim, list) and bool(facet_claim)
    agreement_claim = normalized.get(
        "agreement", normalized.get("agreement_status")
    )
    claims_agreement = (
        agreement_claim is not None and agreement_claim != "not_applicable"
    )
    established_below_two = bool(counts) and max(counts) < 2
    if (
        any(count >= 2 for count in counts)
        or claims_typed_evidence
        or (claims_agreement and not established_below_two)
    ):
        raise EvaluationReportError(
            "Multi-reviewer evidence must be a replay-valid ReviewerAgreement"
        )
    return None


def _facet_agreement_markdown(agreement: ReviewerAgreement) -> list[str]:
    facet_order = {facet: index for index, facet in enumerate(REVIEW_FACETS)}
    rows = [
        "| Reviewer A | Reviewer B | Facet | Shared | Exact | Observed | "
        "Expected | Cohen kappa | Status |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in sorted(
        agreement.facet_agreements,
        key=lambda value: (
            value.reviewer_a_id,
            value.reviewer_b_id,
            facet_order[value.facet],
        ),
    ):
        kappa = (
            _table_text(item.cohen_kappa)
            if item.kappa_defined
            else "not_applicable"
        )
        status = (
            "defined"
            if item.kappa_defined
            else _table_text(item.kappa_undefined_reason)
        )
        rows.append(
            f"| `{_table_text(item.reviewer_a_id)}` | "
            f"`{_table_text(item.reviewer_b_id)}` | `{item.facet}` | "
            f"{len(item.shared_blind_packet_ids)} | "
            f"{item.exact_agreement_count} | "
            f"{_table_text(item.observed_agreement)} | "
            f"{_table_text(item.expected_agreement)} | {kappa} | {status} |"
        )
    return rows


def _human_review_markdown(
    run: SemanticEvaluationRun,
    human_review_summary: object | None,
) -> bytes:
    agreement = _typed_reviewer_agreement(human_review_summary)
    lines = [
        "# C2 human review summary",
        "",
        f"- Run ID: `{run.run_id}`",
        f"- Manually reviewed case count: `{len(run.manually_reviewed_case_ids)}`",
        "- Reviewer agreement: "
        + ("`reported_by_facet`" if agreement is not None else "`not_applicable`"),
        "- Manually reviewed case IDs: "
        + (
            ", ".join(f"`{item}`" for item in sorted(run.manually_reviewed_case_ids))
            if run.manually_reviewed_case_ids
            else "none"
        ),
        "",
    ]
    if agreement is not None:
        lines.extend(
            [
                f"- Agreement artifact ID: `{agreement.agreement_id}`",
                f"- Reviewer count: `{len(agreement.reviewer_ids)}`",
                "- Reviewer IDs: "
                + ", ".join(f"`{item}`" for item in agreement.reviewer_ids),
                "- Reviewed blind packet count: "
                f"`{len(agreement.reviewed_blind_packet_ids)}`",
                "",
                "## Replay-validated facet agreement",
                "",
                *_facet_agreement_markdown(agreement),
                "",
                "## Replay-validated agreement artifact",
                "",
                "```json",
                _pretty_canonical_json(agreement),
                "```",
                "",
            ]
        )
    elif human_review_summary is None:
        lines.extend(
            [
                "No optional human-review summary was supplied for this run.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Untyped review metadata is retained for audit context only; "
                "it is not reviewer-agreement evidence.",
                "",
                "## Supplied review metadata",
                "",
                "```json",
                _pretty_canonical_json(human_review_summary),
                "```",
                "",
            ]
        )
    return "\n".join(lines).encode("utf-8")


def render_evaluation_report(
    run: SemanticEvaluationRun,
    *,
    human_review_summary: object | None = None,
) -> dict[str, bytes]:
    """Render exactly the six required C2 artifacts without filesystem I/O."""

    metrics = _metrics_payload(run)
    confusion = _confusion_payload(run)
    bilingual = _bilingual_payload(run)
    artifacts = {
        "summary.md": _summary_markdown(run),
        "metrics.json": canonical_json_bytes(metrics),
        "failures.jsonl": _failures_jsonl(run),
        "confusion_matrices.json": canonical_json_bytes(confusion),
        "bilingual_consistency.json": canonical_json_bytes(bilingual),
        "human_review_summary.md": _human_review_markdown(
            run, human_review_summary
        ),
    }
    if tuple(artifacts) != REPORT_FILENAMES:
        raise AssertionError("C2 report artifact set differs from its public contract")
    return artifacts


def _write_exclusive(path: Path, content: bytes) -> None:
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        created = True
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise EvaluationReportExistsError(
            f"C2 report artifact already exists: {path.name}"
        ) from exc
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        if created:
            path.unlink(missing_ok=True)
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)


def write_evaluation_report(
    run: SemanticEvaluationRun,
    run_root: str | os.PathLike[str],
    *,
    human_review_summary: object | None = None,
) -> tuple[Path, ...]:
    """Create the six C2 report files atomically with respect to overwrite.

    All bytes are rendered before the first filesystem mutation.  Existing
    report artifacts are rejected up front and every individual write also
    uses ``O_EXCL`` to close the race window.  If a later write fails, only
    files created by this invocation are removed.
    """

    artifacts = render_evaluation_report(
        run,
        human_review_summary=human_review_summary,
    )
    root = Path(run_root).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise EvaluationReportError("C2 report root must be a directory")
    root.mkdir(parents=True, exist_ok=True)
    paths = tuple(root / filename for filename in REPORT_FILENAMES)
    existing = tuple(path.name for path in paths if path.exists())
    if existing:
        raise EvaluationReportExistsError(
            "C2 report is create-only; existing artifacts: "
            + ", ".join(existing)
        )

    created: list[Path] = []
    try:
        for path in paths:
            _write_exclusive(path, artifacts[path.name])
            created.append(path)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return paths


# Explicit semantic aliases make the public intent clear while keeping the
# shorter names convenient for focused tests and scripts.
render_semantic_evaluation_report = render_evaluation_report
write_semantic_evaluation_report = write_evaluation_report


__all__ = [
    "EvaluationReportError",
    "EvaluationReportExistsError",
    "REPORT_FILENAMES",
    "render_evaluation_report",
    "render_semantic_evaluation_report",
    "write_evaluation_report",
    "write_semantic_evaluation_report",
]
