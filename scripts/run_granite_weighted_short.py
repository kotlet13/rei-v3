from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.engine import ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection, PsycheState, Scenario
from rei.providers import OllamaProvider
from rei.weighted_audit import (
    PROFILE_TOP_MINDS,
    audit_weighted_synthesis,
    normalize_decision,
    summarize_stock_phrase_cases,
    warning_codes,
)


MODEL = "granite4.1:30b"
DEFAULT_NUM_CTX = 65536
DEFAULT_NUM_GPU = 999

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

MANUAL_AUDIT_PROFILES = ["R", "E", "I", "REI"]
MANUAL_AUDIT_SCENARIOS = [
    "pure-budget-allocation",
    "creative-status-risk",
    "night-door-noise",
    "business-runway",
]

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "pure-budget-allocation",
        "title": "Pure budget allocation",
        "expected_pressure": "racio",
        "prompt": (
            "A project lead has a fixed budget and must allocate it between testing, design, infrastructure, "
            "and marketing. There is no social drama, no bodily threat, and no image wound; the decision is "
            "mainly about constraints, sequence, and opportunity cost."
        ),
        "grounding_terms": ["budget", "testing", "design", "infrastructure", "marketing", "allocation", "cost"],
        "allowed_options": [
            "prioritize testing",
            "prioritize design",
            "prioritize infrastructure",
            "prioritize marketing",
            "balanced allocation",
        ],
        "option_aliases": {
            "balanced allocation": [
                "balanced quantitative model",
                "balanced weighted model",
                "weighted scoring model",
                "balances expected returns",
                "balances marginal utility",
                "balances stakeholder",
                "allocate the budget using",
                "sufficient funds for",
            ]
        },
    },
    {
        "id": "technical-architecture-choice",
        "title": "Technical architecture choice",
        "expected_pressure": "racio",
        "prompt": (
            "A developer must choose between three technical architectures. One is fast but brittle, one is "
            "slower but reliable, and one is elegant but untested. The decision depends on timeline, "
            "maintenance cost, reversibility, and known constraints."
        ),
        "grounding_terms": ["architecture", "fast", "brittle", "reliable", "untested", "maintenance", "timeline"],
        "allowed_options": [
            "fast but brittle architecture",
            "slower reliable architecture",
            "elegant untested architecture",
            "phased architecture spike",
        ],
        "option_aliases": {
            "fast but brittle architecture": ["fast architecture", "fast but brittle"],
            "slower reliable architecture": ["slower but reliable", "reliable architecture"],
            "elegant untested architecture": ["elegant but untested", "untested architecture"],
            "phased architecture spike": ["architecture spike", "phased spike", "small spike"],
        },
    },
    {
        "id": "business-runway",
        "title": "Business launch with runway",
        "expected_pressure": "mixed",
        "prompt": (
            "A person wants to launch a business and already has six months of runway, one paying customer, "
            "and strong excitement, but still fears that a wrong move could collapse stability."
        ),
        "grounding_terms": ["business", "runway", "paying customer", "stability", "launch", "collapse"],
        "allowed_options": [
            "launch now",
            "extend runway",
            "pilot with paying customer",
            "delay launch",
            "hybrid staged launch",
        ],
        "option_aliases": {
            "launch now": ["launch the business", "start the launch"],
            "extend runway": ["extend the runway", "preserve runway"],
            "pilot with paying customer": ["pilot", "paying customer"],
            "delay launch": ["delay the launch", "wait before launch"],
            "hybrid staged launch": [
                "staged launch",
                "hybrid launch",
                "launch in stages",
                "structured incremental growth",
                "incremental growth plan",
                "controlled growth strategy",
                "phased growth strategy",
                "controlled phased launch",
                "controlled, phased launch",
                "phased launch strategy",
                "incremental launch plan",
                "controlled growth experiment",
                "small, predefined budget",
                "strict kpis",
                "safety thresholds",
                "balances runway preservation",
            ],
        },
    },
    {
        "id": "creative-status-risk",
        "title": "Creative status risk",
        "expected_pressure": "emocio",
        "prompt": (
            "An artist must choose between a safe accepted exhibition and a bold personal piece that could be "
            "admired or mocked. The bold option feels alive, visible, and dangerous to their pride."
        ),
        "grounding_terms": ["artist", "exhibition", "bold", "admired", "mocked", "pride", "visible"],
        "allowed_options": [
            "safe accepted exhibition",
            "bold personal piece",
            "hybrid staged release",
            "delay and gather feedback",
        ],
        "option_aliases": {
            "safe accepted exhibition": ["accepted exhibition", "safe exhibition"],
            "bold personal piece": ["personal piece", "bold piece"],
            "hybrid staged release": [
                "staged release",
                "hybrid release",
                "alongside the safe accepted exhibition",
                "alongside safe accepted exhibition",
                "present both the safe accepted exhibition",
                "both the safe accepted exhibition and the bold personal piece",
                "both risk and recognition",
                "maintaining a fallback",
                "calculated risk for creative growth",
                "controlled setting",
                "complemented by presenting",
            ],
            "delay and gather feedback": ["gather feedback", "delay for feedback"],
        },
    },
    {
        "id": "night-door-noise",
        "title": "Night door noise",
        "expected_pressure": "instinkt",
        "prompt": (
            "A person hears a hard noise near the front door late at night. They do not know whether it is "
            "harmless or dangerous. The immediate question is whether to open the door, stay still, call for "
            "help, or secure distance."
        ),
        "grounding_terms": ["door", "noise", "night", "open", "listen", "call for help", "secure distance"],
        "allowed_options": [
            "open the door",
            "stay still and listen",
            "secure distance",
            "call for help",
            "check through a safe barrier",
        ],
        "option_aliases": {
            "open the door": ["open it", "open the front door"],
            "stay still and listen": ["stay still", "listen first"],
            "secure distance": ["keep distance", "secure a distance", "move away"],
            "call for help": ["call help", "call someone", "call emergency"],
            "check through a safe barrier": ["safe barrier", "look through", "check through"],
        },
    },
]


