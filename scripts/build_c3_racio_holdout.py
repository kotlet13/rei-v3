"""Build the sealed, manually authored C3 Racio-interpreter holdout corpus.

The script is a deterministic serializer for human-authored case definitions.
It never calls a model and writes public provider inputs and evaluator-only gold
to physically separate JSONL files.  The destination is create-only so a sealed
holdout cannot be regenerated over an existing corpus by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_PUBLIC = "rei-c3-racio-interpreter-public-case-v1"
SCHEMA_GOLD = "rei-c3-racio-interpreter-gold-case-v1"
SCHEMA_MANIFEST = "rei-c3-racio-interpreter-benchmark-manifest-v2"
BENCHMARK_ID = "rei-c3-racio-interpreter-holdout-v1"
CORPUS_VERSION = "2026-07-15"
CALIBRATION_POLICY_ID = "c3-conscious-access-calibration-v1"
SEMANTIC_LAB_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "semantic_lab_v1"
SEMANTIC_LAB_VARIANT_MODES: tuple[str, ...] = (
    "sl_canonical",
    "sl_paraphrase",
    "en_operational_gloss",
    "keyword_trap",
    "same_behavior_different_route",
    "same_route_different_behavior",
    "missing_information",
    "contradictory_surface_cue",
)
SOURCE_FIXTURE_SHA256: dict[str, str] = {
    "sf_emocio_three_scenes": (
        "ea17c06478dfde3bfcf001ea79a2ae14ae97688140bf9497401886537b68a200"
    ),
    "sf_malek_motor_delegation": (
        "c070a12238e4e70e46695a9613744eac5d00c8f117f2b1c0192360daff9f7e02"
    ),
    "sf_new_year_resolution": (
        "d8675185264783e1bebc7408f2922309683f84f58d98b6bee8697fb61c873a64"
    ),
    "sf_same_behavior_three_routes": (
        "38c663fb46d560efb0c7d9b7f51d298298287037c033faf50b91b25ceb645f5a"
    ),
    "sf_same_route_different_behavior": (
        "0b714e795a8b090775a104d3f801a62c5329d18960912121107410e1f4e08b1c"
    ),
    "sf_scarcity_and_saving": (
        "438ccce1efb59ac51859dc92416776dd938571fc9ccd971a3e87250beec5d812"
    ),
    "sf_spoznanje_unanimous": (
        "4513ff3c9f24d43d54b1e64472b29f1e65d67c433130cbed482253e5fa14f628"
    ),
    "sf_three_modal_planning_paths": (
        "3bc80d70b0ab5a3f69ae3610f390f63c387faac9fc795d8e54bbad943c442c99"
    ),
}
EXPECTED_INSTRUCTION_SHA256 = (
    "c5ea5a0936bbab5e9bb481e53443eb9119cb5bf2c1d58737f3bb0214ebcfb1b0"
)
EXPECTED_OUTPUT_SCHEMA_SHA256 = (
    "7b51eeadc1e13223016a1ab95aab88b9141ed7d11a5400bd05cf25988645bd1c"
)
PROTOCOL_SCOPED_PATHS: tuple[str, ...] = (
    "app/backend/rei",
    "config/racio_interpreter_models.yaml",
    "scripts/build_c3_racio_holdout.py",
    "tests/fixtures/semantic_lab_v1",
)


ROOT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "root_id": "c3h_root_emocio_three_scenes",
        "family_id": "sf_emocio_three_scenes",
        "source_mind": "E",
        "source_option_id": "option_invite",
        "source_route_tags": (
            "current_scene",
            "desired_scene",
            "broken_scene",
            "scene_transformation",
        ),
        "mapping_rationale": (
            "The reviewed scene transformation maps to connect with a bounded "
            "broken-scene motive class."
        ),
        "cue_signal": "desired_scene_mismatch",
        "cue_value": "empty_hall_vs_collaborative_group",
        "action_signal": "motor_urge",
        "action": "connect",
        "motive": "broken_scene",
        "correct_option_id": "option_001",
        "options_sl": (
            "Ustvari pot iz prazne dvorane proti sodelujočemu prizoru.",
            "Nadaljuj v porušeni osamljeni smeri brez povabila.",
        ),
        "options_en": (
            "Create a path from the empty hall toward the collaborative scene.",
            "Continue in the broken solitary direction without an invitation.",
        ),
        "ambiguity_mode": "mixed",
        "conflict_action": "withdraw_contact",
    },
    {
        "root_id": "c3h_root_new_year_readiness",
        "family_id": "sf_new_year_resolution",
        "source_mind": "E",
        "source_option_id": "option_defer",
        "source_route_tags": ("desired_scene_absent", "low_attraction"),
        "mapping_rationale": (
            "Absent desired-scene attraction maps to protective deferral and the "
            "controlled broken-scene class."
        ),
        "cue_signal": "desired_scene_absent",
        "cue_value": "low_attraction_to_planned_exercise",
        "action_signal": "motor_urge",
        "action": "protect",
        "motive": "broken_scene",
        "correct_option_id": "option_002",
        "options_sl": (
            "Začni vadbo po zapisanem vsakodnevnem urniku.",
            "Odloži začetek in ponovno preveri sodelovanje razumov.",
        ),
        "options_en": (
            "Start exercising according to the written daily schedule.",
            "Defer the start and recheck cooperation among the minds.",
        ),
        "ambiguity_mode": "mixed",
        "conflict_action": "withdraw_contact",
    },
    {
        "root_id": "c3h_root_motor_delegation",
        "family_id": "sf_malek_motor_delegation",
        "source_mind": "E",
        "source_option_id": "option_delegate_motor",
        "source_route_tags": (
            "motor_pattern",
            "direct_experience",
            "delegated_execution",
        ),
        "mapping_rationale": (
            "The reviewed delegated motor route directly maps to perform and "
            "motor_pattern."
        ),
        "cue_signal": "motor_pattern_readiness",
        "cue_value": 0.91,
        "action_signal": "motor_urge",
        "action": "perform",
        "motive": "motor_pattern",
        "correct_option_id": "option_001",
        "options_sl": (
            "Prepusti motorično izvedbo izurjenemu vzorcu ob ohranjenem mandatu.",
            "Vsak del giba zavestno nadzoruj in prekini izurjeno celoto.",
        ),
        "options_en": (
            "Delegate motor execution to the trained pattern while retaining the mandate.",
            "Consciously control every part of the movement and interrupt the trained whole.",
        ),
        "ambiguity_mode": "mixed",
        "conflict_action": "freeze",
    },
    {
        "root_id": "c3h_root_spoznanje_loss",
        "family_id": "sf_spoznanje_unanimous",
        "source_mind": "E",
        "source_option_id": "option_end",
        "source_route_tags": ("broken_scene", "desired_release"),
        "mapping_rationale": (
            "Repeated broken-scene evidence maps to a boundary-setting tendency "
            "and the controlled broken-scene class."
        ),
        "cue_signal": "broken_scene_recurrence",
        "cue_value": "repeated_harmful_collaboration",
        "action_signal": "motor_urge",
        "action": "set_boundary",
        "motive": "broken_scene",
        "correct_option_id": "option_002",
        "options_sl": (
            "Nadaljuj škodljivo sodelovanje kljub ponavljajoči se porušeni sliki.",
            "Prekini škodljivo sodelovanje po več ponovitvah.",
        ),
        "options_en": (
            "Continue the harmful collaboration despite the recurring broken scene.",
            "End the harmful collaboration after repeated occurrences.",
        ),
        "ambiguity_mode": "mixed",
        "conflict_action": "freeze",
    },
    {
        "root_id": "c3h_root_scarcity_saving",
        "family_id": "sf_scarcity_and_saving",
        "source_mind": "I",
        "source_option_id": "option_save",
        "source_route_tags": (
            "scarcity",
            "resource_security",
            "uncertainty_horizon",
        ),
        "mapping_rationale": (
            "Reviewed scarcity and resource-security tags map to protect and the "
            "coarse body-alarm class."
        ),
        "cue_signal": "resource_insecurity",
        "cue_value": 0.89,
        "action_signal": "raw_urge",
        "action": "protect",
        "motive": "body_alarm",
        "correct_option_id": "option_001",
        "options_sl": (
            "Odloži drag nakup in ohrani osnovno rezervo med negotovostjo.",
            "Porabi večino rezerve, ne da bi preveril čas naslednjega prihodka.",
        ),
        "options_en": (
            "Delay the expensive purchase and preserve the basic reserve during uncertainty.",
            "Spend most of the reserve without checking when the next income arrives.",
        ),
        "ambiguity_mode": "conflicted",
        "conflict_action": "approach",
    },
    {
        "root_id": "c3h_root_three_modal_path",
        "family_id": "sf_three_modal_planning_paths",
        "source_mind": "I",
        "source_option_id": "option_route_b",
        "source_route_tags": ("hazard_filter", "escape", "weather_uncertainty"),
        "mapping_rationale": (
            "The reviewed hazard-filter and escape route maps to seek_safety and "
            "the coarse body-alarm class."
        ),
        "cue_signal": "boundary_alarm",
        "cue_value": 0.86,
        "action_signal": "raw_urge",
        "action": "seek_safety",
        "motive": "body_alarm",
        "correct_option_id": "option_002",
        "options_sl": (
            "Izberi daljšo slikovito pot z več izpostavljenimi odseki.",
            "Izberi krajšo zaščiteno pot z manj izpostavljenosti in boljšim umikom.",
        ),
        "options_en": (
            "Choose the longer scenic route with more exposed sections.",
            "Choose the shorter protected route with less exposure and better escape.",
        ),
        "ambiguity_mode": "conflicted",
        "conflict_action": "approach",
    },
    {
        "root_id": "c3h_root_same_behavior_body_alarm",
        "family_id": "sf_same_behavior_three_routes",
        "source_mind": "I",
        "source_option_id": "option_leave",
        "source_route_tags": ("body_alarm", "escape"),
        "mapping_rationale": (
            "The reviewed body-alarm escape route directly maps to seek_safety "
            "and body_alarm."
        ),
        "cue_signal": "body_alarm",
        "cue_value": "alarm_at_event_exit_time",
        "action_signal": "raw_urge",
        "action": "seek_safety",
        "motive": "body_alarm",
        "correct_option_id": "option_001",
        "options_sl": (
            "Zapusti dogodek ob telesnem alarmu.",
            "Ostani na dogodku kljub telesnemu alarmu.",
        ),
        "options_en": (
            "Leave the event when the body alarm appears.",
            "Stay at the event despite the body alarm.",
        ),
        "ambiguity_mode": "conflicted",
        "conflict_action": "withdraw_contact",
    },
    {
        "root_id": "c3h_root_same_boundary_route",
        "family_id": "sf_same_route_different_behavior",
        "source_mind": "I",
        "source_option_id": "option_step_back",
        "source_route_tags": ("boundary", "protected_target", "action_affordance"),
        "mapping_rationale": (
            "The reviewed protected-boundary route maps to set_boundary and "
            "boundary_alarm."
        ),
        "cue_signal": "boundary_alarm",
        "cue_value": 0.92,
        "action_signal": "raw_urge",
        "action": "set_boundary",
        "motive": "boundary_alarm",
        "correct_option_id": "option_002",
        "options_sl": (
            "Jasno verbalno zavrni in zaščiti isto mejo.",
            "Fizično se odmakni in zaščiti isto mejo.",
        ),
        "options_en": (
            "Clearly say no and protect the same boundary.",
            "Step back physically and protect the same boundary.",
        ),
        "ambiguity_mode": "conflicted",
        "conflict_action": "seek_attachment",
    },
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return ("".join(f"{_canonical_json(record)}\n" for record in records)).encode(
        "utf-8"
    )


def _observation(
    observation_id: str,
    signal_name: str,
    *,
    value: Any | None = None,
    degraded: bool = False,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "observation_id": observation_id,
        "signal_name": signal_name,
        "perception_status": "degraded" if degraded else "clear",
        "provenance": "manifested",
    }
    if not degraded:
        record["perceived_value_json"] = _canonical_json(value)
    return record


def _language_text(language: str, slovenian: str, english: str) -> str:
    return slovenian if language == "sl" else english


def build_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public_records: list[dict[str, Any]] = []
    gold_records: list[dict[str, Any]] = []
    case_number = 0
    pair_number = 0
    for root in ROOT_SPECS:
        for ambiguity_class in ("unambiguous", "ambiguous"):
            pair_number += 1
            pair_id = f"c3h_pair_{pair_number:03d}"
            for language in ("sl", "en"):
                case_number += 1
                case_id = f"c3h_case_{case_number:03d}"
                options = root[f"options_{language}"]
                packet: dict[str, Any] = {
                    "source_mind": root["source_mind"],
                    "language": language,
                }
                if ambiguity_class == "unambiguous":
                    packet["visible_observations"] = [
                        _observation(
                            "observation_001",
                            root["cue_signal"],
                            value=root["cue_value"],
                        ),
                        _observation(
                            "observation_002",
                            root["action_signal"],
                            value=f"structured_tendency:{root['action']}",
                        ),
                    ]
                    packet["channel_quality"] = 1.0
                    packet["uncertainty"] = _language_text(
                        language,
                        "Vidna znak in smer sta jasna, motiv pa ostaja omejena hipoteza.",
                        "The visible cue and direction are clear while motive remains a bounded hypothesis.",
                    )
                    acceptance_mode = "accepting"
                    expected_option_id = root["correct_option_id"]
                    expected_action = root["action"]
                    expected_motive = root["motive"]
                    maximum_confidence = None
                    variant_suffix = "accepting"
                elif root["ambiguity_mode"] == "mixed":
                    packet["visible_observations"] = [
                        _observation(
                            "observation_001",
                            root["cue_signal"],
                            value=(
                                0.55
                                if isinstance(root["cue_value"], (int, float))
                                else root["cue_value"]
                            ),
                        ),
                        _observation(
                            "observation_002",
                            root["action_signal"],
                            degraded=True,
                        ),
                    ]
                    packet["omitted_observation_ids"] = ["observation_003"]
                    packet["channel_quality"] = 0.45
                    packet["uncertainty"] = _language_text(
                        language,
                        "Kontekstni znak je viden, odločilna smer dejanja pa manjka.",
                        "The contextual cue is visible while the decisive action direction is missing.",
                    )
                    acceptance_mode = "mixed"
                    expected_option_id = None
                    expected_action = "unknown"
                    expected_motive = "unknown"
                    maximum_confidence = 0.35
                    variant_suffix = "mixed_missing"
                else:
                    packet["visible_observations"] = [
                        _observation(
                            "observation_001",
                            root["action_signal"],
                            value=f"structured_tendency:{root['action']}",
                        ),
                        _observation(
                            "observation_002",
                            root["action_signal"],
                            value=f"structured_tendency:{root['conflict_action']}",
                        ),
                    ]
                    packet["channel_quality"] = 0.2
                    packet["uncertainty"] = _language_text(
                        language,
                        "Dve vidni težnji dejanja kažeta v različni smeri.",
                        "Two visible action tendencies point in different directions.",
                    )
                    acceptance_mode = "conflicted"
                    expected_option_id = None
                    expected_action = "unknown"
                    expected_motive = "unknown"
                    maximum_confidence = 0.35
                    variant_suffix = "conflicted"

                packet["public_option_scope"] = [
                    {"option_id": "option_001", "description": options[0]},
                    {"option_id": "option_002", "description": options[1]},
                ]
                public_records.append(
                    {
                        "schema_version": SCHEMA_PUBLIC,
                        "case_id": case_id,
                        "root_id": root["root_id"],
                        "packet_input": packet,
                    }
                )
                gold_records.append(
                    {
                        "schema_version": SCHEMA_GOLD,
                        "case_id": case_id,
                        "root_id": root["root_id"],
                        "family_id": root["family_id"],
                        "variant_id": (
                            f"{root['family_id']}__{variant_suffix}_{language}"
                        ),
                        "expected_source_mind": root["source_mind"],
                        "expected_language": language,
                        "acceptance_mode": acceptance_mode,
                        "ambiguity_class": ambiguity_class,
                        "expected_option_id": expected_option_id,
                        "expected_action_tendency": expected_action,
                        "expected_motive_class": expected_motive,
                        "maximum_ambiguous_confidence": maximum_confidence,
                        "bilingual_pair_id": pair_id,
                        "native_truth_id": f"native_truth_c3h_{case_number:03d}",
                        "profile_id": f"profile_c3h_{case_number:03d}",
                        "evaluator_only_canary": f"HIDDEN_C3H_CANARY_{case_number:03d}",
                    }
                )
    return public_records, gold_records


def _require_hex(value: str, *, length: int, label: str) -> str:
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError(f"{label} must be exactly {length} lowercase hex characters")
    return value


def _read_fixture_object(
    path: Path,
    *,
    fixture_root: Path,
    label: str,
) -> tuple[bytes, dict[str, Any]]:
    root = fixture_root.expanduser().absolute()
    source = path.expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("C3 semantic fixture root must be a regular directory")
    if source.parent != root or source.is_symlink() or not source.is_file():
        raise ValueError(f"{label} must be a regular file directly below fixture root")
    try:
        payload = source.read_bytes()
        value = json.loads(payload)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not readable JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain one JSON object")
    return payload, value


def _fixture_manifest_entries(fixture_root: Path) -> dict[str, dict[str, Any]]:
    _, manifest = _read_fixture_object(
        fixture_root / "manifest.json",
        fixture_root=fixture_root,
        label="C3 semantic fixture manifest",
    )
    expected_contract = {
        "schema_version": "rei-semantic-fixture-manifest-v1",
        "lab_id": "rei-semantic-lab-v1",
        "family_count": 24,
        "variant_count": 192,
        "review_status": "canon_approved",
        "model_generated_gold": False,
        "training_export": False,
    }
    if any(manifest.get(key) != value for key, value in expected_contract.items()):
        raise ValueError("C3 semantic fixture manifest differs from approved contract")
    if tuple(manifest.get("variant_modes", ())) != SEMANTIC_LAB_VARIANT_MODES:
        raise ValueError("C3 semantic fixture variant modes differ from approved order")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 24:
        raise ValueError("C3 semantic fixture manifest must enumerate 24 families")

    entries: dict[str, dict[str, Any]] = {}
    paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {
            "family_id",
            "path",
            "sha256",
            "variant_count",
        }:
            raise ValueError("C3 semantic fixture entry has an invalid shape")
        family_id = item.get("family_id")
        relative_path = item.get("path")
        if (
            not isinstance(family_id, str)
            or not family_id
            or relative_path != f"{family_id}.json"
            or Path(str(relative_path)).name != relative_path
            or item.get("variant_count") != 8
        ):
            raise ValueError("C3 semantic fixture entry identity is invalid")
        _require_hex(
            str(item.get("sha256")),
            length=64,
            label=f"fixture SHA-256 for {family_id}",
        )
        if family_id in entries or relative_path in paths:
            raise ValueError("C3 semantic fixture entries must be unique")
        entries[family_id] = item
        paths.add(relative_path)
    if tuple(entries) != tuple(sorted(entries)):
        raise ValueError("C3 semantic fixture entries must be sorted by family ID")
    if sum(int(item["variant_count"]) for item in entries.values()) != 192:
        raise ValueError("C3 semantic fixture family counts differ from manifest")
    return entries


def validate_source_grounding_fixtures(
    fixture_root: Path = SEMANTIC_LAB_FIXTURE_ROOT,
) -> tuple[dict[str, Any], ...]:
    """Validate and freeze the exact reviewed fixture route behind every root."""

    root_ids = tuple(str(spec.get("root_id", "")) for spec in ROOT_SPECS)
    family_ids = tuple(str(spec.get("family_id", "")) for spec in ROOT_SPECS)
    if (
        len(ROOT_SPECS) != 8
        or len(set(root_ids)) != 8
        or len(set(family_ids)) != 8
        or set(family_ids) != set(SOURCE_FIXTURE_SHA256)
    ):
        raise ValueError("C3 roots must bijectively match the eight pinned fixtures")

    entries = _fixture_manifest_entries(fixture_root)
    pins: list[dict[str, Any]] = []
    for spec in ROOT_SPECS:
        family_id = str(spec["family_id"])
        entry = entries.get(family_id)
        expected_hash = SOURCE_FIXTURE_SHA256[family_id]
        expected_name = f"{family_id}.json"
        if (
            entry is None
            or entry.get("path") != expected_name
            or entry.get("sha256") != expected_hash
            or entry.get("variant_count") != 8
        ):
            raise ValueError(
                f"C3 source fixture manifest pin differs for {family_id}"
            )
        fixture_payload, fixture = _read_fixture_object(
            fixture_root / expected_name,
            fixture_root=fixture_root,
            label=f"C3 semantic fixture {family_id}",
        )
        if hashlib.sha256(fixture_payload).hexdigest() != expected_hash:
            raise ValueError(f"C3 source fixture SHA-256 differs for {family_id}")
        variants = fixture.get("variants")
        if (
            fixture.get("schema_version") != "rei-semantic-family-fixture-v1"
            or fixture.get("family_id") != family_id
            or fixture.get("review_status") != "canon_approved"
            or fixture.get("model_generated_gold") is not False
            or fixture.get("training_export") is not False
            or not isinstance(variants, list)
            or len(variants) != 8
        ):
            raise ValueError(f"C3 source fixture contract differs for {family_id}")
        if tuple(
            variant.get("mode") if isinstance(variant, dict) else None
            for variant in variants
        ) != SEMANTIC_LAB_VARIANT_MODES:
            raise ValueError(f"C3 source fixture modes differ for {family_id}")

        for variant in variants:
            routes = variant.get("expected_routes")
            if not isinstance(routes, list):
                raise ValueError(f"C3 source fixture routes are invalid for {family_id}")
            selected = [
                route
                for route in routes
                if isinstance(route, dict)
                and route.get("mind") == spec["source_mind"]
            ]
            if len(selected) != 1:
                raise ValueError(
                    f"C3 source fixture must expose one selected route for {family_id}"
                )
            route = selected[0]
            if (
                route.get("family_id") != family_id
                or route.get("variant_id") != variant.get("variant_id")
                or route.get("option_id") != spec["source_option_id"]
                or tuple(route.get("route_tags", ()))
                != tuple(spec["source_route_tags"])
            ):
                raise ValueError(
                    f"C3 source route pin differs from fixture for {family_id}"
                )
            if variant.get("mode") == "sl_canonical":
                interpretations = variant.get("interpretation_variants")
                if not isinstance(interpretations, list):
                    raise ValueError(
                        f"C3 source interpretations are invalid for {family_id}"
                    )
                selected_interpretations = [
                    interpretation
                    for interpretation in interpretations
                    if isinstance(interpretation, dict)
                    and interpretation.get("source_mind") == spec["source_mind"]
                ]
                if len(selected_interpretations) != 1:
                    raise ValueError(
                        "C3 canonical source fixture must expose exactly one "
                        f"selected interpretation for {family_id}"
                    )
                interpretation = selected_interpretations[0]
                if (
                    interpretation.get("family_id") != family_id
                    or interpretation.get("variant_id")
                    != variant.get("variant_id")
                    or interpretation.get("expected_option_id")
                    != spec["source_option_id"]
                ):
                    raise ValueError(
                        "C3 canonical interpretation pin differs from fixture "
                        f"for {family_id}"
                    )

        pins.append(
            {
                "root_id": spec["root_id"],
                "family_id": family_id,
                "fixture_path": (
                    f"tests/fixtures/semantic_lab_v1/{expected_name}"
                ),
                "fixture_sha256": expected_hash,
                "fixture_review_status": "canon_approved",
                "fixture_variant_count": 8,
                "source_mind": spec["source_mind"],
                "source_option_id": spec["source_option_id"],
                "source_route_tags": list(spec["source_route_tags"]),
                "holdout_option_id": spec["correct_option_id"],
                "expected_action_tendency": spec["action"],
                "expected_motive_class": spec["motive"],
                "mapping_rationale": spec["mapping_rationale"],
            }
        )
    return tuple(sorted(pins, key=lambda pin: str(pin["root_id"])))


def build_corpus_bytes(
    *,
    protocol_freeze_commit: str,
    instruction_sha256: str,
    output_schema_sha256: str,
    fixture_root: Path = SEMANTIC_LAB_FIXTURE_ROOT,
) -> dict[str, bytes]:
    protocol_freeze_commit = _require_hex(
        protocol_freeze_commit,
        length=40,
        label="protocol freeze commit",
    )
    instruction_sha256 = _require_hex(
        instruction_sha256,
        length=64,
        label="instruction SHA-256",
    )
    output_schema_sha256 = _require_hex(
        output_schema_sha256,
        length=64,
        label="output schema SHA-256",
    )
    source_grounding_pins = validate_source_grounding_fixtures(fixture_root)
    public_records, gold_records = build_records()
    public_bytes = _jsonl_bytes(public_records)
    gold_bytes = _jsonl_bytes(gold_records)
    manifest = {
        "schema_version": SCHEMA_MANIFEST,
        "benchmark_id": BENCHMARK_ID,
        "corpus_version": CORPUS_VERSION,
        "suite_role": "untouched_holdout",
        "protocol_freeze_commit": protocol_freeze_commit,
        "instruction_sha256": instruction_sha256,
        "output_schema_sha256": output_schema_sha256,
        "calibration_policy_id": CALIBRATION_POLICY_ID,
        "gold_origin": "manually_authored",
        "model_generated_gold": False,
        "training_export": False,
        "sealed_before_candidate_run": True,
        "post_seal_prompt_tuning_allowed": False,
        "counts": {
            "cases": 32,
            "roots": 8,
            "emocio": 16,
            "instinkt": 16,
            "slovenian": 16,
            "english": 16,
            "unambiguous": 16,
            "ambiguous": 16,
            "accepting": 16,
            "mixed": 8,
            "conflicted": 8,
            "bilingual_pairs": 16,
        },
        "ambiguity_confidence_threshold": 0.35,
        "bilingual_confidence_tolerance": 0.15,
        "source_family_ids": sorted(root["family_id"] for root in ROOT_SPECS),
        "source_grounding_pins": list(source_grounding_pins),
        "files": [
            {
                "path": "public_cases.jsonl",
                "sha256": hashlib.sha256(public_bytes).hexdigest(),
                "case_count": 32,
            },
            {
                "path": "gold.jsonl",
                "sha256": hashlib.sha256(gold_bytes).hexdigest(),
                "case_count": 32,
            },
        ],
        "root_ids": sorted(root["root_id"] for root in ROOT_SPECS),
    }
    return {
        "manifest.json": f"{_canonical_json(manifest)}\n".encode("utf-8"),
        "public_cases.jsonl": public_bytes,
        "gold.jsonl": gold_bytes,
    }


def write_corpus(
    output_dir: Path,
    *,
    protocol_freeze_commit: str,
    instruction_sha256: str,
    output_schema_sha256: str,
    fixture_root: Path = SEMANTIC_LAB_FIXTURE_ROOT,
) -> tuple[Path, ...]:
    payloads = build_corpus_bytes(
        protocol_freeze_commit=protocol_freeze_commit,
        instruction_sha256=instruction_sha256,
        output_schema_sha256=output_schema_sha256,
        fixture_root=fixture_root,
    )
    target = output_dir.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError("C3 holdout destination is create-only")
    target.parent.mkdir(parents=True, exist_ok=True)
    prefix = f".{target.name}.staging-"
    staging = Path(tempfile.mkdtemp(prefix=prefix, dir=target.parent)).absolute()
    published = False
    try:
        if staging.parent != target.parent or not staging.name.startswith(prefix):
            raise RuntimeError("C3 holdout staging directory escaped its parent")
        for name in ("manifest.json", "public_cases.jsonl", "gold.jsonl"):
            path = staging / name
            with path.open("xb") as handle:
                handle.write(payloads[name])
                handle.flush()
                os.fsync(handle.fileno())
        if target.exists() or target.is_symlink():
            raise FileExistsError("C3 holdout destination appeared during publication")
        os.rename(staging, target)
        published = True
    finally:
        if (
            not published
            and staging.exists()
            and staging.parent == target.parent
            and staging.name.startswith(prefix)
        ):
            shutil.rmtree(staging)
    return tuple(
        target / name
        for name in ("manifest.json", "public_cases.jsonl", "gold.jsonl")
    )


def verify_repository_protocol_pins(
    *,
    protocol_freeze_commit: str,
    instruction_sha256: str,
    output_schema_sha256: str,
) -> None:
    """Fail closed when the CLI is not sealing the checked-out protocol."""

    from app.backend.rei.communication.structured_interpreter import (
        StructuredRacioInterpreterOutput,
    )
    from app.backend.rei.ids import sha256_hex
    from app.backend.rei.providers.ollama_interpreter import (
        RACIO_INTERPRETER_STRUCTURED_INSTRUCTION,
    )

    if instruction_sha256 != EXPECTED_INSTRUCTION_SHA256:
        raise ValueError("C3 holdout instruction pin differs from frozen protocol")
    if output_schema_sha256 != EXPECTED_OUTPUT_SCHEMA_SHA256:
        raise ValueError("C3 holdout schema pin differs from frozen protocol")
    if (
        sha256_hex(RACIO_INTERPRETER_STRUCTURED_INSTRUCTION)
        != EXPECTED_INSTRUCTION_SHA256
    ):
        raise ValueError("Checked-out C3 instruction differs from frozen protocol")
    if (
        sha256_hex(StructuredRacioInterpreterOutput.model_json_schema())
        != EXPECTED_OUTPUT_SCHEMA_SHA256
    ):
        raise ValueError("Checked-out C3 schema differs from frozen protocol")

    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if branch.stdout.strip() != "main":
        raise ValueError("C3 holdout must be sealed directly on main")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip() != protocol_freeze_commit:
        raise ValueError("C3 holdout must be sealed from the protocol-freeze HEAD")
    remote = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if remote.stdout.strip() != protocol_freeze_commit:
        raise ValueError("C3 holdout requires protocol freeze pushed to origin/main")
    status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *PROTOCOL_SCOPED_PATHS,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise ValueError("C3 protocol-scoped paths must be committed and clean")
    for cached in (False, True):
        command = ["git", "diff", "--quiet"]
        if cached:
            command.append("--cached")
        command.extend([protocol_freeze_commit, "--", *PROTOCOL_SCOPED_PATHS])
        difference = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if difference.returncode != 0:
            raise ValueError(
                "C3 protocol-scoped paths differ from protocol-freeze commit"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol-freeze-commit", required=True)
    parser.add_argument("--instruction-sha256", required=True)
    parser.add_argument("--output-schema-sha256", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    verify_repository_protocol_pins(
        protocol_freeze_commit=args.protocol_freeze_commit,
        instruction_sha256=args.instruction_sha256,
        output_schema_sha256=args.output_schema_sha256,
    )
    paths = write_corpus(
        args.output_dir,
        protocol_freeze_commit=args.protocol_freeze_commit,
        instruction_sha256=args.instruction_sha256,
        output_schema_sha256=args.output_schema_sha256,
    )
    print(
        _canonical_json(
            {
                "output_dir": str(args.output_dir.expanduser().resolve()),
                "files": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in paths
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
