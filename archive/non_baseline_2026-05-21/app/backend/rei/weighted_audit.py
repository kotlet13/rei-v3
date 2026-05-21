from __future__ import annotations

from collections import Counter, defaultdict
import json
import re
from typing import Any


MIND_IDS = ("R", "E", "I")

PROFILE_TOP_MINDS: dict[str, list[str]] = {
    "R": ["R"],
    "E": ["E"],
    "I": ["I"],
    "RE": ["R", "E"],
    "RI": ["R", "I"],
    "EI": ["E", "I"],
    "R>E>I": ["R"],
    "R>I>E": ["R"],
    "E>R>I": ["E"],
    "E>I>R": ["E"],
    "I>R>E": ["I"],
    "I>E>R": ["I"],
    "REI": ["R", "E", "I"],
}

SCENARIO_PRESSURE_MIND: dict[str, str | None] = {
    "pure-budget-allocation": "R",
    "technical-architecture-choice": "R",
    "business-runway": None,
    "creative-status-risk": "E",
    "night-door-noise": "I",
}

SCENARIO_GROUNDING_TERMS: dict[str, list[str]] = {
    "pure-budget-allocation": [
        "budget",
        "testing",
        "design",
        "infrastructure",
        "marketing",
        "allocation",
        "cost",
    ],
    "technical-architecture-choice": [
        "architecture",
        "fast",
        "brittle",
        "reliable",
        "untested",
        "maintenance",
        "timeline",
    ],
    "business-runway": [
        "business",
        "runway",
        "paying customer",
        "stability",
        "launch",
        "collapse",
    ],
    "creative-status-risk": [
        "artist",
        "exhibition",
        "bold",
        "admired",
        "mocked",
        "pride",
        "visible",
    ],
    "night-door-noise": [
        "door",
        "noise",
        "night",
        "open",
        "listen",
        "call for help",
        "secure distance",
    ],
}

FUNCTIONAL_PRESENCE_THRESHOLD = 0.4
SCENARIO_GROUNDING_THRESHOLD = 0.35

FUNCTIONAL_MARKERS: dict[str, dict[str, list[str]]] = {
    "R": {
        "facts_or_evidence": ["fact", "evidence", "proof", "known", "unknown", "data", "constraint"],
        "calculation_or_tradeoff": [
            "cost",
            "benefit",
            "tradeoff",
            "utility",
            "material",
            "probability",
            "budget",
            "resource",
        ],
        "sequence_or_plan": ["sequence", "order", "timeline", "step", "plan", "execute", "test"],
        "explicit_consequence": ["consequence", "if", "then", "result", "outcome", "condition"],
        "rationalization_awareness": ["rationalization", "justify", "explanation", "after-the-fact", "reason"],
    },
    "E": {
        "image_or_scene": ["image", "scene", "visible", "appearance", "picture", "display", "show"],
        "desire_or_aliveness": ["desire", "aliveness", "alive", "pull", "attraction", "longing", "spark"],
        "social_meaning": [
            "recognition",
            "admiration",
            "belonging",
            "status",
            "audience",
            "connection",
            "response",
        ],
        "shame_or_pride": ["shame", "pride", "humiliation", "mocked", "embarrassment", "dignity"],
        "expressive_value": ["meaning", "beauty", "expression", "creative", "personal", "identity"],
    },
    "I": {
        "threat_or_loss": ["threat", "risk", "loss", "danger", "harm", "collapse", "exposure"],
        "body_or_alarm": ["body", "alarm", "tension", "freeze", "panic", "breath", "throat", "chest"],
        "boundary_or_trust": ["boundary", "trust", "limit", "violation", "distance", "access", "door"],
        "protection_or_withdrawal": ["protect", "guard", "withdraw", "hold", "pause", "secure", "shield"],
        "scarcity_or_safety": ["safety", "scarcity", "runway", "resource", "minimum", "fallback"],
    },
}

GENERIC_SYNTHESIS_PHRASES = [
    "racio contributes",
    "emocio contributes",
    "instinkt contributes",
    "weighted compromise",
    "all three minds",
    "underrepresented signal",
    "character profile",
    "situation-activated",
]

STOCK_PHRASES = [
    "bounded test",
    "minimum safety condition",
    "responsible planning",
    "reversible",
    "stop condition",
    "safety requirement",
    "winning coalition",
    "blocked",
    "preserve safety",
    "smallest reversible next step",
    "gather more data",
    "responsible risk management",
]

