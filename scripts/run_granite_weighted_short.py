from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
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

PROFILE_TOP_MINDS = {
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

SCENARIOS = [
    {
        "id": "pure-budget-allocation",
        "title": "Pure budget allocation",
        "expected_pressure": "racio",
        "prompt": (
            "A project lead has a fixed budget and must allocate it between testing, design, infrastructure, "
            "and marketing. There is no social drama, no bodily threat, and no image wound; the decision is "
            "mainly about constraints, sequence, and opportunity cost."
        ),
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
    },
    {
        "id": "business-runway",
        "title": "Business launch with runway",
        "expected_pressure": "mixed",
        "prompt": (
            "A person wants to launch a business and already has six months of runway, one paying customer, "
            "and strong excitement, but still fears that a wrong move could collapse stability."
        ),
    },
    {
        "id": "creative-status-risk",
        "title": "Creative status risk",
        "expected_pressure": "emocio",
        "prompt": (
            "An artist must choose between a safe accepted exhibition and a bold personal piece that could be "
            "admired or mocked. The bold option feels alive, visible, and dangerous to their pride."
        ),
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
    },
]

REPETITION_PATTERNS = [
    "bounded test",
    "minimum safety condition",
    "responsible planning",
    "reversible",
    "stop condition",
    "safety requirement",
    "winning coalition",
    "blocked",
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


def selected_scenarios(raw_filter: str | None) -> list[dict[str, str]]:
    if not raw_filter:
        return list(SCENARIOS)
    tokens = [token.strip().lower() for token in raw_filter.split(",") if token.strip()]
    chosen = [
        scenario
        for scenario in SCENARIOS
        if any(token in scenario["id"].lower() or token in scenario["title"].lower() for token in tokens)
    ]
    if not chosen:
        raise SystemExit(f"No selected scenario matched {raw_filter!r}")
    return chosen


def selected_profiles(raw_profiles: str | None) -> list[str]:
    if not raw_profiles:
        return list(PROFILES)
    profiles = [item.strip() for item in raw_profiles.split(",") if item.strip()]
    unknown = [profile for profile in profiles if profile not in PROFILES]
    if unknown:
        raise SystemExit(f"Unknown profiles: {', '.join(unknown)}")
    return profiles


def build_plan(scenarios: list[dict[str, str]], profiles: list[str], max_cases: int | None) -> list[dict[str, Any]]:
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
                    "profile": profile,
                    "profile_top_minds": PROFILE_TOP_MINDS[profile],
                }
            )
    if max_cases:
        return plan[:max_cases]
    return plan


def repetition_hits(payload: dict[str, Any]) -> dict[str, int]:
    text = json.dumps(payload, ensure_ascii=False).lower()
    hits: dict[str, int] = {}
    for phrase in REPETITION_PATTERNS:
        count = len(re.findall(re.escape(phrase), text))
        if count:
            hits[phrase] = count
    return hits


def compact_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    compact = dict(diagnostics)
    compact["llm_calls"] = [
        {key: value for key, value in call.items() if key not in {"request", "response"}}
        for call in diagnostics.get("llm_calls", [])
    ]
    return compact


def evaluate_trace(trace_payload: dict[str, Any], profile: str) -> dict[str, Any]:
    synthesis = trace_payload.get("synthesis_turn", {})
    contributions = synthesis.get("weighted_contributions") or {}
    ranking = synthesis.get("contribution_ranking") or []
    tilt = synthesis.get("synthesis_tilt")
    expected_top = PROFILE_TOP_MINDS[profile]
    top_share = max(contributions.values()) if contributions else 0.0
    bottom_share = min(contributions.values()) if contributions else 0.0
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
        "dominant_coalition_legacy": synthesis.get("dominant_coalition"),
        "blocked_mind_legacy": synthesis.get("blocked_mind"),
        "decision_choice": (synthesis.get("decision") or {}).get("chosen_option"),
        "decision_rationale": (synthesis.get("decision") or {}).get("rationale"),
        "final_monologue": synthesis.get("final_monologue"),
        "main_agreement": synthesis.get("main_agreement"),
        "main_conflict": synthesis.get("main_conflict"),
        "repetition_hits": repetition_hits(synthesis),
    }


