#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS = ["granite4.1:30b", "gemma4:31b", "qwen3.6:35b"]
DEFAULT_NUM_CTX = 65536
DEFAULT_NUM_GPU = 999
DEFAULT_PROFILES_PRESET = "all"
ALL_PROFILES = [
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
CORE_PROFILES = ["R=E=I", "R>(E=I)", "E>(R=I)", "I>(R=E)", "R>E>I", "E>R>I", "I>R>E"]
SCENARIO_KEYS = [
    ("material-loss-with-evidence", "Material loss with incomplete evidence"),
    ("pure-budget-allocation", "Pure budget allocation"),
    ("public-stage-image-crack", "Public stage image crack"),
    ("boundary-too-fast", "Relationship request too fast"),
    ("creative-status-risk", "Creative status risk"),
    ("business-runway", "Business launch with runway"),
    ("night-door-noise", "Night door noise"),
    ("technical-architecture-choice", "Technical architecture choice"),
]


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_progress(path: Path, line: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    message = f"[{timestamp}] {line}"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")
    print(message, flush=True)


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def selected_models(raw_models: str) -> list[str]:
    models = [model.strip() for model in raw_models.split(",") if model.strip()]
    return models or list(DEFAULT_MODELS)


def selected_profiles(args: argparse.Namespace) -> str:
    if args.profiles_preset == "all":
        return ",".join(ALL_PROFILES)
    if args.profiles_preset == "core":
        return ",".join(CORE_PROFILES)
    return args.profiles


def profile_list(raw_profiles: str) -> list[str]:
    return [profile.strip() for profile in raw_profiles.split(",") if profile.strip()]


def selected_scenario_count(raw_filter: str | None) -> int:
    if not raw_filter:
        return len(SCENARIO_KEYS)
    tokens = [token.strip().lower() for token in raw_filter.split(",") if token.strip()]
    return sum(
        1
        for scenario_id, title in SCENARIO_KEYS
        if any(token in scenario_id.lower() or token in title.lower() for token in tokens)
    )


def estimated_cases_per_model(args: argparse.Namespace, profiles: list[str]) -> int:
    count = selected_scenario_count(args.scenario_filter) * len(profiles) * max(1, args.repeat)
    if args.max_cases is not None:
        count = min(count, args.max_cases)
    return count


def unload_ollama_model(model: str, base_url: str, progress_path: Path) -> None:
    payload = {
        "model": model,
        "prompt": "",
        "stream": False,
        "keep_alive": 0,
        "options": {"num_predict": 1},
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30):
            append_progress(progress_path, f"UNLOAD model={model} ok")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        append_progress(progress_path, f"UNLOAD model={model} failed={exc}")


def terminate_process(process: subprocess.Popen[str], progress_path: Path, label: str) -> None:
    if process.poll() is not None:
        return
    append_progress(progress_path, f"INTERRUPT terminating {label} pid={process.pid}")
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        append_progress(progress_path, f"INTERRUPT killing {label} pid={process.pid}")
        process.kill()
        process.wait(timeout=15)


def read_summary(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": f"Could not read summary: {exc}"}


def run_model_probe(
    model: str,
    args: argparse.Namespace,
    run_root: Path,
    progress_path: Path,
    profiles: str,
    model_index: int,
    model_total: int,
    cases_per_model: int,
) -> dict[str, Any]:
    model_slug = model.replace("/", "_").replace(":", "_").replace(".", "_")
    output_dir = run_root / model_slug
    script = ROOT / "scripts" / "run_rei_role_drift_probe.py"
    command = [
        sys.executable,
        str(script),
        "--confirm-run",
        "--provider",
        "ollama",
        "--model",
        model,
        "--num-ctx",
        str(args.num_ctx),
        "--num-gpu",
        str(args.num_gpu),
        "--output-dir",
        str(output_dir),
        "--profiles",
        profiles,
        "--acceptance-mode",
        args.acceptance_mode,
        "--ollama-base-url",
        args.ollama_base_url,
        "--live-mode",
        args.live_mode,
        "--global-case-offset",
        str((model_index - 1) * cases_per_model),
        "--global-case-total",
        str(model_total * cases_per_model),
        "--sequence-model-index",
        str(model_index),
        "--sequence-model-total",
        str(model_total),
        "--dashboard-refresh-seconds",
        str(args.dashboard_refresh_seconds),
    ]
    if args.scenario_filter:
        command.extend(["--scenario-filter", args.scenario_filter])
    if args.repeat:
        command.extend(["--repeat", str(args.repeat)])
    if args.max_cases is not None:
        command.extend(["--max-cases", str(args.max_cases)])
    if args.no_memory:
        command.append("--no-memory")
    if args.debug_trace:
        command.append("--debug-trace")
    if args.live_stream:
        command.append("--live-stream")
    if args.no_live_ui:
        command.append("--no-live-ui")
    if args.no_live_stream:
        command.append("--no-live-stream")

    stdout_path = output_dir / "sequence_stdout.txt"
    stderr_path = output_dir / "sequence_stderr.txt"
    output_dir.mkdir(parents=True, exist_ok=True)
    append_progress(progress_path, f"RUN model={model} output_dir={output_dir}")
    started = time.perf_counter()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    direct_dashboard = args.live_mode == "dashboard" and not args.no_live_ui
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=None if direct_dashboard else subprocess.PIPE,
        stderr=None if direct_dashboard else subprocess.STDOUT,
        bufsize=1,
        env=env,
    )
    stdout_lines: list[str] = []
    try:
        if direct_dashboard:
            returncode = process.wait()
        else:
            assert process.stdout is not None
            while True:
                chunk = process.stdout.read(1)
                if chunk:
                    stdout_lines.append(chunk)
                    print(chunk, end="", flush=True)
                    continue
                if process.poll() is not None:
                    break
            returncode = process.wait()
    except KeyboardInterrupt:
        terminate_process(process, progress_path, f"model probe {model}")
        unload_ollama_model(model, args.ollama_base_url, progress_path)
        stdout_path.write_text("".join(stdout_lines), encoding="utf-8")
        stderr_path.write_text(
            "Run interrupted. stderr was merged into sequence_stdout.txt for live progress streaming.\n",
            encoding="utf-8",
        )
        raise
    elapsed = round(time.perf_counter() - started, 3)
    if direct_dashboard:
        stdout_path.write_text(
            "Dashboard mode wrote directly to the PowerShell console. See progress.log, results.jsonl, and report.md.\n",
            encoding="utf-8",
        )
        stderr_path.write_text(
            "Dashboard mode inherited stderr directly from the child process.\n",
            encoding="utf-8",
        )
    else:
        stdout_path.write_text("".join(stdout_lines), encoding="utf-8")
        stderr_path.write_text("stderr was merged into sequence_stdout.txt for live progress streaming.\n", encoding="utf-8")
    summary_path = output_dir / "summary.json"
    summary = read_summary(summary_path)
    result = {
        "model": model,
        "returncode": returncode,
        "elapsed_seconds": elapsed,
        "output_dir": relative_path(output_dir),
        "summary": relative_path(summary_path),
        "stdout": relative_path(stdout_path),
        "stderr": relative_path(stderr_path),
        "metrics": summary.get("metrics", {}),
        "status": summary.get("status", "unknown"),
        "error_count": summary.get("error_count", 0),
    }
    append_progress(
        progress_path,
        f"DONE model={model} returncode={returncode} elapsed={elapsed} errors={result['error_count']}",
    )
    return result


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"error": "Could not decode JSONL row", "raw": line})
    return rows


