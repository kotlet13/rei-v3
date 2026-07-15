from __future__ import annotations

from pathlib import Path

import pytest

from app.backend.rei.evaluation.controlled_profile_eval import (
    CONTROLLED_ACCEPTANCE_MODE_ORDER,
    ControlledProfileAcceptanceReport,
    evaluate_controlled_profile_acceptance,
)
from app.backend.rei.ids import content_id, sha256_hex
from app.backend.rei.models.character import CHARACTER_PROFILE_ORDER


REPO_ROOT = Path(__file__).parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "native_bundles"


@pytest.fixture(scope="module")
def report() -> ControlledProfileAcceptanceReport:
    return evaluate_controlled_profile_acceptance(FIXTURE_ROOT)


def _status_map(values: object) -> dict[str, int]:
    return {item.status: item.count for item in values}


def _rehash_mode(payload: dict[str, object], index: int) -> None:
    mode = payload["mode_results"][index]
    base = {
        key: value
        for key, value in mode.items()
        if key not in {"mode_result_id", "mode_result_hash"}
    }
    mode["mode_result_id"] = content_id("controlled_profile_mode", base)
    mode["mode_result_hash"] = sha256_hex(
        {"mode_result_id": mode["mode_result_id"], **base}
    )


def _rehash_invariant(payload: dict[str, object], index: int) -> None:
    invariant = payload["paired_invariants"][index]
    base = {
        key: value
        for key, value in invariant.items()
        if key not in {"invariant_id", "invariant_hash"}
    }
    invariant["invariant_id"] = content_id("controlled_profile_invariant", base)
    invariant["invariant_hash"] = sha256_hex(
        {"invariant_id": invariant["invariant_id"], **base}
    )


def _rehash_report(payload: dict[str, object]) -> None:
    base = {
        key: value
        for key, value in payload.items()
        if key not in {"report_id", "report_hash"}
    }
    payload["report_id"] = content_id("controlled_profile_acceptance", base)
    payload["report_hash"] = sha256_hex(
        {"report_id": payload["report_id"], **base}
    )


def test_report_is_exact_paired_12_by_13_by_3_without_native_execution(
    report: ControlledProfileAcceptanceReport,
) -> None:
    assert report.report_id == (
        "controlled_profile_acceptance_fc866622cdf2fe1c5e24ea6787bafd3a"
    )
    assert report.report_hash == (
        "63c1e0293f99efc5bc0e736aaa24491ecc1a2a5d15c7e6362a97b58a58107c13"
    )
    assert report.fixture_count == 12
    assert report.profile_count == 13
    assert report.mode_count == 3
    assert report.total_row_count == 468
    assert report.native_processor_executions == 0
    assert len(report.paired_invariants) == 156
    assert report.frozen_bundle_governance_invariant is True
    assert report.technical_contract_passed is True
    assert report.semantic_authority_granted is False
    assert report.aggregate_score_present is False
    assert "score" not in type(report).model_fields

    assert tuple(item.mode for item in report.mode_results) == (
        CONTROLLED_ACCEPTANCE_MODE_ORDER
    )
    for result in report.mode_results:
        assert result.row_count == 156
        assert result.native_processor_executions == 0
        assert len(result.matrix.fixture_ids) == 12
        assert result.matrix.profile_order == CHARACTER_PROFILE_ORDER


def test_mode_metrics_preserve_acceptance_specific_conscious_behavior_results(
    report: ControlledProfileAcceptanceReport,
) -> None:
    by_mode = {item.mode: item for item in report.mode_results}

    assert by_mode["accepting"].mandate_conscious_option_divergence_count == 0
    assert by_mode["mixed"].mandate_conscious_option_divergence_count == 54
    assert by_mode["conflicted"].mandate_conscious_option_divergence_count == 54
    assert by_mode["accepting"].conscious_behavior_state_divergence_count == 0
    assert by_mode["mixed"].conscious_behavior_state_divergence_count == 79
    assert by_mode["conflicted"].conscious_behavior_state_divergence_count == 130

    assert _status_map(by_mode["accepting"].behavior_status_counts) == {
        "executed": 130,
        "delayed": 0,
        "oscillating": 0,
        "sabotaged": 0,
        "blocked": 0,
        "unresolved": 26,
    }
    assert _status_map(by_mode["mixed"].behavior_status_counts) == {
        "executed": 51,
        "delayed": 0,
        "oscillating": 79,
        "sabotaged": 0,
        "blocked": 0,
        "unresolved": 26,
    }
    assert _status_map(by_mode["conflicted"].behavior_status_counts) == {
        "executed": 0,
        "delayed": 0,
        "oscillating": 0,
        "sabotaged": 130,
        "blocked": 0,
        "unresolved": 26,
    }
    assert all(
        item.conscious_behavior_option_divergence_count == 0
        for item in report.mode_results
    )


