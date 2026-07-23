"""Explicit Ollama-backed native Racio provider.

Only Racio crosses this text-model boundary.  Emocio and Instinkt remain
independent native processors, and the provider never receives character or
governance state.  Every selected runtime option and the full local model
digest are frozen before execution and carried into the run manifest.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib import error, parse, request

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
)
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ProviderParameter,
    ensure_call_contract,
    ensure_call_record_contract,
)
from ..models.racio import RacioInputPacket, RacioNativeConclusion
from ..racio.contracts import RacioStructuredOutput
from ..racio.text_reasoner_adapter import RACIO_STRUCTURED_INSTRUCTION
from .deterministic import (
    DeterministicEmocioNativeProvider,
    DeterministicInstinktNativeProvider,
    build_deterministic_native_providers,
)
from .native import ExecutionClock, build_provider_call_spec


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "granite4.1:30b"
DEFAULT_OLLAMA_SEED = 314159
DEFAULT_OLLAMA_NUM_CTX = 65536
DEFAULT_OLLAMA_NUM_GPU = 999
DEFAULT_OLLAMA_NUM_PREDICT = 1536
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 600.0
DEFAULT_OLLAMA_KEEP_ALIVE = "10m"
MAX_OLLAMA_RESPONSE_BYTES = 4 * 1024 * 1024
OLLAMA_PROVIDER_REVISION = "rei-native-ollama-racio-b14-v1"
OLLAMA_NO_FALLBACK_REASON = (
    "The native Ollama Racio smoke has no hidden retry or fallback provider."
)


class OllamaProviderError(RuntimeError):
    """Base class for safe, prompt-free Ollama integration failures."""


class OllamaTransportError(OllamaProviderError):
    """The Ollama HTTP boundary failed before a valid response was available."""


class OllamaResponseError(OllamaProviderError):
    """Ollama returned a response that does not close the approved contract."""


class OllamaJsonTransport(Protocol):
    def request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]: ...


class _NoRedirectHandler(request.HTTPRedirectHandler):
    """Never move a local prompt across an unapproved HTTP boundary."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