def collect_synthesis_rows(run_root: Path, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        output_dir = run_root / Path(result["output_dir"]).name
        for case in read_jsonl(output_dir / "results.jsonl"):
            if "response" not in case:
                rows.append(
                    {
                        "model": result["model"],
                        "scenario_id": case.get("scenario_id"),
                        "profile": case.get("profile"),
                        "repeat_index": case.get("repeat_index"),
                        "error": case.get("error", "missing response"),
                    }
                )
                continue
            ego = case.get("response", {}).get("ego_resultant", {})
            acceptance = case.get("response", {}).get("acceptance", {})
            rows.append(
                {
                    "model": result["model"],
                    "scenario_id": case.get("scenario_id"),
                    "scenario_title": case.get("scenario_title"),
                    "expected_pressure": case.get("expected_pressure"),
                    "profile": case.get("profile"),
                    "repeat_index": case.get("repeat_index"),
                    "leading_mind": ego.get("leading_mind"),
                    "profile_leader": ego.get("profile_leader"),
                    "situational_driver": ego.get("situational_driver"),
                    "resultant_leader_under_pressure": ego.get("resultant_leader_under_pressure"),
                    "racio_role": ego.get("racio_role"),
                    "emocio_role": ego.get("emocio_role"),
                    "instinkt_role": ego.get("instinkt_role"),
                    "decision_stability": ego.get("decision_stability"),
                    "acceptance_level": acceptance.get("overall_level"),
                    "behavioral_alignment": acceptance.get("behavioral_alignment"),
                    "integrated_decision": ego.get("integrated_decision"),
                    "likely_action_under_pressure": ego.get("likely_action_under_pressure"),
                    "smallest_acceptable_next_step": ego.get("smallest_acceptable_next_step"),
                }
            )
    return rows


def write_synthesis_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def truncate(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def write_synthesis_report(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# REI Character Synthesis Log",
        "",
        "## Run",
        "",
        f"- **run_id:** `{summary['run_id']}`",
        f"- **num_ctx:** `{summary['num_ctx']}`",
        f"- **num_gpu:** `{summary['num_gpu']}`",
        f"- **models:** `{', '.join(summary['models'])}`",
        f"- **live_mode:** `{summary['live_mode']}`",
        f"- **profiles_count:** `{summary['profiles_count']}`",
        f"- **profiles_preset:** `{summary['profiles_preset']}`",
        "",
        "## Synthesis Index",
        "",
        "| Model | Scenario | Profile | Leading | Stability | Acceptance | Integrated decision | Next step |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row.get("error"):
            lines.append(
                f"| `{row.get('model')}` | `{row.get('scenario_id')}` | `{row.get('profile')}` | "
                f"`error` |  |  | {truncate(row.get('error'))} |  |"
            )
            continue
        lines.append(
            f"| `{row['model']}` | `{row['scenario_id']}` | `{row['profile']}` | "
            f"`{row.get('leading_mind')}` | `{row.get('decision_stability')}` | "
            f"`{row.get('acceptance_level')}` | {truncate(row.get('integrated_decision'))} | "
            f"{truncate(row.get('smallest_acceptable_next_step'))} |"
        )
    lines.extend(["", "## Full Rows", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row.get('model')} / {row.get('scenario_id')} / {row.get('profile')} / repeat {row.get('repeat_index')}",
                "",
            ]
        )
        if row.get("error"):
            lines.extend([f"- **error:** {row['error']}", ""])
            continue
        for key in [
            "expected_pressure",
            "leading_mind",
            "profile_leader",
            "situational_driver",
            "resultant_leader_under_pressure",
            "racio_role",
            "emocio_role",
            "instinkt_role",
            "decision_stability",
            "acceptance_level",
            "behavioral_alignment",
            "integrated_decision",
            "likely_action_under_pressure",
            "smallest_acceptable_next_step",
        ]:
            lines.append(f"- **{key}:** {row.get(key)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_comparison_report(path: Path, results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# REI Model A/B/C Sequence",
        "",
        "## Run",
        "",
        f"- **run_id:** `{summary['run_id']}`",
        f"- **num_ctx:** `{summary['num_ctx']}`",
        f"- **num_gpu:** `{summary['num_gpu']}`",
        f"- **models:** `{', '.join(summary['models'])}`",
        f"- **profiles_preset:** `{summary['profiles_preset']}`",
        f"- **profiles_count:** `{summary['profiles_count']}`",
        f"- **estimated_total_cases:** `{summary['estimated_total_cases']}`",
        f"- **live_mode:** `{summary['live_mode']}`",
        f"- **status:** `{summary['status']}`",
        "",
        "## Results",
        "",
        "| Model | Return | Cases | Fallbacks | Avg drift R/E/I | Avg max overlap | Repetition hits | Report |",
        "| --- | ---: | ---: | ---: | --- | ---: | --- | --- |",
    ]
    for result in results:
        metrics = result.get("metrics") or {}
        drift = metrics.get("average_drift_by_mind") or {}
        drift_text = f"{drift.get('racio', '-')}/{drift.get('emocio', '-')}/{drift.get('instinkt', '-')}"
        repetition = metrics.get("repetition_hits") or {}
        report = Path(result["output_dir"]) / "report.md"
        lines.append(
            f"| `{result['model']}` | `{result['returncode']}` | `{metrics.get('total_cases', '-')}` | "
            f"`{metrics.get('fallback_count', '-')}` | `{drift_text}` | "
            f"`{metrics.get('average_max_signal_jaccard', '-')}` | `{json.dumps(repetition, ensure_ascii=False)}` | "
            f"`{report.as_posix()}` |"
        )
    lines.extend(["", "## Output Files", ""])
    for key in ["plan", "summary", "report", "progress"]:
        lines.append(f"- **{key}:** `{summary[key]}`")
    if "synthesis_jsonl" in summary:
        lines.append(f"- **synthesis_jsonl:** `{summary['synthesis_jsonl']}`")
    if "synthesis_report" in summary:
        lines.append(f"- **synthesis_report:** `{summary['synthesis_report']}`")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    configure_console()
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or run serial REI role-drift probes across multiple Ollama models. "
            "By default this writes only a plan; pass --confirm-run to call models."
        )
    )
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    parser.add_argument("--num-gpu", type=int, default=DEFAULT_NUM_GPU)
    parser.add_argument("--profiles", default="R=E=I")
    parser.add_argument("--profiles-preset", choices=["custom", "core", "all"], default=DEFAULT_PROFILES_PRESET)
    parser.add_argument("--scenario-filter", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--acceptance-mode", choices=["unknown", "accepting", "mixed", "conflicted"], default="mixed")
    parser.add_argument("--no-memory", action="store_true")
    parser.add_argument("--debug-trace", action="store_true")
    parser.add_argument("--live-mode", choices=["dashboard", "stream", "lines", "off"], default="dashboard")
    parser.add_argument("--live-stream", action="store_true")
    parser.add_argument("--no-live-ui", action="store_true")
    parser.add_argument("--no-live-stream", action="store_true")
    parser.add_argument("--dashboard-refresh-seconds", type=float, default=1.0)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--confirm-run", action="store_true")
    parser.add_argument("--no-unload-between", action="store_true")
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    args = parser.parse_args()

    models = selected_models(args.models)
    profiles = selected_profiles(args)
    profiles_selected = profile_list(profiles)
    cases_per_model = estimated_cases_per_model(args, profiles_selected)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = Path(args.output_dir or ROOT / "output" / "reports" / f"rei_model_ab_sequence_{run_id}")
    run_root.mkdir(parents=True, exist_ok=True)
    plan_path = run_root / "sequence_plan.json"
    summary_path = run_root / "sequence_summary.json"
    report_path = run_root / "sequence_report.md"
    synthesis_jsonl_path = run_root / "sequence_synthesis.jsonl"
    synthesis_report_path = run_root / "sequence_synthesis_report.md"
    progress_path = run_root / "sequence_progress.log"
    plan = {
        "run_id": run_id,
        "status": "planned_only" if not args.confirm_run else "ready_to_run",
        "models": models,
        "num_ctx": args.num_ctx,
        "num_gpu": args.num_gpu,
        "profiles": profiles,
        "profiles_count": len(profiles_selected),
        "profiles_list": profiles_selected,
        "profiles_preset": args.profiles_preset,
        "scenario_filter": args.scenario_filter,
        "repeat": args.repeat,
        "max_cases": args.max_cases,
        "acceptance_mode": args.acceptance_mode,
        "live_mode": "off" if args.no_live_ui else args.live_mode,
        "live_stream": (args.live_mode == "stream" or args.live_stream) and not args.no_live_ui and not args.no_live_stream,
        "dashboard_refresh_seconds": args.dashboard_refresh_seconds,
        "estimated_cases_per_model": cases_per_model,
        "estimated_total_cases": len(models) * cases_per_model,
        "use_memory": not args.no_memory,
        "unload_between": not args.no_unload_between,
        "confirm_run_required": True,
    }
    write_json(plan_path, plan)

    if not args.confirm_run:
        summary = {
            **plan,
            "status": "planned_only",
            "message": "No model calls were made. Re-run with --confirm-run when other tests are paused.",
            "plan": relative_path(plan_path),
            "summary": relative_path(summary_path),
            "report": relative_path(report_path),
            "synthesis_jsonl": relative_path(synthesis_jsonl_path),
            "synthesis_report": relative_path(synthesis_report_path),
            "progress": relative_path(progress_path),
            "results": [],
        }
        write_json(summary_path, summary)
        write_comparison_report(report_path, [], summary)
        write_synthesis_jsonl(synthesis_jsonl_path, [])
        write_synthesis_report(synthesis_report_path, [], summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    append_progress(
        progress_path,
        f"START models={','.join(models)} num_ctx={args.num_ctx} profiles_count={len(profiles_selected)} profiles={profiles}",
    )
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    interrupted = False
    current_model: str | None = None
    try:
        for model_index, model in enumerate(models, start=1):
            current_model = model
            result = run_model_probe(
                model=model,
                args=args,
                run_root=run_root,
                progress_path=progress_path,
                profiles=profiles,
                model_index=model_index,
                model_total=len(models),
                cases_per_model=cases_per_model,
            )
            results.append(result)
            if not args.no_unload_between:
                unload_ollama_model(model, args.ollama_base_url, progress_path)
            if result.get("returncode") != 0:
                append_progress(
                    progress_path,
                    f"STOP model={model} returncode={result.get('returncode')} - not continuing to next model",
                )
                break
    except KeyboardInterrupt:
        interrupted = True
        append_progress(progress_path, "INTERRUPT requested by user; writing partial reports")
        if current_model and not args.no_unload_between:
            unload_ollama_model(current_model, args.ollama_base_url, progress_path)
    elapsed_seconds = round(time.perf_counter() - started, 3)
    failed = [result for result in results if result.get("returncode") != 0]
    summary = {
        **plan,
        "status": "interrupted" if interrupted else "completed",
        "elapsed_seconds": elapsed_seconds,
        "failed_models": [result["model"] for result in failed],
        "plan": relative_path(plan_path),
        "summary": relative_path(summary_path),
        "report": relative_path(report_path),
        "synthesis_jsonl": relative_path(synthesis_jsonl_path),
        "synthesis_report": relative_path(synthesis_report_path),
        "progress": relative_path(progress_path),
        "results": results,
    }
    synthesis_rows = collect_synthesis_rows(run_root, results)
    write_synthesis_jsonl(synthesis_jsonl_path, synthesis_rows)
    write_synthesis_report(synthesis_report_path, synthesis_rows, summary)
    write_json(summary_path, summary)
    write_comparison_report(report_path, results, summary)
    append_progress(progress_path, f"FINISH elapsed={elapsed_seconds} failed={len(failed)}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if interrupted:
        return 130
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
