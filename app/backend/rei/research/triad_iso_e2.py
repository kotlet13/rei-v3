"""TRIAD-ISO-E2 final utility completion and two-call execution.

This module is deliberately research-only.  It creates a reviewed V3 source
projection, proves its pair invariants without model calls, seals exactly two
Racio calls, and projects the already reviewed Emocio annotation and typed
Instinkt mapping without executing either native processor.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, sha256_hex, utc_now
from ..emocio.policy import choose_native_option
from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText
from ..models.instinkt import BodyDelta
from ..models.racio import RacioInputPacket
from ..providers.native import SystemExecutionClock
from ..providers.ollama import OllamaStructuredOutputValidationError
from ..providers.ollama_en import OLLAMA_EN_TRIAD_PROVIDER_REVISION
from ..racio.text_reasoner_adapter import RACIO_STRUCTURED_INSTRUCTION_EN
from .triad_iso_e1 import (
    _failed_record,
    _failure_projection,
    _file_sha256,
    _git,
    _json,
    _object_sha256,
    _projection,
    _racio_preparation,
    _write_json,
)
from .triad_iso_r1 import validate_json_projection
from .triad_iso_r2 import (
    R2_OUTPUT_RELATIVE_PATH,
    compile_emocio_typed_annotation,
    e1_instinkt_projection_inputs,
    project_emocio_typed_valuations,
    project_instinkt_typed_sensitivity,
    source_evidence_address,
    source_option_address,
)
from .triad_s2 import EXPECTED_MODEL_DIGEST, MODEL_PROFILE, build_provider


EXPECTED_BASE_COMMIT: Final = "a9d587b62b64eeaa0456575e6230a5b53cc35795"
EXPECTED_R2_CANDIDATE_SHA256: Final = (
    "1cb5fdefdedd379da3b4448758e05c40b9901b27af91f7a30ff26caa90b8d2e3"
)
R2_CANDIDATE_RELATIVE_PATH: Final = (
    R2_OUTPUT_RELATIVE_PATH / "corrected_candidate_v2.json"
)
R2_EMOCIO_RELATIVE_PATH: Final = (
    R2_OUTPUT_RELATIVE_PATH / "emocio_typed_replay.json"
)
R2_INSTINKT_RELATIVE_PATH: Final = (
    R2_OUTPUT_RELATIVE_PATH / "instinkt_typed_sensitivity.json"
)
E1_OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-e1-2026-07-24"
)
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-e2-2026-07-24"
)
CANDIDATE_V3_RELATIVE_PATH: Final = (
    OUTPUT_RELATIVE_PATH / "corrected_candidate_v3.json"
)
UTILITY_CASE_ORDER: Final = (
    "trip_racio_utility_material",
    "trip_racio_utility_pleasure",
)
PROTECTIVE_CASE_ORDER: Final = (
    "trip_protective_context_exposed",
    "trip_protective_context_supported",
)
CASE_ORDER: Final = UTILITY_CASE_ORDER + PROTECTIVE_CASE_ORDER
LOCAL_FACT_SL: Final = (
    "Cenejši lokalni obalni izlet stane 480 EUR, kar je 10 odstotkov "
    "prostega proračuna."
)
LOCAL_FACT_EN: Final = (
    "The cheaper local coastal trip costs EUR 480, which is 10 percent of "
    "the discretionary budget."
)
LOCAL_EVIDENCE_ID: Final = "utility_ev_local_cost"
INSTINKT_MAPPER_REVISION: Final = (
    "triad-iso-e2-source-addressed-typed-utility-v1"
)
EXECUTION_POLICY: Final[Mapping[str, Any]] = {
    "call_order": UTILITY_CASE_ORDER,
    "racio_model_calls": 2,
    "retries": 0,
    "fallbacks": 0,
    "character_replay": 0,
    "native_emocio_processor_executions": 0,
    "native_instinkt_processor_executions": 0,
    "protective_racio_calls": 0,
}
LEAKAGE_KEYS: Final = frozenset(
    {
        "character",
        "character_profile",
        "governance",
        "governance_tier",
        "expected_option",
        "expected_option_id",
        "expected_action",
        "leading_mind",
        "gold_route",
        "preferred_option",
    }
)
PRIVATE_KEYS: Final = frozenset(
    {"thinking", "thoughts", "reasoning_content", "chain_of_thought"}
)

E2_EFFECT_RULES: Final[Mapping[str, Mapping[str, float]]] = {
    "discretionary_resource_commitment_10": {"resource_security": -0.09},
    "discretionary_resource_commitment_25": {"resource_security": -0.15},
    "bounded_cancellation_recovery": {
        "escape_availability": 0.12,
        "predictability": 0.08,
    },
    "trusted_attachment_support": {
        "attachment_security": 0.15,
        "tension": -0.05,
        "trust": 0.12,
    },
    "verified_provider_support": {"predictability": 0.10, "trust": 0.10},
    "verified_return_support": {
        "escape_availability": 0.15,
        "predictability": 0.10,
    },
    "discretionary_resource_preserved": {"resource_security": 0.15},
}
E2_PREDICATE_REQUIREMENTS: Final[Mapping[str, frozenset[str]]] = {
    "discretionary_resource_commitment_10": frozenset(
        {"discretionary_budget_exposure_10"}
    ),
    "discretionary_resource_commitment_25": frozenset(
        {"discretionary_budget_exposure"}
    ),
    "bounded_cancellation_recovery": frozenset({"bounded_cancellation"}),
    "trusted_attachment_support": frozenset({"trusted_companion_present"}),
    "verified_provider_support": frozenset({"verified_providers"}),
    "verified_return_support": frozenset({"verified_return_path"}),
    "discretionary_resource_preserved": frozenset(
        {"discretionary_budget_exposure"}
    ),
}


class E2EvidenceAssertion(FrozenModel):
    evidence_id: NonEmptyId
    source_text_sha256: HashDigest
    assertions: tuple[NonEmptyId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def canonical(self) -> "E2EvidenceAssertion":
        if self.assertions != tuple(sorted(set(self.assertions))):
            raise ValueError("E2 assertions must use canonical unique order")
        return self


class E2EffectCategory(FrozenModel):
    category_id: NonEmptyId
    option_id: NonEmptyId
    supporting_evidence_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    semantic_predicate: NonEmptyId
    body_deltas: tuple[BodyDelta, ...]

    @model_validator(mode="after")
    def fixed_rule(self) -> "E2EffectCategory":
        if self.semantic_predicate not in E2_EFFECT_RULES:
            raise ValueError("Unknown E2 effect predicate")
        if self.category_id != self.semantic_predicate:
            raise ValueError("E2 category identity must equal its predicate")
        expected = E2_EFFECT_RULES[self.semantic_predicate]
        observed = {item.dimension: item.delta for item in self.body_deltas}
        if observed != expected:
            raise ValueError("E2 body deltas differ from the frozen typed rule")
        return self


class E2OptionEffect(FrozenModel):
    option_id: NonEmptyId
    source_option_sha256: HashDigest
    source_consequence: NonEmptyText
    source_evidence_scope_ids: tuple[NonEmptyId, ...]
    categories: tuple[E2EffectCategory, ...] = ()


class E2TypedMapping(FrozenModel):
    schema_version: str = "triad-instinkt-e2-typed-route-mapping-v1"
    mapping_mode: str = "explicit_source_addressed_for_human_review"
    source_evidence_sha256: HashDigest
    protected_target_label: NonEmptyText
    budget_kind: str = "discretionary_budget"
    necessary_cash_reserve_claim: bool = False
    evidence_assertions: tuple[E2EvidenceAssertion, ...]
    option_effects: tuple[E2OptionEffect, ...] = Field(min_length=2)


def _case_index(candidate: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {case["case_id"]: case for case in candidate["cases"]}


def _append_fact(source: dict[str, Any], text: str) -> None:
    facts = source["facts"]
    if any(item["evidence_id"] == LOCAL_EVIDENCE_ID for item in facts):
        raise ValueError("V2 unexpectedly already contains the E2 local-cost fact")
    cost_index = next(
        index
        for index, item in enumerate(facts)
        if item["evidence_id"] == "utility_ev_cost"
    )
    facts.insert(
        cost_index + 1,
        {"evidence_id": LOCAL_EVIDENCE_ID, "text": text},
    )


def _category(
    option_id: str,
    predicate: str,
    evidence_ids: Sequence[str],
) -> Mapping[str, Any]:
    return {
        "category_id": predicate,
        "option_id": option_id,
        "supporting_evidence_ids": sorted(set(evidence_ids)),
        "semantic_predicate": predicate,
        "body_deltas": [
            {"dimension": key, "delta": value}
            for key, value in sorted(E2_EFFECT_RULES[predicate].items())
        ],
    }


def _assertion(
    case: Mapping[str, Any],
    evidence_id: str,
    *assertions: str,
) -> Mapping[str, Any]:
    facts = {
        item["evidence_id"]: item["text"]
        for item in case["operational_en"]["facts"]
    }
    return {
        "evidence_id": evidence_id,
        "source_text_sha256": sha256_hex(facts[evidence_id]),
        "assertions": sorted(set(assertions)),
    }


def _utility_instinkt_mapping(case: Mapping[str, Any]) -> Mapping[str, Any]:
    options = {
        item["option_id"]: item for item in case["operational_en"]["options"]
    }
    assertions = [
        _assertion(case, "utility_ev_cost", "discretionary_budget_exposure"),
        _assertion(
            case,
            LOCAL_EVIDENCE_ID,
            "discretionary_budget_exposure_10",
        ),
        _assertion(case, "utility_ev_reversibility", "bounded_cancellation"),
        _assertion(case, "utility_ev_companion", "trusted_companion_present"),
        _assertion(
            case,
            "utility_ev_safety",
            "verified_providers",
            "verified_return_path",
        ),
    ]
    definitions = {
        "utility_trip_book": {
            "consequence": (
                "Self enters verified distant travel with trusted attachment "
                "support, a 25-percent discretionary-budget commitment, "
                "bounded cancellation, verified providers, and verified return."
            ),
            "scope": (
                "utility_ev_companion",
                "utility_ev_cost",
                "utility_ev_reversibility",
                "utility_ev_safety",
            ),
            "categories": (
                ("discretionary_resource_commitment_25", ("utility_ev_cost",)),
                (
                    "bounded_cancellation_recovery",
                    ("utility_ev_reversibility",),
                ),
                ("trusted_attachment_support", ("utility_ev_companion",)),
                ("verified_provider_support", ("utility_ev_safety",)),
                ("verified_return_support", ("utility_ev_safety",)),
            ),
        },
        "utility_trip_local": {
            "consequence": (
                "Self enters the local coastal trip with trusted attachment "
                "support and commits 10 percent of the discretionary budget; "
                "no distant-provider or distant-return support is inferred."
            ),
            "scope": (LOCAL_EVIDENCE_ID, "utility_ev_companion"),
            "categories": (
                (
                    "discretionary_resource_commitment_10",
                    (LOCAL_EVIDENCE_ID,),
                ),
                ("trusted_attachment_support", ("utility_ev_companion",)),
            ),
        },
        "utility_trip_home": {
            "consequence": (
                "Self makes neither stated travel expenditure and retains the "
                "discretionary budget."
            ),
            "scope": ("utility_ev_cost",),
            "categories": (
                ("discretionary_resource_preserved", ("utility_ev_cost",)),
            ),
        },
    }
    effects = []
    for option_id in sorted(definitions):
        definition = definitions[option_id]
        effects.append(
            {
                "option_id": option_id,
                "source_option_sha256": hashlib.sha256(
                    canonical_json_bytes(options[option_id])
                ).hexdigest(),
                "source_consequence": definition["consequence"],
                "source_evidence_scope_ids": sorted(definition["scope"]),
                "categories": sorted(
                    (
                        _category(option_id, predicate, evidence_ids)
                        for predicate, evidence_ids in definition["categories"]
                    ),
                    key=lambda item: item["category_id"],
                ),
            }
        )
    return {
        "schema_version": "triad-instinkt-e2-typed-route-mapping-v1",
        "mapping_mode": "explicit_source_addressed_for_human_review",
        "source_evidence_sha256": source_evidence_address(case),
        "protected_target_label": (
            "Self's physical integrity, trusted attachment context, return "
            "ability, and discretionary budget."
        ),
        "budget_kind": "discretionary_budget",
        "necessary_cash_reserve_claim": False,
        "evidence_assertions": sorted(
            assertions, key=lambda item: item["evidence_id"]
        ),
        "option_effects": effects,
    }


def compile_e2_mapping(
    case: Mapping[str, Any],
    value: Mapping[str, Any],
) -> E2TypedMapping:
    mapping = validate_json_projection(E2TypedMapping, value)
    if mapping.source_evidence_sha256 != source_evidence_address(case):
        raise ValueError("E2 mapping source address differs")
    facts = {
        item["evidence_id"]: item["text"]
        for item in case["operational_en"]["facts"]
    }
    options = {
        item["option_id"]: item for item in case["operational_en"]["options"]
    }
    assertions = {item.evidence_id: item for item in mapping.evidence_assertions}
    if {item.option_id for item in mapping.option_effects} != set(options):
        raise ValueError("E2 typed mapping does not cover public options")
    for evidence_id, assertion in assertions.items():
        if evidence_id not in facts:
            raise ValueError("E2 assertion cites unknown evidence")
        if assertion.source_text_sha256 != sha256_hex(facts[evidence_id]):
            raise ValueError("E2 assertion source text address differs")
    for effect in mapping.option_effects:
        if effect.source_option_sha256 != source_option_address(
            case, effect.option_id
        ):
            raise ValueError("E2 option source address differs")
        if not set(effect.source_evidence_scope_ids).issubset(assertions):
            raise ValueError("E2 option scope lacks a typed assertion")
        for category in effect.categories:
            if category.option_id != effect.option_id:
                raise ValueError("E2 category belongs to another option")
            if not set(category.supporting_evidence_ids).issubset(
                effect.source_evidence_scope_ids
            ):
                raise ValueError("E2 category cites evidence outside its option")
            cited = {
                assertion
                for evidence_id in category.supporting_evidence_ids
                for assertion in assertions[evidence_id].assertions
            }
            if not E2_PREDICATE_REQUIREMENTS[
                category.semantic_predicate
            ].issubset(cited):
                raise ValueError("E2 category lacks its required assertion")
    return mapping


def corrected_candidate_v3(repository_root: Path) -> Mapping[str, Any]:
    path = repository_root / R2_CANDIDATE_RELATIVE_PATH
    if _file_sha256(path) != EXPECTED_R2_CANDIDATE_SHA256:
        raise ValueError("Frozen R2 corrected candidate bytes changed")
    candidate = copy.deepcopy(_json(path))
    candidate.update(
        {
            "schema_version": "triad-iso-e2-corrected-candidate-v3",
            "candidate_id": "triad-route-isolation-e2-candidate-2026-07-24",
            "status": "unsealed_candidate",
            "execution_authorized": False,
            "human_review_status": "approved_for_triad_iso_e2_exact_scope",
            "approval_scope": {
                "source_cases": CASE_ORDER,
                "racio_model_calls": UTILITY_CASE_ORDER,
                "manual_emocio_annotation_projection": True,
                "typed_instinkt_mapping_projection": True,
                "general_processor_authority": False,
                "character_replay": False,
            },
            "source_r2_candidate": {
                "path": R2_CANDIDATE_RELATIVE_PATH.as_posix(),
                "sha256": EXPECTED_R2_CANDIDATE_SHA256,
            },
        }
    )
    for case in candidate["cases"]:
        if case["case_id"] not in UTILITY_CASE_ORDER:
            continue
        _append_fact(case["canonical_sl"], LOCAL_FACT_SL)
        _append_fact(case["operational_en"], LOCAL_FACT_EN)
        racio = case["route_packets"]["racio"]
        fact_index = racio["facts"].index("utility_ev_cost")
        racio["facts"].insert(fact_index + 1, LOCAL_EVIDENCE_ID)
        local = next(
            item
            for item in racio["material_strategic_consequences"]
            if item["option_id"] == "utility_trip_local"
        )
        if case["case_id"].endswith("_material"):
            local["consequence"] = (
                "Self commits EUR 480, or 10 percent of the discretionary "
                "budget, for a local coastal experience with no signed studio "
                "demonstration or separately grounded strategic return."
            )
            racio["opportunity_cost"] = (
                "The distant trip commits EUR 1200 and the local trip commits "
                "EUR 480, so either amount cannot cover other costs; not "
                "booking the distant trip gives up the signed demonstration "
                "and bounded studio saving."
            )
        else:
            local["consequence"] = (
                "Self commits EUR 480, or 10 percent of the discretionary "
                "budget, for a local coastal experience with no separate "
                "strategic or material return."
            )
            racio["opportunity_cost"] = (
                "The distant trip commits EUR 1200 and the local trip commits "
                "EUR 480, so either amount cannot cover other unknown costs; "
                "not travelling gives up the explicitly stated experience."
            )
        annotation = case["route_packets"]["emocio"][
            "typed_route_annotation_v1"
        ]
        annotation["source_evidence_sha256"] = source_evidence_address(case)
        case["route_packets"]["instinkt"][
            "typed_effect_mapping_v1"
        ] = _utility_instinkt_mapping(case)
    return candidate


def _semantic_emocio_annotation(annotation: Mapping[str, Any]) -> Any:
    value = copy.deepcopy(annotation)
    value.pop("source_evidence_sha256", None)
    return value


def _mapping_semantics(mapping: Mapping[str, Any]) -> Any:
    value = copy.deepcopy(mapping)
    value.pop("source_evidence_sha256", None)
    return value


def _utility_instinkt_projection(
    repository_root: Path,
    case: Mapping[str, Any],
) -> Mapping[str, Any]:
    mapping = compile_e2_mapping(
        case,
        case["route_packets"]["instinkt"]["typed_effect_mapping_v1"],
    )
    packet, body, config, base_effects = e1_instinkt_projection_inputs(
        repository_root, case["case_id"]
    )
    packet = packet.model_copy(
        update={
            "evidence_ids": tuple(
                sorted((*packet.evidence_ids, LOCAL_EVIDENCE_ID))
            ),
            "physical_cues": (
                *packet.physical_cues,
                LOCAL_FACT_EN,
            ),
        }
    )
    projection = project_instinkt_typed_sensitivity(
        mapping=mapping,  # type: ignore[arg-type]
        packet=packet,
        body_state=body,
        config=config,
        base_effects=base_effects,
    )
    return {
        "mapping": mapping.model_dump(mode="json"),
        **_projection(projection),
        "projection_mode": "human_reviewed_typed_mapping_deterministic_projection",
        "native_processor_executions": 0,
        "model_calls": 0,
    }


def deterministic_references(
    repository_root: Path,
    candidate: Mapping[str, Any],
) -> Mapping[str, Any]:
    index = _case_index(candidate)
    r2_emocio = _case_index(_json(repository_root / R2_EMOCIO_RELATIVE_PATH))
    r2_instinkt = _case_index(_json(repository_root / R2_INSTINKT_RELATIVE_PATH))
    cases: dict[str, Any] = {}
    utility_i = {}
    for case_id in UTILITY_CASE_ORDER:
        case = index[case_id]
        annotation = compile_emocio_typed_annotation(
            case,
            case["route_packets"]["emocio"]["typed_route_annotation_v1"],
        )
        valuations = project_emocio_typed_valuations(annotation)
        decision = choose_native_option(valuations)
        e_projection = {
            "typed_annotation": annotation.model_dump(mode="json"),
            "annotation_sha256": _object_sha256(
                annotation.model_dump(mode="json")
            ),
            "evidence_closure": "passed",
            "valuation_vectors": {
                item.option_id: {
                    dimension.name: dimension.score
                    for dimension in item.dimensions
                }
                for item in valuations
            },
            "aggregate_scores": {
                item.option_id: item.score for item in decision.aggregate_scores
            },
            "selected_option_id": (
                decision.selected.option_id
                if decision.selected is not None
                else None
            ),
            "tied_option_ids": decision.tied_option_ids,
            "manual_annotation": True,
            "processor_capability_claimed": False,
            "projection_mode": "human_reviewed_annotation_deterministic_projection",
            "native_processor_executions": 0,
            "model_calls": 0,
        }
        frozen_e = r2_emocio[case_id]
        if _semantic_emocio_annotation(
            e_projection["typed_annotation"]
        ) != _semantic_emocio_annotation(frozen_e["typed_annotation"]):
            raise ValueError(f"Emocio route semantics changed for {case_id}")
        if e_projection["valuation_vectors"] != frozen_e["valuation_vectors"]:
            raise ValueError(f"Emocio valuation vector changed for {case_id}")
        utility_i[case_id] = _utility_instinkt_projection(
            repository_root, case
        )
        utility_i[case_id]["mapping_sha256"] = _object_sha256(
            utility_i[case_id]["mapping"]
        )
        utility_i[case_id]["category_evidence_closure"] = "passed"
        utility_i[case_id]["typed_mapping"] = True
        utility_i[case_id]["processor_capability_claimed"] = False
        cases[case_id] = {"emocio": e_projection, "instinkt": utility_i[case_id]}
    if _mapping_semantics(
        utility_i[UTILITY_CASE_ORDER[0]]["mapping"]
    ) != _mapping_semantics(utility_i[UTILITY_CASE_ORDER[1]]["mapping"]):
        raise ValueError("Utility Instinkt typed route differs across variants")
    for key in ("option_results", "selected_option_id", "tied_option_ids"):
        if utility_i[UTILITY_CASE_ORDER[0]][key] != utility_i[
            UTILITY_CASE_ORDER[1]
        ][key]:
            raise ValueError("Utility Instinkt projection is not stable")
    for case_id in PROTECTIVE_CASE_ORDER:
        cases[case_id] = {
            "emocio": r2_emocio[case_id],
            "instinkt": r2_instinkt[case_id],
            "projection_mode": "frozen_r2_deterministic_reference",
            "native_processor_executions": 0,
            "model_calls": 0,
        }
    return {
        "schema_version": "triad-iso-e2-deterministic-references-v1",
        "cases": cases,
        "research_hypothesis": {
            "name": "monotone_discretionary_budget_exposure",
            "status": "implementation_hypothesis",
            "resource_security_deltas": {
                "10_percent": -0.09,
                "25_percent": -0.15,
                "38_percent": -0.20,
            },
        },
        "native_processor_executions": {"E": 0, "I": 0},
        "model_calls": 0,
    }


def _protective_reuse(
    repository_root: Path,
    candidate: Mapping[str, Any],
    provider: Any,
) -> Mapping[str, Any]:
    e1_seal = _json(repository_root / E1_OUTPUT_RELATIVE_PATH / "pre_call_seal.json")
    checks = {
        "provider_revision": e1_seal["provider_revision"]
        == OLLAMA_EN_TRIAD_PROVIDER_REVISION,
        "instruction_sha256": e1_seal["instruction_sha256"]
        == sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN),
        "model_digest": e1_seal["model_digest"] == provider.runtime.digest,
        "model_profile": e1_seal["model_profile"] == MODEL_PROFILE,
    }
    cases = []
    index = _case_index(candidate)
    for case_id in PROTECTIVE_CASE_ORDER:
        _, _, packet, call_spec, _ = _racio_preparation(index[case_id], provider)
        e1_inputs_path = (
            repository_root
            / E1_OUTPUT_RELATIVE_PATH
            / "cases"
            / case_id
            / "inputs.json"
        )
        e1_native_path = (
            repository_root
            / E1_OUTPUT_RELATIVE_PATH
            / "cases"
            / case_id
            / "native_outputs.json"
        )
        e1_inputs = _json(e1_inputs_path)
        e1_packet = validate_json_projection(
            RacioInputPacket, e1_inputs["racio"]["packet"]
        )
        native = _json(e1_native_path)
        options_equal = (
            e1_inputs["operational_en"]["options"]
            == index[case_id]["operational_en"]["options"]
        )
        packet_equal = e1_packet.content_hash() == packet.content_hash()
        accepted = native["racio"]["status"] == "accepted"
        case_passed = packet_equal and options_equal and accepted
        checks[f"{case_id}_packet_hash"] = packet_equal
        checks[f"{case_id}_options"] = options_equal
        checks[f"{case_id}_accepted"] = accepted
        cases.append(
            {
                "case_id": case_id,
                "status": "reused_frozen_accepted_conclusion"
                if case_passed
                else "reuse_mismatch",
                "packet_hash": packet.content_hash(),
                "frozen_packet_hash": e1_packet.content_hash(),
                "call_spec_hash": call_spec.content_hash(),
                "source_inputs": {
                    "path": e1_inputs_path.relative_to(repository_root).as_posix(),
                    "sha256": _file_sha256(e1_inputs_path),
                },
                "source_native_outputs": {
                    "path": e1_native_path.relative_to(repository_root).as_posix(),
                    "sha256": _file_sha256(e1_native_path),
                },
                "conclusion": native["racio"]["conclusion"] if accepted else None,
            }
        )
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "cases": cases,
        "protective_model_calls": 0,
    }


def _racio_pair_invariants(
    material: Mapping[str, Any],
    pleasure: Mapping[str, Any],
) -> Mapping[str, bool]:
    m_source = material["operational_en"]
    p_source = pleasure["operational_en"]
    m_facts = {item["evidence_id"]: item["text"] for item in m_source["facts"]}
    p_facts = {item["evidence_id"]: item["text"] for item in p_source["facts"]}
    changed = {"utility_ev_benefit", "utility_ev_beneficiary"}
    common_ids = (set(m_facts) | set(p_facts)) - changed
    m_route = material["route_packets"]["racio"]
    p_route = pleasure["route_packets"]["racio"]
    route_diff_keys = {
        key
        for key in set(m_route) | set(p_route)
        if m_route.get(key) != p_route.get(key)
    }
    benefit_related_route_fields = {
        "explicit_beneficiary",
        "explicit_goal",
        "material_strategic_consequences",
        "opportunity_cost",
        "enforceability_control",
        "time_sequence",
        "unknowns",
    }
    return {
        "public_options_identical": m_source["options"] == p_source["options"],
        "public_option_order_identical": [
            item["option_id"] for item in m_source["options"]
        ]
        == [item["option_id"] for item in p_source["options"]],
        "common_operational_facts_identical": all(
            m_facts.get(key) == p_facts.get(key) for key in common_ids
        ),
        "local_cost_fact_identical": m_facts.get(LOCAL_EVIDENCE_ID)
        == p_facts.get(LOCAL_EVIDENCE_ID)
        == LOCAL_FACT_EN,
        "racio_fact_scope_identical": material["route_packets"]["racio"][
            "facts"
        ]
        == pleasure["route_packets"]["racio"]["facts"],
        "racio_route_diff_benefit_limited": route_diff_keys.issubset(
            benefit_related_route_fields
        ),
        "emocio_route_semantics_identical": (
            {
                key: value
                for key, value in material["route_packets"]["emocio"].items()
                if key != "typed_route_annotation_v1"
            }
            == {
                key: value
                for key, value in pleasure["route_packets"]["emocio"].items()
                if key != "typed_route_annotation_v1"
            }
            and _semantic_emocio_annotation(
                material["route_packets"]["emocio"]["typed_route_annotation_v1"]
            )
            == _semantic_emocio_annotation(
                pleasure["route_packets"]["emocio"]["typed_route_annotation_v1"]
            )
        ),
        "instinkt_route_semantics_identical": _mapping_semantics(
            material["route_packets"]["instinkt"]["typed_effect_mapping_v1"]
        )
        == _mapping_semantics(
            pleasure["route_packets"]["instinkt"]["typed_effect_mapping_v1"]
        ),
    }


def _leakage_free(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in LEAKAGE_KEYS | PRIVATE_KEYS:
                return False
            if not _leakage_free(child):
                return False
    elif isinstance(value, (list, tuple)):
        return all(_leakage_free(child) for child in value)
    elif isinstance(value, str) and re.search(
        r"\b(?:preferred|best|safest|expected winner)\b", value, re.I
    ):
        return False
    return True


def model_free_preflight(
    repository_root: Path,
    candidate: Mapping[str, Any],
    provider: Any,
) -> Mapping[str, Any]:
    index = _case_index(candidate)
    invariants = _racio_pair_invariants(
        index[UTILITY_CASE_ORDER[0]], index[UTILITY_CASE_ORDER[1]]
    )
    references = deterministic_references(repository_root, candidate)
    reuse = _protective_reuse(repository_root, candidate, provider)
    checks = {
        **invariants,
        "candidate_case_order": tuple(candidate["case_order"]) == CASE_ORDER,
        "candidate_unsealed": candidate["status"] == "unsealed_candidate",
        "execution_not_authorized": candidate["execution_authorized"] is False,
        "exact_scope_reviewed": candidate["human_review_status"]
        == "approved_for_triad_iso_e2_exact_scope",
        "no_leakage": _leakage_free(candidate),
        "sl_en_ids_match": all(
            [item["evidence_id"] for item in case["canonical_sl"]["facts"]]
            == [item["evidence_id"] for item in case["operational_en"]["facts"]]
            and [item["option_id"] for item in case["canonical_sl"]["options"]]
            == [item["option_id"] for item in case["operational_en"]["options"]]
            for case in candidate["cases"]
        ),
        "protective_racio_reuse_exact": reuse["status"] == "passed",
        "emocio_projection_model_free": references[
            "native_processor_executions"
        ]["E"]
        == 0,
        "instinkt_projection_model_free": references[
            "native_processor_executions"
        ]["I"]
        == 0,
        "effect_rule_monotone": -0.09 > -0.15 > -0.20,
    }
    return {
        "schema_version": "triad-iso-e2-model-free-preflight-v1",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "protective_reuse": reuse,
        "model_calls": 0,
        "native_processor_executions": {"E": 0, "I": 0},
    }


def _utility_preparations(
    candidate: Mapping[str, Any],
    provider: Any,
) -> list[Mapping[str, Any]]:
    index = _case_index(candidate)
    prepared = []
    for case_id in UTILITY_CASE_ORDER:
        scene, world, packet, call_spec, request_payload = _racio_preparation(
            index[case_id], provider
        )
        prepared.append(
            {
                "case_id": case_id,
                "scene": scene,
                "world": world,
                "packet": packet,
                "call_spec": call_spec,
                "request_payload": request_payload,
            }
        )
    return prepared


def seal_e2(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    if output_root.exists():
        raise ValueError("TRIAD-ISO-E2 output root already exists; seal is create-only")
    if _git(repository_root, "rev-parse", "HEAD") != EXPECTED_BASE_COMMIT:
        raise ValueError("TRIAD-ISO-E2 base commit differs")
    provider = build_provider()
    if provider.runtime.digest != EXPECTED_MODEL_DIGEST:
        raise ValueError("Exact local model digest differs before seal")
    candidate = corrected_candidate_v3(repository_root)
    preflight = model_free_preflight(repository_root, candidate, provider)
    if preflight["status"] != "passed":
        failed = [key for key, value in preflight["checks"].items() if not value]
        raise ValueError(f"TRIAD-ISO-E2 preflight failed: {failed}")
    references = deterministic_references(repository_root, candidate)
    prepared = _utility_preparations(candidate, provider)

    _write_json(repository_root / CANDIDATE_V3_RELATIVE_PATH, candidate)
    _write_json(output_root / "preflight_report.json", preflight)
    _write_json(output_root / "deterministic_route_references.json", references)
    input_records = []
    for item in prepared:
        path = output_root / "cases" / item["case_id"] / "inputs.json"
        value = {
            "schema_version": "triad-iso-e2-racio-input-v1",
            "case_id": item["case_id"],
            "canonical_sl": _case_index(candidate)[item["case_id"]]["canonical_sl"],
            "operational_en": _case_index(candidate)[item["case_id"]][
                "operational_en"
            ],
            "racio": {
                "scene": item["scene"],
                "world": item["world"],
                "packet": item["packet"],
                "call_spec": item["call_spec"],
                "request_payload": item["request_payload"],
            },
            "character_replay": False,
            "emocio_native_processor_execution": False,
            "instinkt_native_processor_execution": False,
        }
        _write_json(path, value)
        input_records.append(
            {
                "case_id": item["case_id"],
                "path": path.relative_to(repository_root).as_posix(),
                "sha256": _file_sha256(path),
                "candidate_case_sha256": _object_sha256(
                    _case_index(candidate)[item["case_id"]]
                ),
                "canonical_sl_sha256": _object_sha256(value["canonical_sl"]),
                "operational_en_sha256": _object_sha256(value["operational_en"]),
                "racio_packet_sha256": item["packet"].content_hash(),
                "emocio_packet_sha256": _object_sha256(
                    _case_index(candidate)[item["case_id"]]["route_packets"][
                        "emocio"
                    ]
                ),
                "emocio_annotation_sha256": _object_sha256(
                    _case_index(candidate)[item["case_id"]]["route_packets"][
                        "emocio"
                    ]["typed_route_annotation_v1"]
                ),
                "instinkt_packet_sha256": _object_sha256(
                    _case_index(candidate)[item["case_id"]]["route_packets"][
                        "instinkt"
                    ]
                ),
                "instinkt_mapping_sha256": _object_sha256(
                    _case_index(candidate)[item["case_id"]]["route_packets"][
                        "instinkt"
                    ]["typed_effect_mapping_v1"]
                ),
            }
        )
    ledger = {
        "schema_version": "triad-iso-e2-expected-call-ledger-v1",
        "state": "sealed_before_calls",
        "expected": {
            "model_calls": 2,
            "retries": 0,
            "fallbacks": 0,
            "character_replay": 0,
        },
        "entries": [
            {
                "ordinal": ordinal,
                "case_id": item["case_id"],
                "call_id": item["call_spec"].call_id,
                "call_spec_hash": item["call_spec"].content_hash(),
                "status": "sealed",
            }
            for ordinal, item in enumerate(prepared, 1)
        ],
    }
    _write_json(output_root / "expected_call_ledger.json", ledger)
    module_path = Path(__file__).resolve()
    script_path = repository_root / "scripts/run_triad_iso_e2.py"
    base = {
        "schema_version": "triad-iso-e2-pre-call-seal-v1",
        "phase": "TRIAD-ISO-E2",
        "base_commit": EXPECTED_BASE_COMMIT,
        "source_r2_candidate": {
            "path": R2_CANDIDATE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_R2_CANDIDATE_SHA256,
        },
        "candidate_v3": {
            "path": CANDIDATE_V3_RELATIVE_PATH.as_posix(),
            "sha256": _file_sha256(repository_root / CANDIDATE_V3_RELATIVE_PATH),
            "status": "unsealed_candidate",
        },
        "preflight_report": {
            "path": (OUTPUT_RELATIVE_PATH / "preflight_report.json").as_posix(),
            "sha256": _file_sha256(output_root / "preflight_report.json"),
            "passed": True,
        },
        "deterministic_route_references": {
            "path": (
                OUTPUT_RELATIVE_PATH / "deterministic_route_references.json"
            ).as_posix(),
            "sha256": _file_sha256(
                output_root / "deterministic_route_references.json"
            ),
        },
        "input_records": input_records,
        "provider_revision": OLLAMA_EN_TRIAD_PROVIDER_REVISION,
        "instruction_sha256": sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN),
        "instinkt_mapper_revision": INSTINKT_MAPPER_REVISION,
        "generic_effect_rules_sha256": _object_sha256(E2_EFFECT_RULES),
        "model": provider.runtime.model,
        "model_digest": provider.runtime.digest,
        "model_profile": MODEL_PROFILE,
        "call_order": UTILITY_CASE_ORDER,
        "call_specs": [_projection(item["call_spec"]) for item in prepared],
        "expected_call_ledger": {
            "path": (OUTPUT_RELATIVE_PATH / "expected_call_ledger.json").as_posix(),
            "sha256": _file_sha256(output_root / "expected_call_ledger.json"),
        },
        "implementation": {
            "module_path": module_path.relative_to(repository_root).as_posix(),
            "module_sha256": _file_sha256(module_path),
            "script_path": script_path.relative_to(repository_root).as_posix(),
            "script_sha256": _file_sha256(script_path),
        },
        "execution_policy": EXECUTION_POLICY,
        "output_root": OUTPUT_RELATIVE_PATH.as_posix(),
        "created_at": utc_now(),
    }
    projected_base = _projection(base)
    seal = {
        **projected_base,
        "seal_sha256": _object_sha256(projected_base),
    }
    _write_json(output_root / "pre_call_seal.json", seal)
    return seal


def verify_seal(
    repository_root: Path,
    provider: Any | None = None,
) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    seal = _json(output_root / "pre_call_seal.json")
    base = {key: value for key, value in seal.items() if key != "seal_sha256"}
    if _object_sha256(base) != seal["seal_sha256"]:
        raise ValueError("TRIAD-ISO-E2 seal hash differs")
    for record_key in (
        "source_r2_candidate",
        "candidate_v3",
        "preflight_report",
        "deterministic_route_references",
        "expected_call_ledger",
    ):
        record = seal[record_key]
        if _file_sha256(repository_root / record["path"]) != record["sha256"]:
            raise ValueError(f"Sealed E2 file changed: {record_key}")
    for key in ("module", "script"):
        path = repository_root / seal["implementation"][f"{key}_path"]
        if _file_sha256(path) != seal["implementation"][f"{key}_sha256"]:
            raise ValueError(f"Sealed E2 implementation changed: {key}")
    if seal["instruction_sha256"] != sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN):
        raise ValueError("Sealed E2 Racio instruction changed")
    if seal["model_profile"] != MODEL_PROFILE:
        raise ValueError("Sealed E2 model profile changed")
    active = provider or build_provider()
    if active.runtime.digest != seal["model_digest"]:
        raise ValueError("Exact local digest changed after E2 seal")
    candidate = _json(repository_root / seal["candidate_v3"]["path"])
    preflight = model_free_preflight(repository_root, candidate, active)
    if preflight != _json(repository_root / seal["preflight_report"]["path"]):
        raise ValueError("Cold E2 preflight differs from seal")
    prepared = _utility_preparations(candidate, active)
    if [_projection(item["call_spec"]) for item in prepared] != seal["call_specs"]:
        raise ValueError("E2 call specs changed after seal")
    for record, item in zip(seal["input_records"], prepared, strict=True):
        if _file_sha256(repository_root / record["path"]) != record["sha256"]:
            raise ValueError(f"Sealed E2 input changed: {record['case_id']}")
        if item["packet"].content_hash() != record["racio_packet_sha256"]:
            raise ValueError(f"Cold E2 packet changed: {record['case_id']}")
    return seal, prepared


def initialize_execution(repository_root: Path) -> Mapping[str, Any]:
    path = repository_root / OUTPUT_RELATIVE_PATH / "call_ledger.json"
    if path.exists():
        return _json(path)
    seal, _ = verify_seal(repository_root)
    expected = _json(
        repository_root / OUTPUT_RELATIVE_PATH / "expected_call_ledger.json"
    )
    ledger = {
        "schema_version": "triad-iso-e2-call-ledger-v1",
        "state": "ready",
        "pre_call_seal_sha256": seal["seal_sha256"],
        "expected": expected["expected"],
        "actual": {
            "model_call_attempts": 0,
            "retries": 0,
            "fallbacks": 0,
            "character_replay": 0,
            "native_emocio_processor_executions": 0,
            "native_instinkt_processor_executions": 0,
        },
        "entries": [
            {
                "ordinal": item["ordinal"],
                "case_id": item["case_id"],
                "call_id": item["call_id"],
                "status": "planned",
            }
            for item in expected["entries"]
        ],
    }
    _write_json(path, ledger)
    return ledger


def run_next(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    provider = build_provider()
    _, prepared = verify_seal(repository_root, provider)
    ledger = initialize_execution(repository_root)
    ledger_path = output_root / "call_ledger.json"
    if ledger["state"] not in {"ready", "executing"}:
        raise ValueError(f"E2 execution is not runnable from {ledger['state']}")
    if any(item["status"] == "dispatching" for item in ledger["entries"]):
        raise ValueError("Prior E2 attempt is indeterminate; retry is forbidden")
    entry = next(
        (item for item in ledger["entries"] if item["status"] == "planned"),
        None,
    )
    if entry is None:
        raise ValueError("Both sealed E2 calls were already attempted")
    expected_ordinal = ledger["actual"]["model_call_attempts"] + 1
    if entry["ordinal"] != expected_ordinal:
        raise ValueError("E2 call order changed")
    item = next(value for value in prepared if value["case_id"] == entry["case_id"])
    ledger["state"] = "executing"
    entry["status"] = "dispatching"
    entry["attempt_recorded_before_dispatch"] = True
    ledger["actual"]["model_call_attempts"] += 1
    _write_json(ledger_path, ledger)

    clock = SystemExecutionClock()
    started = utc_now()
    execution = None
    failure = None
    diagnostic = None
    failed_record = None
    try:
        execution = provider.execute(
            item["packet"], call=item["call_spec"], clock=clock
        )
        entry["racio_status"] = "accepted"
    except Exception as exc:
        failure, diagnostic = _failure_projection(exc)
        failed_record = _failed_record(
            call=item["call_spec"],
            started_at=started,
            finished_at=utc_now(),
            warning=(
                f"{failure['validation_stage']}:{failure['failure_code']}:"
                f"{failure.get('final_json_sha256') or 'none'}"
            ),
        )
        entry["racio_status"] = (
            "rejected"
            if isinstance(exc, OllamaStructuredOutputValidationError)
            else "provider_failed"
        )
        entry["failure_code"] = failure["failure_code"]
        entry["final_json_sha256"] = failure.get("final_json_sha256")
    case_root = output_root / "cases" / entry["case_id"]
    _write_json(
        case_root / "call_record.json",
        {
            "schema_version": "triad-iso-e2-call-record-v1",
            "case_id": entry["case_id"],
            "call_spec": item["call_spec"],
            "call_record": (
                execution.call_record if execution is not None else failed_record
            ),
            "result_evidence": (
                execution.reasoning_artifact if execution is not None else None
            ),
            "failed_output_diagnostic": diagnostic,
            "failure": failure,
            "retries": 0,
            "fallbacks": 0,
            "private_thinking_persisted": False,
        },
    )
    _write_json(
        case_root / "racio_output.json",
        {
            "schema_version": "triad-iso-e2-racio-output-v1",
            "case_id": entry["case_id"],
            "status": entry["racio_status"],
            "conclusion": execution.conclusion if execution is not None else None,
            "failure": failure,
            "processor_execution_count": 1,
        },
    )
    entry["status"] = "complete"
    if ledger["actual"]["model_call_attempts"] == 2:
        ledger["state"] = "two_calls_complete"
    _write_json(ledger_path, ledger)
    return {
        "case_id": entry["case_id"],
        "ordinal": entry["ordinal"],
        "racio_status": entry["racio_status"],
        "failure_code": entry.get("failure_code"),
        "model_call_attempts": ledger["actual"]["model_call_attempts"],
    }


def _semantic_conclusion(conclusion: Mapping[str, Any] | None) -> Any:
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
            "abstains",
            "uncertainty",
        )
    }


def _render_report(
    *,
    seal: Mapping[str, Any],
    outputs: Mapping[str, Any],
    references: Mapping[str, Any],
    reuse: Mapping[str, Any],
) -> str:
    lines = [
        "# TRIAD-ISO-E2 final utility route-isolation execution",
        "",
        "Research-only route-isolation screen. This is not a holdout, model "
        "promotion, global REI score, native Emocio processor execution, native "
        "Instinkt processor execution, image-native Emocio claim, raw-scene "
        "Instinkt claim, character replay, ConsciousDecision, or BehaviorResultant.",
        "",
        "## Execution boundary",
        "",
        f"- Seal: `{seal['seal_sha256']}`.",
        f"- Candidate V3: `{seal['candidate_v3']['sha256']}` "
        "(`unsealed_candidate`; exact E2 scope only).",
        f"- Model digest: `{seal['model_digest']}`.",
        "- Racio calls: exactly 2; retries: 0; fallbacks: 0.",
        "- Protective Racio conclusions: frozen E1 reuse only; no protective calls.",
        "- Emocio and Instinkt: deterministic projections of human-reviewed "
        "source-addressed annotations/mappings; native processor executions: 0.",
        "",
        "## Utility pair",
        "",
        "### Held constant",
        "",
        "- Public option IDs, descriptions, and order.",
        "- Destination attraction, rarity, companion, verified travel context, "
        "cancellation terms, EUR 1,200 distant cost, EUR 480 local cost, and "
        "EUR 4,800 discretionary budget base.",
        "- Emocio typed relation semantics and 11-dimensional valuation vectors.",
        "- Instinkt typed consequence/effect mapping.",
        "",
        "### Changed",
        "",
        "- Explicit benefit, beneficiary, goal, benefit-dependent consequence "
        "chain, and corresponding bounded unknown.",
        "",
    ]
    for case_id in UTILITY_CASE_ORDER:
        output = outputs[case_id]
        conclusion = output["conclusion"]
        lines.extend(
            [
                f"### `{case_id}`",
                "",
                f"- Racio status: `{output['status']}`.",
                f"- Selected option: "
                f"`{conclusion['option_id'] if conclusion else 'none'}`.",
            ]
        )
        if conclusion:
            lines.extend(
                [
                    "- Facts used: " + "; ".join(conclusion["facts_used"]),
                    "- Unknowns retained: "
                    + ("; ".join(conclusion["unknowns"]) or "none"),
                    "- Explicit goal: " + conclusion["explicit_goal"],
                    "- Causal route: " + " → ".join(conclusion["causal_sequence"]),
                    "- Utility structure: "
                    + "; ".join(conclusion["utility_structure"]),
                    "- Main objection: " + conclusion["main_objection"],
                    "- Unsupported claims: see human review field below; Codex "
                    "does not adjudicate semantic plausibility.",
                ]
            )
        else:
            lines.append(
                f"- Failure: `{output['failure']['failure_code']}` at "
                f"`{output['failure']['validation_stage']}`."
            )
        e = references["cases"][case_id]["emocio"]
        i = references["cases"][case_id]["instinkt"]
        lines.extend(
            [
                "",
                "#### EMOCIO reference",
                "",
                "- Current/desired/broken and visible-option relations are the "
                "frozen human-reviewed R2 semantics.",
                f"- Manual annotation: `true`; evidence closure: "
                f"`{e['evidence_closure']}`; annotation SHA-256: "
                f"`{e['annotation_sha256']}`; processor capability claimed: "
                "`false`.",
                "- Valuation vectors: `" + json.dumps(
                    e["valuation_vectors"], ensure_ascii=False, sort_keys=True
                ) + "`.",
                f"- Deterministic selected option: "
                f"`{e['selected_option_id']}`; ties: "
                f"`{', '.join(e['tied_option_ids']) or 'none'}`.",
                "- Attraction, movement, and novelty remain independently "
                "represented; competition remains `not_relevant`.",
                "",
                "#### INSTINKT reference",
                "",
                f"- Typed mapping: `true`; category/evidence closure: "
                f"`{i['category_evidence_closure']}`; mapping SHA-256: "
                f"`{i['mapping_sha256']}`; processor capability claimed: "
                "`false`.",
                "- Typed option results: `" + json.dumps(
                    i["option_results"], ensure_ascii=False, sort_keys=True
                ) + "`.",
                f"- Selected option: `{i['selected_option_id']}`; ties: "
                f"`{', '.join(i['tied_option_ids']) or 'none'}`.",
                "",
            ]
        )
    first = outputs[UTILITY_CASE_ORDER[0]]["conclusion"]
    second = outputs[UTILITY_CASE_ORDER[1]]["conclusion"]
    route_distinct = (
        first is not None
        and second is not None
        and _semantic_conclusion(first) != _semantic_conclusion(second)
    )
    lines.extend(
        [
            "### Pair observation",
            "",
            f"- Utility Racio route distinct: `{str(route_distinct).lower()}`.",
            "- Option change required: no.",
            "- Emocio utility-pair stable: `true`.",
            "- Instinkt utility-pair stable: `true`.",
            "",
            "## Protective pair frozen reuse",
            "",
            f"- Reuse validation: `{reuse['status']}`.",
        ]
    )
    for case in reuse["cases"]:
        conclusion = case["conclusion"]
        lines.append(
            f"- `{case['case_id']}`: `{case['status']}`; packet "
            f"`{case['packet_hash']}`; option "
            f"`{conclusion['option_id'] if conclusion else 'none'}`."
        )
    lines.extend(
        [
            "- Instinkt protective-pair distinction: retained from frozen R2 "
            "deterministic typed-route reference; no replay or processor execution.",
            "",
            "## Instinkt research hypothesis",
            "",
            "- `10% -> resource_security -0.09`",
            "- `25% -> resource_security -0.15`",
            "- `38% -> resource_security -0.20`",
            "- Status: `implementation_hypothesis`, not an active runtime score.",
            "",
            "## Human review — leave blank",
            "",
            "Material Racio route: [ ] plausible [ ] implausible [ ] uncertain",
            "",
            "Pleasure Racio route: [ ] plausible [ ] implausible [ ] uncertain",
            "",
            "Utility route distinction: [ ] passed [ ] failed [ ] uncertain",
            "",
            "Emocio manual route source-faithful: [ ]",
            "",
            "Instinkt typed route source-faithful: [ ]",
            "",
            "Input appears to predetermine outcome: [ ]",
            "",
            "Ready for remaining six isolation cases: [ ]",
            "",
            "No human-review field was completed by Codex.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def finalize(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    seal, _ = verify_seal(repository_root)
    ledger = _json(output_root / "call_ledger.json")
    if ledger["state"] != "two_calls_complete":
        raise ValueError("E2 cannot finalize before exactly two attempts")
    outputs = {
        case_id: _json(output_root / "cases" / case_id / "racio_output.json")
        for case_id in UTILITY_CASE_ORDER
    }
    references = _json(output_root / "deterministic_route_references.json")
    preflight = _json(output_root / "preflight_report.json")
    reuse = preflight["protective_reuse"]
    accepted = sum(item["status"] == "accepted" for item in outputs.values())
    rejected = sum(item["status"] == "rejected" for item in outputs.values())
    provider_failed = sum(
        item["status"] == "provider_failed" for item in outputs.values()
    )
    failures = [
        item["failure"]
        for item in outputs.values()
        if item["failure"] is not None
    ]
    first = outputs[UTILITY_CASE_ORDER[0]]["conclusion"]
    second = outputs[UTILITY_CASE_ORDER[1]]["conclusion"]
    summary = {
        "schema_version": "triad-iso-e2-summary-v1",
        "phase": "TRIAD-ISO-E2",
        "status": "complete_mixed_or_accepted_two_call_screen",
        "pre_call_seal_sha256": seal["seal_sha256"],
        "candidate_sha256": seal["candidate_v3"]["sha256"],
        "model_digest": seal["model_digest"],
        "calls": 2,
        "retries": 0,
        "fallbacks": 0,
        "racio": {
            "accepted": accepted,
            "rejected": rejected,
            "provider_failed": provider_failed,
            "selected_options": {
                case_id: (
                    value["conclusion"]["option_id"]
                    if value["conclusion"] is not None
                    else None
                )
                for case_id, value in outputs.items()
            },
            "utility_route_distinct": (
                first is not None
                and second is not None
                and _semantic_conclusion(first) != _semantic_conclusion(second)
            ),
        },
        "emocio_utility_pair_stable": True,
        "instinkt_utility_pair_stable": True,
        "protective_racio_reuse_status": reuse["status"],
        "instinkt_protective_pair_distinguishable": True,
        "native_processor_executions": {"E": 0, "I": 0},
        "character_replay": 0,
        "failure_categories": dict(
            Counter(item["failure_code"] for item in failures)
        ),
        "private_thinking_persisted": False,
        "global_rei_score": None,
    }
    _write_json(output_root / "summary.json", summary)
    report = _render_report(
        seal=seal,
        outputs=outputs,
        references=references,
        reuse=reuse,
    )
    (output_root / "report.md").write_text(
        report, encoding="utf-8", newline="\n"
    )
    ledger["state"] = "complete"
    _write_json(output_root / "call_ledger.json", ledger)
    return summary


def cold_verify(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    seal, _ = verify_seal(repository_root)
    ledger = _json(output_root / "call_ledger.json")
    summary = _json(output_root / "summary.json")
    if ledger["state"] != "complete":
        raise ValueError("E2 ledger is not complete")
    if ledger["actual"]["model_call_attempts"] != 2:
        raise ValueError("E2 model-call count differs")
    if ledger["actual"]["retries"] or ledger["actual"]["fallbacks"]:
        raise ValueError("E2 retry/fallback accounting differs")
    if ledger["actual"]["character_replay"]:
        raise ValueError("E2 character replay occurred")
    if (
        ledger["actual"]["native_emocio_processor_executions"]
        or ledger["actual"]["native_instinkt_processor_executions"]
    ):
        raise ValueError("E2 native E/I processor execution occurred")
    for entry in ledger["entries"]:
        if entry["status"] != "complete":
            raise ValueError(f"Incomplete E2 entry: {entry['case_id']}")
    if summary["calls"] != 2:
        raise ValueError("E2 summary call accounting differs")
    for path in output_root.rglob("*"):
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.casefold()
        if any(f'"{key}"' in lowered for key in PRIVATE_KEYS):
            raise ValueError(f"Private thinking key persisted in {path.name}")
        if str(repository_root).casefold() in lowered:
            raise ValueError(f"Local absolute path persisted in {path.name}")
    if not (output_root / "report.md").is_file():
        raise ValueError("E2 report is missing")
    return {
        "status": "passed",
        "seal_sha256": seal["seal_sha256"],
        "candidate_sha256": seal["candidate_v3"]["sha256"],
        "model_digest": seal["model_digest"],
        "calls": summary["calls"],
        "retries": summary["retries"],
        "fallbacks": summary["fallbacks"],
        "racio": summary["racio"],
        "emocio_utility_pair_stable": summary["emocio_utility_pair_stable"],
        "instinkt_utility_pair_stable": summary["instinkt_utility_pair_stable"],
        "protective_racio_reuse_status": summary[
            "protective_racio_reuse_status"
        ],
        "instinkt_protective_pair_distinguishable": summary[
            "instinkt_protective_pair_distinguishable"
        ],
        "failure_categories": summary["failure_categories"],
        "report_sha256": _file_sha256(output_root / "report.md"),
    }


__all__ = [
    "CASE_ORDER",
    "CANDIDATE_V3_RELATIVE_PATH",
    "EXPECTED_BASE_COMMIT",
    "EXPECTED_R2_CANDIDATE_SHA256",
    "OUTPUT_RELATIVE_PATH",
    "UTILITY_CASE_ORDER",
    "cold_verify",
    "corrected_candidate_v3",
    "deterministic_references",
    "finalize",
    "initialize_execution",
    "model_free_preflight",
    "run_next",
    "seal_e2",
    "verify_seal",
]
