"""B11 counterfactual matrix over frozen native bundles and 13 characters."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from .communication.interpreter import DeterministicRacioInterpreter
from .communication.manifestations import build_emocio_manifestation
from .communication.processor import interpret_manifestations
from .conscious.committer import DeterministicRacioCommitter
from .governance.behavior import DeterministicBehaviorResolver
from .governance.fixtures import load_governance_fixture
from .governance.profiles import derive_effective_authority, parse_character_profile
from .governance.resolver import resolve_governance
from .ids import content_id, sha256_hex
from .instinkt.manifestation import build_instinkt_fixture_projection
from .models.character import CHARACTER_PROFILE_ORDER, CharacterProfileId
from .models.common import FrozenArtifactModel, FrozenModel, HashDigest, NonEmptyId
from .models.communication import (
    AcceptanceMode,
    AcceptanceState,
    DirectedMindRelation,
)
from .models.conscious import (
    AlignmentStatus,
    BehaviorResultant,
    BehaviorStatus,
    ConsciousDecision,
    ConsciousDecisionStatus,
    ConsciousInterpretationInput,
    ConsciousMandateView,
)
from .models.governance import (
    GovernanceResolution,
    GovernanceStatus,
    PairConflictStatus,
    SpoznanjeStatus,
)


class NativeProfileMatrixRow(FrozenArtifactModel):
    schema_version: Literal["rei-native-profile-matrix-row-v1"] = (
        "rei-native-profile-matrix-row-v1"
    )
    row_id: NonEmptyId
    fixture_id: NonEmptyId
    profile_id: CharacterProfileId
    native_bundle_id: NonEmptyId
    native_bundle_hash: HashDigest
    governance_resolution_id: NonEmptyId
    governance_resolution_hash: HashDigest
    governance_status: GovernanceStatus
    governance_option_id: NonEmptyId | None
    governance_source_minds: tuple[Literal["R", "E", "I"], ...]
    governance_pair_status: PairConflictStatus | None
    expected_governance_matched: Literal[True] = True
    spoznanje_status: SpoznanjeStatus
    conscious_decision_id: NonEmptyId
    conscious_option_id: NonEmptyId | None
    conscious_status: ConsciousDecisionStatus
    expected_conscious_option_id: NonEmptyId | None
    expected_conscious_status: ConsciousDecisionStatus
    behavior_resultant_id: NonEmptyId
    behavior_option_id: NonEmptyId | None
    behavior_status: BehaviorStatus
    expected_behavior_option_id: NonEmptyId | None
    expected_behavior_status: BehaviorStatus
    governance_alignment: AlignmentStatus
    conscious_alignment: AlignmentStatus
    expected_governance_alignment: AlignmentStatus
    expected_conscious_alignment: AlignmentStatus
    expected_b10_matched: Literal[True] = True
    acceptance_state_id: NonEmptyId
    acceptance_state_hash: HashDigest
    row_hash: HashDigest

    @model_validator(mode="after")
    def validate_row(self) -> Self:
        if (
            self.conscious_option_id != self.expected_conscious_option_id
            or self.conscious_status != self.expected_conscious_status
            or self.behavior_option_id != self.expected_behavior_option_id
            or self.behavior_status != self.expected_behavior_status
            or self.governance_alignment != self.expected_governance_alignment
            or self.conscious_alignment != self.expected_conscious_alignment
        ):
            raise ValueError("Profile matrix row differs from its independent B10 oracle")
        base = self.model_dump(
            mode="python", round_trip=True, exclude={"row_id", "row_hash"}
        )
        if self.row_id != content_id("profile_matrix_row", base):
            raise ValueError("Profile matrix row ID differs from canonical content")
        payload = {"row_id": self.row_id, **base}
        if self.row_hash != sha256_hex(payload):
            raise ValueError("Profile matrix row hash differs from canonical content")
        return self


class NativeProfileMatrixCoverage(FrozenModel):
    """Explicit causal coverage proved by the canonical 12x13 matrix."""

    b10_oracle_rows: int = Field(ge=156, le=156)
    mandate_conscious_option_divergence_rows: int = Field(ge=1)
    conscious_behavior_state_divergence_rows: int = Field(ge=1)
    pair_conflict_rows: int = Field(ge=1)
    thirteenth_majority_rows: int = Field(ge=1)
    simulated_spoznanje_rows: int = Field(ge=1)


class NativeProfileMatrix(FrozenArtifactModel):
    schema_version: Literal["rei-native-profile-matrix-v1"] = (
        "rei-native-profile-matrix-v1"
    )
    matrix_id: NonEmptyId
    mode: Literal["controlled_profile_matrix"] = "controlled_profile_matrix"
    fixture_directory: str
    fixture_ids: tuple[NonEmptyId, ...] = Field(min_length=12, max_length=12)
    profile_order: tuple[CharacterProfileId, ...]
    acceptance_state: AcceptanceState
    rows: tuple[NativeProfileMatrixRow, ...] = Field(min_length=156, max_length=156)
    coverage: NativeProfileMatrixCoverage
    native_processor_executions: Literal[0] = 0
    matrix_hash: HashDigest

    @model_validator(mode="after")
    def validate_matrix(self) -> Self:
        if len(set(self.fixture_ids)) != len(self.fixture_ids):
            raise ValueError("Profile matrix fixture IDs must be unique")
        if self.profile_order != CHARACTER_PROFILE_ORDER:
            raise ValueError("Profile matrix must preserve canonical 13-profile order")
        expected_pairs = tuple(
            (fixture_id, profile_id)
            for fixture_id in self.fixture_ids
            for profile_id in self.profile_order
        )
        actual_pairs = tuple((row.fixture_id, row.profile_id) for row in self.rows)
        if actual_pairs != expected_pairs:
            raise ValueError("Profile matrix rows are incomplete or out of order")
        for fixture_id in self.fixture_ids:
            bundle_refs = {
                (row.native_bundle_id, row.native_bundle_hash)
                for row in self.rows
                if row.fixture_id == fixture_id
            }
            if len(bundle_refs) != 1:
                raise ValueError(
                    "Every profile for one fixture must evaluate the same frozen bundle"
                )
        if any(
            row.acceptance_state_id != self.acceptance_state.acceptance_state_id
            or row.acceptance_state_hash != self.acceptance_state.content_hash()
            for row in self.rows
        ):
            raise ValueError("Profile matrix rows must share one AcceptanceState")
        expected_coverage = _matrix_coverage(self.rows, self.profile_order[-1])
        if self.coverage != expected_coverage:
            raise ValueError("Profile matrix causal coverage differs from its rows")
        base = self.model_dump(
            mode="python", round_trip=True, exclude={"matrix_id", "matrix_hash"}
        )
        if self.matrix_id != content_id("profile_matrix", base):
            raise ValueError("Profile matrix ID differs from canonical content")
        payload = {"matrix_id": self.matrix_id, **base}
        if self.matrix_hash != sha256_hex(payload):
            raise ValueError("Profile matrix hash differs from canonical content")
        return self


def build_matrix_acceptance_state(
    mode: AcceptanceMode = "conflicted",
) -> AcceptanceState:
    relation = DirectedMindRelation(
        visibility=0.5,
        interpretation_fidelity=0.5,
        tolerance=0.5,
        delegation_willingness=0.5,
        sabotage_risk=0.5,
    )
    base = {
        "R_to_E": relation,
        "R_to_I": relation,
        "E_to_R": relation,
        "E_to_I": relation,
        "I_to_R": relation,
        "I_to_E": relation,
        "overall_mode": mode,
    }
    return AcceptanceState(
        acceptance_state_id=content_id("matrix_acceptance", base),
        **base,
    )


class _ExpectedB10Outcome(FrozenModel):
    conscious_option_id: NonEmptyId | None
    conscious_status: ConsciousDecisionStatus
    behavior_option_id: NonEmptyId | None
    behavior_status: BehaviorStatus
    governance_alignment: AlignmentStatus
    conscious_alignment: AlignmentStatus


def _option_alignment(
    option_id: str | None,
    target_option_id: str | None,
) -> AlignmentStatus:
    if option_id is None or target_option_id is None:
        return "not_applicable"
    return "aligned" if option_id == target_option_id else "diverged"


def _expected_b10_outcome(
    *,
    governance: GovernanceResolution,
    racio_option_id: str | None,
    racio_abstains: bool,
    acceptance_state: AcceptanceState,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> _ExpectedB10Outcome:
    """Independent table oracle; it does not call the B10 implementation."""

    mandate_option = governance.mandate.option_id
    actionable = (
        governance.mandate.status
        in {"resolved", "delegated", "functionally_overridden"}
        and mandate_option is not None
    )
    racio_available = not racio_abstains and racio_option_id is not None
    mode = acceptance_state.overall_mode

    if mode == "unknown" or not actionable:
        conscious_option = None
        conscious_status: ConsciousDecisionStatus = "deferred"
        behavior_option = None
        behavior_status: BehaviorStatus = "unresolved"
    elif mode == "accepting":
        conscious_option = mandate_option
        conscious_status = "committed"
        behavior_option = mandate_option
        behavior_status = "executed"
    elif mode == "mixed":
        structural_sources = set(governance.effective_source_minds)
        recognized = "R" in structural_sources or any(
            item.interpretation.source_mind in structural_sources
            and item.interpretation.interpretation_status != "unverified_contract"
            and item.interpretation.inferred_option_id == mandate_option
            for item in interpretation_inputs
        )
        if recognized:
            conscious_option = mandate_option
            conscious_status = "committed"
            behavior_option = mandate_option
            behavior_status = "executed"
        elif racio_available:
            conscious_option = racio_option_id
            conscious_status = "committed"
            behavior_option = racio_option_id
            behavior_status = "oscillating"
        else:
            conscious_option = None
            conscious_status = "deferred"
            behavior_option = None
            behavior_status = "delayed"
    elif racio_available:
        conscious_option = racio_option_id
        conscious_status = "committed"
        behavior_option = racio_option_id
        behavior_status = "sabotaged"
    else:
        conscious_option = None
        conscious_status = "blocked"
        behavior_option = None
        behavior_status = "blocked"

    return _ExpectedB10Outcome(
        conscious_option_id=conscious_option,
        conscious_status=conscious_status,
        behavior_option_id=behavior_option,
        behavior_status=behavior_status,
        governance_alignment=_option_alignment(behavior_option, mandate_option),
        conscious_alignment=_option_alignment(behavior_option, conscious_option),
    )


def _matrix_coverage(
    rows: tuple[NativeProfileMatrixRow, ...],
    thirteenth_profile: CharacterProfileId,
) -> NativeProfileMatrixCoverage:
    return NativeProfileMatrixCoverage(
        b10_oracle_rows=sum(item.expected_b10_matched for item in rows),
        mandate_conscious_option_divergence_rows=sum(
            item.expected_governance_alignment == "diverged" for item in rows
        ),
        conscious_behavior_state_divergence_rows=sum(
            item.expected_conscious_status == "committed"
            and item.expected_behavior_status != "executed"
            for item in rows
        ),
        pair_conflict_rows=sum(item.governance_pair_status is not None for item in rows),
        thirteenth_majority_rows=sum(
            item.profile_id == thirteenth_profile
            and item.governance_status == "resolved"
            and len(item.governance_source_minds) == 2
            for item in rows
        ),
        simulated_spoznanje_rows=sum(
            item.spoznanje_status == "simulated_spoznanje" for item in rows
        ),
    )


def _row(
    *,
    fixture_id: str,
    profile_id: CharacterProfileId,
    bundle_id: str,
    bundle_hash: str,
    governance: GovernanceResolution,
    decision: ConsciousDecision,
    behavior: BehaviorResultant,
    expected_b10: _ExpectedB10Outcome,
    acceptance_state: AcceptanceState,
) -> NativeProfileMatrixRow:
    base = {
        "schema_version": "rei-native-profile-matrix-row-v1",
        "fixture_id": fixture_id,
        "profile_id": profile_id,
        "native_bundle_id": bundle_id,
        "native_bundle_hash": bundle_hash,
        "governance_resolution_id": governance.resolution_id,
        "governance_resolution_hash": governance.content_hash(),
        "governance_status": governance.mandate.status,
        "governance_option_id": governance.mandate.option_id,
        "governance_source_minds": governance.effective_source_minds,
        "governance_pair_status": (
            governance.pair_conflict.status
            if governance.pair_conflict is not None
            else None
        ),
        "expected_governance_matched": True,
        "spoznanje_status": governance.spoznanje_status,
        "conscious_decision_id": decision.decision_id,
        "conscious_option_id": decision.option_id,
        "conscious_status": decision.decision_status,
        "expected_conscious_option_id": expected_b10.conscious_option_id,
        "expected_conscious_status": expected_b10.conscious_status,
        "behavior_resultant_id": behavior.resultant_id,
        "behavior_option_id": behavior.option_id,
        "behavior_status": behavior.status,
        "expected_behavior_option_id": expected_b10.behavior_option_id,
        "expected_behavior_status": expected_b10.behavior_status,
        "governance_alignment": behavior.governance_alignment,
        "conscious_alignment": behavior.conscious_alignment,
        "expected_governance_alignment": expected_b10.governance_alignment,
        "expected_conscious_alignment": expected_b10.conscious_alignment,
        "expected_b10_matched": True,
        "acceptance_state_id": acceptance_state.acceptance_state_id,
        "acceptance_state_hash": acceptance_state.content_hash(),
    }
    row_id = content_id("profile_matrix_row", base)
    payload = {"row_id": row_id, **base}
    return NativeProfileMatrixRow(**payload, row_hash=sha256_hex(payload))


def run_native_profile_matrix(
    fixture_directory: str | Path,
    *,
    acceptance_state: AcceptanceState | None = None,
) -> NativeProfileMatrix:
    """Evaluate governance/B10 only; native processors are never imported or run."""

    fixture_root = Path(fixture_directory).expanduser().resolve()
    fixture_paths = tuple(sorted(fixture_root.glob("*.json")))
    if len(fixture_paths) != 12:
        raise ValueError(
            "Native profile matrix requires exactly 12 frozen fixture files"
        )
    fixtures = tuple(load_governance_fixture(path) for path in fixture_paths)
    fixture_ids = tuple(item.fixture_id for item in fixtures)
    if len(set(fixture_ids)) != len(fixture_ids):
        raise ValueError("Native profile matrix fixture IDs must be unique")
    active_acceptance = acceptance_state or build_matrix_acceptance_state()
    interpreter = DeterministicRacioInterpreter()
    committer = DeterministicRacioCommitter()
    resolver = DeterministicBehaviorResolver()
    rows: list[NativeProfileMatrixRow] = []

    for fixture in fixtures:
        bundle = fixture.native_bundle
        emocio_manifestation = build_emocio_manifestation(conclusion=bundle.emocio)
        instinkt_manifestation = build_instinkt_fixture_projection(
            conclusion=bundle.instinkt,
            body_state=fixture.instinkt_body_state,
        )
        manifestations = (emocio_manifestation, instinkt_manifestation)
        interpreted_e = interpret_manifestations(
            manifestations=(emocio_manifestation,),
            allowed_option_ids=bundle.allowed_option_ids,
            acceptance_state=active_acceptance,
            interpreter=interpreter,
        )
        interpreted_i = interpret_manifestations(
            manifestations=(instinkt_manifestation,),
            allowed_option_ids=bundle.allowed_option_ids,
            acceptance_state=active_acceptance,
            interpreter=interpreter,
        )

        expected_by_profile = {
            item.profile_id: item for item in fixture.expected_profile_outcomes
        }
        for profile_id in CHARACTER_PROFILE_ORDER:
            character = parse_character_profile(profile_id)
            governance = resolve_governance(
                bundle,
                derive_effective_authority(character),
            )
            expected = expected_by_profile[profile_id]
            if (
                governance.mandate.status != expected.status
                or governance.mandate.option_id != expected.option_id
                or governance.effective_source_minds != expected.source_minds
                or (
                    governance.pair_conflict.status
                    if governance.pair_conflict is not None
                    else None
                )
                != expected.pair_status
                or governance.spoznanje_status != fixture.expected_spoznanje_status
            ):
                raise ValueError(
                    f"Governance matrix mismatch for {fixture.fixture_id}/{profile_id}"
                )
            mandate_view = ConsciousMandateView.create_b10(
                governance=governance,
                bundle=bundle,
                manifestations=manifestations,
            )
            interpretation_inputs = (
                ConsciousInterpretationInput.create_b10(
                    mandate_view=mandate_view,
                    request=interpreted_e.request,
                    interpretation=interpreted_e.interpretation,
                    acceptance_state=active_acceptance,
                ),
                ConsciousInterpretationInput.create_b10(
                    mandate_view=mandate_view,
                    request=interpreted_i.request,
                    interpretation=interpreted_i.interpretation,
                    acceptance_state=active_acceptance,
                ),
            )
            decision = committer.commit(
                mandate_view=mandate_view,
                racio_conclusion=bundle.racio,
                acceptance_state=active_acceptance,
                interpretation_inputs=interpretation_inputs,
            )
            behavior = resolver.resolve(
                mandate_view=mandate_view,
                decision=decision,
                acceptance_state=active_acceptance,
                racio_conclusion=bundle.racio,
                interpretation_inputs=interpretation_inputs,
            )
            expected_b10 = _expected_b10_outcome(
                governance=governance,
                racio_option_id=bundle.racio.option_id,
                racio_abstains=bundle.racio.abstains,
                acceptance_state=active_acceptance,
                interpretation_inputs=interpretation_inputs,
            )
            actual_b10 = _ExpectedB10Outcome(
                conscious_option_id=decision.option_id,
                conscious_status=decision.decision_status,
                behavior_option_id=behavior.option_id,
                behavior_status=behavior.status,
                governance_alignment=behavior.governance_alignment,
                conscious_alignment=behavior.conscious_alignment,
            )
            if actual_b10 != expected_b10:
                raise ValueError(
                    f"Independent B10 oracle mismatch for "
                    f"{fixture.fixture_id}/{profile_id}"
                )
            rows.append(
                _row(
                    fixture_id=fixture.fixture_id,
                    profile_id=profile_id,
                    bundle_id=bundle.bundle_id,
                    bundle_hash=bundle.immutable_hash,
                    governance=governance,
                    decision=decision,
                    behavior=behavior,
                    expected_b10=expected_b10,
                    acceptance_state=active_acceptance,
                )
            )

    canonical_rows = tuple(rows)
    base = {
        "schema_version": "rei-native-profile-matrix-v1",
        "mode": "controlled_profile_matrix",
        "fixture_directory": fixture_root.name,
        "fixture_ids": fixture_ids,
        "profile_order": CHARACTER_PROFILE_ORDER,
        "acceptance_state": active_acceptance,
        "rows": canonical_rows,
        "coverage": _matrix_coverage(
            canonical_rows,
            CHARACTER_PROFILE_ORDER[-1],
        ),
        "native_processor_executions": 0,
    }
    matrix_id = content_id("profile_matrix", base)
    payload = {"matrix_id": matrix_id, **base}
    return NativeProfileMatrix(**payload, matrix_hash=sha256_hex(payload))


__all__ = [
    "NativeProfileMatrix",
    "NativeProfileMatrixCoverage",
    "NativeProfileMatrixRow",
    "build_matrix_acceptance_state",
    "run_native_profile_matrix",
]
