"""Fail-closed integration of verified visual valuation into native Emocio.

Generated images remain internal imagination artifacts.  This module only
permits a visual valuation to select a native option when an explicit,
content-addressed robustness and semantic-review approval matches every runtime
provider and prompt profile in the observation cohort.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from ..models.emocio import (
    EmocioVisualState,
    ImaginedVisualArtifact,
    VisualSceneSpec,
)
from ..models.provider import (
    PositiveSeconds,
    ProviderCallSpec,
    ProviderIdentity,
    ensure_call_contract,
)
from ..models.rendering import ImageRenderBatchOutcome, ImageRenderItemOutcome
from ..providers.protocols import (
    ImageEncodingRequest,
    ImageEncodingSpec,
    VerifiedImageEncoder,
    VerifiedImageEncoding,
)
from .policy import EmocioPolicyDecision, OptionAggregateScore
from .renderer import validate_render_batch
from .visual_policy_config import VisualValuationPolicyConfig
from .visual_valuation import (
    BoundVisualEmbedding,
    VisualValuationResult,
    evaluate_visual_valuation,
)
from .visual_world_memory import (
    VisualWorldMemoryRecord,
    build_visual_world_memory_record,
)


VisualCognitionFailureStage = Literal[
    "render",
    "policy_config",
    "encoding",
    "valuation",
    "memory",
    "approval",
]


class VisualObservationBuildError(RuntimeError):
    """Internal carrier preserving partial successful encoding provenance."""

    def __init__(
        self,
        *,
        cause: Exception | None = None,
        failure_code: str | None = None,
        partial_observations: tuple[BoundVisualEmbedding, ...] = (),
        attempted_call_spec: ProviderCallSpec | None = None,
    ) -> None:
        code = failure_code or (
            type(cause).__name__ if cause is not None else "VisualEncodingFailure"
        )
        self.failure_code = code
        self.partial_observations = partial_observations
        self.attempted_call_spec = attempted_call_spec
        super().__init__(f"Visual encoding failed closed ({code})")

    def with_partial_observations(
        self,
        observations: tuple[BoundVisualEmbedding, ...],
    ) -> VisualObservationBuildError:
        return type(self)(
            failure_code=self.failure_code,
            partial_observations=observations,
            attempted_call_spec=self.attempted_call_spec,
        )


def visual_failure_summary(
    stage: VisualCognitionFailureStage,
    error: Exception,
) -> tuple[str, str]:
    """Return stable canonical failure text without persisting provider secrets."""

    code = getattr(error, "failure_code", None) or type(error).__name__
    if not isinstance(code, str) or not code.strip():
        code = "VisualCognitionFailure"
    safe_code = "".join(
        character
        for character in code.strip()[:100]
        if character.isalnum() or character in {"_", "-"}
    ) or "VisualCognitionFailure"
    return safe_code, f"Visual cognition {stage} failed closed ({safe_code})"


class ApprovedVisualPromptProfile(FrozenModel):
    """One exact prompt profile admitted by a reviewed visual cohort."""

    language: LanguageCode
    style_id: NonEmptyId
    profile_hash: HashDigest


class ReviewedVisualCohortCell(FrozenModel):
    """One exact, semantically reviewed cell in the robustness matrix."""

    visual_state_hash: HashDigest
    evaluation_seed: int
    renderer_identity: ProviderIdentity
    prompt_profile: ApprovedVisualPromptProfile
    option_order: tuple[NonEmptyId, ...] = Field(min_length=1)
    encoding_spec_hash: HashDigest
    runtime_profile_hash: HashDigest
    prompt_batch_hash: HashDigest
    approved_leading_option_id: NonEmptyId
    minimum_leading_margin: Score01 = Field(gt=0.0)
    evidence_hash: HashDigest

    @model_validator(mode="after")
    def validate_cell(self) -> Self:
        if self.renderer_identity.kind != "image_renderer":
            raise ValueError("Reviewed visual cell requires an image renderer")
        if len(set(self.option_order)) != len(self.option_order):
            raise ValueError("Reviewed visual cell option order must be unique")
        if self.approved_leading_option_id not in self.option_order:
            raise ValueError(
                "Reviewed visual leader must belong to the exact option order"
            )
        return self


class AdmittedVisualInfluenceApproval(FrozenModel):
    """One approval identity pinned by a separately configured authority."""

    approval_id: NonEmptyId
    approval_hash: HashDigest


def visual_cognition_runtime_profile_hash(
    observations: tuple[BoundVisualEmbedding, ...],
) -> str:
    """Hash exact mode-level runtime settings without scene-specific prompts."""

    cohort = tuple(
        BoundVisualEmbedding.model_validate(
            observation.model_dump(mode="python", round_trip=True)
        )
        for observation in observations
    )
    if not cohort:
        raise ValueError("Visual runtime profile requires observations")
    batch = cohort[0].render_batch
    if any(observation.render_batch != batch for observation in cohort[1:]):
        raise ValueError("Visual runtime profile requires one exact render batch")
    profiles_by_mode: dict[str, set[str]] = {}
    payload_by_hash: dict[str, dict[str, object]] = {}
    for item in batch.items:
        request = item.request
        runtime_payload = {
            "mode": request.mode,
            "renderer_identity": request.provider,
            "pipeline": request.pipeline,
            "width": request.width,
            "height": request.height,
            "num_inference_steps": request.num_inference_steps,
            "guidance_scale": request.guidance_scale,
            "negative_prompt": request.negative_prompt,
            "strength": request.strength,
            "conditioning_method": request.conditioning_method,
            "prompt_language": request.prompt_language,
            "style_id": request.style_id,
            "profile_hash": request.profile_hash,
        }
        digest = sha256_hex(runtime_payload)
        profiles_by_mode.setdefault(request.mode, set()).add(digest)
        payload_by_hash[digest] = runtime_payload
    if set(profiles_by_mode) != {"text_to_image", "image_to_image"}:
        raise ValueError("Visual runtime profile requires T2I and img2img modes")
    if any(len(digests) != 1 for digests in profiles_by_mode.values()):
        raise ValueError("Each visual render mode requires one exact runtime profile")
    encoding_spec = cohort[0].encoding.request.spec
    if any(
        observation.encoding.request.spec != encoding_spec
        for observation in cohort[1:]
    ):
        raise ValueError("Visual runtime profile requires one encoding spec")
    encoding_call_profiles = {
        sha256_hex(
            {
                "provider": observation.encoding.call_spec.provider,
                "seed": observation.encoding.call_spec.seed,
                "parameters": tuple(
                    parameter
                    for parameter in observation.encoding.call_spec.parameters
                    if parameter.name != "image_content_sha256"
                ),
                "timeout_seconds": observation.encoding.call_spec.timeout_seconds,
                "fallback_policy": observation.encoding.call_spec.fallback_policy,
            }
        )
        for observation in cohort
    }
    if len(encoding_call_profiles) != 1:
        raise ValueError("Visual runtime profile requires one encoder call profile")
    mode_profiles = tuple(
        payload_by_hash[next(iter(profiles_by_mode[mode]))]
        for mode in sorted(profiles_by_mode)
    )
    return sha256_hex(
        {
            "schema_version": "rei-native-visual-runtime-profile-v1",
            "render_modes": mode_profiles,
            "encoding_spec_hash": encoding_spec.content_hash(),
            "encoding_call_profile_hash": next(iter(encoding_call_profiles)),
        }
    )


def visual_cognition_prompt_batch_hash(
    observations: tuple[BoundVisualEmbedding, ...],
) -> str:
    """Bind the exact positive prompts and request bytes used by one cohort."""

    cohort = tuple(
        BoundVisualEmbedding.model_validate(
            observation.model_dump(mode="python", round_trip=True)
        )
        for observation in observations
    )
    if not cohort:
        raise ValueError("Visual prompt batch requires observations")
    batch = cohort[0].render_batch
    if any(observation.render_batch != batch for observation in cohort[1:]):
        raise ValueError("Visual prompt batch requires one exact render batch")
    return sha256_hex(
        {
            "schema_version": "rei-native-visual-prompt-batch-v1",
            "requests": tuple(
                {
                    "request_id": item.request.request_id,
                    "request_hash": item.request.content_hash(),
                }
                for item in batch.items
            ),
        }
    )


def _reviewed_cell_coordinate(
    cell: ReviewedVisualCohortCell,
) -> tuple[object, ...]:
    return (
        cell.visual_state_hash,
        cell.evaluation_seed,
        cell.renderer_identity.provider_id,
        cell.renderer_identity.content_hash(),
        cell.prompt_profile.language,
        cell.prompt_profile.style_id,
        cell.prompt_profile.profile_hash,
        cell.option_order,
    )


def _reviewed_cell_sort_key(
    cell: ReviewedVisualCohortCell,
) -> tuple[object, ...]:
    return _reviewed_cell_coordinate(cell)


class VisualNativeInfluenceApproval(FrozenArtifactModel):
    """Explicit review gate required before internal images affect native output.

    Content addressing prevents accidental mutation; it is not a cryptographic
    signature or a substitute for the referenced human review records.
    """

    schema_version: Literal["rei-native-visual-influence-approval-v1"] = (
        "rei-native-visual-influence-approval-v1"
    )
    approval_id: NonEmptyId
    policy_config_id: NonEmptyId
    policy_config_hash: HashDigest
    encoder_identity: ProviderIdentity
    approved_renderer_identities: tuple[ProviderIdentity, ...] = Field(
        min_length=2
    )
    evaluated_seeds: tuple[int, ...] = Field(min_length=3)
    approved_prompt_profiles: tuple[ApprovedVisualPromptProfile, ...] = Field(
        min_length=4
    )
    reviewed_visual_state_hashes: tuple[HashDigest, ...] = Field(min_length=1)
    approved_encoding_spec_hashes: tuple[HashDigest, ...] = Field(min_length=1)
    approved_runtime_profile_hashes: tuple[HashDigest, ...] = Field(min_length=1)
    reviewed_cohort_cells: tuple[ReviewedVisualCohortCell, ...] = Field(
        min_length=1
    )
    robustness_report_hash: HashDigest
    semantic_review_record_hash: HashDigest
    review_authority: NonEmptyText
    semantic_scene_reviewed: Literal[True] = True
    structured_baseline_verified: Literal[True] = True
    action_collapse_robustness_reviewed: Literal[True] = True
    reversed_option_order_reviewed: Literal[True] = True
    grounded_evidence_contamination_count: Literal[0] = 0
    approved_for_native_influence: Literal[True] = True
    internal_only: Literal[True] = True
    external_evidence_claim: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        policy_config: VisualValuationPolicyConfig,
        encoder_identity: ProviderIdentity,
        approved_renderer_identities: tuple[ProviderIdentity, ...],
        evaluated_seeds: tuple[int, ...],
        approved_prompt_profiles: tuple[ApprovedVisualPromptProfile, ...],
        reviewed_visual_state_hashes: tuple[str, ...],
        approved_encoding_spec_hashes: tuple[str, ...],
        approved_runtime_profile_hashes: tuple[str, ...],
        reviewed_cohort_cells: tuple[ReviewedVisualCohortCell, ...],
        robustness_report_hash: str,
        semantic_review_record_hash: str,
        review_authority: str,
    ) -> VisualNativeInfluenceApproval:
        payload = {
            "schema_version": "rei-native-visual-influence-approval-v1",
            "policy_config_id": policy_config.config_id,
            "policy_config_hash": policy_config.content_hash(),
            "encoder_identity": encoder_identity,
            "approved_renderer_identities": tuple(
                sorted(
                    approved_renderer_identities,
                    key=lambda identity: identity.provider_id,
                )
            ),
            "evaluated_seeds": tuple(sorted(evaluated_seeds)),
            "approved_prompt_profiles": tuple(
                sorted(
                    approved_prompt_profiles,
                    key=lambda profile: (
                        profile.language,
                        profile.style_id,
                        profile.profile_hash,
                    ),
                )
            ),
            "reviewed_visual_state_hashes": tuple(
                sorted(reviewed_visual_state_hashes)
            ),
            "approved_encoding_spec_hashes": tuple(
                sorted(approved_encoding_spec_hashes)
            ),
            "approved_runtime_profile_hashes": tuple(
                sorted(approved_runtime_profile_hashes)
            ),
            "reviewed_cohort_cells": tuple(
                sorted(
                    reviewed_cohort_cells,
                    key=_reviewed_cell_sort_key,
                )
            ),
            "robustness_report_hash": robustness_report_hash,
            "semantic_review_record_hash": semantic_review_record_hash,
            "review_authority": review_authority,
            "semantic_scene_reviewed": True,
            "structured_baseline_verified": True,
            "action_collapse_robustness_reviewed": True,
            "reversed_option_order_reviewed": True,
            "grounded_evidence_contamination_count": 0,
            "approved_for_native_influence": True,
            "internal_only": True,
            "external_evidence_claim": False,
        }
        return cls(
            approval_id=content_id("visual_influence_approval", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_approval_scope(self) -> Self:
        encoder = ProviderIdentity.model_validate(
            self.encoder_identity.model_dump(mode="python", round_trip=True)
        )
        if encoder.kind != "image_encoder":
            raise ValueError("Visual influence approval requires an image encoder")
        renderers = tuple(
            ProviderIdentity.model_validate(
                identity.model_dump(mode="python", round_trip=True)
            )
            for identity in self.approved_renderer_identities
        )
        if any(identity.kind != "image_renderer" for identity in renderers):
            raise ValueError(
                "Visual influence approval accepts only image renderer identities"
            )
        renderer_ids = tuple(identity.provider_id for identity in renderers)
        if renderer_ids != tuple(sorted(set(renderer_ids))):
            raise ValueError(
                "Approved visual renderers must use unique canonical order"
            )
        renderer_backends = tuple(
            (
                identity.implementation,
                identity.implementation_revision,
                identity.model,
                identity.model_revision,
            )
            for identity in renderers
        )
        if len(set(renderer_backends)) != len(renderer_backends):
            raise ValueError(
                "Approved visual renderers must use distinct implementation/model "
                "backends, not provider aliases"
            )
        if self.evaluated_seeds != tuple(sorted(set(self.evaluated_seeds))):
            raise ValueError("Evaluated visual seeds must be sorted and unique")
        profiles = tuple(
            ApprovedVisualPromptProfile.model_validate(
                profile.model_dump(mode="python", round_trip=True)
            )
            for profile in self.approved_prompt_profiles
        )
        profile_keys = tuple(
            (profile.language, profile.style_id, profile.profile_hash)
            for profile in profiles
        )
        if profile_keys != tuple(sorted(set(profile_keys))):
            raise ValueError(
                "Approved visual prompt profiles must use unique canonical order"
            )
        languages = {profile.language for profile in profiles}
        if languages != {"en", "sl"}:
            raise ValueError(
                "Visual influence approval requires Slovenian and English review"
            )
        styles = {profile.style_id for profile in profiles}
        if len(styles) < 2:
            raise ValueError(
                "Visual influence approval requires at least two reviewed styles"
            )
        reviewed_language_styles = {
            (profile.language, profile.style_id) for profile in profiles
        }
        required_language_styles = {
            (language, style_id)
            for language in languages
            for style_id in styles
        }
        if reviewed_language_styles != required_language_styles or len(
            profiles
        ) != len(required_language_styles):
            raise ValueError(
                "Every reviewed visual style requires exactly one Slovenian and "
                "one English profile"
            )
        canonical_hash_fields = (
            (
                self.reviewed_visual_state_hashes,
                "reviewed visual-state hashes",
            ),
            (
                self.approved_encoding_spec_hashes,
                "approved encoding-spec hashes",
            ),
            (
                self.approved_runtime_profile_hashes,
                "approved runtime-profile hashes",
            ),
        )
        for values, field_name in canonical_hash_fields:
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")
        cells = tuple(
            ReviewedVisualCohortCell.model_validate(
                cell.model_dump(mode="python", round_trip=True)
            )
            for cell in self.reviewed_cohort_cells
        )
        cell_keys = tuple(_reviewed_cell_sort_key(cell) for cell in cells)
        if cell_keys != tuple(sorted(set(cell_keys))):
            raise ValueError(
                "Reviewed visual cohort cells must use unique canonical order"
            )
        approved_renderers = set(renderers)
        approved_profiles = set(profiles)
        if any(cell.renderer_identity not in approved_renderers for cell in cells):
            raise ValueError("Reviewed visual cell uses an unapproved renderer")
        if any(cell.prompt_profile not in approved_profiles for cell in cells):
            raise ValueError("Reviewed visual cell uses an unapproved prompt profile")
        if any(cell.evaluation_seed not in self.evaluated_seeds for cell in cells):
            raise ValueError("Reviewed visual cell uses an unevaluated seed")
        if any(
            cell.visual_state_hash not in self.reviewed_visual_state_hashes
            for cell in cells
        ):
            raise ValueError("Reviewed visual cell uses an unreviewed visual state")
        if {
            cell.encoding_spec_hash for cell in cells
        } != set(self.approved_encoding_spec_hashes):
            raise ValueError(
                "Reviewed visual cells must exactly cover approved encoding specs"
            )
        if len(self.approved_encoding_spec_hashes) != 1:
            raise ValueError(
                "One visual influence approval requires one exact encoding spec"
            )
        if {
            cell.runtime_profile_hash for cell in cells
        } != set(self.approved_runtime_profile_hashes):
            raise ValueError(
                "Reviewed visual cells must exactly cover approved runtime profiles"
            )

        orders_by_state: dict[str, set[tuple[str, ...]]] = {}
        for cell in cells:
            orders_by_state.setdefault(cell.visual_state_hash, set()).add(
                cell.option_order
            )
        if set(orders_by_state) != set(self.reviewed_visual_state_hashes):
            raise ValueError("Every reviewed visual state requires cohort cells")
        for orders in orders_by_state.values():
            if len(orders) != 2:
                raise ValueError(
                    "Every reviewed visual state requires canonical and reversed "
                    "option-order cells"
                )
            first, second = sorted(orders)
            if tuple(reversed(first)) != second and tuple(reversed(second)) != first:
                raise ValueError(
                    "Reviewed option orders must be exact reversals"
                )

        expected_coordinates = {
            (
                visual_state_hash,
                seed,
                renderer.provider_id,
                renderer.content_hash(),
                profile.language,
                profile.style_id,
                profile.profile_hash,
                option_order,
            )
            for visual_state_hash, option_orders in orders_by_state.items()
            for seed in self.evaluated_seeds
            for renderer in renderers
            for profile in profiles
            for option_order in option_orders
        }
        actual_coordinates = {
            _reviewed_cell_coordinate(cell) for cell in cells
        }
        if actual_coordinates != expected_coordinates:
            raise ValueError(
                "Visual influence approval lacks exact state/seed/renderer/"
                "language/style/option-order cohort coverage"
            )

        runtime_profiles: dict[tuple[str, str, str, str], set[str]] = {}
        for cell in cells:
            key = (
                cell.renderer_identity.provider_id,
                cell.prompt_profile.language,
                cell.prompt_profile.style_id,
                cell.prompt_profile.profile_hash,
            )
            runtime_profiles.setdefault(key, set()).add(
                cell.runtime_profile_hash
            )
        if any(len(hashes) != 1 for hashes in runtime_profiles.values()):
            raise ValueError(
                "Each renderer/prompt profile requires one exact runtime profile"
            )
        runtime_profile_values = {
            next(iter(hashes)) for hashes in runtime_profiles.values()
        }
        if (
            len(runtime_profile_values) != len(runtime_profiles)
            or runtime_profile_values != set(self.approved_runtime_profile_hashes)
        ):
            raise ValueError(
                "Renderer/prompt combinations require distinct exact runtime profiles"
            )

        order_robustness: dict[
            tuple[str, int, str, str, str, str],
            set[tuple[str, str, float]],
        ] = {}
        for cell in cells:
            key = (
                cell.visual_state_hash,
                cell.evaluation_seed,
                cell.renderer_identity.provider_id,
                cell.prompt_profile.language,
                cell.prompt_profile.style_id,
                cell.prompt_profile.profile_hash,
            )
            order_robustness.setdefault(key, set()).add(
                (
                    cell.prompt_batch_hash,
                    cell.approved_leading_option_id,
                    cell.minimum_leading_margin,
                )
            )
        if any(len(outcomes) != 1 for outcomes in order_robustness.values()):
            raise ValueError(
                "Canonical and reversed option order must preserve prompts, "
                "reviewed leader, and minimum margin"
            )
        expected_id = content_id(
            "visual_influence_approval",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"approval_id"},
            ),
        )
        if self.approval_id != expected_id:
            raise ValueError(
                "Visual influence approval ID differs from canonical content"
            )
        return self

    def validate_against(
        self,
        *,
        policy_config: VisualValuationPolicyConfig,
        valuation: VisualValuationResult,
        visual_state: EmocioVisualState,
        observations: tuple[BoundVisualEmbedding, ...],
        option_order: tuple[str, ...],
    ) -> Self:
        """Bind the approval to the exact usable runtime valuation cohort."""

        validated = type(self).model_validate(
            self.model_dump(mode="python", round_trip=True)
        )
        config = VisualValuationPolicyConfig.model_validate(
            policy_config.model_dump(mode="python", round_trip=True)
        )
        result = VisualValuationResult.model_validate(
            valuation.model_dump(mode="python", round_trip=True)
        )
        cohort = tuple(
            BoundVisualEmbedding.model_validate(
                observation.model_dump(mode="python", round_trip=True)
            )
            for observation in observations
        )
        result.validate_against(
            visual_state=visual_state,
            observations=cohort,
            include_cross_seed_consistency=None,
        )
        if visual_state.content_hash() not in validated.reviewed_visual_state_hashes:
            raise ValueError(
                "Runtime visual state is outside the reviewed semantic case scope"
            )
        encoding_spec_hashes = {
            observation.encoding.request.spec.content_hash()
            for observation in cohort
        }
        if (
            len(encoding_spec_hashes) != 1
            or not encoding_spec_hashes.issubset(
                set(validated.approved_encoding_spec_hashes)
            )
        ):
            raise ValueError(
                "Runtime encoding spec is outside the approved visual feature space"
            )
        runtime_profile_hash = visual_cognition_runtime_profile_hash(cohort)
        if runtime_profile_hash not in validated.approved_runtime_profile_hashes:
            raise ValueError(
                "Runtime renderer/encoder profile is outside the reviewed scope"
            )
        if (
            validated.policy_config_id != config.config_id
            or validated.policy_config_hash != config.content_hash()
            or result.policy != config.policy
        ):
            raise ValueError(
                "Visual influence approval differs from the valuation policy config"
            )
        if result.integration_disposition != "usable":
            raise ValueError(
                "Only a usable visual valuation may influence native output"
            )
        if result.encoder_identity != validated.encoder_identity:
            raise ValueError(
                "Visual influence approval differs from the runtime encoder"
            )
        if not cohort:
            raise ValueError("Visual influence approval requires observations")
        if (
            len(option_order) != len(set(option_order))
            or set(option_order)
            != {score.option_id for score in result.option_scores}
        ):
            raise ValueError(
                "Runtime option order differs from the visual valuation scope"
            )
        runtime_seeds = {observation.evaluation_seed for observation in cohort}
        if len(runtime_seeds) != 1:
            raise ValueError(
                "One visual influence decision requires exactly one runtime seed"
            )
        if not runtime_seeds.issubset(set(validated.evaluated_seeds)):
            raise ValueError(
                "Runtime visual seed is outside the reviewed robustness cohort"
            )
        approved_renderers = set(validated.approved_renderer_identities)
        approved_profiles = set(validated.approved_prompt_profiles)
        runtime_renderers: set[ProviderIdentity] = set()
        runtime_profiles: set[ApprovedVisualPromptProfile] = set()
        for observation in cohort:
            matching_items = tuple(
                item
                for item in observation.render_batch.items
                if item.request.source_spec_id == observation.scene_spec.scene_id
            )
            if len(matching_items) != 1:
                raise ValueError(
                    "Approved visual observation has no exact render item"
                )
            request = matching_items[0].request
            runtime_renderers.add(request.provider)
            if request.provider not in approved_renderers:
                raise ValueError(
                    "Runtime visual renderer is outside the approved cohort"
                )
            runtime_profile = (
                ApprovedVisualPromptProfile(
                    language=request.prompt_language,
                    style_id=request.style_id,
                    profile_hash=request.profile_hash,
                )
                if request.prompt_language is not None
                and request.style_id is not None
                and request.profile_hash is not None
                else None
            )
            if (
                request.prompt_language is None
                or request.style_id is None
                or request.profile_hash is None
                or runtime_profile not in approved_profiles
            ):
                raise ValueError(
                    "Runtime visual prompt profile is outside the approved cohort"
                )
            assert runtime_profile is not None
            runtime_profiles.add(runtime_profile)
        if len(runtime_renderers) != 1 or len(runtime_profiles) != 1:
            raise ValueError(
                "Runtime visual cohort requires one renderer and prompt profile"
            )
        runtime_renderer = next(iter(runtime_renderers))
        runtime_profile = next(iter(runtime_profiles))
        runtime_encoding_spec_hash = next(iter(encoding_spec_hashes))
        runtime_prompt_batch_hash = visual_cognition_prompt_batch_hash(cohort)
        matching_cells = tuple(
            cell
            for cell in validated.reviewed_cohort_cells
            if cell.visual_state_hash == visual_state.content_hash()
            and cell.evaluation_seed in runtime_seeds
            and cell.renderer_identity == runtime_renderer
            and cell.prompt_profile == runtime_profile
            and cell.option_order == option_order
            and cell.encoding_spec_hash == runtime_encoding_spec_hash
            and cell.runtime_profile_hash == runtime_profile_hash
            and cell.prompt_batch_hash == runtime_prompt_batch_hash
        )
        if len(matching_cells) != 1:
            raise ValueError(
                "Runtime visual prompt/result cell is outside the reviewed cohort"
            )
        reviewed_cell = matching_cells[0]
        if result.leading_option_id != reviewed_cell.approved_leading_option_id:
            raise ValueError(
                "Runtime visual leader differs from the semantically reviewed direction"
            )
        ranked_scores = sorted(
            (score.fused_score for score in result.option_scores), reverse=True
        )
        leading_margin = (
            1.0
            if len(ranked_scores) == 1
            else round(ranked_scores[0] - ranked_scores[1], 12)
        )
        if leading_margin < reviewed_cell.minimum_leading_margin:
            raise ValueError(
                "Runtime visual leader margin is below the reviewed threshold"
            )
        return self


class PinnedVisualInfluenceAuthority(FrozenArtifactModel):
    """Explicit trust root admitting reviewed visual approvals by exact hash."""

    schema_version: Literal["rei-native-visual-influence-authority-v1"] = (
        "rei-native-visual-influence-authority-v1"
    )
    authority_id: NonEmptyId
    authority_name: NonEmptyText
    trust_root_hash: HashDigest
    admitted_approvals: tuple[AdmittedVisualInfluenceApproval, ...] = Field(
        min_length=1
    )

    @classmethod
    def create(
        cls,
        *,
        authority_name: str,
        trust_root_hash: str,
        admitted_approvals: tuple[VisualNativeInfluenceApproval, ...],
    ) -> PinnedVisualInfluenceAuthority:
        admitted = tuple(
            sorted(
                (
                    AdmittedVisualInfluenceApproval(
                        approval_id=approval.approval_id,
                        approval_hash=approval.content_hash(),
                    )
                    for approval in admitted_approvals
                ),
                key=lambda item: item.approval_id,
            )
        )
        payload = {
            "schema_version": "rei-native-visual-influence-authority-v1",
            "authority_name": authority_name,
            "trust_root_hash": trust_root_hash,
            "admitted_approvals": admitted,
        }
        return cls(
            authority_id=content_id("visual_influence_authority", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_authority(self) -> Self:
        admitted = tuple(
            AdmittedVisualInfluenceApproval.model_validate(
                item.model_dump(mode="python", round_trip=True)
            )
            for item in self.admitted_approvals
        )
        approval_ids = tuple(item.approval_id for item in admitted)
        if approval_ids != tuple(sorted(set(approval_ids))):
            raise ValueError(
                "Admitted visual approvals must use unique canonical order"
            )
        expected_id = content_id(
            "visual_influence_authority",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"authority_id"},
            ),
        )
        if self.authority_id != expected_id:
            raise ValueError(
                "Visual influence authority ID differs from canonical content"
            )
        return self

    def admit(
        self,
        approval: VisualNativeInfluenceApproval,
    ) -> VisualNativeInfluenceApproval:
        """Require the approval's exact ID and bytes in this trust root."""

        authority = type(self).model_validate(
            self.model_dump(mode="python", round_trip=True)
        )
        validated = VisualNativeInfluenceApproval.model_validate(
            approval.model_dump(mode="python", round_trip=True)
        )
        admitted = AdmittedVisualInfluenceApproval(
            approval_id=validated.approval_id,
            approval_hash=validated.content_hash(),
        )
        if admitted not in authority.admitted_approvals:
            raise ValueError(
                "Visual influence approval is outside the pinned trust root"
            )
        return validated


