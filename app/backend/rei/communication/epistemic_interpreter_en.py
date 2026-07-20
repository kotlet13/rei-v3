"""English-primary runtime boundary for bounded Racio interpretation.

This module reuses the frozen V3 draft claims and semantic taxonomy without
changing the historical bilingual V3 contract.  Its packet is English-only by
construction and contains no bilingual gloss fields or review attestations.
The deterministic canonicalizer sorts and validates model claims, but never
repairs or infers their semantics.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from .epistemic_interpreter import RacioReportedUncertainty
from .epistemic_interpreter_v3 import (
    AtomicEvidenceUnitIdV3,
    ActionHypothesisV3,
    MotiveHypothesisV3,
    OpaqueSignalAliasV3,
    OptionInferenceV3,
    RacioEpistemicDraftV3,
)


ACTION_UNKNOWN_REASON_EN: Final = (
    "Racio did not derive an action hypothesis from the listed visible observations."
)
OPTION_UNKNOWN_REASON_EN: Final = (
    "Racio did not derive a sufficiently supported option selection from the listed "
    "visible observations."
)
MOTIVE_UNKNOWN_REASON_EN: Final = (
    "Racio did not derive a motive hypothesis from the listed visible observations."
)

ActionUnknownReasonEn = Literal[
    "Racio did not derive an action hypothesis from the listed visible observations."
]
OptionUnknownReasonEn = Literal[
    "Racio did not derive a sufficiently supported option selection from the listed "
    "visible observations."
]
MotiveUnknownReasonEn = Literal[
    "Racio did not derive a motive hypothesis from the listed visible observations."
]


class EnglishObservationV3(FrozenModel):
    """One citeable, English-primary observation in the visible runtime scope."""

    observation_id: NonEmptyId
    atomic_evidence_unit_id: AtomicEvidenceUnitIdV3
    perceptual_unit_count: Literal[1] = 1
    signal_alias: OpaqueSignalAliasV3
    perception_status: Literal["clear", "degraded"]
    text: NonEmptyText | None
    provenance: Literal["manifested", "renderer_added_ungrounded"]

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.perception_status == "degraded":
            if self.text is not None:
                raise ValueError("A degraded observation cannot expose exact text")
        elif self.text is None:
            raise ValueError("A clear observation requires visible English text")
        return self


class EnglishOptionV3(FrozenModel):
    """One packet-local public option with an English description."""

    option_id: NonEmptyId
    description: NonEmptyText


class RacioEpistemicPacketEnV3(FrozenArtifactModel):
    """Content-addressed English-only packet for local model execution."""

    schema_version: Literal["rei-racio-epistemic-en-packet-v1"] = (
        "rei-racio-epistemic-en-packet-v1"
    )
    packet_id: NonEmptyId
    source_mind: Literal["E", "I"]
    language: Literal["en"] = "en"
    visible_observations: tuple[EnglishObservationV3, ...] = ()
    omitted_observation_ids: tuple[NonEmptyId, ...] = ()
    degraded_observation_ids: tuple[NonEmptyId, ...] = ()
    public_option_scope: tuple[EnglishOptionV3, ...] = ()
    channel_quality: Score01
    uncertainty: NonEmptyText
    packet_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        source_mind: Literal["E", "I"],
        visible_observations: tuple[EnglishObservationV3, ...],
        omitted_observation_ids: tuple[str, ...],
        public_option_scope: tuple[EnglishOptionV3, ...],
        channel_quality: float,
        uncertainty: str,
    ) -> "RacioEpistemicPacketEnV3":
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
            "schema_version": "rei-racio-epistemic-en-packet-v1",
            "source_mind": source_mind,
            "language": "en",
            "visible_observations": observations,
            "omitted_observation_ids": omitted,
            "degraded_observation_ids": degraded,
            "public_option_scope": options,
            "channel_quality": channel_quality,
            "uncertainty": uncertainty,
        }
        packet_id = content_id("racio_epistemic_packet_en", base)
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
        signal_aliases = tuple(item.signal_alias for item in self.visible_observations)
        if len(signal_aliases) != len(set(signal_aliases)):
            raise ValueError("Opaque signal aliases must be unique")
        atomic_unit_ids = tuple(
            item.atomic_evidence_unit_id for item in self.visible_observations
        )
        if len(atomic_unit_ids) != len(set(atomic_unit_ids)):
            raise ValueError(
                "One atomic evidence unit cannot be duplicated across observations"
            )
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
        option_ids = self.public_option_ids
        if option_ids != tuple(sorted(set(option_ids))):
            raise ValueError("Public option aliases must be sorted and unique")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"packet_id", "packet_hash"},
        )
        if self.packet_id != content_id("racio_epistemic_packet_en", id_payload):
            raise ValueError("English epistemic packet ID differs from its content")
        if self.packet_hash != self.content_hash(
            exclude_fields=frozenset({"packet_hash"})
        ):
            raise ValueError("English epistemic packet hash differs from its content")
        return self

    def provider_payload(self) -> dict[str, object]:
        """Return the exact English model view without bilingual audit metadata."""

        return {
            "schema_version": self.schema_version,
            "source_mind": self.source_mind,
            "language": self.language,
            "visible_observations": [
                {
                    "observation_id": item.observation_id,
                    "signal_alias": item.signal_alias,
                    "perception_status": item.perception_status,
                    "text": item.text,
                    "provenance": item.provenance,
                }
                for item in self.visible_observations
            ],
            "omitted_observation_ids": list(self.omitted_observation_ids),
            "degraded_observation_ids": list(self.degraded_observation_ids),
            "public_option_scope": [
                {
                    "option_id": item.option_id,
                    "description": item.description,
                }
                for item in self.public_option_scope
            ],
            "channel_quality": self.channel_quality,
            "uncertainty": self.uncertainty,
        }

    def provider_payload_bytes(self) -> bytes:
        return canonical_json_bytes(self.provider_payload())


class RacioEpistemicInterpretationEnV3(FrozenArtifactModel):
    """Content-addressed canonical V3 semantics with English abstention text."""

    schema_version: Literal["rei-racio-epistemic-en-interpretation-v1"] = (
        "rei-racio-epistemic-en-interpretation-v1"
    )
    interpretation_id: NonEmptyId
    source_mind: Literal["E", "I"]
    language: Literal["en"] = "en"
    cited_observation_ids: tuple[NonEmptyId, ...]
    action_hypotheses: tuple[ActionHypothesisV3, ...]
    action_unknown_reason: ActionUnknownReasonEn | None
    option_inference: OptionInferenceV3 | None
    option_unknown_reason: OptionUnknownReasonEn | None
    motive_hypotheses: tuple[MotiveHypothesisV3, ...]
    motive_unknown_reason: MotiveUnknownReasonEn | None
    racio_reported_uncertainty: RacioReportedUncertainty
    interpretation_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        source_mind: Literal["E", "I"],
        cited_observation_ids: tuple[str, ...],
        action_hypotheses: tuple[ActionHypothesisV3, ...],
        action_unknown_reason: ActionUnknownReasonEn | None,
        option_inference: OptionInferenceV3 | None,
        option_unknown_reason: OptionUnknownReasonEn | None,
        motive_hypotheses: tuple[MotiveHypothesisV3, ...],
        motive_unknown_reason: MotiveUnknownReasonEn | None,
        racio_reported_uncertainty: RacioReportedUncertainty,
    ) -> "RacioEpistemicInterpretationEnV3":
        base = {
            "schema_version": "rei-racio-epistemic-en-interpretation-v1",
            "source_mind": source_mind,
            "language": "en",
            "cited_observation_ids": cited_observation_ids,
            "action_hypotheses": action_hypotheses,
            "action_unknown_reason": action_unknown_reason,
            "option_inference": option_inference,
            "option_unknown_reason": option_unknown_reason,
            "motive_hypotheses": motive_hypotheses,
            "motive_unknown_reason": motive_unknown_reason,
            "racio_reported_uncertainty": racio_reported_uncertainty,
        }
        interpretation_id = content_id("racio_epistemic_interpret_en", base)
        payload = {"interpretation_id": interpretation_id, **base}
        return cls(**payload, interpretation_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_canonical_output(self) -> Self:
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("Global observation citations must be sorted and unique")
        if len(self.action_hypotheses) > 2:
            raise ValueError("At most two action hypotheses are permitted")
        if len(self.motive_hypotheses) > 3:
            raise ValueError("At most three motive hypotheses are permitted")
        action_keys = tuple(item.key for item in self.action_hypotheses)
        motive_keys = tuple(item.key for item in self.motive_hypotheses)
        if len(set(action_keys)) != len(action_keys):
            raise ValueError("Action family/subtype combinations must be unique")
        if len(set(motive_keys)) != len(motive_keys):
            raise ValueError("Motive family/subtype combinations must be unique")
        expected_actions = tuple(
            sorted(
                self.action_hypotheses,
                key=lambda item: (-item.confidence, *item.key),
            )
        )
        expected_motives = tuple(
            sorted(
                self.motive_hypotheses,
                key=lambda item: (-item.confidence, *item.key),
            )
        )
        if self.action_hypotheses != expected_actions:
            raise ValueError("Action hypotheses must use canonical confidence order")
        if self.motive_hypotheses != expected_motives:
            raise ValueError("Motive hypotheses must use canonical confidence order")
        scoped_claims = (
            *self.action_hypotheses,
            *((self.option_inference,) if self.option_inference is not None else ()),
            *self.motive_hypotheses,
        )
        claim_citations = {
            citation
            for item in scoped_claims
            for citation in item.cited_observation_ids
        }
        if set(self.cited_observation_ids) != claim_citations:
            raise ValueError(
                "Global citations must equal the claim-specific citation union"
            )
        if self.action_hypotheses:
            if self.action_unknown_reason is not None:
                raise ValueError("Populated actions cannot claim action unknown")
        elif self.action_unknown_reason != ACTION_UNKNOWN_REASON_EN:
            raise ValueError("Empty actions require the exact English unknown reason")
        if self.motive_hypotheses:
            if self.motive_unknown_reason is not None:
                raise ValueError("Populated motives cannot claim motive unknown")
        elif self.motive_unknown_reason != MOTIVE_UNKNOWN_REASON_EN:
            raise ValueError("Empty motives require the exact English unknown reason")
        if self.option_inference is None:
            if self.option_unknown_reason != OPTION_UNKNOWN_REASON_EN:
                raise ValueError(
                    "Option abstention requires the exact English unknown reason"
                )
        elif self.option_unknown_reason is not None:
            raise ValueError("A selected option cannot also claim option unknown")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"interpretation_id", "interpretation_hash"},
        )
        if self.interpretation_id != content_id(
            "racio_epistemic_interpret_en", id_payload
        ):
            raise ValueError("English interpretation ID differs from its content")
        if self.interpretation_hash != self.content_hash(
            exclude_fields=frozenset({"interpretation_hash"})
        ):
            raise ValueError("English interpretation hash differs from its content")
        return self

    def validate_against(
        self,
        packet: RacioEpistemicPacketEnV3,
    ) -> "RacioEpistemicInterpretationEnV3":
        if self.source_mind != packet.source_mind:
            raise ValueError(
                "English interpretation source mind differs from its packet"
            )
        visible_ids = set(packet.visible_observation_ids)
        if not set(self.cited_observation_ids).issubset(visible_ids):
            raise ValueError(
                "English interpretation cites outside visible packet scope"
            )
        if (
            self.option_inference is not None
            and self.option_inference.option_id not in set(packet.public_option_ids)
        ):
            raise ValueError(
                "English interpretation selects outside public option scope"
            )
        return self


def canonicalize_racio_epistemic_draft_en_v3(
    packet: RacioEpistemicPacketEnV3,
    draft: RacioEpistemicDraftV3,
) -> RacioEpistemicInterpretationEnV3:
    """Canonicalize syntax and packet scope without semantic repair."""

    if draft.source_mind != packet.source_mind:
        raise ValueError("Draft source mind differs from its English packet")

    visible_ids = set(packet.visible_observation_ids)
    public_option_ids = set(packet.public_option_ids)

    def canonical_citations(values: tuple[str, ...]) -> tuple[str, ...]:
        citations = tuple(sorted(set(values)))
        if not set(citations).issubset(visible_ids):
            raise ValueError("Draft claim cites outside visible English packet scope")
        return citations

    actions = tuple(
        sorted(
            (
                ActionHypothesisV3(
                    family=item.family,
                    subtype=item.subtype,
                    family_fallback=item.family_fallback,
                    cited_observation_ids=canonical_citations(
                        item.cited_observation_ids
                    ),
                    confidence=item.confidence,
                    support_mode=item.support_mode,
                )
                for item in draft.action_hypotheses
            ),
            key=lambda item: (-item.confidence, *item.key),
        )
    )
    motives = tuple(
        sorted(
            (
                MotiveHypothesisV3(
                    family=item.family,
                    subtype=item.subtype,
                    cited_observation_ids=canonical_citations(
                        item.cited_observation_ids
                    ),
                    confidence=item.confidence,
                    support_mode=item.support_mode,
                )
                for item in draft.motive_hypotheses
            ),
            key=lambda item: (-item.confidence, *item.key),
        )
    )
    option: OptionInferenceV3 | None = None
    if draft.option_inference is not None:
        if draft.option_inference.option_id not in public_option_ids:
            raise ValueError("Draft selects outside public English option scope")
        option = OptionInferenceV3(
            option_id=draft.option_inference.option_id,
            cited_observation_ids=canonical_citations(
                draft.option_inference.cited_observation_ids
            ),
            confidence=draft.option_inference.confidence,
        )

    claim_citations = {
        citation
        for claim in (
            *actions,
            *((option,) if option is not None else ()),
            *motives,
        )
        for citation in claim.cited_observation_ids
    }
    output = RacioEpistemicInterpretationEnV3.create(
        source_mind=draft.source_mind,
        cited_observation_ids=tuple(sorted(claim_citations)),
        action_hypotheses=actions,
        action_unknown_reason=(None if actions else ACTION_UNKNOWN_REASON_EN),
        option_inference=option,
        option_unknown_reason=(
            None if option is not None else OPTION_UNKNOWN_REASON_EN
        ),
        motive_hypotheses=motives,
        motive_unknown_reason=(None if motives else MOTIVE_UNKNOWN_REASON_EN),
        racio_reported_uncertainty=draft.racio_reported_uncertainty,
    )
    return output.validate_against(packet)


__all__ = [
    "ACTION_UNKNOWN_REASON_EN",
    "ActionUnknownReasonEn",
    "EnglishObservationV3",
    "EnglishOptionV3",
    "MOTIVE_UNKNOWN_REASON_EN",
    "MotiveUnknownReasonEn",
    "OPTION_UNKNOWN_REASON_EN",
    "OptionUnknownReasonEn",
    "RacioEpistemicInterpretationEnV3",
    "RacioEpistemicPacketEnV3",
    "canonicalize_racio_epistemic_draft_en_v3",
]
