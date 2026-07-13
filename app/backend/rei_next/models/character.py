"""Stable ordinal character and person-context contracts."""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import Field, model_validator

from .common import FrozenArtifactModel, FrozenModel, MindId, NonEmptyId, Score01
from .communication import AcceptanceState
from .emocio import EmocioWorld
from .instinkt import InstinktWorld
from .racio import RacioWorld


CharacterRule = Literal["single_top", "ordered_top", "joint_top", "two_of_three"]
CharacterProfileId = Literal[
    "R>(E=I)",
    "E>(R=I)",
    "I>(R=E)",
    "(R=E)>I",
    "(R=I)>E",
    "(E=I)>R",
    "R>E>I",
    "R>I>E",
    "E>R>I",
    "E>I>R",
    "I>R>E",
    "I>E>R",
    "R=E=I",
]
FunctionalOverrideReason = Literal["explicit_functional_unavailability"]

_PROFILE_CONTRACTS: Final[
    dict[CharacterProfileId, tuple[tuple[tuple[MindId, ...], ...], CharacterRule]]
] = {
    "R>(E=I)": ((('R',), ('E', 'I')), "single_top"),
    "E>(R=I)": ((('E',), ('R', 'I')), "single_top"),
    "I>(R=E)": ((('I',), ('R', 'E')), "single_top"),
    "(R=E)>I": ((('R', 'E'), ('I',)), "joint_top"),
    "(R=I)>E": ((('R', 'I'), ('E',)), "joint_top"),
    "(E=I)>R": ((('E', 'I'), ('R',)), "joint_top"),
    "R>E>I": ((('R',), ('E',), ('I',)), "ordered_top"),
    "R>I>E": ((('R',), ('I',), ('E',)), "ordered_top"),
    "E>R>I": ((('E',), ('R',), ('I',)), "ordered_top"),
    "E>I>R": ((('E',), ('I',), ('R',)), "ordered_top"),
    "I>R>E": ((('I',), ('R',), ('E',)), "ordered_top"),
    "I>E>R": ((('I',), ('E',), ('R',)), "ordered_top"),
    "R=E=I": ((('R', 'E', 'I'),), "two_of_three"),
}


class CharacterAuthority(FrozenArtifactModel):
    """A person's stable, ordinal authority profile."""

    schema_version: Literal["rei-native-character-authority-v1"] = (
        "rei-native-character-authority-v1"
    )
    character_id: NonEmptyId
    profile_id: CharacterProfileId
    authority_tiers: tuple[tuple[MindId, ...], ...]
    rule: CharacterRule

    @model_validator(mode="after")
    def validate_authority_tiers(self) -> Self:
        if not self.authority_tiers or any(not tier for tier in self.authority_tiers):
            raise ValueError("authority_tiers must contain non-empty tiers")
        minds = tuple(mind for tier in self.authority_tiers for mind in tier)
        if len(minds) != 3 or set(minds) != {"R", "E", "I"}:
            raise ValueError("authority_tiers must contain R, E, and I exactly once")
        expected_shapes = {
            "single_top": (1, 2),
            "ordered_top": (1, 1, 1),
            "joint_top": (2, 1),
            "two_of_three": (3,),
        }
        if tuple(len(tier) for tier in self.authority_tiers) != expected_shapes[self.rule]:
            raise ValueError("authority_tiers shape does not match the character rule")
        expected_tiers, expected_rule = _PROFILE_CONTRACTS[self.profile_id]
        if self.authority_tiers != expected_tiers or self.rule != expected_rule:
            raise ValueError("profile_id, authority_tiers, and rule must describe one profile")
        return self


class ProcessorAvailability(FrozenModel):
    """Functional availability, explicitly separate from structural character."""

    R: Score01 = 1.0
    E: Score01 = 1.0
    I: Score01 = 1.0


class FunctionalOverride(FrozenArtifactModel):
    """Explicit evidence that one or more processors are functionally unavailable."""

    schema_version: Literal["rei-native-functional-override-v1"] = (
        "rei-native-functional-override-v1"
    )
    functional_override_id: NonEmptyId
    reason: FunctionalOverrideReason = "explicit_functional_unavailability"
    unavailable_minds: tuple[MindId, ...] = Field(min_length=1)
    processor_availability: ProcessorAvailability
    evidence_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    note: str = ""

    @model_validator(mode="after")
    def validate_unavailable_minds(self) -> Self:
        if len(set(self.unavailable_minds)) != len(self.unavailable_minds):
            raise ValueError("unavailable_minds must be unique")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Functional override evidence IDs must be unique")
        return self


