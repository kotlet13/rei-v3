"""Additive English explanation boundary over the frozen V3 semantics.

The historical V3 draft and canonical interpretation remain unchanged.  This
module adds model-authored, claim-local explanations only for claims that Racio
does not make.  Explanations are diagnostic evidence: they never enter the V3
claim citation union and have no authority over the deterministic REI path.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from ..models.common import FrozenModel, NonEmptyId, NonEmptyText
from .epistemic_interpreter import RacioReportedUncertainty
from .epistemic_interpreter_en import (
    RacioEpistemicInterpretationEnV3,
    RacioEpistemicPacketEnV3,
    canonicalize_racio_epistemic_draft_en_v3,
)
from .epistemic_interpreter_v3 import (
    ActionHypothesisDraftV3,
    MotiveHypothesisDraftV3,
    OptionInferenceDraftV3,
    RacioEpistemicDraftV3,
)


class ClaimAbsenceExplanationEnV1(FrozenModel):
    """One concise Gemma-authored explanation for an absent claim."""

    explanation: NonEmptyText = Field(max_length=600)
    cited_observation_ids: tuple[NonEmptyId, ...]

    @model_validator(mode="after")
    def validate_citations(self) -> Self:
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError(
                "Claim-absence explanation citations must be sorted and unique"
            )
        return self


class RacioEpistemicExplainedDraftEnV1(FrozenModel):
    """English model draft with explanations for every absent claim kind."""

    source_mind: Literal["E", "I"]
    action_hypotheses: tuple[ActionHypothesisDraftV3, ...]
    action_abstention_explanation: ClaimAbsenceExplanationEnV1 | None
    option_inference: OptionInferenceDraftV3 | None
    option_abstention_explanation: ClaimAbsenceExplanationEnV1 | None
    motive_hypotheses: tuple[MotiveHypothesisDraftV3, ...]
    motive_abstention_explanation: ClaimAbsenceExplanationEnV1 | None
    racio_reported_uncertainty: RacioReportedUncertainty

    @model_validator(mode="after")
    def validate_claim_explanation_pairs(self) -> Self:
        if len(self.action_hypotheses) > 2:
            raise ValueError("At most two action drafts are permitted")
        if len(self.motive_hypotheses) > 3:
            raise ValueError("At most three motive drafts are permitted")
        pairs = (
            (
                bool(self.action_hypotheses),
                self.action_abstention_explanation,
                "action",
            ),
            (
                self.option_inference is not None,
                self.option_abstention_explanation,
                "option",
            ),
            (
                bool(self.motive_hypotheses),
                self.motive_abstention_explanation,
                "motive",
            ),
        )
        for claim_present, explanation, label in pairs:
            if claim_present and explanation is not None:
                raise ValueError(
                    f"A populated {label} claim cannot also explain abstention"
                )
            if not claim_present and explanation is None:
                raise ValueError(
                    f"An absent {label} claim requires a model-authored explanation"
                )
        return self

    def semantic_draft(self) -> RacioEpistemicDraftV3:
        """Project only frozen V3 semantics; never infer or repair a claim."""

        return RacioEpistemicDraftV3(
            source_mind=self.source_mind,
            action_hypotheses=self.action_hypotheses,
            option_inference=self.option_inference,
            motive_hypotheses=self.motive_hypotheses,
            racio_reported_uncertainty=self.racio_reported_uncertainty,
        )

    def validate_explanations_against(
        self,
        packet: RacioEpistemicPacketEnV3,
    ) -> "RacioEpistemicExplainedDraftEnV1":
        if self.source_mind != packet.source_mind:
            raise ValueError("Explained draft source mind differs from its packet")
        visible = set(packet.visible_observation_ids)
        explanations = (
            self.action_abstention_explanation,
            self.option_abstention_explanation,
            self.motive_abstention_explanation,
        )
        for explanation in explanations:
            if explanation is None:
                continue
            citations = set(explanation.cited_observation_ids)
            if not citations.issubset(visible):
                raise ValueError(
                    "Claim-absence explanation cites outside visible English packet scope"
                )
            if visible and not citations:
                raise ValueError(
                    "Claim-absence explanation must cite relevant visible observations"
                )
            if not visible and citations:
                raise ValueError(
                    "An empty packet cannot support explanation citations"
                )
        return self


def canonicalize_racio_epistemic_explained_draft_en_v1(
    packet: RacioEpistemicPacketEnV3,
    draft: RacioEpistemicExplainedDraftEnV1,
) -> RacioEpistemicInterpretationEnV3:
    """Validate explanations, then reuse the frozen non-semantic V3 canonicalizer."""

    draft.validate_explanations_against(packet)
    return canonicalize_racio_epistemic_draft_en_v3(packet, draft.semantic_draft())


__all__ = [
    "ClaimAbsenceExplanationEnV1",
    "RacioEpistemicExplainedDraftEnV1",
    "canonicalize_racio_epistemic_explained_draft_en_v1",
]
