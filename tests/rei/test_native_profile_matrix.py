from __future__ import annotations

import hashlib
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

from app.backend.rei.governance.fixtures import load_governance_fixture
from app.backend.rei.ids import content_id, sha256_hex
from app.backend.rei.models.character import CHARACTER_PROFILE_ORDER
from app.backend.rei.profile_matrix import (
    NativeProfileMatrix,
    build_matrix_acceptance_state,
    run_native_profile_matrix,
)


REPO_ROOT = Path(__file__).parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "native_bundles"
RUNNER = REPO_ROOT / "scripts" / "run_rei_native_profile_matrix.py"
PROCESSOR_MODULE_SUFFIXES = (
    ".racio.processor",
    ".emocio.processor",
    ".instinkt.processor",
)

ACCEPTANCE_MODE_REGRESSIONS = (
    (
        "accepting",
        "profile_matrix_afee1d4ef7d55c8ae86cef713ef9d810",
        "3209a310369eea4d5050b40e5f122d429de38a98cb79ec1e971b04499aea4af9",
        0,
        0,
    ),
    (
        "mixed",
        "profile_matrix_8033a2430284e16648578ac4b7cb8e00",
        "70111b8b5a57a6d2fba1209f0fbd8d5c355ae4516fc9cb3853aa72eaee711c4d",
        54,
        79,
    ),
    (
        "conflicted",
        "profile_matrix_e7a58ae9d6b89a69959e89331b763a4d",
        "b7249e1d4b4f7aeccdbb48718c1aaaf96e6ea49ed0d8f64b598ed7781974ee31",
        54,
        130,
    ),
)


def _fixture_digests() -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(FIXTURE_ROOT.glob("*.json"))
    }


def test_matrix_is_exact_frozen_12_by_13_and_matches_governance_gold() -> None:
    before = _fixture_digests()

    matrix = run_native_profile_matrix(FIXTURE_ROOT)

    assert len(before) == 12
    assert matrix.mode == "controlled_profile_matrix"
    assert len(matrix.fixture_ids) == 12
    assert matrix.profile_order == CHARACTER_PROFILE_ORDER
    assert len(matrix.profile_order) == 13
    assert len(matrix.rows) == 156
    assert matrix.native_processor_executions == 0
    assert matrix.coverage.b10_oracle_rows == 156
    assert matrix.coverage.mandate_conscious_option_divergence_rows == 54
    assert matrix.coverage.conscious_behavior_state_divergence_rows == 130
    assert matrix.coverage.pair_conflict_rows == 36
    assert matrix.coverage.thirteenth_majority_rows == 9
    assert matrix.coverage.simulated_spoznanje_rows == 13
    assert _fixture_digests() == before

    rows_by_fixture = defaultdict(list)
    for row in matrix.rows:
        rows_by_fixture[row.fixture_id].append(row)
    assert tuple(rows_by_fixture) == matrix.fixture_ids

    for fixture_path in sorted(FIXTURE_ROOT.glob("*.json")):
        fixture = load_governance_fixture(fixture_path)
        fixture_rows = rows_by_fixture[fixture.fixture_id]
        expected_by_profile = {
            outcome.profile_id: outcome
            for outcome in fixture.expected_profile_outcomes
        }

        assert len(fixture_rows) == 13
        assert tuple(row.profile_id for row in fixture_rows) == CHARACTER_PROFILE_ORDER
        assert {row.native_bundle_id for row in fixture_rows} == {
            fixture.native_bundle.bundle_id
        }
        assert {row.native_bundle_hash for row in fixture_rows} == {
            fixture.native_bundle.immutable_hash
        }

        for row in fixture_rows:
            expected = expected_by_profile[row.profile_id]
            assert row.governance_status == expected.status
            assert row.governance_option_id == expected.option_id
            assert row.governance_source_minds == expected.source_minds
            assert row.governance_pair_status == expected.pair_status
            assert row.spoznanje_status == fixture.expected_spoznanje_status
            assert row.expected_governance_matched is True
            assert row.expected_b10_matched is True
            assert row.conscious_option_id == row.expected_conscious_option_id
            assert row.conscious_status == row.expected_conscious_status
            assert row.behavior_option_id == row.expected_behavior_option_id
            assert row.behavior_status == row.expected_behavior_status
            assert row.governance_alignment == row.expected_governance_alignment
            assert row.conscious_alignment == row.expected_conscious_alignment


