from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.backend.rei.communication.conscious_access import (
    ConsciousAccessObservation,
    ConsciousAccessOption,
)
from app.backend.rei.communication.epistemic_interpreter import (
    MOTIVE_HYPOTHESIS_EXPLANATION_SL,
    MOTIVE_UNKNOWN_REASON_SL,
    OPTION_AMBIGUITY_SL,
    MotiveHypothesis,
    RacioEpistemicInterpretationV2,
    RacioEpistemicPacketV2,
)
from app.backend.rei.communication.structured_interpreter import (
    StructuredRacioInterpreterOutput,
)
from app.backend.rei.evaluation.c3_official_suite import (
    OFFICIAL_C3_INSTRUCTION_SHA256,
    OFFICIAL_C3_OUTPUT_SCHEMA_SHA256,
    OFFICIAL_HOLDOUT_MANIFEST_SHA256,
    OFFICIAL_REGRESSION_MANIFEST_SHA256,
    load_official_c3_suite_pair,
)
from app.backend.rei.evaluation.racio_epistemic import (
    EpistemicCaseGoldV2,
    EpistemicGoldMotiveHypothesis,
    RacioEpistemicCaseEvaluation,
    evaluate_racio_epistemic_bilingual_pair,
    evaluate_racio_epistemic_case,
)
from app.backend.rei.ids import canonical_json_bytes, sha256_hex
from app.backend.rei.providers.ollama_interpreter import (
    RACIO_INTERPRETER_STRUCTURED_INSTRUCTION,
)


INSTRUCTION_SHA256 = (
    "c5ea5a0936bbab5e9bb481e53443eb9119cb5bf2c1d58737f3bb0214ebcfb1b0"
)
OUTPUT_SCHEMA_SHA256 = (
    "7b51eeadc1e13223016a1ab95aab88b9141ed7d11a5400bd05cf25988645bd1c"
)


def _observation(
    observation_id: str,
    signal_name: str,
    visible_description: str,
) -> ConsciousAccessObservation:
    return ConsciousAccessObservation(
        observation_id=observation_id,
        signal_name=signal_name,
        perception_status="clear",
        perceived_value_json=canonical_json_bytes(
            {"visible_description": visible_description}
        ).decode("utf-8"),
        provenance="manifested",
    )


def _packet(*, language: str = "sl") -> RacioEpistemicPacketV2:
    descriptions = (
        (
            "Prisoten je impulz ustvariti razdaljo in jasno postaviti mejo.",
            "There is an impulse to create distance and set a clear boundary.",
        ),
        (
            "Sodelovanje se je škodljivo porušilo že večkrat.",
            "The collaboration has broken down harmfully several times.",
        ),
        (
            "Napetost se pojavi ob prestopu osebnega prostora.",
            "Tension appears when personal space is crossed.",
        ),
    )
    index = 0 if language == "sl" else 1
    return RacioEpistemicPacketV2.create(
        source_mind="E",
        language=language,
        visible_observations=(
            _observation("observation_001", "motor_urge", descriptions[0][index]),
            _observation("observation_002", "scene_signal", descriptions[1][index]),
            _observation("observation_003", "somatic_signal", descriptions[2][index]),
        ),
        omitted_observation_ids=(),
        public_option_scope=(
            ConsciousAccessOption(
                option_id="option_001",
                description=(
                    "Jasno verbalno zavrni in zaščiti mejo."
                    if language == "sl"
                    else "Clearly refuse verbally and protect the boundary."
                ),
            ),
            ConsciousAccessOption(
                option_id="option_002",
                description=(
                    "Fizično se odmakni in zaščiti isto mejo."
                    if language == "sl"
                    else "Step back physically and protect the same boundary."
                ),
            ),
        ),
        channel_quality=1.0,
        uncertainty=(
            "Akcija je vidna, njena modalnost in motiv pa nista nujno določljiva."
            if language == "sl"
            else (
                "The action is visible while its modality and motive may be "
                "unresolved."
            )
        ),
    )


