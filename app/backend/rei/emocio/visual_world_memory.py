"""Typed internal visual-world memory with replayable valuation lineage.

Visual-world memory retains only similarities already produced by the narrow
visual valuation pipeline.  Generated images and embeddings never extend
external facts, and semantic meaning is copied only from structured scene
fields.  The module remains independent from the processor and engine.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self, TypeVar

from pydantic import Field, model_validator

from ..ids import content_id
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    Score01,
)
from ..models.ego import OutcomeRecord
from ..models.emocio import (
    AttentionWeight,
    EmocioSceneKind,
    EmocioVisualState,
    VerifiedVisualEmbeddingArtifact,
    VisualSceneSpec,
)
from ..providers.protocols import VerifiedImageEncoding
from .visual_valuation import (
    BoundVisualEmbedding,
    VisualCosineComparison,
    VisualValuationResult,
)


VisualWorldMemoryOutcomeStatus = Literal[
    "observed_positive",
    "observed_negative",
    "mixed",
    "unknown",
]
MemoryComparisonKind = Literal[
    "rollout_to_desired",
    "rollout_to_broken",
]
CosineValue = Annotated[
    float,
    Field(ge=-1.0, le=1.0, allow_inf_nan=False),
]
ModelT = TypeVar("ModelT", bound=FrozenModel)


def _canonical_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _require_canonical_strings(values: tuple[str, ...], field_name: str) -> None:
    if values != _canonical_strings(values):
        raise ValueError(f"{field_name} must be sorted and unique")


def _revalidate(model: ModelT) -> ModelT:
    """Replay validators even when the caller used ``model_copy``."""

    return type(model).model_validate(
        model.model_dump(mode="python", round_trip=True)
    )


class StructuredSocialMeaning(FrozenModel):
    """Social meaning copied only from explicit structured scene fields."""

    source: Literal["visual_scene_spec_structured_fields"] = (
        "visual_scene_spec_structured_fields"
    )
    entities: tuple[str, ...]
    self_position: str
    attention_structure: tuple[AttentionWeight, ...]
    group_belonging: str
    status_relations: tuple[str, ...]
    attraction_markers: tuple[str, ...]

    @classmethod
    def from_scene_spec(cls, scene_spec: VisualSceneSpec) -> Self:
        return cls(
            entities=_canonical_strings(scene_spec.entities),
            self_position=scene_spec.self_position,
            attention_structure=tuple(
                sorted(scene_spec.attention_structure, key=lambda item: item.target)
            ),
            group_belonging=scene_spec.group_belonging,
            status_relations=_canonical_strings(scene_spec.status_relations),
            attraction_markers=_canonical_strings(scene_spec.attraction_markers),
        )

    @model_validator(mode="after")
    def validate_canonical_order(self) -> Self:
        _require_canonical_strings(self.entities, "social meaning entities")
        _require_canonical_strings(
            self.status_relations,
            "social meaning status_relations",
        )
        _require_canonical_strings(
            self.attraction_markers,
            "social meaning attraction_markers",
        )
        attention_targets = tuple(item.target for item in self.attention_structure)
        if attention_targets != tuple(sorted(set(attention_targets))):
            raise ValueError(
                "social meaning attention_structure must use unique canonical targets"
            )
        return self


class StructuredMotorPattern(FrozenModel):
    """Motor pattern copied only from explicit structured scene fields."""

    source: Literal["visual_scene_spec_structured_fields"] = (
        "visual_scene_spec_structured_fields"
    )
    movement: tuple[str, ...]
    obstacle_markers: tuple[str, ...]

    @classmethod
    def from_scene_spec(cls, scene_spec: VisualSceneSpec) -> Self:
        return cls(
            movement=_canonical_strings(scene_spec.movement),
            obstacle_markers=_canonical_strings(scene_spec.obstacle_markers),
        )

    @model_validator(mode="after")
    def validate_canonical_order(self) -> Self:
        _require_canonical_strings(self.movement, "motor pattern movement")
        _require_canonical_strings(
            self.obstacle_markers,
            "motor pattern obstacle_markers",
        )
        return self


class VisualWorldMemoryComparisonLink(FrozenModel):
    """Exact narrow comparison selected for one rollout observation."""

    kind: MemoryComparisonKind
    comparison_id: NonEmptyId
    comparison_hash: HashDigest
    option_id: NonEmptyId
    left_observation_id: NonEmptyId
    right_observation_id: NonEmptyId
    cosine: CosineValue
    normalized_similarity: Score01
    normalized_separation: Score01

    @classmethod
    def from_comparison(
        cls,
        comparison: VisualCosineComparison,
    ) -> Self:
        if comparison.kind not in {
            "rollout_to_desired",
            "rollout_to_broken",
        }:
            raise ValueError(
                "Visual-world memory accepts only desired/broken rollout comparisons"
            )
        if comparison.option_id is None:
            raise ValueError("Visual-world memory comparison requires an option ID")
        return cls(
            kind=comparison.kind,
            comparison_id=comparison.comparison_id,
            comparison_hash=comparison.content_hash(),
            option_id=comparison.option_id,
            left_observation_id=comparison.left_observation_id,
            right_observation_id=comparison.right_observation_id,
            cosine=comparison.cosine,
            normalized_similarity=comparison.normalized_similarity,
            normalized_separation=comparison.normalized_separation,
        )

    def validate_against(self, comparison: VisualCosineComparison) -> Self:
        validated = _revalidate(comparison)
        expected = type(self).from_comparison(validated)
        if self != expected:
            raise ValueError(
                "Visual-world memory comparison differs from visual valuation"
            )
        return self


class VisualWorldMemoryOutcomeLink(FrozenModel):
    """Reserved future link requiring typed execution/decision association."""

    outcome_id: NonEmptyId
    event_id: NonEmptyId
    outcome_record_hash: HashDigest
    status: VisualWorldMemoryOutcomeStatus

    @classmethod
    def from_outcome(
        cls,
        outcome: OutcomeRecord,
        *,
        status: VisualWorldMemoryOutcomeStatus,
    ) -> Self:
        validated = _revalidate(outcome)
        return cls(
            outcome_id=validated.outcome_id,
            event_id=validated.event_id,
            outcome_record_hash=validated.content_hash(),
            status=status,
        )

    def validate_against(self, outcome: OutcomeRecord) -> Self:
        validated = _revalidate(outcome)
        if self.outcome_id != validated.outcome_id:
            raise ValueError("Visual-world memory cites another outcome ID")
        if self.event_id != validated.event_id:
            raise ValueError("Visual-world memory cites another outcome event")
        if self.outcome_record_hash != validated.content_hash():
            raise ValueError("Visual-world memory outcome hash differs from its record")
        return self


class VisualWorldMemoryRecord(FrozenArtifactModel):
    """Content-addressed internal memory of one hypothetical rollout."""

    schema_version: Literal["rei-native-visual-world-memory-v2"] = (
        "rei-native-visual-world-memory-v2"
    )
    memory_id: NonEmptyId

    visual_valuation_result_id: NonEmptyId
    visual_valuation_result_hash: HashDigest
    observation_id: NonEmptyId
    observation_hash: HashDigest
    evaluation_seed: int

    source_scene_spec_id: NonEmptyId
    source_scene_spec_hash: HashDigest
    scene_kind: EmocioSceneKind
    option_id: NonEmptyId

    image_artifact_id: NonEmptyId
    image_artifact_hash: HashDigest
    image_content_sha256: HashDigest

    encoding_id: NonEmptyId
    encoding_hash: HashDigest
    embedding_source_artifact_id: NonEmptyId
    embedding_artifact_hash: HashDigest
    vector_hash: HashDigest

    desired_comparison: VisualWorldMemoryComparisonLink
    broken_comparison: VisualWorldMemoryComparisonLink
    outcome: VisualWorldMemoryOutcomeLink | None = None

    social_meaning: StructuredSocialMeaning
    motor_pattern: StructuredMotorPattern

    internal_only: Literal[True] = True
    external_fact_boundary: Literal[
        "generated_images_never_extend_external_facts"
    ] = "generated_images_never_extend_external_facts"
    embedding_semantic_interpretation: Literal["none"] = "none"

    @property
    def desired_similarity(self) -> float:
        return self.desired_comparison.normalized_similarity

    @property
    def broken_similarity(self) -> float:
        return self.broken_comparison.normalized_similarity

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.outcome is not None:
            raise ValueError(
                "Visual-world rollout memory forbids observed outcomes until "
                "typed execution/decision association is implemented"
            )
        if self.scene_kind != "option_rollout":
            raise ValueError(
                "Visual-world memory accepts only option-rollout observations"
            )
        if self.embedding_source_artifact_id != self.image_artifact_id:
            raise ValueError(
                "Visual-world memory embedding must cite its recorded image"
            )
        expected_comparisons = (
            (self.desired_comparison, "rollout_to_desired"),
            (self.broken_comparison, "rollout_to_broken"),
        )
        for comparison, expected_kind in expected_comparisons:
            if comparison.kind != expected_kind:
                raise ValueError(
                    "Visual-world memory comparison occupies another target slot"
                )
            if (
                comparison.option_id != self.option_id
                or comparison.left_observation_id != self.observation_id
            ):
                raise ValueError(
                    "Visual-world memory comparison cites another observation"
                )
        if (
            self.desired_comparison.comparison_id
            == self.broken_comparison.comparison_id
        ):
            raise ValueError(
                "Desired and broken visual-world comparisons must be distinct"
            )
        self._require_content_id()
        return self

    def _require_content_id(self) -> None:
        expected_id = content_id(
            "visual_world_memory",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"memory_id"},
            ),
        )
        if self.memory_id != expected_id:
            raise ValueError(
                "Visual-world memory ID differs from its canonical content"
            )

    def validate_against(
        self,
        *,
        observation: BoundVisualEmbedding,
        valuation: VisualValuationResult,
        visual_state: EmocioVisualState,
        observations: tuple[BoundVisualEmbedding, ...],
        outcome: OutcomeRecord | None = None,
        outcome_status: VisualWorldMemoryOutcomeStatus | None = None,
    ) -> Self:
        """Replay the valuation and close every stored source reference."""

        sources = _resolve_memory_sources(
            observation=observation,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )
        expected = _memory_payload(
            observation=sources.observation,
            valuation=sources.valuation,
            desired_comparison=sources.desired_comparison,
            broken_comparison=sources.broken_comparison,
            outcome=outcome,
            outcome_status=outcome_status,
        )

        if (
            self.visual_valuation_result_id
            != expected["visual_valuation_result_id"]
            or self.visual_valuation_result_hash
            != expected["visual_valuation_result_hash"]
        ):
            raise ValueError(
                "Visual-world memory valuation lineage differs from its result"
            )
        if (
            self.observation_id != expected["observation_id"]
            or self.observation_hash != expected["observation_hash"]
            or self.evaluation_seed != expected["evaluation_seed"]
        ):
            raise ValueError(
                "Visual-world memory observation lineage differs from its source"
            )
        if (
            self.source_scene_spec_id != expected["source_scene_spec_id"]
            or self.source_scene_spec_hash != expected["source_scene_spec_hash"]
            or self.scene_kind != expected["scene_kind"]
            or self.option_id != expected["option_id"]
        ):
            raise ValueError(
                "Visual-world memory scene-spec lineage differs from its source"
            )
        if (
            self.image_artifact_id != expected["image_artifact_id"]
            or self.image_artifact_hash != expected["image_artifact_hash"]
            or self.image_content_sha256 != expected["image_content_sha256"]
        ):
            raise ValueError(
                "Visual-world memory image lineage differs from its source"
            )
        if (
            self.encoding_id != expected["encoding_id"]
            or self.encoding_hash != expected["encoding_hash"]
            or self.embedding_source_artifact_id
            != expected["embedding_source_artifact_id"]
            or self.embedding_artifact_hash
            != expected["embedding_artifact_hash"]
            or self.vector_hash != expected["vector_hash"]
        ):
            raise ValueError(
                "Visual-world memory encoding lineage differs from its source"
            )
        if (
            self.desired_comparison != expected["desired_comparison"]
            or self.broken_comparison != expected["broken_comparison"]
        ):
            raise ValueError(
                "Visual-world memory comparison lineage differs from its result"
            )
        self.desired_comparison.validate_against(sources.desired_comparison)
        self.broken_comparison.validate_against(sources.broken_comparison)

        if self.social_meaning != expected["social_meaning"]:
            raise ValueError(
                "Visual-world memory social meaning differs from "
                "structured scene fields"
            )
        if self.motor_pattern != expected["motor_pattern"]:
            raise ValueError(
                "Visual-world memory motor pattern differs from structured scene fields"
            )
        if self.outcome != expected["outcome"]:
            raise ValueError(
                "Visual-world memory outcome lineage or status differs from its source"
            )
        if self.outcome is not None and outcome is not None:
            self.outcome.validate_against(outcome)
        if (
            self.internal_only != expected["internal_only"]
            or self.external_fact_boundary != expected["external_fact_boundary"]
            or self.embedding_semantic_interpretation
            != expected["embedding_semantic_interpretation"]
        ):
            raise ValueError("Visual-world memory external-fact boundary was altered")

        # ``model_copy`` deliberately bypasses Pydantic validation; repeat the
        # content-address check here so post-construction tampering fails closed.
        self._require_content_id()
        return self


class _ResolvedMemorySources(FrozenModel):
    observation: BoundVisualEmbedding
    valuation: VisualValuationResult
    desired_comparison: VisualCosineComparison
    broken_comparison: VisualCosineComparison


def _one_target_comparison(
    *,
    valuation: VisualValuationResult,
    observation: BoundVisualEmbedding,
    kind: MemoryComparisonKind,
) -> VisualCosineComparison:
    matches = tuple(
        comparison
        for comparison in valuation.comparisons
        if comparison.kind == kind
        and comparison.option_id == observation.scene_spec.option_id
        and comparison.left_observation_id == observation.observation_id
    )
    if len(matches) != 1:
        raise ValueError(
            "Visual-world memory requires exactly one "
            f"{kind} comparison for its rollout observation"
        )
    return _revalidate(matches[0])


def _resolve_memory_sources(
    *,
    observation: BoundVisualEmbedding,
    valuation: VisualValuationResult,
    visual_state: EmocioVisualState,
    observations: tuple[BoundVisualEmbedding, ...],
) -> _ResolvedMemorySources:
    validated_valuation = _revalidate(valuation)
    validated_valuation.validate_against(
        visual_state=visual_state,
        observations=observations,
        include_cross_seed_consistency=None,
    )
    validated_observations = tuple(_revalidate(item) for item in observations)
    validated_observation = _revalidate(observation)
    matching_observations = tuple(
        item
        for item in validated_observations
        if item.observation_id == validated_observation.observation_id
    )
    if (
        len(matching_observations) != 1
        or matching_observations[0] != validated_observation
        or matching_observations[0].content_hash()
        != validated_observation.content_hash()
    ):
        raise ValueError(
            "Selected visual-world observation is not an exact replay-set member"
        )
    if validated_observation.role != "option_rollout":
        raise ValueError(
            "Visual-world memory accepts only option-rollout observations"
        )
    if validated_observation.scene_spec.option_id is None:
        raise ValueError("Visual-world memory rollout requires an option ID")
    if not isinstance(
        validated_observation.embedding,
        VerifiedVisualEmbeddingArtifact,
    ):
        raise TypeError(
            "Visual-world memory requires a VerifiedVisualEmbeddingArtifact"
        )
    if not isinstance(validated_observation.encoding, VerifiedImageEncoding):
        raise TypeError("Visual-world memory requires a verified image encoding")
    if (
        validated_observation.observation_id
        not in validated_valuation.observation_ids
    ):
        raise ValueError(
            "Visual-world memory observation is outside the valuation result"
        )
    if (
        validated_valuation.encoder_identity
        != validated_observation.embedding.encoder_identity
        or validated_valuation.dimensions
        != validated_observation.embedding.dimensions
    ):
        raise ValueError(
            "Visual-world memory observation encoder differs from its valuation"
        )
    desired = _one_target_comparison(
        valuation=validated_valuation,
        observation=validated_observation,
        kind="rollout_to_desired",
    )
    broken = _one_target_comparison(
        valuation=validated_valuation,
        observation=validated_observation,
        kind="rollout_to_broken",
    )
    return _ResolvedMemorySources(
        observation=validated_observation,
        valuation=validated_valuation,
        desired_comparison=desired,
        broken_comparison=broken,
    )


def _build_outcome_link(
    outcome: OutcomeRecord | None,
    outcome_status: VisualWorldMemoryOutcomeStatus | None,
) -> VisualWorldMemoryOutcomeLink | None:
    if outcome is not None or outcome_status is not None:
        raise ValueError(
            "Visual-world rollout memory forbids outcome linkage until typed "
            "execution/decision association is implemented"
        )
    return None


def _memory_payload(
    *,
    observation: BoundVisualEmbedding,
    valuation: VisualValuationResult,
    desired_comparison: VisualCosineComparison,
    broken_comparison: VisualCosineComparison,
    outcome: OutcomeRecord | None,
    outcome_status: VisualWorldMemoryOutcomeStatus | None,
) -> dict[str, object]:
    scene_spec = observation.scene_spec
    image = observation.image
    embedding = observation.embedding
    encoding = observation.encoding
    return {
        "schema_version": "rei-native-visual-world-memory-v2",
        "visual_valuation_result_id": valuation.result_id,
        "visual_valuation_result_hash": valuation.content_hash(),
        "observation_id": observation.observation_id,
        "observation_hash": observation.content_hash(),
        "evaluation_seed": observation.evaluation_seed,
        "source_scene_spec_id": scene_spec.scene_id,
        "source_scene_spec_hash": scene_spec.content_hash(),
        "scene_kind": scene_spec.scene_kind,
        "option_id": scene_spec.option_id,
        "image_artifact_id": image.image_id,
        "image_artifact_hash": image.content_hash(),
        "image_content_sha256": image.content_sha256,
        "encoding_id": encoding.encoding_id,
        "encoding_hash": encoding.content_hash(),
        "embedding_source_artifact_id": embedding.source_artifact_id,
        "embedding_artifact_hash": embedding.content_hash(),
        "vector_hash": embedding.vector_hash,
        "desired_comparison": VisualWorldMemoryComparisonLink.from_comparison(
            desired_comparison
        ),
        "broken_comparison": VisualWorldMemoryComparisonLink.from_comparison(
            broken_comparison
        ),
        "outcome": _build_outcome_link(outcome, outcome_status),
        "social_meaning": StructuredSocialMeaning.from_scene_spec(scene_spec),
        "motor_pattern": StructuredMotorPattern.from_scene_spec(scene_spec),
        "internal_only": True,
        "external_fact_boundary": (
            "generated_images_never_extend_external_facts"
        ),
        "embedding_semantic_interpretation": "none",
    }


def build_visual_world_memory_record(
    *,
    observation: BoundVisualEmbedding,
    valuation: VisualValuationResult,
    visual_state: EmocioVisualState,
    observations: tuple[BoundVisualEmbedding, ...],
    outcome: OutcomeRecord | None = None,
    outcome_status: VisualWorldMemoryOutcomeStatus | None = None,
) -> VisualWorldMemoryRecord:
    """Build hypothetical memory only from a verified rollout valuation."""

    sources = _resolve_memory_sources(
        observation=observation,
        valuation=valuation,
        visual_state=visual_state,
        observations=observations,
    )
    payload = _memory_payload(
        observation=sources.observation,
        valuation=sources.valuation,
        desired_comparison=sources.desired_comparison,
        broken_comparison=sources.broken_comparison,
        outcome=outcome,
        outcome_status=outcome_status,
    )
    record = VisualWorldMemoryRecord(
        memory_id=content_id("visual_world_memory", payload),
        **payload,
    )
    return record.validate_against(
        observation=sources.observation,
        valuation=sources.valuation,
        visual_state=visual_state,
        observations=observations,
        outcome=outcome,
        outcome_status=outcome_status,
    )


__all__ = [
    "StructuredMotorPattern",
    "StructuredSocialMeaning",
    "VisualWorldMemoryComparisonLink",
    "VisualWorldMemoryOutcomeLink",
    "VisualWorldMemoryOutcomeStatus",
    "VisualWorldMemoryRecord",
    "build_visual_world_memory_record",
]
