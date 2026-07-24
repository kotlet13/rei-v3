"""TRIAD-ISO-R2 source-addressed typed-route correction.

This module is research-only and model-free.  It treats Emocio route semantics
as explicit human-authored annotations, never as an autonomous compiler from
case IDs, option IDs, or prose.  Instinkt effect categories are likewise
explicit typed mappings closed over source evidence from the same option.

The module never executes a native processor, provider, character replay,
image generation, or governance path.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import Field, model_validator

from ..emocio.policy import choose_native_option
from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..instinkt.dynamics import simulate_option_rollout
from ..instinkt.packets import InstinktEffectSpec, bind_instinkt_effects
from ..instinkt.policy import protective_cost
from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText
from ..models.emocio import (
    EMOCIO_VALUATION_DIMENSIONS,
    EmocioOptionValuation,
    ValuationDimension,
)
from ..models.instinkt import (
    BODY_DIMENSIONS,
    BodyDelta,
    BodyState,
    InstinktInputPacket,
    InstinktSimulationConfig,
)
from .triad_iso_e1 import (
    CASE_ORDER,
    OUTPUT_RELATIVE_PATH as E1_OUTPUT_RELATIVE_PATH,
    PRIVATE_KEYS,
)
from .triad_iso_r1 import (
    ADJUDICATION_RELATIVE_PATH,
    R1_OUTPUT_RELATIVE_PATH,
    _action,
    _json,
    _object_sha256,
    _outcome,
    _walk,
    _write_json,
    cold_verify_r1,
    formal_verify_e1,
    validate_json_projection,
)


R2_OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-e1r2-2026-07-24"
)
R1_CANDIDATE_RELATIVE_PATH: Final = (
    R1_OUTPUT_RELATIVE_PATH / "corrected_candidate.json"
)
EXPECTED_R1_CANDIDATE_SHA256: Final = (
    "77724ec00a06a6da5d0ff8d42443f01704173c633d7033359f14807c683abfa3"
)
EXPECTED_R1_CASE_SHA256: Final[Mapping[str, str]] = {
    "trip_racio_utility_material": (
        "d08ca21a2acbed3b48bf325225a7e54a20c86c3353ad7a5df49ea20f557b9bd8"
    ),
    "trip_racio_utility_pleasure": (
        "dfed733997b60bde8a54733eea33fd600b574755b1c6a3e62d4bc91b36f3f093"
    ),
    "trip_protective_context_exposed": (
        "e951272a85aa252525520dff1472aeef3626db5d4428bdd2baf0f3d382240ffe"
    ),
    "trip_protective_context_supported": (
        "c1dc6eed046c3f2ab442253274de511d321a14cf6a7470f7dcbbb89c7ed891bf"
    ),
}
EXPECTED_R1_FILE_COUNT: Final = 6

RelationState = Literal["grounded", "bounded_unknown", "not_relevant"]


class SourceAddressedRelationV1(FrozenModel):
    state: RelationState
    value: NonEmptyId | None = None
    evidence_ids: tuple[NonEmptyId, ...] = ()

    @model_validator(mode="after")
    def validate_relation(self) -> "SourceAddressedRelationV1":
        if self.state == "not_relevant":
            if self.value is not None or self.evidence_ids:
                raise ValueError(
                    "A not-relevant relation cannot carry a value or evidence"
                )
        elif self.value is None or not self.evidence_ids:
            raise ValueError(
                "A grounded or bounded-unknown relation requires value and evidence"
            )
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("Relation evidence IDs must use canonical unique order")
        return self


EMOCIO_OPTION_RELATION_FIELDS: Final = (
    "target_scene_identity",
    "self_position_relation",
    "attraction_target",
    "attraction_strength",
    "movement_destination",
    "movement_magnitude",
    "immediacy",
    "novelty_strength",
    "obstacle_relation",
    "desired_state_relation",
    "broken_state_relation",
    "attention_relation",
    "status_relation",
    "competition_relation",
    "belonging_relation",
)

EMOCIO_RELATION_DOMAINS: Final[Mapping[str, frozenset[str]]] = {
    "self_position_relation": frozenset(
        {"centered_at_decision", "centered_in_result_scene"}
    ),
    "attraction_strength": frozenset({"absent", "present", "stronger"}),
    "movement_magnitude": frozenset({"none", "bounded", "large_new"}),
    "immediacy": frozenset({"none", "bounded", "immediate"}),
    "novelty_strength": frozenset({"absent", "present", "stronger"}),
    "obstacle_relation": frozenset({"persists", "transformed", "removed"}),
    "desired_state_relation": frozenset({"not_aligned", "partial", "aligned"}),
    "broken_state_relation": frozenset(
        {"remains", "partial_escape", "escaped"}
    ),
    "attention_relation": frozenset({"absent", "present", "stronger"}),
    "status_relation": frozenset({"absent", "present", "stronger"}),
    "competition_relation": frozenset({"absent", "present", "stronger"}),
    "belonging_relation": frozenset({"absent", "present", "stronger"}),
}


class EmocioTypedOptionRouteV1(FrozenModel):
    option_id: NonEmptyId
    source_option_sha256: HashDigest
    source_evidence_scope_ids: tuple[NonEmptyId, ...]
    target_scene_identity: SourceAddressedRelationV1
    self_position_relation: SourceAddressedRelationV1
    attraction_target: SourceAddressedRelationV1
    attraction_strength: SourceAddressedRelationV1
    movement_destination: SourceAddressedRelationV1
    movement_magnitude: SourceAddressedRelationV1
    immediacy: SourceAddressedRelationV1
    novelty_strength: SourceAddressedRelationV1
    obstacle_relation: SourceAddressedRelationV1
    desired_state_relation: SourceAddressedRelationV1
    broken_state_relation: SourceAddressedRelationV1
    attention_relation: SourceAddressedRelationV1
    status_relation: SourceAddressedRelationV1
    competition_relation: SourceAddressedRelationV1
    belonging_relation: SourceAddressedRelationV1

    @model_validator(mode="after")
    def validate_option_route(self) -> "EmocioTypedOptionRouteV1":
        if self.source_evidence_scope_ids != tuple(
            sorted(set(self.source_evidence_scope_ids))
        ):
            raise ValueError("Option evidence scope must use canonical unique order")
        scope = set(self.source_evidence_scope_ids)
        for field_name in EMOCIO_OPTION_RELATION_FIELDS:
            relation = getattr(self, field_name)
            if not set(relation.evidence_ids).issubset(scope):
                raise ValueError(
                    f"{field_name} cites evidence outside its option source scope"
                )
            allowed = EMOCIO_RELATION_DOMAINS.get(field_name)
            if (
                relation.state != "not_relevant"
                and allowed is not None
                and relation.value not in allowed
            ):
                raise ValueError(
                    f"{field_name} has an unsupported typed relation value"
                )
        return self


class EmocioTypedRouteAnnotationV1(FrozenModel):
    schema_version: Literal["triad-emocio-typed-route-annotation-v1"] = (
        "triad-emocio-typed-route-annotation-v1"
    )
    annotation_mode: Literal["explicit_source_addressed_for_human_review"] = (
        "explicit_source_addressed_for_human_review"
    )
    source_evidence_sha256: HashDigest
    companion_visible: SourceAddressedRelationV1
    companion_enjoyment_relation: SourceAddressedRelationV1
    options: tuple[EmocioTypedOptionRouteV1, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_annotation(self) -> "EmocioTypedRouteAnnotationV1":
        option_ids = tuple(item.option_id for item in self.options)
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Emocio typed option IDs must be unique")
        return self


def _canonical_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _source_facts(case: Mapping[str, Any]) -> dict[str, str]:
    return {
        item["evidence_id"]: item["text"]
        for item in case["operational_en"]["facts"]
    }


def _source_options(case: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        item["option_id"]: item for item in case["operational_en"]["options"]
    }


def source_evidence_address(case: Mapping[str, Any]) -> str:
    """Address facts and public options, excluding case IDs and route prose."""

    return _canonical_fingerprint(
        {
            "facts": case["operational_en"]["facts"],
            "unknowns": case["operational_en"]["unknowns"],
            "options": case["operational_en"]["options"],
        }
    )


def source_option_address(
    case: Mapping[str, Any],
    option_id: str,
) -> str:
    return _canonical_fingerprint(_source_options(case)[option_id])


def _canonical_relation(relation: SourceAddressedRelationV1) -> Mapping[str, Any]:
    return {
        **relation.model_dump(mode="json"),
        "evidence_ids": sorted(relation.evidence_ids),
    }


def compile_emocio_typed_annotation(
    case: Mapping[str, Any],
    annotation: Mapping[str, Any] | EmocioTypedRouteAnnotationV1,
) -> EmocioTypedRouteAnnotationV1:
    """Validate and canonicalize only explicit typed annotation.

    No case ID, option-ID token, list position, or prose field is consulted to
    create semantic values.
    """

    value = (
        annotation.model_dump(mode="json")
        if isinstance(annotation, EmocioTypedRouteAnnotationV1)
        else annotation
    )
    typed = validate_json_projection(EmocioTypedRouteAnnotationV1, value)
    if typed.source_evidence_sha256 != source_evidence_address(case):
        raise ValueError("Emocio annotation belongs to another source evidence set")
    facts = _source_facts(case)
    options = _source_options(case)
    if {item.option_id for item in typed.options} != set(options):
        raise ValueError("Emocio annotation must cover every public option exactly")
    for item in typed.options:
        if item.source_option_sha256 != source_option_address(case, item.option_id):
            raise ValueError("Emocio typed option belongs to another public option")
        if not set(item.source_evidence_scope_ids).issubset(facts):
            raise ValueError("Emocio option scope contains unknown evidence")
    for relation in (
        typed.companion_visible,
        typed.companion_enjoyment_relation,
    ):
        if not set(relation.evidence_ids).issubset(facts):
            raise ValueError("Emocio route-level relation cites unknown evidence")

    payload = typed.model_dump(mode="json")
    payload["companion_visible"] = _canonical_relation(typed.companion_visible)
    payload["companion_enjoyment_relation"] = _canonical_relation(
        typed.companion_enjoyment_relation
    )
    canonical_options = []
    for item in sorted(typed.options, key=lambda option: option.option_id):
        projected = item.model_dump(mode="json")
        projected["source_evidence_scope_ids"] = sorted(
            item.source_evidence_scope_ids
        )
        for field_name in EMOCIO_OPTION_RELATION_FIELDS:
            projected[field_name] = _canonical_relation(
                getattr(item, field_name)
            )
        canonical_options.append(projected)
    payload["options"] = canonical_options
    return validate_json_projection(EmocioTypedRouteAnnotationV1, payload)


def _relation_score(
    relation: SourceAddressedRelationV1,
    values: Mapping[str, float],
) -> float:
    if relation.state == "not_relevant":
        return 0.0
    if relation.state == "bounded_unknown":
        return 0.5
    if relation.value not in values:
        raise ValueError("Typed relation has no deterministic valuation projection")
    return values[relation.value]


def _emocio_vector(route: EmocioTypedOptionRouteV1) -> Mapping[str, float]:
    ordinal = {"absent": 0.0, "present": 0.6, "stronger": 1.0}
    desired = {"not_aligned": 0.0, "partial": 0.55, "aligned": 1.0}
    broken = {"remains": 0.0, "partial_escape": 0.55, "escaped": 1.0}
    position = {
        "centered_at_decision": 0.75,
        "centered_in_result_scene": 1.0,
    }
    movement = {"none": 0.0, "bounded": 0.5, "large_new": 1.0}
    immediacy = {"none": 0.0, "bounded": 0.5, "immediate": 1.0}
    obstacle = {"persists": 0.0, "transformed": 0.5, "removed": 1.0}
    obstacle_score = _relation_score(route.obstacle_relation, obstacle)
    immediacy_score = _relation_score(route.immediacy, immediacy)
    return {
        "desired_scene_match": _relation_score(
            route.desired_state_relation, desired
        ),
        "distance_from_broken_scene": _relation_score(
            route.broken_state_relation, broken
        ),
        "self_visibility": _relation_score(
            route.self_position_relation, position
        ),
        "belonging": _relation_score(route.belonging_relation, ordinal),
        "attention": _relation_score(route.attention_relation, ordinal),
        "attraction": _relation_score(route.attraction_strength, ordinal),
        "novelty": _relation_score(route.novelty_strength, ordinal),
        "movement": _relation_score(route.movement_magnitude, movement),
        "status": _relation_score(route.status_relation, ordinal),
        "competitive_success": _relation_score(
            route.competition_relation, ordinal
        ),
        "attack_or_breakthrough_affordance": round(
            (obstacle_score + immediacy_score) / 2.0,
            6,
        ),
    }


def project_emocio_typed_valuations(
    annotation: EmocioTypedRouteAnnotationV1,
) -> tuple[EmocioOptionValuation, ...]:
    valuations = []
    for route in annotation.options:
        vector = _emocio_vector(route)
        valuations.append(
            EmocioOptionValuation(
                option_id=route.option_id,
                rollout_scene_id=content_id(
                    "triad_iso_r2_emocio_typed_route",
                    route.model_dump(mode="json"),
                ),
                dimensions=tuple(
                    ValuationDimension(name=name, score=vector[name])
                    for name in EMOCIO_VALUATION_DIMENSIONS
                ),
            )
        )
    return tuple(sorted(valuations, key=lambda item: item.option_id))


def _rel(
    value: str | None = None,
    *evidence_ids: str,
    state: RelationState = "grounded",
) -> Mapping[str, Any]:
    if state == "not_relevant":
        return {"state": state, "value": None, "evidence_ids": []}
    return {
        "state": state,
        "value": value,
        "evidence_ids": sorted(set(evidence_ids)),
    }


def _manual_emocio_option(
    case: Mapping[str, Any],
    *,
    option_id: str,
    semantic_role: Literal["distant", "local", "home"],
    scene_evidence_id: str,
    novelty_evidence_id: str | None,
) -> Mapping[str, Any]:
    """Render one explicit human-authored recipe; this is not the compiler."""

    if semantic_role == "distant":
        values = {
            "target_scene_identity": _rel("distant_coast", scene_evidence_id),
            "self_position_relation": _rel(
                "centered_in_result_scene", scene_evidence_id
            ),
            "attraction_target": _rel("distant_coast", scene_evidence_id),
            "attraction_strength": _rel("stronger", scene_evidence_id),
            "movement_destination": _rel("distant_coast", scene_evidence_id),
            "movement_magnitude": _rel("large_new", scene_evidence_id),
            "immediacy": _rel("immediate", scene_evidence_id),
            "novelty_strength": _rel(
                "stronger", novelty_evidence_id or scene_evidence_id
            ),
            "obstacle_relation": _rel("removed", scene_evidence_id),
            "desired_state_relation": _rel("aligned", scene_evidence_id),
            "broken_state_relation": _rel("escaped", scene_evidence_id),
        }
    elif semantic_role == "local":
        values = {
            "target_scene_identity": _rel("local_coast", scene_evidence_id),
            "self_position_relation": _rel(
                "centered_in_result_scene", scene_evidence_id
            ),
            "attraction_target": _rel("local_coast", scene_evidence_id),
            "attraction_strength": _rel("present", scene_evidence_id),
            "movement_destination": _rel("local_coast", scene_evidence_id),
            "movement_magnitude": _rel("bounded", scene_evidence_id),
            "immediacy": _rel("bounded", scene_evidence_id),
            "novelty_strength": _rel("present", scene_evidence_id),
            "obstacle_relation": _rel("transformed", scene_evidence_id),
            "desired_state_relation": _rel("partial", scene_evidence_id),
            "broken_state_relation": _rel(
                "partial_escape", scene_evidence_id
            ),
        }
    else:
        values = {
            "target_scene_identity": _rel("home_scene", scene_evidence_id),
            "self_position_relation": _rel(
                "centered_at_decision", scene_evidence_id
            ),
            "attraction_target": _rel(state="not_relevant"),
            "attraction_strength": _rel("absent", scene_evidence_id),
            "movement_destination": _rel(state="not_relevant"),
            "movement_magnitude": _rel("none", scene_evidence_id),
            "immediacy": _rel("none", scene_evidence_id),
            "novelty_strength": _rel("absent", scene_evidence_id),
            "obstacle_relation": _rel("persists", scene_evidence_id),
            "desired_state_relation": _rel(
                "not_aligned", scene_evidence_id
            ),
            "broken_state_relation": _rel("remains", scene_evidence_id),
        }
    scope = {scene_evidence_id}
    if novelty_evidence_id is not None:
        scope.add(novelty_evidence_id)
    return {
        "option_id": option_id,
        "source_option_sha256": source_option_address(case, option_id),
        "source_evidence_scope_ids": sorted(scope),
        **values,
        "attention_relation": _rel(state="not_relevant"),
        "status_relation": _rel(state="not_relevant"),
        "competition_relation": _rel(state="not_relevant"),
        "belonging_relation": _rel(state="not_relevant"),
    }


_UTILITY_SOURCE_HASHES: Final = frozenset(
    {
        EXPECTED_R1_CASE_SHA256["trip_racio_utility_material"],
        EXPECTED_R1_CASE_SHA256["trip_racio_utility_pleasure"],
    }
)
_EXPOSED_SOURCE_HASH: Final = EXPECTED_R1_CASE_SHA256[
    "trip_protective_context_exposed"
]
_SUPPORTED_SOURCE_HASH: Final = EXPECTED_R1_CASE_SHA256[
    "trip_protective_context_supported"
]


def author_emocio_annotation(case: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the predeclared human-authored annotation for exact source bytes."""

    source_hash = _object_sha256(case)
    if source_hash in _UTILITY_SOURCE_HASHES:
        recipe = (
            ("utility_trip_book", "distant"),
            ("utility_trip_local", "local"),
            ("utility_trip_home", "home"),
        )
        scene_evidence_id = "utility_ev_destination"
        novelty_evidence_id = "utility_ev_rarity"
        companion_evidence_id = "utility_ev_companion"
        companion_value = "present"
    elif source_hash == _EXPOSED_SOURCE_HASH:
        recipe = (
            ("trip_book", "distant"),
            ("trip_local", "local"),
            ("trip_home", "home"),
        )
        scene_evidence_id = "protective_ev_attraction"
        novelty_evidence_id = "protective_ev_rarity"
        companion_evidence_id = "protective_ev_companion"
        companion_value = "absent"
    elif source_hash == _SUPPORTED_SOURCE_HASH:
        recipe = (
            ("trip_book", "distant"),
            ("trip_local", "local"),
            ("trip_home", "home"),
        )
        scene_evidence_id = "protective_ev_attraction"
        novelty_evidence_id = "protective_ev_rarity"
        companion_evidence_id = "protective_ev_companion"
        companion_value = "present"
    else:
        raise ValueError("No human-reviewed Emocio annotation for source case")
    options = [
        _manual_emocio_option(
            case,
            option_id=option_id,
            semantic_role=role,
            scene_evidence_id=scene_evidence_id,
            novelty_evidence_id=(
                novelty_evidence_id if role == "distant" else None
            ),
        )
        for option_id, role in recipe
    ]
    return {
        "schema_version": "triad-emocio-typed-route-annotation-v1",
        "annotation_mode": "explicit_source_addressed_for_human_review",
        "source_evidence_sha256": source_evidence_address(case),
        "companion_visible": _rel(
            companion_value,
            companion_evidence_id,
        ),
        "companion_enjoyment_relation": _rel(state="not_relevant"),
        "options": sorted(options, key=lambda item: item["option_id"]),
    }