MIND_MARKERS: dict[str, list[str]] = {
    "R": [
        "racio",
        "calculation",
        "cost",
        "evidence",
        "proof",
        "sequence",
        "utility",
        "material",
        "constraint",
        "tradeoff",
        "plan",
        "explicit consequence",
    ],
    "E": [
        "emocio",
        "image",
        "desire",
        "pride",
        "shame",
        "recognition",
        "visible",
        "admiration",
        "aliveness",
        "belonging",
        "meaning",
        "status",
    ],
    "I": [
        "instinkt",
        "risk",
        "loss",
        "danger",
        "boundary",
        "body",
        "safety",
        "exposure",
        "withdrawal",
        "trust",
        "protection",
        "threat",
    ],
}


def _synthesis(trace_payload: dict[str, Any]) -> dict[str, Any]:
    synthesis = trace_payload.get("synthesis_turn") or {}
    return synthesis if isinstance(synthesis, dict) else {}


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _numeric_mind_map(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    values: dict[str, float] = {}
    for mind in MIND_IDS:
        number = _as_float(raw.get(mind))
        if number is not None:
            values[mind] = number
    return values


def normalized_contributions(contributions: dict[str, float]) -> dict[str, float]:
    total = sum(contributions.values())
    if total <= 0:
        return {}
    return {mind: round(contributions.get(mind, 0.0) / total, 3) for mind in MIND_IDS}


def expected_ranking(contributions: dict[str, float]) -> list[str]:
    return sorted(MIND_IDS, key=lambda mind: (contributions.get(mind, 0.0), -MIND_IDS.index(mind)), reverse=True)


def contribution_integrity(synthesis: dict[str, Any]) -> dict[str, Any]:
    contributions = _numeric_mind_map(synthesis.get("weighted_contributions"))
    ranking = [mind for mind in synthesis.get("contribution_ranking") or [] if mind in MIND_IDS]
    contribution_sum = round(sum(contributions.values()), 3)
    expected = expected_ranking(contributions) if set(contributions) == set(MIND_IDS) else []
    normalized = normalized_contributions(contributions)
    tilt = synthesis.get("synthesis_tilt")
    return {
        "contribution_sum": contribution_sum,
        "contribution_sum_valid": bool(contributions) and abs(contribution_sum - 1.0) <= 0.02,
        "weighted_contributions_normalized": bool(contributions) and abs(contribution_sum - 1.0) <= 0.02,
        "normalized_contributions": normalized,
        "ranking_matches_contributions": bool(expected) and ranking[:3] == expected,
        "tilt_matches_ranking": bool(ranking) and tilt == ranking[0],
    }


def mind_marker_visibility(text: str) -> dict[str, bool]:
    lowered = text.lower()
    visibility: dict[str, bool] = {}
    for mind, markers in MIND_MARKERS.items():
        visibility[mind] = any(re.search(rf"\b{re.escape(marker.lower())}\b", lowered) for marker in markers)
    return visibility


def stock_phrase_hits_in_text(text: str) -> dict[str, int]:
    lowered = text.lower()
    hits: dict[str, int] = {}
    for phrase in STOCK_PHRASES:
        count = len(re.findall(re.escape(phrase), lowered))
        if count:
            hits[phrase] = count
    return hits


def stock_phrase_hits(payload: Any) -> dict[str, int]:
    return stock_phrase_hits_in_text(json.dumps(payload, ensure_ascii=False))


def _contains_marker(text: str, marker: str) -> bool:
    escaped = re.escape(marker.lower())
    if re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.lower()):
        return True
    return False


def extract_functional_mind_evidence(text: str) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for mind, groups in FUNCTIONAL_MARKERS.items():
        evidence: list[dict[str, object]] = []
        missing: list[str] = []
        for group, markers in groups.items():
            found = [marker for marker in markers if _contains_marker(text, marker)]
            if found:
                evidence.append({"group": group, "markers": found})
            else:
                missing.append(group)
        score = round(len(evidence) / len(groups), 3) if groups else 0.0
        result[mind] = {
            "present": score >= FUNCTIONAL_PRESENCE_THRESHOLD,
            "score": score,
            "evidence": evidence,
            "missing_functions": missing,
        }
    return result