def append_progress(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def selected_scenarios(raw_filter: str | None, manual_audit: bool = False) -> list[dict[str, Any]]:
    scenarios = list(SCENARIOS)
    if manual_audit and not raw_filter:
        return [scenario for scenario in scenarios if scenario["id"] in MANUAL_AUDIT_SCENARIOS]
    if not raw_filter:
        return scenarios
    tokens = [token.strip().lower() for token in raw_filter.split(",") if token.strip()]
    chosen = [
        scenario
        for scenario in scenarios
        if any(token in scenario["id"].lower() or token in scenario["title"].lower() for token in tokens)
    ]
    if manual_audit:
        chosen = [scenario for scenario in chosen if scenario["id"] in MANUAL_AUDIT_SCENARIOS]
    if not chosen:
        raise SystemExit(f"No selected scenario matched {raw_filter!r}")
    return chosen


def selected_profiles(raw_profiles: str | None, manual_audit: bool = False) -> list[str]:
    if manual_audit and not raw_profiles:
        return list(MANUAL_AUDIT_PROFILES)
    if not raw_profiles:
        return list(PROFILES)
    profiles = [item.strip() for item in raw_profiles.split(",") if item.strip()]
    unknown = [profile for profile in profiles if profile not in PROFILES]
    if unknown:
        raise SystemExit(f"Unknown profiles: {', '.join(unknown)}")
    if manual_audit:
        profiles = [profile for profile in profiles if profile in MANUAL_AUDIT_PROFILES]
    if not profiles:
        raise SystemExit("No selected profile remains after manual audit filtering.")
    return profiles


def build_plan(scenarios: list[dict[str, Any]], profiles: list[str], max_cases: int | None) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for scenario in scenarios:
        for profile in profiles:
            plan.append(
                {
                    "case_index": len(plan) + 1,
                    "scenario_id": scenario["id"],
                    "scenario_title": scenario["title"],
                    "expected_pressure": scenario["expected_pressure"],
                    "scenario_prompt": scenario["prompt"],
                    "grounding_terms": scenario.get("grounding_terms") or [],
                    "allowed_options": scenario["allowed_options"],
                    "option_aliases": scenario.get("option_aliases") or {},
                    "profile": profile,
                    "profile_top_minds": PROFILE_TOP_MINDS[profile],
                }
            )
    if max_cases:
        return plan[:max_cases]
    return plan


def compact_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    compact = dict(diagnostics)
    compact["llm_calls"] = [
        {key: value for key, value in call.items() if key not in {"request", "response"}}
        for call in diagnostics.get("llm_calls", [])
    ]
    return compact


def scenario_for_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": case["scenario_id"],
        "title": case["scenario_title"],
        "expected_pressure": case["expected_pressure"],
        "prompt": case["scenario_prompt"],
        "grounding_terms": case.get("grounding_terms") or [],
        "allowed_options": case.get("allowed_options") or [],
        "option_aliases": case.get("option_aliases") or {},
    }


def evaluate_trace(trace_payload: dict[str, Any], profile: str, case: dict[str, Any]) -> dict[str, Any]:
    synthesis = trace_payload.get("synthesis_turn", {}) or {}
    contributions = synthesis.get("weighted_contributions") or {}
    ranking = synthesis.get("contribution_ranking") or []
    tilt = synthesis.get("synthesis_tilt")
    expected_top = PROFILE_TOP_MINDS[profile]
    numeric_values = [value for value in contributions.values() if isinstance(value, (int, float))]
    top_share = max(numeric_values) if numeric_values else 0.0
    bottom_share = min(numeric_values) if numeric_values else 0.0
    rei_audit = audit_weighted_synthesis(
        trace_payload,
        profile,
        case["scenario_id"],
        grounding_terms=case.get("grounding_terms") or [],
    )
    decision = normalize_decision(trace_payload, scenario_for_case(case))
    rei_audit["decision_extraction_valid"] = decision["valid"]

    return {
        "synthesis_tilt": tilt,
        "profile_top_minds": expected_top,
        "tilt_matches_profile_top": tilt in expected_top,
        "underrepresented_signal": synthesis.get("underrepresented_signal"),
        "hijack_risk": synthesis.get("hijack_risk"),
        "processor_weights": synthesis.get("processor_weights"),
        "weighted_contributions": contributions,
        "contribution_ranking": ranking,
        "contribution_spread": round(top_share - bottom_share, 3),
        "contribution_sum": rei_audit["contribution_sum"],
        "contribution_sum_valid": rei_audit["contribution_sum_valid"],
        "weighted_contributions_normalized": rei_audit["weighted_contributions_normalized"],
        "normalized_contributions": rei_audit["normalized_contributions"],
        "ranking_matches_contributions": rei_audit["ranking_matches_contributions"],
        "tilt_matches_ranking": rei_audit["tilt_matches_ranking"],
        "dominant_coalition_legacy": synthesis.get("dominant_coalition"),
        "blocked_mind_legacy": synthesis.get("blocked_mind"),
        "decision": decision,
        "decision_choice": decision["chosen_option"],
        "decision_valid": decision["valid"],
        "decision_problem": decision["problem"],
        "final_monologue": synthesis.get("final_monologue"),
        "main_agreement": synthesis.get("main_agreement"),
        "main_conflict": synthesis.get("main_conflict"),
        "repetition_hits": rei_audit["stock_phrase_hits"],
        "rei_audit": rei_audit,
    }


