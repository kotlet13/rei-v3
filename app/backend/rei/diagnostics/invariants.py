"""Inspectable invariant gate for one completed native REI cycle."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from ..ids import content_id, sha256_hex
from ..models.character import CharacterAuthority, EffectiveAuthority
from ..models.common import FrozenArtifactModel, FrozenModel, HashDigest, NonEmptyId
from ..models.conscious import (
    BehaviorResultant,
    ConsciousDecision,
    RacioSelfNarrative,
)
from ..models.ego import EgoCompositionSnapshot, EgoMeasure, EgoTrace
from ..models.governance import GovernanceResolution
from ..models.run import NativeMindBundle, RunManifest


class InvariantCheck(FrozenModel):
    check_id: NonEmptyId
    status: Literal["passed", "failed"]
    detail: str


class InvariantReport(FrozenArtifactModel):
    schema_version: Literal["rei-native-invariant-report-v1"] = (
        "rei-native-invariant-report-v1"
    )
    report_id: NonEmptyId
    run_id: NonEmptyId
    checks: tuple[InvariantCheck, ...]
    all_passed: bool
    report_hash: HashDigest

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        check_ids = tuple(item.check_id for item in self.checks)
        if len(set(check_ids)) != len(check_ids):
            raise ValueError("Invariant check IDs must be unique")
        expected_all_passed = bool(self.checks) and all(
            item.status == "passed" for item in self.checks
        )
        if self.all_passed != expected_all_passed:
            raise ValueError("Invariant report summary differs from its checks")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"report_id", "report_hash"},
        )
        if self.report_id != content_id("invariant_report", base):
            raise ValueError("Invariant report ID differs from canonical content")
        payload = {"report_id": self.report_id, **base}
        if self.report_hash != sha256_hex(payload):
            raise ValueError("Invariant report hash differs from canonical content")
        return self


def _check(check_id: str, condition: bool, detail: str) -> InvariantCheck:
    return InvariantCheck(
        check_id=check_id,
        status="passed" if condition else "failed",
        detail=detail,
    )


def build_cycle_invariant_report(
    *,
    run_id: NonEmptyId,
    bundle: NativeMindBundle,
    character: CharacterAuthority,
    effective_authority: EffectiveAuthority,
    governance: GovernanceResolution,
    decision: ConsciousDecision,
    behavior: BehaviorResultant,
    narrative: RacioSelfNarrative,
    measure: EgoMeasure,
    trace: EgoTrace,
    snapshot: EgoCompositionSnapshot,
    manifest: RunManifest,
) -> InvariantReport:
    """Evaluate cross-layer boundaries without introducing a new decision maker."""

    checks = (
        _check(
            "native_bundle_frozen",
            bundle.immutable_hash == bundle.content_hash(
                exclude_fields=frozenset({"immutable_hash"})
            ),
            "NativeMindBundle content matches its immutable hash.",
        ),
        _check(
            "structural_character_preserved",
            effective_authority.structural_profile == character,
            "Effective authority preserves the complete structural character.",
        ),
        _check(
            "governance_bound_to_bundle",
            governance.native_bundle_id == bundle.bundle_id
            and governance.native_bundle_hash == bundle.immutable_hash,
            "Governance cites the exact native bundle ID and hash.",
        ),
        _check(
            "conscious_decision_is_racio",
            decision.made_by == "R" and decision.derivation_status == "derived_b10",
            "The conscious decision is an explicit derived B10 Racio artifact.",
        ),
        _check(
            "behavior_bound_to_decision",
            behavior.source_decision_id == decision.decision_id
            and behavior.source_decision_hash == decision.content_hash(),
            "Behavior cites the exact frozen conscious decision.",
        ),
        _check(
            "narration_is_downstream",
            narrative.source_decision_id == decision.decision_id
            and narrative.source_resultant_id == behavior.resultant_id,
            "Narration cites rather than replaces decision and behavior.",
        ),
        _check(
            "ego_measure_closes_cycle",
            measure.native_bundle_id == bundle.bundle_id
            and measure.governance_resolution_id == governance.resolution_id
            and measure.conscious_decision == decision
            and measure.behavior_resultant == behavior,
            "EgoMeasure records the exact completed cycle artifacts.",
        ),
        _check(
            "ego_trace_append_only_result",
            bool(trace.measures) and trace.measures[-1].measure_id == measure.measure_id,
            "The persisted trace ends with the new immutable measure.",
        ),
        _check(
            "snapshot_cites_trace",
            snapshot.through_measure_id == measure.measure_id
            and snapshot.source_trace_hash == trace.trace_hash,
            "The composition snapshot is derived through the appended measure.",
        ),
        _check(
            "manifest_complete",
            manifest.run_id == run_id and manifest.status == "completed",
            "RunManifest is terminal and identifies this run.",
        ),
        _check(
            "native_provider_outputs_are_conclusions_only",
            all(
                bundle.bundle_id not in call.output_artifact_ids
                for call in manifest.provider_calls
            ),
            "No provider call claims ownership of deterministic bundle assembly.",
        ),
    )
    base = {
        "schema_version": "rei-native-invariant-report-v1",
        "run_id": run_id,
        "checks": checks,
        "all_passed": all(item.status == "passed" for item in checks),
    }
    report_id = content_id("invariant_report", base)
    payload = {"report_id": report_id, **base}
    report = InvariantReport(**payload, report_hash=sha256_hex(payload))
    if not report.all_passed:
        failed = ", ".join(
            item.check_id for item in report.checks if item.status == "failed"
        )
        raise ValueError(f"Native cycle invariant gate failed: {failed}")
    return report


__all__ = ["InvariantCheck", "InvariantReport", "build_cycle_invariant_report"]
