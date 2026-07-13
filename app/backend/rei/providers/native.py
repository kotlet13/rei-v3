"""Runtime-neutral native provider contracts and auditable execution clocks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, runtime_checkable

from ..ids import content_id, utc_now
from ..models.common import (
    FrozenArtifactModel,
    HashDigest,
    NonEmptyId,
    SafetyNotice,
    UtcTimestamp,
)
from ..models.communication import InstinktManifestation
from ..models.emocio import (
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioVisualState,
    EmocioWorld,
    ImageArtifact,
)
from ..models.instinkt import (
    BodyState,
    InstinktInputPacket,
    InstinktMemoryRecord,
    InstinktNativeConclusion,
    InstinktOptionRollout,
    InstinktSimulationConfig,
    OptionBodyEffect,
)
from ..models.provider import (
    PositiveSeconds,
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ProviderParameter,
)
from ..models.racio import RacioInputPacket, RacioNativeConclusion
from ..models.scene import SceneEvent


@runtime_checkable
class ExecutionClock(Protocol):
    """Timestamp source whose mode is explicit in run provenance."""

    @property
    def synthetic(self) -> bool: ...

    def timestamp(self, stage: str) -> UtcTimestamp: ...


@dataclass(frozen=True, slots=True)
class SystemExecutionClock:
    """Observe actual UTC wall-clock boundaries in production execution."""

    @property
    def synthetic(self) -> bool:
        return False

    def timestamp(self, stage: str) -> UtcTimestamp:
        del stage
        return utc_now()


_DETERMINISTIC_STAGE_OFFSETS = {
    "run_started": 0,
    "racio_call_started": 1,
    "emocio_call_started": 1,
    "instinkt_call_started": 1,
    "racio_call_finished": 2,
    "emocio_call_finished": 2,
    "instinkt_call_finished": 2,
    "assembly_started": 3,
    "assembly_finished": 4,
    "measure_created": 5,
    "run_finished": 6,
}


@dataclass(frozen=True, slots=True)
class DeterministicExecutionClock:
    """Explicit logical clock for byte-identical fixture/evaluation replay."""

    base: UtcTimestamp

    @property
    def synthetic(self) -> bool:
        return True

    def timestamp(self, stage: str) -> UtcTimestamp:
        try:
            offset = _DETERMINISTIC_STAGE_OFFSETS[stage]
        except KeyError as exc:
            raise ValueError(f"Unknown deterministic clock stage: {stage}") from exc
        return self.base + timedelta(microseconds=offset)


def build_provider_call_spec(
    *,
    identity: ProviderIdentity,
    request_id: NonEmptyId,
    input_artifact_ids: tuple[NonEmptyId, ...],
    seed: int | None = None,
    parameters: tuple[ProviderParameter, ...] = (),
    timeout_seconds: PositiveSeconds = 30.0,
    fallback_policy: ProviderFallbackPolicy | None = None,
    safety_notice: SafetyNotice = SafetyNotice(),
) -> ProviderCallSpec:
    """Build a runtime-neutral call contract selected by a provider.

    The engine never guesses model parameters, seeds or fallback behavior. A
    provider owns those choices and may use this helper to freeze them into a
    canonical call spec before execution.
    """

    if len(set(input_artifact_ids)) != len(input_artifact_ids):
        raise ValueError("Native provider call inputs must be unique")
    canonical_inputs = tuple(sorted(input_artifact_ids))
    if request_id not in canonical_inputs:
        raise ValueError("Native request artifact must be recorded as a call input")
    active_fallback = fallback_policy or ProviderFallbackPolicy(
        mode="none",
        no_fallback_reason="Provider declared no fallback for this native call.",
    )
    base = {
        "schema_version": "rei-native-provider-call-spec-v1",
        "request_id": request_id,
        "input_artifact_ids": canonical_inputs,
        "provider": identity,
        "seed": seed,
        "parameters": parameters,
        "timeout_seconds": timeout_seconds,
        "fallback_policy": active_fallback,
        "safety_notice": safety_notice,
    }
    return ProviderCallSpec(
        call_id=content_id("provider_call", base),
        **base,
    )


@runtime_checkable
class RacioNativeExecution(Protocol):
    conclusion: RacioNativeConclusion
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord

    @property
    def reasoning_artifact(self) -> FrozenArtifactModel | None: ...


@runtime_checkable
class EmocioNativeExecution(Protocol):
    conclusion: EmocioNativeConclusion
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord

    @property
    def source_world_id(self) -> NonEmptyId: ...

    @property
    def source_world_hash(self) -> HashDigest: ...

    @property
    def packet(self) -> EmocioInputPacket: ...

    @property
    def visual_state(self) -> EmocioVisualState: ...

    @property
    def rendered_images(self) -> tuple[ImageArtifact, ...]: ...

    @property
    def renderer_warning(self) -> str | None: ...


@runtime_checkable
class InstinktNativeExecution(Protocol):
    conclusion: InstinktNativeConclusion
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord
    packet: InstinktInputPacket
    source_body_state: BodyState
    option_effects: tuple[OptionBodyEffect, ...]
    associations: tuple[InstinktMemoryRecord, ...]

    @property
    def rollouts(self) -> tuple[InstinktOptionRollout, ...]: ...

    @property
    def manifestation(self) -> InstinktManifestation: ...

    @property
    def config(self) -> InstinktSimulationConfig: ...


@runtime_checkable
class RacioNativeProvider(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def required_input_artifact_ids(
        self, packet: RacioInputPacket
    ) -> tuple[NonEmptyId, ...]: ...

    def build_call_spec(self, packet: RacioInputPacket) -> ProviderCallSpec: ...

    def execute(
        self,
        packet: RacioInputPacket,
        *,
        call: ProviderCallSpec,
        clock: ExecutionClock,
    ) -> RacioNativeExecution: ...


@runtime_checkable
class EmocioNativeProvider(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def required_input_artifact_ids(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
        packet: EmocioInputPacket,
    ) -> tuple[NonEmptyId, ...]: ...

    def build_call_spec(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
        packet: EmocioInputPacket,
    ) -> ProviderCallSpec: ...

    def execute(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
        *,
        packet: EmocioInputPacket,
        call: ProviderCallSpec,
        clock: ExecutionClock,
    ) -> EmocioNativeExecution: ...


@runtime_checkable
class InstinktNativeProvider(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def required_input_artifact_ids(
        self,
        *,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        source_body_state: BodyState,
        option_effects: tuple[OptionBodyEffect, ...],
        config: InstinktSimulationConfig,
        associations: tuple[InstinktMemoryRecord, ...],
    ) -> tuple[NonEmptyId, ...]: ...

    def build_call_spec(
        self,
        *,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        source_body_state: BodyState,
        option_effects: tuple[OptionBodyEffect, ...],
        config: InstinktSimulationConfig,
        associations: tuple[InstinktMemoryRecord, ...],
    ) -> ProviderCallSpec: ...

    def execute(
        self,
        *,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        source_body_state: BodyState,
        option_effects: tuple[OptionBodyEffect, ...],
        config: InstinktSimulationConfig,
        associations: tuple[InstinktMemoryRecord, ...],
        call: ProviderCallSpec,
        clock: ExecutionClock,
    ) -> InstinktNativeExecution: ...


@runtime_checkable
class NativeProviderSet(Protocol):
    racio: RacioNativeProvider
    emocio: EmocioNativeProvider
    instinkt: InstinktNativeProvider

    @property
    def identities(self) -> tuple[ProviderIdentity, ...]: ...


__all__ = [
    "DeterministicExecutionClock",
    "EmocioNativeExecution",
    "EmocioNativeProvider",
    "ExecutionClock",
    "InstinktNativeExecution",
    "InstinktNativeProvider",
    "NativeProviderSet",
    "RacioNativeExecution",
    "RacioNativeProvider",
    "SystemExecutionClock",
    "build_provider_call_spec",
]
