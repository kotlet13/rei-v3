from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.backend.rei.evaluation.human_review import (
    REVIEW_FACETS,
    BlindReviewLedger,
    BlindReviewPacket,
    FinalReviewRecord,
    ReviewMaterialCommitment,
    commit_review_material,
    prepare_blind_review,
    record_final_review,
    record_first_pass,
    reveal_review_context,
    reviewer_agreement,
)
from app.backend.rei.ids import content_id


SOURCE_MANIFEST_HASH = "a" * 64


def _commitment(
    *,
    case_id: str,
    subject_id: str,
    material_variant: str = "canonical",
) -> ReviewMaterialCommitment:
    return commit_review_material(
        authority_id="trusted-review-fixture-authority",
        source_manifest_hash=SOURCE_MANIFEST_HASH,
        case_id=case_id,
        subject_id=subject_id,
        blind_presented_text="Nevtralen opis za slepo presojo.",
        language="sl",
        route_ids=(f"route-{case_id}",),
        visible_artifact_ids=(f"artifact-{case_id}",),
        visible_observation_ids=(f"observation-{case_id}",),
        source_excerpts=(
            (f"source-{case_id}", f"Pregledani povzetek vira: {material_variant}."),
        ),
        grounded_scene_text=f"Utemeljena scena {case_id}: {material_variant}.",
        grounded_scene_artifact_ids=(f"grounded-{case_id}",),
        grounded_evidence_ids=(f"evidence-{case_id}",),
    )


def _review_case(
    *,
    case_id: str,
    subject_id: str,
) -> tuple[ReviewMaterialCommitment, BlindReviewPacket]:
    commitment = _commitment(case_id=case_id, subject_id=subject_id)
    return commitment, prepare_blind_review(commitment)


def _first_pass(
    packet: BlindReviewPacket,
    *,
    reviewer_id: str,
):
    return record_first_pass(
        packet,
        reviewer_id=reviewer_id,
        selected_mind="R",
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=4,
        translation_quality=4,
        uncertainty=2,
    )


def _final_review(
    commitment: ReviewMaterialCommitment,
    packet: BlindReviewPacket,
    *,
    reviewer_id: str,
    selected_mind: str,
    reasoning_quality: int,
    translation_quality: int,
    uncertainty: int,
) -> FinalReviewRecord:
    session = _first_pass(packet, reviewer_id=reviewer_id)
    revealed = reveal_review_context(
        session,
        material_commitment=commitment,
    )
    return record_final_review(
        revealed,
        selected_mind=selected_mind,
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=reasoning_quality,
        translation_quality=translation_quality,
        uncertainty=uncertainty,
    )


def test_blind_packet_is_bound_to_commitment_without_revealing_raw_material():
    raw_identifiers = (
        "case-raw-canary-7f16",
        "subject-raw-canary-8a27",
        "route-case-raw-canary-7f16",
        "artifact-case-raw-canary-7f16",
        "observation-case-raw-canary-7f16",
        "source-case-raw-canary-7f16",
        "grounded-case-raw-canary-7f16",
        "evidence-case-raw-canary-7f16",
    )
    commitment = commit_review_material(
        authority_id="trusted-review-fixture-authority",
        source_manifest_hash=SOURCE_MANIFEST_HASH,
        case_id=raw_identifiers[0],
        subject_id=raw_identifiers[1],
        blind_presented_text="Nevtralen opis za slepo presojo.",
        language="sl",
        route_ids=(raw_identifiers[2],),
        visible_artifact_ids=(raw_identifiers[3],),
        visible_observation_ids=(raw_identifiers[4],),
        source_excerpts=((raw_identifiers[5], "canonical-source-text-canary"),),
        grounded_scene_text="canonical-grounded-scene-canary",
        grounded_scene_artifact_ids=(raw_identifiers[6],),
        grounded_evidence_ids=(raw_identifiers[7],),
    )
    packet = prepare_blind_review(commitment)

    serialized = packet.model_dump_json()
    forbidden_values = (
        *raw_identifiers,
        "canonical-source-text-canary",
        "canonical-grounded-scene-canary",
    )
    assert all(value not in serialized for value in forbidden_values)
    assert set(BlindReviewPacket.model_fields).isdisjoint(
        {
            "case_id",
            "subject_id",
            "material_commitment",
            "source_excerpts",
            "grounded_scene_text",
            "expected_label",
            "ground_truth",
            "target_label",
        }
    )
    assert packet.material_commitment_id == commitment.commitment_id
    assert packet.blind_route_ids != (raw_identifiers[2],)
    assert packet.evaluator_model_calls == 0


