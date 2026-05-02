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
    "premik",
    "začeti",
    "zaceti",
    "zagnati",
    "odpreti",
    "svoboda",
    "iti naprej",
    "dati odpoved",
    "poskusiti",
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
    "meja",
    "preveriti",
    "odlašati",
    "odlasati",
    "počakati",
    "pocakati",
    "zaščititi",
    "zascititi",
    "tveganje",
    "varnost",
    "stabilnost",
    "umik",
    "izguba",
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
    "facts",
    "timeline",
    "cost",
    "constraints",
    "podatki",
    "dokazi",
    "možnost",
    "moznost",
    "načrt",
    "nacrt",
    "zaporedje",
    "struktura",
    "test",
    "neznano",
    "strošek",
    "strosek",
}
ATTACHMENT_WORDS = {
    "alone",
    "abandonment",
    "return",
    "partner",
    "panic",
    "attachment",
    "relationship",
    "repair",
    "sam",
    "sama",
    "zapuščen",
    "zapuscen",
    "vrniti",
    "partner",
    "panika",
    "navezanost",
    "odnos",
}
FREEZE_WORDS = {
    "freeze",
    "freezing",
    "body alarm",
    "body freezes",
    "judging",
    "judgment",
    "disappear",
    "paralysis",
    "zamrzniti",
    "zmrznem",
    "telo",
    "presoja",
    "izpostavljenost",
    "izginem",
}
RETURN_LOOP_WORDS = {
    "return",
    "returning",
    "one more chance",
    "beautiful",
    "hurts",
    "painful",
    "alone",
    "panic",
    "vrniti",
    "lep",
    "boli",
    "sam",
    "sama",
    "panika",
}
BOUNDED_ACTION_WORDS = {
    "bounded",
    "reversible",
    "pilot",
    "prototype",
    "small test",
    "one test",
    "stop condition",
    "runway",
    "omejen",
    "reverzibilen",
    "poskus",
    "pilot",
}
CONFRONT_WORDS = {"confront", "boundary violation", "honesty", "friend", "soočiti", "soociti", "meja"}


def _text(*values: Any) -> str:
    chunks: list[str] = []
    for value in values:
        if isinstance(value, list):
            chunks.extend(str(item) for item in value)
        elif isinstance(value, dict):
            chunks.extend(str(item) for item in value.values())
        elif value is not None:
            chunks.append(str(value))
    return " ".join(chunks).lower()


def _has_any(text: str, words: set[str]) -> bool:
    return any(word in text for word in words)


def _signal_text(signal: dict[str, Any]) -> str:
    return _text(
        signal.get("preferred_action"),
        signal.get("known_facts"),
        signal.get("logical_options"),
        signal.get("rationalization_risk"),
        signal.get("unknowns"),
        signal.get("desired_image"),
        signal.get("broken_image"),
        signal.get("pride_or_shame"),
        signal.get("attack_impulse"),
        signal.get("threat_map"),
        signal.get("minimum_safety_condition"),
        signal.get("flight_or_freeze_signal"),
        signal.get("attachment_issue"),
        signal.get("perception"),
        signal.get("primary_motive"),
        signal.get("non_accepted_expression"),
    )


def infer_action_tag(signal: dict[str, Any], mind: str) -> str:
    text = _signal_text(signal)
    if _has_any(text, RETURN_LOOP_WORDS):
        return "return"
    if _has_any(text, FREEZE_WORDS):
        return "withdraw"
    if _has_any(text, {"delay", "wait", "pause", "research", "odlašati", "odlasati", "počakati", "pocakati"}):
        return "delay"
    if _has_any(text, CONFRONT_WORDS):
        return "confront"
    if _has_any(text, BOUNDED_ACTION_WORDS):
        return "move"
    if _has_any(text, MOVEMENT_WORDS):
        return "move"
    if _has_any(text, PLANNING_WORDS) or mind == "racio":
        return "analyze"
    if _has_any(text, SAFETY_WORDS) or mind == "instinkt":
        return "protect"
    return "unknown"


def classify_behavioral_alignment(
    racio: dict[str, Any],
    emocio: dict[str, Any],
    instinkt: dict[str, Any],
) -> str:
    tags = {
        "racio": infer_action_tag(racio, "racio"),
        "emocio": infer_action_tag(emocio, "emocio"),
        "instinkt": infer_action_tag(instinkt, "instinkt"),
    }
    active = {tag for tag in tags.values() if tag != "unknown"}
    if not active:
        return "unknown"
    if len(active) == 1:
        return "aligned"
    if active <= {"analyze", "delay", "protect"}:
        return "aligned"
    if active <= {"return", "protect"}:
        return "aligned"
    if "move" in active and active.intersection({"delay", "withdraw", "protect"}):
        return "split"
    if "return" in active and active.intersection({"analyze", "protect"}):
        return "ambivalent"
    return "ambivalent"


