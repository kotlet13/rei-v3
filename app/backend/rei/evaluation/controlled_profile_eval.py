"""Controlled C7 acceptance ablation over frozen native bundles.

The evaluator changes only the explicit acceptance mode.  It reuses each of
the twelve checked-in native bundles across the canonical thirteen structural
Character profiles and never executes a native processor.  The report keeps
the three dimensional cohorts separate; it deliberately defines no aggregate
score and grants no semantic authority about people.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from ..models.character import CHARACTER_PROFILE_ORDER, CharacterProfileId
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    MindId,
    NonEmptyId,
    NonEmptyText,
)
from ..models.conscious import (
    AlignmentStatus,
    BehaviorStatus,
    ConsciousDecisionStatus,
)
from ..models.governance import (
    GovernanceStatus,
    PairConflictStatus,
    SpoznanjeStatus,
)
from ..profile_matrix import (
    NativeProfileMatrix,
    NativeProfileMatrixRow,
    build_matrix_acceptance_state,
    run_native_profile_matrix,
)


ControlledAcceptanceMode = Literal["accepting", "mixed", "conflicted"]
CONTROLLED_ACCEPTANCE_MODE_ORDER: tuple[ControlledAcceptanceMode, ...] = (
    "accepting",
    "mixed",
    "conflicted",
)
_CONSCIOUS_STATUS_ORDER: tuple[ConsciousDecisionStatus, ...] = (
    "committed",
    "deferred",
    "oscillating",
    "blocked",
    "unknown",
)
_BEHAVIOR_STATUS_ORDER: tuple[BehaviorStatus, ...] = (
    "executed",
    "delayed",
    "oscillating",
    "sabotaged",
    "blocked",
    "unresolved",
)
_ALIGNMENT_STATUS_ORDER: tuple[AlignmentStatus, ...] = (
    "aligned",
    "diverged",
    "unknown",
    "not_applicable",
)


def _cold_revalidate(value):
    model_type = type(value)
    cold = model_type.model_validate(
        value.model_dump(mode="python", round_trip=True)
    )
    if cold != value:
        raise ValueError("Controlled profile input changed during cold validation")
    return cold


class ControlledProfileStatusCount(FrozenModel):
    """One explicit categorical count; zero-count categories stay visible."""

    status: NonEmptyId
    count: int = Field(ge=0, le=156)


class ControlledProfileOptionCount(FrozenModel):
    """One option-frequency cell, including explicit abstention as ``None``."""

    option_id: NonEmptyId | None
    count: int = Field(ge=1, le=156)


def _status_counts(
    values: tuple[str, ...],
    order: tuple[str, ...],
) -> tuple[ControlledProfileStatusCount, ...]:
    counts = Counter(values)
    if set(counts).difference(order):
        raise ValueError("Controlled profile matrix contains an unknown status")
    return tuple(
        ControlledProfileStatusCount(status=status, count=counts[status])
        for status in order
    )


def _option_counts(
    values: tuple[str | None, ...],
) -> tuple[ControlledProfileOptionCount, ...]:
    counts = Counter(values)
    return tuple(
        ControlledProfileOptionCount(option_id=option_id, count=counts[option_id])
        for option_id in sorted(
            counts,
            key=lambda value: (value is not None, value or ""),
        )
    )


def _mode_metrics(matrix: NativeProfileMatrix) -> dict[str, object]:
    rows = matrix.rows
    return {
        "row_count": len(rows),
        "native_processor_executions": matrix.native_processor_executions,
        "mandate_conscious_option_divergence_count": (
            matrix.coverage.mandate_conscious_option_divergence_rows
        ),
        "conscious_behavior_state_divergence_count": (
            matrix.coverage.conscious_behavior_state_divergence_rows
        ),
        "conscious_behavior_option_divergence_count": sum(
            row.conscious_option_id != row.behavior_option_id for row in rows
        ),
        "conscious_status_counts": _status_counts(
            tuple(row.conscious_status for row in rows),
            _CONSCIOUS_STATUS_ORDER,
        ),
        "behavior_status_counts": _status_counts(
            tuple(row.behavior_status for row in rows),
            _BEHAVIOR_STATUS_ORDER,
        ),
        "governance_alignment_counts": _status_counts(
            tuple(row.governance_alignment for row in rows),
            _ALIGNMENT_STATUS_ORDER,
        ),
        "conscious_alignment_counts": _status_counts(
            tuple(row.conscious_alignment for row in rows),
            _ALIGNMENT_STATUS_ORDER,
        ),
        "conscious_option_counts": _option_counts(
            tuple(row.conscious_option_id for row in rows)
        ),
        "behavior_option_counts": _option_counts(
            tuple(row.behavior_option_id for row in rows)
        ),
    }


class ControlledProfileAcceptanceModeResult(FrozenArtifactModel):
    """One exact 12 x 13 acceptance-mode cohort and its separate metrics."""

    schema_version: Literal["rei-c7-controlled-profile-mode-result-v1"] = (
        "rei-c7-controlled-profile-mode-result-v1"
    )
    mode_result_id: NonEmptyId
    mode: ControlledAcceptanceMode
    matrix: NativeProfileMatrix
    row_count: Literal[156] = 156
    native_processor_executions: Literal[0] = 0
    mandate_conscious_option_divergence_count: int = Field(ge=0, le=156)
    conscious_behavior_state_divergence_count: int = Field(ge=0, le=156)
    conscious_behavior_option_divergence_count: int = Field(ge=0, le=156)
    conscious_status_counts: tuple[ControlledProfileStatusCount, ...]
    behavior_status_counts: tuple[ControlledProfileStatusCount, ...]
    governance_alignment_counts: tuple[ControlledProfileStatusCount, ...]
    conscious_alignment_counts: tuple[ControlledProfileStatusCount, ...]
    conscious_option_counts: tuple[ControlledProfileOptionCount, ...]
    behavior_option_counts: tuple[ControlledProfileOptionCount, ...]
    mode_result_hash: HashDigest

    @classmethod
    def create(
        cls,
        matrix: NativeProfileMatrix,
    ) -> "ControlledProfileAcceptanceModeResult":
        matrix = _cold_revalidate(matrix)
        mode = matrix.acceptance_state.overall_mode
        if mode not in CONTROLLED_ACCEPTANCE_MODE_ORDER:
            raise ValueError(
                "Controlled profile evaluation excludes unknown acceptance"
            )
        base = {
            "schema_version": "rei-c7-controlled-profile-mode-result-v1",
            "mode": mode,
            "matrix": matrix,
            **_mode_metrics(matrix),
        }
        mode_result_id = content_id("controlled_profile_mode", base)
        payload = {"mode_result_id": mode_result_id, **base}
        return cls(**payload, mode_result_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_mode_result(self) -> Self:
        matrix = _cold_revalidate(self.matrix)
        if matrix.acceptance_state.overall_mode != self.mode:
            raise ValueError("Controlled profile mode differs from AcceptanceState")
        if self.mode not in CONTROLLED_ACCEPTANCE_MODE_ORDER:
            raise ValueError("Controlled profile mode is outside canonical scope")
        expected = _mode_metrics(matrix)
        actual = {key: getattr(self, key) for key in expected}
        if actual != expected:
            raise ValueError(
                "Controlled profile mode metrics differ from matrix replay"
            )
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"mode_result_id", "mode_result_hash"},
        )
        if self.mode_result_id != content_id("controlled_profile_mode", base):
            raise ValueError(
                "Controlled profile mode ID differs from canonical content"
            )
        payload = {"mode_result_id": self.mode_result_id, **base}
        if self.mode_result_hash != sha256_hex(payload):
            raise ValueError(
                "Controlled profile mode hash differs from canonical content"
            )
        return self


class ControlledProfileModeRowRef(FrozenModel):
    mode: ControlledAcceptanceMode
    row_id: NonEmptyId
    row_hash: HashDigest
    acceptance_state_id: NonEmptyId
    acceptance_state_hash: HashDigest


def _governance_signature(row: NativeProfileMatrixRow) -> tuple[object, ...]:
    return (
        row.fixture_id,
        row.profile_id,
        row.native_bundle_id,
        row.native_bundle_hash,
        row.governance_resolution_id,
        row.governance_resolution_hash,
        row.governance_status,
        row.governance_option_id,
        row.governance_source_minds,
        row.governance_pair_status,
        row.spoznanje_status,
    )


class ControlledProfilePairedInvariant(FrozenArtifactModel):
    """One fixture/profile pair proven invariant across all three modes."""

    schema_version: Literal["rei-c7-controlled-profile-paired-invariant-v1"] = (
        "rei-c7-controlled-profile-paired-invariant-v1"
    )
    invariant_id: NonEmptyId
    fixture_id: NonEmptyId
    profile_id: CharacterProfileId
    native_bundle_id: NonEmptyId
    native_bundle_hash: HashDigest
    governance_resolution_id: NonEmptyId
    governance_resolution_hash: HashDigest
    governance_status: GovernanceStatus
    governance_option_id: NonEmptyId | None
    governance_source_minds: tuple[MindId, ...]
    governance_pair_status: PairConflictStatus | None
    spoznanje_status: SpoznanjeStatus
    mode_rows: tuple[ControlledProfileModeRowRef, ...] = Field(
        min_length=3,
        max_length=3,
    )
    invariant_hash: HashDigest

    @classmethod
    def create(
        cls,
        rows: tuple[NativeProfileMatrixRow, ...],
    ) -> "ControlledProfilePairedInvariant":
        if len(rows) != len(CONTROLLED_ACCEPTANCE_MODE_ORDER):
            raise ValueError("Controlled profile pair requires exactly three rows")
        signatures = tuple(_governance_signature(row) for row in rows)
        if any(signature != signatures[0] for signature in signatures[1:]):
            raise ValueError(
                "Frozen bundle or governance changed across acceptance modes"
            )
        acceptance_state_ids = tuple(row.acceptance_state_id for row in rows)
        if len(set(acceptance_state_ids)) != len(acceptance_state_ids):
            raise ValueError("Controlled acceptance states must be distinct")
        first = rows[0]
        mode_rows = tuple(
            ControlledProfileModeRowRef(
                mode=mode,
                row_id=row.row_id,
                row_hash=row.row_hash,
                acceptance_state_id=row.acceptance_state_id,
                acceptance_state_hash=row.acceptance_state_hash,
            )
            for mode, row in zip(CONTROLLED_ACCEPTANCE_MODE_ORDER, rows, strict=True)
        )
        base = {
            "schema_version": "rei-c7-controlled-profile-paired-invariant-v1",
            "fixture_id": first.fixture_id,
            "profile_id": first.profile_id,
            "native_bundle_id": first.native_bundle_id,
            "native_bundle_hash": first.native_bundle_hash,
            "governance_resolution_id": first.governance_resolution_id,
            "governance_resolution_hash": first.governance_resolution_hash,
            "governance_status": first.governance_status,
            "governance_option_id": first.governance_option_id,
            "governance_source_minds": first.governance_source_minds,
            "governance_pair_status": first.governance_pair_status,
            "spoznanje_status": first.spoznanje_status,
            "mode_rows": mode_rows,
        }
        invariant_id = content_id("controlled_profile_invariant", base)
        payload = {"invariant_id": invariant_id, **base}
        return cls(**payload, invariant_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_invariant(self) -> Self:
        modes = tuple(item.mode for item in self.mode_rows)
        if modes != CONTROLLED_ACCEPTANCE_MODE_ORDER:
            raise ValueError("Controlled profile row refs use non-canonical mode order")
        if len({item.row_id for item in self.mode_rows}) != len(self.mode_rows):
            raise ValueError("Controlled profile paired rows must be distinct")
        if len({item.acceptance_state_id for item in self.mode_rows}) != len(
            self.mode_rows
        ):
            raise ValueError("Controlled profile paired states must be distinct")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"invariant_id", "invariant_hash"},
        )
        if self.invariant_id != content_id("controlled_profile_invariant", base):
            raise ValueError("Controlled profile invariant ID differs from content")
        payload = {"invariant_id": self.invariant_id, **base}
        if self.invariant_hash != sha256_hex(payload):
            raise ValueError("Controlled profile invariant hash differs from content")
        return self


def _paired_invariants(
    mode_results: tuple[ControlledProfileAcceptanceModeResult, ...],
) -> tuple[ControlledProfilePairedInvariant, ...]:
    matrix_rows = tuple(item.matrix.rows for item in mode_results)
    row_keys = tuple(
        tuple((row.fixture_id, row.profile_id) for row in rows)
        for rows in matrix_rows
    )
    if any(keys != row_keys[0] for keys in row_keys[1:]):
        raise ValueError("Controlled profile matrices have different row coverage")
    return tuple(
        ControlledProfilePairedInvariant.create(rows)
        for rows in zip(*matrix_rows, strict=True)
    )


class ControlledProfileAcceptanceReport(FrozenArtifactModel):
    """Content-addressed 12 x 13 x 3 governance/acceptance report."""

    schema_version: Literal["rei-c7-controlled-profile-acceptance-report-v1"] = (
        "rei-c7-controlled-profile-acceptance-report-v1"
    )
    report_id: NonEmptyId
    evaluator_revision: Literal["c7-controlled-profile-v1"] = (
        "c7-controlled-profile-v1"
    )
    gate_kind: Literal["bounded_software_contract"] = "bounded_software_contract"
    authority_scope: Literal[
        "synthetic_governance_counterfactual_not_person_semantics"
    ] = "synthetic_governance_counterfactual_not_person_semantics"
    semantic_authority_granted: Literal[False] = False
    aggregate_score_present: Literal[False] = False
    fixture_directory: NonEmptyText
    fixture_count: Literal[12] = 12
    profile_count: Literal[13] = 13
    mode_count: Literal[3] = 3
    total_row_count: Literal[468] = 468
    native_processor_executions: Literal[0] = 0
    mode_results: tuple[ControlledProfileAcceptanceModeResult, ...] = Field(
        min_length=3,
        max_length=3,
    )
    paired_invariants: tuple[ControlledProfilePairedInvariant, ...] = Field(
        min_length=156,
        max_length=156,
    )
    frozen_bundle_governance_invariant: Literal[True] = True
    technical_contract_passed: Literal[True] = True
    report_hash: HashDigest

    @classmethod
    def create(
        cls,
        mode_results: tuple[ControlledProfileAcceptanceModeResult, ...],
    ) -> "ControlledProfileAcceptanceReport":
        mode_results = tuple(_cold_revalidate(item) for item in mode_results)
        modes = tuple(item.mode for item in mode_results)
        if modes != CONTROLLED_ACCEPTANCE_MODE_ORDER:
            raise ValueError("Controlled profile modes must use canonical order")
        invariants = _paired_invariants(mode_results)
        fixture_directory = mode_results[0].matrix.fixture_directory
        base = {
            "schema_version": "rei-c7-controlled-profile-acceptance-report-v1",
            "evaluator_revision": "c7-controlled-profile-v1",
            "gate_kind": "bounded_software_contract",
            "authority_scope": (
                "synthetic_governance_counterfactual_not_person_semantics"
            ),
            "semantic_authority_granted": False,
            "aggregate_score_present": False,
            "fixture_directory": fixture_directory,
            "fixture_count": 12,
            "profile_count": 13,
            "mode_count": 3,
            "total_row_count": 468,
            "native_processor_executions": 0,
            "mode_results": mode_results,
            "paired_invariants": invariants,
            "frozen_bundle_governance_invariant": True,
            "technical_contract_passed": True,
        }
        report_id = content_id("controlled_profile_acceptance", base)
        payload = {"report_id": report_id, **base}
        return cls(**payload, report_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        mode_results = tuple(_cold_revalidate(item) for item in self.mode_results)
        modes = tuple(item.mode for item in mode_results)
        if modes != CONTROLLED_ACCEPTANCE_MODE_ORDER:
            raise ValueError("Controlled profile report mode order differs")
        matrices = tuple(item.matrix for item in mode_results)
        fixture_directories = {matrix.fixture_directory for matrix in matrices}
        fixture_orders = {matrix.fixture_ids for matrix in matrices}
        profile_orders = {matrix.profile_order for matrix in matrices}
        if fixture_directories != {self.fixture_directory}:
            raise ValueError("Controlled profile fixture directories differ")
        if len(fixture_orders) != 1 or len(next(iter(fixture_orders))) != 12:
            raise ValueError(
                "Controlled profile reports require one frozen fixture set"
            )
        if profile_orders != {CHARACTER_PROFILE_ORDER}:
            raise ValueError("Controlled profile reports require canonical profiles")
        if sum(item.row_count for item in mode_results) != self.total_row_count:
            raise ValueError("Controlled profile report row count differs")
        if sum(
            item.native_processor_executions for item in mode_results
        ) != self.native_processor_executions:
            raise ValueError("Controlled profile report executed native processors")
        expected_invariants = _paired_invariants(mode_results)
        if self.paired_invariants != expected_invariants:
            raise ValueError("Controlled profile invariants differ from paired replay")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"report_id", "report_hash"},
        )
        if self.report_id != content_id("controlled_profile_acceptance", base):
            raise ValueError("Controlled profile report ID differs from content")
        payload = {"report_id": self.report_id, **base}
        if self.report_hash != sha256_hex(payload):
            raise ValueError("Controlled profile report hash differs from content")
        return self


def evaluate_controlled_profile_acceptance(
    fixture_directory: str | Path,
) -> ControlledProfileAcceptanceReport:
    """Run the exact frozen 12 x 13 matrix under all three acceptance modes."""

    mode_results = tuple(
        ControlledProfileAcceptanceModeResult.create(
            run_native_profile_matrix(
                fixture_directory,
                acceptance_state=build_matrix_acceptance_state(mode),
            )
        )
        for mode in CONTROLLED_ACCEPTANCE_MODE_ORDER
    )
    return ControlledProfileAcceptanceReport.create(mode_results)


__all__ = [
    "CONTROLLED_ACCEPTANCE_MODE_ORDER",
    "ControlledProfileAcceptanceModeResult",
    "ControlledProfileAcceptanceReport",
    "ControlledProfileOptionCount",
    "ControlledProfilePairedInvariant",
    "ControlledProfileStatusCount",
    "evaluate_controlled_profile_acceptance",
]
