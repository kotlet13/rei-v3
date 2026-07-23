"""TRIAD-D1 route diagnosis and model-free TRIAD-S2 candidate preflight.

Nothing in this module is imported by an active native processor or provider.
It reads the frozen TRIAD-S1 compact evidence, diagnoses capacity, and builds
replaceable research contracts for a future, separately sealed TRIAD-S2 run.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel

from ..ids import canonical_json_bytes


TRIAD_S1_HEAD: Final = "01d23f650494e4a24e47887325d9c9e11675424e"
TRIAD_S1_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-response-screen-v1-2026-07-23"
)
TRIAD_S2_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-s2-candidate-2026-07-23"
)
VALID_S1_CASE_IDS: Final = (
    "imperfect_product_launch",
    "loan_to_friend",
    "unstable_slope_rescue",
    "public_credit_conflict",
    "spontaneous_trip",
    "ambiguous_silence",
)
S2_CASE_IDS: Final = (
    "factory_overtemperature",
    "loan_to_friend",
    "public_credit_conflict",
    "spontaneous_trip",
)
EMOCIO_COUNTERFACTUAL_FIELDS: Final = (
    "entities_added",
    "entities_removed",
    "composition_changes",
    "movement",
    "self_position",
    "attention",
    "belonging",
    "status_relations",
    "attraction_markers",
    "obstacle_persistence",
    "obstacle_removal",
)
_EMOCIO_SIGNATURE_FIELDS: Final = (
    *EMOCIO_COUNTERFACTUAL_FIELDS,
)
_LEAKAGE_KEYS: Final = frozenset(
    {
        "expected_option_id",
        "expected_action",
        "expected_motive",
        "leading_mind",
        "character",
        "character_profile",
        "governance",
        "governance_tier",
        "gold_route",
        "selected_option",
        "selected_option_id",
        "protective_cost",
    }
)
_LEADING_TEXT: Final = re.compile(
    r"\b(safest|most safe|best|preferred|should choose|correct option|"
    r"expected option|must select)\b",
    re.IGNORECASE,
)


# Generic category-to-body-effect hypotheses. The same rule is used in every
# case; cases cannot tune a numeric protective cost or a desired winner.
CONSEQUENCE_EFFECT_RULES: Final[Mapping[str, Mapping[str, float]]] = {
    "hazard_exposure_stopped": {
        "physical_integrity": 0.10,
        "tension": -0.15,
        "predictability": 0.10,
    },
    "hazard_exposure_brief": {
        "physical_integrity": -0.05,
        "uncertainty": -0.10,
        "predictability": 0.05,
    },
    "hazard_exposure_continues": {
        "physical_integrity": -0.25,
        "tension": 0.20,
        "predictability": -0.10,
    },
    "resource_loss": {"resource_security": -0.20},
    "resource_exposure_high": {
        "resource_security": -0.30,
        "escape_availability": -0.10,
    },
    "resource_exposure_bounded": {"resource_security": -0.12},
    "resource_preserved": {"resource_security": 0.05},
    "boundary_added": {
        "boundary_integrity": 0.20,
        "predictability": 0.15,
    },
    "boundary_absent": {
        "boundary_integrity": -0.10,
        "predictability": -0.10,
    },
    "public_social_exposure": {
        "tension": 0.20,
        "uncertainty": 0.10,
    },
    "private_social_exposure": {
        "tension": -0.05,
        "predictability": 0.10,
    },
    "authorship_boundary_unaddressed": {"boundary_integrity": -0.15},
    "irreversible_commitment": {"escape_availability": -0.20},
    "reversible_commitment": {"escape_availability": -0.05},
    "movement_activation": {"arousal": 0.10},
    "movement_local": {"arousal": 0.05},
    "movement_absent": {"arousal": -0.05},
}


_S2_EMOCIO_DELTAS: Final[Mapping[str, tuple[Mapping[str, Any], ...]]] = {
    "factory_overtemperature": (
        {
            "option_id": "factory_shutdown",
            "evidence_basis_ids": (
                "factory_ev_damage",
                "factory_ev_visual",
            ),
            "delta": {
                "entities_added": ("controlled shutdown procedure",),
                "entities_removed": ("active production flow",),
                "composition_changes": (
                    "temperature gauge remains visible beside intact equipment",
                    "production flow changes to controlled stop",
                ),
                "movement": ("operator executes controlled stop sequence",),
                "self_position": "at shutdown controls",
                "attention": ("shutdown sequence", "temperature gauge"),
                "belonging": "operator remains responsible for shared process",
                "status_relations": ("operator accountable to shared process",),
                "attraction_markers": ("intact equipment", "clear operator position"),
                "obstacle_persistence": ("financial loss marker remains",),
                "obstacle_removal": ("continued production heat input",),
            },
        },
        {
            "option_id": "factory_verify",
            "evidence_basis_ids": (
                "factory_ev_sensor",
                "factory_ev_visual",
            ),
            "delta": {
                "entities_added": ("second sensor display", "three-minute timer"),
                "entities_removed": (),
                "composition_changes": (
                    "two conflicting sensor displays are inspected together",
                ),
                "movement": ("operator compares two displays",),
                "self_position": "between primary and backup displays",
                "attention": ("sensor disagreement", "three-minute limit"),
                "belonging": "operator remains responsible for shared process",
                "status_relations": ("operator accountable to shared process",),
                "attraction_markers": ("clear operator position",),
                "obstacle_persistence": (
                    "production heat input persists during brief verification",
                    "sensor truth remains unknown until checked",
                ),
                "obstacle_removal": (),
            },
        },
        {
            "option_id": "factory_continue",
            "evidence_basis_ids": (
                "factory_ev_temperature",
                "factory_ev_damage",
            ),
            "delta": {
                "entities_added": (),
                "entities_removed": (),
                "composition_changes": (
                    "active production flow remains beside rising gauge",
                ),
                "movement": ("production line keeps moving",),
                "self_position": "at current production controls",
                "attention": ("current production settings",),
                "belonging": "operator remains responsible for shared process",
                "status_relations": ("operator accountable to shared process",),
                "attraction_markers": (),
                "obstacle_persistence": (
                    "rising temperature",
                    "equipment-damage possibility",
                    "sensor disagreement",
                ),
                "obstacle_removal": (),
            },
        },
    ),
    "loan_to_friend": (
        {
            "option_id": "loan_full",
            "evidence_basis_ids": (
                "loan_ev_need",
                "loan_ev_budget",
            ),
            "delta": {
                "entities_added": ("full transfer marker",),
                "entities_removed": (),
                "composition_changes": (
                    "repair invoice remains between both people",
                    "cash-reserve display decreases by the full requested sum",
                ),
                "movement": ("full amount passes across the table",),
                "self_position": "lender remains opposite friend",
                "attention": ("friend's repair invoice", "reduced reserve display"),
                "belonging": "friend and lender remain at one table",
                "status_relations": ("friend and lender without a new written boundary",),
                "attraction_markers": ("continued connection",),
                "obstacle_persistence": (
                    "repayment timing remains unknown",
                    "relationship outcome remains unknown",
                ),
                "obstacle_removal": ("unfunded repair invoice",),
            },
        },
        {
            "option_id": "loan_limited_contract",
            "evidence_basis_ids": (
                "loan_ev_need",
                "loan_ev_history",
                "loan_ev_budget",
            ),
            "delta": {
                "entities_added": ("limited transfer marker", "written repayment date"),
                "entities_removed": (),
                "composition_changes": (
                    "smaller transfer and written date sit between both people",
                    "cash-reserve display decreases by a bounded amount",
                ),
                "movement": ("smaller amount and written date pass across the table",),
                "self_position": "lender remains opposite friend",
                "attention": ("repair invoice", "written repayment date"),
                "belonging": "friend and lender remain at one table",
                "status_relations": (
                    "friend and lender share an explicit repayment boundary",
                ),
                "attraction_markers": (
                    "continued connection",
                    "partly retained reserve display",
                ),
                "obstacle_persistence": (
                    "repayment timing remains uncertain",
                    "relationship outcome remains unknown",
                ),
                "obstacle_removal": (),
            },
        },
        {
            "option_id": "loan_decline",
            "evidence_basis_ids": (
                "loan_ev_need",
                "loan_ev_budget",
            ),
            "delta": {
                "entities_added": (),
                "entities_removed": ("transfer marker",),
                "composition_changes": (
                    "repair invoice remains unfunded",
                    "cash-reserve display remains unchanged",
                ),
                "movement": ("cash reserve remains with lender",),
                "self_position": "lender remains opposite friend",
                "attention": ("unfunded invoice", "unchanged reserve display"),
                "belonging": "relationship position remains unknown",
                "status_relations": ("friend and lender remain without a transfer",),
                "attraction_markers": ("stable reserve display",),
                "obstacle_persistence": (
                    "repair need remains",
                    "relationship outcome remains unknown",
                ),
                "obstacle_removal": ("cash-reserve exposure",),
            },
        },
    ),
    "public_credit_conflict": (
        {
            "option_id": "credit_public_confront",
            "evidence_basis_ids": (
                "credit_ev_statement",
                "credit_ev_record",
                "credit_ev_leader",
                "credit_ev_social_unknown",
            ),
            "delta": {
                "entities_added": ("timestamped record on meeting projection",),
                "entities_removed": (),
                "composition_changes": (
                    "authorship record becomes public while meeting continues",
                ),
                "movement": ("author stands and displays the record",),
                "self_position": "beside the shared projection",
                "attention": ("authorship record", "colleague's statement"),
                "belonging": "author, colleague, leader, and group remain in one meeting",
                "status_relations": (
                    "authorship claim is contested before leader and group",
                ),
                "attraction_markers": ("visible authorship record",),
                "obstacle_persistence": (
                    "social consequences remain unknown",
                ),
                "obstacle_removal": ("record hidden from the meeting",),
            },
        },
        {
            "option_id": "credit_private_evidence",
            "evidence_basis_ids": (
                "credit_ev_record",
                "credit_ev_leader",
            ),
            "delta": {
                "entities_added": ("private authorship record review",),
                "entities_removed": (),
                "composition_changes": (
                    "meeting ends before record is shown privately to leader",
                ),
                "movement": ("author moves beside leader after the meeting",),
                "self_position": "beside leader in private review",
                "attention": ("timestamped authorship record",),
                "belonging": "author and leader share a private evidence review",
                "status_relations": (
                    "leader receives authorship evidence outside the group",
                ),
                "attraction_markers": ("visible authorship record", "balanced positions"),
                "obstacle_persistence": (
                    "leader's assessment remains unknown",
                    "public statement remains uncorrected during the meeting",
                ),
                "obstacle_removal": ("record hidden from leader",),
            },
        },
        {
            "option_id": "credit_no_response",
            "evidence_basis_ids": (
                "credit_ev_statement",
                "credit_ev_record",
            ),
            "delta": {
                "entities_added": (),
                "entities_removed": (),
                "composition_changes": (
                    "colleague remains centered beside shared work",
                    "timestamped record stays on the laptop",
                ),
                "movement": ("author remains seated with no follow-up",),
                "self_position": "away from the shared projection",
                "attention": ("meeting proceeds without authorship evidence",),
                "belonging": "author remains in the observing group",
                "status_relations": ("colleague's public authorship claim remains"),
                "attraction_markers": (),
                "obstacle_persistence": (
                    "authorship record remains unseen",
                    "leader's assessment remains unknown",
                ),
                "obstacle_removal": (),
            },
        },
    ),
    "spontaneous_trip": (
        {
            "option_id": "trip_book",
            "evidence_basis_ids": (
                "trip_ev_deadline",
                "trip_ev_budget",
                "trip_ev_rarity",
            ),
            "delta": {
                "entities_added": ("booked distant ticket",),
                "entities_removed": ("uncommitted travel offer",),
                "composition_changes": (
                    "distant coast moves into the active route",
                    "discretionary-budget marker decreases by trip cost",
                ),
                "movement": ("distant travel begins",),
                "self_position": "traveller on distant route",
                "attention": ("distant coast", "non-refundable ticket"),
                "belonging": "single traveller remains the decision subject",
                "status_relations": (),
                "attraction_markers": ("expanded horizon", "vivid movement"),
                "obstacle_persistence": (
                    "future major costs remain unknown",
                    "experience satisfaction remains unknown",
                ),
                "obstacle_removal": ("closed horizon",),
            },
        },
        {
            "option_id": "trip_local",
            "evidence_basis_ids": (
                "trip_ev_budget",
                "trip_ev_visual",
            ),
            "delta": {
                "entities_added": ("local route marker",),
                "entities_removed": ("distant booking commitment",),
                "composition_changes": (
                    "nearby route moves into the active path",
                    "discretionary-budget marker decreases by a smaller amount",
                ),
                "movement": ("local travel begins",),
                "self_position": "traveller on nearby route",
                "attention": ("nearby route", "partly retained budget marker"),
                "belonging": "single traveller remains the decision subject",
                "status_relations": (),
                "attraction_markers": ("movement", "retained footing"),
                "obstacle_persistence": (
                    "distant horizon remains unvisited",
                    "experience satisfaction remains unknown",
                ),
                "obstacle_removal": ("full trip-cost exposure",),
            },
        },
        {
            "option_id": "trip_home",
            "evidence_basis_ids": (
                "trip_ev_budget",
                "trip_ev_visual",
            ),
            "delta": {
                "entities_added": (),
                "entities_removed": ("active travel route",),
                "composition_changes": (
                    "distant and local routes remain outside the active path",
                    "discretionary-budget marker remains unchanged",
                ),
                "movement": ("traveller remains in place",),
                "self_position": "traveller before closed travel routes",
                "attention": ("unchanged budget marker", "closed horizon"),
                "belonging": "single traveller remains the decision subject",
                "status_relations": (),
                "attraction_markers": ("retained footing",),
                "obstacle_persistence": (
                    "closed horizon",
                    "experience satisfaction remains unknown",
                ),
                "obstacle_removal": ("trip-cost exposure",),
            },
        },
    ),
}


_S2_INSTINKT_CONSEQUENCES: Final[
    Mapping[str, tuple[Mapping[str, Any], ...]]
] = {
    "factory_overtemperature": (
        {
            "option_id": "factory_shutdown",
            "facts": (
                {
                    "consequence_id": "factory_shutdown_heat_stop",
                    "statement": (
                        "The controlled shutdown stops production heat input and "
                        "incurs the stated shutdown loss."
                    ),
                    "source_evidence_ids": ("factory_ev_damage",),
                    "effect_categories": (
                        "hazard_exposure_stopped",
                        "resource_loss",
                    ),
                },
            ),
        },
        {
            "option_id": "factory_verify",
            "facts": (
                {
                    "consequence_id": "factory_verify_brief_exposure",
                    "statement": (
                        "The three-minute sensor check keeps the process exposed "
                        "briefly while comparing the conflicting readings."
                    ),
                    "source_evidence_ids": (
                        "factory_ev_sensor",
                        "factory_ev_temperature",
                    ),
                    "effect_categories": ("hazard_exposure_brief",),
                },
            ),
        },
        {
            "option_id": "factory_continue",
            "facts": (
                {
                    "consequence_id": "factory_continue_heat_exposure",
                    "statement": (
                        "Continuing at current settings preserves the rising-heat "
                        "exposure described by the process evidence."
                    ),
                    "source_evidence_ids": (
                        "factory_ev_temperature",
                        "factory_ev_damage",
                    ),
                    "effect_categories": ("hazard_exposure_continues",),
                },
            ),
        },
    ),
    "loan_to_friend": (
        {
            "option_id": "loan_full",
            "facts": (
                {
                    "consequence_id": "loan_full_reserve_exposure",
                    "statement": (
                        "The full transfer exposes 45 percent of the cash reserve."
                    ),
                    "source_evidence_ids": ("loan_ev_budget",),
                    "effect_categories": ("resource_exposure_high",),
                },
                {
                    "consequence_id": "loan_full_no_new_boundary",
                    "statement": (
                        "The full-loan option adds no new contractual repayment boundary."
                    ),
                    "source_evidence_ids": ("loan_ev_history",),
                    "effect_categories": ("boundary_absent",),
                },
            ),
        },
        {
            "option_id": "loan_limited_contract",
            "facts": (
                {
                    "consequence_id": "loan_limited_bounded_exposure",
                    "statement": (
                        "The limited transfer exposes a bounded portion of the reserve."
                    ),
                    "source_evidence_ids": ("loan_ev_budget",),
                    "effect_categories": ("resource_exposure_bounded",),
                },
                {
                    "consequence_id": "loan_limited_written_boundary",
                    "statement": (
                        "The written repayment date adds an explicit repayment boundary."
                    ),
                    "source_evidence_ids": ("loan_ev_history",),
                    "effect_categories": ("boundary_added",),
                },
            ),
        },
        {
            "option_id": "loan_decline",
            "facts": (
                {
                    "consequence_id": "loan_decline_reserve_unchanged",
                    "statement": (
                        "Declining leaves the cash reserve unchanged while the "
                        "relationship consequence remains unknown."
                    ),
                    "source_evidence_ids": (
                        "loan_ev_budget",
                        "loan_ev_need",
                    ),
                    "effect_categories": ("resource_preserved",),
                },
            ),
        },
    ),
    "public_credit_conflict": (
        {
            "option_id": "credit_public_confront",
            "facts": (
                {
                    "consequence_id": "credit_public_exposure",
                    "statement": (
                        "Displaying the record during the meeting creates public "
                        "social exposure whose consequences remain unknown."
                    ),
                    "source_evidence_ids": (
                        "credit_ev_record",
                        "credit_ev_leader",
                        "credit_ev_social_unknown",
                    ),
                    "effect_categories": (
                        "public_social_exposure",
                        "boundary_added",
                    ),
                },
            ),
        },
        {
            "option_id": "credit_private_evidence",
            "facts": (
                {
                    "consequence_id": "credit_private_review",
                    "statement": (
                        "Showing the timestamped record privately limits exposure "
                        "to the leader and preserves a later authorship boundary."
                    ),
                    "source_evidence_ids": (
                        "credit_ev_record",
                        "credit_ev_leader",
                    ),
                    "effect_categories": (
                        "private_social_exposure",
                        "boundary_added",
                    ),
                },
            ),
        },
        {
            "option_id": "credit_no_response",
            "facts": (
                {
                    "consequence_id": "credit_no_response_boundary",
                    "statement": (
                        "No response leaves the public authorship claim unaddressed."
                    ),
                    "source_evidence_ids": (
                        "credit_ev_statement",
                        "credit_ev_record",
                    ),
                    "effect_categories": ("authorship_boundary_unaddressed",),
                },
            ),
        },
    ),
    "spontaneous_trip": (
        {
            "option_id": "trip_book",
            "facts": (
                {
                    "consequence_id": "trip_book_budget_commitment",
                    "statement": (
                        "Booking commits 38 percent of the discretionary budget "
                        "under a non-refundable purchase."
                    ),
                    "source_evidence_ids": (
                        "trip_ev_budget",
                        "trip_ev_deadline",
                    ),
                    "effect_categories": (
                        "resource_exposure_high",
                        "irreversible_commitment",
                        "movement_activation",
                    ),
                },
            ),
        },
        {
            "option_id": "trip_local",
            "facts": (
                {
                    "consequence_id": "trip_local_bounded_commitment",
                    "statement": (
                        "The local route spends a smaller amount and starts local movement."
                    ),
                    "source_evidence_ids": (
                        "trip_ev_budget",
                        "trip_ev_visual",
                    ),
                    "effect_categories": (
                        "resource_exposure_bounded",
                        "reversible_commitment",
                        "movement_local",
                    ),
                },
            ),
        },
        {
            "option_id": "trip_home",
            "facts": (
                {
                    "consequence_id": "trip_home_no_commitment",
                    "statement": (
                        "Staying home leaves the discretionary budget unchanged "
                        "and starts no travel movement."
                    ),
                    "source_evidence_ids": (
                        "trip_ev_budget",
                        "trip_ev_visual",
                    ),
                    "effect_categories": (
                        "resource_preserved",
                        "movement_absent",
                    ),
                },
            ),
        },
    ),
}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def model_free_projection(value: Any) -> Any:
    """Serialize Pydantic and dataclass artifacts without executing a processor."""

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
    return value


def native_artifact_id_projection(
    compact_call_record: Mapping[str, Any],
) -> Mapping[str, str]:
    """Separate native conclusions from non-conclusion processing artifacts."""

    outputs = {
        mind: tuple(compact_call_record[mind]["call_record"]["output_artifact_ids"])
        for mind in ("racio", "emocio", "instinkt")
    }

    def exactly_one(prefix: str, values: Sequence[str]) -> str:
        matches = tuple(value for value in values if value.startswith(prefix))
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one {prefix} artifact")
        return matches[0]

    projected = {
        "racio_conclusion_id": exactly_one("racio_conclusion_", outputs["racio"]),
        "emocio_conclusion_id": exactly_one(
            "emocio_conclusion_", outputs["emocio"]
        ),
        "emocio_processing_result_id": exactly_one(
            "emocio_processing_result_", outputs["emocio"]
        ),
        "instinkt_conclusion_id": exactly_one(
            "instinkt_conclusion_", outputs["instinkt"]
        ),
    }
    conclusion_ids = (
        projected["racio_conclusion_id"],
        projected["emocio_conclusion_id"],
        projected["instinkt_conclusion_id"],
    )
    if projected["emocio_processing_result_id"] in conclusion_ids:
        raise ValueError("Emocio processing result cannot be a native conclusion")
    return projected


def _walk(value: Any, path: tuple[str, ...] = ()):
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def audit_expected_answer_leakage(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    findings: list[Mapping[str, str]] = []
    for path, value in _walk(candidate):
        if path and path[-1].casefold() in _LEAKAGE_KEYS:
            findings.append(
                {
                    "path": ".".join(path),
                    "kind": "forbidden_key",
                    "value_sha256": canonical_fingerprint(value),
                }
            )
        if isinstance(value, str) and _LEADING_TEXT.search(value):
            findings.append(
                {
                    "path": ".".join(path),
                    "kind": "leading_text",
                    "value_sha256": canonical_fingerprint(value),
                }
            )
    return {
        "schema_version": "triad-d1-leakage-report-v1",
        "phase": "TRIAD-D1",
        "model_calls": 0,
        "processor_calls": 0,
        "profile_blind": not findings,
        "expected_answer_leakage_found": bool(findings),
        "findings": findings,
    }


def _counterfactual_signature(item: Mapping[str, Any]) -> str:
    delta = item["delta"]
    return canonical_fingerprint(
        {field: delta[field] for field in _EMOCIO_SIGNATURE_FIELDS}
    )


def _derived_effect(item: Mapping[str, Any]) -> Mapping[str, float]:
    combined: dict[str, float] = {}
    for fact in item["facts"]:
        for category in fact["effect_categories"]:
            try:
                rule = CONSEQUENCE_EFFECT_RULES[category]
            except KeyError as exc:
                raise ValueError(f"Unknown consequence effect category: {category}") from exc
            for dimension, delta in rule.items():
                combined[dimension] = round(combined.get(dimension, 0.0) + delta, 6)
    return dict(sorted(combined.items()))


def _effect_signature(item: Mapping[str, Any]) -> str:
    return canonical_fingerprint(_derived_effect(item))


def _validate_duplicate_signatures(
    items: Sequence[Mapping[str, Any]],
    signatures: Mapping[str, str],
    *,
    kind: str,
) -> None:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        groups.setdefault(signatures[item["option_id"]], []).append(item)
    for duplicates in groups.values():
        if len(duplicates) > 1 and not all(
            item.get("intentional_ambiguity") is True for item in duplicates
        ):
            ids = tuple(item["option_id"] for item in duplicates)
            raise ValueError(f"Unmarked identical {kind} signatures: {ids}")


def preflight_s2_candidate(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    """Capacity-only preflight; it never computes or asserts a winning option."""

    if candidate.get("schema_version") != "triad-s2-corpus-candidate-v1":
        raise ValueError("Unsupported TRIAD-S2 candidate schema")
    cases = candidate.get("cases")
    if not isinstance(cases, list):
        raise ValueError("TRIAD-S2 candidate cases must be a list")
    if tuple(case.get("case_id") for case in cases) != S2_CASE_IDS:
        raise ValueError("TRIAD-S2 candidate must contain the exact four cases")
    leakage = audit_expected_answer_leakage(candidate)
    if leakage["expected_answer_leakage_found"]:
        raise ValueError("TRIAD-S2 candidate contains expected-answer leakage")

    case_reports = []
    for case in cases:
        option_ids = tuple(
            option["option_id"] for option in case["operational_en"]["options"]
        )
        evidence_ids = {
            evidence["evidence_id"]
            for evidence in case["operational_en"]["evidence"]
        }
        emocio_items = tuple(case["emocio_input"]["option_counterfactuals"])
        instinkt_items = tuple(case["instinkt_input"]["option_consequences"])
        if {item["option_id"] for item in emocio_items} != set(option_ids):
            raise ValueError("Emocio counterfactual scope differs from public options")
        if {item["option_id"] for item in instinkt_items} != set(option_ids):
            raise ValueError("Instinkt consequence scope differs from public options")
        for item in emocio_items:
            delta = item["delta"]
            if tuple(delta) != EMOCIO_COUNTERFACTUAL_FIELDS:
                raise ValueError("Emocio counterfactual fields are not canonical")
            if not set(item["evidence_basis_ids"]).issubset(evidence_ids):
                raise ValueError("Emocio consequence evidence is outside case scope")
        for item in instinkt_items:
            if not item["facts"]:
                raise ValueError("Instinkt option consequence facts cannot be empty")
            for fact in item["facts"]:
                if not set(fact["source_evidence_ids"]).issubset(evidence_ids):
                    raise ValueError("Instinkt consequence evidence is outside case scope")
                if not fact["effect_categories"]:
                    raise ValueError("Instinkt consequence fact lacks a typed effect")

        e_signatures = {
            item["option_id"]: _counterfactual_signature(item)
            for item in emocio_items
        }
        i_signatures = {
            item["option_id"]: _effect_signature(item)
            for item in instinkt_items
        }
        if len(set(e_signatures.values())) < 2:
            raise ValueError("Emocio has fewer than two counterfactual signatures")
        if len(set(i_signatures.values())) < 2:
            raise ValueError("Instinkt has fewer than two grounded effect signatures")
        _validate_duplicate_signatures(
            emocio_items,
            e_signatures,
            kind="Emocio counterfactual",
        )
        _validate_duplicate_signatures(
            instinkt_items,
            i_signatures,
            kind="Instinkt effect",
        )

        reverse_e = {
            item["option_id"]: _counterfactual_signature(item)
            for item in reversed(emocio_items)
        }
        reverse_i = {
            item["option_id"]: _effect_signature(item)
            for item in reversed(instinkt_items)
        }
        if e_signatures != reverse_e or i_signatures != reverse_i:
            raise ValueError("Option order changed a distinguishability signature")
        case_reports.append(
            {
                "case_id": case["case_id"],
                "emocio": {
                    "counterfactual_scene_signatures": dict(sorted(e_signatures.items())),
                    "unique_signature_count": len(set(e_signatures.values())),
                    "at_least_two_distinct": True,
                    "option_order_invariant": True,
                },
                "instinkt": {
                    "grounded_effect_signatures": dict(sorted(i_signatures.items())),
                    "derived_effects": {
                        item["option_id"]: _derived_effect(item)
                        for item in sorted(
                            instinkt_items,
                            key=lambda value: value["option_id"],
                        )
                    },
                    "unique_signature_count": len(set(i_signatures.values())),
                    "every_effect_has_option_specific_evidence": True,
                    "at_least_two_distinct": True,
                    "option_order_invariant": True,
                },
            }
        )
    return {
        "schema_version": "triad-d1-distinguishability-preflight-v1",
        "phase": "TRIAD-D1",
        "candidate_phase": "TRIAD-S2",
        "gate_scope": "distinguishability_only_not_option_quality",
        "model_calls": 0,
        "processor_calls": 0,
        "case_count": len(case_reports),
        "passed": True,
        "cases": case_reports,
    }


def build_s2_candidate(repository_root: Path) -> Mapping[str, Any]:
    s1 = _json(repository_root / TRIAD_S1_RELATIVE_PATH / "corpus.json")
    by_case = {case["case_id"]: case for case in s1["cases"]}
    cases = []
    for case_id in S2_CASE_IDS:
        source = by_case[case_id]
        cases.append(
            {
                "case_id": case_id,
                "source_s1_case_sha256": canonical_fingerprint(source),
                "canonical_sl": source["canonical_sl"],
                "operational_en": source["operational_en"],
                "racio_input": source["racio_input"],
                "emocio_input": {
                    "mode": "structured_only",
                    "world": source["emocio_input"]["world"],
                    "contract": (
                        "Apply option-specific structured counterfactual deltas, then "
                        "compare resulting scenes with desired and broken scenes; "
                        "option label matching is not a consequence model."
                    ),
                    "option_counterfactuals": _S2_EMOCIO_DELTAS[case_id],
                },
                "instinkt_input": {
                    "mapper": "RuleBasedOptionConsequenceInterpreterResearchV1",
                    "body_state": source["instinkt_input"]["body_state"],
                    "contract": (
                        "Derive typed body effects from grounded option-specific "
                        "consequence facts; packet-wide cues cannot be copied to "
                        "every option as an identical effect."
                    ),
                    "option_consequences": _S2_INSTINKT_CONSEQUENCES[case_id],
                },
                "profile_blind": True,
            }
        )
    return model_free_projection({
        "schema_version": "triad-s2-corpus-candidate-v1",
        "phase": "TRIAD-S2",
        "status": "candidate_preflight_only",
        "source_of_truth": "canonical_sl",
        "projection_method": "manually_written_operational_en",
        "execution_seal_created": False,
        "model_calls_performed": 0,
        "untouched_holdout": False,
        "promotion_evidence": False,
        "training_data": False,
        "case_count": 4,
        "future_targets": {
            "racio_model_calls": 4,
            "native_conclusions": 12,
            "frozen_bundles": 4,
            "character_replay_rows": 52,
        },
        "cases": cases,
    })


def build_expected_call_ledger() -> Mapping[str, Any]:
    return {
        "schema_version": "triad-s2-model-free-expected-call-ledger-v1",
        "phase": "TRIAD-S2",
        "prepared_by_phase": "TRIAD-D1",
        "state": "candidate_unsealed_not_executed",
        "execution_seal_created": False,
        "expected_future_execution": {
            "model_calls": 4,
            "retries": 0,
            "fallbacks": 0,
            "native_conclusions": 12,
            "frozen_bundles": 4,
            "character_replay_rows": 52,
        },
        "triad_d1_actual": {
            "scope": "s2_candidate_preparation_and_preflight_only",
            "model_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "native_processor_calls": 0,
            "character_replay_rows": 0,
        },
        "entries": [
            {
                "ordinal": index,
                "case_id": case_id,
                "future_model_calls": 1,
                "status": "planned_unsealed",
            }
            for index, case_id in enumerate(S2_CASE_IDS, start=1)
        ],
    }


def _semantic_scene_projection(rollout: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        field: rollout[field]
        for field in (
            "entities",
            "composition",
            "movement",
            "self_position",
            "attention_structure",
            "group_belonging",
            "status_relations",
            "attraction_markers",
            "obstacle_markers",
        )
    }


def _instinkt_effect_projection(effect: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        field: effect[field]
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
        )
    }


def build_s1_route_audit(repository_root: Path) -> Mapping[str, Any]:
    root = repository_root / TRIAD_S1_RELATIVE_PATH / "cases"
    cases = []
    for case_id in VALID_S1_CASE_IDS:
        outputs = _json(root / case_id / "native_outputs.json")
        inputs = _json(root / case_id / "inputs.json")
        visual_state = outputs["emocio"]["visual_state"]
        valuations = visual_state["option_valuations"]
        rollouts = visual_state["option_rollouts"]
        score_by_option = {
            item["option_id"]: item["score"]
            for item in outputs["emocio"]["policy"]["aggregate_scores"]
        }
        vectors = {
            item["option_id"]: {
                dimension["name"]: dimension["score"]
                for dimension in item["dimensions"]
            }
            for item in valuations
        }
        dimension_names = tuple(next(iter(vectors.values())))
        differing = tuple(
            name
            for name in dimension_names
            if len({vector[name] for vector in vectors.values()}) > 1
        )
        equal = tuple(name for name in dimension_names if name not in differing)
        rollout_signatures = {
            item["option_id"]: canonical_fingerprint(
                _semantic_scene_projection(item)
            )
            for item in rollouts
        }
        vector_signatures = {
            option_id: canonical_fingerprint(vector)
            for option_id, vector in vectors.items()
        }
        exact_desired_or_broken_atoms = {
            item["option_id"]: tuple(
                sorted(
                    set(item["composition"]).intersection(
                        {
                            *visual_state["desired_scene"]["composition"],
                            *visual_state["broken_scene"]["composition"],
                        }
                    )
                )
            )
            for item in rollouts
        }

        prediction_by_option = {
            item["option_id"]: item for item in outputs["instinkt"]["predictions"]
        }
        effect_by_option = {
            item["option_id"]: item for item in outputs["instinkt"]["option_effects"]
        }
        rollout_by_option = {
            item["option_id"]: item for item in outputs["instinkt"]["rollouts"]
        }
        cost_by_option = {
            item["option_id"]: item["protective_cost"]
            for item in outputs["instinkt"]["policy"]["option_scores"]
        }
        binding_by_id = {
            item["binding_id"]: item
            for item in inputs["instinkt"]["packet"]["cue_evidence_bindings"]
        }
        effect_signatures = {
            option_id: canonical_fingerprint(
                _instinkt_effect_projection(effect)
            )
            for option_id, effect in effect_by_option.items()
        }
        effect_counts = Counter(effect_signatures.values())
        tied_options = tuple(outputs["instinkt"]["policy"]["tied_option_ids"])
        tied_identical = (
            len(tied_options) > 1
            and len({effect_signatures[item] for item in tied_options}) == 1
        )
        degeneracy = any(count > 1 for count in effect_counts.values())
        classifications = []
        if tied_identical or degeneracy:
            classifications.extend(
                (
                    "identical-effect degeneracy",
                    "missing option-specific consequence",
                    "insufficient cue scope",
                )
            )
        cases.append(
            {
                "case_id": case_id,
                "emocio": {
                    "options": [
                        {
                            "option_id": option_id,
                            "valuation_dimensions": vectors[option_id],
                            "aggregate_score": score_by_option[option_id],
                            "valuation_vector_fingerprint": vector_signatures[
                                option_id
                            ],
                            "rollout_scene_fingerprint": rollout_signatures[
                                option_id
                            ],
                            "desired_or_broken_atom_matches": (
                                exact_desired_or_broken_atoms[option_id]
                            ),
                        }
                        for option_id in sorted(vectors)
                    ],
                    "dimensions_differing_between_options": differing,
                    "dimensions_equal_for_all_options": equal,
                    "full_rollout_inputs_identical": (
                        len(set(rollout_signatures.values())) == 1
                    ),
                    "valuation_vectors_identical": (
                        len(set(vector_signatures.values())) == 1
                    ),
                    "tie_semantically_justified": False,
                    "tie_due_to_identical_full_rollout_inputs": False,
                    "tie_undetermined": False,
                    "tie_diagnosis": (
                        "Distinct option label/description atoms change each full "
                        "rollout signature, but all scorer-relevant desired, broken, "
                        "movement, belonging, status, and attraction comparisons "
                        "collapse to the same valuation vector."
                    ),
                },
                "instinkt": {
                    "options": [
                        {
                            "option_id": option_id,
                            "cue_bindings": [
                                binding_by_id[binding_id]
                                for evidence in prediction_by_option[option_id][
                                    "evidence"
                                ]
                                for binding_id in evidence["cue_binding_ids"]
                            ],
                            "option_relations": [
                                evidence["option_relation"]
                                for evidence in prediction_by_option[option_id][
                                    "evidence"
                                ]
                            ],
                            "rule_ids": [
                                evidence["rule_id"]
                                for evidence in prediction_by_option[option_id][
                                    "evidence"
                                ]
                            ],
                            "predicted_body_deltas": prediction_by_option[option_id][
                                "combined_deltas"
                            ],
                            "effect_fingerprint": effect_signatures[option_id],
                            "predicted_loss": rollout_by_option[option_id][
                                "predicted_loss"
                            ],
                            "recoverability": rollout_by_option[option_id][
                                "recoverability"
                            ],
                            "protective_cost": cost_by_option[option_id],
                            "effect_signature_unique": (
                                effect_counts[effect_signatures[option_id]] == 1
                            ),
                        }
                        for option_id in sorted(effect_by_option)
                    ],
                    "policy_status": outputs["instinkt"]["policy"]["status"],
                    "selected_option_id": outputs["instinkt"]["policy"][
                        "selected_option_id"
                    ],
                    "tied_option_ids": tied_options,
                    "tie_has_identical_effect_signature": tied_identical,
                    "legitimate_protective_ambiguity": "not_established",
                    "classifications": tuple(classifications),
                    "tie_diagnosis": (
                        "The packet-wide grounded cue was copied through a coarse "
                        "protective/adverse option-text relation. Options in the same "
                        "relation inherited the same rule, deltas, loss, "
                        "recoverability, and protective cost."
                        if tied_options
                        else "No final policy tie occurred, but at least two options "
                        "still share one packet-wide effect signature."
                    ),
                },
            }
        )
    family_call = _json(root / "family_relocation" / "call_record.json")
    family_outputs = _json(root / "family_relocation" / "native_outputs.json")
    identities = native_artifact_id_projection(family_call)
    factory = _json(root / "factory_overtemperature" / "native_outputs.json")
    return {
        "schema_version": "triad-d1-route-distinguishability-audit-v1",
        "phase": "TRIAD-D1",
        "source_phase": "TRIAD-S1",
        "model_calls": 0,
        "global_score_computed": False,
        "cases": cases,
        "hypothesis_result": {
            "status": "confirmed_with_precision",
            "case_count": 6,
            "emocio_all_valuation_vectors_identical_within_case": all(
                case["emocio"]["valuation_vectors_identical"] for case in cases
            ),
            "emocio_all_full_rollout_signatures_identical_within_case": all(
                case["emocio"]["full_rollout_inputs_identical"] for case in cases
            ),
            "interpretation": (
                "All six cases inherit the same movement, belonging, status, and "
                "attraction structure within each case. Option label/description "
                "atoms do make full rollout signatures distinct, but exact atom "
                "comparison gives them no distinct desired/broken valuation effect."
            ),
        },
        "family_relocation": {
            **identities,
            "compact_observed_conclusion_ids": family_outputs[
                "observed_conclusion_ids"
            ],
            "projection_defect": (
                "The compact observed-conclusion list contains the Emocio "
                "processing-result ID instead of the Emocio conclusion ID."
            ),
            "replayed_after_original_execution": False,
            "included_in_s1_statistics": False,
        },
        "factory_overtemperature": {
            "original_status": factory["status"],
            "original_failure_type": factory["failure_type"],
            "exact_contract_rejection_cause_observable": False,
            "diagnosis": (
                "The historical compact evidence records only the bounded generic "
                "rejection. TRIAD-D1 does not infer an exact failure category and "
                "does not call the model again."
            ),
        },
    }


def render_route_audit(audit: Mapping[str, Any]) -> str:
    lines = [
        "# TRIAD-D1 route distinguishability audit",
        "",
        "Status: model-free diagnosis of the six fully evidenced TRIAD-S1 cases.",
        "TRIAD-S1 remains a historical partial screen. No model or native processor "
        "was executed, no global score was computed, and no frozen S1 artifact was "
        "rewritten.",
        "",
        "## Result",
        "",
        audit["hypothesis_result"]["interpretation"],
        "",
        "The hypothesis is therefore **confirmed with precision**: the full rollout "
        "JSON objects are not identical, but their differences are semantically "
        "inert for the current 11-dimension structured valuator. None of the six "
        "Emocio ties is established as semantically justified; none is "
        "undetermined from the compact evidence.",
        "",
        "For Instinkt, every case has only packet-wide cue scope and a coarse "
        "protective/adverse option relation. Duplicate effect signatures are not "
        "marked intentional ambiguity, so this audit classifies them as "
        "identical-effect degeneracy, missing option-specific consequence, and "
        "insufficient cue scope. This diagnosis does not assert which option should "
        "win.",
        "",
    ]
    for case in audit["cases"]:
        lines.extend((f"## {case['case_id']}", "", "### EMOCIO", ""))
        lines.append(
            "| option ID | 11-dimension valuation vector | aggregate | vector "
            "fingerprint | full rollout fingerprint |"
        )
        lines.append("|---|---|---:|---|---|")
        for option in case["emocio"]["options"]:
            vector = "; ".join(
                f"{name}={score}"
                for name, score in option["valuation_dimensions"].items()
            )
            lines.append(
                f"| `{option['option_id']}` | {vector} | "
                f"{option['aggregate_score']} | "
                f"`{option['valuation_vector_fingerprint']}` | "
                f"`{option['rollout_scene_fingerprint']}` |"
            )
        lines.extend(
            (
                "",
                "- Dimensions differing between options: "
                + (
                    ", ".join(case["emocio"]["dimensions_differing_between_options"])
                    or "none"
                )
                + ".",
                "- Dimensions equal for all options: "
                + ", ".join(case["emocio"]["dimensions_equal_for_all_options"])
                + ".",
                "- Full rollout inputs identical: "
                + str(case["emocio"]["full_rollout_inputs_identical"]).lower()
                + ".",
                "- Valuation vectors identical: "
                + str(case["emocio"]["valuation_vectors_identical"]).lower()
                + ".",
                "- Tie semantically justified: false.",
                "- Tie caused by identical full rollout inputs: false.",
                "- Tie undetermined: false.",
                "- Diagnosis: " + case["emocio"]["tie_diagnosis"],
                "",
                "### INSTINKT",
                "",
            )
        )
        lines.append(
            "| option ID | cue bindings | option relation | rule IDs | body deltas | "
            "effect fingerprint | loss | recoverability | protective cost | unique |"
        )
        lines.append("|---|---|---|---|---|---|---:|---:|---:|---|")
        for option in case["instinkt"]["options"]:
            bindings = "; ".join(
                f"{item['binding_id']} ({item['cue_class']}: {item['cue']})"
                for item in option["cue_bindings"]
            )
            deltas = "; ".join(
                f"{item['dimension']}={item['delta']}"
                for item in option["predicted_body_deltas"]
            )
            lines.append(
                f"| `{option['option_id']}` | {bindings} | "
                f"{', '.join(option['option_relations'])} | "
                f"{', '.join(option['rule_ids'])} | {deltas} | "
                f"`{option['effect_fingerprint']}` | "
                f"{option['predicted_loss']} | {option['recoverability']} | "
                f"{option['protective_cost']} | "
                f"{str(option['effect_signature_unique']).lower()} |"
            )
        classifications = (
            ", ".join(case["instinkt"]["classifications"]) or "none"
        )
        lines.extend(
            (
                "",
                f"- Policy status: `{case['instinkt']['policy_status']}`.",
                "- Selected option: "
                + (
                    f"`{case['instinkt']['selected_option_id']}`."
                    if case["instinkt"]["selected_option_id"]
                    else "none."
                ),
                "- Tied option IDs: "
                + (
                    ", ".join(
                        f"`{item}`"
                        for item in case["instinkt"]["tied_option_ids"]
                    )
                    if case["instinkt"]["tied_option_ids"]
                    else "none"
                )
                + ".",
                "- Legitimate protective ambiguity: not established; no "
                "intentional-ambiguity marker exists in S1.",
                f"- Classification: {classifications}.",
                "- Diagnosis: " + case["instinkt"]["tie_diagnosis"],
                "",
            )
        )

    family = audit["family_relocation"]
    factory = audit["factory_overtemperature"]
    lines.extend(
        (
            "## Family relocation reconciliation",
            "",
            f"- Racio conclusion ID: `{family['racio_conclusion_id']}`.",
            f"- Emocio conclusion ID: `{family['emocio_conclusion_id']}`.",
            "- Emocio processing-result ID: "
            f"`{family['emocio_processing_result_id']}`.",
            f"- Instinkt conclusion ID: `{family['instinkt_conclusion_id']}`.",
            "",
            family["projection_defect"],
            "The regression fix is prospective: conclusion IDs are now selected by "
            "artifact type/prefix, the Emocio dataclass has a model-free serializer, "
            "and a processing-result ID cannot enter the three native conclusion "
            "slots. No S1 bundle was reconstructed. "
            "`replayed_after_original_execution=false`; family relocation remains "
            "excluded from S1 statistics.",
            "",
            "## Factory failure observability",
            "",
            f"- Original compact status: `{factory['original_status']}`.",
            f"- Original failure type: `{factory['original_failure_type']}`.",
            "- Exact original contract rejection cause observable: false.",
            "",
            factory["diagnosis"],
            "For future screens, the provider now emits a bounded typed diagnostic "
            "for an already-parsed `RacioStructuredOutput` packet-contract rejection: "
            "canonical JSON projection, SHA-256, exact bounded failure code, "
            "validation stage, and `accepted=false`. It stores no thinking, raw "
            "traceback, local path, E/I output, character, or gold label.",
            "",
            "## Replaceable capability hypothesis for TRIAD-S2",
            "",
            "Emocio receives option-specific structured counterfactual deltas for "
            "entities, composition, movement, self position, attention, belonging, "
            "status, attraction, and obstacle persistence/removal. A future "
            "valuator may compare the resulting scenes with desired and broken "
            "scenes; exact option-label matching is not the consequence model.",
            "",
            "Instinkt receives grounded option-specific consequence facts. A generic "
            "research mapper derives typed body deltas from consequence categories; "
            "the candidate contains neither expected protective costs nor expected "
            "selections. Packet-wide cues cannot automatically create one effect for "
            "every option.",
            "",
            "The model-free preflight checks signature variance, evidence scope, "
            "explicit marking of intentional ambiguity, and option-order invariance. "
            "It checks capacity only, not which option should win.",
            "",
            "## Scope statement",
            "",
            "Emocio response was tested after structured scene routing. This does "
            "not validate image-native visual cognition.",
            "",
            "Instinkt response was tested after typed cue routing. This does not "
            "validate raw-scene Instinkt perception.",
            "",
            "TRIAD-S2 is prepared only as an unsealed candidate. Its future target is "
            "4 Racio calls, 12 native conclusions, 4 frozen bundles, and 52 replay "
            "rows. TRIAD-D1 performed 0 model calls and created no pre-call execution "
            "seal.",
            "",
        )
    )
    return "\n".join(lines)


def frozen_s1_paths(repository_root: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            TRIAD_S1_HEAD,
            "--",
            TRIAD_S1_RELATIVE_PATH.as_posix(),
        ],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(
        Path(line)
        for line in result.stdout.splitlines()
        if line.strip()
    )


def verify_frozen_s1_bytes(repository_root: Path) -> None:
    """Compare every pre-D1 S1 byte against the accepted S1 execution head."""

    for relative_path in frozen_s1_paths(repository_root):
        expected = subprocess.run(
            ["git", "show", f"{TRIAD_S1_HEAD}:{relative_path.as_posix()}"],
            cwd=repository_root,
            check=True,
            capture_output=True,
        ).stdout
        observed = (repository_root / relative_path).read_bytes()
        if observed != expected:
            raise ValueError(f"Frozen TRIAD-S1 bytes changed: {relative_path}")


__all__ = [
    "CONSEQUENCE_EFFECT_RULES",
    "S2_CASE_IDS",
    "TRIAD_S1_HEAD",
    "TRIAD_S1_RELATIVE_PATH",
    "TRIAD_S2_RELATIVE_PATH",
    "VALID_S1_CASE_IDS",
    "audit_expected_answer_leakage",
    "build_expected_call_ledger",
    "build_s1_route_audit",
    "build_s2_candidate",
    "canonical_fingerprint",
    "frozen_s1_paths",
    "model_free_projection",
    "native_artifact_id_projection",
    "preflight_s2_candidate",
    "render_route_audit",
    "verify_frozen_s1_bytes",
]
