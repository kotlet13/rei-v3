"""TRIAD-ISO-E3 three-pair native-route isolation execution.

Research-only execution: three pair-shared Racio calls plus deterministic
projections of explicit, source-addressed human annotations for Emocio and
Instinkt.  It contains no native E/I processor, character, governance, image,
shadow, or raw-scene path.
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

from ..emocio.policy import choose_native_option
from ..ids import canonical_json_bytes, content_id, sha256_hex, utc_now
from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText
from ..models.instinkt import (
    BodyDelta,
    BodyState,
    InstinktInputPacket,
    InstinktSimulationConfig,
)
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
    EMOCIO_OPTION_RELATION_FIELDS,
    compile_emocio_typed_annotation,
    project_emocio_typed_valuations,
    project_instinkt_typed_sensitivity,
    source_evidence_address,
    source_option_address,
)
from .triad_s2 import EXPECTED_MODEL_DIGEST, MODEL_PROFILE, build_provider


EXPECTED_BASE_COMMIT: Final = "429d80ad3dbc6aaecdf6e42b0872011abee3eaa9"
SOURCE_CANDIDATE_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-p1-2026-07-23/"
    "route_isolation_corpus_candidate.json"
)
EXPECTED_SOURCE_CANDIDATE_SHA256: Final = (
    "e9e1608b5eb3e472e6953c310749f21b676013602d5658849ab36356701144aa"
)
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-e3-2026-07-24"
)
PAIR_ORDER: Final = (
    "public_credit_audience",
    "loan_attachment_distance",
    "factory_public_status",
)
PAIR_CASES: Final[Mapping[str, tuple[str, str]]] = {
    "public_credit_audience": (
        "public_credit_audience_visible",
        "public_credit_audience_absent",
    ),
    "loan_attachment_distance": (
        "loan_attachment_distance_close",
        "loan_attachment_distance_distant",
    ),
    "factory_public_status": (
        "factory_public_status_visible",
        "factory_public_status_anonymous",
    ),
}
CASE_ORDER: Final = tuple(
    case_id for pair_id in PAIR_ORDER for case_id in PAIR_CASES[pair_id]
)
SEMANTIC_ADDRESSES: Final[Mapping[str, str]] = {
    "f3823c9d4245c45b12493c20d0c20f1537116abe5b9a2b44065679eec9068949": (
        "public_visible"
    ),
    "b27859cf29194b2d43eb8fe29596f89a32f1e563b0f30bde642d9d6037abe9bb": (
        "public_absent"
    ),
    "d3aecbeaffe3c3e93cc2635fbaee75118d691b44550cc9bbdcbb43c4f584e7ca": (
        "loan_close"
    ),
    "d9eb794bb1393690d3a8dc84902682d3957f9e19d3b9e5c2a676e7db49670bc3": (
        "loan_distant"
    ),
    "2ff3e30a5c61d10e678638d7b142645e01767c962ff0d680ac3583c54acc32b2": (
        "factory_visible"
    ),
    "61c5caf3cbf3b041cea692eabf508b8835e8e013f5058cf9bd07ef482aaefb93": (
        "factory_anonymous"
    ),
}
EXECUTION_POLICY: Final[Mapping[str, Any]] = {
    "call_order": PAIR_ORDER,
    "pair_shared_racio_calls": 3,
    "retries": 0,
    "fallbacks": 0,
    "character_replay": 0,
    "native_emocio_processor_executions": 0,
    "native_instinkt_processor_executions": 0,
}
PRIVATE_KEYS: Final = frozenset(
    {"thinking", "thoughts", "reasoning_content", "chain_of_thought"}
)
LEAKAGE_KEYS: Final = frozenset(
    {
        "expected_option",
        "expected_option_id",
        "expected_action",
        "leading_mind",
        "gold_route",
        "preferred_option",
        "option_flip_target",
        "character",
        "character_profile",
        "governance",
        "governance_tier",
    }
)


E3_EFFECT_RULES: Final[Mapping[str, Mapping[str, float]]] = {
    "authorship_boundary_asserted": {"boundary_integrity": 0.15},
    "official_correction_recovery": {
        "boundary_integrity": 0.08,
        "predictability": 0.10,
    },
    "official_recovery_assessment_unknown": {
        "predictability": -0.05,
        "uncertainty": 0.08,
    },
    "named_group_exposure": {
        "escape_availability": -0.08,
        "tension": 0.08,
    },
    "unknown_social_response": {"trust": -0.05, "uncertainty": 0.08},
    "authorship_boundary_unasserted": {"boundary_integrity": -0.15},
    "resource_exposure_45": {"resource_security": -0.20},
    "resource_exposure_15": {"resource_security": -0.11},
    "resource_preserved": {"resource_security": 0.15},
    "late_repayment_distrust": {"trust": -0.12, "uncertainty": 0.10},
    "no_new_contract_boundary": {"boundary_integrity": -0.15},
    "written_repayment_boundary": {
        "boundary_integrity": 0.15,
        "predictability": 0.08,
    },
    "irreversible_transfer": {"escape_availability": -0.10},
    "repayment_recovery_unknown": {
        "predictability": -0.08,
        "uncertainty": 0.08,
    },
    "genuine_need_fully_met": {
        "attachment_security": 0.08,
        "tension": -0.04,
    },
    "genuine_need_partly_met": {
        "attachment_security": 0.04,
        "tension": -0.02,
    },
    "genuine_need_unmet": {"tension": 0.08},
    "close_attachment_care": {
        "attachment_security": 0.12,
        "trust": 0.05,
    },
    "close_attachment_loss_unknown": {
        "attachment_security": -0.12,
        "uncertainty": 0.08,
    },
    "shutdown_escape": {
        "escape_availability": 0.20,
        "predictability": 0.10,
    },
    "shutdown_resource_loss": {"resource_security": -0.15},
    "sensor_truth_unknown": {
        "predictability": -0.08,
        "uncertainty": 0.08,
    },
    "damage_state_unknown": {"uncertainty": 0.08},
    "verification_exposure": {"tension": 0.08, "uncertainty": 0.08},
    "verification_information": {"predictability": 0.08},
    "continued_heat_exposure": {
        "physical_integrity": -0.20,
        "tension": 0.12,
        "uncertainty": 0.10,
    },
}


class E3EvidenceAssertion(FrozenModel):
    evidence_id: NonEmptyId
    source_text_sha256: HashDigest
    assertions: tuple[NonEmptyId, ...] = Field(min_length=1)


class E3EffectCategory(FrozenModel):
    category_id: NonEmptyId
    option_id: NonEmptyId
    supporting_evidence_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    semantic_predicate: NonEmptyId
    body_deltas: tuple[BodyDelta, ...]

    @model_validator(mode="after")
    def fixed_rule(self) -> "E3EffectCategory":
        expected = E3_EFFECT_RULES.get(self.semantic_predicate)
        if expected is None or self.category_id != self.semantic_predicate:
            raise ValueError("Unknown or non-canonical E3 effect category")
        observed = {item.dimension: item.delta for item in self.body_deltas}
        if observed != expected:
            raise ValueError("E3 body deltas differ from the frozen rule")
        return self


class E3OptionEffect(FrozenModel):
    option_id: NonEmptyId
    source_option_sha256: HashDigest
    source_consequence: NonEmptyText
    source_evidence_scope_ids: tuple[NonEmptyId, ...]
    categories: tuple[E3EffectCategory, ...]


class E3TypedMapping(FrozenModel):
    schema_version: str = "triad-instinkt-e3-typed-route-mapping-v1"
    mapping_mode: str = "explicit_source_addressed_for_human_review"
    source_evidence_sha256: HashDigest
    protected_target_label: NonEmptyText
    evidence_assertions: tuple[E3EvidenceAssertion, ...]
    option_effects: tuple[E3OptionEffect, ...] = Field(min_length=2)


def _semantic_address(case: Mapping[str, Any]) -> str:
    source = case["operational_en"]
    value = {
        "facts": source["facts"],
        "unknowns": source["unknowns"],
        "option_descriptions": sorted(
            item["description"] for item in source["options"]
        ),
    }
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _semantic_kind(case: Mapping[str, Any]) -> str:
    address = _semantic_address(case)
    if address not in SEMANTIC_ADDRESSES:
        raise ValueError("No reviewed E3 route annotation for source address")
    return SEMANTIC_ADDRESSES[address]


def _source_texts(case: Mapping[str, Any]) -> dict[str, str]:
    source = case["operational_en"]
    return {
        **{item["evidence_id"]: item["text"] for item in source["facts"]},
        **{item["unknown_id"]: item["text"] for item in source["unknowns"]},
    }


def _option_by_description(
    case: Mapping[str, Any], description: str
) -> Mapping[str, Any]:
    matches = [
        item
        for item in case["operational_en"]["options"]
        if item["description"] == description
    ]
    if len(matches) != 1:
        raise ValueError("Reviewed E3 option description is not unique")
    return matches[0]


def _rel(
    value: str | None = None,
    evidence_ids: Sequence[str] = (),
    *,
    state: str = "grounded",
) -> Mapping[str, Any]:
    if state == "not_relevant":
        return {"state": state, "value": None, "evidence_ids": []}
    return {
        "state": state,
        "value": value,
        "evidence_ids": sorted(set(evidence_ids)),
    }


def _emocio_option(
    case: Mapping[str, Any],
    description: str,
    evidence_ids: Sequence[str],
    *,
    target: str,
    self_position: str,
    movement: str,
    immediacy: str,
    obstacle: str,
    desired: str,
    broken: str,
    attention: str,
    status: str,
    competition: str,
    belonging: str,
    desired_state: str = "grounded",
    status_state: str = "grounded",
) -> Mapping[str, Any]:
    option = _option_by_description(case, description)
    evidence = tuple(sorted(set(evidence_ids)))
    absent = _rel("absent", evidence)
    return {
        "option_id": option["option_id"],
        "source_option_sha256": source_option_address(
            case, option["option_id"]
        ),
        "source_evidence_scope_ids": evidence,
        "target_scene_identity": _rel(target, evidence),
        "self_position_relation": _rel(self_position, evidence),
        "attraction_target": _rel(state="not_relevant"),
        "attraction_strength": absent,
        "movement_destination": (
            _rel(target, evidence)
            if movement != "none"
            else _rel(state="not_relevant")
        ),
        "movement_magnitude": _rel(movement, evidence),
        "immediacy": _rel(immediacy, evidence),
        "novelty_strength": absent,
        "obstacle_relation": _rel(obstacle, evidence),
        "desired_state_relation": _rel(
            desired, evidence, state=desired_state
        ),
        "broken_state_relation": _rel(broken, evidence),
        "attention_relation": _rel(attention, evidence),
        "status_relation": _rel(status, evidence, state=status_state),
        "competition_relation": _rel(competition, evidence),
        "belonging_relation": _rel(belonging, evidence),
    }


def author_emocio_annotation(case: Mapping[str, Any]) -> Mapping[str, Any]:
    kind = _semantic_kind(case)
    options: list[Mapping[str, Any]]
    if kind in {"public_visible", "public_absent"}:
        visible = kind == "public_visible"
        options = [
            _emocio_option(
                case,
                "Display the record during the meeting and challenge the statement immediately.",
                (
                    "credit_ev_claim",
                    "credit_ev_record",
                    "credit_ev_audience",
                    "credit_ev_positions",
                    "credit_ev_recognition",
                ),
                target="visible_authorship_correction",
                self_position="centered_in_result_scene",
                movement="bounded",
                immediacy="immediate",
                obstacle="transformed",
                desired="aligned",
                broken="partial_escape",
                attention="stronger" if visible else "present",
                status="present",
                competition="present",
                belonging="present",
                desired_state="bounded_unknown",
                status_state="bounded_unknown",
            ),
            _emocio_option(
                case,
                "Display the record privately to the leader after the meeting.",
                ("credit_ev_record", "credit_ev_correction"),
                target="leader_facing_correction",
                self_position="centered_in_result_scene",
                movement="bounded",
                immediacy="bounded",
                obstacle="transformed",
                desired="partial",
                broken="partial_escape",
                attention="present",
                status="absent",
                competition="present",
                belonging="absent",
            ),
            _emocio_option(
                case,
                "Do not display the record or raise the authorship issue.",
                ("credit_ev_claim", "credit_ev_positions"),
                target="unchanged_authorship_scene",
                self_position="centered_at_decision",
                movement="none",
                immediacy="none",
                obstacle="persists",
                desired="not_aligned",
                broken="remains",
                attention="absent",
                status="absent",
                competition="absent",
                belonging="absent",
            ),
        ]
    elif kind in {"loan_close", "loan_distant"}:
        options = [
            _emocio_option(
                case,
                "Lend the full EUR 9000 without a new contract.",
                ("loan_ev_need", "loan_ev_terms"),
                target="full_transfer_scene",
                self_position="centered_in_result_scene",
                movement="bounded",
                immediacy="immediate",
                obstacle="transformed",
                desired="partial",
                broken="partial_escape",
                attention="present",
                status="absent",
                competition="absent",
                belonging="absent",
                desired_state="bounded_unknown",
            ),
            _emocio_option(
                case,
                "Lend EUR 3000 with a written twelve-month repayment date.",
                ("loan_ev_need", "loan_ev_terms"),
                target="partial_transfer_scene",
                self_position="centered_in_result_scene",
                movement="bounded",
                immediacy="immediate",
                obstacle="transformed",
                desired="partial",
                broken="partial_escape",
                attention="present",
                status="absent",
                competition="absent",
                belonging="absent",
                desired_state="bounded_unknown",
            ),
            _emocio_option(
                case,
                "Lend no money.",
                ("loan_ev_need",),
                target="no_transfer_scene",
                self_position="centered_at_decision",
                movement="none",
                immediacy="immediate",
                obstacle="persists",
                desired="not_aligned",
                broken="remains",
                attention="present",
                status="absent",
                competition="absent",
                belonging="absent",
                desired_state="bounded_unknown",
            ),
        ]
    else:
        visible = kind == "factory_visible"
        common_attention = "present" if visible else "absent"
        common_status = "present" if visible else "absent"
        common_belonging = "present" if visible else "absent"
        common_state = "bounded_unknown" if visible else "grounded"
        options = [
            _emocio_option(
                case,
                "Execute a controlled shutdown immediately.",
                (
                    "factory_ev_damage",
                    "factory_ev_audience",
                    "factory_ev_status",
                ),
                target="shutdown_control_scene",
                self_position="centered_in_result_scene",
                movement="bounded",
                immediacy="immediate",
                obstacle="removed",
                desired="aligned",
                broken="escaped",
                attention=common_attention,
                status=common_status,
                competition="absent",
                belonging=common_belonging,
                status_state=common_state,
            ),
            _emocio_option(
                case,
                "Verify both sensors for no more than three minutes and then decide again.",
                (
                    "factory_ev_sensor",
                    "factory_ev_time",
                    "factory_ev_audience",
                    "factory_ev_status",
                ),
                target="verification_control_scene",
                self_position="centered_in_result_scene",
                movement="bounded",
                immediacy="immediate",
                obstacle="transformed",
                desired="partial",
                broken="partial_escape",
                attention=common_attention,
                status=common_status,
                competition="absent",
                belonging=common_belonging,
                status_state=common_state,
            ),
            _emocio_option(
                case,
                "Continue production at the current settings.",
                (
                    "factory_ev_temperature",
                    "factory_ev_audience",
                    "factory_ev_status",
                ),
                target="continued_production_scene",
                self_position="centered_at_decision",
                movement="bounded",
                immediacy="immediate",
                obstacle="persists",
                desired="not_aligned",
                broken="remains",
                attention=common_attention,
                status=common_status,
                competition="absent",
                belonging=common_belonging,
                status_state=common_state,
            ),
        ]
    return {
        "schema_version": "triad-emocio-typed-route-annotation-v1",
        "annotation_mode": "explicit_source_addressed_for_human_review",
        "source_evidence_sha256": source_evidence_address(case),
        "companion_visible": _rel(state="not_relevant"),
        "companion_enjoyment_relation": _rel(state="not_relevant"),
        "options": options,
    }


def _assertion(
    case: Mapping[str, Any], evidence_id: str, *assertions: str
) -> Mapping[str, Any]:
    texts = _source_texts(case)
    return {
        "evidence_id": evidence_id,
        "source_text_sha256": sha256_hex(texts[evidence_id]),
        "assertions": sorted(set(assertions)),
    }


def _category(
    option_id: str, predicate: str, evidence_ids: Sequence[str]
) -> Mapping[str, Any]:
    return {
        "category_id": predicate,
        "option_id": option_id,
        "supporting_evidence_ids": sorted(set(evidence_ids)),
        "semantic_predicate": predicate,
        "body_deltas": [
            {"dimension": key, "delta": value}
            for key, value in sorted(E3_EFFECT_RULES[predicate].items())
        ],
    }


def _mapping_option(
    case: Mapping[str, Any],
    description: str,
    consequence: str,
    categories: Sequence[tuple[str, Sequence[str]]],
) -> Mapping[str, Any]:
    option = _option_by_description(case, description)
    scope = sorted(
        {
            evidence_id
            for _, evidence_ids in categories
            for evidence_id in evidence_ids
        }
    )
    return {
        "option_id": option["option_id"],
        "source_option_sha256": source_option_address(
            case, option["option_id"]
        ),
        "source_consequence": consequence,
        "source_evidence_scope_ids": scope,
        "categories": sorted(
            (
                _category(option["option_id"], predicate, evidence_ids)
                for predicate, evidence_ids in categories
            ),
            key=lambda value: value["category_id"],
        ),
    }


def author_instinkt_mapping(case: Mapping[str, Any]) -> Mapping[str, Any]:
    kind = _semantic_kind(case)
    assertions: list[Mapping[str, Any]]
    options: list[Mapping[str, Any]]
    if kind in {"public_visible", "public_absent"}:
        visible = kind == "public_visible"
        assertions = [
            _assertion(case, "credit_ev_claim", "authorship_boundary_loss"),
            _assertion(case, "credit_ev_record", "authorship_boundary_evidence"),
            _assertion(case, "credit_ev_correction", "official_recovery_path"),
            _assertion(
                case,
                "credit_unknown_leader_assessment",
                "official_recovery_assessment_unknown",
            ),
            _assertion(
                case,
                "credit_unknown_colleague_response",
                "unknown_social_response",
            ),
        ]
        if visible:
            assertions.append(
                _assertion(case, "credit_ev_audience", "named_group_exposure")
            )
        public_categories = [
            ("authorship_boundary_asserted", ("credit_ev_record",)),
            (
                "official_correction_recovery",
                ("credit_ev_correction",),
            ),
            (
                "official_recovery_assessment_unknown",
                ("credit_unknown_leader_assessment",),
            ),
            (
                "unknown_social_response",
                ("credit_unknown_colleague_response",),
            ),
        ]
        if visible:
            public_categories.append(
                ("named_group_exposure", ("credit_ev_audience",))
            )
        options = [
            _mapping_option(
                case,
                "Display the record during the meeting and challenge the statement immediately.",
                "The authorship boundary is asserted immediately; official recovery and colleague response remain uncertain.",
                public_categories,
            ),
            _mapping_option(
                case,
                "Display the record privately to the leader after the meeting.",
                "The authorship boundary is asserted to the leader through the same official recovery mechanism.",
                (
                    ("authorship_boundary_asserted", ("credit_ev_record",)),
                    (
                        "official_correction_recovery",
                        ("credit_ev_correction",),
                    ),
                    (
                        "official_recovery_assessment_unknown",
                        ("credit_unknown_leader_assessment",),
                    ),
                ),
            ),
            _mapping_option(
                case,
                "Do not display the record or raise the authorship issue.",
                "No social exposure is added, while the authorship boundary remains unasserted.",
                (
                    (
                        "authorship_boundary_unasserted",
                        ("credit_ev_claim",),
                    ),
                ),
            ),
        ]
        protected = "Self's authorship boundary and recoverable work-group position."
    elif kind in {"loan_close", "loan_distant"}:
        close = kind == "loan_close"
        assertions = [
            _assertion(case, "loan_ev_need", "genuine_need"),
            _assertion(case, "loan_ev_history", "late_repayment_history"),
            _assertion(case, "loan_ev_reserve", "resource_exposure_45"),
            _assertion(
                case,
                "loan_ev_terms",
                "full_no_new_contract",
                "limited_written_boundary",
                "transfer_irreversible",
            ),
            _assertion(
                case, "loan_unknown_repayment", "repayment_recovery_unknown"
            ),
        ]
        if close:
            assertions.extend(
                [
                    _assertion(
                        case, "loan_ev_relationship", "close_attachment_history"
                    ),
                    _assertion(
                        case, "loan_ev_attachment", "fear_of_attachment_loss"
                    ),
                ]
            )
        full_categories = [
            ("resource_exposure_45", ("loan_ev_reserve",)),
            ("late_repayment_distrust", ("loan_ev_history",)),
            ("no_new_contract_boundary", ("loan_ev_terms",)),
            ("irreversible_transfer", ("loan_ev_terms",)),
            (
                "repayment_recovery_unknown",
                ("loan_unknown_repayment",),
            ),
            ("genuine_need_fully_met", ("loan_ev_need",)),
        ]
        limited_categories = [
            ("resource_exposure_15", ("loan_ev_reserve", "loan_ev_terms")),
            ("late_repayment_distrust", ("loan_ev_history",)),
            ("written_repayment_boundary", ("loan_ev_terms",)),
            ("irreversible_transfer", ("loan_ev_terms",)),
            (
                "repayment_recovery_unknown",
                ("loan_unknown_repayment",),
            ),
            ("genuine_need_partly_met", ("loan_ev_need",)),
        ]
        decline_categories = [
            ("resource_preserved", ("loan_ev_reserve",)),
            ("genuine_need_unmet", ("loan_ev_need",)),
        ]
        if close:
            full_categories.append(
                ("close_attachment_care", ("loan_ev_relationship",))
            )
            limited_categories.append(
                ("close_attachment_care", ("loan_ev_relationship",))
            )
            decline_categories.append(
                (
                    "close_attachment_loss_unknown",
                    ("loan_ev_attachment",),
                )
            )
        options = [
            _mapping_option(
                case,
                "Lend the full EUR 9000 without a new contract.",
                "The genuine need is fully funded while 45 percent of reserve is exposed without a new contract.",
                full_categories,
            ),
            _mapping_option(
                case,
                "Lend EUR 3000 with a written twelve-month repayment date.",
                "The genuine need is partly funded under a written boundary while transfer recovery remains uncertain.",
                limited_categories,
            ),
            _mapping_option(
                case,
                "Lend no money.",
                "The reserve is retained while the genuine need remains unfunded by self.",
                decline_categories,
            ),
        ]
        protected = (
            "Self's reserve and repayment boundary, the grounded need, and "
            "close attachment only when source-addressed."
        )
    else:
        assertions = [
            _assertion(case, "factory_ev_temperature", "continued_heat"),
            _assertion(case, "factory_ev_sensor", "conflicting_signal"),
            _assertion(case, "factory_ev_time", "three_minute_exposure"),
            _assertion(case, "factory_ev_damage", "equipment_damage"),
            _assertion(
                case, "factory_ev_shutdown_loss", "shutdown_resource_loss"
            ),
            _assertion(
                case, "factory_unknown_sensor", "sensor_truth_unknown"
            ),
            _assertion(
                case, "factory_unknown_damage", "damage_state_unknown"
            ),
        ]
        options = [
            _mapping_option(
                case,
                "Execute a controlled shutdown immediately.",
                "Heat input stops while the stated EUR 75000 resource loss occurs.",
                (
                    ("shutdown_escape", ("factory_ev_damage",)),
                    (
                        "shutdown_resource_loss",
                        ("factory_ev_shutdown_loss",),
                    ),
                    (
                        "sensor_truth_unknown",
                        ("factory_unknown_sensor",),
                    ),
                    (
                        "damage_state_unknown",
                        ("factory_unknown_damage",),
                    ),
                ),
            ),
            _mapping_option(
                case,
                "Verify both sensors for no more than three minutes and then decide again.",
                "Information can improve while exposure continues for up to three minutes.",
                (
                    (
                        "verification_exposure",
                        ("factory_ev_time", "factory_ev_damage"),
                    ),
                    ("verification_information", ("factory_ev_sensor",)),
                    (
                        "sensor_truth_unknown",
                        ("factory_unknown_sensor",),
                    ),
                    (
                        "damage_state_unknown",
                        ("factory_unknown_damage",),
                    ),
                ),
            ),
            _mapping_option(
                case,
                "Continue production at the current settings.",
                "Rising-heat exposure and possible equipment damage continue.",
                (
                    (
                        "continued_heat_exposure",
                        ("factory_ev_temperature", "factory_ev_damage"),
                    ),
                    (
                        "sensor_truth_unknown",
                        ("factory_unknown_sensor",),
                    ),
                    (
                        "damage_state_unknown",
                        ("factory_unknown_damage",),
                    ),
                ),
            ),
        ]
        protected = (
            "Operator and equipment integrity, escape from escalating heat, "
            "and recoverable plant resources."
        )
    return {
        "schema_version": "triad-instinkt-e3-typed-route-mapping-v1",
        "mapping_mode": "explicit_source_addressed_for_human_review",
        "source_evidence_sha256": source_evidence_address(case),
        "protected_target_label": protected,
        "evidence_assertions": sorted(
            assertions, key=lambda value: value["evidence_id"]
        ),
        "option_effects": sorted(
            options, key=lambda value: value["option_id"]
        ),
    }


def compile_instinkt_mapping(
    case: Mapping[str, Any], value: Mapping[str, Any]
) -> E3TypedMapping:
    mapping = validate_json_projection(E3TypedMapping, value)
    if mapping.source_evidence_sha256 != source_evidence_address(case):
        raise ValueError("E3 Instinkt source address differs")
    texts = _source_texts(case)
    assertions = {item.evidence_id: item for item in mapping.evidence_assertions}
    options = {
        item["option_id"]: item for item in case["operational_en"]["options"]
    }
    if {item.option_id for item in mapping.option_effects} != set(options):
        raise ValueError("E3 Instinkt mapping does not cover public options")
    for evidence_id, assertion in assertions.items():
        if evidence_id not in texts:
            raise ValueError("E3 Instinkt assertion cites unknown source")
        if assertion.source_text_sha256 != sha256_hex(texts[evidence_id]):
            raise ValueError("E3 Instinkt assertion text address differs")
    for effect in mapping.option_effects:
        if effect.source_option_sha256 != source_option_address(
            case, effect.option_id
        ):
            raise ValueError("E3 Instinkt option address differs")
        if not set(effect.source_evidence_scope_ids).issubset(assertions):
            raise ValueError("E3 Instinkt effect lacks source assertions")
        for category in effect.categories:
            if category.option_id != effect.option_id:
                raise ValueError("E3 Instinkt category belongs to another option")
            if not set(category.supporting_evidence_ids).issubset(
                effect.source_evidence_scope_ids
            ):
                raise ValueError("E3 Instinkt category crosses option scope")
    return mapping


def _instinkt_projection(
    case: Mapping[str, Any], mapping: E3TypedMapping
) -> Mapping[str, Any]:
    source = case["operational_en"]
    route = case["route_packets"]["instinkt"]
    body_base = {
        "energy": 0.70,
        "fatigue": 0.20,
        "pain": 0.00,
        "arousal": 0.40,
        "tension": 0.40,
        "physical_integrity": 0.90,
        "uncertainty": 0.50,
        "trust": 0.50,
        "attachment_security": 0.50,
        "resource_security": 0.70,
        "boundary_integrity": 0.50,
        "escape_availability": 0.50,
        "predictability": 0.50,
    }
    body = BodyState(
        body_state_id=content_id("triad_iso_e3_body", body_base),
        **body_base,
    )
    packet_base = {
        "scene_id": content_id(
            "triad_iso_e3_instinkt_scene",
            {
                "event": source["event"],
                "options": source["options"],
                "source_address": _semantic_address(case),
            },
        ),
        "source_body_state_id": body.body_state_id,
        "physical_cues": (route["danger_types"], route["possible_loss"]),
        "uncertainty_cues": (
            route["trust_distrust"],
            route["recoverability"],
        ),
        "trust_cues": (route["trust_distrust"],),
        "boundary_cues": (route["boundary"],),
        "attachment_cues": (route["attachment_care"],),
        "scarcity_cues": (route["scarcity"],),
        "escape_cues": (
            route["escape_reversibility"],
            route["recoverability"],
        ),
        "explicit_body_cues": (),
        "option_ids": tuple(
            sorted(item["option_id"] for item in source["options"])
        ),
        "evidence_ids": tuple(
            sorted(item.evidence_id for item in mapping.evidence_assertions)
        ),
        "caveat": (
            "TRIAD-ISO-E3 model-free source-addressed typed mapping; no "
            "native processor, expected option, character, or governance."
        ),
    }
    packet = InstinktInputPacket(
        packet_id=content_id("triad_iso_e3_instinkt_packet", packet_base),
        **packet_base,
    )
    config = InstinktSimulationConfig.create()
    base_effects = {
        option_id: {
            "option_id": option_id,
            "base_predicted_loss": 0.40,
            "base_recoverability": 0.50,
            "minimum_safety_condition": (
                "Retain the source-stated boundary and recovery conditions."
            ),
        }
        for option_id in packet.option_ids
    }
    projected = project_instinkt_typed_sensitivity(
        mapping=mapping,  # type: ignore[arg-type]
        packet=packet,
        body_state=body,
        config=config,
        base_effects=base_effects,
    )
    return {
        "mapping": mapping.model_dump(mode="json"),
        "mapping_sha256": _object_sha256(mapping.model_dump(mode="json")),
        "category_evidence_closure": "passed",
        **_projection(projected),
        "typed_mapping": True,
        "processor_capability_claimed": False,
        "native_processor_executions": 0,
        "model_calls": 0,
    }


def _load_source_candidate(repository_root: Path) -> Mapping[str, Any]:
    path = repository_root / SOURCE_CANDIDATE_RELATIVE_PATH
    if _file_sha256(path) != EXPECTED_SOURCE_CANDIDATE_SHA256:
        raise ValueError("Frozen TRIAD-ISO-P1 source candidate bytes changed")
    return _json(path)


def execution_candidate(repository_root: Path) -> Mapping[str, Any]:
    source = _load_source_candidate(repository_root)
    pairs = []
    source_pairs = {item["pair_id"]: item for item in source["pairs"]}
    for pair_id in PAIR_ORDER:
        pair = source_pairs[pair_id]
        variants = copy.deepcopy(pair["variants"])
        if tuple(item["case_id"] for item in variants) != PAIR_CASES[pair_id]:
            raise ValueError(f"Frozen P1 variant order changed for {pair_id}")
        pairs.append(
            {
                "pair_id": pair_id,
                "isolation_target": pair["isolation_target"],
                "variant_fact_ids": pair["variant_fact_ids"],
                "variants": variants,
            }
        )
    return {
        "schema_version": "triad-iso-e3-execution-candidate-v1",
        "status": "unsealed_candidate",
        "execution_authorized": False,
        "human_review_status": "approved_for_triad_iso_e3_exact_scope",
        "source_candidate": {
            "path": SOURCE_CANDIDATE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_SOURCE_CANDIDATE_SHA256,
        },
        "pair_order": PAIR_ORDER,
        "case_order": CASE_ORDER,
        "pairs": pairs,
        "model_calls": 0,
        "character_replay": 0,
    }


def _corrected_racio_route(
    pair_id: str, route: Mapping[str, Any]
) -> Mapping[str, Any]:
    value = copy.deepcopy(route)
    if pair_id == "public_credit_audience":
        value["explicit_goal"] = (
            "Preserve accurate and enforceable authorship attribution in the "
            "official record while controlling interruption and uncertainty."
        )
    elif pair_id == "loan_attachment_distance":
        value["explicit_goal"] = (
            "Protect self's liquidity, ownership of funds, and enforceable "
            "repayment position while responding to the request."
        )
    else:
        value["facts"] = [
            item
            for item in value["facts"]
            if item != "factory_ev_retaliation"
        ]
        value["explicit_goal"] = (
            "Minimize expected technical and financial loss under the "
            "three-minute decision boundary while retaining stated uncertainty."
        )
    return value


def _shared_preparations(
    candidate: Mapping[str, Any], provider: Any
) -> list[Mapping[str, Any]]:
    prepared = []
    for pair in candidate["pairs"]:
        pair_id = pair["pair_id"]
        variants = []
        for source_case in pair["variants"]:
            case = copy.deepcopy(source_case)
            case["route_packets"]["racio"] = _corrected_racio_route(
                pair_id, source_case["route_packets"]["racio"]
            )
            scene, world, packet, call_spec, request_payload = (
                _racio_preparation(case, provider)
            )
            variants.append(
                {
                    "case_id": case["case_id"],
                    "scene": scene,
                    "world": world,
                    "packet": packet,
                    "call_spec": call_spec,
                    "request_payload": request_payload,
                }
            )
        if variants[0]["packet"].content_hash() != variants[1][
            "packet"
        ].content_hash():
            raise ValueError(f"Pair-shared Racio packet differs: {pair_id}")
        if variants[0]["request_payload"] != variants[1]["request_payload"]:
            raise ValueError(f"Pair-shared Racio payload differs: {pair_id}")
        prepared.append(
            {
                "pair_id": pair_id,
                "variants": variants,
                **{
                    key: variants[0][key]
                    for key in (
                        "scene",
                        "world",
                        "packet",
                        "call_spec",
                        "request_payload",
                    )
                },
            }
        )
    return prepared


def _packet_explicit_goal(packet: RacioInputPacket) -> str:
    prefix = "Explicit goal: "
    goals = [
        cue.removeprefix(prefix)
        for cue in packet.symbolic_and_language_cues
        if cue.startswith(prefix)
    ]
    if len(goals) != 1:
        raise ValueError("Racio packet must expose exactly one explicit goal")
    return goals[0]


def deterministic_references(
    candidate: Mapping[str, Any]
) -> Mapping[str, Any]:
    cases = {}
    for pair in candidate["pairs"]:
        for case in pair["variants"]:
            annotation = compile_emocio_typed_annotation(
                case, author_emocio_annotation(case)
            )
            valuations = project_emocio_typed_valuations(annotation)
            decision = choose_native_option(valuations)
            mapping = compile_instinkt_mapping(
                case, author_instinkt_mapping(case)
            )
            cases[case["case_id"]] = {
                "pair_id": pair["pair_id"],
                "emocio": {
                    "annotation": annotation.model_dump(mode="json"),
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
                        item.option_id: item.score
                        for item in decision.aggregate_scores
                    },
                    "selected_option_id": (
                        decision.selected.option_id
                        if decision.selected is not None
                        else None
                    ),
                    "tied_option_ids": decision.tied_option_ids,
                    "manual_annotation": True,
                    "processor_capability_claimed": False,
                    "native_processor_executions": 0,
                    "model_calls": 0,
                },
                "instinkt": _instinkt_projection(case, mapping),
            }
    return {
        "schema_version": "triad-iso-e3-deterministic-references-v1",
        "cases": cases,
        "native_processor_executions": {"E": 0, "I": 0},
        "model_calls": 0,
    }


def _normalized_by_description(
    case: Mapping[str, Any], values: Mapping[str, Any]
) -> Mapping[str, Any]:
    descriptions = {
        item["option_id"]: item["description"]
        for item in case["operational_en"]["options"]
    }
    return {
        descriptions[option_id]: value
        for option_id, value in values.items()
    }


def _replace_opaque_option_ids(
    value: Any, renames: Mapping[str, str]
) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _replace_opaque_option_ids(child, renames)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_replace_opaque_option_ids(child, renames) for child in value]
    if isinstance(value, tuple):
        return tuple(
            _replace_opaque_option_ids(child, renames) for child in value
        )
    if isinstance(value, str):
        return renames.get(value, value)
    return value


def _semantic_instinkt_results(
    case: Mapping[str, Any], projection: Mapping[str, Any]
) -> Mapping[str, Any]:
    descriptions = {
        item["option_id"]: item["description"]
        for item in case["operational_en"]["options"]
    }
    return {
        descriptions[item["option_id"]]: {
            key: value
            for key, value in item.items()
            if key != "option_id"
        }
        for item in projection["option_results"]
    }


def _opaque_and_order_invariance(
    candidate: Mapping[str, Any]
) -> Mapping[str, bool]:
    checks: dict[str, bool] = {}
    for pair in candidate["pairs"]:
        for source_case in pair["variants"]:
            original_case = copy.deepcopy(source_case)
            original_annotation = compile_emocio_typed_annotation(
                original_case, author_emocio_annotation(original_case)
            )
            original_e = _normalized_by_description(
                original_case,
                {
                    item.option_id: {
                        dimension.name: dimension.score
                        for dimension in item.dimensions
                    }
                    for item in project_emocio_typed_valuations(
                        original_annotation
                    )
                },
            )
            original_mapping = compile_instinkt_mapping(
                original_case, author_instinkt_mapping(original_case)
            )
            original_i = _semantic_instinkt_results(
                original_case,
                _instinkt_projection(original_case, original_mapping),
            )

            option_ids = [
                item["option_id"]
                for item in original_case["operational_en"]["options"]
            ]
            renames = {
                option_id: f"opaque_option_{index + 1}"
                for index, option_id in enumerate(option_ids)
            }
            opaque_case = _replace_opaque_option_ids(
                copy.deepcopy(original_case), renames
            )
            opaque_case["case_id"] = "opaque_case"
            for language in ("canonical_sl", "operational_en"):
                opaque_case[language]["options"].reverse()
            opaque_case["route_packets"]["emocio"][
                "option_visible_changes"
            ].reverse()
            opaque_case["route_packets"]["instinkt"][
                "option_consequences"
            ].reverse()

            opaque_annotation = compile_emocio_typed_annotation(
                opaque_case, author_emocio_annotation(opaque_case)
            )
            opaque_e = _normalized_by_description(
                opaque_case,
                {
                    item.option_id: {
                        dimension.name: dimension.score
                        for dimension in item.dimensions
                    }
                    for item in project_emocio_typed_valuations(
                        opaque_annotation
                    )
                },
            )
            opaque_mapping = compile_instinkt_mapping(
                opaque_case, author_instinkt_mapping(opaque_case)
            )
            opaque_i = _semantic_instinkt_results(
                opaque_case,
                _instinkt_projection(opaque_case, opaque_mapping),
            )
            checks[source_case["case_id"]] = (
                original_e == opaque_e and original_i == opaque_i
            )
    return checks


def _leakage_free(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in LEAKAGE_KEYS | PRIVATE_KEYS:
                return False
            if not _leakage_free(child):
                return False
    elif isinstance(value, (list, tuple)):
        return all(_leakage_free(child) for child in value)
    elif isinstance(value, str) and (
        re.search(r"\b(?:preferred|best|safest|expected winner)\b", value, re.I)
        or "non-acceptance intensification" in value.casefold()
    ):
        return False
    return True


def model_free_preflight(
    candidate: Mapping[str, Any], provider: Any
) -> Mapping[str, Any]:
    prepared = _shared_preparations(candidate, provider)
    references = deterministic_references(candidate)
    opaque_order_checks = _opaque_and_order_invariance(candidate)
    case_index = {
        case["case_id"]: case
        for pair in candidate["pairs"]
        for case in pair["variants"]
    }
    ref = references["cases"]
    pair_checks = {}
    for item in prepared:
        pair_id = item["pair_id"]
        a, b = PAIR_CASES[pair_id]
        public_options_equal = (
            case_index[a]["operational_en"]["options"]
            == case_index[b]["operational_en"]["options"]
        )
        e_a = _normalized_by_description(
            case_index[a], ref[a]["emocio"]["valuation_vectors"]
        )
        e_b = _normalized_by_description(
            case_index[b], ref[b]["emocio"]["valuation_vectors"]
        )
        i_a = _normalized_by_description(
            case_index[a],
            {
                row["option_id"]: {
                    "deltas": row["combined_body_deltas"],
                    "cost": row["protective_cost"],
                }
                for row in ref[a]["instinkt"]["option_results"]
            },
        )
        i_b = _normalized_by_description(
            case_index[b],
            {
                row["option_id"]: {
                    "deltas": row["combined_body_deltas"],
                    "cost": row["protective_cost"],
                }
                for row in ref[b]["instinkt"]["option_results"]
            },
        )
        pair_checks[pair_id] = {
            "racio_packet_byte_identical": item["variants"][0][
                "packet"
            ].content_hash()
            == item["variants"][1]["packet"].content_hash(),
            "public_options_identical": public_options_equal,
            "emocio_distinguishable_or_stable_as_declared": (
                e_a != e_b
                if pair_id in {
                    "public_credit_audience",
                    "factory_public_status",
                }
                else e_a == e_b
            ),
            "instinkt_distinguishable_or_stable_as_declared": (
                i_a != i_b
                if pair_id == "loan_attachment_distance"
                else (
                    i_a == i_b
                    if pair_id == "factory_public_status"
                    else True
                )
            ),
        }
    serialized_packets = {
        item["pair_id"]: json.dumps(
            item["request_payload"], ensure_ascii=False
        ).casefold()
        for item in prepared
    }
    checks = {
        "source_candidate_hash": candidate["source_candidate"]["sha256"]
        == EXPECTED_SOURCE_CANDIDATE_SHA256,
        "exact_pair_order": tuple(candidate["pair_order"]) == PAIR_ORDER,
        "exact_case_order": tuple(candidate["case_order"]) == CASE_ORDER,
        "all_pair_checks": all(
            all(values.values()) for values in pair_checks.values()
        ),
        "emocio_evidence_closure": all(
            value["emocio"]["evidence_closure"] == "passed"
            for value in ref.values()
        ),
        "instinkt_evidence_closure": all(
            value["instinkt"]["category_evidence_closure"] == "passed"
            for value in ref.values()
        ),
        "no_leakage": _leakage_free(candidate),
        "no_global_score": "global_rei_score"
        not in json.dumps(candidate, ensure_ascii=False).casefold(),
        "loan_need_not_compassion_goal": "compassion"
        not in next(
            _packet_explicit_goal(item["packet"]).casefold()
            for item in prepared
            if item["pair_id"] == "loan_attachment_distance"
        ),
        "public_audience_absent_from_racio": all(
            token not in serialized_packets["public_credit_audience"]
            for token in ("six project-team", "wider audience", "publicly recognized")
        ),
        "factory_status_absent_from_racio": all(
            token not in serialized_packets["factory_public_status"]
            for token in ("competency review", "recognition", "status")
        ),
        "factory_status_absent_from_instinkt": (
            ref["factory_public_status_visible"]["instinkt"]["option_results"]
            == ref["factory_public_status_anonymous"]["instinkt"]["option_results"]
        ),
        "factory_recognition_not_option_winner_specific": len(
            {
                tuple(
                    (
                        option["attention_relation"]["state"],
                        option["attention_relation"]["value"],
                        option["status_relation"]["state"],
                        option["status_relation"]["value"],
                    )
                )
                for option in ref["factory_public_status_visible"]["emocio"][
                    "annotation"
                ]["options"]
            }
        )
        == 1,
        "opaque_and_order_invariance": all(opaque_order_checks.values()),
        "zero_model_calls": references["model_calls"] == 0,
        "zero_native_processor_executions": references[
            "native_processor_executions"
        ]
        == {"E": 0, "I": 0},
    }
    return {
        "schema_version": "triad-iso-e3-model-free-preflight-v1",
        "status": "passed"
        if all(checks.values())
        else "failed",
        "checks": checks,
        "pair_checks": pair_checks,
        "opaque_order_checks": opaque_order_checks,
        "pair_packet_hashes": {
            item["pair_id"]: item["packet"].content_hash()
            for item in prepared
        },
        "model_calls": 0,
        "native_processor_executions": {"E": 0, "I": 0},
    }


def seal_e3(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / OUTPUT_RELATIVE_PATH
    if output_root.exists():
        raise ValueError("TRIAD-ISO-E3 output root exists; seal is create-only")
    if _git(repository_root, "rev-parse", "HEAD") != EXPECTED_BASE_COMMIT:
        raise ValueError("TRIAD-ISO-E3 base commit differs")
    provider = build_provider()
    if provider.runtime.digest != EXPECTED_MODEL_DIGEST:
        raise ValueError("Exact local model digest differs before E3 seal")
    candidate = execution_candidate(repository_root)
    preflight = model_free_preflight(candidate, provider)
    if preflight["status"] != "passed":
        failed = [key for key, value in preflight["checks"].items() if not value]
        raise ValueError(f"TRIAD-ISO-E3 preflight failed: {failed}")
    references = deterministic_references(candidate)
    prepared = _shared_preparations(candidate, provider)
    _write_json(output_root / "execution_candidate.json", candidate)
    _write_json(output_root / "preflight_report.json", preflight)
    _write_json(output_root / "deterministic_route_references.json", references)
    input_records = []
    case_index = {
        case["case_id"]: case
        for pair in candidate["pairs"]
        for case in pair["variants"]
    }
    for item in prepared:
        pair_root = output_root / "pairs" / item["pair_id"]
        inputs = {
            "schema_version": "triad-iso-e3-pair-input-v1",
            "pair_id": item["pair_id"],
            "case_ids": PAIR_CASES[item["pair_id"]],
            "source_case_hashes": {
                case_id: _object_sha256(case_index[case_id])
                for case_id in PAIR_CASES[item["pair_id"]]
            },
            "racio": {
                "scene": item["scene"],
                "world": item["world"],
                "packet": item["packet"],
                "call_spec": item["call_spec"],
                "request_payload": item["request_payload"],
            },
            "emocio_annotation_hashes": {
                case_id: references["cases"][case_id]["emocio"][
                    "annotation_sha256"
                ]
                for case_id in PAIR_CASES[item["pair_id"]]
            },
            "instinkt_mapping_hashes": {
                case_id: references["cases"][case_id]["instinkt"][
                    "mapping_sha256"
                ]
                for case_id in PAIR_CASES[item["pair_id"]]
            },
            "native_processor_executions": {"E": 0, "I": 0},
            "character_replay": 0,
        }
        _write_json(pair_root / "inputs.json", inputs)
        input_records.append(
            {
                "pair_id": item["pair_id"],
                "path": (pair_root / "inputs.json")
                .relative_to(repository_root)
                .as_posix(),
                "sha256": _file_sha256(pair_root / "inputs.json"),
                "racio_packet_sha256": item["packet"].content_hash(),
                "variant_packet_hashes": {
                    variant["case_id"]: variant["packet"].content_hash()
                    for variant in item["variants"]
                },
                "source_case_hashes": inputs["source_case_hashes"],
                "emocio_annotation_hashes": inputs[
                    "emocio_annotation_hashes"
                ],
                "instinkt_mapping_hashes": inputs[
                    "instinkt_mapping_hashes"
                ],
            }
        )
    expected = {
        "schema_version": "triad-iso-e3-expected-ledger-v1",
        "state": "sealed_before_calls",
        "expected": {
            "model_calls": 3,
            "retries": 0,
            "fallbacks": 0,
            "character_replay": 0,
        },
        "entries": [
            {
                "ordinal": ordinal,
                "pair_id": item["pair_id"],
                "call_id": item["call_spec"].call_id,
                "call_spec_hash": item["call_spec"].content_hash(),
                "status": "sealed",
            }
            for ordinal, item in enumerate(prepared, 1)
        ],
    }
    _write_json(output_root / "expected_call_ledger.json", expected)
    module_path = Path(__file__).resolve()
    script_path = repository_root / "scripts/run_triad_iso_e3.py"
    base = {
        "schema_version": "triad-iso-e3-pre-call-seal-v1",
        "phase": "TRIAD-ISO-E3",
        "base_commit": EXPECTED_BASE_COMMIT,
        "source_candidate": {
            "path": SOURCE_CANDIDATE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_SOURCE_CANDIDATE_SHA256,
        },
        "execution_candidate": {
            "path": (OUTPUT_RELATIVE_PATH / "execution_candidate.json").as_posix(),
            "sha256": _file_sha256(output_root / "execution_candidate.json"),
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
        "model": provider.runtime.model,
        "model_digest": provider.runtime.digest,
        "model_profile": MODEL_PROFILE,
        "call_order": PAIR_ORDER,
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
        "effect_rules_sha256": _object_sha256(E3_EFFECT_RULES),
        "execution_policy": EXECUTION_POLICY,
        "output_root": OUTPUT_RELATIVE_PATH.as_posix(),
        "created_at": utc_now(),
    }
    projected = _projection(base)
    seal = {**projected, "seal_sha256": _object_sha256(projected)}
    _write_json(output_root / "pre_call_seal.json", seal)
    return seal


def verify_seal(
    repository_root: Path, provider: Any | None = None
) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    root = repository_root / OUTPUT_RELATIVE_PATH
    seal = _json(root / "pre_call_seal.json")
    base = {key: value for key, value in seal.items() if key != "seal_sha256"}
    if _object_sha256(base) != seal["seal_sha256"]:
        raise ValueError("TRIAD-ISO-E3 seal hash differs")
    for key in (
        "source_candidate",
        "execution_candidate",
        "preflight_report",
        "deterministic_route_references",
        "expected_call_ledger",
    ):
        record = seal[key]
        if _file_sha256(repository_root / record["path"]) != record["sha256"]:
            raise ValueError(f"Sealed E3 file changed: {key}")
    for key in ("module", "script"):
        path = repository_root / seal["implementation"][f"{key}_path"]
        if _file_sha256(path) != seal["implementation"][f"{key}_sha256"]:
            raise ValueError(f"Sealed E3 implementation changed: {key}")
    active = provider or build_provider()
    if active.runtime.digest != seal["model_digest"]:
        raise ValueError("Exact local digest changed after E3 seal")
    candidate = _json(repository_root / seal["execution_candidate"]["path"])
    preflight = model_free_preflight(candidate, active)
    if preflight != _json(repository_root / seal["preflight_report"]["path"]):
        raise ValueError("Cold E3 preflight differs from seal")
    prepared = _shared_preparations(candidate, active)
    if [_projection(item["call_spec"]) for item in prepared] != seal["call_specs"]:
        raise ValueError("E3 call specs changed after seal")
    for record in seal["input_records"]:
        if _file_sha256(repository_root / record["path"]) != record["sha256"]:
            raise ValueError(f"Sealed E3 input changed: {record['pair_id']}")
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
        "schema_version": "triad-iso-e3-call-ledger-v1",
        "state": "ready",
        "pre_call_seal_sha256": seal["seal_sha256"],
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
                "pair_id": item["pair_id"],
                "call_id": item["call_id"],
                "status": "planned",
            }
            for item in expected["entries"]
        ],
    }
    _write_json(path, ledger)
    return ledger


def run_next(repository_root: Path) -> Mapping[str, Any]:
    root = repository_root / OUTPUT_RELATIVE_PATH
    provider = build_provider()
    _, prepared = verify_seal(repository_root, provider)
    ledger = initialize_execution(repository_root)
    ledger_path = root / "call_ledger.json"
    if ledger["state"] not in {"ready", "executing"}:
        raise ValueError(f"E3 execution not runnable from {ledger['state']}")
    if any(item["status"] == "dispatching" for item in ledger["entries"]):
        raise ValueError("Prior E3 attempt is indeterminate; retry forbidden")
    entry = next(
        (item for item in ledger["entries"] if item["status"] == "planned"),
        None,
    )
    if entry is None:
        raise ValueError("All three E3 calls were already attempted")
    if entry["ordinal"] != ledger["actual"]["model_call_attempts"] + 1:
        raise ValueError("E3 call order changed")
    item = next(value for value in prepared if value["pair_id"] == entry["pair_id"])
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
    pair_root = root / "pairs" / entry["pair_id"]
    _write_json(
        pair_root / "call_record.json",
        {
            "schema_version": "triad-iso-e3-call-record-v1",
            "pair_id": entry["pair_id"],
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
        pair_root / "racio_output.json",
        {
            "schema_version": "triad-iso-e3-pair-racio-output-v1",
            "pair_id": entry["pair_id"],
            "status": entry["racio_status"],
            "packet_hash": item["packet"].content_hash(),
            "reused_for_case_ids": PAIR_CASES[entry["pair_id"]],
            "conclusion": execution.conclusion if execution is not None else None,
            "failure": failure,
            "processor_execution_count": 1,
        },
    )
    entry["status"] = "complete"
    if ledger["actual"]["model_call_attempts"] == 3:
        ledger["state"] = "three_calls_complete"
    _write_json(ledger_path, ledger)
    return {
        "pair_id": entry["pair_id"],
        "ordinal": entry["ordinal"],
        "racio_status": entry["racio_status"],
        "failure_code": entry.get("failure_code"),
        "model_call_attempts": ledger["actual"]["model_call_attempts"],
    }


def _pair_observations(
    references: Mapping[str, Any]
) -> Mapping[str, Any]:
    ref = references["cases"]
    output = {}
    for pair_id, (a, b) in PAIR_CASES.items():
        e_a = ref[a]["emocio"]
        e_b = ref[b]["emocio"]
        i_a = ref[a]["instinkt"]
        i_b = ref[b]["instinkt"]
        output[pair_id] = {
            "emocio_route_distinct": e_a["valuation_vectors"]
            != e_b["valuation_vectors"],
            "emocio_option_difference": e_a["selected_option_id"]
            != e_b["selected_option_id"],
            "instinkt_route_distinct": i_a["option_results"]
            != i_b["option_results"],
            "instinkt_option_difference": i_a["selected_option_id"]
            != i_b["selected_option_id"],
        }
    return output


def _render_report(
    seal: Mapping[str, Any],
    outputs: Mapping[str, Any],
    references: Mapping[str, Any],
    observations: Mapping[str, Any],
    candidate: Mapping[str, Any],
    prepared: Sequence[Mapping[str, Any]],
) -> str:
    case_index = {
        case["case_id"]: case
        for pair in candidate["pairs"]
        for case in pair["variants"]
    }
    prepared_index = {item["pair_id"]: item for item in prepared}
    held_changed = {
        "public_credit_audience": (
            "Authorship claim, timestamped record, official correction mechanism, pay/ownership/authority consequences, no retaliation, options.",
            "Named wider audience, self/rival visual position, and public recognition scene.",
        ),
        "loan_attachment_distance": (
            "Genuine EUR 9000 need, repayment history, 45-percent exposure, EUR 3000 written boundary, no self material benefit, options.",
            "Close twelve-year attachment and fear of loss versus distant acquaintance without attachment history.",
        ),
        "factory_public_status": (
            "11 C rise, conflicting sensor, three-minute window, damage possibility, EUR 75000 shutdown loss, options.",
            "Named audience and conditional operator recognition versus anonymous handling.",
        ),
    }
    lines = [
        "# TRIAD-ISO-E3 remaining native-route isolation pairs",
        "",
        "Research-only screen: three pair-shared Racio calls and model-free "
        "deterministic projections of explicit human-reviewed Emocio and "
        "Instinkt annotations. No native E/I processor, character replay, "
        "global REI score, image, shadow, raw-scene, G4, or promotion claim.",
        "",
        f"- Seal: `{seal['seal_sha256']}`.",
        f"- Model digest: `{seal['model_digest']}`.",
        "- Calls/retries/fallbacks: `3/0/0`.",
        "",
    ]
    for pair_id in PAIR_ORDER:
        output = outputs[pair_id]
        conclusion = output["conclusion"]
        a, b = PAIR_CASES[pair_id]
        visible_packet = json.loads(
            prepared_index[pair_id]["request_payload"]["prompt"]
        )
        lines.extend(
            [
                f"## `{pair_id}`",
                "",
                "### HELD CONSTANT",
                "",
                held_changed[pair_id][0],
                "",
                "### CHANGED",
                "",
                held_changed[pair_id][1],
                "",
                "### PAIR-SHARED RACIO",
                "",
                f"- Status: `{output['status']}`.",
                f"- Packet: `{output['packet_hash']}`.",
                f"- Reused for: `{a}`, `{b}`.",
                f"- Option: `{conclusion['option_id'] if conclusion else 'none'}`.",
                "- Exact shared visible packet:",
                "",
                "```json",
                json.dumps(
                    visible_packet,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                ),
                "```",
            ]
        )
        if conclusion:
            lines.extend(
                [
                    "- Facts used: " + "; ".join(conclusion["facts_used"]),
                    "- Unknowns retained: "
                    + ("; ".join(conclusion["unknowns"]) or "none"),
                    "- Goal: " + conclusion["explicit_goal"],
                    "- Route: " + " -> ".join(conclusion["causal_sequence"]),
                    "- Utility: " + "; ".join(conclusion["utility_structure"]),
                    "- Main objection: " + conclusion["main_objection"],
                ]
            )
        else:
            lines.append(
                f"- Failure: `{output['failure']['failure_code']}`."
            )
        for label, case_id in (("A", a), ("B", b)):
            e = references["cases"][case_id]["emocio"]
            i = references["cases"][case_id]["instinkt"]
            e_route = case_index[case_id]["route_packets"]["emocio"]
            i_route = case_index[case_id]["route_packets"]["instinkt"]
            lines.extend(
                [
                    "",
                    f"### EMOCIO VARIANT {label} -- `{case_id}`",
                    "",
                    f"- Current scene: {e_route['current_scene']}",
                    f"- Desired scene: {e_route['desired_scene']}",
                    f"- Broken scene: {e_route['broken_scene']}",
                    "- Option scenes: `"
                    + json.dumps(
                        e_route["option_visible_changes"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "`.",
                    f"- Annotation: `{e['annotation_sha256']}`; closure: "
                    f"`{e['evidence_closure']}`; manual: `true`; processor "
                    "capability claimed: `false`.",
                    f"- Selected: `{e['selected_option_id']}`; ties: "
                    f"`{', '.join(e['tied_option_ids']) or 'none'}`.",
                    "- Valuation vectors: `"
                    + json.dumps(
                        e["valuation_vectors"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "`.",
                    "",
                    f"### INSTINKT VARIANT {label} -- `{case_id}`",
                    "",
                    f"- Danger: {i_route['danger_types']}",
                    f"- Trust/distrust: {i_route['trust_distrust']}",
                    f"- Attachment/care: {i_route['attachment_care']}",
                    f"- Scarcity: {i_route['scarcity']}",
                    f"- Escape/reversibility: {i_route['escape_reversibility']}",
                    f"- Recoverability: {i_route['recoverability']}",
                    f"- Mapping: `{i['mapping_sha256']}`; closure: "
                    f"`{i['category_evidence_closure']}`; typed: `true`; "
                    "processor capability claimed: `false`.",
                    f"- Selected: `{i['selected_option_id']}`; ties: "
                    f"`{', '.join(i['tied_option_ids']) or 'none'}`.",
                    "- Option effects: `"
                    + json.dumps(
                        i["option_results"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "`.",
                ]
            )
        obs = observations[pair_id]
        lines.extend(
            [
                "",
                "### ROUTE DIFFERENCE",
                "",
                f"- Emocio: `{str(obs['emocio_route_distinct']).lower()}`.",
                f"- Instinkt: `{str(obs['instinkt_route_distinct']).lower()}`.",
                "",
                "### OPTION DIFFERENCE",
                "",
                f"- Emocio: `{str(obs['emocio_option_difference']).lower()}`.",
                f"- Instinkt: `{str(obs['instinkt_option_difference']).lower()}`.",
                "",
                "### CROSS-MIND SIDE EFFECTS",
                "",
                (
                    "- Public audience may legitimately affect Instinkt social "
                    "exposure; this is not the primary target."
                    if pair_id == "public_credit_audience"
                    else "- Non-target route is stable under the declared mapping."
                ),
                "",
                "### UNSUPPORTED INFERENCE",
                "",
                "- Contract validation found no out-of-scope evidence ID. "
                "Semantic unsupported-inference adjudication remains blank "
                "for human review.",
                "",
                "### HUMAN REVIEW -- LEAVE BLANK",
                "",
                "- Racio pair isolation: [ ] passed [ ] failed [ ] uncertain",
                "- Emocio route fidelity: [ ] plausible [ ] implausible [ ] uncertain",
                "- Instinkt pair isolation: [ ] passed [ ] failed [ ] uncertain",
                "- Option change required: no",
                "- Route meaningfully changed: [ ]",
                "- Non-target route remained stable: [ ]",
                "- Unsupported inference: [ ]",
                "- Cross-route contamination: [ ]",
                "- Input appears to predetermine outcome: [ ]",
                "- Ready for character replay: [ ]",
                "",
            ]
        )
    lines.append("No human-review field was completed by Codex.")
    return "\n".join(lines).rstrip() + "\n"


def finalize(repository_root: Path) -> Mapping[str, Any]:
    root = repository_root / OUTPUT_RELATIVE_PATH
    seal, prepared = verify_seal(repository_root)
    ledger = _json(root / "call_ledger.json")
    if ledger["state"] != "three_calls_complete":
        raise ValueError("E3 cannot finalize before exactly three attempts")
    outputs = {
        pair_id: _json(root / "pairs" / pair_id / "racio_output.json")
        for pair_id in PAIR_ORDER
    }
    references = _json(root / "deterministic_route_references.json")
    candidate = _json(root / "execution_candidate.json")
    observations = _pair_observations(references)
    failures = [
        value["failure"]
        for value in outputs.values()
        if value["failure"] is not None
    ]
    summary = {
        "schema_version": "triad-iso-e3-summary-v1",
        "phase": "TRIAD-ISO-E3",
        "status": "complete_three_pair_screen",
        "pre_call_seal_sha256": seal["seal_sha256"],
        "model_digest": seal["model_digest"],
        "calls": 3,
        "retries": 0,
        "fallbacks": 0,
        "racio": {
            pair_id: {
                "status": value["status"],
                "selected_option_id": (
                    value["conclusion"]["option_id"]
                    if value["conclusion"] is not None
                    else None
                ),
            }
            for pair_id, value in outputs.items()
        },
        "route_observations": observations,
        "non_target_route_stability": {
            "public_credit_instinkt": (
                "legitimately_affected_by_named_audience"
                if observations["public_credit_audience"][
                    "instinkt_route_distinct"
                ]
                else "stable"
            ),
            "loan_emocio": not observations["loan_attachment_distance"][
                "emocio_route_distinct"
            ],
            "factory_instinkt": not observations["factory_public_status"][
                "instinkt_route_distinct"
            ],
            "racio_pair_shared_all": True,
        },
        "failure_categories": dict(
            Counter(item["failure_code"] for item in failures)
        ),
        "native_processor_executions": {"E": 0, "I": 0},
        "character_replay": 0,
        "private_thinking_persisted": False,
        "global_rei_score": None,
    }
    _write_json(root / "summary.json", summary)
    (root / "report.md").write_text(
        _render_report(
            seal,
            outputs,
            references,
            observations,
            candidate,
            prepared,
        ),
        encoding="utf-8",
        newline="\n",
    )
    ledger["state"] = "complete"
    _write_json(root / "call_ledger.json", ledger)
    return summary


def cold_verify(repository_root: Path) -> Mapping[str, Any]:
    root = repository_root / OUTPUT_RELATIVE_PATH
    seal, _ = verify_seal(repository_root)
    ledger = _json(root / "call_ledger.json")
    summary = _json(root / "summary.json")
    if ledger["state"] != "complete":
        raise ValueError("E3 ledger is not complete")
    if ledger["actual"]["model_call_attempts"] != 3:
        raise ValueError("E3 model-call accounting differs")
    if ledger["actual"]["retries"] or ledger["actual"]["fallbacks"]:
        raise ValueError("E3 retry/fallback accounting differs")
    if ledger["actual"]["character_replay"]:
        raise ValueError("E3 character replay occurred")
    if (
        ledger["actual"]["native_emocio_processor_executions"]
        or ledger["actual"]["native_instinkt_processor_executions"]
    ):
        raise ValueError("E3 native E/I processor execution occurred")
    if any(item["status"] != "complete" for item in ledger["entries"]):
        raise ValueError("E3 has an incomplete call entry")
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.casefold()
        if any(f'"{key}"' in lowered for key in PRIVATE_KEYS):
            raise ValueError(f"Private thinking key persisted in {path.name}")
        if str(repository_root).casefold() in lowered:
            raise ValueError(f"Local absolute path persisted in {path.name}")
    if not (root / "report.md").is_file():
        raise ValueError("E3 report is missing")
    return {
        "status": "passed",
        "seal_sha256": seal["seal_sha256"],
        "model_digest": seal["model_digest"],
        "calls": summary["calls"],
        "retries": summary["retries"],
        "fallbacks": summary["fallbacks"],
        "racio": summary["racio"],
        "route_observations": summary["route_observations"],
        "non_target_route_stability": summary["non_target_route_stability"],
        "failure_categories": summary["failure_categories"],
        "report_sha256": _file_sha256(root / "report.md"),
    }


__all__ = [
    "CASE_ORDER",
    "EXPECTED_BASE_COMMIT",
    "EXPECTED_SOURCE_CANDIDATE_SHA256",
    "OUTPUT_RELATIVE_PATH",
    "PAIR_CASES",
    "PAIR_ORDER",
    "SOURCE_CANDIDATE_RELATIVE_PATH",
    "author_emocio_annotation",
    "author_instinkt_mapping",
    "cold_verify",
    "deterministic_references",
    "execution_candidate",
    "finalize",
    "initialize_execution",
    "model_free_preflight",
    "run_next",
    "seal_e3",
    "verify_seal",
]
