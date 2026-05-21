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

from rei.engine import ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection
from rei.normalization import normalize_mind_name
from rei.providers import LMStudioProvider, OllamaProvider


SIMULATION_CAVEAT = (
    "This is a REI-inspired reflection model, not diagnosis, therapy, consciousness, "
    "or scientific proof."
)

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
        "expected_driver": "instinkt",
        "prompt": (
            "I want to quit my job and start a business, but I keep delaying. "
            "I say I need more data, but I also feel excited by freedom and afraid of losing stability."
        ),
    },
    {
        "id": "public_talk_freeze",
        "title": "Public talk freeze",
        "expected_driver": "instinkt",
        "prompt": (
            "I want to give a public talk. I know it would help my career, but my body freezes when I imagine "
            "people judging me. I want recognition, but I also want to disappear."
        ),
    },
    {
        "id": "relationship_return",
        "title": "Returning to a painful relationship",
        "expected_driver": "instinkt_or_emocio",
        "prompt": (
            "A person keeps returning to a relationship that hurts them. They can logically explain why they "
            "should leave, but they still hope it will become beautiful and panic when imagining being alone."
        ),
    },
    {
        "id": "architecture_choice",
        "title": "Architecture choice",
        "expected_driver": "racio",
        "prompt": (
            "A developer must choose between three technical architectures. One is fast but brittle, one is "
            "slower but reliable, and one is elegant but untested. The decision depends on timeline, "
            "maintenance cost, and known constraints."
        ),
    },
    {
        "id": "budget_allocation",
        "title": "Budget allocation",
        "expected_driver": "racio",
        "prompt": (
            "A project lead has a fixed budget and must allocate it between testing, design, infrastructure, "
            "and marketing. There is no emotional conflict, but the tradeoffs are complex."
        ),
    },
    {
        "id": "exam_planning",
        "title": "Exam planning",
        "expected_driver": "racio",
        "prompt": (
            "A student has ten days before an exam and must choose how to divide study time across four topics "
            "with different difficulty and scoring weight."
        ),
    },
    {
        "id": "artist_safe_vs_bold",
        "title": "Artist safe vs bold",
        "expected_driver": "emocio",
        "prompt": (
            "An artist must choose between a safe exhibition that will be accepted and a bold personal piece "
            "that could be admired or mocked. The bold option feels alive."
        ),
    },
    {
        "id": "impress_someone",
        "title": "Impress someone",
        "expected_driver": "emocio",
        "prompt": (
            "A person wants to impress someone they admire. They consider making a dramatic gesture that could "
            "create connection or humiliation."
        ),
    },
    {
        "id": "performance_status_choice",
        "title": "Performance status choice",
        "expected_driver": "emocio",
        "prompt": (
            "A performer must decide whether to take a visible role with status and applause or a smaller "
            "reliable role that nobody will notice."
        ),
    },
    {
        "id": "move_abroad",
        "title": "Move abroad",
        "expected_driver": "mixed",
        "prompt": (
            "A person considers moving abroad. It is rationally possible, emotionally exciting, and frightening "
            "because it may weaken family closeness and safety."
        ),
    },
    {
        "id": "confront_boundary_violation",
        "title": "Confront boundary violation",
        "expected_driver": "mixed",
        "prompt": (
            "A person needs to confront a friend who repeatedly crosses a boundary. They want honesty, fear "
            "losing the relationship, and want to preserve dignity."
        ),
    },
    {
        "id": "launch_with_runway",
        "title": "Launch with runway",
        "expected_driver": "mixed",
        "prompt": (
            "A person wants to launch a business and already has six months of runway, one paying customer, "
            "and strong excitement, but still feels some fear."
        ),
    },
]


def choose_provider(mode: str, model: Optional[str], no_llm: bool, debug_trace: bool) -> ProviderSelection:
    if no_llm or mode == "deterministic":
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


