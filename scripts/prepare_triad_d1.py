"""Build or cold-verify bounded TRIAD-D1 and TRIAD-S2-candidate artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.backend.rei.research.triad_d1 import (
    TRIAD_S1_RELATIVE_PATH,
    TRIAD_S2_RELATIVE_PATH,
    audit_expected_answer_leakage,
    build_expected_call_ledger,
    build_s1_route_audit,
    build_s2_candidate,
    preflight_s2_candidate,
    render_route_audit,
    verify_frozen_s1_bytes,
)


def _render_json(value: Any) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


def _artifacts() -> Mapping[Path, str]:
    candidate = build_s2_candidate(REPOSITORY_ROOT)
    preflight = preflight_s2_candidate(candidate)
    leakage = audit_expected_answer_leakage(candidate)
    audit = build_s1_route_audit(REPOSITORY_ROOT)
    return {
        REPOSITORY_ROOT
        / TRIAD_S1_RELATIVE_PATH
        / "route_distinguishability_audit.md": render_route_audit(audit),
        REPOSITORY_ROOT
        / TRIAD_S2_RELATIVE_PATH
        / "corpus_candidate.json": _render_json(candidate),
        REPOSITORY_ROOT
        / TRIAD_S2_RELATIVE_PATH
        / "distinguishability_report.json": _render_json(preflight),
        REPOSITORY_ROOT
        / TRIAD_S2_RELATIVE_PATH
        / "leakage_report.json": _render_json(leakage),
        REPOSITORY_ROOT
        / TRIAD_S2_RELATIVE_PATH
        / "expected_call_ledger.json": _render_json(
            build_expected_call_ledger()
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Compare committed artifacts with a cold model-free rebuild.",
    )
    args = parser.parse_args()
    verify_frozen_s1_bytes(REPOSITORY_ROOT)
    artifacts = _artifacts()
    if args.verify:
        for path, expected in artifacts.items():
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                raise ValueError(f"TRIAD-D1 artifact differs from cold rebuild: {path}")
        print(
            json.dumps(
                {
                    "status": "verified",
                    "artifact_count": len(artifacts),
                    "frozen_s1_bytes_unchanged": True,
                    "model_calls": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    for path, rendered in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": "prepared",
                "artifact_count": len(artifacts),
                "frozen_s1_bytes_unchanged": True,
                "model_calls": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
