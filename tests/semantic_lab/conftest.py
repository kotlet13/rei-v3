from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "knowledge" / "semantic_lab_v1"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "semantic_lab_v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture(scope="session")
def families() -> list[dict[str, Any]]:
    return read_jsonl(SOURCE_ROOT / "scenario_families" / "families.jsonl")


@pytest.fixture(scope="session")
def family_fixtures() -> dict[str, dict[str, Any]]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURE_ROOT.glob("sf_*.json"))
    }


@pytest.fixture(scope="session")
def fixture_manifest() -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
