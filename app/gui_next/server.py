"""Local HTTP surface for the deterministic native REI workbench."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter, ValidationError

from app.backend.rei_next.emocio.artifacts import inspect_png
from app.backend.rei_next.ego.trace_store import (
    EgoTraceConflictError,
    EgoTraceStoreError,
)
from app.backend.rei_next.engine import ReiNativeCycleRequest, ReiNativeEngine
from app.backend.rei_next.models.character import (
    CHARACTER_PROFILE_CONTRACTS,
    CHARACTER_PROFILE_ORDER,
)
from app.backend.rei_next.models.common import PUBLIC_SAFETY_CAVEAT_SL
from app.backend.rei_next.models.emocio import ImageArtifact
from app.backend.rei_next.persistence import (
    ArtifactExistsError,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStoreError,
    FileArtifactStore,
)
from app.backend.rei_next.providers.native import DeterministicExecutionClock
from app.backend.rei_next.providers.protocols import StoredArtifact

from .view_model import COMMUNICATION_WARNING, build_workbench_view


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_FIXTURE = (
    ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
)
RUNS_ROOT_ENV = "REI_GUI_NEXT_RUNS_ROOT"
EGO_TRACES_ROOT_ENV = "REI_GUI_NEXT_EGO_TRACES_ROOT"
DEFAULT_RUNS_ROOT = ROOT / "output" / "runs"
DEFAULT_EGO_TRACES_ROOT = ROOT / "output" / "ego_traces"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IMAGE_INDEX_PATH = "emocio/images/index.json"
IMAGE_INDEX_ADAPTER = TypeAdapter(tuple[ImageArtifact, ...])


app = FastAPI(
    title="REI Native Composition Workbench",
    version="1",
    description=(
        "Deterministic four-panel inspection surface for native REI cycles."
    ),
)
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR, check_dir=False),
    name="static",
)


def _configured_root(environment_name: str, default: Path) -> Path:
    configured = os.environ.get(environment_name)
    if configured is None or not configured.strip():
        return default
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def _runs_root() -> Path:
    return _configured_root(RUNS_ROOT_ENV, DEFAULT_RUNS_ROOT)


def _ego_traces_root() -> Path:
    return _configured_root(EGO_TRACES_ROOT_ENV, DEFAULT_EGO_TRACES_ROOT)


def _artifact_store() -> FileArtifactStore:
    return FileArtifactStore(_runs_root())


def _engine(request: ReiNativeCycleRequest) -> ReiNativeEngine:
    """Build only the provider-free deterministic B11 runtime."""

    return ReiNativeEngine.with_file_stores(
        runs_root=_runs_root(),
        ego_traces_root=_ego_traces_root(),
        clock=DeterministicExecutionClock(request.started_at),
    )


def _profile_contracts() -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for profile_id in CHARACTER_PROFILE_ORDER:
        authority_tiers, rule = CHARACTER_PROFILE_CONTRACTS[profile_id]
        contracts.append(
            {
                "profile_id": profile_id,
                "authority_tiers": [list(tier) for tier in authority_tiers],
                "rule": rule,
            }
        )
    return contracts


def _default_request() -> ReiNativeCycleRequest:
    try:
        return ReiNativeCycleRequest.model_validate_json(DEFAULT_FIXTURE.read_bytes())
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        raise RuntimeError("The checked-in native GUI fixture is invalid") from exc


def _parse_cycle_request(content: bytes) -> ReiNativeCycleRequest:
    """Use Pydantic's JSON mode so strict tuple/datetime contracts stay exact."""

    try:
        return ReiNativeCycleRequest.model_validate_json(content)
    except (UnicodeError, ValueError, ValidationError) as exc:
        detail = (
            exc.errors(
                include_url=False,
                include_context=False,
                include_input=False,
            )
            if isinstance(exc, ValidationError)
            else [{"type": "invalid_json", "msg": str(exc)}]
        )
        raise HTTPException(status_code=422, detail=detail) from exc


def _stored_artifact(record: Any) -> StoredArtifact:
    return StoredArtifact(**record.model_dump(mode="python"))


