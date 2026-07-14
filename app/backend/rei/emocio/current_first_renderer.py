"""Current-scene-first rendering for visual Emocio option rollouts.

The coordinator deliberately renders the frozen current scene before any
counterfactual rollout.  Every rollout then receives one byte-addressed
reference to that exact generated artifact; it never independently recreates
or substitutes a source image.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from ..models.common import FrozenModel, Score01
from ..models.emocio import ImageArtifact, VisualSceneSpec
from ..models.rendering import (
    ImageRenderBatchOutcome,
    ImageRenderBatchStatus,
    ImageRenderItemOutcome,
    ImageRenderPreparationFailure,
    ImageSourceReference,
)
from ..providers.protocols import ImageRenderer
from .renderer import (
    LocalEmocioRenderer,
    RenderSettings,
    ScenePromptCompiler,
    StructuredScenePromptCompiler,
)


RolloutConditioningMethod = Literal["reference_image", "classic_strength"]


class CurrentFirstRolloutConfig(FrozenModel):
    """Explicit image-conditioning contract for option rollouts."""

    conditioning_method: RolloutConditioningMethod = "reference_image"
    classic_strength: Score01 | None = None

    @model_validator(mode="after")
    def validate_conditioning(self) -> Self:
        if self.conditioning_method == "reference_image":
            if self.classic_strength is not None:
                raise ValueError(
                    "reference_image conditioning cannot carry classic_strength"
                )
        elif self.classic_strength is None:
            raise ValueError(
                "classic_strength conditioning requires an explicit strength"
            )
        return self


def _validate_scene_order(
    scenes: tuple[VisualSceneSpec, ...],
) -> tuple[VisualSceneSpec, VisualSceneSpec, VisualSceneSpec, tuple[VisualSceneSpec, ...]]:
    if len(scenes) < 3:
        raise ValueError(
            "Current-first rendering requires current, desired, and broken scenes"
        )
    scene_ids = tuple(scene.scene_id for scene in scenes)
    if len(set(scene_ids)) != len(scene_ids):
        raise ValueError("Current-first renderer input scene IDs must be unique")

    current, desired, broken, *rollout_list = scenes
    expected_roles = (
        ("first", current, "current"),
        ("second", desired, "desired"),
        ("third", broken, "broken"),
    )
    for position, scene, expected_kind in expected_roles:
        if scene.scene_kind != expected_kind:
            raise ValueError(
                f"Current-first renderer {position} scene must be {expected_kind}"
            )

    rollouts = tuple(rollout_list)
    if any(scene.scene_kind != "option_rollout" for scene in rollouts):
        raise ValueError(
            "Current-first renderer accepts only option rollouts after broken"
        )
    option_ids = tuple(scene.option_id for scene in rollouts)
    if len(set(option_ids)) != len(option_ids):
        raise ValueError("Current-first rollout option IDs must be unique")
    if option_ids != tuple(sorted(option_ids)):
        raise ValueError(
            "Current-first option rollouts must use canonical option_id order"
        )
    return current, desired, broken, rollouts


def _batch_status(
    *,
    source_count: int,
    items: tuple[ImageRenderItemOutcome, ...],
) -> ImageRenderBatchStatus:
    successes = sum(item.artifact is not None for item in items)
    if successes == source_count:
        return "succeeded"
    if successes == 0:
        return "failed"
    return "partial"


class CurrentFirstEmocioRenderer:
    """Render the current scene once and reuse it for every option rollout.

    Current, desired, and broken scenes are text-to-image requests.  Rollouts
    are image-conditioned requests whose source is constructed only with
    :meth:`ImageSourceReference.from_artifact_with_scene_lineage` from the
    validated current-scene outcome.  The underlying provider is called directly
    by :class:`LocalEmocioRenderer`, whose approved call specs forbid fallback.
    """

    def __init__(
        self,
        *,
        provider: ImageRenderer,
        settings: RenderSettings,
        prompt_compiler: ScenePromptCompiler | None = None,
        rollout: CurrentFirstRolloutConfig | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._prompt_compiler = prompt_compiler or StructuredScenePromptCompiler()
        self._rollout = rollout or CurrentFirstRolloutConfig()

    def _text_renderer(self) -> LocalEmocioRenderer:
        return LocalEmocioRenderer(
            provider=self._provider,
            settings=self._settings,
            prompt_compiler=self._prompt_compiler,
        )

    def _rollout_renderer(
        self,
        rollouts: tuple[VisualSceneSpec, ...],
        source: ImageSourceReference,
    ) -> LocalEmocioRenderer:
        sources = {scene.scene_id: source for scene in rollouts}
        conditioning = {
            scene.scene_id: self._rollout.conditioning_method for scene in rollouts
        }
        strengths = (
            {
                scene.scene_id: self._rollout.classic_strength
                for scene in rollouts
            }
            if self._rollout.conditioning_method == "classic_strength"
            else {}
        )
        return LocalEmocioRenderer(
            provider=self._provider,
            settings=self._settings,
            prompt_compiler=self._prompt_compiler,
            image_to_image_sources=sources,
            image_to_image_strengths=strengths,
            image_to_image_conditioning=conditioning,
        )

    @staticmethod
    def _current_artifact(
        batch: ImageRenderBatchOutcome,
        current: VisualSceneSpec,
    ) -> ImageArtifact | None:
        for item in batch.items:
            if item.request.source_spec_id == current.scene_id:
                return item.artifact
        return None

    def render(
        self,
        scenes: tuple[VisualSceneSpec, ...],
        *,
        seed: int,
    ) -> ImageRenderBatchOutcome:
        current, desired, broken, rollouts = _validate_scene_order(scenes)

        # Ordering is operationally significant: establish the one reusable
        # current image before any other scene or rollout can be attempted.
        current_batch = self._text_renderer().render((current,), seed=seed)
        context_batch = self._text_renderer().render(
            (desired, broken),
            seed=seed,
        )
        sub_batches = [current_batch, context_batch]
        extra_failures: tuple[ImageRenderPreparationFailure, ...] = ()
        extra_warnings: tuple[str, ...] = ()

        current_artifact = self._current_artifact(current_batch, current)
        source: ImageSourceReference | None = None
        if current_artifact is not None:
            try:
                source = ImageSourceReference.from_artifact_with_scene_lineage(
                    current_artifact
                )
            except Exception as exc:
                message = " ".join(str(exc).split())[:500] or type(exc).__name__
                extra_warnings = (
                    "Current scene artifact could not become a verified rollout "
                    f"source: {message}",
                )

        if rollouts and source is not None:
            sub_batches.append(
                self._rollout_renderer(rollouts, source).render(
                    rollouts,
                    seed=seed,
                )
            )
        elif rollouts:
            message = (
                "Current scene render is unavailable; option rollout image "
                "conditioning was not attempted and no provider fallback is allowed"
            )
            extra_failures = tuple(
                ImageRenderPreparationFailure.create(
                    source_spec=scene,
                    failure_code="current_scene_render_unavailable",
                    failure_message=message,
                )
                for scene in rollouts
            )
            extra_warnings = (*extra_warnings, message)

        item_by_scene: dict[str, ImageRenderItemOutcome] = {}
        failure_by_scene: dict[str, ImageRenderPreparationFailure] = {
            failure.source_spec_id: failure for failure in extra_failures
        }
        warnings: list[str] = []
        for batch in sub_batches:
            warnings.extend(batch.warnings)
            for item in batch.items:
                if item.request.source_spec_id in item_by_scene:
                    raise ValueError("Sub-batches attempted one scene more than once")
                item_by_scene[item.request.source_spec_id] = item
            for failure in batch.preparation_failures:
                if failure.source_spec_id in failure_by_scene:
                    raise ValueError("Sub-batches failed one scene more than once")
                failure_by_scene[failure.source_spec_id] = failure
        warnings.extend(extra_warnings)

        source_ids = tuple(scene.scene_id for scene in scenes)
        items = tuple(
            item_by_scene[scene_id]
            for scene_id in source_ids
            if scene_id in item_by_scene
        )
        failures = tuple(
            failure_by_scene[scene_id]
            for scene_id in source_ids
            if scene_id in failure_by_scene
        )
        return ImageRenderBatchOutcome.create(
            source_spec_ids=source_ids,
            root_seed=seed,
            status=_batch_status(source_count=len(scenes), items=items),
            items=items,
            preparation_failures=failures,
            warnings=tuple(warnings),
        )


__all__ = [
    "CurrentFirstEmocioRenderer",
    "CurrentFirstRolloutConfig",
    "RolloutConditioningMethod",
]
