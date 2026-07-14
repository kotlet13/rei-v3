"""Pinned FireRed 1.1 image-editor member for the C4 composite screen."""

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


FIRERED_EDITOR_ID = "firered_image_edit_1_1"
FIRERED_MODEL_ID = "FireRedTeam/FireRed-Image-Edit-1.1"
FIRERED_MODEL_REVISION = "3bc3f2a12722fd9883eb6357500de191d56baaf5"
FIRERED_PIPELINE_CLASS = "QwenImageEditPlusPipeline"


def firered_editor_runtime_config(
    *,
    snapshot_path: str | Path,
    snapshot_manifest_sha256: str,
) -> CompositeEditorRuntimeConfig:
    """Create the exact BF16/CPU-offload FireRed 1.1 screen runtime pin."""

    return CompositeEditorRuntimeConfig(
        editor_id=FIRERED_EDITOR_ID,
        repo_id=FIRERED_MODEL_ID,
        revision=FIRERED_MODEL_REVISION,
        adapter_implementation=(
            "rei.emocio.firered_editor.FireRedImageEditorBackend"
        ),
        adapter_implementation_revision=(
            f"{EDITOR_ADAPTER_REVISION};firered-1.1-v1"
        ),
        pipeline_class=FIRERED_PIPELINE_CLASS,
        guidance_argument="true_cfg_scale",
        pass_output_dimensions=True,
        local_snapshot_path=str(Path(snapshot_path).expanduser().resolve()),
        expected_snapshot_manifest_sha256=snapshot_manifest_sha256,
    )


class FireRedImageEditorBackend(LazyLocalCompositeEditorBackend):
    """Named FireRed adapter; all execution stays in the shared closed backend."""


def build_firered_editor_member(
    *,
    snapshot_path: str | Path,
    snapshot_manifest_sha256: str,
    artifact_root: str | Path,
) -> CompositeEditorMember:
    """Verify FireRed and bind it to the existing image-render provider contract."""

    config = firered_editor_runtime_config(
        snapshot_path=snapshot_path,
        snapshot_manifest_sha256=snapshot_manifest_sha256,
    )
    backend = FireRedImageEditorBackend(config)
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
    "FIRERED_EDITOR_ID",
    "FIRERED_MODEL_ID",
    "FIRERED_MODEL_REVISION",
    "FIRERED_PIPELINE_CLASS",
    "FireRedImageEditorBackend",
    "build_firered_editor_member",
    "firered_editor_runtime_config",
]
