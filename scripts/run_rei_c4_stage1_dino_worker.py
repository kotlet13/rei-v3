"""One-process DINOv2 worker reached only through the no-site bootstrap."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from rei.emocio.artifacts import LocalPngArtifactStore
from rei.emocio.dinov2_encoder import (
    DINOV2_BASE_DIMENSIONS,
    DinoV2BaseImageEncoder,
    DinoV2RuntimeConfig,
    LocalFloat32VectorStore,
)
from rei.emocio.vector_encoding import verified_float32_le_vector
from rei.evaluation.c4_stage1_screen import (
    C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
)
from rei.ids import canonical_json_bytes
from rei.models.emocio import ImageArtifact
from rei.models.provider import ProviderCallSpec


_RESULT_SCHEMA = "rei-c4-stage1-dino-child-result-v1"
_RESULT_FILENAME = "result.json"
_MODEL_ROOTS = {"accelerate", "diffusers", "safetensors", "torch", "transformers"}


def _write_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _execute(raw: bytes) -> int:
    if type(raw) is not bytes:
        raise TypeError("DINO worker requires immutable authorized request bytes")
    request = json.loads(raw.decode("utf-8", errors="strict"))
    if canonical_json_bytes(request) != raw:
        raise ValueError("DINO worker request is not canonical")
    staging = Path(request["staging_root"])
    render_root = Path(request["render_run_root"])
    snapshot = Path(request["snapshot_path"])
    if (
        not staging.is_absolute()
        or not render_root.is_absolute()
        or not snapshot.is_absolute()
        or tuple(staging.iterdir())
        or os.environ.get("HF_HUB_OFFLINE") != "1"
        or os.environ.get("TRANSFORMERS_OFFLINE") != "1"
        or os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID"
        or os.environ.get("CUDA_VISIBLE_DEVICES") != request["cuda_physical_gpu_uuid"]
        or "site" in sys.modules
    ):
        raise ValueError("DINO worker runtime is not closed")
    image = ImageArtifact.model_validate(request["image"])
    call = ProviderCallSpec.model_validate(request["call"])
    if any(name.split(".", 1)[0] in _MODEL_ROOTS for name in sys.modules):
        raise ValueError("DINO model packages were imported before worker gates")
    encoder = DinoV2BaseImageEncoder(
        runtime=DinoV2RuntimeConfig(
            local_snapshot_path=os.fspath(snapshot),
            expected_snapshot_manifest_sha256=(
                C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256
            ),
            device="cuda",
        ),
        image_store=LocalPngArtifactStore(render_root),
        vector_store=LocalFloat32VectorStore(staging),
    )
    encoding = encoder.encode(image, call=call)
    vector_path = staging.joinpath(*encoding.vector_ref.split("/"))
    vector = vector_path.read_bytes()
    _, digest = verified_float32_le_vector(
        vector,
        expected_dimensions=DINOV2_BASE_DIMENSIONS,
    )
    if digest != encoding.vector_hash:
        raise ValueError("DINO worker vector differs from encoding")
    result = canonical_json_bytes(
        {"schema_version": _RESULT_SCHEMA, "encoding": encoding}
    )
    _write_new(staging / _RESULT_FILENAME, result)
    return 0


def run_authorized_request(raw: bytes) -> int:
    """Consume the exact bytes already validated by the no-site bootstrap."""

    try:
        return _execute(raw)
    except Exception:
        return 2


def main(argv: list[str] | None = None) -> int:
    del argv
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