@dataclass(frozen=True, slots=True)
class UrllibOllamaTransport:
    """Small standard-library transport with a bounded response body."""

    def request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        body = None if payload is None else canonical_json_bytes(payload)
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        http_request = request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        opener = request.build_opener(
            request.ProxyHandler({}),
            _NoRedirectHandler(),
        )
        try:
            with opener.open(http_request, timeout=timeout_seconds) as response:
                raw = response.read(max_response_bytes + 1)
        except error.HTTPError as exc:
            raise OllamaTransportError(
                f"Ollama HTTP request failed with status {exc.code}"
            ) from exc
        except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise OllamaTransportError("Ollama HTTP request failed") from exc
        if len(raw) > max_response_bytes:
            raise OllamaTransportError("Ollama response exceeded the configured limit")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaTransportError("Ollama returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise OllamaTransportError("Ollama response must be a JSON object")
        return decoded


def _validated_base_url(value: str, *, allow_remote: bool) -> str:
    parsed = parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("Ollama base URL must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Ollama base URL must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Ollama base URL must not contain a path, query, or fragment")
    if not allow_remote:
        hostname = parsed.hostname.rstrip(".").lower()
        loopback = hostname == "localhost"
        if not loopback:
            try:
                loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                loopback = False
        if not loopback:
            raise ValueError(
                "Remote Ollama endpoints require explicit allow_remote=True"
            )
    return value.rstrip("/")


@dataclass(frozen=True, slots=True)
class OllamaApiClient:
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    allow_remote: bool = False
    transport: OllamaJsonTransport = UrllibOllamaTransport()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "base_url",
            _validated_base_url(self.base_url, allow_remote=self.allow_remote),
        )

    def get(self, path: str, *, timeout_seconds: float = 10.0) -> Mapping[str, Any]:
        return self.transport.request_json(
            method="GET",
            url=f"{self.base_url}{path}",
            payload=None,
            timeout_seconds=timeout_seconds,
            max_response_bytes=MAX_OLLAMA_RESPONSE_BYTES,
        )

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        return self.transport.request_json(
            method="POST",
            url=f"{self.base_url}{path}",
            payload=payload,
            timeout_seconds=timeout_seconds,
            max_response_bytes=MAX_OLLAMA_RESPONSE_BYTES,
        )

    def version(self) -> str:
        value = self.get("/api/version").get("version")
        if not isinstance(value, str) or not value.strip():
            raise OllamaResponseError("Ollama version response is missing version")
        return value.strip()

    def model_entry(self, model: str) -> Mapping[str, Any]:
        models = self.get("/api/tags").get("models")
        if not isinstance(models, list):
            raise OllamaResponseError("Ollama tags response is missing models")
        matches = [
            item
            for item in models
            if isinstance(item, dict)
            and (item.get("name") == model or item.get("model") == model)
        ]
        if len(matches) != 1:
            raise OllamaResponseError(
                f"Expected exactly one local Ollama model named {model!r}"
            )
        selected = matches[0]
        if selected.get("remote_model") or selected.get("remote_host"):
            raise OllamaResponseError("Selected Ollama model is remote, not local")
        return selected

    def show(self, model: str) -> Mapping[str, Any]:
        response = self.post(
            "/api/show",
            {"model": model, "verbose": False},
            timeout_seconds=30.0,
        )
        if response.get("remote_model") or response.get("remote_host"):
            raise OllamaResponseError("Selected Ollama model details are remote")
        return response

    def ps(self) -> Mapping[str, Any]:
        return self.get("/api/ps")

    def generate(
        self,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        return self.post("/api/generate", payload, timeout_seconds=timeout_seconds)


def _environment_int(
    environ: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int,
) -> int:
    raw = environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _environment_bool(
    environ: Mapping[str, str],
    name: str,
    default: bool,
) -> bool:
    raw = environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


@dataclass(frozen=True, slots=True)
class OllamaRacioSettings:
    model: str = DEFAULT_OLLAMA_MODEL
    seed: int = DEFAULT_OLLAMA_SEED
    temperature: float = 0.0
    num_ctx: int = DEFAULT_OLLAMA_NUM_CTX
    num_gpu: int = DEFAULT_OLLAMA_NUM_GPU
    num_predict: int = DEFAULT_OLLAMA_NUM_PREDICT
    timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS
    keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE
    require_full_gpu: bool = False

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Ollama model must be non-empty")
        if self.seed < 0:
            raise ValueError("Ollama seed must be non-negative")
        if self.num_ctx < 1 or self.num_gpu < 0 or self.num_predict < 1:
            raise ValueError("Ollama context, GPU, and prediction options are invalid")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Ollama timeout must be positive")
        if not math.isfinite(self.temperature) or self.temperature < 0:
            raise ValueError("Ollama temperature cannot be negative")
        if not self.keep_alive.strip():
            raise ValueError("Ollama keep_alive must be non-empty")
        if not isinstance(self.require_full_gpu, bool):
            raise ValueError("Ollama require_full_gpu must be boolean")

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "OllamaRacioSettings":
        active = os.environ if environ is None else environ
        return cls(
            model=active.get("REI_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            seed=_environment_int(
                active,
                "REI_OLLAMA_SEED",
                DEFAULT_OLLAMA_SEED,
                minimum=0,
            ),
            num_ctx=_environment_int(
                active,
                "REI_OLLAMA_NUM_CTX",
                DEFAULT_OLLAMA_NUM_CTX,
                minimum=1,
            ),
            num_gpu=_environment_int(
                active,
                "REI_OLLAMA_NUM_GPU",
                DEFAULT_OLLAMA_NUM_GPU,
                minimum=0,
            ),
            num_predict=_environment_int(
                active,
                "REI_OLLAMA_NUM_PREDICT",
                DEFAULT_OLLAMA_NUM_PREDICT,
                minimum=1,
            ),
            keep_alive=active.get(
                "REI_OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE
            ),
            require_full_gpu=_environment_bool(
                active,
                "REI_OLLAMA_REQUIRE_FULL_GPU",
                False,
            ),
        )


@dataclass(frozen=True, slots=True)
class OllamaRuntimeModel:
    server_version: str
    model: str
    digest: HashDigest
    size_bytes: int
    quantization_level: str | None
    context_length: int
    capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OllamaActiveModel:
    model: str
    digest: HashDigest
    size_bytes: int
    size_vram_bytes: int
    context_length: int
    gpu_percent_rounded: int

    @property
    def full_gpu(self) -> bool:
        """True only when Ollama reports every active model byte in VRAM."""

        return self.size_vram_bytes == self.size_bytes


def inspect_ollama_runtime(
    client: OllamaApiClient,
    model: str,
    *,
    expected_digest: str | None = None,
) -> OllamaRuntimeModel:
    server_version = client.version()
    entry = client.model_entry(model)
    shown = client.show(model)
    digest = entry.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise OllamaResponseError("Local Ollama model is missing a full digest")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise OllamaResponseError("Local Ollama model digest is not hexadecimal") from exc
    digest = digest.lower()
    if expected_digest is not None and digest != expected_digest.lower():
        raise OllamaResponseError("Local Ollama model digest differs from expectation")
    size = entry.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise OllamaResponseError("Local Ollama model size is invalid")
    tag_details = entry.get("details")
    tag_details = tag_details if isinstance(tag_details, dict) else {}
    shown_details = shown.get("details")
    shown_details = shown_details if isinstance(shown_details, dict) else {}
    quantization = shown_details.get(
        "quantization_level", tag_details.get("quantization_level")
    )
    if quantization is not None and not isinstance(quantization, str):
        raise OllamaResponseError("Ollama quantization metadata is invalid")
    tag_quantization = tag_details.get("quantization_level")
    if (
        tag_quantization is not None
        and quantization is not None
        and tag_quantization != quantization
    ):
        raise OllamaResponseError("Ollama quantization metadata is inconsistent")
    model_info = shown.get("model_info")
    if not isinstance(model_info, dict):
        raise OllamaResponseError("Ollama show response is missing model_info")
    architecture = model_info.get("general.architecture")
    if not isinstance(architecture, str) or not architecture:
        raise OllamaResponseError("Ollama show response is missing architecture")
    context_length = model_info.get(f"{architecture}.context_length")
    if (
        not isinstance(context_length, int)
        or isinstance(context_length, bool)
        or context_length <= 0
    ):
        raise OllamaResponseError("Ollama context metadata is invalid")
    tag_context_length = tag_details.get("context_length")
    if tag_context_length is not None and tag_context_length != context_length:
        raise OllamaResponseError("Ollama context metadata is inconsistent")
    capabilities_value = shown.get("capabilities", entry.get("capabilities"))
    if not isinstance(capabilities_value, list) or not all(
        isinstance(item, str) for item in capabilities_value
    ):
        raise OllamaResponseError("Ollama capability metadata is invalid")
    capabilities = tuple(sorted(set(capabilities_value)))
    if "completion" not in capabilities:
        raise OllamaResponseError("Selected Ollama model lacks text completion")
    tag_capabilities = entry.get("capabilities")
    if tag_capabilities is not None:
        if not isinstance(tag_capabilities, list) or not all(
            isinstance(item, str) for item in tag_capabilities
        ):
            raise OllamaResponseError("Ollama tag capabilities are invalid")
        canonical_tag_capabilities = tuple(sorted(set(tag_capabilities)))
        if (
            "completion" not in canonical_tag_capabilities
            or not set(canonical_tag_capabilities).issubset(capabilities)
        ):
            raise OllamaResponseError("Ollama capability metadata is inconsistent")
    return OllamaRuntimeModel(
        server_version=server_version,
        model=model,
        digest=digest,
        size_bytes=size,
        quantization_level=quantization,
        context_length=context_length,
        capabilities=capabilities,
    )


def inspect_ollama_active_model(
    client: OllamaApiClient,
    model: str,
) -> OllamaActiveModel:
    models = client.ps().get("models")
    if not isinstance(models, list):
        raise OllamaResponseError("Ollama ps response is missing models")
    matches = [
        item
        for item in models
        if isinstance(item, dict)
        and (item.get("name") == model or item.get("model") == model)
    ]
    if len(matches) != 1:
        raise OllamaResponseError("Expected the generated model to remain active")
    selected = matches[0]
    if selected.get("remote_model") or selected.get("remote_host"):
        raise OllamaResponseError("Active Ollama model is remote, not local")
    digest = selected.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise OllamaResponseError("Active Ollama model is missing a full digest")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise OllamaResponseError("Active Ollama model digest is invalid") from exc

    def positive_integer(name: str) -> int:
        value = selected.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise OllamaResponseError(f"Active Ollama {name} is invalid")
        return value

    size = positive_integer("size")
    size_vram = positive_integer("size_vram")
    if size_vram > size:
        raise OllamaResponseError("Active Ollama size_vram exceeds total size")
    context_length = positive_integer("context_length")
    gpu_percent = round((size_vram / size) * 100)
    return OllamaActiveModel(
        model=model,
        digest=digest.lower(),
        size_bytes=size,
        size_vram_bytes=size_vram,
        context_length=context_length,
        gpu_percent_rounded=gpu_percent,
    )


class OllamaRacioResponseEvidence(FrozenArtifactModel):
    """Durable evidence for the untrusted structured model response."""

    schema_version: Literal["rei-native-ollama-racio-response-v1"] = (
        "rei-native-ollama-racio-response-v1"
    )
    result_id: NonEmptyId
    packet_id: NonEmptyId
    packet_hash: HashDigest
    call_id: NonEmptyId
    call_spec_hash: HashDigest
    provider_id: NonEmptyId
    model: NonEmptyText
    model_revision: HashDigest
    ollama_server_version: NonEmptyText
    request_payload_hash: HashDigest
    response_envelope_hash: HashDigest
    response_text: str = Field(min_length=1)
    response_created_at: NonEmptyText | None = None
    done_reason: Literal["stop"]
    total_duration_ns: int | None = Field(default=None, ge=0)
    load_duration_ns: int | None = Field(default=None, ge=0)
    prompt_eval_count: int | None = Field(default=None, ge=0)
    prompt_eval_duration_ns: int | None = Field(default=None, ge=0)
    eval_count: int | None = Field(default=None, ge=0)
    eval_duration_ns: int | None = Field(default=None, ge=0)
    evidence_ids_used: tuple[NonEmptyId, ...] = ()
    active_context_length: int = Field(gt=0)
    active_size_bytes: int = Field(gt=0)
    active_size_vram_bytes: int = Field(gt=0)
    active_gpu_percent_rounded: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_result_id(self) -> "OllamaRacioResponseEvidence":
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"result_id"},
        )
        if self.result_id != content_id("ollama_racio_response", payload):
            raise ValueError("Ollama response evidence ID is not content-addressed")
        return self

    @classmethod
    def create(
        cls,
        *,
        packet: RacioInputPacket,
        call: ProviderCallSpec,
        runtime: OllamaRuntimeModel,
        request_payload: Mapping[str, Any],
        response: Mapping[str, Any],
        structured: RacioStructuredOutput,
        placement: OllamaActiveModel,
    ) -> "OllamaRacioResponseEvidence":
        response_text = response.get("response")
        if not isinstance(response_text, str) or not response_text.strip():
            raise OllamaResponseError("Ollama generation response is empty")

        def optional_non_empty(name: str) -> str | None:
            value = response.get(name)
            if value is None:
                return None
            if not isinstance(value, str) or not value.strip():
                raise OllamaResponseError(f"Ollama {name} metadata is invalid")
            return value

        def optional_count(name: str) -> int | None:
            value = response.get(name)
            if value is None:
                return None
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise OllamaResponseError(f"Ollama {name} metadata is invalid")
            return value

        base = {
            "schema_version": "rei-native-ollama-racio-response-v1",
            "packet_id": packet.packet_id,
            "packet_hash": packet.content_hash(),
            "call_id": call.call_id,
            "call_spec_hash": call.content_hash(),
            "provider_id": call.provider.provider_id,
            "model": runtime.model,
            "model_revision": runtime.digest,
            "ollama_server_version": runtime.server_version,
            "request_payload_hash": sha256_hex(request_payload),
            "response_envelope_hash": sha256_hex(response),
            "response_text": response_text,
            "response_created_at": optional_non_empty("created_at"),
            "done_reason": optional_non_empty("done_reason"),
            "total_duration_ns": optional_count("total_duration"),
            "load_duration_ns": optional_count("load_duration"),
            "prompt_eval_count": optional_count("prompt_eval_count"),
            "prompt_eval_duration_ns": optional_count("prompt_eval_duration"),
            "eval_count": optional_count("eval_count"),
            "eval_duration_ns": optional_count("eval_duration"),
            "evidence_ids_used": structured.evidence_ids_used,
            "active_context_length": placement.context_length,
            "active_size_bytes": placement.size_bytes,
            "active_size_vram_bytes": placement.size_vram_bytes,
            "active_gpu_percent_rounded": placement.gpu_percent_rounded,
        }
        return cls(
            result_id=content_id("ollama_racio_response", base),
            **base,
        )

    def validate_against(
        self,
        *,
        packet: RacioInputPacket,
        call: ProviderCallSpec,
        runtime: OllamaRuntimeModel,
        placement: OllamaActiveModel,
        request_payload: Mapping[str, Any],
        response: Mapping[str, Any],
        structured: RacioStructuredOutput,
    ) -> "OllamaRacioResponseEvidence":
        if self.packet_id != packet.packet_id or self.packet_hash != packet.content_hash():
            raise ValueError("Ollama evidence differs from the Racio packet")
        if self.call_id != call.call_id or self.call_spec_hash != call.content_hash():
            raise ValueError("Ollama evidence differs from the approved call")
        if self.provider_id != call.provider.provider_id:
            raise ValueError("Ollama evidence differs from the provider identity")
        if (
            self.model != runtime.model
            or self.model_revision != runtime.digest
            or self.ollama_server_version != runtime.server_version
            or call.provider.model != runtime.model
            or call.provider.model_revision != runtime.digest
        ):
            raise ValueError("Ollama evidence differs from model provenance")
        if (
            placement.model != runtime.model
            or placement.digest != runtime.digest
            or self.active_context_length != placement.context_length
            or self.active_size_bytes != placement.size_bytes
            or self.active_size_vram_bytes != placement.size_vram_bytes
            or self.active_gpu_percent_rounded != placement.gpu_percent_rounded
        ):
            raise ValueError("Ollama evidence differs from active model placement")
        if (
            self.request_payload_hash != sha256_hex(request_payload)
            or self.response_envelope_hash != sha256_hex(response)
            or self.response_text != response.get("response")
            or self.evidence_ids_used != structured.evidence_ids_used
        ):
            raise ValueError("Ollama evidence differs from request or response bytes")
        return self


