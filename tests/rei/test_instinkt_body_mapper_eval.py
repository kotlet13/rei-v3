from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.evaluation.body_mapper_eval import (
    BODY_MAPPER_REPORT_FILENAMES,
    BodyMapperEvaluationReport,
    evaluate_body_mapper,
    load_body_mapper_gold,
    render_body_mapper_report,
    write_body_mapper_report,
)
from app.backend.rei.instinkt.effect_mapper import RuleBasedEmbodiedCueInterpreter
from app.backend.rei.instinkt.effect_rules import load_instinkt_effect_rules
from app.backend.rei.models.instinkt import BodyDelta
from app.backend.rei.models.instinkt_effects import (
    EmbodiedCueRule,
    InstinktEffectRuleSet,
)
from scripts.run_instinkt_body_mapper_eval import (
    DEFAULT_FIXTURE_ROOT,
    DEFAULT_GOLD_PATH,
    check_report,
)


REQUIRED_NEGATIVE_KINDS = {
    "unrelated_evidence",
    "unbound_cue",
    "mixed_valid_invalid_binding",
    "negated_evidence_en",
    "negated_evidence_sl",
    "negated_option_dont",
    "negated_option_cant",
    "negated_option_sl_ne",
    "distant_option_negation_en",
    "distant_option_negation_sl",
    "ambiguous_option",
    "keyword_trap",
    "metalinguistic_mention",
    "missing_information",
}


@pytest.fixture(scope="module")
def report() -> BodyMapperEvaluationReport:
    return evaluate_body_mapper(
        fixtures_root=DEFAULT_FIXTURE_ROOT,
        gold_path=DEFAULT_GOLD_PATH,
    )


def test_c5_gold_is_honest_internal_non_blind_and_has_full_coverage() -> None:
    suite, gold_sha256 = load_body_mapper_gold(DEFAULT_GOLD_PATH)
    raw = DEFAULT_GOLD_PATH.read_bytes()

    assert gold_sha256 == hashlib.sha256(raw).hexdigest()
    assert suite.training_export is False
    assert suite.model_generated_gold is False
    assert suite.status == "implementation_hypothesis"
    assert suite.review_status == "internal_non_blind"
    assert suite.gate_kind == "bounded_software_contract"
    assert len(suite.families) == 12
    assert sum(len(item.positive_cells) for item in suite.families) == 36
    assert len(suite.negative_controls) == 17
    assert {item.control_kind for item in suite.negative_controls} == (
        REQUIRED_NEGATIVE_KINDS
    )
    assert sum(
        item.control_kind == "metalinguistic_mention"
        for item in suite.negative_controls
    ) == 4
    for family in suite.families:
        assert {item.mode for item in family.positive_cells} == {
            "sl_primary",
            "sl_alternate",
            "en",
        }
        assert {item.language for item in family.positive_cells} == {"sl", "en"}
        assert all(item.cue_bindings for item in family.positive_cells)
        assert all(effect.body_deltas for effect in family.manual_effects)
        assert all(
            delta.tolerance == 0.05
            for effect in family.manual_effects
            for delta in effect.body_deltas
        )
        assert all(
            binding.assertion_status == "asserted_positive"
            and binding.cue_class
            and binding.cited_text
            for cell in family.positive_cells
            for binding in cell.cue_bindings
        )
        assert {effect.option_id for effect in family.manual_effects} >= {
            family.manual_expected_option_id
        }

    evaluator_source = inspect.getsource(evaluate_body_mapper)
    assert "ruleset.by_cue_class" not in evaluator_source
    assert "candidate_terms" not in evaluator_source


def test_c5_report_binds_inputs_and_replays_manual_b8(
    report: BodyMapperEvaluationReport,
) -> None:
    assert report.semantic_family_count == 12
    assert report.positive_cell_count == 36
    assert report.negative_control_count == 17
    assert report.gate_kind == "bounded_software_contract"
    assert report.gold_status == "implementation_hypothesis"
    assert report.review_status == "internal_non_blind"
    assert report.effect_vector_count == 72
    assert report.passing_effect_vector_count == report.effect_vector_count
    assert report.provenanced_delta_count == report.emitted_delta_count
    assert report.character_leakage_count == 0
    assert report.silent_default_count == 0
    assert report.gold_sha256 == hashlib.sha256(
        DEFAULT_GOLD_PATH.read_bytes()
    ).hexdigest()

    modes_by_family: dict[str, set[str]] = {}
    for case in report.cases:
        modes_by_family.setdefault(case.family_id, set()).add(case.mode)
        fixture_path = DEFAULT_FIXTURE_ROOT / f"{case.family_id}.json"
        assert case.fixture_sha256 == hashlib.sha256(
            fixture_path.read_bytes()
        ).hexdigest()
        assert case.packet_id
        assert case.packet_hash
        assert case.scene_hash
        assert case.cue_binding_ids
        assert len(case.cue_binding_ids) == len(case.cue_binding_hashes)
        assert case.manual_policy_status == case.expected_auto_status
        assert case.manual_effect_ids
        assert len(case.manual_effect_ids) == len(case.manual_effect_hashes)
        assert case.manual_policy_id
        assert case.manual_policy_hash
        assert case.manual_config_id
        assert case.manual_config_hash
        assert {item.option_id for item in case.manual_policy_scores} == set(
            case.option_ids
        )
        assert case.effect_vectors_agree is True
        assert {item.option_id for item in case.effect_vector_agreements} == set(
            case.option_ids
        )
        assert all(item.passes for item in case.effect_vector_agreements)
        assert all(
            item.expected_deltas and item.actual_deltas
            for item in case.effect_vector_agreements
        )
        if case.expected_auto_status == "selected":
            assert case.manual_option_id == case.manual_expected_option_id
        else:
            assert case.manual_option_id is None
        for option in case.option_results:
            assert option.source_scene_hash == case.scene_hash
            assert option.source_packet_id == case.packet_id
            assert option.source_packet_hash == case.packet_hash
            assert option.ruleset_id == report.ruleset_id
            assert option.ruleset_hash == report.ruleset_hash
            if option.delta_count:
                assert option.source_evidence_ids
                assert option.cue_binding_ids
    assert all(
        modes == {"sl_primary", "sl_alternate", "en"}
        for modes in modes_by_family.values()
    )