def _hypothesis(
    family: str,
    subtype: str,
    confidence: float,
    *citations: str,
    explanation: str = MOTIVE_HYPOTHESIS_EXPLANATION_SL,
) -> MotiveHypothesis:
    return MotiveHypothesis(
        family=family,
        subtype=subtype,
        cited_observation_ids=tuple(sorted(citations)),
        confidence=confidence,
        explanation_short_sl=explanation,
    )


def _output(
    *,
    option_id: str | None = None,
    option_confidence: float = 0.0,
    motives: tuple[MotiveHypothesis, ...] = (),
    action: str = "set_boundary",
    action_confidence: float = 0.9,
    cited: tuple[str, ...] = ("observation_001",),
    ambiguity: str | None = OPTION_AMBIGUITY_SL,
) -> RacioEpistemicInterpretationV2:
    return RacioEpistemicInterpretationV2(
        source_mind="E",
        cited_observation_ids=tuple(sorted(cited)),
        inferred_action_tendency=action,
        action_confidence=action_confidence,
        inferred_option_id=option_id,
        option_confidence=option_confidence,
        motive_hypotheses=motives,
        motive_unknown_reason=(
            None
            if motives
            else MOTIVE_UNKNOWN_REASON_SL
        ),
        unresolved_ambiguity=ambiguity,
    )


def _gold(
    *,
    language: str = "sl",
    option_determinacy: str = "underdetermined",
    motives: tuple[EpistemicGoldMotiveHypothesis, ...] = (),
    motive_support_level: str = "not_identifiable",
) -> EpistemicCaseGoldV2:
    underdetermined = option_determinacy == "underdetermined"
    return EpistemicCaseGoldV2(
        case_id=f"case_{language}",
        bilingual_pair_id="pair_001",
        expected_source_mind="E",
        expected_language=language,
        option_determinacy=option_determinacy,
        acceptable_option_ids=(
            ("option_001", "option_002")
            if underdetermined
            else ("option_001",)
        ),
        option_support_observation_ids=(
            () if underdetermined else ("observation_001",)
        ),
        expected_action_tendencies=("set_boundary",),
        action_support_level="direct",
        action_support_observation_ids=("observation_001",),
        acceptable_motive_hypotheses=motives,
        motive_support_level=motive_support_level,
        maximum_action_confidence=0.95,
        maximum_option_confidence=(0.0 if underdetermined else 0.9),
        maximum_motive_confidence=0.8,
        required_abstention=underdetermined,
        forbidden_inferences=(
            "action_name_as_motive_evidence",
            "option_text_as_hidden_signal",
        ),
        source_claim_ids=("claim_001",),
        native_truth_id=f"native_truth_{language}",
        profile_id=f"profile_{language}",
        evaluator_only_canary=f"HIDDEN_CANARY_{language}",
    )


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {
            *(str(key) for key in value),
            *(nested for item in value.values() for nested in _walk_keys(item)),
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _walk_keys(item)}
    return set()


def test_v1_schema_and_hash_remain_unchanged() -> None:
    assert OFFICIAL_C3_INSTRUCTION_SHA256 == INSTRUCTION_SHA256
    assert OFFICIAL_C3_OUTPUT_SCHEMA_SHA256 == OUTPUT_SCHEMA_SHA256
    assert sha256_hex(RACIO_INTERPRETER_STRUCTURED_INSTRUCTION) == INSTRUCTION_SHA256
    assert (
        sha256_hex(StructuredRacioInterpreterOutput.model_json_schema())
        == OUTPUT_SCHEMA_SHA256
    )

    holdout, regression = load_official_c3_suite_pair()
    assert holdout.manifest_file_hash == OFFICIAL_HOLDOUT_MANIFEST_SHA256
    assert regression.manifest_file_hash == OFFICIAL_REGRESSION_MANIFEST_SHA256


