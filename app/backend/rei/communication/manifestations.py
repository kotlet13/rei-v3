"""Provider-free construction of consciously observable B9 manifestations."""

from __future__ import annotations

from ..models.communication import EmocioManifestation
from ..models.emocio import EmocioNativeConclusion, ImageArtifact


def build_emocio_manifestation(
    *,
    conclusion: EmocioNativeConclusion,
    images: tuple[ImageArtifact, ...] = (),
) -> EmocioManifestation:
    """Apply the explicit ``b9_fixture_emocio_projection_v1`` policy."""

    return EmocioManifestation.create_b9_fixture_projection(
        conclusion=conclusion,
        images=images,
    )


__all__ = ["build_emocio_manifestation"]
