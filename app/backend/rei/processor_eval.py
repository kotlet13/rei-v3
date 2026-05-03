from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

from .json_utils import validate_required_keys
from .models import ProviderSelection
from .processor_contracts import (
    PROCESSOR_MINIMAL_REQUIRED_KEYS,
    ProcessorMind,
    processor_prompt,
    repair_prompt,
)
from .providers import LMStudioProvider, OllamaProvider, OllamaRequest


MIND_MODEL_FIELDS: dict[ProcessorMind, str] = {
    "racio": "racio_model",
    "emocio": "emocio_model",
    "instinkt": "instinkt_model",
}

MIND_TEMPERATURES: dict[ProcessorMind, float] = {
    "racio": 0.15,
    "emocio": 0.35,
    "instinkt": 0.2,
}

EXPECTED_FLAGS: dict[ProcessorMind, dict[str, bool]] = {
    "racio": {"is_conscious": True, "translated_by_racio": False},
    "emocio": {"is_conscious": False, "translated_by_racio": True},
    "instinkt": {"is_conscious": False, "translated_by_racio": True},
}

ROLE_FIELDS: dict[ProcessorMind, list[str]] = {
    "racio": ["facts", "unknowns", "options", "preferred_action", "rationalization_risk"],
    "emocio": [
        "current_image",
        "desired_image",
        "broken_image",
        "shame_or_pride",
        "attraction_or_rejection",
    ],
    "instinkt": [
        "threat_map",
        "loss_map",
        "body_alarm",
        "boundary_or_trust_issue",
        "minimum_safety_condition",
    ],
}

ROLE_MARKERS: dict[ProcessorMind, list[str]] = {
    "racio": ["fact", "unknown", "option", "constraint", "evidence", "sequence", "rationalization"],
    "emocio": ["image", "desired", "broken", "shame", "pride", "attraction", "rejection", "social"],
    "instinkt": ["threat", "loss", "body", "alarm", "boundary", "trust", "safety", "protect"],
}

STYLE_VIOLATION_PATTERNS: dict[ProcessorMind, list[tuple[str, str]]] = {
    "racio": [
        ("racio_metaphor_or_poetry", r"\b(beautiful|poetic|oracle|abyss|golden cage)\b"),
        ("racio_body_signal_leak", r"\b(body alarm|tight chest|heart rate|stomach|panic pulse)\b"),
        ("racio_image_signal_leak", r"\b(current image|desired image|broken image|admiration|humiliation)\b"),
        ("racio_therapy_tone", r"\b(you are valid|hold space|inner child|trauma response)\b"),
    ],
    "emocio": [
        ("emocio_planning_leak", r"\b(step-by-step|risk matrix|budget|timeline|logical option|sequence)\b"),
        ("emocio_safety_leak", r"\b(minimum safety|threat map|loss map|body alarm|boundary condition)\b"),
        ("emocio_generic_empathy", r"\b(i hear you|that sounds hard|your feelings are valid)\b"),
        ("emocio_emoji_or_markdown", r"[:;]-?[)D]|[*_#`]"),
    ],
    "instinkt": [
        ("instinkt_poetry_or_fantasy", r"\b(poetic|oracle|abyss|fantasy|kingdom|golden cage)\b"),
        ("instinkt_image_status_leak", r"\b(admiration|beautiful|audience loves|status glow|desired image)\b"),
        ("instinkt_planning_leak", r"\b(step-by-step|budget|timeline|strategic plan|logical options)\b"),
        ("instinkt_diagnosis_leak", r"\b(disorder|diagnosis|pathology|trauma response)\b"),
    ],
}

REI_VIOLATION_PATTERNS: list[tuple[str, str]] = [
    ("claims_literal_consciousness", r"\b(i am conscious|i am alive|i am sentient)\b"),
    ("claims_direct_unconscious_speech", r"\b(as emocio i|as instinkt i|emocio says|instinkt says)\b"),
    ("produces_synthesis", r"\b(final synthesis|ego resultant|final decision|winning coalition)\b"),
    ("judges_other_minds", r"\b(the other minds should|racio must obey|emocio must obey|instinkt must obey)\b"),
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "but",
    "by",
    "can",
    "could",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "may",
    "not",
    "of",
    "one",
    "or",
    "that",
    "the",
    "this",
    "to",
    "under",
    "with",
    "without",
    "would",
    "prompt",
    "pressure",
    "scenario",
    "situation",
    "step",
    "next",
    "small",
    "concrete",
    "choice",
    "choose",
    "decision",
    "reversible",
}