def test_character_is_absent_from_v2_packet() -> None:
    packet = _packet()
    payload = packet.provider_payload()
    encoded = packet.provider_payload_bytes().decode("utf-8")
    forbidden = {
        "acceptance_mode",
        "character_profile",
        "authority_tier",
        "profile_weight",
        "resultant_leader",
        "native_truth_id",
        "profile_id",
        "expected_option_id",
        "expected_motive",
        "packet_id",
        "packet_hash",
    }
    assert forbidden.isdisjoint(_walk_keys(payload))
    assert packet.packet_id not in encoded
    assert packet.packet_hash not in encoded

    forged = packet.model_dump(mode="python", round_trip=True)
    forged["character_profile"] = "E>R>I"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RacioEpistemicPacketV2.model_validate(forged)


def test_action_does_not_imply_motive() -> None:
    packet = _packet()
    output = _output()

    assert output.validate_against(packet) is output
    assert output.inferred_action_tendency == "set_boundary"
    assert output.motive_hypotheses == ()
    assert output.motive_unknown_reason is not None


def test_action_or_option_text_cannot_support_a_motive() -> None:
    packet = _packet()
    action_only_motive = _hypothesis(
        "protection",
        "boundary_alarm",
        0.8,
        "observation_001",
    )
    output = _output(
        motives=(action_only_motive,),
        cited=("observation_001",),
    )

    result = evaluate_racio_epistemic_case(
        packet=packet,
        gold=_gold(),
        output=output,
        input_packet_unchanged=True,
    )

    assert result.hard_contract_pass is True
    assert result.action_support == "supported"
    assert result.motive_support == "unsupported"
    assert result.unsupported_motive_overclaim_count == 1
    assert "unsupported_motive_overclaim" in result.research_observations


def test_option_text_cannot_create_hidden_signal() -> None:
    packet = _packet()
    gold = _gold()
    overcommitted = _output(
        option_id="option_001",
        option_confidence=0.9,
        ambiguity=None,
    )

    result = evaluate_racio_epistemic_case(
        packet=packet,
        gold=gold,
        output=overcommitted,
        input_packet_unchanged=True,
    )

    assert result.hard_contract_pass is True
    assert result.action_support == "supported"
    assert result.option_mapping == "overcommitted"
    assert result.option_citation_support is False
    assert result.abstention_quality == "missed"
    assert "option_mapping_failure" in result.research_observations


def test_same_action_different_motive_is_valid() -> None:
    packet = _packet()
    scene = _hypothesis(
        "scene", "recurrent_broken_scene", 0.8, "observation_002"
    )
    protection = _hypothesis(
        "protection", "boundary_alarm", 0.8, "observation_003"
    )

    scene_output = _output(
        motives=(scene,), cited=("observation_001", "observation_002")
    )
    protection_output = _output(
        motives=(protection,), cited=("observation_001", "observation_003")
    )

    assert scene_output.validate_against(packet).inferred_action_tendency == (
        protection_output.validate_against(packet).inferred_action_tendency
    )
    assert scene_output.motive_hypotheses[0].family == "scene"
    assert protection_output.motive_hypotheses[0].family == "protection"


def test_gold_requires_motive_support_beyond_the_action_cue() -> None:
    action_only = EpistemicGoldMotiveHypothesis(
        family="protection",
        subtype="boundary_alarm",
        supporting_observation_ids=("observation_001",),
    )

    with pytest.raises(ValidationError, match="beyond the action cue"):
        _gold(
            motives=(action_only,),
            motive_support_level="unique",
        )


