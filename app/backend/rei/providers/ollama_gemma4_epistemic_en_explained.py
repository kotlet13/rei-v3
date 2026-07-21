"""Gemma 4 English bridge with cited explanations for absent Racio claims.

This provider is additive.  It leaves the historical V3 and EN1 provider
revisions untouched, reuses their one-attempt transport and exact model
profile, and projects semantic claims through the frozen English V3
canonicalizer.  Model-authored abstention explanations remain diagnostic-only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Self

from pydantic import Field, ValidationError, model_validator

from ..communication.epistemic_interpreter_en import (
    RacioEpistemicInterpretationEnV3,
    RacioEpistemicPacketEnV3,
)
from ..communication.epistemic_interpreter_en_explained import (
    RacioEpistemicExplainedDraftEnV1,
    canonicalize_racio_epistemic_explained_draft_en_v1,
)
from ..communication.epistemic_interpreter_v3 import (
    RacioEpistemicStructuralSidecarV3,
)
from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import FrozenArtifactModel, HashDigest, NonEmptyId, NonEmptyText
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
from .ollama_gemma4_epistemic_en import OllamaGemma4EpistemicEnProvider
from .ollama_gemma4_epistemic_v3 import (
    GEMMA4_EPISTEMIC_V3_INSTRUCTION,
    GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION,
    Gemma4EpistemicV3ExecutionError,
    V3FailureStage,
)


GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION = (
    "rei-racio-gemma4-epistemic-v3-en-explained-chat-v1"
)

_EXPLANATION_RULES = """
Use the names Emocio, Instinkt, and Racio exactly. Never translate or
substitute these names.

