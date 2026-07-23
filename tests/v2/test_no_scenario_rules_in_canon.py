from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_rei_canon_v2 import (
    find_forbidden_benchmark_phrases,
    normalize_for_benchmark_scan,
)


ROOT = Path(__file__).resolve().parents[2]


def test_no_benchmark_scenario_rules_in_canon_v2() -> None:
    findings = find_forbidden_benchmark_phrases(ROOT)
    assert not findings, "Forbidden benchmark rules found:\n" + "\n".join(
        f" - {finding}" for finding in findings
    )


@pytest.mark.parametrize(
    ("variant", "normalized"),
    [
        ("quit-job", "quit job"),
        ("SIDE_HUSTLE", "side hustle"),
        ("first business-change scenario", "first business change scenario"),
        ("all-in transition", "all in transition"),
    ],
)
def test_benchmark_scan_normalizes_punctuation_and_case(variant: str, normalized: str) -> None:
    assert normalize_for_benchmark_scan(variant) == normalized
