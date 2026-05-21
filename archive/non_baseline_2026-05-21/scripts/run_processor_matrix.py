#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.models import ProviderSelection
from rei.processor_contracts import ProcessorMind
from rei.processor_eval import compare_processor_outputs, run_processor_signal, score_processor_signal
from rei.providers import LMStudioProvider, OllamaProvider


PROCESSOR_SCENARIOS = [
    {
        "id": "public-stage",
        "title": "Public stage under image pressure",
        "prompt": (
            "A person has to step in front of a full auditorium in five minutes. Outside they look calm, "
            "but inside they feel the performance could reveal a crack in their image of competence."
        ),
    },
    {
        "id": "career-family",
        "title": "Career path under family pressure",
        "prompt": (
            "A person must choose one career path. Their family expects a practical respected profession. "
            "They feel pulled toward visible creative work, but fear instability and disappointing people."
        ),
    },
    {
        "id": "business-runway",
        "title": "Business launch with limited runway",
        "prompt": (
            "A person wants to launch a business. They have six months of runway, one paying customer, "
            "and strong excitement, but they also fear that one wrong step could collapse stability."
        ),
    },
    {
        "id": "relationship-boundary",
        "title": "Relationship boundary and trust",
        "prompt": (
            "A person wants to say yes to a relationship request, but something about the request feels too fast. "
            "They want closeness and also fear losing their boundary."
        ),
    },
    {
        "id": "creative-exposure",
        "title": "Creative exposure online",
        "prompt": (
            "A person is about to publish personal creative work online. They want visibility and recognition, "
            "but also fear ridicule, comparison, and becoming too exposed."
        ),
    },
    {
        "id": "lifestyle-choice",
        "title": "Choosing a way of life",
        "prompt": (
            "A person has to choose between a fast urban life, a quieter home-centered life, or a nomadic path. "
            "Each option promises something real and removes something else."
        ),
    },
]

MINDS: list[ProcessorMind] = ["racio", "emocio", "instinkt"]


def choose_provider(mode: str, model: Optional[str], debug_trace: bool) -> ProviderSelection:
    if mode == "deterministic":
        return ProviderSelection(provider_mode="deterministic", use_llm=False, debug_trace=debug_trace)

    lmstudio_models = LMStudioProvider().list_models()
    ollama_models = OllamaProvider().list_models()
    if mode == "lmstudio" or (mode == "auto" and lmstudio_models):
        selected = model or (lmstudio_models[0] if lmstudio_models else ProviderSelection().racio_model)
        return ProviderSelection(
            provider_mode="lmstudio",
            racio_model=selected,
            emocio_model=selected,
            instinkt_model=selected,
            synthesis_model=selected,
            use_llm=True,
            debug_trace=debug_trace,
        )
    if mode == "ollama" or (mode == "auto" and ollama_models):
        selected = model or (ollama_models[0] if ollama_models else "qwen3.5:9b")
        return ProviderSelection(
            provider_mode="ollama",
            racio_model=selected,
            emocio_model=selected,
            instinkt_model=selected,
            synthesis_model=selected,
            use_llm=True,
            debug_trace=debug_trace,
        )
    return ProviderSelection(provider_mode="deterministic", use_llm=False, debug_trace=debug_trace)


def filtered_scenarios(raw_filter: Optional[str]) -> list[dict[str, str]]:
    if not raw_filter:
        return list(PROCESSOR_SCENARIOS)
    tokens = [token.strip().lower() for token in raw_filter.split(",") if token.strip()]
    scenarios = [
        scenario
        for scenario in PROCESSOR_SCENARIOS
        if any(token in scenario["id"].lower() or token in scenario["title"].lower() for token in tokens)
    ]
    if not scenarios:
        raise SystemExit(f"No scenarios matched --scenario-filter={raw_filter!r}")
    return scenarios


def selected_minds(raw_mind: str) -> list[ProcessorMind]:
    if raw_mind == "all":
        return list(MINDS)
    return [raw_mind]  # type: ignore[list-item]


