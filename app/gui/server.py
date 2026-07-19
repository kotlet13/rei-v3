"""Local HTTP surface for the deterministic native REI workbench."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter, ValidationError
from starlette.concurrency import run_in_threadpool

from app.backend.rei.emocio.artifacts import inspect_png
from app.backend.rei.ego.trace_store import (
    EgoTraceConflictError,
    EgoTraceStoreError,
    FileEgoTraceStore,
)
from app.backend.rei.engine import ReiNativeCycleRequest, ReiNativeEngine
from app.backend.rei.ids import canonical_json_bytes
from app.backend.rei.models.character import (
    CHARACTER_PROFILE_CONTRACTS,
    CHARACTER_PROFILE_ORDER,
)
from app.backend.rei.models.common import PUBLIC_SAFETY_CAVEAT_SL
from app.backend.rei.models.emocio import ImageArtifact
from app.backend.rei.models.run import NativeMindBundle
from app.backend.rei.persistence import (
    ArtifactExistsError,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStoreError,
    FileArtifactStore,
)
from app.backend.rei.providers.native import DeterministicExecutionClock
from app.backend.rei.providers.protocols import StoredArtifact

from .semantic_lab import SemanticLabIntegrityError, build_semantic_lab_view
from .shadow_view import (
    SHADOW_EVIDENCE_IDS,
    ShadowEvidenceIntegrityError,
    build_shadow_evidence_index,
    build_shadow_evidence_view,
    is_registered_shadow_evidence_id,
)
from .storage import ego_partition_id, validate_ego_partition_id
from .view_model import COMMUNICATION_WARNING, build_workbench_view


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_FIXTURE = (
    ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
)
RUNS_ROOT_ENV = "REI_GUI_RUNS_ROOT"
EGO_TRACES_ROOT_ENV = "REI_GUI_EGO_TRACES_ROOT"
ALLOW_REMOTE_DEBUG_ENV = "REI_GUI_ALLOW_REMOTE_DEBUG"
ALLOW_REMOTE_ENV = "REI_GUI_ALLOW_REMOTE"
DEFAULT_RUNS_ROOT = ROOT / "output" / "runs"
DEFAULT_EGO_TRACES_ROOT = ROOT / "output" / "ego_traces"
MAX_CYCLE_REQUEST_BYTES = 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IMAGE_INDEX_PATH = "emocio/images/index.json"
NATIVE_BUNDLE_PATH = "native/bundle.json"
RUN_RESERVATION_PATH = "diagnostics/run_reservation.json"
MAX_HISTORY_RUN_DIRECTORIES = 64
MAX_NATIVE_BUNDLE_BYTES = 2 * MAX_CYCLE_REQUEST_BYTES
MAX_GUI_LONGITUDINAL_BUNDLES = 30
IMAGE_INDEX_ADAPTER = TypeAdapter(tuple[ImageArtifact, ...])
_SEMANTIC_LAB_BUILD_GATE = BoundedSemaphore(value=1)
_SHADOW_EVIDENCE_BUILD_GATE = BoundedSemaphore(value=1)
_CYCLE_EXECUTION_GATE = BoundedSemaphore(value=1)


app = FastAPI(
    title="REI Native Composition Workbench",
    version="2",
    description=(
        "Read-only Semantic Lab plus deterministic native-process and "
        "longitudinal Ego inspection views."
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


def _ego_runs_root(ego_id: str) -> Path:
    """Return a filesystem-safe, non-identifying partition for one Ego."""

    return _runs_root() / f"ego-{ego_partition_id(ego_id)}"


def _partition_runs_root(partition_id: str) -> Path:
    return _runs_root() / f"ego-{validate_ego_partition_id(partition_id)}"


class _BoundedGuiArtifactStore(FileArtifactStore):
    """Reject GUI bundles that restart recovery cannot read safely."""

    def write_json(
        self,
        run_id: str,
        relative_path: str,
        artifact: Any,
        *,
        overwrite: bool = False,
    ) -> StoredArtifact:
        if relative_path == NATIVE_BUNDLE_PATH:
            content = canonical_json_bytes(artifact)
            if len(content) > MAX_NATIVE_BUNDLE_BYTES:
                raise ArtifactIntegrityError(
                    "Native bundle exceeds the bounded GUI recovery contract"
                )
            return self.write_bytes(
                run_id,
                relative_path,
                content,
                overwrite=overwrite,
            )
        if overwrite:
            return super().write_json(
                run_id,
                relative_path,
                artifact,
                overwrite=overwrite,
            )
        return super().write_json(run_id, relative_path, artifact)


def _artifact_store(ego_id: str) -> FileArtifactStore:
    return _BoundedGuiArtifactStore(_ego_runs_root(ego_id))


def _partition_artifact_store(partition_id: str) -> FileArtifactStore:
    return _BoundedGuiArtifactStore(
        _partition_runs_root(partition_id),
        create=False,
    )


def _engine(request: ReiNativeCycleRequest) -> ReiNativeEngine:
    """Build only the provider-free deterministic B11 runtime."""

    return ReiNativeEngine(
        artifact_store=_artifact_store(request.ego_id),
        ego_trace_store=FileEgoTraceStore(_ego_traces_root()),
        clock=DeterministicExecutionClock(request.started_at),
    )


def _verified_historical_bundles(
    request: ReiNativeCycleRequest,
) -> tuple[NativeMindBundle, ...]:
    """Resolve private longitudinal bundle history from verified local runs."""

    if (
        request.historical_bundles
        or request.historical_emocio_signals
        or request.historical_instinkt_signals
    ):
        raise ValueError(
            "GUI cycle history is server-resolved and cannot be supplied by the client"
        )

    store = _artifact_store(request.ego_id)
    run_ids = _bounded_partition_run_ids(store, incoming_run_id=request.run_id)
    trace = FileEgoTraceStore(_ego_traces_root()).load_trace(request.ego_id)
    expected: dict[str, tuple[str, str]] = {}
    for measure in trace.measures:
        lineage = (measure.native_bundle_hash, measure.event_id)
        previous = expected.setdefault(measure.native_bundle_id, lineage)
        if previous != lineage:
            raise ArtifactIntegrityError(
                "EgoTrace reuses a native bundle ID with conflicting lineage"
            )
    if not expected:
        return ()
    if len(trace.measures) >= MAX_GUI_LONGITUDINAL_BUNDLES:
        raise ValueError(
            "This bounded GUI Ego session already contains 30 measures; start "
            "a new session before running another cycle"
        )

    resolved: dict[str, NativeMindBundle] = {}
    for run_id in run_ids:
        if len(resolved) == len(expected):
            break
        try:
            candidate = NativeMindBundle.model_validate_json(
                store.read_bounded_unverified(
                    run_id,
                    NATIVE_BUNDLE_PATH,
                    maximum_size=MAX_NATIVE_BUNDLE_BYTES,
                )
            )
        except (
            OSError,
            UnicodeError,
            ValueError,
            ValidationError,
            ArtifactStoreError,
        ):
            continue
        expected_lineage = expected.get(candidate.bundle_id)
        if expected_lineage is None or candidate.bundle_id in resolved:
            continue
        if (candidate.immutable_hash, candidate.scene_id) != expected_lineage:
            continue

        try:
            final_manifest_path = store.artifact_path(run_id, "run_manifest.json")
            prepared_manifest_path = store.artifact_path(
                run_id, "diagnostics/prepared_manifest.json"
            )
            if final_manifest_path.exists():
                manifest = store.verify_run(run_id)
                prepared_only = False
            elif prepared_manifest_path.exists():
                manifest = store.verify_prepared_run(run_id)
                prepared_only = True
            else:
                continue
        except (OSError, ValueError, ArtifactStoreError):
            continue
        reservation = _verified_run_reservation(
            store,
            manifest,
            run_id=run_id,
        )
        if reservation["ego_id"] != request.ego_id:
            raise ArtifactIntegrityError(
                "Historical run reservation belongs to another Ego"
            )
        bundle_ids = tuple(
            item.artifact_id
            for item in manifest.native_artifact_hashes
            if item.role == "native_bundle"
        )
        if len(bundle_ids) != 1:
            raise ArtifactIntegrityError(
                "Historical run must identify exactly one native bundle"
            )
        bundle_id = bundle_ids[0]
        if bundle_id != candidate.bundle_id:
            raise ArtifactIntegrityError(
                "Historical manifest identifies another native bundle"
            )

        if prepared_only:
            request_hash = reservation.get("request_hash")
            recovered_manifest = store.recover_prepared_run(
                run_id,
                request_hash=request_hash,
                ego_id=request.ego_id,
                trace=trace,
            )
            if recovered_manifest is None:
                continue
            manifest = recovered_manifest
        records = tuple(
            item
            for item in manifest.artifact_inventory
            if item.relative_path == NATIVE_BUNDLE_PATH
        )
        if len(records) != 1:
            raise ArtifactIntegrityError(
                "Verified historical run must contain exactly one native bundle"
            )
        if not 0 < records[0].size_bytes <= MAX_NATIVE_BUNDLE_BYTES:
            raise ArtifactIntegrityError(
                "Verified historical native bundle exceeds the GUI byte limit"
            )
        try:
            verified = NativeMindBundle.model_validate_json(
                store.read_verified(_stored_artifact(records[0]))
            )
        except (UnicodeError, ValueError, ValidationError) as exc:
            raise ArtifactIntegrityError(
                "Verified historical native bundle is invalid"
            ) from exc
        if (
            verified != candidate
            or verified.bundle_id != bundle_id
            or (verified.immutable_hash, verified.scene_id) != expected_lineage
        ):
            raise ArtifactIntegrityError(
                "Historical native bundle differs from EgoTrace lineage"
            )
        resolved[verified.bundle_id] = verified

    missing = tuple(bundle_id for bundle_id in expected if bundle_id not in resolved)
    if missing:
        raise ArtifactIntegrityError(
            "Verified run history does not cover the persisted EgoTrace"
        )
    return tuple(resolved[bundle_id] for bundle_id in expected)


def _bounded_partition_run_ids(
    store: FileArtifactStore,
    *,
    incoming_run_id: str,
) -> tuple[str, ...]:
    """Enumerate one Ego partition with an absolute amount-of-work bound."""

    recent_runs: list[tuple[int, str]] = []
    entry_names: set[str] = set()
    try:
        with os.scandir(store.root) as entries:
            for index, entry in enumerate(entries, start=1):
                if index > MAX_HISTORY_RUN_DIRECTORIES:
                    raise ArtifactIntegrityError(
                        "Ego run partition exceeds the bounded directory limit"
                    )
                entry_names.add(entry.name)
                if not entry.is_dir(follow_symlinks=False):
                    continue
                try:
                    modified_ns = entry.stat(follow_symlinks=False).st_mtime_ns
                except OSError:
                    continue
                recent_runs.append((modified_ns, entry.name))
    except ArtifactIntegrityError:
        raise
    except OSError as exc:
        raise ArtifactIntegrityError("Run history cannot be enumerated") from exc
    if (
        len(entry_names) >= MAX_HISTORY_RUN_DIRECTORIES
        and incoming_run_id not in entry_names
    ):
        raise ArtifactIntegrityError(
            "Ego run partition has no capacity for another run"
        )
    return tuple(name for _modified_ns, name in sorted(recent_runs, reverse=True))


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


async def _bounded_request_body(request: Request) -> bytes:
    """Read a cycle request without allowing an unbounded in-memory body."""

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Content-Length must be a non-negative integer.",
            ) from exc
        if declared_size < 0:
            raise HTTPException(
                status_code=400,
                detail="Content-Length must be a non-negative integer.",
            )
        if declared_size > MAX_CYCLE_REQUEST_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Cycle request body exceeds the "
                    f"{MAX_CYCLE_REQUEST_BYTES}-byte limit."
                ),
            )

    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_CYCLE_REQUEST_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Cycle request body exceeds the "
                    f"{MAX_CYCLE_REQUEST_BYTES}-byte limit."
                ),
            )
        content.extend(chunk)
    return bytes(content)


def _loopback_client(request: Request) -> bool:
    if request.client is None:
        return False
    host = request.client.host.strip().strip("[]").split("%", maxsplit=1)[0]
    if host.casefold() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    return bool(
        address.version == 6
        and address.ipv4_mapped
        and address.ipv4_mapped.is_loopback
    )


def _request_authority(request: Request) -> tuple[str, int | None]:
    host_headers = request.headers.getlist("host")
    if len(host_headers) != 1:
        raise HTTPException(status_code=400, detail="Exactly one Host header is required.")
    raw = host_headers[0].strip()
    if not raw or any(character in raw for character in ("/", "\\", "@")):
        raise HTTPException(status_code=400, detail="The Host header is invalid.")
    try:
        parsed = urlsplit(f"//{raw}")
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="The Host header is invalid.") from exc
    if (
        hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(status_code=400, detail="The Host header is invalid.")
    return hostname, port


def _loopback_hostname(hostname: str) -> bool:
    normalized = hostname.strip().strip("[]").split("%", maxsplit=1)[0]
    if normalized.casefold() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    return bool(
        address.version == 6
        and address.ipv4_mapped
        and address.ipv4_mapped.is_loopback
    )


def _host_identity(hostname: str) -> str:
    normalized = hostname.strip().strip("[]").split("%", maxsplit=1)[0]
    try:
        return ipaddress.ip_address(normalized).compressed.casefold()
    except ValueError:
        return normalized.rstrip(".").casefold()


def _require_same_origin_json(request: Request) -> None:
    media_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0]
    if media_type.strip().casefold() != "application/json":
        raise HTTPException(
            status_code=415,
            detail="Cycle requests require Content-Type: application/json.",
        )
    if request.headers.get("sec-fetch-site", "").strip().casefold() == "cross-site":
        raise HTTPException(status_code=403, detail="Cross-site cycle requests are forbidden.")

    origin = request.headers.get("origin")
    if origin is None:
        return
    try:
        parsed = urlsplit(origin)
        origin_host = parsed.hostname
        origin_port = parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Cycle request Origin is invalid.") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or origin_host is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(status_code=403, detail="Cycle request Origin is invalid.")

    request_host, request_port = _request_authority(request)
    request_scheme = request.url.scheme.casefold() or "http"
    expected_request_port = request_port or (443 if request_scheme == "https" else 80)
    expected_origin_port = origin_port or (443 if parsed.scheme == "https" else 80)
    if (
        parsed.scheme.casefold() != request_scheme
        or _host_identity(origin_host) != _host_identity(request_host)
        or expected_origin_port != expected_request_port
    ):
        raise HTTPException(status_code=403, detail="Cross-origin cycle requests are forbidden.")


def _remote_debug_enabled() -> bool:
    return os.environ.get(ALLOW_REMOTE_DEBUG_ENV, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _remote_access_enabled() -> bool:
    return os.environ.get(ALLOW_REMOTE_ENV, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _secure_response(request: Request, response: Response) -> Response:
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'none'; connect-src 'self'; "
        "form-action 'none'; frame-ancestors 'none'; img-src 'self'; "
        "object-src 'none'; script-src 'self'; style-src 'self'; "
        "style-src-attr 'unsafe-inline'",
    )
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.middleware("http")
async def enforce_loopback_default(request: Request, call_next: Any) -> Response:
    """Reject remote clients unless the operator explicitly enables them."""

    fetch_site = request.headers.get("sec-fetch-site", "").strip().casefold()
    if request.url.path.startswith("/api/") and fetch_site not in {
        "",
        "none",
        "same-origin",
    }:
        return _secure_response(
            request,
            JSONResponse(
                status_code=403,
                content={"detail": "Cross-origin browser access to the REI API is denied."},
            ),
        )
    try:
        request_host, _request_port = _request_authority(request)
    except HTTPException as exc:
        return _secure_response(
            request,
            JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}),
        )
    remote_access = _remote_access_enabled()
    if not remote_access and not (
        _loopback_client(request) and _loopback_hostname(request_host)
    ):
        return _secure_response(
            request,
            JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "REI GUI is loopback-only by default. Set "
                        f"{ALLOW_REMOTE_ENV}=true to opt in to remote access."
                    )
                },
            ),
        )
    return _secure_response(request, await call_next(request))


def _require_debug_access(request: Request, *, debug: bool) -> None:
    """Keep evaluator ground truth local unless explicitly exposed."""

    request_host, _request_port = _request_authority(request)
    local_request = _loopback_client(request) and _loopback_hostname(request_host)
    remote_debug_allowed = _remote_access_enabled() and _remote_debug_enabled()
    if debug and not (local_request or remote_debug_allowed):
        raise HTTPException(
            status_code=403,
            detail=(
                "Debug evaluator ground truth is restricted to loopback clients. "
                f"Set both {ALLOW_REMOTE_ENV}=true and "
                f"{ALLOW_REMOTE_DEBUG_ENV}=true to opt in to remote exposure."
            ),
        )


def _require_loopback_shadow_replay(request: Request) -> None:
    """Keep every frozen shadow replay endpoint strictly loopback-only."""

    request_host, _request_port = _request_authority(request)
    if not (_loopback_client(request) and _loopback_hostname(request_host)):
        raise HTTPException(
            status_code=403,
            detail=(
                "Frozen shadow evidence replay is restricted to "
                "loopback clients."
            ),
        )


def _stored_artifact(record: Any) -> StoredArtifact:
    return StoredArtifact(**record.model_dump(mode="python"))


def _verified_run_reservation(
    store: FileArtifactStore,
    manifest: Any,
    *,
    run_id: str,
) -> dict[str, Any]:
    records = tuple(
        item
        for item in manifest.artifact_inventory
        if item.relative_path == RUN_RESERVATION_PATH
    )
    if len(records) != 1:
        raise ArtifactIntegrityError(
            "Verified run must inventory exactly one run reservation"
        )
    try:
        content = store.read_verified(_stored_artifact(records[0]))
        reservation = json.loads(content)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ArtifactIntegrityError("Run reservation is invalid") from exc
    required_keys = {
        "schema_version",
        "run_id",
        "ego_id",
        "request_hash",
        "expected_trace_hash",
        "created_at",
    }
    if (
        not isinstance(reservation, dict)
        or set(reservation) != required_keys
        or reservation.get("schema_version")
        != "rei-native-run-reservation-v1"
        or reservation.get("run_id") != run_id
        or not isinstance(reservation.get("ego_id"), str)
        or not isinstance(reservation.get("request_hash"), str)
        or canonical_json_bytes(reservation) != content
    ):
        raise ArtifactIntegrityError("Run reservation contract is invalid")
    return reservation


def _verified_image(
    store: FileArtifactStore,
    *,
    partition_id: str,
    run_id: str,
    image_id: str,
) -> tuple[bytes, ImageArtifact]:
    """Resolve an image only through a fully verified V2 manifest inventory."""

    manifest = store.verify_run(run_id)
    reservation = _verified_run_reservation(store, manifest, run_id=run_id)
    if ego_partition_id(reservation["ego_id"]) != partition_id:
        raise ArtifactIntegrityError(
            "Run reservation differs from its Ego partition"
        )
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
        "schema_version": "rei-semantic-native-workbench-bootstrap-v2",
        "default_request": _default_request().model_dump(mode="json"),
        "profile_contracts": _profile_contracts(),
        "safety_caveat": PUBLIC_SAFETY_CAVEAT_SL,
        "communication_warning": COMMUNICATION_WARNING,
        "shadow_evidence_replay": {
            "available": True,
            "live_model_execution": False,
            "authority": "none",
            "evidence_ids": list(SHADOW_EVIDENCE_IDS),
        },
        "execution": {
            "providers": "deterministic_only",
            "models_enabled": False,
            "image_generation_enabled": False,
            "dataset_actions_enabled": False,
            "semantic_lab_read_only": True,
            "network_scope": "loopback_default",
            "remote_access_policy": "trusted_single_user_unauthenticated_opt_in",
            "longitudinal_bundle_limit": MAX_GUI_LONGITUDINAL_BUNDLES,
            "history_lookup_window": MAX_HISTORY_RUN_DIRECTORIES,
            "run_storage_partition": "sha256_ego_id",
        },
    }


@app.get("/api/semantic-lab")
def semantic_lab() -> dict[str, Any]:
    """Return the cold-verified C1/C2/C7 read model without executing REI."""

    if not _SEMANTIC_LAB_BUILD_GATE.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Semantic Lab evidence verification is already in progress.",
            headers={"Retry-After": "1"},
        )
    try:
        try:
            return build_semantic_lab_view(ROOT)
        except (OSError, SemanticLabIntegrityError, ValueError) as exc:
            raise HTTPException(
                status_code=409,
                detail="Semantic Lab evidence failed integrity verification.",
            ) from exc
    finally:
        _SEMANTIC_LAB_BUILD_GATE.release()


def _shadow_replay(build: Any) -> dict[str, Any]:
    if not _SHADOW_EVIDENCE_BUILD_GATE.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Shadow evidence verification is already in progress.",
            headers={"Retry-After": "1"},
        )
    try:
        try:
            return build()
        except ShadowEvidenceIntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Frozen shadow evidence failed integrity verification.",
            ) from exc
    finally:
        _SHADOW_EVIDENCE_BUILD_GATE.release()


@app.get("/api/shadow-evidence")
def shadow_evidence_index(request: Request) -> dict[str, Any]:
    """Return the cold-verified, model-free frozen replay registry."""

    _require_loopback_shadow_replay(request)
    return _shadow_replay(lambda: build_shadow_evidence_index(ROOT))


@app.get("/api/shadow-evidence/{evidence_id}")
def shadow_evidence_detail(
    evidence_id: str,
    request: Request,
    debug: bool = False,
) -> dict[str, Any]:
    """Return one allowlisted replay; never accept a filesystem locator."""

    _require_loopback_shadow_replay(request)
    if not is_registered_shadow_evidence_id(evidence_id):
        raise HTTPException(status_code=404, detail="Shadow evidence ID not found.")
    return _shadow_replay(
        lambda: build_shadow_evidence_view(ROOT, evidence_id, debug=debug)
    )


def execute_native_cycle(
    request: ReiNativeCycleRequest,
    *,
    debug: bool = False,
) -> dict[str, Any]:
    try:
        historical_bundles = _verified_historical_bundles(request)
        hydrated_request = request.model_copy(
            update={"historical_bundles": historical_bundles}
        )
        result = _engine(hydrated_request).run_cycle(hydrated_request)
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
        if str(exc).startswith(
            (
                "Historical bundles must exactly cover",
                "Historical bundle identity, hash and event must exactly match",
            )
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "The longitudinal EgoTrace changed while history was being "
                    "resolved; retry the cycle with a new run ID."
                ),
            ) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/cycles")
async def run_native_cycle(
    request: Request,
    debug: bool = False,
) -> dict[str, Any]:
    _require_same_origin_json(request)
    _require_debug_access(request, debug=debug)
    cycle_request = _parse_cycle_request(await _bounded_request_body(request))
    if not _CYCLE_EXECUTION_GATE.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="A native cycle is already executing.",
            headers={"Retry-After": "1"},
        )
    try:
        return await run_in_threadpool(
            execute_native_cycle,
            cycle_request,
            debug=debug,
        )
    finally:
        _CYCLE_EXECUTION_GATE.release()


@app.get("/api/ego-runs/{partition_id}/{run_id}/images/{image_id}")
def verified_run_image(partition_id: str, run_id: str, image_id: str) -> Response:
    try:
        content, artifact = _verified_image(
            _partition_artifact_store(partition_id),
            partition_id=partition_id,
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
    "ALLOW_REMOTE_ENV",
    "app",
    "bootstrap",
    "execute_native_cycle",
    "index",
    "run_native_cycle",
    "semantic_lab",
    "shadow_evidence_detail",
    "shadow_evidence_index",
    "verified_run_image",
]
