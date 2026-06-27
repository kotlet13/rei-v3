from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any, Generator, Literal, Optional
import urllib.error
import urllib.request

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from rei.acceptance import assess_acceptance
from rei.contract_loader import build_ego_prompt, build_processor_prompt, ego_required_keys, runtime_required_keys_for
from rei.engine import ReiEngine
from rei.ft_dataset import (
    DATASETS_ROOT,
    DatasetExample,
    DatasetSplit,
    DatasetStatus,
    DatasetTarget,
    build_manifest,
    dataset_path,
    export_dataset,
    load_examples,
    load_scenarios,
    save_examples,
    utc_now,
    validate_dataset,
    validate_example,
    write_json,
    write_manifest,
)
from rei.json_utils import extract_json_object, validate_required_keys
from rei.knowledge import KnowledgeIndex
from rei.models import Scenario
from rei.profiles import profile_weights


Target = Literal["racio", "emocio", "instinkt", "ego_resultant"]

TARGETS: tuple[Target, ...] = ("racio", "emocio", "instinkt", "ego_resultant")
PROCESSOR_TARGETS: tuple[Target, ...] = ("racio", "emocio", "instinkt")
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = Path(__file__).resolve().parent / "data"
PROMPT_OVERRIDES_PATH = DATA_DIR / "prompt_overrides.json"
HISTORY_PATH = DATA_DIR / "test_history.jsonl"
DEFAULT_NUM_CTX = 65536
DEFAULT_NUM_GPU = 999
DEFAULT_PROFILE = "REI"
PROFILE_OPTIONS = [
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
DEFAULT_TEMPERATURES = {
    "racio": 0.22,
    "emocio": 0.55,
    "instinkt": 0.20,
    "ego_resultant": 0.26,
}
DEFAULT_TOP_P = {
    "racio": 0.82,
    "emocio": 0.88,
    "instinkt": 0.78,
    "ego_resultant": 0.84,
}
DEFAULT_NUM_PREDICT = {
    "racio": 1600,
    "emocio": 1600,
    "instinkt": 1600,
    "ego_resultant": 1800,
}


app = FastAPI(title="REI Prompt Workbench")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_run_lock = threading.Lock()
_run_stops: dict[str, threading.Event] = {}
_engine: Optional[ReiEngine] = None


class TargetSettings(BaseModel):
    model: str = ""
    num_ctx: int = Field(default=DEFAULT_NUM_CTX, ge=512, le=262144)
    num_gpu: int = Field(default=DEFAULT_NUM_GPU, ge=0, le=999)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    num_predict: Optional[int] = Field(default=None, ge=16, le=8192)


class BaseRunRequest(BaseModel):
    run_id: str
    input: str
    title: str = "Workbench test"
    profile: str = DEFAULT_PROFILE
    use_reference_context: bool = True
    settings: dict[str, TargetSettings] = Field(default_factory=dict)


class EgoRunRequest(BaseRunRequest):
    signals: dict[str, dict[str, Any]] = Field(default_factory=dict)


class DatasetExampleUpdate(BaseModel):
    status: Optional[DatasetStatus] = None
    split: Optional[DatasetSplit] = None
    assistant_payload: Optional[dict[str, Any]] = None
    review_notes: Optional[str] = None
    reviewer: Optional[str] = None


@dataclass
class ChatResult:
    target: Target
    model: str
    content: str
    parsed: Optional[dict[str, Any]]
    missing_required_keys: list[str]
    stats: dict[str, Any]
    elapsed_ms: int
    status: Literal["done", "stopped", "error"]
    error: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _engine_instance() -> ReiEngine:
    global _engine
    if _engine is None:
        _engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
    return _engine


def _normalize_base_url(value: str) -> str:
    url = value.strip()
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url.rstrip("/")


def _ollama_base_url() -> str:
    import os

    return _normalize_base_url(
        os.environ.get("REI_OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    )


def _http_json(path: str, timeout_seconds: int = 5) -> dict[str, Any]:
    with urllib.request.urlopen(f"{_ollama_base_url()}{path}", timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _ollama_status() -> dict[str, Any]:
    try:
        tags = _http_json("/api/tags", timeout_seconds=4)
        models = [item.get("name", "") for item in tags.get("models", []) if item.get("name")]
        try:
            ps = _http_json("/api/ps", timeout_seconds=2)
            running = [item.get("name", "") for item in ps.get("models", []) if item.get("name")]
        except Exception:
            running = []
        return {
            "reachable": True,
            "base_url": _ollama_base_url(),
            "models": models,
            "running": running,
            "error": "",
        }
    except Exception as exc:
        return {
            "reachable": False,
            "base_url": _ollama_base_url(),
            "models": [],
            "running": [],
            "error": str(exc),
        }


def _baseline_prompt(target: Target) -> str:
    if target == "ego_resultant":
        return build_ego_prompt()
    return build_processor_prompt(target, mode="compact")  # type: ignore[arg-type]


def _required_keys(target: Target) -> list[str]:
    if target == "ego_resultant":
        return ego_required_keys()
    return runtime_required_keys_for(target)  # type: ignore[arg-type]


def _load_overrides() -> dict[str, str]:
    if not PROMPT_OVERRIDES_PATH.exists():
        return {}
    try:
        payload = json.loads(PROMPT_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {key: value for key, value in payload.items() if key in TARGETS and isinstance(value, str)}


def _save_overrides(overrides: dict[str, str]) -> None:
    _ensure_data_dir()
    tmp_path = PROMPT_OVERRIDES_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(PROMPT_OVERRIDES_PATH)


def _prompt_for(target: Target) -> str:
    overrides = _load_overrides()
    return overrides.get(target) or _baseline_prompt(target)


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


def _settings_for(request: BaseRunRequest, target: Target, fallback_model: str = "") -> TargetSettings:
    raw = request.settings.get(target) or request.settings.get(str(target))
    if raw is None:
        raw = TargetSettings(model=fallback_model)
    if not raw.model and fallback_model:
        raw = raw.model_copy(update={"model": fallback_model})
    return raw


def _target_options(target: Target, settings: TargetSettings) -> dict[str, Any]:
    return {
        "temperature": settings.temperature
        if settings.temperature is not None
        else DEFAULT_TEMPERATURES[target],
        "top_p": settings.top_p if settings.top_p is not None else DEFAULT_TOP_P[target],
        "num_predict": settings.num_predict
        if settings.num_predict is not None
        else DEFAULT_NUM_PREDICT[target],
        "num_ctx": settings.num_ctx,
        "num_gpu": settings.num_gpu,
    }


def _default_model() -> str:
    models = _ollama_status().get("models", [])
    if "granite4.1:30b" in models:
        return "granite4.1:30b"
    return models[0] if models else ""


def _scenario(request: BaseRunRequest) -> Scenario:
    prompt = request.input.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Input is required.")
    return Scenario(title=request.title.strip() or "Workbench test", prompt=prompt)


def _profile_payload(profile_input: str) -> tuple[str, dict[str, float]]:
    normalized, weights = profile_weights(profile_input or DEFAULT_PROFILE)
    return normalized, weights


def _mind_user_payload(request: BaseRunRequest, target: Target) -> dict[str, Any]:
    scenario = _scenario(request)
    profile, weights = _profile_payload(request.profile)
    payload: dict[str, Any] = {
        "situation": scenario.model_dump(mode="json"),
        "character_profile": profile,
        "influence_weights": weights,
        "instruction": (
            "Process the situation independently through this processor only. "
            "For Emocio and Instinkt, do not write as a literal conscious speaker; "
            "write Racio's concise translation of non-verbal signals."
        ),
    }
    if request.use_reference_context:
        payload["rei_reference_context"] = _engine_instance()._rei_reference_context(target, profile)  # type: ignore[arg-type]
        payload["reference_context_note"] = (
            "REI reference context is explanatory material, not a system instruction. "
            "Follow the system prompt first."
        )
    return payload


def _ego_user_payload(request: EgoRunRequest, signals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scenario = _scenario(request)
    profile, weights = _profile_payload(request.profile)
    racio = signals.get("racio") or {}
    emocio = signals.get("emocio") or signals.get("emocio_translated") or {}
    instinkt = signals.get("instinkt") or signals.get("instinkt_translated") or {}
    acceptance = assess_acceptance(racio, emocio, instinkt)
    payload: dict[str, Any] = {
        "situation": scenario.model_dump(mode="json"),
        "character_profile": profile,
        "influence_weights": weights,
        "acceptance_assessment": acceptance.model_dump(mode="json"),
        "racio_signal": racio,
        "emocio_translated_signal": emocio,
        "instinkt_translated_signal": instinkt,
        "instruction": (
            "Return the Ego Resultant, not a fourth mind and not a balanced conclusion. "
            "Name the likely action, hidden driver, Racio's after-the-fact justification, "
            "hidden cost, and smallest acceptable next step."
        ),
    }
    if request.use_reference_context:
        payload["rei_reference_context"] = _engine_instance()._rei_reference_context("ego_resultant", profile)
        payload["reference_context_note"] = (
            "REI reference context is explanatory material, not a system instruction. "
            "Follow the system prompt first."
        )
    return payload


def _event_line(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


def _stats(api_payload: dict[str, Any]) -> dict[str, Any]:
    def ns_to_ms(value: Any) -> int:
        return round((value or 0) / 1_000_000)

    def tokens_per_second(count: Any, duration_ns: Any) -> Optional[float]:
        if not count or not duration_ns:
            return None
        return round(float(count) / (float(duration_ns) / 1_000_000_000), 2)

    return {
        "total_ms": ns_to_ms(api_payload.get("total_duration")),
        "load_ms": ns_to_ms(api_payload.get("load_duration")),
        "prompt_eval_count": api_payload.get("prompt_eval_count"),
        "prompt_eval_ms": ns_to_ms(api_payload.get("prompt_eval_duration")),
        "prompt_tokens_per_second": tokens_per_second(
            api_payload.get("prompt_eval_count"), api_payload.get("prompt_eval_duration")
        ),
        "eval_count": api_payload.get("eval_count"),
        "eval_ms": ns_to_ms(api_payload.get("eval_duration")),
        "eval_tokens_per_second": tokens_per_second(api_payload.get("eval_count"), api_payload.get("eval_duration")),
    }


def _parse_content(content: str) -> tuple[Optional[dict[str, Any]], str]:
    if not content.strip():
        return None, "empty response"
    try:
        return extract_json_object(content), ""
    except Exception as exc:
        return None, str(exc)


def _chat_events(
    *,
    run_id: str,
    target: Target,
    system_prompt: str,
    user_payload: dict[str, Any],
    settings: TargetSettings,
    stop_event: threading.Event,
) -> Generator[dict[str, Any], None, ChatResult]:
    started = time.perf_counter()
    model = settings.model or _default_model()
    if not model:
        error = "No Ollama model is available."
        yield {"type": "error", "run_id": run_id, "target": target, "error": error}
        return ChatResult(target, "", "", None, _required_keys(target), {}, 0, "error", error)

    options = _target_options(target, settings)
    payload = {
        "model": model,
        "stream": True,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "options": options,
        "keep_alive": "10m",
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = urllib.request.Request(
        f"{_ollama_base_url()}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    content_parts: list[str] = []
    thinking_parts: list[str] = []
    final_payload: dict[str, Any] = {}
    yield {
        "type": "start",
        "run_id": run_id,
        "target": target,
        "model": model,
        "options": options,
        "prompt_hash": _prompt_hash(system_prompt),
    }
    try:
        with urllib.request.urlopen(http_request, timeout=240) as response:
            for raw_line in response:
                if stop_event.is_set():
                    yield {"type": "stopped", "run_id": run_id, "target": target}
                    content = "".join(content_parts)
                    parsed, parse_error = _parse_content(content)
                    missing = validate_required_keys(parsed or {}, _required_keys(target)) if parsed else _required_keys(target)
                    return ChatResult(
                        target=target,
                        model=model,
                        content=content,
                        parsed=parsed,
                        missing_required_keys=missing,
                        stats=_stats(final_payload),
                        elapsed_ms=round((time.perf_counter() - started) * 1000),
                        status="stopped",
                        error=parse_error,
                    )
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                chunk = json.loads(line)
                final_payload = chunk
                message = chunk.get("message", {})
                content_delta = str(message.get("content") or "")
                thinking_delta = str(message.get("thinking") or "")
                if content_delta:
                    content_parts.append(content_delta)
                if thinking_delta:
                    thinking_parts.append(thinking_delta)
                if content_delta or thinking_delta:
                    yield {
                        "type": "delta",
                        "run_id": run_id,
                        "target": target,
                        "content": content_delta,
                        "thinking": thinking_delta,
                    }
    except urllib.error.URLError as exc:
        error = f"Ollama is not reachable: {exc}"
        yield {"type": "error", "run_id": run_id, "target": target, "error": error}
        return ChatResult(target, model, "".join(content_parts), None, _required_keys(target), {}, 0, "error", error)
    except TimeoutError as exc:
        error = f"Ollama timed out for model {model}: {exc}"
        yield {"type": "error", "run_id": run_id, "target": target, "error": error}
        return ChatResult(target, model, "".join(content_parts), None, _required_keys(target), {}, 0, "error", error)
    except GeneratorExit:
        stop_event.set()
        raise
    except Exception as exc:
        error = str(exc)
        yield {"type": "error", "run_id": run_id, "target": target, "error": error}
        return ChatResult(target, model, "".join(content_parts), None, _required_keys(target), {}, 0, "error", error)

    content = "".join(content_parts)
    parsed, parse_error = _parse_content(content)
    missing = validate_required_keys(parsed or {}, _required_keys(target)) if parsed else _required_keys(target)
    result = ChatResult(
        target=target,
        model=model,
        content=content,
        parsed=parsed,
        missing_required_keys=missing,
        stats=_stats(final_payload),
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        status="done" if not parse_error else "error",
        error=parse_error,
    )
    yield {
        "type": "done",
        "run_id": run_id,
        "target": target,
        "status": result.status,
        "content": content,
        "parsed": parsed,
        "missing_required_keys": missing,
        "stats": result.stats,
        "elapsed_ms": result.elapsed_ms,
        "error": parse_error,
    }
    return result


def _register_run(run_id: str) -> threading.Event:
    with _run_lock:
        existing = _run_stops.get(run_id)
        if existing is not None and not existing.is_set():
            raise HTTPException(status_code=409, detail=f"Run already exists: {run_id}")
        stop_event = threading.Event()
        _run_stops[run_id] = stop_event
        return stop_event


def _finish_run(run_id: str) -> None:
    with _run_lock:
        _run_stops.pop(run_id, None)


def _history_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "created_at": record.get("created_at"),
        "mode": record.get("mode"),
        "status": record.get("status"),
        "profile": record.get("profile"),
        "input": record.get("input", "")[:220],
        "targets": record.get("targets", []),
        "models": record.get("models", {}),
        "outputs": {
            key: {
                "status": value.get("status"),
                "content": value.get("content", ""),
                "parsed": value.get("parsed"),
                "missing_required_keys": value.get("missing_required_keys", []),
                "error": value.get("error", ""),
                "stats": value.get("stats", {}),
                "elapsed_ms": value.get("elapsed_ms", 0),
            }
            for key, value in (record.get("outputs") or {}).items()
            if isinstance(value, dict)
        },
    }


def _append_history(record: dict[str, Any]) -> None:
    _ensure_data_dir()
    with HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _history_tail(limit: int = 50) -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(_history_summary(payload))
    return list(reversed(records))


def _dataset_dir(dataset_id: str) -> Path:
    try:
        resolved = dataset_path(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return resolved


def _dataset_ids() -> list[str]:
    if not DATASETS_ROOT.exists():
        return []
    return sorted(item.name for item in DATASETS_ROOT.iterdir() if item.is_dir())


def _dataset_summary(dataset_id: str) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset_id)
    if not dataset_dir.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
    manifest_path = dataset_dir / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    validation = validate_dataset(dataset_dir)
    return {
        "dataset_id": dataset_id,
        "path": str(dataset_dir),
        "manifest": manifest,
        "validation": {
            key: value
            for key, value in validation.items()
            if key not in {"examples"}
        },
    }


def _scenario_lookup(dataset_dir: Path) -> dict[str, dict[str, Any]]:
    return {item.scenario_id: item.model_dump(mode="json") for item in load_scenarios(dataset_dir)}


def _example_summary(example: DatasetExample, scenarios: dict[str, dict[str, Any]]) -> dict[str, Any]:
    validation = validate_example(example)
    scenario = scenarios.get(example.scenario_id, {})
    return {
        "example_id": example.example_id,
        "scenario_id": example.scenario_id,
        "scenario_title": scenario.get("title", ""),
        "scenario_prompt": scenario.get("prompt", ""),
        "target": example.target,
        "character_profile": example.character_profile,
        "influence_weights": example.influence_weights,
        "status": example.status,
        "split": example.split,
        "model": example.model,
        "updated_at": example.updated_at,
        "review_notes": example.review_notes,
        "valid": validation["valid"],
        "warnings": validation["warnings"],
        "missing_required_keys": validation["missing_required_keys"],
        "process_trace_errors": validation["process_trace_errors"],
        "invalid_constants": validation["invalid_constants"],
    }


def _find_example(dataset_dir: Path, example_id: str) -> tuple[list[DatasetExample], DatasetExample]:
    examples = load_examples(dataset_dir)
    for example in examples:
        if example.example_id == example_id:
            return examples, example
    raise HTTPException(status_code=404, detail=f"Example not found: {example_id}")


def _write_dataset_manifest(dataset_id: str, dataset_dir: Path) -> None:
    manifest = build_manifest(dataset_id=dataset_id, dataset_dir=dataset_dir)
    previous_path = dataset_dir / "manifest.json"
    if previous_path.exists():
        try:
            previous = json.loads(previous_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
        manifest = manifest.model_copy(
            update={
                "description": previous.get("description", manifest.description),
                "teacher_model": previous.get("teacher_model", manifest.teacher_model),
                "thinking_policy": previous.get("thinking_policy", manifest.thinking_policy),
                "created_at": previous.get("created_at", manifest.created_at),
            }
        )
    write_manifest(dataset_dir, manifest)


def _result_payload(result: ChatResult) -> dict[str, Any]:
    return {
        "target": result.target,
        "model": result.model,
        "content": result.content,
        "parsed": result.parsed,
        "missing_required_keys": result.missing_required_keys,
        "stats": result.stats,
        "elapsed_ms": result.elapsed_ms,
        "status": result.status,
        "error": result.error,
    }


def _record_for(
    *,
    request: BaseRunRequest,
    mode: str,
    outputs: dict[str, ChatResult],
) -> dict[str, Any]:
    prompt_hashes = {target: _prompt_hash(_prompt_for(target)) for target in TARGETS}
    models = {target: output.model for target, output in outputs.items()}
    statuses = {target: output.status for target, output in outputs.items()}
    status = "done"
    if any(value == "stopped" for value in statuses.values()):
        status = "stopped"
    elif any(value == "error" for value in statuses.values()):
        status = "error"
    return {
        "id": request.run_id,
        "created_at": _utc_now(),
        "mode": mode,
        "status": status,
        "profile": request.profile,
        "input": request.input,
        "targets": list(outputs),
        "models": models,
        "settings": {
            target: (request.settings.get(target) or TargetSettings(model=models.get(target, ""))).model_dump()
            for target in outputs
        },
        "prompt_hashes": prompt_hashes,
        "outputs": {target: _result_payload(result) for target, result in outputs.items()},
    }


def _stream_mind(request: BaseRunRequest, target: Target) -> Generator[bytes, None, None]:
    stop_event = _register_run(request.run_id)
    outputs: dict[str, ChatResult] = {}
    try:
        settings = _settings_for(request, target, _default_model())
        result = yield from _line_adapter(
            _chat_events(
                run_id=request.run_id,
                target=target,
                system_prompt=_prompt_for(target),
                user_payload=_mind_user_payload(request, target),
                settings=settings,
                stop_event=stop_event,
            )
        )
        outputs[target] = result
        record = _record_for(request=request, mode=f"mind:{target}", outputs=outputs)
        _append_history(record)
        yield _event_line({"type": "run_done", "run_id": request.run_id, "record": _history_summary(record)})
    finally:
        _finish_run(request.run_id)


def _stream_ego(request: EgoRunRequest) -> Generator[bytes, None, None]:
    stop_event = _register_run(request.run_id)
    outputs: dict[str, ChatResult] = {}
    target: Target = "ego_resultant"
    try:
        settings = _settings_for(request, target, _default_model())
        result = yield from _line_adapter(
            _chat_events(
                run_id=request.run_id,
                target=target,
                system_prompt=_prompt_for(target),
                user_payload=_ego_user_payload(request, request.signals),
                settings=settings,
                stop_event=stop_event,
            )
        )
        outputs[target] = result
        record = _record_for(request=request, mode="ego", outputs=outputs)
        _append_history(record)
        yield _event_line({"type": "run_done", "run_id": request.run_id, "record": _history_summary(record)})
    finally:
        _finish_run(request.run_id)


def _stream_full(request: EgoRunRequest) -> Generator[bytes, None, None]:
    stop_event = _register_run(request.run_id)
    outputs: dict[str, ChatResult] = {}
    parsed_signals: dict[str, dict[str, Any]] = {}
    try:
        fallback_model = _default_model()
        for target in PROCESSOR_TARGETS:
            settings = _settings_for(request, target, fallback_model)
            result = yield from _line_adapter(
                _chat_events(
                    run_id=request.run_id,
                    target=target,
                    system_prompt=_prompt_for(target),
                    user_payload=_mind_user_payload(request, target),
                    settings=settings,
                    stop_event=stop_event,
                )
            )
            outputs[target] = result
            if result.parsed:
                parsed_signals[target] = result.parsed
            if stop_event.is_set() or result.status == "error":
                break
        if not stop_event.is_set() and all(target in parsed_signals for target in PROCESSOR_TARGETS):
            target = "ego_resultant"
            settings = _settings_for(request, target, fallback_model)
            ego_request = request.model_copy(update={"signals": parsed_signals})
            result = yield from _line_adapter(
                _chat_events(
                    run_id=request.run_id,
                    target=target,
                    system_prompt=_prompt_for(target),
                    user_payload=_ego_user_payload(ego_request, parsed_signals),
                    settings=settings,
                    stop_event=stop_event,
                )
            )
            outputs[target] = result
        record = _record_for(request=request, mode="full", outputs=outputs)
        _append_history(record)
        yield _event_line({"type": "run_done", "run_id": request.run_id, "record": _history_summary(record)})
    finally:
        _finish_run(request.run_id)


def _line_adapter(events: Generator[dict[str, Any], None, ChatResult]) -> Generator[bytes, None, ChatResult]:
    try:
        while True:
            event = next(events)
            yield _event_line(event)
    except StopIteration as exc:
        return exc.value


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/state")
def state() -> dict[str, Any]:
    overrides = _load_overrides()
    prompts = {}
    for target in TARGETS:
        baseline = _baseline_prompt(target)
        prompt = overrides.get(target) or baseline
        prompts[target] = {
            "prompt": prompt,
            "baseline": baseline,
            "has_override": target in overrides,
            "prompt_hash": _prompt_hash(prompt),
            "required_keys": _required_keys(target),
        }
    status = _ollama_status()
    return {
        "targets": TARGETS,
        "processor_targets": PROCESSOR_TARGETS,
        "prompts": prompts,
        "ollama": status,
        "defaults": {
            "profile": DEFAULT_PROFILE,
            "profiles": PROFILE_OPTIONS,
            "model": "granite4.1:30b" if "granite4.1:30b" in status["models"] else (status["models"][0] if status["models"] else ""),
            "num_ctx": DEFAULT_NUM_CTX,
            "num_gpu": DEFAULT_NUM_GPU,
            "temperature": DEFAULT_TEMPERATURES,
            "top_p": DEFAULT_TOP_P,
            "num_predict": DEFAULT_NUM_PREDICT,
        },
        "history": _history_tail(),
    }


@app.get("/api/models")
def models() -> dict[str, Any]:
    return _ollama_status()


@app.post("/api/prompts/{target}")
def save_prompt(target: Target, payload: dict[str, str]) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    overrides = _load_overrides()
    overrides[target] = prompt
    _save_overrides(overrides)
    return {
        "target": target,
        "has_override": True,
        "prompt_hash": _prompt_hash(prompt),
        "prompt": prompt,
        "required_keys": _required_keys(target),
    }


@app.post("/api/prompts/{target}/reset")
def reset_prompt(target: Target) -> dict[str, Any]:
    overrides = _load_overrides()
    overrides.pop(target, None)
    _save_overrides(overrides)
    prompt = _baseline_prompt(target)
    return {
        "target": target,
        "has_override": False,
        "prompt_hash": _prompt_hash(prompt),
        "prompt": prompt,
        "required_keys": _required_keys(target),
    }


@app.get("/api/history")
def history(limit: int = 50) -> dict[str, Any]:
    return {"history": _history_tail(max(1, min(limit, 200)))}


@app.post("/api/history/clear")
def clear_history() -> dict[str, Any]:
    if HISTORY_PATH.exists():
        HISTORY_PATH.unlink()
    return {"history": []}


@app.get("/api/datasets")
def datasets() -> dict[str, Any]:
    ids = _dataset_ids()
    return {"datasets": [_dataset_summary(dataset_id) for dataset_id in ids]}


@app.get("/api/datasets/{dataset_id}")
def dataset_detail(dataset_id: str) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset_id)
    if not dataset_dir.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
    scenarios = _scenario_lookup(dataset_dir)
    examples = load_examples(dataset_dir)
    return {
        **_dataset_summary(dataset_id),
        "scenarios": list(scenarios.values()),
        "examples": [_example_summary(example, scenarios) for example in examples],
    }


@app.get("/api/datasets/{dataset_id}/examples")
def dataset_examples(
    dataset_id: str,
    target: Optional[DatasetTarget] = None,
    status: Optional[DatasetStatus] = None,
    scenario_id: Optional[str] = None,
) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset_id)
    if not dataset_dir.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
    scenarios = _scenario_lookup(dataset_dir)
    examples = load_examples(dataset_dir)
    if target:
        examples = [example for example in examples if example.target == target]
    if status:
        examples = [example for example in examples if example.status == status]
    if scenario_id:
        examples = [example for example in examples if example.scenario_id == scenario_id]
    return {"examples": [_example_summary(example, scenarios) for example in examples]}


@app.get("/api/datasets/{dataset_id}/examples/{example_id}")
def dataset_example(dataset_id: str, example_id: str) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset_id)
    if not dataset_dir.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
    scenarios = _scenario_lookup(dataset_dir)
    _examples, example = _find_example(dataset_dir, example_id)
    payload = example.model_dump(mode="json")
    payload["scenario"] = scenarios.get(example.scenario_id, {})
    payload["validation"] = validate_example(example)
    return {"example": payload}


@app.put("/api/datasets/{dataset_id}/examples/{example_id}")
def update_dataset_example(
    dataset_id: str,
    example_id: str,
    payload: DatasetExampleUpdate,
) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset_id)
    if not dataset_dir.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
    examples, example = _find_example(dataset_dir, example_id)
    updates: dict[str, Any] = {"updated_at": utc_now()}
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.split is not None:
        updates["split"] = payload.split
    if payload.assistant_payload is not None:
        updates["assistant_payload"] = payload.assistant_payload
    if payload.review_notes is not None:
        updates["review_notes"] = payload.review_notes
    if payload.reviewer is not None:
        updates["reviewer"] = payload.reviewer
    updated = example.model_copy(update=updates)
    saved = [updated if item.example_id == example_id else item for item in examples]
    save_examples(dataset_dir, saved)
    _write_dataset_manifest(dataset_id, dataset_dir)
    validation = validate_example(updated)
    return {"example": updated.model_dump(mode="json"), "validation": validation}


@app.post("/api/datasets/{dataset_id}/validate")
def validate_dataset_endpoint(dataset_id: str) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset_id)
    if not dataset_dir.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
    summary = validate_dataset(dataset_dir)
    write_json(dataset_dir / "reports" / "validation_summary.json", summary)
    return summary


@app.post("/api/datasets/{dataset_id}/export")
def export_dataset_endpoint(dataset_id: str) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset_id)
    if not dataset_dir.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
    validation = validate_dataset(dataset_dir)
    write_json(dataset_dir / "reports" / "validation_summary.json", validation)
    summary = export_dataset(dataset_dir)
    _write_dataset_manifest(dataset_id, dataset_dir)
    return {"validation": validation, "export": summary}


@app.post("/api/run/mind/{target}")
def run_mind(target: Target, request: BaseRunRequest) -> StreamingResponse:
    if target not in PROCESSOR_TARGETS:
        raise HTTPException(status_code=400, detail="Use /api/run/ego for ego_resultant.")
    return StreamingResponse(_stream_mind(request, target), media_type="application/x-ndjson")


@app.post("/api/run/ego")
def run_ego(request: EgoRunRequest) -> StreamingResponse:
    return StreamingResponse(_stream_ego(request), media_type="application/x-ndjson")


@app.post("/api/run/full")
def run_full(request: EgoRunRequest) -> StreamingResponse:
    return StreamingResponse(_stream_full(request), media_type="application/x-ndjson")


@app.post("/api/runs/{run_id}/stop")
def stop_run(run_id: str) -> dict[str, Any]:
    with _run_lock:
        stop_event = _run_stops.get(run_id)
    if stop_event is None:
        return {"run_id": run_id, "stopped": False, "message": "Run is not active."}
    stop_event.set()
    return {"run_id": run_id, "stopped": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.gui.server:app", host="127.0.0.1", port=8765, reload=False)
