from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.backend.rei.communication.epistemic_interpreter import (
    RacioReportedUncertainty,
)
from app.backend.rei.communication.epistemic_interpreter_en import (
    ACTION_UNKNOWN_REASON_EN,
    MOTIVE_UNKNOWN_REASON_EN,
    OPTION_UNKNOWN_REASON_EN,
    EnglishObservationV3,
    EnglishOptionV3,
    RacioEpistemicPacketEnV3,
    canonicalize_racio_epistemic_draft_en_v3,
)
from app.backend.rei.communication.epistemic_interpreter_v3 import (
    ActionHypothesisDraftV3,
    MotiveHypothesisDraftV3,
    OptionInferenceDraftV3,
    RacioEpistemicDraftV3,
)


def _packet(*, option_description: str = "Move away from the marked point."):
    return RacioEpistemicPacketEnV3.create(
        source_mind="E",
        visible_observations=(
            EnglishObservationV3(
                observation_id="observation_002",
                atomic_evidence_unit_id="atomic_002",
                signal_alias="signal_002",
                perception_status="clear",
                text="The body increases its distance from the marked point.",
                provenance="manifested",
            ),
            EnglishObservationV3(
                observation_id="observation_001",
                atomic_evidence_unit_id="atomic_001",
                signal_alias="signal_001",
                perception_status="clear",
                text="One clear backward step is visible.",
                provenance="manifested",
            ),
        ),
        omitted_observation_ids=("observation_004", "observation_003"),
        public_option_scope=(
            EnglishOptionV3(
                option_id="option_001",
                description=option_description,
            ),
            EnglishOptionV3(
                option_id="option_002",
                description="Move toward the marked point.",
            ),
        ),
        channel_quality=0.9,
        uncertainty=(
            "The filter may omit or degrade part of the signal; keep any inference "
            "hypothetical."
        ),
    )


def _uncertainty() -> RacioReportedUncertainty:
    return RacioReportedUncertainty(
        option_mapping="uncertain",
        motive_interpretation="not_reported",
    )


def test_full_abstention_is_valid_and_uses_only_english_bounded_reasons() -> None:
    packet = _packet()
    output = canonicalize_racio_epistemic_draft_en_v3(
        packet,
        RacioEpistemicDraftV3(
            source_mind="E",
            action_hypotheses=(),
            option_inference=None,
            motive_hypotheses=(),
            racio_reported_uncertainty=_uncertainty(),
        ),
    )

    assert output.language == "en"
    assert output.cited_observation_ids == ()
    assert output.action_hypotheses == ()
    assert output.action_unknown_reason == ACTION_UNKNOWN_REASON_EN
    assert output.option_inference is None
    assert output.option_unknown_reason == OPTION_UNKNOWN_REASON_EN
    assert output.motive_hypotheses == ()
    assert output.motive_unknown_reason == MOTIVE_UNKNOWN_REASON_EN
    assert output.racio_reported_uncertainty == _uncertainty()


def test_claims_preserve_semantics_and_canonicalize_only_order_and_citations() -> None:
    packet = _packet()
    draft = RacioEpistemicDraftV3(
        source_mind="E",
        action_hypotheses=(
            ActionHypothesisDraftV3(
                family="protection_regulation",
                subtype="seek_safety",
                cited_observation_ids=("observation_002",),
                confidence=0.61,
                support_mode="functional_inference",
            ),
            ActionHypothesisDraftV3(
                family="protection_regulation",
                subtype="retreat",
                cited_observation_ids=(
                    "observation_002",
                    "observation_001",
                    "observation_001",
                ),
                confidence=0.82,
                support_mode="direct_manifestation",
            ),
        ),
        option_inference=OptionInferenceDraftV3(
            option_id="option_001",
            cited_observation_ids=("observation_002", "observation_001"),
            confidence=0.74,
        ),
        motive_hypotheses=(
            MotiveHypothesisDraftV3(
                family="protection",
                subtype="escape_alarm",
                cited_observation_ids=("observation_002",),
                confidence=0.43,
                support_mode="contextually_supported",
            ),
        ),
        racio_reported_uncertainty=_uncertainty(),
    )

    output = canonicalize_racio_epistemic_draft_en_v3(packet, draft)

    assert tuple(item.subtype for item in output.action_hypotheses) == (
        "retreat",
        "seek_safety",
    )
    assert output.action_hypotheses[0].cited_observation_ids == (
        "observation_001",
        "observation_002",
    )
    assert output.action_hypotheses[0].support_mode == "direct_manifestation"
    assert output.action_hypotheses[0].confidence == 0.82
    assert output.option_inference is not None
    assert output.option_inference.option_id == "option_001"
    assert output.option_inference.cited_observation_ids == (
        "observation_001",
        "observation_002",
    )
    assert output.motive_hypotheses[0].family == "protection"
    assert output.motive_hypotheses[0].subtype == "escape_alarm"
    assert output.motive_hypotheses[0].support_mode == "contextually_supported"
    assert output.cited_observation_ids == (
        "observation_001",
        "observation_002",
    )
    assert output.action_unknown_reason is None
    assert output.option_unknown_reason is None
    assert output.motive_unknown_reason is None