def test_c5_quality_failures_are_reported_not_silently_tuned(
    report: BodyMapperEvaluationReport,
) -> None:
    failed_positive = [item for item in report.cases if not item.passes]
    failed_negative = [
        item for item in report.negative_controls if not item.passes
    ]

    assert report.passing_case_count + len(failed_positive) == 36
    assert report.passing_negative_control_count + len(failed_negative) == 17
    assert report.contract_violation_count == (
        len(failed_positive) + len(failed_negative)
    )
    assert report.gate_passed is (report.contract_violation_count == 0)
    assert all(
        item.auto_policy_status in {
            "selected",
            "abstained_tie",
            "mapper_abstained",
            "mapper_error",
        }
        for item in report.cases
    )
    keyword_trap = next(
        item
        for item in report.negative_controls
        if item.control_kind == "keyword_trap"
    )
    if keyword_trap.actual_status != "mapper_abstained":
        assert keyword_trap.passes is False
        assert keyword_trap.no_emitted_effect is False


def test_c5_gate_rejects_same_policy_mutant_with_wrong_effect_vector() -> None:
    ruleset = load_instinkt_effect_rules()
    rules = list(ruleset.rules)
    index = next(
        index for index, rule in enumerate(rules) if rule.cue_class == "attachment"
    )
    source = rules[index]
    mutated_deltas = tuple(
        BodyDelta(
            dimension=item.dimension,
            delta=-0.25 if item.dimension == "uncertainty" else item.delta,
        )
        for item in source.protective_deltas
    )
    rules[index] = EmbodiedCueRule.model_validate(
        {
            **source.model_dump(mode="python", round_trip=True),
            "protective_deltas": mutated_deltas,
        }
    )
    mutant = RuleBasedEmbodiedCueInterpreter(
        InstinktEffectRuleSet.create(
            revision="c5-vector-mutant-test",
            minimum_association_score=ruleset.minimum_association_score,
            rules=tuple(rules),
            conflict_pairs=ruleset.conflict_pairs,
        )
    )

    mutant_report = evaluate_body_mapper(
        fixtures_root=DEFAULT_FIXTURE_ROOT,
        gold_path=DEFAULT_GOLD_PATH,
        mapper=mutant,
    )
    affected = tuple(
        item
        for item in mutant_report.cases
        if item.family_id == "sf_attachment_loss_fear"
    )

    assert affected
    assert all(item.manual_auto_agrees for item in affected)
    assert all(not item.effect_vectors_agree for item in affected)
    assert all(not item.passes for item in affected)
    assert mutant_report.passing_effect_vector_count < mutant_report.effect_vector_count
    assert mutant_report.gate_passed is False


def test_c5_report_validators_reject_derived_count_and_hash_tampering(
    report: BodyMapperEvaluationReport,
) -> None:
    payload = report.model_dump(mode="json", round_trip=True)
    round_trip = BodyMapperEvaluationReport.model_validate_json(
        json.dumps(payload, ensure_ascii=False)
    )
    assert round_trip == report

    tampered_count = dict(payload)
    tampered_count["positive_cell_count"] += 1
    with pytest.raises(ValidationError, match="derived fields differ"):
        BodyMapperEvaluationReport.model_validate_json(
            json.dumps(tampered_count, ensure_ascii=False)
        )

    tampered_hash = dict(payload)
    tampered_hash["report_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="hash differs"):
        BodyMapperEvaluationReport.model_validate_json(
            json.dumps(tampered_hash, ensure_ascii=False)
        )

    tampered_violation = dict(payload)
    tampered_violation["contract_violation_count"] = -1
    with pytest.raises(ValidationError):
        BodyMapperEvaluationReport.model_validate_json(
            json.dumps(tampered_violation, ensure_ascii=False)
        )


def test_body_mapper_report_is_reproducible_atomic_and_immutable(
    tmp_path: Path,
    report: BodyMapperEvaluationReport,
) -> None:
    output = tmp_path / "c5-report"
    rendered = render_body_mapper_report(report)
    written = write_body_mapper_report(report, output)

    assert tuple(path.name for path in written) == BODY_MAPPER_REPORT_FILENAMES
    check_report(output, rendered)
    with pytest.raises(FileExistsError, match="already exists"):
        write_body_mapper_report(report, output)

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    marker = occupied / "user-owned.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        write_body_mapper_report(report, occupied)
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert not any((occupied / name).exists() for name in BODY_MAPPER_REPORT_FILENAMES)


def test_body_mapper_writer_rejects_symlink_destination_before_writing(
    tmp_path: Path,
    report: BodyMapperEvaluationReport,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlinks unavailable on this host: {exc}")

    with pytest.raises(FileExistsError, match="symlink"):
        write_body_mapper_report(report, linked)
    assert not any((real / name).exists() for name in BODY_MAPPER_REPORT_FILENAMES)