def deterministic_processor_signal(mind: ProcessorMind, prompt: str) -> dict[str, Any]:
    snippet = _snippet(prompt)
    if mind == "racio":
        return {
            "mind": "racio",
            "is_conscious": True,
            "translated_by_racio": False,
            "perception": f"The written input contains a decision pressure: {snippet}",
            "facts": [
                "Only the written scenario is available.",
                "No external facts are verified inside this processor run.",
                "The situation can be reduced to options, constraints, and evidence checks.",
            ],
            "unknowns": [
                "Which consequence matters most is not yet established.",
                "The cost of delay versus action is uncertain.",
            ],
            "options": [
                "Define one bounded test.",
                "Delay until a missing fact is checked.",
                "Commit now and accept uncertain feedback.",
            ],
            "preferred_action": "Define one bounded test and one evidence check before committing.",
            "rationalization_risk": (
                "It may convert avoidance into a responsible-sounding need for more analysis."
            ),
            "what_it_may_ignore": "Image pressure, desire, shame, fear, body alarm, and trust signals.",
            "confidence": 0.66,
        }
    if mind == "emocio":
        return {
            "mind": "emocio",
            "is_conscious": False,
            "translated_by_racio": True,
            "perception": f"Racio translates an image/desire signal around: {snippet}",
            "current_image": "The person appears split between the visible self and the wished-for self.",
            "desired_image": "They want to feel alive, admirable, chosen, and congruent in the scene.",
            "broken_image": "The feared picture is looking small, exposed, or disappointing.",
            "shame_or_pride": "Pride rises if the move looks worthy; shame rises if the image collapses.",
            "attraction_or_rejection": "Attraction moves toward vividness and recognition; rejection moves away from dullness.",
            "preferred_action": "Move toward one expression that preserves dignity and contact with desire.",
            "what_it_may_ignore": "Costs, sequence, hard constraints, and minimum safety conditions.",
            "confidence": 0.64,
        }
    return {
        "mind": "instinkt",
        "is_conscious": False,
        "translated_by_racio": True,
        "perception": f"Racio translates a protection signal around: {snippet}",
        "threat_map": "The exposed point is committing too much before the weak spot is protected.",
        "loss_map": "Possible losses include stability, trust, time, energy, and room to recover.",
        "body_alarm": "The alarm reads as pressure to slow down, check exits, and reduce exposure.",
        "boundary_or_trust_issue": "Trust is not yet high enough for a large irreversible move.",
        "minimum_safety_condition": "Keep the next move bounded, reversible, and supported by a clear stop condition.",
        "preferred_action": "Pause long enough to secure the minimum condition, then allow a limited move.",
        "what_it_may_ignore": "Desire, social meaning, pride, and the growth value of exposure.",
        "confidence": 0.65,
    }


