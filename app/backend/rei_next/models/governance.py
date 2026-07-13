"""Immutable ordinal-governance records.

The B3 resolution, delegation, and negotiation policies live in
``app.backend.rei_next.governance``.  This module contains only strict data and
content-lineage contracts.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from .character import CharacterProfileId
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    MindId,
    NonEmptyId,
    NonEmptyText,
)


PairConflictStatus = Literal["resolved", "unresolved"]
GovernanceStatus = Literal[
    "resolved",
    "unresolved",
    "delegated",
    "functionally_overridden",
]
AgreementKind = Literal["unanimous", "majority", "all_different", "incomplete"]
SpoznanjeStatus = Literal[
    "simulated_spoznanje",
    "partial_agreement",
    "no_spoznanje",
    "unknown",
]

_MIND_ORDER: tuple[MindId, ...] = ("R", "E", "I")


def _canonical_minds(minds: tuple[MindId, ...]) -> tuple[MindId, ...]:
    mind_set = set(minds)
    return tuple(mind for mind in _MIND_ORDER if mind in mind_set)


class MindOption(FrozenModel):
    """Deterministically serializable non-null option keyed by a mind."""

    mind: MindId
    option_id: NonEmptyId


class MindConclusionPosition(FrozenModel):
    """One native conclusion's equality-relevant position."""

    mind: MindId
    conclusion_id: NonEmptyId
    option_id: NonEmptyId | None
    abstains: bool = False

    @model_validator(mode="after")
    def validate_abstention(self) -> Self:
        if self.abstains and self.option_id is not None:
            raise ValueError("An abstaining mind cannot cast an option vote")
        return self


class MindStatement(FrozenModel):
    """Deterministically serializable statement keyed by a mind."""

    mind: MindId
    statement: str