def test_material_commitment_is_content_addressed_and_tamper_evident():
    first = _commitment(case_id="case-content", subject_id="subject-content")
    replay = _commitment(case_id="case-content", subject_id="subject-content")
    changed = _commitment(
        case_id="case-content",
        subject_id="subject-content",
        material_variant="changed",
    )

    assert first == replay
    assert first.commitment_id == replay.commitment_id
    assert changed.commitment_id != first.commitment_id
    assert changed.material_hash != first.material_hash

    tampered = first.model_dump(mode="python", round_trip=True)
    tampered["grounded_scene_text"] = "Naknadno spremenjena scena."
    with pytest.raises(ValidationError, match="material hash"):
        ReviewMaterialCommitment.model_validate(tampered)


def test_ledger_runs_idempotent_first_pass_reveal_final_state_machine():
    commitment, packet = _review_case(
        case_id="case-state-machine",
        subject_id="subject-state-machine",
    )
    ledger = BlindReviewLedger((commitment,))
    first_pass_kwargs = {
        "reviewer_id": "reviewer-state-machine",
        "selected_mind": "R",
        "selected_route_id": packet.blind_route_ids[0],
        "reasoning_quality": 3,
        "translation_quality": 4,
        "uncertainty": 3,
        "notes": "Prva slepa presoja.",
    }
    session = ledger.record_first_pass(packet, **first_pass_kwargs)
    assert ledger.record_first_pass(packet, **first_pass_kwargs) is session
    assert session.state == "first_pass_recorded"
    assert not hasattr(session, "source_excerpts")

    revealed = ledger.reveal_review_context(
        session,
        material_commitment=commitment,
    )
    assert (
        ledger.reveal_review_context(
            session,
            material_commitment=commitment,
        )
        is revealed
    )
    assert revealed.state == "context_revealed"
    assert revealed.source_excerpts == commitment.source_excerpts
    assert revealed.grounded_scene_text == commitment.grounded_scene_text

    final_kwargs = {
        "selected_mind": "E",
        "selected_route_id": packet.blind_route_ids[0],
        "reasoning_quality": 4,
        "translation_quality": 5,
        "uncertainty": 2,
        "notes": "Presoja po razkritju.",
    }
    final = ledger.record_final_review(revealed, **final_kwargs)
    assert ledger.record_final_review(revealed, **final_kwargs) is final
    assert final.state == "final_review_recorded"
    assert final.judgment_changed

    with pytest.raises(ValidationError):
        session.state = "context_revealed"


def test_ledger_rejects_different_first_pass_for_same_reviewer():
    commitment, packet = _review_case(
        case_id="case-first-pass-branch",
        subject_id="subject-first-pass-branch",
    )
    ledger = BlindReviewLedger((commitment,))
    ledger.record_first_pass(
        packet,
        reviewer_id="reviewer-a",
        selected_mind="R",
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=3,
        translation_quality=3,
        uncertainty=3,
    )

    with pytest.raises(ValueError, match="different first pass"):
        ledger.record_first_pass(
            packet,
            reviewer_id="reviewer-a",
            selected_mind="E",
            selected_route_id=packet.blind_route_ids[0],
            reasoning_quality=4,
            translation_quality=3,
            uncertainty=3,
        )


def test_second_reveal_with_different_material_is_rejected():
    commitment, packet = _review_case(
        case_id="case-reveal-branch",
        subject_id="subject-reveal-branch",
    )
    different = _commitment(
        case_id=commitment.case_id,
        subject_id=commitment.subject_id,
        material_variant="different-material",
    )
    ledger = BlindReviewLedger((commitment, different))
    session = ledger.record_first_pass(
        packet,
        reviewer_id="reviewer-a",
        selected_mind="R",
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=3,
        translation_quality=3,
        uncertainty=3,
    )
    original = ledger.reveal_review_context(
        session,
        material_commitment=commitment,
    )
    assert original.material_commitment == commitment

    with pytest.raises(ValueError, match="blind packet commitment"):
        ledger.reveal_review_context(
            session,
            material_commitment=different,
        )


