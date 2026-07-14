"""Transparent comparison of Racio narration and longitudinal composition."""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import model_validator

from ..ids import content_id, sha256_hex
from ..models.common import FrozenArtifactModel, HashDigest, NonEmptyId
from ..models.conscious import RacioSelfNarrative
from ..models.ego import EgoCompositionSnapshot


NarrativeDivergenceFacet = Literal[
    "claimed_motive_not_observed",
    "omitted_minds",
    "recurrent_translation_gaps",
]


def _cold_revalidate(value: RacioSelfNarrative | EgoCompositionSnapshot):
    model_type = type(value)
    cold = model_type.model_validate(
        value.model_dump(mode="python", round_trip=True)
    )
    if cold != value:
        raise ValueError("Narrative diagnostic input changed during cold validation")
    return cold


def _lexical_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def _composition_claims(snapshot: EgoCompositionSnapshot) -> tuple[str, ...]:
    values = (
        *snapshot.identity_motifs,
        *snapshot.recurring_conflicts,
        *snapshot.unresolved_tensions,
        *snapshot.resolved_tensions,
        *snapshot.spoznanja,
        *snapshot.commitments,
        *snapshot.relationship_patterns,
    )
    return tuple(dict.fromkeys(values))


def _source_narrative_hash(narrative: RacioSelfNarrative) -> str:
    return narrative.narrative_hash or narrative.content_hash()


def _claimed_motive_is_observed(
    claimed_motive: str,
    observed_claims: tuple[str, ...],
) -> bool:
    """Use only visible exact lexical tokens, never semantic similarity."""

    motive = _lexical_token(claimed_motive)
    if not motive:
        return False
    for claim in observed_claims:
        normalized = _lexical_token(claim)
        if motive == normalized or motive == normalized.rsplit(":", 1)[-1]:
            return True
    return False


def _diagnostic_values(
    narrative: RacioSelfNarrative,
    snapshot: EgoCompositionSnapshot,
) -> dict[str, object]:
    observed_claims = _composition_claims(snapshot)
    facets: list[NarrativeDivergenceFacet] = []
    if not _claimed_motive_is_observed(narrative.claimed_motive, observed_claims):
        facets.append("claimed_motive_not_observed")
    if narrative.omitted_minds:
        facets.append("omitted_minds")
    if snapshot.recurring_translation_errors:
        facets.append("recurrent_translation_gaps")
    return {
        "claimed_motive": narrative.claimed_motive,
        "observed_composition_claims": observed_claims,
        "acknowledged_minds": narrative.acknowledged_minds,
        "omitted_minds": narrative.omitted_minds,
        "recurrent_translation_gaps": snapshot.recurring_translation_errors,
        "evidence_measure_ids": snapshot.evidence_measure_ids,
        "divergence_facets": tuple(facets),
        "narrative_composition_diverges": bool(facets),
    }


class NarrativeCompositionDiagnostic(FrozenArtifactModel):
    """A replayable diagnostic, not a correction or decision artifact."""

    schema_version: Literal["rei-narrative-composition-diagnostic-v1"] = (
        "rei-narrative-composition-diagnostic-v1"
    )
    diagnostic_id: NonEmptyId
    source_narrative: RacioSelfNarrative
    source_narrative_hash: HashDigest
    source_snapshot: EgoCompositionSnapshot
    source_snapshot_hash: HashDigest
    claimed_motive: str
    observed_composition_claims: tuple[str, ...]
    acknowledged_minds: tuple[Literal["R", "E", "I"], ...]
    omitted_minds: tuple[Literal["R", "E", "I"], ...]
    recurrent_translation_gaps: tuple[str, ...]
    evidence_measure_ids: tuple[NonEmptyId, ...]
    divergence_facets: tuple[NarrativeDivergenceFacet, ...]
    narrative_composition_diverges: bool
    diagnostic_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        narrative: RacioSelfNarrative,
        snapshot: EgoCompositionSnapshot,
    ) -> "NarrativeCompositionDiagnostic":
        narrative = _cold_revalidate(narrative)
        snapshot = _cold_revalidate(snapshot)
        values = _diagnostic_values(narrative, snapshot)
        base = {
            "schema_version": "rei-narrative-composition-diagnostic-v1",
            "source_narrative": narrative,
            "source_narrative_hash": _source_narrative_hash(narrative),
            "source_snapshot": snapshot,
            "source_snapshot_hash": snapshot.composition_hash,
            **values,
        }
        diagnostic_id = content_id("narrative_diagnostic", base)
        payload = {"diagnostic_id": diagnostic_id, **base}
        return cls(**payload, diagnostic_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_diagnostic(self) -> Self:
        if self.source_narrative_hash != _source_narrative_hash(
            self.source_narrative
        ):
            raise ValueError("Narrative diagnostic source hash differs")
        if self.source_snapshot_hash != self.source_snapshot.composition_hash:
            raise ValueError("Composition diagnostic source hash differs")
        expected = _diagnostic_values(self.source_narrative, self.source_snapshot)
        actual = {
            key: getattr(self, key)
            for key in (
                "claimed_motive",
                "observed_composition_claims",
                "acknowledged_minds",
                "omitted_minds",
                "recurrent_translation_gaps",
                "evidence_measure_ids",
                "divergence_facets",
                "narrative_composition_diverges",
            )
        }
        if actual != expected:
            raise ValueError("Narrative diagnostic differs from transparent replay")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"diagnostic_id", "diagnostic_hash"},
        )
        if self.diagnostic_id != content_id("narrative_diagnostic", base):
            raise ValueError("Narrative diagnostic ID differs from its content")
        payload = {"diagnostic_id": self.diagnostic_id, **base}
        if self.diagnostic_hash != sha256_hex(payload):
            raise ValueError("Narrative diagnostic hash differs from its content")
        return self


def diagnose_narrative_composition(
    narrative: RacioSelfNarrative,
    snapshot: EgoCompositionSnapshot,
) -> NarrativeCompositionDiagnostic:
    narrative = _cold_revalidate(narrative)
    snapshot = _cold_revalidate(snapshot)
    return NarrativeCompositionDiagnostic.create(
        narrative=narrative,
        snapshot=snapshot,
    )


__all__ = [
    "NarrativeCompositionDiagnostic",
    "NarrativeDivergenceFacet",
    "diagnose_narrative_composition",
]