# Deliberately empty until a reviewed authority artifact is pinned by a scoped
# repository commit. Runtime callers cannot authorize themselves by merely
# constructing an approval and an authority with arbitrary evidence hashes.
REPOSITORY_PINNED_VISUAL_INFLUENCE_AUTHORITIES: frozenset[
    tuple[str, str]
] = frozenset()


def require_repository_pinned_visual_authority(
    authority: PinnedVisualInfluenceAuthority,
) -> PinnedVisualInfluenceAuthority:
    """Admit only an authority whose exact ID and bytes are pinned in source."""

    validated = PinnedVisualInfluenceAuthority.model_validate(
        authority.model_dump(mode="python", round_trip=True)
    )
    identity = (validated.authority_id, validated.content_hash())
    if identity not in REPOSITORY_PINNED_VISUAL_INFLUENCE_AUTHORITIES:
        raise ValueError(
            "Visual influence authority is not pinned by repository configuration"
        )
    return validated


class VisualCognitionFailure(FrozenArtifactModel):
    """Content-addressed failure boundary for an attempted visual stage."""

    schema_version: Literal["rei-native-visual-cognition-failure-v1"] = (
        "rei-native-visual-cognition-failure-v1"
    )
    failure_id: NonEmptyId
    stage: VisualCognitionFailureStage
    failure_code: NonEmptyText
    failure_message: NonEmptyText
    render_batch_id: NonEmptyId | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    render_batch_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    observation_ids: tuple[NonEmptyId, ...] = ()
    observation_hashes: tuple[HashDigest, ...] = ()
    attempted_call_spec: ProviderCallSpec | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_valuation_result_id: NonEmptyId | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_valuation_result_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_approval_id: NonEmptyId | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_approval_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_authority_id: NonEmptyId | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    visual_influence_authority_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    internal_only: Literal[True] = True
    external_evidence_claim: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        stage: VisualCognitionFailureStage,
        error: Exception,
        render_batch: ImageRenderBatchOutcome | None = None,
        observations: tuple[BoundVisualEmbedding, ...] = (),
        attempted_call_spec: ProviderCallSpec | None = None,
        valuation: VisualValuationResult | None = None,
        approval: VisualNativeInfluenceApproval | None = None,
        authority: PinnedVisualInfluenceAuthority | None = None,
    ) -> VisualCognitionFailure:
        code, message = visual_failure_summary(stage, error)
        payload = {
            "schema_version": "rei-native-visual-cognition-failure-v1",
            "stage": stage,
            "failure_code": code,
            "failure_message": message,
            "observation_ids": tuple(item.observation_id for item in observations),
            "observation_hashes": tuple(
                item.content_hash() for item in observations
            ),
            "internal_only": True,
            "external_evidence_claim": False,
        }
        if render_batch is not None:
            payload.update(
                render_batch_id=render_batch.batch_id,
                render_batch_hash=render_batch.content_hash(),
            )
        if attempted_call_spec is not None:
            payload["attempted_call_spec"] = ProviderCallSpec.model_validate(
                attempted_call_spec.model_dump(mode="python", round_trip=True)
            )
        if valuation is not None:
            payload.update(
                visual_valuation_result_id=valuation.result_id,
                visual_valuation_result_hash=valuation.content_hash(),
            )
        if approval is not None:
            payload.update(
                visual_influence_approval_id=approval.approval_id,
                visual_influence_approval_hash=approval.content_hash(),
            )
        if authority is not None:
            payload.update(
                visual_influence_authority_id=authority.authority_id,
                visual_influence_authority_hash=authority.content_hash(),
            )
        return cls(
            failure_id=content_id("visual_cognition_failure", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        if len(self.observation_ids) != len(self.observation_hashes):
            raise ValueError(
                "Visual failure observation IDs and hashes must have equal length"
            )
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("Visual failure observation IDs must be unique")
        valuation_lineage = (
            self.visual_valuation_result_id,
            self.visual_valuation_result_hash,
        )
        approval_lineage = (
            self.visual_influence_approval_id,
            self.visual_influence_approval_hash,
        )
        authority_lineage = (
            self.visual_influence_authority_id,
            self.visual_influence_authority_hash,
        )
        batch_lineage = (self.render_batch_id, self.render_batch_hash)
        if any(item is not None for item in batch_lineage) != all(
            item is not None for item in batch_lineage
        ):
            raise ValueError("Visual failure render-batch lineage must be paired")
        if any(item is not None for item in valuation_lineage) != all(
            item is not None for item in valuation_lineage
        ):
            raise ValueError("Visual failure valuation lineage must be paired")
        if any(item is not None for item in approval_lineage) != all(
            item is not None for item in approval_lineage
        ):
            raise ValueError("Visual failure approval lineage must be paired")
        if any(item is not None for item in authority_lineage) != all(
            item is not None for item in authority_lineage
        ):
            raise ValueError("Visual failure authority lineage must be paired")
        if self.stage == "policy_config" and (
            self.observation_ids or self.visual_valuation_result_id is not None
        ):
            raise ValueError(
                "Early visual failure cannot cite downstream observations or valuation"
            )
        if self.stage == "render" and (
            self.observation_ids
            or self.attempted_call_spec is not None
            or self.visual_valuation_result_id is not None
            or self.visual_influence_approval_id is not None
            or self.visual_influence_authority_id is not None
        ):
            raise ValueError(
                "Visual render failure cannot cite downstream visual artifacts"
            )
        if self.stage != "render" and self.render_batch_id is None:
            raise ValueError(
                "Post-render visual failure requires exact render-batch lineage"
            )
        if self.stage == "encoding" and self.visual_valuation_result_id is not None:
            raise ValueError("Encoding failure cannot cite a visual valuation")
        if self.stage == "valuation" and (
            not self.observation_ids
            or self.visual_valuation_result_id is not None
        ):
            raise ValueError(
                "Visual valuation failure requires observations and no result"
            )
        if self.stage in {"memory", "approval"} and (
            not self.observation_ids
            or self.visual_valuation_result_id is None
        ):
            raise ValueError(
                "Late visual failure requires observations and valuation result"
            )
        if self.stage != "approval" and self.visual_influence_approval_id is not None:
            raise ValueError("Only approval failure may cite an approval artifact")
        if self.stage != "approval" and self.visual_influence_authority_id is not None:
            raise ValueError("Only approval failure may cite an authority artifact")
        if self.attempted_call_spec is not None:
            call = ProviderCallSpec.model_validate(
                self.attempted_call_spec.model_dump(
                    mode="python",
                    round_trip=True,
                )
            )
            if self.stage != "encoding":
                raise ValueError(
                    "Only encoding failure may cite an attempted provider call"
                )
            if (
                call.provider.kind != "image_encoder"
                or call.fallback_policy.mode != "none"
                or len(call.input_artifact_ids) != 1
            ):
                raise ValueError(
                    "Attempted visual encoding call must be direct and exact"
                )
        expected_id = content_id(
            "visual_cognition_failure",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"failure_id"},
            ),
        )
        if self.failure_id != expected_id:
            raise ValueError(
                "Visual cognition failure ID differs from canonical content"
            )
        return self

    def validate_against(
        self,
        *,
        render_batch: ImageRenderBatchOutcome | None,
        observations: tuple[BoundVisualEmbedding, ...],
        valuation: VisualValuationResult | None,
        approval: VisualNativeInfluenceApproval | None,
        authority: PinnedVisualInfluenceAuthority | None,
    ) -> Self:
        validated = type(self).model_validate(
            self.model_dump(mode="python", round_trip=True)
        )
        if observations:
            if render_batch is None:
                raise ValueError(
                    "Visual failure observations require their exact render batch"
                )
            if any(
                observation.render_batch != render_batch
                for observation in observations
            ):
                raise ValueError(
                    "Visual failure observation belongs to another render batch"
                )
        if validated.attempted_call_spec is not None:
            if render_batch is None:
                raise ValueError(
                    "Attempted encoding call requires the exact render batch"
                )
            render_image_ids = {
                item.artifact.image_id
                for item in render_batch.items
                if item.artifact is not None
            }
            if not set(
                validated.attempted_call_spec.input_artifact_ids
            ).issubset(render_image_ids):
                raise ValueError(
                    "Attempted encoding call leaves the exact render batch"
                )
        if (
            validated.render_batch_id
            != (None if render_batch is None else render_batch.batch_id)
            or validated.render_batch_hash
            != (None if render_batch is None else render_batch.content_hash())
            or validated.observation_ids
            != tuple(item.observation_id for item in observations)
            or validated.observation_hashes
            != tuple(item.content_hash() for item in observations)
            or validated.visual_valuation_result_id
            != (None if valuation is None else valuation.result_id)
            or validated.visual_valuation_result_hash
            != (None if valuation is None else valuation.content_hash())
            or validated.visual_influence_approval_id
            != (None if approval is None else approval.approval_id)
            or validated.visual_influence_approval_hash
            != (None if approval is None else approval.content_hash())
            or validated.visual_influence_authority_id
            != (None if authority is None else authority.authority_id)
            or validated.visual_influence_authority_hash
            != (None if authority is None else authority.content_hash())
        ):
            raise ValueError(
                "Visual cognition failure differs from its exact source artifacts"
            )
        return self


