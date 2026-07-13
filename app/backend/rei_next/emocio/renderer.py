"""Optional presentation renderer boundary for the B6 structured core."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.emocio import ImageArtifact, VisualSceneSpec


@runtime_checkable
class EmocioRenderer(Protocol):
    """Render frozen scene specs without participating in native valuation."""

    def render(
        self,
        scenes: tuple[VisualSceneSpec, ...],
        *,
        seed: int,
    ) -> tuple[ImageArtifact, ...]: ...


class NullRenderer:
    """Pure no-op renderer used by deterministic tests and headless runs."""

    def render(
        self,
        scenes: tuple[VisualSceneSpec, ...],
        *,
        seed: int,
    ) -> tuple[ImageArtifact, ...]:
        del scenes, seed
        return ()


def validate_renderer_outputs(
    images: tuple[ImageArtifact, ...],
    scenes: tuple[VisualSceneSpec, ...],
    *,
    expected_seed: int | None = None,
) -> None:
    """Validate presentation lineage without feeding it back into native state."""

    scene_by_id = {scene.scene_id: scene for scene in scenes}
    image_ids = tuple(image.image_id for image in images)
    if len(set(image_ids)) != len(image_ids):
        raise ValueError("Renderer image IDs must be unique")
    for image in images:
        source_scene = scene_by_id.get(image.source_spec_id)
        if source_scene is None:
            raise ValueError("Renderer output cites a scene outside this Emocio run")
        if image.input_spec_hash != source_scene.content_hash():
            raise ValueError("Renderer output input hash differs from its frozen scene")
        if expected_seed is not None and image.seed != expected_seed:
            raise ValueError("Renderer output seed differs from the requested seed")
        if image.grounded is not False:
            raise ValueError("Renderer output can never be grounded evidence")


__all__ = ["EmocioRenderer", "NullRenderer", "validate_renderer_outputs"]
