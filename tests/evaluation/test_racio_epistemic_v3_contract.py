from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.communication.epistemic_interpreter import (
    MOTIVE_UNKNOWN_REASON_SL,
    RacioEpistemicInterpretationV2,
    RacioEpistemicPacketV2,
    RacioReportedUncertainty,
)
from app.backend.rei.communication.epistemic_interpreter_v3 import (
    ACTION_SUBTYPES_BY_FAMILY_V3,
    ACTION_UNKNOWN_REASON_SL_V3,
    LEGACY_ACTION_RESOLUTION_V3,
    ActionHypothesisV3,
    AuditedBilingualTextV3,
    BilingualGlossAuditV3,
    BilingualObservationV3,
    BilingualOptionV3,
    BilingualUncertaintyV3,
    MotiveHypothesisV3,
    RacioEpistemicInterpretationV3,
    RacioEpistemicPacketV3,
    RacioEpistemicStructuralSidecarV3,
    reserved_bilingual_markers_v3,
)
from app.backend.rei.communication.structured_interpreter import (
    StructuredRacioInterpreterOutput,
)
from app.backend.rei.evaluation.racio_epistemic import (
    EpistemicCaseGoldV2,
    RacioEpistemicBilingualEvaluation,
    RacioEpistemicCaseEvaluation,
)
from app.backend.rei.evaluation.racio_epistemic_v3 import (
    EpistemicCaseGoldV3,
    EpistemicGoldActionHypothesisV3,
    EpistemicGoldMotiveHypothesisV3,
    RacioEpistemicBilingualEvaluationV3,
    RacioEpistemicCaseEvaluationV3,
    evaluate_racio_epistemic_bilingual_pair_v3,
    evaluate_racio_epistemic_case_v3,
)
from app.backend.rei.ids import sha256_hex


REPO_ROOT = Path(__file__).resolve().parents[2]
G3_ROOT = (
    REPO_ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "g3-gemma4-racio-epistemic-2026-07-17"
)


def _plain_text(canonical_sl: str) -> AuditedBilingualTextV3:
    return AuditedBilingualTextV3(canonical_sl=canonical_sl)


def _audited_text(
    canonical_sl: str,
    operational_en: str,
    *,
    signature: tuple[str, ...] = ("role:visible", "stage:none"),
) -> AuditedBilingualTextV3:
    audit = BilingualGlossAuditV3.create(
        reviewer_id="human_reviewer_001",
        canonical_sl=canonical_sl,
        operational_en=operational_en,
        canonical_sl_signature=signature,
        operational_en_signature=signature,
        approved=True,
        signatures_equivalent=True,
        reserved_collisions_aligned=True,
        no_added_action_claims=True,
        no_added_motive_claims=True,
        no_added_causal_claims=True,
        role_aligned=True,
        strength_aligned=True,
        polarity_aligned=True,
        modality_aligned=True,
    )
    return AuditedBilingualTextV3(
        canonical_sl=canonical_sl,
        operational_en=operational_en,
        gloss_audit=audit,
    )


def _packet(
    *,
    presentation_mode: str = "canonical_sl_only",
    canonical_suffix: str = "",
) -> RacioEpistemicPacketV3:
    bilingual = presentation_mode != "canonical_sl_only"

    def visible(sl: str, en: str) -> AuditedBilingualTextV3:
        sl = f"{sl}{canonical_suffix}"
        return _audited_text(sl, en) if bilingual else _plain_text(sl)

    observations = (
        BilingualObservationV3(
            observation_id="observation_001",
            signal_alias="signal_001",
            perception_status="clear",
            text=visible("Vidna je prva smer.", "The first direction is visible."),
            provenance="manifested",
        ),
        BilingualObservationV3(
            observation_id="observation_002",
            signal_alias="signal_002",
            perception_status="clear",
            text=visible("Vidna je druga opora.", "The second support is visible."),
            provenance="manifested",
        ),
        BilingualObservationV3(
            observation_id="observation_003",
            signal_alias="signal_003",
            perception_status="clear",
            text=visible("Vidna je tretja opora.", "The third support is visible."),
            provenance="manifested",
        ),
    )
    option_text = visible("Izberi prvo možnost.", "Choose the first option.")
    uncertainty_text = visible(
        "Negotovost ostaja omejena.",
        "Uncertainty remains bounded.",
    )
    return RacioEpistemicPacketV3.create(
        source_mind="E",
        presentation_mode=presentation_mode,
        visible_observations=observations,
        omitted_observation_ids=(),
        public_option_scope=(
            BilingualOptionV3(option_id="option_001", text=option_text),
        ),
        channel_quality=1.0,
        uncertainty=BilingualUncertaintyV3(text=uncertainty_text),
    )


def _action(
    *,
    family: str = "protection_regulation",
    subtype: str | None = "set_boundary",
    family_fallback: str | None = None,
    citations: tuple[str, ...] = ("observation_001",),
    confidence: float = 0.9,
    support_mode: str = "direct_manifestation",
) -> ActionHypothesisV3:
    return ActionHypothesisV3(
        family=family,
        subtype=subtype,
        family_fallback=family_fallback,
        cited_observation_ids=citations,
        confidence=confidence,
        support_mode=support_mode,
    )


