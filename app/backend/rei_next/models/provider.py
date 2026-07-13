"""Provider provenance value objects shared by runs and provider protocols."""

from __future__ import annotations

import json
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    SafetyNotice,
    UtcTimestamp,
)


PositiveSeconds = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
ProviderKind = Literal[
    "text_reasoner",
    "vision_language",
    "image_renderer",
    "image_encoder",
    "visual_world_model",
    "body_dynamics",
    "artifact_store",
    "ego_trace_store",
]
ProviderCallStatus = Literal["succeeded", "failed", "timed_out", "fell_back"]
ProviderAttemptStatus = Literal["succeeded", "failed", "timed_out"]
ProviderFallbackStatus = Literal["succeeded", "failed", "timed_out", "skipped"]


class ProviderIdentity(FrozenArtifactModel):
    """Stable provider implementation identity with optional model provenance."""

    schema_version: Literal["rei-native-provider-identity-v1"] = (
        "rei-native-provider-identity-v1"
    )
    provider_id: NonEmptyId
    kind: ProviderKind
    implementation: NonEmptyText
    implementation_revision: NonEmptyText
    uses_model: bool = False
    model: NonEmptyText | None = None
    model_revision: NonEmptyText | None = None

    @model_validator(mode="after")
    def require_model_revision(self) -> Self:
        if self.uses_model and (self.model is None or self.model_revision is None):
            raise ValueError("Model-backed providers require model and revision")
        if not self.uses_model and (
            self.model is not None or self.model_revision is not None
        ):
            raise ValueError("Non-model providers cannot claim model provenance")
        return self


class ProviderParameter(FrozenModel):
    """One named provider setting stored as canonical JSON text."""

    name: NonEmptyText
    canonical_json_value: NonEmptyText

    @model_validator(mode="after")
    def validate_canonical_json(self) -> Self:
        try:
            value = json.loads(self.canonical_json_value)
        except json.JSONDecodeError as exc:
            raise ValueError("Provider parameter value must be valid JSON") from exc
        canonical = canonical_json_bytes(value).decode("utf-8")
        if canonical != self.canonical_json_value:
            raise ValueError("Provider parameter value must use canonical JSON")
        return self


def _require_unique_parameters(parameters: tuple[ProviderParameter, ...]) -> None:
    names = tuple(parameter.name for parameter in parameters)
    if len(set(names)) != len(names):
        raise ValueError("Provider parameter names must be unique")
    if names != tuple(sorted(names)):
        raise ValueError("Provider parameters must use canonical name order")


