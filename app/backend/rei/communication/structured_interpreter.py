"""C3 structured Racio interpreter contract over conscious-access packets only."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from pydantic import model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from ..models.communication import (
    ManifestationObservation,
    RacioInterpretation,
    RacioInterpreterRequest,
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
from ..providers.native import (
    ExecutionClock,
    SystemExecutionClock,
    build_provider_call_spec,
)
from .conscious_access import (
    ConsciousAccessFilter,
    ConsciousAccessPacket,
    ConsciousAccessResult,
    InterpreterAblationMode,
    TrustedVisibleArtifact,
)


DETERMINISTIC_INTERPRETER_POLICY = "c3-deterministic-visible-signal-baseline-v1"
INTERPRETER_NO_FALLBACK_REASON = (
    "C3 interpreter calls fail closed; no hidden provider or deterministic fallback."
)

InterpreterMotiveClass = Literal[
    "attachment",
    "body_alarm",
    "boundary_alarm",
    "broken_scene",
    "motor_pattern",
    "unknown",
]
InterpreterActionTendency = Literal[
    "approach",
    "attack",
    "compete",
    "connect",
    "conserve",
    "freeze",
    "improvise",
    "maintain",
    "perform",
    "protect",
    "seek_attachment",
    "seek_safety",
    "set_boundary",
    "unknown",
    "withdraw",
    "withdraw_contact",
]


class StructuredRacioInterpreterOutput(FrozenModel):
    """Strict alias-only model output; extra fields (including CoT) are forbidden."""

    source_mind: Literal["E", "I"]
    cited_observation_ids: tuple[NonEmptyId, ...]
    inferred_option_id: NonEmptyId | None
    inferred_action_tendency: InterpreterActionTendency | None
    inferred_motive_class: InterpreterMotiveClass | None
    confidence: Score01
    alternative_hypotheses: tuple[NonEmptyText, ...]
    unresolved_ambiguity: NonEmptyText | None

    @model_validator(mode="after")
    def validate_canonical_output(self) -> "StructuredRacioInterpreterOutput":
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("Cited observation aliases must be sorted and unique")
        if len(set(self.alternative_hypotheses)) != len(
            self.alternative_hypotheses
        ):
            raise ValueError("Alternative hypotheses must be unique")
        if self.inferred_option_id is None and self.unresolved_ambiguity is None:
            raise ValueError("Option abstention requires explicit unresolved ambiguity")
        return self

    def validate_against(
        self,
        packet: ConsciousAccessPacket,
    ) -> "StructuredRacioInterpreterOutput":
        if self.source_mind != packet.source_mind:
            raise ValueError("Interpreter output source mind differs from its packet")
        visible_ids = {
            observation.observation_id
            for observation in packet.visible_observations
        }
        if not set(self.cited_observation_ids).issubset(visible_ids):
            raise ValueError("Interpreter output cites an observation outside packet scope")
        if packet.visible_observations and not self.cited_observation_ids:
            raise ValueError("An interpretation must cite a visible observation")
        if not packet.visible_observations:
            if self.cited_observation_ids:
                raise ValueError("An empty packet cannot have observation citations")
            if any(
                value is not None
                for value in (
                    self.inferred_option_id,
                    self.inferred_action_tendency,
                    self.inferred_motive_class,
                )
            ):
                raise ValueError("An empty packet cannot support an inference")
            if self.confidence != 0.0:
                raise ValueError("An empty packet requires zero confidence")
        option_ids = {option.option_id for option in packet.public_option_scope}
        if (
            self.inferred_option_id is not None
            and self.inferred_option_id not in option_ids
        ):
            raise ValueError("Interpreter output selects an option outside packet scope")
        return self


class StructuredRacioInterpreterEvidence(FrozenArtifactModel):
    """Provider-neutral result lineage used by the deterministic baseline."""

    schema_version: Literal["rei-structured-racio-interpreter-evidence-v1"] = (
        "rei-structured-racio-interpreter-evidence-v1"
    )
    result_id: NonEmptyId
    packet_id: NonEmptyId
    packet_hash: HashDigest
    call_id: NonEmptyId
    call_spec_hash: HashDigest
    provider_id: NonEmptyId
    output: StructuredRacioInterpreterOutput
    result_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        packet: ConsciousAccessPacket,
        call: ProviderCallSpec,
        output: StructuredRacioInterpreterOutput,
    ) -> "StructuredRacioInterpreterEvidence":
        output.validate_against(packet)
        base = {
            "schema_version": "rei-structured-racio-interpreter-evidence-v1",
            "packet_id": packet.packet_id,
            "packet_hash": packet.content_hash(),
            "call_id": call.call_id,
            "call_spec_hash": call.content_hash(),
            "provider_id": call.provider.provider_id,
            "output": output,
        }
        result_id = content_id("structured_racio_interpreter", base)
        payload = {"result_id": result_id, **base}
        return cls(**payload, result_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_evidence(self) -> "StructuredRacioInterpreterEvidence":
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"result_id", "result_hash"},
        )
        if self.result_id != content_id("structured_racio_interpreter", id_payload):
            raise ValueError("Structured interpreter evidence ID differs from content")
        if self.result_hash != self.content_hash(
            exclude_fields=frozenset({"result_hash"})
        ):
            raise ValueError("Structured interpreter evidence hash differs from content")
        return self


@runtime_checkable
class StructuredRacioInterpreterExecution(Protocol):
    output: StructuredRacioInterpreterOutput
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord


@runtime_checkable
class RacioInterpreterProvider(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def required_input_artifact_ids(
        self,
        packet: ConsciousAccessPacket,
    ) -> tuple[NonEmptyId, ...]: ...

    def build_call_spec(self, packet: ConsciousAccessPacket) -> ProviderCallSpec: ...

    def execute(
        self,
        packet: ConsciousAccessPacket,
        *,
        call: ProviderCallSpec,
        clock: ExecutionClock,
    ) -> StructuredRacioInterpreterExecution: ...


def _parameter(name: str, value: object) -> ProviderParameter:
    return ProviderParameter(
        name=name,
        canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
    )


@dataclass(frozen=True, slots=True)
class DeterministicStructuredRacioInterpreterExecution:
    output: StructuredRacioInterpreterOutput
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord
    response_evidence: StructuredRacioInterpreterEvidence

    def __post_init__(self) -> None:
        ensure_call_record_contract(self.call_spec, self.call_record)
        if self.call_record.status != "succeeded":
            raise ValueError("Deterministic interpreter execution must succeed directly")
        if self.call_record.output_artifact_ids != (
            self.response_evidence.result_id,
        ):
            raise ValueError("Interpreter call must publish its exact result evidence")
        if self.response_evidence.output != self.output:
            raise ValueError("Interpreter output differs from its evidence")


@dataclass(frozen=True, slots=True)
class DeterministicStructuredRacioInterpreterProvider:
    """Model-free option-abstaining baseline over the exact public packet."""

    timeout_seconds: float = 30.0

    @property
    def identity(self) -> ProviderIdentity:
        payload = {
            "kind": "text_reasoner",
            "implementation": (
                "rei.communication.structured_interpreter."
                "DeterministicStructuredRacioInterpreterProvider"
            ),
            "implementation_revision": "1",
            "uses_model": False,
        }
        return ProviderIdentity(
            provider_id=content_id("provider", payload),
            **payload,
        )

    @property
    def parameters(self) -> tuple[ProviderParameter, ...]:
        values = {
            "output_schema_sha256": sha256_hex(
                StructuredRacioInterpreterOutput.model_json_schema()
            ),
            "policy": DETERMINISTIC_INTERPRETER_POLICY,
        }
        return tuple(_parameter(name, values[name]) for name in sorted(values))

    def required_input_artifact_ids(
        self,
        packet: ConsciousAccessPacket,
    ) -> tuple[NonEmptyId, ...]:
        return (packet.packet_id,)

    def build_call_spec(self, packet: ConsciousAccessPacket) -> ProviderCallSpec:
        return build_provider_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=(packet.packet_id,),
            parameters=self.parameters,
            timeout_seconds=self.timeout_seconds,
            fallback_policy=ProviderFallbackPolicy(
                mode="none",
                no_fallback_reason=INTERPRETER_NO_FALLBACK_REASON,
            ),
        )

    def _interpret(
        self,
        packet: ConsciousAccessPacket,
    ) -> StructuredRacioInterpreterOutput:
        action: str | None = None
        motive: str | None = None
        action_citation: str | None = None
        for observation in packet.visible_observations:
            if (
                observation.perception_status != "clear"
                or observation.signal_name not in {"motor_urge", "raw_urge"}
                or observation.perceived_value_json is None
            ):
                continue
            value = json.loads(observation.perceived_value_json)
            if isinstance(value, str) and value.startswith("structured_tendency:"):
                candidate = value.removeprefix("structured_tendency:")
                if candidate:
                    action = candidate
                    action_citation = observation.observation_id
                    break
        if action_citation is not None:
            citations = (action_citation,)
        elif packet.visible_observations:
            citations = (packet.visible_observations[0].observation_id,)
        else:
            citations = ()
        decisive_signal_limited = bool(
            packet.omitted_observation_ids
            or packet.degraded_observation_ids
            or packet.channel_quality <= 0.35
        )
        if citations and decisive_signal_limited:
            action = "unknown"
            motive = "unknown"
        ambiguity = (
            "Vidni signal ne zadošča za izbiro javne možnosti."
            if packet.language == "sl"
            else "The visible signal is insufficient to select a public option."
        )
        alternatives = (
            (ambiguity,) if packet.visible_observations else ()
        )
        output = StructuredRacioInterpreterOutput(
            source_mind=packet.source_mind,
            cited_observation_ids=tuple(sorted(citations)),
            inferred_option_id=None,
            inferred_action_tendency=action,
            inferred_motive_class=motive,
            confidence=(
                min(
                    0.35 if decisive_signal_limited else 0.49,
                    packet.channel_quality,
                )
                if citations
                else 0.0
            ),
            alternative_hypotheses=alternatives,
            unresolved_ambiguity=ambiguity,
        )
        return output.validate_against(packet)

    def execute(
        self,
        packet: ConsciousAccessPacket,
        *,
        call: ProviderCallSpec,
        clock: ExecutionClock,
    ) -> DeterministicStructuredRacioInterpreterExecution:
        ensure_call_contract(
            self.identity,
            call,
            request_id=packet.packet_id,
            expected_kind="text_reasoner",
            required_input_artifact_ids=(packet.packet_id,),
        )
        if call != self.build_call_spec(packet):
            raise ValueError("Deterministic interpreter call differs from its contract")
        started_at = clock.timestamp("racio_call_started")
        output = self._interpret(packet)
        evidence = StructuredRacioInterpreterEvidence.create(
            packet=packet,
            call=call,
            output=output,
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
        return DeterministicStructuredRacioInterpreterExecution(
            output=output,
            call_spec=call,
            call_record=record,
            response_evidence=evidence,
        )


@dataclass(frozen=True, slots=True)
class StructuredRacioInterpretationResult:
    """Trusted adapter result retaining filter and provider evidence together."""

    access: ConsciousAccessResult
    execution: StructuredRacioInterpreterExecution
    interpretation: RacioInterpretation


def adapt_structured_racio_interpretation(
    *,
    request: RacioInterpreterRequest,
    access: ConsciousAccessResult,
    execution: StructuredRacioInterpreterExecution,
    interpreter_id: str,
    interpreter_revision: str,
    interpreter_policy: str,
) -> StructuredRacioInterpretationResult:
    """Resolve public aliases only after a provider has returned a valid result."""

    packet = access.packet
    audit = access.audit
    if (
        audit.source_request_id != request.request_id
        or audit.source_request_hash != request.content_hash()
        or audit.packet_id != packet.packet_id
        or audit.packet_hash != packet.content_hash()
    ):
        raise ValueError("Conscious-access audit differs from request or packet")
    if execution.call_spec.request_id != packet.packet_id:
        raise ValueError("Interpreter execution belongs to another access packet")
    ensure_call_record_contract(execution.call_spec, execution.call_record)
    execution.output.validate_against(packet)
    evidence = getattr(execution, "response_evidence", None)
    if evidence is None:
        evidence = getattr(execution, "reasoning_artifact", None)
    if evidence is None:
        raise ValueError("Interpreter execution is missing response evidence")
    evidence_result_id = getattr(evidence, "result_id", None)
    content_hash = getattr(evidence, "content_hash", None)
    if not isinstance(evidence_result_id, str) or not callable(content_hash):
        raise ValueError("Interpreter response evidence is not a hashed artifact")
    if (
        getattr(evidence, "packet_id", None) != packet.packet_id
        or getattr(evidence, "packet_hash", None) != packet.content_hash()
        or getattr(evidence, "call_id", None) != execution.call_spec.call_id
        or getattr(evidence, "call_spec_hash", None)
        != execution.call_spec.content_hash()
        or getattr(evidence, "provider_id", None)
        != execution.call_spec.provider.provider_id
    ):
        raise ValueError("Interpreter response evidence has inconsistent lineage")

    observation_by_id = {
        observation.observation_id: observation
        for view in request.observable_views
        for observation in view.observations
    }
    cited_observations: list[ManifestationObservation] = []
    for public_id in execution.output.cited_observation_ids:
        source_id = audit.source_observation_id(public_id)
        observation = observation_by_id.get(source_id)
        if observation is None:
            raise ValueError("Public citation does not resolve into the trusted request")
        cited_observations.append(observation)
    inferred_option_id = (
        audit.source_option_id(execution.output.inferred_option_id)
        if execution.output.inferred_option_id is not None
        else None
    )
    interpretation = RacioInterpretation.create_c3(
        request=request,
        observations=tuple(cited_observations),
        inferred_option_id=inferred_option_id,
        inferred_action_tendency=execution.output.inferred_action_tendency,
        inferred_motive_class=execution.output.inferred_motive_class,
        confidence=execution.output.confidence,
        alternative_hypotheses=execution.output.alternative_hypotheses,
        unresolved_ambiguity=execution.output.unresolved_ambiguity,
        interpreter_id=interpreter_id,
        interpreter_revision=interpreter_revision,
        interpreter_policy=interpreter_policy,
        language=packet.language,
        conscious_access_packet_id=packet.packet_id,
        conscious_access_packet_hash=packet.content_hash(),
        interpreter_result_id=evidence_result_id,
        interpreter_result_hash=content_hash(),
    )
    return StructuredRacioInterpretationResult(
        access=access,
        execution=execution,
        interpretation=interpretation,
    )


@dataclass(frozen=True, slots=True)
class StructuredLLMRacioInterpreter:
    """Legacy-protocol adapter that puts conscious access before one provider call."""

    provider: RacioInterpreterProvider
    language: LanguageCode = "sl"
    ablation_mode: InterpreterAblationMode = "structured_only"
    option_descriptions: Mapping[str, str] | None = None
    supplemental_artifacts: tuple[TrustedVisibleArtifact, ...] = ()
    access_filter: ConsciousAccessFilter = field(
        default_factory=ConsciousAccessFilter
    )
    clock: ExecutionClock = field(default_factory=SystemExecutionClock)

    @property
    def interpreter_id(self) -> str:
        return self.provider.identity.provider_id

    @property
    def interpreter_revision(self) -> str:
        return self.provider.identity.implementation_revision

    @property
    def interpreter_policy(self) -> str:
        return (
            "c3_structured_llm_conscious_access_v1:"
            f"{self.ablation_mode}:{self.provider.identity.provider_id}"
        )

    def interpret_with_evidence(
        self,
        request: RacioInterpreterRequest,
        *,
        language: LanguageCode | None = None,
        option_descriptions: Mapping[str, str] | None = None,
    ) -> StructuredRacioInterpretationResult:
        active_language = self.language if language is None else language
        active_option_descriptions = (
            self.option_descriptions
            if option_descriptions is None
            else option_descriptions
        )
        access = self.access_filter.apply(
            request,
            language=active_language,
            ablation_mode=self.ablation_mode,
            option_descriptions=active_option_descriptions,
            supplemental_artifacts=self.supplemental_artifacts,
        )
        call = self.provider.build_call_spec(access.packet)
        execution = self.provider.execute(
            access.packet,
            call=call,
            clock=self.clock,
        )
        return adapt_structured_racio_interpretation(
            request=request,
            access=access,
            execution=execution,
            interpreter_id=self.interpreter_id,
            interpreter_revision=self.interpreter_revision,
            interpreter_policy=self.interpreter_policy,
        )

    def interpret(self, request: RacioInterpreterRequest) -> RacioInterpretation:
        return self.interpret_with_evidence(request).interpretation


@dataclass(frozen=True, slots=True)
class VisionLanguageRacioInterpreter(StructuredLLMRacioInterpreter):
    """C3 VLM adapter using the same strict output and trusted alias resolver."""

    ablation_mode: InterpreterAblationMode = "structured_plus_image"

    def __post_init__(self) -> None:
        if self.ablation_mode not in {
            "image_only",
            "structured_plus_image",
            "body_graph_plus_structured",
        }:
            raise ValueError("Vision-language interpreter requires a visual ablation")


__all__ = [
    "DETERMINISTIC_INTERPRETER_POLICY",
    "DeterministicStructuredRacioInterpreterExecution",
    "DeterministicStructuredRacioInterpreterProvider",
    "INTERPRETER_NO_FALLBACK_REASON",
    "InterpreterActionTendency",
    "InterpreterMotiveClass",
    "RacioInterpreterProvider",
    "StructuredLLMRacioInterpreter",
    "StructuredRacioInterpretationResult",
    "StructuredRacioInterpreterEvidence",
    "StructuredRacioInterpreterExecution",
    "StructuredRacioInterpreterOutput",
    "VisionLanguageRacioInterpreter",
    "adapt_structured_racio_interpretation",
]
