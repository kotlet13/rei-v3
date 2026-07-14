"""Replayable, modality-specific world learning after one Ego measure.

Each updater consumes the same immutable cycle lineage but writes only fields
owned by its modality.  There is deliberately no shared prose-summary field.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..emocio.vector_encoding import normalized_float32_le_bytes
from ..emocio.visual_valuation import BoundVisualEmbedding
from ..ids import content_id, sha256_hex
from ..models.common import FrozenArtifactModel, HashDigest, NonEmptyId, NonEmptyText
from ..models.conscious import RacioSelfNarrative
from ..models.ego import EgoMeasure
from ..models.emocio import (
    EmocioVisualState,
    EmocioWorld,
)
from ..models.instinkt import BodyState, InstinktOptionRollout, InstinktWorld
from ..models.racio import RacioWorld
from ..models.run import NativeMindBundle
from ..persistence.artifacts import ArtifactIntegrityError, validate_stored_artifact
from ..providers.protocols import ArtifactStore, StoredArtifact
from ..instinkt.outcome_learning import InstinktOutcomeUpdate


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


def _validate_storage_receipt(artifact: StoredArtifact) -> StoredArtifact:
    try:
        return validate_stored_artifact(artifact)
    except ArtifactIntegrityError as exc:
        raise ValueError(str(exc)) from exc


def _cold_revalidate(value: object) -> object:
    """Cross the C6 boundary through a fresh Pydantic validation pass."""

    model_type = type(value)
    validator = getattr(model_type, "model_validate", None)
    dumper = getattr(value, "model_dump", None)
    if validator is None or dumper is None:
        raise TypeError("C6 world-update inputs must be Pydantic artifacts")
    cold = validator(dumper(mode="python", round_trip=True))
    if cold != value:
        raise ValueError("C6 world-update input changed during cold revalidation")
    return cold


def _artifact_hash(value: FrozenArtifactModel) -> str:
    return value.content_hash()


def _validate_lineage(measure: EgoMeasure, bundle: NativeMindBundle) -> None:
    measure = _cold_revalidate(measure)  # type: ignore[assignment]
    bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
    if (
        measure.native_bundle_id != bundle.bundle_id
        or measure.native_bundle_hash != bundle.immutable_hash
        or measure.event_id != bundle.scene_id
    ):
        raise ValueError("World update lineage differs from the Ego measure bundle")


def _stable_novel(existing: tuple[str, ...], candidates: tuple[str, ...]) -> tuple[str, ...]:
    seen = set(existing)
    novel: list[str] = []
    for candidate in candidates:
        value = candidate.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        novel.append(value)
    return tuple(novel)


def _stable_union(existing: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
    return (*existing, *_stable_novel(existing, additions))


class EmocioLongitudinalVisualSignal(FrozenArtifactModel):
    """Byte-backed internal visual signal admitted to longitudinal memory.

    The signal carries the exact structured scene, image, imagination boundary,
    verified embedding, and create-only storage receipts.  C6 v1 captures it as
    a post-cycle internal evaluation artifact, not as output of the source
    cycle's Emocio processor.  It is never external evidence and never acquires
    semantic meaning from its vector alone.
    """

    schema_version: Literal["rei-c6-emocio-longitudinal-visual-signal-v1"] = (
        "rei-c6-emocio-longitudinal-visual-signal-v1"
    )
    signal_id: NonEmptyId
    source_run_id: NonEmptyId
    capture_stage: Literal["post_cycle_internal_evaluation"] = (
        "post_cycle_internal_evaluation"
    )
    source_cycle_processing_artifact: Literal[False] = False
    source_measure_id: NonEmptyId
    source_measure_hash: HashDigest
    source_bundle_id: NonEmptyId
    source_bundle_hash: HashDigest
    source_visual_state: EmocioVisualState
    source_visual_state_hash: HashDigest
    bound_observation: BoundVisualEmbedding
    bound_observation_hash: HashDigest
    image_storage: StoredArtifact
    embedding_storage: StoredArtifact
    embedding_vector: tuple[FiniteFloat, ...] = Field(min_length=1)
    internal_only: Literal[True] = True
    external_evidence: Literal[False] = False
    semantic_interpretation: Literal["none"] = "none"
    signal_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        visual_state: EmocioVisualState,
        observation: BoundVisualEmbedding,
        image_storage: StoredArtifact,
        embedding_storage: StoredArtifact,
        image_bytes: bytes,
        embedding_bytes: bytes,
        embedding_vector: tuple[float, ...],
    ) -> "EmocioLongitudinalVisualSignal":
        measure = _cold_revalidate(measure)  # type: ignore[assignment]
        bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
        visual_state = _cold_revalidate(visual_state)  # type: ignore[assignment]
        observation = _cold_revalidate(observation)  # type: ignore[assignment]
        image_storage = _cold_revalidate(image_storage)  # type: ignore[assignment]
        embedding_storage = _cold_revalidate(embedding_storage)  # type: ignore[assignment]
        _validate_storage_receipt(image_storage)
        _validate_storage_receipt(embedding_storage)
        if image_storage.run_id != embedding_storage.run_id:
            raise ValueError("C6 visual signal receipts must belong to one source run")
        canonical_vector_bytes = normalized_float32_le_bytes(
            embedding_vector,
            expected_dimensions=observation.embedding.dimensions,
        )
        if embedding_bytes != canonical_vector_bytes:
            raise ValueError("C6 supplied vector bytes differ from the exact vector")
        if (
            not image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
            or hashlib.sha256(image_bytes).hexdigest()
            != observation.image.content_sha256
        ):
            raise ValueError("C6 supplied image bytes differ from PNG provenance")
        if (
            image_storage.size_bytes != len(image_bytes)
            or embedding_storage.size_bytes != len(embedding_bytes)
            or image_storage.content_sha256
            != hashlib.sha256(image_bytes).hexdigest()
            or embedding_storage.content_sha256
            != hashlib.sha256(embedding_bytes).hexdigest()
        ):
            raise ValueError("C6 supplied bytes differ from their storage receipts")
        base = {
            "schema_version": "rei-c6-emocio-longitudinal-visual-signal-v1",
            "source_run_id": image_storage.run_id,
            "capture_stage": "post_cycle_internal_evaluation",
            "source_cycle_processing_artifact": False,
            "source_measure_id": measure.measure_id,
            "source_measure_hash": measure.measure_hash,
            "source_bundle_id": bundle.bundle_id,
            "source_bundle_hash": bundle.immutable_hash,
            "source_visual_state": visual_state,
            "source_visual_state_hash": visual_state.content_hash(),
            "bound_observation": observation,
            "bound_observation_hash": observation.content_hash(),
            "image_storage": image_storage,
            "embedding_storage": embedding_storage,
            "embedding_vector": embedding_vector,
            "internal_only": True,
            "external_evidence": False,
            "semantic_interpretation": "none",
        }
        signal_id = content_id("c6_emocio_visual_signal", base)
        payload = {"signal_id": signal_id, **base}
        return cls(**payload, signal_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_signal(self) -> Self:
        visual_state = _cold_revalidate(self.source_visual_state)
        observation = _cold_revalidate(self.bound_observation)
        image_storage = _cold_revalidate(self.image_storage)
        embedding_storage = _cold_revalidate(self.embedding_storage)
        _validate_storage_receipt(image_storage)
        _validate_storage_receipt(embedding_storage)
        if (
            self.source_run_id != image_storage.run_id
            or self.source_run_id != embedding_storage.run_id
        ):
            raise ValueError("C6 visual signal receipts differ from its source run")
        if (
            self.source_measure_hash != self.source_measure_hash.lower()
            or self.source_bundle_hash != self.source_bundle_hash.lower()
        ):
            raise ValueError("C6 visual signal hashes must be canonical")
        if (
            self.source_visual_state_hash != visual_state.content_hash()
            or self.bound_observation_hash != observation.content_hash()
        ):
            raise ValueError("C6 visual signal source hash differs from its artifact")
        scenes = (
            visual_state.current_scene,
            visual_state.desired_scene,
            visual_state.broken_scene,
            *visual_state.option_rollouts,
        )
        if observation.scene_spec not in scenes:
            raise ValueError("C6 visual signal scene is outside its visual state")
        vector_bytes = normalized_float32_le_bytes(
            self.embedding_vector,
            expected_dimensions=observation.embedding.dimensions,
        )
        if hashlib.sha256(vector_bytes).hexdigest() != observation.embedding.vector_hash:
            raise ValueError("C6 visual vector differs from embedding provenance")
        if (
            image_storage.relative_path != observation.image.path
            or image_storage.content_sha256 != observation.image.content_sha256
        ):
            raise ValueError("C6 image storage receipt differs from image provenance")
        if (
            embedding_storage.content_sha256 != observation.embedding.vector_hash
            or embedding_storage.relative_path != observation.encoding.vector_ref
            or embedding_storage.size_bytes != len(vector_bytes)
            or image_storage.run_id != embedding_storage.run_id
        ):
            raise ValueError("C6 embedding storage receipt differs from vector provenance")
        base = self.model_dump(
            mode="python", round_trip=True, exclude={"signal_id", "signal_hash"}
        )
        if self.signal_id != content_id("c6_emocio_visual_signal", base):
            raise ValueError("C6 visual signal ID differs from its content")
        payload = {"signal_id": self.signal_id, **base}
        if self.signal_hash != sha256_hex(payload):
            raise ValueError("C6 visual signal hash differs from its content")
        return self

    def validate_against(
        self,
        *,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        visual_state: EmocioVisualState,
    ) -> Self:
        measure = _cold_revalidate(measure)  # type: ignore[assignment]
        bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
        visual_state = _cold_revalidate(visual_state)  # type: ignore[assignment]
        _validate_lineage(measure, bundle)
        if (
            self.source_measure_id != measure.measure_id
            or self.source_measure_hash != measure.measure_hash
            or self.source_bundle_id != bundle.bundle_id
            or self.source_bundle_hash != bundle.immutable_hash
            or self.source_visual_state != visual_state
            or self.source_visual_state_hash != visual_state.content_hash()
            or bundle.emocio_visual_state_id != visual_state.visual_state_id
            or bundle.emocio_visual_state_hash != visual_state.content_hash()
        ):
            raise ValueError("C6 visual signal lineage differs from its cycle")
        return self

    def validate_stored_bytes(self, store: ArtifactStore) -> Self:
        """Cold-read both receipts and prove the signal is byte backed."""

        _validate_storage_receipt(self.image_storage)
        _validate_storage_receipt(self.embedding_storage)
        read_verified = getattr(store, "read_verified", None)
        try:
            if read_verified is not None:
                image_bytes = read_verified(self.image_storage)
                vector_bytes = read_verified(self.embedding_storage)
            else:
                image_bytes = store.read_bytes(self.image_storage.storage_id)
                vector_bytes = store.read_bytes(self.embedding_storage.storage_id)
        except ArtifactIntegrityError as exc:
            raise ValueError(str(exc)) from exc
        if (
            len(image_bytes) != self.image_storage.size_bytes
            or hashlib.sha256(image_bytes).hexdigest()
            != self.image_storage.content_sha256
            or len(vector_bytes) != self.embedding_storage.size_bytes
            or hashlib.sha256(vector_bytes).hexdigest()
            != self.embedding_storage.content_sha256
        ):
            raise ValueError("C6 visual storage bytes differ from their receipts")
        expected_vector = normalized_float32_le_bytes(
            self.embedding_vector,
            expected_dimensions=self.bound_observation.embedding.dimensions,
        )
        if vector_bytes != expected_vector:
            raise ValueError("C6 stored embedding bytes differ from the exact vector")
        if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("C6 stored image is not a PNG artifact")
        return self

    @property
    def world_memory_reference(self) -> str:
        return f"visual_signal:{self.signal_id}:{self.signal_hash}"

    @property
    def social_position_references(self) -> tuple[str, ...]:
        """Exact structured social-position fields from the current scene."""

        scene = self.source_visual_state.current_scene
        return (
            f"social_position:self:{scene.self_position}",
            f"social_position:group_belonging:{scene.group_belonging}",
            *(
                f"social_position:status_relation:{value}"
                for value in scene.status_relations
            ),
        )


class InstinktLongitudinalBodySignal(FrozenArtifactModel):
    """Exact selected-rollout body transition and recovery signal."""

    schema_version: Literal["rei-c6-instinkt-longitudinal-body-signal-v1"] = (
        "rei-c6-instinkt-longitudinal-body-signal-v1"
    )
    signal_id: NonEmptyId
    source_measure_id: NonEmptyId
    source_measure_hash: HashDigest
    source_bundle_id: NonEmptyId
    source_bundle_hash: HashDigest
    selected_rollout: InstinktOptionRollout
    selected_rollout_hash: HashDigest
    body_before: BodyState
    body_before_hash: HashDigest
    predicted_body_after: BodyState
    predicted_body_after_hash: HashDigest
    predicted_recoverability: Annotated[
        float, Field(ge=0.0, le=1.0, allow_inf_nan=False)
    ]
    measured_outcome_update: InstinktOutcomeUpdate | None = None
    measured_outcome_update_hash: HashDigest | None = None
    epistemic_status: Literal["predicted_rollout", "measured_outcome"]
    signal_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        rollout: InstinktOptionRollout,
        measured_outcome_update: InstinktOutcomeUpdate | None = None,
    ) -> "InstinktLongitudinalBodySignal":
        if measured_outcome_update is not None:
            raise ValueError(
                "C6 v1 measured body signals require a full C5 replay context"
            )
        measure = _cold_revalidate(measure)  # type: ignore[assignment]
        bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
        rollout = _cold_revalidate(rollout)  # type: ignore[assignment]
        if measured_outcome_update is not None:
            measured_outcome_update = _cold_revalidate(  # type: ignore[assignment]
                measured_outcome_update
            )
        _validate_lineage(measure, bundle)
        body_before = rollout.trajectory[0]
        predicted_body_after = rollout.trajectory[-1]
        base = {
            "schema_version": "rei-c6-instinkt-longitudinal-body-signal-v1",
            "source_measure_id": measure.measure_id,
            "source_measure_hash": measure.measure_hash,
            "source_bundle_id": bundle.bundle_id,
            "source_bundle_hash": bundle.immutable_hash,
            "selected_rollout": rollout,
            "selected_rollout_hash": rollout.content_hash(),
            "body_before": body_before,
            "body_before_hash": body_before.content_hash(),
            "predicted_body_after": predicted_body_after,
            "predicted_body_after_hash": predicted_body_after.content_hash(),
            "predicted_recoverability": rollout.recoverability,
            "measured_outcome_update": measured_outcome_update,
            "measured_outcome_update_hash": (
                None
                if measured_outcome_update is None
                else measured_outcome_update.update_hash
            ),
            "epistemic_status": (
                "measured_outcome"
                if measured_outcome_update is not None
                else "predicted_rollout"
            ),
        }
        signal_id = content_id("c6_instinkt_body_signal", base)
        payload = {"signal_id": signal_id, **base}
        return cls(**payload, signal_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_signal(self) -> Self:
        if self.measured_outcome_update is not None:
            raise ValueError(
                "C6 v1 measured body signals require a full C5 replay context"
            )
        rollout = _cold_revalidate(self.selected_rollout)
        body_before = _cold_revalidate(self.body_before)
        predicted_body_after = _cold_revalidate(self.predicted_body_after)
        if (
            self.selected_rollout_hash != rollout.content_hash()
            or self.body_before_hash != body_before.content_hash()
            or self.predicted_body_after_hash != predicted_body_after.content_hash()
            or self.body_before != rollout.trajectory[0]
            or self.predicted_body_after != rollout.trajectory[-1]
            or self.predicted_recoverability != rollout.recoverability
        ):
            raise ValueError("C6 body signal differs from selected-rollout replay")
        if (self.measured_outcome_update is None) != (
            self.measured_outcome_update_hash is None
        ):
            raise ValueError("C6 measured outcome update ID/hash must be paired")
        expected_status = (
            "measured_outcome"
            if self.measured_outcome_update is not None
            else "predicted_rollout"
        )
        if self.epistemic_status != expected_status:
            raise ValueError("C6 body signal epistemic status differs from evidence")
        if self.measured_outcome_update is not None:
            measured = _cold_revalidate(self.measured_outcome_update)
            if (
                self.measured_outcome_update_hash != measured.update_hash
                or measured.source_rollout_id != rollout.rollout_id
                or measured.source_rollout_hash != rollout.rollout_hash
                or measured.source_body_state_id != self.body_before.body_state_id
                or measured.source_body_state_hash != self.body_before_hash
            ):
                raise ValueError("C6 measured outcome sidecar differs from rollout lineage")
        base = self.model_dump(
            mode="python", round_trip=True, exclude={"signal_id", "signal_hash"}
        )
        if self.signal_id != content_id("c6_instinkt_body_signal", base):
            raise ValueError("C6 body signal ID differs from its content")
        payload = {"signal_id": self.signal_id, **base}
        if self.signal_hash != sha256_hex(payload):
            raise ValueError("C6 body signal hash differs from its content")
        return self

    def validate_against(
        self,
        *,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
    ) -> Self:
        measure = _cold_revalidate(measure)  # type: ignore[assignment]
        bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
        _validate_lineage(measure, bundle)
        conclusion = bundle.instinkt
        rollout_hashes = tuple(
            item
            for item in bundle.instinkt_rollout_hashes
            if item.artifact_id == self.selected_rollout.rollout_id
        )
        if (
            self.source_measure_id != measure.measure_id
            or self.source_measure_hash != measure.measure_hash
            or self.source_bundle_id != bundle.bundle_id
            or self.source_bundle_hash != bundle.immutable_hash
            or conclusion.decisive_rollout_id != self.selected_rollout.rollout_id
            or conclusion.decisive_rollout_option_id != self.selected_rollout.option_id
            or conclusion.option_id != self.selected_rollout.option_id
            or len(rollout_hashes) != 1
            or rollout_hashes[0].sha256 != self.selected_rollout_hash
            or bundle.instinkt_body_state_id != self.body_before.body_state_id
            or bundle.instinkt_body_state_hash != self.body_before_hash
        ):
            raise ValueError("C6 body signal lineage differs from its selected rollout")
        return self

    @property
    def body_transition_reference(self) -> str:
        return f"body_signal:{self.signal_id}:{self.signal_hash}"

    @property
    def recovery_reference(self) -> str:
        return (
            f"predicted_recoverability:{self.signal_id}:{self.signal_hash}:"
            f"{self.predicted_recoverability:.12g}"
        )

    @property
    def measured_body_after(self) -> BodyState | None:
        if self.measured_outcome_update is None:
            return None
        return self.measured_outcome_update.body_after


def _racio_derivation(
    world: RacioWorld,
    measure: EgoMeasure,
    bundle: NativeMindBundle,
    narrative: RacioSelfNarrative,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    RacioWorld,
]:
    world = _cold_revalidate(world)  # type: ignore[assignment]
    narrative = _cold_revalidate(narrative)  # type: ignore[assignment]
    _validate_lineage(measure, bundle)
    if (
        narrative.source_decision_id != measure.conscious_decision.decision_id
        or narrative.source_resultant_id != measure.behavior_resultant.resultant_id
    ):
        raise ValueError("Racio self-narrative differs from the EgoMeasure lineage")
    outcome_effects = (
        () if measure.outcome is None else measure.outcome.observed_effects
    )
    fact_additions = _stable_novel(
        world.facts,
        (*bundle.racio.facts_used, *outcome_effects),
    )
    selected = (
        "native_abstention"
        if bundle.racio.option_id is None
        else f"native_option:{bundle.racio.option_id}"
    )
    belief_additions = _stable_novel(world.explicit_beliefs, (selected,))
    narrative_hash = narrative.narrative_hash or narrative.content_hash()
    self_narrative_additions = _stable_novel(
        (*world.explicit_beliefs, *belief_additions),
        (f"self_narrative:{narrative.narrative_id}:{narrative_hash}",),
    )
    causal_additions = _stable_novel(
        world.rules,
        tuple(f"causal_link:{value}" for value in bundle.racio.causal_sequence),
    )
    timeline_candidates = [f"event:{measure.event_id}"]
    if measure.outcome is not None:
        timeline_candidates.append(f"outcome:{measure.outcome.outcome_id}")
    timeline_additions = _stable_novel(
        world.timelines,
        tuple(timeline_candidates),
    )
    commitment_candidates: tuple[str, ...] = ()
    if (
        measure.conscious_decision.decision_status == "committed"
        and measure.conscious_decision.option_id is not None
    ):
        commitment_candidates = (
            f"conscious_option:{measure.conscious_decision.option_id}",
        )
    commitment_additions = _stable_novel(
        world.commitments,
        commitment_candidates,
    )
    base = {
        "schema_version": "rei-native-racio-world-v1",
        "explicit_beliefs": _stable_union(
            world.explicit_beliefs,
            (*belief_additions, *self_narrative_additions),
        ),
        "facts": _stable_union(world.facts, fact_additions),
        "rules": _stable_union(world.rules, causal_additions),
        "timelines": _stable_union(world.timelines, timeline_additions),
        "commitments": _stable_union(world.commitments, commitment_additions),
    }
    updated = RacioWorld(world_id=content_id("racio_world", base), **base)
    return (
        fact_additions,
        belief_additions,
        causal_additions,
        timeline_additions,
        commitment_additions,
        self_narrative_additions,
        updated,
    )


def _emocio_derivation(
    world: EmocioWorld,
    measure: EgoMeasure,
    bundle: NativeMindBundle,
    visual_signal: EmocioLongitudinalVisualSignal,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    EmocioWorld,
]:
    world = _cold_revalidate(world)  # type: ignore[assignment]
    _validate_lineage(measure, bundle)
    visual_signal.validate_against(
        measure=measure,
        bundle=bundle,
        visual_state=visual_signal.source_visual_state,
    )
    conclusion = bundle.emocio
    visual_additions = _stable_novel(
        world.visual_memories,
        (visual_signal.world_memory_reference,),
    )
    desired_additions = _stable_novel(
        world.desired_scenes,
        (conclusion.desired_scene_id, conclusion.desired_transformation),
    )
    broken_additions = _stable_novel(
        world.broken_scenes,
        (conclusion.main_obstacle,),
    )
    # Social position is copied only from the exact structured current-scene
    # layout.  The embedding remains an internal identity/provenance feature
    # and is never interpreted as social evidence.
    social_additions = _stable_novel(
        world.social_identity_motifs,
        visual_signal.social_position_references,
    )
    attraction_candidates = [f"action_tendency:{conclusion.action_tendency}"]
    if conclusion.option_id is not None:
        attraction_candidates.append(f"native_option:{conclusion.option_id}")
    attraction_additions = _stable_novel(
        world.attraction_patterns,
        tuple(attraction_candidates),
    )
    motor_candidates = [f"behavior:{measure.behavior_resultant.predicted_action}"]
    if measure.outcome is not None:
        motor_candidates.extend(
            f"outcome:{effect}" for effect in measure.outcome.observed_effects
        )
    motor_additions = _stable_novel(world.motor_patterns, tuple(motor_candidates))
    base = {
        "schema_version": "rei-native-emocio-world-v1",
        "visual_memories": _stable_union(world.visual_memories, visual_additions),
        "desired_scenes": _stable_union(world.desired_scenes, desired_additions),
        "broken_scenes": _stable_union(world.broken_scenes, broken_additions),
        "social_identity_motifs": _stable_union(
            world.social_identity_motifs,
            social_additions,
        ),
        "attraction_patterns": _stable_union(
            world.attraction_patterns,
            attraction_additions,
        ),
        "motor_patterns": _stable_union(world.motor_patterns, motor_additions),
    }
    updated = EmocioWorld(world_id=content_id("emocio_world", base), **base)
    return (
        visual_additions,
        desired_additions,
        broken_additions,
        social_additions,
        attraction_additions,
        motor_additions,
        updated,
    )


def _instinkt_derivation(
    world: InstinktWorld,
    measure: EgoMeasure,
    bundle: NativeMindBundle,
    body_signal: InstinktLongitudinalBodySignal,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    InstinktWorld,
]:
    world = _cold_revalidate(world)  # type: ignore[assignment]
    _validate_lineage(measure, bundle)
    body_signal.validate_against(measure=measure, bundle=bundle)
    conclusion = bundle.instinkt
    # C5 owns exact materialized association closure.  C6 must never place an
    # opaque event/alarm string in that index without an InstinktAssociation.
    association_additions: tuple[str, ...] = ()
    # Prediction-only recovery remains an explicit audit delta. It must not be
    # promoted into learned/trusted Instinkt world state without C5 evidence.
    recovery_additions = (body_signal.recovery_reference,)
    trusted_additions: tuple[str, ...] = ()
    threat_additions = _stable_novel(
        world.threat_patterns,
        (conclusion.dominant_alarm, *conclusion.danger_claims),
    )
    attachment_additions = _stable_novel(
        world.attachment_objects,
        conclusion.protected_targets,
    )
    loss_additions: tuple[str, ...] = ()
    boundary_additions = _stable_novel(
        world.boundary_patterns,
        (f"minimum_safety:{conclusion.minimum_safety_condition}",),
    )
    base = {
        "schema_version": "rei-native-instinkt-world-v1",
        "associations": _stable_union(world.associations, association_additions),
        "trusted_patterns": _stable_union(world.trusted_patterns, trusted_additions),
        "threat_patterns": _stable_union(world.threat_patterns, threat_additions),
        "attachment_objects": _stable_union(
            world.attachment_objects,
            attachment_additions,
        ),
        "unresolved_losses": _stable_union(
            world.unresolved_losses,
            loss_additions,
        ),
        "boundary_patterns": _stable_union(
            world.boundary_patterns,
            boundary_additions,
        ),
    }
    updated = InstinktWorld(world_id=content_id("instinkt_world", base), **base)
    return (
        association_additions,
        trusted_additions,
        threat_additions,
        attachment_additions,
        loss_additions,
        boundary_additions,
        recovery_additions,
        updated,
    )


class RacioWorldUpdate(FrozenArtifactModel):
    schema_version: Literal["rei-racio-world-update-v2"] = "rei-racio-world-update-v2"
    update_id: NonEmptyId
    source_world: RacioWorld
    source_measure: EgoMeasure
    source_bundle: NativeMindBundle
    source_narrative: RacioSelfNarrative
    source_narrative_hash: HashDigest
    fact_additions: tuple[NonEmptyText, ...]
    explicit_belief_additions: tuple[NonEmptyText, ...]
    causal_link_additions: tuple[NonEmptyText, ...]
    timeline_additions: tuple[NonEmptyText, ...]
    commitment_additions: tuple[NonEmptyText, ...]
    self_narrative_additions: tuple[NonEmptyText, ...]
    updated_world: RacioWorld
    update_hash: HashDigest

    @classmethod
    def create(
        cls,
        world: RacioWorld,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        narrative: RacioSelfNarrative,
    ) -> "RacioWorldUpdate":
        world = _cold_revalidate(world)  # type: ignore[assignment]
        measure = _cold_revalidate(measure)  # type: ignore[assignment]
        bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
        narrative = _cold_revalidate(narrative)  # type: ignore[assignment]
        values = _racio_derivation(world, measure, bundle, narrative)
        base = {
            "schema_version": "rei-racio-world-update-v2",
            "source_world": world,
            "source_measure": measure,
            "source_bundle": bundle,
            "source_narrative": narrative,
            "source_narrative_hash": narrative.narrative_hash
            or narrative.content_hash(),
            "fact_additions": values[0],
            "explicit_belief_additions": values[1],
            "causal_link_additions": values[2],
            "timeline_additions": values[3],
            "commitment_additions": values[4],
            "self_narrative_additions": values[5],
            "updated_world": values[6],
        }
        update_id = content_id("racio_world_update", base)
        payload = {"update_id": update_id, **base}
        return cls(**payload, update_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        expected = _racio_derivation(
            self.source_world,
            self.source_measure,
            self.source_bundle,
            self.source_narrative,
        )
        actual = (
            self.fact_additions,
            self.explicit_belief_additions,
            self.causal_link_additions,
            self.timeline_additions,
            self.commitment_additions,
            self.self_narrative_additions,
            self.updated_world,
        )
        if self.source_narrative_hash != (
            self.source_narrative.narrative_hash
            or self.source_narrative.content_hash()
        ):
            raise ValueError("Racio world update narrative hash differs")
        _validate_update_identity(self, "racio_world_update", actual == expected)
        return self


class EmocioWorldUpdate(FrozenArtifactModel):
    schema_version: Literal["rei-emocio-world-update-v2"] = "rei-emocio-world-update-v2"
    update_id: NonEmptyId
    source_world: EmocioWorld
    source_measure: EgoMeasure
    source_bundle: NativeMindBundle
    visual_signal: EmocioLongitudinalVisualSignal
    visual_memory_additions: tuple[NonEmptyText, ...]
    desired_scene_additions: tuple[NonEmptyText, ...]
    broken_scene_additions: tuple[NonEmptyText, ...]
    social_identity_motif_additions: tuple[NonEmptyText, ...]
    attraction_pattern_additions: tuple[NonEmptyText, ...]
    motor_pattern_additions: tuple[NonEmptyText, ...]
    updated_world: EmocioWorld
    update_hash: HashDigest

    @classmethod
    def create(
        cls,
        world: EmocioWorld,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        visual_signal: EmocioLongitudinalVisualSignal,
        artifact_store: ArtifactStore,
    ) -> "EmocioWorldUpdate":
        world = _cold_revalidate(world)  # type: ignore[assignment]
        measure = _cold_revalidate(measure)  # type: ignore[assignment]
        bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
        visual_signal = _cold_revalidate(visual_signal)  # type: ignore[assignment]
        visual_signal.validate_stored_bytes(artifact_store)
        values = _emocio_derivation(world, measure, bundle, visual_signal)
        base = {
            "schema_version": "rei-emocio-world-update-v2",
            "source_world": world,
            "source_measure": measure,
            "source_bundle": bundle,
            "visual_signal": visual_signal,
            "visual_memory_additions": values[0],
            "desired_scene_additions": values[1],
            "broken_scene_additions": values[2],
            "social_identity_motif_additions": values[3],
            "attraction_pattern_additions": values[4],
            "motor_pattern_additions": values[5],
            "updated_world": values[6],
        }
        update_id = content_id("emocio_world_update", base)
        payload = {"update_id": update_id, **base}
        return cls(**payload, update_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        expected = _emocio_derivation(
            self.source_world,
            self.source_measure,
            self.source_bundle,
            self.visual_signal,
        )
        actual = (
            self.visual_memory_additions,
            self.desired_scene_additions,
            self.broken_scene_additions,
            self.social_identity_motif_additions,
            self.attraction_pattern_additions,
            self.motor_pattern_additions,
            self.updated_world,
        )
        _validate_update_identity(self, "emocio_world_update", actual == expected)
        return self


class InstinktWorldUpdate(FrozenArtifactModel):
    schema_version: Literal["rei-instinkt-world-update-v2"] = (
        "rei-instinkt-world-update-v2"
    )
    update_id: NonEmptyId
    source_world: InstinktWorld
    source_measure: EgoMeasure
    source_bundle: NativeMindBundle
    body_signal: InstinktLongitudinalBodySignal
    body_before: BodyState
    predicted_body_after: BodyState
    predicted_recoverability: Annotated[
        float, Field(ge=0.0, le=1.0, allow_inf_nan=False)
    ]
    measured_body_after: BodyState | None = None
    association_additions: tuple[NonEmptyText, ...]
    trusted_pattern_additions: tuple[NonEmptyText, ...]
    threat_pattern_additions: tuple[NonEmptyText, ...]
    attachment_object_additions: tuple[NonEmptyText, ...]
    unresolved_loss_additions: tuple[NonEmptyText, ...]
    boundary_pattern_additions: tuple[NonEmptyText, ...]
    recovery_pattern_additions: tuple[NonEmptyText, ...]
    updated_world: InstinktWorld
    update_hash: HashDigest

    @classmethod
    def create(
        cls,
        world: InstinktWorld,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        body_signal: InstinktLongitudinalBodySignal,
    ) -> "InstinktWorldUpdate":
        world = _cold_revalidate(world)  # type: ignore[assignment]
        measure = _cold_revalidate(measure)  # type: ignore[assignment]
        bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
        body_signal = _cold_revalidate(body_signal)  # type: ignore[assignment]
        values = _instinkt_derivation(world, measure, bundle, body_signal)
        base = {
            "schema_version": "rei-instinkt-world-update-v2",
            "source_world": world,
            "source_measure": measure,
            "source_bundle": bundle,
            "body_signal": body_signal,
            "body_before": body_signal.body_before,
            "predicted_body_after": body_signal.predicted_body_after,
            "predicted_recoverability": body_signal.predicted_recoverability,
            "measured_body_after": body_signal.measured_body_after,
            "association_additions": values[0],
            "trusted_pattern_additions": values[1],
            "threat_pattern_additions": values[2],
            "attachment_object_additions": values[3],
            "unresolved_loss_additions": values[4],
            "boundary_pattern_additions": values[5],
            "recovery_pattern_additions": values[6],
            "updated_world": values[7],
        }
        update_id = content_id("instinkt_world_update", base)
        payload = {"update_id": update_id, **base}
        return cls(**payload, update_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        expected = _instinkt_derivation(
            self.source_world,
            self.source_measure,
            self.source_bundle,
            self.body_signal,
        )
        actual = (
            self.association_additions,
            self.trusted_pattern_additions,
            self.threat_pattern_additions,
            self.attachment_object_additions,
            self.unresolved_loss_additions,
            self.boundary_pattern_additions,
            self.recovery_pattern_additions,
            self.updated_world,
        )
        if (
            self.body_before != self.body_signal.body_before
            or self.predicted_body_after != self.body_signal.predicted_body_after
            or self.predicted_recoverability
            != self.body_signal.predicted_recoverability
            or self.measured_body_after != self.body_signal.measured_body_after
        ):
            raise ValueError("Instinkt world update body/recovery fields diverge")
        _validate_update_identity(self, "instinkt_world_update", actual == expected)
        return self


def _validate_update_identity(
    update: RacioWorldUpdate | EmocioWorldUpdate | InstinktWorldUpdate,
    prefix: str,
    semantic_match: bool,
) -> None:
    if not semantic_match:
        raise ValueError("World update differs from deterministic modality replay")
    base = update.model_dump(
        mode="python",
        round_trip=True,
        exclude={"update_id", "update_hash"},
    )
    if update.update_id != content_id(prefix, base):
        raise ValueError("World update ID differs from its content")
    payload = {"update_id": update.update_id, **base}
    if update.update_hash != sha256_hex(payload):
        raise ValueError("World update hash differs from its content")


@dataclass(frozen=True, slots=True)
class RacioWorldUpdater:
    def update(
        self,
        world: RacioWorld,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        narrative: RacioSelfNarrative,
    ) -> RacioWorldUpdate:
        return RacioWorldUpdate.create(world, measure, bundle, narrative)


@dataclass(frozen=True, slots=True)
class EmocioWorldUpdater:
    def update(
        self,
        world: EmocioWorld,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        visual_signal: EmocioLongitudinalVisualSignal,
        artifact_store: ArtifactStore,
    ) -> EmocioWorldUpdate:
        return EmocioWorldUpdate.create(
            world,
            measure,
            bundle,
            visual_signal,
            artifact_store,
        )


@dataclass(frozen=True, slots=True)
class InstinktWorldUpdater:
    def update(
        self,
        world: InstinktWorld,
        measure: EgoMeasure,
        bundle: NativeMindBundle,
        body_signal: InstinktLongitudinalBodySignal,
    ) -> InstinktWorldUpdate:
        return InstinktWorldUpdate.create(world, measure, bundle, body_signal)


__all__ = [
    "EmocioLongitudinalVisualSignal",
    "EmocioWorldUpdate",
    "EmocioWorldUpdater",
    "InstinktLongitudinalBodySignal",
    "InstinktWorldUpdate",
    "InstinktWorldUpdater",
    "RacioWorldUpdate",
    "RacioWorldUpdater",
]
