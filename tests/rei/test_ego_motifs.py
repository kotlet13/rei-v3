from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.backend.rei.ego.motifs import (
    CanonicalMotifRule,
    EmbeddingMotifHypothesis,
    MotifCandidate,
    MotifHypothesisValidation,
    MotifObservation,
    ThreeStageMotifEngine,
)


def _observation(token: str, measure_id: str) -> MotifObservation:
    return MotifObservation.create(motif_token=token, measure_id=measure_id)


def test_exact_recurrence_is_measure_sourced_and_input_order_independent() -> None:
    observations = (
        _observation("Boundary Pressure", "measure_2"),
        _observation("boundary-pressure", "measure_1"),
        _observation("single", "measure_3"),
    )
    engine = ThreeStageMotifEngine()

    first = engine.derive_exact(observations)
    replay = engine.derive_exact(tuple(reversed(observations)))

    assert first == replay
    assert len(first) == 1
    assert first[0].stage == "exact"
    assert first[0].canonical_motif == "boundary_pressure"
    assert first[0].evidence_measure_ids == ("measure_1", "measure_2")
    assert MotifCandidate.model_validate_json(first[0].model_dump_json()) == first[0]


def test_canonical_normalization_requires_a_source_grounded_alias_rule() -> None:
    observations = (
        _observation("career growth", "measure_1"),
        _observation("professional advancement", "measure_2"),
    )
    rule = CanonicalMotifRule.create(
        canonical_motif="vocational development",
        aliases=("career growth", "professional advancement"),
        source_claim_ids=("claim_reviewed_alias_map",),
    )

    assert ThreeStageMotifEngine().derive_canonical(observations) == ()
    candidates = ThreeStageMotifEngine((rule,)).derive_canonical(observations)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.stage == "canonical"
    assert candidate.canonical_rule == rule
    assert candidate.observed_tokens == (
        "career_growth",
        "professional_advancement",
    )
    assert candidate.evidence_measure_ids == ("measure_1", "measure_2")


def test_canonical_alias_ambiguity_fails_closed() -> None:
    first = CanonicalMotifRule.create(
        canonical_motif="growth",
        aliases=("advance",),
        source_claim_ids=("claim_1",),
    )
    second = CanonicalMotifRule.create(
        canonical_motif="status",
        aliases=("advance",),
        source_claim_ids=("claim_2",),
    )

    with pytest.raises(ValueError, match="multiple rules"):
        ThreeStageMotifEngine((first, second))


def test_motif_engine_cold_rejects_stale_rule_identity() -> None:
    rule = CanonicalMotifRule.create(
        canonical_motif="growth",
        aliases=("advance",),
        source_claim_ids=("claim_1",),
    )
    stale = rule.model_copy(update={"canonical_motif": "forged"})
    with pytest.raises(ValidationError, match="aliases|ID differs|hash differs"):
        ThreeStageMotifEngine((stale,))


def test_embedding_hypothesis_requires_separate_typed_acceptance() -> None:
    hypothesis = EmbeddingMotifHypothesis.create(
        proposed_motif="belonging risk",
        observed_tokens=("social exclusion", "group rupture"),
        evidence_measure_ids=("measure_1", "measure_2"),
        embedding_artifact_ids=("embedding_1", "embedding_2"),
        embedding_artifact_hashes=("a" * 64, "b" * 64),
        similarity=0.87,
    )
    rejected = MotifHypothesisValidation.create(
        hypothesis=hypothesis,
        validator_id="motif_reviewer",
        validator_revision="1",
        decision="rejected",
        cited_measure_ids=hypothesis.evidence_measure_ids,
        rationale="The similarity is not semantically grounded.",
    )
    engine = ThreeStageMotifEngine()

    with pytest.raises(ValueError, match="Rejected"):
        engine.admit_embedding_hypothesis(hypothesis, rejected)

    accepted = MotifHypothesisValidation.create(
        hypothesis=hypothesis,
        validator_id="motif_reviewer",
        validator_revision="1",
        decision="accepted",
        cited_measure_ids=hypothesis.evidence_measure_ids,
        rationale="Both cited measures explicitly describe belonging loss.",
    )
    candidate = engine.admit_embedding_hypothesis(hypothesis, accepted)

    assert candidate.stage == "embedding_hypothesis"
    assert candidate.hypothesis_validation == accepted
    assert candidate.evidence_measure_ids == hypothesis.evidence_measure_ids

    payload = candidate.model_dump(mode="python", round_trip=True)
    payload["evidence_measure_ids"] = ("measure_1", "measure_3")
    with pytest.raises(ValidationError, match="differs from its hypothesis"):
        MotifCandidate.model_validate(payload)


def test_embedding_validation_must_cite_hypothesis_measures_exactly() -> None:
    hypothesis = EmbeddingMotifHypothesis.create(
        proposed_motif="recurring rupture",
        observed_tokens=("rupture one", "rupture two"),
        evidence_measure_ids=("measure_1", "measure_2"),
        embedding_artifact_ids=("embedding_pair",),
        embedding_artifact_hashes=("c" * 64,),
        similarity=0.8,
    )
    with pytest.raises(ValidationError, match="cite the hypothesis evidence exactly"):
        MotifHypothesisValidation.create(
            hypothesis=hypothesis,
            validator_id="motif_reviewer",
            validator_revision="1",
            decision="accepted",
            cited_measure_ids=("measure_1", "measure_3"),
            rationale="Invalid citation boundary.",
        )
