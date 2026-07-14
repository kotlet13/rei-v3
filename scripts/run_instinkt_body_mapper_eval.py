"""Run or reproduce the deterministic C5 Instinkt body-mapper quality gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.backend.rei.evaluation.body_mapper_eval import (  # noqa: E402
    BODY_MAPPER_REPORT_FILENAMES,
    evaluate_body_mapper,
    render_body_mapper_report,
    write_body_mapper_report,
)


RUN_ID = "c5-body-mapper-v3-2026-07-14"
DEFAULT_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "semantic_lab_v1"
DEFAULT_GOLD_PATH = (
    REPO_ROOT
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "c5_instinkt_body_mapper"
    / "gold.json"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Docs" / "evals" / "semantic_lab_v1" / RUN_ID


def check_report(output_root: str | Path, expected: dict[str, bytes]) -> None:
    root = Path(output_root).expanduser().resolve()
    actual_names = (
        tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
        if root.is_dir()
        else ()
    )
    expected_names = tuple(sorted(BODY_MAPPER_REPORT_FILENAMES))
    if actual_names != expected_names:
        raise ValueError(
            f"C5 report artifact set differs: {actual_names!r} != {expected_names!r}"
        )
    mismatches = [
        name for name, payload in expected.items() if (root / name).read_bytes() != payload
    ]
    if mismatches:
        raise ValueError(
            "C5 report bytes are not reproducible: " + ", ".join(mismatches)
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--gold-path", type=Path, default=DEFAULT_GOLD_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare checked-in report bytes without writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = evaluate_body_mapper(
        fixtures_root=args.fixture_root,
        gold_path=args.gold_path,
    )
    rendered = render_body_mapper_report(report)
    if args.check:
        check_report(args.output_root, rendered)
        action = "checked"
    else:
        write_body_mapper_report(report, args.output_root)
        action = "created"
    print(
        json.dumps(
            {
                "action": action,
                "run_id": RUN_ID,
                "report_id": report.report_id,
                "gate_passed": report.gate_passed,
                "gold_sha256": report.gold_sha256,
                "passing_case_count": report.passing_case_count,
                "positive_cell_count": report.positive_cell_count,
                "semantic_family_count": report.semantic_family_count,
                "passing_negative_control_count": (
                    report.passing_negative_control_count
                ),
                "negative_control_count": report.negative_control_count,
                "contract_violation_count": report.contract_violation_count,
                "output_root": str(Path(args.output_root).resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
