"""Conscious commitment, narration, and observable behavior contracts.

B10 keeps three things deliberately separate: the character-governed mandate,
Racio's conscious commitment, and the behavior that follows.  Runtime B10
artifacts are content-addressed and cite their exact sanitized inputs.  The
original permissive contracts remain available as ``unverified_contract``
records so B2/B4 traces can still be read.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    MindId,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from .communication import (
    AcceptanceState,
    CommunicationArtifactRef,
    EmocioManifestation,
    InstinktManifestation,
    RacioInterpretation,
    RacioInterpreterRequest,
)
from .governance import (
    GovernanceResolution,
    GovernanceStatus,
    MindStatement,
    TaskDelegation,
)
from .racio import RacioNativeConclusion
from .run import NativeMindBundle


ConsciousDecisionStatus = Literal[
    "committed",
    "deferred",
    "oscillating",
    "blocked",
    "unknown",
]
BehaviorStatus = Literal[
    "executed",
    "delayed",
    "oscillating",
    "sabotaged",
    "blocked",
    "unresolved",
]
AlignmentStatus = Literal["aligned", "diverged", "unknown", "not_applicable"]
B10DerivationStatus = Literal["unverified_contract", "derived_b10"]

_MIND_ORDER: tuple[MindId, ...] = ("R", "E", "I")
_INTERPRETED_MIND_ORDER: tuple[Literal["E", "I"], ...] = ("E", "I")


def _canonical_minds(minds: tuple[MindId, ...]) -> tuple[MindId, ...]:
    selected = set(minds)
    return tuple(mind for mind in _MIND_ORDER if mind in selected)


def _alignment(option_id: str | None, target_option_id: str | None) -> AlignmentStatus:
    if target_option_id is None or option_id is None:
        return "not_applicable"
    return "aligned" if option_id == target_option_id else "diverged"


class InterpretationLineageRef(FrozenModel):
    """Exact scene-bound conscious interpretation cited by a B10 artifact."""

    source_mind: Literal["E", "I"]
    source_scene_id: NonEmptyId
    interpretation_input_id: NonEmptyId
    interpretation_input_hash: HashDigest
    interpretation_id: NonEmptyId
    interpretation_hash: HashDigest
    source_request_id: NonEmptyId
    source_request_hash: HashDigest


class ConsciousManifestationRef(FrozenModel):
    """Public current-cycle manifestation identity available to consciousness."""

    source_mind: Literal["E", "I"]
    manifestation_id: NonEmptyId
    manifestation_hash: HashDigest


class ConsciousInterpretationInput(FrozenArtifactModel):
    """A B9 request/interpretation pair bound to one explicit cycle scene."""

    schema_version: Literal["rei-native-conscious-interpretation-input-v1"] = (
        "rei-native-conscious-interpretation-input-v1"
    )
    interpretation_input_id: NonEmptyId
    source_scene_id: NonEmptyId
    source_mandate_view_id: NonEmptyId
    source_mandate_view_hash: HashDigest
    request: RacioInterpreterRequest
    interpretation: RacioInterpretation
    acceptance_state_id: NonEmptyId
    acceptance_state_hash: HashDigest
    input_hash: HashDigest

    @classmethod
    def create_b10(
        cls,
        *,
        mandate_view: ConsciousMandateView,
        request: RacioInterpreterRequest,
        interpretation: RacioInterpretation,
        acceptance_state: AcceptanceState,
    ) -> ConsciousInterpretationInput:
        interpretation.validate_against_request(request)
        if (
            request.acceptance_state_id != acceptance_state.acceptance_state_id
            or request.acceptance_state_hash != acceptance_state.content_hash()
        ):
            raise ValueError("Conscious interpretation request uses another AcceptanceState")
        base = {
            "schema_version": "rei-native-conscious-interpretation-input-v1",
            "source_scene_id": mandate_view.source_scene_id,
            "source_mandate_view_id": mandate_view.mandate_view_id,
            "source_mandate_view_hash": mandate_view.content_hash(),
            "request": request,
            "interpretation": interpretation,
            "acceptance_state_id": acceptance_state.acceptance_state_id,
            "acceptance_state_hash": acceptance_state.content_hash(),
        }
        input_id = content_id("conscious_interpretation_input", base)
        payload = {"interpretation_input_id": input_id, **base}
        return cls(**payload, input_hash=sha256_hex(payload)).validate_against(
            mandate_view=mandate_view,
            acceptance_state=acceptance_state,
        )

    @model_validator(mode="after")
    def validate_input(self) -> Self:
        self.interpretation.validate_against_request(self.request)
        if self.interpretation.source_mind != self.request.source_mind:
            raise ValueError("Conscious interpretation source mind differs")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"interpretation_input_id", "input_hash"},
        )
        if self.interpretation_input_id != content_id(
            "conscious_interpretation_input", base
        ):
            raise ValueError("interpretation_input_id does not match canonical content")
        payload = {"interpretation_input_id": self.interpretation_input_id, **base}
        if self.input_hash != sha256_hex(payload):
            raise ValueError("Conscious interpretation input hash differs")
        return self

    def validate_against(
        self,
        *,
        mandate_view: ConsciousMandateView,
        acceptance_state: AcceptanceState,
    ) -> Self:
        if (
            self.source_scene_id != mandate_view.source_scene_id
            or self.source_mandate_view_id != mandate_view.mandate_view_id
            or self.source_mandate_view_hash != mandate_view.content_hash()
        ):
            raise ValueError("Conscious interpretation belongs to another conscious cycle")
        if (
            self.acceptance_state_id != acceptance_state.acceptance_state_id
            or self.acceptance_state_hash != acceptance_state.content_hash()
            or self.request.acceptance_state_id != acceptance_state.acceptance_state_id
            or self.request.acceptance_state_hash != acceptance_state.content_hash()
        ):
            raise ValueError("Conscious interpretation belongs to another AcceptanceState")
        expected_manifestations = tuple(
            CommunicationArtifactRef(
                artifact_id=item.manifestation_id,
                artifact_hash=item.manifestation_hash,
            )
            for item in mandate_view.observable_manifestations
            if item.source_mind == self.request.source_mind
        )
        if (
            not expected_manifestations
            or self.request.source_manifestation_hashes != expected_manifestations
        ):
            raise ValueError(
                "Conscious interpretation manifestations differ from the current cycle"
            )
        return self


def _interpretation_refs(
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
) -> tuple[InterpretationLineageRef, ...]:
    by_mind = {
        item.interpretation.source_mind: item for item in interpretation_inputs
    }
    if len(by_mind) != len(interpretation_inputs):
        raise ValueError("At most one Racio interpretation per source mind is allowed")
    if any(
        item.interpretation.interpretation_status == "unverified_contract"
        for item in interpretation_inputs
    ):
        raise ValueError("B10 accepts only lineage-complete B9 interpretations")
    return tuple(
        InterpretationLineageRef(
            source_mind=mind,
            source_scene_id=by_mind[mind].source_scene_id,
            interpretation_input_id=by_mind[mind].interpretation_input_id,
            interpretation_input_hash=by_mind[mind].content_hash(),
            interpretation_id=by_mind[mind].interpretation.interpretation_id,
            interpretation_hash=by_mind[mind].interpretation.content_hash(),
            source_request_id=by_mind[mind].request.request_id,
            source_request_hash=by_mind[mind].request.content_hash(),
        )
        for mind in _INTERPRETED_MIND_ORDER
        if mind in by_mind
    )


def _conscious_manifestation_refs(
    *,
    bundle: NativeMindBundle,
    manifestations: tuple[EmocioManifestation | InstinktManifestation, ...],
) -> tuple[ConsciousManifestationRef, ...]:
    refs: list[ConsciousManifestationRef] = []
    for manifestation in manifestations:
        if isinstance(manifestation, EmocioManifestation):
            source_mind: Literal["E", "I"] = "E"
            conclusion = bundle.emocio
        elif isinstance(manifestation, InstinktManifestation):
            source_mind = "I"
            conclusion = bundle.instinkt
        else:
            raise TypeError("Conscious view accepts only E/I manifestation artifacts")
        if (
            manifestation.source_conclusion_id != conclusion.conclusion_id
            or manifestation.source_conclusion_hash != conclusion.content_hash()
        ):
            raise ValueError("Conscious manifestation belongs to another native bundle")
        refs.append(
            ConsciousManifestationRef(
                source_mind=source_mind,
                manifestation_id=manifestation.manifestation_id,
                manifestation_hash=manifestation.content_hash(),
            )
        )
    refs.sort(
        key=lambda item: (
            _INTERPRETED_MIND_ORDER.index(item.source_mind),
            item.manifestation_id,
        )
    )
    minds = tuple(item.source_mind for item in refs)
    if len(set(minds)) != len(minds):
        raise ValueError("At most one current-cycle manifestation per E/I mind is allowed")
    return tuple(refs)


class ConsciousMandateView(FrozenArtifactModel):
    """Consciously available governance data with hidden native motives removed."""

    schema_version: Literal["rei-native-conscious-mandate-view-v1"] = (
        "rei-native-conscious-mandate-view-v1"
    )
    mandate_view_id: NonEmptyId
    source_scene_id: NonEmptyId
    source_racio_conclusion_id: NonEmptyId
    source_racio_conclusion_hash: HashDigest
    status: GovernanceStatus
    structural_source_minds: tuple[MindId, ...]
    option_id: NonEmptyId | None = None
    objections: tuple[MindStatement, ...] = ()
    delegation: TaskDelegation | None = None
    observable_manifestations: tuple[ConsciousManifestationRef, ...] = ()
    view_hash: HashDigest

    @classmethod
    def create_b10(
        cls,
        *,
        governance: GovernanceResolution,
        bundle: NativeMindBundle,
        manifestations: tuple[EmocioManifestation | InstinktManifestation, ...],
    ) -> ConsciousMandateView:
        """Project a cycle mandate without exposing hidden-dependent fingerprints."""

        if (
            governance.native_bundle_id != bundle.bundle_id
            or governance.native_bundle_hash != bundle.immutable_hash
        ):
            raise ValueError("Governance resolution belongs to another native bundle")
        mandate = governance.mandate
        manifestation_refs = _conscious_manifestation_refs(
            bundle=bundle,
            manifestations=manifestations,
        )

        base = {
            "schema_version": "rei-native-conscious-mandate-view-v1",
            "source_scene_id": bundle.scene_id,
            "source_racio_conclusion_id": bundle.racio.conclusion_id,
            "source_racio_conclusion_hash": bundle.racio.content_hash(),
            "status": mandate.status,
            "structural_source_minds": mandate.structural_source_minds,
            "option_id": mandate.option_id,
            "objections": mandate.objections,
            "delegation": mandate.delegation,
            "observable_manifestations": manifestation_refs,
        }
        view_id = content_id("conscious_mandate_view", base)
        payload = {"mandate_view_id": view_id, **base}
        return cls(**payload, view_hash=sha256_hex(payload)).validate_against(
            governance=governance,
            bundle=bundle,
            manifestations=manifestations,
        )

    @model_validator(mode="after")
    def validate_view(self) -> Self:
        if not self.structural_source_minds:
            raise ValueError("Conscious mandate view requires structural source minds")
        if self.structural_source_minds != _canonical_minds(
            self.structural_source_minds
        ):
            raise ValueError("Conscious mandate source minds must use R, E, I order")
        objection_minds = tuple(item.mind for item in self.objections)
        if len(set(objection_minds)) != len(objection_minds):
            raise ValueError("Conscious mandate objections must be unique by mind")
        if objection_minds != _canonical_minds(objection_minds):
            raise ValueError("Conscious mandate objections must use R, E, I order")
        if self.status == "delegated" and self.delegation is None:
            raise ValueError("A delegated conscious view requires delegation")
        if self.status != "delegated" and self.delegation is not None:
            raise ValueError("Delegation is only valid for a delegated conscious view")
        if self.status == "unresolved" and self.option_id is not None:
            raise ValueError("An unresolved conscious view cannot select an option")
        if (
            self.status in {"resolved", "functionally_overridden"}
            and self.option_id is None
        ):
            raise ValueError("A resolved conscious view requires an option")
        if (
            self.delegation is not None
            and self.delegation.option_id is not None
            and self.option_id != self.delegation.option_id
        ):
            raise ValueError("Delegation option must match the conscious mandate view")
        manifestation_minds = tuple(
            item.source_mind for item in self.observable_manifestations
        )
        if len(set(manifestation_minds)) != len(manifestation_minds):
            raise ValueError("Conscious manifestations must be unique by mind")
        expected_manifestation_minds = tuple(
            mind for mind in _INTERPRETED_MIND_ORDER if mind in manifestation_minds
        )
        if manifestation_minds != expected_manifestation_minds:
            raise ValueError("Conscious manifestations must use canonical E, I order")
        base = {
            "schema_version": self.schema_version,
            "source_scene_id": self.source_scene_id,
            "source_racio_conclusion_id": self.source_racio_conclusion_id,
            "source_racio_conclusion_hash": self.source_racio_conclusion_hash,
            "status": self.status,
            "structural_source_minds": self.structural_source_minds,
            "option_id": self.option_id,
            "objections": self.objections,
            "delegation": self.delegation,
            "observable_manifestations": self.observable_manifestations,
        }
        if self.mandate_view_id != content_id("conscious_mandate_view", base):
            raise ValueError("mandate_view_id does not match canonical content")
        payload = {"mandate_view_id": self.mandate_view_id, **base}
        if self.view_hash != sha256_hex(payload):
            raise ValueError("view_hash does not match canonical content")
        return self

    def validate_against(
        self,
        *,
        governance: GovernanceResolution,
        bundle: NativeMindBundle,
        manifestations: tuple[EmocioManifestation | InstinktManifestation, ...],
    ) -> Self:
        if (
            governance.native_bundle_id != bundle.bundle_id
            or governance.native_bundle_hash != bundle.immutable_hash
        ):
            raise ValueError("Conscious mandate sources do not share one native bundle")
        self.validate_governance_projection(
            governance=governance,
            bundle=bundle,
        )
        expected_refs = _conscious_manifestation_refs(
            bundle=bundle,
            manifestations=manifestations,
        )
        if self.observable_manifestations != expected_refs:
            raise ValueError("Conscious mandate view differs from current-cycle manifestations")
        return self

    def validate_governance_projection(
        self,
        *,
        governance: GovernanceResolution,
        bundle: NativeMindBundle,
    ) -> Self:
        """Validate the governance fields when manifestations are checked separately."""

        if (
            governance.native_bundle_id != bundle.bundle_id
            or governance.native_bundle_hash != bundle.immutable_hash
        ):
            raise ValueError("Conscious mandate sources do not share one native bundle")
        mandate = governance.mandate
        if (
            self.source_scene_id != bundle.scene_id
            or self.source_racio_conclusion_id != bundle.racio.conclusion_id
            or self.source_racio_conclusion_hash != bundle.racio.content_hash()
            or self.status != mandate.status
            or self.structural_source_minds != mandate.structural_source_minds
            or self.option_id != mandate.option_id
            or self.objections != mandate.objections
            or self.delegation != mandate.delegation
        ):
            raise ValueError("Conscious mandate view differs from its source mandate")
        return self


class ConsciousDecision(FrozenArtifactModel):
    """A conscious commitment made through Racio, not a governance mandate."""

    schema_version: Literal["rei-native-conscious-decision-v1"] = (
        "rei-native-conscious-decision-v1"
    )
    decision_id: NonEmptyId
    derivation_status: B10DerivationStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    source_mandate_view_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_mandate_view_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_scene_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_racio_conclusion_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_racio_conclusion_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_acceptance_state_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_acceptance_state_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_interpretations: tuple[InterpretationLineageRef, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    committer_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    committer_revision: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    committer_policy: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    committer_policy_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    applied_rule_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    policy_basis: Literal["implementation_hypothesis"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    made_by: Literal["R"] = "R"
    option_id: NonEmptyId | None = None
    declared_reason: str
    conscious_confidence: Score01
    aligned_with_governance_mandate: bool | None = None
    decision_status: ConsciousDecisionStatus
    decision_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @classmethod
    def create_b10(
        cls,
        *,
        mandate_view: ConsciousMandateView,
        racio_conclusion: RacioNativeConclusion,
        acceptance_state: AcceptanceState,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
        option_id: NonEmptyId | None,
        declared_reason: str,
        conscious_confidence: Score01,
        decision_status: ConsciousDecisionStatus,
        committer_id: NonEmptyId,
        committer_revision: NonEmptyText,
        committer_policy: NonEmptyText,
        committer_policy_hash: HashDigest,
        applied_rule_id: NonEmptyId,
    ) -> ConsciousDecision:
        refs = _interpretation_refs(interpretation_inputs)
        alignment = (
            None
            if mandate_view.option_id is None or option_id is None
            else option_id == mandate_view.option_id
        )
        base = {
            "schema_version": "rei-native-conscious-decision-v1",
            "derivation_status": "derived_b10",
            "source_mandate_view_id": mandate_view.mandate_view_id,
            "source_mandate_view_hash": mandate_view.content_hash(),
            "source_scene_id": mandate_view.source_scene_id,
            "source_racio_conclusion_id": racio_conclusion.conclusion_id,
            "source_racio_conclusion_hash": racio_conclusion.content_hash(),
            "source_acceptance_state_id": acceptance_state.acceptance_state_id,
            "source_acceptance_state_hash": acceptance_state.content_hash(),
            "committer_id": committer_id,
            "committer_revision": committer_revision,
            "committer_policy": committer_policy,
            "committer_policy_hash": committer_policy_hash,
            "applied_rule_id": applied_rule_id,
            "policy_basis": "implementation_hypothesis",
            "made_by": "R",
            "option_id": option_id,
            "declared_reason": declared_reason,
            "conscious_confidence": conscious_confidence,
            "aligned_with_governance_mandate": alignment,
            "decision_status": decision_status,
        }
        if refs:
            base["source_interpretations"] = refs
        decision_id = content_id("conscious_decision", base)
        payload = {"decision_id": decision_id, **base}
        decision = cls(**payload, decision_hash=sha256_hex(payload))
        return decision.validate_against(
            mandate_view=mandate_view,
            racio_conclusion=racio_conclusion,
            acceptance_state=acceptance_state,
            interpretation_inputs=interpretation_inputs,
        )

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if (
            self.derivation_status == "derived_b10"
            and self.decision_status == "committed"
            and self.option_id is None
        ):
            raise ValueError("A committed conscious decision requires an option")
        if (
            self.derivation_status == "derived_b10"
            and self.decision_status != "committed"
            and self.option_id is not None
        ):
            raise ValueError("A non-committed B10 decision cannot select an option")
        if (
            self.derivation_status == "derived_b10"
            and self.committer_policy == "b10-conscious-commit-table-v1"
            and self.committer_revision == "1"
        ):
            canonical_statuses = {
                "unknown_or_non_actionable": "deferred",
                "accepting_actionable": "committed",
                "mixed_recognized_or_r_led": "committed",
                "mixed_unrecognized_with_racio_option": "committed",
                "mixed_unrecognized_without_racio_option": "deferred",
                "conflicted_with_racio_option": "committed",
                "conflicted_without_racio_option": "blocked",
            }
            if self.applied_rule_id not in canonical_statuses:
                raise ValueError("Unknown canonical B10 commitment rule")
            if self.decision_status != canonical_statuses[self.applied_rule_id]:
                raise ValueError("Decision status differs from canonical B10 rule")
        minds = tuple(item.source_mind for item in self.source_interpretations)
        if len(set(minds)) != len(minds):
            raise ValueError("Decision interpretation lineage must be unique by mind")
        expected_minds = tuple(mind for mind in _INTERPRETED_MIND_ORDER if mind in minds)
        if minds != expected_minds:
            raise ValueError("Decision interpretations must use canonical E, I order")
        lineage = (
            self.source_mandate_view_id,
            self.source_mandate_view_hash,
            self.source_scene_id,
            self.source_racio_conclusion_id,
            self.source_racio_conclusion_hash,
            self.source_acceptance_state_id,
            self.source_acceptance_state_hash,
            self.committer_id,
            self.committer_revision,
            self.committer_policy,
            self.committer_policy_hash,
            self.applied_rule_id,
            self.policy_basis,
            self.decision_hash,
        )
        if self.derivation_status == "unverified_contract":
            if any(value is not None for value in lineage) or self.source_interpretations:
                raise ValueError("Legacy conscious decision cannot claim B10 lineage")
            return self
        if any(value is None for value in lineage):
            raise ValueError("B10 conscious decision requires complete lineage")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"decision_id", "decision_hash"},
        )
        if self.decision_id != content_id("conscious_decision", base):
            raise ValueError("decision_id does not match canonical content")
        payload = {"decision_id": self.decision_id, **base}
        if self.decision_hash != sha256_hex(payload):
            raise ValueError("decision_hash does not match canonical content")
        return self

    def validate_against(
        self,
        *,
        mandate_view: ConsciousMandateView,
        racio_conclusion: RacioNativeConclusion,
        acceptance_state: AcceptanceState,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    ) -> Self:
        expected_refs = _interpretation_refs(interpretation_inputs)
        required_minds = (
            set()
            if "R" in mandate_view.structural_source_minds
            else set(mandate_view.structural_source_minds).intersection({"E", "I"})
        )
        provided_minds = {item.source_mind for item in expected_refs}
        missing_minds = required_minds - provided_minds
        if missing_minds:
            raise ValueError(
                "E/I-led conscious decision requires typed B9 interpretation "
                f"lineage for: {', '.join(sorted(missing_minds))}"
            )
        if (
            self.source_mandate_view_id != mandate_view.mandate_view_id
            or self.source_mandate_view_hash != mandate_view.content_hash()
            or self.source_scene_id != mandate_view.source_scene_id
        ):
            raise ValueError("Conscious decision cites another governance mandate")
        if (
            self.source_racio_conclusion_id != racio_conclusion.conclusion_id
            or self.source_racio_conclusion_hash != racio_conclusion.content_hash()
            or mandate_view.source_racio_conclusion_id != racio_conclusion.conclusion_id
            or mandate_view.source_racio_conclusion_hash != racio_conclusion.content_hash()
            or mandate_view.source_scene_id != racio_conclusion.source_scene_id
        ):
            raise ValueError("Conscious decision cites another Racio conclusion")
        if (
            self.source_acceptance_state_id != acceptance_state.acceptance_state_id
            or self.source_acceptance_state_hash != acceptance_state.content_hash()
        ):
            raise ValueError("Conscious decision cites another AcceptanceState")
        if self.source_interpretations != expected_refs:
            raise ValueError("Conscious decision interpretation lineage differs")
        for item in interpretation_inputs:
            item.validate_against(
                mandate_view=mandate_view,
                acceptance_state=acceptance_state,
            )
        expected_alignment = (
            None
            if mandate_view.option_id is None or self.option_id is None
            else self.option_id == mandate_view.option_id
        )
        if self.aligned_with_governance_mandate != expected_alignment:
            raise ValueError("Conscious decision governance alignment is not derived")
        allowed_options = {
            option
            for option in (
                mandate_view.option_id,
                racio_conclusion.option_id,
            )
            if option is not None
        }
        if self.option_id is not None and self.option_id not in allowed_options:
            raise ValueError("Conscious decision selected an option outside its inputs")
        if (
            self.committer_policy == "b10-conscious-commit-table-v1"
            and self.committer_revision == "1"
        ):
            if self.applied_rule_id in {
                "accepting_actionable",
                "mixed_recognized_or_r_led",
            }:
                expected_option = mandate_view.option_id
            elif self.applied_rule_id in {
                "mixed_unrecognized_with_racio_option",
                "conflicted_with_racio_option",
            }:
                expected_option = racio_conclusion.option_id
            else:
                expected_option = None
            if self.option_id != expected_option:
                raise ValueError("Decision option differs from canonical B10 rule")
        return self


class RacioSelfNarrative(FrozenArtifactModel):
    """A downstream self-narrative that cannot mutate decision or behavior."""

    schema_version: Literal["rei-native-racio-self-narrative-v1"] = (
        "rei-native-racio-self-narrative-v1"
    )
    narrative_id: NonEmptyId
    derivation_status: B10DerivationStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    source_mandate_view_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_mandate_view_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_decision_id: NonEmptyId
    source_decision_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_resultant_id: NonEmptyId | None = None
    source_resultant_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_interpretations: tuple[InterpretationLineageRef, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    narrator_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    narrator_revision: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    narrator_policy: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    narrator_policy_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    policy_basis: Literal["implementation_hypothesis"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    explanation: str
    claimed_motive: str
    acknowledged_minds: tuple[MindId, ...] = ()
    omitted_minds: tuple[MindId, ...] = ()
    uncertainty: str
    narrative_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @classmethod
    def create_b10(
        cls,
        *,
        mandate_view: ConsciousMandateView,
        decision: ConsciousDecision,
        resultant: BehaviorResultant,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
        explanation: str,
        claimed_motive: str,
        acknowledged_minds: tuple[MindId, ...],
        omitted_minds: tuple[MindId, ...],
        uncertainty: str,
        narrator_id: NonEmptyId,
        narrator_revision: NonEmptyText,
        narrator_policy: NonEmptyText,
        narrator_policy_hash: HashDigest,
    ) -> RacioSelfNarrative:
        refs = _interpretation_refs(interpretation_inputs)
        if refs != decision.source_interpretations:
            raise ValueError("Narrative inputs differ from the decision interpretations")
        base = {
            "schema_version": "rei-native-racio-self-narrative-v1",
            "derivation_status": "derived_b10",
            "source_mandate_view_id": mandate_view.mandate_view_id,
            "source_mandate_view_hash": mandate_view.content_hash(),
            "source_decision_id": decision.decision_id,
            "source_decision_hash": decision.content_hash(),
            "source_resultant_id": resultant.resultant_id,
            "source_resultant_hash": resultant.content_hash(),
            "narrator_id": narrator_id,
            "narrator_revision": narrator_revision,
            "narrator_policy": narrator_policy,
            "narrator_policy_hash": narrator_policy_hash,
            "policy_basis": "implementation_hypothesis",
            "explanation": explanation,
            "claimed_motive": claimed_motive,
            "acknowledged_minds": acknowledged_minds,
            "omitted_minds": omitted_minds,
            "uncertainty": uncertainty,
        }
        if refs:
            base["source_interpretations"] = refs
        narrative_id = content_id("racio_self_narrative", base)
        payload = {"narrative_id": narrative_id, **base}
        narrative = cls(**payload, narrative_hash=sha256_hex(payload))
        return narrative.validate_against(
            mandate_view=mandate_view,
            decision=decision,
            resultant=resultant,
            interpretation_inputs=interpretation_inputs,
        )

    @model_validator(mode="after")
    def validate_narrative(self) -> Self:
        if len(set(self.acknowledged_minds)) != len(self.acknowledged_minds):
            raise ValueError("acknowledged_minds must be unique")
        if len(set(self.omitted_minds)) != len(self.omitted_minds):
            raise ValueError("omitted_minds must be unique")
        overlap = set(self.acknowledged_minds) & set(self.omitted_minds)
        if overlap:
            raise ValueError("a mind cannot be both acknowledged and omitted")
        if self.derivation_status == "derived_b10":
            if self.acknowledged_minds != _canonical_minds(self.acknowledged_minds):
                raise ValueError("acknowledged_minds must use canonical R, E, I order")
            if self.omitted_minds != _canonical_minds(self.omitted_minds):
                raise ValueError("omitted_minds must use canonical R, E, I order")
        minds = tuple(item.source_mind for item in self.source_interpretations)
        if len(set(minds)) != len(minds):
            raise ValueError("Narrative interpretation lineage must be unique by mind")
        lineage = (
            self.source_mandate_view_id,
            self.source_mandate_view_hash,
            self.source_decision_hash,
            self.source_resultant_hash,
            self.narrator_id,
            self.narrator_revision,
            self.narrator_policy,
            self.narrator_policy_hash,
            self.policy_basis,
            self.narrative_hash,
        )
        if self.derivation_status == "unverified_contract":
            if any(value is not None for value in lineage) or self.source_interpretations:
                raise ValueError("Legacy narrative cannot claim B10 lineage")
            return self
        if self.source_resultant_id is None or any(value is None for value in lineage):
            raise ValueError("B10 narrative requires complete lineage")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"narrative_id", "narrative_hash"},
        )
        if self.narrative_id != content_id("racio_self_narrative", base):
            raise ValueError("narrative_id does not match canonical content")
        payload = {"narrative_id": self.narrative_id, **base}
        if self.narrative_hash != sha256_hex(payload):
            raise ValueError("narrative_hash does not match canonical content")
        return self

    def validate_against(
        self,
        *,
        mandate_view: ConsciousMandateView,
        decision: ConsciousDecision,
        resultant: BehaviorResultant,
        interpretation_inputs: tuple[ConsciousInterpretationInput, ...],
    ) -> Self:
        if (
            self.source_mandate_view_id != mandate_view.mandate_view_id
            or self.source_mandate_view_hash != mandate_view.content_hash()
        ):
            raise ValueError("Narrative cites another conscious mandate view")
        if (
            self.source_decision_id != decision.decision_id
            or self.source_decision_hash != decision.content_hash()
        ):
            raise ValueError("Narrative cites another conscious decision")
        if (
            self.source_resultant_id != resultant.resultant_id
            or self.source_resultant_hash != resultant.content_hash()
        ):
            raise ValueError("Narrative cites another behavior resultant")
        if self.source_interpretations != _interpretation_refs(interpretation_inputs):
            raise ValueError("Narrative interpretation lineage differs")
        if self.source_interpretations != decision.source_interpretations:
            raise ValueError("Narrative interpretations differ from its conscious decision")
        return self


class BehaviorResultant(FrozenArtifactModel):
    """Observable one-cycle behavior, separate from mandate and commitment."""

    schema_version: Literal["rei-native-behavior-resultant-v1"] = (
        "rei-native-behavior-resultant-v1"
    )
    resultant_id: NonEmptyId
    derivation_status: B10DerivationStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    source_mandate_view_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_mandate_view_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_scene_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_decision_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_decision_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_acceptance_state_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_acceptance_state_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    behavior_policy_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    behavior_policy_revision: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    behavior_policy_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    applied_rule_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    policy_basis: Literal["implementation_hypothesis"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    option_id: NonEmptyId | None = None
    status: BehaviorStatus
    governance_alignment: AlignmentStatus
    conscious_alignment: AlignmentStatus
    operational_controller: MindId | None = None
    residual_tensions: tuple[str, ...] = ()
    predicted_action: str
    resultant_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @classmethod
    def create_b10(
        cls,
        *,
        mandate_view: ConsciousMandateView,
        decision: ConsciousDecision,
        acceptance_state: AcceptanceState,
        behavior_policy_id: NonEmptyId,
        behavior_policy_revision: NonEmptyText,
        behavior_policy_hash: HashDigest,
        applied_rule_id: NonEmptyId,
        option_id: NonEmptyId | None,
        status: BehaviorStatus,
        operational_controller: MindId | None,
        residual_tensions: tuple[str, ...],
        predicted_action: str,
    ) -> BehaviorResultant:
        base = {
            "schema_version": "rei-native-behavior-resultant-v1",
            "derivation_status": "derived_b10",
            "source_mandate_view_id": mandate_view.mandate_view_id,
            "source_mandate_view_hash": mandate_view.content_hash(),
            "source_scene_id": mandate_view.source_scene_id,
            "source_decision_id": decision.decision_id,
            "source_decision_hash": decision.content_hash(),
            "source_acceptance_state_id": acceptance_state.acceptance_state_id,
            "source_acceptance_state_hash": acceptance_state.content_hash(),
            "behavior_policy_id": behavior_policy_id,
            "behavior_policy_revision": behavior_policy_revision,
            "behavior_policy_hash": behavior_policy_hash,
            "applied_rule_id": applied_rule_id,
            "policy_basis": "implementation_hypothesis",
            "option_id": option_id,
            "status": status,
            "governance_alignment": _alignment(option_id, mandate_view.option_id),
            "conscious_alignment": _alignment(option_id, decision.option_id),
            "operational_controller": operational_controller,
            "residual_tensions": residual_tensions,
            "predicted_action": predicted_action,
        }
        resultant_id = content_id("behavior_resultant", base)
        payload = {"resultant_id": resultant_id, **base}
        resultant = cls(**payload, resultant_hash=sha256_hex(payload))
        return resultant.validate_against(
            mandate_view=mandate_view,
            decision=decision,
            acceptance_state=acceptance_state,
            behavior_policy_id=behavior_policy_id,
            behavior_policy_revision=behavior_policy_revision,
            behavior_policy_hash=behavior_policy_hash,
        )

    @model_validator(mode="after")
    def validate_resultant(self) -> Self:
        if (
            self.derivation_status == "derived_b10"
            and self.status == "executed"
            and self.option_id is None
        ):
            raise ValueError("Executed behavior requires an option")
        if (
            self.derivation_status == "derived_b10"
            and self.status != "executed"
            and self.operational_controller is not None
        ):
            raise ValueError("Non-executed B10 behavior cannot assign a controller")
        if (
            self.derivation_status == "derived_b10"
            and self.behavior_policy_id == "b10-behavior-resolution-table-v1"
            and self.behavior_policy_revision == "1"
        ):
            canonical_statuses = {
                "unknown_or_non_actionable": "unresolved",
                "accepting_actionable": "executed",
                "mixed_recognized_or_r_led": "executed",
                "mixed_unrecognized_with_racio_option": "oscillating",
                "mixed_unrecognized_without_racio_option": "delayed",
                "conflicted_with_racio_option": "sabotaged",
                "conflicted_without_racio_option": "blocked",
            }
            if self.applied_rule_id not in canonical_statuses:
                raise ValueError("Unknown canonical B10 behavior rule")
            if self.status != canonical_statuses[self.applied_rule_id]:
                raise ValueError("Behavior status differs from canonical B10 rule")
        lineage = (
            self.source_mandate_view_id,
            self.source_mandate_view_hash,
            self.source_scene_id,
            self.source_decision_id,
            self.source_decision_hash,
            self.source_acceptance_state_id,
            self.source_acceptance_state_hash,
            self.behavior_policy_id,
            self.behavior_policy_revision,
            self.behavior_policy_hash,
            self.applied_rule_id,
            self.policy_basis,
            self.resultant_hash,
        )
        if self.derivation_status == "unverified_contract":
            if any(value is not None for value in lineage):
                raise ValueError("Legacy behavior resultant cannot claim B10 lineage")
            return self
        if any(value is None for value in lineage):
            raise ValueError("B10 behavior resultant requires complete lineage")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"resultant_id", "resultant_hash"},
        )
        if self.resultant_id != content_id("behavior_resultant", base):
            raise ValueError("resultant_id does not match canonical content")
        payload = {"resultant_id": self.resultant_id, **base}
        if self.resultant_hash != sha256_hex(payload):
            raise ValueError("resultant_hash does not match canonical content")
        return self

    def validate_against(
        self,
        *,
        mandate_view: ConsciousMandateView,
        decision: ConsciousDecision,
        acceptance_state: AcceptanceState,
        behavior_policy_id: str,
        behavior_policy_revision: str,
        behavior_policy_hash: str,
    ) -> Self:
        if (
            self.source_mandate_view_id != mandate_view.mandate_view_id
            or self.source_mandate_view_hash != mandate_view.content_hash()
            or self.source_scene_id != mandate_view.source_scene_id
        ):
            raise ValueError("Behavior resultant cites another governance mandate")
        if (
            self.source_decision_id != decision.decision_id
            or self.source_decision_hash != decision.content_hash()
        ):
            raise ValueError("Behavior resultant cites another conscious decision")
        if self.applied_rule_id != decision.applied_rule_id:
            raise ValueError("Behavior rule differs from its conscious decision rule")
        if (
            self.source_acceptance_state_id != acceptance_state.acceptance_state_id
            or self.source_acceptance_state_hash != acceptance_state.content_hash()
        ):
            raise ValueError("Behavior resultant cites another AcceptanceState")
        if (
            self.behavior_policy_id != behavior_policy_id
            or self.behavior_policy_revision != behavior_policy_revision
            or self.behavior_policy_hash != behavior_policy_hash
        ):
            raise ValueError("Behavior resultant cites another rule table")
        if self.governance_alignment != _alignment(
            self.option_id, mandate_view.option_id
        ):
            raise ValueError("Behavior governance alignment is not derived")
        if self.conscious_alignment != _alignment(self.option_id, decision.option_id):
            raise ValueError("Behavior conscious alignment is not derived")
        expected_controller: MindId | None = None
        if self.status == "executed":
            if mandate_view.delegation is not None:
                expected_controller = mandate_view.delegation.delegate_mind
            elif len(mandate_view.structural_source_minds) == 1:
                expected_controller = mandate_view.structural_source_minds[0]
        if self.operational_controller != expected_controller:
            raise ValueError("Behavior operational controller is not derived")
        return self


__all__ = [
    "AlignmentStatus",
    "B10DerivationStatus",
    "BehaviorResultant",
    "BehaviorStatus",
    "ConsciousDecision",
    "ConsciousDecisionStatus",
    "ConsciousInterpretationInput",
    "ConsciousManifestationRef",
    "ConsciousMandateView",
    "InterpretationLineageRef",
    "RacioSelfNarrative",
]
