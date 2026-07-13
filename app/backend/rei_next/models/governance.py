"""Ordinal governance records.

This module intentionally contains no resolver, weighting, tie-breaking, or
negotiation algorithm.  It only defines immutable inputs and outputs for those
later B3 policies.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from .common import FrozenArtifactModel, FrozenModel, MindId, NonEmptyId


PairConflictStatus = Literal["resolved", "unresolved"]
GovernanceStatus = Literal[
    "resolved",
    "unresolved",
    "delegated",
    "functionally_overridden",
]


class MindOption(FrozenModel):
    """Deterministically serializable option entry keyed by a mind."""

    mind: MindId
    option_id: NonEmptyId


class MindStatement(FrozenModel):
    """Deterministically serializable statement entry keyed by a mind."""

    mind: MindId
    statement: str


class PairConflict(FrozenArtifactModel):
    """Recorded disagreement or resolution between two equal leading minds."""

    schema_version: Literal["rei-native-pair-conflict-v1"] = (
        "rei-native-pair-conflict-v1"
    )
    pair_conflict_id: NonEmptyId
    top_minds: tuple[MindId, MindId]
    option_by_mind: tuple[MindOption, MindOption]
    status: PairConflictStatus
    negotiation_rounds: int = Field(default=0, ge=0, le=2)

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        if len(set(self.top_minds)) != 2:
            raise ValueError("top_minds must contain two distinct minds")
        option_minds = tuple(entry.mind for entry in self.option_by_mind)
        if option_minds != self.top_minds:
            raise ValueError("option_by_mind must follow the canonical top_minds order")
        options_agree = len({entry.option_id for entry in self.option_by_mind}) == 1
        if options_agree and self.status != "resolved":
            raise ValueError("An agreeing top pair must be resolved")
        if not options_agree and self.status != "unresolved":
            raise ValueError("A disagreeing top pair must remain unresolved")
        return self


class TaskDelegation(FrozenArtifactModel):
    """An operational delegation that does not mutate structural authority."""

    schema_version: Literal["rei-native-task-delegation-v1"] = (
        "rei-native-task-delegation-v1"
    )
    delegation_id: NonEmptyId
    delegating_minds: tuple[MindId, ...]
    delegate_mind: MindId
    task: str
    option_id: NonEmptyId | None = None
    rationale: str = ""
    preserves_structural_authority: Literal[True] = True

    @model_validator(mode="after")
    def validate_delegators(self) -> Self:
        if not self.delegating_minds:
            raise ValueError("delegating_minds must not be empty")
        if len(set(self.delegating_minds)) != len(self.delegating_minds):
            raise ValueError("delegating_minds must be unique")
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
        for name, entries in (
            ("objections", self.objections),
            ("hidden_native_motives", self.hidden_native_motives),
        ):
            minds = tuple(entry.mind for entry in entries)
            if len(set(minds)) != len(minds):
                raise ValueError(f"{name} may contain at most one entry per mind")
            canonical_minds = tuple(
                mind for mind in ("R", "E", "I") if mind in set(minds)
            )
            if minds != canonical_minds:
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


__all__ = [
    "GovernanceMandate",
    "GovernanceStatus",
    "MindOption",
    "MindStatement",
    "PairConflict",
    "PairConflictStatus",
    "TaskDelegation",
]
