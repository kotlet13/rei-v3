#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import textwrap
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.engine import ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection
from rei.providers import LMStudioProvider, OllamaProvider


SCENARIOS: list[dict[str, str]] = [
    {
        "id": "material-loss-with-evidence",
        "title": "Material loss with incomplete evidence",
        "expected_pressure": "racio_instinkt",
        "prompt": (
            "A person suspects that expensive equipment at work may be stolen tonight. They have partial "
            "evidence, a limited window to act, and responsibility for the material loss if it happens. "
            "They must choose whether to secure the equipment quietly, confront someone, or wait for proof."
        ),
    },
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
        "id": "public-stage-image-crack",
        "title": "Public stage image crack",
        "expected_pressure": "emocio_instinkt",
        "prompt": (
            "A person has to step in front of a full auditorium in five minutes. Outside they look calm, but "
            "inside they feel the performance could reveal a crack in their image of competence."
        ),
    },
    {
        "id": "boundary-too-fast",
        "title": "Relationship request too fast",
        "expected_pressure": "instinkt_emocio",
        "prompt": (
            "A person wants to say yes to a relationship request, but something about the request feels too "
            "fast. They want closeness and beauty, yet they also feel their boundary becoming unclear."
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
        "id": "business-runway",
        "title": "Business launch with runway",
        "expected_pressure": "mixed",
        "prompt": (
            "A person wants to launch a business and already has six months of runway, one paying customer, "
            "and strong excitement, but still fears that a wrong move could collapse stability."
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
]


DEFAULT_PROFILES = ["R=E=I"]
DEFAULT_NUM_CTX = 65536
DEFAULT_NUM_GPU = 999

MIND_SIGNAL_KEYS = {
    "racio": "racio",
    "emocio": "emocio_translated",
    "instinkt": "instinkt_translated",
}

ROLE_TERMS: dict[str, dict[str, list[str]]] = {
    "racio": {
        "native": [
            "cost",
            "constraint",
            "evidence",
            "sequence",
            "option",
            "tradeoff",
            "verify",
            "probability",
            "control",
            "timeline",
            "material",
            "loss",
            "reversible",
            "condition",
        ],
        "foreign": [
            "afraid",
            "fear",
            "panic",
            "freeze",
            "body",
            "chest",
            "throat",
            "shame",
            "humiliation",
            "disappear",
            "alarm",
            "beautiful",
            "alive",
        ],
    },
    "emocio": {
        "native": [
            "image",
            "alive",
            "admiration",
            "shame",
            "pride",
            "visible",
            "beauty",
            "recognition",
            "humiliation",
            "desire",
            "scene",
            "status",
            "mocked",
        ],
        "foreign": [
            "optimize",
            "probability",
            "utility",
            "evidence",
            "budget",
            "risk management",
            "step-by-step",
            "regulate",
            "ground the body",
            "safety plan",
        ],
    },
    "instinkt": {
        "native": [
            "danger",
            "threat",
            "boundary",
            "loss",
            "exposure",
            "withdraw",
            "stop",
            "freeze",
            "alarm",
            "protect",
            "scarcity",
            "trust",
            "access",
            "distance",
            "secure",
        ],
        "foreign": [
            "analyze",
            "optimize",
            "strategy",
            "evidence",
            "probability",
            "utility",
            "tradeoff",
            "compare",
            "calculate",
            "timeline",
            "budget",
            "rational",
            "data",
            "model",
        ],
    },
}

REPETITION_PHRASES = [
    "one reversible test",
    "bounded test",
    "minimum safety condition",
    "smallest acceptable exposure",
    "stop condition",
    "take only the next reversible step",
    "responsible planning",
]

PROGRESS_ECHO = True


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


class LiveConsole:
    MIND_NAMES = {
        "racio": "Racio",
        "emocio": "Emocio",
        "instinkt": "Instinkt",
        "ego_resultant": "Synthesis",
    }
    COLORS = {
        "reset": "\x1b[0m",
        "bold": "\x1b[1m",
        "dim": "\x1b[2m",
        "cyan": "\x1b[36m",
        "blue": "\x1b[34m",
        "green": "\x1b[32m",
        "yellow": "\x1b[33m",
        "red": "\x1b[31m",
    }

    def __init__(
        self,
        mode: str,
        stream_text: bool,
        global_case_offset: int = 0,
        global_case_total: Optional[int] = None,
        sequence_model_index: Optional[int] = None,
        sequence_model_total: Optional[int] = None,
        refresh_seconds: float = 1.0,
    ) -> None:
        self.mode = mode
        self.enabled = mode != "off"
        self.stream_text = stream_text
        self.global_case_offset = max(0, global_case_offset)
        self.global_case_total = global_case_total
        self.sequence_model_index = sequence_model_index
        self.sequence_model_total = sequence_model_total
        self.refresh_seconds = max(0.25, refresh_seconds)
        self.use_color = os.getenv("NO_COLOR") is None
        self.active_label: Optional[str] = None
        self.active_started = 0.0
        self.case_started = 0.0
        self.current_case: dict[str, Any] = {}
        self.current_model = ""
        self.phase_text = ""
        self.last_output_phase = ""
        self.phase_stats: dict[str, Any] = {}
        self.last_case_summary: dict[str, Any] = {}
        self.rendered_lines = 0
        self.render_width = 0
        self.last_rendered_at = 0.0
        self.cursor_hidden = False

    def color(self, name: str, text: str) -> str:
        if not self.use_color:
            return text
        return f"{self.COLORS[name]}{text}{self.COLORS['reset']}"

    @staticmethod
    def terminal_width() -> int:
        return max(78, min(150, shutil.get_terminal_size((112, 30)).columns))

    @staticmethod
    def console_text(text: Any) -> str:
        value = str(text or "")
        return value.encode("utf-8", "replace").decode("utf-8", "replace")

    @staticmethod
    def clip(text: Any, width: int) -> str:
        compact = " ".join(LiveConsole.console_text(text).split())
        if len(compact) <= width:
            return compact
        return compact[: max(0, width - 3)] + "..."

    @staticmethod
    def progress_bar(done: int, total: int, width: int = 34) -> str:
        ratio = done / max(1, total)
        filled = min(width, max(0, int(width * ratio)))
        return f"[{'=' * filled}{'-' * (width - filled)}] {done}/{total} {ratio * 100:5.1f}%"

    @classmethod
    def phase_name(cls, raw_label: Any) -> str:
        label = str(raw_label or "llm")
        name, _, attempt = label.partition(":")
        pretty = cls.MIND_NAMES.get(name, name)
        return f"{pretty} attempt {attempt}" if attempt else pretty

    def current_global_index(self) -> int:
        if not self.current_case:
            return self.global_case_offset
        return self.global_case_offset + int(self.current_case.get("case_index", 0))

    def start_case(self, case: dict[str, Any], total: int, model: str) -> None:
        if not self.enabled:
            return
        self.current_case = dict(case)
        self.current_model = model
        self.case_started = time.perf_counter()
        self.active_label = None
        self.active_started = 0.0
        self.phase_text = ""
        self.last_output_phase = ""
        self.phase_stats = {}
        self.last_case_summary = {}
        if self.mode == "stream":
            bar = self.progress_bar(self.current_global_index(), self.global_case_total or total)
            print(
                "\n"
                f"{bar} | model={model}\n"
                f"test={case['scenario_id']} | profile={case['profile']} | expected={case['expected_pressure']}",
                flush=True,
            )
        elif self.mode == "lines":
            print(
                f"RUN {self.current_global_index()}/{self.global_case_total or total} "
                f"model={model} test={case['scenario_id']} profile={case['profile']}",
                flush=True,
            )
        else:
            self.render(force=True)

    def finish_case(self, case: dict[str, Any]) -> None:
        if not self.enabled or "case_summary" not in case:
            return
        summary = case["case_summary"]
        self.last_case_summary = {
            "elapsed": case.get("elapsed_seconds"),
            "leading": summary.get("leading_mind"),
            "stability": summary.get("decision_stability"),
        }
        if self.mode in {"stream", "lines"}:
            print(
                f"\ncase_done elapsed={case['elapsed_seconds']}s "
                f"leading={summary.get('leading_mind')} stability={summary.get('decision_stability')}",
                flush=True,
            )
        else:
            self.render(force=True)

    def response_preview(self, width: int, height: int = 8) -> list[str]:
        text = self.phase_text.strip()
        if not text:
            return ["phase running; first output snapshot appears when this mind finishes..."]
        tail = text[-3000:]
        lines: list[str] = []
        for part in tail.splitlines() or [tail]:
            wrapped = textwrap.wrap(part, width=width, replace_whitespace=False) or [""]
            lines.extend(wrapped)
        return lines[-height:]

    def render(self, force: bool = False) -> None:
        if not self.enabled or self.mode != "dashboard":
            return
        now = time.perf_counter()
        if not force and now - self.last_rendered_at < self.refresh_seconds:
            return
        self.last_rendered_at = now
        width = self.terminal_width()
        self.render_width = width
        total = self.global_case_total or int(self.current_case.get("case_index", 1))
        current = min(max(1, self.current_global_index()), max(1, total))
        phase = self.phase_name(self.active_label)
        phase_elapsed = round(now - self.active_started, 1) if self.active_started else 0
        case_elapsed = round(now - self.case_started, 1) if self.case_started else 0
        model_prefix = ""
        if self.sequence_model_index and self.sequence_model_total:
            model_prefix = f"model {self.sequence_model_index}/{self.sequence_model_total} | "
        stats = self.phase_stats or {}
        summary = self.last_case_summary
        preview_width = max(50, width - 4)
        divider = "-" * width
        title = "REI role probe"
        lines = [
            self.color("yellow", self.color("bold", self.clip("REI role probe", width))),
            self.color("green", self.progress_bar(current, total, width=max(18, min(44, width - 28)))),
            self.color("blue", self.clip(f"{model_prefix}{self.current_model} | ctx active via Ollama | run {current}/{total}", width)),
            self.clip(
                f"test: {self.current_case.get('scenario_id')} | profile: {self.current_case.get('profile')} | "
                f"expected: {self.current_case.get('expected_pressure')}",
                width,
            ),
            self.color(
                "blue",
                self.clip(
                    f"phase: {phase} | phase_elapsed: {phase_elapsed}s | case_elapsed: {case_elapsed}s | "
                    f"eval_tps: {stats.get('eval_tokens_per_second', '-')}",
                    width,
                ),
            ),
        ]
        if summary:
            lines.append(
                self.color(
                    "yellow",
                    self.clip(
                        f"last case: elapsed={summary.get('elapsed')}s leading={summary.get('leading')} "
                        f"stability={summary.get('stability')}",
                        width,
                    ),
                )
            )
        else:
            lines.append(self.color("dim", self.clip("last case: none yet", width)))
        output_title = "current mind output"
        if self.last_output_phase:
            output_title = f"last completed output: {self.last_output_phase}"
        lines.extend([divider, self.color("yellow", f"{output_title} (last lines):")])
        preview = self.response_preview(preview_width)
        lines.extend(self.clip(line, preview_width) for line in preview)
        while len(preview) < 8:
            lines.append("")
            preview.append("")
        lines.extend([divider, self.color("dim", "Ctrl+C writes partial summary and unloads the current Ollama model.")])
        target_lines = max(self.rendered_lines, len(lines))
        while len(lines) < target_lines:
            lines.append("")
        if self.rendered_lines:
            sys.stdout.write(f"\x1b[{self.rendered_lines}A\r")
        elif not self.cursor_hidden:
            sys.stdout.write("\x1b[?25l")
            self.cursor_hidden = True
        for line in lines:
            sys.stdout.write(self.pad_ansi(line, width) + "\x1b[K\n")
        sys.stdout.flush()
        self.rendered_lines = len(lines)

    def close(self) -> None:
        if self.cursor_hidden:
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()
            self.cursor_hidden = False

    @classmethod
    def visible_len(cls, text: str) -> int:
        return len(re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text))

    @classmethod
    def pad_ansi(cls, text: str, width: int) -> str:
        visible = cls.visible_len(text)
        if visible >= width:
            return text
        return cls.console_text(text + (" " * (width - visible)))

    def stream_event(self, event: dict[str, Any]) -> None:
        if not self.enabled:
            return
        event_type = event.get("type")
        phase = self.phase_name(event.get("label"))
        model = event.get("model") or ""
        if event_type == "start":
            self.active_label = str(event.get("label") or "")
            self.active_started = time.perf_counter()
            if self.stream_text:
                self.phase_text = ""
                self.last_output_phase = ""
            self.phase_stats = {}
            if self.mode == "dashboard":
                self.render(force=True)
            else:
                print(f"\n>>> {phase} | model={model}", flush=True)
            return
        if event_type == "delta":
            if not self.stream_text:
                return
            text = str(event.get("content") or event.get("thinking") or "")
            if not text:
                return
            self.phase_text += text
            if self.mode == "dashboard":
                self.render()
            elif self.mode == "stream":
                sys.stdout.write(text)
                sys.stdout.flush()
            return
        if event_type == "done":
            elapsed = round(time.perf_counter() - self.active_started, 2) if self.active_started else 0
            stats = event.get("stats") or {}
            final_text = str(event.get("content") or event.get("thinking") or "")
            if final_text and not self.phase_text:
                self.phase_text = final_text
                self.last_output_phase = phase
            self.phase_stats = stats
            if self.mode == "dashboard":
                self.render(force=True)
            else:
                print(
                    f"\n<<< {phase} done elapsed={elapsed}s "
                    f"eval_tps={stats.get('eval_tokens_per_second')} "
                    f"prompt_tps={stats.get('prompt_tokens_per_second')}",
                    flush=True,
                )


def choose_provider(mode: str, model: Optional[str], debug_trace: bool) -> ProviderSelection:
    if mode == "deterministic":
        return ProviderSelection(provider_mode="deterministic", use_llm=False, debug_trace=debug_trace)

    if mode == "lmstudio":
        lmstudio_models = LMStudioProvider().list_models()
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

    if mode == "auto":
        lmstudio_models = LMStudioProvider().list_models()
        if lmstudio_models and model is None:
            return choose_provider("lmstudio", None, debug_trace)

    selected = model or "qwen3.6:35b"
    return ProviderSelection(
        provider_mode="ollama",
        racio_model=selected,
        emocio_model=selected,
        instinkt_model=selected,
        synthesis_model=selected,
        use_llm=True,
        debug_trace=debug_trace,
    )


def selected_scenarios(raw_filter: Optional[str]) -> list[dict[str, str]]:
    if not raw_filter:
        return list(SCENARIOS)
    tokens = [token.strip().lower() for token in raw_filter.split(",") if token.strip()]
    matches = [
        scenario
        for scenario in SCENARIOS
        if any(token in scenario["id"].lower() or token in scenario["title"].lower() for token in tokens)
    ]
    if not matches:
        raise SystemExit(f"No scenarios matched --scenario-filter={raw_filter!r}")
    return matches


def selected_profiles(raw_profiles: str) -> list[str]:
    profiles = [profile.strip() for profile in raw_profiles.split(",") if profile.strip()]
    return profiles or list(DEFAULT_PROFILES)


def build_case_plan(
    scenarios: list[dict[str, str]],
    profiles: list[str],
    repeat: int,
    max_cases: Optional[int],
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for repeat_index in range(1, repeat + 1):
        for scenario in scenarios:
            for profile in profiles:
                plan.append(
                    {
                        "case_index": len(plan) + 1,
                        "repeat_index": repeat_index,
                        "scenario_id": scenario["id"],
                        "scenario_title": scenario["title"],
                        "expected_pressure": scenario["expected_pressure"],
                        "scenario_prompt": scenario["prompt"],
                        "profile": profile,
                    }
                )
                if max_cases is not None and len(plan) >= max_cases:
                    return plan
    return plan


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_progress(path: Path, line: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    message = f"[{timestamp}] {line}"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")
    if PROGRESS_ECHO:
        print(message, flush=True)


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
            write_progress(progress_path, f"UNLOAD model={model} ok")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        write_progress(progress_path, f"UNLOAD model={model} failed={exc}")


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    return str(value or "")


def term_hits(text: str, terms: Iterable[str]) -> Counter[str]:
    lowered = text.lower()
    hits: Counter[str] = Counter()
    for term in terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b" if " " not in term else re.escape(term.lower())
        count = len(re.findall(pattern, lowered))
        if count:
            hits[term] = count
    return hits


def mind_role_drift(mind: str, signal: dict[str, Any]) -> dict[str, Any]:
    text = flatten_text(signal)
    native_hits = term_hits(text, ROLE_TERMS[mind]["native"])
    foreign_hits = term_hits(text, ROLE_TERMS[mind]["foreign"])
    native_total = sum(native_hits.values())
    foreign_total = sum(foreign_hits.values())
    denominator = max(1, native_total + foreign_total)
    drift_score = round(foreign_total / denominator, 4)
    flags: list[str] = []
    if mind == "racio" and foreign_total:
        flags.append("racio_uses_fear_body_or_image_language")
    if mind == "instinkt" and foreign_total:
        flags.append("instinkt_uses_rational_strategy_language")
    if mind == "emocio" and foreign_total:
        flags.append("emocio_uses_analysis_or_regulation_language")
    if native_total == 0:
        flags.append(f"{mind}_missing_native_terms")
    return {
        "mind": mind,
        "native_hits": dict(native_hits),
        "foreign_hits": dict(foreign_hits),
        "native_total": native_total,
        "foreign_total": foreign_total,
        "drift_score": drift_score,
        "flags": flags,
    }


def repetition_hits(response_payload: dict[str, Any]) -> dict[str, int]:
    text = flatten_text(response_payload).lower()
    return {
        phrase: len(re.findall(re.escape(phrase), text))
        for phrase in REPETITION_PHRASES
        if phrase in text
    }


def token_set(text: str) -> set[str]:
    stopwords = {
        "the",
        "and",
        "that",
        "with",
        "this",
        "from",
        "into",
        "must",
        "should",
        "would",
        "could",
        "their",
        "there",
        "then",
        "only",
        "before",
        "after",
        "about",
        "because",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z_'-]{2,}", text.lower())
        if token not in stopwords
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return round(len(left & right) / max(1, len(left | right)), 4)


def distinctness_probe(signals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    compact = {
        mind: " ".join(
            str(signal.get(key, ""))
            for key in ["perception", "primary_motive", "preferred_action", "risk_if_dominant"]
        )
        for mind, signal in signals.items()
    }
    pairs = {
        "racio_emocio": jaccard(token_set(compact["racio"]), token_set(compact["emocio"])),
        "racio_instinkt": jaccard(token_set(compact["racio"]), token_set(compact["instinkt"])),
        "emocio_instinkt": jaccard(token_set(compact["emocio"]), token_set(compact["instinkt"])),
    }
    return {
        "pair_jaccard": pairs,
        "max_jaccard": max(pairs.values()),
        "distinctness_warning": max(pairs.values()) >= 0.32,
    }


def compact_diagnostics(diagnostics: dict[str, Any], debug_trace: bool) -> dict[str, Any]:
    if debug_trace:
        return diagnostics
    compact = dict(diagnostics)
    compact["llm_calls"] = [
        {
            key: value
            for key, value in call.items()
            if key not in {"request", "response"}
        }
        for call in diagnostics.get("llm_calls", [])
    ]
    return compact


def summarize_case(response_payload: dict[str, Any]) -> dict[str, Any]:
    ego = response_payload.get("ego_resultant", {})
    acceptance = response_payload.get("acceptance", {})
    return {
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


def run_case(
    engine: ReiEngine,
    provider: ProviderSelection,
    plan_case: dict[str, Any],
    acceptance_mode: str,
    use_memory: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    response, diagnostics = engine.run_rei_cycle(
        user_prompt=plan_case["scenario_prompt"],
        character_profile=plan_case["profile"],
        acceptance_mode=acceptance_mode,  # type: ignore[arg-type]
        rounds=0,
        stream=False,
        use_memory=use_memory,
        provider=provider,
    )
    elapsed_seconds = round(time.perf_counter() - started, 3)
    response_payload = response.model_dump(mode="json")
    signals = {
        mind: response_payload["signals"][signal_key]
        for mind, signal_key in MIND_SIGNAL_KEYS.items()
    }
    drift = {mind: mind_role_drift(mind, signal) for mind, signal in signals.items()}
    return {
        **plan_case,
        "elapsed_seconds": elapsed_seconds,
        "provider": provider.provider_mode,
        "model": provider.racio_model,
        "response": response_payload,
        "case_summary": summarize_case(response_payload),
        "role_drift": drift,
        "distinctness": distinctness_probe(signals),
        "repetition_hits": repetition_hits(response_payload),
        "diagnostics": compact_diagnostics(diagnostics, provider.debug_trace),
    }


def average(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    drift_by_mind: dict[str, list[float]] = defaultdict(list)
    flags: Counter[str] = Counter()
    repetition: Counter[str] = Counter()
    leading: Counter[str] = Counter()
    stability: Counter[str] = Counter()
    max_jaccards: list[float] = []
    fallback_count = 0
    for case in cases:
        leading.update([str(case["case_summary"].get("leading_mind") or "unknown")])
        stability.update([str(case["case_summary"].get("decision_stability") or "unknown")])
        max_jaccards.append(float(case["distinctness"]["max_jaccard"]))
        repetition.update(case.get("repetition_hits", {}))
        fallback_count += len(case.get("diagnostics", {}).get("fallbacks", []))
        for mind, drift in case["role_drift"].items():
            drift_by_mind[mind].append(float(drift["drift_score"]))
            flags.update(drift["flags"])
    return {
        "total_cases": len(cases),
        "fallback_count": fallback_count,
        "average_elapsed_seconds": average([float(case["elapsed_seconds"]) for case in cases]),
        "average_max_signal_jaccard": average(max_jaccards),
        "average_drift_by_mind": {
            mind: average(values)
            for mind, values in sorted(drift_by_mind.items())
        },
        "role_drift_flags": dict(sorted(flags.items())),
        "repetition_hits": dict(sorted(repetition.items())),
        "leading_mind_counts": dict(sorted(leading.items())),
        "decision_stability_counts": dict(sorted(stability.items())),
    }


def md_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def truncate(value: Any, limit: int = 140) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def signal_markdown(title: str, signal: dict[str, Any], drift: dict[str, Any]) -> list[str]:
    lines = [f"### {title}", ""]
    for key in [
        "perception",
        "primary_motive",
        "preferred_action",
        "accepted_expression",
        "non_accepted_expression",
        "resistance_to_other_minds",
        "what_this_mind_needs",
        "risk_if_ignored",
        "risk_if_dominant",
        "uncertainty",
    ]:
        if key in signal:
            lines.append(f"- **{key}:** {md_value(signal[key])}")
    extra_keys = [
        key
        for key in signal.keys()
        if key
        not in {
            "mind",
            "is_conscious",
            "translated_by_racio",
            "processing_mode",
            "confidence",
            "safety_flags",
            "perception",
            "primary_motive",
            "preferred_action",
            "accepted_expression",
            "non_accepted_expression",
            "resistance_to_other_minds",
            "what_this_mind_needs",
            "risk_if_ignored",
            "risk_if_dominant",
            "uncertainty",
        }
    ]
    for key in extra_keys:
        lines.append(f"- **{key}:** {md_value(signal[key])}")
    lines.extend(
        [
            f"- **role_drift_score:** `{drift['drift_score']}`",
            f"- **native_hits:** `{md_value(drift['native_hits'])}`",
            f"- **foreign_hits:** `{md_value(drift['foreign_hits'])}`",
            f"- **flags:** `{md_value(drift['flags'])}`",
            "",
        ]
    )
    return lines


def write_report(path: Path, cases: list[dict[str, Any]], metrics: dict[str, Any], summary: dict[str, Any]) -> None:
    lines = [
        "# REI Role Drift Probe",
        "",
        "## Run",
        "",
        f"- **run_id:** `{summary['run_id']}`",
        f"- **provider:** `{summary['provider']}`",
        f"- **model:** `{summary['model']}`",
        f"- **num_ctx:** `{summary['num_ctx']}`",
        f"- **num_gpu:** `{summary['num_gpu']}`",
        f"- **cases:** `{metrics['total_cases']}`",
        f"- **fallback_count:** `{metrics['fallback_count']}`",
        f"- **average_elapsed_seconds:** `{metrics['average_elapsed_seconds']}`",
        f"- **average_max_signal_jaccard:** `{metrics['average_max_signal_jaccard']}`",
        f"- **average_drift_by_mind:** `{md_value(metrics['average_drift_by_mind'])}`",
        f"- **role_drift_flags:** `{md_value(metrics['role_drift_flags'])}`",
        f"- **repetition_hits:** `{md_value(metrics['repetition_hits'])}`",
        "",
        "## Case Index",
        "",
        "| Scenario | Profile | Expected | Leading | Stability | Drift R/E/I | Max overlap | Integrated decision |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        drift = case["role_drift"]
        drift_summary = (
            f"{drift['racio']['drift_score']}/"
            f"{drift['emocio']['drift_score']}/"
            f"{drift['instinkt']['drift_score']}"
        )
        lines.append(
            f"| {case['scenario_id']} | {case['profile']} | {case['expected_pressure']} | "
            f"{case['case_summary']['leading_mind']} | {case['case_summary']['decision_stability']} | "
            f"{drift_summary} | {case['distinctness']['max_jaccard']} | "
            f"{truncate(case['case_summary']['integrated_decision'], 90)} |"
        )
    lines.append("")
    for case in cases:
        response = case["response"]
        signals = response["signals"]
        summary_case = case["case_summary"]
        lines.extend(
            [
                f"## {case['scenario_id']} / {case['profile']} / repeat {case['repeat_index']}",
                "",
                f"**Prompt:** {case['scenario_prompt']}",
                "",
                "### Final Result",
                "",
            ]
        )
        for key, value in summary_case.items():
            lines.append(f"- **{key}:** {md_value(value)}")
        lines.extend(
            [
                f"- **distinctness:** `{md_value(case['distinctness'])}`",
                f"- **repetition_hits:** `{md_value(case['repetition_hits'])}`",
                "",
            ]
        )
        lines.extend(signal_markdown("Racio", signals["racio"], case["role_drift"]["racio"]))
        lines.extend(signal_markdown("Emocio translated", signals["emocio_translated"], case["role_drift"]["emocio"]))
        lines.extend(signal_markdown("Instinkt translated", signals["instinkt_translated"], case["role_drift"]["instinkt"]))
        acceptance = response["acceptance"]
        lines.extend(["### Acceptance", ""])
        for key, value in acceptance.items():
            lines.append(f"- **{key}:** {md_value(value)}")
        lines.append("")
    lines.extend(["## Output Files", ""])
    for key in ["summary", "plan", "results_jsonl", "report", "progress"]:
        lines.append(f"- **{key}:** `{summary[key]}`")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    configure_console()
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or run REI role-drift probes. By default this only writes a scenario plan. "
            "Pass --confirm-run when you are ready to call local models."
        )
    )
    parser.add_argument("--provider", choices=["auto", "ollama", "lmstudio", "deterministic"], default="ollama")
    parser.add_argument("--model", default="qwen3.6:35b")
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    parser.add_argument("--num-gpu", type=int, default=DEFAULT_NUM_GPU)
    parser.add_argument("--profiles", default=",".join(DEFAULT_PROFILES))
    parser.add_argument("--scenario-filter", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--acceptance-mode", choices=["unknown", "accepting", "mixed", "conflicted"], default="mixed")
    parser.add_argument("--no-memory", action="store_true")
    parser.add_argument("--debug-trace", action="store_true")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--confirm-run", action="store_true")
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--live-mode", choices=["dashboard", "stream", "lines", "off"], default="dashboard")
    parser.add_argument("--live-stream", action="store_true")
    parser.add_argument("--no-live-ui", action="store_true")
    parser.add_argument("--no-live-stream", action="store_true")
    parser.add_argument("--global-case-offset", type=int, default=0)
    parser.add_argument("--global-case-total", type=int, default=None)
    parser.add_argument("--sequence-model-index", type=int, default=None)
    parser.add_argument("--sequence-model-total", type=int, default=None)
    parser.add_argument("--dashboard-refresh-seconds", type=float, default=1.0)
    args = parser.parse_args()
    live_mode = "off" if args.no_live_ui else args.live_mode
    live_stream = (live_mode == "stream" or args.live_stream) and not args.no_live_stream
    global PROGRESS_ECHO
    PROGRESS_ECHO = live_mode != "dashboard"

    if args.num_ctx:
        os.environ["REI_OLLAMA_NUM_CTX"] = str(args.num_ctx)
    if args.num_gpu:
        os.environ["REI_OLLAMA_NUM_GPU"] = str(args.num_gpu)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir or ROOT / "output" / "reports" / f"rei_role_drift_probe_{run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "scenario_plan.json"
    summary_path = output_dir / "summary.json"
    results_path = output_dir / "results.jsonl"
    report_path = output_dir / "report.md"
    progress_path = output_dir / "progress.log"

    scenarios = selected_scenarios(args.scenario_filter)
    profiles = selected_profiles(args.profiles)
    plan = build_case_plan(scenarios, profiles, max(1, args.repeat), args.max_cases)
    plan_payload = {
        "run_id": run_id,
        "provider": args.provider,
        "model": args.model,
        "num_ctx": args.num_ctx,
        "num_gpu": args.num_gpu,
        "acceptance_mode": args.acceptance_mode,
        "live_mode": live_mode,
        "live_stream": live_stream,
        "global_case_offset": args.global_case_offset,
        "global_case_total": args.global_case_total,
        "use_memory": not args.no_memory,
        "case_count": len(plan),
        "cases": plan,
    }
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.confirm_run:
        summary = {
            "run_id": run_id,
            "status": "planned_only",
            "message": "No model calls were made. Re-run with --confirm-run when ready.",
            "provider": args.provider,
            "model": args.model,
            "num_ctx": args.num_ctx,
            "num_gpu": args.num_gpu,
            "case_count": len(plan),
            "live_mode": live_mode,
            "live_stream": live_stream,
            "plan": relative_path(plan_path),
            "summary": relative_path(summary_path),
            "results_jsonl": relative_path(results_path),
            "report": relative_path(report_path),
            "progress": relative_path(progress_path),
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    provider = choose_provider(args.provider, args.model, args.debug_trace)
    live_console = LiveConsole(
        mode=live_mode,
        stream_text=live_stream,
        global_case_offset=args.global_case_offset,
        global_case_total=args.global_case_total,
        sequence_model_index=args.sequence_model_index,
        sequence_model_total=args.sequence_model_total,
        refresh_seconds=args.dashboard_refresh_seconds,
    )
    ollama_provider = OllamaProvider(base_url=args.ollama_base_url)
    if provider.provider_mode == "ollama":
        ollama_provider.stream_responses = live_stream
        ollama_provider.stream_callback = live_console.stream_event if live_mode != "off" else None
    knowledge = KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json")
    engine = ReiEngine(
        knowledge=knowledge,
        ollama=ollama_provider,
        lmstudio=LMStudioProvider(),
    )
    write_progress(
        progress_path,
        f"START provider={provider.provider_mode} model={provider.racio_model} num_ctx={args.num_ctx} cases={len(plan)}",
    )
    started = time.perf_counter()
    cases: list[dict[str, Any]] = []
    interrupted = False
    try:
        for plan_case in plan:
            label = f"{plan_case['case_index']:03d}/{len(plan)} {plan_case['scenario_id']} profile={plan_case['profile']}"
            live_console.start_case(plan_case, len(plan), provider.racio_model)
            write_progress(progress_path, f"RUN {label}")
            try:
                case = run_case(
                    engine=engine,
                    provider=provider,
                    plan_case=plan_case,
                    acceptance_mode=args.acceptance_mode,
                    use_memory=not args.no_memory,
                )
            except Exception as exc:
                case = {
                    **plan_case,
                    "provider": provider.provider_mode,
                    "model": provider.racio_model,
                    "error": str(exc),
                    "elapsed_seconds": 0,
                }
                write_progress(progress_path, f"ERROR {label} {exc}")
            else:
                live_console.finish_case(case)
                write_progress(
                    progress_path,
                    f"DONE {label} elapsed={case['elapsed_seconds']} "
                    f"leading={case['case_summary']['leading_mind']} fallbacks={len(case['diagnostics'].get('fallbacks', []))}",
                )
            append_jsonl(results_path, case)
            cases.append(case)
    except KeyboardInterrupt:
        interrupted = True
        write_progress(progress_path, "INTERRUPT requested by user; writing partial report")
        if provider.provider_mode == "ollama":
            unload_ollama_model(provider.racio_model, args.ollama_base_url, progress_path)

    successful_cases = [case for case in cases if "response" in case]
    metrics = aggregate(successful_cases)
    elapsed_seconds = round(time.perf_counter() - started, 3)
    summary = {
        "run_id": run_id,
        "status": "interrupted" if interrupted else "completed",
        "provider": provider.provider_mode,
        "model": provider.racio_model,
        "num_ctx": args.num_ctx,
        "num_gpu": args.num_gpu,
        "case_count": len(plan),
        "live_mode": live_mode,
        "live_stream": live_stream,
        "completed_cases": len(successful_cases),
        "error_count": len(cases) - len(successful_cases),
        "remaining_cases": len(plan) - len(cases),
        "elapsed_seconds": elapsed_seconds,
        "metrics": metrics,
        "plan": relative_path(plan_path),
        "summary": relative_path(summary_path),
        "results_jsonl": relative_path(results_path),
        "report": relative_path(report_path),
        "progress": relative_path(progress_path),
    }
    write_report(report_path, successful_cases, metrics, summary)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_progress(progress_path, f"FINISH completed={len(successful_cases)} errors={summary['error_count']}")
    live_console.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if interrupted:
        return 130
    return 0 if not summary["error_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