@pytest.mark.parametrize("claim_kind", ("action", "option", "motive"))
def test_claim_citations_outside_visible_scope_fail_closed(claim_kind: str) -> None:
    action = ()
    option = None
    motive = ()
    if claim_kind == "action":
        action = (
            ActionHypothesisDraftV3(
                family="protection_regulation",
                subtype="retreat",
                cited_observation_ids=("observation_999",),
                confidence=0.8,
                support_mode="direct_manifestation",
            ),
        )
    elif claim_kind == "option":
        option = OptionInferenceDraftV3(
            option_id="option_001",
            cited_observation_ids=("observation_999",),
            confidence=0.8,
        )
    else:
        motive = (
            MotiveHypothesisDraftV3(
                family="protection",
                subtype="escape_alarm",
                cited_observation_ids=("observation_999",),
                confidence=0.8,
                support_mode="speculative",
            ),
        )

    with pytest.raises(ValueError, match="outside visible English packet scope"):
        canonicalize_racio_epistemic_draft_en_v3(
            _packet(),
            RacioEpistemicDraftV3(
                source_mind="E",
                action_hypotheses=action,
                option_inference=option,
                motive_hypotheses=motive,
                racio_reported_uncertainty=_uncertainty(),
            ),
        )


def test_option_outside_public_scope_and_source_mismatch_fail_closed() -> None:
    packet = _packet()
    outside_option = RacioEpistemicDraftV3(
        source_mind="E",
        action_hypotheses=(),
        option_inference=OptionInferenceDraftV3(
            option_id="option_999",
            cited_observation_ids=("observation_001",),
            confidence=0.8,
        ),
        motive_hypotheses=(),
        racio_reported_uncertainty=_uncertainty(),
    )
    with pytest.raises(ValueError, match="outside public English option scope"):
        canonicalize_racio_epistemic_draft_en_v3(packet, outside_option)

    wrong_source = RacioEpistemicDraftV3(
        source_mind="I",
        action_hypotheses=(),
        option_inference=None,
        motive_hypotheses=(),
        racio_reported_uncertainty=_uncertainty(),
    )
    with pytest.raises(ValueError, match="source mind differs"):
        canonicalize_racio_epistemic_draft_en_v3(packet, wrong_source)


@pytest.mark.parametrize(
    "draft_factory",
    (
        lambda: ActionHypothesisDraftV3(
            family="protection_regulation",
            subtype="retreat",
            cited_observation_ids=(),
            confidence=0.8,
            support_mode="direct_manifestation",
        ),
        lambda: OptionInferenceDraftV3(
            option_id="option_001",
            cited_observation_ids=(),
            confidence=0.8,
        ),
        lambda: MotiveHypothesisDraftV3(
            family="protection",
            subtype="escape_alarm",
            cited_observation_ids=(),
            confidence=0.8,
            support_mode="speculative",
        ),
    ),
)
def test_every_populated_claim_still_requires_local_evidence(draft_factory) -> None:
    with pytest.raises(ValidationError, match="requires claim-local citations"):
        draft_factory()


def test_provider_payload_is_explicitly_english_and_has_no_bilingual_keys() -> None:
    packet = _packet()
    payload = packet.provider_payload()
    encoded = packet.provider_payload_bytes().decode("utf-8")

    assert payload["language"] == "en"
    assert payload["visible_observations"][0]["text"] == (
        "One clear backward step is visible."
    )
    assert payload["public_option_scope"][0]["description"] == (
        "Move away from the marked point."
    )
    assert payload["uncertainty"].startswith("The filter may omit")
    assert "canonical_sl" not in encoded
    assert "operational_en" not in encoded
    assert "gloss_audit" not in encoded
    assert json.loads(encoded) == payload


def test_packet_rejects_non_english_language_metadata() -> None:
    payload = _packet().model_dump(mode="python", round_trip=True)
    payload["language"] = "sl"

    with pytest.raises(ValidationError, match="Input should be 'en'"):
        RacioEpistemicPacketEnV3.model_validate(payload)


def test_packet_and_interpretation_ids_and_hashes_are_stable() -> None:
    first_packet = _packet()
    repeated_packet = _packet()
    changed_packet = _packet(option_description="Increase physical distance.")

    assert first_packet == repeated_packet
    assert first_packet.packet_id == repeated_packet.packet_id
    assert first_packet.packet_hash == repeated_packet.packet_hash
    assert changed_packet.packet_id != first_packet.packet_id
    assert changed_packet.packet_hash != first_packet.packet_hash

    draft = RacioEpistemicDraftV3(
        source_mind="E",
        action_hypotheses=(),
        option_inference=None,
        motive_hypotheses=(),
        racio_reported_uncertainty=_uncertainty(),
    )
    first_output = canonicalize_racio_epistemic_draft_en_v3(first_packet, draft)
    repeated_output = canonicalize_racio_epistemic_draft_en_v3(
        repeated_packet,
        draft,
    )

    assert first_output == repeated_output
    assert first_output.interpretation_id == repeated_output.interpretation_id
    assert first_output.interpretation_hash == repeated_output.interpretation_hash
    assert first_output.interpretation_hash == first_output.content_hash(
        exclude_fields=frozenset({"interpretation_hash"})
    )