def detect_role_name_only_warning(text: str, functional_presence: dict[str, dict[str, object]]) -> bool:
    names = {"R": "racio", "E": "emocio", "I": "instinkt"}
    lowered = text.lower()
    for mind, name in names.items():
        if name in lowered and not functional_presence.get(mind, {}).get("present"):
            return True
    return False


def functional_presence_score(functional_presence: dict[str, dict[str, object]]) -> float:
    scores = [_as_float(functional_presence.get(mind, {}).get("score")) or 0.0 for mind in MIND_IDS]
    return round(sum(scores) / len(MIND_IDS), 3)


def detect_generic_role_listing(text: str, functional_presence: dict[str, dict[str, object]]) -> bool:
    lowered = text.lower()
    generic_count = sum(1 for phrase in GENERIC_SYNTHESIS_PHRASES if phrase in lowered)
    return generic_count >= 3 and functional_presence_score(functional_presence) < 0.65


def scenario_grounding_audit(text: str, scenario_id: str, grounding_terms: list[str] | None = None) -> dict[str, object]:
    terms = grounding_terms if grounding_terms is not None else SCENARIO_GROUNDING_TERMS.get(scenario_id, [])
    matched = [term for term in terms if _contains_marker(text, term)]
    missing = [term for term in terms if term not in matched]
    score = round(len(matched) / len(terms), 3) if terms else 0.0
    return {
        "score": score,
        "matched_terms": matched,
        "missing_expected_terms": missing,
        "low_scenario_grounding_warning": bool(terms) and score < SCENARIO_GROUNDING_THRESHOLD,
    }


def classify_weighted_compromise_quality(audit: dict[str, Any]) -> str:
    if not audit.get("has_final_monologue") or not audit.get("has_weighted_contributions"):
        return "unknown"
    functional = audit.get("functional_presence") or {}
    present_count = sum(1 for mind in MIND_IDS if functional.get(mind, {}).get("present"))
    scenario_grounding = audit.get("scenario_grounding") or {}
    stock_hits = sum((audit.get("stock_phrase_hits") or {}).values())
    severe_stock = stock_hits > 3
    weighted_ok = bool(
        audit.get("all_three_minds_present_in_contributions")
        and audit.get("ranking_matches_contributions")
        and audit.get("tilt_matches_ranking")
    )
    grounding_ok = not scenario_grounding.get("low_scenario_grounding_warning")
    if (
        audit.get("all_three_minds_functionally_present")
        and weighted_ok
        and grounding_ok
        and not audit.get("generic_role_listing_warning")
        and not severe_stock
    ):
        return "good"
    if weighted_ok and present_count >= 2 and grounding_ok:
        return "partial"
    return "weak"


def _hijack_note_is_substantive(note: Any, expected_mind: str | None, profile_top: list[str]) -> bool:
    if not expected_mind or expected_mind in profile_top:
        return True
    text = str(note or "").strip().lower()
    if not text:
        return False
    generic_low = text.startswith("low:") or "remains inside the character profile" in text
    return not generic_low


def _rei_explanation(
    final_monologue: str,
    main_conflict: str,
    main_agreement: str,
    contributions: dict[str, float],
    functional_presence: dict[str, dict[str, object]],
) -> dict[str, Any]:
    text = " ".join([final_monologue, main_conflict, main_agreement]).lower()
    majority_pair: list[str] = []
    for first, second in (("R", "E"), ("R", "I"), ("E", "I")):
        first_visible = bool(functional_presence.get(first, {}).get("present")) or any(
            marker in text for marker in MIND_MARKERS[first]
        )
        second_visible = bool(functional_presence.get(second, {}).get("present")) or any(
            marker in text for marker in MIND_MARKERS[second]
        )
        if first_visible and second_visible:
            majority_pair = [first, second]
            break
    minority = next((mind for mind in MIND_IDS if mind not in majority_pair), None) if majority_pair else None
    ranking = expected_ranking(contributions) if set(contributions) == set(MIND_IDS) else []
    top_two_gap = 0.0
    if len(ranking) >= 2:
        top_two_gap = round(contributions[ranking[0]] - contributions[ranking[1]], 3)
    rei_top_two_close = bool(ranking) and top_two_gap <= 0.15
    rei_minority_objection_visible = bool(
        minority
        and (
            functional_presence.get(minority, {}).get("present")
            or any(marker in text for marker in MIND_MARKERS[minority])
        )
    )
    explanation_present = bool(
        majority_pair
        and (
            "two of three" in text
            or "two-of-three" in text
            or "two out of three" in text
            or "majority" in text
            or "majority pair" in text
        )
    )
    if rei_top_two_close and (
        rei_minority_objection_visible
        or all(functional_presence.get(mind, {}).get("present") for mind in MIND_IDS)
    ):
        explanation_present = True
    return {
        "rei_two_of_three_explanation_present": explanation_present,
        "rei_majority_pair": majority_pair,
        "rei_minority_objection": minority,
        "rei_top_two_gap": top_two_gap,
        "rei_top_two_close": rei_top_two_close,
        "rei_minority_objection_visible": rei_minority_objection_visible,
    }