def _verified_image(
    store: FileArtifactStore,
    *,
    run_id: str,
    image_id: str,
) -> tuple[bytes, ImageArtifact]:
    """Resolve an image only through a fully verified V2 manifest inventory."""

    manifest = store.verify_run(run_id)
    index_records = tuple(
        item
        for item in manifest.artifact_inventory
        if item.relative_path == IMAGE_INDEX_PATH
    )
    if len(index_records) != 1:
        raise ArtifactIntegrityError(
            "Verified run must inventory exactly one Emocio image index"
        )
    try:
        images = IMAGE_INDEX_ADAPTER.validate_json(
            store.read_verified(_stored_artifact(index_records[0]))
        )
    except (UnicodeError, ValueError, ValidationError) as exc:
        raise ArtifactIntegrityError("Emocio image index is invalid") from exc
    image_ids = tuple(item.image_id for item in images)
    if len(set(image_ids)) != len(image_ids):
        raise ArtifactIntegrityError("Emocio image index repeats an image ID")
    matches = tuple(item for item in images if item.image_id == image_id)
    if not matches:
        raise ArtifactNotFoundError("Rendered image is absent from the verified index")
    if len(matches) != 1:
        raise ArtifactIntegrityError("Rendered image ID is ambiguous")
    artifact = matches[0]
    if (
        artifact.media_type != "image/png"
        or not artifact.path.startswith("emocio/images/")
        or not artifact.path.endswith(".png")
    ):
        raise ArtifactIntegrityError("Only inventoried Emocio PNG artifacts are served")

    pixel_records = tuple(
        item
        for item in manifest.artifact_inventory
        if item.relative_path == artifact.path
    )
    if len(pixel_records) != 1:
        raise ArtifactIntegrityError(
            "Image metadata path is absent from the verified manifest inventory"
        )
    pixel_record = pixel_records[0]
    if pixel_record.content_sha256 != artifact.content_sha256:
        raise ArtifactIntegrityError(
            "Image metadata hash differs from the verified manifest inventory"
        )
    content = store.read_verified(_stored_artifact(pixel_record))
    if hashlib.sha256(content).hexdigest() != artifact.content_sha256:
        raise ArtifactIntegrityError("Rendered image bytes differ from their metadata")
    if not content.startswith(PNG_SIGNATURE):
        raise ArtifactIntegrityError("Rendered image media signature is not PNG")
    try:
        dimensions = inspect_png(content)
    except ValueError as exc:
        raise ArtifactIntegrityError(
            "Rendered image failed strict PNG verification"
        ) from exc
    if dimensions != (artifact.width, artifact.height):
        raise ArtifactIntegrityError(
            "Rendered image dimensions differ from their metadata"
        )
    return content, artifact


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    """Return UI configuration and a fixture without executing the engine."""

    return {
        "schema_version": "rei-native-workbench-bootstrap-v1",
        "default_request": _default_request().model_dump(mode="json"),
        "profile_contracts": _profile_contracts(),
        "safety_caveat": PUBLIC_SAFETY_CAVEAT_SL,
        "communication_warning": COMMUNICATION_WARNING,
        "execution": {
            "providers": "deterministic_only",
            "models_enabled": False,
            "image_generation_enabled": False,
            "dataset_actions_enabled": False,
        },
    }


def execute_native_cycle(
    request: ReiNativeCycleRequest,
    *,
    debug: bool = False,
) -> dict[str, Any]:
    try:
        result = _engine(request).run_cycle(request)
        return build_workbench_view(result, debug=debug)
    except (ArtifactExistsError, EgoTraceConflictError) as exc:
        raise HTTPException(
            status_code=409,
            detail="The run already exists or its EgoTrace changed concurrently.",
        ) from exc
    except (ArtifactStoreError, EgoTraceStoreError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Native run persistence failed integrity verification.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/cycles")
async def run_native_cycle(
    request: Request,
    debug: bool = False,
) -> dict[str, Any]:
    cycle_request = _parse_cycle_request(await request.body())
    return execute_native_cycle(cycle_request, debug=debug)


@app.get("/api/runs/{run_id}/images/{image_id}")
def verified_run_image(run_id: str, image_id: str) -> Response:
    try:
        content, artifact = _verified_image(
            _artifact_store(),
            run_id=run_id,
            image_id=image_id,
        )
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Verified image not found.") from exc
    except (ArtifactStoreError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Run image failed manifest or content integrity verification.",
        ) from exc
    return Response(
        content=content,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "ETag": f'"{artifact.content_sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


__all__ = [
    "app",
    "bootstrap",
    "execute_native_cycle",
    "index",
    "run_native_cycle",
    "verified_run_image",
]
