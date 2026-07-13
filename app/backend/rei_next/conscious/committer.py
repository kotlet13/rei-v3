"""Transparent B10 Racio commitment after governance and interpretation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from pydantic import model_validator

from ..models.common import FrozenModel, NonEmptyId, NonEmptyText
from ..models.communication import AcceptanceState, RacioInterpretation
from ..models.conscious import (
    ConsciousDecision,
    ConsciousInterpretationInput,
    ConsciousMandateView,
)
from ..models.racio import RacioNativeConclusion


B10_COMMIT_POLICY_ID = "b10-conscious-commit-table-v1"
B10_COMMIT_POLICY_REVISION = "1"

CommitOptionSource = Literal["none", "governance_mandate", "racio_native_conclusion"]
CommitReasonSource = Literal[
    "deferred",
    "mandate_interpretation_or_racio",
    "racio_native",
    "blocked",
]


class ConsciousCommitRule(FrozenModel):
    """One public row of the ordered deterministic commitment table."""

    rule_id: NonEmptyId
    priority: int
    option_source: CommitOptionSource
    decision_status: Literal["committed", "deferred", "blocked"]
    reason_source: CommitReasonSource


class ConsciousCommitPolicy(FrozenModel):
    """Caller-injectable, content-addressable B10 commitment configuration."""

    policy_id: NonEmptyId = B10_COMMIT_POLICY_ID
    revision: NonEmptyText = B10_COMMIT_POLICY_REVISION
    basis: Literal["implementation_hypothesis"] = "implementation_hypothesis"
    ordered_rules: tuple[ConsciousCommitRule, ...]

    @model_validator(mode="after")
    def validate_exhaustive_table(self) -> ConsciousCommitPolicy:
        expected = (
            "unknown_or_non_actionable",
            "accepting_actionable",
            "mixed_recognized_or_r_led",
            "mixed_unrecognized_with_racio_option",
            "mixed_unrecognized_without_racio_option",
            "conflicted_with_racio_option",
            "conflicted_without_racio_option",
        )
        if tuple(rule.rule_id for rule in self.ordered_rules) != expected:
            raise ValueError("B10 commitment rows must be complete and canonically ordered")
        if tuple(rule.priority for rule in self.ordered_rules) != tuple(range(1, 8)):
            raise ValueError("B10 commitment priorities must be exactly 1 through 7")
        canonical_semantics = (
            ("none", "deferred", "deferred"),
            ("governance_mandate", "committed", "mandate_interpretation_or_racio"),
            ("governance_mandate", "committed", "mandate_interpretation_or_racio"),
            ("racio_native_conclusion", "committed", "racio_native"),
            ("none", "deferred", "deferred"),
            ("racio_native_conclusion", "committed", "racio_native"),
            ("none", "blocked", "blocked"),
        )
        actual_semantics = tuple(
            (rule.option_source, rule.decision_status, rule.reason_source)
            for rule in self.ordered_rules
        )
        if (
            self.policy_id == B10_COMMIT_POLICY_ID
            and self.revision == B10_COMMIT_POLICY_REVISION
            and actual_semantics != canonical_semantics
        ):
            raise ValueError("Canonical B10 commitment semantics are immutable in revision 1")
        return self

    def rule(self, rule_id: str) -> ConsciousCommitRule:
        for rule in self.ordered_rules:
            if rule.rule_id == rule_id:
                return rule
        raise ValueError(f"Unknown B10 commitment rule: {rule_id}")


DEFAULT_B10_COMMIT_POLICY = ConsciousCommitPolicy(
    ordered_rules=(
        ConsciousCommitRule(
            rule_id="unknown_or_non_actionable",
            priority=1,
            option_source="none",
            decision_status="deferred",
            reason_source="deferred",
        ),
        ConsciousCommitRule(
            rule_id="accepting_actionable",
            priority=2,
            option_source="governance_mandate",
            decision_status="committed",
            reason_source="mandate_interpretation_or_racio",
        ),
        ConsciousCommitRule(
            rule_id="mixed_recognized_or_r_led",
            priority=3,
            option_source="governance_mandate",
            decision_status="committed",
            reason_source="mandate_interpretation_or_racio",
        ),
        ConsciousCommitRule(
            rule_id="mixed_unrecognized_with_racio_option",
            priority=4,
            option_source="racio_native_conclusion",
            decision_status="committed",
            reason_source="racio_native",
        ),
        ConsciousCommitRule(
            rule_id="mixed_unrecognized_without_racio_option",
            priority=5,
            option_source="none",
            decision_status="deferred",
            reason_source="deferred",
        ),
        ConsciousCommitRule(
            rule_id="conflicted_with_racio_option",
            priority=6,
            option_source="racio_native_conclusion",
            decision_status="committed",
            reason_source="racio_native",
        ),
        ConsciousCommitRule(
            rule_id="conflicted_without_racio_option",
            priority=7,
            option_source="none",
            decision_status="blocked",
            reason_source="blocked",
        ),
    )
)


@runtime_checkable
class RacioCommitter(Protocol):
    """Racio-only conscious commitment boundary."""

    @property
    def committer_id(self) -> str: ...

    @property
    def replay_safe(self) -> bool: ...

    def commit(
        self,
        *,
        mandate_view: ConsciousMandateView,
        racio_conclusion: RacioNativeConclusion,
        acceptance_state: AcceptanceState,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    ) -> ConsciousDecision: ...


def _is_actionable(view: ConsciousMandateView) -> bool:
    return (
        view.status in {"resolved", "delegated", "functionally_overridden"}
        and view.option_id is not None
    )


def _is_recognized(
    view: ConsciousMandateView,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> bool:
    if "R" in view.structural_source_minds:
        return True
    source_minds = set(view.structural_source_minds).intersection({"E", "I"})
    return any(
        item.interpretation.source_mind in source_minds
        and item.interpretation.interpretation_status != "unverified_contract"
        and item.interpretation.inferred_option_id == view.option_id
        for item in interpretation_inputs
    )


def select_commit_rule_id(
    *,
    mandate_view: ConsciousMandateView,
    racio_conclusion: RacioNativeConclusion,
    acceptance_state: AcceptanceState,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> str:
    """Select one ordered row using only the canon-declared branch inputs."""

    actionable = _is_actionable(mandate_view)
    if acceptance_state.overall_mode == "unknown" or not actionable:
        return "unknown_or_non_actionable"
    if acceptance_state.overall_mode == "accepting":
        return "accepting_actionable"
    racio_option_available = (
        not racio_conclusion.abstains and racio_conclusion.option_id is not None
    )
    if acceptance_state.overall_mode == "mixed":
        if _is_recognized(mandate_view, interpretation_inputs):
            return "mixed_recognized_or_r_led"
        return (
            "mixed_unrecognized_with_racio_option"
            if racio_option_available
            else "mixed_unrecognized_without_racio_option"
        )
    return (
        "conflicted_with_racio_option"
        if racio_option_available
        else "conflicted_without_racio_option"
    )


def _raw_interpretations(
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> tuple[RacioInterpretation, ...]:
    return tuple(item.interpretation for item in interpretation_inputs)


def _validate_cycle_inputs(
    *,
    mandate_view: ConsciousMandateView,
    racio_conclusion: RacioNativeConclusion,
    acceptance_state: AcceptanceState,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> None:
    if (
        mandate_view.source_racio_conclusion_id != racio_conclusion.conclusion_id
        or mandate_view.source_racio_conclusion_hash != racio_conclusion.content_hash()
        or mandate_view.source_scene_id != racio_conclusion.source_scene_id
    ):
        raise ValueError("Committer inputs do not share one native cycle")
    minds = tuple(item.interpretation.source_mind for item in interpretation_inputs)
    if len(set(minds)) != len(minds):
        raise ValueError("Committer accepts at most one interpretation per E/I mind")
    required_minds = (
        set()
        if "R" in mandate_view.structural_source_minds
        else set(mandate_view.structural_source_minds).intersection({"E", "I"})
    )
    missing_minds = required_minds - set(minds)
    if missing_minds:
        raise ValueError(
            "E/I-led conscious commitment requires a typed B9 interpretation "
            f"for: {', '.join(sorted(missing_minds))}"
        )
    for item in interpretation_inputs:
        item.validate_against(
            mandate_view=mandate_view,
            acceptance_state=acceptance_state,
        )


def _interpreted_reason(
    *,
    mandate_view: ConsciousMandateView,
    racio_conclusion: RacioNativeConclusion,
    acceptance_state: AcceptanceState,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> str:
    interpretations = _raw_interpretations(interpretation_inputs)
    if "R" in mandate_view.structural_source_minds:
        return racio_conclusion.explicit_goal
    by_mind = {item.source_mind: item for item in interpretations}
    source_order = tuple(
        mind for mind in ("E", "I") if mind in mandate_view.structural_source_minds
    )
    candidates = tuple(
        by_mind[mind]
        for mind in source_order
        if mind in by_mind
        and (
            acceptance_state.overall_mode == "accepting"
            or by_mind[mind].inferred_option_id == mandate_view.option_id
        )
    )
    for interpretation in candidates:
        if interpretation.inferred_motive.strip():
            return interpretation.inferred_motive
    return (
        "Racio consciously adopts the governance mandate while its motive "
        "remains unavailable in the conscious interpretation."
    )


@dataclass(frozen=True, slots=True)
class DeterministicRacioCommitter:
    """Provider-free execution of the public B10 commitment table."""

    policy: ConsciousCommitPolicy = field(default_factory=lambda: DEFAULT_B10_COMMIT_POLICY)

    @property
    def committer_id(self) -> str:
        return "deterministic-racio-committer-v1"

    @property
    def replay_safe(self) -> bool:
        return True

    def commit(
        self,
        *,
        mandate_view: ConsciousMandateView,
        racio_conclusion: RacioNativeConclusion,
        acceptance_state: AcceptanceState,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    ) -> ConsciousDecision:
        _validate_cycle_inputs(
            mandate_view=mandate_view,
            racio_conclusion=racio_conclusion,
            acceptance_state=acceptance_state,
            interpretation_inputs=interpretation_inputs,
        )

        rule_id = select_commit_rule_id(
            mandate_view=mandate_view,
            racio_conclusion=racio_conclusion,
            acceptance_state=acceptance_state,
            interpretation_inputs=interpretation_inputs,
        )
        rule = self.policy.rule(rule_id)
        if rule.option_source == "governance_mandate":
            option_id = mandate_view.option_id
        elif rule.option_source == "racio_native_conclusion":
            option_id = racio_conclusion.option_id
        else:
            option_id = None

        if rule.reason_source == "mandate_interpretation_or_racio":
            reason = _interpreted_reason(
                mandate_view=mandate_view,
                racio_conclusion=racio_conclusion,
                acceptance_state=acceptance_state,
                interpretation_inputs=interpretation_inputs,
            )
        elif rule.reason_source == "racio_native":
            reason = racio_conclusion.explicit_goal
        elif rule.reason_source == "blocked":
            reason = (
                "Racio records blocked conscious commitment under explicitly "
                "conflicted coordination and has no native option to commit."
            )
        else:
            reason = (
                "Racio defers because acceptance is unknown or the governance "
                "mandate is not actionable in this cycle."
                if rule_id == "unknown_or_non_actionable"
                else "Racio defers because it did not recognize the mandate and has no native option."
            )

        return ConsciousDecision.create_b10(
            mandate_view=mandate_view,
            racio_conclusion=racio_conclusion,
            acceptance_state=acceptance_state,
            interpretation_inputs=interpretation_inputs,
            option_id=option_id,
            declared_reason=reason,
            conscious_confidence=racio_conclusion.confidence,
            decision_status=rule.decision_status,
            committer_id=self.committer_id,
            committer_revision=self.policy.revision,
            committer_policy=self.policy.policy_id,
            committer_policy_hash=self.policy.content_hash(),
            applied_rule_id=rule.rule_id,
        )


def validate_commitment_replay(
    *,
    committer: RacioCommitter,
    decision: ConsciousDecision,
    mandate_view: ConsciousMandateView,
    racio_conclusion: RacioNativeConclusion,
    acceptance_state: AcceptanceState,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> ConsciousDecision:
    """Reject a stored decision that differs from replay-safe commitment."""

    if committer.replay_safe is not True:
        raise ValueError("Commitment replay requires a replay-safe committer")
    replayed = committer.commit(
        mandate_view=mandate_view,
        racio_conclusion=racio_conclusion,
        acceptance_state=acceptance_state,
        interpretation_inputs=interpretation_inputs,
    )
    if decision != replayed:
        raise ValueError("Conscious decision differs from deterministic replay")
    return decision


__all__ = [
    "B10_COMMIT_POLICY_ID",
    "B10_COMMIT_POLICY_REVISION",
    "ConsciousCommitPolicy",
    "ConsciousCommitRule",
    "DEFAULT_B10_COMMIT_POLICY",
    "DeterministicRacioCommitter",
    "RacioCommitter",
    "select_commit_rule_id",
    "validate_commitment_replay",
]
