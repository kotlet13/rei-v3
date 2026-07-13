"""Downstream Racio self-narration for immutable B10 decisions and behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from ..models.common import FrozenModel, MindId
from ..models.conscious import (
    BehaviorResultant,
    ConsciousDecision,
    ConsciousInterpretationInput,
    ConsciousMandateView,
    RacioSelfNarrative,
)


B10_NARRATION_POLICY_ID = "b10-racio-self-narrative-v1"
B10_NARRATION_POLICY_REVISION = "1"


class RacioNarrationPolicy(FrozenModel):
    """Public narration policy; it describes, but never resolves, behavior."""

    policy_id: Literal["b10-racio-self-narrative-v1"] = B10_NARRATION_POLICY_ID
    revision: Literal["1"] = B10_NARRATION_POLICY_REVISION
    basis: Literal["implementation_hypothesis"] = "implementation_hypothesis"
    acknowledge_governance_sources: Literal[True] = True
    acknowledge_recorded_objections: Literal[True] = True
    preserve_divergence_language: Literal[True] = True
    may_mutate_decision_or_behavior: Literal[False] = False


DEFAULT_B10_NARRATION_POLICY = RacioNarrationPolicy()


@runtime_checkable
class RacioNarrator(Protocol):
    """Read-only narration boundary downstream of commitment and behavior."""

    @property
    def narrator_id(self) -> str: ...

    @property
    def replay_safe(self) -> bool: ...

    def narrate(
        self,
        *,
        mandate_view: ConsciousMandateView,
        decision: ConsciousDecision,
        resultant: BehaviorResultant,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    ) -> RacioSelfNarrative: ...


def _canonical_minds(minds: set[MindId]) -> tuple[MindId, ...]:
    return tuple(mind for mind in ("R", "E", "I") if mind in minds)


@dataclass(frozen=True, slots=True)
class DeterministicRacioNarrator:
    """Provider-free narrative that reports all recorded divergence explicitly."""

    policy: RacioNarrationPolicy = field(
        default_factory=lambda: DEFAULT_B10_NARRATION_POLICY
    )

    @property
    def narrator_id(self) -> str:
        return "deterministic-racio-narrator-v1"

    @property
    def replay_safe(self) -> bool:
        return True

    def narrate(
        self,
        *,
        mandate_view: ConsciousMandateView,
        decision: ConsciousDecision,
        resultant: BehaviorResultant,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    ) -> RacioSelfNarrative:
        if decision.derivation_status != "derived_b10":
            raise ValueError("B10 narrator requires a derived B10 conscious decision")
        if resultant.derivation_status != "derived_b10":
            raise ValueError("B10 narrator requires a derived B10 behavior resultant")
        if (
            resultant.source_decision_id != decision.decision_id
            or resultant.source_decision_hash != decision.content_hash()
        ):
            raise ValueError("Narrator inputs do not share one conscious decision")
        if (
            decision.source_mandate_view_id != mandate_view.mandate_view_id
            or resultant.source_mandate_view_id != mandate_view.mandate_view_id
        ):
            raise ValueError("Narrator inputs do not share one conscious mandate view")

        acknowledged: set[MindId] = {"R"}
        acknowledged.update(mandate_view.structural_source_minds)
        acknowledged.update(item.mind for item in mandate_view.objections)
        acknowledged.update(
            item.interpretation.source_mind for item in interpretation_inputs
        )
        acknowledged_minds = _canonical_minds(acknowledged)
        omitted_minds = _canonical_minds({"R", "E", "I"} - acknowledged)

        explanation = (
            f"Governance mandate {mandate_view.status} selected "
            f"{mandate_view.option_id!r}; Racio consciously recorded "
            f"{decision.decision_status} with {decision.option_id!r}; behavior "
            f"is {resultant.status} with {resultant.option_id!r}. "
            f"Governance alignment is {resultant.governance_alignment} and "
            f"conscious alignment is {resultant.conscious_alignment}."
        )
        if resultant.residual_tensions:
            explanation = (
                f"{explanation} Residual tensions: "
                + "; ".join(resultant.residual_tensions)
                + "."
            )
        uncertainty = (
            "This is Racio's downstream explanation, not proof of hidden E/I motives; "
            "it cannot revise the frozen mandate, decision, or behavior."
        )
        return RacioSelfNarrative.create_b10(
            mandate_view=mandate_view,
            decision=decision,
            resultant=resultant,
            interpretation_inputs=interpretation_inputs,
            explanation=explanation,
            claimed_motive=decision.declared_reason,
            acknowledged_minds=acknowledged_minds,
            omitted_minds=omitted_minds,
            uncertainty=uncertainty,
            narrator_id=self.narrator_id,
            narrator_revision=self.policy.revision,
            narrator_policy=self.policy.policy_id,
            narrator_policy_hash=self.policy.content_hash(),
        )


def validate_narration_replay(
    *,
    narrator: RacioNarrator,
    narrative: RacioSelfNarrative,
    mandate_view: ConsciousMandateView,
    decision: ConsciousDecision,
    resultant: BehaviorResultant,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> RacioSelfNarrative:
    """Reject a stored narrative that differs from deterministic replay."""

    if narrator.replay_safe is not True:
        raise ValueError("Narration replay requires a replay-safe narrator")
    replayed = narrator.narrate(
        mandate_view=mandate_view,
        decision=decision,
        resultant=resultant,
        interpretation_inputs=interpretation_inputs,
    )
    if narrative != replayed:
        raise ValueError("Racio self-narrative differs from deterministic replay")
    return narrative


__all__ = [
    "B10_NARRATION_POLICY_ID",
    "B10_NARRATION_POLICY_REVISION",
    "DEFAULT_B10_NARRATION_POLICY",
    "DeterministicRacioNarrator",
    "RacioNarrationPolicy",
    "RacioNarrator",
    "validate_narration_replay",
]