@dataclass(frozen=True, slots=True)
class VisualCognitionArtifacts:
    """Replayable internal artifacts produced before the approval decision."""

    observations: tuple[BoundVisualEmbedding, ...]
    valuation: VisualValuationResult
    memories: tuple[VisualWorldMemoryRecord, ...]


def _encode_visual_scene_observation(
    *,
    scene: VisualSceneSpec,
    item: ImageRenderItemOutcome | None,
    render_batch: ImageRenderBatchOutcome,
    encoder: VerifiedImageEncoder,
    encoder_identity: ProviderIdentity,
    encoder_spec: ImageEncodingSpec,
    encoding_timeout_seconds: PositiveSeconds,
) -> BoundVisualEmbedding:
    """Build one observation or preserve the exact attempted encoder call."""

    attempted_call: ProviderCallSpec | None = None
    try:
        if (
            item is None
            or item.artifact is None
            or item.call_record.status != "succeeded"
            or item.call_record.primary_status != "succeeded"
            or item.call_record.fallback is not None
        ):
            raise ValueError(
                "Visual cognition requires one direct successful image per scene"
            )
        image = item.artifact
        imagined = ImaginedVisualArtifact(
            artifact_id=image.image_id,
            originating_scene_spec_id=scene.scene_id,
            option_id=scene.option_id,
            seed=image.seed,
            model_identity=item.request.provider,
            ungrounded_elements=image.generated_only_elements,
        )
        imagined.validate_against(image, scene)
        request = ImageEncodingRequest.model_validate(
            encoder.request_for(image).model_dump(
                mode="python",
                round_trip=True,
            )
        )
        if request.provider != encoder_identity or request.spec != encoder_spec:
            raise ValueError(
                "Image encoder request differs from its advertised identity or spec"
            )
        request.validate_image(image)
        attempted_call = ProviderCallSpec.model_validate(
            encoder.build_call_spec(
                image,
                timeout_seconds=encoding_timeout_seconds,
            ).model_dump(mode="python", round_trip=True)
        )
        ensure_call_contract(
            encoder_identity,
            attempted_call,
            request_id=request.request_id,
            expected_kind="image_encoder",
            required_input_artifact_ids=(image.image_id,),
        )
        if (
            attempted_call.request_id != request.request_id
            or attempted_call.input_artifact_ids != (image.image_id,)
            or attempted_call.parameters != request.provider_parameters
            or attempted_call.fallback_policy.mode != "none"
        ):
            raise ValueError(
                "Image encoder call differs from its immutable request"
            )
        encoding = VerifiedImageEncoding.model_validate(
            encoder.encode(image, call=attempted_call).model_dump(
                mode="python",
                round_trip=True,
            )
        )
        if encoding.request != request:
            raise ValueError(
                "Image encoder result differs from its immutable request"
            )
        vector = encoder.read_vector(encoding)
        return BoundVisualEmbedding.create(
            role=scene.scene_kind,
            evaluation_seed=render_batch.root_seed,
            render_batch=render_batch,
            scene_spec=scene,
            image=image,
            imagined=imagined,
            encoding=encoding,
            vector=vector,
        )
    except VisualObservationBuildError:
        raise
    except Exception as exc:
        raise VisualObservationBuildError(
            cause=exc,
            attempted_call_spec=attempted_call,
        ) from None


