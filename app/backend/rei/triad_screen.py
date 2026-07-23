"""Bounded TRIAD-S1 development-screen preparation, execution, and replay."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping

from pydantic import BaseModel

from .emocio.packets import build_emocio_packet
from .emocio.processor import DeterministicEmocioProcessor
from .governance.profiles import parse_character_profile
from .governance.resolver import assess_agreement_pattern, resolve_governance
from .ids import canonical_json_bytes, content_id, sha256_hex, utc_now
from .instinkt.effect_compiler import compile_prediction_to_option_body_effect
from .instinkt.effect_mapper import RuleBasedEmbodiedCueInterpreter
from .instinkt.packets import build_instinkt_packet
from .models.character import CHARACTER_PROFILE_ORDER
from .models.emocio import EmocioWorld
from .models.instinkt import (
    BodyState,
    InstinktCueEvidenceBinding,
    InstinktCueEvidenceCitation,
    InstinktSimulationConfig,
    InstinktWorld,
)
from .models.racio import RacioConsequence, RacioWorld
from .models.run import NativeMindBundle
from .models.scene import DecisionOption, EvidenceItem, SceneEvent
from .providers.deterministic import (
    DeterministicEmocioNativeProvider,
    DeterministicInstinktNativeProvider,
)
from .providers.native import SystemExecutionClock
from .racio.packets import build_racio_packet
from .racio.text_reasoner_adapter import RACIO_STRUCTURED_INSTRUCTION_EN


EXPECTED_CASE_IDS: Final = (
    "factory_overtemperature",
    "family_relocation",
    "imperfect_product_launch",
    "loan_to_friend",
    "unstable_slope_rescue",
    "public_credit_conflict",
    "spontaneous_trip",
    "ambiguous_silence",
)
EXPECTED_MODEL_DIGEST: Final = (
    "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7"
)
MODEL_PROFILE: Final[dict[str, Any]] = {
    "model": "gemma4:31b",
    "expected_digest": EXPECTED_MODEL_DIGEST,
    "seed": 314159,
    "temperature": 0.0,
    "top_p": 0.95,
    "top_k": 64,
    "num_ctx": 65536,
    "num_gpu": 999,
    "retry": 0,
    "fallback": "none",
    "thinking_persisted": False,
    "require_full_gpu": True,
}
PROVIDER_REVISION: Final = "rei-native-ollama-racio-en-triad-screen-v1"
SCREEN_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-response-screen-v1-2026-07-23"
)

_LEAKAGE_KEYS: Final = frozenset(
    {
        "expected_option_id",
        "expected_action",
        "expected_motive",
        "leading_mind",
        "character",
        "character_profile",
        "governance_tier",
        "gold_route",
    }
)
_LEADING_OPTION_TEXT: Final = re.compile(
    r"\b(safest|most safe|most reasonable|most desirable|"
    r"best option|preferred option|should choose|correct option)\b",
    re.IGNORECASE,
)
_SLOVENE_FREE_TEXT: Final = re.compile(
    r"[čšžČŠŽ]|\b("
    r"bližnj|čakanje|družin|izberi|izgub|lahko|možnost|nadaljuj|"
    r"neznan|ni znano|odloč|ostani|poboč|poškodb|preveri|proračun|"
    r"selitev|senzor|sporočil|strošek|temperatur|zavrni|zaslug"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PreparedTriadCase:
    case_id: str
    source: Mapping[str, Any]
    operational: Mapping[str, Any]
    scene: SceneEvent
    racio_world: RacioWorld
    racio_packet: Any
    emocio_world: EmocioWorld
    emocio_packet: Any
    body_state: BodyState
    instinkt_world: InstinktWorld
    instinkt_packet: Any
    instinkt_ruleset: Any
    instinkt_predictions: tuple[Any, ...]
    instinkt_compilations: tuple[Any, ...]
    instinkt_effects: tuple[Any, ...]
    instinkt_config: InstinktSimulationConfig


def _json_value(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _model_from_json(model_type: Any, value: Any) -> Any:
    return model_type.model_validate_json(
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
        default=lambda item: item.isoformat(),
    )
    path.write_text(rendered + "\n", encoding="utf-8", newline="\n")


def _model_json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", round_trip=True)
    if dataclasses.is_dataclass(value):
        return {
            field.name: _model_json(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _model_json(child) for key, child in value.items()}
    if isinstance(value, list | tuple):
        return [_model_json(child) for child in value]
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(value: Any, *, path: tuple[str, ...] = ()):
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, path=(*path, str(key)))
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            yield from _walk(child, path=(*path, str(index)))


def _ids(items: list[Mapping[str, Any]], field: str) -> tuple[str, ...]:
    return tuple(str(item[field]) for item in items)


def _validate_projection_pair(case: Mapping[str, Any]) -> None:
    source = case["canonical_sl"]
    operational = case["operational_en"]
    if source["language"] != "sl" or operational["language"] != "en":
        raise ValueError("Corpus projections must declare exact sl/en languages")
    if source["event_id"] != operational["event_id"]:
        raise ValueError("SL and EN event IDs differ")
    for collection, identifier_fields in (
        ("evidence", ("claim_id", "evidence_id", "modality")),
        ("options", ("option_id",)),
        ("constraints", ("constraint_id",)),
        ("unknowns", ("unknown_id",)),
    ):
        left = source[collection]
        right = operational[collection]
        if len(left) != len(right):
            raise ValueError(f"SL and EN {collection} counts differ")
        for field in identifier_fields:
            if _ids(left, field) != _ids(right, field):
                raise ValueError(f"SL and EN {collection}.{field} scopes differ")
    if tuple(source["actors"]) != tuple(operational["actors"]):
        raise ValueError("SL and EN actor scopes differ")


def validate_corpus(corpus: Mapping[str, Any]) -> None:
    """Model-free structure, language, scope, and leakage audit."""

    if corpus.get("schema_version") != "triad-response-screen-corpus-v1":
        raise ValueError("Unsupported TRIAD-S1 corpus schema")
    cases = corpus.get("cases")
    if not isinstance(cases, list):
        raise ValueError("TRIAD-S1 corpus cases must be a list")
    case_ids = tuple(item.get("case_id") for item in cases)
    if case_ids != EXPECTED_CASE_IDS or corpus.get("case_count") != 8:
        raise ValueError("TRIAD-S1 corpus must contain the exact ordered eight cases")
    if (
        corpus.get("source_of_truth") != "canonical_sl"
        or corpus.get("projection_method") != "manually_written_operational_en"
        or corpus.get("untouched_holdout") is not False
        or corpus.get("promotion_evidence") is not False
        or corpus.get("training_data") is not False
    ):
        raise ValueError("TRIAD-S1 corpus status declarations are incomplete")

    for case in cases:
        _validate_projection_pair(case)
        for path, value in _walk(case):
            if path and path[-1].casefold() in _LEAKAGE_KEYS:
                raise ValueError(f"Processor-facing leakage key found: {'.'.join(path)}")
            if isinstance(value, str) and _LEADING_OPTION_TEXT.search(value):
                raise ValueError(f"Leading option text found: {'.'.join(path)}")
        for path, value in _walk(case["operational_en"]):
            if isinstance(value, str) and _SLOVENE_FREE_TEXT.search(value):
                raise ValueError(
                    f"Operational English contains Slovene free text: {'.'.join(path)}"
                )
        if case["emocio_input"].get("mode") != "structured_only":
            raise ValueError("TRIAD-S1 Emocio must be structured_only")
        if "renderer" in case["emocio_input"] or "image_model" in case["emocio_input"]:
            raise ValueError("TRIAD-S1 Emocio input cannot request image generation")


def _scene_from_projection(case_id: str, projection: Mapping[str, Any]) -> SceneEvent:
    evidence = tuple(
        EvidenceItem(
            evidence_id=item["evidence_id"],
            modality=item["modality"],
            content=item["content"],
            grounded=True,
            source_ref=f"triad-s1:{case_id}:{item['claim_id']}",
            confidence=1.0,
            provenance_kind="supplied",
        )
        for item in projection["evidence"]
    )
    options = tuple(
        DecisionOption(
            option_id=item["option_id"],
            label=item["label"],
            description=item["description"],
        )
        for item in projection["options"]
    )
    return SceneEvent(
        event_id=projection["event_id"],
        raw_input=projection["raw_input"],
        language=projection["language"],
        evidence=evidence,
        options=options,
        actors=tuple(projection["actors"]),
        constraints=tuple(item["text"] for item in projection["constraints"]),
        unknowns=tuple(item["text"] for item in projection["unknowns"]),
    )


def _racio_world(case_id: str, source: Mapping[str, Any]) -> RacioWorld:
    payload = {
        "schema_version": "rei-native-racio-world-v1",
        **{key: tuple(value) for key, value in source.items()},
    }
    return RacioWorld(
        world_id=content_id(f"racio_{case_id[:12]}", payload),
        **payload,
    )


def _emocio_world(case_id: str, source: Mapping[str, Any]) -> EmocioWorld:
    payload = {
        "schema_version": "rei-native-emocio-world-v1",
        **{key: tuple(value) for key, value in source.items()},
    }
    return EmocioWorld(
        world_id=content_id(f"emocio_{case_id[:11]}", payload),
        **payload,
    )


def _body_state(case_id: str, source: Mapping[str, Any]) -> BodyState:
    payload = {
        "schema_version": "rei-native-body-state-v1",
        **source,
    }
    return BodyState(
        body_state_id=content_id(f"body_{case_id[:14]}", payload),
        **payload,
    )


def _cue_binding(
    *,
    scene: SceneEvent,
    source: Mapping[str, Any],
) -> InstinktCueEvidenceBinding:
    evidence = next(
        item for item in scene.evidence if item.evidence_id == source["evidence_id"]
    )
    cited_text = source["cited_text"]
    start = evidence.content.casefold().find(cited_text.casefold())
    if start < 0:
        raise ValueError("Instinkt cited text is absent from its evidence")
    exact = evidence.content[start : start + len(cited_text)]
    citation = InstinktCueEvidenceCitation.create(
        evidence=evidence,
        start_char=start,
        end_char=start + len(cited_text),
    )
    return InstinktCueEvidenceBinding.create(
        lane=source["lane"],
        cue_class=source["cue_class"],
        cue=exact,
        assertion_status="asserted_positive",
        citations=(citation,),
    )


def prepare_case(case: Mapping[str, Any]) -> PreparedTriadCase:
    case_id = str(case["case_id"])
    source = case["canonical_sl"]
    operational = case["operational_en"]
    scene = _scene_from_projection(case_id, operational)
    racio_world = _racio_world(case_id, case["racio_input"]["world"])
    consequences = tuple(
        RacioConsequence.model_validate(item)
        for item in case["racio_input"]["explicit_consequences"]
    )
    racio_packet = build_racio_packet(
        scene,
        racio_world,
        symbolic_and_language_cues=(scene.raw_input,),
        numeric_cues=tuple(case["racio_input"]["numeric_cues"]),
        time=tuple(case["racio_input"]["time"]),
        rules=tuple(case["racio_input"]["rules"]),
        explicit_consequences=consequences,
    )
    emocio_world = _emocio_world(case_id, case["emocio_input"]["world"])
    emocio_packet = build_emocio_packet(scene)
    body_state = _body_state(case_id, case["instinkt_input"]["body_state"])
    instinkt_world = InstinktWorld.create()
    bindings = tuple(
        _cue_binding(scene=scene, source=item)
        for item in case["instinkt_input"]["cue_bindings"]
    )
    lane_values: dict[str, tuple[str, ...]] = {
        "physical_cues": (),
        "uncertainty_cues": (),
        "trust_cues": (),
        "boundary_cues": (),
        "attachment_cues": (),
        "scarcity_cues": (),
        "escape_cues": (),
        "explicit_body_cues": (),
    }
    for binding in bindings:
        lane_values[binding.lane] = (
            *lane_values[binding.lane],
            binding.cue,
        )
    instinkt_packet = build_instinkt_packet(
        scene,
        body_state,
        **lane_values,
        evidence_ids=tuple(
            sorted(
                {
                    evidence_id
                    for binding in bindings
                    for evidence_id in binding.evidence_ids
                }
            )
        ),
        cue_evidence_bindings=bindings,
    )
    mapper = RuleBasedEmbodiedCueInterpreter()
    predictions = tuple(
        mapper.infer_effects(
            scene,
            instinkt_packet,
            instinkt_world,
            body_state,
            option,
        )
        for option in sorted(scene.options, key=lambda item: item.option_id)
    )
    if any(item.abstains for item in predictions):
        abstained = tuple(item.option_id for item in predictions if item.abstains)
        raise ValueError(f"Instinkt typed routing abstained for options={abstained}")
    option_by_id = {item.option_id: item for item in scene.options}
    compilations = tuple(
        compile_prediction_to_option_body_effect(
            prediction=prediction,
            scene=scene,
            packet=instinkt_packet,
            world=instinkt_world,
            body=body_state,
            option=option_by_id[prediction.option_id],
            ruleset=mapper.ruleset,
        )
        for prediction in predictions
    )
    config = InstinktSimulationConfig.create()
    return PreparedTriadCase(
        case_id=case_id,
        source=source,
        operational=operational,
        scene=scene,
        racio_world=racio_world,
        racio_packet=racio_packet,
        emocio_world=emocio_world,
        emocio_packet=emocio_packet,
        body_state=body_state,
        instinkt_world=instinkt_world,
        instinkt_packet=instinkt_packet,
        instinkt_ruleset=mapper.ruleset,
        instinkt_predictions=predictions,
        instinkt_compilations=compilations,
        instinkt_effects=tuple(item.option_body_effect for item in compilations),
        instinkt_config=config,
    )


def prepare_corpus(corpus: Mapping[str, Any]) -> tuple[PreparedTriadCase, ...]:
    validate_corpus(corpus)
    prepared = tuple(prepare_case(case) for case in corpus["cases"])
    if tuple(item.case_id for item in prepared) != EXPECTED_CASE_IDS:
        raise ValueError("Prepared TRIAD-S1 case order changed")
    return prepared


def _inputs_projection(item: PreparedTriadCase) -> dict[str, Any]:
    return {
        "schema_version": "triad-response-screen-inputs-v1",
        "case_id": item.case_id,
        "source": {
            "canonical_sl": item.source,
            "operational_en": item.operational,
        },
        "public_option_scope": tuple(
            option.option_id for option in item.scene.options
        ),
        "racio": {
            "scene": _model_json(item.scene),
            "world": _model_json(item.racio_world),
            "packet": _model_json(item.racio_packet),
            "instruction_sha256": sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN),
        },
        "emocio": {
            "mode": "structured_only",
            "world": _model_json(item.emocio_world),
            "packet": _model_json(item.emocio_packet),
            "renderer": None,
            "image_model_calls": 0,
        },
        "instinkt": {
            "effect_source": "rule_based",
            "world": _model_json(item.instinkt_world),
            "body_state": _model_json(item.body_state),
            "packet": _model_json(item.instinkt_packet),
            "ruleset": _model_json(item.instinkt_ruleset),
            "predictions": [_model_json(value) for value in item.instinkt_predictions],
            "compilations": [
                _model_json(value) for value in item.instinkt_compilations
            ],
            "simulation_config": _model_json(item.instinkt_config),
            "model_mapper_calls": 0,
        },
        "profile_blind": True,
    }


def prepare_pre_call_screen(repository_root: Path) -> Mapping[str, Any]:
    """Freeze the authored corpus and every processor-facing input before calls."""

    screen_root = repository_root / SCREEN_RELATIVE_PATH
    corpus_path = screen_root / "corpus.json"
    corpus = _json_value(corpus_path)
    prepared = prepare_corpus(corpus)
    input_records: list[dict[str, Any]] = []
    for item in prepared:
        path = screen_root / "cases" / item.case_id / "inputs.json"
        projection = _inputs_projection(item)
        _write_json(path, projection)
        input_records.append(
            {
                "case_id": item.case_id,
                "path": path.relative_to(repository_root).as_posix(),
                "sha256": _file_sha256(path),
                "racio_packet_id": item.racio_packet.packet_id,
                "emocio_packet_id": item.emocio_packet.packet_id,
                "instinkt_packet_id": item.instinkt_packet.packet_id,
            }
        )

    manifest_payload = {
        "schema_version": "triad-response-screen-corpus-manifest-v1",
        "phase": "TRIAD-S1",
        "corpus_path": corpus_path.relative_to(repository_root).as_posix(),
        "corpus_sha256": _file_sha256(corpus_path),
        "case_order": EXPECTED_CASE_IDS,
        "input_records": input_records,
        "corpus_status": {
            "frozen_before_calls": True,
            "untouched_holdout": False,
            "promotion_evidence": False,
            "training_data": False,
        },
    }
    manifest = {
        **manifest_payload,
        "manifest_sha256": sha256_hex(manifest_payload),
    }
    _write_json(screen_root / "corpus_manifest.json", manifest)

    expected_entries = [
        {
            "ordinal": index,
            "case_id": case_id,
            "expected_model_calls": 1,
            "expected_retries": 0,
            "expected_fallbacks": 0,
            "status": "planned",
        }
        for index, case_id in enumerate(EXPECTED_CASE_IDS, start=1)
    ]
    ledger = {
        "schema_version": "triad-response-screen-call-ledger-v1",
        "phase": "TRIAD-S1",
        "expected": {
            "model_calls": 8,
            "retries": 0,
            "fallbacks": 0,
        },
        "actual": {
            "model_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "entries": expected_entries,
        "state": "sealed_before_calls",
    }
    _write_json(screen_root / "call_ledger.json", ledger)

    seal_payload = {
        "schema_version": "triad-response-screen-pre-call-seal-v1",
        "phase": "TRIAD-S1",
        "sealed_at": utc_now()
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "corpus_manifest_sha256": _file_sha256(
            screen_root / "corpus_manifest.json"
        ),
        "case_input_sha256": {
            item["case_id"]: item["sha256"] for item in input_records
        },
        "public_option_scope": {
            item.case_id: tuple(
                option.option_id for option in item.scene.options
            )
            for item in prepared
        },
        "model_profile": MODEL_PROFILE,
        "provider_revision": PROVIDER_REVISION,
        "instruction_sha256": sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN),
        "expected_call_ledger": {
            "model_calls": 8,
            "retries": 0,
            "fallbacks": 0,
            "case_order": EXPECTED_CASE_IDS,
        },
        "declarations": {
            "corpus_frozen_before_calls": True,
            "development_screen": True,
            "untouched_holdout": False,
            "promotion_evidence": False,
            "training_data": False,
        },
    }
    seal = {**seal_payload, "seal_sha256": sha256_hex(seal_payload)}
    _write_json(screen_root / "pre_call_seal.json", seal)
    return seal


def verify_pre_call_screen(repository_root: Path) -> tuple[PreparedTriadCase, ...]:
    screen_root = repository_root / SCREEN_RELATIVE_PATH
    corpus_path = screen_root / "corpus.json"
    manifest_path = screen_root / "corpus_manifest.json"
    seal_path = screen_root / "pre_call_seal.json"
    corpus = _json_value(corpus_path)
    manifest = _json_value(manifest_path)
    seal = _json_value(seal_path)
    manifest_payload = {
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    }
    if manifest["manifest_sha256"] != sha256_hex(manifest_payload):
        raise ValueError("Corpus manifest hash is invalid")
    if manifest["corpus_sha256"] != _file_sha256(corpus_path):
        raise ValueError("Sealed corpus bytes changed")
    if seal["corpus_manifest_sha256"] != _file_sha256(manifest_path):
        raise ValueError("Sealed corpus manifest bytes changed")
    seal_payload = {key: value for key, value in seal.items() if key != "seal_sha256"}
    if seal["seal_sha256"] != sha256_hex(seal_payload):
        raise ValueError("Pre-call seal hash is invalid")
    prepared = prepare_corpus(corpus)
    for item in manifest["input_records"]:
        path = repository_root / item["path"]
        if _file_sha256(path) != item["sha256"]:
            raise ValueError(f"Sealed case input changed: {item['case_id']}")
        if seal["case_input_sha256"][item["case_id"]] != item["sha256"]:
            raise ValueError(f"Seal and manifest disagree: {item['case_id']}")
    if seal["model_profile"] != MODEL_PROFILE:
        raise ValueError("Sealed model profile differs from TRIAD-S1 contract")
    if seal["provider_revision"] != PROVIDER_REVISION:
        raise ValueError("Sealed provider revision differs from TRIAD-S1 contract")
    return prepared


def summarize_agreements(bundles: tuple[NativeMindBundle, ...]) -> Mapping[str, int]:
    counts = Counter(assess_agreement_pattern(bundle).agreement_kind for bundle in bundles)
    return {
        "unanimous": counts["unanimous"],
        "majority": counts["majority"],
        "all_different": counts["all_different"],
        "incomplete": counts["incomplete"],
    }


def replay_profiles(bundle: NativeMindBundle) -> tuple[Any, ...]:
    """Resolve all 13 profiles without invoking a native processor or model."""

    frozen_hash = bundle.immutable_hash
    rows = []
    for profile_id in CHARACTER_PROFILE_ORDER:
        character = parse_character_profile(
            profile_id,
            character_id=content_id(
                "triad_character",
                {"bundle_id": bundle.bundle_id, "profile_id": profile_id},
            ),
        )
        governance = resolve_governance(bundle, character)
        rows.append(governance)
        if bundle.immutable_hash != frozen_hash:
            raise ValueError("Character replay mutated the frozen native bundle")
    return tuple(rows)


def _call_record_projection(
    *,
    request_payload: Mapping[str, Any],
    racio_execution: Any,
    emocio_execution: Any,
    instinkt_execution: Any,
) -> dict[str, Any]:
    return {
        "schema_version": "triad-response-screen-call-record-v1",
        "status": "complete",
        "racio": {
            "request_payload": request_payload,
            "call_spec": _model_json(racio_execution.call_spec),
            "call_record": _model_json(racio_execution.call_record),
            "result_evidence": _model_json(racio_execution.reasoning_artifact),
            "retries": 0,
            "fallbacks": 0,
        },
        "emocio": {
            "call_spec": _model_json(emocio_execution.call_spec),
            "call_record": _model_json(emocio_execution.call_record),
            "uses_model": False,
        },
        "instinkt": {
            "call_spec": _model_json(instinkt_execution.call_spec),
            "call_record": _model_json(instinkt_execution.call_record),
            "uses_model": False,
        },
        "private_thinking_persisted": False,
    }


def _native_output_projection(
    *,
    item: PreparedTriadCase,
    bundle: NativeMindBundle,
    agreement: Any,
    racio_execution: Any,
    emocio_execution: Any,
    instinkt_execution: Any,
) -> dict[str, Any]:
    return {
        "schema_version": "triad-response-screen-native-outputs-v1",
        "status": "complete",
        "case_id": item.case_id,
        "processor_execution_counts": {"R": 1, "E": 1, "I": 1},
        "bundle": _model_json(bundle),
        "agreement_pattern": _model_json(agreement),
        "racio": {
            "conclusion": _model_json(racio_execution.conclusion),
            "lineage": {
                "source_packet_id": item.racio_packet.packet_id,
                "provider_result_id": racio_execution.reasoning_artifact.result_id,
                "conclusion_id": racio_execution.conclusion.conclusion_id,
            },
        },
        "emocio": {
            "mode": "structured_only",
            "conclusion": _model_json(emocio_execution.conclusion),
            "visual_state": _model_json(emocio_execution.visual_state),
            "policy": _model_json(emocio_execution.processing.policy),
            "stage_order": emocio_execution.processing.stage_order,
            "rendered_images": [],
            "lineage": {
                "source_packet_id": item.emocio_packet.packet_id,
                "intermediate_visual_state_id": (
                    emocio_execution.visual_state.visual_state_id
                ),
                "conclusion_id": emocio_execution.conclusion.conclusion_id,
            },
        },
        "instinkt": {
            "effect_source": "rule_based",
            "conclusion": _model_json(instinkt_execution.conclusion),
            "predictions": [
                _model_json(value) for value in item.instinkt_predictions
            ],
            "compilations": [
                _model_json(value) for value in item.instinkt_compilations
            ],
            "option_effects": [
                _model_json(value) for value in instinkt_execution.option_effects
            ],
            "rollouts": [
                _model_json(value) for value in instinkt_execution.rollouts
            ],
            "policy": _model_json(instinkt_execution.processing.policy),
            "simulation_config": _model_json(instinkt_execution.config),
            "lineage": {
                "source_packet_id": item.instinkt_packet.packet_id,
                "prediction_ids": tuple(
                    value.prediction_id for value in item.instinkt_predictions
                ),
                "rollout_ids": tuple(
                    value.rollout_id for value in instinkt_execution.rollouts
                ),
                "conclusion_id": instinkt_execution.conclusion.conclusion_id,
            },
        },
    }


def _profile_projection(
    *,
    case_id: str,
    bundle: NativeMindBundle,
    governance_rows: tuple[Any, ...],
) -> dict[str, Any]:
    return {
        "schema_version": "triad-response-screen-profile-matrix-v1",
        "status": "complete",
        "case_id": case_id,
        "native_bundle_id": bundle.bundle_id,
        "native_bundle_hash": bundle.immutable_hash,
        "profile_order": CHARACTER_PROFILE_ORDER,
        "native_processor_executions": 0,
        "model_calls": 0,
        "rows": [
            {
                "profile_id": row.profile_id,
                "structural_source_minds": row.mandate.structural_source_minds,
                "selected_mandate_option": row.mandate.option_id,
                "governance_status": row.mandate.status,
                "unresolved_pair_conflict": (
                    row.pair_conflict is not None
                    and row.pair_conflict.status == "unresolved"
                ),
                "two_of_three_result": (
                    row.mandate.option_id
                    if row.profile_id == "R=E=I"
                    and row.agreement_pattern.agreement_kind
                    in {"unanimous", "majority"}
                    else None
                ),
                "simulated_spoznanje_status": row.spoznanje_status,
                "governance": _model_json(row),
            }
            for row in governance_rows
        ],
    }


def _json_code(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _md_list(values: list[str] | tuple[str, ...]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- None"


def _human_rubric() -> str:
    blocks = []
    for mind in ("Racio", "Emocio", "Instinkt"):
        blocks.append(
            f"""#### {mind} route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________"""
        )
    return "\n\n".join(blocks)


