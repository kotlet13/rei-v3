from __future__ import annotations

from typing import Any, Optional

from .models import AcceptanceAssessment


MOVEMENT_WORDS = {
    "act",
    "approach",
    "begin",
    "enter",
    "express",
    "freedom",
    "launch",
    "move",
    "open",
    "quit",
    "show",
    "start",
    "try",
}
SAFETY_WORDS = {
    "boundary",
    "check",
    "delay",
    "hold",
    "pause",
    "protect",
    "reduce",
    "risk",
    "runway",
    "safe",
    "safety",
    "stability",
    "wait",
    "withdraw",
}
PLANNING_WORDS = {
    "data",
    "evidence",
    "option",
    "plan",
    "sequence",
    "structure",
    "test",
    "unknown",
}


def _text(*values: Any) -> str:
    chunks: list[str] = []
    for value in values:
        if isinstance(value, list):
            chunks.extend(str(item) for item in value)
        elif value is not None:
            chunks.append(str(value))
    return " ".join(chunks).lower()


def _has_any(text: str, words: set[str]) -> bool:
    return any(word in text for word in words)


def assess_acceptance(
    racio: dict[str, Any],
    emocio: dict[str, Any],
    instinkt: dict[str, Any],
    mode: Optional[str] = None,
) -> AcceptanceAssessment:
    racio_text = _text(
        racio.get("preferred_action"),
        racio.get("resistance_to_other_minds"),
        racio.get("unknowns"),
        racio.get("rationalization_risk"),
    )
    emocio_text = _text(
        emocio.get("preferred_action"),
        emocio.get("desired_image"),
        emocio.get("resistance_to_other_minds"),
        emocio.get("non_accepted_expression"),
    )
    instinkt_text = _text(
        instinkt.get("preferred_action"),
        instinkt.get("minimum_safety_condition"),
        instinkt.get("threat_map"),
        instinkt.get("resistance_to_other_minds"),
        instinkt.get("non_accepted_expression"),
    )

    desire_vs_safety = _has_any(emocio_text, MOVEMENT_WORDS) and _has_any(instinkt_text, SAFETY_WORDS)
    rational_plan_unaccepted = (
        _has_any(racio_text, PLANNING_WORDS)
        and _has_any(emocio_text, {"shame", "humiliation", "dead", "boring", "alive", "desire"})
        and _has_any(instinkt_text, SAFETY_WORDS)
    )
    epistemic_gap = len(racio.get("unknowns") or []) >= 3 or "unknown" in racio_text

    if mode in {"accepting", "mixed", "conflicted", "unknown"} and mode != "unknown":
        overall = mode
    elif rational_plan_unaccepted:
        overall = "conflicted"
    elif desire_vs_safety or epistemic_gap:
        overall = "mixed"
    else:
        overall = "accepting"

    if rational_plan_unaccepted:
        main_conflict = "Racio can explain a plan, while Emocio and Instinkt do not yet accept its cost."
        sabotage = "The system may delay or reframe avoidance as responsible planning."
        lead_next = "racio"
    elif desire_vs_safety:
        main_conflict = "Emocio wants movement or image renewal while Instinkt asks for minimum safety."
        sabotage = "Instinkt may slow the move, or Emocio may push before safety is defined."
        lead_next = "instinkt"
    elif epistemic_gap:
        main_conflict = "Racio does not have enough explicit information to close the decision cleanly."
        sabotage = "The next step may become over-analysis instead of a bounded test."
        lead_next = "racio"
    else:
        main_conflict = "No major incompatibility is visible in the first processor pass."
        sabotage = "The main risk is treating a provisional simulation as certainty."
        lead_next = "racio"

    return AcceptanceAssessment(
        overall_level=overall,  # type: ignore[arg-type]
        racio_acceptance="Racio can contribute if its plan remains provisional and checks non-verbal resistance.",
        emocio_acceptance="Emocio can contribute if image, desire, and shame are named without turning into domination.",
        instinkt_acceptance="Instinkt can contribute if safety is defined as a condition for action, not a veto on all movement.",
        main_conflict=main_conflict,
        likely_sabotage_point=sabotage,
        task_delegation={
            "lead_next": lead_next,
            "racio_needs": "clear facts, unknowns, sequence, and a bounded test",
            "emocio_needs": "an image of aliveness or dignity that does not require manipulation",
            "instinkt_needs": "minimum safety, boundary, and reversibility",
        },
    )
