"""Deterministic visual comparison and fused Emocio option valuation.

The module consumes only provenance-closed internal image embeddings.  It does
not infer, add, or expose facts about the external scene.  Integration with the
runtime processor is intentionally left to a later phase boundary.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    Score01,
)
from ..models.emocio import (
    EmocioVisualState,
    ImageArtifact,
    ImaginedVisualArtifact,
    VerifiedVisualEmbeddingArtifact,
    VisualSceneSpec,
)
from ..models.provider import ProviderIdentity
from ..models.rendering import (
    ImageRenderBatchOutcome,
    ImageRenderItemOutcome,
    ImageSourceReference,
)
from ..providers.protocols import (
    VerifiedImageEncoding,
    validate_image_render_outcome,
)
from .renderer import validate_render_batch
from .valuation import aggregate_option_valuation, value_option_rollout
from .vector_encoding import (
    canonical_l2_float32_le_vector,
    normalized_float32_le_bytes,
    verified_float32_le_vector,
)


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
NonNegativeFinite = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
CosineValue = Annotated[
    float,
    Field(ge=-1.0, le=1.0, allow_inf_nan=False),
]
VisualObservationRole = Literal[
    "current",
    "desired",
    "broken",
    "option_rollout",
]
VisualComparisonKind = Literal[
    "current_to_desired",
    "rollout_to_desired",
    "rollout_to_broken",
    "rollout_cross_seed_consistency",
    "rollout_to_rollout_action_separation",
]
VisualIntegrationDisposition = Literal[
    "usable",
    "review_tie",
    "review_action_collapse",
]
VisualUncertaintyReason = Literal[
    "desired_broken_target_ambiguity",
    "cross_seed_inconsistency",
    "cross_seed_consistency_not_requested",
]


def canonical_visual_vector_hash(vector: tuple[float, ...]) -> str:
    """Hash exact normalized float32-LE bytes shared with the image encoder."""

    _, _, digest = canonical_l2_float32_le_vector(vector)
    return digest


class ImplementationHypothesisWeight(FrozenModel):
    """One non-negative coefficient with its epistemic basis attached."""

    value: NonNegativeFinite
    basis: Literal["implementation_hypothesis"] = "implementation_hypothesis"


class VisualValuationPolicy(FrozenArtifactModel):
    """Auditable weights and deterministic diagnostic thresholds."""

    schema_version: Literal["rei-native-visual-valuation-policy-v1"] = (
        "rei-native-visual-valuation-policy-v1"
    )
    policy_id: NonEmptyId
    structured_weight: ImplementationHypothesisWeight
    desired_similarity_weight: ImplementationHypothesisWeight
    broken_avoidance_weight: ImplementationHypothesisWeight
    seed_consistency_penalty: ImplementationHypothesisWeight
    uncertainty_penalty: ImplementationHypothesisWeight
    action_collapse_epsilon: Score01 = 0.01
    selection_tie_epsilon: Score01 = 0.000001
    basis: Literal["implementation_hypothesis"] = "implementation_hypothesis"

    @classmethod
    def create(
        cls,
        *,
        structured_weight: float,
        desired_similarity_weight: float,
        broken_avoidance_weight: float,
        seed_consistency_penalty: float,
        uncertainty_penalty: float,
        action_collapse_epsilon: float = 0.01,
        selection_tie_epsilon: float = 0.000001,
    ) -> VisualValuationPolicy:
        weight = ImplementationHypothesisWeight
        payload = {
            "schema_version": "rei-native-visual-valuation-policy-v1",
            "structured_weight": weight(value=structured_weight),
            "desired_similarity_weight": weight(
                value=desired_similarity_weight
            ),
            "broken_avoidance_weight": weight(value=broken_avoidance_weight),
            "seed_consistency_penalty": weight(value=seed_consistency_penalty),
            "uncertainty_penalty": weight(value=uncertainty_penalty),
            "action_collapse_epsilon": action_collapse_epsilon,
            "selection_tie_epsilon": selection_tie_epsilon,
            "basis": "implementation_hypothesis",
        }
        return cls(
            policy_id=content_id("visual_valuation_policy", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        base_total = (
            self.structured_weight.value
            + self.desired_similarity_weight.value
            + self.broken_avoidance_weight.value
        )
        if base_total <= 0.0:
            raise ValueError("At least one positive visual base weight is required")
        expected_id = content_id(
            "visual_valuation_policy",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"policy_id"},
            ),
        )
        if self.policy_id != expected_id:
            raise ValueError(
                "Visual valuation policy ID differs from canonical content"
            )
        return self


def _validated_render_item(
    *,
    render_batch: ImageRenderBatchOutcome,
    evaluation_seed: int,
    scene_spec: VisualSceneSpec,
    image: ImageArtifact,
) -> tuple[ImageRenderBatchOutcome, ImageRenderItemOutcome]:
    """Revalidate one complete batch and select the exact direct-success item."""

    validated_batch = ImageRenderBatchOutcome.model_validate(
        render_batch.model_dump(mode="python", round_trip=True)
    )
    if validated_batch != render_batch:
        raise ValueError("Visual observation render batch changed during replay")
    if validated_batch.status != "succeeded":
        raise ValueError("Visual observations require a succeeded render batch")
    if validated_batch.root_seed != evaluation_seed:
        raise ValueError(
            "Visual observation evaluation seed differs from render batch root seed"
        )
    matches = tuple(
        item
        for item in validated_batch.items
        if item.request.source_spec_id == scene_spec.scene_id
    )
    if len(matches) != 1:
        raise ValueError(
            "Visual observation requires exactly one render item for its scene"
        )
    item = matches[0]
    if (
        item.artifact is None
        or item.call_record.status != "succeeded"
        or item.call_record.primary_status != "succeeded"
        or item.call_record.fallback is not None
    ):
        raise ValueError(
            "Visual observations require one direct successful render item"
        )
    validate_image_render_outcome(item, source_spec=scene_spec)
    if item.artifact != image or item.artifact.content_hash() != image.content_hash():
        raise ValueError(
            "Visual observation image differs from its exact render batch item"
        )
    return validated_batch, item


class BoundVisualEmbedding(FrozenArtifactModel):
    """One vector bound to its scene, image, imagination, and encoder lineage."""

    schema_version: Literal["rei-native-bound-visual-embedding-v1"] = (
        "rei-native-bound-visual-embedding-v1"
    )
    observation_id: NonEmptyId
    role: VisualObservationRole
    evaluation_seed: int
    render_batch: ImageRenderBatchOutcome
    scene_spec: VisualSceneSpec
    image: ImageArtifact
    imagined: ImaginedVisualArtifact
    encoding: VerifiedImageEncoding
    embedding: VerifiedVisualEmbeddingArtifact
    vector: tuple[FiniteFloat, ...]
    internal_only: Literal[True] = True
    external_evidence_claim: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        role: VisualObservationRole,
        evaluation_seed: int,
        render_batch: ImageRenderBatchOutcome,
        scene_spec: VisualSceneSpec,
        image: ImageArtifact,
        imagined: ImaginedVisualArtifact,
        encoding: VerifiedImageEncoding,
        vector: tuple[float, ...],
        embedding: VerifiedVisualEmbeddingArtifact | None = None,
    ) -> BoundVisualEmbedding:
        _, canonical_vector, vector_hash = canonical_l2_float32_le_vector(
            vector,
            expected_dimensions=encoding.dimensions,
        )
        if vector_hash != encoding.vector_hash:
            raise ValueError("Visual vector hash differs from image encoding")
        derived_embedding = encoding.to_visual_embedding()
        if embedding is not None and embedding != derived_embedding:
            raise ValueError(
                "Supplied visual embedding differs from the verified image encoding"
            )
        payload = {
            "schema_version": "rei-native-bound-visual-embedding-v1",
            "role": role,
            "evaluation_seed": evaluation_seed,
            "render_batch": render_batch,
            "scene_spec": scene_spec,
            "image": image,
            "imagined": imagined,
            "encoding": encoding,
            "embedding": derived_embedding,
            "vector": canonical_vector,
            "internal_only": True,
            "external_evidence_claim": False,
        }
        return cls(
            observation_id=content_id("visual_observation", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_lineage_and_vector(self) -> Self:
        if self.role != self.scene_spec.scene_kind:
            raise ValueError("Visual observation role differs from its scene kind")
        _validated_render_item(
            render_batch=self.render_batch,
            evaluation_seed=self.evaluation_seed,
            scene_spec=self.scene_spec,
            image=self.image,
        )
        self.imagined.validate_against(self.image, self.scene_spec)
        # Re-run every nested provenance validator explicitly.  ``model_copy`` can
        # otherwise construct a forged nested model without executing its own
        # validators before this enclosing artifact is replay-validated.
        self.encoding.request.validate_request()
        self.encoding.call_spec.validate_call_spec()
        self.encoding.call.validate_call_record()
        self.encoding.validate_lineage()
        self.encoding.request.validate_image(self.image)
        if self.encoding.call_spec.input_artifact_ids != (self.image.image_id,):
            raise ValueError(
                "Image encoding call must cite exactly its source image input"
            )
        if self.encoding.call.input_artifact_ids != (self.image.image_id,):
            raise ValueError(
                "Image encoding record must cite exactly its source image input"
            )
        if self.encoding.call.output_artifact_ids != (self.encoding.encoding_id,):
            raise ValueError(
                "Image encoding call must publish exactly its encoding artifact"
            )
        if (
            self.encoding.call_spec.fallback_policy.mode != "none"
            or self.encoding.call.fallback is not None
            or self.encoding.call.status != "succeeded"
            or self.encoding.call.primary_status != "succeeded"
        ):
            raise ValueError(
                "Bound visual embeddings require a direct successful encoder call"
            )
        derived_embedding = self.encoding.to_visual_embedding()
        if self.embedding != derived_embedding:
            raise ValueError(
                "Visual embedding differs from its verified image encoding"
            )
        self.embedding.validate_against(self.imagined)
        if self.image.input_spec_hash != self.scene_spec.content_hash():
            raise ValueError("Image input hash differs from its visual scene spec")
        if (
            len(self.vector) != self.embedding.dimensions
            or self.embedding.dimensions != self.encoding.dimensions
        ):
            raise ValueError("Visual vector dimensions differ from embedding metadata")
        if any(not math.isfinite(value) for value in self.vector):
            raise ValueError("Visual vectors must contain only finite values")
        if not any(value != 0.0 for value in self.vector):
            raise ValueError("Cosine comparison forbids a zero visual vector")
        exact_bytes = normalized_float32_le_bytes(
            self.vector,
            expected_dimensions=self.embedding.dimensions,
        )
        _, exact_hash = verified_float32_le_vector(
            exact_bytes,
            expected_dimensions=self.embedding.dimensions,
        )
        if (
            exact_hash != self.embedding.vector_hash
            or exact_hash != self.encoding.vector_hash
        ):
            raise ValueError("Visual vector hash differs from embedding metadata")
        expected_id = content_id(
            "visual_observation",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"observation_id"},
            ),
        )
        if self.observation_id != expected_id:
            raise ValueError("Visual observation ID differs from canonical content")
        return self


class VisualCosineComparison(FrozenArtifactModel):
    """One narrow internal cosine comparison with no external-fact semantics."""

    schema_version: Literal["rei-native-visual-cosine-comparison-v1"] = (
        "rei-native-visual-cosine-comparison-v1"
    )
    comparison_id: NonEmptyId
    kind: VisualComparisonKind
    option_id: NonEmptyId | None
    paired_option_id: NonEmptyId | None
    left_observation_id: NonEmptyId
    right_observation_id: NonEmptyId
    cosine: CosineValue
    normalized_similarity: Score01
    normalized_separation: Score01
    internal_only: Literal[True] = True
    external_evidence_claim: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        kind: VisualComparisonKind,
        option_id: str | None,
        paired_option_id: str | None = None,
        left: BoundVisualEmbedding,
        right: BoundVisualEmbedding,
    ) -> VisualCosineComparison:
        expected_roles = {
            "current_to_desired": ("current", "desired"),
            "rollout_to_desired": ("option_rollout", "desired"),
            "rollout_to_broken": ("option_rollout", "broken"),
            "rollout_cross_seed_consistency": (
                "option_rollout",
                "option_rollout",
            ),
            "rollout_to_rollout_action_separation": (
                "option_rollout",
                "option_rollout",
            ),
        }
        if (left.role, right.role) != expected_roles[kind]:
            raise ValueError("Visual comparison roles differ from its narrow kind")
        if kind == "current_to_desired":
            if option_id is not None or paired_option_id is not None:
                raise ValueError("Current-to-desired comparison forbids an option ID")
        elif option_id is None or left.scene_spec.option_id != option_id:
            raise ValueError("Rollout comparison option differs from its observation")
        if kind == "rollout_cross_seed_consistency":
            if paired_option_id is not None:
                raise ValueError("Cross-seed comparison accepts only one option")
            if right.scene_spec.option_id != option_id:
                raise ValueError("Cross-seed comparison requires one rollout option")
            if left.evaluation_seed == right.evaluation_seed:
                raise ValueError("Cross-seed comparison requires different seeds")
            if left.scene_spec.content_hash() != right.scene_spec.content_hash():
                raise ValueError("Cross-seed comparison requires one scene spec")
        elif kind == "rollout_to_rollout_action_separation":
            if (
                paired_option_id is None
                or right.scene_spec.option_id != paired_option_id
                or option_id >= paired_option_id
            ):
                raise ValueError(
                    "Action-separation comparison requires a canonical option pair"
                )
            if left.evaluation_seed != right.evaluation_seed:
                raise ValueError(
                    "Action-separation comparison requires one evaluation seed"
                )
        elif left.evaluation_seed != right.evaluation_seed:
            raise ValueError("Target comparisons require one evaluation seed")
        cosine = _cosine(left.vector, right.vector)
        normalized_similarity = _round_score((cosine + 1.0) / 2.0)
        payload = {
            "schema_version": "rei-native-visual-cosine-comparison-v1",
            "kind": kind,
            "option_id": option_id,
            "paired_option_id": paired_option_id,
            "left_observation_id": left.observation_id,
            "right_observation_id": right.observation_id,
            "cosine": cosine,
            "normalized_similarity": normalized_similarity,
            "normalized_separation": _round_score(
                1.0 - normalized_similarity
            ),
            "internal_only": True,
            "external_evidence_claim": False,
        }
        return cls(
            comparison_id=content_id("visual_comparison", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        rollout_kind = self.kind != "current_to_desired"
        if rollout_kind != (self.option_id is not None):
            raise ValueError("Only rollout comparisons may carry an option ID")
        pair_kind = self.kind == "rollout_to_rollout_action_separation"
        if pair_kind != (self.paired_option_id is not None):
            raise ValueError("Only action separation may carry a paired option ID")
        if pair_kind and self.option_id >= self.paired_option_id:
            raise ValueError("Action separation requires canonical option order")
        expected_similarity = _round_score((self.cosine + 1.0) / 2.0)
        if self.normalized_similarity != expected_similarity:
            raise ValueError("Normalized visual similarity differs from cosine")
        if self.normalized_separation != _round_score(
            1.0 - self.normalized_similarity
        ):
            raise ValueError("Normalized visual separation differs from similarity")
        expected_id = content_id(
            "visual_comparison",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"comparison_id"},
            ),
        )
        if self.comparison_id != expected_id:
            raise ValueError("Visual comparison ID differs from canonical content")
        return self


class FusedVisualOptionScore(FrozenArtifactModel):
    """One transparent structured/visual fused score and penalty decomposition."""

    schema_version: Literal["rei-native-fused-visual-option-score-v1"] = (
        "rei-native-fused-visual-option-score-v1"
    )
    score_id: NonEmptyId
    option_id: NonEmptyId
    rollout_scene_id: NonEmptyId
    structured_valuation_hash: HashDigest
    replicate_count: int = Field(gt=0)
    structured_score: Score01
    desired_similarity: Score01
    broken_similarity: Score01
    broken_avoidance: Score01
    seed_consistency: Score01 | None
    target_ambiguity: Score01
    uncertainty: Score01
    uncertainty_reasons: tuple[VisualUncertaintyReason, ...]
    base_weighted_numerator: NonNegativeFinite
    base_weight_denominator: Annotated[
        float,
        Field(gt=0.0, allow_inf_nan=False),
    ]
    pre_penalty_score: Score01
    consistency_penalty: NonNegativeFinite
    uncertainty_penalty: NonNegativeFinite
    fused_score: Score01
    internal_only: Literal[True] = True
    external_evidence_claim: Literal[False] = False

    @model_validator(mode="after")
    def validate_score(self) -> Self:
        expected_avoidance = _round_score(1.0 - self.broken_similarity)
        if self.broken_avoidance != expected_avoidance:
            raise ValueError("Broken-scene avoidance differs from visual similarity")
        expected_ambiguity = _round_score(
            1.0 - abs(self.desired_similarity - self.broken_similarity)
        )
        if self.target_ambiguity != expected_ambiguity:
            raise ValueError("Visual target ambiguity differs from similarities")
        if self.seed_consistency is None:
            expected_uncertainty = self.target_ambiguity
            expected_reasons: tuple[VisualUncertaintyReason, ...] = (
                "desired_broken_target_ambiguity",
                "cross_seed_consistency_not_requested",
            )
            if self.consistency_penalty != 0.0:
                raise ValueError(
                    "A score without cross-seed comparison cannot claim its penalty"
                )
        else:
            expected_uncertainty = _mean(
                (
                    self.target_ambiguity,
                    _round_score(1.0 - self.seed_consistency),
                )
            )
            expected_reasons = (
                "desired_broken_target_ambiguity",
                "cross_seed_inconsistency",
            )
        if self.uncertainty != expected_uncertainty:
            raise ValueError("Visual uncertainty differs from recorded components")
        if self.uncertainty_reasons != expected_reasons:
            raise ValueError("Visual uncertainty reasons differ from its components")
        expected_pre_penalty = _round_score(
            self.base_weighted_numerator / self.base_weight_denominator
        )
        if self.pre_penalty_score != expected_pre_penalty:
            raise ValueError("Pre-penalty score differs from recorded weighted terms")
        expected_fused = _round_score(
            self.pre_penalty_score
            - self.consistency_penalty
            - self.uncertainty_penalty
        )
        if self.fused_score != expected_fused:
            raise ValueError("Fused score differs from recorded penalty terms")
        expected_id = content_id(
            "visual_option_score",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"score_id"},
            ),
        )
        if self.score_id != expected_id:
            raise ValueError("Visual option score ID differs from canonical content")
        return self


class VisualActionCollapseDiagnostic(FrozenModel):
    """Direct rollout collapse plus a secondary target-projection diagnostic."""

    detected: bool
    option_ids: tuple[NonEmptyId, ...]
    minimum_direct_separation: Score01
    maximum_projection_profile_spread: Score01
    epsilon: Score01
    method: Literal[
        "minimum_direct_rollout_separation"
    ] = "minimum_direct_rollout_separation"
    external_evidence_claim: Literal[False] = False

    @model_validator(mode="after")
    def validate_detection(self) -> Self:
        expected = (
            len(self.option_ids) >= 2
            and self.minimum_direct_separation <= self.epsilon
        )
        if self.detected != expected:
            raise ValueError("Action-collapse flag differs from its recorded threshold")
        return self


class VisualValuationResult(FrozenArtifactModel):
    """Integration-ready internal valuation result; never an evidence artifact."""

    schema_version: Literal["rei-native-visual-valuation-result-v1"] = (
        "rei-native-visual-valuation-result-v1"
    )
    result_id: NonEmptyId
    visual_state_id: NonEmptyId
    visual_state_hash: HashDigest
    policy: VisualValuationPolicy
    encoder_identity: ProviderIdentity
    dimensions: int = Field(gt=0)
    observation_ids: tuple[NonEmptyId, ...]
    comparisons: tuple[VisualCosineComparison, ...]
    current_desired_similarity: Score01
    option_scores: tuple[FusedVisualOptionScore, ...]
    mean_uncertainty: Score01
    action_collapse: VisualActionCollapseDiagnostic
    leading_option_id: NonEmptyId | None
    tied_option_ids: tuple[NonEmptyId, ...]
    integration_disposition: VisualIntegrationDisposition
    internal_only: Literal[True] = True
    external_evidence_claim: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        self.policy.validate_policy()
        self.action_collapse.validate_detection()
        for comparison in self.comparisons:
            comparison.validate_comparison()
        for score in self.option_scores:
            score.validate_score()
        if self.encoder_identity.kind != "image_encoder":
            raise ValueError("Visual valuation requires one image_encoder identity")
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("Visual valuation observation IDs must be unique")
        option_ids = tuple(score.option_id for score in self.option_scores)
        if not option_ids:
            raise ValueError("Visual valuation result requires option scores")
        if option_ids != tuple(sorted(option_ids)) or len(set(option_ids)) != len(
            option_ids
        ):
            raise ValueError("Visual option scores must use unique canonical order")
        if self.tied_option_ids != tuple(sorted(self.tied_option_ids)):
            raise ValueError("Tied visual option IDs must use canonical order")
        if self.leading_option_id is not None and self.tied_option_ids:
            raise ValueError("A unique visual leader cannot also claim a tie")
        comparison_ids = tuple(item.comparison_id for item in self.comparisons)
        if len(set(comparison_ids)) != len(comparison_ids):
            raise ValueError("Visual comparisons must be unique")
        observation_scope = set(self.observation_ids)
        if any(
            item.left_observation_id not in observation_scope
            or item.right_observation_id not in observation_scope
            for item in self.comparisons
        ):
            raise ValueError("Visual comparison leaves the observation scope")

        current_comparisons = tuple(
            item
            for item in self.comparisons
            if item.kind == "current_to_desired"
        )
        if not current_comparisons or self.current_desired_similarity != (
            _comparison_mean(current_comparisons)
        ):
            raise ValueError(
                "Current-to-desired aggregate differs from visual comparisons"
            )

        base_denominator = (
            self.policy.structured_weight.value
            + self.policy.desired_similarity_weight.value
            + self.policy.broken_avoidance_weight.value
        )
        replicate_counts = {item.replicate_count for item in self.option_scores}
        if len(replicate_counts) != 1:
            raise ValueError("Visual option scores require one replicate count")
        replicate_count = next(iter(replicate_counts))
        if len(current_comparisons) != replicate_count:
            raise ValueError("Current comparison count differs from visual replicates")
        for score in self.option_scores:
            desired_comparisons = tuple(
                item
                for item in self.comparisons
                if item.kind == "rollout_to_desired"
                and item.option_id == score.option_id
            )
            broken_comparisons = tuple(
                item
                for item in self.comparisons
                if item.kind == "rollout_to_broken"
                and item.option_id == score.option_id
            )
            consistency_comparisons = tuple(
                item
                for item in self.comparisons
                if item.kind == "rollout_cross_seed_consistency"
                and item.option_id == score.option_id
            )
            if (
                len(desired_comparisons) != replicate_count
                or len(broken_comparisons) != replicate_count
                or _comparison_mean(desired_comparisons)
                != score.desired_similarity
                or _comparison_mean(broken_comparisons) != score.broken_similarity
            ):
                raise ValueError(
                    "Visual option aggregates differ from narrow comparisons"
                )
            expected_consistency_count = (
                replicate_count * (replicate_count - 1) // 2
                if score.seed_consistency is not None
                else 0
            )
            if len(consistency_comparisons) != expected_consistency_count:
                raise ValueError(
                    "Cross-seed comparison count differs from visual replicates"
                )
            if score.seed_consistency is not None and (
                _comparison_mean(consistency_comparisons)
                != score.seed_consistency
            ):
                raise ValueError(
                    "Seed consistency differs from cross-seed comparisons"
                )
            expected_numerator = round(
                self.policy.structured_weight.value * score.structured_score
                + self.policy.desired_similarity_weight.value
                * score.desired_similarity
                + self.policy.broken_avoidance_weight.value
                * score.broken_avoidance,
                12,
            )
            if (
                score.base_weight_denominator != base_denominator
                or score.base_weighted_numerator != expected_numerator
            ):
                raise ValueError(
                    "Visual fused score differs from recorded policy weights"
                )
            expected_consistency_penalty = (
                round(
                    self.policy.seed_consistency_penalty.value
                    * _round_score(1.0 - score.seed_consistency),
                    12,
                )
                if score.seed_consistency is not None
                else 0.0
            )
            expected_uncertainty_penalty = round(
                self.policy.uncertainty_penalty.value * score.uncertainty,
                12,
            )
            if (
                score.consistency_penalty != expected_consistency_penalty
                or score.uncertainty_penalty != expected_uncertainty_penalty
            ):
                raise ValueError(
                    "Visual penalties differ from recorded policy weights"
                )
        if self.mean_uncertainty != _mean(
            tuple(item.uncertainty for item in self.option_scores)
        ):
            raise ValueError("Mean visual uncertainty differs from option scores")

        action_comparisons = tuple(
            item
            for item in self.comparisons
            if item.kind == "rollout_to_rollout_action_separation"
        )
        expected_pairs = tuple(combinations(option_ids, 2))
        if len(action_comparisons) != replicate_count * len(expected_pairs):
            raise ValueError(
                "Action-separation comparison count differs from option replicates"
            )
        for option_pair in expected_pairs:
            if sum(
                (item.option_id, item.paired_option_id) == option_pair
                for item in action_comparisons
            ) != replicate_count:
                raise ValueError(
                    "Action-separation comparisons do not cover each option pair"
                )
        minimum_separation = (
            min(item.normalized_separation for item in action_comparisons)
            if action_comparisons
            else 1.0
        )
        profile_spread = 0.0
        if len(self.option_scores) >= 2:
            profile_spread = max(
                max(
                    abs(left.desired_similarity - right.desired_similarity),
                    abs(left.broken_similarity - right.broken_similarity),
                )
                for left, right in combinations(self.option_scores, 2)
            )
        if (
            self.action_collapse.option_ids != option_ids
            or self.action_collapse.epsilon
            != self.policy.action_collapse_epsilon
            or self.action_collapse.minimum_direct_separation
            != _round_score(minimum_separation)
            or self.action_collapse.maximum_projection_profile_spread
            != _round_score(profile_spread)
        ):
            raise ValueError(
                "Action-collapse diagnostic differs from visual option profiles"
            )

        maximum = max(item.fused_score for item in self.option_scores)
        expected_tied = tuple(
            item.option_id
            for item in self.option_scores
            if maximum - item.fused_score
            <= self.policy.selection_tie_epsilon
        )
        raw_leader = expected_tied[0] if len(expected_tied) == 1 else None
        expected_leader = (
            None if self.action_collapse.detected else raw_leader
        )
        expected_ties = () if raw_leader is not None else expected_tied
        if (
            self.leading_option_id != expected_leader
            or self.tied_option_ids != expected_ties
        ):
            raise ValueError("Visual leader/tie record differs from fused scores")
        expected_disposition: VisualIntegrationDisposition
        if self.action_collapse.detected:
            expected_disposition = "review_action_collapse"
        elif self.leading_option_id is None:
            expected_disposition = "review_tie"
        else:
            expected_disposition = "usable"
        if self.integration_disposition != expected_disposition:
            raise ValueError("Visual integration disposition differs from diagnostics")
        expected_id = content_id(
            "visual_valuation_result",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"result_id"},
            ),
        )
        if self.result_id != expected_id:
            raise ValueError(
                "Visual valuation result ID differs from canonical content"
            )
        return self

    def validate_against(
        self,
        *,
        visual_state: EmocioVisualState,
        observations: tuple[BoundVisualEmbedding, ...],
        include_cross_seed_consistency: bool | None = None,
    ) -> Self:
        """Replay the complete valuation against its canonical source artifacts."""

        validated = VisualValuationResult.model_validate(
            self.model_dump(mode="python", round_trip=True)
        )
        score_modes = {
            score.seed_consistency is not None
            for score in validated.option_scores
        }
        if len(score_modes) != 1:
            raise ValueError(
                "Visual valuation result mixes cross-seed consistency modes"
            )
        recorded_mode = next(iter(score_modes))
        comparison_mode = any(
            comparison.kind == "rollout_cross_seed_consistency"
            for comparison in validated.comparisons
        )
        if comparison_mode != recorded_mode:
            raise ValueError(
                "Visual valuation consistency comparisons differ from score mode"
            )
        if (
            include_cross_seed_consistency is not None
            and include_cross_seed_consistency != recorded_mode
        ):
            raise ValueError(
                "Requested cross-seed consistency mode differs from the result"
            )
        replay_mode = (
            recorded_mode
            if include_cross_seed_consistency is None
            else include_cross_seed_consistency
        )
        expected = evaluate_visual_valuation(
            policy=validated.policy,
            visual_state=visual_state,
            observations=observations,
            include_cross_seed_consistency=replay_mode,
        )
        if validated != expected:
            raise ValueError(
                "Visual valuation result differs from deterministic source replay"
            )
        return self


def _round_score(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Visual valuation produced a non-finite score")
    return round(min(1.0, max(0.0, value)), 12)


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        raise ValueError("Visual valuation cannot average an empty collection")
    return _round_score(math.fsum(values) / len(values))


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("Cosine comparison requires equal vector dimensions")
    if not left:
        raise ValueError("Cosine comparison requires non-empty vectors")
    if any(not math.isfinite(value) for value in (*left, *right)):
        raise ValueError("Cosine comparison requires finite vectors")
    left_scale = max(abs(value) for value in left)
    right_scale = max(abs(value) for value in right)
    if left_scale == 0.0 or right_scale == 0.0:
        raise ValueError("Cosine comparison forbids zero vectors")
    scaled_left = tuple(value / left_scale for value in left)
    scaled_right = tuple(value / right_scale for value in right)
    numerator = math.fsum(
        left_value * right_value
        for left_value, right_value in zip(
            scaled_left,
            scaled_right,
            strict=True,
        )
    )
    left_norm = math.sqrt(math.fsum(value * value for value in scaled_left))
    right_norm = math.sqrt(math.fsum(value * value for value in scaled_right))
    cosine = numerator / (left_norm * right_norm)
    if not math.isfinite(cosine):
        raise ValueError("Cosine comparison produced a non-finite result")
    return round(min(1.0, max(-1.0, cosine)), 12)


def _comparison_mean(
    comparisons: tuple[VisualCosineComparison, ...],
) -> float:
    return _mean(tuple(item.normalized_similarity for item in comparisons))


def _pipeline_common_profile(
    item: ImageRenderItemOutcome,
) -> tuple[str, str, tuple[object, ...]]:
    """Return the exact mode-independent renderer runtime profile."""

    conditioning = tuple(
        parameter
        for parameter in item.request.pipeline.parameters
        if parameter.name == "conditioning_method"
    )
    if len(conditioning) != 1:
        raise ValueError(
            "Visual valuation pipeline specs require one conditioning_method"
        )
    expected_conditioning = canonical_json_bytes(
        item.request.conditioning_method
    ).decode("utf-8")
    if conditioning[0].canonical_json_value != expected_conditioning:
        raise ValueError(
            "Visual valuation pipeline conditioning differs from render request"
        )
    shared_parameters = tuple(
        parameter
        for parameter in item.request.pipeline.parameters
        if parameter.name != "conditioning_method"
    )
    return (
        item.request.pipeline.implementation,
        item.request.pipeline.implementation_revision,
        shared_parameters,
    )


def _validate_observation_matrix(
    *,
    observations: tuple[BoundVisualEmbedding, ...],
    visual_state: EmocioVisualState,
) -> tuple[
    tuple[int, ...],
    tuple[str, ...],
    dict[tuple[int, str, str | None], BoundVisualEmbedding],
]:
    if not observations:
        raise ValueError("Visual valuation requires embedding observations")
    observation_ids = tuple(item.observation_id for item in observations)
    if len(set(observation_ids)) != len(observation_ids):
        raise ValueError("Visual observations must be unique")
    encoders = {item.embedding.encoder_identity for item in observations}
    if len(encoders) != 1:
        raise ValueError("Visual observations require one exact encoder identity")
    dimensions = {item.embedding.dimensions for item in observations}
    if len(dimensions) != 1:
        raise ValueError("Visual observations require one embedding dimension")

    valuations = visual_state.option_valuations
    valuation_by_option = {item.option_id: item for item in valuations}
    if len(valuation_by_option) != len(valuations) or not valuations:
        raise ValueError("Structured option valuations must be non-empty and unique")
    option_ids = tuple(sorted(valuation_by_option))
    seeds = tuple(sorted({item.evaluation_seed for item in observations}))
    matrix: dict[tuple[int, str, str | None], BoundVisualEmbedding] = {}
    for observation in observations:
        option_id = observation.scene_spec.option_id
        key = (observation.evaluation_seed, observation.role, option_id)
        if key in matrix:
            raise ValueError("Visual observation matrix contains a duplicate role")
        matrix[key] = observation

    expected_role_keys = {
        (role, None) for role in ("current", "desired", "broken")
    } | {("option_rollout", option_id) for option_id in option_ids}
    expected_scene_by_key = {
        ("current", None): visual_state.current_scene,
        ("desired", None): visual_state.desired_scene,
        ("broken", None): visual_state.broken_scene,
        **{
            ("option_rollout", scene.option_id): scene
            for scene in visual_state.option_rollouts
        },
    }
    selected_render_items: list[ImageRenderItemOutcome] = []
    for seed in seeds:
        actual_role_keys = {
            (role, option_id)
            for matrix_seed, role, option_id in matrix
            if matrix_seed == seed
        }
        if actual_role_keys != expected_role_keys:
            raise ValueError(
                "Every evaluation seed requires current, desired, broken, and all "
                "option rollout observations"
            )
        ordered_observations = tuple(
            matrix[(seed, role, option_id)]
            for role, option_id in (
                ("current", None),
                ("desired", None),
                ("broken", None),
                *(
                    ("option_rollout", option_id)
                    for option_id in option_ids
                ),
            )
        )
        for observation in ordered_observations:
            key = (observation.role, observation.scene_spec.option_id)
            expected_scene = expected_scene_by_key[key]
            if (
                observation.scene_spec != expected_scene
                or observation.scene_spec.content_hash()
                != expected_scene.content_hash()
            ):
                raise ValueError(
                    "Visual observation scene differs from the exact visual state"
                )
        render_batch = ordered_observations[0].render_batch
        if any(
            observation.render_batch != render_batch
            or observation.render_batch.content_hash()
            != render_batch.content_hash()
            for observation in ordered_observations[1:]
        ):
            raise ValueError(
                "Every evaluation seed requires one exact render batch"
            )
        expected_scenes = tuple(
            observation.scene_spec for observation in ordered_observations
        )
        validate_render_batch(
            render_batch,
            expected_scenes,
            expected_seed=seed,
        )
        seed_render_items: list[ImageRenderItemOutcome] = []
        for observation in ordered_observations:
            _, render_item = _validated_render_item(
                render_batch=observation.render_batch,
                evaluation_seed=observation.evaluation_seed,
                scene_spec=observation.scene_spec,
                image=observation.image,
            )
            expected_mode = (
                "image_to_image"
                if observation.role == "option_rollout"
                else "text_to_image"
            )
            if render_item.request.mode != expected_mode:
                raise ValueError(
                    "Visual observation render mode differs from its scene role"
                )
            seed_render_items.append(render_item)
            selected_render_items.append(render_item)
        current_artifact = seed_render_items[0].artifact
        if current_artifact is None:
            raise ValueError("Current visual observation has no render artifact")
        expected_rollout_source = (
            ImageSourceReference.from_artifact_with_scene_lineage(
                current_artifact
            )
        )
        for item in seed_render_items[3:]:
            if item.request.source_image != expected_rollout_source:
                raise ValueError(
                    "Every option rollout must use the exact current-scene image"
                )

    renderer_identity = selected_render_items[0].request.provider
    if any(
        item.request.provider != renderer_identity
        for item in selected_render_items[1:]
    ):
        raise ValueError("Visual observations require one exact renderer identity")
    prompt_profile = (
        selected_render_items[0].request.prompt_language,
        selected_render_items[0].request.style_id,
        selected_render_items[0].request.profile_hash,
    )
    if any(value is None for value in prompt_profile):
        raise ValueError(
            "Visual observations require explicit prompt language, style, and profile"
        )
    if any(
        (
            item.request.prompt_language,
            item.request.style_id,
            item.request.profile_hash,
        )
        != prompt_profile
        for item in selected_render_items[1:]
    ):
        raise ValueError(
            "Visual observations require one exact prompt language/style profile"
        )
    pipeline_by_mode: dict[str, object] = {}
    common_profile = _pipeline_common_profile(selected_render_items[0])
    for item in selected_render_items:
        prior = pipeline_by_mode.setdefault(
            item.request.mode,
            item.request.pipeline,
        )
        if prior != item.request.pipeline:
            raise ValueError(
                "Visual observations require one exact pipeline spec per render mode"
            )
        if _pipeline_common_profile(item) != common_profile:
            raise ValueError(
                "Visual render modes require one exact shared pipeline runtime profile"
            )

    encoding_spec = observations[0].encoding.request.spec
    if any(
        observation.encoding.request.spec != encoding_spec
        or observation.encoding.request.spec.content_hash()
        != encoding_spec.content_hash()
        for observation in observations[1:]
    ):
        raise ValueError(
            "Visual observations require one exact image encoding spec"
        )

    for role, option_id in sorted(expected_role_keys):
        samples = tuple(matrix[(seed, role, option_id)] for seed in seeds)
        spec_hashes = {sample.scene_spec.content_hash() for sample in samples}
        if len(spec_hashes) != 1:
            raise ValueError("Cross-seed observations must preserve one scene spec")
        if option_id is not None:
            valuation = valuation_by_option[option_id]
            if valuation.rollout_scene_id != samples[0].scene_spec.scene_id:
                raise ValueError(
                    "Structured valuation rollout differs from visual observation"
                )
    return seeds, option_ids, matrix


def evaluate_visual_valuation(
    *,
    policy: VisualValuationPolicy,
    visual_state: EmocioVisualState,
    observations: tuple[BoundVisualEmbedding, ...],
    include_cross_seed_consistency: bool = False,
) -> VisualValuationResult:
    """Compare narrow visual targets and return deterministic fused option scores."""

    # Pydantic does not re-run validators when an already-built model instance is
    # passed through ``model_validate``.  Reconstruct every input from its dump so
    # a stale ``model_copy`` cannot bypass content IDs, vector hashes, or lineage.
    policy = VisualValuationPolicy.model_validate(
        policy.model_dump(mode="python", round_trip=True)
    )
    visual_state = EmocioVisualState.model_validate(
        visual_state.model_dump(mode="python", round_trip=True)
    )
    replayed_valuations = tuple(
        value_option_rollout(
            rollout,
            current_scene=visual_state.current_scene,
            desired_scene=visual_state.desired_scene,
            broken_scene=visual_state.broken_scene,
        )
        for rollout in visual_state.option_rollouts
    )
    if visual_state.option_valuations != replayed_valuations:
        raise ValueError(
            "Visual state option valuations differ from deterministic scene replay"
        )
    observations = tuple(
        BoundVisualEmbedding.model_validate(
            observation.model_dump(mode="python", round_trip=True)
        )
        for observation in observations
    )
    valuations = replayed_valuations
    seeds, option_ids, matrix = _validate_observation_matrix(
        observations=observations,
        visual_state=visual_state,
    )
    if include_cross_seed_consistency and len(seeds) < 2:
        raise ValueError(
            "Cross-seed consistency requires at least two evaluation seeds"
        )

    comparisons: list[VisualCosineComparison] = []
    current_desired: list[VisualCosineComparison] = []
    desired_by_option: dict[str, list[VisualCosineComparison]] = {
        option_id: [] for option_id in option_ids
    }
    broken_by_option: dict[str, list[VisualCosineComparison]] = {
        option_id: [] for option_id in option_ids
    }
    consistency_by_option: dict[str, list[VisualCosineComparison]] = {
        option_id: [] for option_id in option_ids
    }

    for seed in seeds:
        current = matrix[(seed, "current", None)]
        desired = matrix[(seed, "desired", None)]
        broken = matrix[(seed, "broken", None)]
        comparison = VisualCosineComparison.create(
            kind="current_to_desired",
            option_id=None,
            left=current,
            right=desired,
        )
        current_desired.append(comparison)
        comparisons.append(comparison)
        for option_id in option_ids:
            rollout = matrix[(seed, "option_rollout", option_id)]
            desired_comparison = VisualCosineComparison.create(
                kind="rollout_to_desired",
                option_id=option_id,
                left=rollout,
                right=desired,
            )
            broken_comparison = VisualCosineComparison.create(
                kind="rollout_to_broken",
                option_id=option_id,
                left=rollout,
                right=broken,
            )
            desired_by_option[option_id].append(desired_comparison)
            broken_by_option[option_id].append(broken_comparison)
            comparisons.extend((desired_comparison, broken_comparison))
        for left_option_id, right_option_id in combinations(option_ids, 2):
            comparisons.append(
                VisualCosineComparison.create(
                    kind="rollout_to_rollout_action_separation",
                    option_id=left_option_id,
                    paired_option_id=right_option_id,
                    left=matrix[(seed, "option_rollout", left_option_id)],
                    right=matrix[(seed, "option_rollout", right_option_id)],
                )
            )

    if include_cross_seed_consistency:
        for option_id in option_ids:
            samples = tuple(
                matrix[(seed, "option_rollout", option_id)] for seed in seeds
            )
            for left, right in combinations(samples, 2):
                comparison = VisualCosineComparison.create(
                    kind="rollout_cross_seed_consistency",
                    option_id=option_id,
                    left=left,
                    right=right,
                )
                consistency_by_option[option_id].append(comparison)
                comparisons.append(comparison)

    valuation_by_option = {item.option_id: item for item in valuations}
    base_denominator = (
        policy.structured_weight.value
        + policy.desired_similarity_weight.value
        + policy.broken_avoidance_weight.value
    )
    option_scores: list[FusedVisualOptionScore] = []
    for option_id in option_ids:
        valuation = valuation_by_option[option_id]
        structured_score = aggregate_option_valuation(valuation)
        desired_similarity = _comparison_mean(tuple(desired_by_option[option_id]))
        broken_similarity = _comparison_mean(tuple(broken_by_option[option_id]))
        broken_avoidance = _round_score(1.0 - broken_similarity)
        consistency = (
            _comparison_mean(tuple(consistency_by_option[option_id]))
            if include_cross_seed_consistency
            else None
        )
        target_ambiguity = _round_score(
            1.0 - abs(desired_similarity - broken_similarity)
        )
        if consistency is None:
            uncertainty = target_ambiguity
            uncertainty_reasons: tuple[VisualUncertaintyReason, ...] = (
                "desired_broken_target_ambiguity",
                "cross_seed_consistency_not_requested",
            )
            consistency_penalty = 0.0
        else:
            consistency_uncertainty = _round_score(1.0 - consistency)
            uncertainty = _mean((target_ambiguity, consistency_uncertainty))
            uncertainty_reasons = (
                "desired_broken_target_ambiguity",
                "cross_seed_inconsistency",
            )
            consistency_penalty = round(
                policy.seed_consistency_penalty.value * consistency_uncertainty,
                12,
            )
        numerator = round(
            policy.structured_weight.value * structured_score
            + policy.desired_similarity_weight.value * desired_similarity
            + policy.broken_avoidance_weight.value * broken_avoidance,
            12,
        )
        pre_penalty = _round_score(numerator / base_denominator)
        uncertainty_penalty = round(
            policy.uncertainty_penalty.value * uncertainty,
            12,
        )
        score_payload = {
            "schema_version": "rei-native-fused-visual-option-score-v1",
            "option_id": option_id,
            "rollout_scene_id": valuation.rollout_scene_id,
            "structured_valuation_hash": valuation.content_hash(),
            "replicate_count": len(seeds),
            "structured_score": structured_score,
            "desired_similarity": desired_similarity,
            "broken_similarity": broken_similarity,
            "broken_avoidance": broken_avoidance,
            "seed_consistency": consistency,
            "target_ambiguity": target_ambiguity,
            "uncertainty": uncertainty,
            "uncertainty_reasons": uncertainty_reasons,
            "base_weighted_numerator": numerator,
            "base_weight_denominator": base_denominator,
            "pre_penalty_score": pre_penalty,
            "consistency_penalty": consistency_penalty,
            "uncertainty_penalty": uncertainty_penalty,
            "fused_score": _round_score(
                pre_penalty - consistency_penalty - uncertainty_penalty
            ),
            "internal_only": True,
            "external_evidence_claim": False,
        }
        option_scores.append(
            FusedVisualOptionScore(
                score_id=content_id("visual_option_score", score_payload),
                **score_payload,
            )
        )

    profile_spread = 0.0
    if len(option_scores) >= 2:
        profile_spread = max(
            max(
                abs(left.desired_similarity - right.desired_similarity),
                abs(left.broken_similarity - right.broken_similarity),
            )
            for left, right in combinations(option_scores, 2)
        )
    profile_spread = _round_score(profile_spread)
    direct_action_comparisons = tuple(
        item
        for item in comparisons
        if item.kind == "rollout_to_rollout_action_separation"
    )
    minimum_direct_separation = _round_score(
        min(
            (
                item.normalized_separation
                for item in direct_action_comparisons
            ),
            default=1.0,
        )
    )
    action_collapse = VisualActionCollapseDiagnostic(
        detected=(
            len(option_scores) >= 2
            and minimum_direct_separation <= policy.action_collapse_epsilon
        ),
        option_ids=option_ids,
        minimum_direct_separation=minimum_direct_separation,
        maximum_projection_profile_spread=profile_spread,
        epsilon=policy.action_collapse_epsilon,
    )

    maximum = max(item.fused_score for item in option_scores)
    tied_option_ids = tuple(
        item.option_id
        for item in option_scores
        if maximum - item.fused_score <= policy.selection_tie_epsilon
    )
    raw_leading_option_id = (
        tied_option_ids[0] if len(tied_option_ids) == 1 else None
    )
    leading_option_id = (
        None if action_collapse.detected else raw_leading_option_id
    )
    canonical_ties = (
        ()
        if raw_leading_option_id is not None
        else tuple(sorted(tied_option_ids))
    )
    if action_collapse.detected:
        disposition: VisualIntegrationDisposition = "review_action_collapse"
    elif leading_option_id is None:
        disposition = "review_tie"
    else:
        disposition = "usable"

    ordered_observations = tuple(
        sorted(
            observations,
            key=lambda item: (
                item.evaluation_seed,
                item.role,
                item.scene_spec.option_id or "",
                item.observation_id,
            ),
        )
    )
    payload = {
        "schema_version": "rei-native-visual-valuation-result-v1",
        "visual_state_id": visual_state.visual_state_id,
        "visual_state_hash": visual_state.content_hash(),
        "policy": policy,
        "encoder_identity": ordered_observations[0].embedding.encoder_identity,
        "dimensions": ordered_observations[0].embedding.dimensions,
        "observation_ids": tuple(
            item.observation_id for item in ordered_observations
        ),
        "comparisons": tuple(comparisons),
        "current_desired_similarity": _comparison_mean(tuple(current_desired)),
        "option_scores": tuple(option_scores),
        "mean_uncertainty": _mean(
            tuple(item.uncertainty for item in option_scores)
        ),
        "action_collapse": action_collapse,
        "leading_option_id": leading_option_id,
        "tied_option_ids": canonical_ties,
        "integration_disposition": disposition,
        "internal_only": True,
        "external_evidence_claim": False,
    }
    return VisualValuationResult(
        result_id=content_id("visual_valuation_result", payload),
        **payload,
    )


__all__ = [
    "BoundVisualEmbedding",
    "FusedVisualOptionScore",
    "ImplementationHypothesisWeight",
    "VisualActionCollapseDiagnostic",
    "VisualCosineComparison",
    "VisualValuationPolicy",
    "VisualValuationResult",
    "canonical_visual_vector_hash",
    "evaluate_visual_valuation",
]