def _require_unique_ids(values: tuple[NonEmptyId, ...], field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must contain unique artifact IDs")


class ProviderFallbackPlan(FrozenModel):
    """Approved secondary call details, fixed before primary execution."""

    provider: ProviderIdentity
    seed: int | None = None
    parameters: tuple[ProviderParameter, ...] = ()
    timeout_seconds: PositiveSeconds

    @model_validator(mode="after")
    def require_seed_for_model(self) -> Self:
        _require_unique_parameters(self.parameters)
        if self.provider.uses_model and self.seed is None:
            raise ValueError("Model-backed fallback providers require a recorded seed")
        return self


class ProviderFallbackPolicy(FrozenModel):
    """Explicitly choose an approved provider fallback or document its absence."""

    mode: Literal["provider", "none"]
    plan: ProviderFallbackPlan | None = None
    no_fallback_reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.mode == "provider":
            if self.plan is None or self.no_fallback_reason is not None:
                raise ValueError(
                    "Provider fallback mode requires a plan and forbids a no-fallback reason"
                )
            return self
        if self.plan is not None or self.no_fallback_reason is None:
            raise ValueError(
                "No-fallback mode requires a reason and forbids a provider plan"
            )
        return self


class ProviderFallbackRecord(FrozenModel):
    provider: ProviderIdentity
    seed: int | None = None
    parameters: tuple[ProviderParameter, ...] = ()
    timeout_seconds: PositiveSeconds
    started_at: UtcTimestamp | None = None
    finished_at: UtcTimestamp | None = None
    status: ProviderFallbackStatus
    skip_reason: NonEmptyText | None = None
    output_artifact_ids: tuple[NonEmptyId, ...] = ()
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_fallback_record(self) -> Self:
        _require_unique_parameters(self.parameters)
        _require_unique_ids(self.output_artifact_ids, "output_artifact_ids")
        if self.status == "skipped":
            if self.started_at is not None or self.finished_at is not None:
                raise ValueError("A skipped fallback cannot claim execution timestamps")
            if self.skip_reason is None:
                raise ValueError("A skipped fallback requires an explicit reason")
        else:
            if self.started_at is None or self.finished_at is None:
                raise ValueError("An attempted fallback requires complete timestamps")
            if self.finished_at < self.started_at:
                raise ValueError("Fallback call cannot finish before it starts")
            if self.skip_reason is not None:
                raise ValueError("An attempted fallback cannot carry a skip reason")
        if self.provider.uses_model and self.seed is None:
            raise ValueError("Model-backed fallback records require a seed")
        if self.status != "succeeded" and self.output_artifact_ids:
            raise ValueError("An unsuccessful fallback cannot publish final artifacts")
        return self


class ProviderCallSpec(FrozenArtifactModel):
    """Immutable call contract approved before any provider is invoked."""

    schema_version: Literal["rei-native-provider-call-spec-v1"] = (
        "rei-native-provider-call-spec-v1"
    )
    call_id: NonEmptyId
    request_id: NonEmptyId
    input_artifact_ids: tuple[NonEmptyId, ...] = ()
    provider: ProviderIdentity
    seed: int | None = None
    parameters: tuple[ProviderParameter, ...] = ()
    timeout_seconds: PositiveSeconds
    fallback_policy: ProviderFallbackPolicy
    safety_notice: SafetyNotice = SafetyNotice()

    @model_validator(mode="after")
    def validate_call_spec(self) -> Self:
        _require_unique_parameters(self.parameters)
        _require_unique_ids(self.input_artifact_ids, "input_artifact_ids")
        if self.provider.uses_model and self.seed is None:
            raise ValueError("Model-backed provider calls require a recorded seed")
        fallback = self.fallback_policy.plan
        if fallback is not None:
            if fallback.provider.provider_id == self.provider.provider_id:
                raise ValueError("Fallback provider must differ from the primary provider")
            if fallback.provider.kind != self.provider.kind:
                raise ValueError("Fallback provider must expose the same capability")
        return self


class ProviderCallRecord(FrozenArtifactModel):
    """Immutable result provenance linked to the exact approved call-spec hash."""

    schema_version: Literal["rei-native-provider-call-record-v1"] = (
        "rei-native-provider-call-record-v1"
    )
    call_id: NonEmptyId
    spec_hash: HashDigest
    request_id: NonEmptyId
    input_artifact_ids: tuple[NonEmptyId, ...] = ()
    provider: ProviderIdentity
    seed: int | None = None
    parameters: tuple[ProviderParameter, ...] = ()
    timeout_seconds: PositiveSeconds
    started_at: UtcTimestamp
    primary_finished_at: UtcTimestamp
    finished_at: UtcTimestamp
    status: ProviderCallStatus
    primary_status: ProviderAttemptStatus
    fallback: ProviderFallbackRecord | None = None
    output_artifact_ids: tuple[NonEmptyId, ...] = ()
    warnings: tuple[str, ...] = ()
    safety_notice: SafetyNotice = SafetyNotice()

    @model_validator(mode="after")
    def validate_call_record(self) -> Self:
        _require_unique_parameters(self.parameters)
        _require_unique_ids(self.input_artifact_ids, "input_artifact_ids")
        _require_unique_ids(self.output_artifact_ids, "output_artifact_ids")
        if set(self.input_artifact_ids).intersection(self.output_artifact_ids):
            raise ValueError(
                "An immutable artifact ID cannot be both call input and output"
            )
        if self.finished_at < self.started_at:
            raise ValueError("Provider call cannot finish before it starts")
        if not self.started_at <= self.primary_finished_at <= self.finished_at:
            raise ValueError(
                "Primary attempt completion must fall within the aggregate call"
            )
        if self.provider.uses_model and self.seed is None:
            raise ValueError("Model-backed provider records require a seed")
        if self.fallback is None:
            if self.status == "fell_back":
                raise ValueError("A fallback status requires the complete fallback record")
            if self.primary_status != self.status:
                raise ValueError("A direct call status must match the primary attempt")
            if self.primary_finished_at != self.finished_at:
                raise ValueError(
                    "A call without fallback must finish with its primary attempt"
                )
            if self.status != "succeeded" and self.output_artifact_ids:
                raise ValueError("An unsuccessful call cannot publish final artifacts")
        else:
            if self.primary_status not in {"failed", "timed_out"}:
                raise ValueError(
                    "Fallback execution requires a failed or timed-out primary"
                )
            if self.fallback.provider.provider_id == self.provider.provider_id:
                raise ValueError("Fallback provider must differ from the primary provider")
            if self.fallback.provider.kind != self.provider.kind:
                raise ValueError("Fallback provider must expose the same capability")
            if self.fallback.status == "succeeded":
                expected_status: ProviderCallStatus = "fell_back"
            elif self.fallback.status == "skipped":
                expected_status = self.primary_status
            else:
                expected_status = self.fallback.status
            if self.status != expected_status:
                raise ValueError(
                    "Aggregate status must reflect the fallback attempt outcome"
                )
            if self.fallback.status == "skipped":
                if self.finished_at != self.primary_finished_at:
                    raise ValueError(
                        "A call with skipped fallback must finish with its primary attempt"
                    )
            else:
                if self.fallback.started_at < self.primary_finished_at:
                    raise ValueError("Fallback cannot start before the primary attempt ends")
                if self.fallback.finished_at > self.finished_at:
                    raise ValueError("Fallback cannot finish after the aggregate call")
            if self.fallback.status == "succeeded" and (
                self.output_artifact_ids != self.fallback.output_artifact_ids
            ):
                raise ValueError(
                    "A successful fallback must provide the call's final output artifacts"
                )
            if self.fallback.status != "succeeded" and self.output_artifact_ids:
                raise ValueError(
                    "An unsuccessful fallback cannot publish final call artifacts"
                )
        return self


def ensure_call_contract(
    identity: ProviderIdentity,
    call: ProviderCallSpec,
    *,
    request_id: NonEmptyId,
    seed: int | None = None,
    expected_kind: ProviderKind | None = None,
    required_input_artifact_ids: tuple[NonEmptyId, ...] = (),
) -> None:
    """Guard the lineage that every provider implementation must enforce."""

    if call.provider != identity:
        raise ValueError("Provider call identity does not match the implementation")
    if call.request_id != request_id:
        raise ValueError("Provider call request_id does not match its input")
    if seed is not None and call.seed != seed:
        raise ValueError("Explicit provider seed does not match call provenance")
    if expected_kind is not None and identity.kind != expected_kind:
        raise ValueError("Provider identity does not expose the required capability")
    if not set(required_input_artifact_ids).issubset(call.input_artifact_ids):
        raise ValueError("Provider call omits required request input artifacts")


def ensure_call_record_contract(
    spec: ProviderCallSpec,
    record: ProviderCallRecord,
) -> None:
    """Prove that an execution record closes its exact pre-approved call spec."""

    if record.call_id != spec.call_id:
        raise ValueError("Provider call record and spec must share call_id")
    if record.spec_hash != spec.content_hash():
        raise ValueError("Provider call record does not match its spec hash")
    if (
        record.request_id != spec.request_id
        or record.input_artifact_ids != spec.input_artifact_ids
        or record.provider != spec.provider
        or record.seed != spec.seed
        or record.parameters != spec.parameters
        or record.timeout_seconds != spec.timeout_seconds
        or record.safety_notice != spec.safety_notice
    ):
        raise ValueError("Provider call record diverges from its approved spec")

    approved_fallback = spec.fallback_policy.plan
    if record.fallback is None:
        if (
            approved_fallback is not None
            and record.primary_status in {"failed", "timed_out"}
        ):
            raise ValueError(
                "A failed primary with planned fallback requires an outcome or skip record"
            )
        return
    if approved_fallback is None:
        raise ValueError("Unplanned fallback cannot appear in a call record")
    if (
        record.fallback.provider != approved_fallback.provider
        or record.fallback.seed != approved_fallback.seed
        or record.fallback.parameters != approved_fallback.parameters
        or record.fallback.timeout_seconds != approved_fallback.timeout_seconds
    ):
        raise ValueError("Fallback execution diverges from its approved plan")


__all__ = [
    "PositiveSeconds",
    "ProviderAttemptStatus",
    "ProviderCallRecord",
    "ProviderCallSpec",
    "ProviderCallStatus",
    "ProviderFallbackPlan",
    "ProviderFallbackPolicy",
    "ProviderFallbackRecord",
    "ProviderFallbackStatus",
    "ProviderIdentity",
    "ProviderKind",
    "ProviderParameter",
    "ensure_call_contract",
    "ensure_call_record_contract",
]
