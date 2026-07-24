from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.research.triad_iso_r1 import cold_verify_r1, formal_verify_e1
from app.backend.rei.research.triad_iso_r2 import (
    R2_EFFECT_RULES,
    R2_OUTPUT_RELATIVE_PATH,
    author_emocio_annotation,
    author_instinkt_mapping,
    cold_verify_r2,
    compile_emocio_typed_annotation,
    compile_instinkt_typed_mapping,
    corrected_candidate_v2,
    e1_instinkt_projection_inputs,
    frozen_r1_inventory,
    project_emocio_typed_valuations,
    project_instinkt_typed_sensitivity,
    replay_emocio_typed,
    replay_instinkt_typed,
    source_evidence_address,
    source_option_address,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
R1_CANDIDATE = (
    REPOSITORY_ROOT
    / "Docs/evals/semantic_lab_v1/triad-route-isolation-e1r-2026-07-24/"
    "corrected_candidate.json"
)


def _r1_case(case_id: str) -> dict:
    candidate = json.loads(R1_CANDIDATE.read_text(encoding="utf-8"))
    return next(item for item in candidate["cases"] if item["case_id"] == case_id)


def _vectors(annotation) -> dict[str, dict[str, float]]:
    return {
        item.option_id: {
            dimension.name: dimension.score for dimension in item.dimensions
        }
        for item in project_emocio_typed_valuations(annotation)
    }


def _rename_options(
    case: dict,
    *,
    annotation: dict | None = None,
    mapping: dict | None = None,
) -> dict[str, str]:
    old_ids = [item["option_id"] for item in case["operational_en"]["options"]]
    renames = {
        old_id: f"option_{chr(ord('a') + index)}"
        for index, old_id in enumerate(old_ids)
    }
    for language in ("canonical_sl", "operational_en"):
        for option in case[language]["options"]:
            option["option_id"] = renames[option["option_id"]]
    for change in case["route_packets"]["emocio"]["option_visible_changes"]:
        change["option_id"] = renames[change["option_id"]]
    for consequence in case["route_packets"]["instinkt"]["option_consequences"]:
        consequence["option_id"] = renames[consequence["option_id"]]
    if annotation is not None:
        for option in annotation["options"]:
            option["option_id"] = renames[option["option_id"]]
            option["source_option_sha256"] = source_option_address(
                case, option["option_id"]
            )
        annotation["source_evidence_sha256"] = source_evidence_address(case)
    if mapping is not None:
        for effect in mapping["option_effects"]:
            effect["option_id"] = renames[effect["option_id"]]
            effect["source_option_sha256"] = source_option_address(
                case, effect["option_id"]
            )
            for category in effect["categories"]:
                category["option_id"] = effect["option_id"]
        mapping["source_evidence_sha256"] = source_evidence_address(case)
    return renames


def _normalized_instinkt_mapping(mapping) -> list[dict]:
    return sorted(
        [
        {
            "source_consequence": item.source_consequence,
            "scope": item.source_evidence_scope_ids,
            "categories": [
                {
                    "predicate": category.semantic_predicate,
                    "evidence": category.supporting_evidence_ids,
                    "deltas": tuple(
                        (delta.dimension, delta.delta)
                        for delta in category.body_deltas
                    ),
                }
                for category in item.categories
            ],
        }
        for item in mapping.option_effects
        ],
        key=lambda item: item["source_consequence"],
    )


def test_emocio_compiler_has_no_case_or_lexical_option_inference() -> None:
    source = inspect.getsource(compile_emocio_typed_annotation)

    assert "case_id" not in source
    assert ".endswith" not in source
    assert "trip_book" not in source
    assert "trip_local" not in source
    assert "trip_home" not in source


def test_emocio_opaque_option_ids_preserve_semantic_valuation() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    original = compile_emocio_typed_annotation(case, annotation)
    renamed_case = copy.deepcopy(case)
    renamed_annotation = copy.deepcopy(annotation)
    renames = _rename_options(
        renamed_case,
        annotation=renamed_annotation,
    )
    renamed = compile_emocio_typed_annotation(
        renamed_case, renamed_annotation
    )
    original_vectors = _vectors(original)
    renamed_vectors = _vectors(renamed)

    assert {
        renames[option_id]: vector
        for option_id, vector in original_vectors.items()
    } == renamed_vectors


def test_emocio_case_id_is_not_part_of_semantic_result() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    renamed = copy.deepcopy(case)
    renamed["case_id"] = "opaque_case"

    assert compile_emocio_typed_annotation(
        case, annotation
    ) == compile_emocio_typed_annotation(renamed, annotation)


def test_emocio_option_order_is_canonicalized() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    reversed_annotation = copy.deepcopy(annotation)
    reversed_annotation["options"].reverse()

    assert compile_emocio_typed_annotation(
        case, annotation
    ) == compile_emocio_typed_annotation(case, reversed_annotation)


def test_emocio_real_prose_paraphrase_does_not_change_typed_valuation() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    paraphrase = copy.deepcopy(case)
    route = paraphrase["route_packets"]["emocio"]
    route["current_scene"] = "A differently worded view of the same route state."
    route["desired_scene"] = "The same desired relations, phrased another way."
    route["broken_scene"] = "The same broken relations in alternate prose."
    for index, item in enumerate(route["option_visible_changes"]):
        item["change"] = f"Paraphrased visible consequence {index}."

    assert compile_emocio_typed_annotation(
        case, annotation
    ) == compile_emocio_typed_annotation(paraphrase, annotation)
    assert _vectors(
        compile_emocio_typed_annotation(case, annotation)
    ) == _vectors(compile_emocio_typed_annotation(paraphrase, annotation))


def test_emocio_attraction_relation_changes_only_attraction_dimension() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    changed = copy.deepcopy(annotation)
    book = next(
        item
        for item in changed["options"]
        if item["option_id"] == "utility_trip_book"
    )
    book["attraction_strength"]["value"] = "present"
    original_vectors = _vectors(
        compile_emocio_typed_annotation(case, annotation)
    )
    changed_vectors = _vectors(
        compile_emocio_typed_annotation(case, changed)
    )
    left = original_vectors["utility_trip_book"]
    right = changed_vectors["utility_trip_book"]

    assert {
        name for name in left if left[name] != right[name]
    } == {"attraction"}


def test_visible_companion_without_enjoyment_does_not_change_attraction() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    changed = copy.deepcopy(annotation)
    changed["companion_visible"]["value"] = "absent"
    left = _vectors(compile_emocio_typed_annotation(case, annotation))
    right = _vectors(compile_emocio_typed_annotation(case, changed))

    assert {
        option_id: vector["attraction"]
        for option_id, vector in left.items()
    } == {
        option_id: vector["attraction"]
        for option_id, vector in right.items()
    }


def test_emocio_competition_is_not_inferred_from_obstacle_removal() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = compile_emocio_typed_annotation(
        case, author_emocio_annotation(case)
    )
    vectors = _vectors(annotation)

    assert all(
        item.competition_relation.state == "not_relevant"
        for item in annotation.options
    )
    assert all(
        vector["competitive_success"] == 0.0
        for vector in vectors.values()
    )
    assert vectors["utility_trip_book"][
        "attack_or_breakthrough_affordance"
    ] > 0.0


def test_emocio_novelty_is_independent_of_movement() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    changed = copy.deepcopy(annotation)
    book = next(
        item
        for item in changed["options"]
        if item["option_id"] == "utility_trip_book"
    )
    book["novelty_strength"]["value"] = "present"
    left = _vectors(compile_emocio_typed_annotation(case, annotation))
    right = _vectors(compile_emocio_typed_annotation(case, changed))

    assert left["utility_trip_book"]["movement"] == right[
        "utility_trip_book"
    ]["movement"]
    assert left["utility_trip_book"]["novelty"] != right[
        "utility_trip_book"
    ]["novelty"]


def test_emocio_non_not_relevant_relation_requires_evidence() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    annotation["options"][0]["attraction_strength"]["evidence_ids"] = []

    with pytest.raises(ValidationError):
        compile_emocio_typed_annotation(case, annotation)


def test_emocio_evidence_from_another_option_fails() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    home = next(
        item
        for item in annotation["options"]
        if item["option_id"] == "utility_trip_home"
    )
    home["attraction_strength"]["evidence_ids"] = ["utility_ev_companion"]

    with pytest.raises(ValidationError):
        compile_emocio_typed_annotation(case, annotation)


def test_emocio_unknown_evidence_fails() -> None:
    case = _r1_case("trip_racio_utility_material")
    annotation = author_emocio_annotation(case)
    annotation["options"][0]["source_evidence_scope_ids"].append(
        "unknown_evidence"
    )
    annotation["options"][0]["source_evidence_scope_ids"].sort()

    with pytest.raises(ValueError, match="unknown evidence"):
        compile_emocio_typed_annotation(case, annotation)


def test_instinkt_compiler_has_no_case_or_lexical_option_inference() -> None:
    source = inspect.getsource(compile_instinkt_typed_mapping)

    assert "case_id" not in source
    assert ".endswith" not in source
    assert "trip_book" not in source
    assert "trip_home" not in source


def test_instinkt_opaque_case_id_preserves_mapping() -> None:
    case = _r1_case("trip_protective_context_exposed")
    mapping = author_instinkt_mapping(case)
    renamed = copy.deepcopy(case)
    renamed["case_id"] = "opaque_case"

    assert compile_instinkt_typed_mapping(
        case, mapping
    ) == compile_instinkt_typed_mapping(renamed, mapping)


def test_instinkt_opaque_option_ids_preserve_typed_categories() -> None:
    case = _r1_case("trip_protective_context_exposed")
    mapping = author_instinkt_mapping(case)
    original = compile_instinkt_typed_mapping(case, mapping)
    renamed_case = copy.deepcopy(case)
    renamed_mapping = copy.deepcopy(mapping)
    _rename_options(renamed_case, mapping=renamed_mapping)
    renamed = compile_instinkt_typed_mapping(
        renamed_case, renamed_mapping
    )

    assert _normalized_instinkt_mapping(original) == (
        _normalized_instinkt_mapping(renamed)
    )


def test_instinkt_category_to_option_evidence_closure() -> None:
    case = _r1_case("trip_protective_context_supported")
    mapping = author_instinkt_mapping(case)
    home = next(
        item
        for item in mapping["option_effects"]
        if item["option_id"] == "trip_home"
    )
    home["categories"][0]["supporting_evidence_ids"] = [
        "protective_ev_companion"
    ]

    with pytest.raises(ValidationError):
        compile_instinkt_typed_mapping(case, mapping)


def test_verified_distance_cannot_be_typed_as_unfamiliar_danger() -> None:
    case = _r1_case("trip_protective_context_supported")
    mapping = author_instinkt_mapping(case)
    book = next(
        item
        for item in mapping["option_effects"]
        if item["option_id"] == "trip_book"
    )
    book["categories"].append(
        {
            "category_id": "unfamiliar_environment_danger",
            "option_id": "trip_book",
            "supporting_evidence_ids": ["protective_ev_environment"],
            "semantic_predicate": "unfamiliar_environment_danger",
            "body_deltas": [
                {"dimension": name, "delta": value}
                for name, value in sorted(
                    R2_EFFECT_RULES[
                        "unfamiliar_environment_danger"
                    ].items()
                )
            ],
        }
    )
    book["categories"].sort(key=lambda item: item["category_id"])

    with pytest.raises(ValueError, match="required source assertion"):
        compile_instinkt_typed_mapping(case, mapping)


def test_unfamiliar_uncertain_danger_changes_protective_route() -> None:
    replay = replay_instinkt_typed(REPOSITORY_ROOT)
    by_case = {item["case_id"]: item for item in replay["cases"]}
    exposed_book = next(
        item
        for item in by_case["trip_protective_context_exposed"][
            "option_results"
        ]
        if item["option_id"] == "trip_book"
    )
    supported_book = next(
        item
        for item in by_case["trip_protective_context_supported"][
            "option_results"
        ]
        if item["option_id"] == "trip_book"
    )

    assert exposed_book["protective_cost"] > supported_book["protective_cost"]
    assert {
        item["semantic_predicate"]
        for item in exposed_book["category_contributions"]
    }.intersection(
        {
            "unfamiliar_environment_danger",
            "unverified_provider_danger",
            "uncertain_return_danger",
        }
    )
    assert not {
        item["semantic_predicate"]
        for item in supported_book["category_contributions"]
    }.intersection(
        {
            "unfamiliar_environment_danger",
            "unverified_provider_danger",
            "uncertain_return_danger",
        }
    )


def test_discretionary_resource_exposure_remains_independently_active() -> None:
    for case_id in (
        "trip_protective_context_exposed",
        "trip_protective_context_supported",
    ):
        case = _r1_case(case_id)
        mapping = compile_instinkt_typed_mapping(
            case, author_instinkt_mapping(case)
        )
        book = next(
            item for item in mapping.option_effects if item.option_id == "trip_book"
        )
        resource = next(
            item
            for item in book.categories
            if item.semantic_predicate
            == "discretionary_resource_commitment_38"
        )
        assert tuple(
            (delta.dimension, delta.delta) for delta in resource.body_deltas
        ) == (("resource_security", -0.2),)
        assert mapping.budget_kind == "discretionary_budget"
        assert mapping.necessary_cash_reserve_claim is False


def test_protected_target_prose_does_not_change_numeric_path() -> None:
    case = _r1_case("trip_protective_context_supported")
    mapping_payload = author_instinkt_mapping(case)
    original = compile_instinkt_typed_mapping(case, mapping_payload)
    changed_payload = copy.deepcopy(mapping_payload)
    changed_payload["protected_target_label"] = (
        "A paraphrased label for the same typed protected targets."
    )
    changed = compile_instinkt_typed_mapping(case, changed_payload)
    packet, body, config, base_effects = e1_instinkt_projection_inputs(
        REPOSITORY_ROOT, case["case_id"]
    )
    left = project_instinkt_typed_sensitivity(
        mapping=original,
        packet=packet,
        body_state=body,
        config=config,
        base_effects=base_effects,
    )
    right = project_instinkt_typed_sensitivity(
        mapping=changed,
        packet=packet,
        body_state=body,
        config=config,
        base_effects=base_effects,
    )

    assert [
        (
            item["option_id"],
            item["predicted_loss"],
            item["recoverability"],
            item["protective_cost"],
        )
        for item in left["option_results"]
    ] == [
        (
            item["option_id"],
            item["predicted_loss"],
            item["recoverability"],
            item["protective_cost"],
        )
        for item in right["option_results"]
    ]


def test_corrected_candidate_v2_is_unsealed_and_leakage_free() -> None:
    candidate = corrected_candidate_v2(REPOSITORY_ROOT)
    serialized = json.dumps(candidate, ensure_ascii=False).casefold()

    assert len(candidate["cases"]) == 4
    assert candidate["status"] == "unsealed_candidate"
    assert candidate["execution_authorized"] is False
    assert candidate["human_review_status"] == "pending"
    assert all(
        any(
            fact["evidence_id"] == "utility_ev_budget_base"
            and "4800" in fact["text"]
            for fact in case["operational_en"]["facts"]
        )
        for case in candidate["cases"][:2]
    )
    assert "semantic_route_representation" not in serialized
    assert "expected_option" not in serialized
    assert "option_flip_target" not in serialized
    assert "necessary cash reserve" not in serialized
    assert "character_profile" not in serialized
    assert "governance" not in serialized


def test_model_free_replays_do_not_claim_processor_capability() -> None:
    emocio = replay_emocio_typed(REPOSITORY_ROOT)
    instinkt = replay_instinkt_typed(REPOSITORY_ROOT)

    assert all(
        item["manual_annotation_valid"] is True
        and item["evidence_closure"] == "passed"
        and item["processor_capability_claimed"] is False
        and item["native_processor_executions"] == 0
        and item["model_calls"] == 0
        for item in emocio["cases"]
    )
    assert all(
        item["manual_mapping_valid"] is True
        and item["evidence_closure"] == "passed"
        and item["processor_capability_claimed"] is False
        and item["native_processor_executions"] == 0
        and item["model_calls"] == 0
        for item in instinkt["cases"]
    )


def test_original_e1_and_r1_cold_verify_without_r1_byte_mutation() -> None:
    before = frozen_r1_inventory(REPOSITORY_ROOT)

    assert formal_verify_e1(REPOSITORY_ROOT)["status"] == "passed"
    assert cold_verify_r1(REPOSITORY_ROOT)["status"] == "passed"
    assert frozen_r1_inventory(REPOSITORY_ROOT) == before


def test_committed_r2_outputs_cold_verify_when_present() -> None:
    if not (REPOSITORY_ROOT / R2_OUTPUT_RELATIVE_PATH / "manifest.json").is_file():
        pytest.skip("TRIAD-ISO-R2 outputs have not been prepared yet")

    result = cold_verify_r2(REPOSITORY_ROOT)
    assert result["status"] == "passed"
    assert result["model_calls"] == 0
    assert result["character_replay_rows"] == 0
    assert result["original_r1_bytes_unchanged"] is True