def build_visual_observations(
    *,
    visual_state: EmocioVisualState,
    render_batch: ImageRenderBatchOutcome,
    encoder: VerifiedImageEncoder,
    encoding_timeout_seconds: PositiveSeconds,
) -> tuple[BoundVisualEmbedding, ...]:
    """Encode every exact successful batch image with closed provenance."""

    visual_state = EmocioVisualState.model_validate(
        visual_state.model_dump(mode="python", round_trip=True)
    )
    render_batch = ImageRenderBatchOutcome.model_validate(
        render_batch.model_dump(mode="python", round_trip=True)
    )
    scenes = (
        visual_state.current_scene,
        visual_state.desired_scene,
        visual_state.broken_scene,
        *visual_state.option_rollouts,
    )
    validate_render_batch(
        render_batch,
        scenes,
        expected_seed=render_batch.root_seed,
    )
    if render_batch.status != "succeeded":
        raise ValueError("Visual cognition requires a succeeded render batch")
    encoder_identity = ProviderIdentity.model_validate(
        encoder.identity.model_dump(mode="python", round_trip=True)
    )
    if encoder_identity.kind != "image_encoder":
        raise ValueError("Visual cognition requires an image_encoder identity")
    encoder_spec = ImageEncodingSpec.model_validate(
        encoder.encoding_spec().model_dump(mode="python", round_trip=True)
    )
    item_by_scene = {
        item.request.source_spec_id: item for item in render_batch.items
    }
    observations: list[BoundVisualEmbedding] = []
    for scene in scenes:
        item = item_by_scene.get(scene.scene_id)
        try:
            observations.append(
                _encode_visual_scene_observation(
                    scene=scene,
                    item=item,
                    render_batch=render_batch,
                    encoder=encoder,
                    encoder_identity=encoder_identity,
                    encoder_spec=encoder_spec,
                    encoding_timeout_seconds=encoding_timeout_seconds,
                )
            )
        except VisualObservationBuildError as exc:
            raise exc.with_partial_observations(tuple(observations)) from None
    return tuple(observations)