def markdown_value(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def truncate(value: Any, limit: int = 96) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def signal_section(title: str, signal: dict[str, Any]) -> str:
    lines = [f"### {title}", ""]
    for key, value in signal.items():
        lines.append(f"- **{key}:** {markdown_value(value)}")
    lines.append("")
    return "\n".join(lines)


def baseline_pros_cons(prompt: str) -> dict[str, Any]:
    lower = prompt.lower()
    risks = []
    if any(token in lower for token in ["risk", "stability", "fear", "freeze", "panic", "humiliation"]):
        risks.append("A pressure signal may distort timing or make the next step too large.")
    if any(token in lower for token in ["budget", "cost", "timeline", "exam", "architecture"]):
        risks.append("A poor sequence or missing constraint may create avoidable rework.")
    if not risks:
        risks.append("The input is limited, so the first step should stay reversible.")
    return {
        "pros": [
            "A bounded choice can create real feedback.",
            "The situation contains enough information for a small next step.",
        ],
        "cons": [
            "The full outcome is uncertain.",
            "A large irreversible move could amplify the cost of a wrong read.",
        ],
        "risks": risks,
        "next_step": "Define one reversible test, one stop condition, and the evidence needed for the next decision.",
    }


def baseline_plain_reflection(
    prompt: str,
    engine: ReiEngine,
    provider: ProviderSelection,
) -> dict[str, Any]:
    deterministic = {
        "summary": "The dilemma contains competing pressures that should be converted into a small practical test.",
        "likely_action_under_pressure": "Delay or choose the most immediately relieving option unless the next step is bounded.",
        "recommended_next_step": "Choose one reversible action and define what would count as useful feedback.",
        "uncertainty": "This baseline does not use REI structure and is based only on the written prompt.",
    }
    if provider.provider_mode not in {"ollama", "lmstudio"} or not provider.use_llm:
        return deterministic

    diagnostics: dict[str, Any] = {"llm_calls": [], "fallbacks": []}
    try:
        payload = engine._call_cycle_json(  # noqa: SLF001 - runner intentionally reuses provider JSON coercion.
            provider=provider,
            label="plain_llm_reflection",
            model=provider.synthesis_model,
            system=(
                "You are a helpful reflective assistant. Analyze the user's dilemma and suggest a practical next step. "
                "Do not use REI terms. Return one JSON object only."
            ),
            user_payload={
                "prompt": prompt,
                "required_json": {
                    "summary": "",
                    "likely_action_under_pressure": "",
                    "recommended_next_step": "",
                    "uncertainty": "",
                },
            },
            required_keys=["summary", "likely_action_under_pressure", "recommended_next_step", "uncertainty"],
            temperature=0.25,
            top_p=0.85,
            num_predict=800,
            diagnostics=diagnostics,
        )
    except Exception as exc:
        return {**deterministic, "fallback_reason": str(exc)}
    return {key: str(payload.get(key) or deterministic[key]) for key in deterministic}


def deterministic_rei_baseline(engine: ReiEngine, prompt: str, profile: str) -> dict[str, Any]:
    response, diagnostics = engine.run_rei_cycle(
        prompt,
        character_profile=profile,
        provider=ProviderSelection(provider_mode="deterministic", use_llm=False, debug_trace=False),
    )
    ego = response.ego_resultant
    return {
        "profile_leader": ego.profile_leader,
        "situational_driver": ego.situational_driver,
        "resultant_leader_under_pressure": ego.resultant_leader_under_pressure,
        "acceptance_quality": response.acceptance.acceptance_quality,
        "likely_action_under_pressure": ego.likely_action_under_pressure,
        "fallback_count": len(diagnostics.get("fallbacks", [])),
    }


def baselines_for_case(
    prompt: str,
    profile: str,
    engine: ReiEngine,
    provider: ProviderSelection,
) -> dict[str, Any]:
    return {
        "plain_llm_reflection": baseline_plain_reflection(prompt, engine, provider),
        "pros_cons": baseline_pros_cons(prompt),
        "deterministic_rei_fallback": deterministic_rei_baseline(engine, prompt, profile),
    }


def case_driver_fields(case: dict[str, Any]) -> dict[str, str]:
    response = case.get("response") or {}
    ego = response.get("ego_resultant") or {}
    acceptance = response.get("acceptance") or {}
    profile_leader = normalize_mind_name(ego.get("profile_leader"))
    situational_driver = normalize_mind_name(ego.get("situational_driver"))
    resultant = normalize_mind_name(
        ego.get("resultant_leader_under_pressure") or ego.get("leading_mind")
    )
    return {
        "profile_leader": profile_leader,
        "situational_driver": situational_driver,
        "resultant_leader_under_pressure": resultant,
        "behavioral_alignment": str(acceptance.get("behavioral_alignment") or "unknown"),
        "acceptance_quality": str(acceptance.get("acceptance_quality") or "unknown"),
    }


def enum_normalization_count(case: dict[str, Any]) -> int:
    response = case.get("response") or {}
    ego = response.get("ego_resultant") or {}
    fields = [
        "profile_leader",
        "situational_driver",
        "resultant_leader_under_pressure",
        "leading_mind",
        "resisting_mind",
        "ignored_or_misrepresented_mind",
    ]
    count = 0
    for field in fields:
        raw = ego.get(field)
        if raw is None:
            continue
        normalized = normalize_mind_name(raw)
        if str(raw).strip() != normalized:
            count += 1
    return count


def case_summary_row(case: dict[str, Any]) -> str:
    fields = case_driver_fields(case)
    ego = case["response"]["ego_resultant"]
    return (
        f"| {case['scenario_id']} | {case['profile']} | {fields['profile_leader']} | "
        f"{fields['situational_driver']} | {fields['resultant_leader_under_pressure']} | "
        f"{fields['behavioral_alignment']} | {fields['acceptance_quality']} | "
        f"{truncate(ego.get('likely_action_under_pressure'))} |"
    )


def case_markdown(case: dict[str, Any]) -> str:
    response = case["response"]
    signals = response["signals"]
    acceptance = response["acceptance"]
    ego = response["ego_resultant"]
    fields = case_driver_fields(case)
    lines = [
        f"## {case['scenario_id']} / {case['profile']} / repeat {case['repeat_index']}",
        "",
        f"**Title:** {case['scenario_title']}",
        "",
        f"**Expected driver:** `{case['expected_driver']}`",
        "",
        f"**Situation:** {case['scenario_prompt']}",
        "",
        "### Drivers",
        "",
        f"- **Profile leader:** {fields['profile_leader']}",
        f"- **Profile leader minds:** {markdown_value(ego.get('profile_leader_minds', []))}",
        f"- **Situational driver:** {fields['situational_driver']}",
        f"- **Resultant under pressure:** {fields['resultant_leader_under_pressure']}",
        f"- **Leading mind (legacy):** {normalize_mind_name(ego.get('leading_mind'))}",
        f"- **Racio role:** {ego.get('racio_role')}",
        f"- **Emocio role:** {ego.get('emocio_role')}",
        f"- **Instinkt role:** {ego.get('instinkt_role')}",
        f"- **Decision stability:** {ego.get('decision_stability')}",
        f"- **Profile influence:** {ego.get('profile_influence_explanation')}",
        "",
        signal_section("Conscious Racio Monologue", signals["racio"]),
        signal_section("Translated Emocio Signal", signals["emocio_translated"]),
        signal_section("Translated Instinkt Signal", signals["instinkt_translated"]),
        "### Acceptance",
        "",
        f"- **Overall level:** {acceptance.get('overall_level')}",
        f"- **Behavioral alignment:** {acceptance.get('behavioral_alignment')}",
        f"- **Acceptance quality:** {acceptance.get('acceptance_quality')}",
        f"- **Non-acceptance pattern:** {acceptance.get('non_acceptance_pattern')}",
        f"- **Coalition pattern:** {acceptance.get('coalition_pattern')}",
        f"- **Sabotage mechanism:** {acceptance.get('sabotage_mechanism')}",
        f"- **Main conflict:** {acceptance.get('main_conflict')}",
        f"- **Task delegation:** {markdown_value(acceptance.get('task_delegation', {}))}",
        "",
        "### Prediction",
        "",
        f"- **Likely action under pressure:** {ego.get('likely_action_under_pressure')}",
        f"- **Racio justification afterward:** {ego.get('racio_justification_afterwards')}",
        f"- **Hidden driver:** {ego.get('hidden_driver')}",
        f"- **Hidden cost:** {ego.get('hidden_cost')}",
        f"- **Integrated decision:** {ego.get('integrated_decision')}",
        f"- **Smallest acceptable next step:** {ego.get('smallest_acceptable_next_step')}",
        f"- **Racio-only prediction:** {ego.get('prediction_if_racio_rules_alone')}",
        f"- **Emocio-only prediction:** {ego.get('prediction_if_emocio_rules_alone')}",
        f"- **Instinkt-only prediction:** {ego.get('prediction_if_instinkt_rules_alone')}",
        f"- **Uncertainty:** {ego.get('uncertainty')}",
        "",
    ]
    if "baselines" in case:
        lines.extend(["### Baselines", ""])
        for name, payload in case["baselines"].items():
            lines.append(f"#### {name}")
            lines.append("")
            for key, value in payload.items():
                lines.append(f"- **{key}:** {markdown_value(value)}")
            lines.append("")
    return "\n".join(lines)


def filtered_scenarios(filter_value: Optional[str]) -> list[dict[str, str]]:
    if not filter_value:
        return SCENARIOS
    terms = [term.strip().lower() for term in filter_value.split(",") if term.strip()]
    return [
        scenario
        for scenario in SCENARIOS
        if any(term in scenario["id"].lower() or term in scenario["title"].lower() for term in terms)
    ]


def filtered_profiles(filter_value: Optional[str]) -> list[str]:
    if not filter_value:
        return PROFILES
    terms = [term.strip().lower() for term in filter_value.split(",") if term.strip()]
    return [profile for profile in PROFILES if any(term in profile.lower() for term in terms)]


def build_case_plan(
    scenarios: list[dict[str, str]],
    profiles: list[str],
    repeat: int,
    max_cases: Optional[int],
) -> list[tuple[int, dict[str, str], str]]:
    planned = [
        (repeat_index, scenario, profile)
        for repeat_index in range(1, repeat + 1)
        for scenario in scenarios
        for profile in profiles
    ]
    return planned[:max_cases] if max_cases else planned


def counter_markdown(counter: Counter[str]) -> str:
    if not counter:
        return "`none`"
    return ", ".join(f"`{key}`: {value}" for key, value in sorted(counter.items()))


def aggregate_metrics(cases: list[dict[str, Any]], fallback_count: int) -> dict[str, Any]:
    valid_cases = [case for case in cases if "response" in case]
    total = len(valid_cases)
    resultant_counts: Counter[str] = Counter()
    profile_leader_counts: Counter[str] = Counter()
    situational_counts: Counter[str] = Counter()
    alignment_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    per_scenario: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: {
            "profile_leader": Counter(),
            "situational_driver": Counter(),
            "resultant_leader_under_pressure": Counter(),
            "behavioral_alignment": Counter(),
            "acceptance_quality": Counter(),
        }
    )
    resultants_by_scenario: dict[str, set[str]] = defaultdict(set)
    situational_by_profile: dict[str, set[str]] = defaultdict(set)
    enum_errors = 0
    llm_times: list[int] = []

    for case in valid_cases:
        fields = case_driver_fields(case)
        resultant_counts[fields["resultant_leader_under_pressure"]] += 1
        profile_leader_counts[fields["profile_leader"]] += 1
        situational_counts[fields["situational_driver"]] += 1
        alignment_counts[fields["behavioral_alignment"]] += 1
        quality_counts[fields["acceptance_quality"]] += 1
        scenario_id = case["scenario_id"]
        profile = case["profile"]
        for field, value in fields.items():
            per_scenario[scenario_id][field][value] += 1
        if fields["resultant_leader_under_pressure"] != "unknown":
            resultants_by_scenario[scenario_id].add(fields["resultant_leader_under_pressure"])
        if fields["situational_driver"] != "unknown":
            situational_by_profile[profile].add(fields["situational_driver"])
        enum_errors += enum_normalization_count(case)
        for call in case.get("diagnostics", {}).get("llm_calls", []):
            elapsed = call.get("elapsed_ms")
            if isinstance(elapsed, int):
                llm_times.append(elapsed)

    def ratio(mind: str) -> float:
        return round(resultant_counts[mind] / total, 4) if total else 0.0

    profile_sensitivity = 0.0
    if resultants_by_scenario:
        profile_sensitivity = sum(
            min(len(values), 3) / 3 for values in resultants_by_scenario.values()
        ) / len(resultants_by_scenario)

    scenario_sensitivity = 0.0
    if situational_by_profile:
        scenario_sensitivity = sum(
            min(len(values), 3) / 3 for values in situational_by_profile.values()
        ) / len(situational_by_profile)

    equal_profile_single_leader = any(
        case["profile"] == "R=E=I" and case_driver_fields(case)["profile_leader"] in {"racio", "emocio", "instinkt"}
        for case in valid_cases
    )
    warnings = []
    if ratio("instinkt") > 0.80:
        warnings.append("WARNING: Instinkt dominance ratio > 0.80. Check scenario balance, prompts, and Ego arbitration.")
    if equal_profile_single_leader:
        warnings.append("WARNING: Equal profile resolved to a single mind. Check tie handling.")
    if enum_errors:
        warnings.append("WARNING: Mind enum casing or alias values were normalized.")

    return {
        "total_cases": total,
        "fallback_count": fallback_count,
        "instinkt_dominance_ratio": ratio("instinkt"),
        "racio_dominance_ratio": ratio("racio"),
        "emocio_dominance_ratio": ratio("emocio"),
        "mixed_dominance_ratio": ratio("mixed"),
        "profile_sensitivity_score": round(profile_sensitivity, 4),
        "scenario_sensitivity_score": round(scenario_sensitivity, 4),
        "enum_normalization_errors": enum_errors,
        "average_llm_time_ms": round(sum(llm_times) / len(llm_times)) if llm_times else 0,
        "resultant_counts": dict(resultant_counts),
        "profile_leader_counts": dict(profile_leader_counts),
        "situational_driver_counts": dict(situational_counts),
        "behavioral_alignment_counts": dict(alignment_counts),
        "acceptance_quality_counts": dict(quality_counts),
        "per_scenario": {
            scenario: {field: dict(counter) for field, counter in counters.items()}
            for scenario, counters in per_scenario.items()
        },
        "warnings": warnings,
    }