def artifact_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "output_dir": output_dir,
        "progress": output_dir / "progress.log",
        "results_jsonl": output_dir / "results.jsonl",
        "summary": output_dir / "summary.json",
        "report": output_dir / "report.md",
        "scenario_plan": output_dir / "scenario_plan.json",
    }


def artifact_integrity(paths: dict[str, Path], expected_jsonl_lines: int) -> dict[str, Any]:
    results_path = paths["results_jsonl"]
    lines = count_jsonl_lines(results_path)
    return {
        "results_jsonl_exists": results_path.exists(),
        "results_jsonl_lines": lines,
        "expected_jsonl_lines": expected_jsonl_lines,
        "results_jsonl_complete": results_path.exists() and lines == expected_jsonl_lines,
        "report_exists": paths["report"].exists(),
        "summary_exists": paths["summary"].exists(),
        "progress_exists": paths["progress"].exists(),
        "scenario_plan_exists": paths["scenario_plan"].exists(),
    }


def weighted_integrity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if not row.get("error")]
    audits = [(row.get("evaluation") or {}).get("rei_audit") or {} for row in completed]
    return {
        "all_cases_have_three_contributions": bool(completed)
        and all(audit.get("all_three_minds_present_in_contributions") for audit in audits),
        "ranking_mismatch_count": sum(1 for audit in audits if not audit.get("ranking_matches_contributions")),
        "tilt_mismatch_count": sum(1 for audit in audits if not audit.get("tilt_matches_ranking")),
        "bad_sum_count": sum(1 for audit in audits if not audit.get("contribution_sum_valid")),
        "missing_weighted_field_count": sum(
            1
            for audit in audits
            if not (
                audit.get("has_processor_weights")
                and audit.get("has_weighted_contributions")
                and audit.get("has_contribution_ranking")
                and audit.get("has_synthesis_tilt")
                and audit.get("has_underrepresented_signal")
                and audit.get("has_final_monologue")
            )
        ),
    }


def decision_validity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if not row.get("error")]
    valid = sum(1 for row in completed if row.get("evaluation", {}).get("decision", {}).get("valid"))
    invalid = len(completed) - valid
    return {
        "valid": valid,
        "invalid": invalid,
        "rate": round(valid / len(completed), 3) if completed else 0.0,
    }


def functional_presence_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if not row.get("error")]
    audits = [row.get("evaluation", {}).get("rei_audit", {}) for row in completed]
    total = len(audits)
    all_three = sum(1 for audit in audits if audit.get("all_three_minds_functionally_present"))
    per_mind_scores: dict[str, list[float]] = {"R": [], "E": [], "I": []}
    for audit in audits:
        functional = audit.get("functional_presence") or {}
        for mind in per_mind_scores:
            value = functional.get(mind, {}).get("score", 0.0)
            per_mind_scores[mind].append(float(value or 0.0))
    return {
        "all_three_functionally_present": all_three,
        "total": total,
        "rate": round(all_three / total, 3) if total else 0.0,
        "average_functional_presence_score": round(
            sum(float(audit.get("functional_presence_score") or 0.0) for audit in audits) / total,
            3,
        )
        if total
        else 0.0,
        "per_mind_average_score": {
            mind: round(sum(scores) / len(scores), 3) if scores else 0.0
            for mind, scores in per_mind_scores.items()
        },
        "role_name_only_warning_count": sum(1 for audit in audits if audit.get("role_name_only_warning")),
        "generic_role_listing_warning_count": sum(1 for audit in audits if audit.get("generic_role_listing_warning")),
        "low_scenario_grounding_warning_count": sum(
            1 for audit in audits if (audit.get("scenario_grounding") or {}).get("low_scenario_grounding_warning")
        ),
        "scenario_grounding_pass": sum(
            1 for audit in audits if not (audit.get("scenario_grounding") or {}).get("low_scenario_grounding_warning")
        ),
        "scenario_grounding_rate": round(
            sum(
                1
                for audit in audits
                if not (audit.get("scenario_grounding") or {}).get("low_scenario_grounding_warning")
            )
            / total,
            3,
        )
        if total
        else 0.0,
    }


def weighted_compromise_quality_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"good": 0, "partial": 0, "weak": 0, "unknown": 0}
    for row in rows:
        if row.get("error"):
            continue
        quality = row.get("evaluation", {}).get("rei_audit", {}).get("weighted_compromise_quality") or "unknown"
        counts[str(quality)] = counts.get(str(quality), 0) + 1
    return counts


