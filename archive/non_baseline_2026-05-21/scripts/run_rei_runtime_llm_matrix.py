from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
from rei.prompts import EGO_REQUIRED_KEYS, PROCESSOR_FULL_REQUIRED_KEYS, PROCESSOR_REQUIRED_KEYS
from rei.providers import OllamaProvider


SCENARIOS = [
    {
        "id": "meeting_avoidance",
        "title": "Meeting avoidance",
        "relationship_return_expected": False,
        "prompt": "I do not want to attend the meeting. I need to decide whether to go, ask for the agenda, or decline.",
    },
    {
        "id": "quit_job_start_business",
        "title": "Quit job / start business",
        "relationship_return_expected": False,
        "prompt": (
            "I want to quit my job and start a business, but I keep delaying. I say I need more data, "
            "but I also feel excited by freedom and afraid of losing stability."
        ),
    },
    {
        "id": "public_speaking_freeze",
        "title": "Public speaking freeze",
        "relationship_return_expected": False,
        "prompt": (
            "I want to give a public talk. I know it would help my career, but my body freezes when I imagine "
            "people judging me. I want recognition, but I also want to disappear."
        ),
    },
    {
        "id": "romantic_return_loop",
        "title": "Romantic return loop",
        "relationship_return_expected": True,
        "prompt": (
            "A person keeps returning to a relationship that hurts them. They can logically explain why they "
            "should leave, but they still hope it will become beautiful and panic when imagining being alone."
        ),
    },
    {
        "id": "conflict_with_coworker",
        "title": "Conflict with coworker",
        "relationship_return_expected": False,
        "prompt": (
            "I need to address a coworker who keeps interrupting my work and taking credit in meetings. "
            "I want to stay professional, but I also feel angry and exposed."
        ),
    },
    {
        "id": "risky_opportunity",
        "title": "Risky opportunity",
        "relationship_return_expected": False,
        "prompt": (
            "A risky opportunity could accelerate my career, but it would require visible commitment, "
            "uncertain money, and possible public failure. I need to choose whether to pursue it."
        ),
    },
    {
        "id": "expensive_purchase",
        "title": "Expensive purchase",
        "relationship_return_expected": False,
        "prompt": (
            "I am considering an expensive purchase that looks useful and exciting, but it may strain my budget. "
            "I need to decide whether to buy now, wait, or choose a cheaper option."
        ),
    },
    {
        "id": "grief_loss",
        "title": "Grief/loss scenario",
        "relationship_return_expected": False,
        "prompt": (
            "I lost someone important and I need to decide how to handle work, family expectations, and the urge "
            "to withdraw. I feel grief, pressure to function, and fear of being overwhelmed."
        ),
    },
    {
        "id": "creative_project_obsession",
        "title": "Creative project obsession",
        "relationship_return_expected": False,
        "prompt": (
            "I am obsessed with a creative project and keep working late even when my health, money, and relationships "
            "need attention. The project feels alive and important, but it is becoming consuming."
        ),
    },
    {
        "id": "boundary_violation",
        "title": "Boundary violation",
        "relationship_return_expected": False,
        "prompt": (
            "Someone repeatedly crosses a clear boundary after I asked them to stop. I need to decide whether to "
            "confront them, reduce contact, or set a firmer consequence."
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


def provider_for(mode: str, model: str, debug_trace: bool) -> ProviderSelection:
    if mode == "deterministic":
        return ProviderSelection(provider_mode="deterministic", use_llm=False, debug_trace=debug_trace)
    return ProviderSelection(
        provider_mode="ollama",
        racio_model=model,
        emocio_model=model,
        instinkt_model=model,
        synthesis_model=model,
        use_llm=True,
        debug_trace=debug_trace,
    )


def signals_payload(response_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    signals = response_payload.get("signals") or {}
    return {
        "racio": dict(signals.get("racio") or {}),
        "emocio": dict(signals.get("emocio_translated") or {}),
        "instinkt": dict(signals.get("instinkt_translated") or {}),
    }


def distinctness_for(response_payload: dict[str, Any]) -> dict[str, Any]:
    return compare_processor_outputs(signals_payload(response_payload))


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
        if not required or not isinstance(parsed, dict):
            continue
        rows.append(
            {
                "label": label,
                "missing": validate_required_keys(parsed, required),
            }
        )
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


def false_positive_flags(scenario: dict[str, Any], response_payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(response_payload, ensure_ascii=False).lower()
    acceptance = response_payload.get("acceptance") or {}
    task_delegation = acceptance.get("task_delegation") or {}
    return_action = any(str(value).lower() == "return" for key, value in task_delegation.items() if key.endswith("_action_tag"))
    romantic_artifact = any(
        phrase in text
        for phrase in (
            "attachment panic",
            "beautiful-image hope",
            "fear of being alone",
            "return to the relationship",
            "return to my partner",
            "go back to the relationship",
        )
    )
    non_relationship = not bool(scenario.get("relationship_return_expected"))
    return {
        "return_action_on_non_relationship": non_relationship and return_action,
        "romantic_pattern_on_non_relationship": non_relationship and romantic_artifact,
        "fear_of_being_alone_on_non_relationship": non_relationship and "fear of being alone" in text,
        "beautiful_image_hope_on_non_relationship": non_relationship and "beautiful-image hope" in text,
        "coffee_friend_invention": any(phrase in text for phrase in ("coffee", "friend scenario", "with a friend")),
        "meeting_romance_artifact": scenario["id"] == "meeting_avoidance" and romantic_artifact,
    }


def run_case(
    engine: ReiEngine,
    scenario: dict[str, Any],
    profile: str,
    provider: ProviderSelection,
) -> dict[str, Any]:
    started = time.perf_counter()
    response, diagnostics = engine.run_rei_cycle(
        scenario["prompt"],
        character_profile=profile,
        provider=provider,
    )
    response_payload = response.model_dump(mode="json")
    missing = final_missing_required_keys(response_payload)
    raw_missing = raw_call_missing_required_keys(diagnostics)
    return {
        "provider": provider.provider_mode,
        "model": provider.racio_model if provider.use_llm else "deterministic",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "output": response_payload,
        "fallback_count": len(diagnostics.get("fallbacks", [])),
        "fallbacks": diagnostics.get("fallbacks", []),
        "missing_required_keys": missing,
        "raw_call_missing_required_keys": raw_missing,
        "token_count": token_count(diagnostics),
        "processor_distinctness": distinctness_for(response_payload),
        "false_positive_pattern_flags": false_positive_flags(scenario, response_payload),
        "diagnostics": diagnostics,
    }


def summarize_case(case: dict[str, Any]) -> dict[str, Any]:
    live = case.get("live_llm") or {}
    deterministic = case.get("deterministic") or {}
    live_flags = live.get("false_positive_pattern_flags") or {}
    det_flags = deterministic.get("false_positive_pattern_flags") or {}
    return {
        "scenario_id": case["scenario_id"],
        "title": case["scenario_title"],
        "deterministic_fallback_count": deterministic.get("fallback_count"),
        "live_fallback_count": live.get("fallback_count"),
        "live_missing_required_keys": live.get("missing_required_keys"),
        "live_raw_call_missing_required_keys": live.get("raw_call_missing_required_keys"),
        "live_token_total": ((live.get("token_count") or {}).get("totals") or {}).get("total"),
        "deterministic_max_distinctness_jaccard": ((deterministic.get("processor_distinctness") or {}).get("max_overlap")),
        "live_max_distinctness_jaccard": ((live.get("processor_distinctness") or {}).get("max_overlap")),
        "deterministic_false_positive_flags": det_flags,
        "live_false_positive_flags": live_flags,
    }


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = [summarize_case(case) for case in cases]
    return {
        "case_count": len(cases),
        "live_total_fallback_count": sum(int(item.get("live_fallback_count") or 0) for item in summaries),
        "deterministic_total_fallback_count": sum(int(item.get("deterministic_fallback_count") or 0) for item in summaries),
        "live_total_tokens": sum(int(item.get("live_token_total") or 0) for item in summaries),
        "live_false_positive_cases": [
            item["scenario_id"]
            for item in summaries
            if any(bool(value) for value in (item.get("live_false_positive_flags") or {}).values())
        ],
        "deterministic_false_positive_cases": [
            item["scenario_id"]
            for item in summaries
            if any(bool(value) for value in (item.get("deterministic_false_positive_flags") or {}).values())
        ],
        "cases": summaries,
    }


def write_markdown(path: Path, run: dict[str, Any], summary: dict[str, Any]) -> None:
    lines = [
        "# REI Runtime LLM Matrix",
        "",
        f"- Run id: `{run['run_id']}`",
        f"- Model: `{run['model']}`",
        f"- Profile: `{run['profile']}`",
        f"- Ollama context: `{run['num_ctx']}`",
        f"- Ollama GPU layers: `{run['num_gpu']}`",
        f"- Cases: `{summary['case_count']}`",
        f"- Live fallback count: `{summary['live_total_fallback_count']}`",
        f"- Live total tokens: `{summary['live_total_tokens']}`",
        "",
        "| Scenario | Live fallbacks | Live tokens | Live max Jaccard | Live false-positive flags |",
        "|---|---:|---:|---:|---|",
    ]
    for item in summary["cases"]:
        flags = ", ".join(key for key, value in item["live_false_positive_flags"].items() if value) or "none"
        lines.append(
            f"| `{item['scenario_id']}` | `{item['live_fallback_count']}` | `{item['live_token_total']}` | "
            f"`{item['live_max_distinctness_jaccard']}` | {flags} |"
        )
    lines.append("")
    lines.append("## Case Summaries")
    lines.append("")
    for item in summary["cases"]:
        lines.extend(
            [
                f"### {item['scenario_id']}",
                "",
                f"- Deterministic fallbacks: `{item['deterministic_fallback_count']}`",
                f"- Live fallbacks: `{item['live_fallback_count']}`",
                f"- Live token total: `{item['live_token_total']}`",
                f"- Live raw missing keys: `{item['live_raw_call_missing_required_keys']}`",
                f"- Live final missing keys: `{item['live_missing_required_keys']}`",
                f"- Deterministic false-positive flags: `{item['deterministic_false_positive_flags']}`",
                f"- Live false-positive flags: `{item['live_false_positive_flags']}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic and live Ollama REI runtime scenario checks.")
    parser.add_argument("--model", default="granite4.1:30b")
    parser.add_argument("--profile", default="R=E=I")
    parser.add_argument("--num-ctx", type=int, default=65536)
    parser.add_argument("--num-gpu", type=int, default=999)
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--scenario-filter", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ["REI_OLLAMA_NUM_CTX"] = str(args.num_ctx)
    os.environ["REI_OLLAMA_NUM_GPU"] = str(args.num_gpu)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / "output" / "reports" / "rei_runtime_llm_matrix" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "progress.log"
    jsonl_path = output_dir / "cases.jsonl"
    cases_path = output_dir / "cases.json"
    summary_path = output_dir / "summary.json"
    markdown_path = output_dir / "summary.md"

    terms = [term.strip().lower() for term in str(args.scenario_filter or "").split(",") if term.strip()]
    scenarios = [
        scenario
        for scenario in SCENARIOS
        if not terms or any(term in scenario["id"].lower() or term in scenario["title"].lower() for term in terms)
    ]
    run_meta = {
        "run_id": run_id,
        "model": args.model,
        "profile": args.profile,
        "num_ctx": args.num_ctx,
        "num_gpu": args.num_gpu,
        "output_dir": str(output_dir),
        "scenario_count": len(scenarios),
    }
    write_json(output_dir / "run.json", run_meta)
    write_progress(
        progress_path,
        f"START run_id={run_id} model={args.model} num_ctx={args.num_ctx} num_gpu={args.num_gpu} scenarios={len(scenarios)}",
    )

    available_models = OllamaProvider(base_url=args.ollama_base_url).list_models(timeout_seconds=10)
    if args.model not in available_models:
        write_progress(progress_path, f"WARNING requested_model_not_listed model={args.model} available={available_models}")

    engine = ReiEngine(
        KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"),
        ollama=OllamaProvider(base_url=args.ollama_base_url),
    )
    deterministic_provider = provider_for("deterministic", args.model, debug_trace=True)
    live_provider = provider_for("ollama", args.model, debug_trace=True)

    cases: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios, start=1):
        write_progress(progress_path, f"RUN {index}/{len(scenarios)} {scenario['id']} deterministic")
        deterministic = run_case(engine, scenario, args.profile, deterministic_provider)
        write_progress(progress_path, f"DONE {index}/{len(scenarios)} {scenario['id']} deterministic")

        write_progress(progress_path, f"RUN {index}/{len(scenarios)} {scenario['id']} live_llm")
        try:
            live = run_case(engine, scenario, args.profile, live_provider)
            write_progress(
                progress_path,
                f"DONE {index}/{len(scenarios)} {scenario['id']} live_llm "
                f"fallbacks={live['fallback_count']} tokens={live['token_count']['totals']['total']}",
            )
        except Exception as exc:
            live = {
                "provider": "ollama",
                "model": args.model,
                "error": str(exc),
                "fallback_count": 1,
                "fallbacks": [{"mind": "run", "reason": str(exc)}],
                "missing_required_keys": {},
                "raw_call_missing_required_keys": [],
                "token_count": {"totals": {"prompt": 0, "eval": 0, "total": 0}, "calls": []},
                "processor_distinctness": {},
                "false_positive_pattern_flags": {},
                "diagnostics": {},
            }
            write_progress(progress_path, f"ERROR {index}/{len(scenarios)} {scenario['id']} live_llm error={exc}")

        case = {
            "run_id": run_id,
            "case_index": index,
            "scenario_id": scenario["id"],
            "scenario_title": scenario["title"],
            "scenario_prompt": scenario["prompt"],
            "profile": args.profile,
            "deterministic": deterministic,
            "live_llm": live,
        }
        append_jsonl(jsonl_path, case)
        cases.append(case)
        write_json(cases_path, cases)
        summary = aggregate(cases)
        write_json(summary_path, summary)
        write_markdown(markdown_path, run_meta, summary)

    summary = aggregate(cases)
    write_json(cases_path, cases)
    write_json(summary_path, summary)
    write_markdown(markdown_path, run_meta, summary)
    write_progress(progress_path, f"COMPLETE run_id={run_id} cases={len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