def evaluate_visual_cognition(
    *,
    visual_state: EmocioVisualState,
    render_batch: ImageRenderBatchOutcome,
    encoder: VerifiedImageEncoder,
    policy_config: VisualValuationPolicyConfig,
    encoding_timeout_seconds: PositiveSeconds,
) -> VisualCognitionArtifacts:
    """Build a one-seed valuation and hypothetical rollout memories."""

    observations = build_visual_observations(
        visual_state=visual_state,
        render_batch=render_batch,
        encoder=encoder,
        encoding_timeout_seconds=encoding_timeout_seconds,
    )
    valuation = evaluate_visual_valuation(
        policy=policy_config.policy,
        visual_state=visual_state,
        observations=observations,
        include_cross_seed_consistency=False,
    )
    memories = tuple(
        build_visual_world_memory_record(
            observation=observation,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )
        for observation in observations
        if observation.role == "option_rollout"
    )
    return VisualCognitionArtifacts(
        observations=observations,
        valuation=valuation,
        memories=memories,
    )


def policy_from_visual_valuation(
    *,
    visual_state: EmocioVisualState,
    valuation: VisualValuationResult,
) -> EmocioPolicyDecision:
    """Project one approved unique visual leader into the native policy shape."""

    if (
        valuation.integration_disposition != "usable"
        or valuation.leading_option_id is None
        or valuation.tied_option_ids
    ):
        raise ValueError("Visual native policy requires one usable unique leader")
    valuation_by_option = {
        item.option_id: item for item in visual_state.option_valuations
    }
    selected = valuation_by_option.get(valuation.leading_option_id)
    if selected is None:
        raise ValueError("Visual leader is outside the structured option scope")
    scores = tuple(
        OptionAggregateScore(
            option_id=item.option_id,
            score=item.fused_score,
        )
        for item in valuation.option_scores
    )
    return EmocioPolicyDecision(
        selected=selected,
        aggregate_scores=scores,
    )


__all__ = [
    "AdmittedVisualInfluenceApproval",
    "ApprovedVisualPromptProfile",
    "PinnedVisualInfluenceAuthority",
    "ReviewedVisualCohortCell",
    "VisualCognitionArtifacts",
    "VisualCognitionFailure",
    "VisualCognitionFailureStage",
    "VisualNativeInfluenceApproval",
    "VisualObservationBuildError",
    "build_visual_observations",
    "evaluate_visual_cognition",
    "policy_from_visual_valuation",
    "require_repository_pinned_visual_authority",
    "visual_cognition_prompt_batch_hash",
    "visual_cognition_runtime_profile_hash",
    "visual_failure_summary",
]
