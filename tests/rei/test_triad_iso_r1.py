from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.models.provider import ProviderCallRecord
from app.backend.rei.research.triad_iso_r1 import (
    R1_OUTPUT_RELATIVE_PATH,
    cold_verify_r1,
    compile_semantic_emocio_representation,
    corrected_candidate,
    formal_verify_e1,
    frozen_e1_inventory,
    material_rejection_adjudication,
    racio_commensurability_preflight,
    replay_emocio,
    replay_instinkt_sensitivity,
    seal_reconciliation,
    semantic_emocio_valuations,
    semantic_route_source,
    validate_json_projection,
)
from app.backend.rei.research.triad_iso_e1 import (
    CANDIDATE_RELATIVE_PATH,
    OUTPUT_RELATIVE_PATH,
)
from app.backend.rei.models.racio import RacioInputPacket


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _call_record() -> dict:
    return json.loads(
        (
            REPOSITORY_ROOT
            / OUTPUT_RELATIVE_PATH
            / "cases/trip_protective_context_exposed/call_record.json"
        ).read_text(encoding="utf-8")
    )["racio"]["call_record"]


def _candidate_case(case_id: str) -> dict:
    candidate = json.loads(
        (REPOSITORY_ROOT / CANDIDATE_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    return next(
        case
        for pair in candidate["pairs"]
        for case in pair["variants"]
        if case["case_id"] == case_id
    )


def test_json_mode_rehydrates_valid_tuple_and_datetime() -> None:
    record = validate_json_projection(ProviderCallRecord, _call_record())

    assert isinstance(record.input_artifact_ids, tuple)
    assert record.started_at.tzinfo is not None


def test_json_mode_rejects_invalid_tuple_item() -> None:
    payload = copy.deepcopy(_call_record())
    payload["input_artifact_ids"][0] = 7

    with pytest.raises(ValidationError):
        validate_json_projection(ProviderCallRecord, payload)


def test_json_mode_rejects_invalid_datetime() -> None:
    payload = copy.deepcopy(_call_record())
    payload["started_at"] = "not-an-iso-8601-datetime"

    with pytest.raises(ValidationError):
        validate_json_projection(ProviderCallRecord, payload)


def test_original_e1_formally_verifies_without_byte_mutation() -> None:
    before = frozen_e1_inventory(REPOSITORY_ROOT)
    result = formal_verify_e1(REPOSITORY_ROOT)
    after = frozen_e1_inventory(REPOSITORY_ROOT)

    assert result["status"] == "passed"
    assert result["validation_mode"] == "pydantic_json"
    assert result["domain_validators_relaxed"] is False
    assert before == after


def test_seal_reconciliation_identifies_s2_value() -> None:
    result = seal_reconciliation(REPOSITORY_ROOT)

    assert result["reported_value_origin"]["phase"] == "TRIAD-S2"
    assert result["committed_e1_origin"]["phase"] == "TRIAD-ISO-E1"
    assert result["verdict"] == "operator_response_cross_phase_misattribution"
    assert result["e1_artifact_or_calculation_defect"] is False


def test_material_rejection_has_exact_bounded_diagnostic() -> None:
    result = material_rejection_adjudication(REPOSITORY_ROOT)
    diagnostic = result["adjudication"]

    assert diagnostic["unsupported_evidence_ids"] == ("utility_ev_rarity",)
    assert diagnostic["used_facts_without_required_citations"] == ()
    assert diagnostic["evidence_to_fact_mapping"]["utility_ev_rarity"] == (
        "The same offer was available once during the last three years."
    )
    assert diagnostic["exact_contract_preserved"] is True
    assert diagnostic["thinking_included"] is False


def test_current_racio_packet_marks_budget_base_under_specified() -> None:
    inputs = json.loads(
        (
            REPOSITORY_ROOT
            / OUTPUT_RELATIVE_PATH
            / "cases/trip_racio_utility_material/inputs.json"
        ).read_text(encoding="utf-8")
    )
    packet = validate_json_projection(RacioInputPacket, inputs["racio"]["packet"])
    result = racio_commensurability_preflight(packet)

    assert result["absolute_spend_present"] is True
    assert result["budget_base_status"] == "under_specified"
    assert result["comparison_status"] == "partially_commensurable"
    assert result["required_route_constraints"]["confidence_cap"] == 0.65
    assert result["required_route_constraints"]["hardcoded_abstention"] is False


def test_semantic_equivalent_prose_and_irrelevant_text_do_not_change_projection() -> None:
    case = _candidate_case("trip_racio_utility_material")
    source = semantic_route_source(case)
    alternate = copy.deepcopy(source)
    alternate["irrelevant_prose"] = (
        "Different narration that does not change any typed relation."
    )

    assert compile_semantic_emocio_representation(source) == (
        compile_semantic_emocio_representation(alternate)
    )


def test_companion_without_added_enjoyment_does_not_change_attraction() -> None:
    case = _candidate_case("trip_protective_context_exposed")
    without = semantic_route_source(case)
    with_companion = copy.deepcopy(without)
    with_companion["companion_visible"] = True
    with_companion["companion_adds_grounded_enjoyment"] = False
    left = semantic_emocio_valuations(
        compile_semantic_emocio_representation(without)
    )
    right = semantic_emocio_valuations(
        compile_semantic_emocio_representation(with_companion)
    )

    left_attraction = {
        item.option_id: next(
            value.score for value in item.dimensions if value.name == "attraction"
        )
        for item in left
    }
    right_attraction = {
        item.option_id: next(
            value.score for value in item.dimensions if value.name == "attraction"
        )
        for item in right
    }
    assert left_attraction == right_attraction


def test_semantic_movement_and_ordinal_attraction_remain_distinct() -> None:
    source = compile_semantic_emocio_representation(
        semantic_route_source(_candidate_case("trip_racio_utility_material"))
    )
    valuations = semantic_emocio_valuations(source)
    vectors = {
        item.option_id: {
            value.name: value.score for value in item.dimensions
        }
        for item in valuations
    }

    assert vectors["utility_trip_book"]["movement"] == 1.0
    assert vectors["utility_trip_local"]["movement"] == 0.5
    assert vectors["utility_trip_home"]["movement"] == 0.0
    assert vectors["utility_trip_book"]["attraction"] == 1.0
    assert vectors["utility_trip_local"]["attraction"] == 0.6


def test_semantic_option_order_does_not_change_output() -> None:
    source = semantic_route_source(_candidate_case("trip_racio_utility_material"))
    reversed_source = copy.deepcopy(source)
    reversed_source["options"] = list(reversed(reversed_source["options"]))

    assert semantic_emocio_valuations(
        compile_semantic_emocio_representation(source)
    ) == semantic_emocio_valuations(
        compile_semantic_emocio_representation(reversed_source)
    )


def test_emocio_replay_distinguishes_old_collapse_without_processor_run() -> None:
    result = replay_emocio(REPOSITORY_ROOT)

    assert len(result["cases"]) == 4
    assert all(
        item["old_abstention_cause"] == "representation_collapse"
        for item in result["cases"]
    )
    assert all(item["native_processor_executions"] == 0 for item in result["cases"])
    assert all(item["model_calls"] == 0 for item in result["cases"])


def test_instinkt_sensitivity_removes_only_unsupported_upgrades() -> None:
    result = replay_instinkt_sensitivity(REPOSITORY_ROOT)
    supported = next(
        item
        for item in result["cases"]
        if item["case_id"] == "trip_protective_context_supported"
    )
    exposed = next(
        item
        for item in result["cases"]
        if item["case_id"] == "trip_protective_context_exposed"
    )

    assert "necessary" not in supported["corrected_protected_target"].casefold()
    assert supported["frozen_consequence_facts_changed"] is False
    assert all(
        "avoids_distant_exposure" not in item["corrected_effect_categories"]
        for item in supported["corrected_effect_paths"]
    )
    assert any(
        "avoids_unfamiliar_uncertain_exposure"
        in item["corrected_effect_categories"]
        for item in exposed["corrected_effect_paths"]
    )
    assert supported["option_flip_targeted"] is False
    assert supported["instinkt_native_processor_executions"] == 0


def test_corrected_candidate_is_unsealed_and_leakage_free() -> None:
    candidate = corrected_candidate(REPOSITORY_ROOT)
    utility = next(
        item
        for item in candidate["cases"]
        if item["case_id"] == "trip_racio_utility_material"
    )

    assert candidate["status"] == "unsealed_candidate"
    assert candidate["execution_authorized"] is False
    assert candidate["model_calls"] == 0
    assert candidate["character_replay"] == 0
    assert any(
        fact["evidence_id"] == "utility_ev_budget_base"
        for fact in utility["operational_en"]["facts"]
    )
    assert utility["route_packets"]["instinkt"]["protected_target_semantics"][
        "budget_kind"
    ] == "discretionary_budget"


def test_committed_r1_outputs_cold_verify_when_present() -> None:
    if not (REPOSITORY_ROOT / R1_OUTPUT_RELATIVE_PATH / "manifest.json").is_file():
        pytest.skip("TRIAD-ISO-R1 outputs have not been prepared yet")

    result = cold_verify_r1(REPOSITORY_ROOT)
    assert result["status"] == "passed"
    assert result["model_calls"] == 0
    assert result["character_replay_rows"] == 0
