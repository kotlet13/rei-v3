"""Run and reproduce the deterministic C2 semantic evaluation quality gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.backend.rei.evaluation.manual_cases import (  # noqa: E402
    DEFAULT_FIXTURE_ROOT,
    ManualFixtureSetOutcome,
    evaluate_manual_fixture_set,
)
from app.backend.rei.evaluation.models import SemanticEvaluationRun  # noqa: E402
from app.backend.rei.evaluation.report import (  # noqa: E402
    REPORT_FILENAMES,
    render_evaluation_report,
    write_evaluation_report,
)


RUN_ID = "c2-deterministic-2026-07-14"
OFFICIAL_MANIFEST_SHA256 = (
    "a2aed73eac97d68b90236da15d214b6121c84378800e85764fc267dba75bc7cc"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Docs" / "evals" / "semantic_lab_v1" / RUN_ID


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_evaluation_run(
    fixture_root: str | Path | None = None,
) -> tuple[ManualFixtureSetOutcome, SemanticEvaluationRun]:
    """Evaluate the manifest-bound gold corpus and freeze one reportable run."""

    root = Path(fixture_root or DEFAULT_FIXTURE_ROOT).expanduser().resolve()
    manifest_hash = _sha256_file(root / "manifest.json")
    if manifest_hash != OFFICIAL_MANIFEST_SHA256:
        raise ValueError(
            "Official C2 manifest hash mismatch: "
            f"{manifest_hash} != {OFFICIAL_MANIFEST_SHA256}"
        )
    suite = evaluate_manual_fixture_set(root)
    if not suite.exact_match:
        mismatches = ", ".join(
            outcome.case_id for outcome in suite.outcomes if not outcome.exact_match
        )
        raise ValueError(f"C2 manual evaluator mismatch: {mismatches}")
    if suite.evaluator_model_calls != 0:
        raise ValueError("The deterministic C2 quality gate made model calls")

    run = SemanticEvaluationRun(
        run_id=RUN_ID,
        source_manifest_hash=manifest_hash,
        results=tuple(outcome.semantic_result for outcome in suite.outcomes),
        manually_reviewed_case_ids=tuple(
            sorted(outcome.case_id for outcome in suite.outcomes)
        ),
        evaluator_model_calls=0,
    )
    return suite, run


def human_review_summary(suite: ManualFixtureSetOutcome) -> dict[str, object]:
    """Describe reviewed gold without inventing multi-reviewer agreement."""

    return {
        "schema_version": "rei-semantic-c2-manual-review-summary-v1",
        "reviewer_count": 0,
        "reviewer_ids": [],
        "agreement_status": "not_applicable",
        "blind_review_workflow_implemented": True,
        "gold_origin": "manually_authored",
        "model_generated_gold": False,
        "case_count": len(suite.outcomes),
        "exact_evaluator_match_count": suite.exact_match_count,
        "positive_case_count": suite.manifest.positive_case_count,
        "negative_case_count": suite.manifest.negative_case_count,
        "evaluator_model_calls": suite.evaluator_model_calls,
        "note": (
            "No two-reviewer blind-review dataset was supplied for C2; "
            "agreement is therefore not applicable."
        ),
    }


def check_report(
    output_root: str | Path,
    expected: dict[str, bytes],
) -> None:
    """Require the checked-in report directory to match rendered bytes exactly."""

    root = Path(output_root).expanduser().resolve()
    actual_names = (
        tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
        if root.is_dir()
        else ()
    )
    expected_names = tuple(sorted(REPORT_FILENAMES))
    if actual_names != expected_names:
        raise ValueError(
            f"C2 report artifact set differs: {actual_names!r} != {expected_names!r}"
        )
    mismatches = [
        name for name, payload in expected.items() if (root / name).read_bytes() != payload
    ]
    if mismatches:
        raise ValueError(
            "C2 report bytes are not reproducible: " + ", ".join(mismatches)
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=DEFAULT_FIXTURE_ROOT,
        help="Manifest-bound C2 manual fixture directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory for the six required C2 report artifacts.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare existing report bytes without writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    suite, run = build_evaluation_run(args.fixture_root)
    review = human_review_summary(suite)
    rendered = render_evaluation_report(run, human_review_summary=review)
    if args.check:
        check_report(args.output_root, rendered)
        action = "checked"
    else:
        write_evaluation_report(
            run,
            args.output_root,
            human_review_summary=review,
        )
        action = "created"
    print(
        json.dumps(
            {
                "action": action,
                "run_id": run.run_id,
                "case_count": len(suite.outcomes),
                "exact_match_count": suite.exact_match_count,
                "evaluator_model_calls": run.evaluator_model_calls,
                "output_root": str(Path(args.output_root).resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
