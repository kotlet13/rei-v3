"""Provider-free native R/E/I adapters with closed call provenance.

These adapters make the deterministic native processors usable through the
same pre-approved call-spec and immutable call-record boundary as external
providers.  The capability kinds are the nearest existing B2 protocol kinds;
the identities explicitly state that no model is used.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from ..emocio.packets import build_emocio_packet
from ..emocio.processor import DeterministicEmocioProcessor, EmocioProcessingResult
from ..emocio.runtime import (
    EmocioBinarySnapshot,
    EmocioProcessingArtifact,
    EmocioProcessorRuntimeConfig,
    binary_snapshots_from_processing,
)
from ..ids import content_id
from ..instinkt.processor import InstinktProcessResult, process_instinkt
from ..instinkt.association_memory import BoundedAssociativeMemory
from ..models.common import NonEmptyId, UtcTimestamp
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
    instinkt_memory_record_id,
)
from ..models.provider import (
    PositiveSeconds,
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ProviderKind,
    ensure_call_contract,
    ensure_call_record_contract,
)
from ..models.racio import RacioInputPacket, RacioNativeConclusion
from ..models.scene import SceneEvent
from ..racio.processor import DeterministicRacioProvider
from .native import ExecutionClock, build_provider_call_spec


_NO_FALLBACK_REASON = (
    "Provider-free deterministic native execution has no external fallback."
)

NativeConclusionT = TypeVar(
    "NativeConclusionT",
    RacioNativeConclusion,
    EmocioNativeConclusion,
    InstinktNativeConclusion,
)


def _canonical_artifact_ids(
    artifact_ids: tuple[NonEmptyId, ...],
) -> tuple[NonEmptyId, ...]:
    if len(set(artifact_ids)) != len(artifact_ids):
        raise ValueError("Deterministic native call inputs must be unique")
    return tuple(sorted(artifact_ids))


def emocio_world_input_id(world: EmocioWorld) -> NonEmptyId:
    """Content-address the exact Emocio world admitted to one native call."""

    return content_id("emocio_world_input", world)


def instinkt_memory_input_id(
    associations: tuple[InstinktMemoryRecord, ...],
) -> NonEmptyId:
    """Content-address exact experienced and observation-only memory records."""

    return content_id("instinkt_memory_input", associations)


def instinkt_association_input_id(
    associations: tuple[InstinktMemoryRecord, ...],
) -> NonEmptyId:
    """Backward-compatible name for the generalized typed memory input."""

    return instinkt_memory_input_id(associations)


def _identity(
    *,
    capability: str,
    kind: ProviderKind,
    implementation: str,
    implementation_revision: str,
) -> ProviderIdentity:
    identity_payload = {
        "capability": capability,
        "kind": kind,
        "implementation": implementation,
        "implementation_revision": implementation_revision,
        "uses_model": False,
    }
    return ProviderIdentity(
        provider_id=content_id("provider", identity_payload),
        kind=kind,
        implementation=implementation,
        implementation_revision=implementation_revision,
        uses_model=False,
    )


def build_native_call_spec(
    *,
    identity: ProviderIdentity,
    request_id: NonEmptyId,
    input_artifact_ids: tuple[NonEmptyId, ...],
    timeout_seconds: PositiveSeconds = 30.0,
) -> ProviderCallSpec:
    """Create one stable, no-model, no-fallback native call contract."""

    if identity.uses_model:
        raise ValueError("Deterministic native call specs require a non-model identity")
    return build_provider_call_spec(
        identity=identity,
        request_id=request_id,
        input_artifact_ids=_canonical_artifact_ids(input_artifact_ids),
        timeout_seconds=timeout_seconds,
        fallback_policy=ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason=_NO_FALLBACK_REASON,
        ),
    )


def _validate_call(
    *,
    identity: ProviderIdentity,
    call: ProviderCallSpec,
    request_id: NonEmptyId,
    expected_kind: ProviderKind,
    expected_inputs: tuple[NonEmptyId, ...],
) -> None:
    canonical_inputs = _canonical_artifact_ids(expected_inputs)
    ensure_call_contract(
        identity,
        call,
        request_id=request_id,
        expected_kind=expected_kind,
        required_input_artifact_ids=canonical_inputs,
    )
    if call.input_artifact_ids != canonical_inputs:
        raise ValueError(
            "Deterministic native call must contain exactly its profile-blind inputs"
        )
    if call.seed is not None or call.parameters:
        raise ValueError("Provider-free deterministic native calls use no seed or parameters")
    if call.fallback_policy.mode != "none":
        raise ValueError("Provider-free deterministic native calls cannot use a fallback")
    canonical_call = build_native_call_spec(
        identity=identity,
        request_id=request_id,
        input_artifact_ids=canonical_inputs,
        timeout_seconds=call.timeout_seconds,
    )
    if call != canonical_call:
        raise ValueError("Deterministic native call differs from its canonical call spec")


def _successful_record(
    *,
    call: ProviderCallSpec,
    output_artifact_ids: tuple[NonEmptyId, ...],
    started_at: UtcTimestamp,
    finished_at: UtcTimestamp,
) -> ProviderCallRecord:
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
        output_artifact_ids=output_artifact_ids,
        safety_notice=call.safety_notice,
    )
    ensure_call_record_contract(call, record)
    return record


def _execution_start(
    *,
    clock: ExecutionClock | None,
    stage: str,
    started_at: UtcTimestamp | None,
    finished_at: UtcTimestamp | None,
) -> UtcTimestamp:
    if clock is not None:
        if started_at is not None or finished_at is not None:
            raise ValueError("Pass either an execution clock or explicit timestamps")
        return clock.timestamp(stage)
    if started_at is None or finished_at is None:
        raise ValueError("Explicit provider execution requires both timestamps")
    return started_at


def _execution_finish(
    *,
    clock: ExecutionClock | None,
    stage: str,
    finished_at: UtcTimestamp | None,
) -> UtcTimestamp:
    if clock is not None:
        return clock.timestamp(stage)
    if finished_at is None:
        raise ValueError("Explicit provider execution requires a finish timestamp")
    return finished_at


@dataclass(frozen=True, slots=True)
class NativeProviderExecution(Generic[NativeConclusionT]):
    """One native conclusion and its exact approved/observed provider boundary."""

    conclusion: NativeConclusionT
    call_spec: ProviderCallSpec
    call_record: ProviderCallRecord

    def _expected_output_artifact_ids(self) -> tuple[NonEmptyId, ...]:
        return (self.conclusion.conclusion_id,)

    def __post_init__(self) -> None:
        ensure_call_record_contract(self.call_spec, self.call_record)
        if self.call_record.status != "succeeded":
            raise ValueError("Deterministic native execution must succeed directly")
        if self.call_record.output_artifact_ids != self._expected_output_artifact_ids():
            raise ValueError("Native provider outputs differ from its exact artifacts")


@dataclass(frozen=True, slots=True)
class RacioNativeExecution(NativeProviderExecution[RacioNativeConclusion]):
    """Provider-bound deterministic Racio conclusion."""

    @property
    def reasoning_artifact(self) -> None:
        """Deterministic Racio has no external model-response evidence."""

        return None


@dataclass(frozen=True, slots=True)
class EmocioNativeExecution(NativeProviderExecution[EmocioNativeConclusion]):
    """Provider-bound Emocio conclusion plus its replayable native intermediates."""

    processing: EmocioProcessingResult
    runtime_config: EmocioProcessorRuntimeConfig | None = None
    processing_artifact: EmocioProcessingArtifact | None = None
    binary_snapshots: tuple[EmocioBinarySnapshot, ...] = ()

    def _expected_output_artifact_ids(self) -> tuple[NonEmptyId, ...]:
        outputs = (self.conclusion.conclusion_id,)
        if self.processing_artifact is not None:
            outputs = (*outputs, self.processing_artifact.result_id)
        return outputs

    def __post_init__(self) -> None:
        NativeProviderExecution.__post_init__(self)
        if self.conclusion != self.processing.native_conclusion:
            raise ValueError("Emocio execution conclusion differs from its processing result")
        configured = self.runtime_config is not None
        if configured != (self.processing_artifact is not None):
            raise ValueError(
                "Configured Emocio execution requires runtime and processing artifacts"
            )
        if not configured and self.binary_snapshots:
            raise ValueError(
                "Default structured Emocio execution cannot publish binary snapshots"
            )
        if self.processing_artifact is not None and (
            self.processing_artifact != EmocioProcessingArtifact.create(self.processing)
        ):
            raise ValueError(
                "Emocio processing artifact differs from the executed result"
            )

    @property
    def packet(self) -> EmocioInputPacket:
        return self.processing.packet

    @property
    def source_world_id(self) -> str:
        return self.processing.source_world_id

    @property
    def source_world_hash(self) -> str:
        return self.processing.source_world_hash

    @property
    def visual_state(self) -> EmocioVisualState:
        return self.processing.visual_state

    @property
    def rendered_images(self) -> tuple[ImageArtifact, ...]:
        return self.processing.rendered_images

    @property
    def renderer_warning(self) -> str | None:
        return self.processing.renderer_warning


@dataclass(frozen=True, slots=True)
class InstinktNativeExecution(NativeProviderExecution[InstinktNativeConclusion]):
    """Provider-bound Instinkt conclusion plus its typed simulation inputs/results."""

    packet: InstinktInputPacket
    source_body_state: BodyState
    option_effects: tuple[OptionBodyEffect, ...]
    associations: tuple[InstinktMemoryRecord, ...]
    processing: InstinktProcessResult

    def __post_init__(self) -> None:
        NativeProviderExecution.__post_init__(self)
        if self.conclusion != self.processing.conclusion:
            raise ValueError("Instinkt execution conclusion differs from its processing result")

    @property
    def rollouts(self) -> tuple[InstinktOptionRollout, ...]:
        return self.processing.rollouts

    @property
    def manifestation(self):
        return self.processing.manifestation

    @property
    def config(self) -> InstinktSimulationConfig:
        return self.processing.config


@dataclass(frozen=True, slots=True)
class DeterministicRacioNativeProvider:
    """Strict call-provenance adapter around the profile-blind B5 fixture policy."""

    processor: DeterministicRacioProvider = field(
        default_factory=DeterministicRacioProvider
    )

    @property
    def identity(self) -> ProviderIdentity:
        policy_hash = self.processor.policy.content_hash()
        return _identity(
            capability="racio_native",
            kind="text_reasoner",
            implementation="rei.racio.DeterministicRacioProvider",
            implementation_revision=f"b11-v1:{policy_hash[:16]}",
        )

    def required_input_artifact_ids(
        self,
        packet: RacioInputPacket,
    ) -> tuple[NonEmptyId, ...]:
        return (packet.packet_id,)

    def build_call_spec(self, packet: RacioInputPacket) -> ProviderCallSpec:
        return build_native_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=self.required_input_artifact_ids(packet),
        )

    def execute(
        self,
        packet: RacioInputPacket,
        *,
        call: ProviderCallSpec,
        clock: ExecutionClock | None = None,
        started_at: UtcTimestamp | None = None,
        finished_at: UtcTimestamp | None = None,
    ) -> RacioNativeExecution:
        observed_start = _execution_start(
            clock=clock,
            stage="racio_call_started",
            started_at=started_at,
            finished_at=finished_at,
        )
        _validate_call(
            identity=self.identity,
            call=call,
            request_id=packet.packet_id,
            expected_kind="text_reasoner",
            expected_inputs=self.required_input_artifact_ids(packet),
        )
        conclusion = self.processor.process(packet)
        observed_finish = _execution_finish(
            clock=clock,
            stage="racio_call_finished",
            finished_at=finished_at,
        )
        record = _successful_record(
            call=call,
            output_artifact_ids=(conclusion.conclusion_id,),
            started_at=observed_start,
            finished_at=observed_finish,
        )
        return RacioNativeExecution(
            conclusion=conclusion,
            call_spec=call,
            call_record=record,
        )


@dataclass(frozen=True, slots=True)
class DeterministicEmocioNativeProvider:
    """Provider-owned facade over one exact Emocio processor configuration."""

    processor: DeterministicEmocioProcessor = field(
        default_factory=DeterministicEmocioProcessor
    )
    publish_runtime_config: bool = False

    @property
    def _is_legacy_default(self) -> bool:
        processor = self.processor
        return (
            not self.publish_runtime_config
            and type(processor) is DeterministicEmocioProcessor
            and processor.renderer is None
            and type(processor.render_seed) is int
            and processor.render_seed == 0
            and processor.cognition_mode is None
            and processor.image_encoder is None
            and processor.visual_policy_config is None
            and processor.visual_influence_approval is None
            and processor.visual_influence_authority is None
            and type(processor.encoding_timeout_seconds) is float
            and processor.encoding_timeout_seconds == 30.0
        )

    @property
    def runtime_config(self) -> EmocioProcessorRuntimeConfig:
        return EmocioProcessorRuntimeConfig.from_processor(self.processor)

    @staticmethod
    def configured_identity(
        runtime_config: EmocioProcessorRuntimeConfig,
    ) -> ProviderIdentity:
        return _identity(
            capability="emocio_native",
            kind="visual_world_model",
            implementation="rei.emocio.process_emocio",
            implementation_revision=(
                "c4-runtime-v1:" + runtime_config.content_hash()
            ),
        )

    @property
    def identity(self) -> ProviderIdentity:
        if not self._is_legacy_default:
            return self.configured_identity(self.runtime_config)
        return _identity(
            capability="emocio_native",
            kind="visual_world_model",
            implementation="rei.emocio.process_emocio",
            implementation_revision="b11-v1",
        )

    def required_input_artifact_ids(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
        packet: EmocioInputPacket | None = None,
    ) -> tuple[NonEmptyId, ...]:
        active_packet = packet or build_emocio_packet(scene)
        active_packet.validate_against(scene)
        inputs = (
            scene.event_id,
            active_packet.packet_id,
            emocio_world_input_id(world),
        )
        if not self._is_legacy_default:
            inputs = (*inputs, *self.runtime_config.input_artifact_ids)
        return _canonical_artifact_ids(inputs)

    def configured_call_spec(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
        packet: EmocioInputPacket,
        *,
        runtime_config: EmocioProcessorRuntimeConfig,
    ) -> ProviderCallSpec:
        scene_count = 3 + len(scene.options)
        timeout_seconds = runtime_config.outer_timeout_seconds_for(
            scene_count=scene_count,
        )
        return build_provider_call_spec(
            identity=self.configured_identity(runtime_config),
            request_id=packet.packet_id,
            input_artifact_ids=_canonical_artifact_ids(
                (
                    scene.event_id,
                    packet.packet_id,
                    emocio_world_input_id(world),
                    *runtime_config.input_artifact_ids,
                )
            ),
            seed=runtime_config.render_seed,
            parameters=runtime_config.provider_parameters,
            timeout_seconds=timeout_seconds,
            fallback_policy=ProviderFallbackPolicy(
                mode="none",
                no_fallback_reason=_NO_FALLBACK_REASON,
            ),
        )

    def build_call_spec(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
        packet: EmocioInputPacket,
    ) -> ProviderCallSpec:
        if not self._is_legacy_default:
            runtime_config = self.runtime_config
            return self.configured_call_spec(
                scene,
                world,
                packet,
                runtime_config=runtime_config,
            )
        return build_native_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=self.required_input_artifact_ids(
                scene, world, packet
            ),
        )

    def execute(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
        *,
        packet: EmocioInputPacket | None = None,
        call: ProviderCallSpec,
        clock: ExecutionClock | None = None,
        started_at: UtcTimestamp | None = None,
        finished_at: UtcTimestamp | None = None,
    ) -> EmocioNativeExecution:
        observed_start = _execution_start(
            clock=clock,
            stage="emocio_call_started",
            started_at=started_at,
            finished_at=finished_at,
        )
        legacy_default = self._is_legacy_default
        monotonic_deadline = (
            None
            if legacy_default
            else time.monotonic() + call.timeout_seconds
        )
        active_packet = packet or build_emocio_packet(scene)
        active_packet.validate_against(scene)
        runtime_config: EmocioProcessorRuntimeConfig | None = None
        if legacy_default:
            _validate_call(
                identity=self.identity,
                call=call,
                request_id=active_packet.packet_id,
                expected_kind="visual_world_model",
                expected_inputs=self.required_input_artifact_ids(
                    scene, world, active_packet
                ),
            )
        else:
            # Re-freeze the live dependencies immediately before execution.
            # Any mutation since call approval therefore fails before a renderer
            # or encoder can be invoked.
            runtime_config = EmocioProcessorRuntimeConfig.from_processor(
                self.processor
            )
            expected_call = self.configured_call_spec(
                scene,
                world,
                active_packet,
                runtime_config=runtime_config,
            )
            ensure_call_contract(
                expected_call.provider,
                call,
                request_id=active_packet.packet_id,
                seed=runtime_config.render_seed,
                expected_kind="visual_world_model",
                required_input_artifact_ids=expected_call.input_artifact_ids,
            )
            if call != expected_call:
                raise ValueError(
                    "Configured Emocio call differs from its exact runtime contract"
                )
            assert monotonic_deadline is not None
            if time.monotonic() > monotonic_deadline:
                raise TimeoutError(
                    "Configured Emocio outer call exceeded its deadline"
                )
        processing = self.processor.process(
            scene,
            world,
            packet=active_packet,
        )
        if monotonic_deadline is not None and time.monotonic() > monotonic_deadline:
            raise TimeoutError("Configured Emocio outer call exceeded its deadline")
        if processing.packet != active_packet:
            raise ValueError("Emocio provider packet differs from its approved request")
        conclusion = processing.native_conclusion
        processing_artifact = (
            None
            if runtime_config is None
            else EmocioProcessingArtifact.create(processing)
        )
        binary_snapshots = (
            ()
            if runtime_config is None
            else binary_snapshots_from_processing(processing, self.processor)
        )
        if monotonic_deadline is not None and time.monotonic() > monotonic_deadline:
            raise TimeoutError("Configured Emocio outer call exceeded its deadline")
        observed_finish = _execution_finish(
            clock=clock,
            stage="emocio_call_finished",
            finished_at=finished_at,
        )
        output_artifact_ids = (conclusion.conclusion_id,)
        if processing_artifact is not None:
            output_artifact_ids = (
                *output_artifact_ids,
                processing_artifact.result_id,
            )
        record = _successful_record(
            call=call,
            output_artifact_ids=output_artifact_ids,
            started_at=observed_start,
            finished_at=observed_finish,
        )
        return EmocioNativeExecution(
            conclusion=conclusion,
            call_spec=call,
            call_record=record,
            processing=processing,
            runtime_config=runtime_config,
            processing_artifact=processing_artifact,
            binary_snapshots=binary_snapshots,
        )


@dataclass(frozen=True, slots=True)
class DeterministicInstinktNativeProvider:
    """Provider-free B8 adapter with explicit body/effect/config provenance."""

    @property
    def identity(self) -> ProviderIdentity:
        return _identity(
            capability="instinkt_native",
            kind="body_dynamics",
            implementation="rei.instinkt.process_instinkt",
            implementation_revision="b11-v1",
        )

    def required_input_artifact_ids(
        self,
        *,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        source_body_state: BodyState,
        option_effects: tuple[OptionBodyEffect, ...],
        config: InstinktSimulationConfig,
        associations: tuple[InstinktMemoryRecord, ...] = (),
    ) -> tuple[NonEmptyId, ...]:
        canonical_effects = tuple(
            sorted(option_effects, key=lambda item: item.option_id)
        )
        canonical_associations = tuple(
            sorted(associations, key=instinkt_memory_record_id)
        )
        inputs = (
                scene.event_id,
                packet.packet_id,
                source_body_state.body_state_id,
                config.config_id,
                *(effect.effect_id for effect in canonical_effects),
            )
        if canonical_associations:
            inputs = (
                *inputs,
                instinkt_memory_input_id(canonical_associations),
            )
        return _canonical_artifact_ids(inputs)

    def build_call_spec(
        self,
        *,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        source_body_state: BodyState,
        option_effects: tuple[OptionBodyEffect, ...],
        config: InstinktSimulationConfig,
        associations: tuple[InstinktMemoryRecord, ...] = (),
    ) -> ProviderCallSpec:
        return build_native_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=self.required_input_artifact_ids(
                scene=scene,
                packet=packet,
                source_body_state=source_body_state,
                option_effects=option_effects,
                config=config,
                associations=associations,
            ),
        )

    def execute(
        self,
        *,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        source_body_state: BodyState,
        option_effects: tuple[OptionBodyEffect, ...],
        call: ProviderCallSpec,
        config: InstinktSimulationConfig | None = None,
        associations: tuple[InstinktMemoryRecord, ...] = (),
        clock: ExecutionClock | None = None,
        started_at: UtcTimestamp | None = None,
        finished_at: UtcTimestamp | None = None,
    ) -> InstinktNativeExecution:
        observed_start = _execution_start(
            clock=clock,
            stage="instinkt_call_started",
            started_at=started_at,
            finished_at=finished_at,
        )
        active_config = config or InstinktSimulationConfig.create()
        canonical_effects = tuple(
            sorted(option_effects, key=lambda item: item.option_id)
        )
        canonical_associations = tuple(
            sorted(associations, key=instinkt_memory_record_id)
        )
        if len({instinkt_memory_record_id(item) for item in canonical_associations}) != len(
            canonical_associations
        ):
            raise ValueError("Instinkt memory record IDs must be unique")
        packet.validate_against(scene, source_body_state)
        for effect in canonical_effects:
            effect.validate_against(packet)
        _validate_call(
            identity=self.identity,
            call=call,
            request_id=packet.packet_id,
            expected_kind="body_dynamics",
            expected_inputs=self.required_input_artifact_ids(
                scene=scene,
                packet=packet,
                source_body_state=source_body_state,
                option_effects=canonical_effects,
                config=active_config,
                associations=canonical_associations,
            ),
        )
        memory = None
        if canonical_associations:
            memory = BoundedAssociativeMemory()
            for association in canonical_associations:
                memory.add(association)
        processing = process_instinkt(
            scene=scene,
            packet=packet,
            source_body_state=source_body_state,
            option_effects=canonical_effects,
            config=active_config,
            memory=memory,
        )
        conclusion = processing.conclusion
        observed_finish = _execution_finish(
            clock=clock,
            stage="instinkt_call_finished",
            finished_at=finished_at,
        )
        record = _successful_record(
            call=call,
            output_artifact_ids=(conclusion.conclusion_id,),
            started_at=observed_start,
            finished_at=observed_finish,
        )
        return InstinktNativeExecution(
            conclusion=conclusion,
            call_spec=call,
            call_record=record,
            packet=packet,
            source_body_state=source_body_state,
            option_effects=canonical_effects,
            associations=canonical_associations,
            processing=processing,
        )


@dataclass(frozen=True, slots=True)
class DeterministicNativeProviders:
    """Canonical provider-free R/E/I provider set used by deterministic runs."""

    racio: DeterministicRacioNativeProvider = field(
        default_factory=DeterministicRacioNativeProvider
    )
    emocio: DeterministicEmocioNativeProvider = field(
        default_factory=DeterministicEmocioNativeProvider
    )
    instinkt: DeterministicInstinktNativeProvider = field(
        default_factory=DeterministicInstinktNativeProvider
    )

    @property
    def identities(self) -> tuple[ProviderIdentity, ...]:
        return (self.racio.identity, self.emocio.identity, self.instinkt.identity)


def build_deterministic_native_providers(
    *,
    emocio_processor: DeterministicEmocioProcessor | None = None,
) -> DeterministicNativeProviders:
    """Return the deterministic provider set with an optional Emocio runtime."""

    return DeterministicNativeProviders(
        emocio=(
            DeterministicEmocioNativeProvider()
            if emocio_processor is None
            else DeterministicEmocioNativeProvider(
                processor=emocio_processor,
                publish_runtime_config=True,
            )
        )
    )


__all__ = [
    "DeterministicEmocioNativeProvider",
    "DeterministicInstinktNativeProvider",
    "DeterministicNativeProviders",
    "DeterministicRacioNativeProvider",
    "EmocioNativeExecution",
    "InstinktNativeExecution",
    "NativeProviderExecution",
    "RacioNativeExecution",
    "build_deterministic_native_providers",
    "build_native_call_spec",
    "emocio_world_input_id",
    "instinkt_association_input_id",
    "instinkt_memory_input_id",
]
