"""Sealed TRIAD-S2 distinguishable-route development execution.

The module is research-only. It freezes four English Racio call contracts,
manually routed structured Emocio counterfactuals, and grounded Instinkt
option consequences. Character replay consumes only completed frozen bundles.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel

from ..emocio.packets import build_emocio_packet
from ..emocio.policy import EmocioPolicyDecision, choose_native_option
from ..emocio.processor import _native_conclusion
from ..emocio.scene_graph import CompiledEmocioScenes, compile_emocio_scenes
from ..emocio.valuation import build_emocio_visual_state
from ..governance.resolver import assess_agreement_pattern
from ..ids import canonical_json_bytes, content_id, sha256_hex, utc_now
from ..instinkt.packets import (
    InstinktEffectSpec,
    bind_instinkt_effects,
    build_instinkt_packet,
)
from ..models.emocio import (
    AttentionWeight,
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioVisualState,
    EmocioWorld,
    VisualSceneSpec,
)
from ..models.instinkt import (
    BODY_DIMENSIONS,
    BodyDelta,
    BodyState,
    InstinktInputPacket,
    InstinktSimulationConfig,
    OptionBodyEffect,
)
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderIdentity,
    ensure_call_record_contract,
)
from ..models.racio import RacioConsequence, RacioInputPacket, RacioWorld
from ..models.run import NativeMindBundle
from ..models.scene import DecisionOption, EvidenceItem, SceneEvent
from ..providers.deterministic import (
    DeterministicInstinktNativeProvider,
    InstinktNativeExecution,
    build_native_call_spec,
    emocio_world_input_id,
)
from ..providers.native import SystemExecutionClock
from ..providers.ollama import (
    DEFAULT_OLLAMA_NUM_PREDICT,
    OllamaApiClient,
    OllamaRacioSettings,
    OllamaStructuredOutputValidationError,
)
from ..providers.ollama_en import (
    OLLAMA_EN_TRIAD_PROVIDER_REVISION,
    OllamaRacioNativeEnTriadProvider,
)
from ..racio.packets import build_racio_packet
from ..racio.text_reasoner_adapter import RACIO_STRUCTURED_INSTRUCTION_EN
from ..triad_screen import replay_profiles
from .triad_d1 import (
    CONSEQUENCE_EFFECT_RULES,
    S2_CASE_IDS,
    TRIAD_S2_RELATIVE_PATH as CANDIDATE_RELATIVE_PATH,
    audit_expected_answer_leakage,
    canonical_fingerprint,
    preflight_s2_candidate,
)


OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-response-screen-v2-2026-07-23"
)
EXPECTED_MODEL_DIGEST: Final = (
    "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7"
)
MODEL_PROFILE: Final[Mapping[str, Any]] = {
    "model": "gemma4:31b",
    "model_digest": EXPECTED_MODEL_DIGEST,
    "seed": 314159,
    "temperature": 0.0,
    "top_p": 0.95,
    "top_k": 64,
    "num_ctx": 65536,
    "num_gpu": 999,
    "num_predict": DEFAULT_OLLAMA_NUM_PREDICT,
    "retry": 0,
    "fallback": "none",
    "require_full_gpu": True,
    "thinking_persisted": False,
}
EMOCIO_PROVIDER_REVISION: Final = "triad-s2-counterfactual-structured-v1"
INSTINKT_MAPPER_REVISION: Final = "triad-s2-option-consequence-mapper-v1"
EXECUTION_POLICY: Final[Mapping[str, Any]] = {
    "case_order": S2_CASE_IDS,
    "racio_calls_per_case": 1,
    "emocio_executions_per_case": 1,
    "instinkt_executions_per_case": 1,
    "execute_emocio_after_racio_contract_rejection": True,
    "execute_instinkt_after_racio_contract_rejection": True,
    "stop_after_non_contract_provider_failure": True,
    "retry": 0,
    "fallback": "none",
    "character_replay_requires_complete_bundle": True,
}
_SEALED_FILENAMES: Final = (
    "pre_call_seal.json",
    "expected_call_ledger.json",
)
_PRIVATE_THINKING_KEYS: Final = frozenset(
    {
        "thinking",
        "thoughts",
        "reasoning_content",
        "chain_of_thought",
    }
)


@dataclass(frozen=True, slots=True)
class PreparedS2Case:
    case_id: str
    candidate: Mapping[str, Any]
    scene: SceneEvent
    racio_world: RacioWorld
    racio_packet: RacioInputPacket
    emocio_world: EmocioWorld
    emocio_packet: EmocioInputPacket
    emocio_compiled: CompiledEmocioScenes
    emocio_counterfactual_lineage: tuple[Mapping[str, Any], ...]
    body_state: BodyState
    instinkt_packet: InstinktInputPacket
    instinkt_effects: tuple[OptionBodyEffect, ...]
    instinkt_effect_lineage: tuple[Mapping[str, Any], ...]
    instinkt_config: InstinktSimulationConfig
    racio_call_spec: ProviderCallSpec
    emocio_call_spec: ProviderCallSpec
    instinkt_call_spec: ProviderCallSpec
    racio_request_payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ResearchEmocioExecution:
    conclusion: EmocioNativeConclusion
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord
    packet: EmocioInputPacket
    source_world_id: str
    source_world_hash: str
    visual_state: EmocioVisualState
    policy: EmocioPolicyDecision
    rendered_images: tuple[Any, ...] = ()
    renderer_warning: str | None = None

    def __post_init__(self) -> None:
        ensure_call_record_contract(self.call_spec, self.call_record)
        if self.call_record.status != "succeeded":
            raise ValueError("Research Emocio execution did not succeed directly")
        if self.call_record.output_artifact_ids != (
            self.visual_state.visual_state_id,
            self.conclusion.conclusion_id,
        ):
            raise ValueError("Research Emocio outputs differ from sealed artifacts")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        model_free_projection(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    )
    path.write_text(rendered + "\n", encoding="utf-8", newline="\n")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_free_projection(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", round_trip=True)
    if dataclasses.is_dataclass(value):
        return {
            field.name: model_free_projection(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): model_free_projection(child)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [model_free_projection(child) for child in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _canonical(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


def _walk(value: Any, path: tuple[str, ...] = ()):
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _scene_from_projection(case_id: str, source: Mapping[str, Any]) -> SceneEvent:
    return SceneEvent(
        event_id=source["event_id"],
        raw_input=source["raw_input"],
        language=source["language"],
        evidence=tuple(
            EvidenceItem(
                evidence_id=item["evidence_id"],
                modality=item["modality"],
                content=item["content"],
                grounded=True,
                source_ref=f"triad-s2:{case_id}:{item['claim_id']}",
                confidence=1.0,
                provenance_kind="supplied",
            )
            for item in source["evidence"]
        ),
        options=tuple(
            DecisionOption(
                option_id=item["option_id"],
                label=item["label"],
                description=item["description"],
            )
            for item in source["options"]
        ),
        actors=tuple(source["actors"]),
        constraints=tuple(item["text"] for item in source["constraints"]),
        unknowns=tuple(item["text"] for item in source["unknowns"]),
    )


def _racio_world(case_id: str, source: Mapping[str, Any]) -> RacioWorld:
    payload = {
        "schema_version": "rei-native-racio-world-v1",
        **{key: tuple(value) for key, value in source.items()},
    }
    return RacioWorld(
        world_id=content_id(f"s2_racio_{case_id[:11]}", payload),
        **payload,
    )


def _emocio_world(case_id: str, source: Mapping[str, Any]) -> EmocioWorld:
    payload = {
        "schema_version": "rei-native-emocio-world-v1",
        **{key: tuple(value) for key, value in source.items()},
    }
    return EmocioWorld(
        world_id=content_id(f"s2_emocio_{case_id[:10]}", payload),
        **payload,
    )


def _body_state(case_id: str, source: Mapping[str, Any]) -> BodyState:
    payload = {"schema_version": "rei-native-body-state-v1", **source}
    return BodyState(
        body_state_id=content_id(f"s2_body_{case_id[:12]}", payload),
        **payload,
    )


def _emocio_identity() -> ProviderIdentity:
    payload = {
        "kind": "visual_world_model",
        "implementation": (
            "rei.research.triad_s2.execute_research_emocio_once"
        ),
        "implementation_revision": EMOCIO_PROVIDER_REVISION,
        "uses_model": False,
    }
    return ProviderIdentity(
        provider_id=content_id("provider", payload),
        **payload,
    )


def _emocio_call_spec(
    *,
    scene: SceneEvent,
    packet: EmocioInputPacket,
    world: EmocioWorld,
    counterfactuals: Sequence[Mapping[str, Any]],
) -> ProviderCallSpec:
    counterfactual_input_id = content_id(
        "triad_s2_emocio_counterfactuals",
        model_free_projection(counterfactuals),
    )
    return build_native_call_spec(
        identity=_emocio_identity(),
        request_id=packet.packet_id,
        input_artifact_ids=(
            scene.event_id,
            packet.packet_id,
            emocio_world_input_id(world),
            counterfactual_input_id,
        ),
    )


def _attention(values: Sequence[str]) -> tuple[AttentionWeight, ...]:
    return tuple(
        sorted(
            (
                AttentionWeight(
                    target=content_id("s2_attention_target", value),
                    score=1.0,
                )
                for value in set(values)
            ),
            key=lambda item: item.target,
        )
    )


def _build_s2_emocio_packet(
    *,
    scene: SceneEvent,
    counterfactuals: Sequence[Mapping[str, Any]],
) -> EmocioInputPacket:
    """Extend the routed packet only with sealed counterfactual evidence.

    The active packet builder deliberately admits only visual/body evidence.
    TRIAD-S2's manual structured adapter also needs the grounded facts that
    support its precommitted option scenes.  This research-only packet keeps
    the active routing fields unchanged and expands only the evidence scope.
    """

    routed = build_emocio_packet(scene)
    counterfactual_evidence_ids = {
        evidence_id
        for item in counterfactuals
        for evidence_id in item["evidence_basis_ids"]
    }
    grounded_scene_evidence_ids = {
        item.evidence_id for item in scene.evidence if item.grounded
    }
    if not counterfactual_evidence_ids.issubset(grounded_scene_evidence_ids):
        raise ValueError(
            "S2 Emocio counterfactual evidence must be grounded in the scene"
        )
    payload = routed.model_dump(mode="python")
    payload.pop("packet_id")
    payload["source_scene_hash"] = None
    payload["evidence_ids"] = tuple(
        sorted(set(routed.evidence_ids) | counterfactual_evidence_ids)
    )
    payload["caveat"] = (
        f"{routed.caveat} TRIAD-S2 research adapter adds only the sealed "
        "grounded evidence basis for manual option counterfactual scenes; "
        "the exact source SceneEvent hash is preserved by the enclosing "
        "sealed call lineage rather than asserted as an active-router packet."
    )
    packet = EmocioInputPacket(
        packet_id=content_id("emocio_packet", payload),
        **payload,
    )
    return packet.validate_against(scene)


def _counterfactual_scene(
    *,
    scene: SceneEvent,
    packet: EmocioInputPacket,
    world: EmocioWorld,
    current: VisualSceneSpec,
    item: Mapping[str, Any],
) -> VisualSceneSpec:
    delta = item["delta"]
    removed = set(delta["entities_removed"])
    self_position = delta["self_position"]
    entities = _canonical(
        (
            *(value for value in current.entities if value not in removed),
            *delta["entities_added"],
            self_position,
        )
    )
    composition = _canonical(
        (
            *(value for value in current.composition if value not in removed),
            *delta["composition_changes"],
            *delta["attraction_markers"],
            *delta["obstacle_persistence"],
        )
    )
    inferred = _canonical(
        (
            *delta["entities_added"],
            *delta["entities_removed"],
            *delta["composition_changes"],
            *delta["movement"],
            self_position,
            *delta["attention"],
            delta["belonging"],
            *delta["status_relations"],
            *delta["attraction_markers"],
            *delta["obstacle_persistence"],
            *delta["obstacle_removal"],
        )
    )
    payload = {
        "schema_version": "rei-native-visual-scene-spec-v1",
        "scene_kind": "option_rollout",
        "option_id": item["option_id"],
        "entities": entities,
        "self_position": self_position,
        "attention_structure": _attention(delta["attention"]),
        "group_belonging": delta["belonging"],
        "status_relations": _canonical(delta["status_relations"]),
        "movement": _canonical(delta["movement"]),
        "composition": composition,
        "attraction_markers": _canonical(delta["attraction_markers"]),
        "obstacle_markers": _canonical(delta["obstacle_persistence"]),
        "grounded_evidence_ids": tuple(sorted(item["evidence_basis_ids"])),
        "inferred_elements": inferred,
    }
    result = VisualSceneSpec(
        scene_id=content_id(
            "visual_scene",
            {
                "source_scene_hash": scene.scene_hash(),
                "source_packet_hash": packet.content_hash(),
                "source_world_hash": world.content_hash(),
                "research_adapter_revision": EMOCIO_PROVIDER_REVISION,
                **payload,
            },
        ),
        **payload,
    )
    return result.validate_against(scene)


def compile_s2_emocio_counterfactuals(
    *,
    scene: SceneEvent,
    packet: EmocioInputPacket,
    world: EmocioWorld,
    counterfactuals: Sequence[Mapping[str, Any]],
) -> tuple[CompiledEmocioScenes, tuple[Mapping[str, Any], ...]]:
    baseline = compile_emocio_scenes(scene, packet, world)
    by_option = {item["option_id"]: item for item in counterfactuals}
    if len(by_option) != len(counterfactuals):
        raise ValueError("S2 Emocio counterfactual options must be unique")
    if set(by_option) != set(packet.allowed_option_ids):
        raise ValueError("S2 Emocio counterfactuals must cover every option")
    rollouts = tuple(
        _counterfactual_scene(
            scene=scene,
            packet=packet,
            world=world,
            current=baseline.current_scene,
            item=by_option[option_id],
        )
        for option_id in sorted(by_option)
    )
    lineage = tuple(
        {
            "option_id": item["option_id"],
            "candidate_counterfactual_signature": canonical_fingerprint(item["delta"]),
            "actual_scene_signature": canonical_fingerprint(
                {
                    field: model_free_projection(rollout)[field]
                    for field in (
                        "entities",
                        "self_position",
                        "attention_structure",
                        "group_belonging",
                        "status_relations",
                        "movement",
                        "composition",
                        "attraction_markers",
                        "obstacle_markers",
                    )
                }
            ),
            "evidence_basis_ids": tuple(item["evidence_basis_ids"]),
            "delta": item["delta"],
        }
        for item, rollout in (
            (by_option[rollout.option_id], rollout) for rollout in rollouts
        )
    )
    if len({item["actual_scene_signature"] for item in lineage}) < 2:
        raise ValueError("S2 Emocio actual scene signatures are not distinguishable")
    return (
        CompiledEmocioScenes(
            current_scene=baseline.current_scene,
            desired_scene=baseline.desired_scene,
            broken_scene=baseline.broken_scene,
            option_rollouts=rollouts,
        ),
        lineage,
    )


def _derived_effect(item: Mapping[str, Any]) -> Mapping[str, float]:
    combined: dict[str, float] = {}
    for fact in item["facts"]:
        for category in fact["effect_categories"]:
            try:
                rule = CONSEQUENCE_EFFECT_RULES[category]
            except KeyError as exc:
                raise ValueError(
                    f"Unknown sealed consequence-effect category: {category}"
                ) from exc
            for dimension, delta in rule.items():
                combined[dimension] = round(
                    combined.get(dimension, 0.0) + delta,
                    6,
                )
    return {
        dimension: combined[dimension]
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


def _dimension_outcome(
    deltas: Mapping[str, float],
    dimension: str,
) -> str:
    value = deltas.get(dimension)
    if value is None:
        return f"not_changed_by_sealed_consequence:{dimension}"
    return f"sealed_consequence_delta:{dimension}:{value:+.6f}"


def map_s2_instinkt_effects(
    *,
    scene: SceneEvent,
    body_state: BodyState,
    option_consequences: Sequence[Mapping[str, Any]],
) -> tuple[
    InstinktInputPacket,
    tuple[OptionBodyEffect, ...],
    tuple[Mapping[str, Any], ...],
]:
    by_option = {item["option_id"]: item for item in option_consequences}
    if len(by_option) != len(option_consequences):
        raise ValueError("S2 Instinkt consequence options must be unique")
    option_ids = {option.option_id for option in scene.options}
    if set(by_option) != option_ids:
        raise ValueError("S2 Instinkt consequences must cover every option")
    evidence_ids = tuple(
        sorted(
            {
                evidence_id
                for item in option_consequences
                for fact in item["facts"]
                for evidence_id in fact["source_evidence_ids"]
            }
        )
    )
    packet = build_instinkt_packet(
        scene,
        body_state,
        evidence_ids=evidence_ids,
        caveat=(
            "TRIAD-S2 profile-blind packet; typed effects derive only from "
            "sealed option-specific consequence facts and their evidence."
        ),
    )
    specs = []
    lineage = []
    for option_id in sorted(by_option):
        item = by_option[option_id]
        deltas = _derived_effect(item)
        categories = tuple(
            sorted(
                {
                    category
                    for fact in item["facts"]
                    for category in fact["effect_categories"]
                }
            )
        )
        option_evidence = tuple(
            sorted(
                {
                    evidence_id
                    for fact in item["facts"]
                    for evidence_id in fact["source_evidence_ids"]
                }
            )
        )
        specs.append(
            InstinktEffectSpec(
                option_id=option_id,
                body_deltas=tuple(
                    BodyDelta(dimension=dimension, delta=delta)
                    for dimension, delta in deltas.items()
                ),
                base_predicted_loss=0.5,
                base_recoverability=0.5,
                dominant_alarm="sealed_option_consequence:" + "+".join(categories),
                protected_targets=tuple(deltas),
                boundary_outcome=_dimension_outcome(
                    deltas,
                    "boundary_integrity",
                ),
                trust_outcome=_dimension_outcome(deltas, "trust"),
                attachment_outcome=_dimension_outcome(
                    deltas,
                    "attachment_security",
                ),
                escape_outcome=_dimension_outcome(
                    deltas,
                    "escape_availability",
                ),
                action_tendency=_effect_action(deltas),
                minimum_safety_condition=(
                    "option-specific consequence evidence remains within "
                    "the sealed packet scope"
                ),
                association_cue_tokens=tuple(
                    sorted(
                        {
                            *categories,
                            *(
                                fact["consequence_id"]
                                for fact in item["facts"]
                            ),
                        }
                    )
                ),
                triggering_evidence_ids=option_evidence,
            )
        )
        lineage.append(
            {
                "option_id": option_id,
                "consequence_facts": item["facts"],
                "effect_categories": categories,
                "derived_body_deltas": deltas,
                "source_evidence_ids": option_evidence,
            }
        )
    effects = bind_instinkt_effects(packet, tuple(specs))
    effect_by_option = {effect.option_id: effect for effect in effects}
    frozen_lineage = tuple(
        {
            **item,
            "effect_id": effect_by_option[item["option_id"]].effect_id,
            "effect_signature": canonical_fingerprint(
                {
                    field: model_free_projection(
                        effect_by_option[item["option_id"]]
                    )[field]
                    for field in (
                        "body_deltas",
                        "base_predicted_loss",
                        "base_recoverability",
                        "dominant_alarm",
                        "protected_targets",
                        "boundary_outcome",
                        "trust_outcome",
                        "attachment_outcome",
                        "escape_outcome",
                        "action_tendency",
                        "minimum_safety_condition",
                        "triggering_evidence_ids",
                    )
                }
            ),
        }
        for item in lineage
    )
    if len({item["effect_signature"] for item in frozen_lineage}) < 2:
        raise ValueError("S2 Instinkt grounded effect signatures are not distinct")
    return packet, effects, frozen_lineage


def _successful_record(
    *,
    call: ProviderCallSpec,
    output_artifact_ids: tuple[str, ...],
    started_at: Any,
    finished_at: Any,
) -> ProviderCallRecord:
    record = ProviderCallRecord(
        call_id=call.call_id,
        spec_hash=call.content_hash(),
        request_id=call.request_id,
        input_artifact_ids=call.input_artifact_ids,
        provider=call.provider,
        seed=call.seed,
        parameters=call.parameters,
        timeout_seconds=call.timeout_seconds,
        started_at=started_at,
        primary_finished_at=finished_at,
        finished_at=finished_at,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=output_artifact_ids,
        safety_notice=call.safety_notice,
    )
    ensure_call_record_contract(call, record)
    return record


def _failed_record(
    *,
    call: ProviderCallSpec,
    started_at: Any,
    finished_at: Any,
    warning: str,
) -> ProviderCallRecord:
    record = ProviderCallRecord(
        call_id=call.call_id,
        spec_hash=call.content_hash(),
        request_id=call.request_id,
        input_artifact_ids=call.input_artifact_ids,
        provider=call.provider,
        seed=call.seed,
        parameters=call.parameters,
        timeout_seconds=call.timeout_seconds,
        started_at=started_at,
        primary_finished_at=finished_at,
        finished_at=finished_at,
        status="failed",
        primary_status="failed",
        output_artifact_ids=(),
        warnings=(warning,),
        safety_notice=call.safety_notice,
    )
    ensure_call_record_contract(call, record)
    return record


def execute_research_emocio_once(
    item: PreparedS2Case,
    *,
    clock: SystemExecutionClock,
) -> ResearchEmocioExecution:
    started_at = clock.timestamp("emocio_call_started")
    visual_state = build_emocio_visual_state(
        scene=item.scene,
        packet=item.emocio_packet,
        world=item.emocio_world,
        compiled=item.emocio_compiled,
    )
    policy = choose_native_option(visual_state.option_valuations)
    conclusion = _native_conclusion(
        packet=item.emocio_packet,
        visual_state=visual_state,
        policy=policy,
    )
    finished_at = clock.timestamp("emocio_call_finished")
    record = _successful_record(
        call=item.emocio_call_spec,
        output_artifact_ids=(
            visual_state.visual_state_id,
            conclusion.conclusion_id,
        ),
        started_at=started_at,
        finished_at=finished_at,
    )
    return ResearchEmocioExecution(
        conclusion=conclusion,
        call_spec=item.emocio_call_spec,
        call_record=record,
        packet=item.emocio_packet,
        source_world_id=item.emocio_world.world_id,
        source_world_hash=item.emocio_world.content_hash(),
        visual_state=visual_state,
        policy=policy,
    )


def build_provider() -> OllamaRacioNativeEnTriadProvider:
    settings = OllamaRacioSettings(
        model=MODEL_PROFILE["model"],
        seed=MODEL_PROFILE["seed"],
        temperature=MODEL_PROFILE["temperature"],
        num_ctx=MODEL_PROFILE["num_ctx"],
        num_gpu=MODEL_PROFILE["num_gpu"],
        num_predict=MODEL_PROFILE["num_predict"],
        require_full_gpu=True,
    )
    provider = OllamaRacioNativeEnTriadProvider.discover(
        client=OllamaApiClient(),
        settings=settings,
        expected_digest=EXPECTED_MODEL_DIGEST,
    )
    if provider.runtime.digest != EXPECTED_MODEL_DIGEST:
        raise ValueError("Local model digest differs from TRIAD-S2")
    if provider.identity.implementation_revision.split(";", 1)[0] != (
        OLLAMA_EN_TRIAD_PROVIDER_REVISION
    ):
        raise ValueError("English Racio provider revision changed")
    if provider.top_p != MODEL_PROFILE["top_p"]:
        raise ValueError("English Racio top_p changed")
    if provider.top_k != MODEL_PROFILE["top_k"]:
        raise ValueError("English Racio top_k changed")
    return provider


def prepare_cases(
    candidate: Mapping[str, Any],
    provider: OllamaRacioNativeEnTriadProvider,
) -> tuple[PreparedS2Case, ...]:
    preflight_s2_candidate(candidate)
    if audit_expected_answer_leakage(candidate)["expected_answer_leakage_found"]:
        raise ValueError("TRIAD-S2 candidate contains expected-answer leakage")
    instinkt_provider = DeterministicInstinktNativeProvider()
    prepared = []
    for case in candidate["cases"]:
        case_id = case["case_id"]
        scene = _scene_from_projection(case_id, case["operational_en"])
        racio_world = _racio_world(case_id, case["racio_input"]["world"])
        racio_packet = build_racio_packet(
            scene,
            racio_world,
            symbolic_and_language_cues=(scene.raw_input,),
            numeric_cues=tuple(case["racio_input"]["numeric_cues"]),
            time=tuple(case["racio_input"]["time"]),
            rules=tuple(case["racio_input"]["rules"]),
            explicit_consequences=tuple(
                RacioConsequence.model_validate(value)
                for value in case["racio_input"]["explicit_consequences"]
            ),
        )
        if racio_packet.language != "en":
            raise ValueError("TRIAD-S2 Racio packet must be English")
        emocio_world = _emocio_world(case_id, case["emocio_input"]["world"])
        emocio_packet = _build_s2_emocio_packet(
            scene=scene,
            counterfactuals=case["emocio_input"]["option_counterfactuals"],
        )
        compiled, counterfactual_lineage = compile_s2_emocio_counterfactuals(
            scene=scene,
            packet=emocio_packet,
            world=emocio_world,
            counterfactuals=case["emocio_input"]["option_counterfactuals"],
        )
        body_state = _body_state(case_id, case["instinkt_input"]["body_state"])
        instinkt_packet, effects, effect_lineage = map_s2_instinkt_effects(
            scene=scene,
            body_state=body_state,
            option_consequences=case["instinkt_input"]["option_consequences"],
        )
        config = InstinktSimulationConfig.create()
        racio_call = provider.build_call_spec(racio_packet)
        emocio_call = _emocio_call_spec(
            scene=scene,
            packet=emocio_packet,
            world=emocio_world,
            counterfactuals=case["emocio_input"]["option_counterfactuals"],
        )
        instinkt_call = instinkt_provider.build_call_spec(
            scene=scene,
            packet=instinkt_packet,
            source_body_state=body_state,
            option_effects=effects,
            config=config,
        )
        request_payload = provider.request_payload(racio_packet)
        serialized_payload = json.dumps(request_payload, ensure_ascii=False)
        if any(
            forbidden in serialized_payload
            for forbidden in ("canonical_sl", "notes_sl", "prompt_sl")
        ):
            raise ValueError("Racio model payload contains a source-language field")
        prepared.append(
            PreparedS2Case(
                case_id=case_id,
                candidate=case,
                scene=scene,
                racio_world=racio_world,
                racio_packet=racio_packet,
                emocio_world=emocio_world,
                emocio_packet=emocio_packet,
                emocio_compiled=compiled,
                emocio_counterfactual_lineage=counterfactual_lineage,
                body_state=body_state,
                instinkt_packet=instinkt_packet,
                instinkt_effects=effects,
                instinkt_effect_lineage=effect_lineage,
                instinkt_config=config,
                racio_call_spec=racio_call,
                emocio_call_spec=emocio_call,
                instinkt_call_spec=instinkt_call,
                racio_request_payload=request_payload,
            )
        )
    if tuple(item.case_id for item in prepared) != S2_CASE_IDS:
        raise ValueError("TRIAD-S2 case order differs from the approved order")
    return tuple(prepared)


def _input_projection(item: PreparedS2Case) -> Mapping[str, Any]:
    return {
        "schema_version": "triad-s2-sealed-inputs-v1",
        "case_id": item.case_id,
        "source": {
            "canonical_sl": item.candidate["canonical_sl"],
            "operational_en": item.candidate["operational_en"],
        },
        "public_options": item.candidate["operational_en"]["options"],
        "racio": {
            "scene": item.scene,
            "world": item.racio_world,
            "packet": item.racio_packet,
            "request_payload": item.racio_request_payload,
            "call_spec": item.racio_call_spec,
        },
        "emocio": {
            "mode": "manual_structured_counterfactual_routing",
            "world": item.emocio_world,
            "packet": item.emocio_packet,
            "compiled_scenes": item.emocio_compiled,
            "counterfactual_lineage": item.emocio_counterfactual_lineage,
            "call_spec": item.emocio_call_spec,
            "image_generation_calls": 0,
        },
        "instinkt": {
            "mode": "manual_option_consequence_routing",
            "body_state": item.body_state,
            "packet": item.instinkt_packet,
            "option_effects": item.instinkt_effects,
            "effect_lineage": item.instinkt_effect_lineage,
            "simulation_config": item.instinkt_config,
            "call_spec": item.instinkt_call_spec,
            "model_mapper_calls": 0,
        },
        "profile_blind": True,
    }


def _expected_call_ledger(prepared: Sequence[PreparedS2Case]) -> Mapping[str, Any]:
    return {
        "schema_version": "triad-s2-expected-call-ledger-v1",
        "phase": "TRIAD-S2",
        "state": "sealed_before_calls",
        "expected": {
            "model_calls": 4,
            "retries": 0,
            "fallbacks": 0,
            "maximum_native_bundles": 4,
            "maximum_character_replay_rows": 52,
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


def seal_s2(repository_root: Path) -> Mapping[str, Any]:
    candidate_root = repository_root / CANDIDATE_RELATIVE_PATH
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    if output_root.exists():
        raise ValueError("TRIAD-S2 output root already exists; seal is create-only")
    candidate_path = candidate_root / "corpus_candidate.json"
    distinguishability_path = candidate_root / "distinguishability_report.json"
    leakage_path = candidate_root / "leakage_report.json"
    d1_ledger_path = candidate_root / "expected_call_ledger.json"
    candidate = _json(candidate_path)
    preflight = preflight_s2_candidate(candidate)
    if preflight != _json(distinguishability_path):
        raise ValueError("Committed distinguishability report differs from cold preflight")
    leakage = audit_expected_answer_leakage(candidate)
    if leakage != _json(leakage_path):
        raise ValueError("Committed leakage report differs from cold audit")
    provider = build_provider()
    prepared = prepare_cases(candidate, provider)

    input_records = []
    for item in prepared:
        path = output_root / "cases" / item.case_id / "inputs.json"
        _write_json(path, _input_projection(item))
        input_records.append(
            {
                "case_id": item.case_id,
                "path": path.relative_to(repository_root).as_posix(),
                "sha256": _file_sha256(path),
                "racio_call_id": item.racio_call_spec.call_id,
                "racio_call_spec_hash": item.racio_call_spec.content_hash(),
            }
        )
    expected_ledger = _expected_call_ledger(prepared)
    expected_ledger_path = output_root / "expected_call_ledger.json"
    _write_json(expected_ledger_path, expected_ledger)
    base = {
        "schema_version": "triad-s2-pre-call-execution-seal-v1",
        "phase": "TRIAD-S2",
        "candidate_corpus": {
            "path": candidate_path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(candidate_path),
        },
        "distinguishability_report": {
            "path": distinguishability_path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(distinguishability_path),
        },
        "leakage_report": {
            "path": leakage_path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(leakage_path),
        },
        "d1_expected_call_ledger": {
            "path": d1_ledger_path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(d1_ledger_path),
        },
        "generic_effect_rules_sha256": canonical_fingerprint(
            CONSEQUENCE_EFFECT_RULES
        ),
        "racio_provider_revision": OLLAMA_EN_TRIAD_PROVIDER_REVISION,
        "model_digest": provider.runtime.digest,
        "instruction_sha256": sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN),
        "model_profile": MODEL_PROFILE,
        "racio_call_specs": [
            model_free_projection(item.racio_call_spec) for item in prepared
        ],
        "expected_call_ledger": {
            "path": expected_ledger_path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(expected_ledger_path),
        },
        "case_input_records": input_records,
        "execution_policy": EXECUTION_POLICY,
        "output_root": OUTPUT_RELATIVE_PATH.as_posix(),
        "declarations": {
            "manual_structured_routing": True,
            "image_native_emocio_claim": False,
            "raw_scene_instinkt_claim": False,
            "holdout": False,
            "promotion_evidence": False,
            "global_rei_score": False,
            "thinking_persisted": False,
        },
        "created_at": utc_now(),
    }
    base = model_free_projection(base)
    seal = {**base, "seal_sha256": canonical_fingerprint(base)}
    _write_json(output_root / "pre_call_seal.json", seal)
    return seal


def verify_seal(
    repository_root: Path,
    provider: OllamaRacioNativeEnTriadProvider | None = None,
) -> tuple[Mapping[str, Any], tuple[PreparedS2Case, ...]]:
    candidate_root = repository_root / CANDIDATE_RELATIVE_PATH
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    seal = _json(output_root / "pre_call_seal.json")
    seal_base = {key: value for key, value in seal.items() if key != "seal_sha256"}
    if canonical_fingerprint(seal_base) != seal["seal_sha256"]:
        raise ValueError("TRIAD-S2 pre-call seal hash differs")
    for field in (
        "candidate_corpus",
        "distinguishability_report",
        "leakage_report",
        "d1_expected_call_ledger",
        "expected_call_ledger",
    ):
        record = seal[field]
        if _file_sha256(repository_root / record["path"]) != record["sha256"]:
            raise ValueError(f"TRIAD-S2 sealed file changed: {field}")
    if seal["generic_effect_rules_sha256"] != canonical_fingerprint(
        CONSEQUENCE_EFFECT_RULES
    ):
        raise ValueError("TRIAD-S2 generic effect rules changed")
    if seal["model_profile"] != MODEL_PROFILE:
        raise ValueError("TRIAD-S2 model profile changed")
    if seal["instruction_sha256"] != sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN):
        raise ValueError("TRIAD-S2 provider instruction changed")
    active_provider = provider or build_provider()
    if active_provider.runtime.digest != seal["model_digest"]:
        raise ValueError("TRIAD-S2 local model digest changed after seal")
    candidate = _json(candidate_root / "corpus_candidate.json")
    prepared = prepare_cases(candidate, active_provider)
    if [
        model_free_projection(item.racio_call_spec) for item in prepared
    ] != seal["racio_call_specs"]:
        raise ValueError("TRIAD-S2 Racio call specs changed after seal")
    for record, item in zip(
        seal["case_input_records"],
        prepared,
        strict=True,
    ):
        path = repository_root / record["path"]
        if record["case_id"] != item.case_id:
            raise ValueError("TRIAD-S2 case input order changed")
        if _file_sha256(path) != record["sha256"]:
            raise ValueError("TRIAD-S2 sealed case input changed")
        if _json(path) != model_free_projection(_input_projection(item)):
            raise ValueError("TRIAD-S2 case input differs from cold preparation")
    return seal, prepared


def _valuation_projection(execution: ResearchEmocioExecution) -> Mapping[str, Any]:
    state = execution.visual_state
    score_by_option = {
        item.option_id: item.score for item in execution.policy.aggregate_scores
    }
    vectors = {
        valuation.option_id: {
            item.name: item.score for item in valuation.dimensions
        }
        for valuation in state.option_valuations
    }
    signatures = {
        option_id: canonical_fingerprint(vector)
        for option_id, vector in vectors.items()
    }
    return {
        "visual_state": state,
        "policy": execution.policy,
        "current_scene": state.current_scene,
        "desired_scene": state.desired_scene,
        "broken_scene": state.broken_scene,
        "counterfactual_scenes": state.option_rollouts,
        "valuation_vectors": vectors,
        "valuation_vector_signatures": signatures,
        "aggregate_scores": score_by_option,
        "selected_option_id": execution.conclusion.option_id,
        "abstains": execution.conclusion.abstains,
        "tied_option_ids": execution.policy.tied_option_ids,
        "signature_distinction": (
            len({item.scene_id for item in state.option_rollouts}) >= 2
        ),
        "valuation_distinction": len(set(signatures.values())) >= 2,
        "policy_distinction": (
            len(set(signatures.values())) >= 2
            and (
                execution.conclusion.option_id is not None
                or bool(execution.policy.tied_option_ids)
            )
        ),
        "failure_marker": (
            None
            if len(set(signatures.values())) >= 2
            else "emocio_valuator_still_semantically_inert"
        ),
        "scene_routes": [
            _scene_route_projection(
                rollout,
                desired=state.desired_scene,
                broken=state.broken_scene,
            )
            for rollout in state.option_rollouts
        ],
    }


def _scene_route_projection(
    rollout: VisualSceneSpec,
    *,
    desired: VisualSceneSpec,
    broken: VisualSceneSpec,
) -> Mapping[str, Any]:
    return {
        "option_id": rollout.option_id,
        "scene_to_desired": {
            "composition_overlap": tuple(
                sorted(set(rollout.composition) & set(desired.composition))
            ),
            "movement_overlap": tuple(
                sorted(set(rollout.movement) & set(desired.movement))
            ),
            "status_overlap": tuple(
                sorted(set(rollout.status_relations) & set(desired.status_relations))
            ),
            "attraction_overlap": tuple(
                sorted(set(rollout.composition) & set(desired.attraction_markers))
            ),
        },
        "scene_to_broken": {
            "composition_overlap": tuple(
                sorted(set(rollout.composition) & set(broken.composition))
            ),
            "obstacle_overlap": tuple(
                sorted(set(rollout.composition) & set(broken.obstacle_markers))
            ),
        },
    }


def _instinkt_projection(
    item: PreparedS2Case,
    execution: InstinktNativeExecution,
) -> Mapping[str, Any]:
    rollout_by_option = {
        rollout.option_id: rollout for rollout in execution.rollouts
    }
    cost_by_option = {
        score.option_id: score.protective_cost
        for score in execution.processing.policy.option_scores
    }
    signatures = {
        value["option_id"]: value["effect_signature"]
        for value in item.instinkt_effect_lineage
    }
    return {
        "body_state": item.body_state,
        "option_paths": [
            {
                **value,
                "effect": next(
                    effect
                    for effect in execution.option_effects
                    if effect.option_id == value["option_id"]
                ),
                "predicted_loss": rollout_by_option[value["option_id"]].predicted_loss,
                "recoverability": rollout_by_option[
                    value["option_id"]
                ].recoverability,
                "protective_cost": cost_by_option[value["option_id"]],
            }
            for value in item.instinkt_effect_lineage
        ],
        "selected_option_id": execution.conclusion.option_id,
        "abstains": execution.conclusion.abstains,
        "tied_option_ids": execution.processing.policy.tied_option_ids,
        "effect_distinction": len(set(signatures.values())) >= 2,
        "every_effect_has_option_specific_evidence": all(
            bool(value["source_evidence_ids"])
            for value in item.instinkt_effect_lineage
        ),
        "failure_marker": (
            "instinkt_effect_degeneracy_reappeared"
            if len(set(signatures.values())) < len(signatures)
            else None
        ),
    }


def _profile_projection(
    *,
    item: PreparedS2Case,
    bundle: NativeMindBundle,
    rows: Sequence[Any],
) -> Mapping[str, Any]:
    return {
        "schema_version": "triad-s2-profile-matrix-v1",
        "case_id": item.case_id,
        "status": "complete",
        "native_bundle_id": bundle.bundle_id,
        "native_bundle_hash": bundle.immutable_hash,
        "native_processor_executions_during_replay": 0,
        "model_calls_during_replay": 0,
        "rows": [
            {
                "profile_id": row.profile_id,
                "structural_source_minds": row.mandate.structural_source_minds,
                "mandate_status": row.mandate.status,
                "mandate_option_id": row.mandate.option_id,
                "pair_status": (
                    row.pair_conflict.status
                    if row.pair_conflict is not None
                    else None
                ),
                "two_of_three": (
                    row.mandate.option_id
                    if row.profile_id == "R=E=I"
                    and row.agreement_pattern.agreement_kind
                    in {"unanimous", "majority"}
                    else None
                ),
                "spoznanje_status": row.spoznanje_status,
                "governance_resolution_id": row.resolution_id,
                "governance": row,
            }
            for row in rows
        ],
    }


def execute_s2(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    if (output_root / "call_ledger.json").exists():
        raise ValueError("TRIAD-S2 execution is create-only and cannot retry")
    provider = build_provider()
    seal, prepared = verify_seal(repository_root, provider)
    expected_ledger = _json(output_root / "expected_call_ledger.json")
    if expected_ledger["state"] != "sealed_before_calls":
        raise ValueError("TRIAD-S2 expected ledger is not sealed")
    ledger = {
        "schema_version": "triad-s2-call-ledger-v1",
        "phase": "TRIAD-S2",
        "state": "executing",
        "pre_call_seal_sha256": seal["seal_sha256"],
        "expected": expected_ledger["expected"],
        "actual": {"model_calls": 0, "retries": 0, "fallbacks": 0},
        "entries": [
            {
                "ordinal": entry["ordinal"],
                "case_id": entry["case_id"],
                "racio_call_id": entry["racio_call_id"],
                "status": "planned",
            }
            for entry in expected_ledger["entries"]
        ],
    }
    ledger_path = output_root / "call_ledger.json"
    _write_json(ledger_path, ledger)
    instinkt_provider = DeterministicInstinktNativeProvider()
    clock = SystemExecutionClock()
    bundles = []
    failures = []
    abstentions = Counter()
    agreement_counts = Counter()
    processor_counts = {"R": 0, "E": 0, "I": 0}
    replay_rows = 0
    stop_after_case = False

    for item, entry in zip(prepared, ledger["entries"], strict=True):
        if stop_after_case:
            entry["status"] = "not_run_after_non_contract_failure"
            continue
        case_root = output_root / "cases" / item.case_id
        entry["status"] = "dispatching"
        ledger["actual"]["model_calls"] += 1
        processor_counts["R"] += 1
        _write_json(ledger_path, ledger)
        racio_started = utc_now()
        racio_execution = None
        racio_diagnostic = None
        racio_failure = None
        try:
            racio_execution = provider.execute(
                item.racio_packet,
                call=item.racio_call_spec,
                clock=clock,
            )
            entry["racio_status"] = "accepted"
        except OllamaStructuredOutputValidationError as exc:
            racio_finished = utc_now()
            racio_diagnostic = exc.diagnostic
            racio_failure = {
                "failure_type": type(exc).__name__,
                "failure_code": exc.diagnostic.failure_code,
                "validation_stage": exc.diagnostic.validation_stage,
                "final_json_sha256": exc.diagnostic.final_json_sha256,
                "accepted": False,
                "message": str(exc),
            }
            racio_failed_record = _failed_record(
                call=item.racio_call_spec,
                started_at=racio_started,
                finished_at=racio_finished,
                warning=(
                    f"{exc.diagnostic.validation_stage}:"
                    f"{exc.diagnostic.failure_code}:"
                    f"{exc.diagnostic.final_json_sha256}"
                ),
            )
            entry.update(
                {
                    "racio_status": "rejected",
                    "failure_code": exc.diagnostic.failure_code,
                    "final_json_sha256": exc.diagnostic.final_json_sha256,
                }
            )
            failures.append({"case_id": item.case_id, **racio_failure})
        except Exception as exc:
            racio_finished = utc_now()
            racio_failed_record = _failed_record(
                call=item.racio_call_spec,
                started_at=racio_started,
                finished_at=racio_finished,
                warning=f"non_contract_provider_failure:{type(exc).__name__}",
            )
            racio_failure = {
                "failure_type": type(exc).__name__,
                "failure_code": "non_contract_provider_failure",
                "validation_stage": "provider_execution",
                "accepted": False,
                "message": str(exc),
            }
            entry.update(
                {
                    "racio_status": "provider_failed",
                    "failure_code": "non_contract_provider_failure",
                }
            )
            failures.append({"case_id": item.case_id, **racio_failure})
            stop_after_case = True

        execute_ei = (
            racio_execution is not None
            or isinstance(racio_diagnostic, BaseModel)
        )
        emocio_execution = None
        instinkt_execution = None
        if execute_ei:
            emocio_execution = execute_research_emocio_once(item, clock=clock)
            processor_counts["E"] += 1
            instinkt_execution = instinkt_provider.execute(
                scene=item.scene,
                packet=item.instinkt_packet,
                source_body_state=item.body_state,
                option_effects=item.instinkt_effects,
                config=item.instinkt_config,
                call=item.instinkt_call_spec,
                clock=clock,
            )
            processor_counts["I"] += 1

        bundle = None
        agreement = None
        governance_rows = ()
        if (
            racio_execution is not None
            and emocio_execution is not None
            and instinkt_execution is not None
        ):
            bundle = NativeMindBundle.create(
                scene=item.scene,
                racio_packet=item.racio_packet,
                emocio_packet=item.emocio_packet,
                instinkt_packet=item.instinkt_packet,
                emocio_visual_state=emocio_execution.visual_state,
                instinkt_body_state=item.body_state,
                instinkt_rollouts=instinkt_execution.rollouts,
                racio=racio_execution.conclusion,
                emocio=emocio_execution.conclusion,
                instinkt=instinkt_execution.conclusion,
            )
            agreement = assess_agreement_pattern(bundle)
            governance_rows = replay_profiles(bundle)
            bundles.append(bundle)
            agreement_counts[agreement.agreement_kind] += 1
            replay_rows += len(governance_rows)
            for mind, conclusion in (
                ("R", racio_execution.conclusion),
                ("E", emocio_execution.conclusion),
                ("I", instinkt_execution.conclusion),
            ):
                abstentions[mind] += int(conclusion.abstains)
        else:
            if emocio_execution is not None:
                abstentions["E"] += int(emocio_execution.conclusion.abstains)
            if instinkt_execution is not None:
                abstentions["I"] += int(instinkt_execution.conclusion.abstains)

        call_projection = {
            "schema_version": "triad-s2-call-record-v1",
            "case_id": item.case_id,
            "racio": {
                "call_spec": item.racio_call_spec,
                "call_record": (
                    racio_execution.call_record
                    if racio_execution is not None
                    else racio_failed_record
                ),
                "result_evidence": (
                    racio_execution.reasoning_artifact
                    if racio_execution is not None
                    else None
                ),
                "failed_output_diagnostic": racio_diagnostic,
                "failure": racio_failure,
                "retries": 0,
                "fallbacks": 0,
            },
            "emocio": (
                None
                if emocio_execution is None
                else {
                    "call_spec": emocio_execution.call_spec,
                    "call_record": emocio_execution.call_record,
                    "uses_model": False,
                }
            ),
            "instinkt": (
                None
                if instinkt_execution is None
                else {
                    "call_spec": instinkt_execution.call_spec,
                    "call_record": instinkt_execution.call_record,
                    "uses_model": False,
                }
            ),
            "private_thinking_persisted": False,
        }
        _write_json(case_root / "call_record.json", call_projection)
        native_projection = {
            "schema_version": "triad-s2-native-outputs-v1",
            "case_id": item.case_id,
            "processor_execution_counts": {
                "R": 1,
                "E": int(emocio_execution is not None),
                "I": int(instinkt_execution is not None),
            },
            "racio": (
                {
                    "status": "accepted",
                    "conclusion": racio_execution.conclusion,
                }
                if racio_execution is not None
                else {
                    "status": "rejected",
                    "conclusion": None,
                    "failure": racio_failure,
                }
            ),
            "emocio": (
                None
                if emocio_execution is None
                else {
                    "conclusion": emocio_execution.conclusion,
                    **_valuation_projection(emocio_execution),
                    "counterfactual_lineage": item.emocio_counterfactual_lineage,
                }
            ),
            "instinkt": (
                None
                if instinkt_execution is None
                else {
                    "conclusion": instinkt_execution.conclusion,
                    "rollouts": instinkt_execution.rollouts,
                    "policy": instinkt_execution.processing.policy,
                    **_instinkt_projection(item, instinkt_execution),
                }
            ),
            "bundle": bundle,
            "agreement_pattern": agreement,
        }
        _write_json(case_root / "native_outputs.json", native_projection)
        _write_json(
            case_root / "profile_matrix.json",
            (
                _profile_projection(
                    item=item,
                    bundle=bundle,
                    rows=governance_rows,
                )
                if bundle is not None
                else {
                    "schema_version": "triad-s2-profile-matrix-v1",
                    "case_id": item.case_id,
                    "status": "not_run_without_complete_bundle",
                    "native_processor_executions_during_replay": 0,
                    "model_calls_during_replay": 0,
                    "rows": [],
                }
            ),
        )
        entry["status"] = (
            "complete"
            if bundle is not None
            else "racio_rejected_ei_completed"
            if racio_diagnostic is not None
            else "provider_failed"
        )
        _write_json(ledger_path, ledger)

    ledger["state"] = (
        "complete"
        if ledger["actual"]["model_calls"] == 4 and not stop_after_case
        else "stopped_after_non_contract_failure"
    )
    _write_json(ledger_path, ledger)
    case_outputs = [
        _json(output_root / "cases" / case_id / "native_outputs.json")
        for case_id in S2_CASE_IDS
        if (output_root / "cases" / case_id / "native_outputs.json").exists()
    ]
    summary = {
        "schema_version": "triad-s2-summary-v1",
        "phase": "TRIAD-S2",
        "pre_call_seal_sha256": seal["seal_sha256"],
        "model": provider.runtime.model,
        "model_digest": provider.runtime.digest,
        "provider_revision": OLLAMA_EN_TRIAD_PROVIDER_REVISION,
        "calls": ledger["actual"]["model_calls"],
        "retries": ledger["actual"]["retries"],
        "fallbacks": ledger["actual"]["fallbacks"],
        "racio": {
            "accepted": sum(
                output["racio"]["status"] == "accepted"
                for output in case_outputs
            ),
            "rejected": sum(
                output["racio"]["status"] == "rejected"
                for output in case_outputs
            ),
        },
        "emocio_valuation_distinguishable": sum(
            output["emocio"] is not None
            and output["emocio"]["valuation_distinction"]
            for output in case_outputs
        ),
        "instinkt_effect_distinguishable": sum(
            output["instinkt"] is not None
            and output["instinkt"]["effect_distinction"]
            for output in case_outputs
        ),
        "complete_frozen_bundles": len(bundles),
        "character_replay_rows": replay_rows,
        "agreement_patterns": {
            "unanimous": agreement_counts["unanimous"],
            "majority": agreement_counts["majority"],
            "all_different": agreement_counts["all_different"],
            "incomplete": agreement_counts["incomplete"],
        },
        "abstentions": {
            "R": abstentions["R"],
            "E": abstentions["E"],
            "I": abstentions["I"],
        },
        "processor_execution_counts": processor_counts,
        "failure_categories": dict(
            Counter(item["failure_code"] for item in failures)
        ),
        "failures": failures,
        "image_generation_calls": 0,
        "gemma_emocio_shadow_calls": 0,
        "gemma_instinkt_shadow_calls": 0,
        "global_rei_score": None,
        "holdout": False,
        "promotion_evidence": False,
    }
    _write_json(output_root / "summary.json", summary)
    render_report(repository_root, summary)
    return summary


def _render_json_inline(value: Any) -> str:
    return json.dumps(
        model_free_projection(value),
        ensure_ascii=False,
        sort_keys=True,
    )


def _human_review_fields() -> list[str]:
    lines = []
    for mind in ("Racio", "Emocio", "Instinkt"):
        lines.extend(
            (
                f"**{mind} route:**",
                "",
                "- plausible: ",
                "- implausible: ",
                "- uncertain: ",
                "- option plausible: ",
                "- route meaningfully distinct: ",
                "- unsupported inference: ",
                "- abstention appropriate: ",
                "- input appears to predetermine outcome: ",
                "",
            )
        )
    return lines


def render_report(repository_root: Path, summary: Mapping[str, Any]) -> str:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    lines = [
        "# TRIAD-S2 distinguishable native-route development screen",
        "",
        "This is a development screen with manual structured routing. It is not "
        "a holdout, not promotion evidence, and does not compute a global REI score.",
        "",
        "Emocio uses sealed structured counterfactual scenes. No image was generated "
        "and no image-native Emocio claim is made.",
        "",
        "Instinkt uses sealed option-specific consequence facts and typed body "
        "effects. No raw-scene Instinkt perception claim is made.",
        "",
        "## Execution summary",
        "",
        f"- Pre-call seal: `{summary['pre_call_seal_sha256']}`.",
        f"- Model digest: `{summary['model_digest']}`.",
        f"- Calls/retries/fallbacks: {summary['calls']}/"
        f"{summary['retries']}/{summary['fallbacks']}.",
        f"- Racio accepted/rejected: {summary['racio']['accepted']}/"
        f"{summary['racio']['rejected']}.",
        "- Emocio valuation-distinguishable: "
        f"{summary['emocio_valuation_distinguishable']}/4.",
        "- Instinkt effect-distinguishable: "
        f"{summary['instinkt_effect_distinguishable']}/4.",
        f"- Complete frozen bundles: {summary['complete_frozen_bundles']}.",
        f"- Character replay rows: {summary['character_replay_rows']}.",
        "",
    ]
    for case_id in S2_CASE_IDS:
        case_root = output_root / "cases" / case_id
        if not (case_root / "native_outputs.json").exists():
            lines.extend(
                (f"## {case_id}", "", "Not run after a provider failure.", "")
            )
            continue
        inputs = _json(case_root / "inputs.json")
        outputs = _json(case_root / "native_outputs.json")
        matrix = _json(case_root / "profile_matrix.json")
        lines.extend(
            (
                f"## {case_id}",
                "",
                "### Source",
                "",
                "**Canonical Slovenian**",
                "",
                _render_json_inline(inputs["source"]["canonical_sl"]),
                "",
                "**Operational English sent to Racio**",
                "",
                _render_json_inline(inputs["source"]["operational_en"]),
                "",
                "### Racio",
                "",
            )
        )
        if outputs["racio"]["status"] == "accepted":
            conclusion = outputs["racio"]["conclusion"]
            lines.extend(
                (
                    f"- Status: accepted.",
                    f"- Selected option: `{conclusion['option_id']}`.",
                    f"- Facts used: {_render_json_inline(conclusion['facts_used'])}.",
                    f"- Unknowns retained: "
                    f"{_render_json_inline(conclusion['unknowns'])}.",
                    f"- Causal sequence: "
                    f"{_render_json_inline(conclusion['causal_sequence'])}.",
                    f"- Utility structure: "
                    f"{_render_json_inline(conclusion['utility_structure'])}.",
                    f"- Explicit goal: {conclusion['explicit_goal']}",
                    f"- Main objection: {conclusion['main_objection']}",
                    f"- Confidence: {conclusion['confidence']}.",
                    f"- Uncertainty: {conclusion['uncertainty']}",
                    "",
                )
            )
        else:
            failure = outputs["racio"]["failure"]
            lines.extend(
                (
                    "- Status: rejected.",
                    f"- Failure code: `{failure['failure_code']}`.",
                    f"- Validation stage: `{failure['validation_stage']}`.",
                    f"- Final JSON SHA-256: "
                    f"`{failure.get('final_json_sha256', 'not_available')}`.",
                    "- accepted=false; retry=0; fallback=0.",
                    "",
                )
            )
        emocio = outputs["emocio"]
        if emocio is None or outputs["instinkt"] is None:
            lines.extend(
                (
                    "### Emocio and Instinkt",
                    "",
                    "Not executed because the sealed policy stops after a "
                    "non-contract Racio provider failure.",
                    "",
                    "### Character outcomes",
                    "",
                    "No replay: a complete frozen bundle was unavailable.",
                    "",
                    "### Human review",
                    "",
                    *_human_review_fields(),
                )
            )
            continue
        lines.extend(
            (
                "### Emocio",
                "",
                f"- Current scene: "
                f"{_render_json_inline(emocio['current_scene'])}.",
                f"- Desired scene: "
                f"{_render_json_inline(emocio['desired_scene'])}.",
                f"- Broken scene: "
                f"{_render_json_inline(emocio['broken_scene'])}.",
                f"- Counterfactual scenes: "
                f"{_render_json_inline(emocio['counterfactual_scenes'])}.",
                f"- Valuation vectors: "
                f"{_render_json_inline(emocio['valuation_vectors'])}.",
                f"- Aggregate scores: "
                f"{_render_json_inline(emocio['aggregate_scores'])}.",
                f"- Selected option: `{emocio['selected_option_id']}`.",
                f"- Abstains: {str(emocio['abstains']).lower()}.",
                f"- Tied options: "
                f"{_render_json_inline(emocio['tied_option_ids'])}.",
                f"- Signature distinction: "
                f"{str(emocio['signature_distinction']).lower()}.",
                f"- Valuation distinction: "
                f"{str(emocio['valuation_distinction']).lower()}.",
                f"- Policy distinction: "
                f"{str(emocio['policy_distinction']).lower()}.",
                f"- Failure marker: `{emocio['failure_marker']}`.",
                f"- Scene-to-desired / scene-to-broken routes: "
                f"{_render_json_inline(emocio['scene_routes'])}.",
                "",
                "### Instinkt",
                "",
                f"- Starting body state: "
                f"{_render_json_inline(outputs['instinkt']['body_state'])}.",
                f"- Three consequence/effect paths: "
                f"{_render_json_inline(outputs['instinkt']['option_paths'])}.",
                f"- Selected option: "
                f"`{outputs['instinkt']['selected_option_id']}`.",
                f"- Abstains: "
                f"{str(outputs['instinkt']['abstains']).lower()}.",
                f"- Tied options: "
                f"{_render_json_inline(outputs['instinkt']['tied_option_ids'])}.",
                f"- Effect distinction: "
                f"{str(outputs['instinkt']['effect_distinction']).lower()}.",
                f"- Failure marker: "
                f"`{outputs['instinkt']['failure_marker']}`.",
                "",
                "### Comparison",
                "",
                f"- Agreement pattern: "
                f"{_render_json_inline(outputs['agreement_pattern'])}.",
                "",
                "### Character outcomes",
                "",
            )
        )
        if matrix["rows"]:
            lines.extend(
                (
                    "| profile | source minds | mandate | pair conflict | "
                    "two-of-three | spoznanje |",
                    "|---|---|---|---|---|---|",
                )
            )
            for row in matrix["rows"]:
                lines.append(
                    f"| `{row['profile_id']}` | "
                    f"{','.join(row['structural_source_minds'])} | "
                    f"`{row['mandate_option_id']}` | "
                    f"`{row['pair_status']}` | "
                    f"`{row['two_of_three']}` | "
                    f"`{row['spoznanje_status']}` |"
                )
        else:
            lines.append("No replay: a complete frozen bundle was unavailable.")
        lines.extend(("", "### Human review", "", *_human_review_fields()))
    report = "\n".join(lines) + "\n"
    (output_root / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )
    return report


def cold_verify_s2(repository_root: Path) -> Mapping[str, Any]:
    from ..models.emocio import EmocioNativeConclusion
    from ..models.governance import AgreementPattern, GovernanceResolution
    from ..models.instinkt import (
        InstinktNativeConclusion,
        InstinktOptionRollout,
    )
    from ..models.racio import RacioNativeConclusion
    from ..providers.ollama import (
        OllamaRacioFailedOutputDiagnostic,
        OllamaRacioNativeExecution,
        OllamaRacioResponseEvidence,
    )

    output_root = repository_root / OUTPUT_RELATIVE_PATH
    seal, prepared = verify_seal(repository_root)
    ledger = _json(output_root / "call_ledger.json")
    summary = _json(output_root / "summary.json")
    if ledger["actual"]["retries"] != 0 or ledger["actual"]["fallbacks"] != 0:
        raise ValueError("TRIAD-S2 evidence contains retry or fallback")
    if ledger["actual"]["model_calls"] > 4:
        raise ValueError("TRIAD-S2 evidence exceeds four model calls")
    if summary["pre_call_seal_sha256"] != seal["seal_sha256"]:
        raise ValueError("TRIAD-S2 summary cites another seal")
    total_bundles = 0
    total_rows = 0
    accepted = 0
    rejected = 0
    e_distinct = 0
    i_distinct = 0
    for item in prepared:
        case_root = output_root / "cases" / item.case_id
        if not (case_root / "native_outputs.json").exists():
            continue
        calls = _json(case_root / "call_record.json")
        outputs = _json(case_root / "native_outputs.json")
        matrix = _json(case_root / "profile_matrix.json")
        for path, _ in _walk((calls, outputs, matrix)):
            if path and path[-1].casefold() in _PRIVATE_THINKING_KEYS:
                raise ValueError("TRIAD-S2 compact evidence contains private thinking")
        racio_record = ProviderCallRecord.model_validate(
            calls["racio"]["call_record"]
        )
        ensure_call_record_contract(item.racio_call_spec, racio_record)
        if outputs["racio"]["status"] == "accepted":
            accepted += 1
            if calls["racio"]["failed_output_diagnostic"] is not None:
                raise ValueError("Accepted Racio output carries failure diagnostic")
            racio_conclusion = RacioNativeConclusion.model_validate(
                outputs["racio"]["conclusion"]
            )
            racio_evidence = OllamaRacioResponseEvidence.model_validate(
                calls["racio"]["result_evidence"]
            )
            OllamaRacioNativeExecution(
                conclusion=racio_conclusion,
                call_spec=item.racio_call_spec,
                call_record=racio_record,
                reasoning_artifact=racio_evidence,
            )
            racio_conclusion.validate_against(item.racio_packet)
        else:
            rejected += 1
            diagnostic = calls["racio"]["failed_output_diagnostic"]
            if diagnostic is not None:
                failed_output = OllamaRacioFailedOutputDiagnostic.model_validate(
                    diagnostic
                )
                if failed_output.accepted is not False:
                    raise ValueError("Rejected Racio diagnostic is not accepted=false")
                if (
                    failed_output.final_json_sha256
                    != outputs["racio"]["failure"]["final_json_sha256"]
                ):
                    raise ValueError("Rejected Racio JSON hash differs")
        if outputs["emocio"] is not None:
            visual_state = EmocioVisualState.model_validate(
                outputs["emocio"]["visual_state"]
            )
            emocio_conclusion = EmocioNativeConclusion.model_validate(
                outputs["emocio"]["conclusion"]
            )
            visual_state.validate_against(item.emocio_packet, item.scene)
            emocio_conclusion.validate_against(
                item.emocio_packet,
                visual_state,
            )
            e_distinct += int(outputs["emocio"]["valuation_distinction"])
        if outputs["instinkt"] is not None:
            instinkt_conclusion = InstinktNativeConclusion.model_validate(
                outputs["instinkt"]["conclusion"]
            )
            rollouts = tuple(
                InstinktOptionRollout.model_validate(value)
                for value in outputs["instinkt"]["rollouts"]
            )
            for effect in item.instinkt_effects:
                effect.validate_against(item.instinkt_packet)
            instinkt_conclusion.validate_against(
                item.instinkt_packet,
                item.body_state,
                rollouts,
            )
            i_distinct += int(outputs["instinkt"]["effect_distinction"])
        if outputs["bundle"] is not None:
            bundle = NativeMindBundle.model_validate(outputs["bundle"])
            bundle.validate_packets(
                scene=item.scene,
                racio_packet=item.racio_packet,
                emocio_packet=item.emocio_packet,
                instinkt_packet=item.instinkt_packet,
            )
            if len(matrix["rows"]) != 13:
                raise ValueError("Completed TRIAD-S2 bundle lacks 13 replay rows")
            if matrix["native_processor_executions_during_replay"] != 0:
                raise ValueError("Character replay executed a native processor")
            if matrix["model_calls_during_replay"] != 0:
                raise ValueError("Character replay executed a model")
            agreement = AgreementPattern.model_validate(
                outputs["agreement_pattern"]
            )
            if agreement.native_bundle_id != bundle.bundle_id:
                raise ValueError("Agreement pattern cites another bundle")
            for row in matrix["rows"]:
                governance = GovernanceResolution.model_validate(
                    row["governance"]
                )
                if (
                    governance.native_bundle_id != bundle.bundle_id
                    or governance.native_bundle_hash != bundle.immutable_hash
                ):
                    raise ValueError("Character row cites another bundle")
            total_bundles += 1
            total_rows += len(matrix["rows"])
        elif matrix["rows"]:
            raise ValueError("Incomplete TRIAD-S2 case has replay rows")
    expected = {
        "accepted": accepted,
        "rejected": rejected,
        "e_distinct": e_distinct,
        "i_distinct": i_distinct,
        "bundles": total_bundles,
        "rows": total_rows,
    }
    observed = {
        "accepted": summary["racio"]["accepted"],
        "rejected": summary["racio"]["rejected"],
        "e_distinct": summary["emocio_valuation_distinguishable"],
        "i_distinct": summary["instinkt_effect_distinguishable"],
        "bundles": summary["complete_frozen_bundles"],
        "rows": summary["character_replay_rows"],
    }
    if expected != observed:
        raise ValueError("TRIAD-S2 compact summary differs from cold evidence")
    observed_report = (output_root / "report.md").read_text(encoding="utf-8")
    expected_report = render_report(repository_root, summary)
    if observed_report != expected_report:
        raise ValueError("TRIAD-S2 report differs from cold projection")
    return summary


__all__ = [
    "EMOCIO_PROVIDER_REVISION",
    "EXECUTION_POLICY",
    "EXPECTED_MODEL_DIGEST",
    "INSTINKT_MAPPER_REVISION",
    "MODEL_PROFILE",
    "OUTPUT_RELATIVE_PATH",
    "PreparedS2Case",
    "ResearchEmocioExecution",
    "build_provider",
    "cold_verify_s2",
    "compile_s2_emocio_counterfactuals",
    "execute_research_emocio_once",
    "execute_s2",
    "map_s2_instinkt_effects",
    "model_free_projection",
    "prepare_cases",
    "render_report",
    "seal_s2",
    "verify_seal",
]