InstinktAssertion = Literal[
    "discretionary_budget_exposure",
    "bounded_cancellation",
    "nonrefundable_purchase",
    "trusted_companion_present",
    "trusted_companion_absent",
    "unfamiliar_environment",
    "documented_environment",
    "unverified_providers",
    "verified_providers",
    "uncertain_return_path",
    "verified_return_path",
]
InstinktPredicate = Literal[
    "discretionary_resource_commitment_25",
    "discretionary_resource_commitment_38",
    "bounded_cancellation_recovery",
    "nonrefundable_resource_exposure",
    "trusted_attachment_support",
    "absence_of_trusted_support",
    "unfamiliar_environment_danger",
    "unverified_provider_danger",
    "uncertain_return_danger",
    "verified_provider_support",
    "verified_return_support",
    "avoids_unfamiliar_uncertain_exposure",
    "discretionary_resource_preserved",
]

R2_EFFECT_RULES: Final[Mapping[str, Mapping[str, float]]] = {
    "discretionary_resource_commitment_25": {"resource_security": -0.15},
    "discretionary_resource_commitment_38": {"resource_security": -0.20},
    "bounded_cancellation_recovery": {
        "escape_availability": 0.12,
        "predictability": 0.08,
    },
    "nonrefundable_resource_exposure": {
        "resource_security": -0.05,
        "escape_availability": -0.10,
    },
    "trusted_attachment_support": {
        "trust": 0.12,
        "attachment_security": 0.15,
        "tension": -0.05,
    },
    "absence_of_trusted_support": {
        "trust": -0.10,
        "attachment_security": -0.15,
        "tension": 0.10,
    },
    "unfamiliar_environment_danger": {
        "predictability": -0.15,
        "uncertainty": 0.12,
    },
    "unverified_provider_danger": {
        "trust": -0.15,
        "uncertainty": 0.10,
    },
    "uncertain_return_danger": {
        "escape_availability": -0.20,
        "uncertainty": 0.15,
    },
    "verified_provider_support": {
        "trust": 0.10,
        "predictability": 0.10,
    },
    "verified_return_support": {
        "escape_availability": 0.15,
        "predictability": 0.10,
    },
    "avoids_unfamiliar_uncertain_exposure": {
        "escape_availability": 0.12,
        "tension": -0.08,
    },
    "discretionary_resource_preserved": {"resource_security": 0.15},
}