def test_hierarchical_gold_accepts_only_precommitted_alternatives() -> None:
    packet = _packet()
    general = EpistemicGoldMotiveHypothesis(
        family="protection",
        subtype="general_body_alarm",
        supporting_observation_ids=("observation_003",),
    )
    boundary = EpistemicGoldMotiveHypothesis(
        family="protection",
        subtype="boundary_alarm",
        supporting_observation_ids=("observation_003",),
    )
    gold = _gold(
        motives=(boundary, general),
        motive_support_level="hierarchical",
    )

    for subtype in ("general_body_alarm", "boundary_alarm"):
        hypothesis = _hypothesis(
            "protection",
            subtype,
            0.75,
            "observation_003",
        )
        result = evaluate_racio_epistemic_case(
            packet=packet,
            gold=gold,
            output=_output(
                motives=(hypothesis,),
                cited=("observation_001", "observation_003"),
            ),
            input_packet_unchanged=True,
        )
        assert result.motive_support == "hierarchy_compatible"
        assert result.motive_hypothesis_coverage == 1.0
        assert result.unsupported_motive_overclaim_count == 0

    sibling = _hypothesis(
        "protection",
        "resource_alarm",
        0.75,
        "observation_003",
    )
    sibling_result = evaluate_racio_epistemic_case(
        packet=packet,
        gold=gold,
        output=_output(
            motives=(sibling,),
            cited=("observation_001", "observation_003"),
        ),
        input_packet_unchanged=True,
    )
    assert sibling_result.motive_support == "unsupported"
    assert sibling_result.unsupported_motive_overclaim_count == 1


def test_same_action_two_modalities_requires_option_abstention() -> None:
    packet = _packet()
    gold = _gold()
    abstaining = _output()

    result = evaluate_racio_epistemic_case(
        packet=packet,
        gold=gold,
        output=abstaining,
        input_packet_unchanged=True,
    )

    assert result.option_determinacy == "underdetermined"
    assert result.option_mapping == "required_abstention"
    assert result.abstention_quality == "required_and_observed"
    assert result.motive_support == "unknown_preserved"


def test_motive_hypotheses_are_cited() -> None:
    with pytest.raises(ValidationError, match="requires visible observation"):
        _hypothesis("scene", "scene_repair", 0.7)

    outside = _hypothesis("scene", "scene_repair", 0.7, "observation_999")
    output = _output(
        motives=(outside,),
        cited=("observation_001", "observation_999"),
    )
    with pytest.raises(ValueError, match="outside packet scope"):
        output.validate_against(_packet())


def test_motive_hypotheses_max_three() -> None:
    hypotheses = (
        _hypothesis("scene", "broken_scene", 0.9, "observation_002"),
        _hypothesis("protection", "boundary_alarm", 0.8, "observation_003"),
        _hypothesis("motor_social", "motor_execution", 0.7, "observation_001"),
        _hypothesis("scene", "scene_repair", 0.6, "observation_002"),
    )
    with pytest.raises(ValidationError, match="At most three"):
        _output(
            motives=hypotheses,
            cited=("observation_001", "observation_002", "observation_003"),
        )

    reversed_rank = (
        _hypothesis("scene", "scene_repair", 0.7, "observation_002"),
        _hypothesis("scene", "broken_scene", 0.9, "observation_002"),
    )
    with pytest.raises(ValidationError, match="canonical confidence"):
        _output(motives=reversed_rank, cited=("observation_001", "observation_002"))


@pytest.mark.parametrize(
    "explanation",
    (
        "Oseba je depresivna in to je morda pravi opis.",
        "Karakter je morda E nad R nad I.",
        "Pravi motiv je boundary_alarm; to je morda hipoteza.",
        "Profil E>R>I lahko pojasni ta motiv.",
        "Motiv je boundary_alarm; morda je razlaga omejena.",
        "Gre za shizofrenijo; morda je to le hipoteza.",
        "Dokazano gre za boundary_alarm, vendar je to morda hipoteza.",
    ),
)
def test_motive_explanation_rejects_character_diagnosis_and_fact_claims(
    explanation: str,
) -> None:
    with pytest.raises(ValidationError):
        _hypothesis(
            "protection",
            "boundary_alarm",
            0.7,
            "observation_003",
            explanation=explanation,
        )


@pytest.mark.parametrize(
    ("field_name", "unsafe_text"),
    (
        (
            "motive_unknown_reason",
            "Oseba je depresivna, čeprav motiv morda ni določljiv.",
        ),
        (
            "unresolved_ambiguity",
            "Karakter je zagotovo razlog za to dvoumnost.",
        ),
    ),
)
def test_free_text_fields_reject_character_or_diagnosis_claims(
    field_name: str,
    unsafe_text: str,
) -> None:
    payload = _output().model_dump(mode="python", round_trip=True)
    payload[field_name] = unsafe_text
    with pytest.raises(ValidationError):
        RacioEpistemicInterpretationV2.model_validate(payload)