class AgreementPattern(FrozenArtifactModel):
    """Profile-independent equality pattern of the three frozen conclusions."""

    schema_version: Literal["rei-native-agreement-pattern-v1"] = (
        "rei-native-agreement-pattern-v1"
    )
    agreement_pattern_id: NonEmptyId
    native_bundle_id: NonEmptyId
    native_bundle_hash: HashDigest
    positions: tuple[
        MindConclusionPosition,
        MindConclusionPosition,
        MindConclusionPosition,
    ]
    agreement_kind: AgreementKind
    spoznanje_status: SpoznanjeStatus
    winning_option_id: NonEmptyId | None = None
    agreeing_minds: tuple[MindId, ...] = ()
    agreement_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        native_bundle_id: NonEmptyId,
        native_bundle_hash: HashDigest,
        positions: tuple[
            MindConclusionPosition,
            MindConclusionPosition,
            MindConclusionPosition,
        ],
        agreement_kind: AgreementKind,
        spoznanje_status: SpoznanjeStatus,
        winning_option_id: NonEmptyId | None = None,
        agreeing_minds: tuple[MindId, ...] = (),
    ) -> AgreementPattern:
        base = {
            "schema_version": "rei-native-agreement-pattern-v1",
            "native_bundle_id": native_bundle_id,
            "native_bundle_hash": native_bundle_hash,
            "positions": positions,
            "agreement_kind": agreement_kind,
            "spoznanje_status": spoznanje_status,
            "winning_option_id": winning_option_id,
            "agreeing_minds": agreeing_minds,
        }
        agreement_pattern_id = content_id("agreement", base)
        payload = {"agreement_pattern_id": agreement_pattern_id, **base}
        return cls(**payload, agreement_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_pattern(self) -> Self:
        minds = tuple(position.mind for position in self.positions)
        if minds != _MIND_ORDER:
            raise ValueError("Agreement positions must use canonical R, E, I order")
        if len(set(self.agreeing_minds)) != len(self.agreeing_minds):
            raise ValueError("agreeing_minds must be unique")
        if self.agreeing_minds != _canonical_minds(self.agreeing_minds):
            raise ValueError("agreeing_minds must use canonical R, E, I order")

        options = tuple(position.option_id for position in self.positions)
        incomplete = any(
            position.abstains or position.option_id is None
            for position in self.positions
        )
        if self.agreement_kind == "incomplete":
            if not incomplete:
                raise ValueError("An incomplete agreement requires a missing option")
            if (
                self.spoznanje_status != "unknown"
                or self.winning_option_id is not None
                or self.agreeing_minds
            ):
                raise ValueError("Incomplete agreement must remain unknown and vote-free")
        elif incomplete:
            raise ValueError("A missing or abstaining position must be incomplete")
        elif self.agreement_kind == "unanimous":
            if (
                self.spoznanje_status != "simulated_spoznanje"
                or self.winning_option_id is None
                or self.agreeing_minds != _MIND_ORDER
                or set(options) != {self.winning_option_id}
            ):
                raise ValueError("Unanimous agreement requires three equal non-null options")
        elif self.agreement_kind == "majority":
            if (
                self.spoznanje_status != "partial_agreement"
                or self.winning_option_id is None
                or len(self.agreeing_minds) != 2
            ):
                raise ValueError("Majority agreement requires two supporting minds")
            supporting = tuple(
                position.mind
                for position in self.positions
                if position.option_id == self.winning_option_id
            )
            if supporting != self.agreeing_minds:
                raise ValueError("agreeing_minds must identify the exact option majority")
        elif (
            self.spoznanje_status != "no_spoznanje"
            or self.winning_option_id is not None
            or self.agreeing_minds
            or len(set(options)) != 3
        ):
            raise ValueError("All-different agreement must contain three distinct options")

        base = {
            "schema_version": self.schema_version,
            "native_bundle_id": self.native_bundle_id,
            "native_bundle_hash": self.native_bundle_hash,
            "positions": self.positions,
            "agreement_kind": self.agreement_kind,
            "spoznanje_status": self.spoznanje_status,
            "winning_option_id": self.winning_option_id,
            "agreeing_minds": self.agreeing_minds,
        }
        if self.agreement_pattern_id != content_id("agreement", base):
            raise ValueError("agreement_pattern_id does not match canonical content")
        payload = {"agreement_pattern_id": self.agreement_pattern_id, **base}
        if self.agreement_hash != sha256_hex(payload):
            raise ValueError("agreement_hash does not match canonical content")
        return self


class PairNegotiationRound(FrozenArtifactModel):
    """One bounded pair round backed by genuinely new information or rollout."""

    schema_version: Literal["rei-native-pair-negotiation-round-v1"] = (
        "rei-native-pair-negotiation-round-v1"
    )
    round_id: NonEmptyId
    round_number: int = Field(ge=1, le=2)
    top_minds: tuple[MindId, MindId]
    option_by_mind: tuple[MindOption, MindOption]
    new_information_ids: tuple[NonEmptyId, ...] = ()
    new_rollout_ids: tuple[NonEmptyId, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        round_number: int,
        top_minds: tuple[MindId, MindId],
        option_by_mind: tuple[MindOption, MindOption],
        new_information_ids: tuple[NonEmptyId, ...] = (),
        new_rollout_ids: tuple[NonEmptyId, ...] = (),
    ) -> PairNegotiationRound:
        base = {
            "schema_version": "rei-native-pair-negotiation-round-v1",
            "round_number": round_number,
            "top_minds": top_minds,
            "option_by_mind": option_by_mind,
            "new_information_ids": new_information_ids,
            "new_rollout_ids": new_rollout_ids,
        }
        return cls(round_id=content_id("pair_round", base), **base)

    @model_validator(mode="after")
    def validate_round(self) -> Self:
        if len(set(self.top_minds)) != 2:
            raise ValueError("top_minds must contain two distinct minds")
        if self.top_minds != _canonical_minds(self.top_minds):
            raise ValueError("top_minds must use canonical R, E, I order")
        if tuple(entry.mind for entry in self.option_by_mind) != self.top_minds:
            raise ValueError("option_by_mind must follow top_minds order")
        if not self.new_information_ids and not self.new_rollout_ids:
            raise ValueError("Each negotiation round requires new information or rollout")
        evidence_ids = self.new_information_ids + self.new_rollout_ids
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Negotiation provenance IDs must be unique within a round")
        return self


class PairConflict(FrozenArtifactModel):
    """Recorded disagreement or resolution between two equal leading minds."""

    schema_version: Literal["rei-native-pair-conflict-v1"] = (
        "rei-native-pair-conflict-v1"
    )
    pair_conflict_id: NonEmptyId
    top_minds: tuple[MindId, MindId]
    option_by_mind: tuple[MindOption, MindOption]
    status: PairConflictStatus
    initial_option_by_mind: tuple[MindOption, MindOption] | None = None
    negotiation_rounds: int = Field(default=0, ge=0, le=2)
    negotiation_history: tuple[PairNegotiationRound, ...] = ()

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        if len(set(self.top_minds)) != 2:
            raise ValueError("top_minds must contain two distinct minds")
        if self.top_minds != _canonical_minds(self.top_minds):
            raise ValueError("top_minds must use canonical R, E, I order")
        option_minds = tuple(entry.mind for entry in self.option_by_mind)
        if option_minds != self.top_minds:
            raise ValueError("option_by_mind must follow the canonical top_minds order")
        if self.initial_option_by_mind is not None and tuple(
            entry.mind for entry in self.initial_option_by_mind
        ) != self.top_minds:
            raise ValueError("initial_option_by_mind must follow top_minds order")
        if self.negotiation_history and self.initial_option_by_mind is None:
            raise ValueError("Negotiated pair conflict must preserve its initial options")
        if self.negotiation_rounds != len(self.negotiation_history):
            raise ValueError("negotiation_rounds must equal the proven round history")
        expected_rounds = tuple(range(1, len(self.negotiation_history) + 1))
        if tuple(item.round_number for item in self.negotiation_history) != expected_rounds:
            raise ValueError("Negotiation round numbers must be contiguous from one")
        if any(item.top_minds != self.top_minds for item in self.negotiation_history):
            raise ValueError("Every negotiation round must retain the same top pair")
        if (
            self.negotiation_history
            and self.negotiation_history[-1].option_by_mind != self.option_by_mind
        ):
            raise ValueError("PairConflict options must equal the final negotiation round")
        if self.negotiation_history:
            current_options = self.initial_option_by_mind
            if current_options is None:  # guarded above; narrows the model type
                raise ValueError("Negotiated pair conflict requires initial options")
            for round_record in self.negotiation_history:
                if len({entry.option_id for entry in current_options}) == 1:
                    raise ValueError("Negotiation must stop once the top pair agrees")
                current_options = round_record.option_by_mind
        provenance_ids = tuple(
            artifact_id
            for item in self.negotiation_history
            for artifact_id in item.new_information_ids + item.new_rollout_ids
        )
        if len(set(provenance_ids)) != len(provenance_ids):
            raise ValueError("Every negotiation round must add new provenance")
        options_agree = len({entry.option_id for entry in self.option_by_mind}) == 1
        if options_agree and self.status != "resolved":
            raise ValueError("An agreeing top pair must be resolved")
        if not options_agree and self.status != "unresolved":
            raise ValueError("A disagreeing top pair must remain unresolved")
        return self


class TaskDelegation(FrozenArtifactModel):
    """An explicit operational delegation that cannot mutate authority tiers."""

    schema_version: Literal["rei-native-task-delegation-v1"] = (
        "rei-native-task-delegation-v1"
    )
    delegation_id: NonEmptyId
    delegating_minds: tuple[MindId, ...]
    delegate_mind: MindId
    task: NonEmptyText
    option_id: NonEmptyId | None = None
    rationale: str = ""
    preserves_structural_authority: Literal[True] = True

    @model_validator(mode="after")
    def validate_delegators(self) -> Self:
        if not self.delegating_minds:
            raise ValueError("delegating_minds must not be empty")
        if len(set(self.delegating_minds)) != len(self.delegating_minds):
            raise ValueError("delegating_minds must be unique")
        if self.delegating_minds != _canonical_minds(self.delegating_minds):
            raise ValueError("delegating_minds must use canonical R, E, I order")
        if self.delegate_mind in self.delegating_minds:
            raise ValueError("A delegation must target another mind")
        return self


class GovernanceMandate(FrozenArtifactModel):
    """Structural governance result, distinct from any conscious decision."""

    schema_version: Literal["rei-native-governance-mandate-v1"] = (
        "rei-native-governance-mandate-v1"
    )
    mandate_id: NonEmptyId
    status: GovernanceStatus
    structural_source_minds: tuple[MindId, ...]
    option_id: NonEmptyId | None = None
    objections: tuple[MindStatement, ...] = ()
    delegation: TaskDelegation | None = None
    # Diagnostic trace only; never ground-truth input to RacioInterpreter.
    hidden_native_motives: tuple[MindStatement, ...] = ()

    @model_validator(mode="after")
    def validate_mind_entries(self) -> Self:
        if not self.structural_source_minds:
            raise ValueError("structural_source_minds must not be empty")
        if len(set(self.structural_source_minds)) != len(self.structural_source_minds):
            raise ValueError("structural_source_minds must be unique")
        if self.structural_source_minds != _canonical_minds(
            self.structural_source_minds
        ):
            raise ValueError(
                "structural_source_minds must use canonical R, E, I order"
            )
        for name, entries in (
            ("objections", self.objections),
            ("hidden_native_motives", self.hidden_native_motives),
        ):
            minds = tuple(entry.mind for entry in entries)
            if len(set(minds)) != len(minds):
                raise ValueError(f"{name} may contain at most one entry per mind")
            if minds != _canonical_minds(minds):
                raise ValueError(f"{name} must use canonical R, E, I order")
        if self.status == "delegated" and self.delegation is None:
            raise ValueError("delegated mandate requires a delegation record")
        if self.status != "delegated" and self.delegation is not None:
            raise ValueError("delegation is only valid for a delegated mandate")
        if self.status == "unresolved" and self.option_id is not None:
            raise ValueError("unresolved mandate cannot select an option")
        if self.status in {"resolved", "functionally_overridden"} and self.option_id is None:
            raise ValueError("resolved mandate status requires an option")
        if (
            self.delegation is not None
            and self.delegation.option_id is not None
            and self.option_id != self.delegation.option_id
        ):
            raise ValueError("Delegation option must match the governance mandate")
        return self


class GovernanceResolution(FrozenArtifactModel):
    """Content-addressed B3 result with complete input lineage."""

    schema_version: Literal["rei-native-governance-resolution-v1"] = (
        "rei-native-governance-resolution-v1"
    )
    resolution_id: NonEmptyId
    native_bundle_id: NonEmptyId
    native_bundle_hash: HashDigest
    character_id: NonEmptyId
    character_hash: HashDigest
    profile_id: CharacterProfileId
    effective_authority_id: NonEmptyId
    effective_authority_hash: HashDigest
    structural_top_minds: tuple[MindId, ...]
    effective_source_minds: tuple[MindId, ...]
    agreement_pattern: AgreementPattern
    mandate: GovernanceMandate
    pair_conflict: PairConflict | None = None
    resolution_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        native_bundle_id: NonEmptyId,
        native_bundle_hash: HashDigest,
        character_id: NonEmptyId,
        character_hash: HashDigest,
        profile_id: CharacterProfileId,
        effective_authority_id: NonEmptyId,
        effective_authority_hash: HashDigest,
        structural_top_minds: tuple[MindId, ...],
        effective_source_minds: tuple[MindId, ...],
        agreement_pattern: AgreementPattern,
        mandate: GovernanceMandate,
        pair_conflict: PairConflict | None = None,
    ) -> GovernanceResolution:
        base = {
            "schema_version": "rei-native-governance-resolution-v1",
            "native_bundle_id": native_bundle_id,
            "native_bundle_hash": native_bundle_hash,
            "character_id": character_id,
            "character_hash": character_hash,
            "profile_id": profile_id,
            "effective_authority_id": effective_authority_id,
            "effective_authority_hash": effective_authority_hash,
            "structural_top_minds": structural_top_minds,
            "effective_source_minds": effective_source_minds,
            "agreement_pattern": agreement_pattern,
            "mandate": mandate,
            "pair_conflict": pair_conflict,
        }
        resolution_id = content_id("governance", base)
        payload = {"resolution_id": resolution_id, **base}
        return cls(**payload, resolution_hash=sha256_hex(payload))

    @property
    def spoznanje_status(self) -> SpoznanjeStatus:
        return self.agreement_pattern.spoznanje_status

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        for name, minds in (
            ("structural_top_minds", self.structural_top_minds),
            ("effective_source_minds", self.effective_source_minds),
        ):
            if not minds or len(set(minds)) != len(minds):
                raise ValueError(f"{name} must contain unique mind IDs")
            if minds != _canonical_minds(minds):
                raise ValueError(f"{name} must use canonical R, E, I order")
        if self.mandate.structural_source_minds != self.effective_source_minds:
            raise ValueError(
                "Mandate sources must equal the resolution's effective sources"
            )
        if (
            self.agreement_pattern.native_bundle_id != self.native_bundle_id
            or self.agreement_pattern.native_bundle_hash != self.native_bundle_hash
        ):
            raise ValueError("Agreement pattern must cite the resolved native bundle")
        if self.pair_conflict is not None:
            if self.pair_conflict.top_minds != self.effective_source_minds:
                raise ValueError(
                    "PairConflict top minds must equal the effective mandate sources"
                )
            if (
                self.pair_conflict.status == "resolved"
                and self.pair_conflict.option_by_mind[0].option_id
                != self.mandate.option_id
            ):
                raise ValueError(
                    "Resolved PairConflict option must equal the mandate option"
                )
        if (
            self.pair_conflict is not None
            and self.pair_conflict.status == "unresolved"
            and self.mandate.status not in {"unresolved", "delegated"}
        ):
            raise ValueError("An unresolved pair may only remain unresolved or delegate")
        base = {
            "schema_version": self.schema_version,
            "native_bundle_id": self.native_bundle_id,
            "native_bundle_hash": self.native_bundle_hash,
            "character_id": self.character_id,
            "character_hash": self.character_hash,
            "profile_id": self.profile_id,
            "effective_authority_id": self.effective_authority_id,
            "effective_authority_hash": self.effective_authority_hash,
            "structural_top_minds": self.structural_top_minds,
            "effective_source_minds": self.effective_source_minds,
            "agreement_pattern": self.agreement_pattern,
            "mandate": self.mandate,
            "pair_conflict": self.pair_conflict,
        }
        if self.resolution_id != content_id("governance", base):
            raise ValueError("resolution_id does not match canonical content")
        payload = {"resolution_id": self.resolution_id, **base}
        if self.resolution_hash != sha256_hex(payload):
            raise ValueError("resolution_hash does not match canonical content")
        return self


__all__ = [
    "AgreementKind",
    "AgreementPattern",
    "GovernanceMandate",
    "GovernanceResolution",
    "GovernanceStatus",
    "MindConclusionPosition",
    "MindOption",
    "MindStatement",
    "PairConflict",
    "PairConflictStatus",
    "PairNegotiationRound",
    "SpoznanjeStatus",
    "TaskDelegation",
]
