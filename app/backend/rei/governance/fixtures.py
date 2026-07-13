"""Canonical, synthetic governance fixture contracts.

The expectations in this module are a deliberately independent oracle for the
finite B3 governance truth table.  They never import or call the runtime profile
parser or governance resolver.  The only shared profile datum is the canonical
ordered profile tuple owned by :mod:`rei.models.character`.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, NamedTuple, Self

from pydantic import Field, model_validator

from ..models.character import CHARACTER_PROFILE_ORDER, CharacterProfileId
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    MindId,
    NonEmptyId,
    NonEmptyText,
)
from ..models.emocio import EmocioInputPacket, EmocioVisualState
from ..models.instinkt import BodyState, InstinktInputPacket, InstinktOptionRollout
from ..models.racio import RacioInputPacket
from ..models.run import NativeMindBundle
from ..models.scene import SceneEvent


LogicPattern = Literal["AAA", "RE_I", "RI_E", "EI_R", "ABC"]
ExpectedGovernanceStatus = Literal["resolved", "unresolved"]
ExpectedPairStatus = Literal["resolved", "unresolved"]
ExpectedSpoznanjeStatus = Literal[
    "simulated_spoznanje",
    "partial_agreement",
    "no_spoznanje",
]
NativeReasonSourceField = Literal[
    "explicit_goal",
    "desired_transformation",
    "minimum_safety_condition",
]


class NativeReasonExpectation(FrozenModel):
    """One modality-native reason preserved by a synthetic fixture."""

    mind: MindId
    source_field: NativeReasonSourceField
    reason: NonEmptyText

    @model_validator(mode="after")
    def validate_source_field(self) -> Self:
        expected_field = {
            "R": "explicit_goal",
            "E": "desired_transformation",
            "I": "minimum_safety_condition",
        }[self.mind]
        if self.source_field != expected_field:
            raise ValueError("Native reason source field must match its mind modality")
        return self


class ExpectedProfileOutcome(FrozenModel):
    """Independent expected governance outcome for one canonical profile."""

    profile_id: CharacterProfileId
    status: ExpectedGovernanceStatus
    option_id: NonEmptyId | None
    source_minds: tuple[MindId, ...] = Field(min_length=1)
    pair_status: ExpectedPairStatus | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if len(set(self.source_minds)) != len(self.source_minds):
            raise ValueError("Expected source minds must be unique")
        canonical_sources = tuple(
            mind for mind in ("R", "E", "I") if mind in set(self.source_minds)
        )
        if self.source_minds != canonical_sources:
            raise ValueError("Expected source minds must use canonical R, E, I order")
        if self.status == "resolved" and self.option_id is None:
            raise ValueError("A resolved fixture outcome requires an option")
        if self.status == "unresolved" and self.option_id is not None:
            raise ValueError("An unresolved fixture outcome cannot select an option")
        if self.pair_status == "resolved" and self.status != "resolved":
            raise ValueError("A resolved top pair must yield a resolved outcome")
        if self.pair_status == "unresolved" and self.status != "unresolved":
            raise ValueError("An unresolved top pair must yield an unresolved outcome")
        return self


class _OutcomeBlueprint(NamedTuple):
    status: ExpectedGovernanceStatus
    option_from: MindId | None
    source_minds: tuple[MindId, ...]
    pair_status: ExpectedPairStatus | None


def _resolved(
    option_from: MindId,
    source_minds: tuple[MindId, ...],
    pair_status: ExpectedPairStatus | None = None,
) -> _OutcomeBlueprint:
    return _OutcomeBlueprint("resolved", option_from, source_minds, pair_status)


def _unresolved(
    source_minds: tuple[MindId, ...],
    pair_status: ExpectedPairStatus | None = None,
) -> _OutcomeBlueprint:
    return _OutcomeBlueprint("unresolved", None, source_minds, pair_status)


# Each tuple follows CHARACTER_PROFILE_ORDER.  This is an explicit 5 x 13
# truth-table oracle, not an implementation of the runtime resolver.
_TRUTH_TABLE: Final = MappingProxyType(
    {
        "AAA": (
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _resolved("R", ("R", "E"), "resolved"),
            _resolved("R", ("R", "I"), "resolved"),
            _resolved("E", ("E", "I"), "resolved"),
            _resolved("R", ("R",)),
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _resolved("I", ("I",)),
            _resolved("R", ("R", "E", "I")),
        ),
        "RE_I": (
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _resolved("R", ("R", "E"), "resolved"),
            _unresolved(("R", "I"), "unresolved"),
            _unresolved(("E", "I"), "unresolved"),
            _resolved("R", ("R",)),
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _resolved("I", ("I",)),
            _resolved("R", ("R", "E")),
        ),
        "RI_E": (
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _unresolved(("R", "E"), "unresolved"),
            _resolved("R", ("R", "I"), "resolved"),
            _unresolved(("E", "I"), "unresolved"),
            _resolved("R", ("R",)),
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _resolved("I", ("I",)),
            _resolved("R", ("R", "I")),
        ),
        "EI_R": (
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _unresolved(("R", "E"), "unresolved"),
            _unresolved(("R", "I"), "unresolved"),
            _resolved("E", ("E", "I"), "resolved"),
            _resolved("R", ("R",)),
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _resolved("I", ("I",)),
            _resolved("E", ("E", "I")),
        ),
        "ABC": (
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _unresolved(("R", "E"), "unresolved"),
            _unresolved(("R", "I"), "unresolved"),
            _unresolved(("E", "I"), "unresolved"),
            _resolved("R", ("R",)),
            _resolved("R", ("R",)),
            _resolved("E", ("E",)),
            _resolved("E", ("E",)),
            _resolved("I", ("I",)),
            _resolved("I", ("I",)),
            _unresolved(("R", "E", "I")),
        ),
    }
)

_SPOZNANJE_BY_PATTERN: Final = MappingProxyType(
    {
        "AAA": (True, "simulated_spoznanje"),
        "RE_I": (False, "partial_agreement"),
        "RI_E": (False, "partial_agreement"),
        "EI_R": (False, "partial_agreement"),
        "ABC": (False, "no_spoznanje"),
    }
)


def classify_logic_pattern(bundle: NativeMindBundle) -> LogicPattern:
    """Classify three non-abstaining native option IDs into one truth-table row."""

    r_option = bundle.racio.option_id
    e_option = bundle.emocio.option_id
    i_option = bundle.instinkt.option_id
    if r_option is None or e_option is None or i_option is None:
        raise ValueError("Canonical governance fixtures require three non-null options")
    if r_option == e_option == i_option:
        return "AAA"
    if r_option == e_option:
        return "RE_I"
    if r_option == i_option:
        return "RI_E"
    if e_option == i_option:
        return "EI_R"
    return "ABC"


def canonical_expected_profile_outcomes(
    logic_pattern: LogicPattern,
    option_by_mind: dict[MindId, NonEmptyId],
) -> tuple[ExpectedProfileOutcome, ...]:
    """Materialize the independent oracle for fixture-specific option IDs."""

    if set(option_by_mind) != {"R", "E", "I"}:
        raise ValueError("The fixture oracle requires exactly R, E, and I options")
    blueprints = _TRUTH_TABLE[logic_pattern]
    if len(blueprints) != len(CHARACTER_PROFILE_ORDER):
        raise RuntimeError("Fixture truth table no longer matches canonical profile order")
    return tuple(
        ExpectedProfileOutcome(
            profile_id=profile_id,
            status=blueprint.status,
            option_id=(
                option_by_mind[blueprint.option_from]
                if blueprint.option_from is not None
                else None
            ),
            source_minds=blueprint.source_minds,
            pair_status=blueprint.pair_status,
        )
        for profile_id, blueprint in zip(
            CHARACTER_PROFILE_ORDER,
            blueprints,
            strict=True,
        )
    )


def load_governance_fixture(path: Path) -> "CanonicalGovernanceFixture":
    """Load and strictly validate one checked-in canonical fixture."""

    return CanonicalGovernanceFixture.model_validate_json(
        path.read_text(encoding="utf-8")
    )


class CanonicalGovernanceFixture(FrozenArtifactModel):
    """One full-lineage synthetic bundle and its explicit B3 expectations."""

    schema_version: Literal["rei-native-governance-fixture-v1"] = (
        "rei-native-governance-fixture-v1"
    )
    fixture_id: NonEmptyId
    fixture_status: Literal["synthetic_architecture_fixture"] = (
        "synthetic_architecture_fixture"
    )
    normative_scope: Literal["governance_only"] = "governance_only"
    description: NonEmptyText
    logic_pattern: LogicPattern
    scene: SceneEvent
    racio_packet: RacioInputPacket
    emocio_packet: EmocioInputPacket
    instinkt_packet: InstinktInputPacket
    emocio_visual_state: EmocioVisualState
    instinkt_body_state: BodyState
    instinkt_rollouts: tuple[InstinktOptionRollout, ...] = Field(min_length=1)
    native_bundle: NativeMindBundle
    expected_native_reasons: tuple[NativeReasonExpectation, ...] = Field(
        min_length=3,
        max_length=3,
    )
    expected_profile_outcomes: tuple[ExpectedProfileOutcome, ...] = Field(
        min_length=13,
        max_length=13,
    )
    open_question_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    expected_spoznanje: bool
    expected_spoznanje_status: ExpectedSpoznanjeStatus

    @model_validator(mode="after")
    def validate_fixture_contract(self) -> Self:
        if not self.scene.evidence:
            raise ValueError("Canonical fixtures require grounded scene evidence")
        if any(
            not evidence.grounded or evidence.provenance_kind != "supplied"
            for evidence in self.scene.evidence
        ):
            raise ValueError("Canonical fixture evidence must be supplied and grounded")

        self.native_bundle.validate_native_lineage(
            scene=self.scene,
            racio_packet=self.racio_packet,
            emocio_packet=self.emocio_packet,
            instinkt_packet=self.instinkt_packet,
            emocio_visual_state=self.emocio_visual_state,
            instinkt_body_state=self.instinkt_body_state,
            instinkt_rollouts=self.instinkt_rollouts,
        )
        conclusions = (
            self.native_bundle.racio,
            self.native_bundle.emocio,
            self.native_bundle.instinkt,
        )
        if tuple(conclusion.mind for conclusion in conclusions) != ("R", "E", "I"):
            raise ValueError("A canonical bundle must contain exactly R, E, and I conclusions")
        conclusion_ids = tuple(conclusion.conclusion_id for conclusion in conclusions)
        if len(set(conclusion_ids)) != 3:
            raise ValueError("Canonical native conclusions must have distinct IDs")

        actual_pattern = classify_logic_pattern(self.native_bundle)
        if self.logic_pattern != actual_pattern:
            raise ValueError("Fixture logic_pattern does not match native conclusion options")

        reason_minds = tuple(item.mind for item in self.expected_native_reasons)
        if reason_minds != ("R", "E", "I"):
            raise ValueError("Native reason expectations must use exact R, E, I order")
        expected_reason_values = {
            "R": self.native_bundle.racio.explicit_goal,
            "E": self.native_bundle.emocio.desired_transformation,
            "I": self.native_bundle.instinkt.minimum_safety_condition,
        }
        for expectation in self.expected_native_reasons:
            if expectation.reason != expected_reason_values[expectation.mind]:
                raise ValueError("Expected native reason differs from its frozen conclusion")

        option_by_mind: dict[MindId, NonEmptyId] = {
            "R": self.native_bundle.racio.option_id,
            "E": self.native_bundle.emocio.option_id,
            "I": self.native_bundle.instinkt.option_id,
        }
        expected_outcomes = canonical_expected_profile_outcomes(
            self.logic_pattern,
            option_by_mind,
        )
        if self.expected_profile_outcomes != expected_outcomes:
            raise ValueError("Explicit profile outcomes differ from the independent oracle")

        if len(set(self.open_question_ids)) != len(self.open_question_ids):
            raise ValueError("Fixture open question IDs must be unique")
        if any(not question_id.startswith("OQ-") for question_id in self.open_question_ids):
            raise ValueError("Fixture open question IDs must use the OQ- prefix")

        expected_spoznanje, expected_status = _SPOZNANJE_BY_PATTERN[
            self.logic_pattern
        ]
        if (
            self.expected_spoznanje != expected_spoznanje
            or self.expected_spoznanje_status != expected_status
        ):
            raise ValueError("Spoznanje expectation differs from the logic pattern")
        return self


__all__ = [
    "CanonicalGovernanceFixture",
    "ExpectedGovernanceStatus",
    "ExpectedPairStatus",
    "ExpectedProfileOutcome",
    "ExpectedSpoznanjeStatus",
    "LogicPattern",
    "NativeReasonExpectation",
    "NativeReasonSourceField",
    "canonical_expected_profile_outcomes",
    "classify_logic_pattern",
    "load_governance_fixture",
]
