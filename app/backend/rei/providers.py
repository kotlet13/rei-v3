from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from .json_utils import extract_json_object


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaRequest:
    model: str
    system: str
    user: str
    temperature: float = 0.4
    top_p: float = 0.9
    num_predict: int = 280
    think: Optional[Union[str, bool]] = None
    keep_alive: Optional[Union[str, int]] = "10m"
    timeout_seconds: int = 180
    extra_options: dict[str, Any] = field(default_factory=dict)


class OllamaProvider:
    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")
        self.default_options = self._default_options_from_env()

    def list_models(self, timeout_seconds: int = 5) -> list[str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
        return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]

    def chat_json(self, request: OllamaRequest) -> tuple[dict[str, Any], dict[str, Any]]:
        started = time.perf_counter()
        options: dict[str, Any] = {
            "temperature": request.temperature,
            "top_p": request.top_p,
            "num_predict": request.num_predict,
        }
        options.update(self.default_options)
        options.update(request.extra_options)

        payload = {
            "model": request.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "options": options,
        }
        if request.think is not None:
            payload["think"] = request.think
        if request.keep_alive is not None:
            payload["keep_alive"] = request.keep_alive
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout_seconds) as response:
                api_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ProviderError(f"Ollama is not reachable: {exc}") from exc
        except TimeoutError as exc:
            raise ProviderError(f"Ollama timed out for model {request.model}") from exc

        content = api_payload.get("message", {}).get("content", "")
        if not str(content).strip():
            thinking = api_payload.get("message", {}).get("thinking", "")
            raise ProviderError(f"Ollama returned an empty response; thinking_chars={len(str(thinking))}")
        parsed = self._parse_json_object(content)
        diagnostics = {
            "provider": "ollama",
            "model": request.model,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "raw_chars": len(content),
            "thinking_chars": len(str(api_payload.get("message", {}).get("thinking", ""))),
            "stats": self._stats(api_payload),
            "request": {
                "system": request.system,
                "user": request.user,
                "options": options,
                "think": request.think,
                "keep_alive": request.keep_alive,
                "format": "json",
            },
            "response": {
                "content": content,
                "parsed": parsed,
                "message_keys": sorted(api_payload.get("message", {}).keys()),
            },
        }
        return parsed, diagnostics

    @staticmethod
    def _default_options_from_env() -> dict[str, int]:
        options = {
            "num_ctx": 4096,
            "num_thread": 8,
        }
        env_map = {
            "REI_OLLAMA_NUM_CTX": "num_ctx",
            "REI_OLLAMA_NUM_THREAD": "num_thread",
            "REI_OLLAMA_NUM_BATCH": "num_batch",
        }
        for env_name, option_name in env_map.items():
            raw_value = os.getenv(env_name)
            if raw_value is None:
                continue
            try:
                value = int(raw_value)
            except ValueError:
                continue
            if value > 0:
                options[option_name] = value
        return options

    @staticmethod
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
                api_payload.get("prompt_eval_count"),
                api_payload.get("prompt_eval_duration"),
            ),
            "eval_count": api_payload.get("eval_count"),
            "eval_ms": ns_to_ms(api_payload.get("eval_duration")),
            "eval_tokens_per_second": tokens_per_second(
                api_payload.get("eval_count"),
                api_payload.get("eval_duration"),
            ),
        }

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        content = content.strip()
        if not content:
            raise ProviderError("Provider returned an empty response")
        try:
            return extract_json_object(content)
        except (json.JSONDecodeError, ValueError) as exc:
            snippet = content.replace("\n", " ")[:240]
            raise ProviderError(f"Provider did not return a JSON object; content={snippet!r}") from exc


class LMStudioProvider:
    def __init__(self, base_url: str = "http://localhost:1234") -> None:
        self.base_url = base_url.rstrip("/")
        self.context_length = self._int_env("REI_LMSTUDIO_CONTEXT_LENGTH", 4096)

    def list_models(self, timeout_seconds: int = 5) -> list[str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/v1/models", timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
        return [item.get("id", "") for item in payload.get("data", []) if item.get("id")]

    def chat_json(self, request: OllamaRequest) -> tuple[dict[str, Any], dict[str, Any]]:
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "model": request.model,
            "system_prompt": request.system,
            "input": request.user,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_output_tokens": request.num_predict,
            "reasoning": self._reasoning_setting(request.think),
            "context_length": self.context_length,
            "store": False,
        }
        payload.update(self._native_options(request.extra_options))
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/api/v1/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout_seconds) as response:
                api_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ProviderError(f"LM Studio is not reachable: {exc}") from exc
        except TimeoutError as exc:
            raise ProviderError(f"LM Studio timed out for model {request.model}") from exc

        output_items = api_payload.get("output", [])
        content = "".join(
            str(item.get("content", "")) for item in output_items if item.get("type") == "message"
        )
        reasoning_content = "".join(
            str(item.get("content", "")) for item in output_items if item.get("type") == "reasoning"
        )
        if not content.strip():
            raise ProviderError(f"LM Studio returned an empty response; reasoning_chars={len(reasoning_content)}")
        parsed = OllamaProvider._parse_json_object(content)
        stats = self._stats(api_payload.get("stats", {}))
        diagnostics = {
            "provider": "lmstudio",
            "model": request.model,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "raw_chars": len(content),
            "thinking_chars": len(reasoning_content),
            "stats": stats,
            "request": {
                "system": request.system,
                "user": request.user,
                "options": payload,
                "think": request.think,
                "format": "json",
            },
            "response": {
                "content": content,
                "parsed": parsed,
                "output_types": [item.get("type") for item in output_items],
            },
        }
        return parsed, diagnostics

    @staticmethod
    def _reasoning_setting(think: Optional[Union[str, bool]]) -> str:
        if think is True:
            return "on"
        if think is False or think is None:
            return "off"
        return str(think)

    @staticmethod
    def _native_options(extra_options: dict[str, Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        if "num_ctx" in extra_options:
            mapped["context_length"] = extra_options["num_ctx"]
        if "top_k" in extra_options:
            mapped["top_k"] = extra_options["top_k"]
        if "repeat_penalty" in extra_options:
            mapped["repeat_penalty"] = extra_options["repeat_penalty"]
        return mapped

    @staticmethod
    def _stats(stats: dict[str, Any]) -> dict[str, Any]:
        return {
            "prompt_eval_count": stats.get("input_tokens"),
            "eval_count": stats.get("total_output_tokens"),
            "reasoning_output_tokens": stats.get("reasoning_output_tokens"),
            "eval_tokens_per_second": stats.get("tokens_per_second"),
            "time_to_first_token_seconds": stats.get("time_to_first_token_seconds"),
            "model_load_time_seconds": stats.get("model_load_time_seconds"),
        }

    @staticmethod
    def _int_env(name: str, default: int) -> int:
        raw_value = os.getenv(name)
        if raw_value is None:
            return default
        try:
            value = int(raw_value)
        except ValueError:
            return default
        return value if value > 0 else default