def test_unknown_motive_requires_reason() -> None:
    payload = _output().model_dump(mode="python")
    payload["motive_unknown_reason"] = None
    with pytest.raises(ValidationError, match="requires an unknown reason"):
        RacioEpistemicInterpretationV2.model_validate(payload)

    invalid_family = {
        "family": "scene",
        "subtype": "boundary_alarm",
        "cited_observation_ids": ("observation_003",),
        "confidence": 0.5,
        "explanation_short_sl": MOTIVE_HYPOTHESIS_EXPLANATION_SL,
    }
    with pytest.raises(ValidationError, match="does not belong"):
        MotiveHypothesis.model_validate(invalid_family)


def test_confidences_are_separate() -> None:
    packet = _packet()
    motive = _hypothesis(
        "scene", "recurrent_broken_scene", 0.6, "observation_002"
    )
    output = _output(
        option_id="option_001",
        option_confidence=0.4,
        action_confidence=0.9,
        motives=(motive,),
        cited=("observation_001", "observation_002"),
        ambiguity=None,
    )

    assert output.validate_against(packet) is output
    assert output.action_confidence == 0.9
    assert output.option_confidence == 0.4
    assert output.motive_hypotheses[0].confidence == 0.6
    fields = RacioEpistemicCaseEvaluation.model_fields
    assert "hard_contract_pass" in fields
    assert {
        "passed",
        "semantic_pass",
        "quality_gate_pass",
        "rei_score",
    }.isdisjoint(fields)


def test_evaluator_requires_support_ids_to_be_public() -> None:
    packet = _packet()
    gold_payload = _gold().model_dump(mode="python")
    gold_payload["action_support_observation_ids"] = ("observation_999",)
    gold = EpistemicCaseGoldV2.model_validate(gold_payload)

    with pytest.raises(ValueError, match="support aliases exceed"):
        evaluate_racio_epistemic_case(
            packet=packet,
            gold=gold,
            output=_output(),
            input_packet_unchanged=True,
        )


def test_bilingual_metric_compares_structured_semantics_and_confidence() -> None:
    sl_packet = _packet(language="sl")
    en_packet = _packet(language="en")
    sl_motive = _hypothesis(
        "scene",
        "recurrent_broken_scene",
        0.7,
        "observation_002",
        explanation=MOTIVE_HYPOTHESIS_EXPLANATION_SL,
    )
    en_motive = _hypothesis(
        "scene",
        "recurrent_broken_scene",
        0.75,
        "observation_002",
        explanation=MOTIVE_HYPOTHESIS_EXPLANATION_SL,
    )
    sl_output = _output(
        motives=(sl_motive,), cited=("observation_001", "observation_002")
    )
    en_output = RacioEpistemicInterpretationV2(
        **{
            **_output(
                motives=(en_motive,),
                cited=("observation_001", "observation_002"),
            ).model_dump(mode="python"),
            "source_mind": "E",
        }
    )

    result = evaluate_racio_epistemic_bilingual_pair(
        bilingual_pair_id="pair_001",
        sl_packet=sl_packet,
        sl_output=sl_output,
        en_packet=en_packet,
        en_output=en_output,
        confidence_tolerance=0.1,
    )

    assert result.action_consistent is True
    assert result.option_consistent is True
    assert result.motive_subtype_consistent is True
    assert result.motive_confidence_delta == 0.05
    assert result.motive_confidence_consistent is True


def test_provider_boundary_contains_no_evaluator_gold() -> None:
    packet = _packet()
    gold = _gold()
    encoded = packet.provider_payload_bytes().decode("utf-8")
    assert not any(token in encoded for token in gold.hidden_provider_tokens)
    assert gold.profile_id not in encoded
    assert "acceptable_motive_hypotheses" not in encoded
    assert "option_determinacy" not in encoded
    assert json.loads(encoded) == packet.provider_payload()