def render_report(
    *,
    repository_root: Path,
    prepared: tuple[PreparedTriadCase, ...],
    summary: Mapping[str, Any],
) -> str:
    screen_root = repository_root / SCREEN_RELATIVE_PATH
    lines = [
        "# TRIAD-S1 — native mind response development screen",
        "",
        "Research-only development screen. This is not a G4 holdout, model "
        "promotion evidence, or training data.",
        "",
        f"- Pre-call seal: `{summary['pre_call_seal_sha256']}`",
        f"- Exact model digest: `{summary['model_digest']}`",
        f"- Model calls / retries / fallbacks: "
        f"`{summary['model_calls']} / {summary['retries']} / "
        f"{summary['fallbacks']}`",
        f"- Executed cases: `{summary['executed_cases']}/8`",
        f"- Native conclusions: `{summary['native_conclusions']}/24`",
        f"- Character replay rows: `{summary['character_replay_rows']}/104`",
        "",
        "The corpus was frozen before model calls. It is a development corpus, "
        "not an untouched holdout, not promotion evidence, and not training data.",
        "",
        "Emocio response was tested after structured scene routing. This does "
        "not validate image-native visual cognition.",
        "",
        "Instinkt response was tested after typed cue routing. This does not "
        "validate raw-scene Instinkt perception.",
        "",
        "No global REI score is computed. GovernanceMandate is the primary "
        "character-replay result; no downstream output is treated as evidence "
        "of Racio translation quality.",
    ]
    if summary.get("validation_events"):
        lines.extend(["", "## Validation event log", ""])
        for event in summary["validation_events"]:
            lines.append(
                f"- `{event['event_id']}` — {event['status']}: {event['detail']}"
            )
    for item in prepared:
        case_root = screen_root / "cases" / item.case_id
        inputs = _json_value(case_root / "inputs.json")
        outputs = _json_value(case_root / "native_outputs.json")
        matrix = _json_value(case_root / "profile_matrix.json")
        calls = _json_value(case_root / "call_record.json")
        source = inputs["source"]
        if outputs.get("status") != "complete":
            lines.extend(
                [
                    "",
                    f"## {item.case_id}",
                    "",
                    "### SOURCE",
                    "",
                    "#### Canonical Slovenian",
                    "",
                    source["canonical_sl"]["raw_input"],
                    "",
                    "#### Operational English sealed for Racio",
                    "",
                    source["operational_en"]["raw_input"],
                    "",
                    "### EXECUTION FAILURE",
                    "",
                    f"- Status: `{outputs['status']}`",
                    f"- Failure type: `{outputs.get('failure_type', 'unknown')}`",
                    f"- Failure: {outputs.get('failure', 'No detail recorded.')}",
                    f"- Observed conclusion IDs: "
                    f"`{outputs.get('observed_conclusion_ids', [])}`",
                    "- No native bundle or character replay is claimed for this case.",
                    "",
                    "### HUMAN-REVIEW RUBRIC",
                    "",
                    _human_rubric(),
                ]
            )
            continue
        racio = outputs["racio"]["conclusion"]
        emocio = outputs["emocio"]
        instinkt = outputs["instinkt"]
        agreement = outputs["agreement_pattern"]
        lines.extend(
            [
                "",
                f"## {item.case_id}",
                "",
                "### SOURCE",
                "",
                "#### Canonical Slovenian",
                "",
                source["canonical_sl"]["raw_input"],
                "",
                "#### Operational English sent to Racio",
                "",
                source["operational_en"]["raw_input"],
                "",
                "#### Grounded facts",
                "",
                _md_list(
                    [
                        f"`{value['evidence_id']}` — {value['content']}"
                        for value in source["operational_en"]["evidence"]
                    ]
                ),
                "",
                "#### Explicit unknowns",
                "",
                _md_list(
                    [
                        f"`{value['unknown_id']}` — {value['text']}"
                        for value in source["operational_en"]["unknowns"]
                    ]
                ),
                "",
                "#### Public options",
                "",
                _md_list(
                    [
                        f"`{value['option_id']}` — {value['label']}: "
                        f"{value['description']}"
                        for value in source["operational_en"]["options"]
                    ]
                ),
                "",
                "### RACIO",
                "",
                "#### Exact model input",
                "",
                "System instruction:",
                "",
                "```text",
                calls["racio"]["request_payload"]["system"],
                "```",
                "",
                "Prompt:",
                "",
                "```json",
                _json_code(
                    json.loads(calls["racio"]["request_payload"]["prompt"])
                ),
                "```",
                "",
                f"- Selected option: `{racio['option_id']}`",
                f"- Abstains: `{racio['abstains']}`",
                f"- Facts used: `{racio['facts_used']}`",
                f"- Evidence IDs used: `{racio['evidence_ids_used']}`",
                f"- Unknowns retained: `{racio['unknowns']}`",
                f"- Causal sequence: `{racio['causal_sequence']}`",
                f"- Utility structure: `{racio['utility_structure']}`",
                f"- Explicit goal: {racio['explicit_goal']}",
                f"- Main objection: {racio['main_objection']}",
                f"- Confidence: `{racio['confidence']}`",
                f"- Uncertainty: {racio['uncertainty']}",
                f"- Call evidence: `{calls['racio']['call_record']['call_id']}`",
                f"- Result evidence: "
                f"`{calls['racio']['result_evidence']['result_id']}`",
                "",
                "### EMOCIO",
                "",
                "```json",
                _json_code(
                    {
                        "current_scene": emocio["visual_state"]["current_scene"],
                        "desired_scene": emocio["visual_state"]["desired_scene"],
                        "broken_scene": emocio["visual_state"]["broken_scene"],
                        "option_rollouts": emocio["visual_state"]["option_rollouts"],
                        "option_valuations": (
                            emocio["visual_state"]["option_valuations"]
                        ),
                    }
                ),
                "```",
                "",
                f"- Selected option: `{emocio['conclusion']['option_id']}`",
                f"- Abstains: `{emocio['conclusion']['abstains']}`",
                f"- Desired transformation: "
                f"{emocio['conclusion']['desired_transformation']}",
                f"- Main obstacle: {emocio['conclusion']['main_obstacle']}",
                f"- Uncertainty: {emocio['conclusion']['uncertainty']}",
                "",
                "### INSTINKT",
                "",
                "```json",
                _json_code(
                    {
                        "starting_body_state": inputs["instinkt"]["body_state"],
                        "grounded_cue_bindings": inputs["instinkt"]["packet"].get(
                            "cue_evidence_bindings", []
                        ),
                        "predicted_option_effects": instinkt["option_effects"],
                        "body_rollouts": instinkt["rollouts"],
                        "protective_policy": instinkt["policy"],
                    }
                ),
                "```",
                "",
                f"- Decisive rollout: "
                f"`{instinkt['conclusion']['decisive_rollout_id']}`",
                f"- Selected option: `{instinkt['conclusion']['option_id']}`",
                f"- Abstains: `{instinkt['conclusion']['abstains']}`",
                f"- Dominant alarm: {instinkt['conclusion']['dominant_alarm']}",
                f"- Minimum safety condition: "
                f"{instinkt['conclusion']['minimum_safety_condition']}",
                f"- Uncertainty: {instinkt['conclusion']['uncertainty']}",
                "",
                "### COMPARISON",
                "",
                f"- R / E / I option IDs: `{racio['option_id']}` / "
                f"`{emocio['conclusion']['option_id']}` / "
                f"`{instinkt['conclusion']['option_id']}`",
                f"- Agreement pattern: `{agreement['agreement_kind']}`",
                f"- Same option / different route: human review required; native "
                f"lineage remains separate.",
                f"- All different: "
                f"`{agreement['agreement_kind'] == 'all_different'}`",
                f"- Abstentions: R=`{racio['abstains']}`, "
                f"E=`{emocio['conclusion']['abstains']}`, "
                f"I=`{instinkt['conclusion']['abstains']}`",
                "- Possible route contamination: no cross-mind or character input "
                "was admitted by the model-free contract; semantic contamination "
                "remains for human review.",
                "- Unsupported inference warnings: Racio fact/unknown scope passed "
                "the strict packet validator; Emocio inferred elements and Instinkt "
                "unsupported dimensions/conflict flags remain visible above.",
                "",
                "### CHARACTER OUTCOMES",
                "",
                "| Profile | Structural source minds | Mandate option | "
                "Unresolved pair | Two-of-three | simulated_spoznanje |",
                "|---|---|---|---:|---|---|",
            ]
        )
        for row in matrix["rows"]:
            lines.append(
                f"| {row['profile_id']} | "
                f"{','.join(row['structural_source_minds'])} | "
                f"{row['selected_mandate_option'] or '—'} | "
                f"{str(row['unresolved_pair_conflict']).lower()} | "
                f"{row['two_of_three_result'] or '—'} | "
                f"{row['simulated_spoznanje_status']} |"
            )
        lines.extend(
            [
                "",
                "### HUMAN-REVIEW RUBRIC",
                "",
                _human_rubric(),
            ]
        )
    report = "\n".join(lines) + "\n"
    (screen_root / "report.md").write_text(
        report, encoding="utf-8", newline="\n"
    )
    return report