def test_second_different_final_review_is_rejected():
    commitment, packet = _review_case(
        case_id="case-final-branch",
        subject_id="subject-final-branch",
    )
    ledger = BlindReviewLedger((commitment,))
    session = ledger.record_first_pass(
        packet,
        reviewer_id="reviewer-a",
        selected_mind="R",
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=3,
        translation_quality=3,
        uncertainty=3,
    )
    revealed = ledger.reveal_review_context(
        session,
        material_commitment=commitment,
    )
    ledger.record_final_review(
        revealed,
        selected_mind="R",
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=3,
        translation_quality=3,
        uncertainty=3,
    )

    with pytest.raises(ValueError, match="different final review"):
        ledger.record_final_review(
            revealed,
            selected_mind="E",
            selected_route_id=packet.blind_route_ids[0],
            reasoning_quality=4,
            translation_quality=4,
            uncertainty=2,
        )


def test_ledger_rejects_untrusted_material_and_unregistered_transitions():
    trusted, trusted_packet = _review_case(
        case_id="case-trusted",
        subject_id="subject-trusted",
    )
    untrusted, untrusted_packet = _review_case(
        case_id="case-untrusted",
        subject_id="subject-untrusted",
    )
    ledger = BlindReviewLedger((trusted,))

    with pytest.raises(ValueError, match="not bound to trusted"):
        ledger.record_first_pass(
            untrusted_packet,
            reviewer_id="reviewer-a",
            selected_mind="R",
            selected_route_id=untrusted_packet.blind_route_ids[0],
            reasoning_quality=3,
            translation_quality=3,
            uncertainty=3,
        )

    forged_payload = trusted_packet.model_dump(
        mode="python", round_trip=True, exclude={"packet_id"}
    )
    forged_payload["presented_text"] = "Naknadno zamenjan slepi prikaz."
    forged_packet = BlindReviewPacket(
        packet_id=content_id("blind_review_packet", forged_payload),
        **forged_payload,
    )
    with pytest.raises(ValueError, match="trusted commitment projection"):
        ledger.record_first_pass(
            forged_packet,
            reviewer_id="reviewer-a",
            selected_mind="R",
            selected_route_id=forged_packet.blind_route_ids[0],
            reasoning_quality=3,
            translation_quality=3,
            uncertainty=3,
        )

    unregistered_session = _first_pass(trusted_packet, reviewer_id="reviewer-a")
    with pytest.raises(ValueError, match="not registered"):
        ledger.reveal_review_context(
            unregistered_session,
            material_commitment=trusted,
        )

    assert untrusted.commitment_id not in {trusted.commitment_id}


def test_review_rejects_mismatched_reviewer_and_routes():
    commitment, packet = _review_case(
        case_id="case-mismatch",
        subject_id="subject-mismatch",
    )

    with pytest.raises(ValueError, match="outside the blind route scope"):
        record_first_pass(
            packet,
            reviewer_id="reviewer-a",
            selected_mind="R",
            selected_route_id="raw-route-outside-scope",
            reasoning_quality=3,
            translation_quality=3,
            uncertainty=3,
        )

    session = _first_pass(packet, reviewer_id="reviewer-a")
    revealed = reveal_review_context(
        session,
        material_commitment=commitment,
    )

    with pytest.raises(ValueError, match="outside the blind route scope"):
        record_final_review(
            revealed,
            selected_mind="R",
            selected_route_id="raw-route-outside-scope",
            reasoning_quality=3,
            translation_quality=3,
            uncertainty=3,
        )

    final = record_final_review(
        revealed,
        selected_mind="R",
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=3,
        translation_quality=3,
        uncertainty=3,
    )
    mismatched_reviewer = final.model_dump(mode="python", round_trip=True)
    mismatched_reviewer["reviewer_id"] = "reviewer-b"
    with pytest.raises(ValidationError, match="first-pass reviewer"):
        FinalReviewRecord.model_validate(mismatched_reviewer)