def test_every_fixture_profile_pair_keeps_bundle_and_governance_frozen(
    report: ControlledProfileAcceptanceReport,
) -> None:
    row_maps = tuple(
        {
            (row.fixture_id, row.profile_id): row
            for row in result.matrix.rows
        }
        for result in report.mode_results
    )

    for invariant in report.paired_invariants:
        key = (invariant.fixture_id, invariant.profile_id)
        rows = tuple(row_map[key] for row_map in row_maps)
        assert tuple(item.mode for item in invariant.mode_rows) == (
            CONTROLLED_ACCEPTANCE_MODE_ORDER
        )
        assert {row.native_bundle_id for row in rows} == {
            invariant.native_bundle_id
        }
        assert {row.native_bundle_hash for row in rows} == {
            invariant.native_bundle_hash
        }
        assert {row.governance_resolution_id for row in rows} == {
            invariant.governance_resolution_id
        }
        assert {row.governance_resolution_hash for row in rows} == {
            invariant.governance_resolution_hash
        }
        assert {row.governance_status for row in rows} == {
            invariant.governance_status
        }
        assert {row.governance_option_id for row in rows} == {
            invariant.governance_option_id
        }
        assert {row.governance_source_minds for row in rows} == {
            invariant.governance_source_minds
        }
        assert {row.governance_pair_status for row in rows} == {
            invariant.governance_pair_status
        }
        assert {row.spoznanje_status for row in rows} == {
            invariant.spoznanje_status
        }


def test_report_replay_is_byte_identical(
    report: ControlledProfileAcceptanceReport,
) -> None:
    replay = evaluate_controlled_profile_acceptance(FIXTURE_ROOT)

    assert replay == report
    assert replay.canonical_json_bytes() == report.canonical_json_bytes()
    assert ControlledProfileAcceptanceReport.model_validate_json(
        report.canonical_json_bytes()
    ) == report


def test_rehashed_mode_metrics_cannot_disagree_with_matrix_replay(
    report: ControlledProfileAcceptanceReport,
) -> None:
    payload = report.model_dump(mode="python", round_trip=True)
    payload["mode_results"][0][
        "conscious_behavior_state_divergence_count"
    ] = 1
    _rehash_mode(payload, 0)
    _rehash_report(payload)

    with pytest.raises(ValueError, match="mode metrics differ from matrix replay"):
        ControlledProfileAcceptanceReport.model_validate(payload)


def test_rehashed_pair_cannot_forge_cross_mode_governance_invariance(
    report: ControlledProfileAcceptanceReport,
) -> None:
    payload = report.model_dump(mode="python", round_trip=True)
    invariant = payload["paired_invariants"][0]
    invariant["governance_status"] = (
        "unresolved"
        if invariant["governance_status"] != "unresolved"
        else "resolved"
    )
    _rehash_invariant(payload, 0)
    _rehash_report(payload)

    with pytest.raises(ValueError, match="invariants differ from paired replay"):
        ControlledProfileAcceptanceReport.model_validate(payload)


def test_report_hash_is_content_addressed(
    report: ControlledProfileAcceptanceReport,
) -> None:
    payload = report.model_dump(mode="python", round_trip=True)
    payload["report_hash"] = "0" * 64

    with pytest.raises(ValueError, match="report hash differs from content"):
        ControlledProfileAcceptanceReport.model_validate(payload)
