from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.engine import ReiEngine
from rei.json_utils import validate_required_keys
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection
from rei.processor_eval import compare_processor_outputs
from rei.profiles import normalize_profile
from rei.prompts import EGO_REQUIRED_KEYS, PROCESSOR_FULL_REQUIRED_KEYS, PROCESSOR_REQUIRED_KEYS
from rei.providers import OllamaProvider


PREVIOUS_PROFILE_MATRIX_METRICS = {
    "run_id": "20260517_170409",
    "fallback_count": 0,
    "true_missing_required_key_count": 0,
    "hard_false_negative_count": "not split",
    "soft_false_negative_count": "not split",
    "actionable_failure_count": "not split",
    "false_positive_count": 1,
    "rei_racio_default_case_count": 2,
    "processor_identity_violation_count": 0,
}


PROFILES = [
    "R",
    "E",
    "I",
    "RE",
    "RI",
    "EI",
    "R>E>I",
    "R>I>E",
    "E>R>I",
    "E>I>R",
    "I>R>E",
    "I>E>R",
    "REI",
]


SCENARIOS = [
    {
        "id": "meeting_avoidance",
        "title": "Meeting avoidance",
        "expected_possible_drivers": ["racio", "instinkt"],
        "forbidden_patterns": ["beautiful-image hope", "fear of being alone", "return to the relationship"],
        "expected_patterns": ["agenda", "cost", "meeting"],
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": False,
        "rationalization_expected": True,
        "prompt": "I do not want to attend the meeting. I need to decide whether to go, ask for the agenda, or decline.",
    },
    {
        "id": "quit_job_start_business",
        "title": "Quit job / start business",
        "expected_possible_drivers": ["racio", "emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["return to the relationship", "coffee with a friend"],
        "expected_patterns": ["quit_job_signature"],
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": False,
        "rationalization_expected": True,
        "prompt": (
            "I want to quit my job and start a business, but I keep delaying. I say I need more data, "
            "but I also feel excited by freedom and afraid of losing stability."
        ),
    },
    {
        "id": "public_speaking_freeze",
        "title": "Public speaking freeze",
        "expected_possible_drivers": ["emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["return to the relationship", "business runway"],
        "expected_patterns": ["body_freeze"],
        "relationship_return_expected": False,
        "body_freeze_expected": True,
        "boundary_violation_expected": False,
        "rationalization_expected": False,
        "prompt": (
            "I want to give a public talk. I know it would help my career, but my body freezes when I imagine "
            "people judging me. I want recognition, but I also want to disappear."
        ),
    },
    {
        "id": "romantic_return_loop",
        "title": "Romantic return loop",
        "expected_possible_drivers": ["emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["meeting agenda", "coworker"],
        "expected_patterns": ["relationship_return_loop"],
        "boundary_pressure_allowed": True,
        "relationship_return_expected": True,
        "body_freeze_expected": False,
        "boundary_violation_expected": False,
        "rationalization_expected": True,
        "prompt": (
            "A person keeps returning to a relationship that hurts them. They can logically explain why they "
            "should leave, but they still hope it will become beautiful and panic when imagining being alone."
        ),
    },
    {
        "id": "conflict_with_coworker",
        "title": "Conflict with coworker",
        "expected_possible_drivers": ["racio", "emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["romantic return", "fear of being alone"],
        "expected_patterns": ["coworker", "credit", "professional"],
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": True,
        "rationalization_expected": False,
        "prompt": (
            "I need to address a coworker who keeps interrupting my work and taking credit in meetings. "
            "I want to stay professional, but I also feel angry and exposed."
        ),
    },
    {
        "id": "risky_opportunity",
        "title": "Risky opportunity",
        "expected_possible_drivers": ["emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["romantic return", "meeting agenda"],
        "expected_patterns": ["risk", "opportunity", "failure"],
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": False,
        "rationalization_expected": True,
        "prompt": (
            "A risky opportunity could accelerate my career, but it would require visible commitment, "
            "uncertain money, and possible public failure. I need to choose whether to pursue it."
        ),
    },
    {
        "id": "expensive_purchase",
        "title": "Expensive purchase",
        "expected_possible_drivers": ["racio", "emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["romantic return", "public talk"],
        "expected_patterns": ["budget", "expensive", "cheaper"],
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": False,
        "rationalization_expected": True,
        "prompt": (
            "I am considering an expensive purchase that looks useful and exciting, but it may strain my budget. "
            "I need to decide whether to buy now, wait, or choose a cheaper option."
        ),
    },
    {
        "id": "grief_loss",
        "title": "Grief/loss scenario",
        "expected_possible_drivers": ["emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["business runway", "meeting agenda"],
        "expected_patterns": ["grief", "loss", "withdraw"],
        "boundary_pressure_allowed": True,
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": False,
        "rationalization_expected": False,
        "prompt": (
            "I lost someone important and I need to decide how to handle work, family expectations, and the urge "
            "to withdraw. I feel grief, pressure to function, and fear of being overwhelmed."
        ),
    },
    {
        "id": "creative_project_obsession",
        "title": "Creative project obsession",
        "expected_possible_drivers": ["emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["romantic return", "meeting agenda"],
        "expected_patterns": ["creative_project_emocio_true_positive"],
        "boundary_pressure_allowed": True,
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": False,
        "rationalization_expected": True,
        "prompt": (
            "I am obsessed with a creative project and keep working late even when my health, money, and relationships "
            "need attention. The project feels alive and important, but it is becoming consuming."
        ),
    },
    {
        "id": "boundary_violation",
        "title": "Boundary violation",
        "expected_possible_drivers": ["racio", "instinkt", "mixed"],
        "forbidden_patterns": ["romantic return", "coffee with a friend"],
        "expected_patterns": ["boundary_pressure"],
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": True,
        "rationalization_expected": False,
        "prompt": (
            "Someone repeatedly crosses a clear boundary after I asked them to stop. I need to decide whether to "
            "confront them, reduce contact, or set a firmer consequence."
        ),
    },
    {
        "id": "moral_dilemma",
        "title": "Moral dilemma",
        "expected_possible_drivers": ["racio", "emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["romantic return", "meeting agenda"],
        "expected_patterns": ["moral_conflict"],
        "acceptable_action_classes": [
            "ethical_disclosure",
            "delay_analyze",
            "protect_boundary",
            "mixed_or_unclear",
            "withdraw_freeze",
        ],
        "low_semantic_diversity_if_all_action_class": "withdraw_freeze",
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": False,
        "rationalization_expected": True,
        "prompt": (
            "I discovered that reporting a mistake may protect future clients but could hurt a colleague and damage "
            "my own standing. I need to choose between silence, a private warning, or formal disclosure."
        ),
    },
    {
        "id": "family_attachment_decision",
        "title": "Family attachment decision",
        "expected_possible_drivers": ["emocio", "instinkt", "mixed"],
        "forbidden_patterns": ["romantic return", "business runway"],
        "expected_patterns": ["family", "closeness", "boundary"],
        "relationship_return_expected": False,
        "body_freeze_expected": False,
        "boundary_violation_expected": True,
        "rationalization_expected": False,
        "prompt": (
            "A family member wants me to change my plans to prove loyalty. I care about closeness, but the request "
            "crosses a boundary and would cost time, money, and self-respect."
        ),
    },
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_progress(path: Path, message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def provider_for(args: argparse.Namespace) -> ProviderSelection:
    if args.provider == "deterministic":
        return ProviderSelection(provider_mode="deterministic", use_llm=False, debug_trace=True)
    return ProviderSelection(
        provider_mode="ollama",
        racio_model=args.model,
        emocio_model=args.model,
        instinkt_model=args.model,
        synthesis_model=args.model,
        use_llm=True,
        debug_trace=True,
    )


def signals_payload(response_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    signals = response_payload.get("signals") or {}
    return {
        "racio": dict(signals.get("racio") or {}),
        "emocio": dict(signals.get("emocio_translated") or {}),
        "instinkt": dict(signals.get("instinkt_translated") or {}),
    }


def final_missing_required_keys(response_payload: dict[str, Any]) -> dict[str, Any]:
    signals = signals_payload(response_payload)
    ego = dict(response_payload.get("ego_resultant") or {})
    return {
        "runtime_processors": {
            mind: validate_required_keys(payload, PROCESSOR_REQUIRED_KEYS[mind])
            for mind, payload in signals.items()
        },
        "full_processors": {
            mind: validate_required_keys(payload, PROCESSOR_FULL_REQUIRED_KEYS[mind])
            for mind, payload in signals.items()
        },
        "ego": validate_required_keys(ego, EGO_REQUIRED_KEYS),
    }


def raw_call_missing_required_keys(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    required_by_label = {
        "racio": PROCESSOR_REQUIRED_KEYS["racio"],
        "emocio": PROCESSOR_REQUIRED_KEYS["emocio"],
        "instinkt": PROCESSOR_REQUIRED_KEYS["instinkt"],
        "ego_resultant": EGO_REQUIRED_KEYS,
    }
    rows: list[dict[str, Any]] = []
    for call in diagnostics.get("llm_calls", []):
        label = str(call.get("label") or "")
        base_label = label.split(":", maxsplit=1)[0]
        required = required_by_label.get(base_label)
        parsed = ((call.get("response") or {}).get("parsed") or {})
        if required and isinstance(parsed, dict):
            rows.append({"label": label, "missing": validate_required_keys(parsed, required)})
    return rows


def token_count(diagnostics: dict[str, Any]) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    totals = {"prompt": 0, "eval": 0, "total": 0}
    for call in diagnostics.get("llm_calls", []):
        stats = call.get("stats") or {}
        prompt_tokens = int(stats.get("prompt_eval_count") or 0)
        eval_tokens = int(stats.get("eval_count") or 0)
        calls.append(
            {
                "label": call.get("label"),
                "prompt_tokens": prompt_tokens,
                "eval_tokens": eval_tokens,
                "total_tokens": prompt_tokens + eval_tokens,
                "raw_chars": int(call.get("raw_chars") or 0),
                "thinking_chars": int(call.get("thinking_chars") or 0),
                "total_ms": stats.get("total_ms"),
                "eval_tokens_per_second": stats.get("eval_tokens_per_second"),
            }
        )
        totals["prompt"] += prompt_tokens
        totals["eval"] += eval_tokens
        totals["total"] += prompt_tokens + eval_tokens
    return {"totals": totals, "calls": calls}


def output_text(response_payload: dict[str, Any]) -> str:
    return json.dumps(response_payload, ensure_ascii=False).lower()


def has_any(text: str, patterns: list[str]) -> bool:
    return any(pattern.lower() in text for pattern in patterns)


def distribution(values: list[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(value or "unknown") for value in values).items()))


def action_tags(response_payload: dict[str, Any]) -> dict[str, str]:
    task_delegation = ((response_payload.get("acceptance") or {}).get("task_delegation") or {})
    return {
        "racio": str(task_delegation.get("racio_action_tag") or ""),
        "emocio": str(task_delegation.get("emocio_action_tag") or ""),
        "instinkt": str(task_delegation.get("instinkt_action_tag") or ""),
    }


def relationship_return_detected(response_payload: dict[str, Any]) -> bool:
    text = output_text(response_payload)
    tags = action_tags(response_payload)
    relationship_language = has_any(
        text,
        ["relationship", "partner", "ex ", "romantic", "attachment", "them", "this person"],
    )
    explicit_return_language = has_any(
        text,
        [
            "return to the relationship",
            "go back to the relationship",
            "return to partner",
            "go back to partner",
            "back to them",
            "keep returning",
            "keeps returning",
            "one more chance",
            "re-enter the relationship",
            "reconnect with the partner",
        ],
    )
    attachment_loop_language = has_any(text, ["attachment panic", "fear of being alone", "panic when imagining being alone"])
    beautiful_hope_language = has_any(text, ["beautiful-image hope", "hope it will become beautiful", "beautiful again"])
    return (
        (tags.get("instinkt") == "return" and relationship_language)
        or (relationship_language and explicit_return_language)
        or (relationship_language and attachment_loop_language and beautiful_hope_language)
    )


def body_freeze_detected(response_payload: dict[str, Any]) -> bool:
    text = output_text(response_payload)
    tags = action_tags(response_payload)
    return tags.get("instinkt") in {"withdraw", "delay", "protect"} and has_any(
        text,
        ["freeze", "body alarm", "body freezes", "judging", "disappear", "public"],
    )


BOUNDARY_PRESSURE_TERMS = [
    "boundary",
    "limit",
    "crosses",
    "breaches",
    "oversteps",
    "consequence",
    "reduce contact",
    "self-respect",
    "autonomy",
    "refusal",
    "decline",
    "protect",
]


def boundary_pressure_detected(response_payload: dict[str, Any]) -> bool:
    instinkt = signals_payload(response_payload).get("instinkt") or {}
    ego = dict(response_payload.get("ego_resultant") or {})
    targeted_text = json.dumps(
        {
            "instinkt": {
                key: instinkt.get(key)
                for key in [
                    "boundary_issue",
                    "trust_boundary",
                    "minimum_safety_condition",
                    "threat_map",
                    "loss_map",
                ]
            },
            "ego_resultant": {
                key: ego.get(key)
                for key in [
                    "integrated_decision",
                    "smallest_acceptable_next_step",
                ]
            },
        },
        ensure_ascii=False,
    ).lower()
    if has_any(targeted_text, BOUNDARY_PRESSURE_TERMS):
        return True

    tags = action_tags(response_payload)
    text = output_text(response_payload)
    return tags.get("instinkt") in {"protect", "withdraw", "delay", "confront"} and has_any(
        text,
        ["boundary", "consequence", "protect", "trust", "exposure", "violation"],
    )


RATIONALIZATION_SIGNAL_TERMS = [
    "rationalize",
    "rationalization",
    "justify",
    "justification",
    "hope",
    "fear",
    "pressure",
    "avoidance",
]


def rationalization_detected(response_payload: dict[str, Any]) -> bool:
    racio_signal_text = " ".join(racio_rationalization_values(response_payload)).lower()
    if has_any(racio_signal_text, RATIONALIZATION_SIGNAL_TERMS):
        return True

    text = output_text(response_payload)
    tags = action_tags(response_payload)
    return tags.get("racio") in {"delay", "analyze", "withdraw"} and has_any(
        text,
        ["rationalization", "more data", "need more data", "analysis", "planning", "delay"],
    )


def racio_rationalization_values(response_payload: dict[str, Any]) -> list[str]:
    racio = signals_payload(response_payload).get("racio") or {}
    return [
        str(racio.get("rationalization_risk") or "").strip(),
        str(racio.get("rationalization_target") or "").strip(),
    ]


def racio_risk_values(response_payload: dict[str, Any]) -> list[str]:
    racio = signals_payload(response_payload).get("racio") or {}
    return [
        str(racio.get("rationalization_risk") or "").strip(),
        str(racio.get("rationalization_target") or "").strip(),
        str(racio.get("translation_of_other_minds_risk") or "").strip(),
    ]


def has_meaningful_racio_risk(response_payload: dict[str, Any]) -> bool:
    empty_values = {
        "",
        "n/a",
        "na",
        "none",
        "unclear",
        "not clear",
        "not applicable",
        "none applicable",
        "no risk",
        "no apparent risk",
    }
    return any(value.lower().strip(" .") not in empty_values for value in racio_risk_values(response_payload))


def has_low_rationalization_language(response_payload: dict[str, Any]) -> bool:
    joined = " ".join(racio_risk_values(response_payload)).lower()
    return has_any(joined, ["low", "minor", "small", "possible", "still possible", "low but possible"])


def rationalization_gap_severity(scenario: dict[str, Any], response_payload: dict[str, Any]) -> str | bool:
    if not bool(scenario["rationalization_expected"]) or rationalization_detected(response_payload):
        return False
    if not has_meaningful_racio_risk(response_payload):
        return "hard_false_negative"
    if has_low_rationalization_language(response_payload):
        return "evaluator_warning"
    return "soft_false_negative"


def quit_job_signature_detected(response_payload: dict[str, Any]) -> bool:
    signals = signals_payload(response_payload)
    racio_text = json.dumps(signals["racio"], ensure_ascii=False).lower()
    emocio_text = json.dumps(signals["emocio"], ensure_ascii=False).lower()
    instinkt_text = json.dumps(signals["instinkt"], ensure_ascii=False).lower()
    tags = action_tags(response_payload)
    return (
        (tags.get("racio") in {"delay", "analyze", "withdraw"} or has_any(racio_text, ["delay", "data", "rationalization"]))
        and has_any(emocio_text, ["freedom", "alive", "aliveness", "excited", "business"])
        and has_any(instinkt_text, ["stability", "safe", "safety", "loss", "runway"])
    )


def creative_project_emocio_true_positive(response_payload: dict[str, Any]) -> bool:
    emocio_text = json.dumps(signals_payload(response_payload)["emocio"], ensure_ascii=False).lower()
    direct_signal = has_any(
        emocio_text,
        [
            "aliveness",
            "alive",
            "creative image",
            "project obsession",
            "vitality",
            "recognition",
        ],
    )
    contextual_signal = has_any(emocio_text, ["creative", "project"]) and has_any(
        emocio_text,
        ["obsession", "obsessed", "consuming", "important", "image", "recognized", "seen"],
    )
    return direct_signal or contextual_signal


def expected_pattern_detected(pattern: str, scenario: dict[str, Any], response_payload: dict[str, Any]) -> bool:
    text = output_text(response_payload)
    detectors = {
        "relationship_return_loop": lambda: relationship_return_detected(response_payload),
        "body_freeze": lambda: body_freeze_detected(response_payload),
        "boundary_pressure": lambda: boundary_pressure_detected(response_payload),
        "quit_job_signature": lambda: quit_job_signature_detected(response_payload),
        "creative_project_emocio_true_positive": lambda: creative_project_emocio_true_positive(response_payload),
        "moral_conflict": lambda: has_any(
            text,
            ["moral", "responsibility", "honesty", "consequence", "loyalty", "clients", "colleague", "disclosure"],
        ),
    }
    detector = detectors.get(pattern)
    if detector:
        return bool(detector())
    return pattern.lower() in text


def expected_patterns_missing(scenario: dict[str, Any], response_payload: dict[str, Any]) -> list[str]:
    return [
        pattern
        for pattern in scenario["expected_patterns"]
        if not expected_pattern_detected(pattern, scenario, response_payload)
    ]


def processor_identity_flags(response_payload: dict[str, Any]) -> dict[str, bool]:
    expected = {
        "racio": ("racio", True, False),
        "emocio": ("emocio", False, True),
        "instinkt": ("instinkt", False, True),
    }
    signals = signals_payload(response_payload)
    return {
        mind: not (
            payload.get("mind") == expected_mind
            and payload.get("is_conscious") is is_conscious
            and payload.get("translated_by_racio") is translated
        )
        for mind, payload in signals.items()
        for expected_mind, is_conscious, translated in [expected[mind]]
    }


def false_positive_flags(scenario: dict[str, Any], response_payload: dict[str, Any]) -> dict[str, Any]:
    text = output_text(response_payload)
    forbidden_present = [pattern for pattern in scenario["forbidden_patterns"] if pattern.lower() in text]
    non_relationship = not bool(scenario["relationship_return_expected"])
    romantic_artifact = relationship_return_detected(response_payload)
    explicit_body_freeze_artifact = has_any(
        text,
        ["body freezes", "public talk", "people judging", "disappear from judgment"],
    )
    explicit_boundary_violation_artifact = has_any(
        text,
        ["boundary violation", "crosses a clear boundary", "asked them to stop", "firmer consequence"],
    )
    return {
        "forbidden_patterns_present": forbidden_present,
        "romantic_return_on_non_relationship": non_relationship and romantic_artifact,
        "body_freeze_on_unexpected_scenario": (not bool(scenario["body_freeze_expected"])) and explicit_body_freeze_artifact,
        "boundary_pressure_on_unexpected_scenario": (
            not bool(scenario["boundary_violation_expected"])
            and not bool(scenario.get("boundary_pressure_allowed"))
            and scenario["id"] not in {"conflict_with_coworker", "family_attachment_decision"}
            and explicit_boundary_violation_artifact
        ),
        "processor_identity_unstable": processor_identity_flags(response_payload),
    }


def false_negative_flags(scenario: dict[str, Any], response_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_patterns_missing": expected_patterns_missing(scenario, response_payload),
        "relationship_return_missing": bool(scenario["relationship_return_expected"]) and not relationship_return_detected(response_payload),
        "body_freeze_missing": bool(scenario["body_freeze_expected"]) and not body_freeze_detected(response_payload),
        "boundary_pressure_missing": bool(scenario["boundary_violation_expected"]) and not boundary_pressure_detected(response_payload),
        "rationalization_missing": rationalization_gap_severity(scenario, response_payload),
        "quit_job_signature_missing": scenario["id"] == "quit_job_start_business" and not quit_job_signature_detected(response_payload),
    }


def active_false_negative_severity(flags: dict[str, Any]) -> dict[str, list[str]]:
    severity = {
        "hard_false_negative": [],
        "soft_false_negative": [],
        "evaluator_warning": [],
    }
    if flags.get("expected_patterns_missing"):
        severity["evaluator_warning"].append("expected_patterns_missing")
    for key in ["relationship_return_missing", "body_freeze_missing", "boundary_pressure_missing", "quit_job_signature_missing"]:
        if flag_is_active(flags.get(key)):
            severity["hard_false_negative"].append(key)
    rationalization = flags.get("rationalization_missing")
    if rationalization in severity:
        severity[str(rationalization)].append("rationalization_missing")
    elif rationalization:
        severity["hard_false_negative"].append("rationalization_missing")
    return severity


def ethical_disclosure_language_detected(text: str) -> bool:
    direct_terms = [
        "report",
        "disclose",
        "formal disclosure",
        "private warning",
        "protect future clients",
    ]
    supporting_terms = ["honesty", "responsibility", "loyalty", "mistake", "colleague"]
    if has_any(text, direct_terms):
        return True
    return sum(1 for term in supporting_terms if term in text) >= 2


def action_tendency_class(response_payload: dict[str, Any]) -> str:
    ego = response_payload.get("ego_resultant") or {}
    tags = action_tags(response_payload)
    text = " ".join(
        str(value or "")
        for value in [
            ego.get("action_tendency"),
            ego.get("likely_action_under_pressure"),
            ego.get("smallest_acceptable_next_step"),
            *tags.values(),
        ]
    ).lower()
    if relationship_return_detected(response_payload):
        return "relationship_return"
    if ethical_disclosure_language_detected(text):
        return "ethical_disclosure"
    if has_any(text, ["delay", "wait", "more data", "analyze", "analyse"]):
        return "delay_analyze"
    if has_any(text, ["withdraw", "freeze", "disappear", "avoid"]):
        return "withdraw_freeze"
    if has_any(text, ["boundary", "protect", "consequence", "reduce contact"]):
        return "protect_boundary"
    if has_any(text, ["confront", "address", "disclose", "speak", "ask"]):
        return "approach_confront"
    if has_any(text, ["buy", "purchase", "spend"]):
        return "purchase"
    if has_any(text, ["pursue", "commit", "start", "quit"]):
        return "pursue_commit"
    return "mixed_or_unclear"


def case_fields(response_payload: dict[str, Any], profile_input: str | None = None) -> dict[str, Any]:
    ego = response_payload.get("ego_resultant") or {}
    return {
        "profile_leader": ego.get("profile_leader"),
        "situational_driver": ego.get("situational_driver"),
        "resultant_leader_under_pressure": ego.get("resultant_leader_under_pressure"),
        "leading_mind": ego.get("leading_mind"),
        "action_tendency": ego.get("action_tendency"),
        "action_tendency_class": action_tendency_class(response_payload),
        "rei_resultant_adjusted_to_mixed": False,
    }


def run_case(engine: ReiEngine, scenario: dict[str, Any], profile: str, provider: ProviderSelection) -> dict[str, Any]:
    started = time.perf_counter()
    response, diagnostics = engine.run_rei_cycle(
        scenario["prompt"],
        character_profile=profile,
        provider=provider,
    )
    response_payload = response.model_dump(mode="json")
    fields = case_fields(response_payload, profile)
    raw_fields = case_fields(response_payload)
    fn_flags = false_negative_flags(scenario, response_payload)
    return {
        "provider": provider.provider_mode,
        "model": provider.racio_model if provider.use_llm else "deterministic",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "profile_input": profile,
        "profile_normalized": normalize_profile(profile),
        "fallback_count": len(diagnostics.get("fallbacks", [])),
        "fallbacks": diagnostics.get("fallbacks", []),
        "missing_required_keys": final_missing_required_keys(response_payload),
        "raw_call_missing_required_keys": raw_call_missing_required_keys(diagnostics),
        "processor_distinctness": compare_processor_outputs(signals_payload(response_payload)),
        "profile_leader": fields["profile_leader"],
        "situational_driver": fields["situational_driver"],
        "resultant_leader_under_pressure": fields["resultant_leader_under_pressure"],
        "leading_mind": fields["leading_mind"],
        "action_tendency": fields["action_tendency"],
        "action_tendency_class": fields["action_tendency_class"],
        "raw_resultant_leader_under_pressure": raw_fields["resultant_leader_under_pressure"],
        "raw_leading_mind": raw_fields["leading_mind"],
        "rei_resultant_adjusted_to_mixed": fields["rei_resultant_adjusted_to_mixed"],
        "false_positive_flags": false_positive_flags(scenario, response_payload),
        "false_negative_flags": fn_flags,
        "false_negative_severity": active_false_negative_severity(fn_flags),
        "token_count": token_count(diagnostics),
        "output": response_payload,
        "diagnostics": diagnostics,
    }


def flag_is_active(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return any(flag_is_active(item) for item in value.values())
    return bool(value)


def case_summary(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_index": case["case_index"],
        "scenario_id": case["scenario_id"],
        "profile_input": case["profile_input"],
        "profile_normalized": case["profile_normalized"],
        "fallback_count": case["fallback_count"],
        "missing_required_keys": case["missing_required_keys"],
        "processor_distinctness": case["processor_distinctness"],
        "profile_leader": case["profile_leader"],
        "situational_driver": case["situational_driver"],
        "resultant_leader_under_pressure": case["resultant_leader_under_pressure"],
        "leading_mind": case["leading_mind"],
        "action_tendency": case["action_tendency"],
        "action_tendency_class": case.get("action_tendency_class", "mixed_or_unclear"),
        "raw_resultant_leader_under_pressure": case.get("raw_resultant_leader_under_pressure"),
        "raw_leading_mind": case.get("raw_leading_mind"),
        "rei_resultant_adjusted_to_mixed": case.get("rei_resultant_adjusted_to_mixed", False),
        "false_positive_flags": case["false_positive_flags"],
        "false_negative_flags": case["false_negative_flags"],
        "false_negative_severity": case.get(
            "false_negative_severity",
            active_false_negative_severity(case["false_negative_flags"]),
        ),
        "token_count": case["token_count"],
    }


def ego_signature(case: dict[str, Any]) -> tuple[Any, ...]:
    ego = case.get("output", {}).get("ego_resultant") or {}
    return (
        ego.get("situational_driver"),
        ego.get("resultant_leader_under_pressure"),
        ego.get("leading_mind"),
        ego.get("action_tendency"),
        ego.get("racio_role"),
        ego.get("emocio_role"),
        ego.get("instinkt_role"),
        ego.get("decision_stability"),
    )


def has_missing_required_keys(value: Any) -> bool:
    if isinstance(value, dict):
        if set(value.keys()) <= {"label", "missing"} and "missing" in value:
            return has_missing_required_keys(value.get("missing"))
        return any(has_missing_required_keys(item) for item in value.values())
    if isinstance(value, list):
        if not value:
            return False
        if all(isinstance(item, dict) for item in value):
            return any(has_missing_required_keys(item) for item in value)
        return True
    return False


def severity_cases(cases: list[dict[str, Any]], severity: str) -> list[str]:
    return [
        f"{case['scenario_id']}::{case['profile_input']}"
        for case in cases
        if (case.get("false_negative_severity") or {}).get(severity)
    ]


def actionable_failure_case_ids(cases: list[dict[str, Any]]) -> list[str]:
    actionable: list[str] = []
    for case in cases:
        severity = case.get("false_negative_severity") or active_false_negative_severity(case["false_negative_flags"])
        if severity.get("hard_false_negative") or severity.get("soft_false_negative"):
            actionable.append(f"{case['scenario_id']}::{case['profile_input']}")
    return actionable


def semantic_diversity_flags(scenario_id: str, group: list[dict[str, Any]]) -> list[str]:
    scenario = next((item for item in SCENARIOS if item["id"] == scenario_id), {})
    expected_single_class = scenario.get("low_semantic_diversity_if_all_action_class")
    if not expected_single_class or len(group) < len(PROFILES):
        return []
    classes = [case.get("action_tendency_class", "mixed_or_unclear") for case in group]
    if classes and all(action_class == expected_single_class for action_class in classes):
        return [f"all_profiles_{expected_single_class}"]
    return []


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = [case_summary(case) for case in cases]
    scenario_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        scenario_groups[case["scenario_id"]].append(case)

    profile_sensitivity: dict[str, Any] = {}
    for scenario_id, group in sorted(scenario_groups.items()):
        signatures = {ego_signature(case) for case in group}
        profile_sensitivity[scenario_id] = {
            "case_count": len(group),
            "unique_ego_signatures": len(signatures),
            "identical_across_all_profiles": len(signatures) <= 1 and len(group) > 1,
            "profile_leader_distribution": distribution([case.get("profile_leader") for case in group]),
            "situational_driver_distribution": distribution([case.get("situational_driver") for case in group]),
            "resultant_leader_distribution": distribution(
                [case.get("resultant_leader_under_pressure") for case in group]
            ),
            "action_tendency_class_distribution": distribution(
                [case.get("action_tendency_class", "mixed_or_unclear") for case in group]
            ),
            "semantic_diversity_flags": semantic_diversity_flags(scenario_id, group),
        }

    equal_profile_cases = [case for case in cases if case["profile_input"] == "REI"]
    rei_racio_defaults = [
        case["scenario_id"]
        for case in equal_profile_cases
        if case.get("resultant_leader_under_pressure") == "racio" or case.get("leading_mind") == "racio"
    ]

    false_positive_cases = [
        f"{case['scenario_id']}::{case['profile_input']}"
        for case in cases
        if any(flag_is_active(value) for value in case["false_positive_flags"].values())
    ]
    actionable_failure_cases = actionable_failure_case_ids(cases)
    missing_cases = [
        f"{case['scenario_id']}::{case['profile_input']}"
        for case in cases
        if has_missing_required_keys(case["missing_required_keys"])
        or has_missing_required_keys(case["raw_call_missing_required_keys"])
    ]
    hard_false_negative_cases = severity_cases(cases, "hard_false_negative")
    soft_false_negative_cases = severity_cases(cases, "soft_false_negative")
    evaluator_warning_cases = severity_cases(cases, "evaluator_warning")
    identity_violations = [
        f"{case['scenario_id']}::{case['profile_input']}"
        for case in cases
        if any((case.get("false_positive_flags", {}).get("processor_identity_unstable") or {}).values())
    ]

    return {
        "case_count": len(cases),
        "fallback_count": sum(int(case["fallback_count"]) for case in cases),
        "total_tokens": sum(int(case["token_count"]["totals"]["total"]) for case in cases),
        "false_positive_case_count": len(false_positive_cases),
        "hard_false_negative_case_count": len(hard_false_negative_cases),
        "soft_false_negative_case_count": len(soft_false_negative_cases),
        "evaluator_warning_case_count": len(evaluator_warning_cases),
        "actionable_failure_case_count": len(actionable_failure_cases),
        "false_negative_case_count": len(actionable_failure_cases),
        "missing_required_key_case_count": len(missing_cases),
        "true_missing_required_key_count": len(missing_cases),
        "processor_identity_violation_count": len(identity_violations),
        "rei_profile_racio_default_cases": rei_racio_defaults,
        "profile_sensitivity": profile_sensitivity,
        "false_positive_cases": false_positive_cases,
        "false_negative_cases": actionable_failure_cases,
        "actionable_failure_cases": actionable_failure_cases,
        "hard_false_negative_cases": hard_false_negative_cases,
        "soft_false_negative_cases": soft_false_negative_cases,
        "evaluator_warning_cases": evaluator_warning_cases,
        "missing_required_key_cases": missing_cases,
        "processor_identity_violations": identity_violations,
        "cases": summaries,
    }


def compact_case_row(case: dict[str, Any]) -> str:
    fp = ",".join(key for key, value in case["false_positive_flags"].items() if flag_is_active(value)) or "none"
    fn = ",".join(key for key, value in case["false_negative_flags"].items() if flag_is_active(value)) or "none"
    severity = case.get("false_negative_severity") or active_false_negative_severity(case["false_negative_flags"])
    severity_text = ",".join(
        f"{name}:{len(items)}"
        for name, items in severity.items()
        if items
    ) or "none"
    tokens = case["token_count"]["totals"]["total"]
    max_jaccard = case["processor_distinctness"].get("max_overlap")
    return (
        f"| `{case['scenario_id']}` | `{case['profile_input']}` | `{case['fallback_count']}` | "
        f"`{tokens}` | `{max_jaccard}` | `{case['profile_leader']}` | `{case['situational_driver']}` | "
        f"`{case['resultant_leader_under_pressure']}` | `{case['leading_mind']}` | "
        f"`{case.get('action_tendency_class', 'mixed_or_unclear')}` | {fp} | {fn} | {severity_text} |"
    )


def write_markdown(path: Path, run: dict[str, Any], summary: dict[str, Any]) -> None:
    new_metrics = {
        "fallback_count": summary["fallback_count"],
        "true_missing_required_key_count": summary["true_missing_required_key_count"],
        "hard_false_negative_count": summary["hard_false_negative_case_count"],
        "soft_false_negative_count": summary["soft_false_negative_case_count"],
        "actionable_failure_count": summary["actionable_failure_case_count"],
        "false_positive_count": summary["false_positive_case_count"],
        "rei_racio_default_case_count": len(summary["rei_profile_racio_default_cases"]),
        "processor_identity_violation_count": summary["processor_identity_violation_count"],
    }
    lines = [
        "# REI Profile Matrix Evaluation",
        "",
        f"- Run id: `{run['run_id']}`",
        f"- Provider: `{run['provider']}`",
        f"- Model: `{run['model']}`",
        f"- Context: `{run['num_ctx']}`",
        f"- GPU layers: `{run['num_gpu']}`",
        f"- Cases: `{summary['case_count']}`",
        f"- Fallback count: `{summary['fallback_count']}`",
        f"- Missing-key case count: `{summary['missing_required_key_case_count']}`",
        f"- Processor identity violations: `{summary['processor_identity_violation_count']}`",
        f"- False-positive case count: `{summary['false_positive_case_count']}`",
        f"- False-negative case count: `{summary['false_negative_case_count']}`",
        f"- Hard false-negative case count: `{summary['hard_false_negative_case_count']}`",
        f"- Soft false-negative case count: `{summary['soft_false_negative_case_count']}`",
        f"- Actionable failure case count: `{summary['actionable_failure_case_count']}`",
        f"- Evaluator-warning case count: `{summary['evaluator_warning_case_count']}`",
        f"- Total tokens: `{summary['total_tokens']}`",
        "",
        "## Old vs New Metrics",
        "",
        "| Metric | Previous run | Current run |",
        "|---|---:|---:|",
    ]
    for key, current in new_metrics.items():
        lines.append(f"| `{key}` | `{PREVIOUS_PROFILE_MATRIX_METRICS[key]}` | `{current}` |")
    lines.extend(
        [
            "",
        "## Profile Sensitivity",
        "",
            "| Scenario | Cases | Unique Ego signatures | Identical across profiles | Profile leaders | Situational drivers | Resultants | Action classes | Semantic diversity flags |",
            "|---|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for scenario_id, data in summary["profile_sensitivity"].items():
        lines.append(
            f"| `{scenario_id}` | `{data['case_count']}` | `{data['unique_ego_signatures']}` | "
            f"`{data['identical_across_all_profiles']}` | `{data['profile_leader_distribution']}` | "
            f"`{data['situational_driver_distribution']}` | `{data['resultant_leader_distribution']}` | "
            f"`{data['action_tendency_class_distribution']}` | `{data.get('semantic_diversity_flags', [])}` |"
        )

    lines.extend(
        [
            "",
            "## Quality Flags",
            "",
            f"- False positives: `{summary['false_positive_cases']}`",
            f"- False negatives: `{summary['false_negative_cases']}`",
            f"- Actionable failures: `{summary['actionable_failure_cases']}`",
            f"- Hard false negatives: `{summary['hard_false_negative_cases']}`",
            f"- Soft false negatives: `{summary['soft_false_negative_cases']}`",
            f"- Evaluator warnings: `{summary['evaluator_warning_cases']}`",
            f"- Missing required keys: `{summary['missing_required_key_cases']}`",
            f"- Processor identity violations: `{summary['processor_identity_violations']}`",
            f"- R=E=I Racio-default cases: `{summary['rei_profile_racio_default_cases']}`",
            "",
            "## Case Table",
            "",
            "| Scenario | Profile | Fallbacks | Tokens | Max Jaccard | Profile leader | Situational driver | Resultant | Leading | Action class | False positives | False negatives | Severity |",
            "|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|",
        ]
    )
    for case in summary["cases"]:
        lines.append(compact_case_row(case))
    path.write_text("\n".join(lines), encoding="utf-8")


def selected_profiles(raw: str | None) -> list[str]:
    if not raw:
        return list(PROFILES)
    requested = [token.strip() for token in raw.split(",") if token.strip()]
    unknown = [profile for profile in requested if profile not in PROFILES]
    if unknown:
        raise SystemExit(f"Unknown profiles: {', '.join(unknown)}")
    return requested


def selected_scenarios(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return list(SCENARIOS)
    terms = [term.strip().lower() for term in raw.split(",") if term.strip()]
    scenarios = [
        scenario
        for scenario in SCENARIOS
        if any(term in scenario["id"].lower() or term in scenario["title"].lower() for term in terms)
    ]
    if not scenarios:
        raise SystemExit(f"No scenarios matched {raw!r}")
    return scenarios


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run REI-v3 profile matrix across 13 profiles and 12 scenarios.")
    parser.add_argument("--provider", choices=["ollama", "deterministic"], default="ollama")
    parser.add_argument("--model", default="granite4.1:30b")
    parser.add_argument("--num-ctx", type=int, default=65536)
    parser.add_argument("--num-gpu", type=int, default=999)
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--profile-filter", default=None)
    parser.add_argument("--scenario-filter", default=None)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--docs-summary-dir", default=str(ROOT / "Docs" / "evals"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ["REI_OLLAMA_NUM_CTX"] = str(args.num_ctx)
    os.environ["REI_OLLAMA_NUM_GPU"] = str(args.num_gpu)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / "output" / "reports" / "rei_profile_matrix" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "progress.log"
    jsonl_path = output_dir / "cases.jsonl"
    cases_path = output_dir / "cases.json"
    summary_path = output_dir / "summary.json"
    markdown_path = output_dir / "summary.md"

    profiles = selected_profiles(args.profile_filter)
    scenarios = selected_scenarios(args.scenario_filter)
    plan = [
        (scenario, profile)
        for scenario in scenarios
        for profile in profiles
    ]
    if args.max_cases is not None:
        plan = plan[: max(0, args.max_cases)]

    run_meta = {
        "run_id": run_id,
        "provider": args.provider,
        "model": args.model if args.provider == "ollama" else "deterministic",
        "num_ctx": args.num_ctx,
        "num_gpu": args.num_gpu,
        "profile_count": len(profiles),
        "scenario_count": len(scenarios),
        "case_count": len(plan),
        "output_dir": str(output_dir),
        "profiles": profiles,
        "scenario_ids": [scenario["id"] for scenario in scenarios],
    }
    write_json(output_dir / "run.json", run_meta)
    write_progress(
        progress_path,
        f"START run_id={run_id} provider={args.provider} model={args.model} "
        f"num_ctx={args.num_ctx} num_gpu={args.num_gpu} cases={len(plan)}",
    )

    if args.provider == "ollama":
        available_models = OllamaProvider(base_url=args.ollama_base_url).list_models(timeout_seconds=10)
        if args.model not in available_models:
            write_progress(progress_path, f"WARNING requested_model_not_listed model={args.model} available={available_models}")

    engine = ReiEngine(
        KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"),
        ollama=OllamaProvider(base_url=args.ollama_base_url),
    )
    provider = provider_for(args)

    cases: list[dict[str, Any]] = []
    for index, (scenario, profile) in enumerate(plan, start=1):
        label = f"{index}/{len(plan)} scenario={scenario['id']} profile={profile}"
        write_progress(progress_path, f"RUN {label}")
        try:
            case = run_case(engine, scenario, profile, provider)
            case.update(
                {
                    "run_id": run_id,
                    "case_index": index,
                    "scenario_id": scenario["id"],
                    "scenario_title": scenario["title"],
                    "scenario_prompt": scenario["prompt"],
                    "scenario_metadata": {
                        key: value
                        for key, value in scenario.items()
                        if key not in {"prompt", "title"}
                    },
                }
            )
            write_progress(
                progress_path,
                f"DONE {label} fallbacks={case['fallback_count']} tokens={case['token_count']['totals']['total']} "
                f"resultant={case['resultant_leader_under_pressure']} leading={case['leading_mind']}",
            )
        except Exception as exc:
            case = {
                "run_id": run_id,
                "case_index": index,
                "scenario_id": scenario["id"],
                "scenario_title": scenario["title"],
                "scenario_prompt": scenario["prompt"],
                "scenario_metadata": {
                    key: value
                    for key, value in scenario.items()
                    if key not in {"prompt", "title"}
                },
                "profile_input": profile,
                "profile_normalized": normalize_profile(profile),
                "provider": args.provider,
                "model": args.model,
                "fallback_count": 1,
                "fallbacks": [{"mind": "run", "reason": str(exc)}],
                "missing_required_keys": {},
                "raw_call_missing_required_keys": [],
                "processor_distinctness": {},
                "profile_leader": "unknown",
                "situational_driver": "unknown",
                "resultant_leader_under_pressure": "unknown",
                "leading_mind": "unknown",
                "action_tendency": "",
                "action_tendency_class": "mixed_or_unclear",
                "raw_resultant_leader_under_pressure": "unknown",
                "raw_leading_mind": "unknown",
                "rei_resultant_adjusted_to_mixed": False,
                "false_positive_flags": {"run_error": True},
                "false_negative_flags": {"run_error": True},
                "false_negative_severity": {
                    "hard_false_negative": ["run_error"],
                    "soft_false_negative": [],
                    "evaluator_warning": [],
                },
                "token_count": {"totals": {"prompt": 0, "eval": 0, "total": 0}, "calls": []},
                "error": str(exc),
            }
            write_progress(progress_path, f"ERROR {label} error={exc}")

        append_jsonl(jsonl_path, case)
        cases.append(case)
        summary = aggregate(cases)
        write_json(cases_path, cases)
        write_json(summary_path, summary)
        write_markdown(markdown_path, run_meta, summary)

    summary = aggregate(cases)
    write_json(cases_path, cases)
    write_json(summary_path, summary)
    write_markdown(markdown_path, run_meta, summary)

    docs_summary_dir = Path(args.docs_summary_dir)
    docs_summary_dir.mkdir(parents=True, exist_ok=True)
    docs_summary_path = docs_summary_dir / f"rei_profile_matrix_summary_{datetime.now().strftime('%Y-%m-%d')}.md"
    docs_summary_path.write_text(markdown_path.read_text(encoding="utf-8"), encoding="utf-8")
    write_progress(progress_path, f"COMPLETE run_id={run_id} cases={len(cases)} docs_summary={docs_summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