def _motive(
    *,
    family: str = "protection",
    subtype: str = "boundary_alarm",
    citations: tuple[str, ...] = ("observation_002",),
    confidence: float = 0.8,
    support_mode: str = "directly_supported",
) -> MotiveHypothesisV3:
    return MotiveHypothesisV3(
        family=family,
        subtype=subtype,
        cited_observation_ids=citations,
        confidence=confidence,
        support_mode=support_mode,
    )


def _output(
    *,
    actions: tuple[ActionHypothesisV3, ...] | None = None,
    motives: tuple[MotiveHypothesisV3, ...] = (),
    option_id: str | None = "option_001",
    option_uncertainty: str = "not_uncertain",
    motive_uncertainty: str = "not_uncertain",
) -> RacioEpistemicInterpretationV3:
    if actions is None:
        actions = (_action(),)
    cited = tuple(
        sorted(
            {
                *(item for action in actions for item in action.cited_observation_ids),
                *(item for motive in motives for item in motive.cited_observation_ids),
                *(("observation_001",) if option_id is not None else ()),
            }
        )
    )
    return RacioEpistemicInterpretationV3(
        source_mind="E",
        cited_observation_ids=cited,
        action_hypotheses=actions,
        action_unknown_reason=(None if actions else ACTION_UNKNOWN_REASON_SL_V3),
        inferred_option_id=option_id,
        option_confidence=(0.8 if option_id is not None else 0.0),
        motive_hypotheses=motives,
        motive_unknown_reason=(None if motives else MOTIVE_UNKNOWN_REASON_SL),
        racio_reported_uncertainty=RacioReportedUncertainty(
            option_mapping=option_uncertainty,
            motive_interpretation=motive_uncertainty,
        ),
    )


def _gold_action(
    *,
    family: str = "protection_regulation",
    subtype: str | None = "set_boundary",
    family_fallback: str | None = None,
    role: str = "exact",
    citations: tuple[str, ...] = ("observation_001",),
    modes: tuple[str, ...] = ("direct_manifestation",),
) -> EpistemicGoldActionHypothesisV3:
    return EpistemicGoldActionHypothesisV3(
        family=family,
        subtype=subtype,
        family_fallback=family_fallback,
        role=role,
        supporting_observation_ids=citations,
        accepted_support_modes=modes,
    )


def _gold_motive(
    *,
    family: str = "protection",
    subtype: str = "boundary_alarm",
    reference_support_mode: str = "directly_supported",
    citations: tuple[str, ...] = ("observation_002",),
) -> EpistemicGoldMotiveHypothesisV3:
    return EpistemicGoldMotiveHypothesisV3(
        family=family,
        subtype=subtype,
        reference_support_mode=reference_support_mode,
        supporting_observation_ids=citations,
    )


def _gold(
    *,
    presentation_mode: str = "canonical_sl_only",
    actions: tuple[EpistemicGoldActionHypothesisV3, ...] | None = None,
    motives: tuple[EpistemicGoldMotiveHypothesisV3, ...] | None = None,
    expected_action_unknown: bool = False,
    motive_identifiability: str = "identifiable",
    action_only: tuple[str, ...] = ("observation_001",),
) -> EpistemicCaseGoldV3:
    if actions is None:
        actions = () if expected_action_unknown else (_gold_action(),)
    if motives is None:
        motives = (
            ()
            if motive_identifiability == "not_identifiable"
            else (_gold_motive(),)
        )
    return EpistemicCaseGoldV3(
        case_id="case_001",
        bilingual_pair_id="pair_001",
        expected_source_mind="E",
        expected_presentation_mode=presentation_mode,
        option_determinacy="unique",
        acceptable_option_ids=("option_001",),
        option_support_observation_ids=("observation_001",),
        required_abstention=False,
        expected_action_unknown=expected_action_unknown,
        acceptable_action_hypotheses=tuple(sorted(actions, key=lambda item: item.key)),
        motive_identifiability=motive_identifiability,
        acceptable_motive_hypotheses=tuple(
            sorted(motives, key=lambda item: item.key)
        ),
        action_only_observation_ids=action_only,
        high_confidence_unsupported_threshold=0.5,
        source_claim_ids=("claim_secret",),
        native_truth_id="native_truth_secret",
        profile_id="profile_secret",
        evaluator_only_canary="EVALUATOR_ONLY_CANARY",
    )


def _evaluate(
    output: RacioEpistemicInterpretationV3,
    *,
    gold: EpistemicCaseGoldV3 | None = None,
    packet: RacioEpistemicPacketV3 | None = None,
) -> RacioEpistemicCaseEvaluationV3:
    packet = packet or _packet()
    gold = gold or _gold()
    return evaluate_racio_epistemic_case_v3(
        packet=packet,
        gold=gold,
        output=output,
        input_packet_unchanged=True,
    )