For every absent claim kind, return its matching abstention explanation:
- action_abstention_explanation when action_hypotheses is empty;
- option_abstention_explanation when option_inference is null;
- motive_abstention_explanation when motive_hypotheses is empty.
Each explanation must state in one plain English sentence which concrete
visible evidence is missing, degraded, ambiguous, zero-valued, unspecified, or
otherwise insufficient, and why that blocks the claim. Do not merely restate
that no claim was derived. Cite the relevant visible observation IDs. When the
packet has visible observations, every abstention explanation needs at least
one relevant citation. When a claim kind is present, its abstention explanation
must be null. Explanations describe Racio's limited visible basis; they are not
native truth, evaluator gold, semantic claim evidence, or authority.
""".strip()

GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION = (
    GEMMA4_EPISTEMIC_V3_INSTRUCTION.replace(
        "Return only semantic claims in RacioEpistemicDraftV3:",
        (
            "Return semantic claims and claim-absence explanations in "
            "RacioEpistemicExplainedDraftEnV1:"
        ),
    )
    .replace(
        "- do not return global citations, unknown-reason text, a sidecar, artifact IDs,\n"
        "  hashes, evaluator data, native truth, profile data, or governance data.",
        "- do not return global claim citations, canonical unknown-reason text, a sidecar,\n"
        "  artifact IDs, hashes, evaluator data, native truth, profile data, or governance data.",
    )
    .replace(
        "\nAction family/subtype combinations are exactly:",
        f"\n\n{_EXPLANATION_RULES}\n\nAction family/subtype combinations are exactly:",
    )
    .replace(
        "matching the supplied DraftV3 schema",
        "matching the supplied explained English draft schema",
    )
)


def gemma4_epistemic_en_explained_output_schema() -> dict[str, Any]:
    """Return the closed model-facing explanation schema."""

    schema = RacioEpistemicExplainedDraftEnV1.model_json_schema()
    schema["properties"]["action_hypotheses"]["maxItems"] = 2
    schema["properties"]["motive_hypotheses"]["maxItems"] = 3
    for definition_name in (
        "ActionHypothesisDraftV3",
        "OptionInferenceDraftV3",
        "MotiveHypothesisDraftV3",
    ):
        definition = schema["$defs"][definition_name]
        definition["properties"]["cited_observation_ids"]["minItems"] = 1
        confidence = definition["properties"]["confidence"]
        confidence.pop("minimum", None)
        confidence["exclusiveMinimum"] = 0.0
    return schema


GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION_SHA256 = sha256_hex(
    GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION
)
GEMMA4_EPISTEMIC_EN_EXPLAINED_SCHEMA_SHA256 = sha256_hex(
    gemma4_epistemic_en_explained_output_schema()
)


class Gemma4EpistemicExplainedEnResponseEvidence(FrozenArtifactModel):
    """Exact request, explained draft, canonical V3 output, and safe metadata."""

    schema_version: Literal[
        "rei-racio-gemma4-epistemic-v3-en-explained-response-v1"
    ] = "rei-racio-gemma4-epistemic-v3-en-explained-response-v1"
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
        "rei-racio-gemma4-epistemic-v3-en-explained-chat-v1"
    ]
    model: Literal["gemma4:31b"]
    model_revision: HashDigest
    ollama_server_version: NonEmptyText
    exact_model_request: dict[str, Any]
    exact_model_request_hash: HashDigest
    request_payload_hash: HashDigest
    response_envelope_hash: HashDigest
    response_envelope_byte_count: int = Field(gt=0)
    final_response_hash: HashDigest
    final_response_byte_count: int = Field(gt=0)
    model_draft: RacioEpistemicExplainedDraftEnV1
    model_draft_hash: HashDigest
    structured_output: RacioEpistemicInterpretationEnV3
    structured_output_hash: HashDigest
    structural_sidecar: RacioEpistemicStructuralSidecarV3
    structural_sidecar_semantic_evidence: Literal[False] = False
    structural_sidecar_governance_effect: Literal[False] = False
    abstention_explanations_semantic_claim_evidence: Literal[False] = False
    abstention_explanations_authority: Literal[False] = False
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
            raise ValueError("Explained English evidence citations must be canonical")
        if self.exact_model_request_hash != sha256_hex(self.exact_model_request):
            raise ValueError("Exact model request differs from its evidence hash")
        if self.exact_model_request_hash != self.request_payload_hash:
            raise ValueError("Persisted exact request differs from dispatched payload")
        if self.active_context_length != self.requested_num_ctx:
            raise ValueError("Active context differs from the pinned request")
        if self.active_size_vram_bytes != self.active_size_bytes:
            raise ValueError("Explained English evidence requires full GPU placement")
        if self.active_gpu_percent_rounded != 100:
            raise ValueError("Explained English evidence requires 100 percent GPU")
        if self.model_draft_hash != sha256_hex(self.model_draft):
            raise ValueError("Explained draft differs from its evidence hash")
        if self.structured_output_hash != sha256_hex(self.structured_output):
            raise ValueError("Canonical output differs from its evidence hash")
        if self.structural_sidecar != RacioEpistemicStructuralSidecarV3.from_output(
            self.structured_output
        ):
            raise ValueError("Structural sidecar differs from canonical output")
        if self.cited_observation_ids != self.structured_output.cited_observation_ids:
            raise ValueError("Evidence claim citations differ from canonical output")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"result_id"}
        )
        if self.result_id != content_id("gemma4_en_explain_response", payload):
            raise ValueError("Explained English response is not content-addressed")
        return self

    @classmethod
    def create(
        cls,
        *,
        packet: RacioEpistemicPacketEnV3,
        call: ProviderCallSpec,
        runtime: OllamaRuntimeModel,
        settings: Gemma4EpistemicSettings,
        exact_model_request: Mapping[str, Any],
        request_payload_hash: str,
        response_envelope_hash: str,
        response_envelope_byte_count: int,
        final_response_hash: str,
        final_response_byte_count: int,
        draft: RacioEpistemicExplainedDraftEnV1,
        output: RacioEpistemicInterpretationEnV3,
        thinking_sha256: str,
        thinking_byte_count: int,
        thinking_token_count: int | None,
        response_metadata: Mapping[str, Any],
        placement: OllamaActiveModel,
    ) -> "Gemma4EpistemicExplainedEnResponseEvidence":
        base = {
            "schema_version": (
                "rei-racio-gemma4-epistemic-v3-en-explained-response-v1"
            ),
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "language": packet.language,
            "language_policy_id": LOCAL_MODEL_LANGUAGE_POLICY_ID,
            "call_id": call.call_id,
            "call_spec_hash": call.content_hash(),
            "provider_id": call.provider.provider_id,
            "provider_revision": GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION,
            "model": runtime.model,
            "model_revision": runtime.digest,
            "ollama_server_version": runtime.server_version,
            "exact_model_request": dict(exact_model_request),
            "exact_model_request_hash": sha256_hex(exact_model_request),
            "request_payload_hash": request_payload_hash,
            "response_envelope_hash": response_envelope_hash,
            "response_envelope_byte_count": response_envelope_byte_count,
            "final_response_hash": final_response_hash,
            "final_response_byte_count": final_response_byte_count,
            "model_draft": draft,
            "model_draft_hash": sha256_hex(draft),
            "structured_output": output,
            "structured_output_hash": sha256_hex(output),
            "structural_sidecar": RacioEpistemicStructuralSidecarV3.from_output(
                output
            ),
            "structural_sidecar_semantic_evidence": False,
            "structural_sidecar_governance_effect": False,
            "abstention_explanations_semantic_claim_evidence": False,
            "abstention_explanations_authority": False,
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
            result_id=content_id("gemma4_en_explain_response", base),
            **base,
        )


@dataclass(frozen=True, slots=True)
class Gemma4EpistemicExplainedEnExecution:
    draft: RacioEpistemicExplainedDraftEnV1
    output: RacioEpistemicInterpretationEnV3
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord
    response_evidence: Gemma4EpistemicExplainedEnResponseEvidence

    def __post_init__(self) -> None:
        ensure_call_record_contract(self.call_spec, self.call_record)
        if (
            self.call_record.status != "succeeded"
            or self.call_record.primary_status != "succeeded"
            or self.call_record.fallback is not None
        ):
            raise ValueError("Explained English execution must succeed without fallback")
        if self.call_record.output_artifact_ids != (
            self.response_evidence.result_id,
        ):
            raise ValueError("Explained call publishes only response evidence")
        if (
            self.response_evidence.packet_id != self.call_spec.request_id
            or self.response_evidence.call_id != self.call_spec.call_id
            or self.response_evidence.provider_revision
            != GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION
            or self.response_evidence.model_draft != self.draft
            or self.response_evidence.structured_output != self.output
        ):
            raise ValueError("Explained English execution lineage is inconsistent")


class OllamaGemma4EpistemicExplainedEnProvider(OllamaGemma4EpistemicEnProvider):
    """One-attempt provider for explained English drafts and frozen semantics."""

    @property
    def identity(self) -> ProviderIdentity:
        payload = {
            "kind": "text_reasoner",
            "implementation": (
                "rei.providers.ollama_gemma4_epistemic_en_explained."
                "OllamaGemma4EpistemicExplainedEnProvider"
            ),
            "implementation_revision": (
                f"{GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION};"
                f"ollama={self.runtime.server_version}"
            ),
            "uses_model": True,
            "model": self.runtime.model,
            "model_revision": self.runtime.digest,
        }
        return ProviderIdentity(provider_id=content_id("provider", payload), **payload)

    @property
    def parameters(self) -> tuple[ProviderParameter, ...]:
        inherited = {
            item.name: item
            for item in super().parameters
            if item.name not in {"draft_schema_sha256", "instruction_sha256"}
        }
        additions = {
            "draft_schema_sha256": (
                GEMMA4_EPISTEMIC_EN_EXPLAINED_SCHEMA_SHA256
            ),
            "instruction_sha256": (
                GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION_SHA256
            ),
            "abstention_explanations_authority": False,
            "abstention_explanations_semantic_claim_evidence": False,
            "source_provider_revision": GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION,
        }
        inherited.update(
            {name: _parameter(name, value) for name, value in additions.items()}
        )
        return tuple(inherited[name] for name in sorted(inherited))

    def request_payload(
        self,
        packet: RacioEpistemicPacketEnV3,
    ) -> Mapping[str, Any]:
        provider_view = packet.provider_payload()
        require_english_local_model_payload(
            declared_language=packet.language,
            provider_payload=provider_view,
        )
        payload = dict(super().request_payload(packet))
        payload["messages"] = [
            {
                "role": "system",
                "content": GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION,
            },
            {
                "role": "user",
                "content": packet.provider_payload_bytes().decode("utf-8"),
            },
        ]
        payload["format"] = gemma4_epistemic_en_explained_output_schema()
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
    ) -> Gemma4EpistemicExplainedEnExecution:
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
                "request_contract_failure", "transport", str(error)
            ) from None
        if call != self.build_call_spec(packet):  # type: ignore[arg-type]
            raise Gemma4EpistemicV3ExecutionError(
                "request_contract_failure",
                "transport",
                "Explained English call differs from its canonical contract",
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
                "Gemma 4 returned duplicate explained-draft JSON keys",
                validation_error="duplicate_json_key",
                validation_diagnostics=_duplicate_key_validation_diagnostics(),
            )
        try:
            draft = RacioEpistemicExplainedDraftEnV1.model_validate_json(
                final_response
            )
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
                "Gemma 4 returned an invalid explained English draft",
                validation_error=validation_error,
            ) from None

        try:
            output = canonicalize_racio_epistemic_explained_draft_en_v1(
                packet, draft
            )
        except (ValidationError, ValueError) as error:
            raise reject_validation(
                "conscious_access_rejected",
                "canonicalizer_v3_validation",
                "Explained draft failed frozen English V3 validation",
                validation_error=f"{type(error).__name__}: {error}",
            ) from None
        del final_response

        evidence = Gemma4EpistemicExplainedEnResponseEvidence.create(
            packet=packet,
            call=call,
            runtime=self.runtime,
            settings=self.settings,
            exact_model_request=payload,
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
        return Gemma4EpistemicExplainedEnExecution(
            draft=draft,
            output=output,
            call_spec=call,
            call_record=record,
            response_evidence=evidence,
        )


__all__ = [
    "GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION",
    "GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION_SHA256",
    "GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION",
    "GEMMA4_EPISTEMIC_EN_EXPLAINED_SCHEMA_SHA256",
    "Gemma4EpistemicExplainedEnExecution",
    "Gemma4EpistemicExplainedEnResponseEvidence",
    "OllamaGemma4EpistemicExplainedEnProvider",
    "gemma4_epistemic_en_explained_output_schema",
]
