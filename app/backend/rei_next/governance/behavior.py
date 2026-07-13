"""Explicit deterministic B10 mapping from commitment to observable behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Formatter
from typing import Literal, Protocol, runtime_checkable

from pydantic import model_validator

from ..models.common import FrozenModel, NonEmptyId, NonEmptyText
from ..models.communication import AcceptanceState
from ..models.conscious import (
    BehaviorResultant,
    BehaviorStatus,
    ConsciousDecision,
    ConsciousInterpretationInput,
    ConsciousMandateView,
)
from ..models.racio import RacioNativeConclusion
from ..conscious.committer import (
    DEFAULT_B10_COMMIT_POLICY,
    ConsciousCommitPolicy,
    select_commit_rule_id,
)


B10_BEHAVIOR_POLICY_ID = "b10-behavior-resolution-table-v1"
B10_BEHAVIOR_POLICY_REVISION = "1"

BehaviorOptionSource = Literal[
    "none",
    "governance_mandate",
    "racio_native_conclusion",
]
ControllerSource = Literal["none", "delegation_or_single_structural_source"]


class BehaviorResolutionRule(FrozenModel):
    """One inspectable row in the B10 behavior table."""

    rule_id: NonEmptyId
    priority: int
    expected_decision_status: Literal["committed", "deferred", "blocked"]
    option_source: BehaviorOptionSource
    behavior_status: BehaviorStatus
    controller_source: ControllerSource
    required_visible_tension: NonEmptyText | None = None
    predicted_action_template: NonEmptyText

    @model_validator(mode="after")
    def validate_template_and_semantics(self) -> BehaviorResolutionRule:
        fields = {
            name
            for _, name, _, _ in Formatter().parse(self.predicted_action_template)
            if name is not None
        }
        if not fields.issubset({"option_id", "mandate_option_id"}):
            raise ValueError("Behavior action template uses an unsupported field")
        if self.behavior_status == "executed":
            if self.option_source == "none":
                raise ValueError("Executed behavior rule requires an option source")
            if self.controller_source != "delegation_or_single_structural_source":
                raise ValueError(
                    "Executed behavior must derive its operational controller"
                )
        elif self.controller_source != "none":
            raise ValueError("Only executed behavior may assign an operational controller")
        return self


class BehaviorResolutionPolicy(FrozenModel):
    """Caller-injectable and hash-addressed B10 behavior configuration."""

    policy_id: NonEmptyId = B10_BEHAVIOR_POLICY_ID
    revision: NonEmptyText = B10_BEHAVIOR_POLICY_REVISION
    basis: Literal["implementation_hypothesis"] = "implementation_hypothesis"
    uses_acceptance_fidelity_audit: Literal[False] = False
    uses_relation_thresholds: Literal[False] = False
    uses_character_weights: Literal[False] = False
    uses_prose_keywords: Literal[False] = False
    ordered_rules: tuple[BehaviorResolutionRule, ...]

    @model_validator(mode="after")
    def validate_exhaustive_table(self) -> BehaviorResolutionPolicy:
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
            raise ValueError("B10 behavior rows must be complete and canonically ordered")
        if tuple(rule.priority for rule in self.ordered_rules) != tuple(range(1, 8)):
            raise ValueError("B10 behavior priorities must be exactly 1 through 7")
        canonical_semantics = (
            ("deferred", "none", "unresolved", "none", "acceptance_unknown_or_mandate_not_actionable", "No actionable behavior is resolved."),
            ("committed", "governance_mandate", "executed", "delegation_or_single_structural_source", None, "Execute governance-coordinated option {option_id}."),
            ("committed", "governance_mandate", "executed", "delegation_or_single_structural_source", None, "Execute consciously recognized option {option_id}."),
            ("committed", "racio_native_conclusion", "oscillating", "none", "mandate_not_consciously_recognized", "Oscillate around conscious option {option_id} while governance remains {mandate_option_id}."),
            ("deferred", "none", "delayed", "none", "mandate_not_recognized_and_no_racio_option", "Delay action on governance option {mandate_option_id}."),
            ("committed", "racio_native_conclusion", "sabotaged", "none", "conflicted_coordination_sabotage", "Sabotage execution of conscious option {option_id}."),
            ("blocked", "none", "blocked", "none", "conflicted_coordination_without_racio_option", "Block action on governance option {mandate_option_id}."),
        )
        actual_semantics = tuple(
            (
                rule.expected_decision_status,
                rule.option_source,
                rule.behavior_status,
                rule.controller_source,
                rule.required_visible_tension,
                rule.predicted_action_template,
            )
            for rule in self.ordered_rules
        )
        if (
            self.policy_id == B10_BEHAVIOR_POLICY_ID
            and self.revision == B10_BEHAVIOR_POLICY_REVISION
            and actual_semantics != canonical_semantics
        ):
            raise ValueError("Canonical B10 behavior semantics are immutable in revision 1")
        return self

    def rule(self, rule_id: str) -> BehaviorResolutionRule:
        for rule in self.ordered_rules:
            if rule.rule_id == rule_id:
                return rule
        raise ValueError(f"Unknown B10 behavior rule: {rule_id}")


DEFAULT_B10_BEHAVIOR_POLICY = BehaviorResolutionPolicy(
    ordered_rules=(
        BehaviorResolutionRule(
            rule_id="unknown_or_non_actionable",
            priority=1,
            expected_decision_status="deferred",
            option_source="none",
            behavior_status="unresolved",
            controller_source="none",
            required_visible_tension="acceptance_unknown_or_mandate_not_actionable",
            predicted_action_template="No actionable behavior is resolved.",
        ),
        BehaviorResolutionRule(
            rule_id="accepting_actionable",
            priority=2,
            expected_decision_status="committed",
            option_source="governance_mandate",
            behavior_status="executed",
            controller_source="delegation_or_single_structural_source",
            predicted_action_template="Execute governance-coordinated option {option_id}.",
        ),
        BehaviorResolutionRule(
            rule_id="mixed_recognized_or_r_led",
            priority=3,
            expected_decision_status="committed",
            option_source="governance_mandate",
            behavior_status="executed",
            controller_source="delegation_or_single_structural_source",
            predicted_action_template="Execute consciously recognized option {option_id}.",
        ),
        BehaviorResolutionRule(
            rule_id="mixed_unrecognized_with_racio_option",
            priority=4,
            expected_decision_status="committed",
            option_source="racio_native_conclusion",
            behavior_status="oscillating",
            controller_source="none",
            required_visible_tension="mandate_not_consciously_recognized",
            predicted_action_template=(
                "Oscillate around conscious option {option_id} while governance remains "
                "{mandate_option_id}."
            ),
        ),
        BehaviorResolutionRule(
            rule_id="mixed_unrecognized_without_racio_option",
            priority=5,
            expected_decision_status="deferred",
            option_source="none",
            behavior_status="delayed",
            controller_source="none",
            required_visible_tension="mandate_not_recognized_and_no_racio_option",
            predicted_action_template="Delay action on governance option {mandate_option_id}.",
        ),
        BehaviorResolutionRule(
            rule_id="conflicted_with_racio_option",
            priority=6,
            expected_decision_status="committed",
            option_source="racio_native_conclusion",
            behavior_status="sabotaged",
            controller_source="none",
            required_visible_tension="conflicted_coordination_sabotage",
            predicted_action_template="Sabotage execution of conscious option {option_id}.",
        ),
        BehaviorResolutionRule(
            rule_id="conflicted_without_racio_option",
            priority=7,
            expected_decision_status="blocked",
            option_source="none",
            behavior_status="blocked",
            controller_source="none",
            required_visible_tension="conflicted_coordination_without_racio_option",
            predicted_action_template="Block action on governance option {mandate_option_id}.",
        ),
    )
)


def _validate_rule_context(
    *,
    rule: BehaviorResolutionRule,
    mandate_view: ConsciousMandateView,
    decision: ConsciousDecision,
    acceptance_state: AcceptanceState,
    racio_conclusion: RacioNativeConclusion,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    commit_policy: ConsciousCommitPolicy,
) -> str | None:
    expected_rule_id = select_commit_rule_id(
        mandate_view=mandate_view,
        racio_conclusion=racio_conclusion,
        acceptance_state=acceptance_state,
        interpretation_inputs=interpretation_inputs,
    )
    if rule.rule_id != expected_rule_id or decision.applied_rule_id != expected_rule_id:
        raise ValueError("Behavior rule does not replay from the conscious inputs")
    commit_rule = commit_policy.rule(expected_rule_id)
    if (
        decision.committer_policy != commit_policy.policy_id
        or decision.committer_revision != commit_policy.revision
        or decision.committer_policy_hash != commit_policy.content_hash()
    ):
        raise ValueError("Behavior received a decision from another commitment table")
    if commit_rule.option_source == "governance_mandate":
        expected_decision_option = mandate_view.option_id
    elif commit_rule.option_source == "racio_native_conclusion":
        expected_decision_option = racio_conclusion.option_id
    else:
        expected_decision_option = None
    if (
        decision.decision_status != commit_rule.decision_status
        or decision.decision_status != rule.expected_decision_status
        or decision.option_id != expected_decision_option
    ):
        raise ValueError("Conscious decision differs from its commitment-table row")
    if rule.option_source == "governance_mandate":
        behavior_option = mandate_view.option_id
    elif rule.option_source == "racio_native_conclusion":
        behavior_option = racio_conclusion.option_id
    else:
        behavior_option = None
    if behavior_option != decision.option_id:
        raise ValueError("Behavior option source differs from the conscious commitment")
    return behavior_option


def _controller(
    *,
    rule: BehaviorResolutionRule,
    mandate_view: ConsciousMandateView,
) -> Literal["R", "E", "I"] | None:
    if rule.controller_source == "none":
        return None
    if mandate_view.delegation is not None:
        return mandate_view.delegation.delegate_mind
    if len(mandate_view.structural_source_minds) == 1:
        return mandate_view.structural_source_minds[0]
    return None


def _residual_tensions(
    *,
    rule: BehaviorResolutionRule,
    mandate_view: ConsciousMandateView,
    decision: ConsciousDecision,
) -> tuple[str, ...]:
    tensions: list[str] = []
    if rule.required_visible_tension is not None:
        tensions.append(rule.required_visible_tension)
    if (
        mandate_view.option_id is not None
        and decision.option_id is not None
        and decision.option_id != mandate_view.option_id
    ):
        tensions.append(
            "conscious_mandate_divergence:"
            f"decision={decision.option_id};mandate={mandate_view.option_id}"
        )
    tensions.extend(
        f"governance_objection:{item.mind}:{item.statement}"
        for item in mandate_view.objections
    )
    return tuple(tensions)


@runtime_checkable
class BehaviorResolver(Protocol):
    """Deterministic behavior resolution boundary."""

    @property
    def replay_safe(self) -> bool: ...

    def resolve(
        self,
        *,
        mandate_view: ConsciousMandateView,
        decision: ConsciousDecision,
        acceptance_state: AcceptanceState,
        racio_conclusion: RacioNativeConclusion,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    ) -> BehaviorResultant: ...


@dataclass(frozen=True, slots=True)
class DeterministicBehaviorResolver:
    """Execute the injected B10 table without an LLM or hidden score threshold."""

    policy: BehaviorResolutionPolicy = field(
        default_factory=lambda: DEFAULT_B10_BEHAVIOR_POLICY
    )
    commit_policy: ConsciousCommitPolicy = field(
        default_factory=lambda: DEFAULT_B10_COMMIT_POLICY
    )

    @property
    def replay_safe(self) -> bool:
        return True

    def resolve(
        self,
        *,
        mandate_view: ConsciousMandateView,
        decision: ConsciousDecision,
        acceptance_state: AcceptanceState,
        racio_conclusion: RacioNativeConclusion,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    ) -> BehaviorResultant:
        if decision.derivation_status != "derived_b10":
            raise ValueError("B10 behavior requires a derived B10 decision")
        decision.validate_against(
            mandate_view=mandate_view,
            racio_conclusion=racio_conclusion,
            acceptance_state=acceptance_state,
            interpretation_inputs=interpretation_inputs,
        )
        if (
            decision.source_mandate_view_id != mandate_view.mandate_view_id
            or decision.source_mandate_view_hash != mandate_view.content_hash()
        ):
            raise ValueError("Behavior inputs do not share one conscious mandate view")
        if (
            decision.source_acceptance_state_id != acceptance_state.acceptance_state_id
            or decision.source_acceptance_state_hash != acceptance_state.content_hash()
        ):
            raise ValueError("Behavior inputs do not share one AcceptanceState")
        if decision.applied_rule_id is None:
            raise ValueError("B10 decision does not identify its commitment rule")
        rule = self.policy.rule(decision.applied_rule_id)
        option_id = _validate_rule_context(
            rule=rule,
            mandate_view=mandate_view,
            decision=decision,
            acceptance_state=acceptance_state,
            racio_conclusion=racio_conclusion,
            interpretation_inputs=interpretation_inputs,
            commit_policy=self.commit_policy,
        )
        predicted_action = rule.predicted_action_template.format(
            option_id=option_id,
            mandate_option_id=mandate_view.option_id,
        )
        return BehaviorResultant.create_b10(
            mandate_view=mandate_view,
            decision=decision,
            acceptance_state=acceptance_state,
            behavior_policy_id=self.policy.policy_id,
            behavior_policy_revision=self.policy.revision,
            behavior_policy_hash=self.policy.content_hash(),
            applied_rule_id=rule.rule_id,
            option_id=option_id,
            status=rule.behavior_status,
            operational_controller=_controller(rule=rule, mandate_view=mandate_view),
            residual_tensions=_residual_tensions(
                rule=rule,
                mandate_view=mandate_view,
                decision=decision,
            ),
            predicted_action=predicted_action,
        )


def resolve_behavior(
    *,
    mandate_view: ConsciousMandateView,
    decision: ConsciousDecision,
    acceptance_state: AcceptanceState,
    racio_conclusion: RacioNativeConclusion,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    policy: BehaviorResolutionPolicy = DEFAULT_B10_BEHAVIOR_POLICY,
    commit_policy: ConsciousCommitPolicy = DEFAULT_B10_COMMIT_POLICY,
) -> BehaviorResultant:
    """Functional convenience wrapper around the deterministic resolver."""

    return DeterministicBehaviorResolver(
        policy=policy,
        commit_policy=commit_policy,
    ).resolve(
        mandate_view=mandate_view,
        decision=decision,
        acceptance_state=acceptance_state,
        racio_conclusion=racio_conclusion,
        interpretation_inputs=interpretation_inputs,
    )


def validate_behavior_replay(
    *,
    resolver: BehaviorResolver,
    resultant: BehaviorResultant,
    mandate_view: ConsciousMandateView,
    decision: ConsciousDecision,
    acceptance_state: AcceptanceState,
    racio_conclusion: RacioNativeConclusion,
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> BehaviorResultant:
    """Reject a stored behavior resultant that differs from table replay."""

    if resolver.replay_safe is not True:
        raise ValueError("Behavior replay requires a replay-safe resolver")
    replayed = resolver.resolve(
        mandate_view=mandate_view,
        decision=decision,
        acceptance_state=acceptance_state,
        racio_conclusion=racio_conclusion,
        interpretation_inputs=interpretation_inputs,
    )
    if resultant != replayed:
        raise ValueError("Behavior resultant differs from deterministic replay")
    return resultant


__all__ = [
    "B10_BEHAVIOR_POLICY_ID",
    "B10_BEHAVIOR_POLICY_REVISION",
    "BehaviorResolutionPolicy",
    "BehaviorResolutionRule",
    "BehaviorResolver",
    "DEFAULT_B10_BEHAVIOR_POLICY",
    "DeterministicBehaviorResolver",
    "resolve_behavior",
    "validate_behavior_replay",
]