def write_aggregate_summary(path: Path, metrics: dict[str, Any]) -> None:
    lines = [
        "# REI Cycle Aggregate Summary",
        "",
        SIMULATION_CAVEAT,
        "",
        "## Global Metrics",
        "",
    ]
    for key in [
        "total_cases",
        "fallback_count",
        "instinkt_dominance_ratio",
        "racio_dominance_ratio",
        "emocio_dominance_ratio",
        "mixed_dominance_ratio",
        "profile_sensitivity_score",
        "scenario_sensitivity_score",
        "enum_normalization_errors",
        "average_llm_time_ms",
    ]:
        lines.append(f"- **{key}:** {metrics[key]}")
    lines.extend(["", "## Global Counts", ""])
    for key in [
        "profile_leader_counts",
        "situational_driver_counts",
        "resultant_counts",
        "behavioral_alignment_counts",
        "acceptance_quality_counts",
    ]:
        lines.append(f"- **{key}:** {counter_markdown(Counter(metrics[key]))}")
    lines.extend(["", "## Warnings", ""])
    if metrics["warnings"]:
        lines.extend(f"- {warning}" for warning in metrics["warnings"])
    else:
        lines.append("- none")
    lines.extend(["", "## Per Scenario", ""])
    for scenario_id, counters in sorted(metrics["per_scenario"].items()):
        lines.extend([f"### {scenario_id}", ""])
        for field, counter in counters.items():
            lines.append(f"- **{field}:** {counter_markdown(Counter(counter))}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run REI profiles across a scenario matrix.")
    parser.add_argument("--provider", choices=["auto", "lmstudio", "ollama", "deterministic"], default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--scenario-filter", default=None)
    parser.add_argument("--profile-filter", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--include-baseline", action="store_true")
    parser.add_argument("--debug-trace", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    repeat = max(1, args.repeat)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir or ROOT / "output" / "reports" / f"rei_cycle_matrix_{run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "results.jsonl"
    markdown_path = output_dir / "report.md"
    aggregate_path = output_dir / "aggregate_summary.md"
    aggregate_json_path = output_dir / "aggregate_summary.json"
    progress_path = output_dir / "progress.log"
    summary_path = output_dir / "summary.json"

    scenarios = filtered_scenarios(args.scenario_filter)
    profiles = filtered_profiles(args.profile_filter)
    case_plan = build_case_plan(scenarios, profiles, repeat, args.max_cases)
    provider = choose_provider(args.provider, args.model, args.no_llm, args.debug_trace)
    engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
    total = len(case_plan)
    started = time.perf_counter()

    write_progress(
        progress_path,
        f"START provider={provider.provider_mode} model={provider.racio_model} total={total} baseline={args.include_baseline}",
    )
    markdown_path.write_text(
        "# REI Cycle Matrix Report\n\n"
        f"{SIMULATION_CAVEAT}\n\n"
        f"- Run id: `{run_id}`\n"
        f"- Provider: `{provider.provider_mode}`\n"
        f"- Model: `{provider.racio_model}`\n"
        f"- Cases: `{total}`\n"
        f"- Repeat: `{repeat}`\n"
        f"- Baselines: `{args.include_baseline}`\n\n"
        "## Aggregate Table\n\n"
        "| Scenario | Profile | Profile leader | Situational driver | Resultant under pressure | Alignment | Acceptance quality | Likely action |\n"
        "|---|---|---|---|---|---|---|---|\n",
        encoding="utf-8",
    )

    cases: list[dict[str, Any]] = []
    completed = 0
    fallback_count = 0
    for repeat_index, scenario, profile in case_plan:
        completed += 1
        label = f"{completed:03d}/{total} repeat={repeat_index} scenario={scenario['id']} profile={profile}"
        write_progress(progress_path, f"RUN {label}")
        try:
            response, diagnostics = engine.run_rei_cycle(
                scenario["prompt"],
                character_profile=profile,
                provider=provider,
            )
            response_payload = response.model_dump(mode="json")
            case = {
                "run_id": run_id,
                "case_index": completed,
                "repeat_index": repeat_index,
                "scenario_id": scenario["id"],
                "scenario_title": scenario["title"],
                "scenario_prompt": scenario["prompt"],
                "expected_driver": scenario["expected_driver"],
                "profile": profile,
                "response": response_payload,
                "fallbacks": diagnostics.get("fallbacks", []),
                "diagnostics": diagnostics if provider.debug_trace else response_payload.get("diagnostics", {}),
            }
            if args.include_baseline:
                case["baselines"] = baselines_for_case(scenario["prompt"], profile, engine, provider)
            fallback_count += len(diagnostics.get("fallbacks", []))
            append_jsonl(jsonl_path, case)
            cases.append(case)
            with markdown_path.open("a", encoding="utf-8") as handle:
                handle.write(case_summary_row(case) + "\n")
            fields = case_driver_fields(case)
            write_progress(
                progress_path,
                f"DONE {label} profile_leader={fields['profile_leader']} situational={fields['situational_driver']} "
                f"resultant={fields['resultant_leader_under_pressure']} acceptance={fields['acceptance_quality']}",
            )
        except Exception as exc:
            fallback_count += 1
            error_case = {
                "run_id": run_id,
                "case_index": completed,
                "repeat_index": repeat_index,
                "scenario_id": scenario["id"],
                "scenario_title": scenario["title"],
                "expected_driver": scenario["expected_driver"],
                "profile": profile,
                "error": str(exc),
            }
            append_jsonl(jsonl_path, error_case)
            cases.append(error_case)
            write_progress(progress_path, f"ERROR {label} error={exc}")

    with markdown_path.open("a", encoding="utf-8") as handle:
        handle.write("\n## Case Details\n\n")
        for case in cases:
            if "response" in case:
                handle.write(case_markdown(case))
            else:
                handle.write(
                    f"## {case['scenario_id']} / {case['profile']} / repeat {case['repeat_index']}\n\n"
                    f"- **error:** {case['error']}\n\n"
                )

    elapsed_seconds = round(time.perf_counter() - started, 3)
    metrics = aggregate_metrics(cases, fallback_count)
    aggregate_json_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_aggregate_summary(aggregate_path, metrics)

    summary = {
        "run_id": run_id,
        "provider": provider.provider_mode,
        "model": provider.racio_model,
        "total": total,
        "completed": completed,
        "fallback_count": fallback_count,
        "elapsed_seconds": elapsed_seconds,
        "jsonl": relative_path(jsonl_path),
        "markdown": relative_path(markdown_path),
        "aggregate_markdown": relative_path(aggregate_path),
        "aggregate_json": relative_path(aggregate_json_path),
        "progress": relative_path(progress_path),
        "summary": relative_path(summary_path),
        "warnings": metrics["warnings"],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_progress(progress_path, f"FINISH completed={completed} fallbacks={fallback_count} elapsed_seconds={elapsed_seconds}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