@pytest.mark.parametrize(
    (
        "acceptance_mode",
        "expected_matrix_id",
        "expected_matrix_hash",
        "expected_mandate_conscious_divergence",
        "expected_conscious_behavior_divergence",
    ),
    ACCEPTANCE_MODE_REGRESSIONS,
)
def test_matrix_acceptance_modes_are_exact_frozen_regressions(
    acceptance_mode: str,
    expected_matrix_id: str,
    expected_matrix_hash: str,
    expected_mandate_conscious_divergence: int,
    expected_conscious_behavior_divergence: int,
) -> None:
    fixture_digests = _fixture_digests()
    acceptance_state = build_matrix_acceptance_state(acceptance_mode)

    matrix = run_native_profile_matrix(
        FIXTURE_ROOT,
        acceptance_state=acceptance_state,
    )

    assert matrix.matrix_id == expected_matrix_id
    assert matrix.matrix_hash == expected_matrix_hash
    assert matrix.acceptance_state == acceptance_state
    assert matrix.acceptance_state.overall_mode == acceptance_mode
    assert len(matrix.rows) == 156
    assert matrix.native_processor_executions == 0
    assert matrix.coverage.b10_oracle_rows == 156
    assert (
        matrix.coverage.mandate_conscious_option_divergence_rows
        == expected_mandate_conscious_divergence
    )
    assert (
        matrix.coverage.conscious_behavior_state_divergence_rows
        == expected_conscious_behavior_divergence
    )
    assert matrix.coverage.pair_conflict_rows == 36
    assert matrix.coverage.thirteenth_majority_rows == 9
    assert matrix.coverage.simulated_spoznanje_rows == 13
    assert _fixture_digests() == fixture_digests


def test_matrix_replay_is_byte_identical() -> None:
    first = run_native_profile_matrix(FIXTURE_ROOT)
    replay = run_native_profile_matrix(FIXTURE_ROOT)

    assert replay == first
    assert replay.matrix_id == first.matrix_id
    assert replay.matrix_hash == first.matrix_hash
    assert replay.canonical_json_bytes() == first.canonical_json_bytes()
    assert NativeProfileMatrix.model_validate_json(first.canonical_json_bytes()) == first


def test_rehashed_row_cannot_claim_a_false_b10_oracle_match() -> None:
    matrix = run_native_profile_matrix(FIXTURE_ROOT)
    payload = matrix.model_dump(mode="python", round_trip=True)
    row = payload["rows"][0]
    row["conscious_status"] = "blocked"
    row_base = {
        key: value for key, value in row.items() if key not in {"row_id", "row_hash"}
    }
    row["row_id"] = content_id("profile_matrix_row", row_base)
    row["row_hash"] = sha256_hex({"row_id": row["row_id"], **row_base})

    with pytest.raises(ValueError, match="independent B10 oracle"):
        NativeProfileMatrix.model_validate(payload)


def test_matrix_import_and_run_do_not_import_native_processors() -> None:
    script = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
from app.backend.rei.profile_matrix import run_native_profile_matrix
run_native_profile_matrix(Path({str(FIXTURE_ROOT)!r}))
for name in sys.modules:
    if name.endswith({PROCESSOR_MODULE_SUFFIXES!r}):
        raise SystemExit(f\"native processor imported: {{name}}\")
"""

    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""


def test_cli_emits_canonical_json_to_stdout() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--fixture-directory",
            str(FIXTURE_ROOT),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8")
    matrix = NativeProfileMatrix.model_validate_json(completed.stdout)
    assert completed.stdout == matrix.canonical_json_bytes()
    assert len(matrix.rows) == 156
    assert completed.stderr == b""


def test_cli_writes_canonical_json_to_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "matrix.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--fixture-directory",
            str(FIXTURE_ROOT),
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8")
    payload = output_path.read_bytes()
    matrix = NativeProfileMatrix.model_validate_json(payload)
    assert payload == matrix.canonical_json_bytes()
    assert len(matrix.rows) == 156
    assert completed.stdout == b""
    assert completed.stderr == b""
