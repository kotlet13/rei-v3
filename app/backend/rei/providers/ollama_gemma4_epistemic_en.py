"""English-only Gemma 4 bridge over the frozen V3 transport and draft schema.

The historical V3 provider remains unchanged.  This bridge reuses its exact
model profile, English instruction, DraftV3 schema, one-attempt chat transport,
and structural sidecar while binding a new provider revision to the
English-primary runtime packet and canonical interpretation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Self

from pydantic import Field, ValidationError, model_validator

from ..communication.epistemic_interpreter_en import (
    RacioEpistemicInterpretationEnV3,
    RacioEpistemicPacketEnV3,
    canonicalize_racio_epistemic_draft_en_v3,
)
from ..communication.epistemic_interpreter_v3 import (
    RacioEpistemicDraftV3,
    RacioEpistemicStructuralSidecarV3,
)
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
    ProviderIdentity,
    ProviderParameter,
    ensure_call_contract,
    ensure_call_record_contract,
)
from .language_policy import (
    LOCAL_MODEL_LANGUAGE_POLICY_ID,
    require_english_local_model_payload,
)
from .native import ExecutionClock
from .ollama import OllamaActiveModel, OllamaRuntimeModel
from .ollama_gemma4_chat_transport import (
    Gemma4ChatTransportError,
    execute_gemma4_chat_once,
)
from .ollama_gemma4_epistemic import (
    Gemma4EpistemicFailureCode,
    Gemma4EpistemicSettings,
    _contains_duplicate_json_key,
    _duplicate_key_validation_diagnostics,
    _parameter,
    _validate_sanitized_packet,
)
from .ollama_gemma4_epistemic_v3 import (
    GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION,
    Gemma4EpistemicV3ExecutionError,
    OllamaGemma4EpistemicV3Provider,
    V3FailureStage,
)


GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION = (
    "rei-racio-gemma4-epistemic-v3-en-chat-v1"
)


class Gemma4EpistemicEnResponseEvidence(FrozenArtifactModel):
    """English packet, validated DraftV3, output, and private-trace fingerprint."""

    schema_version: Literal[
        "rei-racio-gemma4-epistemic-v3-en-response-v1"
    ] = "rei-racio-gemma4-epistemic-v3-en-response-v1"
    result_id: NonEmptyId
    packet_id: NonEmptyId
    packet_hash: HashDigest
    language: Literal["en"] = "en"
    language_policy_id: Literal["rei-local-model-english-only-v1"] = (
        "rei-local-model-english-only-v1"
    )
    call_id: NonEmptyId
    call_spec_hash: HashDigest
    provider_id: NonEmptyId
    provider_revision: Literal[
        "rei-racio-gemma4-epistemic-v3-en-chat-v1"
    ]
    model: Literal["gemma4:31b"]
    model_revision: HashDigest
    ollama_server_version: NonEmptyText
    request_payload_hash: HashDigest
    response_envelope_hash: HashDigest
    response_envelope_byte_count: int = Field(gt=0)
    final_response_hash: HashDigest
    final_response_byte_count: int = Field(gt=0)
    model_draft: RacioEpistemicDraftV3
    model_draft_hash: HashDigest
    structured_output: RacioEpistemicInterpretationEnV3
    structured_output_hash: HashDigest
    structural_sidecar: RacioEpistemicStructuralSidecarV3
    structural_sidecar_semantic_evidence: Literal[False] = False
    structural_sidecar_governance_effect: Literal[False] = False
    thinking_present: Literal[True] = True
    thinking_sha256: HashDigest
    thinking_byte_count: int = Field(gt=0)
    thinking_token_count: int | None = Field(default=None, ge=0)
    done_reason: Literal["stop"]
    total_duration_ns: int | None = Field(default=None, ge=0)
    load_duration_ns: int | None = Field(default=None, ge=0)
    prompt_eval_count: int | None = Field(default=None, ge=0)
    prompt_eval_duration_ns: int | None = Field(default=None, ge=0)
    eval_count: int | None = Field(default=None, ge=0)
    eval_duration_ns: int | None = Field(default=None, ge=0)
    cited_observation_ids: tuple[NonEmptyId, ...]
    requested_num_ctx: Literal[65536]
    requested_num_gpu: Literal[999]
    active_context_length: int = Field(gt=0)
    active_size_bytes: int = Field(gt=0)
    active_size_vram_bytes: int = Field(gt=0)
    active_gpu_percent_rounded: int = Field(ge=0, le=100)
    model_call_count: Literal[1] = 1
    retry_count: Literal[0] = 0
    fallback_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("English V3 evidence citations must be canonical")
        if self.active_context_length != self.requested_num_ctx:
            raise ValueError("Active context differs from the pinned request")
        if self.active_size_vram_bytes != self.active_size_bytes:
            raise ValueError("English V3 evidence requires full GPU placement")
        if self.active_gpu_percent_rounded != 100:
            raise ValueError("English V3 evidence requires 100 percent GPU placement")
        if self.model_draft_hash != sha256_hex(self.model_draft):
            raise ValueError("DraftV3 differs from its English evidence hash")
        if self.structured_output_hash != sha256_hex(self.structured_output):
            raise ValueError("English V3 output differs from its evidence hash")
        if self.structural_sidecar != RacioEpistemicStructuralSidecarV3.from_output(
            self.structured_output
        ):
            raise ValueError("English V3 sidecar differs from validated output")
        if self.cited_observation_ids != self.structured_output.cited_observation_ids:
            raise ValueError("English evidence citations differ from validated output")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"result_id"},
        )
        if self.result_id != content_id(
            "gemma4_epistemic_v3_en_response",
            payload,
        ):
            raise ValueError("English Gemma response evidence is not content-addressed")
        return self

    @classmethod
    def create(
        cls,
        *,
        packet: RacioEpistemicPacketEnV3,
        call: ProviderCallSpec,
        runtime: OllamaRuntimeModel,
        settings: Gemma4EpistemicSettings,
        request_payload_hash: str,
        response_envelope_hash: str,
        response_envelope_byte_count: int,
        final_response_hash: str,
        final_response_byte_count: int,
        draft: RacioEpistemicDraftV3,
        output: RacioEpistemicInterpretationEnV3,
        thinking_sha256: str,
        thinking_byte_count: int,
        thinking_token_count: int | None,
        response_metadata: Mapping[str, Any],
        placement: OllamaActiveModel,
    ) -> "Gemma4EpistemicEnResponseEvidence":
        base = {
            "schema_version": "rei-racio-gemma4-epistemic-v3-en-response-v1",
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "language": packet.language,
            "language_policy_id": LOCAL_MODEL_LANGUAGE_POLICY_ID,
            "call_id": call.call_id,
            "call_spec_hash": call.content_hash(),
            "provider_id": call.provider.provider_id,
            "provider_revision": GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION,
            "model": runtime.model,
            "model_revision": runtime.digest,
            "ollama_server_version": runtime.server_version,
            "request_payload_hash": request_payload_hash,
            "response_envelope_hash": response_envelope_hash,
            "response_envelope_byte_count": response_envelope_byte_count,
            "final_response_hash": final_response_hash,
            "final_response_byte_count": final_response_byte_count,
            "model_draft": draft,
            "model_draft_hash": sha256_hex(draft),
            "structured_output": output,
            "structured_output_hash": sha256_hex(output),
            "structural_sidecar": (
                RacioEpistemicStructuralSidecarV3.from_output(output)
            ),
            "structural_sidecar_semantic_evidence": False,
            "structural_sidecar_governance_effect": False,
            "thinking_present": True,
            "thinking_sha256": thinking_sha256,
            "thinking_byte_count": thinking_byte_count,
            "thinking_token_count": thinking_token_count,
            "done_reason": response_metadata.get("done_reason"),
            "total_duration_ns": response_metadata.get("total_duration"),
            "load_duration_ns": response_metadata.get("load_duration"),
            "prompt_eval_count": response_metadata.get("prompt_eval_count"),
            "prompt_eval_duration_ns": response_metadata.get(
                "prompt_eval_duration"
            ),
            "eval_count": response_metadata.get("eval_count"),
            "eval_duration_ns": response_metadata.get("eval_duration"),
            "cited_observation_ids": output.cited_observation_ids,
            "requested_num_ctx": settings.num_ctx,
            "requested_num_gpu": settings.num_gpu,
            "active_context_length": placement.context_length,
            "active_size_bytes": placement.size_bytes,
            "active_size_vram_bytes": placement.size_vram_bytes,
            "active_gpu_percent_rounded": placement.gpu_percent_rounded,
            "model_call_count": 1,
            "retry_count": 0,
            "fallback_count": 0,
        }
        return cls(
            result_id=content_id("gemma4_epistemic_v3_en_response", base),
            **base,
        )


@dataclass(frozen=True, slots=True)
class Gemma4EpistemicEnExecution:
    draft: RacioEpistemicDraftV3
    output: RacioEpistemicInterpretationEnV3
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord
    response_evidence: Gemma4EpistemicEnResponseEvidence

    def __post_init__(self) -> None:
        ensure_call_record_contract(self.call_spec, self.call_record)
        if (
            self.call_record.status != "succeeded"
            or self.call_record.primary_status != "succeeded"
            or self.call_record.fallback is not None
        ):
            raise ValueError("English Gemma execution must succeed without fallback")
        if self.call_record.output_artifact_ids != (
            self.response_evidence.result_id,
        ):
            raise ValueError("English Gemma call publishes only response evidence")
        if (
            self.response_evidence.packet_id != self.call_spec.request_id
            or self.call_spec.input_artifact_ids
            != (self.response_evidence.packet_id,)
            or _parameter(
                "packet_hash",
                self.response_evidence.packet_hash,
            )
            not in self.call_spec.parameters
            or _parameter(
                "request_payload_sha256",
                self.response_evidence.request_payload_hash,
            )
            not in self.call_spec.parameters
            or self.response_evidence.call_id != self.call_spec.call_id
            or self.response_evidence.call_spec_hash
            != self.call_spec.content_hash()
            or self.response_evidence.provider_id
            != self.call_spec.provider.provider_id
            or self.response_evidence.provider_revision
            != GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION
            or self.response_evidence.model != self.call_spec.provider.model
            or self.response_evidence.model_revision
            != self.call_spec.provider.model_revision
            or self.response_evidence.model_draft != self.draft
            or self.response_evidence.model_draft_hash != sha256_hex(self.draft)
            or self.response_evidence.structured_output != self.output
            or self.response_evidence.structured_output_hash
            != sha256_hex(self.output)
            or self.response_evidence.structural_sidecar
            != RacioEpistemicStructuralSidecarV3.from_output(self.output)
        ):
            raise ValueError("English Gemma execution lineage is inconsistent")


class OllamaGemma4EpistemicEnProvider(OllamaGemma4EpistemicV3Provider):
    """One-attempt English runtime bridge over the frozen Gemma V3 provider."""

    @property
    def identity(self) -> ProviderIdentity:
        payload = {
            "kind": "text_reasoner",
            "implementation": (
                "rei.providers.ollama_gemma4_epistemic_en."
                "OllamaGemma4EpistemicEnProvider"
            ),
            "implementation_revision": (
                f"{GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION};"
                f"ollama={self.runtime.server_version}"
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
        values = {item.name: item for item in super().parameters}
        additions = {
            "english_interpretation_schema_sha256": sha256_hex(
                RacioEpistemicInterpretationEnV3.model_json_schema()
            ),
            "english_packet_schema_sha256": sha256_hex(
                RacioEpistemicPacketEnV3.model_json_schema()
            ),
            "local_model_language_policy_id": LOCAL_MODEL_LANGUAGE_POLICY_ID,
            "source_provider_revision": GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION,
        }
        values.update(
            {name: _parameter(name, value) for name, value in additions.items()}
        )
        return tuple(values[name] for name in sorted(values))

    def request_payload(
        self,
        packet: RacioEpistemicPacketEnV3,
    ) -> Mapping[str, Any]:
        provider_view = packet.provider_payload()
        require_english_local_model_payload(
            declared_language=packet.language,
            provider_payload=provider_view,
        )
        payload = dict(super().request_payload(packet))  # type: ignore[arg-type]
        require_english_local_model_payload(
            declared_language=packet.language,
            provider_payload=payload,
        )
        return payload

    def execute(
        self,
        packet: RacioEpistemicPacketEnV3,
        *,
        call: ProviderCallSpec,
        clock: ExecutionClock,
    ) -> Gemma4EpistemicEnExecution:
        _validate_sanitized_packet(packet)  # type: ignore[arg-type]
        payload = self.request_payload(packet)
        started_at = clock.timestamp("racio_call_started")
        try:
            ensure_call_contract(
                self.identity,
                call,
                request_id=packet.packet_id,
                seed=self.settings.seed,
                expected_kind="text_reasoner",
                required_input_artifact_ids=self.required_input_artifact_ids(packet),
            )
        except ValueError as error:
            raise Gemma4EpistemicV3ExecutionError(
                "request_contract_failure",
                "transport",
                str(error),
            ) from None
        if call != self.build_call_spec(packet):  # type: ignore[arg-type]
            raise Gemma4EpistemicV3ExecutionError(
                "request_contract_failure",
                "transport",
                "English Gemma V3 call differs from its canonical contract",
            )

        try:
            transport = execute_gemma4_chat_once(
                client=self.client,
                runtime=self.runtime,
                settings=self.settings,
                expected_digest=self.expected_digest,
                payload=payload,
                call=call,
                expected_packet_hash=packet.packet_hash,
                packet_hash_supplier=lambda: packet.packet_hash,
            )
        except Gemma4ChatTransportError as error:
            diagnostics = dict(error.sanitized_diagnostics())
            diagnostics.pop("failure_code")
            raise Gemma4EpistemicV3ExecutionError(
                error.failure_code,
                "transport",
                str(error),
                final_json=error.final_json,
                **diagnostics,
            ) from None

        def reject_validation(
            failure_code: Gemma4EpistemicFailureCode,
            failure_stage: V3FailureStage,
            message: str,
            *,
            validation_error: str | None = None,
            validation_diagnostics: (
                tuple[int, str, str, str | None, str] | None
            ) = None,
        ) -> Gemma4EpistemicV3ExecutionError:
            diagnostics: dict[str, Any] = {}
            if validation_diagnostics is not None:
                (
                    diagnostics["validation_issue_count"],
                    diagnostics["validation_error_type"],
                    diagnostics["validation_field_path"],
                    diagnostics["validation_invariant_code"],
                    diagnostics["validation_diagnostic_sha256"],
                ) = validation_diagnostics
            return Gemma4EpistemicV3ExecutionError(
                failure_code,
                failure_stage,
                message,
                final_json=transport.final_json,
                validation_error=validation_error,
                **transport.rejection_metadata(),
                **diagnostics,
            )

        final_response = transport.final_json
        if _contains_duplicate_json_key(final_response):
            raise reject_validation(
                "structured_output_invalid",
                "draft_v3_validation",
                "Gemma 4 returned duplicate DraftV3 JSON keys",
                validation_error="duplicate_json_key",
                validation_diagnostics=_duplicate_key_validation_diagnostics(),
            )
        try:
            draft = RacioEpistemicDraftV3.model_validate_json(final_response)
        except ValidationError as error:
            validation_error = canonical_json_bytes(
                error.errors(
                    include_url=False,
                    include_context=False,
                    include_input=False,
                )
            ).decode("utf-8")
            raise reject_validation(
                "structured_output_invalid",
                "draft_v3_validation",
                "Gemma 4 returned invalid DraftV3 structured output",
                validation_error=validation_error,
            ) from None

        try:
            output = canonicalize_racio_epistemic_draft_en_v3(packet, draft)
        except (ValidationError, ValueError) as error:
            raise reject_validation(
                "conscious_access_rejected",
                "canonicalizer_v3_validation",
                "DraftV3 failed English deterministic canonicalizer validation",
                validation_error=f"{type(error).__name__}: {error}",
            ) from None
        del final_response

        evidence = Gemma4EpistemicEnResponseEvidence.create(
            packet=packet,
            call=call,
            runtime=self.runtime,
            settings=self.settings,
            request_payload_hash=transport.request_payload_hash,
            response_envelope_hash=transport.response_envelope_hash,
            response_envelope_byte_count=transport.response_envelope_byte_count,
            final_response_hash=transport.final_response_hash,
            final_response_byte_count=transport.final_response_byte_count,
            draft=draft,
            output=output,
            thinking_sha256=transport.thinking_sha256,
            thinking_byte_count=transport.thinking_byte_count,
            thinking_token_count=transport.thinking_token_count,
            response_metadata=transport.response_metadata,
            placement=transport.placement,
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
            output_artifact_ids=(evidence.result_id,),
            safety_notice=call.safety_notice,
        )
        return Gemma4EpistemicEnExecution(
            draft=draft,
            output=output,
            call_spec=call,
            call_record=record,
            response_evidence=evidence,
        )


__all__ = [
    "GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION",
    "Gemma4EpistemicEnExecution",
    "Gemma4EpistemicEnResponseEvidence",
    "OllamaGemma4EpistemicEnProvider",
]