@dataclass(frozen=True, slots=True)
class OllamaRacioNativeExecution:
    conclusion: RacioNativeConclusion
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord
    reasoning_artifact: OllamaRacioResponseEvidence

    def __post_init__(self) -> None:
        ensure_call_record_contract(self.call_spec, self.call_record)
        if self.call_record.status != "succeeded":
            raise ValueError("Ollama native Racio execution must succeed directly")
        if self.call_record.output_artifact_ids != (
            self.reasoning_artifact.result_id,
            self.conclusion.conclusion_id,
        ):
            raise ValueError("Ollama provider must publish evidence then conclusion")
        if (
            self.conclusion.reasoning_provider_result_id
            != self.reasoning_artifact.result_id
            or self.conclusion.reasoning_provider_result_hash
            != self.reasoning_artifact.content_hash()
        ):
            raise ValueError("Racio conclusion does not close its response evidence")
        if (
            self.reasoning_artifact.packet_id != self.conclusion.source_packet_id
            or self.reasoning_artifact.packet_hash
            != self.conclusion.source_packet_hash
            or self.reasoning_artifact.call_id != self.call_spec.call_id
            or self.reasoning_artifact.call_spec_hash
            != self.call_spec.content_hash()
            or self.reasoning_artifact.provider_id
            != self.call_spec.provider.provider_id
            or self.reasoning_artifact.model != self.call_spec.provider.model
            or self.reasoning_artifact.model_revision
            != self.call_spec.provider.model_revision
            or self.reasoning_artifact.evidence_ids_used
            != self.conclusion.evidence_ids_used
        ):
            raise ValueError("Ollama response evidence has inconsistent lineage")


