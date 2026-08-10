"""Compare E1 and E1R pytest JUnit failure node IDs exactly."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _node_id(case: ET.Element) -> str:
    module = case.attrib["classname"].replace(".", "/") + ".py"
    return f"{module}::{case.attrib['name']}"


def _classify(node_id: str) -> str:
    if node_id.startswith("tests/evaluation/test_c3_official_pair.py::"):
        return "preexisting_c3_main_only_git_directory_gate"
    if node_id.startswith("tests/rei/test_triad_"):
        return "preexisting_frozen_triad_hash_or_lineage_gate"
    return "unclassified"


def _read(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    failures = sorted(
        _node_id(case)
        for case in cases
        if case.find("failure") is not None or case.find("error") is not None
    )
    skipped = sum(case.find("skipped") is not None for case in cases)
    time_seconds = sum(float(case.attrib.get("time", "0")) for case in cases)
    return {
        "tests": len(cases),
        "passed": len(cases) - len(failures) - skipped,
        "failed": len(failures),
        "skipped": skipped,
        "testcase_time_seconds": time_seconds,
        "junit_sha256": _sha256(path),
        "failure_node_ids": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = _read(args.baseline)
    candidate = _read(args.candidate)
    baseline_set = set(baseline["failure_node_ids"])
    candidate_set = set(candidate["failure_node_ids"])
    classes: dict[str, list[str]] = {}
    for node_id in sorted(candidate_set):
        classes.setdefault(_classify(node_id), []).append(node_id)
    result = {
        "schema_version": "rei-emocio-vwm-e1r-pytest-regression-v1",
        "baseline_commit": "a1a8e0922a9fb1fd21893b46087cc0e9155146d9",
        "candidate": "uncommitted_e1r_candidate",
        "command_contract": "python -m pytest -q --tb=short --junitxml=<path> --basetemp=<external-path>",
        "baseline": baseline,
        "candidate_result": candidate,
        "new_failures": sorted(candidate_set - baseline_set),
        "resolved_failures": sorted(baseline_set - candidate_set),
        "shared_failures": sorted(baseline_set & candidate_set),
        "candidate_failure_classes": classes,
        "exact_failure_set_match": baseline_set == candidate_set,
        "e1r_introduced_new_failure": bool(candidate_set - baseline_set),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "baseline_failed": baseline["failed"],
        "candidate_failed": candidate["failed"],
        "new_failures": result["new_failures"],
        "resolved_failures": result["resolved_failures"],
        "exact_failure_set_match": result["exact_failure_set_match"],
    }, indent=2))
    return 0 if result["exact_failure_set_match"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
