"""Parallel v2 contract for epistemically bounded Racio interpretation.

The frozen C3 v1 packet, output, prompt, provider, and evidence remain separate.
This module exposes a sanitized development packet and an output that keeps
action, option, and motive hypotheses epistemically distinct.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Literal, Mapping, Self

from pydantic import model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from .conscious_access import ConsciousAccessObservation, ConsciousAccessOption
from .structured_interpreter import InterpreterActionTendency


MotiveFamily = Literal["scene", "motor_social", "protection"]
SceneMotiveSubtype = Literal[
    "desired_scene_absent",
    "desired_scene_mismatch",
    "broken_scene",
    "recurrent_broken_scene",
    "scene_realization",
    "scene_repair",
]
MotorSocialMotiveSubtype = Literal[
    "motor_execution",
    "connection",
    "competition",
    "attention_or_status",
]
ProtectionMotiveSubtype = Literal[
    "general_body_alarm",
    "boundary_alarm",
    "attachment_alarm",
    "resource_alarm",
    "trust_alarm",
    "escape_alarm",
]

MOTIVE_SUBTYPES_BY_FAMILY: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "scene": frozenset(
            {
                "desired_scene_absent",
                "desired_scene_mismatch",
                "broken_scene",
                "recurrent_broken_scene",
                "scene_realization",
                "scene_repair",
            }
        ),
        "motor_social": frozenset(
            {
                "motor_execution",
                "connection",
                "competition",
                "attention_or_status",
            }
        ),
        "protection": frozenset(
            {
                "general_body_alarm",
                "boundary_alarm",
                "attachment_alarm",
                "resource_alarm",
                "trust_alarm",
                "escape_alarm",
            }
        ),
    }
)

MotiveHypothesisExplanationSl = Literal[
    "Omejena hipoteza, ne dejstvo; podprta je le z navedenimi vidnimi opazkami."
]
MotiveUnknownReasonSl = Literal[
    "Vidne opazke ne določajo motiva."
]
UnresolvedAmbiguitySl = Literal[
    "Vidne opazke ne določajo ene javne možnosti.",
    "Vidne opazke podpirajo več konkurenčnih hipotez.",
    (
        "Vidne opazke ne določajo ene javne možnosti in podpirajo več "
        "konkurenčnih hipotez."
    ),
]

MOTIVE_HYPOTHESIS_EXPLANATION_SL: Final = (
    "Omejena hipoteza, ne dejstvo; podprta je le z navedenimi vidnimi opazkami."
)
MOTIVE_UNKNOWN_REASON_SL: Final = "Vidne opazke ne določajo motiva."
OPTION_AMBIGUITY_SL: Final = "Vidne opazke ne določajo ene javne možnosti."
MOTIVE_AMBIGUITY_SL: Final = (
    "Vidne opazke podpirajo več konkurenčnih hipotez."
)
OPTION_AND_MOTIVE_AMBIGUITY_SL: Final = (
    "Vidne opazke ne določajo ene javne možnosti in podpirajo več "
    "konkurenčnih hipotez."
)


def motive_subtype_belongs_to_family(family: str, subtype: str) -> bool:
    """Return whether one operational subtype belongs to its declared family."""

    return subtype in MOTIVE_SUBTYPES_BY_FAMILY.get(family, frozenset())


class MotiveHypothesis(FrozenModel):
    """One cited, explicitly hypothetical interpretation of visible signals."""

    family: MotiveFamily
    subtype: NonEmptyId
    cited_observation_ids: tuple[NonEmptyId, ...]
    confidence: Score01
    explanation_short_sl: MotiveHypothesisExplanationSl

    @property
    def key(self) -> tuple[str, str]:
        return (self.family, self.subtype)

    @model_validator(mode="after")
    def validate_hypothesis(self) -> Self:
        if not motive_subtype_belongs_to_family(self.family, self.subtype):
            raise ValueError("Motive subtype does not belong to its declared family")
        if not self.cited_observation_ids:
            raise ValueError(
                "A motive hypothesis requires visible observation citations"
            )
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("Motive citations must be sorted and unique")
        return self


class RacioEpistemicPacketV2(FrozenArtifactModel):
    """Sanitized provider-visible packet with no native or character lineage."""

    schema_version: Literal["rei-racio-epistemic-packet-v2"] = (
        "rei-racio-epistemic-packet-v2"
    )
    packet_id: NonEmptyId
    source_mind: Literal["E", "I"]
    language: LanguageCode
    visible_observations: tuple[ConsciousAccessObservation, ...] = ()
    omitted_observation_ids: tuple[NonEmptyId, ...] = ()
    degraded_observation_ids: tuple[NonEmptyId, ...] = ()
    public_option_scope: tuple[ConsciousAccessOption, ...] = ()
    channel_quality: Score01
    uncertainty: NonEmptyText
    packet_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        source_mind: Literal["E", "I"],
        language: LanguageCode,
        visible_observations: tuple[ConsciousAccessObservation, ...],
        omitted_observation_ids: tuple[NonEmptyId, ...],
        public_option_scope: tuple[ConsciousAccessOption, ...],
        channel_quality: Score01,
        uncertainty: NonEmptyText,
    ) -> "RacioEpistemicPacketV2":
        observations = tuple(
            sorted(visible_observations, key=lambda item: item.observation_id)
        )
        omitted = tuple(sorted(set(omitted_observation_ids)))
        options = tuple(sorted(public_option_scope, key=lambda item: item.option_id))
        degraded = tuple(
            item.observation_id
            for item in observations
            if item.perception_status == "degraded"
        )
        base = {
            "schema_version": "rei-racio-epistemic-packet-v2",
            "source_mind": source_mind,
            "language": language,
            "visible_observations": observations,
            "omitted_observation_ids": omitted,
            "degraded_observation_ids": degraded,
            "public_option_scope": options,
            "channel_quality": channel_quality,
            "uncertainty": uncertainty,
        }
        packet_id = content_id("racio_epistemic_packet", base)
        payload = {"packet_id": packet_id, **base}
        return cls(**payload, packet_hash=sha256_hex(payload))

    @property
    def visible_observation_ids(self) -> tuple[str, ...]:
        return tuple(item.observation_id for item in self.visible_observations)

    @property
    def public_option_ids(self) -> tuple[str, ...]:
        return tuple(item.option_id for item in self.public_option_scope)

    @model_validator(mode="after")
    def validate_packet(self) -> Self:
        visible_ids = self.visible_observation_ids
        if visible_ids != tuple(sorted(set(visible_ids))):
            raise ValueError("Visible observation aliases must be sorted and unique")
        if self.omitted_observation_ids != tuple(
            sorted(set(self.omitted_observation_ids))
        ):
            raise ValueError("Omitted observation aliases must be sorted and unique")
        if set(visible_ids).intersection(self.omitted_observation_ids):
            raise ValueError("Visible and omitted observation aliases must be disjoint")
        expected_degraded = tuple(
            item.observation_id
            for item in self.visible_observations
            if item.perception_status == "degraded"
        )
        if self.degraded_observation_ids != expected_degraded:
            raise ValueError("Degraded aliases must exactly match visible observations")
        if any(item.public_artifact_ids for item in self.visible_observations):
            raise ValueError("The text-only epistemic packet cannot expose artifacts")
        option_ids = self.public_option_ids
        if option_ids != tuple(sorted(set(option_ids))):
            raise ValueError("Public option aliases must be sorted and unique")
        id_payload = self.model_dump(
            mode="python", round_trip=True, exclude={"packet_id", "packet_hash"}
        )
        if self.packet_id != content_id("racio_epistemic_packet", id_payload):
            raise ValueError("Epistemic packet ID differs from sanitized content")
        if self.packet_hash != self.content_hash(
            exclude_fields=frozenset({"packet_hash"})
        ):
            raise ValueError("Epistemic packet hash differs from sanitized content")
        return self

    def provider_payload(self) -> dict[str, object]:
        """Return the complete and explicit v2 model boundary."""

        return {
            "schema_version": self.schema_version,
            "source_mind": self.source_mind,
            "language": self.language,
            "visible_observations": [
                item.model_dump(mode="json") for item in self.visible_observations
            ],
            "omitted_observation_ids": list(self.omitted_observation_ids),
            "degraded_observation_ids": list(self.degraded_observation_ids),
            "public_option_scope": [
                item.model_dump(mode="json") for item in self.public_option_scope
            ],
            "channel_quality": self.channel_quality,
            "uncertainty": self.uncertainty,
        }

    def provider_payload_bytes(self) -> bytes:
        return canonical_json_bytes(self.provider_payload())


class RacioEpistemicInterpretationV2(FrozenModel):
    """Structured interpretation with independent epistemic claim dimensions."""

    source_mind: Literal["E", "I"]
    cited_observation_ids: tuple[NonEmptyId, ...]
    inferred_action_tendency: InterpreterActionTendency
    action_confidence: Score01
    inferred_option_id: NonEmptyId | None
    option_confidence: Score01
    motive_hypotheses: tuple[MotiveHypothesis, ...]
    motive_unknown_reason: MotiveUnknownReasonSl | None
    unresolved_ambiguity: UnresolvedAmbiguitySl | None

    @model_validator(mode="after")
    def validate_canonical_output(self) -> Self:
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("Global observation citations must be sorted and unique")
        if len(self.motive_hypotheses) > 3:
            raise ValueError("At most three motive hypotheses are permitted")
        motive_keys = tuple(item.key for item in self.motive_hypotheses)
        if len(set(motive_keys)) != len(motive_keys):
            raise ValueError("Motive family/subtype combinations must be unique")
        expected_order = tuple(
            sorted(
                self.motive_hypotheses,
                key=lambda item: (-item.confidence, item.family, item.subtype),
            )
        )
        if self.motive_hypotheses != expected_order:
            raise ValueError(
                "Motive hypotheses must use canonical confidence and identity order"
            )
        global_citations = set(self.cited_observation_ids)
        if any(
            not set(item.cited_observation_ids).issubset(global_citations)
            for item in self.motive_hypotheses
        ):
            raise ValueError("Motive citations must be included in global citations")
        if self.motive_hypotheses:
            if self.motive_unknown_reason is not None:
                raise ValueError(
                    "A populated motive hypothesis set cannot claim motive unknown"
                )
        elif self.motive_unknown_reason is None:
            raise ValueError(
                "An empty motive hypothesis set requires an unknown reason"
            )
        if self.inferred_action_tendency == "unknown":
            if self.action_confidence != 0.0:
                raise ValueError("Unknown action requires zero action confidence")
        elif self.action_confidence == 0.0:
            raise ValueError("A claimed action requires positive action confidence")
        option_is_ambiguous = self.inferred_option_id is None
        motives_are_ambiguous = len(self.motive_hypotheses) > 1
        if option_is_ambiguous and motives_are_ambiguous:
            expected_ambiguity = OPTION_AND_MOTIVE_AMBIGUITY_SL
        elif option_is_ambiguous:
            expected_ambiguity = OPTION_AMBIGUITY_SL
        elif motives_are_ambiguous:
            expected_ambiguity = MOTIVE_AMBIGUITY_SL
        else:
            expected_ambiguity = None
        if self.unresolved_ambiguity != expected_ambiguity:
            raise ValueError(
                "Unresolved ambiguity differs from the structured claim state"
            )
        if self.inferred_option_id is None:
            if self.option_confidence != 0.0:
                raise ValueError("Option abstention requires zero option confidence")
        elif self.option_confidence == 0.0:
            raise ValueError("A selected option requires positive option confidence")
        return self

    def validate_against(
        self,
        packet: RacioEpistemicPacketV2,
    ) -> "RacioEpistemicInterpretationV2":
        if self.source_mind != packet.source_mind:
            raise ValueError("Epistemic output source mind differs from its packet")
        visible_ids = set(packet.visible_observation_ids)
        if not set(self.cited_observation_ids).issubset(visible_ids):
            raise ValueError(
                "Epistemic output cites an observation outside packet scope"
            )
        if packet.visible_observations and not self.cited_observation_ids:
            raise ValueError("An epistemic interpretation must cite visible evidence")
        if not packet.visible_observations:
            if self.cited_observation_ids:
                raise ValueError("An empty packet cannot have observation citations")
            if (
                self.inferred_action_tendency != "unknown"
                or self.inferred_option_id is not None
                or self.motive_hypotheses
            ):
                raise ValueError("An empty packet requires full epistemic abstention")
        if (
            self.inferred_option_id is not None
            and self.inferred_option_id not in set(packet.public_option_ids)
        ):
            raise ValueError("Epistemic output selects an option outside public scope")
        for hypothesis in self.motive_hypotheses:
            if not set(hypothesis.cited_observation_ids).issubset(visible_ids):
                raise ValueError(
                    "A motive hypothesis cites an observation outside packet scope"
                )
        return self


__all__ = [
    "MOTIVE_SUBTYPES_BY_FAMILY",
    "MOTIVE_AMBIGUITY_SL",
    "MOTIVE_HYPOTHESIS_EXPLANATION_SL",
    "MOTIVE_UNKNOWN_REASON_SL",
    "MotorSocialMotiveSubtype",
    "MotiveFamily",
    "MotiveHypothesis",
    "OPTION_AMBIGUITY_SL",
    "OPTION_AND_MOTIVE_AMBIGUITY_SL",
    "ProtectionMotiveSubtype",
    "RacioEpistemicInterpretationV2",
    "RacioEpistemicPacketV2",
    "SceneMotiveSubtype",
    "motive_subtype_belongs_to_family",
]
