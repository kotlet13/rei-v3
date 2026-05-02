from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.engine import ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection
from rei.providers import LMStudioProvider, OllamaProvider


PROFILES = [
    "R>(E=I)",
    "E>(R=I)",
    "I>(R=E)",
    "(R=E)>I",
    "(R=I)>E",
    "(E=I)>R",
    "R>E>I",
    "R>I>E",
    "E>R>I",
    "E>I>R",
    "I>R>E",
    "I>E>R",
    "R=E=I",
]

SCENARIOS = [
    {
        "id": "job_quit_business_delay",
        "title": "Quit job / start business delay",
        "prompt": (
            "I want to quit my job and start a business, but I keep delaying. "
            "I say I need more data, but I also feel excited by freedom and afraid of losing stability."
        ),
    },
    {
        "id": "relationship_return",
        "title": "Returning to a painful relationship",
        "prompt": (
            "A person keeps returning to a relationship that hurts them. They can logically explain why "
            "they should leave, but they still hope it will become beautiful and panic when imagining being alone."
        ),
    },
    {
        "id": "public_talk_freeze",
        "title": "Public talk freeze",
        "prompt": (
            "I want to give a public talk. I know it would help my career, but my body freezes when I imagine "
            "people judging me. I want recognition, but I also want to disappear."
        ),
    },
]


def choose_provider(mode: str, model: Optional[str]) -> ProviderSelection:
    if mode == "deterministic":
        return ProviderSelection(provider_mode="deterministic", use_llm=False, debug_trace=False)

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
            debug_trace=False,
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
            debug_trace=False,
        )
    return ProviderSelection(provider_mode="deterministic", use_llm=False, debug_trace=False)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_progress(path: Path, line: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {line}\n")


def signal_section(title: str, signal: dict[str, Any]) -> str:
    lines = [f"### {title}", ""]
    for key, value in signal.items():
        if isinstance(value, list):
            rendered = "; ".join(str(item) for item in value)
        elif isinstance(value, dict):
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        lines.append(f"- **{key}:** {rendered}")
    lines.append("")
    return "\n".join(lines)


def case_markdown(case: dict[str, Any]) -> str:
    response = case["response"]
    signals = response["signals"]
    acceptance = response["acceptance"]
    ego = response["ego_resultant"]
    lines = [
        f"## {case['scenario_title']} / {case['profile']}",
        "",
        f"**Situation:** {case['scenario_prompt']}",
        "",
        signal_section("Conscious Racio Monologue", signals["racio"]),
        signal_section("Translated Emocio Signal", signals["emocio_translated"]),
        signal_section("Translated Instinkt Signal", signals["instinkt_translated"]),
        "### Acceptance",
        "",
    ]
    for key, value in acceptance.items():
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
        lines.append(f"- **{key}:** {rendered}")
    lines.extend(["", "### Ego Resultant", ""])
    for key, value in ego.items():
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
        if isinstance(value, list):
            rendered = "; ".join(str(item) for item in value)
        lines.append(f"- **{key}:** {rendered}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 13 REI profiles across 3 scenarios.")
    parser.add_argument("--provider", choices=["auto", "lmstudio", "ollama", "deterministic"], default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir or ROOT / "output" / "reports" / f"rei_cycle_matrix_{run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "results.jsonl"
    markdown_path = output_dir / "report.md"
    progress_path = output_dir / "progress.log"
    summary_path = output_dir / "summary.json"

    provider = choose_provider(args.provider, args.model)
    engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
    total = len(SCENARIOS) * len(PROFILES)
    started = time.perf_counter()

    write_progress(progress_path, f"START provider={provider.provider_mode} model={provider.racio_model} total={total}")
    markdown_path.write_text(
        "# REI Cycle Matrix Report\n\n"
        f"- Run id: `{run_id}`\n"
        f"- Provider: `{provider.provider_mode}`\n"
        f"- Model: `{provider.racio_model}`\n"
        f"- Cases: `{total}`\n\n",
        encoding="utf-8",
    )

    completed = 0
    fallbacks = 0
    for scenario in SCENARIOS:
        for profile in PROFILES:
            completed += 1
            label = f"{completed:02d}/{total} {scenario['id']} profile={profile}"
            write_progress(progress_path, f"RUN {label}")
            try:
                response, diagnostics = engine.run_rei_cycle(
                    scenario["prompt"],
                    character_profile=profile,
                    provider=provider,
                )
                response_payload = response.model_dump(mode="json")
                fallbacks += len(diagnostics.get("fallbacks", []))
                case = {
                    "run_id": run_id,
                    "case_index": completed,
                    "scenario_id": scenario["id"],
                    "scenario_title": scenario["title"],
                    "scenario_prompt": scenario["prompt"],
                    "profile": profile,
                    "response": response_payload,
                    "fallbacks": diagnostics.get("fallbacks", []),
                }
                append_jsonl(jsonl_path, case)
                with markdown_path.open("a", encoding="utf-8") as handle:
                    handle.write(case_markdown(case))
                leading = response.ego_resultant.leading_mind
                level = response.acceptance.overall_level
                write_progress(progress_path, f"DONE {label} leading={leading} acceptance={level}")
            except Exception as exc:
                fallbacks += 1
                error_case = {
                    "run_id": run_id,
                    "case_index": completed,
                    "scenario_id": scenario["id"],
                    "profile": profile,
                    "error": str(exc),
                }
                append_jsonl(jsonl_path, error_case)
                write_progress(progress_path, f"ERROR {label} error={exc}")

    elapsed_seconds = round(time.perf_counter() - started, 3)
    summary = {
        "run_id": run_id,
        "provider": provider.provider_mode,
        "model": provider.racio_model,
        "total": total,
        "completed": completed,
        "fallback_count": fallbacks,
        "elapsed_seconds": elapsed_seconds,
        "jsonl": str(jsonl_path),
        "markdown": str(markdown_path),
        "progress": str(progress_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_progress(progress_path, f"FINISH completed={completed} fallbacks={fallbacks} elapsed_seconds={elapsed_seconds}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