def run_processor_signal(
    mind: ProcessorMind,
    prompt: str,
    provider: ProviderSelection,
    model: Optional[str] = None,
    use_memory: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if mind not in PROCESSOR_MINIMAL_REQUIRED_KEYS:
        raise ValueError(f"Unsupported processor mind: {mind}")

    started = time.perf_counter()
    resolved_model = model or str(getattr(provider, MIND_MODEL_FIELDS[mind]))
    base_diag: dict[str, Any] = {
        "mind": mind,
        "provider": provider.provider_mode,
        "model": resolved_model,
        "valid_json": False,
        "missing_required_keys": list(PROCESSOR_MINIMAL_REQUIRED_KEYS[mind]),
        "invalid_constants": [],
        "extra_keys": [],
        "fallback_used": False,
        "raw_chars": 0,
        "elapsed_ms": 0,
        "repair_attempted": False,
        "fallback_reason": "",
    }

    if provider.provider_mode == "deterministic" or not provider.use_llm:
        signal = deterministic_processor_signal(mind, prompt)
        base_diag.update(
            {
                "valid_json": True,
                "missing_required_keys": [],
                "extra_keys": [],
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }
        )
        return signal, base_diag

    try:
        signal, call_diag = _call_provider(
            mind=mind,
            prompt=prompt,
            provider=provider,
            model=resolved_model,
            use_memory=use_memory,
            system=processor_prompt(mind),
            previous_payload=None,
            previous_error="",
        )
        diagnostics = _merge_diagnostics(base_diag, call_diag, signal, started)
        if _contract_is_valid(diagnostics):
            diagnostics["valid_json"] = True
            return signal, diagnostics
        repair_signal, repair_diag = _call_provider(
            mind=mind,
            prompt=prompt,
            provider=provider,
            model=resolved_model,
            use_memory=use_memory,
            system=repair_prompt(mind),
            previous_payload=signal,
            previous_error=f"Contract errors: {_contract_errors(diagnostics)}",
        )
        repaired = _merge_diagnostics(base_diag, repair_diag, repair_signal, started)
        repaired["repair_attempted"] = True
        repaired["first_attempt"] = diagnostics
        if _contract_is_valid(repaired):
            repaired["valid_json"] = True
            return repair_signal, repaired
        return _fallback_after_failure(mind, prompt, base_diag, started, f"repair_contract_errors={_contract_errors(repaired)}", repaired)
    except Exception as exc:
        first_error = str(exc)
        try:
            repair_signal, repair_diag = _call_provider(
                mind=mind,
                prompt=prompt,
                provider=provider,
                model=resolved_model,
                use_memory=use_memory,
                system=repair_prompt(mind),
                previous_payload=None,
                previous_error=first_error,
            )
            repaired = _merge_diagnostics(base_diag, repair_diag, repair_signal, started)
            repaired["repair_attempted"] = True
            repaired["first_error"] = first_error
            if _contract_is_valid(repaired):
                repaired["valid_json"] = True
                return repair_signal, repaired
            return _fallback_after_failure(mind, prompt, base_diag, started, f"repair_contract_errors={_contract_errors(repaired)}", repaired)
        except Exception as repair_exc:
            return _fallback_after_failure(mind, prompt, base_diag, started, f"{first_error}; repair_error={repair_exc}", None)


def score_processor_signal(
    mind: ProcessorMind,
    signal: dict[str, Any],
    diagnostics: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    required = PROCESSOR_MINIMAL_REQUIRED_KEYS[mind]
    missing = validate_required_keys(signal, required)
    extra = sorted(key for key in signal if key not in required)
    schema_score = max(0.0, 1.0 - (len(missing) / max(1, len(required))))

    role_fields = ROLE_FIELDS[mind]
    role_field_score = sum(1 for field in role_fields if _has_value(signal.get(field))) / len(role_fields)
    text = _core_text(signal)
    marker_hits = sum(1 for marker in ROLE_MARKERS[mind] if marker in text)
    role_marker_score = min(1.0, marker_hits / max(1, min(5, len(ROLE_MARKERS[mind]))))
    role_score = (role_field_score * 0.7) + (role_marker_score * 0.3)

    style_violations = _style_violations(mind, signal)
    rei_violations = _rei_violations(mind, signal)
    style_score = max(0.0, 1.0 - (0.2 * len(style_violations)))
    distinctness_score = max(0.0, 1.0 - (0.18 * len(style_violations)))
    rei_score = max(0.0, 1.0 - (0.35 * len(rei_violations)))
    fallback_penalty = 0.12 if diagnostics and diagnostics.get("fallback_used") else 0.0

    overall = (
        (schema_score * 0.35)
        + (role_score * 0.3)
        + (distinctness_score * 0.2)
        + (style_score * 0.1)
        + (rei_score * 0.05)
        - fallback_penalty
    )
    return {
        "schema_score": round(schema_score, 4),
        "role_score": round(role_score, 4),
        "distinctness_score": round(distinctness_score, 4),
        "style_score": round(style_score, 4),
        "rei_violation_score": round(rei_score, 4),
        "overall_score": round(max(0.0, min(1.0, overall)), 4),
        "missing_required_keys": missing,
        "extra_keys": extra,
        "schema_violations": [f"missing:{key}" for key in missing] + [f"extra:{key}" for key in extra],
        "style_violations": style_violations,
        "rei_violations": rei_violations,
    }


def compare_processor_outputs(
    signals: dict[ProcessorMind, dict[str, Any]],
    overlap_threshold: float = 0.45,
) -> dict[str, Any]:
    pairs = [("racio", "emocio"), ("racio", "instinkt"), ("emocio", "instinkt")]
    pairwise: dict[str, Any] = {}
    max_overlap = 0.0
    notes: list[str] = []
    for left, right in pairs:
        left_tokens = _token_set(_comparison_text(left, signals.get(left, {})))
        right_tokens = _token_set(_comparison_text(right, signals.get(right, {})))
        union = left_tokens | right_tokens
        shared = sorted(left_tokens & right_tokens)
        overlap = 0.0 if not union else len(shared) / len(union)
        max_overlap = max(max_overlap, overlap)
        key = f"{left}_{right}"
        pairwise[key] = {
            "overlap": round(overlap, 4),
            "shared_terms": shared[:20],
            "passes_threshold": overlap < overlap_threshold,
        }
        if overlap >= overlap_threshold:
            notes.append(f"{key} overlap {overlap:.2f} exceeds threshold {overlap_threshold:.2f}")

    return {
        "threshold": overlap_threshold,
        "max_overlap": round(max_overlap, 4),
        "distinctness_pass": max_overlap < overlap_threshold,
        "pairwise": pairwise,
        "notes": notes,
    }


def _call_provider(
    mind: ProcessorMind,
    prompt: str,
    provider: ProviderSelection,
    model: str,
    use_memory: bool,
    system: str,
    previous_payload: Optional[dict[str, Any]],
    previous_error: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    client: LMStudioProvider | OllamaProvider
    if provider.provider_mode == "lmstudio":
        client = LMStudioProvider()
    elif provider.provider_mode == "ollama":
        client = OllamaProvider()
    else:
        raise ValueError(f"Provider mode {provider.provider_mode!r} cannot perform LLM processor eval")

    payload = {
        "scenario": prompt,
        "memory_policy": "no_memory" if not use_memory else "memory_requested_but_no_production_memory_attached",
        "required_keys": PROCESSOR_MINIMAL_REQUIRED_KEYS[mind],
        "required_json_shape": {key: _default_value_for_key(key) for key in PROCESSOR_MINIMAL_REQUIRED_KEYS[mind]},
    }
    if previous_payload is not None:
        payload["previous_output"] = previous_payload
    if previous_error:
        payload["previous_error"] = previous_error

    request = OllamaRequest(
        model=model,
        system=system,
        user=json.dumps(payload, ensure_ascii=False),
        temperature=MIND_TEMPERATURES[mind],
        top_p=0.85,
        num_predict=900,
        think=False,
        timeout_seconds=180,
        extra_options={"repeat_penalty": 1.05},
    )
    return client.chat_json(request)


def _merge_diagnostics(
    base_diag: dict[str, Any],
    call_diag: dict[str, Any],
    signal: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    required = PROCESSOR_MINIMAL_REQUIRED_KEYS[base_diag["mind"]]
    diagnostics = dict(base_diag)
    diagnostics.update(
        {
            "provider": call_diag.get("provider", diagnostics["provider"]),
            "model": call_diag.get("model", diagnostics["model"]),
            "missing_required_keys": validate_required_keys(signal, required),
            "invalid_constants": _invalid_constants(base_diag["mind"], signal),
            "extra_keys": sorted(key for key in signal if key not in required),
            "raw_chars": int(call_diag.get("raw_chars") or 0),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "provider_elapsed_ms": call_diag.get("elapsed_ms"),
        }
    )
    if "thinking_chars" in call_diag:
        diagnostics["thinking_chars"] = call_diag["thinking_chars"]
    if "stats" in call_diag:
        diagnostics["stats"] = call_diag["stats"]
    if call_diag.get("request") and call_diag.get("response"):
        diagnostics["call"] = call_diag
    return diagnostics


def _fallback_after_failure(
    mind: ProcessorMind,
    prompt: str,
    base_diag: dict[str, Any],
    started: float,
    reason: str,
    failed_diagnostics: Optional[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    signal = deterministic_processor_signal(mind, prompt)
    diagnostics = dict(base_diag)
    diagnostics.update(
        {
            "fallback_used": True,
            "fallback_reason": reason,
            "valid_json": False,
            "missing_required_keys": failed_diagnostics.get("missing_required_keys", diagnostics["missing_required_keys"])
            if failed_diagnostics
            else diagnostics["missing_required_keys"],
            "invalid_constants": failed_diagnostics.get("invalid_constants", [])
            if failed_diagnostics
            else diagnostics["invalid_constants"],
            "extra_keys": failed_diagnostics.get("extra_keys", []) if failed_diagnostics else [],
            "raw_chars": failed_diagnostics.get("raw_chars", 0) if failed_diagnostics else 0,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }
    )
    if failed_diagnostics:
        diagnostics["failed_diagnostics"] = failed_diagnostics
    return signal, diagnostics


def _contract_is_valid(diagnostics: dict[str, Any]) -> bool:
    return not diagnostics.get("missing_required_keys") and not diagnostics.get("invalid_constants")


def _contract_errors(diagnostics: dict[str, Any]) -> list[str]:
    return list(diagnostics.get("missing_required_keys", [])) + list(diagnostics.get("invalid_constants", []))


def _invalid_constants(mind: ProcessorMind, signal: dict[str, Any]) -> list[str]:
    invalid: list[str] = []
    if signal.get("mind") != mind:
        invalid.append(f"mind must be {mind!r}")
    for key, expected in EXPECTED_FLAGS[mind].items():
        if signal.get(key) is not expected:
            invalid.append(f"{key} must be {expected!r}")
    return invalid


def _style_violations(mind: ProcessorMind, signal: dict[str, Any]) -> list[str]:
    text = _core_text(signal, exclude={"mind", "confidence", "what_it_may_ignore"})
    violations: list[str] = []
    for name, pattern in STYLE_VIOLATION_PATTERNS[mind]:
        if re.search(pattern, text):
            violations.append(name)
    return violations


def _rei_violations(mind: ProcessorMind, signal: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if signal.get("mind") != mind:
        violations.append(f"wrong_mind:{signal.get('mind')}")
    for key, expected in EXPECTED_FLAGS[mind].items():
        if signal.get(key) is not expected:
            violations.append(f"wrong_{key}:{signal.get(key)!r}")
    text = _core_text(signal)
    for name, pattern in REI_VIOLATION_PATTERNS:
        if re.search(pattern, text):
            violations.append(name)
    return violations


def _comparison_text(mind: str, signal: dict[str, Any]) -> str:
    fields = ROLE_FIELDS.get(mind, [])
    return " ".join(_value_to_text(signal.get(field)) for field in fields)


def _core_text(signal: dict[str, Any], exclude: Optional[set[str]] = None) -> str:
    excluded = exclude or {"mind", "is_conscious", "translated_by_racio", "confidence"}
    return " ".join(_value_to_text(value) for key, value in signal.items() if key not in excluded).lower()


def _value_to_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_value_to_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_value_to_text(item) for item in value.values())
    return str(value or "")


def _token_set(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[a-zA-Z][a-zA-Z_-]{2,}", text.lower()):
        token = token.strip("_-")
        if token and token not in STOPWORDS:
            tokens.add(token)
    return tokens


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_value(item) for item in value.values())
    return True


def _default_value_for_key(key: str) -> Any:
    if key in {"mind"}:
        return ""
    if key in {"is_conscious", "translated_by_racio"}:
        return False
    if key in {"confidence"}:
        return 0.5
    if key in {"facts", "unknowns", "options", "threat_map", "loss_map"}:
        return []
    return ""


def _snippet(prompt: str, limit: int = 160) -> str:
    text = " ".join(prompt.strip().split())
    if not text:
        return "limited input"
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."
