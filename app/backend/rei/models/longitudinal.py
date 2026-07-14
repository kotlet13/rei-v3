"""Content-addressed contracts for bounded longitudinal REI scenarios.

The contracts in this module describe evaluation inputs only.  They do not run
the engine, mutate an Ego trace, or introduce a fourth decision-making agent.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from .character import CharacterAuthority
from .common import FrozenArtifactModel, HashDigest, NonEmptyId, NonEmptyText
from .communication import AcceptanceState
from .ego import OutcomeRecord
from .emocio import EmocioWorld
from .instinkt import BodyState, InstinktWorld
from .racio import RacioWorld
from .scene import SceneEvent


LongitudinalOutcomeMode = Literal[
    "none",
    "external_observation",
    "simulator",
]
MAX_LONGITUDINAL_EXPECTATIONS = 64
MAX_LONGITUDINAL_EXPECTATION_CHARS = 512


def _cold_revalidate(value):
    model_type = type(value)
    cold = model_type.model_validate(
        value.model_dump(mode="python", round_trip=True)
    )
    if cold != value:
        raise ValueError("Longitudinal input changed during cold validation")
    return cold


def _validate_unique(values: tuple[str, ...], field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must contain unique values")


class LongitudinalPersonState(FrozenArtifactModel):
    """One exact, profile-bearing starting point for a longitudinal cohort."""

    schema_version: Literal["rei-longitudinal-person-state-v1"] = (
        "rei-longitudinal-person-state-v1"
    )
    state_id: NonEmptyId
    ego_id: NonEmptyId
    structural_character: CharacterAuthority
    acceptance_state: AcceptanceState
    racio_world: RacioWorld
    emocio_world: EmocioWorld
    instinkt_world: InstinktWorld
    body_state: BodyState
    state_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: str,
        structural_character: CharacterAuthority,
        acceptance_state: AcceptanceState,
        racio_world: RacioWorld,
        emocio_world: EmocioWorld,
        instinkt_world: InstinktWorld,
        body_state: BodyState,
    ) -> "LongitudinalPersonState":
        structural_character = _cold_revalidate(structural_character)
        acceptance_state = _cold_revalidate(acceptance_state)
        racio_world = _cold_revalidate(racio_world)
        emocio_world = _cold_revalidate(emocio_world)
        instinkt_world = _cold_revalidate(instinkt_world)
        body_state = _cold_revalidate(body_state)
        base = {
            "schema_version": "rei-longitudinal-person-state-v1",
            "ego_id": ego_id,
            "structural_character": structural_character,
            "acceptance_state": acceptance_state,
            "racio_world": racio_world,
            "emocio_world": emocio_world,
            "instinkt_world": instinkt_world,
            "body_state": body_state,
        }
        state_id = content_id("person_state", base)
        payload = {"state_id": state_id, **base}
        return cls(**payload, state_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"state_id", "state_hash"},
        )
        if self.state_id != content_id("person_state", base):
            raise ValueError("Longitudinal person state ID differs from its content")
        payload = {"state_id": self.state_id, **base}
        if self.state_hash != sha256_hex(payload):
            raise ValueError("Longitudinal person state hash differs from its content")
        return self


class LongitudinalEventStep(FrozenArtifactModel):
    """One ordered scene and its optional externally supplied outcome."""

    schema_version: Literal["rei-longitudinal-event-step-v1"] = (
        "rei-longitudinal-event-step-v1"
    )
    step_id: NonEmptyId
    sequence_index: int = Field(ge=0)
    scene: SceneEvent
    expected_outcome_mode: LongitudinalOutcomeMode
    external_outcome: OutcomeRecord | None = None
    step_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        sequence_index: int,
        scene: SceneEvent,
        expected_outcome_mode: LongitudinalOutcomeMode = "none",
        external_outcome: OutcomeRecord | None = None,
    ) -> "LongitudinalEventStep":
        scene = _cold_revalidate(scene)
        if external_outcome is not None:
            external_outcome = _cold_revalidate(external_outcome)
        base = {
            "schema_version": "rei-longitudinal-event-step-v1",
            "sequence_index": sequence_index,
            "scene": scene,
            "expected_outcome_mode": expected_outcome_mode,
            "external_outcome": external_outcome,
        }
        step_id = content_id("longitudinal_step", base)
        payload = {"step_id": step_id, **base}
        return cls(**payload, step_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_step(self) -> Self:
        if self.external_outcome is None:
            if self.expected_outcome_mode != "none":
                raise ValueError(
                    "A longitudinal step without an outcome must use mode 'none'"
                )
        elif (
            self.external_outcome.event_id != self.scene.event_id
            or self.external_outcome.source != self.expected_outcome_mode
        ):
            raise ValueError(
                "Longitudinal outcome must match the step scene and outcome mode"
            )

        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"step_id", "step_hash"},
        )
        if self.step_id != content_id("longitudinal_step", base):
            raise ValueError("Longitudinal step ID differs from its content")
        payload = {"step_id": self.step_id, **base}
        if self.step_hash != sha256_hex(payload):
            raise ValueError("Longitudinal step hash differs from its content")
        return self


class LongitudinalScenario(FrozenArtifactModel):
    """A bounded 10--30 cycle scenario with explicit semantic expectations."""

    schema_version: Literal["rei-longitudinal-scenario-v1"] = (
        "rei-longitudinal-scenario-v1"
    )
    scenario_id: NonEmptyId
    sequence_id: NonEmptyId
    initial_person_state: LongitudinalPersonState
    steps: tuple[LongitudinalEventStep, ...] = Field(min_length=10, max_length=30)
    expected_motifs: tuple[NonEmptyText, ...] = ()
    expected_translation_patterns: tuple[NonEmptyText, ...] = ()
    expected_world_changes: tuple[NonEmptyText, ...] = ()
    scenario_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        sequence_id: str,
        initial_person_state: LongitudinalPersonState,
        steps: tuple[LongitudinalEventStep, ...],
        expected_motifs: tuple[str, ...] = (),
        expected_translation_patterns: tuple[str, ...] = (),
        expected_world_changes: tuple[str, ...] = (),
    ) -> "LongitudinalScenario":
        initial_person_state = _cold_revalidate(initial_person_state)
        steps = tuple(_cold_revalidate(item) for item in steps)
        expected_motifs = tuple(sorted(set(expected_motifs)))
        expected_translation_patterns = tuple(
            sorted(set(expected_translation_patterns))
        )
        expected_world_changes = tuple(sorted(set(expected_world_changes)))
        base = {
            "schema_version": "rei-longitudinal-scenario-v1",
            "sequence_id": sequence_id,
            "initial_person_state": initial_person_state,
            "steps": steps,
            "expected_motifs": expected_motifs,
            "expected_translation_patterns": expected_translation_patterns,
            "expected_world_changes": expected_world_changes,
        }
        scenario_id = content_id("longitudinal_scenario", base)
        payload = {"scenario_id": scenario_id, **base}
        return cls(**payload, scenario_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_scenario(self) -> Self:
        _cold_revalidate(self.initial_person_state)
        for step in self.steps:
            _cold_revalidate(step)
        expected_indexes = tuple(range(len(self.steps)))
        if tuple(step.sequence_index for step in self.steps) != expected_indexes:
            raise ValueError(
                "Longitudinal scenario steps must use contiguous zero-based indexes"
            )
        _validate_unique(tuple(step.step_id for step in self.steps), "step IDs")
        _validate_unique(
            tuple(step.scene.event_id for step in self.steps),
            "step SceneEvent IDs",
        )
        for field_name in (
            "expected_motifs",
            "expected_translation_patterns",
            "expected_world_changes",
        ):
            _validate_unique(getattr(self, field_name), field_name)
            values = getattr(self, field_name)
            if values != tuple(sorted(values)):
                raise ValueError(f"{field_name} must use canonical sorted order")
            if len(values) > MAX_LONGITUDINAL_EXPECTATIONS:
                raise ValueError(f"{field_name} exceeds its bounded item count")
            if any(
                len(value) > MAX_LONGITUDINAL_EXPECTATION_CHARS for value in values
            ):
                raise ValueError(f"{field_name} contains oversized text")

        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"scenario_id", "scenario_hash"},
        )
        if self.scenario_id != content_id("longitudinal_scenario", base):
            raise ValueError("Longitudinal scenario ID differs from its content")
        payload = {"scenario_id": self.scenario_id, **base}
        if self.scenario_hash != sha256_hex(payload):
            raise ValueError("Longitudinal scenario hash differs from its content")
        return self


__all__ = [
    "LongitudinalEventStep",
    "LongitudinalOutcomeMode",
    "LongitudinalPersonState",
    "LongitudinalScenario",
]
