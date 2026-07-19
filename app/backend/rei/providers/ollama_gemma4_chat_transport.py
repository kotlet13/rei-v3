"""Small one-attempt Gemma chat transport extracted for post-G3 bridges.

The historical V2 provider remains byte-identical because its file hash is a
sealed G3 artifact.  This helper reuses that provider's pinned settings,
runtime inspection, failure vocabulary, and fingerprints while exposing only
the generic chat envelope needed by V3.  It performs exactly one
``POST /api/chat`` and never retains thinking text.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..ids import canonical_json_bytes, sha256_hex
from ..models.provider import ProviderCallSpec
from .ollama import (
    OllamaActiveModel,
    OllamaApiClient,
    OllamaProviderError,
    OllamaRuntimeModel,
    inspect_ollama_active_model,
)
from .ollama_gemma4_epistemic import (
    Gemma4EpistemicExecutionError,
    Gemma4EpistemicFailureCode,
    Gemma4EpistemicSettings,
    _inspect_gemma4_runtime,
    _utf8_fingerprint,
)


class Gemma4ChatTransportError(Gemma4EpistemicExecutionError):
    """Generic transport failure with final JSON retained when it exists."""

    def __init__(
        self,
        failure_code: Gemma4EpistemicFailureCode,
        message: str,
        *,
        final_json: str | None = None,
        **metadata: Any,
    ) -> None:
        super().__init__(failure_code, message, **metadata)
        self.final_json = final_json


@dataclass(frozen=True, slots=True)
class Gemma4ChatTransportResult:
    """Validated chat envelope with private thinking reduced to a fingerprint."""

    final_json: str
    request_payload_hash: str
    response_envelope_hash: str
    response_envelope_byte_count: int
    final_response_hash: str
    final_response_byte_count: int
    thinking_sha256: str
    thinking_byte_count: int
    thinking_token_count: int | None
    response_metadata: Mapping[str, Any]
    placement: OllamaActiveModel

    def rejection_metadata(self) -> dict[str, Any]:
        return {
            "rejected_response_sha256": self.response_envelope_hash,
            "rejected_response_byte_count": self.response_envelope_byte_count,
            "rejected_final_response_sha256": self.final_response_hash,
            "rejected_final_response_byte_count": self.final_response_byte_count,
            "thinking_sha256": self.thinking_sha256,
            "thinking_byte_count": self.thinking_byte_count,
        }


def execute_gemma4_chat_once(
    *,
    client: OllamaApiClient,
    runtime: OllamaRuntimeModel,
    settings: Gemma4EpistemicSettings,
    expected_digest: str,
    payload: Mapping[str, Any],
    call: ProviderCallSpec,
    expected_packet_hash: str,
    packet_hash_supplier: Callable[[], str],
) -> Gemma4ChatTransportResult:
    """Execute and close one exact local Gemma chat envelope."""

    payload_hash = sha256_hex(payload)
    try:
        current_runtime = _inspect_gemma4_runtime(
            client,
            expected_digest=expected_digest,
        )
    except OllamaProviderError:
        raise Gemma4ChatTransportError(
            "runtime_identity_mismatch",
            "Gemma 4 runtime could not be revalidated before generation",
        ) from None
    if current_runtime != runtime:
        raise Gemma4ChatTransportError(
            "runtime_identity_mismatch",
            "Gemma 4 runtime changed after call approval",
        )

    try:
        raw_response = client.post(
            "/api/chat",
            payload,
            timeout_seconds=call.timeout_seconds,
        )
    except OllamaProviderError:
        raise Gemma4ChatTransportError(
            "generation_contract_failure",
            "Gemma 4 chat transport failed",
        ) from None

    try:
        response_bytes = canonical_json_bytes(raw_response)
    except (TypeError, ValueError):
        raise Gemma4ChatTransportError(
            "generation_contract_failure",
            "Gemma 4 returned a non-canonical response envelope",
        ) from None
    response_envelope_hash = hashlib.sha256(response_bytes).hexdigest()
    response_envelope_byte_count = len(response_bytes)
    del response_bytes

    message_value = raw_response.get("message")
    thinking_value = (
        message_value.get("thinking")
        if isinstance(message_value, Mapping)
        else None
    )
    thinking_sha256: str | None = None
    thinking_byte_count: int | None = None
    final_json: str | None = None
    final_response_hash: str | None = None
    final_response_byte_count: int | None = None
    if isinstance(thinking_value, str) and thinking_value.strip():
        thinking_sha256, thinking_byte_count = _utf8_fingerprint(thinking_value)

    def reject_response(
        code: Gemma4EpistemicFailureCode,
        message: str,
    ) -> Gemma4ChatTransportError:
        return Gemma4ChatTransportError(
            code,
            message,
            final_json=final_json,
            rejected_response_sha256=response_envelope_hash,
            rejected_response_byte_count=response_envelope_byte_count,
            rejected_final_response_sha256=final_response_hash,
            rejected_final_response_byte_count=final_response_byte_count,
            thinking_sha256=thinking_sha256,
            thinking_byte_count=thinking_byte_count,
        )

    if (
        sha256_hex(payload) != payload_hash
        or packet_hash_supplier() != expected_packet_hash
    ):
        raise reject_response(
            "request_contract_failure",
            "Gemma 4 request or packet mutated during transport",
        )
    if raw_response.get("done") is not True:
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat did not finish",
        )
    if raw_response.get("done_reason") != "stop":
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat did not stop cleanly",
        )
    if raw_response.get("model") != settings.model:
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat used an unexpected model",
        )
    if raw_response.get("remote_model") or raw_response.get("remote_host"):
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat used a remote model",
        )
    if not isinstance(message_value, Mapping):
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat is missing its assistant message",
        )
    if message_value.get("role") != "assistant":
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat returned a non-assistant message",
        )
    if "response" in raw_response or "thinking" in raw_response:
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat mixed completion and chat response fields",
        )
    if message_value.get("tool_calls") or message_value.get("images"):
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat returned unexpected non-text content",
        )
    if thinking_sha256 is None or thinking_byte_count is None:
        raise reject_response(
            "thinking_separation_failure",
            "Gemma 4 did not return a separate non-empty thinking field",
        )
    content_value = message_value.get("content")
    if not isinstance(content_value, str) or not content_value.strip():
        raise reject_response(
            "generation_contract_failure",
            "Gemma 4 chat is missing final response text",
        )
    final_response_hash, final_response_byte_count = _utf8_fingerprint(
        content_value
    )
    if "<think" in content_value.casefold() or "</think>" in (
        content_value.casefold()
    ):
        raise reject_response(
            "thinking_separation_failure",
            "Gemma 4 final response contains inline thinking",
        )
    final_json = content_value

    def optional_count(name: str) -> int | None:
        value = raw_response.get(name)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise reject_response(
                "generation_contract_failure",
                f"Gemma 4 {name} metadata is invalid",
            )
        return value

    response_metadata = MappingProxyType(
        {
            "done_reason": raw_response.get("done_reason"),
            "total_duration": optional_count("total_duration"),
            "load_duration": optional_count("load_duration"),
            "prompt_eval_count": optional_count("prompt_eval_count"),
            "prompt_eval_duration": optional_count("prompt_eval_duration"),
            "eval_count": optional_count("eval_count"),
            "eval_duration": optional_count("eval_duration"),
        }
    )
    thinking_token_count = optional_count("thinking_count")
    del thinking_value
    del message_value
    del raw_response

    try:
        post_runtime = _inspect_gemma4_runtime(
            client,
            expected_digest=expected_digest,
        )
    except OllamaProviderError:
        raise reject_response(
            "runtime_identity_mismatch",
            "Gemma 4 runtime could not be revalidated after generation",
        ) from None
    if post_runtime != runtime:
        raise reject_response(
            "runtime_identity_mismatch",
            "Gemma 4 runtime changed during generation",
        )
    try:
        placement = inspect_ollama_active_model(client, settings.model)
    except OllamaProviderError:
        raise reject_response(
            "gpu_placement_failure",
            "Gemma 4 placement metadata failed validation",
        ) from None
    if (
        placement.model != runtime.model
        or placement.digest != runtime.digest
        or placement.context_length != settings.num_ctx
        or not placement.full_gpu
        or placement.gpu_percent_rounded != 100
    ):
        raise reject_response(
            "gpu_placement_failure",
            "Gemma 4 is not on the approved digest, context, and full GPU",
        )

    assert final_json is not None
    assert final_response_hash is not None
    assert final_response_byte_count is not None
    assert thinking_sha256 is not None
    assert thinking_byte_count is not None
    return Gemma4ChatTransportResult(
        final_json=final_json,
        request_payload_hash=payload_hash,
        response_envelope_hash=response_envelope_hash,
        response_envelope_byte_count=response_envelope_byte_count,
        final_response_hash=final_response_hash,
        final_response_byte_count=final_response_byte_count,
        thinking_sha256=thinking_sha256,
        thinking_byte_count=thinking_byte_count,
        thinking_token_count=thinking_token_count,
        response_metadata=response_metadata,
        placement=placement,
    )


__all__ = [
    "Gemma4ChatTransportError",
    "Gemma4ChatTransportResult",
    "execute_gemma4_chat_once",
]