def _parameter(name: str, value: Any) -> ProviderParameter:
    return ProviderParameter(
        name=name,
        canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
    )


@dataclass(frozen=True, slots=True)
class OllamaRacioNativeProvider:
    client: OllamaApiClient
    runtime: OllamaRuntimeModel
    settings: OllamaRacioSettings
    expected_digest: HashDigest | None = None

    def __post_init__(self) -> None:
        if self.runtime.model != self.settings.model:
            raise ValueError("Ollama runtime and provider settings select different models")
        if self.settings.num_ctx > self.runtime.context_length:
            raise ValueError("Requested context exceeds the local model context length")
        if (
            self.expected_digest is not None
            and self.expected_digest != self.runtime.digest
        ):
            raise ValueError("Operator-approved digest differs from Ollama runtime")

    @classmethod
    def discover(
        cls,
        *,
        client: OllamaApiClient,
        settings: OllamaRacioSettings,
        expected_digest: str | None = None,
    ) -> "OllamaRacioNativeProvider":
        approved_digest = (
            expected_digest.lower() if expected_digest is not None else None
        )
        return cls(
            client=client,
            runtime=inspect_ollama_runtime(
                client,
                settings.model,
                expected_digest=approved_digest,
            ),
            settings=settings,
            expected_digest=approved_digest,
        )

    @property
    def identity(self) -> ProviderIdentity:
        payload = {
            "kind": "text_reasoner",
            "implementation": "rei.providers.ollama.OllamaRacioNativeProvider",
            "implementation_revision": (
                f"{OLLAMA_PROVIDER_REVISION};ollama={self.runtime.server_version}"
            ),
            "uses_model": True,
            "model": self.runtime.model,
            "model_revision": self.runtime.digest,
        }
        return ProviderIdentity(
            provider_id=content_id("provider", payload),
            **payload,
        )

    @property
    def parameters(self) -> tuple[ProviderParameter, ...]:
        values = {
            "allow_remote": self.client.allow_remote,
            "endpoint": f"{self.client.base_url}/api/generate",
            "format_schema_sha256": sha256_hex(
                RacioStructuredOutput.model_json_schema()
            ),
            "instruction_sha256": sha256_hex(RACIO_STRUCTURED_INSTRUCTION),
            "keep_alive": self.settings.keep_alive,
            "num_ctx": self.settings.num_ctx,
            "num_gpu": self.settings.num_gpu,
            "num_predict": self.settings.num_predict,
            "ollama_server_version": self.runtime.server_version,
            "operator_expected_model_digest": self.expected_digest,
            "require_full_gpu": self.settings.require_full_gpu,
            "raw": False,
            "logprobs": False,
            "shift": False,
            "stream": False,
            "temperature": self.settings.temperature,
            "think": False,
            "truncate": False,
        }
        return tuple(_parameter(name, values[name]) for name in sorted(values))

    def required_input_artifact_ids(
        self,
        packet: RacioInputPacket,
    ) -> tuple[NonEmptyId, ...]:
        return tuple(
            dict.fromkeys(
                (
                    packet.packet_id,
                    packet.world.world_id,
                    *packet.evidence_ids,
                    *packet.previous_racio_projection_ids,
                )
            )
        )

    def build_call_spec(self, packet: RacioInputPacket) -> ProviderCallSpec:
        return build_provider_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=self.required_input_artifact_ids(packet),
            seed=self.settings.seed,
            parameters=self.parameters,
            timeout_seconds=self.settings.timeout_seconds,
            fallback_policy=ProviderFallbackPolicy(
                mode="none",
                no_fallback_reason=OLLAMA_NO_FALLBACK_REASON,
            ),
        )

    def request_payload(self, packet: RacioInputPacket) -> Mapping[str, Any]:
        return {
            "model": self.settings.model,
            "system": RACIO_STRUCTURED_INSTRUCTION,
            "prompt": canonical_json_bytes(packet).decode("utf-8"),
            "format": RacioStructuredOutput.model_json_schema(),
            "raw": False,
            "logprobs": False,
            "truncate": False,
            "shift": False,
            "stream": False,
            "think": False,
            "keep_alive": self.settings.keep_alive,
            "options": {
                "seed": self.settings.seed,
                "temperature": self.settings.temperature,
                "num_ctx": self.settings.num_ctx,
                "num_gpu": self.settings.num_gpu,
                "num_predict": self.settings.num_predict,
            },
        }

    def execute(
        self,
        packet: RacioInputPacket,
        *,
        call: ProviderCallSpec,
        clock: ExecutionClock,
    ) -> OllamaRacioNativeExecution:
        started_at = clock.timestamp("racio_call_started")
        ensure_call_contract(
            self.identity,
            call,
            request_id=packet.packet_id,
            seed=self.settings.seed,
            expected_kind="text_reasoner",
            required_input_artifact_ids=self.required_input_artifact_ids(packet),
        )
        if call != self.build_call_spec(packet):
            raise ValueError("Ollama Racio call differs from its canonical contract")
        payload = self.request_payload(packet)
        payload_hash = sha256_hex(payload)
        current_runtime = inspect_ollama_runtime(
            self.client,
            self.settings.model,
            expected_digest=self.runtime.digest,
        )
        if current_runtime != self.runtime:
            raise OllamaResponseError(
                "Ollama runtime changed after the call contract was approved"
            )
        response = self.client.generate(
            payload,
            timeout_seconds=call.timeout_seconds,
        )
        if sha256_hex(payload) != payload_hash:
            raise OllamaResponseError("Ollama transport mutated the approved request")
        if response.get("done") is not True:
            raise OllamaResponseError("Ollama generation did not finish")
        if response.get("done_reason") != "stop":
            raise OllamaResponseError("Ollama generation did not stop cleanly")
        if response.get("thinking") not in (None, ""):
            raise OllamaResponseError(
                "Ollama returned unapproved thinking despite think=false"
            )
        if response.get("model") != self.settings.model:
            raise OllamaResponseError("Ollama generated with an unexpected model")
        if response.get("remote_model") or response.get("remote_host"):
            raise OllamaResponseError("Ollama generation used a remote model")
        post_runtime = inspect_ollama_runtime(
            self.client,
            self.settings.model,
            expected_digest=self.runtime.digest,
        )
        if post_runtime != self.runtime:
            raise OllamaResponseError("Ollama runtime changed during generation")
        placement = inspect_ollama_active_model(
            self.client,
            self.settings.model,
        )
        if (
            placement.digest != self.runtime.digest
            or placement.context_length != self.settings.num_ctx
        ):
            raise OllamaResponseError(
                "Active Ollama model differs from approved digest or context"
            )
        if self.settings.require_full_gpu and not placement.full_gpu:
            raise OllamaResponseError("Active Ollama model is not fully GPU-resident")
        response_text = response.get("response")
        if not isinstance(response_text, str):
            raise OllamaResponseError("Ollama generation is missing response text")
        try:
            structured = RacioStructuredOutput.model_validate_json(response_text)
        except (ValueError, TypeError) as exc:
            raise OllamaResponseError(
                "Ollama returned invalid structured Racio output"
            ) from exc
        try:
            structured.validate_against(packet)
        except ValueError as exc:
            raise OllamaResponseError(
                "Ollama structured output exceeds the grounded Racio packet"
            ) from exc
        evidence = OllamaRacioResponseEvidence.create(
            packet=packet,
            call=call,
            runtime=self.runtime,
            request_payload=payload,
            response=response,
            structured=structured,
            placement=placement,
        )
        evidence.validate_against(
            packet=packet,
            call=call,
            runtime=self.runtime,
            placement=placement,
            request_payload=payload,
            response=response,
            structured=structured,
        )
        conclusion = structured.to_conclusion(
            packet,
            reasoning_provider_result_id=evidence.result_id,
            reasoning_provider_result_hash=evidence.content_hash(),
        )
        finished_at = clock.timestamp("racio_call_finished")
        record = ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=call.request_id,
            input_artifact_ids=call.input_artifact_ids,
            provider=call.provider,
            seed=call.seed,
            parameters=call.parameters,
            timeout_seconds=call.timeout_seconds,
            started_at=started_at,
            primary_finished_at=finished_at,
            finished_at=finished_at,
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(evidence.result_id, conclusion.conclusion_id),
            safety_notice=call.safety_notice,
        )
        return OllamaRacioNativeExecution(
            conclusion=conclusion,
            call_spec=call,
            call_record=record,
            reasoning_artifact=evidence,
        )


