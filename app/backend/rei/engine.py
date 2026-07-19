"""B11 orchestration of one complete native REI cycle.

The engine is deliberately an assembler and coordinator.  Character authority
is applied only after the three profile-blind native conclusions have finished,
and the run manifest is persisted last so an interrupted tree can never look
complete.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, Mapping

from pydantic import Field, ValidationError, model_validator

from .communication.interpreter import DeterministicRacioInterpreter, RacioInterpreter
from .communication.manifestations import build_emocio_manifestation
from .communication.processor import CommunicationProcessResult, process_communication
from .communication.structured_interpreter import StructuredRacioInterpretationResult
from .communication.text_shadow import (
    RacioInterpreterRuntimeMode,
    ShadowRacioInterpretationExecution,
    ShadowRacioInterpreter,
    execute_racio_text_shadow,
)
from .conscious.committer import DeterministicRacioCommitter, RacioCommitter
from .conscious.narrator import DeterministicRacioNarrator, RacioNarrator
from .diagnostics import InvariantReport, build_cycle_invariant_report, render_diagnostic_report
from .ego.composition import derive_composition_snapshot
from .ego.measure import build_ego_measure
from .ego.projections import EgoModalityProjections, derive_modality_projections
from .ego.trace_store import FileEgoTraceStore
from .ego.world_updates import (
    EmocioLongitudinalVisualSignal,
    InstinktLongitudinalBodySignal,
)
from .emocio.packets import build_emocio_packet
from .emocio.processor import DeterministicEmocioProcessor
from .emocio.runtime import (
    EmocioBinarySnapshot,
    EmocioProcessingArtifact,
    EmocioProcessorRuntimeConfig,
    validate_binary_snapshots_against_processing,
    validate_processing_runtime_closure,
)
from .governance.behavior import BehaviorResolver, DeterministicBehaviorResolver
from .governance.profiles import derive_effective_authority
from .governance.resolver import resolve_governance
from .ids import canonical_json_bytes, content_id, sha256_hex, utc_now
from .instinkt.association_memory import BoundedAssociativeMemory
from .instinkt.effect_compiler import compile_prediction_to_option_body_effect
from .instinkt.effect_mapper import (
    EmbodiedCueInterpreter,
    ModelBackedEffectInferenceDisabledError,
    ModelBackedEmbodiedCueInterpreterStub,
    RuleBasedEmbodiedCueInterpreter,
)
from .instinkt.packets import InstinktEffectSpec, bind_instinkt_effects, build_instinkt_packet
from .instinkt.processor import process_instinkt
from .models.character import CharacterAuthority, EffectiveAuthority, FunctionalOverride
from .models.common import (
    CommitDigest,
    FrozenArtifactModel,
    FrozenModel,
    NonEmptyId,
    NonEmptyText,
    UtcTimestamp,
)
from .models.communication import AcceptanceState, EmocioManifestation, InstinktManifestation
from .models.conscious import (
    BehaviorResultant,
    ConsciousDecision,
    ConsciousInterpretationInput,
    ConsciousMandateView,
    RacioSelfNarrative,
)
from .models.ego import (
    EgoCompositionSnapshot,
    EgoMeasure,
    EgoTrace,
    InstinktProjection,
    OutcomeRecord,
)
from .models.emocio import (
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioVisualState,
    EmocioWorld,
    ImageArtifact,
)
from .models.governance import GovernanceResolution, PairNegotiationRound, TaskDelegation
from .models.instinkt import (
    INSTINKT_CUE_LANES,
    MAX_INSTINKT_ASSOCIATION_RECORDS,
    MAX_INSTINKT_CUE_BINDINGS,
    MAX_INSTINKT_CUES_PER_LANE,
    MAX_INSTINKT_CUE_TEXT_CHARS,
    MAX_INSTINKT_EVIDENCE_IDS,
    MAX_INSTINKT_TOTAL_CUES,
    BodyState,
    InstinktAssociation,
    InstinktCueEvidenceBinding,
    InstinktInputPacket,
    InstinktMemoryRecord,
    InstinktProjectionObservation,
    InstinktSimulationConfig,
    InstinktWorld,
    instinkt_association_content_id,
    instinkt_memory_record_id,
    instinkt_projection_memory_token,
)
from .models.instinkt_effects import (
    EffectSource,
    InstinktEffectRuleSet,
    OptionBodyEffectCompilation,
    OptionBodyEffectPrediction,
)
from .models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderIdentity,
    ensure_call_record_contract,
)
from .models.racio import NumericCue, RacioConsequence, RacioInputPacket, RacioWorld
from .models.run import (
    ArtifactHashRecord,
    EmocioExecutionManifestRecord,
    EmocioMaterializedArtifactRecord,
    NativeBundleAssemblyRecord,
    NativeMindBundle,
    RunArtifactRecord,
    RunManifest,
    SeedRecord,
)
from .models.scene import SceneEvent
from .persistence import ArtifactExistsError, FileArtifactStore, StoredArtifact
from .providers.deterministic import (
    DeterministicEmocioNativeProvider,
    build_deterministic_native_providers,
)
from .providers.native import (
    EmocioNativeExecution,
    ExecutionClock,
    InstinktNativeExecution,
    NativeProviderSet,
    RacioNativeExecution,
    SystemExecutionClock,
)
from .providers.protocols import ArtifactStore, EgoTraceStore
from .racio.packets import build_racio_packet


class ReiNativeCycleRequest(FrozenModel):
    """Explicit, replayable inputs to one longitudinal B11 cycle."""

    schema_version: Literal["rei-native-cycle-request-v1"] = (
        "rei-native-cycle-request-v1"
    )
    run_id: NonEmptyId
    ego_id: NonEmptyId
    source_commit: CommitDigest
    canon_version: NonEmptyText
    mode: Literal["person_longitudinal"] = "person_longitudinal"
    scene: SceneEvent
    racio_world: RacioWorld
    emocio_world: EmocioWorld
    body_state: BodyState
    character: CharacterAuthority
    acceptance_state: AcceptanceState
    instinkt_effect_source: EffectSource = "manual_fixture"
    instinkt_effect_specs: tuple[InstinktEffectSpec, ...] = ()
    instinkt_world: InstinktWorld = Field(default_factory=InstinktWorld.create)
    instinkt_associations: tuple[InstinktAssociation, ...] = ()
    instinkt_config: InstinktSimulationConfig = Field(
        default_factory=InstinktSimulationConfig.create
    )
    symbolic_and_language_cues: tuple[str, ...] | None = None
    numeric_cues: tuple[NumericCue, ...] = ()
    time_cues: tuple[str, ...] = ()
    explicit_rules: tuple[str, ...] = ()
    explicit_consequences: tuple[RacioConsequence, ...] = ()
    instinkt_physical_cues: tuple[str, ...] = ()
    instinkt_uncertainty_cues: tuple[str, ...] = ()
    instinkt_trust_cues: tuple[str, ...] = ()
    instinkt_boundary_cues: tuple[str, ...] = ()
    instinkt_attachment_cues: tuple[str, ...] = ()
    instinkt_scarcity_cues: tuple[str, ...] = ()
    instinkt_escape_cues: tuple[str, ...] = ()
    instinkt_explicit_body_cues: tuple[str, ...] = ()
    instinkt_evidence_ids: tuple[NonEmptyId, ...] = ()
    instinkt_cue_evidence_bindings: tuple[InstinktCueEvidenceBinding, ...] = ()
    functional_override: FunctionalOverride | None = None
    delegation: TaskDelegation | None = None
    negotiation_rounds: tuple[PairNegotiationRound, ...] = ()
    outcome: OutcomeRecord | None = None
    historical_bundles: tuple[NativeMindBundle, ...] = Field(
        default=(), max_length=30
    )
    historical_emocio_signals: tuple[EmocioLongitudinalVisualSignal, ...] = Field(
        default=(), max_length=30
    )
    historical_instinkt_signals: tuple[InstinktLongitudinalBodySignal, ...] = Field(
        default=(), max_length=30
    )
    started_at: UtcTimestamp = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_explicit_scope(self) -> ReiNativeCycleRequest:
        if self.outcome is not None and self.outcome.event_id != self.scene.event_id:
            raise ValueError("Explicit outcome must refer to the current SceneEvent")
        if len(self.scene.options) > self.instinkt_config.max_options:
            raise ValueError(
                "Scene options exceed the configured Instinkt simulation limit"
            )
        request_cue_lanes = {
            "physical_cues": self.instinkt_physical_cues,
            "uncertainty_cues": self.instinkt_uncertainty_cues,
            "trust_cues": self.instinkt_trust_cues,
            "boundary_cues": self.instinkt_boundary_cues,
            "attachment_cues": self.instinkt_attachment_cues,
            "scarcity_cues": self.instinkt_scarcity_cues,
            "escape_cues": self.instinkt_escape_cues,
            "explicit_body_cues": self.instinkt_explicit_body_cues,
        }
        if set(request_cue_lanes) != set(INSTINKT_CUE_LANES):
            raise ValueError("Internal Instinkt cue-lane contract is incomplete")
        lane_sizes = tuple(len(values) for values in request_cue_lanes.values())
        if any(size > MAX_INSTINKT_CUES_PER_LANE for size in lane_sizes):
            raise ValueError("Instinkt cue lane exceeds its bounded input limit")
        if sum(lane_sizes) > MAX_INSTINKT_TOTAL_CUES:
            raise ValueError("Instinkt request exceeds its total cue limit")
        if any(
            len(cue) > MAX_INSTINKT_CUE_TEXT_CHARS
            for values in request_cue_lanes.values()
            for cue in values
        ):
            raise ValueError("Instinkt cue text exceeds its bounded input limit")
        if len(self.instinkt_evidence_ids) > MAX_INSTINKT_EVIDENCE_IDS:
            raise ValueError("Instinkt request exceeds its evidence-reference limit")
        if len(self.instinkt_cue_evidence_bindings) > MAX_INSTINKT_CUE_BINDINGS:
            raise ValueError("Instinkt request exceeds its cue-binding limit")
        option_ids = {option.option_id for option in self.scene.options}
        if self.instinkt_effect_source == "manual_fixture":
            if {item.option_id for item in self.instinkt_effect_specs} != option_ids:
                raise ValueError("Manual Instinkt effect specs must cover the SceneEvent options")
        elif self.instinkt_effect_specs:
            raise ValueError(
                "Automatic Instinkt effect modes cannot consume manual effect specs"
            )
        association_ids = tuple(item.association_id for item in self.instinkt_associations)
        if len(association_ids) > MAX_INSTINKT_ASSOCIATION_RECORDS:
            raise ValueError("Instinkt request exceeds its association-record limit")
        if len(set(association_ids)) != len(association_ids):
            raise ValueError("Instinkt association IDs must be unique")
        world_association_ids = self.instinkt_world.associations
        if self.instinkt_effect_source == "manual_fixture":
            if not set(association_ids).issubset(world_association_ids):
                raise ValueError(
                    "Typed Instinkt associations must be indexed by InstinktWorld"
                )
        else:
            if (
                len(world_association_ids) > MAX_INSTINKT_ASSOCIATION_RECORDS
                or len(set(world_association_ids)) != len(world_association_ids)
            ):
                raise ValueError(
                    "Automatic Instinkt worlds exceed the bounded unique "
                    "association index"
                )
            if set(association_ids) != set(world_association_ids):
                raise ValueError(
                    "Automatic Instinkt association index requires exact "
                    "materialized record closure"
                )
            if any(
                association.association_id.startswith("instinkt_association_")
                and association.association_id
                != instinkt_association_content_id(association)
                for association in self.instinkt_associations
            ):
                raise ValueError(
                    "Automatic content-addressed Instinkt association differs "
                    "from its canonical payload"
                )
        bundle_ids = tuple(item.bundle_id for item in self.historical_bundles)
        if len(set(bundle_ids)) != len(bundle_ids):
            raise ValueError("Historical native bundle IDs must be unique")
        emocio_signal_ids = tuple(
            item.signal_id for item in self.historical_emocio_signals
        )
        emocio_measure_ids = tuple(
            item.source_measure_id for item in self.historical_emocio_signals
        )
        if (
            len(set(emocio_signal_ids)) != len(emocio_signal_ids)
            or len(set(emocio_measure_ids)) != len(emocio_measure_ids)
        ):
            raise ValueError(
                "Historical Emocio signals must be unique by signal and measure"
            )
        instinkt_signal_ids = tuple(
            item.signal_id for item in self.historical_instinkt_signals
        )
        instinkt_measure_ids = tuple(
            item.source_measure_id for item in self.historical_instinkt_signals
        )
        if (
            len(set(instinkt_signal_ids)) != len(instinkt_signal_ids)
            or len(set(instinkt_measure_ids)) != len(instinkt_measure_ids)
        ):
            raise ValueError(
                "Historical Instinkt signals must be unique by signal and measure"
            )
        total_image_bytes = sum(
            item.image_storage.size_bytes
            for item in self.historical_emocio_signals
        )
        total_vector_bytes = sum(
            item.embedding_storage.size_bytes
            for item in self.historical_emocio_signals
        )
        if total_image_bytes > 67_108_864 or total_vector_bytes > 16_777_216:
            raise ValueError(
                "Historical Emocio byte payloads exceed the bounded request limit"
            )
        return self


@dataclass(frozen=True, slots=True)
class ReiNativeCycleResult:
    """Complete typed result and persistence receipt for one B11 cycle."""

    request: ReiNativeCycleRequest
    prior_trace: EgoTrace
    prior_snapshot: EgoCompositionSnapshot | None
    prior_projections: EgoModalityProjections | None
    racio_world_input: RacioWorld
    emocio_world_input: EmocioWorld
    racio_packet: RacioInputPacket
    emocio_packet: EmocioInputPacket
    instinkt_packet: InstinktInputPacket
    instinkt_world_input: InstinktWorld
    instinkt_effect_source: EffectSource
    instinkt_effect_ruleset: InstinktEffectRuleSet | None
    instinkt_effect_predictions: tuple[OptionBodyEffectPrediction, ...]
    instinkt_effect_compilations: tuple[OptionBodyEffectCompilation, ...]
    racio_execution: RacioNativeExecution
    emocio_execution: EmocioNativeExecution
    instinkt_execution: InstinktNativeExecution
    native_bundle: NativeMindBundle
    native_assembly: NativeBundleAssemblyRecord
    effective_authority: EffectiveAuthority
    governance: GovernanceResolution
    emocio_manifestation: EmocioManifestation
    instinkt_manifestation: InstinktManifestation
    emocio_communication: CommunicationProcessResult
    instinkt_communication: CommunicationProcessResult
    shadow_communications: tuple[ShadowRacioInterpretationExecution, ...]
    mandate_view: ConsciousMandateView
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...]
    conscious_decision: ConsciousDecision
    behavior_resultant: BehaviorResultant
    narrative: RacioSelfNarrative
    ego_measure: EgoMeasure
    ego_trace: EgoTrace
    composition_snapshot: EgoCompositionSnapshot
    projections: EgoModalityProjections
    manifest: RunManifest
    invariants: InvariantReport
    stored_artifacts: tuple[StoredArtifact, ...]


def _historical_context(
    *,
    trace: EgoTrace,
    bundles: tuple[NativeMindBundle, ...],
    emocio_signals: tuple[EmocioLongitudinalVisualSignal, ...],
    instinkt_signals: tuple[InstinktLongitudinalBodySignal, ...],
    artifact_store: ArtifactStore,
    current_body_state: BodyState,
    current_instinkt_world: InstinktWorld,
    structural_character: CharacterAuthority,
) -> tuple[
    dict[str, NativeMindBundle],
    EgoCompositionSnapshot | None,
    EgoModalityProjections | None,
]:
    by_id = {item.bundle_id: item for item in bundles}
    if any(
        measure.structural_character != structural_character
        for measure in trace.measures
    ):
        raise ValueError(
            "A longitudinal EgoTrace cannot switch structural CharacterAuthority"
        )
    expected_ids = {measure.native_bundle_id for measure in trace.measures}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        unexpected = sorted(set(by_id) - expected_ids)
        raise ValueError(
            "Historical bundles must exactly cover the loaded EgoTrace "
            f"(missing={missing}, unexpected={unexpected})"
        )
    for measure in trace.measures:
        bundle = by_id[measure.native_bundle_id]
        if (
            measure.native_bundle_hash != bundle.immutable_hash
            or measure.event_id != bundle.scene_id
        ):
            raise ValueError(
                "Historical bundle identity, hash and event must exactly match EgoTrace"
            )
    for signal in emocio_signals:
        signal.validate_stored_bytes(artifact_store)
    measured_signals = tuple(
        signal
        for signal in instinkt_signals
        if signal.measured_outcome_update is not None
    )
    if measured_signals:
        measure_order = {
            measure.measure_id: index for index, measure in enumerate(trace.measures)
        }
        latest = max(
            measured_signals,
            key=lambda item: measure_order.get(item.source_measure_id, -1),
        )
        measured = latest.measured_outcome_update
        if measured is None:  # pragma: no cover - narrowed above
            raise AssertionError("Measured signal lost its outcome update")
        if (
            current_body_state != measured.body_after
            or current_instinkt_world != measured.world_after
        ):
            raise ValueError(
                "The next native cycle must continue from the latest measured "
                "Instinkt body/world update"
            )
    if not trace.measures:
        if emocio_signals or instinkt_signals:
            raise ValueError("Historical modality signals require a prior EgoTrace")
        return by_id, None, None
    return (
        by_id,
        derive_composition_snapshot(trace),
        derive_modality_projections(
            trace,
            by_id,
            emocio_history=emocio_signals,
            instinkt_history=instinkt_signals,
        ),
    )


def _stable_union(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group))


def _racio_world_with_projection(
    world: RacioWorld,
    projections: EgoModalityProjections | None,
) -> RacioWorld:
    if projections is None:
        return world
    projection = projections.racio
    return world.model_copy(
        update={
            "explicit_beliefs": _stable_union(
                world.explicit_beliefs, projection.statements
            ),
            "facts": _stable_union(world.facts, projection.facts),
            "rules": _stable_union(world.rules, projection.causal_links),
            "timelines": _stable_union(world.timelines, projection.chronology),
            "commitments": _stable_union(
                world.commitments, projection.commitments
            ),
        }
    )


def _emocio_world_with_projection(
    world: EmocioWorld,
    projections: EgoModalityProjections | None,
) -> EmocioWorld:
    if projections is None:
        return world
    projection = projections.emocio
    return world.model_copy(
        update={
            "visual_memories": _stable_union(
                world.visual_memories,
                projection.recurring_scenes,
                projection.image_artifact_ids,
                projection.embedding_feature_refs,
            ),
            "desired_scenes": _stable_union(
                world.desired_scenes,
                projection.desire_motifs,
                projection.success_motifs,
                projection.belonging_motifs,
            ),
            "broken_scenes": _stable_union(
                world.broken_scenes, projection.rupture_motifs
            ),
            "social_identity_motifs": _stable_union(
                world.social_identity_motifs,
                projection.status_patterns,
                projection.belonging_motifs,
            ),
            "attraction_patterns": _stable_union(
                world.attraction_patterns,
                projection.desire_motifs,
                projection.success_motifs,
            ),
        }
    )


def _instinkt_history_inputs(
    *,
    projection: InstinktProjection | None,
    specs: tuple[InstinktEffectSpec, ...],
    records: tuple[InstinktMemoryRecord, ...] = (),
) -> tuple[tuple[InstinktEffectSpec, ...], tuple[InstinktMemoryRecord, ...]]:
    """Map typed Ego history into exact-token B8 associative memory.

    The policy performs no prose classification. Every typed projection token
    becomes an observation-only memory record whose strength is derived
    only from its cited measure count. Each observation also carries the exact
    projection ID/hash query token exposed by the Instinkt packet; manual
    fixtures retain their typed-token queries while automatic effects use that
    non-semantic lineage token. Projection observations never carry
    experienced-loss semantics: that remains exclusive to a real
    ``InstinktAssociation`` with a concrete body state and outcome. This makes
    history visible to B8 without privileging an option, fabricating an
    outcome, or importing character authority.
    """

    record_ids = tuple(instinkt_memory_record_id(item) for item in records)
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("Instinkt history record IDs must be unique")
    if projection is None:
        return specs, tuple(sorted(records, key=instinkt_memory_record_id))
    typed_groups = (
        ("body_consequence", projection.body_consequences),
        ("danger", projection.dangers),
        ("loss", projection.losses),
        ("trust", projection.trust_patterns),
        ("attachment", projection.attachment_patterns),
        ("boundary", projection.boundary_patterns),
        ("scarcity", projection.scarcity_patterns),
        ("recovery", projection.recovery_patterns),
    )
    typed_signals = tuple(
        (kind, signal, f"ego_projection:{kind}:{signal}")
        for kind, signals in typed_groups
        for signal in signals
    )
    if not typed_signals:
        return specs, tuple(sorted(records, key=instinkt_memory_record_id))
    evidence_by_text = {
        claim.text: tuple(sorted(claim.evidence_measure_ids))
        for claim in projection.sourced_claims
    }
    recovery_by_text = {
        (
            "predicted_recoverability:"
            f"{reference.source_signal_id}:"
            f"{reference.predicted_recoverability:.12g}"
        ): reference.predicted_recoverability
        for reference in projection.body_history
    }
    observations: list[InstinktProjectionObservation] = []
    projection_memory_token = instinkt_projection_memory_token(
        projection.projection_id,
        projection.projection_hash,
    )
    for kind, signal, cue_token in typed_signals:
        evidence_ids = evidence_by_text.get(
            signal,
            tuple(sorted(projection.evidence_measure_ids)),
        )
        predicted_recoverability = recovery_by_text.get(signal)
        strength = min(
            1.0,
            max(
                0.05,
                (
                    predicted_recoverability
                    if predicted_recoverability is not None
                    else len(evidence_ids) / 4.0
                ),
            ),
        )
        base = {
            "schema_version": "rei-native-instinkt-projection-observation-v1",
            "source_projection_id": projection.projection_id,
            "source_projection_hash": projection.projection_hash,
            "observation_kind": kind,
            "observation": signal,
            "evidence_measure_ids": evidence_ids,
            "cue_signature": tuple(sorted((cue_token, projection_memory_token))),
            "felt_intensity": strength,
            "protected_target": f"ego_history_{kind}",
            "decay": 0.0,
        }
        if predicted_recoverability is not None:
            base["predicted_recoverability"] = predicted_recoverability
        observations.append(
            InstinktProjectionObservation(
                observation_id=content_id(
                    "instinkt_projection_observation", base
                ),
                **base,
            )
        )
    active_specs = tuple(
        spec.model_copy(
            update={
                "association_cue_tokens": _stable_union(
                    spec.association_cue_tokens,
                    tuple(item[2] for item in typed_signals),
                )
            }
        )
        for spec in specs
    )
    combined_records = (*records, *observations)
    combined_ids = tuple(instinkt_memory_record_id(item) for item in combined_records)
    if len(set(combined_ids)) != len(combined_ids):
        raise ValueError("Instinkt history records collide with projection observations")
    return active_specs, tuple(
        sorted(combined_records, key=instinkt_memory_record_id)
    )


def _native_assembly(
    *,
    bundle: NativeMindBundle,
    racio: RacioNativeExecution,
    emocio: EmocioNativeExecution,
    instinkt: InstinktNativeExecution,
    started_at: UtcTimestamp,
    finished_at: UtcTimestamp,
) -> NativeBundleAssemblyRecord:
    base = {
        "schema_version": "rei-native-bundle-assembly-v1",
        "implementation": "rei.engine.ReiNativeEngine",
        "implementation_revision": "b11-v1",
        "racio_conclusion_id": racio.conclusion.conclusion_id,
        "emocio_conclusion_id": emocio.conclusion.conclusion_id,
        "instinkt_conclusion_id": instinkt.conclusion.conclusion_id,
        "bundle_id": bundle.bundle_id,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    return NativeBundleAssemblyRecord(
        assembly_id=content_id("native_assembly", base),
        **base,
    )


def _native_hashes(bundle: NativeMindBundle) -> tuple[ArtifactHashRecord, ...]:
    return (
        ArtifactHashRecord(
            artifact_id=bundle.bundle_id,
            role="native_bundle",
            sha256=bundle.immutable_hash,
        ),
        ArtifactHashRecord(
            artifact_id=bundle.racio.conclusion_id,
            role="racio_native",
            sha256=bundle.racio.content_hash(),
        ),
        ArtifactHashRecord(
            artifact_id=bundle.emocio.conclusion_id,
            role="emocio_native",
            sha256=bundle.emocio.content_hash(),
        ),
        ArtifactHashRecord(
            artifact_id=bundle.instinkt.conclusion_id,
            role="instinkt_native",
            sha256=bundle.instinkt.content_hash(),
        ),
    )


def _seed_records(
    calls: tuple[ProviderCallRecord, ...],
) -> tuple[SeedRecord, ...]:
    records: list[SeedRecord] = []
    for call in calls:
        if call.seed is not None:
            records.append(
                SeedRecord(
                    call_id=call.call_id,
                    attempt="primary",
                    provider_id=call.provider.provider_id,
                    seed=call.seed,
                )
            )
        if (
            call.fallback is not None
            and call.fallback.status != "skipped"
            and call.fallback.seed is not None
        ):
            records.append(
                SeedRecord(
                    call_id=call.call_id,
                    attempt="fallback",
                    provider_id=call.fallback.provider.provider_id,
                    seed=call.fallback.seed,
                )
            )
    return tuple(
        sorted(records, key=lambda item: (item.call_id, item.attempt))
    )


def _validate_preapproved_native_call(
    *,
    spec: ProviderCallSpec,
    identity: ProviderIdentity,
    request_id: str,
    expected_inputs: tuple[str, ...],
) -> None:
    canonical_inputs = tuple(sorted(expected_inputs))
    if (
        spec.provider != identity
        or spec.request_id != request_id
        or spec.input_artifact_ids != canonical_inputs
    ):
        raise ValueError(
            "Native provider call spec differs from its exact identity, request or "
            "profile-blind input scope"
        )


def _validated_racio_reasoning_artifact(
    execution: RacioNativeExecution,
) -> FrozenArtifactModel | None:
    """Close an optional model-response artifact before bundle assembly."""

    artifact = execution.reasoning_artifact
    expected_id = execution.conclusion.reasoning_provider_result_id
    expected_hash = execution.conclusion.reasoning_provider_result_hash
    if expected_id is None:
        if artifact is not None or expected_hash is not None:
            raise ValueError("Racio reasoning artifact lineage is only partially present")
        return None
    if expected_hash is None or not isinstance(artifact, FrozenArtifactModel):
        raise ValueError("Racio conclusion references missing reasoning evidence")
    if (
        getattr(artifact, "result_id", None) != expected_id
        or artifact.content_hash() != expected_hash
    ):
        raise ValueError("Racio reasoning evidence differs from conclusion lineage")
    if expected_id not in execution.call_record.output_artifact_ids:
        raise ValueError("Racio reasoning evidence is not a recorded provider output")
    return artifact


def _c3_response_evidence(
    result: StructuredRacioInterpretationResult,
) -> FrozenArtifactModel:
    evidence = getattr(result.execution, "response_evidence", None)
    if evidence is None:
        evidence = getattr(result.execution, "reasoning_artifact", None)
    if not isinstance(evidence, FrozenArtifactModel):
        raise ValueError("C3 interpreter execution is missing hashed response evidence")
    return evidence


def _validated_c3_results(
    communications: tuple[CommunicationProcessResult, CommunicationProcessResult],
) -> tuple[StructuredRacioInterpretationResult, ...]:
    """Close both optional C3 executions without invoking either provider again."""

    raw_results = tuple(item.c3_result for item in communications)
    if all(result is None for result in raw_results):
        return ()
    if any(result is None for result in raw_results):
        raise ValueError("C3 communication evidence must be present for both E and I")

    results: list[StructuredRacioInterpretationResult] = []
    for expected_mind, communication, candidate in zip(
        ("E", "I"),
        communications,
        raw_results,
        strict=True,
    ):
        assert candidate is not None
        packet = candidate.access.packet
        audit = candidate.access.audit
        execution = candidate.execution
        call_spec = execution.call_spec
        call_record = execution.call_record
        interpretation = candidate.interpretation
        evidence = _c3_response_evidence(candidate)
        evidence_result_id = getattr(evidence, "result_id", None)

        if candidate.interpretation != communication.interpretation:
            raise ValueError("C3 evidence differs from the published interpretation")
        if (
            packet.source_mind != expected_mind
            or communication.request.source_mind != expected_mind
            or interpretation.source_mind != expected_mind
        ):
            raise ValueError("C3 communication results must preserve E then I ordering")
        if (
            audit.source_request_id != communication.request.request_id
            or audit.source_request_hash != communication.request.content_hash()
            or audit.packet_id != packet.packet_id
            or audit.packet_hash != packet.content_hash()
        ):
            raise ValueError("C3 access audit differs from its request or packet")
        if (
            call_spec.request_id != packet.packet_id
            or call_spec.input_artifact_ids != (packet.packet_id,)
        ):
            raise ValueError("C3 call spec must consume only its access packet")
        if call_spec.fallback_policy.mode != "none":
            raise ValueError("C3 call spec must use an explicit no-fallback policy")
        ensure_call_record_contract(call_spec, call_record)
        if (
            call_record.status != "succeeded"
            or call_record.primary_status != "succeeded"
            or call_record.fallback is not None
            or not isinstance(evidence_result_id, str)
            or call_record.output_artifact_ids != (evidence_result_id,)
        ):
            raise ValueError("C3 call record must close one direct response artifact")
        if (
            getattr(evidence, "packet_id", None) != packet.packet_id
            or getattr(evidence, "packet_hash", None) != packet.content_hash()
            or getattr(evidence, "call_id", None) != call_spec.call_id
            or getattr(evidence, "call_spec_hash", None) != call_spec.content_hash()
            or getattr(evidence, "provider_id", None)
            != call_spec.provider.provider_id
        ):
            raise ValueError("C3 response evidence has inconsistent packet/call lineage")
        evidence_output = getattr(evidence, "output", None)
        evidence_output_hash = getattr(evidence, "structured_output_hash", None)
        if evidence_output is not None:
            if evidence_output != execution.output:
                raise ValueError("C3 response evidence differs from structured output")
        elif evidence_output_hash != sha256_hex(execution.output):
            raise ValueError("C3 response evidence does not bind the structured output")
        if (
            interpretation.language != packet.language
            or interpretation.conscious_access_packet_id != packet.packet_id
            or interpretation.conscious_access_packet_hash != packet.content_hash()
            or interpretation.interpreter_id != call_spec.provider.provider_id
            or interpretation.interpreter_revision
            != call_spec.provider.implementation_revision
            or interpretation.interpreter_result_id != evidence_result_id
            or interpretation.interpreter_result_hash != evidence.content_hash()
        ):
            raise ValueError("C3 interpretation has incomplete provider evidence lineage")
        results.append(candidate)
    return tuple(results)


def _unique_provider_identities(
    identities: tuple[ProviderIdentity, ...],
) -> tuple[ProviderIdentity, ...]:
    """Preserve declaration order while rejecting identity-ID collisions."""

    by_id: dict[str, ProviderIdentity] = {}
    ordered: list[ProviderIdentity] = []
    for identity in identities:
        previous = by_id.get(identity.provider_id)
        if previous is None:
            by_id[identity.provider_id] = identity
            ordered.append(identity)
        elif previous != identity:
            raise ValueError("Provider ID maps to conflicting identities")
    return tuple(ordered)


def _provider_identities_from_calls(
    specs: tuple[ProviderCallSpec, ...],
    records: tuple[ProviderCallRecord, ...],
) -> tuple[ProviderIdentity, ...]:
    """Collect primary and fallback identities from an exact call ledger."""

    identities: list[ProviderIdentity] = []
    for spec in specs:
        identities.append(spec.provider)
        if spec.fallback_policy.plan is not None:
            identities.append(spec.fallback_policy.plan.provider)
    for record in records:
        identities.append(record.provider)
        if record.fallback is not None:
            identities.append(record.fallback.provider)
    return _unique_provider_identities(tuple(identities))


def _decisive_body_after(execution: InstinktNativeExecution) -> BodyState | None:
    decisive_id = execution.conclusion.decisive_rollout_id
    if decisive_id is None:
        return None
    matches = tuple(
        rollout for rollout in execution.rollouts if rollout.rollout_id == decisive_id
    )
    if len(matches) != 1:
        raise ValueError("Instinkt decisive rollout must resolve to exactly one trajectory")
    return matches[0].trajectory[-1]


@dataclass(slots=True)
class ReiNativeEngine:
    """Coordinate providers, governance, consciousness, Ego and persistence."""

    artifact_store: ArtifactStore
    ego_trace_store: EgoTraceStore
    providers: NativeProviderSet = field(
        default_factory=build_deterministic_native_providers
    )
    clock: ExecutionClock = field(default_factory=SystemExecutionClock)
    interpreter: RacioInterpreter = field(default_factory=DeterministicRacioInterpreter)
    committer: RacioCommitter = field(default_factory=DeterministicRacioCommitter)
    behavior_resolver: BehaviorResolver = field(
        default_factory=DeterministicBehaviorResolver
    )
    narrator: RacioNarrator = field(default_factory=DeterministicRacioNarrator)
    embodied_cue_interpreter: EmbodiedCueInterpreter | None = None
    racio_interpreter_mode: RacioInterpreterRuntimeMode = "deterministic"
    shadow_racio_interpreter: ShadowRacioInterpreter | None = None

    def __post_init__(self) -> None:
        if self.racio_interpreter_mode == "deterministic":
            if self.shadow_racio_interpreter is not None:
                raise ValueError(
                    "A shadow dependency requires explicit gemma4_text_shadow mode"
                )
            return
        if self.racio_interpreter_mode != "gemma4_text_shadow":
            raise ValueError("Unknown Racio interpreter runtime mode")
        if self.shadow_racio_interpreter is None:
            raise ValueError("Gemma text shadow mode requires an explicit dependency")
        if not isinstance(self.interpreter, DeterministicRacioInterpreter):
            raise ValueError(
                "Gemma text shadow requires the deterministic authoritative interpreter"
            )

    @classmethod
    def with_file_stores(
        cls,
        *,
        runs_root: str | Path = "output/runs",
        ego_traces_root: str | Path = "output/ego_traces",
        clock: ExecutionClock | None = None,
        emocio_processor: DeterministicEmocioProcessor | None = None,
        racio_interpreter_mode: RacioInterpreterRuntimeMode = "deterministic",
        shadow_racio_interpreter: ShadowRacioInterpreter | None = None,
    ) -> ReiNativeEngine:
        return cls(
            artifact_store=FileArtifactStore(runs_root),
            ego_trace_store=FileEgoTraceStore(ego_traces_root),
            providers=build_deterministic_native_providers(
                emocio_processor=emocio_processor,
            ),
            clock=clock or SystemExecutionClock(),
            racio_interpreter_mode=racio_interpreter_mode,
            shadow_racio_interpreter=shadow_racio_interpreter,
        )

    def run_cycle(self, request: ReiNativeCycleRequest) -> ReiNativeCycleResult:
        """Execute one deterministic, profile-blind-then-governed native cycle."""

        # ``model_copy(update=...)`` is intentionally not a Pydantic validation
        # boundary. Reconstruct the typed request before clocks, stores, or
        # providers can observe a caller-forged copy.
        try:
            request = ReiNativeCycleRequest.model_validate(
                request.model_dump(mode="python", round_trip=True)
            )
        except ValidationError as exc:
            if any(
                error.get("loc")
                and error["loc"][0] == "historical_bundles"
                for error in exc.errors()
            ):
                raise ValueError(
                    "Historical bundle identity, hash and event must exactly "
                    "match EgoTrace"
                ) from exc
            raise
        prior_trace = self.ego_trace_store.load_trace(request.ego_id)
        recover_prepared = getattr(
            self.artifact_store,
            "recover_prepared_run",
            None,
        )
        if recover_prepared is not None:
            recovered = recover_prepared(
                request.run_id,
                request_hash=request.content_hash(),
                ego_id=request.ego_id,
                trace=prior_trace,
            )
            if recovered is not None:
                raise ArtifactExistsError(
                    "Run already completed; an interrupted final manifest was recovered "
                    "when necessary"
                )
        history, prior_snapshot, prior_projections = _historical_context(
            trace=prior_trace,
            bundles=request.historical_bundles,
            emocio_signals=request.historical_emocio_signals,
            instinkt_signals=request.historical_instinkt_signals,
            artifact_store=self.artifact_store,
            current_body_state=request.body_state,
            current_instinkt_world=request.instinkt_world,
            structural_character=request.character,
        )
        run_started_at = self.clock.timestamp("run_started")
        ensure_tree = getattr(self.artifact_store, "ensure_run_tree", None)
        if ensure_tree is not None:
            ensure_tree(request.run_id)

        reservation = self.artifact_store.write_bytes(
            request.run_id,
            "diagnostics/run_reservation.json",
            canonical_json_bytes(
                {
                    "schema_version": "rei-native-run-reservation-v1",
                    "run_id": request.run_id,
                    "ego_id": request.ego_id,
                    "request_hash": request.content_hash(),
                    "expected_trace_hash": prior_trace.trace_hash,
                    "created_at": run_started_at,
                }
            ),
        )
        previous_racio_projection_ids = (
            ()
            if prior_projections is None
            else (prior_projections.racio.projection_id,)
        )
        previous_racio_projection_hashes = (
            ()
            if prior_projections is None
            else (prior_projections.racio.projection_hash,)
        )
        previous_emocio_projection_ids = (
            ()
            if prior_projections is None
            else (prior_projections.emocio.projection_id,)
        )
        previous_emocio_projection_hashes = (
            ()
            if prior_projections is None
            else (prior_projections.emocio.projection_hash,)
        )
        previous_instinkt_projection_ids = (
            ()
            if prior_projections is None
            else (prior_projections.instinkt.projection_id,)
        )
        previous_instinkt_projection_hashes = (
            ()
            if prior_projections is None
            else (prior_projections.instinkt.projection_hash,)
        )
        racio_world = _racio_world_with_projection(
            request.racio_world, prior_projections
        )
        emocio_world = _emocio_world_with_projection(
            request.emocio_world, prior_projections
        )
        instinkt_projection = (
            None if prior_projections is None else prior_projections.instinkt
        )

        racio_packet = build_racio_packet(
            request.scene,
            racio_world,
            symbolic_and_language_cues=request.symbolic_and_language_cues,
            numeric_cues=request.numeric_cues,
            time=request.time_cues,
            rules=request.explicit_rules,
            explicit_consequences=request.explicit_consequences,
            previous_racio_projection_ids=previous_racio_projection_ids,
            previous_racio_projection_hashes=previous_racio_projection_hashes,
        )
        emocio_packet = build_emocio_packet(
            request.scene,
            previous_emocio_projection_ids=previous_emocio_projection_ids,
            previous_emocio_projection_hashes=previous_emocio_projection_hashes,
        )
        instinkt_packet = build_instinkt_packet(
            request.scene,
            request.body_state,
            physical_cues=request.instinkt_physical_cues,
            uncertainty_cues=request.instinkt_uncertainty_cues,
            trust_cues=request.instinkt_trust_cues,
            boundary_cues=request.instinkt_boundary_cues,
            attachment_cues=request.instinkt_attachment_cues,
            scarcity_cues=request.instinkt_scarcity_cues,
            escape_cues=request.instinkt_escape_cues,
            explicit_body_cues=request.instinkt_explicit_body_cues,
            evidence_ids=request.instinkt_evidence_ids,
            cue_evidence_bindings=request.instinkt_cue_evidence_bindings,
            previous_instinkt_projection_ids=previous_instinkt_projection_ids,
            previous_instinkt_projection_hashes=(
                previous_instinkt_projection_hashes
            ),
        )
        active_instinkt_specs, instinkt_associations = _instinkt_history_inputs(
            projection=instinkt_projection,
            specs=request.instinkt_effect_specs,
            records=request.instinkt_associations,
        )
        instinkt_effect_ruleset: InstinktEffectRuleSet | None = None
        instinkt_effect_predictions: tuple[OptionBodyEffectPrediction, ...] = ()
        instinkt_effect_compilations: tuple[OptionBodyEffectCompilation, ...] = ()
        if request.instinkt_effect_source == "manual_fixture":
            instinkt_effects = bind_instinkt_effects(
                instinkt_packet,
                active_instinkt_specs,
            )
        else:
            mapper: EmbodiedCueInterpreter
            if self.embodied_cue_interpreter is not None:
                mapper = self.embodied_cue_interpreter
            elif request.instinkt_effect_source == "rule_based":
                mapper = RuleBasedEmbodiedCueInterpreter(
                    association_records=request.instinkt_associations
                )
            else:
                mapper = ModelBackedEmbodiedCueInterpreterStub()
            raw_ruleset = getattr(mapper, "ruleset", None)
            if not isinstance(raw_ruleset, InstinktEffectRuleSet):
                if request.instinkt_effect_source == "model_backed":
                    raise ModelBackedEffectInferenceDisabledError(
                        "Model-backed body-effect inference is a disabled C5 "
                        "stub; no validated provider implementation is configured."
                    )
                raise ValueError(
                    "Automatic Instinkt mapper must expose its exact effect rule set"
                )
            instinkt_effect_ruleset = raw_ruleset
            instinkt_effect_predictions = tuple(
                mapper.infer_effects(
                    request.scene,
                    instinkt_packet,
                    request.instinkt_world,
                    request.body_state,
                    option,
                )
                for option in sorted(
                    request.scene.options, key=lambda item: item.option_id
                )
            )
            if any(
                item.effect_source != request.instinkt_effect_source
                for item in instinkt_effect_predictions
            ):
                raise ValueError(
                    "Instinkt mapper prediction source differs from requested mode"
                )
            association_by_id = {
                item.association_id: item for item in request.instinkt_associations
            }
            for prediction in instinkt_effect_predictions:
                for evidence in prediction.evidence:
                    for match in evidence.association_matches:
                        association = association_by_id.get(match.association_id)
                        if (
                            association is None
                            or match.association_hash != association.content_hash()
                        ):
                            raise ValueError(
                                "Instinkt mapper association lineage differs from "
                                "the request-scoped typed record"
                            )
            abstaining_options = tuple(
                item.option_id
                for item in instinkt_effect_predictions
                if item.abstains
            )
            if abstaining_options:
                raise ValueError(
                    "Rule-based Instinkt mapper abstained without emitting silent "
                    f"defaults for options={abstaining_options}"
                )
            option_by_id = {
                item.option_id: item for item in request.scene.options
            }
            instinkt_effect_compilations = tuple(
                compile_prediction_to_option_body_effect(
                    prediction=prediction,
                    scene=request.scene,
                    packet=instinkt_packet,
                    world=request.instinkt_world,
                    body=request.body_state,
                    option=option_by_id[prediction.option_id],
                    ruleset=instinkt_effect_ruleset,
                    association_records=request.instinkt_associations,
                )
                for prediction in instinkt_effect_predictions
            )
            instinkt_effects = tuple(
                item.option_body_effect
                for item in instinkt_effect_compilations
            )

        racio_spec = self.providers.racio.build_call_spec(racio_packet)
        emocio_spec = self.providers.emocio.build_call_spec(
            request.scene,
            emocio_world,
            emocio_packet,
        )
        instinkt_spec = self.providers.instinkt.build_call_spec(
            scene=request.scene,
            packet=instinkt_packet,
            source_body_state=request.body_state,
            option_effects=instinkt_effects,
            config=request.instinkt_config,
            associations=instinkt_associations,
        )
        _validate_preapproved_native_call(
            spec=racio_spec,
            identity=self.providers.racio.identity,
            request_id=racio_packet.packet_id,
            expected_inputs=self.providers.racio.required_input_artifact_ids(
                racio_packet
            ),
        )
        _validate_preapproved_native_call(
            spec=emocio_spec,
            identity=self.providers.emocio.identity,
            request_id=emocio_packet.packet_id,
            expected_inputs=self.providers.emocio.required_input_artifact_ids(
                request.scene,
                emocio_world,
                emocio_packet,
            ),
        )
        _validate_preapproved_native_call(
            spec=instinkt_spec,
            identity=self.providers.instinkt.identity,
            request_id=instinkt_packet.packet_id,
            expected_inputs=self.providers.instinkt.required_input_artifact_ids(
                scene=request.scene,
                packet=instinkt_packet,
                source_body_state=request.body_state,
                option_effects=instinkt_effects,
                config=request.instinkt_config,
                associations=instinkt_associations,
            ),
        )

        configured_emocio_modes = tuple(
            parameter.canonical_json_value
            for parameter in emocio_spec.parameters
            if parameter.name == "emocio.cognition_mode"
        )
        if len(configured_emocio_modes) > 1:
            raise ValueError("Emocio call declares cognition mode more than once")
        configured_emocio_expected = bool(configured_emocio_modes)
        if (
            self.clock.synthetic
            and configured_emocio_expected
            and configured_emocio_modes[0]
            != canonical_json_bytes("structured_only").decode("utf-8")
        ):
            raise ValueError(
                "Configured rendering Emocio requires a system execution clock so "
                "nested provider intervals remain auditable"
            )

        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="rei-native") as pool:
            racio_future = pool.submit(
                self.providers.racio.execute,
                racio_packet,
                call=racio_spec,
                clock=self.clock,
            )
            emocio_future = pool.submit(
                self.providers.emocio.execute,
                request.scene,
                emocio_world,
                packet=emocio_packet,
                call=emocio_spec,
                clock=self.clock,
            )
            instinkt_future = pool.submit(
                self.providers.instinkt.execute,
                scene=request.scene,
                packet=instinkt_packet,
                source_body_state=request.body_state,
                option_effects=instinkt_effects,
                config=request.instinkt_config,
                associations=instinkt_associations,
                call=instinkt_spec,
                clock=self.clock,
            )
            racio_execution = racio_future.result()
            raw_emocio_execution = emocio_future.result()
            instinkt_execution = instinkt_future.result()

        try:
            raw_runtime_config = getattr(
                raw_emocio_execution,
                "runtime_config",
                None,
            )
            raw_processing_artifact = getattr(
                raw_emocio_execution,
                "processing_artifact",
                None,
            )
            emocio_execution = SimpleNamespace(
                conclusion=EmocioNativeConclusion.model_validate(
                    raw_emocio_execution.conclusion.model_dump(
                        mode="python",
                        round_trip=True,
                    )
                ),
                call_spec=ProviderCallSpec.model_validate(
                    raw_emocio_execution.call_spec.model_dump(
                        mode="python",
                        round_trip=True,
                    )
                ),
                call_record=ProviderCallRecord.model_validate(
                    raw_emocio_execution.call_record.model_dump(
                        mode="python",
                        round_trip=True,
                    )
                ),
                source_world_id=raw_emocio_execution.source_world_id,
                source_world_hash=raw_emocio_execution.source_world_hash,
                packet=EmocioInputPacket.model_validate(
                    raw_emocio_execution.packet.model_dump(
                        mode="python",
                        round_trip=True,
                    )
                ),
                visual_state=EmocioVisualState.model_validate(
                    raw_emocio_execution.visual_state.model_dump(
                        mode="python",
                        round_trip=True,
                    )
                ),
                rendered_images=tuple(
                    ImageArtifact.model_validate(
                        image.model_dump(mode="python", round_trip=True)
                    )
                    for image in raw_emocio_execution.rendered_images
                ),
                renderer_warning=raw_emocio_execution.renderer_warning,
                processing=getattr(raw_emocio_execution, "processing", None),
                runtime_config=(
                    None
                    if raw_runtime_config is None
                    else EmocioProcessorRuntimeConfig.model_validate(
                        raw_runtime_config.model_dump(
                            mode="python",
                            round_trip=True,
                        )
                    )
                ),
                processing_artifact=(
                    None
                    if raw_processing_artifact is None
                    else EmocioProcessingArtifact.model_validate(
                        raw_processing_artifact.model_dump(
                            mode="python",
                            round_trip=True,
                        )
                    )
                ),
                binary_snapshots=tuple(
                    getattr(raw_emocio_execution, "binary_snapshots", ())
                ),
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                "Emocio provider execution failed canonical capture"
            ) from exc
        if (
            emocio_execution.renderer_warning is not None
            and (
                type(emocio_execution.renderer_warning) is not str
                or not emocio_execution.renderer_warning
            )
        ):
            raise ValueError("Emocio renderer warning must be non-empty text")

        if (
            racio_execution.call_spec != racio_spec
            or emocio_execution.call_spec != emocio_spec
            or instinkt_execution.call_spec != instinkt_spec
        ):
            raise ValueError(
                "Native provider returned a call spec other than the pre-approved contract"
            )
        racio_reasoning_artifact = _validated_racio_reasoning_artifact(
            racio_execution
        )
        if (
            emocio_execution.packet != emocio_packet
            or emocio_execution.source_world_id != emocio_world.world_id
            or emocio_execution.source_world_hash != emocio_world.content_hash()
        ):
            raise ValueError(
                "Emocio execution returned a different approved packet or world"
            )
        if instinkt_execution.packet != instinkt_packet:
            raise ValueError("Instinkt execution returned a different approved input packet")
        if (
            instinkt_execution.source_body_state != request.body_state
            or instinkt_execution.option_effects
            != tuple(sorted(instinkt_effects, key=lambda item: item.option_id))
            or instinkt_execution.associations
            != tuple(sorted(instinkt_associations, key=instinkt_memory_record_id))
            or instinkt_execution.config != request.instinkt_config
        ):
            raise ValueError(
                "Instinkt execution returned inputs other than its pre-approved body, "
                "effects, memory or config"
            )

        replay_memory: BoundedAssociativeMemory | None = None
        if instinkt_associations:
            replay_memory = BoundedAssociativeMemory()
            for record in sorted(
                instinkt_associations,
                key=instinkt_memory_record_id,
            ):
                replay_memory.add(record)
        replayed_instinkt = process_instinkt(
            scene=request.scene,
            packet=instinkt_packet,
            source_body_state=request.body_state,
            option_effects=instinkt_effects,
            config=request.instinkt_config,
            memory=replay_memory,
        )
        if (
            instinkt_execution.rollouts != replayed_instinkt.rollouts
            or instinkt_execution.conclusion != replayed_instinkt.conclusion
            or instinkt_execution.manifestation != replayed_instinkt.manifestation
        ):
            raise ValueError(
                "Instinkt provider output differs from canonical B8 memory "
                "retrieval and deterministic replay"
            )

        emocio_runtime_config = getattr(emocio_execution, "runtime_config", None)
        emocio_processing_artifact = getattr(
            emocio_execution,
            "processing_artifact",
            None,
        )
        emocio_binary_snapshots = tuple(
            getattr(emocio_execution, "binary_snapshots", ())
        )
        configured_emocio = emocio_runtime_config is not None
        if configured_emocio != configured_emocio_expected:
            raise ValueError(
                "Emocio execution shape differs from its approved configured call"
            )
        if configured_emocio != (emocio_processing_artifact is not None):
            raise ValueError(
                "Configured Emocio execution must close its processing artifact"
            )
        if not configured_emocio and emocio_binary_snapshots:
            raise ValueError(
                "Legacy Emocio execution cannot publish configured binary snapshots"
            )
        if not configured_emocio and (
            emocio_execution.rendered_images
            or emocio_execution.renderer_warning is not None
        ):
            raise ValueError(
                "Legacy Emocio execution must preserve the structured-only baseline"
            )
        ensure_call_record_contract(emocio_spec, emocio_execution.call_record)
        expected_emocio_outputs = (emocio_execution.conclusion.conclusion_id,)
        if emocio_processing_artifact is not None:
            expected_emocio_outputs = (
                *expected_emocio_outputs,
                emocio_processing_artifact.result_id,
            )
        if (
            emocio_execution.call_record.status != "succeeded"
            or emocio_execution.call_record.primary_status != "succeeded"
            or emocio_execution.call_record.fallback is not None
            or emocio_execution.call_record.output_artifact_ids
            != expected_emocio_outputs
            or emocio_execution.call_record.warnings
        ):
            raise ValueError(
                "Emocio execution record differs from its direct successful call"
            )

        nested_specs: tuple[ProviderCallSpec, ...] = ()
        nested_records: tuple[ProviderCallRecord, ...] = ()
        renderer_call_ids: tuple[str, ...] = ()
        encoder_call_ids: tuple[str, ...] = ()
        emocio_execution_record: EmocioExecutionManifestRecord | None = None
        emocio_renderer_warning = emocio_execution.renderer_warning
        emocio_visual_warning: str | None = None
        if configured_emocio:
            assert emocio_runtime_config is not None
            assert emocio_processing_artifact is not None
            expected_emocio_spec = (
                DeterministicEmocioNativeProvider().configured_call_spec(
                    request.scene,
                    emocio_world,
                    emocio_packet,
                    runtime_config=emocio_runtime_config,
                )
            )
            if emocio_spec != expected_emocio_spec:
                raise ValueError(
                    "Configured Emocio runtime differs from its approved call"
                )
            replayed_processing = emocio_processing_artifact.to_result(
                request.scene,
                emocio_world,
            )
            if (
                replayed_processing.packet != emocio_execution.packet
                or replayed_processing.visual_state != emocio_execution.visual_state
                or replayed_processing.native_conclusion
                != emocio_execution.conclusion
                or replayed_processing.rendered_images
                != emocio_execution.rendered_images
                or replayed_processing.renderer_warning
                != emocio_execution.renderer_warning
            ):
                raise ValueError(
                    "Configured Emocio processing artifact differs from execution"
                )
            (
                nested_specs,
                nested_records,
                renderer_call_ids,
                encoder_call_ids,
            ) = validate_processing_runtime_closure(
                emocio_runtime_config,
                replayed_processing,
            )
            validate_binary_snapshots_against_processing(
                replayed_processing,
                emocio_binary_snapshots,
            )
            emocio_execution.processing = replayed_processing
            emocio_renderer_warning = replayed_processing.renderer_warning
            emocio_visual_warning = replayed_processing.visual_warning
            materialized = tuple(
                EmocioMaterializedArtifactRecord(
                    artifact_id=snapshot.artifact_id,
                    role=snapshot.role,
                    relative_path=snapshot.relative_path,
                    content_sha256=snapshot.content_sha256,
                    size_bytes=len(snapshot.content),
                )
                for snapshot in emocio_binary_snapshots
            )
            emocio_execution_record = EmocioExecutionManifestRecord.create(
                outer_call_id=emocio_execution.call_spec.call_id,
                processor_config_id=emocio_runtime_config.config_id,
                processor_config_hash=emocio_runtime_config.content_hash(),
                processing_artifact_id=emocio_processing_artifact.result_id,
                processing_artifact_hash=(
                    emocio_processing_artifact.content_hash()
                ),
                renderer_call_ids=renderer_call_ids,
                encoder_call_ids=encoder_call_ids,
                materialized_artifacts=materialized,
            )

        assembly_started_at = self.clock.timestamp("assembly_started")
        bundle = NativeMindBundle.create(
            scene=request.scene,
            racio_packet=racio_packet,
            emocio_packet=emocio_packet,
            instinkt_packet=instinkt_packet,
            emocio_visual_state=emocio_execution.visual_state,
            instinkt_body_state=request.body_state,
            instinkt_rollouts=instinkt_execution.rollouts,
            racio=racio_execution.conclusion,
            emocio=emocio_execution.conclusion,
            instinkt=instinkt_execution.conclusion,
            created_at=self.clock.timestamp("assembly_finished"),
        )
        assembly_finished_at = bundle.created_at
        assembly = _native_assembly(
            bundle=bundle,
            racio=racio_execution,
            emocio=emocio_execution,
            instinkt=instinkt_execution,
            started_at=assembly_started_at,
            finished_at=assembly_finished_at,
        )

        effective_authority = derive_effective_authority(
            request.character,
            request.functional_override,
        )
        governance = resolve_governance(
            bundle,
            effective_authority,
            delegation=request.delegation,
            negotiation_rounds=request.negotiation_rounds,
        )
        emocio_manifestation = build_emocio_manifestation(
            conclusion=bundle.emocio,
            images=emocio_execution.rendered_images,
        )
        instinkt_manifestation = instinkt_execution.manifestation
        manifestations = (emocio_manifestation, instinkt_manifestation)
        scene_option_descriptions = {
            option.option_id: option.description for option in request.scene.options
        }

        emocio_communication = process_communication(
            conclusion=bundle.emocio,
            manifestations=(emocio_manifestation,),
            allowed_option_ids=bundle.allowed_option_ids,
            acceptance_state=request.acceptance_state,
            interpreter=self.interpreter,
            language=request.scene.language,
            option_descriptions=scene_option_descriptions,
        )
        instinkt_communication = process_communication(
            conclusion=bundle.instinkt,
            manifestations=(instinkt_manifestation,),
            allowed_option_ids=bundle.allowed_option_ids,
            acceptance_state=request.acceptance_state,
            interpreter=self.interpreter,
            language=request.scene.language,
            option_descriptions=scene_option_descriptions,
        )
        communications = (emocio_communication, instinkt_communication)
        c3_results = _validated_c3_results(communications)
        shadow_communications: tuple[ShadowRacioInterpretationExecution, ...] = ()
        if self.racio_interpreter_mode == "gemma4_text_shadow":
            assert self.shadow_racio_interpreter is not None
            shadow_communications = tuple(
                execute_racio_text_shadow(
                    request=item.request,
                    deterministic=item.interpretation,
                    language=request.scene.language,
                    option_descriptions=scene_option_descriptions,
                    interpreter=self.shadow_racio_interpreter,
                    clock=self.clock,
                )
                for item in communications
            )
        mandate_view = ConsciousMandateView.create_b10(
            governance=governance,
            bundle=bundle,
            manifestations=manifestations,
        )
        interpretation_inputs = tuple(
            ConsciousInterpretationInput.create_b10(
                mandate_view=mandate_view,
                request=result.request,
                interpretation=result.interpretation,
                acceptance_state=request.acceptance_state,
            )
            for result in communications
        )
        conscious_decision = self.committer.commit(
            mandate_view=mandate_view,
            racio_conclusion=bundle.racio,
            acceptance_state=request.acceptance_state,
            interpretation_inputs=interpretation_inputs,
        )
        behavior_resultant = self.behavior_resolver.resolve(
            mandate_view=mandate_view,
            decision=conscious_decision,
            acceptance_state=request.acceptance_state,
            racio_conclusion=bundle.racio,
            interpretation_inputs=interpretation_inputs,
        )
        narrative = self.narrator.narrate(
            mandate_view=mandate_view,
            decision=conscious_decision,
            resultant=behavior_resultant,
            interpretation_inputs=interpretation_inputs,
        )

        measure_created_at = self.clock.timestamp("measure_created")
        ego_measure = build_ego_measure(
            bundle=bundle,
            governance=governance,
            structural_character=request.character,
            effective_authority=effective_authority,
            acceptance_state=request.acceptance_state,
            conscious_decision=conscious_decision,
            behavior_resultant=behavior_resultant,
            racio_interpretations=tuple(
                item.interpretation for item in interpretation_inputs
            ),
            translation_gaps=(
                emocio_communication.translation_gap,
                instinkt_communication.translation_gap,
            ),
            unresolved_tensions=behavior_resultant.residual_tensions,
            outcome=request.outcome,
            created_at=measure_created_at,
        )
        ego_trace = prior_trace.append_measure(ego_measure)

        complete_history = {**history, bundle.bundle_id: bundle}
        composition_snapshot = derive_composition_snapshot(ego_trace)
        projections = derive_modality_projections(
            ego_trace,
            complete_history,
            emocio_history=request.historical_emocio_signals,
            instinkt_history=request.historical_instinkt_signals,
        )

        run_finished_at = self.clock.timestamp("run_finished")
        call_specs: tuple[ProviderCallSpec, ...] = (
            racio_execution.call_spec,
            emocio_execution.call_spec,
            instinkt_execution.call_spec,
            *nested_specs,
            *(result.execution.call_spec for result in c3_results),
            *(
                result.call_spec
                for result in shadow_communications
                if result.call_spec is not None
            ),
        )
        call_records: tuple[ProviderCallRecord, ...] = (
            racio_execution.call_record,
            emocio_execution.call_record,
            instinkt_execution.call_record,
            *nested_records,
            *(result.execution.call_record for result in c3_results),
            *(
                result.call_record
                for result in shadow_communications
                if result.call_record is not None
            ),
        )
        base_provider_identities = (
            *self.providers.identities,
            self.artifact_store.identity,
            self.ego_trace_store.identity,
        )
        additional_specs = (
            *nested_specs,
            *(result.execution.call_spec for result in c3_results),
            *(
                result.call_spec
                for result in shadow_communications
                if result.call_spec is not None
            ),
        )
        additional_records = (
            *nested_records,
            *(result.execution.call_record for result in c3_results),
            *(
                result.call_record
                for result in shadow_communications
                if result.call_record is not None
            ),
        )
        additional_provider_identities = _provider_identities_from_calls(
            additional_specs,
            additional_records,
        )
        manifest_provider_identities = (
            _unique_provider_identities(
                (*base_provider_identities, *additional_provider_identities)
            )
            if additional_provider_identities
            else base_provider_identities
        )
        warnings = tuple(
            dict.fromkeys(
                item
                for item in (
                    emocio_renderer_warning,
                    emocio_visual_warning,
                    (
                        "Deterministic logical execution clock; timestamps are synthetic."
                        if self.clock.synthetic
                        else None
                    ),
                )
                if item is not None
            )
        )
        provisional_manifest = RunManifest(
            run_id=request.run_id,
            source_commit=request.source_commit,
            canon_version=request.canon_version,
            mode=request.mode,
            profile_id=request.character.profile_id,
            acceptance_state_id=request.acceptance_state.acceptance_state_id,
            acceptance_config_hash=request.acceptance_state.content_hash(),
            providers=manifest_provider_identities,
            provider_call_specs=call_specs,
            provider_calls=call_records,
            seeds=_seed_records(call_records),
            native_artifact_hashes=_native_hashes(bundle),
            native_artifact_source="produced",
            native_assembly=assembly,
            emocio_execution=emocio_execution_record,
            started_at=run_started_at,
            finished_at=run_finished_at,
            status="completed",
            warnings=warnings,
            safety_flags=("synthetic_execution_clock",) if self.clock.synthetic else (),
        )
        invariants = build_cycle_invariant_report(
            run_id=request.run_id,
            bundle=bundle,
            character=request.character,
            effective_authority=effective_authority,
            governance=governance,
            decision=conscious_decision,
            behavior=behavior_resultant,
            narrative=narrative,
            measure=ego_measure,
            trace=ego_trace,
            snapshot=composition_snapshot,
            manifest=provisional_manifest,
        )
        prepared_artifacts = self._persist_run(
            request=request,
            racio_world=racio_world,
            emocio_world=emocio_world,
            racio_packet=racio_packet,
            emocio_packet=emocio_packet,
            instinkt_packet=instinkt_packet,
            instinkt_effect_ruleset=instinkt_effect_ruleset,
            instinkt_effect_predictions=instinkt_effect_predictions,
            instinkt_effect_compilations=instinkt_effect_compilations,
            racio_execution=racio_execution,
            racio_reasoning_artifact=racio_reasoning_artifact,
            emocio_execution=emocio_execution,
            instinkt_execution=instinkt_execution,
            bundle=bundle,
            effective_authority=effective_authority,
            governance=governance,
            manifestations=manifestations,
            communications=communications,
            c3_results=c3_results,
            shadow_communications=shadow_communications,
            mandate_view=mandate_view,
            conscious_decision=conscious_decision,
            behavior_resultant=behavior_resultant,
            narrative=narrative,
            ego_measure=ego_measure,
            ego_trace=ego_trace,
            composition_snapshot=composition_snapshot,
            projections=projections,
            invariants=invariants,
            manifest=provisional_manifest,
            reservation=reservation,
        )
        manifest = RunManifest.finalize_v2(
            provisional_manifest,
            tuple(
                RunArtifactRecord(**artifact.model_dump(mode="python"))
                for artifact in prepared_artifacts
            ),
        )
        if build_cycle_invariant_report(
            run_id=request.run_id,
            bundle=bundle,
            character=request.character,
            effective_authority=effective_authority,
            governance=governance,
            decision=conscious_decision,
            behavior=behavior_resultant,
            narrative=narrative,
            measure=ego_measure,
            trace=ego_trace,
            snapshot=composition_snapshot,
            manifest=manifest,
        ) != invariants:
            raise ValueError("Final manifest changed the prepared invariant report")
        prepared_manifest_artifact = self.artifact_store.write_json(
            request.run_id,
            "diagnostics/prepared_manifest.json",
            manifest,
        )
        verify_prepared = getattr(
            self.artifact_store,
            "verify_prepared_run",
            None,
        )
        if callable(verify_prepared):
            verified_prepared = verify_prepared(request.run_id)
            if verified_prepared != manifest:
                raise ValueError(
                    "Prepared run verifier returned another manifest"
                )
        elif configured_emocio:
            raise ValueError(
                "Configured Emocio requires a cold prepared-run verifier before "
                "EgoTrace commit"
            )
        self.ego_trace_store.append_measure(
            request.ego_id,
            ego_measure,
            expected_trace_hash=prior_trace.trace_hash,
        )
        persisted_trace = self.ego_trace_store.load_trace(request.ego_id)
        if persisted_trace != ego_trace:
            raise ValueError("EgoTrace store did not CAS-append the prepared trace")
        manifest_artifact = self.artifact_store.write_json(
            request.run_id,
            "run_manifest.json",
            manifest,
        )
        stored_artifacts = (
            *prepared_artifacts,
            prepared_manifest_artifact,
            manifest_artifact,
        )
        return ReiNativeCycleResult(
            request=request,
            prior_trace=prior_trace,
            prior_snapshot=prior_snapshot,
            prior_projections=prior_projections,
            racio_world_input=racio_world,
            emocio_world_input=emocio_world,
            racio_packet=racio_packet,
            emocio_packet=emocio_packet,
            instinkt_packet=instinkt_packet,
            instinkt_world_input=request.instinkt_world,
            instinkt_effect_source=request.instinkt_effect_source,
            instinkt_effect_ruleset=instinkt_effect_ruleset,
            instinkt_effect_predictions=instinkt_effect_predictions,
            instinkt_effect_compilations=instinkt_effect_compilations,
            racio_execution=racio_execution,
            emocio_execution=emocio_execution,
            instinkt_execution=instinkt_execution,
            native_bundle=bundle,
            native_assembly=assembly,
            effective_authority=effective_authority,
            governance=governance,
            emocio_manifestation=emocio_manifestation,
            instinkt_manifestation=instinkt_manifestation,
            emocio_communication=emocio_communication,
            instinkt_communication=instinkt_communication,
            shadow_communications=shadow_communications,
            mandate_view=mandate_view,
            interpretation_inputs=interpretation_inputs,
            conscious_decision=conscious_decision,
            behavior_resultant=behavior_resultant,
            narrative=narrative,
            ego_measure=ego_measure,
            ego_trace=ego_trace,
            composition_snapshot=composition_snapshot,
            projections=projections,
            manifest=manifest,
            invariants=invariants,
            stored_artifacts=stored_artifacts,
        )

    def _persist_run(
        self,
        *,
        request: ReiNativeCycleRequest,
        racio_world: RacioWorld,
        emocio_world: EmocioWorld,
        racio_packet: RacioInputPacket,
        emocio_packet: EmocioInputPacket,
        instinkt_packet: InstinktInputPacket,
        instinkt_effect_ruleset: InstinktEffectRuleSet | None,
        instinkt_effect_predictions: tuple[OptionBodyEffectPrediction, ...],
        instinkt_effect_compilations: tuple[OptionBodyEffectCompilation, ...],
        racio_execution: RacioNativeExecution,
        racio_reasoning_artifact: FrozenArtifactModel | None,
        emocio_execution: EmocioNativeExecution,
        instinkt_execution: InstinktNativeExecution,
        bundle: NativeMindBundle,
        effective_authority: EffectiveAuthority,
        governance: GovernanceResolution,
        manifestations: tuple[EmocioManifestation, InstinktManifestation],
        communications: tuple[CommunicationProcessResult, CommunicationProcessResult],
        c3_results: tuple[StructuredRacioInterpretationResult, ...],
        shadow_communications: tuple[ShadowRacioInterpretationExecution, ...],
        mandate_view: ConsciousMandateView,
        conscious_decision: ConsciousDecision,
        behavior_resultant: BehaviorResultant,
        narrative: RacioSelfNarrative,
        ego_measure: EgoMeasure,
        ego_trace: EgoTrace,
        composition_snapshot: EgoCompositionSnapshot,
        projections: EgoModalityProjections,
        invariants: InvariantReport,
        manifest: RunManifest,
        reservation: StoredArtifact,
    ) -> tuple[StoredArtifact, ...]:
        """Prepare the full immutable run tree before the authoritative CAS append."""

        run_id = request.run_id
        records: list[StoredArtifact] = [reservation]

        def write_json(path: str, value: object) -> None:
            if hasattr(value, "canonical_json_bytes"):
                records.append(self.artifact_store.write_json(run_id, path, value))
            else:
                records.append(
                    self.artifact_store.write_bytes(
                        run_id,
                        path,
                        canonical_json_bytes(value),
                    )
                )

        write_json("scene/event.json", request.scene)
        write_json("scene/racio_packet.json", racio_packet)
        write_json("scene/emocio_packet.json", emocio_packet)
        write_json("scene/instinkt_packet.json", instinkt_packet)
        write_json("scene/racio_world.json", racio_world)
        write_json("scene/emocio_world.json", emocio_world)
        write_json("native/bundle.json", bundle)
        if racio_reasoning_artifact is not None:
            write_json(
                "native/racio_reasoning_evidence.json",
                racio_reasoning_artifact,
            )
        write_json("native/racio.json", racio_execution.conclusion)
        write_json("native/emocio.json", emocio_execution.conclusion)
        write_json("native/instinkt.json", instinkt_execution.conclusion)

        visual_state = emocio_execution.visual_state
        write_json("emocio/visual_state.json", visual_state)
        visual_scenes = {
            item.scene_id: item
            for item in (
                visual_state.current_scene,
                visual_state.desired_scene,
                visual_state.broken_scene,
                *visual_state.option_rollouts,
            )
        }
        for scene_id, visual_scene in sorted(visual_scenes.items()):
            write_json(f"emocio/scenes/{scene_id}.json", visual_scene)
        write_json(
            "emocio/images/index.json",
            emocio_execution.rendered_images,
        )
        runtime_config = getattr(emocio_execution, "runtime_config", None)
        processing_artifact = getattr(
            emocio_execution,
            "processing_artifact",
            None,
        )
        binary_snapshots = tuple(
            getattr(emocio_execution, "binary_snapshots", ())
        )
        if runtime_config is not None:
            if processing_artifact is None:
                raise ValueError(
                    "Configured Emocio persistence requires its processing artifact"
                )
            write_json(
                "emocio/processor_config.json",
                runtime_config,
            )
            write_json(
                "emocio/processing_result.json",
                processing_artifact,
            )
            persisted_binary_paths: dict[str, EmocioBinarySnapshot] = {}
            for snapshot in binary_snapshots:
                previous = persisted_binary_paths.setdefault(
                    snapshot.relative_path,
                    snapshot,
                )
                if previous is not snapshot:
                    if (
                        previous.role != snapshot.role
                        or previous.content_sha256 != snapshot.content_sha256
                        or previous.content != snapshot.content
                    ):
                        raise ValueError(
                            "One Emocio binary path cannot map to conflicting bytes"
                        )
                    continue
                records.append(
                    self.artifact_store.write_bytes(
                        run_id,
                        snapshot.relative_path,
                        snapshot.content,
                    )
                )

        write_json("instinkt/body_before.json", request.body_state)
        write_json("instinkt/simulation_config.json", request.instinkt_config)
        if request.instinkt_effect_source != "manual_fixture":
            if instinkt_effect_ruleset is None:
                raise ValueError("Automatic Instinkt persistence lacks a rule set")
            if request.scene.options and (
                not instinkt_effect_predictions or not instinkt_effect_compilations
            ):
                raise ValueError(
                    "Automatic Instinkt persistence lacks predictions or compilations"
                )
            if not request.scene.options and (
                instinkt_effect_predictions or instinkt_effect_compilations
            ):
                raise ValueError(
                    "Optionless Instinkt persistence cannot contain option effects"
                )
            write_json("scene/instinkt_world.json", request.instinkt_world)
            write_json(
                "instinkt/effect_source.json",
                {
                    "schema_version": "rei-native-instinkt-effect-source-v1",
                    "effect_source": request.instinkt_effect_source,
                },
            )
            write_json("instinkt/effect_ruleset.json", instinkt_effect_ruleset)
            write_json(
                "instinkt/effect_predictions.json",
                instinkt_effect_predictions,
            )
            write_json(
                "instinkt/effect_compilations.json",
                instinkt_effect_compilations,
            )
        write_json("instinkt/option_effects.json", instinkt_execution.option_effects)
        write_json("instinkt/ego_memory.json", instinkt_execution.associations)
        write_json("instinkt/option_rollouts.json", instinkt_execution.rollouts)
        write_json("instinkt/body_after.json", _decisive_body_after(instinkt_execution))
        write_json("communication/manifestations.json", manifestations)
        write_json(
            "communication/interpretations.json",
            tuple(item.interpretation for item in communications),
        )
        write_json(
            "communication/translation_gaps.json",
            tuple(item.translation_gap for item in communications),
        )
        c3_labels = {"E": "emocio", "I": "instinkt"}
        communication_by_mind = {
            item.request.source_mind: item for item in communications
        }
        for result in c3_results:
            label = c3_labels[result.access.packet.source_mind]
            prefix = f"communication/c3_{label}"
            write_json(
                f"{prefix}_interpreter_request.json",
                communication_by_mind[result.access.packet.source_mind].request,
            )
            write_json(f"{prefix}_access_packet.json", result.access.packet)
            write_json(f"{prefix}_access_audit.json", result.access.audit)
            write_json(f"{prefix}_call_spec.json", result.execution.call_spec)
            write_json(f"{prefix}_call_record.json", result.execution.call_record)
            write_json(f"{prefix}_structured_output.json", result.execution.output)
            write_json(
                f"{prefix}_response_evidence.json",
                _c3_response_evidence(result),
            )
        shadow_labels = {"E": "emocio", "I": "instinkt"}
        for result in shadow_communications:
            label = shadow_labels[result.source_mind]
            prefix = f"communication_shadow/{label}"
            if result.packet is not None:
                write_json(f"{prefix}_packet_v3.json", result.packet)
            if result.call_spec is not None:
                write_json(f"{prefix}_call_spec.json", result.call_spec)
            if result.call_record is not None:
                write_json(f"{prefix}_provider_call_record.json", result.call_record)
            if result.interpretation is not None:
                write_json(
                    f"{prefix}_interpretation_v3.json",
                    result.interpretation,
                )
            if result.response_evidence is not None:
                write_json(
                    f"{prefix}_response_evidence.json",
                    result.response_evidence,
                )
            if result.comparison is not None:
                write_json(f"{prefix}_comparison.json", result.comparison)
            write_json(f"{prefix}_result.json", result.result)
        write_json("governance/character.json", request.character)
        write_json("governance/effective_authority.json", effective_authority)
        write_json("governance/mandate.json", governance)
        write_json("governance/delegation.json", governance.mandate.delegation)
        write_json("conscious/mandate_view.json", mandate_view)
        write_json("conscious/decision.json", conscious_decision)
        write_json("conscious/narrative.json", narrative)
        write_json("behavior/resultant.json", behavior_resultant)
        write_json("ego/measure.json", ego_measure)
        write_json("ego/trace.json", ego_trace)
        write_json("ego/composition_snapshot.json", composition_snapshot)
        write_json("ego/racio_projection.json", projections.racio)
        write_json("ego/emocio_projection.json", projections.emocio)
        write_json("ego/instinkt_projection.json", projections.instinkt)
        write_json("diagnostics/invariants.json", invariants)
        records.append(
            self.artifact_store.write_bytes(
                run_id,
                "diagnostics/report.md",
                render_diagnostic_report(invariants, manifest).encode("utf-8"),
            )
        )
        return tuple(records)


__all__ = [
    "ReiNativeCycleRequest",
    "ReiNativeCycleResult",
    "ReiNativeEngine",
]