def audit_weighted_synthesis(
    trace_payload: dict[str, Any],
    profile: str,
    scenario_id: str,
    grounding_terms: list[str] | None = None,
) -> dict[str, Any]:
    synthesis = _synthesis(trace_payload)
    processor_weights = _numeric_mind_map(synthesis.get("processor_weights"))
    contributions = _numeric_mind_map(synthesis.get("weighted_contributions"))
    ranking = [mind for mind in synthesis.get("contribution_ranking") or [] if mind in MIND_IDS]
    tilt = synthesis.get("synthesis_tilt")
    underrepresented = synthesis.get("underrepresented_signal")
    final_monologue = str(synthesis.get("final_monologue") or "")
    main_conflict = str(synthesis.get("main_conflict") or "")
    main_agreement = str(synthesis.get("main_agreement") or "")
    profile_top = PROFILE_TOP_MINDS.get(profile, [])
    missing_minds = [mind for mind, visible in mind_marker_visibility(final_monologue).items() if not visible]
    expected_pressure_mind = SCENARIO_PRESSURE_MIND.get(scenario_id)
    integrity = contribution_integrity(synthesis)
    functional_presence = extract_functional_mind_evidence(final_monologue)
    all_functional = all(functional_presence[mind]["present"] for mind in MIND_IDS)
    functional_score = functional_presence_score(functional_presence)
    role_name_only = detect_role_name_only_warning(final_monologue, functional_presence)
    generic_role_listing = detect_generic_role_listing(final_monologue, functional_presence)
    grounding = scenario_grounding_audit(final_monologue, scenario_id, grounding_terms)
    rei = (
        _rei_explanation(final_monologue, main_conflict, main_agreement, contributions, functional_presence)
        if profile == "REI"
        else {}
    )
    rei_warning = bool(profile == "REI" and tilt in MIND_IDS and not rei.get("rei_two_of_three_explanation_present"))

    audit = {
        "has_processor_weights": bool(processor_weights),
        "has_weighted_contributions": bool(contributions),
        "has_contribution_ranking": bool(ranking),
        "has_synthesis_tilt": tilt in MIND_IDS,
        "has_underrepresented_signal": underrepresented in MIND_IDS,
        "has_final_monologue": bool(final_monologue.strip()),
        "all_three_minds_present_in_contributions": set(contributions) == set(MIND_IDS),
        "all_three_minds_visible_in_final_monologue": not missing_minds,
        "missing_mind_mentions_in_final_monologue": missing_minds,
        "functional_presence": functional_presence,
        "all_three_minds_functionally_present": all_functional,
        "functional_presence_score": functional_score,
        "role_name_only_warning": role_name_only,
        "generic_role_listing_warning": generic_role_listing,
        "scenario_grounding": grounding,
        "tilt_matches_profile_top": tilt in profile_top,
        "mechanical_profile_match_warning": bool(tilt in profile_top and missing_minds),
        "hijack_expected_but_missing": not _hijack_note_is_substantive(
            synthesis.get("hijack_risk"), expected_pressure_mind, profile_top
        ),
        "stock_phrase_hits": stock_phrase_hits(synthesis),
        "decision_extraction_valid": bool((synthesis.get("decision") or {}).get("chosen_option")),
        "expected_pressure_mind": expected_pressure_mind,
        "rei_two_of_three_explanation_present": rei.get("rei_two_of_three_explanation_present"),
        "rei_majority_pair": rei.get("rei_majority_pair") or [],
        "rei_minority_objection": rei.get("rei_minority_objection"),
        "rei_top_two_gap": rei.get("rei_top_two_gap"),
        "rei_top_two_close": rei.get("rei_top_two_close"),
        "rei_minority_objection_visible": rei.get("rei_minority_objection_visible"),
        "rei_arbitrary_tilt_warning": rei_warning,
        **integrity,
    }
    audit["weighted_compromise_quality"] = classify_weighted_compromise_quality(audit)
    return audit


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _allowed_matches(text: str, allowed_options: list[str], option_aliases: dict[str, list[str]] | None = None) -> list[str]:
    normalized = _normalize_text(text)
    exact = [option for option in allowed_options if normalized == _normalize_text(option)]
    if exact:
        return exact
    alias_matches: list[str] = []
    for option, aliases in (option_aliases or {}).items():
        if option not in allowed_options:
            continue
        if any(_normalize_text(alias) in normalized for alias in aliases):
            alias_matches.append(option)
    if alias_matches:
        for priority_word in ("hybrid", "balanced"):
            priority_matches = [option for option in alias_matches if priority_word in _normalize_text(option)]
            if priority_matches:
                return priority_matches
        return alias_matches
    phrase_matches = [option for option in allowed_options if _normalize_text(option) in normalized]
    if phrase_matches:
        return phrase_matches
    return alias_matches