PREDICATE_REQUIREMENTS: Final[Mapping[str, frozenset[str]]] = {
    "discretionary_resource_commitment_25": frozenset(
        {"discretionary_budget_exposure"}
    ),
    "discretionary_resource_commitment_38": frozenset(
        {"discretionary_budget_exposure"}
    ),
    "bounded_cancellation_recovery": frozenset({"bounded_cancellation"}),
    "nonrefundable_resource_exposure": frozenset({"nonrefundable_purchase"}),
    "trusted_attachment_support": frozenset({"trusted_companion_present"}),
    "absence_of_trusted_support": frozenset({"trusted_companion_absent"}),
    "unfamiliar_environment_danger": frozenset({"unfamiliar_environment"}),
    "unverified_provider_danger": frozenset({"unverified_providers"}),
    "uncertain_return_danger": frozenset({"uncertain_return_path"}),
    "verified_provider_support": frozenset({"verified_providers"}),
    "verified_return_support": frozenset({"verified_return_path"}),
    "discretionary_resource_preserved": frozenset(
        {"discretionary_budget_exposure"}
    ),
}
AVOIDANCE_DANGER_ASSERTIONS: Final = frozenset(
    {
        "unfamiliar_environment",
        "unverified_providers",
        "uncertain_return_path",
    }
)