def execute_screen(repository_root: Path) -> Mapping[str, Any]:
    """Perform exactly one R/E/I execution per case and 13 profile replays."""

    from .providers.ollama import (
        OllamaApiClient,
        OllamaRacioSettings,
    )
    from .providers.ollama_en import OllamaRacioNativeEnTriadProvider

    prepared = verify_pre_call_screen(repository_root)
    screen_root = repository_root / SCREEN_RELATIVE_PATH
    seal = _json_value(screen_root / "pre_call_seal.json")
    ledger_path = screen_root / "call_ledger.json"
    ledger = _json_value(ledger_path)
    initial_run = ledger["state"] == "sealed_before_calls" and ledger["actual"] == {
        "model_calls": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    resumable_run = (
        ledger["state"] == "executing"
        and ledger["actual"]["retries"] == 0
        and ledger["actual"]["fallbacks"] == 0
        and 0 < ledger["actual"]["model_calls"] < 8
    )
    if not initial_run and not resumable_run:
        raise ValueError("TRIAD-S1 call ledger is neither initial nor resumable")

    settings = OllamaRacioSettings(
        model=MODEL_PROFILE["model"],
        seed=MODEL_PROFILE["seed"],
        temperature=MODEL_PROFILE["temperature"],
        num_ctx=MODEL_PROFILE["num_ctx"],
        num_gpu=MODEL_PROFILE["num_gpu"],
        require_full_gpu=True,
    )
    provider = OllamaRacioNativeEnTriadProvider.discover(
        client=OllamaApiClient(),
        settings=settings,
        expected_digest=EXPECTED_MODEL_DIGEST,
    )
    if provider.runtime.digest != EXPECTED_MODEL_DIGEST:
        raise ValueError("Local model digest changed after exact pre-dispatch check")
    if provider.identity.implementation_revision.split(";", 1)[0] != (
        PROVIDER_REVISION
    ):
        raise ValueError("Active provider revision differs from the pre-call seal")

    emocio_provider = DeterministicEmocioNativeProvider(
        processor=DeterministicEmocioProcessor(cognition_mode="structured_only"),
        publish_runtime_config=True,
    )
    instinkt_provider = DeterministicInstinktNativeProvider()
    clock = SystemExecutionClock()
    bundles: list[NativeMindBundle] = []
    abstentions = Counter()
    failures: list[dict[str, str]] = []
    for item, entry in zip(prepared, ledger["entries"], strict=True):
        case_root = screen_root / "cases" / item.case_id
        if entry["status"] == "succeeded":
            output_path = case_root / "native_outputs.json"
            if not output_path.exists():
                raise ValueError("Succeeded ledger entry lacks native outputs")
            bundle = _model_from_json(
                NativeMindBundle,
                _json_value(output_path)["bundle"],
            )
            bundles.append(bundle)
            abstentions["R"] += int(bundle.racio.abstains)
            abstentions["E"] += int(bundle.emocio.abstains)
            abstentions["I"] += int(bundle.instinkt.abstains)
        elif entry["status"] == "validation_rejected":
            failures.append(
                {
                    "case_id": item.case_id,
                    "failure_type": entry["failure_type"],
                    "failure": entry["failure"],
                }
            )
        elif entry["status"] == "dispatching":
            call_path = case_root / "call_record.json"
            if not call_path.exists():
                raise ValueError(
                    "Interrupted dispatch lacks evidence needed to prevent a retry"
                )
            entry.update(
                {
                    "status": "evidence_projection_failed",
                    "failure_type": "EvidenceProjectionError",
                    "failure": (
                        "Native execution completed once, but compact evidence "
                        "projection failed; model and native processors were not rerun."
                    ),
                    "retries": 0,
                    "fallbacks": 0,
                }
            )
            failures.append(
                {
                    "case_id": item.case_id,
                    "failure_type": entry["failure_type"],
                    "failure": entry["failure"],
                }
            )
            _write_json(ledger_path, ledger)

    for ordinal, item in enumerate(prepared, start=1):
        entry = ledger["entries"][ordinal - 1]
        if entry["status"] != "planned":
            continue
        request_payload = provider.request_payload(item.racio_packet)
        if _SLOVENE_FREE_TEXT.search(str(request_payload["prompt"])):
            raise ValueError("Racio model payload contains Slovene free text")
        racio_spec = provider.build_call_spec(item.racio_packet)
        entry.update(
            {
                "call_id": racio_spec.call_id,
                "provider_id": racio_spec.provider.provider_id,
                "model_digest": provider.runtime.digest,
                "status": "dispatching",
            }
        )
        ledger["actual"]["model_calls"] += 1
        ledger["state"] = "executing"
        _write_json(ledger_path, ledger)
        try:
            racio_execution = provider.execute(
                item.racio_packet,
                call=racio_spec,
                clock=clock,
            )
        except Exception as exc:
            entry.update(
                {
                    "status": "validation_rejected",
                    "failure_type": type(exc).__name__,
                    "failure": str(exc),
                }
            )
            failures.append(
                {
                    "case_id": item.case_id,
                    "failure_type": type(exc).__name__,
                    "failure": str(exc),
                }
            )
            _write_json(ledger_path, ledger)
            continue

        emocio_spec = emocio_provider.build_call_spec(
            item.scene,
            item.emocio_world,
            item.emocio_packet,
        )
        emocio_execution = emocio_provider.execute(
            item.scene,
            item.emocio_world,
            packet=item.emocio_packet,
            call=emocio_spec,
            clock=clock,
        )
        instinkt_spec = instinkt_provider.build_call_spec(
            scene=item.scene,
            packet=item.instinkt_packet,
            source_body_state=item.body_state,
            option_effects=item.instinkt_effects,
            config=item.instinkt_config,
        )
        instinkt_execution = instinkt_provider.execute(
            scene=item.scene,
            packet=item.instinkt_packet,
            source_body_state=item.body_state,
            option_effects=item.instinkt_effects,
            config=item.instinkt_config,
            call=instinkt_spec,
            clock=clock,
        )
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
        for mind, conclusion in (
            ("R", racio_execution.conclusion),
            ("E", emocio_execution.conclusion),
            ("I", instinkt_execution.conclusion),
        ):
            abstentions[mind] += int(conclusion.abstains)
        case_root = screen_root / "cases" / item.case_id
        _write_json(
            case_root / "call_record.json",
            _call_record_projection(
                request_payload=request_payload,
                racio_execution=racio_execution,
                emocio_execution=emocio_execution,
                instinkt_execution=instinkt_execution,
            ),
        )
        _write_json(
            case_root / "native_outputs.json",
            _native_output_projection(
                item=item,
                bundle=bundle,
                agreement=agreement,
                racio_execution=racio_execution,
                emocio_execution=emocio_execution,
                instinkt_execution=instinkt_execution,
            ),
        )
        _write_json(
            case_root / "profile_matrix.json",
            _profile_projection(
                case_id=item.case_id,
                bundle=bundle,
                governance_rows=governance_rows,
            ),
        )
        entry.update(
            {
                "status": "succeeded",
                "result_evidence_id": racio_execution.reasoning_artifact.result_id,
                "conclusion_id": racio_execution.conclusion.conclusion_id,
                "retries": 0,
                "fallbacks": 0,
            }
        )
        _write_json(ledger_path, ledger)

    for item, entry in zip(prepared, ledger["entries"], strict=True):
        if entry["status"] in {"succeeded"}:
            continue
        case_root = screen_root / "cases" / item.case_id
        call_path = case_root / "call_record.json"
        observed_ids: list[str] = []
        if call_path.exists():
            call_projection = _json_value(call_path)
            for mind in ("racio", "emocio", "instinkt"):
                output_ids = (
                    call_projection.get(mind, {})
                    .get("call_record", {})
                    .get("output_artifact_ids", [])
                )
                if output_ids:
                    observed_ids.append(output_ids[-1])
        else:
            _write_json(
                call_path,
                {
                    "schema_version": "triad-response-screen-call-record-v1",
                    "status": entry["status"],
                    "case_id": item.case_id,
                    "call_id": entry.get("call_id"),
                    "failure_type": entry.get("failure_type"),
                    "failure": entry.get("failure"),
                    "retries": 0,
                    "fallbacks": 0,
                    "private_thinking_persisted": False,
                },
            )
        _write_json(
            case_root / "native_outputs.json",
            {
                "schema_version": "triad-response-screen-native-outputs-v1",
                "status": entry["status"],
                "case_id": item.case_id,
                "failure_type": entry.get("failure_type"),
                "failure": entry.get("failure"),
                "observed_conclusion_ids": observed_ids,
                "native_bundle": None,
            },
        )
        _write_json(
            case_root / "profile_matrix.json",
            {
                "schema_version": "triad-response-screen-profile-matrix-v1",
                "status": "not_run_without_frozen_bundle",
                "case_id": item.case_id,
                "rows": [],
                "native_processor_executions": 0,
                "model_calls": 0,
            },
        )

    ledger["state"] = "complete" if not failures else "completed_with_rejections"
    _write_json(ledger_path, ledger)
    agreements = summarize_agreements(tuple(bundles))
    observed_conclusion_count = len(bundles) * 3
    for entry in ledger["entries"]:
        if entry["status"] == "evidence_projection_failed":
            observed_conclusion_count += 3
    summary = {
        "schema_version": "triad-response-screen-summary-v1",
        "phase": "TRIAD-S1",
        "branch": "codex/triad-response-screen-v1",
        "pre_call_seal_sha256": seal["seal_sha256"],
        "model": provider.runtime.model,
        "model_digest": provider.runtime.digest,
        "provider_revision": PROVIDER_REVISION,
        "model_calls": ledger["actual"]["model_calls"],
        "retries": ledger["actual"]["retries"],
        "fallbacks": ledger["actual"]["fallbacks"],
        "model_cases_attempted": ledger["actual"]["model_calls"],
        "executed_cases": len(bundles),
        "fully_evidenced_cases": len(bundles),
        "case_target": 8,
        "native_conclusions": observed_conclusion_count,
        "compact_validated_native_conclusions": len(bundles) * 3,
        "native_conclusion_target": 24,
        "character_replay_rows": len(bundles) * len(CHARACTER_PROFILE_ORDER),
        "character_replay_target": 104,
        "abstentions": {
            "R": abstentions["R"],
            "E": abstentions["E"],
            "I": abstentions["I"],
        },
        "agreement_counts": agreements,
        "failures": failures,
        "image_generation_calls": 0,
        "emocio_image_model_calls": 0,
        "instinkt_model_mapper_calls": 0,
        "global_rei_score": None,
    }
    _write_json(screen_root / "summary.json", summary)
    render_report(
        repository_root=repository_root,
        prepared=prepared,
        summary=summary,
    )
    if failures:
        raise RuntimeError(
            f"TRIAD-S1 completed with {len(failures)} validation rejection(s)"
        )
    return summary


def cold_verify_screen(repository_root: Path) -> Mapping[str, Any]:
    """Rehydrate the compact evidence projection without executing processors."""

    from .models.governance import AgreementPattern, GovernanceResolution
    from .models.provider import ProviderCallRecord, ProviderCallSpec
    from .providers.language_policy import require_english_local_model_payload
    from .providers.ollama import (
        OllamaRacioNativeExecution,
        OllamaRacioResponseEvidence,
    )

    prepared = verify_pre_call_screen(repository_root)
    screen_root = repository_root / SCREEN_RELATIVE_PATH
    ledger = _json_value(screen_root / "call_ledger.json")
    summary = _json_value(screen_root / "summary.json")
    if ledger["actual"] != {"model_calls": 8, "retries": 0, "fallbacks": 0}:
        raise ValueError("Compact evidence has incorrect model call accounting")
    if ledger["state"] not in {"complete", "completed_with_rejections"}:
        raise ValueError("Compact evidence call ledger is not complete")
    total_rows = 0
    total_conclusions = 0
    bundles: list[NativeMindBundle] = []
    for item in prepared:
        case_root = screen_root / "cases" / item.case_id
        inputs = _json_value(case_root / "inputs.json")
        calls = _json_value(case_root / "call_record.json")
        outputs = _json_value(case_root / "native_outputs.json")
        matrix = _json_value(case_root / "profile_matrix.json")
        for path, value in _walk((calls, outputs, matrix)):
            if path and path[-1].casefold() in {
                "thinking",
                "thoughts",
                "reasoning_content",
                "chain_of_thought",
            }:
                raise ValueError("Compact evidence persists private thinking")
            if isinstance(value, str) and re.search(
                r"[A-Za-z]:\\\\|/home/|/Users/", value
            ):
                raise ValueError("Compact evidence persists an absolute local path")
        if outputs.get("status") != "complete":
            entry = next(
                value
                for value in ledger["entries"]
                if value["case_id"] == item.case_id
            )
            if outputs["status"] != entry["status"]:
                raise ValueError("Failure projection differs from call ledger")
            if matrix["rows"] or matrix["native_processor_executions"] != 0:
                raise ValueError("Failed case incorrectly claims character replay")
            if outputs.get("native_bundle") is not None:
                raise ValueError("Failed case incorrectly claims a frozen bundle")
            continue
        request_payload = calls["racio"]["request_payload"]
        require_english_local_model_payload(
            declared_language="en",
            provider_payload={
                "language": "en",
                "presentation_mode": "operational_en_only",
                "packet": json.loads(request_payload["prompt"]),
            },
        )
        if "canonical_sl" in json.dumps(request_payload, ensure_ascii=False):
            raise ValueError("Racio request payload leaked canonical_sl")
        spec = _model_from_json(ProviderCallSpec, calls["racio"]["call_spec"])
        record = _model_from_json(
            ProviderCallRecord, calls["racio"]["call_record"]
        )
        evidence = _model_from_json(
            OllamaRacioResponseEvidence,
            calls["racio"]["result_evidence"]
        )
        bundle = _model_from_json(NativeMindBundle, outputs["bundle"])
        agreement = _model_from_json(
            AgreementPattern, outputs["agreement_pattern"]
        )
        racio_execution = OllamaRacioNativeExecution(
            conclusion=bundle.racio,
            call_spec=spec,
            call_record=record,
            reasoning_artifact=evidence,
        )
        if evidence.request_payload_hash != sha256_hex(request_payload):
            raise ValueError("Stored exact Racio input differs from result evidence")
        if racio_execution.conclusion != bundle.racio:
            raise ValueError("Racio call evidence differs from frozen bundle")
        if agreement.native_bundle_id != bundle.bundle_id:
            raise ValueError("Agreement pattern cites another bundle")
        if outputs["processor_execution_counts"] != {"R": 1, "E": 1, "I": 1}:
            raise ValueError("Native processor execution count is not one per mind")
        if matrix["native_processor_executions"] != 0 or matrix["model_calls"] != 0:
            raise ValueError("Character replay reran a native processor or model")
        if len(matrix["rows"]) != 13:
            raise ValueError("Case profile matrix does not contain 13 rows")
        for row in matrix["rows"]:
            governance = _model_from_json(
                GovernanceResolution, row["governance"]
            )
            if (
                governance.native_bundle_id != bundle.bundle_id
                or governance.native_bundle_hash != bundle.immutable_hash
            ):
                raise ValueError("Profile replay row cites another frozen bundle")
        if tuple(row["profile_id"] for row in matrix["rows"]) != (
            CHARACTER_PROFILE_ORDER
        ):
            raise ValueError("Profile replay order differs from the canonical 13")
        if inputs["racio"]["packet"] != _model_json(item.racio_packet):
            raise ValueError("Compact input projection differs from sealed Racio packet")
        bundles.append(bundle)
        total_rows += len(matrix["rows"])
        total_conclusions += 3
    if total_conclusions != len(bundles) * 3:
        raise ValueError("Compact native-conclusion count is inconsistent")
    if total_rows != len(bundles) * len(CHARACTER_PROFILE_ORDER):
        raise ValueError("Compact character-replay count is inconsistent")
    if summary["agreement_counts"] != summarize_agreements(tuple(bundles)):
        raise ValueError("Summary agreement counts differ from frozen bundles")
    if summary["character_replay_rows"] != total_rows:
        raise ValueError("Summary character replay count differs")
    report = (screen_root / "report.md").read_text(encoding="utf-8")
    required_report_text = (
        "Emocio response was tested after structured scene routing. "
        "This does not validate image-native visual cognition.",
        "Instinkt response was tested after typed cue routing. "
        "This does not validate raw-scene Instinkt perception.",
        "not an untouched holdout",
        "not promotion evidence",
        "not training data",
    )
    if any(value not in report for value in required_report_text):
        raise ValueError("Human report is missing a required scope boundary")
    return summary


__all__ = [
    "EXPECTED_CASE_IDS",
    "EXPECTED_MODEL_DIGEST",
    "MODEL_PROFILE",
    "PROVIDER_REVISION",
    "PreparedTriadCase",
    "SCREEN_RELATIVE_PATH",
    "prepare_case",
    "prepare_corpus",
    "prepare_pre_call_screen",
    "cold_verify_screen",
    "execute_screen",
    "render_report",
    "replay_profiles",
    "summarize_agreements",
    "validate_corpus",
    "verify_pre_call_screen",
]
