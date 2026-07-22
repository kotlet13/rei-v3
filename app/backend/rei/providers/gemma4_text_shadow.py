"""Explicit opt-in adapter for the English Gemma 4 epistemic V3 provider.

Importing the default REI engine never imports this module.  The adapter keeps
the provider's exact identity, revision, call specification and one-shot
transport while normalizing known failures into a provider-neutral shadow
attempt with no rejected content or private thinking text.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Literal, Mapping, Self

from pydantic import Field, model_validator

from ..communication.text_shadow import (
    ShadowFailureCode,
    ShadowProviderAttempt,
    ShadowProviderPreflightError,
)
from ..communication.epistemic_interpreter_en import RacioEpistemicPacketEnV3
from ..ids import content_id, sha256_hex
from ..models.common import FrozenArtifactModel, HashDigest, NonEmptyId, NonEmptyText
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ensure_call_record_contract,
)
from .native import ExecutionClock
from .ollama import (
    OllamaApiClient,
    OllamaResponseError,
    OllamaTransportError,
)
from .ollama_gemma4_epistemic import GEMMA4_EPISTEMIC_TIMEOUT_SECONDS
from .ollama_gemma4_epistemic_en_explained import (
    OllamaGemma4EpistemicExplainedEnProvider,
)
from .ollama_gemma4_epistemic_v3 import (
    Gemma4EpistemicV3ExecutionError,
)


_FAILURE_SUMMARIES: Mapping[ShadowFailureCode, str] = {
    "request_contract_failure": "The frozen text-shadow request contract failed.",
    "runtime_identity_mismatch": "The frozen text-shadow runtime identity changed.",
    "gpu_placement_failure": "The frozen digest, context, or GPU placement check failed.",
    "generation_contract_failure": "The one-shot text-shadow generation contract failed.",
    "thinking_separation_failure": "The text-shadow thinking/final separation failed.",
    "structured_output_invalid": "The text-shadow final content failed structured validation.",
    "conscious_access_rejected": "The explained draft failed frozen packet-scope validation.",
    "ollama_unavailable": "The local Ollama runtime was unavailable to text shadow.",
    "wrong_model_digest": "The text-shadow model identity did not match the frozen digest.",
    "timeout": "The text-shadow provider attempt timed out.",
    "wrong_context": "The active text-shadow context differed from the frozen profile.",
    "partial_gpu_placement": "The text-shadow model was not fully placed on the GPU.",
    "invalid_json": "The text-shadow final content was not valid explained-draft JSON.",
    "duplicate_json_key": "The text-shadow final JSON contained a duplicate key.",
    "draft_v3_validation": "The text-shadow final JSON failed explained-draft validation.",
    "canonicalizer_failure": "The explained draft failed the non-semantic V3 canonicalizer.",
    "citation_scope_violation": "The explained draft cited outside the visible observation scope.",
    "option_scope_violation": "The explained draft selected outside the public option scope.",
    "unsupported_language": "The request is outside English-only shadow scope.",
    "packet_construction_failure": "The trusted request could not form a V3 packet.",
    "provider_failure": "The one-shot text-shadow provider contract failed.",
}


_WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])"
)
_MAX_REJECTED_FINAL_BYTES = 1024 * 1024


class Gemma4TextShadowFailureEvidence(FrozenArtifactModel):
    """Exact rejected final content with private thinking excluded.

    This artifact is diagnostic evidence only.  It is never an accepted
    interpretation and a failed ProviderCallRecord still publishes no final
    output artifacts.
    """

    schema_version: Literal[
        "rei-gemma4-text-shadow-failure-evidence-v1"
    ] = "rei-gemma4-text-shadow-failure-evidence-v1"
    result_id: NonEmptyId
    packet_id: NonEmptyId
    packet_hash: HashDigest
    call_id: NonEmptyId
    call_spec_hash: HashDigest
    provider_id: NonEmptyId
    provider_revision: Literal[
        "rei-racio-gemma4-epistemic-v3-en-explained-chat-v1"
    ]
    provider_implementation_revision: NonEmptyText
    model: Literal["gemma4:31b"]
    model_revision: HashDigest
    exact_model_request: dict[str, Any]
    exact_model_request_hash: HashDigest
    failure_stage: Literal[
        "draft_v3_validation",
        "canonicalizer_v3_validation",
    ]
    provider_failure_code: NonEmptyText
    shadow_failure_code: ShadowFailureCode
    validation_error: NonEmptyText
    final_content: NonEmptyText
    final_content_sha256: HashDigest
    final_content_byte_count: int = Field(gt=0, le=_MAX_REJECTED_FINAL_BYTES)
    response_envelope_sha256: HashDigest
    response_envelope_byte_count: int = Field(gt=0)
    thinking_present: Literal[True] = True
    thinking_sha256: HashDigest
    thinking_byte_count: int = Field(gt=0)
    thinking_content_persisted: Literal[False] = False
    final_content_sanitized: Literal[True] = True
    transport_profile_validated: Literal[True] = True
    model_call_count: Literal[1] = 1
    retry_count: Literal[0] = 0
    fallback_count: Literal[0] = 0
    accepted_interpretation_published: Literal[False] = False
    no_authority: Literal[True] = True

    @model_validator(mode="after")
    def validate_failure_evidence(self) -> Self:
        final_bytes = self.final_content.encode("utf-8")
        if len(final_bytes) != self.final_content_byte_count:
            raise ValueError("Rejected final content byte count differs")
        if hashlib.sha256(final_bytes).hexdigest() != self.final_content_sha256:
            raise ValueError("Rejected final content hash differs")
        if self.exact_model_request_hash != sha256_hex(self.exact_model_request):
            raise ValueError("Rejected request differs from its hash")
        for value in (self.final_content, self.validation_error):
            if _WINDOWS_ABSOLUTE_PATH.search(value.replace("\\\\", "\\")):
                raise ValueError("Failure evidence cannot retain a local absolute path")
            if "Traceback (most recent call last)" in value:
                raise ValueError("Failure evidence cannot retain a raw traceback")
        folded = self.final_content.casefold()
        if "<think" in folded or "</think>" in folded:
            raise ValueError("Failure evidence cannot retain inline thinking")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"result_id"},
        )
        if self.result_id != content_id("gemma_shadow_failure", payload):
            raise ValueError("Failure evidence is not content-addressed")
        return self

    @classmethod
    def create(
        cls,
        *,
        packet: RacioEpistemicPacketEnV3,
        call: ProviderCallSpec,
        provider: OllamaGemma4EpistemicExplainedEnProvider,
        error: Gemma4EpistemicV3ExecutionError,
        shadow_failure_code: ShadowFailureCode,
    ) -> "Gemma4TextShadowFailureEvidence":
        if error.failure_stage not in {
            "draft_v3_validation",
            "canonicalizer_v3_validation",
        }:
            raise ValueError("Failure evidence requires a validation-stage failure")
        if error.final_json is None or error.validation_error is None:
            raise ValueError("Validation failure evidence requires final content and detail")
        response_hash = error.rejected_response_sha256
        response_bytes = error.rejected_response_byte_count
        final_hash = error.rejected_final_response_sha256
        final_bytes = error.rejected_final_response_byte_count
        thinking_hash = error.thinking_sha256
        thinking_bytes = error.thinking_byte_count
        if any(
            value is None
            for value in (
                response_hash,
                response_bytes,
                final_hash,
                final_bytes,
                thinking_hash,
                thinking_bytes,
            )
        ):
            raise ValueError("Validation failure lacks closed transport fingerprints")
        exact_request = dict(provider.request_payload(packet))
        base = {
            "schema_version": "rei-gemma4-text-shadow-failure-evidence-v1",
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "call_id": call.call_id,
            "call_spec_hash": call.content_hash(),
            "provider_id": call.provider.provider_id,
            "provider_revision": (
                "rei-racio-gemma4-epistemic-v3-en-explained-chat-v1"
            ),
            "provider_implementation_revision": (
                call.provider.implementation_revision
            ),
            "model": call.provider.model,
            "model_revision": call.provider.model_revision,
            "exact_model_request": exact_request,
            "exact_model_request_hash": sha256_hex(exact_request),
            "failure_stage": error.failure_stage,
            "provider_failure_code": error.failure_code,
            "shadow_failure_code": shadow_failure_code,
            "validation_error": error.validation_error,
            "final_content": error.final_json,
            "final_content_sha256": final_hash,
            "final_content_byte_count": final_bytes,
            "response_envelope_sha256": response_hash,
            "response_envelope_byte_count": response_bytes,
            "thinking_present": True,
            "thinking_sha256": thinking_hash,
            "thinking_byte_count": thinking_bytes,
            "thinking_content_persisted": False,
            "final_content_sanitized": True,
            "transport_profile_validated": True,
            "model_call_count": 1,
            "retry_count": 0,
            "fallback_count": 0,
            "accepted_interpretation_published": False,
            "no_authority": True,
        }
        return cls(
            result_id=content_id("gemma_shadow_failure", base),
            **base,
        )


def _bounded_failure_code(
    error: Gemma4EpistemicV3ExecutionError,
) -> ShadowFailureCode:
    if error.failure_stage == "draft_v3_validation":
        if error.validation_error == "duplicate_json_key":
            return "duplicate_json_key"
        if error.validation_error is not None and "json_invalid" in (
            error.validation_error
        ):
            return "invalid_json"
        return "draft_v3_validation"
    if error.failure_stage == "canonicalizer_v3_validation":
        detail = error.validation_error or ""
        if "outside visible packet scope" in detail or (
            "cites outside packet scope" in detail
        ):
            return "citation_scope_violation"
        if "outside public option" in detail:
            return "option_scope_violation"
        return "canonicalizer_failure"
    return error.failure_code


def _discovery_failure(
    error: OllamaTransportError | OllamaResponseError,
) -> ShadowProviderPreflightError:
    if isinstance(error, OllamaTransportError):
        return ShadowProviderPreflightError(
            "ollama_unavailable",
            _FAILURE_SUMMARIES["ollama_unavailable"],
        )
    failure_code: ShadowFailureCode = (
        "wrong_model_digest"
        if "digest differs" in str(error).casefold()
        else "runtime_identity_mismatch"
    )
    return ShadowProviderPreflightError(
        failure_code,
        _FAILURE_SUMMARIES[failure_code],
    )


@dataclass(frozen=True, slots=True)
class Gemma4TextShadowInterpreter:
    """One-shot shadow adapter over the English-primary V3 provider."""

    provider: OllamaGemma4EpistemicExplainedEnProvider | None
    preflight_failure: ShadowProviderPreflightError | None = None

    def __post_init__(self) -> None:
        if self.provider is not None and not isinstance(
            self.provider,
            OllamaGemma4EpistemicExplainedEnProvider,
        ):
            raise TypeError(
                "Gemma text shadow requires the active English provider wrapper"
            )
        if (self.provider is None) == (self.preflight_failure is None):
            raise ValueError(
                "Gemma text shadow requires one provider or one preflight failure"
            )

    @classmethod
    def discover(
        cls,
        *,
        client: OllamaApiClient,
        environ: Mapping[str, str] | None = None,
        timeout_seconds: float = GEMMA4_EPISTEMIC_TIMEOUT_SECONDS,
    ) -> "Gemma4TextShadowInterpreter":
        try:
            provider = OllamaGemma4EpistemicExplainedEnProvider.discover(
                client=client,
                environ=environ,
                timeout_seconds=timeout_seconds,
            )
        except (OllamaTransportError, OllamaResponseError) as error:
            return cls(provider=None, preflight_failure=_discovery_failure(error))
        return cls(provider=provider)

    def interpret_shadow(
        self,
        packet: RacioEpistemicPacketEnV3,
        *,
        clock: ExecutionClock,
    ) -> ShadowProviderAttempt:
        if self.preflight_failure is not None:
            raise self.preflight_failure
        assert self.provider is not None
        call = self.provider.build_call_spec(packet)
        failure_started_at = clock.timestamp("racio_call_started")
        try:
            execution = self.provider.execute(
                packet,
                call=call,
                clock=clock,
            )
        except Gemma4EpistemicV3ExecutionError as error:
            failure_finished_at = clock.timestamp("racio_call_finished")
            failure_code = _bounded_failure_code(error)
            failure_evidence = None
            failure_evidence_warning: tuple[str, ...] = ()
            if (
                error.failure_stage
                in {"draft_v3_validation", "canonicalizer_v3_validation"}
                and error.final_json is not None
                and error.validation_error is not None
            ):
                try:
                    failure_evidence = Gemma4TextShadowFailureEvidence.create(
                        packet=packet,
                        call=call,
                        provider=self.provider,
                        error=error,
                        shadow_failure_code=failure_code,
                    )
                except (TypeError, ValueError):
                    failure_evidence_warning = (
                        "sanitized_failure_evidence_status:not_persisted",
                    )
            record = ProviderCallRecord(
                call_id=call.call_id,
                spec_hash=call.content_hash(),
                request_id=call.request_id,
                input_artifact_ids=call.input_artifact_ids,
                provider=call.provider,
                seed=call.seed,
                parameters=call.parameters,
                timeout_seconds=call.timeout_seconds,
                started_at=failure_started_at,
                primary_finished_at=failure_finished_at,
                finished_at=failure_finished_at,
                status="failed",
                primary_status="failed",
                output_artifact_ids=(),
                warnings=(
                    f"sanitized_provider_failure_code:{error.failure_code}",
                    f"sanitized_shadow_failure_code:{failure_code}",
                    *failure_evidence_warning,
                ),
                safety_notice=call.safety_notice,
            )
            ensure_call_record_contract(call, record)
            return ShadowProviderAttempt(
                status="failed",
                call_spec=call,
                call_record=record,
                failure_stage=error.failure_stage,
                failure_code=failure_code,
                failure_summary=_FAILURE_SUMMARIES[failure_code],
                failure_evidence=failure_evidence,
                failure_evidence_id=(
                    None if failure_evidence is None else failure_evidence.result_id
                ),
                failure_evidence_sha256=(
                    None
                    if failure_evidence is None
                    else failure_evidence.content_hash()
                ),
            )

        evidence = execution.response_evidence
        return ShadowProviderAttempt(
            status="succeeded",
            call_spec=execution.call_spec,
            call_record=execution.call_record,
            output=execution.output,
            response_evidence=evidence,
            response_evidence_id=evidence.result_id,
            response_evidence_sha256=evidence.content_hash(),
        )


__all__ = [
    "Gemma4TextShadowFailureEvidence",
    "Gemma4TextShadowInterpreter",
]