def summarize(rows: list[dict[str, Any]], run_meta: dict[str, Any]) -> dict[str, Any]:
    completed = [row for row in rows if not row.get("error")]
    errors = [row for row in rows if row.get("error")]
    tilt_counts = Counter(row.get("evaluation", {}).get("synthesis_tilt") for row in completed)
    underrepresented_counts = Counter(row.get("evaluation", {}).get("underrepresented_signal") for row in completed)
    scenario_match: dict[str, dict[str, int]] = defaultdict(lambda: {"matched": 0, "total": 0})
    profile_match: dict[str, dict[str, int]] = defaultdict(lambda: {"matched": 0, "total": 0})
    repetition = Counter()
    for row in completed:
        evaluation = row["evaluation"]
        matched = bool(evaluation.get("tilt_matches_profile_top"))
        scenario_match[row["scenario_id"]]["total"] += 1
        profile_match[row["profile"]]["total"] += 1
        if matched:
            scenario_match[row["scenario_id"]]["matched"] += 1
            profile_match[row["profile"]]["matched"] += 1
        repetition.update(evaluation.get("repetition_hits") or {})

    def with_rates(items: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
        return {
            key: {
                **value,
                "rate": round(value["matched"] / value["total"], 3) if value["total"] else 0.0,
            }
            for key, value in sorted(items.items())
        }

    return {
        **run_meta,
        "status": "completed" if not errors else "completed_with_errors",
        "completed_cases": len(completed),
        "error_count": len(errors),
        "tilt_counts": dict(sorted((str(k), v) for k, v in tilt_counts.items())),
        "underrepresented_counts": dict(sorted((str(k), v) for k, v in underrepresented_counts.items())),
        "profile_top_match": {
            "matched": sum(1 for row in completed if row["evaluation"].get("tilt_matches_profile_top")),
            "total": len(completed),
            "rate": round(
                sum(1 for row in completed if row["evaluation"].get("tilt_matches_profile_top")) / len(completed),
                3,
            )
            if completed
            else 0.0,
        },
        "scenario_profile_match": with_rates(scenario_match),
        "profile_match": with_rates(profile_match),
        "repetition_hits": dict(sorted(repetition.items())),
    }


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
        f"- **elapsed_seconds:** `{summary['elapsed_seconds']}`",
        f"- **profile_top_match:** `{summary['profile_top_match']['matched']}/{summary['profile_top_match']['total']}` (`{summary['profile_top_match']['rate']}`)",
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
            json.dumps(summary["tilt_counts"], ensure_ascii=False, indent=2),
            "",
            "## Repetition Hits",
            "",
            json.dumps(summary["repetition_hits"], ensure_ascii=False, indent=2),
            "",
            "## Cases",
            "",
            "| # | Scenario | Profile | Tilt | Top Match | Underrepresented | Decision |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        if row.get("error"):
            lines.append(
                f"| `{row['case_index']}` | `{row['scenario_id']}` | `{row['profile']}` | `error` |  |  | {row['error']} |"
            )
            continue
        evaluation = row["evaluation"]
        decision = evaluation.get("decision_choice") or ""
        lines.append(
            f"| `{row['case_index']}` | `{row['scenario_id']}` | `{row['profile']}` | "
            f"`{evaluation.get('synthesis_tilt')}` | `{evaluation.get('tilt_matches_profile_top')}` | "
            f"`{evaluation.get('underrepresented_signal')}` | {decision} |"
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
    parser.add_argument("--confirm-run", action="store_true")
    parser.add_argument("--debug-trace", action="store_true")
    parser.add_argument("--no-unload", action="store_true")
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ["REI_OLLAMA_NUM_CTX"] = str(args.num_ctx)
    os.environ["REI_OLLAMA_NUM_GPU"] = str(args.num_gpu)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / "output" / "reports" / f"granite_weighted_short_{run_id}"
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    progress_path = output_dir / "progress.log"
    results_path = output_dir / "results.jsonl"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.md"
    plan_path = output_dir / "scenario_plan.json"

    scenarios = selected_scenarios(args.scenario_filter)
    profiles = selected_profiles(args.profiles)
    plan = build_plan(scenarios, profiles, args.max_cases)
    run_meta = {
        "run_id": run_id,
        "model": args.model,
        "num_ctx": args.num_ctx,
        "num_gpu": args.num_gpu,
        "planned_cases": len(plan),
        "scenario_ids": [scenario["id"] for scenario in scenarios],
        "profiles": profiles,
        "output_dir": str(output_dir),
        "goal_file": str(ROOT / "Docs" / "REI_granite_weighted_short_test_goal_2026-05-16.md"),
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    write_json(plan_path, {"run": run_meta, "cases": plan})
    write_json(summary_path, {**run_meta, "status": "planned_only", "completed_cases": 0, "error_count": 0})

    if not args.confirm_run:
        append_progress(progress_path, f"PLAN_ONLY cases={len(plan)} model={args.model}")
        print(f"Plan written to {plan_path}")
        return 0

    append_progress(progress_path, f"START model={args.model} cases={len(plan)} num_ctx={args.num_ctx} num_gpu={args.num_gpu}")
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
        append_progress(progress_path, f"RUN {label}")
        case_started = time.perf_counter()
        try:
            trace, diagnostics = engine.simulate(
                Scenario(title=case["scenario_title"], prompt=case["scenario_prompt"]),
                PsycheState(character_id=case["profile"], acceptance_level=0.55),
                provider,
            )
            trace_payload = trace.model_dump(mode="json")
            evaluation = evaluate_trace(trace_payload, case["profile"])
            row = {
                **case,
                "elapsed_seconds": round(time.perf_counter() - case_started, 3),
                "trace": trace_payload,
                "evaluation": evaluation,
                "diagnostics": compact_diagnostics(diagnostics),
            }
            append_progress(
                progress_path,
                (
                    f"DONE {label} elapsed={row['elapsed_seconds']} "
                    f"tilt={evaluation.get('synthesis_tilt')} match={evaluation.get('tilt_matches_profile_top')}"
                ),
            )
        except Exception as exc:
            row = {
                **case,
                "elapsed_seconds": round(time.perf_counter() - case_started, 3),
                "error": str(exc),
            }
            append_progress(progress_path, f"ERROR {label} elapsed={row['elapsed_seconds']} error={exc}")
        rows.append(row)
        write_jsonl(results_path, row)
        partial = summarize(rows, {**run_meta, "elapsed_seconds": round(time.perf_counter() - started, 3)})
        partial["status"] = "running"
        write_json(summary_path, partial)
        write_report(report_path, rows, partial)

    elapsed = round(time.perf_counter() - started, 3)
    summary = summarize(rows, {**run_meta, "elapsed_seconds": elapsed})
    summary["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(summary_path, summary)
    write_report(report_path, rows, summary)
    append_progress(progress_path, f"FINISH completed={summary['completed_cases']} errors={summary['error_count']} elapsed_seconds={elapsed}")
    if not args.no_unload:
        unload_ollama_model(args.model, args.ollama_base_url, progress_path)
    return 0 if summary["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