@dataclass(frozen=True, slots=True)
class OllamaRacioNativeProviders:
    """Mixed provider set: model-backed Racio, deterministic Emocio/Instinkt."""

    racio: OllamaRacioNativeProvider
    emocio: DeterministicEmocioNativeProvider
    instinkt: DeterministicInstinktNativeProvider

    @property
    def identities(self) -> tuple[ProviderIdentity, ...]:
        return (self.racio.identity, self.emocio.identity, self.instinkt.identity)


def build_ollama_racio_native_providers(
    provider: OllamaRacioNativeProvider,
) -> OllamaRacioNativeProviders:
    deterministic = build_deterministic_native_providers()
    return OllamaRacioNativeProviders(
        racio=provider,
        emocio=deterministic.emocio,
        instinkt=deterministic.instinkt,
    )


__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_KEEP_ALIVE",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_NUM_CTX",
    "DEFAULT_OLLAMA_NUM_GPU",
    "DEFAULT_OLLAMA_NUM_PREDICT",
    "DEFAULT_OLLAMA_SEED",
    "DEFAULT_OLLAMA_TIMEOUT_SECONDS",
    "OllamaApiClient",
    "OllamaActiveModel",
    "OllamaProviderError",
    "OllamaRacioNativeExecution",
    "OllamaRacioNativeProvider",
    "OllamaRacioNativeProviders",
    "OllamaRacioResponseEvidence",
    "OllamaRacioSettings",
    "OllamaResponseError",
    "OllamaRuntimeModel",
    "OllamaTransportError",
    "UrllibOllamaTransport",
    "build_ollama_racio_native_providers",
    "inspect_ollama_runtime",
    "inspect_ollama_active_model",
]