class EffectiveAuthority(FrozenArtifactModel):
    """A derived authority view for explicit functional unavailability only."""

    schema_version: Literal["rei-native-effective-authority-v1"] = (
        "rei-native-effective-authority-v1"
    )
    effective_authority_id: NonEmptyId
    structural_profile: CharacterAuthority
    effective_tiers: tuple[tuple[MindId, ...], ...]
    override_reason: FunctionalOverrideReason | None = None
    functional_override: FunctionalOverride | None = None

    @model_validator(mode="after")
    def validate_effective_tiers(self) -> Self:
        if any(not tier for tier in self.effective_tiers):
            raise ValueError("effective_tiers cannot contain an empty tier")
        minds = tuple(mind for tier in self.effective_tiers for mind in tier)
        if len(set(minds)) != len(minds):
            raise ValueError("a mind may appear in effective_tiers at most once")
        retained_minds = set(minds)
        expected_projection = tuple(
            retained
            for tier in self.structural_profile.authority_tiers
            if (retained := tuple(mind for mind in tier if mind in retained_minds))
        )
        if self.effective_tiers != expected_projection:
            raise ValueError(
                "effective_tiers may only remove unavailable minds without reordering"
            )
        changed = self.effective_tiers != self.structural_profile.authority_tiers
        if changed:
            if self.override_reason is None or self.functional_override is None:
                raise ValueError(
                    "Changed effective authority requires an explicit functional override"
                )
            removed_minds = {"R", "E", "I"} - retained_minds
            if set(self.functional_override.unavailable_minds) != removed_minds:
                raise ValueError("Functional override must identify exactly the removed minds")
        elif self.override_reason is not None or self.functional_override is not None:
            raise ValueError("Functional override is only valid when effective authority changes")
        return self


class MindDevelopmentState(FrozenModel):
    """Open-ended, sourced development observations for one mind."""

    observations: tuple[str, ...] = ()
    source_artifact_ids: tuple[NonEmptyId, ...] = ()


class MindDevelopment(FrozenArtifactModel):
    """Development context kept separate from stable authority."""

    schema_version: Literal["rei-native-mind-development-v1"] = (
        "rei-native-mind-development-v1"
    )
    mind_development_id: NonEmptyId
    racio: MindDevelopmentState
    emocio: MindDevelopmentState
    instinkt: MindDevelopmentState


class MindWorlds(FrozenArtifactModel):
    """The three modality-specific worlds at one explicit point in time."""

    schema_version: Literal["rei-native-mind-worlds-v1"] = (
        "rei-native-mind-worlds-v1"
    )
    mind_worlds_id: NonEmptyId
    racio: RacioWorld
    emocio: EmocioWorld
    instinkt: InstinktWorld


class CurrentState(FrozenArtifactModel):
    """Transient context that cannot mutate the stored character profile."""

    schema_version: Literal["rei-native-current-state-v1"] = (
        "rei-native-current-state-v1"
    )
    current_state_id: NonEmptyId
    processor_availability: ProcessorAvailability
    racio_observations: tuple[str, ...] = ()
    emocio_observations: tuple[str, ...] = ()
    instinkt_observations: tuple[str, ...] = ()
    source_event_id: NonEmptyId | None = None


class PersonShell(FrozenArtifactModel):
    """Aggregate person context; no component grants an extra decision API."""

    schema_version: Literal["rei-native-person-shell-v1"] = (
        "rei-native-person-shell-v1"
    )
    person_id: NonEmptyId
    character_authority: CharacterAuthority
    mind_development: MindDevelopment
    mind_worlds: MindWorlds
    acceptance_state: AcceptanceState
    current_state: CurrentState
    ego_id: NonEmptyId
    ego_composition_id: NonEmptyId | None = None


__all__ = [
    "CharacterAuthority",
    "CharacterProfileId",
    "CharacterRule",
    "CurrentState",
    "EffectiveAuthority",
    "FunctionalOverride",
    "FunctionalOverrideReason",
    "MindDevelopment",
    "MindDevelopmentState",
    "MindWorlds",
    "PersonShell",
    "ProcessorAvailability",
]