def rei_thirteenth_character_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rei_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.get("error") or row.get("profile") != "REI":
            continue
        audit = row.get("evaluation", {}).get("rei_audit") or {}
        rei_rows.append(
            {
                "case_id": f"{int(row['case_index']):03d}",
                "scenario_id": row["scenario_id"],
                "synthesis_tilt": row.get("evaluation", {}).get("synthesis_tilt"),
                "rei_two_of_three_explanation_present": audit.get("rei_two_of_three_explanation_present"),
                "rei_majority_pair": audit.get("rei_majority_pair") or [],
                "rei_minority_objection": audit.get("rei_minority_objection"),
                "rei_top_two_gap": audit.get("rei_top_two_gap"),
                "rei_top_two_close": audit.get("rei_top_two_close"),
                "rei_minority_objection_visible": audit.get("rei_minority_objection_visible"),
                "rei_arbitrary_tilt_warning": audit.get("rei_arbitrary_tilt_warning"),
            }
        )
    return {
        "rows": rei_rows,
        "arbitrary_tilt_warning_count": sum(1 for row in rei_rows if row["rei_arbitrary_tilt_warning"]),
    }


def summarize(
    rows: list[dict[str, Any]],
    run_meta: dict[str, Any],
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    completed = [row for row in rows if not row.get("error")]
    errors = [row for row in rows if row.get("error")]
    tilt_counts = Counter(row.get("evaluation", {}).get("synthesis_tilt") for row in completed)
    underrepresented_counts = Counter(row.get("evaluation", {}).get("underrepresented_signal") for row in completed)
    scenario_match: dict[str, dict[str, int]] = defaultdict(lambda: {"matched": 0, "total": 0})
    profile_match: dict[str, dict[str, int]] = defaultdict(lambda: {"matched": 0, "total": 0})
    missing_mind_counts = [
        len(row.get("evaluation", {}).get("rei_audit", {}).get("missing_mind_mentions_in_final_monologue") or [])
        for row in completed
    ]
    missing_final_monologue_count = sum(
        1 for row in completed if not row.get("evaluation", {}).get("rei_audit", {}).get("has_final_monologue")
    )

    for row in completed:
        evaluation = row["evaluation"]
        matched = bool(evaluation.get("tilt_matches_profile_top"))
        scenario_match[row["scenario_id"]]["total"] += 1
        profile_match[row["profile"]]["total"] += 1
        if matched:
            scenario_match[row["scenario_id"]]["matched"] += 1
            profile_match[row["profile"]]["matched"] += 1

    def with_rates(items: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
        return {
            key: {
                **value,
                "rate": round(value["matched"] / value["total"], 3) if value["total"] else 0.0,
            }
            for key, value in sorted(items.items())
        }

    profile_top_matched = sum(1 for row in completed if row["evaluation"].get("tilt_matches_profile_top"))
    summary = {
        **run_meta,
        "status": "completed" if not errors else "completed_with_errors",
        "completed_cases": len(completed),
        "error_count": len(errors),
        "tilt_counts": dict(sorted((str(k), v) for k, v in tilt_counts.items())),
        "underrepresented_counts": dict(sorted((str(k), v) for k, v in underrepresented_counts.items())),
        "profile_top_match": {
            "matched": profile_top_matched,
            "total": len(completed),
            "rate": round(profile_top_matched / len(completed), 3) if completed else 0.0,
        },
        "scenario_profile_match": with_rates(scenario_match),
        "profile_match": with_rates(profile_match),
        "decision_validity": decision_validity(rows),
        "weighted_integrity": weighted_integrity(rows),
        "functional_presence_summary": functional_presence_summary(rows),
        "weighted_compromise_quality_counts": weighted_compromise_quality_counts(rows),
        "stock_phrase_diagnostics": summarize_stock_phrase_cases(rows),
        "rei_thirteenth_character_audit": rei_thirteenth_character_audit(rows),
        "model_interpretation": {
            "role": "quality_anchor",
            "small_model_readiness": False,
            "notes": "Granite 30B is used to reduce model weakness as a confounder.",
        },
        "average_missing_mind_count": round(sum(missing_mind_counts) / len(missing_mind_counts), 3)
        if missing_mind_counts
        else 0.0,
        "missing_final_monologue_count": missing_final_monologue_count,
    }
    if paths:
        summary["artifact_integrity"] = artifact_integrity(paths, len(completed) + len(errors))
    summary["warnings"] = warning_codes(summary)
    return summary


def strict_violations(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    strict_artifacts: bool,
    strict_weighted: bool,
    strict_functional: bool = False,
    min_functional_presence_rate: float = 0.8,
    min_scenario_grounding_rate: float = 0.8,
) -> list[str]:
    violations: list[str] = []
    artifact = summary.get("artifact_integrity") or {}
    completed = [row for row in rows if not row.get("error")]
    if strict_artifacts:
        if not artifact.get("results_jsonl_exists") or artifact.get("results_jsonl_lines", 0) == 0:
            violations.append("results.jsonl missing or empty")
        if not artifact.get("results_jsonl_complete"):
            violations.append("results.jsonl line count does not match completed + error cases")
        if not artifact.get("report_exists"):
            violations.append("report.md missing")
        if not artifact.get("summary_exists"):
            violations.append("summary.json missing")
        for row in completed:
            if not (row.get("trace") or {}).get("synthesis_turn"):
                violations.append(f"case {row['case_index']:03d} lacks trace.synthesis_turn")
            if not row.get("evaluation"):
                violations.append(f"case {row['case_index']:03d} lacks evaluation")
    if strict_weighted:
        required = [
            "has_processor_weights",
            "has_weighted_contributions",
            "has_contribution_ranking",
            "has_synthesis_tilt",
            "has_underrepresented_signal",
            "has_final_monologue",
        ]
        for row in completed:
            audit = row.get("evaluation", {}).get("rei_audit") or {}
            missing = [field for field in required if not audit.get(field)]
            if missing:
                violations.append(f"case {row['case_index']:03d} missing weighted fields: {', '.join(missing)}")
    if strict_functional:
        functional = summary.get("functional_presence_summary") or {}
        quality = summary.get("weighted_compromise_quality_counts") or {}
        if functional.get("rate", 0.0) < min_functional_presence_rate:
            violations.append(
                "functional mind presence rate "
                f"{functional.get('rate', 0.0)} is below {min_functional_presence_rate}"
            )
        if functional.get("scenario_grounding_rate", 0.0) < min_scenario_grounding_rate:
            violations.append(
                "scenario grounding rate "
                f"{functional.get('scenario_grounding_rate', 0.0)} is below {min_scenario_grounding_rate}"
            )
        if functional.get("role_name_only_warning_count", 0):
            violations.append("role-name-only functional presence warning exists")
        if functional.get("generic_role_listing_warning_count", 0):
            violations.append("generic role listing warning exists")
        if quality.get("weak", 0):
            violations.append("weak weighted compromise quality exists")
    return violations


def md_code(value: Any) -> str:
    if value is None:
        return "`null`"
    return f"`{str(value).replace('`', '')}`"


def md_json(value: Any) -> str:
    return f"`{json.dumps(value, ensure_ascii=False, sort_keys=True)}`"


def md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def blockquote(text: str | None) -> list[str]:
    if not text:
        return ["> "]
    return [f"> {line}" if line else ">" for line in str(text).splitlines()]


def functional_evidence_text(mind_payload: dict[str, Any]) -> str:
    groups: list[str] = []
    for item in mind_payload.get("evidence") or []:
        group = item.get("group")
        markers = ", ".join(item.get("markers") or [])
        groups.append(f"{group}: {markers}" if markers else str(group))
    return "; ".join(groups)


def write_report(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# Granite Weighted Short Run",
        "",
        "## Run",
        "",
        f"- **run_id:** `{summary['run_id']}`",
        f"- **model:** `{summary['model']}`",
        f"- **status:** `{summary['status']}`",
        f"- **cases:** `{summary['completed_cases']}/{summary['planned_cases']}`",
        f"- **elapsed_seconds:** `{summary.get('elapsed_seconds', 0)}`",
        f"- **profile_top_match:** `{summary['profile_top_match']['matched']}/{summary['profile_top_match']['total']}` (`{summary['profile_top_match']['rate']}`)",
        f"- **warnings:** `{', '.join(summary.get('warnings') or []) or 'none'}`",
        "",
        "## Model Interpretation",
        "",
        "This run uses Granite 30B as a high-capacity reference model.",
        "The purpose is to test architecture and evaluation strictness before scaling down.",
        "A passing Granite run is not proof that smaller models will pass.",
        "A failing Granite run means the prompt/eval architecture is probably still wrong.",
        "",
        "## Artifact Integrity",
        "",
        "```json",
        json.dumps(summary.get("artifact_integrity") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Decision Validity",
        "",
        f"- **valid:** `{summary['decision_validity']['valid']}`",
        f"- **invalid:** `{summary['decision_validity']['invalid']}`",
        f"- **rate:** `{summary['decision_validity']['rate']}`",
        "",
        "## Functional Presence Summary",
        "",
        f"- **all_three_functionally_present_rate:** `{summary['functional_presence_summary']['rate']}`",
        f"- **average_functional_presence_score:** `{summary['functional_presence_summary']['average_functional_presence_score']}`",
        f"- **per_mind_average_score:** {md_json(summary['functional_presence_summary']['per_mind_average_score'])}",
        f"- **weighted_compromise_quality_counts:** {md_json(summary['weighted_compromise_quality_counts'])}",
        f"- **generic_role_listing_warning_count:** `{summary['functional_presence_summary']['generic_role_listing_warning_count']}`",
        f"- **role_name_only_warning_count:** `{summary['functional_presence_summary']['role_name_only_warning_count']}`",
        f"- **low_scenario_grounding_warning_count:** `{summary['functional_presence_summary']['low_scenario_grounding_warning_count']}`",
        "",
        "## Weighted Integrity",
        "",
        "```json",
        json.dumps(summary.get("weighted_integrity") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Scenario Match",
        "",
        "| Scenario | Match | Rate |",
        "| --- | ---: | ---: |",
    ]
    for scenario_id, stats in summary["scenario_profile_match"].items():
        lines.append(f"| `{scenario_id}` | `{stats['matched']}/{stats['total']}` | `{stats['rate']}` |")
    lines.extend(
        [
            "",
            "## Tilt Counts",
            "",
            "```json",
            json.dumps(summary["tilt_counts"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Stock Phrase Diagnostics",
            "",
            f"- **stock_phrase_density:** `{summary['stock_phrase_diagnostics']['stock_phrase_density']}`",
            f"- **density_warning:** `{summary['stock_phrase_diagnostics']['density_warning']}`",
            "",
            "| Phrase | Count | Scenarios | Profiles |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for phrase in summary["stock_phrase_diagnostics"]["phrases"]:
        lines.append(
            f"| `{md_cell(phrase['phrase'])}` | `{phrase['count']}` | "
            f"{md_json(phrase['scenarios'])} | {md_json(phrase['profiles'])} |"
        )
    lines.extend(
        [
            "",
            "## Worst Repetition Cases",
            "",
            "| Case | Scenario | Profile | Count | Hits |",
            "| ---: | --- | --- | ---: | --- |",
        ]
    )
    for case in summary["stock_phrase_diagnostics"]["worst_repetition_cases"]:
        lines.append(
            f"| `{case['case_id']}` | `{case['scenario_id']}` | `{case['profile']}` | "
            f"`{case['count']}` | {md_json(case['hits'])} |"
        )
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| # | Scenario | Profile | Tilt | Top Match | Underrepresented | Decision | Valid |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        if row.get("error"):
            lines.append(
                f"| `{row['case_index']}` | `{row['scenario_id']}` | `{row['profile']}` | `error` |  |  | {md_cell(row['error'])} | `false` |"
            )
            continue
        evaluation = row["evaluation"]
        decision = evaluation.get("decision") or {}
        lines.append(
            f"| `{row['case_index']}` | `{row['scenario_id']}` | `{row['profile']}` | "
            f"`{evaluation.get('synthesis_tilt')}` | `{evaluation.get('tilt_matches_profile_top')}` | "
            f"`{evaluation.get('underrepresented_signal')}` | {md_cell(decision.get('chosen_option') or '')} | "
            f"`{decision.get('valid')}` |"
        )

    lines.extend(["", "## Case Details", ""])
    for row in rows:
        case_id = f"{int(row['case_index']):03d}"
        lines.append(f"### Case {case_id} - {row['scenario_id']} / {row['profile']}")
        lines.append("")
        if row.get("error"):
            lines.extend(["#### Error", "", f"`{row['error']}`", ""])
            continue

        evaluation = row["evaluation"]
        audit = evaluation.get("rei_audit") or {}
        decision = evaluation.get("decision") or {}
        functional = audit.get("functional_presence") or {}
        grounding = audit.get("scenario_grounding") or {}
        lines.extend(
            [
                "#### Profile",
                "",
                f"- Profile: `{row['profile']}`",
                f"- Profile top minds: {md_json(row['profile_top_minds'])}",
                f"- Scenario expected pressure: `{row['expected_pressure']}`",
                "",
                "#### Weighted Synthesis",
                "",
                f"- Processor weights: {md_json(evaluation.get('processor_weights'))}",
                f"- Weighted contributions: {md_json(evaluation.get('weighted_contributions'))}",
                f"- Normalized contributions: {md_json(evaluation.get('normalized_contributions'))}",
                f"- Contribution ranking: {md_json(evaluation.get('contribution_ranking'))}",
                f"- Synthesis tilt: {md_code(evaluation.get('synthesis_tilt'))}",
                f"- Top match: `{evaluation.get('tilt_matches_profile_top')}`",
                f"- Underrepresented signal: {md_code(evaluation.get('underrepresented_signal'))}",
                f"- Hijack risk: {md_code(evaluation.get('hijack_risk'))}",
                f"- Contribution spread: `{evaluation.get('contribution_spread')}`",
                f"- Contribution sum: `{evaluation.get('contribution_sum')}`",
                f"- Contribution sum valid: `{evaluation.get('contribution_sum_valid')}`",
                f"- Ranking matches contributions: `{evaluation.get('ranking_matches_contributions')}`",
                f"- Tilt matches ranking: `{evaluation.get('tilt_matches_ranking')}`",
                "",
                "#### Legacy Diagnostics",
                "",
                f"- Dominant coalition legacy: {md_json(evaluation.get('dominant_coalition_legacy'))}",
                f"- Blocked mind legacy: {md_code(evaluation.get('blocked_mind_legacy'))}",
                "",
                "#### Final Monologue",
                "",
                *blockquote(evaluation.get("final_monologue")),
                "",
                "#### Decision",
                "",
                f"- Chosen option: {md_code(decision.get('chosen_option'))}",
                f"- Decision type: {md_code(decision.get('decision_type'))}",
                f"- Confidence: `{decision.get('confidence')}`",
                f"- Valid: `{decision.get('valid')}`",
                f"- Problem: {md_code(decision.get('problem'))}",
                f"- Source: {md_code(decision.get('source'))}",
                f"- Rationale: {md_code(decision.get('rationale'))}",
                "",
                "#### Functional Mind Presence",
                "",
                "| Mind | Present | Score | Evidence | Missing Functions |",
                "| --- | --- | ---: | --- | --- |",
            ]
        )
        for mind in ["R", "E", "I"]:
            payload = functional.get(mind) or {}
            lines.append(
                f"| `{mind}` | `{payload.get('present')}` | `{payload.get('score')}` | "
                f"{md_cell(functional_evidence_text(payload))} | {md_json(payload.get('missing_functions') or [])} |"
            )
        lines.extend(
            [
                "",
                f"- All three functionally present: `{audit.get('all_three_minds_functionally_present')}`",
                f"- Functional presence score: `{audit.get('functional_presence_score')}`",
                f"- Role-name-only warning: `{audit.get('role_name_only_warning')}`",
                f"- Generic role listing warning: `{audit.get('generic_role_listing_warning')}`",
                "",
                "#### Scenario Grounding",
                "",
                f"- Score: `{grounding.get('score')}`",
                f"- Matched terms: {md_json(grounding.get('matched_terms') or [])}",
                f"- Missing expected terms: {md_json(grounding.get('missing_expected_terms') or [])}",
                f"- Low grounding warning: `{grounding.get('low_scenario_grounding_warning')}`",
                "",
                "#### Weighted Compromise Quality",
                "",
                f"- Quality: `{audit.get('weighted_compromise_quality')}`",
                "",
                "#### REI Audit",
                "",
                f"- Are all three minds present? `{audit.get('all_three_minds_visible_in_final_monologue')}`",
                f"- All three contributions present? `{audit.get('all_three_minds_present_in_contributions')}`",
                f"- Missing mind mentions: {md_json(audit.get('missing_mind_mentions_in_final_monologue'))}",
                f"- Stock phrase hits: {md_json(audit.get('stock_phrase_hits'))}",
                f"- Mechanical match warning: `{audit.get('mechanical_profile_match_warning')}`",
                f"- Hijack expected but missing: `{audit.get('hijack_expected_but_missing')}`",
                "",
            ]
        )

    lines.extend(
        [
            "## REI / Thirteenth Character Audit",
            "",
            "| Case | Scenario | Tilt | Two-of-three Explanation | Top Two Gap | Top Two Close | Majority Pair | Minority Objection | Minority Visible | Arbitrary Tilt Warning |",
            "| ---: | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in summary["rei_thirteenth_character_audit"]["rows"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['scenario_id']}` | `{row['synthesis_tilt']}` | "
            f"`{row['rei_two_of_three_explanation_present']}` | `{row.get('rei_top_two_gap')}` | "
            f"`{row.get('rei_top_two_close')}` | {md_json(row['rei_majority_pair'])} | "
            f"`{row['rei_minority_objection']}` | `{row.get('rei_minority_objection_visible')}` | "
            f"`{row['rei_arbitrary_tilt_warning']}` |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def unload_ollama_model(model: str, base_url: str, progress_path: Path) -> None:
    payload = json.dumps({"model": model, "prompt": "", "keep_alive": 0}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20):
            pass
        append_progress(progress_path, f"UNLOAD model={model} ok")
    except Exception as exc:
        append_progress(progress_path, f"UNLOAD model={model} failed={exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a short Granite-only weighted REI synthesis test.")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    parser.add_argument("--num-gpu", type=int, default=DEFAULT_NUM_GPU)
    parser.add_argument("--scenario-filter", default=None)
    parser.add_argument("--profiles", default=None)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--manual-audit", action="store_true")
    parser.add_argument("--confirm-run", action="store_true")
    parser.add_argument("--debug-trace", action="store_true")
    parser.add_argument("--no-unload", action="store_true")
    strict_artifacts = parser.add_mutually_exclusive_group()
    strict_artifacts.add_argument("--strict-artifacts", dest="strict_artifacts", action="store_true")
    strict_artifacts.add_argument("--no-strict-artifacts", dest="strict_artifacts", action="store_false")
    strict_weighted = parser.add_mutually_exclusive_group()
    strict_weighted.add_argument("--strict-weighted", dest="strict_weighted", action="store_true")
    strict_weighted.add_argument("--no-strict-weighted", dest="strict_weighted", action="store_false")
    strict_functional = parser.add_mutually_exclusive_group()
    strict_functional.add_argument("--strict-functional", dest="strict_functional", action="store_true")
    strict_functional.add_argument("--no-strict-functional", dest="strict_functional", action="store_false")
    parser.add_argument("--min-functional-presence-rate", type=float, default=0.8)
    parser.add_argument("--min-scenario-grounding-rate", type=float, default=0.8)
    parser.set_defaults(strict_artifacts=None, strict_weighted=None, strict_functional=False)
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    return parser.parse_args()


def reset_output_files(paths: dict[str, Path]) -> None:
    for key in ("progress", "results_jsonl", "summary", "report", "scenario_plan"):
        path = paths[key]
        if path.exists():
            path.unlink()


def main() -> int:
    args = parse_args()
    strict_artifacts = args.strict_artifacts if args.strict_artifacts is not None else args.confirm_run
    strict_weighted = args.strict_weighted if args.strict_weighted is not None else args.confirm_run
    strict_functional = bool(args.strict_functional)
    os.environ["REI_OLLAMA_NUM_CTX"] = str(args.num_ctx)
    os.environ["REI_OLLAMA_NUM_GPU"] = str(args.num_gpu)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_name = f"weighted_manual_audit_{run_id}" if args.manual_audit else f"granite_weighted_short_{run_id}"
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / "output" / "reports" / default_name
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    paths = artifact_paths(output_dir)
    reset_output_files(paths)

    scenarios = selected_scenarios(args.scenario_filter, manual_audit=args.manual_audit)
    profiles = selected_profiles(args.profiles, manual_audit=args.manual_audit)
    plan = build_plan(scenarios, profiles, args.max_cases)
    run_meta = {
        "run_id": run_id,
        "model": args.model,
        "num_ctx": args.num_ctx,
        "num_gpu": args.num_gpu,
        "manual_audit": args.manual_audit,
        "strict_artifacts": strict_artifacts,
        "strict_weighted": strict_weighted,
        "strict_functional": strict_functional,
        "min_functional_presence_rate": args.min_functional_presence_rate,
        "min_scenario_grounding_rate": args.min_scenario_grounding_rate,
        "planned_cases": len(plan),
        "scenario_ids": [scenario["id"] for scenario in scenarios],
        "profiles": profiles,
        "output_dir": repo_relative(output_dir),
        "goal_file": repo_relative(ROOT / "Docs" / "REI_granite_weighted_short_test_goal_2026-05-16.md"),
        "summary": repo_relative(paths["summary"]),
        "report": repo_relative(paths["report"]),
        "results_jsonl": repo_relative(paths["results_jsonl"]),
        "progress": repo_relative(paths["progress"]),
        "scenario_plan": repo_relative(paths["scenario_plan"]),
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    write_json(paths["scenario_plan"], {"run": run_meta, "cases": plan})
    initial_summary = summarize([], {**run_meta, "elapsed_seconds": 0.0}, paths)
    initial_summary["status"] = "planned_only"
    write_json(paths["summary"], initial_summary)

    if not args.confirm_run:
        append_progress(paths["progress"], f"PLAN_ONLY cases={len(plan)} model={args.model}")
        print(f"Plan written to {paths['scenario_plan']}")
        return 0

    append_progress(
        paths["progress"],
        (
            f"START model={args.model} cases={len(plan)} num_ctx={args.num_ctx} num_gpu={args.num_gpu} "
            f"strict_artifacts={strict_artifacts} strict_weighted={strict_weighted} "
            f"strict_functional={strict_functional}"
        ),
    )
    engine = ReiEngine(
        KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"),
        ollama=OllamaProvider(base_url=args.ollama_base_url),
    )
    provider = ProviderSelection(
        provider_mode="ollama",
        racio_model=args.model,
        emocio_model=args.model,
        instinkt_model=args.model,
        synthesis_model=args.model,
        use_llm=True,
        debug_trace=args.debug_trace,
    )

    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for case in plan:
        label = f"{case['case_index']:03d}/{len(plan)} {case['scenario_id']} profile={case['profile']}"
        append_progress(paths["progress"], f"RUN {label}")
        case_started = time.perf_counter()
        try:
            trace, diagnostics = engine.simulate(
                Scenario(title=case["scenario_title"], prompt=case["scenario_prompt"]),
                PsycheState(character_id=case["profile"], acceptance_level=0.55),
                provider,
            )
            trace_payload = trace.model_dump(mode="json")
            evaluation = evaluate_trace(trace_payload, case["profile"], case)
            row = {
                **case,
                "elapsed_seconds": round(time.perf_counter() - case_started, 3),
                "trace": trace_payload,
                "evaluation": evaluation,
                "diagnostics": compact_diagnostics(diagnostics),
            }
            append_progress(
                paths["progress"],
                (
                    f"DONE {label} elapsed={row['elapsed_seconds']} "
                    f"tilt={evaluation.get('synthesis_tilt')} "
                    f"match={evaluation.get('tilt_matches_profile_top')} "
                    f"decision_valid={evaluation.get('decision_valid')} "
                    f"quality={evaluation.get('rei_audit', {}).get('weighted_compromise_quality')}"
                ),
            )
        except Exception as exc:
            row = {
                **case,
                "elapsed_seconds": round(time.perf_counter() - case_started, 3),
                "error": str(exc),
            }
            append_progress(paths["progress"], f"ERROR {label} elapsed={row['elapsed_seconds']} error={exc}")
        rows.append(row)
        write_jsonl(paths["results_jsonl"], row)
        partial = summarize(rows, {**run_meta, "elapsed_seconds": round(time.perf_counter() - started, 3)}, paths)
        partial["status"] = "running"
        write_json(paths["summary"], partial)
        write_report(paths["report"], rows, partial)

    elapsed = round(time.perf_counter() - started, 3)
    summary = summarize(rows, {**run_meta, "elapsed_seconds": elapsed}, paths)
    summary["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    violations = strict_violations(
        summary,
        rows,
        strict_artifacts,
        strict_weighted,
        strict_functional=strict_functional,
        min_functional_presence_rate=args.min_functional_presence_rate,
        min_scenario_grounding_rate=args.min_scenario_grounding_rate,
    )
    if violations:
        summary["status"] = "failed_strict_checks"
        summary["strict_violations"] = violations
        for violation in violations:
            append_progress(paths["progress"], f"STRICT_FAIL {violation}")
    summary["warnings"] = warning_codes(summary)
    write_json(paths["summary"], summary)
    write_report(paths["report"], rows, summary)
    append_progress(
        paths["progress"],
        (
            f"FINISH status={summary['status']} completed={summary['completed_cases']} "
            f"errors={summary['error_count']} elapsed_seconds={elapsed} warnings={','.join(summary.get('warnings') or []) or 'none'}"
        ),
    )
    if not args.no_unload:
        unload_ollama_model(args.model, args.ollama_base_url, paths["progress"])
    if violations:
        return 1
    return 0 if summary["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