def build_case_plan(
    scenarios: list[dict[str, str]],
    minds: list[ProcessorMind],
    repeat: int,
    max_cases: Optional[int],
) -> list[tuple[int, dict[str, str], ProcessorMind]]:
    cases: list[tuple[int, dict[str, str], ProcessorMind]] = []
    for repeat_index in range(1, repeat + 1):
        for scenario in scenarios:
            for mind in minds:
                cases.append((repeat_index, scenario, mind))
                if max_cases is not None and len(cases) >= max_cases:
                    return cases
    return cases


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_progress(path: Path, line: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {line}\n")


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def counter_markdown(counter: Counter[str]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"`{key}`={value}" for key, value in sorted(counter.items()))


def public_diagnostics(diagnostics: dict[str, Any], debug_trace: bool) -> dict[str, Any]:
    if debug_trace:
        return diagnostics
    return {
        key: value
        for key, value in diagnostics.items()
        if key
        not in {
            "call",
            "failed_diagnostics",
            "first_attempt",
        }
    }


def aggregate_metrics(cases: list[dict[str, Any]], comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    fallback_count = sum(1 for case in cases if case["diagnostics"].get("fallback_used"))
    valid_json_count = sum(1 for case in cases if case["diagnostics"].get("valid_json"))
    style_counter: Counter[str] = Counter()
    rei_counter: Counter[str] = Counter()
    for case in cases:
        style_counter.update(case["score"].get("style_violations", []))
        rei_counter.update(case["score"].get("rei_violations", []))

    def grouped(key: str) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for case in cases:
            buckets[str(case[key])].append(case)
        result: dict[str, Any] = {}
        for bucket, bucket_cases in sorted(buckets.items()):
            bucket_style: Counter[str] = Counter()
            bucket_rei: Counter[str] = Counter()
            for case in bucket_cases:
                bucket_style.update(case["score"].get("style_violations", []))
                bucket_rei.update(case["score"].get("rei_violations", []))
            result[bucket] = {
                "total_calls": len(bucket_cases),
                "fallback_count": sum(1 for case in bucket_cases if case["diagnostics"].get("fallback_used")),
                "fallback_rate": average(
                    [1.0 if case["diagnostics"].get("fallback_used") else 0.0 for case in bucket_cases]
                ),
                "valid_json_rate": average(
                    [1.0 if case["diagnostics"].get("valid_json") else 0.0 for case in bucket_cases]
                ),
                "average_schema_score": average([case["score"]["schema_score"] for case in bucket_cases]),
                "average_role_score": average([case["score"]["role_score"] for case in bucket_cases]),
                "average_distinctness_score": average([case["score"]["distinctness_score"] for case in bucket_cases]),
                "average_overall_score": average([case["score"]["overall_score"] for case in bucket_cases]),
                "style_violations": dict(sorted(bucket_style.items())),
                "rei_violations": dict(sorted(bucket_rei.items())),
            }
        return result

    return {
        "total_calls": len(cases),
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / len(cases), 4) if cases else 0.0,
        "valid_json_rate": round(valid_json_count / len(cases), 4) if cases else 0.0,
        "average_schema_score": average([case["score"]["schema_score"] for case in cases]),
        "average_role_score": average([case["score"]["role_score"] for case in cases]),
        "average_distinctness_score": average([case["score"]["distinctness_score"] for case in cases]),
        "average_overall_score": average([case["score"]["overall_score"] for case in cases]),
        "style_violations": dict(sorted(style_counter.items())),
        "rei_violations": dict(sorted(rei_counter.items())),
        "per_mind": grouped("mind"),
        "per_model": grouped("model"),
        "distinctness_comparisons": comparisons,
        "distinctness_pass_rate": average(
            [1.0 if comparison["comparison"].get("distinctness_pass") else 0.0 for comparison in comparisons]
        ),
    }


def write_aggregate_summary(path: Path, metrics: dict[str, Any], summary: dict[str, Any]) -> None:
    lines = [
        "# Processor Matrix Aggregate Summary",
        "",
        "## Global Metrics",
        "",
        f"- **run_id:** `{summary['run_id']}`",
        f"- **provider:** `{summary['provider']}`",
        f"- **model:** `{summary['model']}`",
        f"- **total_calls:** `{metrics['total_calls']}`",
        f"- **fallback_rate:** `{metrics['fallback_rate']}`",
        f"- **valid_json_rate:** `{metrics['valid_json_rate']}`",
        f"- **average_schema_score:** `{metrics['average_schema_score']}`",
        f"- **average_role_score:** `{metrics['average_role_score']}`",
        f"- **average_distinctness_score:** `{metrics['average_distinctness_score']}`",
        f"- **average_overall_score:** `{metrics['average_overall_score']}`",
        f"- **distinctness_pass_rate:** `{metrics['distinctness_pass_rate']}`",
        "",
        "## Violations",
        "",
        f"- **style_violations:** {counter_markdown(Counter(metrics['style_violations']))}",
        f"- **rei_violations:** {counter_markdown(Counter(metrics['rei_violations']))}",
        "",
        "## Per Mind",
        "",
    ]
    for mind, data in metrics["per_mind"].items():
        lines.extend(
            [
                f"### {mind}",
                "",
                f"- **total_calls:** `{data['total_calls']}`",
                f"- **fallback_rate:** `{data['fallback_rate']}`",
                f"- **valid_json_rate:** `{data['valid_json_rate']}`",
                f"- **average_schema_score:** `{data['average_schema_score']}`",
                f"- **average_role_score:** `{data['average_role_score']}`",
                f"- **average_distinctness_score:** `{data['average_distinctness_score']}`",
                f"- **average_overall_score:** `{data['average_overall_score']}`",
                "",
            ]
        )
    lines.extend(["## Per Model", ""])
    for model, data in metrics["per_model"].items():
        lines.extend(
            [
                f"### {model}",
                "",
                f"- **total_calls:** `{data['total_calls']}`",
                f"- **fallback_rate:** `{data['fallback_rate']}`",
                f"- **valid_json_rate:** `{data['valid_json_rate']}`",
                f"- **average_overall_score:** `{data['average_overall_score']}`",
                "",
            ]
        )
    lines.extend(["## Distinctness", ""])
    if not metrics["distinctness_comparisons"]:
        lines.append("- no full three-processor groups were available")
    for item in metrics["distinctness_comparisons"]:
        comparison = item["comparison"]
        lines.append(
            f"- `{item['scenario_id']}` repeat `{item['repeat_index']}` max_overlap="
            f"`{comparison['max_overlap']}` pass=`{comparison['distinctness_pass']}`"
        )
    lines.extend(["", "## Output Files", ""])
    for key in ["summary", "results_jsonl", "aggregate_markdown", "aggregate_json", "progress"]:
        lines.append(f"- **{key}:** `{summary[key]}`")
    path.write_text("\n".join(lines), encoding="utf-8")


def strict_failures(metrics: dict[str, Any], max_fallback_rate: float, min_overall_score: float) -> list[str]:
    failures: list[str] = []
    if metrics["fallback_rate"] > max_fallback_rate:
        failures.append(f"fallback_rate {metrics['fallback_rate']} exceeds {max_fallback_rate}")
    if metrics["average_overall_score"] < min_overall_score:
        failures.append(f"average_overall_score {metrics['average_overall_score']} below {min_overall_score}")
    if metrics["rei_violations"]:
        failures.append(f"rei_violations present: {metrics['rei_violations']}")
    failed_comparisons = [
        item for item in metrics["distinctness_comparisons"] if not item["comparison"].get("distinctness_pass")
    ]
    if failed_comparisons:
        failures.append(f"{len(failed_comparisons)} distinctness comparisons failed")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run processor-only REI signal evaluations.")
    parser.add_argument("--provider", choices=["auto", "lmstudio", "ollama", "deterministic"], default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--mind", choices=["racio", "emocio", "instinkt", "all"], default="all")
    parser.add_argument("--scenario-filter", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-fallback-rate", type=float, default=0.05)
    parser.add_argument("--min-overall-score", type=float, default=0.75)
    parser.add_argument("--use-memory", action="store_true")
    parser.add_argument("--debug-trace", action="store_true")
    args = parser.parse_args()

    repeat = max(1, args.repeat)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir or ROOT / "output" / "reports" / f"processor_matrix_{run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    jsonl_path = output_dir / "results.jsonl"
    aggregate_md_path = output_dir / "aggregate_summary.md"
    aggregate_json_path = output_dir / "aggregate_summary.json"
    progress_path = output_dir / "progress.log"

    provider = choose_provider(args.provider, args.model, args.debug_trace)
    scenarios = filtered_scenarios(args.scenario_filter)
    minds = selected_minds(args.mind)
    case_plan = build_case_plan(scenarios, minds, repeat, args.max_cases)
    started = time.perf_counter()
    total = len(case_plan)
    write_progress(
        progress_path,
        f"START provider={provider.provider_mode} model={provider.racio_model} mind={args.mind} total={total}",
    )

    cases: list[dict[str, Any]] = []
    grouped_signals: dict[tuple[int, str, str], dict[ProcessorMind, dict[str, Any]]] = defaultdict(dict)
    completed = 0
    for repeat_index, scenario, mind in case_plan:
        completed += 1
        label = f"{completed:03d}/{total} repeat={repeat_index} scenario={scenario['id']} mind={mind}"
        write_progress(progress_path, f"RUN {label}")
        signal, diagnostics = run_processor_signal(
            mind=mind,
            prompt=scenario["prompt"],
            provider=provider,
            model=args.model,
            use_memory=args.use_memory,
        )
        score = score_processor_signal(mind, signal, diagnostics)
        case = {
            "run_id": run_id,
            "case_index": completed,
            "repeat_index": repeat_index,
            "scenario_id": scenario["id"],
            "scenario_title": scenario["title"],
            "scenario_prompt": scenario["prompt"],
            "mind": mind,
            "provider": diagnostics["provider"],
            "model": diagnostics["model"],
            "signal": signal,
            "diagnostics": public_diagnostics(diagnostics, args.debug_trace),
            "score": score,
        }
        grouped_signals[(repeat_index, scenario["id"], diagnostics["model"])][mind] = signal
        append_jsonl(jsonl_path, case)
        cases.append(case)
        write_progress(
            progress_path,
            f"DONE {label} valid_json={diagnostics.get('valid_json')} fallback={diagnostics.get('fallback_used')} "
            f"overall={score['overall_score']}",
        )

    comparisons: list[dict[str, Any]] = []
    for (repeat_index, scenario_id, model), signals in sorted(grouped_signals.items()):
        if all(mind in signals for mind in MINDS):
            comparisons.append(
                {
                    "repeat_index": repeat_index,
                    "scenario_id": scenario_id,
                    "model": model,
                    "comparison": compare_processor_outputs(signals),
                }
            )

    elapsed_seconds = round(time.perf_counter() - started, 3)
    metrics = aggregate_metrics(cases, comparisons)
    failures = strict_failures(metrics, args.max_fallback_rate, args.min_overall_score) if args.strict else []
    summary = {
        "run_id": run_id,
        "provider": provider.provider_mode,
        "model": provider.racio_model,
        "mind": args.mind,
        "total": total,
        "completed": completed,
        "elapsed_seconds": elapsed_seconds,
        "strict": args.strict,
        "strict_pass": not failures,
        "strict_failures": failures,
        "summary": relative_path(summary_path),
        "results_jsonl": relative_path(jsonl_path),
        "aggregate_markdown": relative_path(aggregate_md_path),
        "aggregate_json": relative_path(aggregate_json_path),
        "progress": relative_path(progress_path),
    }
    aggregate_json_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_aggregate_summary(aggregate_md_path, metrics, summary)
    summary_path.write_text(json.dumps({**summary, "metrics": metrics}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_progress(
        progress_path,
        f"FINISH completed={completed} fallbacks={metrics['fallback_count']} elapsed_seconds={elapsed_seconds} strict_pass={not failures}",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
