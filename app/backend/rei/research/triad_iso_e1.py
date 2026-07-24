"""TRIAD-ISO-E1 four-case native route-isolation execution.

This research-only module prepares route-specific, content-addressed packets
from the frozen TRIAD-ISO-P1 candidate.  It deliberately has no governance or
character replay path.  Execution is split into create-only seal, one-call
steps, finalization, and cold verification so a model attempt can never be
silently repeated after a process interruption.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel

from ..ids import canonical_json_bytes, content_id, sha256_hex, utc_now
from ..instinkt.packets import (
    InstinktEffectSpec,
    bind_instinkt_effects,
    build_instinkt_packet,
)
from ..models.emocio import EmocioInputPacket, EmocioWorld
from ..models.instinkt import (
    BODY_DIMENSIONS,
    BodyDelta,
    BodyState,
    InstinktInputPacket,
    InstinktSimulationConfig,
    OptionBodyEffect,
)
from ..models.provider import ProviderCallSpec
from ..models.racio import RacioConsequence, RacioInputPacket, RacioWorld
from ..models.scene import DecisionOption, EvidenceItem, SceneEvent
from ..providers.deterministic import DeterministicInstinktNativeProvider
from ..providers.native import SystemExecutionClock
from ..providers.ollama import OllamaStructuredOutputValidationError
from ..providers.ollama_en import OLLAMA_EN_TRIAD_PROVIDER_REVISION
from ..racio.packets import build_racio_packet
from ..racio.text_reasoner_adapter import RACIO_STRUCTURED_INSTRUCTION_EN
from .triad_d1 import canonical_fingerprint
from .triad_s2 import (
    EXPECTED_MODEL_DIGEST,
    MODEL_PROFILE,
    ResearchEmocioExecution,
    _build_s2_emocio_packet,
    _emocio_call_spec,
    _failed_record,
    _instinkt_projection,
    _valuation_projection,
    build_provider,
    compile_s2_emocio_counterfactuals,
    execute_research_emocio_once,
)


CANDIDATE_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-p1-2026-07-23/"
    "route_isolation_corpus_candidate.json"
)
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-e1-2026-07-24"
)
EXPECTED_BASE_COMMIT: Final = "041f60b327ae13cabface0acd5f8a1ff30c4be42"
EXPECTED_CANDIDATE_SHA256: Final = (
    "e9e1608b5eb3e472e6953c310749f21b676013602d5658849ab36356701144aa"
)
CASE_ORDER: Final = (
    "trip_racio_utility_material",
    "trip_racio_utility_pleasure",
    "trip_protective_context_exposed",
    "trip_protective_context_supported",
)
PAIR_CASES: Final[Mapping[str, tuple[str, str]]] = {
    "trip_racio_utility": CASE_ORDER[:2],
    "trip_protective_context": CASE_ORDER[2:],
}
EMOCIO_PROVIDER_REVISION: Final = "triad-iso-e1-structured-core-route-v1"
INSTINKT_MAPPER_REVISION: Final = "triad-iso-e1-typed-core-route-v1"
EXECUTION_POLICY: Final[Mapping[str, Any]] = {
    "case_order": CASE_ORDER,
    "racio_model_calls_per_case": 1,
    "emocio_native_executions_per_case": 1,
    "instinkt_native_executions_per_case": 1,
    "execute_emocio_after_racio_rejection_or_provider_failure": True,
    "execute_instinkt_after_racio_rejection_or_provider_failure": True,
    "retries": 0,
    "fallbacks": 0,
    "character_replay": 0,
    "conscious_decision": 0,
    "behavior_resultant": 0,
    "ego_update": 0,
}
PRIVATE_KEYS: Final = frozenset(
    {"thinking", "thoughts", "reasoning_content", "chain_of_thought"}
)
LEAKAGE_KEYS: Final = frozenset(
    {
        "character",
        "character_profile",
        "governance",
        "governance_tier",
        "expected_option",
        "expected_option_id",
        "expected_action",
        "expected_motive",
        "leading_mind",
        "gold_route",
    }
)
FORBIDDEN_PROTECTIVE_TERMS: Final = (
    "companion",
    "lodging",
    "transport",
    "unfamiliar",
    "return path",
    "return-path",
)


CORE_EFFECT_RULES: Final[Mapping[str, Mapping[str, float]]] = {
    "resource_commitment_25": {"resource_security": -0.15},
    "resource_commitment_38": {"resource_security": -0.20},
    "nonrefundable_commitment": {
        "resource_security": -0.05,
        "escape_availability": -0.10,
    },
    "bounded_cancellation": {
        "escape_availability": 0.12,
        "predictability": 0.08,
    },
    "trusted_attachment_support": {
        "trust": 0.12,
        "attachment_security": 0.15,
        "tension": -0.05,
    },
    "alone_without_trusted_support": {
        "trust": -0.10,
        "attachment_security": -0.15,
        "tension": 0.10,
    },
    "unfamiliar_environment": {
        "predictability": -0.15,
        "uncertainty": 0.12,
    },
    "verified_providers": {
        "trust": 0.10,
        "predictability": 0.10,
    },
    "unverified_providers": {
        "trust": -0.15,
        "uncertainty": 0.10,
    },
    "verified_return_path": {
        "escape_availability": 0.15,
        "predictability": 0.10,
    },
    "uncertain_return_path": {
        "escape_availability": -0.20,
        "uncertainty": 0.15,
    },
    "avoids_distant_exposure": {
        "escape_availability": 0.12,
        "tension": -0.08,
    },
    "local_bounded_exposure": {"predictability": 0.08},
    "resource_preserved": {"resource_security": 0.15},
}


@dataclass(frozen=True, slots=True)
class PreparedIsoCase:
    case_id: str
    pair_id: str
    candidate: Mapping[str, Any]
    racio_scene: SceneEvent
    racio_world: RacioWorld
    racio_packet: RacioInputPacket
    racio_call_spec: ProviderCallSpec
    racio_request_payload: Mapping[str, Any]
    scene: SceneEvent
    emocio_world: EmocioWorld
    emocio_packet: EmocioInputPacket
    emocio_compiled: Any
    emocio_counterfactual_lineage: tuple[Mapping[str, Any], ...]
    emocio_call_spec: ProviderCallSpec
    instinkt_scene: SceneEvent
    body_state: BodyState
    instinkt_packet: InstinktInputPacket
    instinkt_effects: tuple[OptionBodyEffect, ...]
    instinkt_effect_lineage: tuple[Mapping[str, Any], ...]
    instinkt_config: InstinktSimulationConfig
    instinkt_call_spec: ProviderCallSpec


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        _projection(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    )
    path.write_text(rendered + "\n", encoding="utf-8", newline="\n")


def _projection(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", round_trip=True)
    if dataclasses.is_dataclass(value):
        return {
            field.name: _projection(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _projection(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_projection(child) for child in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(_projection(value))).hexdigest()


def _git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _walk(value: Any, path: tuple[str, ...] = ()):
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _diff_paths(
    left: Any,
    right: Any,
    path: tuple[str, ...] = (),
) -> list[Mapping[str, Any]]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        result: list[Mapping[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                result.append(
                    {
                        "path": "/".join((*path, str(key))),
                        "left": left.get(key),
                        "right": right.get(key),
                    }
                )
            else:
                result.extend(_diff_paths(left[key], right[key], (*path, str(key))))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        if len(left) != len(right):
            result.append(
                {
                    "path": "/".join(path),
                    "left_length": len(left),
                    "right_length": len(right),
                }
            )
            return result
        for index, (lvalue, rvalue) in enumerate(zip(left, right, strict=True)):
            result.extend(
                _diff_paths(lvalue, rvalue, (*path, str(index)))
            )
        return result
    if left != right:
        return [{"path": "/".join(path), "left": left, "right": right}]
    return []


def _case_index(candidate: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for pair in candidate["pairs"]:
        for case in pair["variants"]:
            result[case["case_id"]] = {
                **case,
                "_pair_id": pair["pair_id"],
            }
    return result


def _options(source: Mapping[str, Any]) -> tuple[DecisionOption, ...]:
    return tuple(
        DecisionOption(
            option_id=item["option_id"],
            label=item["description"],
            description=item["description"],
        )
        for item in source["options"]
    )


def _fact_map(source: Mapping[str, Any]) -> dict[str, str]:
    return {item["evidence_id"]: item["text"] for item in source["facts"]}


def _unknown_map(source: Mapping[str, Any]) -> dict[str, str]:
    return {item["unknown_id"]: item["text"] for item in source["unknowns"]}


def _scene(
    *,
    route: str,
    source: Mapping[str, Any],
    evidence_ids: Sequence[str],
    unknown_ids: Sequence[str] = (),
    raw_input: str,
    modality: str,
    actors: Sequence[str] = ("self",),
    constraints: Sequence[str] = (),
) -> SceneEvent:
    facts = _fact_map(source)
    unknowns = _unknown_map(source)
    base = {
        "schema_version": "rei-native-scene-event-v1",
        "raw_input": raw_input,
        "language": "en",
        "evidence": tuple(
            EvidenceItem(
                evidence_id=evidence_id,
                modality=modality,
                content=facts[evidence_id],
                grounded=True,
                source_ref=f"triad-iso-e1:{route}:{evidence_id}",
                confidence=1.0,
                provenance_kind="supplied",
            )
            for evidence_id in evidence_ids
        ),
        "options": _options(source),
        "actors": tuple(actors),
        "constraints": tuple(constraints),
        "unknowns": tuple(unknowns[item] for item in unknown_ids),
    }
    return SceneEvent(
        event_id=content_id(f"triad_iso_e1_{route}_scene", base),
        **base,
    )


def _racio_preparation(
    case: Mapping[str, Any],
    provider: Any,
) -> tuple[
    SceneEvent,
    RacioWorld,
    RacioInputPacket,
    ProviderCallSpec,
    Mapping[str, Any],
]:
    source = case["operational_en"]
    route = case["route_packets"]["racio"]
    scene = _scene(
        route="racio",
        source=source,
        evidence_ids=route["facts"],
        unknown_ids=route["unknowns"],
        raw_input=source["event"],
        modality="text",
        constraints=(
            "Use only the explicit facts and unknowns in this packet.",
            "Do not infer undeclared strategic or material benefit.",
            "Retain bounded uncertainty and select only a public option.",
        ),
    )
    fact_texts = tuple(item.content for item in scene.evidence)
    world_base = {
        "schema_version": "rei-native-racio-world-v1",
        "explicit_beliefs": (
            f"Explicit goal: {route['explicit_goal']}",
            f"Explicit beneficiary: {route['explicit_beneficiary']}",
        ),
        "facts": fact_texts,
        "rules": (
            "Compassion is not assumed as an unstated decision goal.",
            "A benefit must be explicit, beneficiary-addressed, and grounded.",
            "Attraction or rarity is not an undeclared strategic return.",
        ),
        "timelines": tuple(route["time_sequence"]),
        "commitments": (
            f"Opportunity cost: {route['opportunity_cost']}",
            f"Control and enforceability: {route['enforceability_control']}",
        ),
    }
    world = RacioWorld(
        world_id=content_id("triad_iso_e1_racio_world", world_base),
        **world_base,
    )
    evidence_ids = tuple(route["facts"])
    consequences = tuple(
        RacioConsequence(
            option_id=item["option_id"],
            consequence=(
                f"Beneficiary {item['beneficiary']}: {item['consequence']}"
            ),
            evidence_ids=evidence_ids,
        )
        for item in route["material_strategic_consequences"]
    )
    numeric_cues: list[int | float] = []
    numeric_source = " ".join(
        (
            *fact_texts,
            *(item.consequence for item in consequences),
            route["opportunity_cost"],
        )
    )
    for token in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", numeric_source):
        value: int | float = float(token) if "." in token else int(token)
        if value not in numeric_cues:
            numeric_cues.append(value)
    packet = build_racio_packet(
        scene,
        world,
        symbolic_and_language_cues=(
            source["event"],
            f"Explicit goal: {route['explicit_goal']}",
            f"Explicit beneficiary: {route['explicit_beneficiary']}",
        ),
        numeric_cues=tuple(numeric_cues),
        time=tuple(route["time_sequence"]),
        rules=world.rules,
        explicit_consequences=consequences,
    )
    call_spec = provider.build_call_spec(packet)
    request_payload = provider.request_payload(packet)
    serialized = json.dumps(request_payload, ensure_ascii=False).lower()
    if any(token in serialized for token in ("canonical_sl", "notes_sl", "prompt_sl")):
        raise ValueError("Racio payload contains a forbidden source-language field")
    return scene, world, packet, call_spec, request_payload


def _emocio_counterfactuals(
    route: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    result = []
    for item in route["option_visible_changes"]:
        change = item["change"]
        lowered = change.lower()
        active_movement = not any(
            token in lowered
            for token in ("remain inactive", "remains in", "stays in", "no travel")
        )
        distant = "distant" in lowered
        local = "local" in lowered
        obstacle = route["rival_or_obstacle"]
        result.append(
            {
                "option_id": item["option_id"],
                "evidence_basis_ids": tuple(item["evidence_ids"]),
                "delta": {
                    "entities_added": (change,),
                    "entities_removed": (),
                    "composition_changes": (change,),
                    "movement": ((change,) if active_movement else ()),
                    "self_position": route["self_position"],
                    "attention": (
                        ()
                        if route["attention_recognition"] == "not_relevant"
                        else (route["attention_recognition"],)
                    ),
                    "belonging": route["audience"],
                    "status_relations": (
                        ()
                        if route["attention_recognition"] == "not_relevant"
                        else (route["attention_recognition"],)
                    ),
                    "attraction_markers": (
                        (route["attraction_enjoyment"],)
                        if distant or local
                        else ()
                    ),
                    "obstacle_persistence": (() if active_movement else (obstacle,)),
                    "obstacle_removal": ((obstacle,) if active_movement else ()),
                },
            }
        )
    return tuple(result)


def _emocio_preparation(
    case: Mapping[str, Any],
) -> tuple[
    SceneEvent,
    EmocioWorld,
    EmocioInputPacket,
    Any,
    tuple[Mapping[str, Any], ...],
    ProviderCallSpec,
]:
    source = case["operational_en"]
    route = case["route_packets"]["emocio"]
    counterfactuals = _emocio_counterfactuals(route)
    evidence_ids = {
        evidence_id
        for item in route["option_visible_changes"]
        for evidence_id in item["evidence_ids"]
    }
    if "companion is present" in route["current_scene"].lower():
        evidence_ids.add(
            next(
                item["evidence_id"]
                for item in source["facts"]
                if "companion" in item["evidence_id"]
            )
        )
    has_companion = "companion" in route["current_scene"].lower()
    scene = _scene(
        route="emocio",
        source=source,
        evidence_ids=tuple(sorted(evidence_ids)),
        raw_input=route["current_scene"],
        modality="image",
        actors=(("self", "companion") if has_companion else ("self",)),
        constraints=(
            "Structured visual core route only; no image is generated.",
            "Material utility and protective safety are not desired-image cues.",
        ),
    )
    attraction = (
        ()
        if route["attraction_enjoyment"] == "not_relevant"
        else (route["attraction_enjoyment"],)
    )
    world_base = {
        "schema_version": "rei-native-emocio-world-v1",
        "visual_memories": (route["current_scene"],),
        "desired_scenes": (route["desired_scene"],),
        "broken_scenes": (route["broken_scene"],),
        "social_identity_motifs": (
            route["self_position"],
            route["audience"],
            route["attention_recognition"],
        ),
        "attraction_patterns": attraction,
        "motor_patterns": (route["movement_immediacy"],),
    }
    world = EmocioWorld(
        world_id=content_id("triad_iso_e1_emocio_world", world_base),
        **world_base,
    )
    packet = _build_s2_emocio_packet(
        scene=scene,
        counterfactuals=counterfactuals,
    )
    compiled, lineage = compile_s2_emocio_counterfactuals(
        scene=scene,
        packet=packet,
        world=world,
        counterfactuals=counterfactuals,
    )
    call_spec = _emocio_call_spec(
        scene=scene,
        packet=packet,
        world=world,
        counterfactuals=counterfactuals,
    )
    return scene, world, packet, compiled, lineage, call_spec


def _body_state() -> BodyState:
    base = {
        "schema_version": "rei-native-body-state-v1",
        "energy": 0.75,
        "fatigue": 0.20,
        "pain": 0.0,
        "arousal": 0.50,
        "tension": 0.45,
        "physical_integrity": 1.0,
        "uncertainty": 0.55,
        "trust": 0.55,
        "attachment_security": 0.65,
        "resource_security": 0.65,
        "boundary_integrity": 0.80,
        "escape_availability": 0.65,
        "predictability": 0.50,
    }
    return BodyState(
        body_state_id=content_id("triad_iso_e1_body_state", base),
        **base,
    )


def _effect_categories(
    *,
    consequence: str,
    evidence_text: str,
) -> tuple[str, ...]:
    consequence_lower = consequence.lower()
    combined = f"{consequence} {evidence_text}".lower()
    categories: set[str] = set()
    preserves = "preserve" in consequence_lower
    avoids = "avoid" in consequence_lower
    local = "local" in consequence_lower
    if preserves:
        categories.add("resource_preserved")
    elif local:
        categories.add("local_bounded_exposure")
    else:
        if "25 percent" in combined:
            categories.add("resource_commitment_25")
        if "38 percent" in combined:
            categories.add("resource_commitment_38")
    if not preserves and "non-refundable" in combined:
        categories.add("nonrefundable_commitment")
    if not preserves and "cancel" in combined and "24 hour" in combined:
        categories.add("bounded_cancellation")
    if avoids:
        categories.add("avoids_distant_exposure")
    if not avoids:
        if (
            "no trusted companion" in combined
            or "travels alone" in combined
            or "enters the unfamiliar route alone" in combined
        ):
            categories.add("alone_without_trusted_support")
        elif "trusted companion" in combined or "trusted close" in combined:
            categories.add("trusted_attachment_support")
        if "unfamiliar" in combined:
            categories.add("unfamiliar_environment")
        if "unverified" in combined or "not been verified" in combined:
            categories.add("unverified_providers")
        elif "verified provider" in combined or "providers are verified" in combined:
            categories.add("verified_providers")
        if (
            "uncertain physical return" in combined
            or "no confirmed booking" in combined
            or "return path will be available" in combined
        ):
            categories.add("uncertain_return_path")
        elif (
            "physical return is verified" in combined
            or (
                "confirmed booking" in combined
                and ("alternate" in combined or "return path" in combined)
            )
        ):
            categories.add("verified_return_path")
    if not categories:
        categories.add("local_bounded_exposure")
    return tuple(sorted(categories))


def _effect_deltas(categories: Sequence[str]) -> dict[str, float]:
    combined: dict[str, float] = {}
    for category in categories:
        for dimension, delta in CORE_EFFECT_RULES[category].items():
            combined[dimension] = combined.get(dimension, 0.0) + delta
    return {
        dimension: round(max(-0.25, min(0.25, combined[dimension])), 6)
        for dimension in BODY_DIMENSIONS
        if dimension in combined
    }


def _effect_action(deltas: Mapping[str, float]) -> str:
    if deltas.get("physical_integrity", 0.0) < 0.0:
        return "seek_safety"
    if deltas.get("resource_security", 0.0) < 0.0:
        return "conserve"
    if deltas.get("boundary_integrity", 0.0) < 0.0:
        return "set_boundary"
    if deltas.get("escape_availability", 0.0) < 0.0:
        return "withdraw"
    return "maintain"


def _dimension_outcome(deltas: Mapping[str, float], dimension: str) -> str:
    value = deltas.get(dimension)
    if value is None:
        return f"not_changed_by_grounded_consequence:{dimension}"
    return f"grounded_consequence_delta:{dimension}:{value:+.6f}"


def _instinkt_preparation(
    case: Mapping[str, Any],
) -> tuple[
    SceneEvent,
    BodyState,
    InstinktInputPacket,
    tuple[OptionBodyEffect, ...],
    tuple[Mapping[str, Any], ...],
    InstinktSimulationConfig,
    ProviderCallSpec,
]:
    source = case["operational_en"]
    route = case["route_packets"]["instinkt"]
    consequences = route["option_consequences"]
    evidence_ids = tuple(
        sorted(
            {
                evidence_id
                for item in consequences
                for evidence_id in item["evidence_ids"]
            }
        )
    )
    scene = _scene(
        route="instinkt",
        source=source,
        evidence_ids=evidence_ids,
        raw_input=route["protected_target"],
        modality="body",
        constraints=(
            "Typed protective core route only; no raw-scene perception is claimed.",
            "Option effects derive only from grounded option consequences.",
        ),
    )
    body = _body_state()
    packet = build_instinkt_packet(
        scene,
        body,
        physical_cues=(route["danger_types"], route["possible_loss"]),
        uncertainty_cues=(route["danger_types"], route["recoverability"]),
        trust_cues=(route["trust_distrust"],),
        boundary_cues=(route["boundary"],),
        attachment_cues=(route["attachment_care"], route["protected_target"]),
        scarcity_cues=(route["scarcity"],),
        escape_cues=(
            route["escape_reversibility"],
            route["recoverability"],
            route["familiarity"],
        ),
        explicit_body_cues=(
            ()
            if route["prior_association"] == "not_relevant"
            else (route["prior_association"],)
        ),
        evidence_ids=evidence_ids,
        caveat=(
            "TRIAD-ISO-E1 profile-blind typed core-route packet. Effects derive "
            "only from grounded option-specific consequence evidence; no "
            "preferred option, character, governance tier, or raw-scene claim."
        ),
    )
    facts = _fact_map(source)
    specs = []
    lineage = []
    for item in sorted(consequences, key=lambda value: value["option_id"]):
        evidence_text = " ".join(facts[eid] for eid in item["evidence_ids"])
        categories = _effect_categories(
            consequence=item["consequence"],
            evidence_text=evidence_text,
        )
        deltas = _effect_deltas(categories)
        option_evidence = tuple(sorted(item["evidence_ids"]))
        spec = InstinktEffectSpec(
            option_id=item["option_id"],
            body_deltas=tuple(
                BodyDelta(dimension=dimension, delta=delta)
                for dimension, delta in deltas.items()
            ),
            base_predicted_loss=0.5,
            base_recoverability=0.5,
            dominant_alarm="grounded_core_route:" + "+".join(categories),
            protected_targets=(route["protected_target"],),
            boundary_outcome=_dimension_outcome(deltas, "boundary_integrity"),
            trust_outcome=_dimension_outcome(deltas, "trust"),
            attachment_outcome=_dimension_outcome(
                deltas, "attachment_security"
            ),
            escape_outcome=_dimension_outcome(
                deltas, "escape_availability"
            ),
            action_tendency=_effect_action(deltas),
            minimum_safety_condition=(
                "the grounded consequence and its cited evidence remain valid"
            ),
            association_cue_tokens=categories,
            triggering_evidence_ids=option_evidence,
        )
        specs.append(spec)
        lineage.append(
            {
                "option_id": item["option_id"],
                "consequence_fact": item["consequence"],
                "source_evidence_ids": option_evidence,
                "source_evidence_text": tuple(facts[eid] for eid in option_evidence),
                "effect_categories": categories,
                "derived_body_deltas": deltas,
            }
        )
    effects = bind_instinkt_effects(packet, tuple(specs))
    by_option = {item.option_id: item for item in effects}
    frozen_lineage = tuple(
        {
            **item,
            "effect_id": by_option[item["option_id"]].effect_id,
            "effect_signature": canonical_fingerprint(
                by_option[item["option_id"]].model_dump(
                    mode="json",
                    exclude={"effect_id", "source_packet_id", "source_packet_hash"},
                )
            ),
        }
        for item in lineage
    )
    if len({item["effect_signature"] for item in frozen_lineage}) < 2:
        raise ValueError(
            f"Instinkt effect signatures are inert for {case['case_id']}"
        )
    config = InstinktSimulationConfig.create()
    provider = DeterministicInstinktNativeProvider()
    call_spec = provider.build_call_spec(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=effects,
        config=config,
    )
    return scene, body, packet, effects, frozen_lineage, config, call_spec


def prepare_cases(
    candidate: Mapping[str, Any],
    provider: Any,
) -> tuple[PreparedIsoCase, ...]:
    index = _case_index(candidate)
    prepared = []
    for case_id in CASE_ORDER:
        case = index[case_id]
        r_scene, r_world, r_packet, r_call, r_payload = _racio_preparation(
            case, provider
        )
        e_scene, e_world, e_packet, e_compiled, e_lineage, e_call = (
            _emocio_preparation(case)
        )
        i_scene, body, i_packet, effects, i_lineage, config, i_call = (
            _instinkt_preparation(case)
        )
        prepared.append(
            PreparedIsoCase(
                case_id=case_id,
                pair_id=case["_pair_id"],
                candidate=case,
                racio_scene=r_scene,
                racio_world=r_world,
                racio_packet=r_packet,
                racio_call_spec=r_call,
                racio_request_payload=r_payload,
                scene=e_scene,
                emocio_world=e_world,
                emocio_packet=e_packet,
                emocio_compiled=e_compiled,
                emocio_counterfactual_lineage=e_lineage,
                emocio_call_spec=e_call,
                instinkt_scene=i_scene,
                body_state=body,
                instinkt_packet=i_packet,
                instinkt_effects=effects,
                instinkt_effect_lineage=i_lineage,
                instinkt_config=config,
                instinkt_call_spec=i_call,
            )
        )
    return tuple(prepared)


def _assert_candidate_contract(candidate: Mapping[str, Any]) -> None:
    index = _case_index(candidate)
    if tuple(case_id for case_id in CASE_ORDER if case_id in index) != CASE_ORDER:
        raise ValueError("The frozen candidate does not contain the approved cases")
    for case_id in CASE_ORDER:
        case = index[case_id]
        for path, value in _walk(case):
            if path and path[-1].lower() in LEAKAGE_KEYS:
                raise ValueError(
                    f"Leakage key in {case_id}: {'/'.join(path)}"
                )
            if isinstance(value, str) and re.search(
                r"\b(preferred|safest|best|gold route|leading mind)\b",
                value,
                flags=re.IGNORECASE,
            ):
                raise ValueError(
                    f"Expected-answer leakage in {case_id}: {'/'.join(path)}"
                )
        sl = case["canonical_sl"]
        en = case["operational_en"]
        if [x["evidence_id"] for x in sl["facts"]] != [
            x["evidence_id"] for x in en["facts"]
        ]:
            raise ValueError(f"SL/EN evidence IDs differ for {case_id}")
        if [x["unknown_id"] for x in sl["unknowns"]] != [
            x["unknown_id"] for x in en["unknowns"]
        ]:
            raise ValueError(f"SL/EN unknown IDs differ for {case_id}")
        if [x["option_id"] for x in sl["options"]] != [
            x["option_id"] for x in en["options"]
        ]:
            raise ValueError(f"SL/EN option IDs differ for {case_id}")
    for pair_id, (left_id, right_id) in PAIR_CASES.items():
        left = index[left_id]
        right = index[right_id]
        if left["canonical_sl"]["options"] != right["canonical_sl"]["options"]:
            raise ValueError(f"SL public options changed within {pair_id}")
        if left["operational_en"]["options"] != right["operational_en"]["options"]:
            raise ValueError(f"EN public options changed within {pair_id}")


def pair_invariant_report(
    candidate: Mapping[str, Any],
    prepared: Sequence[PreparedIsoCase],
) -> Mapping[str, Any]:
    _assert_candidate_contract(candidate)
    by_id = {item.case_id: item for item in prepared}
    index = _case_index(candidate)
    material = by_id["trip_racio_utility_material"]
    pleasure = by_id["trip_racio_utility_pleasure"]
    exposed = by_id["trip_protective_context_exposed"]
    supported = by_id["trip_protective_context_supported"]

    utility_raw_diff = _diff_paths(
        index[material.case_id],
        index[pleasure.case_id],
    )
    utility_allowed_prefixes = (
        "case_id",
        "variant_id",
        "_pair_id",
        "canonical_sl/facts/6/text",
        "canonical_sl/facts/7/text",
        "canonical_sl/unknowns/1/text",
        "operational_en/facts/6/text",
        "operational_en/facts/7/text",
        "operational_en/unknowns/1/text",
        "route_packets/racio/",
    )
    utility_unexpected = [
        item
        for item in utility_raw_diff
        if not item["path"].startswith(utility_allowed_prefixes)
    ]
    protective_raw_diff = _diff_paths(
        index[exposed.case_id],
        index[supported.case_id],
    )
    protective_allowed_prefixes = (
        "case_id",
        "variant_id",
        "_pair_id",
        "canonical_sl/facts/5/text",
        "canonical_sl/facts/6/text",
        "canonical_sl/facts/7/text",
        "canonical_sl/facts/8/text",
        "canonical_sl/unknowns",
        "operational_en/facts/5/text",
        "operational_en/facts/6/text",
        "operational_en/facts/7/text",
        "operational_en/facts/8/text",
        "operational_en/unknowns",
        "route_packets/emocio/",
        "route_packets/instinkt/",
    )
    protective_unexpected = [
        item
        for item in protective_raw_diff
        if not item["path"].startswith(protective_allowed_prefixes)
    ]

    checks = {
        "utility_emocio_route_packet_identical": (
            index[material.case_id]["route_packets"]["emocio"]
            == index[pleasure.case_id]["route_packets"]["emocio"]
        ),
        "utility_instinkt_route_packet_identical": (
            index[material.case_id]["route_packets"]["instinkt"]
            == index[pleasure.case_id]["route_packets"]["instinkt"]
        ),
        "utility_prepared_emocio_packet_identical": (
            material.emocio_packet == pleasure.emocio_packet
            and material.emocio_world == pleasure.emocio_world
            and material.emocio_compiled == pleasure.emocio_compiled
        ),
        "utility_prepared_instinkt_packet_identical": (
            material.instinkt_packet == pleasure.instinkt_packet
            and material.instinkt_effects == pleasure.instinkt_effects
        ),
        "utility_unexpected_pair_diffs_absent": not utility_unexpected,
        "protective_racio_route_packet_identical": (
            index[exposed.case_id]["route_packets"]["racio"]
            == index[supported.case_id]["route_packets"]["racio"]
        ),
        "protective_racio_request_payload_byte_identical": (
            canonical_json_bytes(exposed.racio_request_payload)
            == canonical_json_bytes(supported.racio_request_payload)
        ),
        "protective_racio_call_spec_identical": (
            exposed.racio_call_spec == supported.racio_call_spec
        ),
        "protective_unexpected_pair_diffs_absent": not protective_unexpected,
        "all_options_and_order_held": all(
            index[left]["operational_en"]["options"]
            == index[right]["operational_en"]["options"]
            for left, right in PAIR_CASES.values()
        ),
        "no_expected_or_character_governance_leakage": True,
    }
    passed = all(checks.values())
    return {
        "schema_version": "triad-iso-e1-pair-invariants-v1",
        "phase": "TRIAD-ISO-E1",
        "passed": passed,
        "checks": checks,
        "utility_pair": {
            "declared_differences": utility_raw_diff,
            "unexpected_differences": utility_unexpected,
            "held_constant": {
                "emocio_route_packet_sha256": _object_sha256(
                    index[material.case_id]["route_packets"]["emocio"]
                ),
                "instinkt_route_packet_sha256": _object_sha256(
                    index[material.case_id]["route_packets"]["instinkt"]
                ),
                "options_sha256": _object_sha256(
                    index[material.case_id]["operational_en"]["options"]
                ),
            },
        },
        "protective_pair": {
            "declared_differences": protective_raw_diff,
            "unexpected_differences": protective_unexpected,
            "held_constant": {
                "racio_route_packet_sha256": _object_sha256(
                    index[exposed.case_id]["route_packets"]["racio"]
                ),
                "racio_request_payload_sha256": _object_sha256(
                    exposed.racio_request_payload
                ),
                "options_sha256": _object_sha256(
                    index[exposed.case_id]["operational_en"]["options"]
                ),
            },
        },
    }


def _input_projection(item: PreparedIsoCase) -> Mapping[str, Any]:
    return {
        "schema_version": "triad-iso-e1-sealed-inputs-v1",
        "case_id": item.case_id,
        "pair_id": item.pair_id,
        "source_reference": {
            "candidate_path": CANDIDATE_RELATIVE_PATH.as_posix(),
            "case_id": item.case_id,
            "candidate_case_sha256": _object_sha256(
                {key: value for key, value in item.candidate.items() if key != "_pair_id"}
            ),
        },
        "canonical_sl": item.candidate["canonical_sl"],
        "operational_en": item.candidate["operational_en"],
        "racio": {
            "scene": item.racio_scene,
            "world": item.racio_world,
            "packet": item.racio_packet,
            "request_payload": item.racio_request_payload,
            "call_spec": item.racio_call_spec,
        },
        "emocio": {
            "mode": "manual_structured_core_route",
            "scene": item.scene,
            "world": item.emocio_world,
            "packet": item.emocio_packet,
            "compiled_scenes": item.emocio_compiled,
            "counterfactual_lineage": item.emocio_counterfactual_lineage,
            "call_spec": item.emocio_call_spec,
            "image_generation_calls": 0,
        },
        "instinkt": {
            "mode": "typed_core_route",
            "scene": item.instinkt_scene,
            "body_state": item.body_state,
            "packet": item.instinkt_packet,
            "option_effects": item.instinkt_effects,
            "effect_lineage": item.instinkt_effect_lineage,
            "simulation_config": item.instinkt_config,
            "call_spec": item.instinkt_call_spec,
            "model_mapper_calls": 0,
            "raw_scene_perception_claim": False,
        },
        "profile_blind": True,
        "character_replay": 0,
    }


def _expected_ledger(prepared: Sequence[PreparedIsoCase]) -> Mapping[str, Any]:
    return {
        "schema_version": "triad-iso-e1-expected-call-ledger-v1",
        "phase": "TRIAD-ISO-E1",
        "state": "sealed_before_calls",
        "expected": {
            "model_calls": 4,
            "retries": 0,
            "fallbacks": 0,
            "character_replay_rows": 0,
        },
        "execution_policy": EXECUTION_POLICY,
        "entries": [
            {
                "ordinal": ordinal,
                "case_id": item.case_id,
                "racio_call_id": item.racio_call_spec.call_id,
                "racio_call_spec_hash": item.racio_call_spec.content_hash(),
                "emocio_call_id": item.emocio_call_spec.call_id,
                "instinkt_call_id": item.instinkt_call_spec.call_id,
                "status": "sealed",
            }
            for ordinal, item in enumerate(prepared, start=1)
        ],
    }


def seal_e1(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    if output_root.exists():
        raise ValueError("TRIAD-ISO-E1 output root already exists; seal is create-only")
    candidate_path = repository_root / CANDIDATE_RELATIVE_PATH
    if _file_sha256(candidate_path) != EXPECTED_CANDIDATE_SHA256:
        raise ValueError("Frozen TRIAD-ISO-P1 candidate SHA-256 changed")
    base_commit = _git(repository_root, "rev-parse", "HEAD")
    if base_commit != EXPECTED_BASE_COMMIT:
        raise ValueError(
            f"TRIAD-ISO-E1 expected base {EXPECTED_BASE_COMMIT}, observed {base_commit}"
        )
    candidate = _json(candidate_path)
    _assert_candidate_contract(candidate)
    provider = build_provider()
    if provider.runtime.digest != EXPECTED_MODEL_DIGEST:
        raise ValueError("Exact local model digest differs before seal")
    prepared = prepare_cases(candidate, provider)
    report = pair_invariant_report(candidate, prepared)
    if not report["passed"]:
        raise ValueError(
            "Pair invariant preflight failed: "
            + json.dumps(
                {
                    key: value
                    for key, value in report["checks"].items()
                    if not value
                },
                sort_keys=True,
            )
        )

    subset = {
        "schema_version": "triad-iso-e1-reference-subset-v1",
        "phase": "TRIAD-ISO-E1",
        "status": "sealed_execution_subset",
        "source_candidate": {
            "path": CANDIDATE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_CANDIDATE_SHA256,
        },
        "case_order": CASE_ORDER,
        "cases": [
            {
                "ordinal": ordinal,
                "case_id": item.case_id,
                "pair_id": item.pair_id,
                "source_pointer": (
                    f"/pairs/{next(index for index, pair in enumerate(candidate['pairs']) if pair['pair_id'] == item.pair_id)}"
                    f"/variants/{next(index for index, value in enumerate(next(pair for pair in candidate['pairs'] if pair['pair_id'] == item.pair_id)['variants']) if value['case_id'] == item.case_id)}"
                ),
                "candidate_case_sha256": _object_sha256(
                    {
                        key: value
                        for key, value in item.candidate.items()
                        if key != "_pair_id"
                    }
                ),
                "projection_contract": "canonical_json_bytes_equal_to_source_case",
            }
            for ordinal, item in enumerate(prepared, start=1)
        ],
        "excluded_case_count": 6,
        "excluded_cases_executed": False,
    }
    subset_path = output_root / "execution_subset.json"
    _write_json(subset_path, subset)
    invariant_path = output_root / "pair_invariant_report.json"
    _write_json(invariant_path, report)

    input_records = []
    for item in prepared:
        path = output_root / "cases" / item.case_id / "inputs.json"
        _write_json(path, _input_projection(item))
        input_records.append(
            {
                "case_id": item.case_id,
                "path": path.relative_to(repository_root).as_posix(),
                "sha256": _file_sha256(path),
                "canonical_sl_sha256": _object_sha256(
                    item.candidate["canonical_sl"]
                ),
                "operational_en_sha256": _object_sha256(
                    item.candidate["operational_en"]
                ),
                "racio_packet_sha256": item.racio_packet.content_hash(),
                "emocio_packet_sha256": item.emocio_packet.content_hash(),
                "instinkt_packet_sha256": item.instinkt_packet.content_hash(),
            }
        )

    expected = _expected_ledger(prepared)
    expected_path = output_root / "expected_call_ledger.json"
    _write_json(expected_path, expected)
    module_path = Path(__file__).resolve()
    script_path = repository_root / "scripts/run_triad_iso_e1.py"
    base = {
        "schema_version": "triad-iso-e1-pre-call-execution-seal-v1",
        "phase": "TRIAD-ISO-E1",
        "base_commit": base_commit,
        "source_candidate": {
            "path": CANDIDATE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_CANDIDATE_SHA256,
        },
        "execution_subset": {
            "path": subset_path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(subset_path),
        },
        "pair_invariant_report": {
            "path": invariant_path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(invariant_path),
            "passed": True,
        },
        "case_input_records": input_records,
        "generic_effect_rules_sha256": canonical_fingerprint(CORE_EFFECT_RULES),
        "implementation": {
            "module_path": module_path.relative_to(repository_root).as_posix(),
            "module_sha256": _file_sha256(module_path),
            "script_path": script_path.relative_to(repository_root).as_posix(),
            "script_sha256": _file_sha256(script_path),
        },
        "provider_revision": OLLAMA_EN_TRIAD_PROVIDER_REVISION,
        "emocio_adapter_revision": EMOCIO_PROVIDER_REVISION,
        "instinkt_mapper_revision": INSTINKT_MAPPER_REVISION,
        "instruction_sha256": sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN),
        "model": provider.runtime.model,
        "model_digest": provider.runtime.digest,
        "model_profile": MODEL_PROFILE,
        "call_order": CASE_ORDER,
        "racio_call_specs": [
            _projection(item.racio_call_spec) for item in prepared
        ],
        "deterministic_native_call_specs": [
            {
                "case_id": item.case_id,
                "emocio": item.emocio_call_spec,
                "instinkt": item.instinkt_call_spec,
            }
            for item in prepared
        ],
        "expected_call_ledger": {
            "path": expected_path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(expected_path),
        },
        "execution_policy": EXECUTION_POLICY,
        "output_root": OUTPUT_RELATIVE_PATH.as_posix(),
        "declarations": {
            "character_replay": 0,
            "image_generation_calls": 0,
            "gemma_emocio_shadow_calls": 0,
            "gemma_instinkt_shadow_calls": 0,
            "holdout": False,
            "promotion_evidence": False,
            "global_rei_score": False,
            "thinking_persisted": False,
        },
        "created_at": utc_now(),
    }
    projected_base = _projection(base)
    seal = {
        **projected_base,
        "seal_sha256": canonical_fingerprint(projected_base),
    }
    _write_json(output_root / "pre_call_seal.json", seal)
    return seal


def verify_seal(
    repository_root: Path,
    provider: Any | None = None,
) -> tuple[Mapping[str, Any], tuple[PreparedIsoCase, ...]]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    seal = _json(output_root / "pre_call_seal.json")
    base = {key: value for key, value in seal.items() if key != "seal_sha256"}
    if canonical_fingerprint(base) != seal["seal_sha256"]:
        raise ValueError("TRIAD-ISO-E1 seal hash differs")
    for field in ("source_candidate", "execution_subset", "pair_invariant_report"):
        record = seal[field]
        if _file_sha256(repository_root / record["path"]) != record["sha256"]:
            raise ValueError(f"Sealed file changed: {field}")
    expected = seal["expected_call_ledger"]
    if _file_sha256(repository_root / expected["path"]) != expected["sha256"]:
        raise ValueError("Expected call ledger changed")
    for field in ("module", "script"):
        if _file_sha256(
            repository_root / seal["implementation"][f"{field}_path"]
        ) != seal["implementation"][f"{field}_sha256"]:
            raise ValueError(f"Sealed implementation changed: {field}")
    if seal["generic_effect_rules_sha256"] != canonical_fingerprint(
        CORE_EFFECT_RULES
    ):
        raise ValueError("Sealed generic effect rules changed")
    if seal["instruction_sha256"] != sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN):
        raise ValueError("Sealed Racio instruction changed")
    if seal["model_profile"] != MODEL_PROFILE:
        raise ValueError("Sealed model profile changed")
    active_provider = provider or build_provider()
    if active_provider.runtime.digest != seal["model_digest"]:
        raise ValueError("Exact local model digest changed after seal")
    candidate = _json(repository_root / CANDIDATE_RELATIVE_PATH)
    prepared = prepare_cases(candidate, active_provider)
    if pair_invariant_report(candidate, prepared) != _json(
        repository_root / seal["pair_invariant_report"]["path"]
    ):
        raise ValueError("Cold pair-invariant report differs from sealed report")
    if [_projection(item.racio_call_spec) for item in prepared] != seal[
        "racio_call_specs"
    ]:
        raise ValueError("Racio call specs changed after seal")
    for record, item in zip(seal["case_input_records"], prepared, strict=True):
        path = repository_root / record["path"]
        if _file_sha256(path) != record["sha256"]:
            raise ValueError(f"Sealed input changed: {item.case_id}")
        if _json(path) != _projection(_input_projection(item)):
            raise ValueError(f"Cold input differs: {item.case_id}")
    return seal, prepared


def initialize_execution(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    ledger_path = output_root / "call_ledger.json"
    if ledger_path.exists():
        return _json(ledger_path)
    seal, _ = verify_seal(repository_root)
    expected = _json(output_root / "expected_call_ledger.json")
    ledger = {
        "schema_version": "triad-iso-e1-call-ledger-v1",
        "phase": "TRIAD-ISO-E1",
        "state": "ready",
        "pre_call_seal_sha256": seal["seal_sha256"],
        "expected": expected["expected"],
        "actual": {
            "model_call_attempts": 0,
            "retries": 0,
            "fallbacks": 0,
            "emocio_executions": 0,
            "instinkt_executions": 0,
            "character_replay_rows": 0,
        },
        "entries": [
            {
                "ordinal": item["ordinal"],
                "case_id": item["case_id"],
                "racio_call_id": item["racio_call_id"],
                "status": "planned",
            }
            for item in expected["entries"]
        ],
    }
    _write_json(ledger_path, ledger)
    return ledger


def _failure_projection(
    exc: Exception,
) -> tuple[Mapping[str, Any], Any | None]:
    if isinstance(exc, OllamaStructuredOutputValidationError):
        diagnostic = exc.diagnostic
        return (
            {
                "failure_type": type(exc).__name__,
                "failure_code": diagnostic.failure_code,
                "validation_stage": diagnostic.validation_stage,
                "final_json_sha256": diagnostic.final_json_sha256,
                "accepted": False,
                "message": str(exc),
            },
            diagnostic,
        )
    return (
        {
            "failure_type": type(exc).__name__,
            "failure_code": "non_contract_provider_failure",
            "validation_stage": "provider_execution",
            "final_json_sha256": None,
            "accepted": False,
            "message": str(exc),
        },
        None,
    )


def run_next(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    provider = build_provider()
    seal, prepared = verify_seal(repository_root, provider)
    ledger = initialize_execution(repository_root)
    ledger_path = output_root / "call_ledger.json"
    if ledger["state"] not in {"ready", "executing"}:
        raise ValueError(f"Execution is not runnable from state {ledger['state']}")
    if any(entry["status"] == "dispatching" for entry in ledger["entries"]):
        raise ValueError(
            "A prior model attempt is indeterminate; no retry is permitted"
        )
    next_entry = next(
        (entry for entry in ledger["entries"] if entry["status"] == "planned"),
        None,
    )
    if next_entry is None:
        raise ValueError("All four sealed calls have already been attempted")
    item = next(value for value in prepared if value.case_id == next_entry["case_id"])
    expected_ordinal = ledger["actual"]["model_call_attempts"] + 1
    if next_entry["ordinal"] != expected_ordinal:
        raise ValueError("Sealed call order changed")

    ledger["state"] = "executing"
    next_entry["status"] = "dispatching"
    next_entry["attempt_recorded_before_dispatch"] = True
    ledger["actual"]["model_call_attempts"] += 1
    _write_json(ledger_path, ledger)

    clock = SystemExecutionClock()
    racio_started = utc_now()
    racio_execution = None
    diagnostic = None
    failure = None
    failed_record = None
    try:
        racio_execution = provider.execute(
            item.racio_packet,
            call=item.racio_call_spec,
            clock=clock,
        )
        next_entry["racio_status"] = "accepted"
    except Exception as exc:
        finished = utc_now()
        failure, diagnostic = _failure_projection(exc)
        failed_record = _failed_record(
            call=item.racio_call_spec,
            started_at=racio_started,
            finished_at=finished,
            warning=(
                f"{failure['validation_stage']}:{failure['failure_code']}:"
                f"{failure.get('final_json_sha256') or 'none'}"
            ),
        )
        next_entry["racio_status"] = (
            "rejected"
            if isinstance(exc, OllamaStructuredOutputValidationError)
            else "provider_failed"
        )
        next_entry["failure_code"] = failure["failure_code"]
        next_entry["final_json_sha256"] = failure.get("final_json_sha256")

    emocio_execution: ResearchEmocioExecution = execute_research_emocio_once(
        item, clock=clock
    )
    ledger["actual"]["emocio_executions"] += 1
    instinkt_provider = DeterministicInstinktNativeProvider()
    instinkt_execution = instinkt_provider.execute(
        scene=item.instinkt_scene,
        packet=item.instinkt_packet,
        source_body_state=item.body_state,
        option_effects=item.instinkt_effects,
        config=item.instinkt_config,
        call=item.instinkt_call_spec,
        clock=clock,
    )
    ledger["actual"]["instinkt_executions"] += 1

    case_root = output_root / "cases" / item.case_id
    call_record = {
        "schema_version": "triad-iso-e1-call-record-v1",
        "case_id": item.case_id,
        "racio": {
            "call_spec": item.racio_call_spec,
            "call_record": (
                racio_execution.call_record
                if racio_execution is not None
                else failed_record
            ),
            "result_evidence": (
                racio_execution.reasoning_artifact
                if racio_execution is not None
                else None
            ),
            "failed_output_diagnostic": diagnostic,
            "failure": failure,
            "retries": 0,
            "fallbacks": 0,
        },
        "emocio": {
            "call_spec": emocio_execution.call_spec,
            "call_record": emocio_execution.call_record,
            "uses_model": False,
        },
        "instinkt": {
            "call_spec": instinkt_execution.call_spec,
            "call_record": instinkt_execution.call_record,
            "uses_model": False,
        },
        "private_thinking_persisted": False,
    }
    _write_json(case_root / "call_record.json", call_record)
    native_outputs = {
        "schema_version": "triad-iso-e1-native-outputs-v1",
        "case_id": item.case_id,
        "pair_id": item.pair_id,
        "processor_execution_counts": {"R": 1, "E": 1, "I": 1},
        "racio": (
            {
                "status": "accepted",
                "conclusion": racio_execution.conclusion,
            }
            if racio_execution is not None
            else {
                "status": "rejected",
                "conclusion": None,
                "failure": failure,
            }
        ),
        "emocio": {
            "conclusion": emocio_execution.conclusion,
            **_valuation_projection(emocio_execution),
            "counterfactual_lineage": item.emocio_counterfactual_lineage,
        },
        "instinkt": {
            "conclusion": instinkt_execution.conclusion,
            "rollouts": instinkt_execution.rollouts,
            "policy": instinkt_execution.processing.policy,
            **_instinkt_projection(item, instinkt_execution),
            "route_packet": item.candidate["route_packets"]["instinkt"],
        },
        "native_mind_bundle_created": False,
        "character_replay_rows": 0,
    }
    _write_json(case_root / "native_outputs.json", native_outputs)
    next_entry["status"] = "complete"
    next_entry["emocio_status"] = "succeeded"
    next_entry["instinkt_status"] = "succeeded"
    if ledger["actual"]["model_call_attempts"] == 4:
        ledger["state"] = "four_calls_complete"
    _write_json(ledger_path, ledger)
    return {
        "case_id": item.case_id,
        "ordinal": next_entry["ordinal"],
        "racio_status": next_entry["racio_status"],
        "failure_code": next_entry.get("failure_code"),
        "emocio_option": emocio_execution.conclusion.option_id,
        "instinkt_option": instinkt_execution.conclusion.option_id,
        "model_call_attempts": ledger["actual"]["model_call_attempts"],
    }


def _semantic_racio(value: Mapping[str, Any]) -> Mapping[str, Any] | None:
    conclusion = value["racio"]["conclusion"]
    if conclusion is None:
        return None
    return {
        key: conclusion[key]
        for key in (
            "option_id",
            "facts_used",
            "unknowns",
            "causal_sequence",
            "utility_structure",
            "explicit_goal",
            "main_objection",
            "confidence",
            "abstains",
            "uncertainty",
        )
    }


def _semantic_emocio(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "conclusion": {
            key: value["emocio"]["conclusion"][key]
            for key in (
                "option_id",
                "desired_transformation",
                "main_obstacle",
                "action_tendency",
                "intensity",
                "abstains",
                "uncertainty",
            )
        },
        "current_scene": value["emocio"]["current_scene"],
        "desired_scene": value["emocio"]["desired_scene"],
        "broken_scene": value["emocio"]["broken_scene"],
        "counterfactual_scenes": value["emocio"]["counterfactual_scenes"],
        "valuation_vectors": value["emocio"]["valuation_vectors"],
        "aggregate_scores": value["emocio"]["aggregate_scores"],
    }


def _semantic_instinkt(value: Mapping[str, Any]) -> Mapping[str, Any]:
    conclusion = value["instinkt"]["conclusion"]
    return {
        "conclusion": {
            key: conclusion[key]
            for key in (
                "option_id",
                "dominant_alarm",
                "danger_claims",
                "protected_targets",
                "action_tendency",
                "minimum_safety_condition",
                "intensity",
                "abstains",
                "uncertainty",
            )
        },
        "option_paths": value["instinkt"]["option_paths"],
    }


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()


def _pair_analysis(
    outputs: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    material = outputs["trip_racio_utility_material"]
    pleasure = outputs["trip_racio_utility_pleasure"]
    exposed = outputs["trip_protective_context_exposed"]
    supported = outputs["trip_protective_context_supported"]
    r_material = _semantic_racio(material)
    r_pleasure = _semantic_racio(pleasure)
    r_exposed = _semantic_racio(exposed)
    r_supported = _semantic_racio(supported)
    protective_leakage = {}
    for case_id, projection in (
        ("trip_protective_context_exposed", r_exposed),
        ("trip_protective_context_supported", r_supported),
    ):
        rendered = _text(projection) if projection is not None else ""
        protective_leakage[case_id] = [
            term for term in FORBIDDEN_PROTECTIVE_TERMS if term in rendered
        ]
    protective_status = (
        "not_assessable"
        if r_exposed is None or r_supported is None
        else "identical"
        if r_exposed == r_supported
        else "deterministic_instability"
    )
    utility_status = (
        "not_assessable"
        if r_material is None or r_pleasure is None
        else "route_distinct"
        if r_material != r_pleasure
        else "route_not_distinct"
    )
    material_text = _text(r_material)
    pleasure_text = _text(r_pleasure)
    return {
        "racio_protective_pair": {
            "request_payload_byte_identical": True,
            "semantic_stability": protective_status,
            "route_scope_leakage_terms": protective_leakage,
        },
        "racio_utility_pair": {
            "route_distinction": utility_status,
            "material_uses_explicit_studio_benefit": (
                "studio" in material_text
                and ("900" in material_text or "buyer" in material_text)
            ),
            "material_retains_cost": "1200" in material_text,
            "material_retains_uncertainty": bool(
                r_material and r_material["unknowns"]
            ),
            "pleasure_preserves_no_material_return": (
                (
                    "no separate strategic or material return" in pleasure_text
                    or "no business" in pleasure_text
                    or "pleasurable" in pleasure_text
                )
                and "buyer" not in pleasure_text
                and "studio" not in pleasure_text
            ),
        },
        "emocio_utility_pair": {
            "semantic_stability": (
                "identical"
                if _semantic_emocio(material) == _semantic_emocio(pleasure)
                else "non_target_instability"
            ),
        },
        "emocio_protective_pair": {
            "semantic_difference": (
                "identical"
                if _semantic_emocio(exposed) == _semantic_emocio(supported)
                else "cross_visible_companion_effect_or_other_difference"
            )
        },
        "instinkt_utility_pair": {
            "semantic_stability": (
                "identical"
                if _semantic_instinkt(material) == _semantic_instinkt(pleasure)
                else "non_target_instability"
            ),
        },
        "instinkt_protective_pair": {
            "route_distinction": (
                "route_distinct"
                if _semantic_instinkt(exposed) != _semantic_instinkt(supported)
                else "route_not_distinct"
            ),
        },
    }


def _inline(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _markdown_json(value: Any) -> list[str]:
    return [
        "```json",
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2),
        "```",
        "",
    ]


def _human_fields() -> list[str]:
    return [
        "### Human review — blank",
        "",
        "- Racio pair isolation — passed: ",
        "- Racio pair isolation — failed: ",
        "- Racio pair isolation — uncertain: ",
        "- Emocio route fidelity — plausible: ",
        "- Emocio route fidelity — implausible: ",
        "- Emocio route fidelity — uncertain: ",
        "- Instinkt pair isolation — passed: ",
        "- Instinkt pair isolation — failed: ",
        "- Instinkt pair isolation — uncertain: ",
        "- option change required: no",
        "- route meaningfully changed: ",
        "- non-target route remained stable: ",
        "- unsupported inference: ",
        "- cross-route contamination: ",
        "- input appears to predetermine outcome: ",
        "",
    ]


def render_report(
    repository_root: Path,
    summary: Mapping[str, Any],
    outputs: Mapping[str, Mapping[str, Any]],
) -> None:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    inputs = {
        case_id: _json(output_root / "cases" / case_id / "inputs.json")
        for case_id in CASE_ORDER
    }
    lines = [
        "# TRIAD-ISO-E1 — four-case native route-isolation execution",
        "",
        "This is a research-only development execution. It is not a holdout, "
        "not promotion evidence, and it computes no global REI score.",
        "",
        "Emocio used manual structured core-route scenes without image generation. "
        "This does not validate image-native visual cognition.",
        "",
        "Instinkt used grounded typed option consequences. This does not validate "
        "raw-scene Instinkt perception.",
        "",
        "No character replay, ConsciousDecision, BehaviorResultant, or Ego update "
        "was executed.",
        "",
        "## Execution summary",
        "",
        f"- Pre-call seal: `{summary['pre_call_seal_sha256']}`.",
        f"- Candidate SHA-256: `{summary['candidate_sha256']}`.",
        f"- Subset SHA-256: `{summary['subset_sha256']}`.",
        f"- Exact model digest: `{summary['model_digest']}`.",
        f"- Calls/retries/fallbacks: {summary['calls']}/"
        f"{summary['retries']}/{summary['fallbacks']}.",
        f"- Racio accepted/rejected: {summary['racio']['accepted']}/"
        f"{summary['racio']['rejected']}.",
        "",
    ]
    for pair_id, (left_id, right_id) in PAIR_CASES.items():
        left_input = inputs[left_id]
        right_input = inputs[right_id]
        left_output = outputs[left_id]
        right_output = outputs[right_id]
        invariant = _json(output_root / "pair_invariant_report.json")[
            "utility_pair" if pair_id == "trip_racio_utility" else "protective_pair"
        ]
        lines.extend(
            [
                f"## {pair_id}",
                "",
                f"| | `{left_id}` | `{right_id}` |",
                "|---|---|---|",
                "| Racio option | "
                f"`{left_output['racio']['conclusion']['option_id'] if left_output['racio']['conclusion'] else 'rejected'}` | "
                f"`{right_output['racio']['conclusion']['option_id'] if right_output['racio']['conclusion'] else 'rejected'}` |",
                "| Emocio option | "
                f"`{left_output['emocio']['selected_option_id']}` | "
                f"`{right_output['emocio']['selected_option_id']}` |",
                "| Instinkt option | "
                f"`{left_output['instinkt']['selected_option_id']}` | "
                f"`{right_output['instinkt']['selected_option_id']}` |",
                "",
                "### HELD CONSTANT",
                "",
                f"- Public options: `{_inline(left_input['operational_en']['options'])}`.",
                f"- Sealed constant hashes: `{_inline(invariant['held_constant'])}`.",
                "- Route packets expected stable are identified by the pair invariant "
                "report and were cold-rechecked before every call.",
                "",
                "### CHANGED",
                "",
                "Only the following predeclared source paths differ:",
                "",
            ]
        )
        lines.extend(
            f"- `{item['path']}`" for item in invariant["declared_differences"]
        )
        lines.extend(["", "### RACIO", ""])
        for case_id in (left_id, right_id):
            value = inputs[case_id]["racio"]
            output = outputs[case_id]["racio"]
            lines.extend(
                [
                    f"#### `{case_id}` — exact visible packet",
                    "",
                    f"- Selected option: `{output['conclusion']['option_id'] if output['conclusion'] else 'rejected'}`.",
                    f"- Status: `{output['status']}`.",
                    "",
                ]
            )
            lines.extend(_markdown_json(value["packet"]))
            lines.extend(["Route / facts / unknowns / utility / goal:", ""])
            lines.extend(_markdown_json(output["conclusion"]))
        lines.extend(
            [
                "Pair difference (mechanical, not human plausibility judgment):",
                "",
            ]
        )
        pair_key = (
            "racio_utility_pair"
            if pair_id == "trip_racio_utility"
            else "racio_protective_pair"
        )
        lines.extend(_markdown_json(summary["pair_analysis"][pair_key]))
        lines.extend(["### EMOCIO", ""])
        for case_id in (left_id, right_id):
            value = outputs[case_id]["emocio"]
            lines.extend(
                [
                    f"#### `{case_id}`",
                    "",
                    f"- Current: `{_inline(value['current_scene'])}`.",
                    f"- Desired: `{_inline(value['desired_scene'])}`.",
                    f"- Broken: `{_inline(value['broken_scene'])}`.",
                    f"- Selected route: `{value['selected_option_id']}`.",
                    "- Counterfactual option scenes and valuation vectors:",
                    "",
                ]
            )
            lines.extend(
                _markdown_json(
                    {
                        "counterfactual_scenes": value["counterfactual_scenes"],
                        "valuation_vectors": value["valuation_vectors"],
                        "aggregate_scores": value["aggregate_scores"],
                    }
                )
            )
        e_key = (
            "emocio_utility_pair"
            if pair_id == "trip_racio_utility"
            else "emocio_protective_pair"
        )
        lines.extend(
            [
                "Pair difference (mechanical):",
                "",
            ]
        )
        lines.extend(_markdown_json(summary["pair_analysis"][e_key]))
        lines.extend(["### INSTINKT", ""])
        for case_id in (left_id, right_id):
            route = inputs[case_id]["instinkt"]
            value = outputs[case_id]["instinkt"]
            lines.extend(
                [
                    f"#### `{case_id}`",
                    "",
                    f"- Selected route: `{value['selected_option_id']}`.",
                    f"- Danger/trust/attachment/scarcity/escape/recoverability source: "
                    f"`{_inline(value['route_packet'])}`.",
                    "- Consequence/effect paths, predicted loss, recoverability, and "
                    "protective cost:",
                    "",
                ]
            )
            lines.extend(_markdown_json(value["option_paths"]))
        i_key = (
            "instinkt_utility_pair"
            if pair_id == "trip_racio_utility"
            else "instinkt_protective_pair"
        )
        lines.extend(["Pair difference (mechanical):", ""])
        lines.extend(_markdown_json(summary["pair_analysis"][i_key]))
        lines.extend(_human_fields())
    lines.extend(
        [
            "## Scope declarations",
            "",
            "- Manual structured routing: yes.",
            "- Emocio image generation: no.",
            "- Image-native Emocio claim: no.",
            "- Raw-scene Instinkt claim: no.",
            "- Character replay: no.",
            "- Holdout: no.",
            "- Promotion evidence: no.",
            "- Global REI score: none.",
            "",
        ]
    )
    (output_root / "report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )


def finalize(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    seal, _ = verify_seal(repository_root)
    ledger_path = output_root / "call_ledger.json"
    ledger = _json(ledger_path)
    if ledger["state"] != "four_calls_complete":
        raise ValueError("Exactly four calls must complete before finalization")
    if ledger["actual"] != {
        "model_call_attempts": 4,
        "retries": 0,
        "fallbacks": 0,
        "emocio_executions": 4,
        "instinkt_executions": 4,
        "character_replay_rows": 0,
    }:
        raise ValueError("Actual execution accounting differs from the seal")
    outputs = {
        case_id: _json(output_root / "cases" / case_id / "native_outputs.json")
        for case_id in CASE_ORDER
    }
    failures = [
        value["racio"].get("failure")
        for value in outputs.values()
        if value["racio"].get("failure") is not None
    ]
    analysis = _pair_analysis(outputs)
    accepted = sum(value["racio"]["status"] == "accepted" for value in outputs.values())
    summary = {
        "schema_version": "triad-iso-e1-summary-v1",
        "phase": "TRIAD-ISO-E1",
        "pre_call_seal_sha256": seal["seal_sha256"],
        "candidate_sha256": seal["source_candidate"]["sha256"],
        "subset_sha256": seal["execution_subset"]["sha256"],
        "model": seal["model"],
        "model_digest": seal["model_digest"],
        "provider_revision": seal["provider_revision"],
        "calls": 4,
        "retries": 0,
        "fallbacks": 0,
        "racio": {"accepted": accepted, "rejected": 4 - accepted},
        "emocio_executions": 4,
        "instinkt_executions": 4,
        "native_mind_bundles": 0,
        "character_replay_rows": 0,
        "pair_analysis": analysis,
        "abstentions": {
            "R": sum(
                bool(value["racio"]["conclusion"]["abstains"])
                for value in outputs.values()
                if value["racio"]["conclusion"] is not None
            ),
            "E": sum(
                bool(value["emocio"]["conclusion"]["abstains"])
                for value in outputs.values()
            ),
            "I": sum(
                bool(value["instinkt"]["conclusion"]["abstains"])
                for value in outputs.values()
            ),
        },
        "failure_categories": dict(
            Counter(value["failure_code"] for value in failures)
        ),
        "failures": failures,
        "private_thinking_persisted": False,
        "image_generation_calls": 0,
        "gemma_emocio_shadow_calls": 0,
        "gemma_instinkt_shadow_calls": 0,
        "holdout": False,
        "promotion_evidence": False,
        "global_rei_score": None,
    }
    _write_json(output_root / "summary.json", summary)
    render_report(repository_root, summary, outputs)
    ledger["state"] = "complete"
    _write_json(ledger_path, ledger)
    return summary


def cold_verify(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    seal, prepared = verify_seal(repository_root)
    ledger = _json(output_root / "call_ledger.json")
    summary = _json(output_root / "summary.json")
    if ledger["state"] != "complete":
        raise ValueError("TRIAD-ISO-E1 ledger is not complete")
    if ledger["actual"]["model_call_attempts"] != 4:
        raise ValueError("TRIAD-ISO-E1 did not record exactly four model calls")
    if ledger["actual"]["retries"] or ledger["actual"]["fallbacks"]:
        raise ValueError("TRIAD-ISO-E1 retry/fallback accounting is nonzero")
    if ledger["actual"]["character_replay_rows"]:
        raise ValueError("TRIAD-ISO-E1 unexpectedly performed character replay")
    by_id = {item.case_id: item for item in prepared}
    for entry in ledger["entries"]:
        if entry["status"] != "complete":
            raise ValueError(f"Incomplete call ledger entry: {entry['case_id']}")
        case_root = output_root / "cases" / entry["case_id"]
        call_record = _json(case_root / "call_record.json")
        native = _json(case_root / "native_outputs.json")
        if call_record["racio"]["call_spec"] != _projection(
            by_id[entry["case_id"]].racio_call_spec
        ):
            raise ValueError(f"Racio call spec mismatch: {entry['case_id']}")
        if native["processor_execution_counts"] != {"R": 1, "E": 1, "I": 1}:
            raise ValueError(f"Processor count mismatch: {entry['case_id']}")
        if native["native_mind_bundle_created"] or native["character_replay_rows"]:
            raise ValueError(f"Forbidden downstream execution: {entry['case_id']}")
    for path in output_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".json", ".md"}:
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            if any(f'"{key}"' in lowered for key in PRIVATE_KEYS):
                raise ValueError(f"Private-thinking key persisted in {path}")
            if str(repository_root).lower() in lowered:
                raise ValueError(f"Absolute repository path persisted in {path}")
    if summary["pre_call_seal_sha256"] != seal["seal_sha256"]:
        raise ValueError("Summary seal reference differs")
    if summary["calls"] != 4 or summary["character_replay_rows"] != 0:
        raise ValueError("Summary execution accounting differs")
    if not (output_root / "report.md").is_file():
        raise ValueError("Human-readable report is missing")
    return {
        "status": "passed",
        "seal_sha256": seal["seal_sha256"],
        "candidate_sha256": seal["source_candidate"]["sha256"],
        "subset_sha256": seal["execution_subset"]["sha256"],
        "model_digest": seal["model_digest"],
        "calls": summary["calls"],
        "retries": summary["retries"],
        "fallbacks": summary["fallbacks"],
        "character_replay_rows": summary["character_replay_rows"],
        "report_sha256": _file_sha256(output_root / "report.md"),
    }


__all__ = [
    "CASE_ORDER",
    "CANDIDATE_RELATIVE_PATH",
    "EXPECTED_CANDIDATE_SHA256",
    "OUTPUT_RELATIVE_PATH",
    "cold_verify",
    "finalize",
    "initialize_execution",
    "pair_invariant_report",
    "prepare_cases",
    "run_next",
    "seal_e1",
    "verify_seal",
]
