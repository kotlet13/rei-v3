from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_IDS = [
    "conflict_with_coworker::REI",
    "boundary_violation::RI",
    "boundary_violation::R>E>I",
    "boundary_violation::E>I>R",
    "boundary_violation::I>E>R",
    "family_attachment_decision::EI",
    "family_attachment_decision::REI",
]
KEEP_KEYS = [
    "scenario_id",
    "profile_input",
    "signals",
    "acceptance",
    "ego_resultant",
    "false_positive_flags",
    "false_negative_flags",
    "false_negative_severity",
]


def case_key(case: dict[str, Any]) -> str:
    return f"{case.get('scenario_id')}::{case.get('profile_input')}"


def latest_cases_json() -> Path:
    root = ROOT / "output" / "reports" / "rei_profile_matrix"
    candidates = [
        path
        for path in root.glob("*/cases.json")
        if path.is_file() and not path.parent.name.startswith("_")
    ]
    if not candidates:
        raise SystemExit(f"No cases.json files found under {root}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def read_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Expected list of cases in {path}")
    return [case for case in data if isinstance(case, dict)]


def extract_case(case: dict[str, Any]) -> dict[str, Any]:
    output = case.get("output") if isinstance(case.get("output"), dict) else {}
    return {
        "scenario_id": case.get("scenario_id"),
        "profile_input": case.get("profile_input"),
        "signals": output.get("signals"),
        "acceptance": output.get("acceptance"),
        "ego_resultant": output.get("ego_resultant"),
        "false_positive_flags": case.get("false_positive_flags"),
        "false_negative_flags": case.get("false_negative_flags"),
        "false_negative_severity": case.get("false_negative_severity"),
    }


def filter_cases(cases: list[dict[str, Any]], requested_ids: list[str]) -> list[dict[str, Any]]:
    by_id = {case_key(case): case for case in cases}
    missing = [case_id for case_id in requested_ids if case_id not in by_id]
    if missing:
        raise SystemExit(f"Missing requested cases: {', '.join(missing)}")
    return [extract_case(by_id[case_id]) for case_id in requested_ids]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export focused REI profile matrix cases for inspection.")
    parser.add_argument(
        "cases_json",
        nargs="?",
        default=None,
        help="Path to a profile matrix cases.json. Defaults to the newest non-smoke matrix cases.json.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path. Defaults to filtered_rei_cases.json beside cases_json.",
    )
    parser.add_argument(
        "--case",
        dest="case_ids",
        action="append",
        default=None,
        help="Case id in scenario::profile form. Repeat to override the default hard-failure case list.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases_path = Path(args.cases_json) if args.cases_json else latest_cases_json()
    cases_path = cases_path.resolve()
    case_ids = args.case_ids or DEFAULT_CASE_IDS
    output_path = Path(args.output) if args.output else cases_path.with_name("filtered_rei_cases.json")
    extracted = filter_cases(read_cases(cases_path), case_ids)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(extracted, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(extracted)} filtered cases to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
