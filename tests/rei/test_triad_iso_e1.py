from __future__ import annotations

import json
from pathlib import Path

from app.backend.rei.research.triad_iso_e1 import (
    CANDIDATE_RELATIVE_PATH,
    EXPECTED_CANDIDATE_SHA256,
    pair_invariant_report,
    prepare_cases,
)
from app.backend.rei.research.triad_s2 import build_provider


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_frozen_candidate_and_pair_invariants() -> None:
    import hashlib

    path = _root() / CANDIDATE_RELATIVE_PATH
    assert hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_CANDIDATE_SHA256
    candidate = json.loads(path.read_text(encoding="utf-8"))
    provider = build_provider()
    prepared = prepare_cases(candidate, provider)
    report = pair_invariant_report(candidate, prepared)

    assert report["passed"] is True
    assert all(report["checks"].values())
    assert len(prepared) == 4