def _acceptance_quality(
    behavioral_alignment: str,
    combined_text: str,
    action_tags: dict[str, str],
) -> tuple[str, str]:
    if _has_any(combined_text, RETURN_LOOP_WORDS) and _has_any(combined_text, ATTACHMENT_WORDS):
        return "non_accepting", "attachment panic + beautiful-image hope + Racio rationalization"
    if _has_any(combined_text, FREEZE_WORDS):
        return "mixed", "body alarm overrides conscious plan"
    if action_tags.get("racio") == "delay" and _has_any(combined_text, {"data", "research", "planning", "podatki"}):
        return "mixed", "rationalized safety freeze"
    if _has_any(combined_text, BOUNDED_ACTION_WORDS) and behavioral_alignment != "split":
        return "accepting", "bounded reversible action with reality contact"
    if behavioral_alignment == "aligned" and action_tags.get("instinkt") in {"delay", "withdraw", "return"}:
        return "non_accepting", "shared behavior reduces reality contact"
    if behavioral_alignment == "split":
        return "mixed", "one processor moves while another blocks or withdraws"
    return "mixed", "partial acceptance with unresolved processor tension"


def _coalition_pattern(action_tags: dict[str, str], pattern: str, combined_text: str) -> str:
    if "attachment panic" in pattern:
        return "Emocio + Instinkt coalition: beautiful-image hope fused with attachment panic."
    if "rationalized safety" in pattern:
        return "Instinkt + Racio coalition: safety fear translated as responsible planning."
    if "body alarm" in pattern:
        return "Instinkt overrides Racio's plan while Emocio still wants recognition."
    if action_tags.get("racio") == "analyze" and action_tags.get("emocio") == "move" and action_tags.get("instinkt") in {"delay", "withdraw", "protect"}:
        return "Racio and Emocio move toward action while Instinkt guards exposure."
    if _has_any(combined_text, BOUNDED_ACTION_WORDS):
        return "All three processors can cooperate around a bounded reversible test."
    return "No stable coalition is visible yet."


def assess_acceptance(
    racio: dict[str, Any],
    emocio: dict[str, Any],
    instinkt: dict[str, Any],
    mode: Optional[str] = None,
) -> AcceptanceAssessment:
    racio_text = _signal_text(racio)
    emocio_text = _signal_text(emocio)
    instinkt_text = _signal_text(instinkt)
    combined_text = _text(racio_text, emocio_text, instinkt_text)

    action_tags = {
        "racio": infer_action_tag(racio, "racio"),
        "emocio": infer_action_tag(emocio, "emocio"),
        "instinkt": infer_action_tag(instinkt, "instinkt"),
    }
    behavioral_alignment = classify_behavioral_alignment(racio, emocio, instinkt)
    acceptance_quality, non_acceptance_pattern = _acceptance_quality(
        behavioral_alignment,
        combined_text,
        action_tags,
    )

    desire_vs_safety = _has_any(emocio_text, MOVEMENT_WORDS) and _has_any(instinkt_text, SAFETY_WORDS)
    rational_plan_unaccepted = (
        _has_any(racio_text, PLANNING_WORDS)
        and action_tags.get("racio") == "delay"
        and _has_any(emocio_text, {"shame", "humiliation", "dead", "boring", "alive", "desire", "admiration"})
        and _has_any(instinkt_text, SAFETY_WORDS | FREEZE_WORDS)
    )
    epistemic_gap = len(racio.get("unknowns") or []) >= 3 or "unknown" in racio_text

    if mode in {"accepting", "mixed", "conflicted", "unknown"} and mode != "unknown":
        overall = mode
    elif acceptance_quality == "non_accepting":
        overall = "conflicted"
    elif rational_plan_unaccepted or acceptance_quality == "mixed":
        overall = "mixed"
    elif desire_vs_safety or epistemic_gap:
        overall = "mixed"
    else:
        overall = "accepting"

    if "attachment panic" in non_acceptance_pattern:
        main_conflict = "Behavior may align around returning, but the alignment serves panic relief rather than acceptance."
        sabotage = "The loop repeats when fear of being alone and the beautiful image override reality contact."
        lead_next = "instinkt"
    elif rational_plan_unaccepted or "rationalized safety" in non_acceptance_pattern:
        main_conflict = "Racio can explain a plan, while Emocio and Instinkt do not yet accept its cost."
        sabotage = "The system may delay or reframe avoidance as responsible planning."
        lead_next = "racio"
    elif desire_vs_safety:
        main_conflict = "Emocio wants movement or image renewal while Instinkt asks for minimum safety."
        sabotage = "Instinkt may slow the move, or Emocio may push before safety is defined."
        lead_next = "instinkt"
    elif "body alarm" in non_acceptance_pattern:
        main_conflict = "The conscious career plan conflicts with a body-alarm freeze under exposure."
        sabotage = "The talk may be cancelled, postponed, or physically frozen at the threshold."
        lead_next = "instinkt"
    elif epistemic_gap:
        main_conflict = "Racio does not have enough explicit information to close the decision cleanly."
        sabotage = "The next step may become over-analysis instead of a bounded test."
        lead_next = "racio"
    else:
        main_conflict = "No major incompatibility is visible in the first processor pass."
        sabotage = "The main risk is treating a provisional simulation as certainty."
        lead_next = "racio"

    coalition_pattern = _coalition_pattern(action_tags, non_acceptance_pattern, combined_text)
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
            "racio_action_tag": action_tags["racio"],
            "emocio_action_tag": action_tags["emocio"],
            "instinkt_action_tag": action_tags["instinkt"],
        },
        behavioral_alignment=behavioral_alignment,  # type: ignore[arg-type]
        acceptance_quality=acceptance_quality,  # type: ignore[arg-type]
        non_acceptance_pattern=non_acceptance_pattern,
        coalition_pattern=coalition_pattern,
        sabotage_mechanism=sabotage,
    )
