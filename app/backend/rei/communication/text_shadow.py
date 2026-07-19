"""Non-authoritative text-shadow boundary for conscious Racio interpretation.

This module contains no concrete model provider.  It converts the same trusted
``RacioInterpreterRequest`` used by the authoritative communication path into a
packet-local V3 view, records a diagnostic-only comparison, and keeps every
shadow artifact terminal.  Nothing defined here can commit a decision, resolve
governance, update a world, or replace ``CommunicationProcessResult.interpretation``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Protocol, runtime_checkable

from pydantic import model_validator

from ..ids import content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
)
from ..models.communication import RacioInterpretation, RacioInterpreterRequest
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ensure_call_record_contract,
)
from ..providers.native import ExecutionClock
from .conscious_access import ConsciousAccessFilter
from .epistemic_interpreter import RacioReportedUncertainty
from .epistemic_interpreter_v3 import (
    LEGACY_ACTION_RESOLUTION_V3,
    ActionHypothesisV3,
    AuditedBilingualTextV3,
    BilingualObservationV3,
    BilingualOptionV3,
    BilingualUncertaintyV3,
    MotiveHypothesisV3,
    RacioEpistemicInterpretationV3,
    RacioEpistemicPacketV3,
)


RacioInterpreterRuntimeMode = Literal["deterministic", "gemma4_text_shadow"]
ShadowStatus = Literal["succeeded", "failed", "not_attempted"]
ShadowFailureStage = Literal[
    "packet_construction",
    "transport",
    "draft_v3_validation",
    "canonicalizer_v3_validation",
]
ShadowFailureCode = Literal[
    "request_contract_failure",
    "runtime_identity_mismatch",
    "gpu_placement_failure",
    "generation_contract_failure",
    "thinking_separation_failure",
    "structured_output_invalid",
    "conscious_access_rejected",
    "ollama_unavailable",
    "wrong_model_digest",
    "timeout",
    "wrong_context",
    "partial_gpu_placement",
    "invalid_json",
    "duplicate_json_key",
    "draft_v3_validation",
    "canonicalizer_failure",
    "citation_scope_violation",
    "option_scope_violation",
    "unsupported_language",
    "packet_construction_failure",
    "provider_failure",
]


class ShadowPacketConstructionError(ValueError):
    """Bounded packet-adaptation failure that is safe to record."""

    def __init__(self, failure_code: ShadowFailureCode, summary: str) -> None:
        super().__init__(summary)
        self.failure_code = failure_code
        self.summary = summary


@dataclass(frozen=True, slots=True)
class ShadowPacketContext:
    """V3 packet plus transient public-alias mapping, never an acceptance audit."""

    packet: RacioEpistemicPacketV3
    option_alias_bindings: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        public_ids = tuple(item[0] for item in self.option_alias_bindings)
        source_ids = tuple(item[1] for item in self.option_alias_bindings)
        if public_ids != tuple(sorted(set(public_ids))):
            raise ValueError("Shadow option aliases must be sorted and unique")
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Shadow source option IDs must be unique")
        if public_ids != self.packet.public_option_ids:
            raise ValueError("Shadow option bindings must close the V3 public scope")

    def source_option_id(self, public_option_id: str) -> str:
        matches = tuple(
            source
            for public, source in self.option_alias_bindings
            if public == public_option_id
        )
        if len(matches) != 1:
            raise ValueError("Unknown or ambiguous shadow public option alias")
        return matches[0]


class ShadowRacioInterpretationArtifact(FrozenArtifactModel):
    """Content-addressed wrapper around the frozen V3 interpretation value."""

    schema_version: Literal[
        "rei-native-shadow-racio-interpretation-v1"
    ] = "rei-native-shadow-racio-interpretation-v1"
    interpretation_id: NonEmptyId
    packet_id: NonEmptyId
    packet_sha256: HashDigest
    structured_output: RacioEpistemicInterpretationV3
    no_authority: Literal[True] = True
    interpretation_sha256: HashDigest

    @classmethod
    def create(
        cls,
        *,
        packet: RacioEpistemicPacketV3,
        output: RacioEpistemicInterpretationV3,
    ) -> "ShadowRacioInterpretationArtifact":
        output.validate_against(packet)
        base = {
            "schema_version": "rei-native-shadow-racio-interpretation-v1",
            "packet_id": packet.packet_id,
            "packet_sha256": packet.packet_hash,
            "structured_output": output,
            "no_authority": True,
        }
        interpretation_id = content_id("shadow_racio_interpretation", base)
        payload = {"interpretation_id": interpretation_id, **base}
        return cls(
            **payload,
            interpretation_sha256=sha256_hex(payload),
        )

    @model_validator(mode="after")
    def validate_identity(self) -> "ShadowRacioInterpretationArtifact":
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"interpretation_id", "interpretation_sha256"},
        )
        if self.interpretation_id != content_id(
            "shadow_racio_interpretation", id_payload
        ):
            raise ValueError("Shadow interpretation ID differs from its content")
        hash_payload = {"interpretation_id": self.interpretation_id, **id_payload}
        if self.interpretation_sha256 != sha256_hex(hash_payload):
            raise ValueError("Shadow interpretation hash differs from its content")
        if self.structured_output.source_mind not in {"E", "I"}:
            raise ValueError("Shadow interpretation has an invalid source mind")
        return self


class ShadowInterpretationComparison(FrozenArtifactModel):
    """Terminal diagnostic comparison with no authoritative interpretation role."""

    schema_version: Literal[
        "rei-native-shadow-interpretation-comparison-v1"
    ] = "rei-native-shadow-interpretation-comparison-v1"
    comparison_id: NonEmptyId
    source_mind: Literal["E", "I"]
    authoritative_request_id: NonEmptyId
    authoritative_request_sha256: HashDigest
    deterministic_interpretation_id: NonEmptyId
    deterministic_interpretation_sha256: HashDigest
    shadow_interpretation_id: NonEmptyId
    shadow_interpretation_sha256: HashDigest
    deterministic_option_id: NonEmptyId | None
    shadow_public_option_id: NonEmptyId | None
    shadow_source_option_id: NonEmptyId | None
    shadow_option_citations: tuple[NonEmptyId, ...]
    option_mapping_matches: bool
    deterministic_action_tendency: NonEmptyText | None
    shadow_action_hypotheses: tuple[ActionHypothesisV3, ...]
    action_family_matches: bool | None
    action_subtype_matches: bool | None
    deterministic_motive_summary: NonEmptyText
    shadow_motive_hypotheses: tuple[MotiveHypothesisV3, ...]
    shadow_option_uncertainty: Literal[
        "uncertain", "not_uncertain", "not_reported"
    ]
    shadow_motive_uncertainty: Literal[
        "uncertain", "not_uncertain", "not_reported"
    ]
    no_authority: Literal[True] = True
    comparison_sha256: HashDigest

    @classmethod
    def create(
        cls,
        *,
        request: RacioInterpreterRequest,
        deterministic: RacioInterpretation,
        shadow: ShadowRacioInterpretationArtifact,
        packet_context: ShadowPacketContext,
    ) -> "ShadowInterpretationComparison":
        deterministic.validate_against_request(request)
        output = shadow.structured_output
        output.validate_against(packet_context.packet)
        option = output.option_inference
        shadow_public_option_id = None if option is None else option.option_id
        shadow_source_option_id = (
            None
            if shadow_public_option_id is None
            else packet_context.source_option_id(shadow_public_option_id)
        )
        option_mapping_matches = (
            deterministic.inferred_option_id == shadow_source_option_id
        )

        deterministic_family: str | None = None
        deterministic_subtype: str | None = None
        action = deterministic.inferred_action_tendency
        resolutions = LEGACY_ACTION_RESOLUTION_V3.get(action or "", ())
        if len(resolutions) == 1:
            family, subtype = resolutions[0].split("/", 1)
            deterministic_family = family
            if not subtype.startswith("<family_fallback:"):
                deterministic_subtype = subtype
        shadow_families = {item.family for item in output.action_hypotheses}
        shadow_subtypes = {
            item.subtype
            for item in output.action_hypotheses
            if item.subtype is not None
        }
        family_matches = (
            None
            if deterministic_family is None
            else deterministic_family in shadow_families
        )
        subtype_matches = (
            None
            if deterministic_subtype is None
            else deterministic_subtype in shadow_subtypes
        )

        uncertainty: RacioReportedUncertainty = output.racio_reported_uncertainty
        base = {
            "schema_version": "rei-native-shadow-interpretation-comparison-v1",
            "source_mind": request.source_mind,
            "authoritative_request_id": request.request_id,
            "authoritative_request_sha256": request.content_hash(),
            "deterministic_interpretation_id": deterministic.interpretation_id,
            "deterministic_interpretation_sha256": deterministic.content_hash(),
            "shadow_interpretation_id": shadow.interpretation_id,
            "shadow_interpretation_sha256": shadow.interpretation_sha256,
            "deterministic_option_id": deterministic.inferred_option_id,
            "shadow_public_option_id": shadow_public_option_id,
            "shadow_source_option_id": shadow_source_option_id,
            "shadow_option_citations": (
                () if option is None else option.cited_observation_ids
            ),
            "option_mapping_matches": option_mapping_matches,
            "deterministic_action_tendency": action,
            "shadow_action_hypotheses": output.action_hypotheses,
            "action_family_matches": family_matches,
            "action_subtype_matches": subtype_matches,
            "deterministic_motive_summary": deterministic.inferred_motive,
            "shadow_motive_hypotheses": output.motive_hypotheses,
            "shadow_option_uncertainty": uncertainty.option_mapping,
            "shadow_motive_uncertainty": uncertainty.motive_interpretation,
            "no_authority": True,
        }
        comparison_id = content_id("shadow_interpretation_comparison", base)
        payload = {"comparison_id": comparison_id, **base}
        return cls(**payload, comparison_sha256=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_identity(self) -> "ShadowInterpretationComparison":
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"comparison_id", "comparison_sha256"},
        )
        if self.comparison_id != content_id(
            "shadow_interpretation_comparison", id_payload
        ):
            raise ValueError("Shadow comparison ID differs from its content")
        hash_payload = {"comparison_id": self.comparison_id, **id_payload}
        if self.comparison_sha256 != sha256_hex(hash_payload):
            raise ValueError("Shadow comparison hash differs from its content")
        return self


class ShadowRacioInterpretationResult(FrozenArtifactModel):
    """One terminal shadow receipt; all references are diagnostic-only."""

    schema_version: Literal[
        "rei-native-shadow-racio-result-v1"
    ] = "rei-native-shadow-racio-result-v1"
    result_id: NonEmptyId
    source_mind: Literal["E", "I"]
    authoritative_request_id: NonEmptyId
    authoritative_request_sha256: HashDigest
    deterministic_interpretation_id: NonEmptyId
    deterministic_interpretation_sha256: HashDigest
    status: ShadowStatus
    shadow_packet_id: NonEmptyId | None
    shadow_packet_sha256: HashDigest | None
    shadow_interpretation_id: NonEmptyId | None
    shadow_interpretation_sha256: HashDigest | None
    provider_call_record_id: NonEmptyId | None
    provider_call_record_sha256: HashDigest | None
    response_evidence_id: NonEmptyId | None
    response_evidence_sha256: HashDigest | None
    diagnostic_comparison_id: NonEmptyId | None
    diagnostic_comparison_sha256: HashDigest | None
    failure_stage: ShadowFailureStage | None
    failure_code: ShadowFailureCode | None
    failure_summary: NonEmptyText | None
    no_authority: Literal[True] = True
    result_sha256: HashDigest

    @classmethod
    def create(
        cls,
        *,
        request: RacioInterpreterRequest,
        deterministic: RacioInterpretation,
        status: ShadowStatus,
        packet: RacioEpistemicPacketV3 | None = None,
        shadow: ShadowRacioInterpretationArtifact | None = None,
        call_record: ProviderCallRecord | None = None,
        response_evidence_id: str | None = None,
        response_evidence_sha256: str | None = None,
        comparison: ShadowInterpretationComparison | None = None,
        failure_stage: ShadowFailureStage | None = None,
        failure_code: ShadowFailureCode | None = None,
        failure_summary: str | None = None,
    ) -> "ShadowRacioInterpretationResult":
        deterministic.validate_against_request(request)
        base = {
            "schema_version": "rei-native-shadow-racio-result-v1",
            "source_mind": request.source_mind,
            "authoritative_request_id": request.request_id,
            "authoritative_request_sha256": request.content_hash(),
            "deterministic_interpretation_id": deterministic.interpretation_id,
            "deterministic_interpretation_sha256": deterministic.content_hash(),
            "status": status,
            "shadow_packet_id": None if packet is None else packet.packet_id,
            "shadow_packet_sha256": None if packet is None else packet.packet_hash,
            "shadow_interpretation_id": (
                None if shadow is None else shadow.interpretation_id
            ),
            "shadow_interpretation_sha256": (
                None if shadow is None else shadow.interpretation_sha256
            ),
            "provider_call_record_id": (
                None if call_record is None else call_record.call_id
            ),
            "provider_call_record_sha256": (
                None if call_record is None else call_record.content_hash()
            ),
            "response_evidence_id": response_evidence_id,
            "response_evidence_sha256": response_evidence_sha256,
            "diagnostic_comparison_id": (
                None if comparison is None else comparison.comparison_id
            ),
            "diagnostic_comparison_sha256": (
                None if comparison is None else comparison.comparison_sha256
            ),
            "failure_stage": failure_stage,
            "failure_code": failure_code,
            "failure_summary": failure_summary,
            "no_authority": True,
        }
        result_id = content_id("shadow_racio_result", base)
        payload = {"result_id": result_id, **base}
        return cls(**payload, result_sha256=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_result(self) -> "ShadowRacioInterpretationResult":
        paired_fields = (
            (self.shadow_packet_id, self.shadow_packet_sha256),
            (self.shadow_interpretation_id, self.shadow_interpretation_sha256),
            (self.provider_call_record_id, self.provider_call_record_sha256),
            (self.response_evidence_id, self.response_evidence_sha256),
            (self.diagnostic_comparison_id, self.diagnostic_comparison_sha256),
        )
        if any((left is None) != (right is None) for left, right in paired_fields):
            raise ValueError("Shadow receipt references require complete ID/hash pairs")
        success_refs = (
            self.shadow_packet_id,
            self.shadow_interpretation_id,
            self.provider_call_record_id,
            self.response_evidence_id,
            self.diagnostic_comparison_id,
        )
        failure_fields = (
            self.failure_stage,
            self.failure_code,
            self.failure_summary,
        )
        if self.status == "succeeded":
            if any(value is None for value in success_refs) or any(
                value is not None for value in failure_fields
            ):
                raise ValueError("Successful shadow receipt requires all success references")
        elif self.status == "failed":
            if any(value is not None for value in (
                self.shadow_interpretation_id,
                self.response_evidence_id,
                self.diagnostic_comparison_id,
            )) or any(value is None for value in failure_fields):
                raise ValueError("Failed shadow receipt has invalid semantic references")
            if (self.provider_call_record_id is None) != (self.shadow_packet_id is None):
                raise ValueError(
                    "An attempted failed shadow lane requires its exact packet"
                )
        else:
            if any(value is not None for value in (*success_refs, *failure_fields)):
                raise ValueError("Not-attempted shadow receipt cannot claim artifacts or failure")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"result_id", "result_sha256"},
        )
        if self.result_id != content_id("shadow_racio_result", id_payload):
            raise ValueError("Shadow result ID differs from its content")
        hash_payload = {"result_id": self.result_id, **id_payload}
        if self.result_sha256 != sha256_hex(hash_payload):
            raise ValueError("Shadow result hash differs from its content")
        return self


@dataclass(frozen=True, slots=True)
class ShadowProviderAttempt:
    """Provider-neutral one-attempt result returned to the engine."""

    status: Literal["succeeded", "failed"]
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord
    output: RacioEpistemicInterpretationV3 | None = None
    response_evidence: FrozenArtifactModel | None = None
    response_evidence_id: str | None = None
    response_evidence_sha256: str | None = None
    failure_stage: ShadowFailureStage | None = None
    failure_code: ShadowFailureCode | None = None
    failure_summary: str | None = None

    def __post_init__(self) -> None:
        ensure_call_record_contract(self.call_spec, self.call_record)
        evidence_presence = (
            self.response_evidence is not None,
            self.response_evidence_id is not None,
            self.response_evidence_sha256 is not None,
        )
        if any(evidence_presence) and not all(evidence_presence):
            raise ValueError("Shadow response evidence requires object, ID and hash")
        if self.response_evidence is not None:
            if self.response_evidence.content_hash() != self.response_evidence_sha256:
                raise ValueError("Shadow response evidence hash differs from its object")
            if self.call_record.output_artifact_ids != (self.response_evidence_id,):
                raise ValueError("Successful shadow call must publish response evidence")
        failure_fields = (
            self.failure_stage,
            self.failure_code,
            self.failure_summary,
        )
        if self.status == "succeeded":
            if (
                self.call_record.status != "succeeded"
                or self.output is None
                or self.response_evidence is None
                or any(value is not None for value in failure_fields)
            ):
                raise ValueError("Successful shadow attempt is incomplete")
        elif (
            self.call_record.status not in {"failed", "timed_out"}
            or self.output is not None
            or self.response_evidence is not None
            or self.response_evidence_id is not None
            or self.response_evidence_sha256 is not None
            or any(value is None for value in failure_fields)
        ):
            raise ValueError("Failed shadow attempt is incomplete")


@runtime_checkable
class ShadowRacioInterpreter(Protocol):
    """Explicitly injected one-shot shadow interpreter dependency."""

    def interpret_shadow(
        self,
        packet: RacioEpistemicPacketV3,
        *,
        clock: ExecutionClock,
    ) -> ShadowProviderAttempt: ...


@dataclass(frozen=True, slots=True)
class ShadowRacioInterpretationExecution:
    """All terminal artifacts for one E or I shadow lane."""

    source_mind: Literal["E", "I"]
    packet: RacioEpistemicPacketV3 | None
    call_spec: ProviderCallSpec | None
    call_record: ProviderCallRecord | None
    interpretation: ShadowRacioInterpretationArtifact | None
    response_evidence: FrozenArtifactModel | None
    comparison: ShadowInterpretationComparison | None
    result: ShadowRacioInterpretationResult

    def __post_init__(self) -> None:
        if self.result.source_mind != self.source_mind:
            raise ValueError("Shadow execution source mind differs from its receipt")
        if (self.call_spec is None) != (self.call_record is None):
            raise ValueError("Shadow execution call spec and record must appear together")
        if self.call_spec is not None and self.call_record is not None:
            if self.packet is None:
                raise ValueError("A shadow provider call requires its exact packet")
            if (
                self.call_spec.request_id != self.packet.packet_id
                or self.call_spec.input_artifact_ids != (self.packet.packet_id,)
            ):
                raise ValueError("Shadow call spec differs from its packet lineage")
            ensure_call_record_contract(self.call_spec, self.call_record)
        if self.result.status == "succeeded":
            if any(
                value is None
                for value in (
                    self.packet,
                    self.call_spec,
                    self.interpretation,
                    self.response_evidence,
                    self.comparison,
                )
            ):
                raise ValueError("Successful shadow execution is incomplete")
            assert self.packet is not None
            assert self.interpretation is not None
            assert self.response_evidence is not None
            assert self.comparison is not None
            self.interpretation.structured_output.validate_against(self.packet)
            if (
                self.interpretation.packet_id != self.packet.packet_id
                or self.interpretation.packet_sha256 != self.packet.packet_hash
                or self.result.shadow_packet_id != self.packet.packet_id
                or self.result.shadow_packet_sha256 != self.packet.packet_hash
                or self.result.shadow_interpretation_id
                != self.interpretation.interpretation_id
                or self.result.shadow_interpretation_sha256
                != self.interpretation.interpretation_sha256
                or self.result.provider_call_record_id != self.call_record.call_id
                or self.result.provider_call_record_sha256
                != self.call_record.content_hash()
                or self.call_record.output_artifact_ids
                != (self.result.response_evidence_id,)
                or getattr(self.response_evidence, "result_id", None)
                != self.result.response_evidence_id
                or self.result.response_evidence_sha256
                != self.response_evidence.content_hash()
                or self.result.diagnostic_comparison_id
                != self.comparison.comparison_id
                or self.result.diagnostic_comparison_sha256
                != self.comparison.comparison_sha256
                or self.comparison.shadow_interpretation_id
                != self.interpretation.interpretation_id
                or self.comparison.shadow_interpretation_sha256
                != self.interpretation.interpretation_sha256
                or self.comparison.source_mind != self.result.source_mind
                or self.comparison.authoritative_request_id
                != self.result.authoritative_request_id
                or self.comparison.authoritative_request_sha256
                != self.result.authoritative_request_sha256
                or self.comparison.deterministic_interpretation_id
                != self.result.deterministic_interpretation_id
                or self.comparison.deterministic_interpretation_sha256
                != self.result.deterministic_interpretation_sha256
            ):
                raise ValueError("Shadow success artifacts do not close their lineage")
        elif any(
            value is not None
            for value in (self.interpretation, self.response_evidence, self.comparison)
        ):
            raise ValueError("Failed shadow execution cannot carry accepted semantics")
        elif self.call_record is not None and (
            self.packet is None
            or self.result.shadow_packet_id != self.packet.packet_id
            or self.result.shadow_packet_sha256 != self.packet.packet_hash
            or self.result.provider_call_record_id != self.call_record.call_id
            or self.result.provider_call_record_sha256
            != self.call_record.content_hash()
        ):
            raise ValueError("Failed shadow receipt differs from its call record")


def build_racio_epistemic_shadow_packet_v3(
    request: RacioInterpreterRequest,
    *,
    language: Literal["sl", "en"],
    option_descriptions: Mapping[str, str],
) -> ShadowPacketContext:
    """Adapt one trusted request through the existing conscious-access filter.

    The returned V3 packet contains only packet-local aliases and public text.
    The acceptance audit is deliberately discarded after extracting the public
    option alias mapping needed for diagnostic comparison.
    """

    if language != "sl":
        raise ShadowPacketConstructionError(
            "unsupported_language",
            "Gemma text shadow currently requires a canonical Slovene request.",
        )
    if set(option_descriptions) != set(request.allowed_option_ids):
        raise ShadowPacketConstructionError(
            "packet_construction_failure",
            "Public option descriptions do not close the trusted request scope.",
        )
    try:
        access = ConsciousAccessFilter(seed=0).apply(
            request,
            language="sl",
            ablation_mode="structured_only",
            option_descriptions=option_descriptions,
        )
        observations = tuple(
            BilingualObservationV3(
                observation_id=item.observation_id,
                atomic_evidence_unit_id=f"atomic_{index:03d}",
                perceptual_unit_count=1,
                signal_alias=f"signal_{index:03d}",
                perception_status=item.perception_status,
                text=(
                    None
                    if item.perceived_value_json is None
                    else AuditedBilingualTextV3(
                        canonical_sl=(
                            f"{item.signal_name}={item.perceived_value_json}"
                        )
                    )
                ),
                provenance=item.provenance,
            )
            for index, item in enumerate(
                access.packet.visible_observations,
                start=1,
            )
        )
        options = tuple(
            BilingualOptionV3(
                option_id=item.option_id,
                text=AuditedBilingualTextV3(canonical_sl=item.description),
            )
            for item in access.packet.public_option_scope
        )
        packet = RacioEpistemicPacketV3.create(
            source_mind=request.source_mind,
            presentation_mode="canonical_sl_only",
            visible_observations=observations,
            omitted_observation_ids=access.packet.omitted_observation_ids,
            public_option_scope=options,
            channel_quality=access.packet.channel_quality,
            uncertainty=BilingualUncertaintyV3(
                text=AuditedBilingualTextV3(
                    canonical_sl=access.packet.uncertainty,
                )
            ),
        )
        bindings = tuple(
            sorted(
                (
                    (item.public_option_id, item.source_option_id)
                    for item in access.audit.option_lineage
                ),
                key=lambda item: item[0],
            )
        )
        return ShadowPacketContext(
            packet=packet,
            option_alias_bindings=bindings,
        )
    except ShadowPacketConstructionError:
        raise
    except (TypeError, ValueError) as exc:
        raise ShadowPacketConstructionError(
            "packet_construction_failure",
            "The trusted request could not be adapted to the frozen V3 packet.",
        ) from exc


def execute_racio_text_shadow(
    *,
    request: RacioInterpreterRequest,
    deterministic: RacioInterpretation,
    language: Literal["sl", "en"],
    option_descriptions: Mapping[str, str],
    interpreter: ShadowRacioInterpreter,
    clock: ExecutionClock,
) -> ShadowRacioInterpretationExecution:
    """Execute one terminal shadow lane without touching authoritative state."""

    deterministic.validate_against_request(request)
    try:
        packet_context = build_racio_epistemic_shadow_packet_v3(
            request,
            language=language,
            option_descriptions=option_descriptions,
        )
    except ShadowPacketConstructionError as exc:
        result = ShadowRacioInterpretationResult.create(
            request=request,
            deterministic=deterministic,
            status="failed",
            failure_stage="packet_construction",
            failure_code=exc.failure_code,
            failure_summary=exc.summary,
        )
        return ShadowRacioInterpretationExecution(
            source_mind=request.source_mind,
            packet=None,
            call_spec=None,
            call_record=None,
            interpretation=None,
            response_evidence=None,
            comparison=None,
            result=result,
        )

    attempt = interpreter.interpret_shadow(packet_context.packet, clock=clock)
    if attempt.status == "failed":
        result = ShadowRacioInterpretationResult.create(
            request=request,
            deterministic=deterministic,
            status="failed",
            packet=packet_context.packet,
            call_record=attempt.call_record,
            failure_stage=attempt.failure_stage,
            failure_code=attempt.failure_code,
            failure_summary=attempt.failure_summary,
        )
        return ShadowRacioInterpretationExecution(
            source_mind=request.source_mind,
            packet=packet_context.packet,
            call_spec=attempt.call_spec,
            call_record=attempt.call_record,
            interpretation=None,
            response_evidence=None,
            comparison=None,
            result=result,
        )

    assert attempt.output is not None
    assert attempt.response_evidence is not None
    assert attempt.response_evidence_id is not None
    assert attempt.response_evidence_sha256 is not None
    shadow = ShadowRacioInterpretationArtifact.create(
        packet=packet_context.packet,
        output=attempt.output,
    )
    comparison = ShadowInterpretationComparison.create(
        request=request,
        deterministic=deterministic,
        shadow=shadow,
        packet_context=packet_context,
    )
    result = ShadowRacioInterpretationResult.create(
        request=request,
        deterministic=deterministic,
        status="succeeded",
        packet=packet_context.packet,
        shadow=shadow,
        call_record=attempt.call_record,
        response_evidence_id=attempt.response_evidence_id,
        response_evidence_sha256=attempt.response_evidence_sha256,
        comparison=comparison,
    )
    return ShadowRacioInterpretationExecution(
        source_mind=request.source_mind,
        packet=packet_context.packet,
        call_spec=attempt.call_spec,
        call_record=attempt.call_record,
        interpretation=shadow,
        response_evidence=attempt.response_evidence,
        comparison=comparison,
        result=result,
    )


__all__ = [
    "RacioInterpreterRuntimeMode",
    "ShadowFailureCode",
    "ShadowFailureStage",
    "ShadowInterpretationComparison",
    "ShadowPacketConstructionError",
    "ShadowPacketContext",
    "ShadowProviderAttempt",
    "ShadowRacioInterpretationArtifact",
    "ShadowRacioInterpretationExecution",
    "ShadowRacioInterpretationResult",
    "ShadowRacioInterpreter",
    "build_racio_epistemic_shadow_packet_v3",
    "execute_racio_text_shadow",
]
