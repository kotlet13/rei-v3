"""TRIAD-ISO-R1 offline adjudication and representation repair.

The module is deliberately research-only and model-free.  It never modifies
TRIAD-ISO-E1 evidence, never calls a provider, and never executes character
governance.  Its formal verifier rehydrates persisted JSON through Pydantic's
JSON validation mode so strict tuple and datetime fields preserve their JSON
boundary semantics without relaxing domain validators.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

from ..emocio.policy import choose_native_option
from ..ids import canonical_json_bytes, content_id
from ..instinkt.dynamics import simulate_option_rollout
from ..instinkt.packets import InstinktEffectSpec, bind_instinkt_effects
from ..instinkt.policy import protective_cost
from ..models.common import FrozenModel, NonEmptyId, Score01
from ..models.emocio import (
    EMOCIO_VALUATION_DIMENSIONS,
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioOptionValuation,
    EmocioVisualState,
    EmocioWorld,
    ValuationDimension,
)
from ..models.instinkt import (
    BODY_DIMENSIONS,
    BodyDelta,
    BodyState,
    InstinktInputPacket,
    InstinktNativeConclusion,
    InstinktOptionRollout,
    InstinktSimulationConfig,
    OptionBodyEffect,
)
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ensure_call_record_contract,
)
from ..models.racio import RacioInputPacket, RacioNativeConclusion, RacioWorld
from ..models.scene import SceneEvent
from ..providers.ollama import (
    OllamaRacioFailedOutputDiagnostic,
    OllamaRacioResponseEvidence,
)
from .triad_d1 import canonical_fingerprint
from .triad_iso_e1 import (
    CANDIDATE_RELATIVE_PATH,
    CASE_ORDER,
    CORE_EFFECT_RULES,
    EXPECTED_CANDIDATE_SHA256,
    OUTPUT_RELATIVE_PATH as E1_OUTPUT_RELATIVE_PATH,
    PRIVATE_KEYS,
)


R1_OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-e1r-2026-07-24"
)
ADJUDICATION_RELATIVE_PATH: Final = (
    E1_OUTPUT_RELATIVE_PATH / "offline_route_adjudication.md"
)
S2_OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-response-screen-v2-2026-07-23"
)
E1_SEAL_SHA256: Final = (
    "1360554ad44b64f1aa8cdeb4e92d3bf278b8d812d381f0685e4e4595ccf86080"
)
S2_SEAL_SHA256: Final = (
    "ce64ce5b8a8a98d03c0fe2795f30fe60fc29b7ec28d416e0425feb2ee41cd376"
)
EXPECTED_E1_FILE_COUNT: Final = 19
R1_PROVIDER_CALLS: Final = 0
R1_CHARACTER_REPLAY_ROWS: Final = 0

ModelT = TypeVar("ModelT", bound=BaseModel)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    )
    path.write_text(rendered + "\n", encoding="utf-8", newline="\n")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_json_projection(
    model_type: type[ModelT],
    value: Mapping[str, Any],
) -> ModelT:
    """Hydrate one persisted JSON object in Pydantic JSON mode.

    Strict Python-mode validation rejects JSON arrays for tuple fields and
    JSON strings for datetime fields.  JSON mode performs only the intended
    representation conversion; the model's strict field and domain validators
    still execute unchanged.
    """

    return model_type.model_validate_json(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    )


def _walk(value: Any, path: tuple[str, ...] = ()):
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def frozen_e1_inventory(repository_root: Path) -> Mapping[str, Any]:
    """Inventory only the nineteen files committed by E1, not R1 addenda."""

    root = repository_root / E1_OUTPUT_RELATIVE_PATH
    paths = tuple(
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "offline_route_adjudication.md"
    )
    records = [
        {
            "path": path.relative_to(repository_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        }
        for path in paths
    ]
    if len(records) != EXPECTED_E1_FILE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_E1_FILE_COUNT} frozen E1 files, found {len(records)}"
        )
    return {
        "file_count": len(records),
        "files": records,
        "inventory_sha256": _object_sha256(records),
    }


def seal_reconciliation(repository_root: Path) -> Mapping[str, Any]:
    e1_path = repository_root / E1_OUTPUT_RELATIVE_PATH / "pre_call_seal.json"
    s2_path = repository_root / S2_OUTPUT_RELATIVE_PATH / "pre_call_seal.json"
    e1 = _json(e1_path)
    s2 = _json(s2_path)
    if e1["seal_sha256"] != E1_SEAL_SHA256:
        raise ValueError("Committed E1 seal identity changed")
    if s2["seal_sha256"] != S2_SEAL_SHA256:
        raise ValueError("Committed S2 seal identity changed")
    return {
        "reported_value": S2_SEAL_SHA256,
        "reported_value_origin": {
            "phase": "TRIAD-S2",
            "artifact": s2_path.relative_to(repository_root).as_posix(),
            "field": "seal_sha256",
            "artifact_sha256": _file_sha256(s2_path),
        },
        "committed_e1_value": E1_SEAL_SHA256,
        "committed_e1_origin": {
            "phase": "TRIAD-ISO-E1",
            "artifact": e1_path.relative_to(repository_root).as_posix(),
            "field": "seal_sha256",
            "artifact_sha256": _file_sha256(e1_path),
        },
        "verdict": "operator_response_cross_phase_misattribution",
        "e1_artifact_or_calculation_defect": False,
    }


def _validate_input_projection(value: Mapping[str, Any]) -> Mapping[str, Any]:
    racio = value["racio"]
    emocio = value["emocio"]
    instinkt = value["instinkt"]
    r_scene = validate_json_projection(SceneEvent, racio["scene"])
    r_world = validate_json_projection(RacioWorld, racio["world"])
    r_packet = validate_json_projection(RacioInputPacket, racio["packet"])
    r_call = validate_json_projection(ProviderCallSpec, racio["call_spec"])
    r_packet.validate_against(r_scene)
    if r_packet.world != r_world:
        raise ValueError("Formal E1 Racio packet/world projection differs")

    e_scene = validate_json_projection(SceneEvent, emocio["scene"])
    e_world = validate_json_projection(EmocioWorld, emocio["world"])
    e_packet = validate_json_projection(EmocioInputPacket, emocio["packet"])
    e_call = validate_json_projection(ProviderCallSpec, emocio["call_spec"])
    e_packet.validate_against(e_scene)

    i_scene = validate_json_projection(SceneEvent, instinkt["scene"])
    body = validate_json_projection(BodyState, instinkt["body_state"])
    i_packet = validate_json_projection(InstinktInputPacket, instinkt["packet"])
    effects = tuple(
        validate_json_projection(OptionBodyEffect, item)
        for item in instinkt["option_effects"]
    )
    config = validate_json_projection(
        InstinktSimulationConfig, instinkt["simulation_config"]
    )
    i_call = validate_json_projection(ProviderCallSpec, instinkt["call_spec"])
    i_packet.validate_against(i_scene, body)
    for effect in effects:
        effect.validate_against(i_packet)
    return {
        "racio_scene": r_scene,
        "racio_packet": r_packet,
        "racio_call": r_call,
        "emocio_scene": e_scene,
        "emocio_packet": e_packet,
        "emocio_world": e_world,
        "emocio_call": e_call,
        "instinkt_scene": i_scene,
        "body": body,
        "instinkt_packet": i_packet,
        "effects": effects,
        "config": config,
        "instinkt_call": i_call,
    }


def formal_verify_e1(repository_root: Path) -> Mapping[str, Any]:
    """Cold-verify committed E1 JSON without provider discovery or writes."""

    before = frozen_e1_inventory(repository_root)
    root = repository_root / E1_OUTPUT_RELATIVE_PATH
    seal = _json(root / "pre_call_seal.json")
    seal_base = {key: value for key, value in seal.items() if key != "seal_sha256"}
    if canonical_fingerprint(seal_base) != seal["seal_sha256"]:
        raise ValueError("Formal E1 seal hash differs")
    if seal["seal_sha256"] != E1_SEAL_SHA256:
        raise ValueError("Formal E1 seal identity differs")
    for field in ("source_candidate", "execution_subset", "pair_invariant_report"):
        record = seal[field]
        if _file_sha256(repository_root / record["path"]) != record["sha256"]:
            raise ValueError(f"Formal E1 sealed file changed: {field}")
    expected = seal["expected_call_ledger"]
    if _file_sha256(repository_root / expected["path"]) != expected["sha256"]:
        raise ValueError("Formal E1 expected ledger changed")

    ledger = _json(root / "call_ledger.json")
    summary = _json(root / "summary.json")
    if ledger["state"] != "complete":
        raise ValueError("Formal E1 ledger is incomplete")
    if ledger["actual"] != {
        "model_call_attempts": 4,
        "retries": 0,
        "fallbacks": 0,
        "emocio_executions": 4,
        "instinkt_executions": 4,
        "character_replay_rows": 0,
    }:
        raise ValueError("Formal E1 call accounting differs")

    accepted = 0
    rejected = 0
    for case_id in CASE_ORDER:
        case_root = root / "cases" / case_id
        inputs_raw = _json(case_root / "inputs.json")
        calls = _json(case_root / "call_record.json")
        outputs = _json(case_root / "native_outputs.json")
        typed = _validate_input_projection(inputs_raw)

        r_record = validate_json_projection(
            ProviderCallRecord, calls["racio"]["call_record"]
        )
        ensure_call_record_contract(typed["racio_call"], r_record)
        if outputs["racio"]["status"] == "accepted":
            accepted += 1
            conclusion = validate_json_projection(
                RacioNativeConclusion, outputs["racio"]["conclusion"]
            )
            evidence = validate_json_projection(
                OllamaRacioResponseEvidence,
                calls["racio"]["result_evidence"],
            )
            conclusion.validate_against(typed["racio_packet"])
            if evidence.packet_id != typed["racio_packet"].packet_id:
                raise ValueError("Formal E1 Racio evidence cites another packet")
        else:
            rejected += 1
            diagnostic = validate_json_projection(
                OllamaRacioFailedOutputDiagnostic,
                calls["racio"]["failed_output_diagnostic"],
            )
            if diagnostic.final_json_sha256 != outputs["racio"]["failure"][
                "final_json_sha256"
            ]:
                raise ValueError("Formal E1 failed JSON hash differs")

        e_record = validate_json_projection(
            ProviderCallRecord, calls["emocio"]["call_record"]
        )
        ensure_call_record_contract(typed["emocio_call"], e_record)
        visual = validate_json_projection(
            EmocioVisualState, outputs["emocio"]["visual_state"]
        )
        e_conclusion = validate_json_projection(
            EmocioNativeConclusion, outputs["emocio"]["conclusion"]
        )
        visual.validate_against(typed["emocio_packet"], typed["emocio_scene"])
        e_conclusion.validate_against(typed["emocio_packet"], visual)

        i_record = validate_json_projection(
            ProviderCallRecord, calls["instinkt"]["call_record"]
        )
        ensure_call_record_contract(typed["instinkt_call"], i_record)
        rollouts = tuple(
            validate_json_projection(InstinktOptionRollout, item)
            for item in outputs["instinkt"]["rollouts"]
        )
        i_conclusion = validate_json_projection(
            InstinktNativeConclusion, outputs["instinkt"]["conclusion"]
        )
        i_conclusion.validate_against(
            typed["instinkt_packet"], typed["body"], rollouts
        )
        for path, _ in _walk((inputs_raw, calls, outputs)):
            if path and path[-1].casefold() in PRIVATE_KEYS:
                raise ValueError("Formal E1 evidence contains private thinking")

    if (accepted, rejected) != (
        summary["racio"]["accepted"],
        summary["racio"]["rejected"],
    ):
        raise ValueError("Formal E1 Racio accounting differs")
    if summary["character_replay_rows"] != 0:
        raise ValueError("Formal E1 contains character replay")
    after = frozen_e1_inventory(repository_root)
    if after != before:
        raise ValueError("Formal E1 verification mutated frozen bytes")
    return {
        "status": "passed",
        "validation_mode": "pydantic_json",
        "domain_validators_relaxed": False,
        "seal_sha256": seal["seal_sha256"],
        "accepted": accepted,
        "rejected": rejected,
        "frozen_inventory_sha256": before["inventory_sha256"],
        "frozen_file_count": before["file_count"],
        "byte_inventory_unchanged": True,
        "model_calls": 0,
        "character_replay_rows": 0,
    }


def adjudicate_fact_evidence_mismatch(
    packet: RacioInputPacket,
    failed_output: Mapping[str, Any],
) -> Mapping[str, Any]:
    facts_used = tuple(failed_output.get("facts_used", ()))
    citations = tuple(failed_output.get("evidence_ids_used", ()))
    evidence_to_fact = dict(zip(packet.evidence_ids, packet.explicit_facts, strict=True))
    cited = set(citations)
    used = set(facts_used)
    allowed = {
        evidence_id
        for evidence_id, fact in evidence_to_fact.items()
        if fact in used
    }
    unsupported = tuple(sorted(cited - allowed))
    uncited_facts = tuple(
        fact
        for fact in facts_used
        if fact in evidence_to_fact.values()
        and not any(
            evidence_id in cited
            for evidence_id, mapped in evidence_to_fact.items()
            if mapped == fact
        )
    )
    return {
        "failure_code": "fact_evidence_mismatch",
        "unsupported_evidence_ids": unsupported,
        "used_facts_without_required_citations": uncited_facts,
        "evidence_to_fact_mapping": evidence_to_fact,
        "exact_contract_preserved": True,
        "thinking_included": False,
    }


def material_rejection_adjudication(repository_root: Path) -> Mapping[str, Any]:
    case_root = (
        repository_root
        / E1_OUTPUT_RELATIVE_PATH
        / "cases/trip_racio_utility_material"
    )
    inputs = _json(case_root / "inputs.json")
    calls = _json(case_root / "call_record.json")
    packet = validate_json_projection(RacioInputPacket, inputs["racio"]["packet"])
    diagnostic = validate_json_projection(
        OllamaRacioFailedOutputDiagnostic,
        calls["racio"]["failed_output_diagnostic"],
    )
    failed_output = json.loads(diagnostic.canonical_json_projection)
    result = adjudicate_fact_evidence_mismatch(packet, failed_output)
    if result["unsupported_evidence_ids"] != ("utility_ev_rarity",):
        raise ValueError("Material rejection no longer has the adjudicated cause")
    return {
        "case_id": "trip_racio_utility_material",
        "original_status": "rejected",
        "original_failure_code": diagnostic.failure_code,
        "final_json_sha256": diagnostic.final_json_sha256,
        "adjudication": result,
        "original_failed_output_changed": False,
    }


def racio_commensurability_preflight(
    packet: RacioInputPacket,
) -> Mapping[str, Any]:
    text = " ".join(
        (
            *packet.explicit_facts,
            *(item.consequence for item in packet.explicit_consequences),
        )
    )
    percentage_mentions = tuple(
        sorted(set(re.findall(r"\b\d+(?:\.\d+)?\s*percent\b", text, re.I)))
    )
    eur_mentions = tuple(
        sorted(
            set(
                re.findall(
                    r"(?:EUR\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*EUR)",
                    text,
                    re.I,
                )
            )
        )
    )
    budget_base_facts = tuple(
        fact
        for fact in packet.explicit_facts
        if re.search(
            r"(?:budget|reserve).{0,40}(?:is|totals|equals|between).{0,20}EUR",
            fact,
            re.I,
        )
    )
    absolute_spend_present = any(
        "trip costs eur" in fact.casefold() for fact in packet.explicit_facts
    )
    percentage_vs_absolute_benefit = bool(percentage_mentions and eur_mentions)
    budget_base_status = (
        "explicit_or_bounded" if budget_base_facts else "under_specified"
    )
    return {
        "percentage_mentions": percentage_mentions,
        "absolute_eur_mentions": eur_mentions,
        "absolute_spend_present": absolute_spend_present,
        "budget_base_facts": budget_base_facts,
        "percentage_vs_absolute_benefit": percentage_vs_absolute_benefit,
        "budget_base_status": budget_base_status,
        "comparison_status": (
            "partially_commensurable"
            if absolute_spend_present and budget_base_status == "under_specified"
            else "under_specified"
            if percentage_vs_absolute_benefit
            and budget_base_status == "under_specified"
            else "commensurable"
        ),
        "required_route_constraints": {
            "uncertainty_must_be_explicit": (
                percentage_vs_absolute_benefit
                and budget_base_status == "under_specified"
            ),
            "confidence_cap": (
                0.65
                if percentage_vs_absolute_benefit
                and budget_base_status == "under_specified"
                else 1.0
            ),
            "net_benefit_claim_requires_common_unit": True,
            "hardcoded_abstention": False,
        },
    }


SelfPositionRelation = Literal[
    "centered_at_decision",
    "centered_in_result_scene",
]
AttractionStrength = Literal["absent", "present", "stronger"]
MovementMagnitude = Literal["none", "bounded", "large_new"]
Immediacy = Literal["none", "bounded", "immediate"]
ObstacleState = Literal["persists", "transformed", "removed"]
DesiredRelation = Literal["not_aligned", "partial", "aligned"]
BrokenRelation = Literal["remains", "partial_escape", "escaped"]


class EmocioSemanticOptionRoute(FrozenModel):
    option_id: NonEmptyId
    self_position_relation: SelfPositionRelation
    target_scene_identity: NonEmptyId
    attraction_target: NonEmptyId | None = None
    attraction_strength: AttractionStrength
    movement_destination: NonEmptyId | None = None
    movement_magnitude: MovementMagnitude
    immediacy: Immediacy
    obstacle_state: ObstacleState
    desired_state_relation: DesiredRelation
    broken_state_relation: BrokenRelation
    evidence_ids: tuple[NonEmptyId, ...] = Field(min_length=1)


class EmocioSemanticRouteSource(FrozenModel):
    self_identity: Literal["self"]
    desired_target: NonEmptyId
    broken_target: NonEmptyId
    companion_visible: bool
    companion_adds_grounded_enjoyment: bool
    options: tuple[EmocioSemanticOptionRoute, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_options(self) -> "EmocioSemanticRouteSource":
        ids = tuple(item.option_id for item in self.options)
        if len(ids) != len(set(ids)):
            raise ValueError("Semantic Emocio option IDs must be unique")
        return self


def _semantic_option(
    option_id: str,
    evidence_ids: Sequence[str],
    role: Literal["distant", "local", "home"],
) -> Mapping[str, Any]:
    if role == "distant":
        values = {
            "self_position_relation": "centered_in_result_scene",
            "target_scene_identity": "distant_coast",
            "attraction_target": "distant_coast",
            "attraction_strength": "stronger",
            "movement_destination": "distant_coast",
            "movement_magnitude": "large_new",
            "immediacy": "immediate",
            "obstacle_state": "removed",
            "desired_state_relation": "aligned",
            "broken_state_relation": "escaped",
        }
    elif role == "local":
        values = {
            "self_position_relation": "centered_in_result_scene",
            "target_scene_identity": "local_coast",
            "attraction_target": "local_coast",
            "attraction_strength": "present",
            "movement_destination": "local_coast",
            "movement_magnitude": "bounded",
            "immediacy": "bounded",
            "obstacle_state": "transformed",
            "desired_state_relation": "partial",
            "broken_state_relation": "partial_escape",
        }
    else:
        values = {
            "self_position_relation": "centered_at_decision",
            "target_scene_identity": "home",
            "attraction_target": None,
            "attraction_strength": "absent",
            "movement_destination": None,
            "movement_magnitude": "none",
            "immediacy": "none",
            "obstacle_state": "persists",
            "desired_state_relation": "not_aligned",
            "broken_state_relation": "remains",
        }
    return {
        "option_id": option_id,
        **values,
        "evidence_ids": tuple(sorted(evidence_ids)),
    }


def semantic_route_source(case: Mapping[str, Any]) -> Mapping[str, Any]:
    route = case["route_packets"]["emocio"]
    options = []
    for item in route["option_visible_changes"]:
        option_id = item["option_id"]
        role: Literal["distant", "local", "home"]
        if option_id.endswith("_book") or option_id == "trip_book":
            role = "distant"
        elif option_id.endswith("_local") or option_id == "trip_local":
            role = "local"
        else:
            role = "home"
        options.append(_semantic_option(option_id, item["evidence_ids"], role))
    return {
        "self_identity": "self",
        "desired_target": "distant_coast_active_movement",
        "broken_target": "closed_routes_no_travel_movement",
        "companion_visible": "companion" in route["current_scene"].casefold(),
        "companion_adds_grounded_enjoyment": False,
        "options": options,
    }


def compile_semantic_emocio_representation(
    source: Mapping[str, Any],
) -> EmocioSemanticRouteSource:
    """Compile only typed relations; prose annotations are non-authoritative."""

    projection = {
        key: source[key]
        for key in (
            "self_identity",
            "desired_target",
            "broken_target",
            "companion_visible",
            "companion_adds_grounded_enjoyment",
            "options",
        )
    }
    typed = validate_json_projection(EmocioSemanticRouteSource, projection)
    return EmocioSemanticRouteSource(
        **{
            **typed.model_dump(mode="python"),
            "options": tuple(sorted(typed.options, key=lambda item: item.option_id)),
        }
    )


def _semantic_score(
    route: EmocioSemanticOptionRoute,
) -> Mapping[str, float]:
    relation_score = {"not_aligned": 0.0, "partial": 0.55, "aligned": 1.0}
    broken_score = {"remains": 0.0, "partial_escape": 0.55, "escaped": 1.0}
    attraction_score = {"absent": 0.0, "present": 0.6, "stronger": 1.0}
    movement_score = {"none": 0.0, "bounded": 0.5, "large_new": 1.0}
    immediacy_score = {"none": 0.0, "bounded": 0.5, "immediate": 1.0}
    obstacle_score = {"persists": 0.0, "transformed": 0.5, "removed": 1.0}
    desired = relation_score[route.desired_state_relation]
    broken = broken_score[route.broken_state_relation]
    movement = movement_score[route.movement_magnitude]
    immediacy = immediacy_score[route.immediacy]
    obstacle = obstacle_score[route.obstacle_state]
    return {
        "desired_scene_match": desired,
        "distance_from_broken_scene": broken,
        "self_visibility": (
            1.0
            if route.self_position_relation == "centered_in_result_scene"
            else 0.75
        ),
        "belonging": 0.0,
        "attention": 0.0,
        "attraction": attraction_score[route.attraction_strength],
        "novelty": movement,
        "movement": movement,
        "status": 0.0,
        "competitive_success": obstacle,
        "attack_or_breakthrough_affordance": round(
            (movement + immediacy + obstacle) / 3.0, 6
        ),
    }


def semantic_emocio_valuations(
    source: EmocioSemanticRouteSource,
) -> tuple[EmocioOptionValuation, ...]:
    valuations = []
    for route in source.options:
        scores = _semantic_score(route)
        valuations.append(
            EmocioOptionValuation(
                option_id=route.option_id,
                rollout_scene_id=content_id(
                    "triad_iso_r1_semantic_route",
                    route.model_dump(mode="json"),
                ),
                dimensions=tuple(
                    ValuationDimension(name=name, score=scores[name])
                    for name in EMOCIO_VALUATION_DIMENSIONS
                ),
            )
        )
    return tuple(sorted(valuations, key=lambda item: item.option_id))


def _valuation_projection(
    valuations: Sequence[EmocioOptionValuation],
) -> Mapping[str, Mapping[str, float]]:
    return {
        item.option_id: {
            dimension.name: dimension.score for dimension in item.dimensions
        }
        for item in valuations
    }


def _candidate_case_index(candidate: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        case["case_id"]: case
        for pair in candidate["pairs"]
        for case in pair["variants"]
    }


def replay_emocio(repository_root: Path) -> Mapping[str, Any]:
    candidate = _json(repository_root / CANDIDATE_RELATIVE_PATH)
    index = _candidate_case_index(candidate)
    e1_root = repository_root / E1_OUTPUT_RELATIVE_PATH
    cases = []
    for case_id in CASE_ORDER:
        old = _json(e1_root / "cases" / case_id / "native_outputs.json")["emocio"]
        semantic_source = semantic_route_source(index[case_id])
        representation = compile_semantic_emocio_representation(semantic_source)
        valuations = semantic_emocio_valuations(representation)
        policy = choose_native_option(valuations)
        old_ties = tuple(old["tied_option_ids"])
        new_ties = tuple(policy.tied_option_ids)
        cases.append(
            {
                "case_id": case_id,
                "source_case_sha256": _object_sha256(index[case_id]),
                "old_representation": old["counterfactual_lineage"],
                "new_semantic_representation": representation.model_dump(mode="json"),
                "old_valuation_vectors": old["valuation_vectors"],
                "new_valuation_vectors": _valuation_projection(valuations),
                "old_aggregate_scores": old["aggregate_scores"],
                "new_aggregate_scores": {
                    item.option_id: item.score
                    for item in policy.aggregate_scores
                },
                "old_selected_option_id": old["selected_option_id"],
                "new_selected_option_id": (
                    policy.selected.option_id if policy.selected is not None else None
                ),
                "old_tied_option_ids": old_ties,
                "new_tied_option_ids": new_ties,
                "old_abstention_cause": (
                    "representation_collapse"
                    if old_ties and not new_ties
                    else "true_equal_aggregate"
                    if old_ties
                    else "not_applicable"
                ),
                "model_calls": 0,
                "native_processor_executions": 0,
            }
        )
    return {
        "schema_version": "triad-iso-r1-emocio-replay-v1",
        "mode": "research_only_semantic_projection",
        "active_emocio_runtime_changed": False,
        "image_generation_calls": 0,
        "cases": cases,
    }


CORRECTED_EFFECT_RULES: Final[Mapping[str, Mapping[str, float]]] = {
    **{
        key: value
        for key, value in CORE_EFFECT_RULES.items()
        if key != "avoids_distant_exposure"
    },
    "avoids_unfamiliar_uncertain_exposure": CORE_EFFECT_RULES[
        "avoids_distant_exposure"
    ],
    "known_distant_movement": {},
}


def _corrected_categories(
    case_id: str,
    categories: Sequence[str],
) -> tuple[str, ...]:
    result = []
    for category in categories:
        if category != "avoids_distant_exposure":
            result.append(category)
        elif case_id == "trip_protective_context_exposed":
            result.append("avoids_unfamiliar_uncertain_exposure")
        elif case_id == "trip_protective_context_supported":
            continue
        else:
            result.append(category)
    return tuple(sorted(set(result)))


def _corrected_target(case_id: str) -> str:
    if case_id.startswith("trip_racio_utility"):
        return (
            "Self's physical integrity, trusted attachment context, return "
            "ability, and discretionary budget."
        )
    return (
        "Self's physical integrity, ability to return, trusted attachment "
        "context, and discretionary budget."
    )


def _effect_deltas(categories: Sequence[str]) -> Mapping[str, float]:
    combined: dict[str, float] = {}
    for category in categories:
        for dimension, delta in CORRECTED_EFFECT_RULES[category].items():
            combined[dimension] = combined.get(dimension, 0.0) + delta
    return {
        dimension: round(max(-0.25, min(0.25, combined[dimension])), 6)
        for dimension in BODY_DIMENSIONS
        if dimension in combined
    }


def _action(deltas: Mapping[str, float]) -> str:
    if deltas.get("physical_integrity", 0.0) < 0.0:
        return "seek_safety"
    if deltas.get("resource_security", 0.0) < 0.0:
        return "conserve"
    if deltas.get("boundary_integrity", 0.0) < 0.0:
        return "set_boundary"
    if deltas.get("escape_availability", 0.0) < 0.0:
        return "withdraw"
    return "maintain"


def _outcome(deltas: Mapping[str, float], dimension: str) -> str:
    value = deltas.get(dimension)
    return (
        f"not_changed_by_grounded_consequence:{dimension}"
        if value is None
        else f"grounded_consequence_delta:{dimension}:{value:+.6f}"
    )


def replay_instinkt_sensitivity(repository_root: Path) -> Mapping[str, Any]:
    root = repository_root / E1_OUTPUT_RELATIVE_PATH
    cases = []
    for case_id in CASE_ORDER:
        inputs = _json(root / "cases" / case_id / "inputs.json")["instinkt"]
        outputs = _json(root / "cases" / case_id / "native_outputs.json")["instinkt"]
        packet = validate_json_projection(InstinktInputPacket, inputs["packet"])
        body = validate_json_projection(BodyState, inputs["body_state"])
        config = validate_json_projection(
            InstinktSimulationConfig, inputs["simulation_config"]
        )
        original_effects = {
            item["option_id"]: item for item in inputs["option_effects"]
        }
        original_lineage = {
            item["option_id"]: item for item in inputs["effect_lineage"]
        }
        specs = []
        corrected_lineage = []
        for option_id in sorted(original_effects):
            original = original_effects[option_id]
            old_categories = tuple(original_lineage[option_id]["effect_categories"])
            categories = _corrected_categories(case_id, old_categories)
            deltas = _effect_deltas(categories)
            specs.append(
                InstinktEffectSpec(
                    option_id=option_id,
                    body_deltas=tuple(
                        BodyDelta(dimension=dimension, delta=delta)
                        for dimension, delta in deltas.items()
                    ),
                    base_predicted_loss=original["base_predicted_loss"],
                    base_recoverability=original["base_recoverability"],
                    dominant_alarm="grounded_core_route:" + "+".join(categories),
                    protected_targets=(_corrected_target(case_id),),
                    boundary_outcome=_outcome(deltas, "boundary_integrity"),
                    trust_outcome=_outcome(deltas, "trust"),
                    attachment_outcome=_outcome(
                        deltas, "attachment_security"
                    ),
                    escape_outcome=_outcome(deltas, "escape_availability"),
                    action_tendency=_action(deltas),
                    minimum_safety_condition=original[
                        "minimum_safety_condition"
                    ],
                    association_cue_tokens=categories,
                    triggering_evidence_ids=tuple(
                        original["triggering_evidence_ids"]
                    ),
                )
            )
            corrected_lineage.append(
                {
                    "option_id": option_id,
                    "frozen_consequence_fact": original_lineage[option_id][
                        "consequence_fact"
                    ],
                    "source_evidence_ids": original_lineage[option_id][
                        "source_evidence_ids"
                    ],
                    "original_effect_categories": old_categories,
                    "corrected_effect_categories": categories,
                    "corrected_body_deltas": deltas,
                    "numeric_delta_tuning_for_option_flip": False,
                }
            )
        effects = bind_instinkt_effects(packet, tuple(specs))
        rollouts = tuple(
            simulate_option_rollout(
                packet=packet,
                source_body_state=body,
                effect=effect,
                config=config,
            )
            for effect in effects
        )
        costs = {
            rollout.option_id: protective_cost(rollout, config)
            for rollout in rollouts
        }
        minimum = min(costs.values())
        tied = tuple(
            sorted(
                option_id
                for option_id, value in costs.items()
                if abs(value - minimum) <= config.tie_epsilon
            )
        )
        selected = tied[0] if len(tied) == 1 else None
        cases.append(
            {
                "case_id": case_id,
                "original_protected_target": outputs["route_packet"][
                    "protected_target"
                ],
                "corrected_protected_target": _corrected_target(case_id),
                "frozen_consequence_facts_changed": False,
                "original_effect_paths": [
                    {
                        "option_id": item["option_id"],
                        "effect_categories": item["effect_categories"],
                        "protective_cost": item["protective_cost"],
                    }
                    for item in outputs["option_paths"]
                ],
                "corrected_effect_paths": corrected_lineage,
                "corrected_protective_costs": costs,
                "original_selected_option_id": outputs["selected_option_id"],
                "corrected_selected_option_id": selected,
                "corrected_tied_option_ids": tied if selected is None else (),
                "selection_changed": selected != outputs["selected_option_id"],
                "option_flip_targeted": False,
                "instinkt_native_processor_executions": 0,
                "model_calls": 0,
            }
        )
    return {
        "schema_version": "triad-iso-r1-instinkt-sensitivity-v1",
        "mode": "research_only_effect_sensitivity_projection",
        "active_instinkt_runtime_changed": False,
        "cases": cases,
    }


def _add_budget_base(case: dict[str, Any]) -> None:
    sl = {
        "evidence_id": "utility_ev_budget_base",
        "text": "Prosti proračun ob času odločitve znaša 4800 EUR.",
    }
    en = {
        "evidence_id": "utility_ev_budget_base",
        "text": "The discretionary budget at decision time is EUR 4800.",
    }
    if not any(
        item["evidence_id"] == sl["evidence_id"]
        for item in case["canonical_sl"]["facts"]
    ):
        case["canonical_sl"]["facts"].append(sl)
        case["operational_en"]["facts"].append(en)
        case["route_packets"]["racio"]["facts"].append(sl["evidence_id"])


def corrected_candidate(repository_root: Path) -> Mapping[str, Any]:
    original = _json(repository_root / CANDIDATE_RELATIVE_PATH)
    index = _candidate_case_index(original)
    cases = []
    for case_id in CASE_ORDER:
        case = copy.deepcopy(index[case_id])
        if case_id.startswith("trip_racio_utility"):
            _add_budget_base(case)
        semantic = semantic_route_source(case)
        case["route_packets"]["emocio"][
            "semantic_route_representation"
        ] = semantic
        instinkt = case["route_packets"]["instinkt"]
        instinkt["protected_target"] = _corrected_target(case_id)
        instinkt["protected_target_semantics"] = {
            "budget_kind": "discretionary_budget",
            "necessary_cash_reserve_claim": False,
        }
        if case_id == "trip_protective_context_supported":
            instinkt["distance_semantics"] = {
                "known_distant_movement": True,
                "unfamiliar_or_uncertain_danger": False,
                "verified_distance_automatically_adverse": False,
            }
        elif case_id == "trip_protective_context_exposed":
            instinkt["distance_semantics"] = {
                "known_distant_movement": True,
                "unfamiliar_or_uncertain_danger": True,
                "verified_distance_automatically_adverse": False,
            }
        cases.append(case)
    candidate = {
        "schema_version": "triad-iso-r1-corrected-candidate-v1",
        "candidate_id": "triad-route-isolation-e1r-candidate-2026-07-24",
        "status": "unsealed_candidate",
        "execution_authorized": False,
        "model_calls": 0,
        "character_replay": 0,
        "source_candidate": {
            "path": CANDIDATE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_CANDIDATE_SHA256,
        },
        "case_order": CASE_ORDER,
        "cases": cases,
        "declarations": {
            "expected_option_present": False,
            "character_present": False,
            "governance_present": False,
            "non_acceptance_intensification": False,
            "pre_call_execution_seal": False,
        },
    }
    forbidden = {
        "expected_option",
        "expected_option_id",
        "expected_action",
        "leading_mind",
        "gold_route",
        "character",
        "character_profile",
        "governance",
    }
    for path, _ in _walk(candidate):
        if path and path[-1].casefold() in forbidden:
            raise ValueError(
                f"Corrected candidate contains forbidden field: {'/'.join(path)}"
            )
    return candidate


def _render_adjudication(
    *,
    reconciliation: Mapping[str, Any],
    formal: Mapping[str, Any],
    rejection: Mapping[str, Any],
    commensurability: Mapping[str, Any],
    emocio: Mapping[str, Any],
    instinkt: Mapping[str, Any],
    candidate_sha256: str,
) -> str:
    lines = [
        "# TRIAD-ISO-R1 offline route adjudication",
        "",
        "TRIAD-ISO-E1 remains a frozen historical mixed result. This addendum "
        "contains no model calls, native processor reruns, character replay, "
        "promotion claim, or global REI score.",
        "",
        "## Seal reconciliation",
        "",
        f"- `ce64…` is the TRIAD-S2 seal stored in "
        f"`{reconciliation['reported_value_origin']['artifact']}`.",
        f"- The committed TRIAD-ISO-E1 seal is "
        f"`{reconciliation['committed_e1_value']}`.",
        "- Verdict: operator-response cross-phase misattribution. No E1 seal "
        "artifact or seal calculation is defective.",
        "",
        "## Formal JSON-mode verification",
        "",
        f"- Status: `{formal['status']}`.",
        "- Pydantic validation mode: JSON.",
        "- Domain validators relaxed: no.",
        f"- Frozen files: {formal['frozen_file_count']}; byte inventory unchanged: "
        f"{str(formal['byte_inventory_unchanged']).lower()}.",
        f"- Frozen inventory SHA-256: `{formal['frozen_inventory_sha256']}`.",
        "",
        "## Racio material rejection",
        "",
        "- Exact failure: `fact_evidence_mismatch`.",
        "- `evidence_ids_used` contains `utility_ev_rarity`, while `facts_used` "
        "does not contain the corresponding rarity fact. The citation therefore "
        "falls outside the allowed citation union for used facts.",
        f"- Unsupported evidence IDs: "
        f"`{json.dumps(rejection['adjudication']['unsupported_evidence_ids'])}`.",
        f"- Used facts lacking required citations: "
        f"`{json.dumps(rejection['adjudication']['used_facts_without_required_citations'])}`.",
        "- The exact fact/evidence contract remains unchanged; the original output "
        "remains rejected. The prospective diagnostic contains no thinking.",
        "",
        "## Racio commensurability",
        "",
        f"- Current material packet: `{commensurability['comparison_status']}`.",
        f"- Budget base: `{commensurability['budget_base_status']}`.",
        "- EUR 1200 trip spend and EUR 900 bounded benefit share a currency unit, "
        "but reserve impact remains under-specified without an explicit or bounded "
        "absolute budget base.",
        "- Under-specification requires explicit uncertainty and a bounded confidence; "
        "it does not hardcode abstention.",
        "- A net-benefit claim is forbidden whenever compared quantities lack a "
        "common unit.",
        "",
        "## Emocio route diagnosis",
        "",
        "- E1 produced 4/4 Emocio abstentions.",
        "- Utility book/local and protective book/local were exact aggregate ties.",
        "- Distant and local attraction both collapsed to 1.0 although the local "
        "route was explicitly smaller.",
        "- Movement remained 0.0 despite structured movement fields.",
        "- Desired-scene match remained 0.0.",
        "- Companion presence caused novelty/breakthrough aggregate drift despite "
        "the explicit `no extra enjoyment` boundary.",
        "- Isolation stability and semantic fidelity are distinct: utility identity "
        "is an isolation PASS; Emocio cognition is not yet a semantic PASS.",
        "",
        "## Research-only Emocio representation replay",
        "",
        "| Case | Old ties | New ties | Old option | New option | Old abstention diagnosis |",
        "|---|---|---|---|---|---|",
    ]
    for item in emocio["cases"]:
        lines.append(
            f"| `{item['case_id']}` | "
            f"`{','.join(item['old_tied_option_ids'])}` | "
            f"`{','.join(item['new_tied_option_ids'])}` | "
            f"`{item['old_selected_option_id']}` | "
            f"`{item['new_selected_option_id']}` | "
            f"`{item['old_abstention_cause']}` |"
        )
    lines.extend(
        [
            "",
            "The corrected projection uses stable typed relations for self position, "
            "scene target, ordinal attraction, movement, immediacy, obstacle state, "
            "and desired/broken relations. It contains no expected winner or "
            "option-specific tuning. An option change is neither success nor failure "
            "by itself; source-grounded route capacity is the result.",
            "",
            "## Instinkt route adjudication and sensitivity",
            "",
            "- Accepted E1 isolation result: exposed → supported changed the route; "
            "book protective cost fell from 0.658125 to 0.554750. An option flip was "
            "not required.",
            "- `discretionary budget` does not license `necessary cash reserve`.",
            "- Known verified distance is distinct from unfamiliar/uncertain danger.",
            "- Non-refundable resource exposure remains independently represented.",
            "",
            "| Case | Original option | Corrected option | Selection changed |",
            "|---|---|---|---|",
        ]
    )
    for item in instinkt["cases"]:
        lines.append(
            f"| `{item['case_id']}` | `{item['original_selected_option_id']}` | "
            f"`{item['corrected_selected_option_id']}` | "
            f"{str(item['selection_changed']).lower()} |"
        )
    lines.extend(
        [
            "",
            "The sensitivity replay retained every frozen consequence fact, removed "
            "only unsupported semantic upgrades, and did not tune numeric deltas for "
            "an option flip.",
            "",
            "## Corrected unsealed candidate",
            "",
            f"- SHA-256: `{candidate_sha256}`.",
            "- Utility cases add an explicit EUR 4800 discretionary-budget base.",
            "- Emocio carries typed semantic route relations.",
            "- Instinkt retains the discretionary-budget meaning and does not treat "
            "verified distance as automatic danger.",
            "- Status: unsealed; execution is not authorized.",
            "",
            "## Stop state",
            "",
            "- Model calls: 0.",
            "- Character replay rows: 0.",
            "- Remaining six route-isolation cases: not executed.",
            "- G4: not started.",
            "- PR/merge: not performed by this phase.",
            "",
        ]
    )
    return "\n".join(lines).rstrip()


def prepare_r1(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / R1_OUTPUT_RELATIVE_PATH
    adjudication_path = repository_root / ADJUDICATION_RELATIVE_PATH
    if output_root.exists() or adjudication_path.exists():
        raise ValueError("TRIAD-ISO-R1 outputs are create-only")
    before = frozen_e1_inventory(repository_root)
    reconciliation = seal_reconciliation(repository_root)
    formal = formal_verify_e1(repository_root)
    rejection = material_rejection_adjudication(repository_root)

    material_inputs = _json(
        repository_root
        / E1_OUTPUT_RELATIVE_PATH
        / "cases/trip_racio_utility_material/inputs.json"
    )
    material_packet = validate_json_projection(
        RacioInputPacket, material_inputs["racio"]["packet"]
    )
    commensurability = racio_commensurability_preflight(material_packet)
    adjudication = {
        "schema_version": "triad-iso-r1-adjudication-v1",
        "seal_reconciliation": reconciliation,
        "formal_verification": formal,
        "material_rejection": rejection,
        "racio_commensurability": commensurability,
    }
    emocio = replay_emocio(repository_root)
    instinkt = replay_instinkt_sensitivity(repository_root)
    candidate = corrected_candidate(repository_root)

    _write_json(output_root / "adjudication.json", adjudication)
    _write_json(output_root / "emocio_replay.json", emocio)
    _write_json(output_root / "instinkt_sensitivity.json", instinkt)
    _write_json(output_root / "corrected_candidate.json", candidate)
    candidate_sha = _file_sha256(output_root / "corrected_candidate.json")
    report = _render_adjudication(
        reconciliation=reconciliation,
        formal=formal,
        rejection=rejection,
        commensurability=commensurability,
        emocio=emocio,
        instinkt=instinkt,
        candidate_sha256=candidate_sha,
    )
    adjudication_path.write_text(report + "\n", encoding="utf-8", newline="\n")

    outputs = [
        output_root / "adjudication.json",
        output_root / "emocio_replay.json",
        output_root / "instinkt_sensitivity.json",
        output_root / "corrected_candidate.json",
        adjudication_path,
    ]
    manifest_base = {
        "schema_version": "triad-iso-r1-manifest-v1",
        "phase": "TRIAD-ISO-R1",
        "status": "offline_adjudication_complete",
        "base_commit": "187a06a62369bed8aa7b2fd680ae9b3b99602a1b",
        "model_calls": 0,
        "character_replay_rows": 0,
        "native_processor_executions": {"R": 0, "E": 0, "I": 0},
        "image_generation_calls": 0,
        "source_e1": {
            "seal_sha256": E1_SEAL_SHA256,
            "frozen_inventory_sha256": before["inventory_sha256"],
            "frozen_file_count": before["file_count"],
            "bytes_changed": False,
        },
        "outputs": [
            {
                "path": path.relative_to(repository_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
            for path in outputs
        ],
        "corrected_candidate": {
            "status": "unsealed_candidate",
            "execution_authorized": False,
            "sha256": candidate_sha,
        },
        "thinking_persisted": False,
        "local_absolute_paths_persisted": False,
    }
    manifest = {
        **manifest_base,
        "manifest_sha256": _object_sha256(manifest_base),
    }
    _write_json(output_root / "manifest.json", manifest)
    after = frozen_e1_inventory(repository_root)
    if after != before:
        raise ValueError("TRIAD-ISO-R1 mutated frozen E1 bytes")
    return manifest


def cold_verify_r1(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / R1_OUTPUT_RELATIVE_PATH
    manifest = _json(output_root / "manifest.json")
    base = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if _object_sha256(base) != manifest["manifest_sha256"]:
        raise ValueError("TRIAD-ISO-R1 manifest hash differs")
    formal = formal_verify_e1(repository_root)
    if formal["frozen_inventory_sha256"] != manifest["source_e1"][
        "frozen_inventory_sha256"
    ]:
        raise ValueError("TRIAD-ISO-R1 source E1 inventory changed")
    for record in manifest["outputs"]:
        path = repository_root / record["path"]
        if (
            not path.is_file()
            or path.stat().st_size != record["bytes"]
            or _file_sha256(path) != record["sha256"]
        ):
            raise ValueError(f"TRIAD-ISO-R1 output changed: {record['path']}")
    candidate = _json(output_root / "corrected_candidate.json")
    if candidate["status"] != "unsealed_candidate" or candidate[
        "execution_authorized"
    ]:
        raise ValueError("TRIAD-ISO-R1 candidate is not safely unsealed")
    if candidate["model_calls"] != 0 or candidate["character_replay"] != 0:
        raise ValueError("TRIAD-ISO-R1 candidate contains execution")
    for path in output_root.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".md"}:
            text = path.read_text(encoding="utf-8")
            lowered = text.casefold()
            if any(f'"{key}"' in lowered for key in PRIVATE_KEYS):
                raise ValueError(f"Private thinking key persisted in {path}")
            if str(repository_root).casefold() in lowered:
                raise ValueError(f"Local absolute path persisted in {path}")
    return {
        "status": "passed",
        "manifest_sha256": manifest["manifest_sha256"],
        "original_e1_formal_verification": formal["status"],
        "original_e1_bytes_unchanged": True,
        "model_calls": 0,
        "character_replay_rows": 0,
        "thinking_persisted": False,
        "local_absolute_paths_persisted": False,
        "corrected_candidate_sha256": manifest["corrected_candidate"]["sha256"],
    }


__all__ = [
    "ADJUDICATION_RELATIVE_PATH",
    "EmocioSemanticOptionRoute",
    "EmocioSemanticRouteSource",
    "R1_OUTPUT_RELATIVE_PATH",
    "adjudicate_fact_evidence_mismatch",
    "cold_verify_r1",
    "compile_semantic_emocio_representation",
    "corrected_candidate",
    "formal_verify_e1",
    "frozen_e1_inventory",
    "material_rejection_adjudication",
    "prepare_r1",
    "racio_commensurability_preflight",
    "replay_emocio",
    "replay_instinkt_sensitivity",
    "seal_reconciliation",
    "semantic_emocio_valuations",
    "semantic_route_source",
    "validate_json_projection",
]
