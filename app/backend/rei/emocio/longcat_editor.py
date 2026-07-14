"""Pinned LongCat image-editor member for the C4 composite screen."""

from __future__ import annotations

from pathlib import Path

from .artifacts import LocalPngArtifactStore
from .composite_editor import (
    EDITOR_ADAPTER_REVISION,
    CompositeEditorMember,
    CompositeEditorRuntimeConfig,
    LazyLocalCompositeEditorBackend,
    build_editor_renderer,
)


LONGCAT_EDITOR_ID = "longcat_image_edit"
LONGCAT_MODEL_ID = "meituan-longcat/LongCat-Image-Edit"
LONGCAT_MODEL_REVISION = "7b54ef423aa7854be7861600024be5c56ab7875a"
LONGCAT_PIPELINE_CLASS = "LongCatImageEditPipeline"


def longcat_editor_runtime_config(
    *,
    snapshot_path: str | Path,
    snapshot_manifest_sha256: str,
) -> CompositeEditorRuntimeConfig:
    """Create the exact BF16/CPU-offload LongCat screen runtime pin."""

    return CompositeEditorRuntimeConfig(
        editor_id=LONGCAT_EDITOR_ID,
        repo_id=LONGCAT_MODEL_ID,
        revision=LONGCAT_MODEL_REVISION,
        adapter_implementation=(
            "rei.emocio.longcat_editor.LongCatImageEditorBackend"
        ),
        adapter_implementation_revision=(
            f"{EDITOR_ADAPTER_REVISION};longcat-v1"
        ),
        pipeline_class=LONGCAT_PIPELINE_CLASS,
        guidance_argument="guidance_scale",
        pass_output_dimensions=False,
        local_snapshot_path=str(Path(snapshot_path).expanduser().resolve()),
        expected_snapshot_manifest_sha256=snapshot_manifest_sha256,
    )


class LongCatImageEditorBackend(LazyLocalCompositeEditorBackend):
    """Named LongCat adapter; all execution stays in the shared closed backend."""


def build_longcat_editor_member(
    *,
    snapshot_path: str | Path,
    snapshot_manifest_sha256: str,
    artifact_root: str | Path,
) -> CompositeEditorMember:
    """Verify LongCat and bind it to the existing image-render provider contract."""

    config = longcat_editor_runtime_config(
        snapshot_path=snapshot_path,
        snapshot_manifest_sha256=snapshot_manifest_sha256,
    )
    backend = LongCatImageEditorBackend(config)
    snapshot = backend.verify_snapshot()
    store = LocalPngArtifactStore(artifact_root)
    renderer = build_editor_renderer(config, backend=backend, artifact_store=store)
    return CompositeEditorMember(
        config=config,
        snapshot=snapshot,
        renderer=renderer,
        artifact_store=store,
    )


__all__ = [
    "LONGCAT_EDITOR_ID",
    "LONGCAT_MODEL_ID",
    "LONGCAT_MODEL_REVISION",
    "LONGCAT_PIPELINE_CLASS",
    "LongCatImageEditorBackend",
    "build_longcat_editor_member",
    "longcat_editor_runtime_config",
]