def _decision_type(option: str) -> str:
    text = _normalize_text(option)
    if "delay" in text:
        return "delay"
    if "withdraw" in text:
        return "withdraw"
    if "observe" in text or "listen" in text or "stay still" in text:
        return "observe"
    if "hybrid" in text or "balanced" in text or "compromise" in text:
        return "compromise"
    if "confront" in text:
        return "confront"
    if text:
        return "act"
    return "unknown"


def _final_monologue_tail(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)
    if len(parts) < 2:
        return text
    return parts[1]


def normalize_decision(trace_payload: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    synthesis = _synthesis(trace_payload)
    decision = synthesis.get("decision") or {}
    allowed_options = list(scenario.get("allowed_options") or [])
    option_aliases = scenario.get("option_aliases") or {}
    raw_choice = str(decision.get("chosen_option") or "").strip()
    confidence = _as_float(decision.get("confidence")) or 0.0
    rationale = str(decision.get("rationale") or "").strip()
    final_monologue = str(synthesis.get("final_monologue") or "")
    candidates: list[tuple[str, str]] = []
    if raw_choice:
        candidates.append(("trace.synthesis_turn.decision.chosen_option", raw_choice))
    if final_monologue:
        candidates.append(("trace.synthesis_turn.final_monologue", final_monologue))
        tail = _final_monologue_tail(final_monologue)
        if tail != final_monologue:
            candidates.append(("trace.synthesis_turn.final_monologue.tail", tail))

    first_multi_source = ""
    for source, text in candidates:
        matches = _allowed_matches(text, allowed_options, option_aliases)
        if len(matches) == 1:
            chosen = matches[0]
            return {
                "chosen_option": chosen,
                "decision_type": _decision_type(chosen),
                "confidence": round(confidence, 3),
                "rationale": rationale,
                "valid": True,
                "problem": "",
                "source": source,
            }
        if len(matches) > 1 and not first_multi_source:
            first_multi_source = source

    if first_multi_source:
        return {
            "chosen_option": "",
            "decision_type": "unknown",
            "confidence": round(confidence, 3),
            "rationale": rationale,
            "valid": False,
            "problem": "Multiple allowed options matched; refusing prompt-fragment decision.",
            "source": first_multi_source,
        }
    return {
        "chosen_option": "",
        "decision_type": "unknown",
        "confidence": round(confidence, 3),
        "rationale": rationale,
        "valid": False,
        "problem": "No chosen option matched allowed options.",
        "source": candidates[-1][0] if candidates else "none",
    }


def summarize_stock_phrase_cases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_phrase: dict[str, dict[str, Any]] = {}
    worst_cases: list[dict[str, Any]] = []
    completed = [row for row in rows if not row.get("error")]
    for phrase in STOCK_PHRASES:
        by_phrase[phrase] = {
            "phrase": phrase,
            "count": 0,
            "case_ids": [],
            "scenarios": {},
            "profiles": {},
        }
    for row in completed:
        audit = row.get("evaluation", {}).get("rei_audit") or {}
        hits = Counter(audit.get("stock_phrase_hits") or {})
        total_hits = sum(hits.values())
        if total_hits:
            worst_cases.append(
                {
                    "case_id": f"{int(row['case_index']):03d}",
                    "scenario_id": row.get("scenario_id"),
                    "profile": row.get("profile"),
                    "count": total_hits,
                    "hits": dict(sorted(hits.items())),
                }
            )
        for phrase, count in hits.items():
            record = by_phrase.setdefault(
                phrase,
                {"phrase": phrase, "count": 0, "case_ids": [], "scenarios": {}, "profiles": {}},
            )
            record["count"] += count
            record["case_ids"].append(f"{int(row['case_index']):03d}")
            record["scenarios"] = dict(Counter(record["scenarios"]) + Counter({str(row.get("scenario_id")): count}))
            record["profiles"] = dict(Counter(record["profiles"]) + Counter({str(row.get("profile")): count}))
    total_hits = sum(record["count"] for record in by_phrase.values())
    completed_count = len(completed)
    density = round(total_hits / completed_count, 3) if completed_count else 0.0
    return {
        "phrases": [record for record in by_phrase.values() if record["count"]],
        "stock_phrase_density": density,
        "density_warning": density > 2.0,
        "worst_repetition_cases": sorted(worst_cases, key=lambda item: item["count"], reverse=True)[:5],
    }


def warning_codes(summary: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    artifact = summary.get("artifact_integrity") or {}
    weighted = summary.get("weighted_integrity") or {}
    decision = summary.get("decision_validity") or {}
    profile_top = summary.get("profile_top_match") or {}
    stock = summary.get("stock_phrase_diagnostics") or {}
    rei = summary.get("rei_thirteenth_character_audit") or {}
    functional = summary.get("functional_presence_summary") or {}
    quality = summary.get("weighted_compromise_quality_counts") or {}
    expected_jsonl_lines = artifact.get("expected_jsonl_lines", 0)

    if artifact and expected_jsonl_lines > 0 and not artifact.get("results_jsonl_exists"):
        warnings.append("RESULTS_JSONL_EMPTY")
    if artifact and artifact.get("results_jsonl_lines", 0) == 0 and expected_jsonl_lines > 0:
        warnings.append("RESULTS_JSONL_EMPTY")
    if artifact and not artifact.get("results_jsonl_complete"):
        warnings.append("RESULTS_JSONL_LINE_COUNT_MISMATCH")
    if weighted and not weighted.get("all_cases_have_three_contributions"):
        warnings.append("MISSING_WEIGHTED_CONTRIBUTIONS")
    if weighted and weighted.get("ranking_mismatch_count", 0):
        warnings.append("CONTRIBUTION_RANKING_MISMATCH")
    if weighted and weighted.get("tilt_mismatch_count", 0):
        warnings.append("TILT_RANKING_MISMATCH")
    if decision and decision.get("rate", 1.0) < 0.8:
        warnings.append("DECISION_EXTRACTION_LOW_VALIDITY")
    if profile_top.get("rate") == 1.0 and summary.get("average_missing_mind_count", 0) > 0:
        warnings.append("PROFILE_TOP_MATCH_MECHANICAL")
    if stock.get("stock_phrase_density", 0) > 2.0:
        warnings.append("STOCK_PHRASE_DENSITY_HIGH")
    if rei.get("arbitrary_tilt_warning_count", 0):
        warnings.append("REI_ARBITRARY_TILT")
    if summary.get("missing_final_monologue_count", 0):
        warnings.append("MISSING_FINAL_MONOLOGUE")
    if functional and functional.get("rate", 1.0) < 0.8:
        warnings.append("FUNCTIONAL_MIND_PRESENCE_LOW")
    if functional.get("role_name_only_warning_count", 0):
        warnings.append("ROLE_NAME_ONLY_PRESENCE")
    if functional.get("generic_role_listing_warning_count", 0):
        warnings.append("GENERIC_ROLE_LISTING")
    if functional.get("low_scenario_grounding_warning_count", 0):
        warnings.append("LOW_SCENARIO_GROUNDING")
    if quality.get("weak", 0):
        warnings.append("WEIGHTED_COMPROMISE_QUALITY_LOW")
    return warnings