class InstinktEvidenceAssertionV1(FrozenModel):
    evidence_id: NonEmptyId
    source_text_sha256: HashDigest
    assertions: tuple[InstinktAssertion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_assertions(self) -> "InstinktEvidenceAssertionV1":
        if self.assertions != tuple(sorted(set(self.assertions))):
            raise ValueError("Evidence assertions must use canonical unique order")
        return self


class InstinktTypedEffectCategoryV1(FrozenModel):
    category_id: NonEmptyId
    option_id: NonEmptyId
    supporting_evidence_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    semantic_predicate: InstinktPredicate
    body_deltas: tuple[BodyDelta, ...]

    @model_validator(mode="after")
    def validate_category(self) -> "InstinktTypedEffectCategoryV1":
        if self.supporting_evidence_ids != tuple(
            sorted(set(self.supporting_evidence_ids))
        ):
            raise ValueError("Category evidence must use canonical unique order")
        dimensions = tuple(item.dimension for item in self.body_deltas)
        if dimensions != tuple(sorted(set(dimensions))):
            raise ValueError("Category body deltas must use canonical dimension order")
        expected = R2_EFFECT_RULES[self.semantic_predicate]
        actual = {
            item.dimension: round(item.delta, 12) for item in self.body_deltas
        }
        if actual != expected:
            raise ValueError("Category body deltas differ from its typed predicate")
        return self


class InstinktTypedOptionEffectV1(FrozenModel):
    option_id: NonEmptyId
    source_option_sha256: HashDigest
    source_consequence: NonEmptyText
    source_evidence_scope_ids: tuple[NonEmptyId, ...]
    categories: tuple[InstinktTypedEffectCategoryV1, ...] = ()

    @model_validator(mode="after")
    def validate_option_effect(self) -> "InstinktTypedOptionEffectV1":
        if self.source_evidence_scope_ids != tuple(
            sorted(set(self.source_evidence_scope_ids))
        ):
            raise ValueError("Instinkt option evidence scope is not canonical")
        category_ids = tuple(item.category_id for item in self.categories)
        if category_ids != tuple(sorted(set(category_ids))):
            raise ValueError("Instinkt category IDs must use canonical unique order")
        for category in self.categories:
            if category.option_id != self.option_id:
                raise ValueError("Instinkt category belongs to another option")
            if not set(category.supporting_evidence_ids).issubset(
                self.source_evidence_scope_ids
            ):
                raise ValueError("Instinkt category cites another option's evidence")
        return self


class InstinktTypedRouteMappingV1(FrozenModel):
    schema_version: Literal["triad-instinkt-typed-route-mapping-v1"] = (
        "triad-instinkt-typed-route-mapping-v1"
    )
    mapping_mode: Literal["explicit_source_addressed_for_human_review"] = (
        "explicit_source_addressed_for_human_review"
    )
    source_evidence_sha256: HashDigest
    protected_target_label: NonEmptyText
    budget_kind: Literal["discretionary_budget"]
    necessary_cash_reserve_claim: Literal[False]
    evidence_assertions: tuple[InstinktEvidenceAssertionV1, ...]
    option_effects: tuple[InstinktTypedOptionEffectV1, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_mapping(self) -> "InstinktTypedRouteMappingV1":
        evidence_ids = tuple(item.evidence_id for item in self.evidence_assertions)
        if evidence_ids != tuple(sorted(set(evidence_ids))):
            raise ValueError("Instinkt evidence assertions are not canonical")
        option_ids = tuple(item.option_id for item in self.option_effects)
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Instinkt typed option IDs must be unique")
        return self


def _category(
    *,
    option_id: str,
    semantic_predicate: InstinktPredicate,
    evidence_ids: Sequence[str],
) -> Mapping[str, Any]:
    return {
        "category_id": semantic_predicate,
        "option_id": option_id,
        "supporting_evidence_ids": sorted(set(evidence_ids)),
        "semantic_predicate": semantic_predicate,
        "body_deltas": [
            {"dimension": dimension, "delta": delta}
            for dimension, delta in sorted(
                R2_EFFECT_RULES[semantic_predicate].items()
            )
        ],
    }


def _assertion(
    case: Mapping[str, Any],
    evidence_id: str,
    *assertions: InstinktAssertion,
) -> Mapping[str, Any]:
    text = _source_facts(case)[evidence_id]
    return {
        "evidence_id": evidence_id,
        "source_text_sha256": sha256_hex(text),
        "assertions": sorted(set(assertions)),
    }


def _typed_option_effect(
    case: Mapping[str, Any],
    *,
    option_id: str,
    consequence: str,
    evidence_scope: Sequence[str],
    categories: Sequence[tuple[InstinktPredicate, Sequence[str]]],
) -> Mapping[str, Any]:
    return {
        "option_id": option_id,
        "source_option_sha256": source_option_address(case, option_id),
        "source_consequence": consequence,
        "source_evidence_scope_ids": sorted(set(evidence_scope)),
        "categories": sorted(
            (
                _category(
                    option_id=option_id,
                    semantic_predicate=predicate,
                    evidence_ids=evidence_ids,
                )
                for predicate, evidence_ids in categories
            ),
            key=lambda item: item["category_id"],
        ),
    }


def _utility_instinkt_mapping(case: Mapping[str, Any]) -> Mapping[str, Any]:
    assertions = [
        _assertion(
            case,
            "utility_ev_cost",
            "discretionary_budget_exposure",
        ),
        _assertion(
            case,
            "utility_ev_reversibility",
            "bounded_cancellation",
        ),
        _assertion(
            case,
            "utility_ev_companion",
            "trusted_companion_present",
        ),
        _assertion(
            case,
            "utility_ev_safety",
            "verified_providers",
            "verified_return_path",
        ),
    ]
    return {
        "schema_version": "triad-instinkt-typed-route-mapping-v1",
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
        "option_effects": sorted(
            [
                _typed_option_effect(
                    case,
                    option_id="utility_trip_book",
                    consequence=(
                        "Self enters verified travel with trusted attachment "
                        "support, a 25-percent discretionary-budget commitment, "
                        "and bounded cancellation."
                    ),
                    evidence_scope=(
                        "utility_ev_cost",
                        "utility_ev_reversibility",
                        "utility_ev_companion",
                        "utility_ev_safety",
                    ),
                    categories=(
                        (
                            "discretionary_resource_commitment_25",
                            ("utility_ev_cost",),
                        ),
                        (
                            "bounded_cancellation_recovery",
                            ("utility_ev_reversibility",),
                        ),
                        (
                            "trusted_attachment_support",
                            ("utility_ev_companion",),
                        ),
                    ),
                ),
                _typed_option_effect(
                    case,
                    option_id="utility_trip_local",
                    consequence=(
                        "Self enters the local travel option with the same "
                        "grounded trusted companion; no local price is inferred."
                    ),
                    evidence_scope=("utility_ev_companion",),
                    categories=(
                        (
                            "trusted_attachment_support",
                            ("utility_ev_companion",),
                        ),
                    ),
                ),
                _typed_option_effect(
                    case,
                    option_id="utility_trip_home",
                    consequence=(
                        "Self does not make the stated travel expenditure and "
                        "retains the discretionary budget."
                    ),
                    evidence_scope=("utility_ev_cost",),
                    categories=(
                        (
                            "discretionary_resource_preserved",
                            ("utility_ev_cost",),
                        ),
                    ),
                ),
            ],
            key=lambda item: item["option_id"],
        ),
    }


def _protective_instinkt_mapping(
    case: Mapping[str, Any],
    *,
    exposed: bool,
) -> Mapping[str, Any]:
    if exposed:
        context_assertions: tuple[
            tuple[str, tuple[InstinktAssertion, ...]], ...
        ] = (
            (
                "protective_ev_companion",
                ("trusted_companion_absent",),
            ),
            (
                "protective_ev_environment",
                ("unfamiliar_environment",),
            ),
            (
                "protective_ev_lodging_transport",
                ("unverified_providers",),
            ),
            (
                "protective_ev_return_path",
                ("uncertain_return_path",),
            ),
        )
        book_context_categories: tuple[
            tuple[InstinktPredicate, tuple[str, ...]], ...
        ] = (
            (
                "absence_of_trusted_support",
                ("protective_ev_companion",),
            ),
            (
                "unfamiliar_environment_danger",
                ("protective_ev_environment",),
            ),
            (
                "unverified_provider_danger",
                ("protective_ev_lodging_transport",),
            ),
            (
                "uncertain_return_danger",
                ("protective_ev_return_path",),
            ),
        )
        local_categories = (
            (
                "absence_of_trusted_support",
                ("protective_ev_companion",),
            ),
            (
                "avoids_unfamiliar_uncertain_exposure",
                (
                    "protective_ev_environment",
                    "protective_ev_lodging_transport",
                    "protective_ev_return_path",
                ),
            ),
        )
        local_scope = (
            "protective_ev_companion",
            "protective_ev_environment",
            "protective_ev_lodging_transport",
            "protective_ev_return_path",
        )
        local_consequence = (
            "Self takes the local option without trusted attachment support "
            "and does not enter the evidenced unfamiliar route, unverified "
            "providers, or uncertain return path."
        )
        home_extra_categories = (
            (
                "avoids_unfamiliar_uncertain_exposure",
                (
                    "protective_ev_environment",
                    "protective_ev_lodging_transport",
                    "protective_ev_return_path",
                ),
            ),
        )
        home_scope = (
            "protective_ev_price",
            "protective_ev_environment",
            "protective_ev_lodging_transport",
            "protective_ev_return_path",
        )
        home_consequence = (
            "Self does not enter the evidenced unfamiliar route, unverified "
            "providers, or uncertain return path and does not make the stated "
            "discretionary-budget commitment."
        )
    else:
        context_assertions = (
            (
                "protective_ev_companion",
                ("trusted_companion_present",),
            ),
            (
                "protective_ev_environment",
                ("documented_environment",),
            ),
            (
                "protective_ev_lodging_transport",
                ("verified_providers",),
            ),
            (
                "protective_ev_return_path",
                ("verified_return_path",),
            ),
        )
        book_context_categories = (
            (
                "trusted_attachment_support",
                ("protective_ev_companion",),
            ),
            (
                "verified_provider_support",
                ("protective_ev_lodging_transport",),
            ),
            (
                "verified_return_support",
                ("protective_ev_return_path",),
            ),
        )
        local_categories = (
            (
                "trusted_attachment_support",
                ("protective_ev_companion",),
            ),
        )
        local_scope = ("protective_ev_companion",)
        local_consequence = (
            "Self takes the local option with grounded trusted attachment "
            "support; verified distance is not represented as danger."
        )
        home_extra_categories = ()
        home_scope = ("protective_ev_price",)
        home_consequence = (
            "Self does not make the stated discretionary-budget commitment; "
            "no distance-avoidance benefit is inferred."
        )
    assertions = [
        _assertion(
            case,
            "protective_ev_price",
            "discretionary_budget_exposure",
        ),
        _assertion(
            case,
            "protective_ev_refund",
            "nonrefundable_purchase",
        ),
        *(
            _assertion(case, evidence_id, *values)
            for evidence_id, values in context_assertions
        ),
    ]
    book_categories = (
        (
            "discretionary_resource_commitment_38",
            ("protective_ev_price",),
        ),
        (
            "nonrefundable_resource_exposure",
            ("protective_ev_refund",),
        ),
        *book_context_categories,
    )
    home_categories = (
        (
            "discretionary_resource_preserved",
            ("protective_ev_price",),
        ),
        *home_extra_categories,
    )
    return {
        "schema_version": "triad-instinkt-typed-route-mapping-v1",
        "mapping_mode": "explicit_source_addressed_for_human_review",
        "source_evidence_sha256": source_evidence_address(case),
        "protected_target_label": (
            "Self's physical integrity, ability to return, trusted attachment "
            "context, and discretionary budget."
        ),
        "budget_kind": "discretionary_budget",
        "necessary_cash_reserve_claim": False,
        "evidence_assertions": sorted(
            assertions, key=lambda item: item["evidence_id"]
        ),
        "option_effects": sorted(
            [
                _typed_option_effect(
                    case,
                    option_id="trip_book",
                    consequence=(
                        "Self enters the distant travel option under the "
                        "source-addressed protective context and non-refundable "
                        "38-percent discretionary-budget exposure."
                    ),
                    evidence_scope=(
                        "protective_ev_price",
                        "protective_ev_refund",
                        "protective_ev_companion",
                        "protective_ev_environment",
                        "protective_ev_lodging_transport",
                        "protective_ev_return_path",
                    ),
                    categories=book_categories,
                ),
                _typed_option_effect(
                    case,
                    option_id="trip_local",
                    consequence=local_consequence,
                    evidence_scope=local_scope,
                    categories=local_categories,
                ),
                _typed_option_effect(
                    case,
                    option_id="trip_home",
                    consequence=home_consequence,
                    evidence_scope=home_scope,
                    categories=home_categories,
                ),
            ],
            key=lambda item: item["option_id"],
        ),
    }


def author_instinkt_mapping(case: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the typed mapping selected by exact source content address."""

    source_hash = _object_sha256(case)
    if source_hash in _UTILITY_SOURCE_HASHES:
        return _utility_instinkt_mapping(case)
    if source_hash == _EXPOSED_SOURCE_HASH:
        return _protective_instinkt_mapping(case, exposed=True)
    if source_hash == _SUPPORTED_SOURCE_HASH:
        return _protective_instinkt_mapping(case, exposed=False)
    raise ValueError("No human-reviewed Instinkt mapping for source case")


def compile_instinkt_typed_mapping(
    case: Mapping[str, Any],
    mapping: Mapping[str, Any] | InstinktTypedRouteMappingV1,
) -> InstinktTypedRouteMappingV1:
    """Validate source closure without deriving any category from IDs or prose."""

    value = (
        mapping.model_dump(mode="json")
        if isinstance(mapping, InstinktTypedRouteMappingV1)
        else mapping
    )
    typed = validate_json_projection(InstinktTypedRouteMappingV1, value)
    if typed.source_evidence_sha256 != source_evidence_address(case):
        raise ValueError("Instinkt mapping belongs to another source evidence set")
    facts = _source_facts(case)
    options = _source_options(case)
    if {item.option_id for item in typed.option_effects} != set(options):
        raise ValueError("Instinkt typed mapping must cover all public options")
    assertions = {
        item.evidence_id: item for item in typed.evidence_assertions
    }
    for evidence_id, assertion in assertions.items():
        if evidence_id not in facts:
            raise ValueError("Instinkt mapping contains unknown evidence")
        if assertion.source_text_sha256 != sha256_hex(facts[evidence_id]):
            raise ValueError("Instinkt evidence assertion text address differs")
    for effect in typed.option_effects:
        if effect.source_option_sha256 != source_option_address(
            case, effect.option_id
        ):
            raise ValueError("Instinkt effect belongs to another public option")
        if not set(effect.source_evidence_scope_ids).issubset(assertions):
            raise ValueError("Instinkt option scope lacks typed evidence assertions")
        for category in effect.categories:
            cited_assertions = {
                assertion_value
                for evidence_id in category.supporting_evidence_ids
                for assertion_value in assertions[evidence_id].assertions
            }
            if (
                category.semantic_predicate
                == "avoids_unfamiliar_uncertain_exposure"
            ):
                if not cited_assertions.intersection(
                    AVOIDANCE_DANGER_ASSERTIONS
                ):
                    raise ValueError(
                        "Avoidance category lacks unfamiliar/uncertain danger evidence"
                    )
            elif not PREDICATE_REQUIREMENTS[
                category.semantic_predicate
            ].issubset(cited_assertions):
                raise ValueError(
                    "Instinkt category lacks its required source assertion"
                )

    payload = typed.model_dump(mode="json")
    payload["evidence_assertions"] = sorted(
        payload["evidence_assertions"],
        key=lambda item: item["evidence_id"],
    )
    for assertion in payload["evidence_assertions"]:
        assertion["assertions"] = sorted(assertion["assertions"])
    canonical_effects = []
    for effect in sorted(
        typed.option_effects, key=lambda item: item.option_id
    ):
        projected = effect.model_dump(mode="json")
        projected["source_evidence_scope_ids"] = sorted(
            effect.source_evidence_scope_ids
        )
        projected["categories"] = sorted(
            projected["categories"], key=lambda item: item["category_id"]
        )
        for category in projected["categories"]:
            category["supporting_evidence_ids"] = sorted(
                category["supporting_evidence_ids"]
            )
            category["body_deltas"] = sorted(
                category["body_deltas"], key=lambda item: item["dimension"]
            )
        canonical_effects.append(projected)
    payload["option_effects"] = canonical_effects
    return validate_json_projection(InstinktTypedRouteMappingV1, payload)


def _combined_deltas(
    categories: Sequence[InstinktTypedEffectCategoryV1],
) -> Mapping[str, float]:
    values: dict[str, float] = {}
    for category in categories:
        for item in category.body_deltas:
            values[item.dimension] = values.get(item.dimension, 0.0) + item.delta
    return {
        dimension: round(max(-0.25, min(0.25, values[dimension])), 6)
        for dimension in BODY_DIMENSIONS
        if dimension in values
    }


def _effect_spec(
    *,
    effect: InstinktTypedOptionEffectV1,
    protected_target_label: str,
    base_effect: Mapping[str, Any],
    excluded_category_id: str | None = None,
) -> InstinktEffectSpec:
    categories = tuple(
        category
        for category in effect.categories
        if category.category_id != excluded_category_id
    )
    deltas = _combined_deltas(categories)
    category_ids = tuple(category.category_id for category in categories)
    evidence_ids = tuple(
        sorted(
            {
                evidence_id
                for category in categories
                for evidence_id in category.supporting_evidence_ids
            }
        )
    )
    return InstinktEffectSpec(
        option_id=effect.option_id,
        body_deltas=tuple(
            BodyDelta(dimension=dimension, delta=delta)
            for dimension, delta in deltas.items()
        ),
        base_predicted_loss=base_effect["base_predicted_loss"],
        base_recoverability=base_effect["base_recoverability"],
        dominant_alarm=(
            "typed_source_route:" + "+".join(category_ids)
            if category_ids
            else "typed_source_route:no_grounded_category"
        ),
        protected_targets=(protected_target_label,),
        boundary_outcome=_outcome(deltas, "boundary_integrity"),
        trust_outcome=_outcome(deltas, "trust"),
        attachment_outcome=_outcome(deltas, "attachment_security"),
        escape_outcome=_outcome(deltas, "escape_availability"),
        action_tendency=_action(deltas),
        minimum_safety_condition=base_effect["minimum_safety_condition"],
        association_cue_tokens=category_ids,
        triggering_evidence_ids=evidence_ids,
    )


def project_instinkt_typed_sensitivity(
    *,
    mapping: InstinktTypedRouteMappingV1,
    packet: InstinktInputPacket,
    body_state: BodyState,
    config: InstinktSimulationConfig,
    base_effects: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    specs = tuple(
        _effect_spec(
            effect=effect,
            protected_target_label=mapping.protected_target_label,
            base_effect=base_effects[effect.option_id],
        )
        for effect in mapping.option_effects
    )
    effects = bind_instinkt_effects(packet, specs)
    rollouts = {
        effect.option_id: simulate_option_rollout(
            packet=packet,
            source_body_state=body_state,
            effect=effect,
            config=config,
        )
        for effect in effects
    }
    costs = {
        option_id: protective_cost(rollout, config)
        for option_id, rollout in rollouts.items()
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
    option_results = []
    for typed_effect in mapping.option_effects:
        total_cost = costs[typed_effect.option_id]
        contributions = []
        for category in typed_effect.categories:
            reduced_spec = _effect_spec(
                effect=typed_effect,
                protected_target_label=mapping.protected_target_label,
                base_effect=base_effects[typed_effect.option_id],
                excluded_category_id=category.category_id,
            )
            reduced_effect = reduced_spec.bind(packet)
            reduced_rollout = simulate_option_rollout(
                packet=packet,
                source_body_state=body_state,
                effect=reduced_effect,
                config=config,
            )
            reduced_cost = protective_cost(reduced_rollout, config)
            contributions.append(
                {
                    "category_id": category.category_id,
                    "semantic_predicate": category.semantic_predicate,
                    "supporting_evidence_ids": category.supporting_evidence_ids,
                    "body_deltas": {
                        item.dimension: item.delta
                        for item in category.body_deltas
                    },
                    "marginal_protective_cost_contribution": round(
                        total_cost - reduced_cost,
                        6,
                    ),
                }
            )
        rollout = rollouts[typed_effect.option_id]
        option_results.append(
            {
                "option_id": typed_effect.option_id,
                "source_consequence": typed_effect.source_consequence,
                "combined_body_deltas": _combined_deltas(
                    typed_effect.categories
                ),
                "predicted_loss": rollout.predicted_loss,
                "recoverability": rollout.recoverability,
                "protective_cost": total_cost,
                "category_contributions": contributions,
            }
        )
    return {
        "option_results": option_results,
        "selected_option_id": selected,
        "tied_option_ids": () if selected is not None else tied,
        "native_processor_executions": 0,
        "model_calls": 0,
    }


def _candidate_case_index(candidate: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {item["case_id"]: item for item in candidate["cases"]}


def _load_r1_candidate(repository_root: Path) -> Mapping[str, Any]:
    path = repository_root / R1_CANDIDATE_RELATIVE_PATH
    if hashlib.sha256(path.read_bytes()).hexdigest() != EXPECTED_R1_CANDIDATE_SHA256:
        raise ValueError("Frozen R1 corrected candidate bytes changed")
    candidate = _json(path)
    index = _candidate_case_index(candidate)
    if tuple(candidate["case_order"]) != CASE_ORDER:
        raise ValueError("Frozen R1 case order changed")
    for case_id in CASE_ORDER:
        if _object_sha256(index[case_id]) != EXPECTED_R1_CASE_SHA256[case_id]:
            raise ValueError(f"Frozen R1 source case changed: {case_id}")
    return candidate


def corrected_candidate_v2(repository_root: Path) -> Mapping[str, Any]:
    r1 = _load_r1_candidate(repository_root)
    index = _candidate_case_index(r1)
    cases = []
    for case_id in CASE_ORDER:
        source = index[case_id]
        case = copy.deepcopy(source)
        case["source_r1_case_sha256"] = _object_sha256(source)
        case["route_packets"]["emocio"].pop(
            "semantic_route_representation", None
        )
        emocio = compile_emocio_typed_annotation(
            source, author_emocio_annotation(source)
        )
        instinkt = compile_instinkt_typed_mapping(
            source, author_instinkt_mapping(source)
        )
        case["route_packets"]["emocio"][
            "typed_route_annotation_v1"
        ] = emocio.model_dump(mode="json")
        case["route_packets"]["instinkt"][
            "typed_effect_mapping_v1"
        ] = instinkt.model_dump(mode="json")
        cases.append(case)
    candidate = {
        "schema_version": "triad-iso-r2-corrected-candidate-v2",
        "candidate_id": "triad-route-isolation-e1r2-candidate-2026-07-24",
        "status": "unsealed_candidate",
        "execution_authorized": False,
        "human_review_status": "pending",
        "source_r1_candidate": {
            "path": R1_CANDIDATE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_R1_CANDIDATE_SHA256,
        },
        "case_order": CASE_ORDER,
        "cases": cases,
        "route_mode": "core_route",
    }
    forbidden_keys = {
        "expected_option",
        "expected_option_id",
        "expected_action",
        "leading_mind",
        "gold_route",
        "character",
        "character_profile",
        "governance",
        "option_flip_target",
    }
    for path, value in _walk(candidate):
        if path and path[-1].casefold() in forbidden_keys:
            raise ValueError(f"Corrected candidate V2 leakage at {'/'.join(path)}")
        if isinstance(value, str) and re.search(
            r"\b(?:preferred|best|safest|expected winner)\b",
            value,
            re.I,
        ):
            raise ValueError(f"Corrected candidate V2 leading prose at {'/'.join(path)}")
    return candidate


def replay_emocio_typed(repository_root: Path) -> Mapping[str, Any]:
    candidate = corrected_candidate_v2(repository_root)
    cases = []
    for case in candidate["cases"]:
        annotation = compile_emocio_typed_annotation(
            case,
            case["route_packets"]["emocio"]["typed_route_annotation_v1"],
        )
        valuations = project_emocio_typed_valuations(annotation)
        decision = choose_native_option(valuations)
        cases.append(
            {
                "case_id": case["case_id"],
                "source_r1_case_sha256": case["source_r1_case_sha256"],
                "manual_annotation_valid": True,
                "evidence_closure": "passed",
                "typed_annotation": annotation.model_dump(mode="json"),
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
                "processor_capability_claimed": False,
                "native_processor_executions": 0,
                "model_calls": 0,
            }
        )
    return {
        "schema_version": "triad-iso-r2-emocio-typed-replay-v1",
        "mode": "manual_annotation_deterministic_valuation",
        "cases": cases,
    }


def e1_instinkt_projection_inputs(
    repository_root: Path,
    case_id: str,
) -> tuple[
    InstinktInputPacket,
    BodyState,
    InstinktSimulationConfig,
    Mapping[str, Mapping[str, Any]],
]:
    inputs = _json(
        repository_root
        / E1_OUTPUT_RELATIVE_PATH
        / "cases"
        / case_id
        / "inputs.json"
    )["instinkt"]
    packet = validate_json_projection(InstinktInputPacket, inputs["packet"])
    body = validate_json_projection(BodyState, inputs["body_state"])
    config = validate_json_projection(
        InstinktSimulationConfig, inputs["simulation_config"]
    )
    base_effects = {
        item["option_id"]: item for item in inputs["option_effects"]
    }
    return packet, body, config, base_effects


def replay_instinkt_typed(repository_root: Path) -> Mapping[str, Any]:
    candidate = corrected_candidate_v2(repository_root)
    cases = []
    for case in candidate["cases"]:
        mapping = compile_instinkt_typed_mapping(
            case,
            case["route_packets"]["instinkt"]["typed_effect_mapping_v1"],
        )
        packet, body, config, base_effects = e1_instinkt_projection_inputs(
            repository_root, case["case_id"]
        )
        projection = project_instinkt_typed_sensitivity(
            mapping=mapping,
            packet=packet,
            body_state=body,
            config=config,
            base_effects=base_effects,
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "source_r1_case_sha256": case["source_r1_case_sha256"],
                "manual_mapping_valid": True,
                "evidence_closure": "passed",
                "typed_mapping": mapping.model_dump(mode="json"),
                **projection,
                "processor_capability_claimed": False,
            }
        )
    return {
        "schema_version": "triad-iso-r2-instinkt-typed-sensitivity-v1",
        "mode": "manual_mapping_deterministic_effect_sensitivity",
        "cases": cases,
    }


def pair_invariance_checks(
    emocio: Mapping[str, Any],
    instinkt: Mapping[str, Any],
) -> Mapping[str, Any]:
    e_index = {item["case_id"]: item for item in emocio["cases"]}
    i_index = {item["case_id"]: item for item in instinkt["cases"]}
    utility = CASE_ORDER[:2]
    protective = CASE_ORDER[2:]
    utility_e = (
        e_index[utility[0]]["valuation_vectors"]
        == e_index[utility[1]]["valuation_vectors"]
    )
    utility_i = [
        {
            "option_id": item["option_id"],
            "combined_body_deltas": item["combined_body_deltas"],
            "protective_cost": item["protective_cost"],
        }
        for item in i_index[utility[0]]["option_results"]
    ] == [
        {
            "option_id": item["option_id"],
            "combined_body_deltas": item["combined_body_deltas"],
            "protective_cost": item["protective_cost"],
        }
        for item in i_index[utility[1]]["option_results"]
    ]
    protective_e = (
        e_index[protective[0]]["valuation_vectors"]
        == e_index[protective[1]]["valuation_vectors"]
    )
    protective_i = (
        i_index[protective[0]]["option_results"]
        != i_index[protective[1]]["option_results"]
    )
    return {
        "schema_version": "triad-iso-r2-pair-invariance-v1",
        "utility_pair": {
            "emocio_non_target_route_stable": utility_e,
            "instinkt_non_target_route_stable": utility_i,
        },
        "protective_pair": {
            "emocio_typed_valuation_stable": protective_e,
            "instinkt_typed_route_distinguishable": protective_i,
        },
        "all_checks_passed": all(
            (utility_e, utility_i, protective_e, protective_i)
        ),
        "model_calls": 0,
        "native_processor_executions": {"E": 0, "I": 0},
    }


def frozen_r1_inventory(repository_root: Path) -> Mapping[str, Any]:
    paths = [
        path
        for path in sorted((repository_root / R1_OUTPUT_RELATIVE_PATH).rglob("*"))
        if path.is_file()
    ]
    paths.append(repository_root / ADJUDICATION_RELATIVE_PATH)
    paths = sorted(paths)
    records = [
        {
            "path": path.relative_to(repository_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in paths
    ]
    if len(records) != EXPECTED_R1_FILE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_R1_FILE_COUNT} frozen R1 files, found {len(records)}"
        )
    return {
        "file_count": len(records),
        "files": records,
        "inventory_sha256": _object_sha256(records),
    }


RELATION_TO_DIMENSION: Final[Mapping[str, str]] = {
    "target_scene_identity": "identity_only_not_scored",
    "self_position_relation": "self_visibility",
    "attraction_target": "target_only_not_scored",
    "attraction_strength": "attraction",
    "movement_destination": "destination_only_not_scored",
    "movement_magnitude": "movement",
    "immediacy": "attack_or_breakthrough_affordance",
    "novelty_strength": "novelty",
    "obstacle_relation": "attack_or_breakthrough_affordance",
    "desired_state_relation": "desired_scene_match",
    "broken_state_relation": "distance_from_broken_scene",
    "attention_relation": "attention",
    "status_relation": "status",
    "competition_relation": "competitive_success",
    "belonging_relation": "belonging",
}


def _render_report(
    *,
    candidate_sha256: str,
    emocio: Mapping[str, Any],
    instinkt: Mapping[str, Any],
    pairs: Mapping[str, Any],
) -> str:
    e_index = {item["case_id"]: item for item in emocio["cases"]}
    i_index = {item["case_id"]: item for item in instinkt["cases"]}
    lines = [
        "# TRIAD-ISO-R2 source-addressed typed-route correction",
        "",
        "This is a model-free research annotation and deterministic sensitivity "
        "screen. It is not autonomous Emocio cognition, an Instinkt processor "
        "execution, character evidence, holdout evidence, or promotion evidence.",
        "",
        "## Boundaries",
        "",
        "- `EmocioTypedRouteAnnotationV1` is explicit, source-addressed, and "
        "prepared for human review; semantic acceptance remains pending.",
        "- The compiler validates, checks evidence closure, canonicalizes, and "
        "projects valuations; it does not infer semantics from prose or IDs.",
        "- Instinkt categories cite typed assertions from the same option scope.",
        "- No decision derives from an option ID; no correction derives from a "
        "case ID.",
        "- Competition is not relevant in all four travel cases.",
        "- Distance alone is not danger.",
        "- Model calls: 0; character replay: 0; native processor executions: 0.",
        "",
        "## Candidate",
        "",
        f"- Corrected candidate V2 SHA-256: `{candidate_sha256}`.",
        "- Status: `unsealed_candidate`; execution authorized: false.",
        "- EUR 4800 budget base remains present in both utility cases.",
        "",
        "## Pair invariance",
        "",
        f"- Utility Emocio stable: "
        f"`{str(pairs['utility_pair']['emocio_non_target_route_stable']).lower()}`.",
        f"- Utility Instinkt stable: "
        f"`{str(pairs['utility_pair']['instinkt_non_target_route_stable']).lower()}`.",
        f"- Protective Emocio stable: "
        f"`{str(pairs['protective_pair']['emocio_typed_valuation_stable']).lower()}`.",
        f"- Protective Instinkt distinguishable: "
        f"`{str(pairs['protective_pair']['instinkt_typed_route_distinguishable']).lower()}`.",
        "",
    ]
    for case_id in CASE_ORDER:
        e_case = e_index[case_id]
        i_case = i_index[case_id]
        lines.extend(
            [
                f"## `{case_id}`",
                "",
                "Manual annotation validity: `passed`. Evidence closure: "
                "`passed`. Processor capability claimed: `false`.",
                "",
                "### EMOCIO",
                "",
            ]
        )
        for option in e_case["typed_annotation"]["options"]:
            lines.extend(
                [
                    f"#### `{option['option_id']}`",
                    "",
                    "| Typed relation | Value | Evidence | Resulting dimension |",
                    "|---|---|---|---|",
                ]
            )
            for field_name in EMOCIO_OPTION_RELATION_FIELDS:
                relation = option[field_name]
                value = (
                    "not_relevant"
                    if relation["state"] == "not_relevant"
                    else f"{relation['state']}:{relation['value']}"
                )
                evidence = ", ".join(relation["evidence_ids"]) or "—"
                lines.append(
                    f"| `{field_name}` | `{value}` | `{evidence}` | "
                    f"`{RELATION_TO_DIMENSION[field_name]}` |"
                )
            vector = e_case["valuation_vectors"][option["option_id"]]
            lines.extend(
                [
                    "",
                    "Valuation: "
                    + ", ".join(
                        f"`{name}={score:.6f}`"
                        for name, score in vector.items()
                    ),
                    "",
                ]
            )
        lines.extend(
            [
                f"Deterministic selected option: "
                f"`{e_case['selected_option_id']}`; ties: "
                f"`{', '.join(e_case['tied_option_ids']) or 'none'}`.",
                "",
                "### INSTINKT",
                "",
            ]
        )
        for option in i_case["option_results"]:
            lines.extend(
                [
                    f"#### `{option['option_id']}`",
                    "",
                    f"Source-addressed consequence: {option['source_consequence']}",
                    "",
                    "| Category | Semantic predicate | Evidence | Body delta | "
                    "Protective-cost contribution |",
                    "|---|---|---|---|---:|",
                ]
            )
            if not option["category_contributions"]:
                lines.append(
                    "| — | `no_grounded_category` | — | — | `0.000000` |"
                )
            for category in option["category_contributions"]:
                evidence = ", ".join(category["supporting_evidence_ids"])
                deltas = ", ".join(
                    f"{name}:{value:+.6f}"
                    for name, value in category["body_deltas"].items()
                )
                lines.append(
                    f"| `{category['category_id']}` | "
                    f"`{category['semantic_predicate']}` | `{evidence}` | "
                    f"`{deltas}` | "
                    f"`{category['marginal_protective_cost_contribution']:.6f}` |"
                )
            lines.extend(
                [
                    "",
                    f"Predicted loss: `{option['predicted_loss']:.6f}`; "
                    f"recoverability: `{option['recoverability']:.6f}`; "
                    f"protective cost: `{option['protective_cost']:.6f}`.",
                    "",
                ]
            )
        lines.extend(
            [
                f"Deterministic selected option: "
                f"`{i_case['selected_option_id']}`; ties: "
                f"`{', '.join(i_case['tied_option_ids']) or 'none'}`.",
                "",
            ]
        )
    lines.extend(
        [
            "## Stop state",
            "",
            "- Original E1 and R1 bytes remain unchanged.",
            "- Thinking content and local absolute paths are absent.",
            "- No execution seal was created.",
            "- No provider, model, image, character, remaining case, or G4 "
            "execution occurred.",
        ]
    )
    return "\n".join(lines).rstrip()


def _artifact_has_private_or_local_data(value: Any) -> bool:
    for path, item in _walk(value):
        if path and path[-1].casefold() in PRIVATE_KEYS:
            return True
        if isinstance(item, str) and (
            re.search(r"(?:[A-Za-z]:\\|/[A-Za-z0-9_.-]+/)", item)
            and not item.startswith("Docs/")
        ):
            return True
    return False


def prepare_r2(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / R2_OUTPUT_RELATIVE_PATH
    if output_root.exists():
        raise ValueError("TRIAD-ISO-R2 outputs are create-only")
    formal_verify_e1(repository_root)
    cold_verify_r1(repository_root)
    before = frozen_r1_inventory(repository_root)
    candidate = corrected_candidate_v2(repository_root)
    emocio = replay_emocio_typed(repository_root)
    instinkt = replay_instinkt_typed(repository_root)
    pairs = pair_invariance_checks(emocio, instinkt)
    if not pairs["all_checks_passed"]:
        raise ValueError("TRIAD-ISO-R2 pair invariance preflight failed")

    _write_json(output_root / "corrected_candidate_v2.json", candidate)
    _write_json(output_root / "emocio_typed_replay.json", emocio)
    _write_json(output_root / "instinkt_typed_sensitivity.json", instinkt)
    _write_json(output_root / "pair_invariance.json", pairs)
    candidate_sha = hashlib.sha256(
        (output_root / "corrected_candidate_v2.json").read_bytes()
    ).hexdigest()
    report = _render_report(
        candidate_sha256=candidate_sha,
        emocio=emocio,
        instinkt=instinkt,
        pairs=pairs,
    )
    report_path = output_root / "report.md"
    report_path.write_text(report + "\n", encoding="utf-8", newline="\n")

    outputs = [
        output_root / "corrected_candidate_v2.json",
        output_root / "emocio_typed_replay.json",
        output_root / "instinkt_typed_sensitivity.json",
        output_root / "pair_invariance.json",
        report_path,
    ]
    manifest_base = {
        "schema_version": "triad-iso-r2-manifest-v1",
        "phase": "TRIAD-ISO-R2",
        "status": "offline_typed_route_correction_complete",
        "base_commit": "fff7617a22948f595e075da267d52d90720cca03",
        "model_calls": 0,
        "character_replay_rows": 0,
        "native_processor_executions": {"E": 0, "I": 0, "R": 0},
        "image_generation_calls": 0,
        "source_r1": {
            "candidate_sha256": EXPECTED_R1_CANDIDATE_SHA256,
            "frozen_inventory_sha256": before["inventory_sha256"],
            "frozen_file_count": before["file_count"],
            "bytes_changed": False,
        },
        "outputs": [
            {
                "path": path.relative_to(repository_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in outputs
        ],
        "corrected_candidate_v2": {
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
    after = frozen_r1_inventory(repository_root)
    if after != before:
        raise ValueError("TRIAD-ISO-R2 mutated frozen R1 bytes")
    return manifest


def cold_verify_r2(repository_root: Path) -> Mapping[str, Any]:
    output_root = repository_root / R2_OUTPUT_RELATIVE_PATH
    manifest = _json(output_root / "manifest.json")
    base = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if _object_sha256(base) != manifest["manifest_sha256"]:
        raise ValueError("TRIAD-ISO-R2 manifest hash differs")
    formal_verify_e1(repository_root)
    cold_verify_r1(repository_root)
    r1_inventory = frozen_r1_inventory(repository_root)
    if r1_inventory["inventory_sha256"] != manifest["source_r1"][
        "frozen_inventory_sha256"
    ]:
        raise ValueError("TRIAD-ISO-R2 source R1 inventory changed")
    for record in manifest["outputs"]:
        path = repository_root / record["path"]
        if (
            not path.is_file()
            or path.stat().st_size != record["bytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]
        ):
            raise ValueError(f"TRIAD-ISO-R2 output changed: {record['path']}")
    candidate = _json(output_root / "corrected_candidate_v2.json")
    if candidate["status"] != "unsealed_candidate":
        raise ValueError("TRIAD-ISO-R2 candidate status changed")
    if candidate["execution_authorized"] is not False:
        raise ValueError("TRIAD-ISO-R2 candidate became executable")
    pairs = _json(output_root / "pair_invariance.json")
    if pairs["all_checks_passed"] is not True:
        raise ValueError("TRIAD-ISO-R2 pair invariance no longer passes")
    for path in output_root.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".md"}:
            value: Any = (
                _json(path) if path.suffix == ".json" else path.read_text("utf-8")
            )
            if _artifact_has_private_or_local_data(value):
                raise ValueError(
                    f"TRIAD-ISO-R2 artifact contains private/local data: {path.name}"
                )
    return {
        "status": "passed",
        "model_calls": 0,
        "character_replay_rows": 0,
        "native_processor_executions": {"E": 0, "I": 0, "R": 0},
        "original_e1_formal_verification": "passed",
        "original_r1_cold_verification": "passed",
        "original_r1_bytes_unchanged": True,
        "thinking_persisted": False,
        "local_absolute_paths_persisted": False,
        "candidate_v2_sha256": manifest["corrected_candidate_v2"]["sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
    }


__all__ = [
    "EmocioTypedOptionRouteV1",
    "EmocioTypedRouteAnnotationV1",
    "InstinktEvidenceAssertionV1",
    "InstinktTypedEffectCategoryV1",
    "InstinktTypedOptionEffectV1",
    "InstinktTypedRouteMappingV1",
    "R2_OUTPUT_RELATIVE_PATH",
    "SourceAddressedRelationV1",
    "author_emocio_annotation",
    "author_instinkt_mapping",
    "cold_verify_r2",
    "compile_emocio_typed_annotation",
    "compile_instinkt_typed_mapping",
    "corrected_candidate_v2",
    "e1_instinkt_projection_inputs",
    "frozen_r1_inventory",
    "pair_invariance_checks",
    "prepare_r2",
    "project_emocio_typed_valuations",
    "project_instinkt_typed_sensitivity",
    "replay_emocio_typed",
    "replay_instinkt_typed",
    "source_evidence_address",
    "source_option_address",
]
