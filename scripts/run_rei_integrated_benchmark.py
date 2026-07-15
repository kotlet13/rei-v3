"""Run or reproduce the model-free C7 integrated REI benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.backend.rei.evaluation.integrated_benchmark import (  # noqa: E402
    check_c7_report,
    evaluate_c7_integrated_benchmark,
    write_c7_report,
)


RUN_ID = "c7-integrated-2026-07-15"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Defaults to the C7 manifest below --repository-root.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Defaults to the C7 evaluation directory below --repository-root.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Cold-replay C7 and compare the checked-in seven-file report byte-for-byte.",
    )
    parser.add_argument(
        "--require-research-ready",
        action="store_true",
        help=(
            "Return exit code 2 while any research-quality blocker remains; this "
            "does not alter or suppress the technical report."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repository_root = Path(args.repository_root).expanduser().resolve()
    manifest_path = args.manifest_path or (
        repository_root
        / "knowledge"
        / "canon_v2"
        / "semantic_lab_v1"
        / "c7_integrated"
        / "manifest.json"
    )
    output_root = args.output_root or (
        repository_root / "Docs" / "evals" / "semantic_lab_v1" / RUN_ID
    )
    report = evaluate_c7_integrated_benchmark(
        repository_root,
        manifest_path=manifest_path,
    )
    if args.check:
        check_c7_report(report, output_root)
        action = "checked"
    else:
        write_c7_report(report, output_root)
        action = "created"
    print(
        json.dumps(
            {
                "action": action,
                "run_id": RUN_ID,
                "report_id": report.report_id,
                "report_hash": report.report_hash,
                "technical_contract_passed": report.technical_contract_passed,
                "research_quality_status": report.research_quality_status,
                "research_readiness_blocker_codes": (
                    report.research_readiness_blocker_codes
                ),
                "current_model_call_count": report.current_model_call_count,
                "historical_model_call_count": report.historical_model_call_count,
                "aggregate_score_present": report.aggregate_score_present,
                "interaction_effects_measured": report.interaction_effects_measured,
                "semantic_authority_granted": report.semantic_authority_granted,
                "production_authority_granted": report.production_authority_granted,
                "controlled_profile_row_count": (
                    report.controlled_profile.total_row_count
                ),
                "person_causality_case_count": report.person_causality.case_count,
                "passed_metric_count": report.passed_metric_count,
                "blocked_metric_count": report.blocked_metric_count,
                "observed_metric_count": report.observed_metric_count,
                "not_measured_metric_count": report.not_measured_metric_count,
                "output_root": str(Path(output_root).expanduser().resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if not report.technical_contract_passed:
        return 1
    if args.require_research_ready and report.research_quality_status != "passed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
