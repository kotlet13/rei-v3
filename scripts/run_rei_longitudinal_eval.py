"""Run or reproduce the deterministic C6 longitudinal Ego quality gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.backend.rei.evaluation.longitudinal_eval import (  # noqa: E402
    LONGITUDINAL_REPORT_FILENAMES,
    MAX_LONGITUDINAL_REPORT_BYTES,
    evaluate_longitudinal_corpus,
    render_longitudinal_report,
    write_longitudinal_report,
)


RUN_ID = "c6-longitudinal-2026-07-14"
DEFAULT_CORPUS_PATH = (
    REPO_ROOT
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "c6_longitudinal"
    / "corpus.json"
)
DEFAULT_TEMPLATE_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Docs" / "evals" / "semantic_lab_v1" / RUN_ID


def check_report(output_root: str | Path, expected: dict[str, bytes]) -> None:
    root = Path(output_root).expanduser().resolve()
    actual_names = (
        tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
        if root.is_dir()
        else ()
    )
    expected_names = tuple(sorted(LONGITUDINAL_REPORT_FILENAMES))
    if actual_names != expected_names:
        raise ValueError(
            f"C6 report artifact set differs: {actual_names!r} != {expected_names!r}"
        )
    mismatches: list[str] = []
    for name, payload in expected.items():
        path = root / name
        if path.stat().st_size > MAX_LONGITUDINAL_REPORT_BYTES:
            raise ValueError(f"C6 checked report {name!r} exceeds its size bound")
        if path.read_bytes() != payload:
            mismatches.append(name)
    if mismatches:
        raise ValueError(
            "C6 report bytes are not reproducible: " + ", ".join(mismatches)
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument(
        "--template-fixture", type=Path, default=DEFAULT_TEMPLATE_FIXTURE
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Re-run the full gate and compare checked-in report bytes without writing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = evaluate_longitudinal_corpus(
        corpus_path=args.corpus_path,
        template_fixture_path=args.template_fixture,
    )
    rendered = render_longitudinal_report(report)
    if args.check:
        check_report(args.output_root, rendered)
        action = "checked"
    else:
        write_longitudinal_report(report, args.output_root)
        action = "created"
    print(
        json.dumps(
            {
                "action": action,
                "run_id": RUN_ID,
                "report_id": report.report_id,
                "gate_passed": report.gate_passed,
                "technical_gate_passed": report.technical_gate_passed,
                "semantic_authority_granted": report.semantic_authority_granted,
                "instinkt_learning_scope": report.instinkt_learning_scope,
                "projection_signal_integration_complete": (
                    report.projection_signal_integration_complete
                ),
                "measured_body_signal_cycle_count": (
                    report.measured_body_signal_cycle_count
                ),
                "sequence_count": report.sequence_count,
                "total_cycle_count": report.total_cycle_count,
                "motif_precision": report.motif_precision,
                "output_root": str(Path(args.output_root).resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