def test_v1_v2_hashes_and_frozen_g3_artifacts_still_cold_validate() -> None:
    expected_hashes = {
        StructuredRacioInterpreterOutput: (
            "7b51eeadc1e13223016a1ab95aab88b9141ed7d11a5400bd05cf25988645bd1c"
        ),
        RacioEpistemicPacketV2: (
            "9c3f879b71f0dc39a99db0b123cb5fa02e0dec38fbde8d0c3652e8157ae1c2e1"
        ),
        RacioEpistemicInterpretationV2: (
            "35d41e6cedbb04fab84ff87499a22b4349713bcba766164d8b1acd5adb86f9db"
        ),
        EpistemicCaseGoldV2: (
            "3d61da032ada72b5757e99b41cc572fdfea078f85fff6e59d964211a91343b57"
        ),
        RacioEpistemicCaseEvaluation: (
            "0b5bcdfc7f20dc618ac20ae945acde687b4c35129da653126dfb7e8f0af7b7dc"
        ),
        RacioEpistemicBilingualEvaluation: (
            "97fdf3ac2f745452b5546757028f8fecc68e518a8ecb15f92a3937d24a04d106"
        ),
    }
    for model, expected in expected_hashes.items():
        assert sha256_hex(model.model_json_schema()) == expected

    manifest = json.loads(
        (
            REPO_ROOT
            / "knowledge/canon_v2/semantic_lab_v1/gemma4_epistemic_dev_v1/manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["frozen_profile"]["output_schema_sha256"] == (
        "16602d51fb48f6b64b415ea22693bae16ebf67a97a9ca52703cdd58ca4cae49e"
    )

    case_dirs = sorted((G3_ROOT / "cases").iterdir())
    assert len(case_dirs) == 16
    for case_dir in case_dirs:
        packet = RacioEpistemicPacketV2.model_validate_json(
            (case_dir / "sanitized_packet.json").read_text(encoding="utf-8")
        )
        output = RacioEpistemicInterpretationV2.model_validate_json(
            (case_dir / "structured_output.json").read_text(encoding="utf-8")
        )
        evaluation = RacioEpistemicCaseEvaluation.model_validate_json(
            (case_dir / "case_evaluation.json").read_text(encoding="utf-8")
        )
        assert output.validate_against(packet) is output
        assert evaluation.case_id == case_dir.name

    pair_files = sorted((G3_ROOT / "bilingual_pairs").glob("*.json"))
    assert len(pair_files) == 8
    for pair_file in pair_files:
        wrapper = json.loads(pair_file.read_text(encoding="utf-8"))
        pair = RacioEpistemicBilingualEvaluation.model_validate(
            wrapper["evaluation"]
        )
        assert pair.bilingual_pair_id == wrapper["bilingual_pair_id"]


def test_v2_and_v3_shapes_do_not_silently_coerce() -> None:
    v3_payload = _output().model_dump(mode="python", round_trip=True)
    with pytest.raises(ValidationError):
        RacioEpistemicInterpretationV2.model_validate(v3_payload)

    v2_payload = json.loads(
        (
            G3_ROOT / "cases/g3_h1_sl/structured_output.json"
        ).read_text(encoding="utf-8")
    )
    with pytest.raises(ValidationError):
        RacioEpistemicInterpretationV3.model_validate(v2_payload)


def test_v3_action_taxonomy_resolves_legacy_ambiguities() -> None:
    assert "seek_attachment" not in {
        subtype
        for values in ACTION_SUBTYPES_BY_FAMILY_V3.values()
        for subtype in values
    }
    assert LEGACY_ACTION_RESOLUTION_V3["seek_attachment"] == (
        "approach_engage/seek_contact",
    )
    assert len(LEGACY_ACTION_RESOLUTION_V3["maintain"]) == 3
    assert LEGACY_ACTION_RESOLUTION_V3["unknown"] == ()
    assert LEGACY_ACTION_RESOLUTION_V3["withdraw"] == ()
    assert LEGACY_ACTION_RESOLUTION_V3["withdraw_contact"] == (
        "protection_regulation/withdraw_contact",
    )

    for legacy in ("seek_attachment", "maintain", "unknown", "withdraw"):
        with pytest.raises(ValidationError):
            _action(subtype=legacy)

    assert _action(family="approach_engage", subtype="seek_contact").subtype == (
        "seek_contact"
    )
    assert _action(subtype="maintain_boundary").subtype == "maintain_boundary"
    assert _action(subtype="withdraw_contact").subtype == "withdraw_contact"
    fallback = _action(subtype=None, family_fallback="protect")
    assert fallback.key == (
        "protection_regulation",
        "<family_fallback:protect>",
    )


@pytest.mark.parametrize(
    ("action", "gold_actions", "family", "subtype", "overclaims", "code"),
    (
        (
            _action(),
            (_gold_action(),),
            1.0,
            1.0,
            0,
            "supported_exact",
        ),
        (
            _action(family="approach_engage", subtype="approach"),
            (
                _gold_action(family="approach_engage", subtype="connect"),
                _gold_action(
                    family="approach_engage",
                    subtype="approach",
                    role="acceptable_sibling",
                ),
            ),
            1.0,
            0.0,
            0,
            "supported_acceptable_sibling",
        ),
        (
            _action(subtype=None, family_fallback="protect"),
            (
                _gold_action(),
                _gold_action(
                    subtype=None,
                    family_fallback="protect",
                    role="parent_fallback",
                ),
            ),
            1.0,
            0.0,
            0,
            "supported_parent_fallback",
        ),
        (
            _action(subtype="seek_safety"),
            (_gold_action(),),
            1.0,
            0.0,
            1,
            "family_only_unsupported_subtype",
        ),
        (
            _action(subtype=None, family_fallback="protect"),
            (_gold_action(),),
            0.0,
            0.0,
            1,
            "unaccepted_family_fallback",
        ),
        (
            _action(family="confrontation", subtype="attack"),
            (_gold_action(),),
            0.0,
            0.0,
            1,
            "wrong_family",
        ),
    ),
)
def test_action_family_subtype_parent_and_sibling_are_independent(
    action: ActionHypothesisV3,
    gold_actions: tuple[EpistemicGoldActionHypothesisV3, ...],
    family: float,
    subtype: float,
    overclaims: int,
    code: str,
) -> None:
    result = _evaluate(_output(actions=(action,)), gold=_gold(actions=gold_actions))
    assert result.action_family_support == family
    assert result.action_subtype_support == subtype
    assert result.action_unsupported_overclaims == overclaims
    assert result.action_hypothesis_assessments[0].assessment == code


def test_attack_and_compete_share_family_but_are_not_exact() -> None:
    attack_gold = (_gold_action(family="confrontation", subtype="attack"),)
    compete = _action(family="confrontation", subtype="compete")
    result = _evaluate(_output(actions=(compete,)), gold=_gold(actions=attack_gold))
    assert result.action_family_support == 1.0
    assert result.action_subtype_support == 0.0
    assert result.action_unsupported_overclaims == 1


def test_action_bounds_order_citations_and_speculative_support() -> None:
    first = _action(confidence=0.9)
    second = _action(
        family="protection_regulation",
        subtype="seek_safety",
        confidence=0.8,
    )
    third = _action(
        family="confrontation", subtype="attack", confidence=0.7
    )
    payload = _output(actions=(first,)).model_dump(mode="python", round_trip=True)
    payload["action_hypotheses"] = (first, second, third)
    with pytest.raises(ValidationError, match="At most two action"):
        RacioEpistemicInterpretationV3.model_validate(payload)

    payload["action_hypotheses"] = (second, first)
    with pytest.raises(ValidationError, match="canonical confidence"):
        RacioEpistemicInterpretationV3.model_validate(payload)

    outside = _action(citations=("observation_999",))
    outside_output = _output(actions=(outside,))
    with pytest.raises(ValueError, match="outside packet scope"):
        outside_output.validate_against(_packet())

    speculative = _action(support_mode="speculative")
    result = _evaluate(_output(actions=(speculative,)))
    assert result.action_family_support == 0.0
    assert result.action_subtype_support == 0.0
    assert result.action_unsupported_overclaims == 0
    assessment = result.action_hypothesis_assessments[0]
    assert assessment.assessment == "speculative_not_supported"
    assert assessment.identity_precommitted is True
    assert assessment.citation_support is True
    assert assessment.support_mode_accepted is False

    wrong_speculative = _action(
        family="confrontation",
        subtype="attack",
        support_mode="speculative",
    )
    wrong_result = _evaluate(_output(actions=(wrong_speculative,)))
    wrong_assessment = wrong_result.action_hypothesis_assessments[0]
    assert wrong_assessment.assessment == "wrong_family"
    assert wrong_assessment.identity_precommitted is False
    assert wrong_result.action_unsupported_overclaims == 1


def test_direct_motive_gold_and_output_require_non_action_evidence() -> None:
    action_only_motive = _gold_motive(citations=("observation_001",))
    with pytest.raises(ValidationError, match="non-action observation support"):
        _gold(motives=(action_only_motive,))

    output = _output(
        motives=(_motive(citations=("observation_001",)),)
    )
    result = _evaluate(output)
    assessment = result.motive_hypothesis_assessments[0]
    assert assessment.assessment == "action_only_evidence"
    assert assessment.identity_precommitted is True
    assert assessment.citation_support is False
    assert assessment.action_evidence_cited is True
    assert assessment.action_only_evidence is True
    assert result.motive_family_coverage == 0.0
    assert result.motive_subtype_coverage == 0.0
    assert result.motive_precision == 0.0


def test_only_direct_motive_support_counts_reference_metrics() -> None:
    direct = _evaluate(_output(motives=(_motive(),)))
    assert direct.motive_family_coverage == 1.0
    assert direct.motive_subtype_coverage == 1.0
    assert direct.motive_precision == 1.0

    contextual = _evaluate(
        _output(motives=(_motive(support_mode="contextually_supported"),))
    )
    assert contextual.motive_family_coverage == 0.0
    assert contextual.motive_subtype_coverage == 0.0
    assert contextual.motive_precision == 0.0
    assert contextual.contextual_motive_hypothesis_count == 1

    speculative = _evaluate(
        _output(motives=(_motive(support_mode="speculative"),))
    )
    assert speculative.motive_family_coverage == 0.0
    assert speculative.motive_precision == 0.0
    assert speculative.speculative_motive_hypothesis_count == 1
    speculative_assessment = speculative.motive_hypothesis_assessments[0]
    assert speculative_assessment.identity_precommitted is True
    assert speculative_assessment.citation_support is True

    wrong_speculative = _motive(
        family="motor_social",
        subtype="competition",
        citations=("observation_001",),
        support_mode="speculative",
    )
    wrong = _evaluate(_output(motives=(wrong_speculative,)))
    wrong_assessment = wrong.motive_hypothesis_assessments[0]
    assert wrong_assessment.assessment == "unsupported_identity"
    assert wrong_assessment.action_evidence_cited is True
    assert wrong_assessment.action_only_evidence is True
    assert wrong.motive_unsupported_overclaims == 1

    wrong_subtype = _evaluate(
        _output(motives=(_motive(subtype="attachment_alarm"),))
    )
    wrong_subtype_assessment = wrong_subtype.motive_hypothesis_assessments[0]
    assert wrong_subtype_assessment.assessment == (
        "family_only_unsupported_subtype"
    )
    assert wrong_subtype_assessment.family_credit is True
    assert wrong_subtype_assessment.subtype_credit is False
    assert wrong_subtype.motive_family_coverage == 1.0
    assert wrong_subtype.motive_subtype_coverage == 0.0
    assert wrong_subtype.motive_precision == 0.0
    assert wrong_subtype.motive_unsupported_overclaims == 1


def test_contextually_bounded_gold_preserves_non_direct_unknown_state() -> None:
    contextual_gold = _gold_motive(
        family="motor_social",
        subtype="connection",
        reference_support_mode="contextually_supported",
    )
    gold = _gold(
        motives=(contextual_gold,),
        motive_identifiability="contextually_bounded",
    )
    contextual_output = _output(
        motives=(
            _motive(
                family="motor_social",
                subtype="connection",
                support_mode="contextually_supported",
            ),
        )
    )
    contextual = _evaluate(contextual_output, gold=gold)
    assert contextual.motive_family_coverage == 1.0
    assert contextual.motive_subtype_coverage == 1.0
    assert contextual.motive_precision == 0.0
    assert contextual.unknown_preservation.motive == "preserved"
    assert contextual.motive_hypothesis_assessments[0].assessment == (
        "contextually_supported_not_reference"
    )

    direct_claim = contextual_output.model_copy(
        update={
            "motive_hypotheses": (
                contextual_output.motive_hypotheses[0].model_copy(
                    update={"support_mode": "directly_supported"}
                ),
            )
        }
    )
    direct = _evaluate(direct_claim, gold=gold)
    assert direct.unknown_preservation.motive == "violated"
    assert direct.motive_hypothesis_assessments[0].assessment == (
        "support_mode_overclaim"
    )

    empty = _evaluate(_output(motives=()), gold=gold)
    assert empty.motive_precision == 1.0
    assert empty.unknown_preservation.motive == "preserved"

    action_only_context_gold = (
        _gold_motive(
            family="motor_social",
            subtype="connection",
            reference_support_mode="contextually_supported",
            citations=("observation_001",),
        ),
        _gold_motive(
            family="scene",
            subtype="desired_scene_mismatch",
            reference_support_mode="contextually_supported",
            citations=("observation_001",),
        ),
    )
    action_only_context_output = (
        _motive(
            family="motor_social",
            subtype="connection",
            citations=("observation_001",),
            confidence=0.9,
            support_mode="contextually_supported",
        ),
        _motive(
            family="scene",
            subtype="desired_scene_mismatch",
            citations=("observation_001",),
            confidence=0.8,
            support_mode="contextually_supported",
        ),
    )
    nonminimal = _evaluate(
        _output(motives=action_only_context_output),
        gold=_gold(
            motives=action_only_context_gold,
            motive_identifiability="contextually_bounded",
        ),
    )
    assert nonminimal.motive_redundant_nonminimal_count == 1
    second = nonminimal.motive_hypothesis_assessments[1]
    assert second.assessment == "redundant_nonminimal"
    assert second.action_only_evidence is True
    assert second.redundant_nonminimal is True


def test_additional_motive_requires_distinct_non_action_evidence() -> None:
    boundary = _gold_motive()
    scene_same_evidence = _gold_motive(
        family="scene",
        subtype="desired_scene_mismatch",
        citations=("observation_002",),
    )
    motives = (
        _motive(confidence=0.9),
        _motive(
            family="scene",
            subtype="desired_scene_mismatch",
            confidence=0.8,
        ),
    )
    with pytest.raises(ValidationError, match="own independent non-action"):
        _gold(motives=(boundary, scene_same_evidence))

    contextual_scene_same_evidence = _gold_motive(
        family="scene",
        subtype="desired_scene_mismatch",
        reference_support_mode="contextually_supported",
        citations=("observation_002",),
    )
    contextual_motives = (
        motives[0],
        motives[1].model_copy(update={"support_mode": "contextually_supported"}),
    )
    redundant = _evaluate(
        _output(motives=contextual_motives),
        gold=_gold(motives=(boundary, contextual_scene_same_evidence)),
    )
    assert redundant.motive_redundant_nonminimal_count == 1
    assert redundant.motive_precision == 0.5

    higher_ranked_contextual = (
        _motive(
            family="scene",
            subtype="desired_scene_mismatch",
            confidence=0.9,
            support_mode="contextually_supported",
        ),
        _motive(confidence=0.8),
    )
    ranked_redundant = _evaluate(
        _output(motives=higher_ranked_contextual),
        gold=_gold(motives=(boundary, contextual_scene_same_evidence)),
    )
    assert ranked_redundant.motive_redundant_nonminimal_count == 1
    assert ranked_redundant.motive_precision == 0.0

    scene_distinct = _gold_motive(
        family="scene",
        subtype="desired_scene_mismatch",
        citations=("observation_003",),
    )
    distinct_motives = (
        _motive(confidence=0.9),
        _motive(
            family="scene",
            subtype="desired_scene_mismatch",
            citations=("observation_003",),
            confidence=0.8,
        ),
    )
    supported = _evaluate(
        _output(motives=distinct_motives),
        gold=_gold(motives=(boundary, scene_distinct)),
    )
    assert supported.motive_redundant_nonminimal_count == 0
    assert supported.motive_precision == 1.0
    assert supported.motive_subtype_coverage == 1.0


def test_r3_connection_is_action_surface_or_context_not_direct_motive() -> None:
    seek_contact = _action(family="approach_engage", subtype="seek_contact")
    action_gold = (
        _gold_action(family="approach_engage", subtype="seek_contact"),
    )
    attachment = _gold_motive(
        family="protection",
        subtype="attachment_alarm",
        citations=("observation_002",),
    )
    connection_context = _gold_motive(
        family="motor_social",
        subtype="connection",
        reference_support_mode="contextually_supported",
        citations=("observation_002",),
    )
    gold = _gold(
        actions=action_gold,
        motives=(connection_context, attachment),
        action_only=("observation_001",),
    )

    contextual = _motive(
        family="motor_social",
        subtype="connection",
        support_mode="contextually_supported",
    )
    contextual_result = _evaluate(
        _output(actions=(seek_contact,), motives=(contextual,)),
        gold=gold,
    )
    assert contextual_result.action_subtype_support == 1.0
    assert contextual_result.motive_subtype_coverage == 0.0
    assert contextual_result.motive_precision == 0.0
    assert contextual_result.motive_hypothesis_assessments[0].assessment == (
        "contextually_supported_not_reference"
    )

    direct_claim = _motive(
        family="motor_social",
        subtype="connection",
        support_mode="directly_supported",
    )
    direct_result = _evaluate(
        _output(actions=(seek_contact,), motives=(direct_claim,)),
        gold=gold,
    )
    assert direct_result.motive_hypothesis_assessments[0].assessment == (
        "support_mode_overclaim"
    )
    assert direct_result.high_confidence_unsupported_motive_count == 1

    primary = _motive(
        family="protection",
        subtype="attachment_alarm",
        confidence=0.9,
    )
    extra = _motive(
        family="motor_social",
        subtype="connection",
        confidence=0.8,
        support_mode="contextually_supported",
    )
    combined = _evaluate(
        _output(actions=(seek_contact,), motives=(primary, extra)),
        gold=gold,
    )
    assert combined.motive_redundant_nonminimal_count == 1
    assert combined.motive_precision == 0.5


def test_unknown_action_and_motive_are_preserved_without_fake_labels() -> None:
    output = _output(actions=(), motives=())
    result = _evaluate(
        output,
        gold=_gold(
            expected_action_unknown=True,
            motive_identifiability="not_identifiable",
            action_only=(),
        ),
    )
    assert result.unknown_preservation.action == "preserved"
    assert result.unknown_preservation.motive == "preserved"
    assert result.action_family_support == 1.0
    assert result.motive_precision == 1.0

    speculative = _motive(support_mode="speculative")
    violated = _evaluate(
        _output(actions=(), motives=(speculative,)),
        gold=_gold(
            expected_action_unknown=True,
            motive_identifiability="not_identifiable",
            action_only=(),
        ),
    )
    assert violated.unknown_preservation.motive == "violated"
    assert "motive_unknown_preservation_failure" in violated.research_observations


def test_bilingual_audit_binds_one_identity_and_rejects_semantic_drift() -> None:
    packet = _packet(presentation_mode="canonical_sl_plus_operational_en")
    payload = packet.provider_payload()
    assert len(payload["visible_observations"]) == 3
    assert {
        item["observation_id"] for item in payload["visible_observations"]
    } == {"observation_001", "observation_002", "observation_003"}
    encoded = packet.provider_payload_bytes().decode("utf-8")
    assert "gloss_audit" not in encoded
    assert "audit_hash" not in encoded

    aligned_motive = _audited_text("alarm meje", "boundary alarm")
    assert aligned_motive.gloss_audit is not None
    assert reserved_bilingual_markers_v3("alarm meje") == (
        "motive:protection/boundary_alarm",
    )
    assert reserved_bilingual_markers_v3("alarm meje") == (
        reserved_bilingual_markers_v3("boundary alarm")
    )

    bound = _audited_text("Vidna sprememba.", "A change is visible.")
    forged = bound.model_dump(mode="python", round_trip=True)
    forged["operational_en"] = "A different change is visible."
    with pytest.raises(ValidationError, match="does not bind"):
        AuditedBilingualTextV3.model_validate(forged)

    with pytest.raises(ValidationError):
        _audited_text("umik", "escape from danger")
    with pytest.raises(ValidationError):
        _audited_text("set boundary", "boundary alarm")
    with pytest.raises(ValidationError):
        _audited_text("A visible change.", "A visible change because of danger.")

    with pytest.raises(ValidationError, match="semantic signatures"):
        BilingualGlossAuditV3.create(
            reviewer_id="human_reviewer_001",
            canonical_sl="Vidna sprememba.",
            operational_en="A visible change.",
            canonical_sl_signature=("strength:possible",),
            operational_en_signature=("strength:definite",),
            approved=True,
            signatures_equivalent=True,
            reserved_collisions_aligned=True,
            no_added_action_claims=True,
            no_added_motive_claims=True,
            no_added_causal_claims=True,
            role_aligned=True,
            strength_aligned=True,
            polarity_aligned=True,
            modality_aligned=True,
        )


@pytest.mark.parametrize(
    ("canonical_sl", "operational_en", "marker"),
    (
        (
            "pristop in vključevanje",
            "approach engage",
            "action_family:approach_engage",
        ),
        (
            "zaščitna regulacija",
            "protection regulation",
            "action_family:protection_regulation",
        ),
        ("soočenje", "confrontation", "action_family:confrontation"),
        (
            "izvedba in izražanje",
            "execution expression",
            "action_family:execution_expression",
        ),
        (
            "motorično socialno",
            "motor social",
            "motive_family:motor_social",
        ),
        ("zaščita", "protection", "motive_family:protection"),
        ("porušen prizor", "broken scene", "motive:scene/broken_scene"),
        (
            "želeni prizor manjka",
            "desired scene absent",
            "motive:scene/desired_scene_absent",
        ),
        (
            "neskladje želenega prizora",
            "desired scene mismatch",
            "motive:scene/desired_scene_mismatch",
        ),
        (
            "ponavljajoč se porušen prizor",
            "recurrent broken scene",
            "motive:scene/recurrent_broken_scene",
        ),
        (
            "uresničitev prizora",
            "scene realization",
            "motive:scene/scene_realization",
        ),
        ("popravilo prizora", "scene repair", "motive:scene/scene_repair"),
        (
            "pozornost ali status",
            "attention or status",
            "motive:motor_social/attention_or_status",
        ),
        (
            "tekmovalnost",
            "competition",
            "motive:motor_social/competition",
        ),
        ("povezanost", "connection", "motive:motor_social/connection"),
        (
            "motorična izvedba",
            "motor execution",
            "motive:motor_social/motor_execution",
        ),
        (
            "alarm navezanosti",
            "attachment alarm",
            "motive:protection/attachment_alarm",
        ),
        (
            "alarm meje",
            "boundary alarm",
            "motive:protection/boundary_alarm",
        ),
        (
            "alarm pobega",
            "escape alarm",
            "motive:protection/escape_alarm",
        ),
        (
            "splošni telesni alarm",
            "general body alarm",
            "motive:protection/general_body_alarm",
        ),
        (
            "alarm virov",
            "resource alarm",
            "motive:protection/resource_alarm",
        ),
        (
            "alarm zaupanja",
            "trust alarm",
            "motive:protection/trust_alarm",
        ),
    ),
)
def test_bilingual_marker_audit_aligns_slovenian_motive_terms(
    canonical_sl: str,
    operational_en: str,
    marker: str,
) -> None:
    audited = _audited_text(canonical_sl, operational_en)
    assert audited.gloss_audit is not None
    canonical_markers = reserved_bilingual_markers_v3(canonical_sl)
    operational_markers = reserved_bilingual_markers_v3(operational_en)
    assert marker in canonical_markers
    assert canonical_markers == operational_markers


def test_english_presentation_requires_audited_observation_option_and_uncertainty() -> None:
    packet = _packet()
    payload = packet.model_dump(mode="python", round_trip=True)
    payload["presentation_mode"] = "operational_en_only"
    payload.pop("packet_id")
    payload.pop("packet_hash")
    with pytest.raises(ValidationError, match="English presentation"):
        RacioEpistemicPacketV3.create(
            source_mind=payload["source_mind"],
            presentation_mode=payload["presentation_mode"],
            visible_observations=packet.visible_observations,
            omitted_observation_ids=packet.omitted_observation_ids,
            public_option_scope=packet.public_option_scope,
            channel_quality=packet.channel_quality,
            uncertainty=packet.uncertainty,
        )


def test_bilingual_metrics_keep_family_subtype_support_and_uncertainty_separate() -> None:
    sl_packet = _packet(presentation_mode="canonical_sl_only")
    en_packet = _packet(presentation_mode="operational_en_only")
    sl_output = _output(
        actions=(_action(subtype="set_boundary"),),
        option_uncertainty="not_reported",
    )
    en_output = _output(
        actions=(_action(subtype="seek_safety"),),
        option_uncertainty="uncertain",
    )
    pair = evaluate_racio_epistemic_bilingual_pair_v3(
        bilingual_pair_id="pair_001",
        sl_packet=sl_packet,
        sl_output=sl_output,
        en_packet=en_packet,
        en_output=en_output,
    )
    assert pair.bilingual_family_consistency.action is True
    assert pair.bilingual_subtype_consistency.action is False
    assert pair.uncertainty_consistency.option is False

    extra_speculative = _motive(
        family="protection",
        subtype="general_body_alarm",
        confidence=0.7,
        support_mode="speculative",
    )
    en_with_extra = _output(motives=(extra_speculative,))
    motive_pair = evaluate_racio_epistemic_bilingual_pair_v3(
        bilingual_pair_id="pair_001",
        sl_packet=sl_packet,
        sl_output=_output(),
        en_packet=en_packet,
        en_output=en_with_extra,
    )
    assert motive_pair.bilingual_subtype_consistency.motive is False
    assert motive_pair.motive_support_mode_consistency is False

    sl_ranked = _output(
        actions=(
            _action(subtype="set_boundary", confidence=0.9),
            _action(
                subtype="seek_safety",
                citations=("observation_002",),
                confidence=0.8,
            ),
        )
    )
    en_ranked = _output(
        actions=(
            _action(
                subtype="seek_safety",
                citations=("observation_002",),
                confidence=0.95,
            ),
            _action(subtype="set_boundary", confidence=0.7),
        )
    )
    reordered = evaluate_racio_epistemic_bilingual_pair_v3(
        bilingual_pair_id="pair_001",
        sl_packet=sl_packet,
        sl_output=sl_ranked,
        en_packet=en_packet,
        en_output=en_ranked,
    )
    assert reordered.bilingual_subtype_consistency.action is True
    assert reordered.citation_identity_consistency is True

    changed_en_packet = _packet(
        presentation_mode="operational_en_only",
        canonical_suffix=" Druga identiteta.",
    )
    with pytest.raises(ValueError, match="same canonical evidence"):
        evaluate_racio_epistemic_bilingual_pair_v3(
            bilingual_pair_id="pair_001",
            sl_packet=sl_packet,
            sl_output=_output(),
            en_packet=changed_en_packet,
            en_output=_output(),
        )

    with pytest.raises(ValueError, match="EN pair member"):
        evaluate_racio_epistemic_bilingual_pair_v3(
            bilingual_pair_id="pair_001",
            sl_packet=sl_packet,
            sl_output=_output(),
            en_packet=sl_packet,
            en_output=_output(),
        )


def test_sidecar_is_structural_only_and_v3_has_no_runtime_authority() -> None:
    output = _output(motives=(_motive(support_mode="speculative"),))
    sidecar = RacioEpistemicStructuralSidecarV3.from_output(output)
    assert set(RacioEpistemicStructuralSidecarV3.model_fields) == {
        "option_id_present",
        "motive_hypothesis_count",
    }
    assert sidecar.option_id_present is True
    assert sidecar.motive_hypothesis_count == 1

    forged_output = output.model_dump(mode="python", round_trip=True)
    forged_output["option_id_present"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        RacioEpistemicInterpretationV3.model_validate(forged_output)

    assert "sidecar" not in inspect.signature(
        evaluate_racio_epistemic_case_v3
    ).parameters
    assert {
        "passed",
        "semantic_pass",
        "quality_gate_pass",
        "rei_score",
    }.isdisjoint(RacioEpistemicCaseEvaluationV3.model_fields)
    assert {
        "passed",
        "semantic_pass",
        "quality_gate_pass",
        "rei_score",
    }.isdisjoint(RacioEpistemicBilingualEvaluationV3.model_fields)

    runtime_paths = (
        "app/backend/rei/engine.py",
        "app/backend/rei/governance/resolver.py",
        "app/backend/rei/conscious/committer.py",
        "app/backend/rei/governance/behavior.py",
        "app/backend/rei/providers/ollama_gemma4_epistemic.py",
    )
    forbidden = (
        "epistemic_interpreter_v3",
        "racio_epistemic_v3",
        "RacioEpistemicStructuralSidecarV3",
    )
    for relative in runtime_paths:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden)
