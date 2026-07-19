"""Explicit opt-in adapter for the frozen Gemma 4 epistemic V3 provider.

Importing the default REI engine never imports this module.  The adapter keeps
the provider's exact identity, revision, call specification and one-shot
transport while normalizing known failures into a provider-neutral shadow
attempt with no rejected content or private thinking text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..communication.text_shadow import (
    ShadowFailureCode,
    ShadowProviderAttempt,
)
from ..communication.epistemic_interpreter_v3 import RacioEpistemicPacketV3
from ..models.provider import ProviderCallRecord, ensure_call_record_contract
from .native import ExecutionClock
from .ollama import OllamaApiClient
from .ollama_gemma4_epistemic import GEMMA4_EPISTEMIC_TIMEOUT_SECONDS
from .ollama_gemma4_epistemic_v3 import (
    Gemma4EpistemicV3ExecutionError,
    OllamaGemma4EpistemicV3Provider,
)


_FAILURE_SUMMARIES: Mapping[ShadowFailureCode, str] = {
    "request_contract_failure": "The frozen text-shadow request contract failed.",
    "runtime_identity_mismatch": "The frozen text-shadow runtime identity changed.",
    "gpu_placement_failure": "The frozen digest, context, or GPU placement check failed.",
    "generation_contract_failure": "The one-shot text-shadow generation contract failed.",
    "thinking_separation_failure": "The text-shadow thinking/final separation failed.",
    "structured_output_invalid": "The text-shadow final content failed structured validation.",
    "conscious_access_rejected": "DraftV3 failed frozen packet-scope validation.",
    "ollama_unavailable": "The local Ollama runtime was unavailable to text shadow.",
    "wrong_model_digest": "The text-shadow model identity did not match the frozen digest.",
    "timeout": "The text-shadow provider attempt timed out.",
    "wrong_context": "The active text-shadow context differed from the frozen profile.",
    "partial_gpu_placement": "The text-shadow model was not fully placed on the GPU.",
    "invalid_json": "The text-shadow final content was not valid DraftV3 JSON.",
    "duplicate_json_key": "The text-shadow final JSON contained a duplicate key.",
    "draft_v3_validation": "The text-shadow final JSON failed DraftV3 validation.",
    "canonicalizer_failure": "DraftV3 failed the non-semantic V3 canonicalizer.",
    "citation_scope_violation": "DraftV3 cited outside the visible observation scope.",
    "option_scope_violation": "DraftV3 selected outside the public option scope.",
    "unsupported_language": "The request is outside canonical Slovene shadow scope.",
    "packet_construction_failure": "The trusted request could not form a V3 packet.",
    "provider_failure": "The one-shot text-shadow provider contract failed.",
}


def _bounded_failure_code(
    error: Gemma4EpistemicV3ExecutionError,
) -> ShadowFailureCode:
    if error.failure_stage == "draft_v3_validation":
        if error.validation_error == "duplicate_json_key":
            return "duplicate_json_key"
    return error.failure_code


@dataclass(frozen=True, slots=True)
class Gemma4TextShadowInterpreter:
    """One-shot shadow adapter over the frozen V3 provider implementation."""

    provider: OllamaGemma4EpistemicV3Provider

    @classmethod
    def discover(
        cls,
        *,
        client: OllamaApiClient,
        environ: Mapping[str, str] | None = None,
        timeout_seconds: float = GEMMA4_EPISTEMIC_TIMEOUT_SECONDS,
    ) -> "Gemma4TextShadowInterpreter":
        return cls(
            provider=OllamaGemma4EpistemicV3Provider.discover(
                client=client,
                environ=environ,
                timeout_seconds=timeout_seconds,
            )
        )

    def interpret_shadow(
        self,
        packet: RacioEpistemicPacketV3,
        *,
        clock: ExecutionClock,
    ) -> ShadowProviderAttempt:
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


__all__ = ["Gemma4TextShadowInterpreter"]