def test_review_artifact_ids_are_deterministic_for_identical_inputs():
    commitment_a, packet_a = _review_case(
        case_id="case-deterministic",
        subject_id="subject-deterministic",
    )
    commitment_b, packet_b = _review_case(
        case_id="case-deterministic",
        subject_id="subject-deterministic",
    )
    assert commitment_a.commitment_id == commitment_b.commitment_id
    assert packet_a == packet_b

    session_a = _first_pass(packet_a, reviewer_id="reviewer-deterministic")
    session_b = _first_pass(packet_b, reviewer_id="reviewer-deterministic")
    assert session_a.session_id == session_b.session_id

    reveal_a = reveal_review_context(
        session_a,
        material_commitment=commitment_a,
    )
    reveal_b = reveal_review_context(
        session_b,
        material_commitment=commitment_b,
    )
    assert reveal_a.reveal_id == reveal_b.reveal_id

    final_kwargs = {
        "selected_mind": "E",
        "selected_route_id": packet_a.blind_route_ids[0],
        "reasoning_quality": 5,
        "translation_quality": 4,
        "uncertainty": 1,
    }
    final_a = record_final_review(reveal_a, **final_kwargs)
    final_b = record_final_review(reveal_b, **final_kwargs)
    assert final_a.final_review_id == final_b.final_review_id
    assert final_a == final_b


def test_cohen_kappa_is_undefined_for_degenerate_reviewer_marginals():
    commitment, packet = _review_case(
        case_id="case-kappa-undefined",
        subject_id="subject-kappa-undefined",
    )
    reviews = tuple(
        _final_review(
            commitment,
            packet,
            reviewer_id=reviewer_id,
            selected_mind="R",
            reasoning_quality=5,
            translation_quality=5,
            uncertainty=1,
        )
        for reviewer_id in ("reviewer-a", "reviewer-b")
    )

    agreement = reviewer_agreement(reviews)
    assert tuple(item.facet for item in agreement.facet_agreements) == REVIEW_FACETS
    assert all(item.observed_agreement == 1.0 for item in agreement.facet_agreements)
    assert all(item.expected_agreement == 1.0 for item in agreement.facet_agreements)
    assert all(not item.kappa_defined for item in agreement.facet_agreements)
    assert all(item.cohen_kappa is None for item in agreement.facet_agreements)


def test_cohen_kappa_is_computed_for_non_degenerate_reviewer_marginals():
    cases = tuple(
        _review_case(case_id=case_id, subject_id=subject_id)
        for case_id, subject_id in (
            ("case-kappa-one", "subject-kappa-one"),
            ("case-kappa-two", "subject-kappa-two"),
        )
    )
    reviews = (
        _final_review(
            *cases[0],
            reviewer_id="reviewer-a",
            selected_mind="R",
            reasoning_quality=5,
            translation_quality=4,
            uncertainty=1,
        ),
        _final_review(
            *cases[0],
            reviewer_id="reviewer-b",
            selected_mind="R",
            reasoning_quality=5,
            translation_quality=4,
            uncertainty=1,
        ),
        _final_review(
            *cases[1],
            reviewer_id="reviewer-a",
            selected_mind="E",
            reasoning_quality=2,
            translation_quality=2,
            uncertainty=4,
        ),
        _final_review(
            *cases[1],
            reviewer_id="reviewer-b",
            selected_mind="I",
            reasoning_quality=3,
            translation_quality=3,
            uncertainty=5,
        ),
    )

    agreement = reviewer_agreement(reviews)
    by_facet = {item.facet: item for item in agreement.facet_agreements}
    assert set(by_facet) == set(REVIEW_FACETS)
    assert by_facet["mind"].kappa_defined
    assert by_facet["mind"].cohen_kappa == pytest.approx(1.0 / 3.0)
    assert by_facet["reasoning_quality"].cohen_kappa == pytest.approx(1.0 / 3.0)
    assert by_facet["translation_quality"].cohen_kappa == pytest.approx(1.0 / 3.0)
    assert by_facet["uncertainty"].cohen_kappa == pytest.approx(1.0 / 3.0)
