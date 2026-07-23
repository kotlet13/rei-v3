"""Pinned headed-browser presenter for the C4 Stage 1 blind review.

The presenter is deliberately a small host adapter around the committed review
UI.  It re-captures the exact runtime manifest, serves only the three pinned UI
assets from memory while the browser context is offline, and exposes a narrow
``window.reiReviewHost`` bridge before the document loads.  Provider and model
identities are never part of the bridge packet.

Playwright is imported lazily so cold validation and the model-free test suite
do not require a browser runtime.  A caller may inject the Playwright factory
for deterministic tests.
"""

from __future__ import annotations

import hashlib
import hmac
from importlib import metadata
import json
import math
import os
import secrets
import shutil
import stat
import struct
import sys
import threading
import time
import zlib
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, ContextManager, Literal, Protocol, Self

from pydantic import model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import FrozenArtifactModel, HashDigest
from .c4_stage1_review import (
    C4Stage1DisplayContext,
    C4Stage1VisibleOutput,
    build_c4_stage1_display_port_acknowledgement,
)
from .c4_stage1_review_environment import (
    CHROMIUM_EXECUTABLE_RELATIVE_PATH,
    RUNTIME_PYTHON_RELATIVE_PATH,
    verify_presenter_runtime,
)
from .c4_stage1_review_runtime import (
    C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256,
    C4_STAGE1_REVIEW_IPC_PROTOCOL,
    C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
    C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
    C4_STAGE1_REVIEW_PRESENTER_REVISION,
    C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
    C4Stage1ReviewRuntimeManifest,
    verify_c4_stage1_review_runtime_manifest,
)


_INDEX_URL = "https://rei-c4-stage1.invalid/index.html"
_ASSET_URLS = {
    "index.html": _INDEX_URL,
    "review.css": "https://rei-c4-stage1.invalid/review.css",
    "review.js": "https://rei-c4-stage1.invalid/review.js",
}
_MEDIA_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "review.css": "text/css; charset=utf-8",
    "review.js": "text/javascript; charset=utf-8",
}
_OUTPUT_BOOLEAN_FIELDS = (
    "source_subject_present",
    "identity_preserved",
    "unchanged_composition_preserved",
    "option_action_correct",
    "no_extra_actor",
    "no_generated_external_evidence_claim",
    "reviewer_uncertain",
)
_PAIR_BOOLEAN_FIELDS = (
    "actions_visibly_distinct",
    "same_source_bytes_confirmed",
)
_MAX_SUBMISSION_CANONICAL_BYTES = 64 * 1024
_MAX_BLINDED_PNG_BYTES = 128 * 1024 * 1024
_DEFAULT_TIMEOUT_MS = 60 * 60 * 1000
_OPERATIONAL_PROBE_TIMEOUT_MS = 15 * 60 * 1000
_CANCEL_HARD_TERMINATION_GRACE_MS = 2_000
_WAIT_POLL_SLICE_MS = 250
_NO_PERSIST_BROWSER_ARGS = (
    "--disable-application-cache",
    "--disable-background-networking",
    "--disk-cache-size=1",
    "--media-cache-size=1",
)

C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION = "1.61.0"
C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION = "1228"
C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION = "149.0.7827.55"

_GET_PACKET_BINDING = "__reiC4Stage1GetReviewPacketV1"
_MARK_READY_BINDING = "__reiC4Stage1MarkReviewReadyV1"
_SUBMIT_BINDING = "__reiC4Stage1SubmitReviewV1"
_CANCEL_BINDING = "__reiC4Stage1CancelReviewV1"


class C4Stage1ReviewPresenterError(RuntimeError):
    """The pinned review could not complete without weakening its boundary."""


class C4Stage1ReviewSealedTreeIdentity(FrozenArtifactModel):
    """Path-free identity and aggregate inventory of one sealed runtime tree."""

    schema_version: Literal["rei-c4-stage1-review-sealed-tree-identity-v1"] = (
        "rei-c4-stage1-review-sealed-tree-identity-v1"
    )
    manifest_id: str
    canonical_sha256: HashDigest
    canonical_size_bytes: int
    tree_content_id: str
    tree_content_sha256: HashDigest
    file_count: int
    directory_count: int
    executable_count: int
    total_size_bytes: int
    regular_files_only: Literal[True] = True
    links_reparse_points_and_hardlinks_allowed: Literal[False] = False
    python_bytecode_and_cache_directories_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_aggregates(self) -> Self:
        if any(
            type(value) is not int or value < lower
            for value, lower in (
                (self.canonical_size_bytes, 1),
                (self.file_count, 1),
                (self.directory_count, 0),
                (self.executable_count, 1),
                (self.total_size_bytes, 1),
            )
        ):
            raise ValueError("C4 sealed runtime tree aggregates are invalid")
        if self.executable_count > self.file_count:
            raise ValueError("C4 sealed runtime executable count is invalid")
        return self


class C4Stage1ReviewExternalRuntimePin(FrozenArtifactModel):
    """Create-only provenance and complete external runtime-tree identity."""

    schema_version: Literal["rei-c4-stage1-review-external-runtime-pin-v1"] = (
        "rei-c4-stage1-review-external-runtime-pin-v1"
    )
    external_runtime_pin_id: str
    external_runtime_pin_sha256: HashDigest
    verification_schema_version: Literal["rei-c4-stage1-review-runtime-verification-v1"]
    verification_id: str
    verification_sha256: HashDigest
    provenance_id: str
    provenance_canonical_sha256: HashDigest
    provenance_canonical_size_bytes: int
    create_only_inventory_verified: Literal[True] = True
    runtime_manifest: C4Stage1ReviewSealedTreeIdentity
    browser_manifest: C4Stage1ReviewSealedTreeIdentity
    runtime_python_relative_path: Literal["venv/Scripts/python.exe"] = (
        RUNTIME_PYTHON_RELATIVE_PATH
    )
    runtime_python_sha256: HashDigest
    runtime_python_size_bytes: int
    installed_browsers_json_sha256: HashDigest
    installed_browsers_json_size_bytes: int
    chromium_executable_relative_path: Literal[
        "chromium-1228/chrome-win64/chrome.exe"
    ] = CHROMIUM_EXECUTABLE_RELATIVE_PATH
    chromium_executable_sha256: HashDigest
    chromium_executable_size_bytes: int
    checkpoint_applied_during_all_file_and_tree_hashing: Literal[True] = True
    paths_stored: Literal[False] = False
    browser_process_launch_performed: Literal[False] = False
    headed_full_ui_smoke_performed: Literal[False] = False
    model_calls: Literal[0] = 0

    @classmethod
    def create(
        cls, verification: dict[str, object]
    ) -> C4Stage1ReviewExternalRuntimePin:
        """Validate and bind the path-free result of ``verify_presenter_runtime``."""

        try:
            provenance = verification["provenance"]
            runtime = verification["runtime_manifest"]
            browser = verification["browser_manifest"]
            runtime_python = verification["runtime_python"]
            browsers_json = verification["installed_browsers_json"]
            chromium = verification["chromium_executable"]
            if not all(
                type(value) is dict
                for value in (
                    provenance,
                    runtime,
                    browser,
                    runtime_python,
                    browsers_json,
                    chromium,
                )
            ):
                raise TypeError
            verification_body = dict(verification)
            verification_id = verification_body.pop("verification_id")
            if verification_id != content_id(
                "c4_review_runtime_verification", verification_body
            ):
                raise ValueError
            verification_bytes = canonical_json_bytes(verification)
            body = {
                "schema_version": "rei-c4-stage1-review-external-runtime-pin-v1",
                "verification_schema_version": verification["schema_version"],
                "verification_id": verification_id,
                "verification_sha256": hashlib.sha256(verification_bytes).hexdigest(),
                "provenance_id": provenance["provenance_id"],
                "provenance_canonical_sha256": provenance["canonical_sha256"],
                "provenance_canonical_size_bytes": provenance["canonical_size_bytes"],
                "create_only_inventory_verified": provenance[
                    "create_only_inventory_verified"
                ],
                "runtime_manifest": {
                    "schema_version": "rei-c4-stage1-review-sealed-tree-identity-v1",
                    **{
                        key: runtime[key]
                        for key in C4Stage1ReviewSealedTreeIdentity.model_fields
                        if key != "schema_version"
                    },
                },
                "browser_manifest": {
                    "schema_version": "rei-c4-stage1-review-sealed-tree-identity-v1",
                    **{
                        key: browser[key]
                        for key in C4Stage1ReviewSealedTreeIdentity.model_fields
                        if key != "schema_version"
                    },
                },
                "runtime_python_relative_path": runtime_python["relative_path"],
                "runtime_python_sha256": runtime_python["sha256"],
                "runtime_python_size_bytes": runtime_python["size_bytes"],
                "installed_browsers_json_sha256": browsers_json["sha256"],
                "installed_browsers_json_size_bytes": browsers_json["size_bytes"],
                "chromium_executable_relative_path": chromium["relative_path"],
                "chromium_executable_sha256": chromium["sha256"],
                "chromium_executable_size_bytes": chromium["size_bytes"],
                "checkpoint_applied_during_all_file_and_tree_hashing": verification[
                    "checkpoint_applied_during_all_file_and_tree_hashing"
                ],
                "paths_stored": verification["paths_stored"],
                "browser_process_launch_performed": verification[
                    "browser_process_launch_performed"
                ],
                "headed_full_ui_smoke_performed": verification[
                    "headed_full_ui_smoke_performed"
                ],
                "model_calls": verification["model_calls"],
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise C4Stage1ReviewPresenterError(
                "The external review runtime verification result is incomplete"
            ) from exc
        return cls(
            external_runtime_pin_id=content_id("c4_review_external_runtime", body),
            external_runtime_pin_sha256=hashlib.sha256(
                canonical_json_bytes(body)
            ).hexdigest(),
            **body,
        )

    @model_validator(mode="after")
    def validate_runtime_pin(self) -> Self:
        for value in (
            self.provenance_canonical_size_bytes,
            self.runtime_python_size_bytes,
            self.installed_browsers_json_size_bytes,
            self.chromium_executable_size_bytes,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError("C4 external runtime file size is invalid")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"external_runtime_pin_id", "external_runtime_pin_sha256"},
        )
        if (
            self.external_runtime_pin_id
            != content_id("c4_review_external_runtime", body)
            or self.external_runtime_pin_sha256
            != hashlib.sha256(canonical_json_bytes(body)).hexdigest()
        ):
            raise ValueError("C4 external runtime pin address is invalid")
        return self


class C4Stage1ReviewBrowserRuntimePin(FrozenArtifactModel):
    """Path-free content identity of the exact operational browser runtime."""

    schema_version: Literal["rei-c4-stage1-review-browser-runtime-v1"] = (
        "rei-c4-stage1-review-browser-runtime-v1"
    )
    browser_runtime_id: str
    browser_runtime_sha256: HashDigest
    playwright_python_version: Literal["1.61.0"] = C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION
    chromium_revision: Literal["1228"] = C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION
    chromium_version: Literal["149.0.7827.55"] = C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION
    browser_executable_identity: str
    browser_executable_sha256: HashDigest
    browser_executable_size_bytes: int
    external_runtime: C4Stage1ReviewExternalRuntimePin
    distribution_metadata_verified: Literal[True] = True
    executable_stable_rehash_required: Literal[True] = True
    headed_offline_launch_probe_passed: Literal[True] = True
    lifetime_process_tree_containment_established: Literal[True] = True

    @classmethod
    def create(
        cls,
        *,
        browser_executable_sha256: str,
        browser_executable_size_bytes: int,
        external_runtime: C4Stage1ReviewExternalRuntimePin,
    ) -> C4Stage1ReviewBrowserRuntimePin:
        external_runtime = C4Stage1ReviewExternalRuntimePin.model_validate(
            external_runtime.model_dump(mode="python", round_trip=True)
        )
        if (
            browser_executable_sha256 != external_runtime.chromium_executable_sha256
            or browser_executable_size_bytes
            != external_runtime.chromium_executable_size_bytes
        ):
            raise C4Stage1ReviewPresenterError(
                "The live Chromium executable differs from the sealed browser tree"
            )
        executable_body = {
            "playwright_python_version": C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION,
            "chromium_revision": C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION,
            "chromium_version": C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION,
            "browser_executable_sha256": browser_executable_sha256,
            "browser_executable_size_bytes": browser_executable_size_bytes,
            "external_runtime": external_runtime.model_dump(
                mode="python", round_trip=True
            ),
        }
        body = {
            "schema_version": "rei-c4-stage1-review-browser-runtime-v1",
            **executable_body,
            "browser_executable_identity": content_id(
                "c4_review_browser_executable", executable_body
            ),
            "distribution_metadata_verified": True,
            "executable_stable_rehash_required": True,
            "headed_offline_launch_probe_passed": True,
            "lifetime_process_tree_containment_established": True,
        }
        return cls(
            browser_runtime_id=content_id("c4_review_browser_runtime", body),
            browser_runtime_sha256=hashlib.sha256(
                canonical_json_bytes(body)
            ).hexdigest(),
            **body,
        )

    @model_validator(mode="after")
    def validate_runtime_pin(self) -> Self:
        if type(self.browser_executable_size_bytes) is not int or not (
            0 < self.browser_executable_size_bytes <= 2 * 1024 * 1024 * 1024
        ):
            raise ValueError("C4 Stage 1 browser executable size is invalid")
        executable_body = {
            "playwright_python_version": self.playwright_python_version,
            "chromium_revision": self.chromium_revision,
            "chromium_version": self.chromium_version,
            "browser_executable_sha256": self.browser_executable_sha256,
            "browser_executable_size_bytes": self.browser_executable_size_bytes,
            "external_runtime": self.external_runtime.model_dump(
                mode="python", round_trip=True
            ),
        }
        if self.browser_executable_identity != content_id(
            "c4_review_browser_executable", executable_body
        ):
            raise ValueError("C4 Stage 1 browser executable identity is invalid")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"browser_runtime_id", "browser_runtime_sha256"},
        )
        if (
            self.browser_runtime_id != content_id("c4_review_browser_runtime", body)
            or self.browser_runtime_sha256
            != hashlib.sha256(canonical_json_bytes(body)).hexdigest()
        ):
            raise ValueError("C4 Stage 1 browser runtime address is invalid")
        return self


@dataclass(slots=True)
class _BrowserSessionState:
    packet_delivered: bool = False
    ui_ready: bool = False
    terminal_kind: str | None = None
    pending_submission: bytes | None = None
    failure: str | None = None
    blocked_request_url: str | None = None
    submitted_at: datetime | None = None


class _ProcessTreeContainment(Protocol):
    def terminate(self, reason: str) -> None: ...


class _WindowsPresenterJobContainment:
    """Lifetime nested Job Object inherited by every Playwright descendant."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise C4Stage1ReviewPresenterError(
                "C4 Stage 1 presenter containment requires Windows Job Objects"
            )
        try:  # imports stay lazy and do not touch the external sealed runtime
            import ctypes
            from types import SimpleNamespace

            from .process_tree_runner import CtypesWindowsJobApi

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            current_handle = kernel32.GetCurrentProcess()
            if not current_handle:
                raise OSError("GetCurrentProcess returned no handle")
            self._api = CtypesWindowsJobApi()
            self._job = self._api.create_kill_on_close_job()
            self._api.assign(
                self._job,
                SimpleNamespace(_handle=int(current_handle)),
            )
        except Exception as exc:
            raise C4Stage1ReviewPresenterError(
                "The presenter could not establish lifetime Job containment"
            ) from exc

    def terminate(self, _reason: str) -> None:
        try:
            self._api.terminate(self._job)
        finally:  # pragma: no cover - successful job termination kills this process
            os._exit(74)


@dataclass(slots=True)
class _DeadlineControl:
    deadline_ns: int
    monotonic_ns: Callable[[], int]
    hard_terminate: Callable[[str], None]
    cancellation_grace_ms: int
    cancelled: threading.Event = dataclass_field(default_factory=threading.Event)
    completed: threading.Event = dataclass_field(default_factory=threading.Event)
    termination_requested: threading.Event = dataclass_field(
        default_factory=threading.Event
    )
    _termination_lock: threading.Lock = dataclass_field(default_factory=threading.Lock)
    _watchdog: threading.Thread | None = None

    def checkpoint(self, label: str) -> None:
        if self.cancelled.is_set():
            raise C4Stage1ReviewPresenterError(
                f"The C4 Stage 1 presentation was cancelled during {label}"
            )
        if self.monotonic_ns() >= self.deadline_ns:
            raise C4Stage1ReviewPresenterError(
                f"The absolute C4 Stage 1 presentation deadline expired during {label}"
            )

    def remaining_ms(self, label: str) -> int:
        self.checkpoint(label)
        return max(
            1,
            math.ceil((self.deadline_ns - self.monotonic_ns()) / 1_000_000),
        )

    def cleanup_checkpoint(self, label: str) -> None:
        if self.monotonic_ns() >= self.deadline_ns:
            raise C4Stage1ReviewPresenterError(
                f"The absolute C4 Stage 1 presentation deadline expired during {label}"
            )

    def request_hard_termination(self, reason: str) -> None:
        with self._termination_lock:
            if self.termination_requested.is_set():
                return
            self.termination_requested.set()
        self.hard_terminate(reason)

    def start_watchdog(self) -> None:
        def watch() -> None:
            cancel_started_ns: int | None = None
            while not self.completed.is_set():
                now = self.monotonic_ns()
                if now >= self.deadline_ns:
                    self.request_hard_termination("absolute-deadline")
                    return
                if self.cancelled.is_set():
                    if cancel_started_ns is None:
                        cancel_started_ns = now
                    if (
                        now - cancel_started_ns
                        >= self.cancellation_grace_ms * 1_000_000
                    ):
                        self.request_hard_termination("cancel-grace-expired")
                        return
                wait_ns = min(self.deadline_ns - now, 50_000_000)
                if cancel_started_ns is not None:
                    cancel_deadline = (
                        cancel_started_ns + self.cancellation_grace_ms * 1_000_000
                    )
                    wait_ns = min(wait_ns, max(1, cancel_deadline - now))
                self.completed.wait(max(0.001, wait_ns / 1_000_000_000))

        self._watchdog = threading.Thread(
            target=watch,
            name="rei-c4-review-deadline-watchdog",
            daemon=True,
        )
        self._watchdog.start()

    def finish(self) -> None:
        self.completed.set()
        watchdog = self._watchdog
        if watchdog is not None and watchdog is not threading.current_thread():
            watchdog.join(timeout=0.1)


@dataclass(frozen=True, slots=True)
class _PngPixelIdentity:
    """Decoded-pixel inputs whose equality proves a lossless PNG rewrite."""

    ihdr: bytes
    width: int
    height: int
    bytes_per_pixel: int
    decoded_pixels: bytes
    row_filter_types: bytes = dataclass_field(compare=False)
    filtered_scanlines: bytes = dataclass_field(compare=False)
    compressed_idat: bytes = dataclass_field(compare=False)


@dataclass(frozen=True, slots=True)
class _BlindedCandidate:
    slot: str
    context_index: int
    instruction: str
    png_bytes: bytes


@dataclass(frozen=True, slots=True)
class _BlindedPresentation:
    session_token: str
    source_slot: str
    source_png_bytes: bytes
    candidates: tuple[_BlindedCandidate, _BlindedCandidate]

    def browser_packet(self) -> dict[str, Any]:
        return {
            "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
            "serviceSchemaRevision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
            "ledgerSchemaRevision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
            "sessionToken": self.session_token,
            "referenceSlot": {
                "slot": self.source_slot,
                "pngBytes": list(self.source_png_bytes),
            },
            "candidateSlots": [
                {
                    "slot": item.slot,
                    "instruction": item.instruction,
                    "pngBytes": list(item.png_bytes),
                }
                for item in self.candidates
            ],
        }


def _default_playwright_factory() -> ContextManager[Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised without dependency
        raise C4Stage1ReviewPresenterError(
            "Python Playwright is required for the headed C4 Stage 1 review"
        ) from exc
    return sync_playwright()


def _default_playwright_runtime_identity() -> tuple[str, str, str]:
    """Read the installed distribution's own Chromium inventory lazily."""

    try:
        distribution = metadata.distribution("playwright")
        version = distribution.version
        inventory_path = Path(
            distribution.locate_file("playwright/driver/package/browsers.json")
        ).resolve(strict=True)
        before = os.lstat(inventory_path)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _is_reparse_point(before)
            or before.st_nlink != 1
            or not 0 < before.st_size <= 1024 * 1024
        ):
            raise OSError
        raw = inventory_path.read_bytes()
        after = os.lstat(inventory_path)
        if (
            not os.path.samestat(before, after)
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise OSError
        decoded = json.loads(raw.decode("utf-8"))
        browsers = decoded.get("browsers") if type(decoded) is dict else None
        chromium = (
            [
                item
                for item in browsers
                if type(item) is dict and item.get("name") == "chromium"
            ]
            if type(browsers) is list
            else []
        )
        if len(chromium) != 1:
            raise ValueError
        revision = chromium[0].get("revision")
        browser_version = chromium[0].get("browserVersion")
    except Exception as exc:
        raise C4Stage1ReviewPresenterError(
            "The pinned Python Playwright distribution metadata is unavailable"
        ) from exc
    if (version, revision, browser_version) != (
        C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION,
        C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION,
        C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION,
    ):
        raise C4Stage1ReviewPresenterError(
            "The installed Playwright/Chromium revision differs from the C4 pin"
        )
    return version, revision, browser_version


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_chunk(kind: bytes, value: bytes) -> bytes:
    return (
        struct.pack(">I", len(value))
        + kind
        + value
        + struct.pack(">I", zlib.crc32(kind + value) & 0xFFFFFFFF)
    )


def _paeth(left: int, above: int, upper_left: int) -> int:
    value = left + above - upper_left
    left_distance = abs(value - left)
    above_distance = abs(value - above)
    upper_left_distance = abs(value - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _unfilter_png_rows(
    filtered: bytes, *, width: int, height: int, bytes_per_pixel: int
) -> tuple[bytes, bytes]:
    row_bytes = width * bytes_per_pixel
    pixels = bytearray(height * row_bytes)
    filters = bytearray(height)
    offset = 0
    previous = bytes(row_bytes)
    for row_index in range(height):
        filter_type = filtered[offset]
        filters[row_index] = filter_type
        offset += 1
        encoded = filtered[offset : offset + row_bytes]
        offset += row_bytes
        if filter_type > 4 or len(encoded) != row_bytes:
            raise C4Stage1ReviewPresenterError("Review PNG row filter is invalid")
        decoded = bytearray(row_bytes)
        for index, value in enumerate(encoded):
            left = decoded[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            above = previous[index]
            upper_left = (
                previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            )
            predictor = (
                0
                if filter_type == 0
                else left
                if filter_type == 1
                else above
                if filter_type == 2
                else (left + above) // 2
                if filter_type == 3
                else _paeth(left, above, upper_left)
            )
            decoded[index] = (value + predictor) & 0xFF
        start = row_index * row_bytes
        pixels[start : start + row_bytes] = decoded
        previous = decoded
    return bytes(pixels), bytes(filters)


def _filter_png_rows(
    pixels: bytes,
    *,
    width: int,
    height: int,
    bytes_per_pixel: int,
    filter_types: bytes,
) -> bytes:
    row_bytes = width * bytes_per_pixel
    filtered = bytearray(height * (row_bytes + 1))
    output_offset = 0
    previous = bytes(row_bytes)
    for row_index, filter_type in enumerate(filter_types):
        current = pixels[row_index * row_bytes : (row_index + 1) * row_bytes]
        filtered[output_offset] = filter_type
        output_offset += 1
        for index, value in enumerate(current):
            left = current[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            above = previous[index]
            upper_left = (
                previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            )
            predictor = (
                0
                if filter_type == 0
                else left
                if filter_type == 1
                else above
                if filter_type == 2
                else (left + above) // 2
                if filter_type == 3
                else _paeth(left, above, upper_left)
            )
            filtered[output_offset] = (value - predictor) & 0xFF
            output_offset += 1
        previous = current
    return bytes(filtered)


def _parse_png_pixel_identity(value: bytes) -> _PngPixelIdentity:
    """Strictly parse bounded PNG pixels without retaining identifying metadata."""

    if (
        type(value) is not bytes
        or not len(_PNG_SIGNATURE) < len(value) <= _MAX_BLINDED_PNG_BYTES
        or not value.startswith(_PNG_SIGNATURE)
    ):
        raise C4Stage1ReviewPresenterError("Review material is not a bounded PNG")
    offset = len(_PNG_SIGNATURE)
    ihdr: bytes | None = None
    palette: bytes | None = None
    transparency: bytes | None = None
    idat_parts: list[bytes] = []
    seen_idat = False
    idat_ended = False
    seen_iend = False
    while offset < len(value):
        if len(value) - offset < 12:
            raise C4Stage1ReviewPresenterError("Review PNG framing is incomplete")
        length = struct.unpack(">I", value[offset : offset + 4])[0]
        kind = value[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(value) or any(
            not (65 <= item <= 90 or 97 <= item <= 122) for item in kind
        ):
            raise C4Stage1ReviewPresenterError("Review PNG chunk framing is invalid")
        body = value[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", value[offset + 8 + length : end])[0]
        if (zlib.crc32(kind + body) & 0xFFFFFFFF) != expected_crc:
            raise C4Stage1ReviewPresenterError("Review PNG chunk checksum is invalid")
        if ihdr is None and kind != b"IHDR":
            raise C4Stage1ReviewPresenterError("Review PNG does not begin with IHDR")
        if kind == b"IHDR":
            if ihdr is not None or length != 13 or offset != len(_PNG_SIGNATURE):
                raise C4Stage1ReviewPresenterError("Review PNG IHDR is invalid")
            ihdr = body
        elif kind == b"PLTE":
            if palette is not None or seen_idat or not 0 < length <= 768 or length % 3:
                raise C4Stage1ReviewPresenterError("Review PNG palette is invalid")
            palette = body
        elif kind == b"tRNS":
            if transparency is not None or seen_idat:
                raise C4Stage1ReviewPresenterError("Review PNG transparency is invalid")
            transparency = body
        elif kind == b"IDAT":
            if idat_ended:
                raise C4Stage1ReviewPresenterError("Review PNG IDAT is not contiguous")
            seen_idat = True
            idat_parts.append(body)
        else:
            if seen_idat:
                idat_ended = True
            if kind == b"IEND":
                if length != 0 or seen_iend or end != len(value):
                    raise C4Stage1ReviewPresenterError("Review PNG IEND is invalid")
                seen_iend = True
            elif kind[0] & 0x20 == 0:
                raise C4Stage1ReviewPresenterError(
                    "Review PNG contains an unsupported critical chunk"
                )
        offset = end
    if ihdr is None or not idat_parts or not seen_iend:
        raise C4Stage1ReviewPresenterError("Review PNG structure is incomplete")

    width, height, bit_depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", ihdr)
    )
    if (
        not 0 < width <= 0x7FFFFFFF
        or not 0 < height <= 0x7FFFFFFF
        or bit_depth != 8
        or color_type not in (2, 6)
        or compression != 0
        or filtering != 0
        or interlace != 0
        or palette is not None
        or transparency is not None
    ):
        raise C4Stage1ReviewPresenterError(
            "Review PNG must be RGB8 or RGBA8 and non-interlaced"
        )
    bytes_per_pixel = 3 if color_type == 2 else 4
    expected_size = height * (1 + (width * bytes_per_pixel))
    if not 0 < expected_size <= _MAX_BLINDED_PNG_BYTES:
        raise C4Stage1ReviewPresenterError("Review PNG decoded pixels exceed the bound")
    try:
        decompressor = zlib.decompressobj()
        compressed_idat = b"".join(idat_parts)
        filtered = decompressor.decompress(compressed_idat, expected_size + 1)
        if len(filtered) <= expected_size:
            filtered += decompressor.flush(expected_size + 1 - len(filtered))
    except zlib.error as exc:
        raise C4Stage1ReviewPresenterError(
            "Review PNG pixel stream is invalid"
        ) from exc
    if (
        len(filtered) != expected_size
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise C4Stage1ReviewPresenterError("Review PNG pixel stream is not exact")
    decoded_pixels, row_filter_types = _unfilter_png_rows(
        filtered,
        width=width,
        height=height,
        bytes_per_pixel=bytes_per_pixel,
    )
    return _PngPixelIdentity(
        ihdr=ihdr,
        width=width,
        height=height,
        bytes_per_pixel=bytes_per_pixel,
        decoded_pixels=decoded_pixels,
        row_filter_types=row_filter_types,
        filtered_scanlines=filtered,
        compressed_idat=compressed_idat,
    )


def _blind_png(value: bytes, *, nonce: bytes) -> bytes:
    """Losslessly rewrite one PNG in memory with unlinkable session entropy."""

    if type(nonce) is not bytes or len(nonce) != 32:
        raise C4Stage1ReviewPresenterError("PNG blinding nonce must be 256 bits")
    identity = _parse_png_pixel_identity(value)
    entropy = hashlib.shake_256(b"rei-c4-stage1-png-blinding-v2\x00" + nonce).digest(
        identity.height + 64
    )
    filter_types = bytes(item % 5 for item in entropy[: identity.height])
    if filter_types == identity.row_filter_types:
        filter_types = bytes(((filter_types[0] + 1) % 5, *filter_types[1:]))
    filtered = _filter_png_rows(
        identity.decoded_pixels,
        width=identity.width,
        height=identity.height,
        bytes_per_pixel=identity.bytes_per_pixel,
        filter_types=filter_types,
    )
    if hmac.compare_digest(filtered, identity.filtered_scanlines):
        raise C4Stage1ReviewPresenterError(
            "PNG row-filter randomization did not change the scanline stream"
        )
    strategies = (
        zlib.Z_DEFAULT_STRATEGY,
        zlib.Z_FILTERED,
        zlib.Z_HUFFMAN_ONLY,
        zlib.Z_RLE,
        zlib.Z_FIXED,
    )
    compressor = zlib.compressobj(
        level=1 + (entropy[identity.height] % 9),
        method=zlib.DEFLATED,
        wbits=15,
        memLevel=1 + (entropy[identity.height + 1] % 9),
        strategy=strategies[entropy[identity.height + 2] % len(strategies)],
    )
    compressed = compressor.compress(filtered) + compressor.flush()
    if hmac.compare_digest(compressed, identity.compressed_idat):
        raise C4Stage1ReviewPresenterError(
            "PNG compression randomization did not change the IDAT stream"
        )
    chunks = [_png_chunk(b"IHDR", identity.ihdr)]
    chunks.append(_png_chunk(b"reIa", nonce))
    chunk_entropy = hashlib.shake_256(b"idat-chunks\x00" + nonce).digest(
        max(32, (len(compressed) // 1024) + 32)
    )
    cursor = 0
    chunk_index = 0
    while cursor < len(compressed):
        maximum = min(16 * 1024, len(compressed) - cursor)
        chunk_size = 1 + (chunk_entropy[chunk_index % len(chunk_entropy)] % maximum)
        chunks.append(_png_chunk(b"IDAT", compressed[cursor : cursor + chunk_size]))
        cursor += chunk_size
        chunk_index += 1
    chunks.append(_png_chunk(b"IEND", b""))
    blinded = _PNG_SIGNATURE + b"".join(chunks)
    if len(blinded) > _MAX_BLINDED_PNG_BYTES:
        raise C4Stage1ReviewPresenterError("Blinded review PNG exceeds the byte bound")
    if (
        hmac.compare_digest(_sha256(blinded), _sha256(value))
        or _parse_png_pixel_identity(blinded) != identity
    ):
        raise C4Stage1ReviewPresenterError(
            "The in-memory PNG blinding rewrite did not preserve exact pixels"
        )
    return blinded


def _operational_probe_png(red: int, green: int, blue: int) -> bytes:
    """Create a metadata-free RGB8 PNG solely for the runtime smoke probe."""

    width = height = 8
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    filtered = b"".join(
        bytes((0,))
        + b"".join(
            bytes(
                (
                    (red + row + column) & 0xFF,
                    (green + (2 * row) + column) & 0xFF,
                    (blue + row + (2 * column)) & 0xFF,
                )
            )
            for column in range(width)
        )
        for row in range(height)
    )
    return (
        _PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(filtered, level=1))
        + _png_chunk(b"IEND", b"")
    )


def _is_reparse_point(value: os.stat_result) -> bool:
    return bool(getattr(value, "st_file_attributes", 0) & 0x400)


def _stable_executable_identity(
    executable: Path, *, checkpoint: Callable[[str], None] | None = None
) -> tuple[str, int]:
    try:
        executable = executable.resolve(strict=True)
        before = os.lstat(executable)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _is_reparse_point(before)
            or before.st_nlink != 1
            or not 0 < before.st_size <= 2 * 1024 * 1024 * 1024
        ):
            raise OSError
        digest = hashlib.sha256()
        with executable.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                if checkpoint is not None:
                    checkpoint("browser executable hashing")
                digest.update(chunk)
            opened = os.fstat(handle.fileno())
        after = os.lstat(executable)
        if (
            not os.path.samestat(before, opened)
            or not os.path.samestat(before, after)
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise OSError
    except OSError as exc:
        raise C4Stage1ReviewPresenterError(
            "The pinned browser executable is not stable and ordinary"
        ) from exc
    return digest.hexdigest(), before.st_size


def _strict_record(
    value: object, expected_keys: set[str], *, label: str
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected_keys:
        raise C4Stage1ReviewPresenterError(f"{label} has the wrong fields")
    return value


def _strict_text(value: object, *, label: str, maximum: int = 200) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or value.strip() != value
    ):
        raise C4Stage1ReviewPresenterError(f"{label} must be bounded text")
    return value


def _strict_bool(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        raise C4Stage1ReviewPresenterError(f"{label} must be an explicit boolean")
    return value


def _host_init_script() -> str:
    """Return the fixed pre-document bridge used by the pinned UI."""

    return f"""
(() => {{
  'use strict';
  const state = {{
    packetDelivered: false,
    packet: null,
    markingReady: false,
    uiReady: false,
    bindingPending: false,
    terminal: false,
    submitted: false,
    cancelled: false,
    failed: false
  }};

  function failClosed(error) {{
    state.failed = true;
    state.terminal = true;
    throw error;
  }}

  function visibleUiMatchesPacket() {{
    if (!state.packetDelivered || state.packet === null) return false;
    const packet = state.packet;
    const status = document.getElementById('review-status');
    const submit = document.getElementById('submit-review');
    const cancel = document.getElementById('cancel-review');
    const reviewer = document.getElementById('reviewer-pseudonym');
    const source = document.getElementById('source-image');
    if (!status || status.textContent !== 'Verified review material is ready.' ||
        !submit || submit.disabled || !cancel || cancel.disabled ||
        !reviewer || reviewer.value !== '' || !source ||
        !source.src.startsWith('blob:') || !source.complete ||
        source.naturalWidth <= 0 || source.naturalHeight <= 0 ||
        document.getElementById('source-slot')?.textContent !==
          packet.referenceSlot.slot ||
        document.querySelectorAll('input[type="radio"]:checked').length !== 0) {{
      return false;
    }}
    return packet.candidateSlots.length === 2 &&
      packet.candidateSlots.every((output, index) => {{
      const image = document.getElementById(`output-image-${{index}}`);
      return image && image.src.startsWith('blob:') && image.complete &&
        image.naturalWidth > 0 && image.naturalHeight > 0 &&
        document.getElementById(`output-code-${{index}}`)?.textContent ===
          output.slot &&
        document.getElementById(`output-instruction-${{index}}`)?.textContent ===
          output.instruction;
    }});
  }}

  async function markReadyIfPossible() {{
    if (state.uiReady || state.markingReady || state.failed || state.terminal ||
        !visibleUiMatchesPacket()) return;
    state.markingReady = true;
    try {{
      await globalThis.{_MARK_READY_BINDING}({{
        ipcProtocol: '{C4_STAGE1_REVIEW_IPC_PROTOCOL}',
        sessionToken: state.packet.sessionToken
      }});
      state.uiReady = true;
    }} catch (error) {{
      failClosed(error);
    }} finally {{
      state.markingReady = false;
    }}
  }}

  const host = Object.freeze({{
    async getReviewPacket(request) {{
      if (state.packetDelivered || state.terminal) {{
        return failClosed(new TypeError('Review packet was requested more than once'));
      }}
      try {{
        const packet = await globalThis.{_GET_PACKET_BINDING}(request);
        state.packet = packet;
        state.packetDelivered = true;
        return packet;
      }} catch (error) {{
        return failClosed(error);
      }}
    }},
    async submitReview(submission) {{
      await markReadyIfPossible();
      if (!state.uiReady || state.terminal || state.bindingPending) {{
        return failClosed(new TypeError('Review UI is not ready for submission'));
      }}
      state.bindingPending = true;
      try {{
        await globalThis.{_SUBMIT_BINDING}(submission);
        state.submitted = true;
        state.terminal = true;
        return Object.freeze({{ accepted: true }});
      }} catch (error) {{
        return failClosed(error);
      }} finally {{
        state.bindingPending = false;
      }}
    }},
    async cancelReview(request) {{
      await markReadyIfPossible();
      if (!state.uiReady || state.terminal || state.bindingPending) {{
        return failClosed(new TypeError('Review UI is not ready for cancellation'));
      }}
      state.bindingPending = true;
      try {{
        await globalThis.{_CANCEL_BINDING}(request);
        state.cancelled = true;
        state.terminal = true;
        return Object.freeze({{ cancelled: true }});
      }} catch (error) {{
        return failClosed(error);
      }} finally {{
        state.bindingPending = false;
      }}
    }}
  }});

  Object.defineProperty(globalThis, '__reiReviewHostState', {{
    value: state,
    configurable: false,
    enumerable: false,
    writable: false
  }});
  Object.defineProperty(globalThis, 'reiReviewHost', {{
    value: host,
    configurable: false,
    enumerable: false,
    writable: false
  }});

  document.addEventListener('DOMContentLoaded', () => {{
    const observer = new MutationObserver(() => void markReadyIfPossible());
    observer.observe(document.documentElement, {{
      subtree: true,
      childList: true,
      attributes: true,
      characterData: true
    }});
    ['source-image', 'output-image-0', 'output-image-1'].forEach((id) => {{
      const image = document.getElementById(id);
      image?.addEventListener('load', () => void markReadyIfPossible());
      image?.addEventListener('error', () => {{
        try {{ failClosed(new TypeError('A blinded review image failed to decode')); }}
        catch (_) {{ /* the terminal failure is retained in host state */ }}
      }});
    }});
    void markReadyIfPossible();
  }}, {{ once: true }});
  document.addEventListener('load', () => void markReadyIfPossible(), true);
}})();
"""


class C4Stage1OfflineReviewPresenter:
    """Run one exact, headed, offline C4 Stage 1 review session."""

    presenter_implementation_id = C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
    presenter_revision = C4_STAGE1_REVIEW_PRESENTER_REVISION

    def __init__(
        self,
        *,
        repository_root: str | Path,
        runtime_manifest: C4Stage1ReviewRuntimeManifest,
        user_data_dir: str | Path,
        runtime_provenance_root: str | Path,
        external_runtime_root: str | Path,
        external_browser_root: str | Path,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
        playwright_factory: Callable[[], ContextManager[Any]] | None = None,
        runtime_identity_resolver: Callable[[], tuple[str, str, str]] | None = None,
        runtime_verifier: Callable[..., dict[str, object]] | None = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        utc_clock: Callable[[], datetime] | None = None,
        process_tree_containment: _ProcessTreeContainment | None = None,
        cancellation_grace_ms: int = _CANCEL_HARD_TERMINATION_GRACE_MS,
    ) -> None:
        repository_root = Path(repository_root)
        user_data_dir = Path(user_data_dir)
        runtime_provenance_root = Path(runtime_provenance_root)
        external_runtime_root = Path(external_runtime_root)
        external_browser_root = Path(external_browser_root)
        if not repository_root.is_absolute():
            raise C4Stage1ReviewPresenterError("repository_root must be absolute")
        if not user_data_dir.is_absolute():
            raise C4Stage1ReviewPresenterError("user_data_dir must be absolute")
        if not all(
            path.is_absolute()
            for path in (
                runtime_provenance_root,
                external_runtime_root,
                external_browser_root,
            )
        ):
            raise C4Stage1ReviewPresenterError(
                "All sealed review runtime roots must be absolute"
            )
        if not isinstance(runtime_manifest, C4Stage1ReviewRuntimeManifest):
            raise TypeError("runtime_manifest must be a C4Stage1ReviewRuntimeManifest")
        if type(timeout_ms) is not int or not 1_000 <= timeout_ms <= 4 * 60 * 60 * 1000:
            raise C4Stage1ReviewPresenterError("timeout_ms is outside the review bound")
        if playwright_factory is not None and not callable(playwright_factory):
            raise TypeError("playwright_factory must be callable")
        if runtime_identity_resolver is not None and not callable(
            runtime_identity_resolver
        ):
            raise TypeError("runtime_identity_resolver must be callable")
        if runtime_verifier is not None and not callable(runtime_verifier):
            raise TypeError("runtime_verifier must be callable")
        if not callable(monotonic_ns):
            raise TypeError("monotonic_ns must be callable")
        if utc_clock is not None and not callable(utc_clock):
            raise TypeError("utc_clock must be callable")
        if process_tree_containment is not None and not callable(
            getattr(process_tree_containment, "terminate", None)
        ):
            raise TypeError("process_tree_containment must expose terminate")
        if (
            type(cancellation_grace_ms) is not int
            or not 10 <= cancellation_grace_ms <= 30_000
        ):
            raise C4Stage1ReviewPresenterError(
                "cancellation_grace_ms is outside the fail-closed bound"
            )
        if playwright_factory is None and not sys.flags.dont_write_bytecode:
            raise C4Stage1ReviewPresenterError(
                "The sealed review runtime must be launched with bytecode writes disabled"
            )

        self._repository_root = repository_root.resolve(strict=True)
        try:
            self._runtime_provenance_root = runtime_provenance_root.resolve(strict=True)
            self._external_runtime_root = external_runtime_root.resolve(strict=True)
            self._external_browser_root = external_browser_root.resolve(strict=True)
        except OSError as exc:
            raise C4Stage1ReviewPresenterError(
                "A sealed review runtime root does not exist"
            ) from exc
        sealed_roots = (
            self._runtime_provenance_root,
            self._external_runtime_root,
            self._external_browser_root,
        )
        if len(set(sealed_roots)) != 3 or any(
            left.is_relative_to(right) or right.is_relative_to(left)
            for index, left in enumerate(sealed_roots)
            for right in sealed_roots[index + 1 :]
        ):
            raise C4Stage1ReviewPresenterError(
                "The sealed review runtime roots must be disjoint"
            )
        self._runtime_manifest = C4Stage1ReviewRuntimeManifest.model_validate(
            runtime_manifest.model_dump(mode="python", round_trip=True)
        )
        self._user_data_dir = user_data_dir
        self._timeout_ms = timeout_ms
        self._playwright_factory = playwright_factory or _default_playwright_factory
        self._runtime_identity_resolver = (
            runtime_identity_resolver or _default_playwright_runtime_identity
        )
        self._runtime_verifier = runtime_verifier or verify_presenter_runtime
        self._require_revision_in_path = playwright_factory is None
        self._require_external_python_binding = playwright_factory is None
        self._monotonic_ns = monotonic_ns
        self._utc_clock = utc_clock or (lambda: datetime.now(timezone.utc))
        self._process_tree_containment = (
            process_tree_containment or _WindowsPresenterJobContainment()
        )
        self._hard_terminate = self._process_tree_containment.terminate
        self._cancellation_grace_ms = cancellation_grace_ms
        self._lock = threading.Lock()
        self._active = False
        self._active_control: _DeadlineControl | None = None
        self._attempted_context_ids: set[str] = set()
        self._submissions: dict[str, tuple[bytes, datetime]] = {}
        self._browser_runtime_pin: C4Stage1ReviewBrowserRuntimePin | None = None
        self._browser_executable_path: Path | None = None
        self._browser_user_data_parent: Path | None = None

        if self._require_external_python_binding:
            expected_python = self._external_runtime_root.joinpath(
                *RUNTIME_PYTHON_RELATIVE_PATH.split("/")
            ).resolve(strict=True)
            if Path(sys.executable).resolve(strict=True) != expected_python:
                raise C4Stage1ReviewPresenterError(
                    "The presenter was not launched by the sealed review Python"
                )

    @property
    def session_timeout_ms(self) -> int:
        return self._timeout_ms

    @property
    def browser_runtime_pin(self) -> C4Stage1ReviewBrowserRuntimePin:
        if self._browser_runtime_pin is None:
            raise C4Stage1ReviewPresenterError(
                "The browser runtime has not passed its operational probe"
            )
        return C4Stage1ReviewBrowserRuntimePin.model_validate(
            self._browser_runtime_pin.model_dump(mode="python", round_trip=True)
        )

    @property
    def browser_executable_path(self) -> Path:
        """Return the private resolved executable root only after the live probe."""

        if self._browser_executable_path is None:
            raise C4Stage1ReviewPresenterError(
                "The browser executable path is unavailable before the live probe"
            )
        return self._browser_executable_path

    @property
    def browser_user_data_parent(self) -> Path:
        """Return the private external session parent only after the live probe."""

        if self._browser_user_data_parent is None:
            raise C4Stage1ReviewPresenterError(
                "The browser session parent is unavailable before the live probe"
            )
        return self._browser_user_data_parent

    @property
    def runtime_provenance_root(self) -> Path:
        """Return the resolved create-only provenance root for boundary checks."""

        return self._runtime_provenance_root

    @property
    def external_runtime_root(self) -> Path:
        """Return the resolved sealed Python/Playwright runtime root."""

        return self._external_runtime_root

    @property
    def external_browser_root(self) -> Path:
        """Return the resolved sealed Chromium runtime root."""

        return self._external_browser_root

    def _new_deadline_control(
        self,
        timeout_ms: int,
        *,
        cancellation_event: threading.Event | None = None,
    ) -> _DeadlineControl:
        started_ns = self._monotonic_ns()
        control = _DeadlineControl(
            deadline_ns=started_ns + (timeout_ms * 1_000_000),
            monotonic_ns=self._monotonic_ns,
            hard_terminate=self._hard_terminate,
            cancellation_grace_ms=self._cancellation_grace_ms,
            cancelled=(
                cancellation_event
                if cancellation_event is not None
                else threading.Event()
            ),
        )
        control.start_watchdog()
        return control

    def _resolve_exact_runtime_identity(self, control: _DeadlineControl) -> None:
        control.checkpoint("Playwright distribution identity start")
        try:
            identity = self._runtime_identity_resolver()
        except C4Stage1ReviewPresenterError:
            raise
        except Exception as exc:
            raise C4Stage1ReviewPresenterError(
                "The pinned Playwright runtime identity could not be resolved"
            ) from exc
        if identity != (
            C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION,
            C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION,
            C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION,
        ):
            raise C4Stage1ReviewPresenterError(
                "The installed Playwright/Chromium revision differs from the C4 pin"
            )
        control.checkpoint("Playwright distribution identity completion")

    def _verify_external_runtime(
        self,
        control: _DeadlineControl,
        *,
        expected: C4Stage1ReviewExternalRuntimePin | None = None,
    ) -> C4Stage1ReviewExternalRuntimePin:
        control.checkpoint("external runtime tree verification start")
        try:
            result = self._runtime_verifier(
                self._runtime_provenance_root,
                self._external_runtime_root,
                self._external_browser_root,
                checkpoint=lambda: control.checkpoint(
                    "external runtime tree verification hashing"
                ),
            )
            pin = C4Stage1ReviewExternalRuntimePin.create(result)
        except C4Stage1ReviewPresenterError:
            raise
        except Exception as exc:
            try:
                control.checkpoint("external runtime tree verification failure")
            except C4Stage1ReviewPresenterError as terminal:
                raise terminal from exc
            raise C4Stage1ReviewPresenterError(
                "The complete external review runtime tree failed verification"
            ) from exc
        if expected is not None:
            expected = C4Stage1ReviewExternalRuntimePin.model_validate(
                expected.model_dump(mode="python", round_trip=True)
            )
            if pin != expected:
                raise C4Stage1ReviewPresenterError(
                    "The external browser runtime changed after its live probe"
                )
        control.checkpoint("external runtime tree verification completion")
        return pin

    def _capture_executable_pin(
        self,
        chromium: Any,
        control: _DeadlineControl,
        external_runtime: C4Stage1ReviewExternalRuntimePin,
    ) -> C4Stage1ReviewBrowserRuntimePin:
        control.checkpoint("browser executable identity start")
        executable = Path(chromium.executable_path).resolve(strict=True)
        expected_executable = self._external_browser_root.joinpath(
            *CHROMIUM_EXECUTABLE_RELATIVE_PATH.split("/")
        ).resolve(strict=True)
        if executable != expected_executable:
            raise C4Stage1ReviewPresenterError(
                "The live Chromium executable is outside the sealed browser tree"
            )
        if self._require_revision_in_path and (
            f"chromium-{C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION}"
            not in {part.casefold() for part in executable.parts}
        ):
            raise C4Stage1ReviewPresenterError(
                "The Chromium executable path differs from the pinned revision"
            )
        digest, size = _stable_executable_identity(
            executable, checkpoint=control.checkpoint
        )
        control.checkpoint("browser executable identity completion")
        return C4Stage1ReviewBrowserRuntimePin.create(
            browser_executable_sha256=digest,
            browser_executable_size_bytes=size,
            external_runtime=external_runtime,
        )

    @staticmethod
    def _close_browser_context(
        browser_context: Any,
        control: _DeadlineControl,
        *,
        label: str,
    ) -> None:
        deadline_failure: C4Stage1ReviewPresenterError | None = None
        try:
            control.cleanup_checkpoint(f"{label} close start")
        except C4Stage1ReviewPresenterError as exc:
            deadline_failure = exc
            control.request_hard_termination(f"{label}-close-deadline")
        try:
            browser_context.close()
        except Exception as exc:
            control.request_hard_termination(f"{label}-close-failed")
            if deadline_failure is not None:
                raise deadline_failure from exc
            raise C4Stage1ReviewPresenterError(
                f"The {label} browser context did not close cleanly"
            ) from exc
        try:
            control.cleanup_checkpoint(f"{label} close completion")
        except C4Stage1ReviewPresenterError as exc:
            deadline_failure = deadline_failure or exc
            control.request_hard_termination(f"{label}-close-deadline")
        if deadline_failure is not None:
            raise deadline_failure

    @staticmethod
    def _exit_playwright_manager(
        manager: ContextManager[Any],
        control: _DeadlineControl,
        *,
        label: str,
    ) -> None:
        deadline_failure: C4Stage1ReviewPresenterError | None = None
        try:
            control.cleanup_checkpoint(f"{label} Playwright driver exit start")
        except C4Stage1ReviewPresenterError as exc:
            deadline_failure = exc
            control.request_hard_termination(f"{label}-driver-exit-deadline")
        try:
            manager.__exit__(None, None, None)
        except Exception as exc:
            control.request_hard_termination(f"{label}-driver-exit-failed")
            if deadline_failure is not None:
                raise deadline_failure from exc
            raise C4Stage1ReviewPresenterError(
                f"The {label} Playwright driver did not exit cleanly"
            ) from exc
        try:
            control.cleanup_checkpoint(f"{label} Playwright driver exit completion")
        except C4Stage1ReviewPresenterError as exc:
            deadline_failure = deadline_failure or exc
            control.request_hard_termination(f"{label}-driver-exit-deadline")
        if deadline_failure is not None:
            raise deadline_failure

    def _remove_profile_under_control(
        self,
        session_dir: Path,
        control: _DeadlineControl,
        *,
        label: str,
    ) -> None:
        deadline_failure: C4Stage1ReviewPresenterError | None = None
        try:
            control.cleanup_checkpoint(f"{label} profile cleanup start")
        except C4Stage1ReviewPresenterError as exc:
            deadline_failure = exc
            control.request_hard_termination(f"{label}-profile-cleanup-deadline")
        try:
            self._remove_external_session_dir(session_dir)
        except Exception as exc:
            control.request_hard_termination(f"{label}-profile-cleanup-failed")
            if deadline_failure is not None:
                raise deadline_failure from exc
            raise
        try:
            control.cleanup_checkpoint(f"{label} profile cleanup completion")
        except C4Stage1ReviewPresenterError as exc:
            deadline_failure = deadline_failure or exc
            control.request_hard_termination(f"{label}-profile-cleanup-deadline")
        if deadline_failure is not None:
            raise deadline_failure

    def verify_operational(self) -> bool:
        """Verify pins and complete one bounded headed/offline UI submission."""

        control = self._new_deadline_control(
            min(self._timeout_ms, _OPERATIONAL_PROBE_TIMEOUT_MS)
        )
        try:
            return self._verify_operational_with_control(control)
        finally:
            control.finish()

    def _verify_operational_with_control(self, control: _DeadlineControl) -> bool:
        session_dir: Path | None = None
        browser_context: Any | None = None
        manager: ContextManager[Any] | None = None
        browser_executable_path: Path | None = None
        browser_user_data_parent: Path | None = None
        runtime_pin: C4Stage1ReviewBrowserRuntimePin | None = None
        external_runtime: C4Stage1ReviewExternalRuntimePin | None = None
        try:
            self._browser_runtime_pin = None
            self._browser_executable_path = None
            self._browser_user_data_parent = None
            control.checkpoint("review runtime manifest verification start")
            manifest = verify_c4_stage1_review_runtime_manifest(
                self._repository_root, self._runtime_manifest
            )
            control.checkpoint("review runtime manifest verification completion")
            assets = self._read_exact_assets(manifest, control=control)
            external_runtime = self._verify_external_runtime(control)
            self._resolve_exact_runtime_identity(control)
            control.checkpoint("operational profile creation start")
            session_dir = self._create_external_session_dir()
            control.checkpoint("operational profile creation completion")
            browser_user_data_parent = session_dir.parent.resolve(strict=True)
            control.checkpoint("operational Playwright manager creation start")
            manager = self._playwright_factory()
            control.checkpoint("operational Playwright manager creation completion")
            control.checkpoint("operational Playwright driver entry start")
            playwright = manager.__enter__()
            control.checkpoint("operational Playwright driver entry completion")
            browser_executable_path = Path(playwright.chromium.executable_path).resolve(
                strict=True
            )
            runtime_pin = self._capture_executable_pin(
                playwright.chromium, control, external_runtime
            )
            control.checkpoint("operational browser launch start")
            browser_context = playwright.chromium.launch_persistent_context(
                str(session_dir),
                headless=False,
                offline=True,
                accept_downloads=False,
                service_workers="block",
                timeout=control.remaining_ms("operational browser launch timeout"),
                args=list(_NO_PERSIST_BROWSER_ARGS),
            )
            control.checkpoint("operational browser launch completion")
            browser_context.set_offline(True)
            control.checkpoint("operational browser offline completion")
            self._run_operational_ui_probe(
                browser_context=browser_context,
                assets=assets,
                control=control,
            )
            self._close_browser_context(
                browser_context, control, label="operational probe"
            )
            browser_context = None
            self._exit_playwright_manager(manager, control, label="operational probe")
            manager = None
        except C4Stage1ReviewPresenterError as exc:
            if "absolute C4 Stage 1 presentation deadline" in str(
                exc
            ) or "presentation was cancelled" in str(exc):
                raise
            raise C4Stage1ReviewPresenterError(
                "The pinned headed browser runtime is not operational"
            ) from exc
        except Exception as exc:
            raise C4Stage1ReviewPresenterError(
                "The pinned headed browser runtime is not operational"
            ) from exc
        finally:
            cleanup_failure: Exception | None = None
            if browser_context is not None:
                try:
                    self._close_browser_context(
                        browser_context, control, label="operational probe"
                    )
                except Exception:
                    control.request_hard_termination("operational-probe-close-failed")
            if manager is not None:
                try:
                    self._exit_playwright_manager(
                        manager, control, label="operational probe"
                    )
                except Exception:
                    control.request_hard_termination("operational-driver-exit-failed")
            if session_dir is not None:
                try:
                    self._remove_profile_under_control(
                        session_dir, control, label="operational"
                    )
                except Exception as exc:
                    control.request_hard_termination(
                        "operational-profile-cleanup-failed"
                    )
                    cleanup_failure = exc
            if cleanup_failure is not None:
                if isinstance(
                    cleanup_failure, C4Stage1ReviewPresenterError
                ) and "absolute C4 Stage 1 presentation deadline" in str(
                    cleanup_failure
                ):
                    raise cleanup_failure
                raise C4Stage1ReviewPresenterError(
                    "The browser operational probe did not clean up"
                ) from cleanup_failure
        if (
            browser_executable_path is None
            or browser_user_data_parent is None
            or runtime_pin is None
            or external_runtime is None
        ):
            raise C4Stage1ReviewPresenterError(
                "The operational browser roots were not captured"
            )
        self._verify_external_runtime(control, expected=external_runtime)
        self._browser_runtime_pin = runtime_pin
        self._browser_executable_path = browser_executable_path
        self._browser_user_data_parent = browser_user_data_parent
        control.checkpoint("operational verification sealing completion")
        return True

    @staticmethod
    def _wait_for_function_bounded(
        page: Any,
        expression: str,
        control: _DeadlineControl,
        *,
        label: str,
    ) -> None:
        while True:
            timeout_ms = min(
                _WAIT_POLL_SLICE_MS,
                control.remaining_ms(f"{label} polling"),
            )
            try:
                page.wait_for_function(expression, timeout=timeout_ms)
            except Exception as exc:
                if type(exc).__name__ != "TimeoutError":
                    raise
                control.checkpoint(f"{label} polling timeout")
                continue
            control.checkpoint(f"{label} completion")
            return

    def _run_operational_ui_probe(
        self,
        *,
        browser_context: Any,
        assets: dict[str, bytes],
        control: _DeadlineControl,
    ) -> None:
        """Exercise the committed UI from decode readiness through host-confirmed submit."""

        control.checkpoint("operational UI material construction start")
        secret = secrets.token_bytes(32)

        def opaque(prefix: str, label: bytes) -> str:
            return prefix + hmac.new(secret, label, hashlib.sha256).hexdigest()

        source = _blind_png(
            _operational_probe_png(11, 22, 33),
            nonce=hmac.new(secret, b"probe-source", hashlib.sha256).digest(),
        )
        candidates = [
            {
                "slot": opaque("slot-", f"probe-slot-{index}".encode("ascii")),
                "instruction": f"Operational probe instruction {index + 1}.",
                "pngBytes": list(
                    _blind_png(
                        _operational_probe_png(40 + index, 50 + index, 60 + index),
                        nonce=hmac.new(
                            secret,
                            f"probe-png-{index}".encode("ascii"),
                            hashlib.sha256,
                        ).digest(),
                    )
                ),
            }
            for index in range(2)
        ]
        candidates.sort(key=lambda item: item["slot"])
        session_token = opaque("session-", b"probe-session")
        packet = {
            "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
            "serviceSchemaRevision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
            "ledgerSchemaRevision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
            "sessionToken": session_token,
            "referenceSlot": {
                "slot": opaque("slot-", b"probe-reference"),
                "pngBytes": list(source),
            },
            "candidateSlots": candidates,
        }
        control.checkpoint("operational UI material construction completion")
        served_urls: set[str] = set()
        page_holder: list[Any] = []
        packet_delivered = False
        ready_confirmed = False
        submit_confirmed = False

        def validate_source(source_value: object) -> None:
            control.checkpoint("operational host binding")
            if type(source_value) is not dict or not page_holder:
                raise C4Stage1ReviewPresenterError(
                    "The operational probe host source is invalid"
                )
            if (
                source_value.get("page") is not page_holder[0]
                or getattr(source_value.get("frame"), "url", None) != _INDEX_URL
            ):
                raise C4Stage1ReviewPresenterError(
                    "The operational probe host source is unexpected"
                )

        def get_packet(source_value: object, request: object) -> dict[str, Any]:
            nonlocal packet_delivered
            validate_source(source_value)
            if packet_delivered or request != {
                "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                "serviceSchemaRevision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
                "ledgerSchemaRevision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
            }:
                raise C4Stage1ReviewPresenterError(
                    "The operational probe packet request is invalid"
                )
            packet_delivered = True
            return packet

        def mark_ready(source_value: object, request: object) -> dict[str, bool]:
            nonlocal ready_confirmed
            validate_source(source_value)
            if (
                not packet_delivered
                or ready_confirmed
                or request
                != {
                    "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                    "sessionToken": session_token,
                }
            ):
                raise C4Stage1ReviewPresenterError(
                    "The operational probe readiness is invalid"
                )
            ready_confirmed = True
            return {"ready": True}

        def submit(source_value: object, value: object) -> dict[str, bool]:
            nonlocal submit_confirmed
            validate_source(source_value)
            value = _strict_record(
                value,
                {
                    "ipcProtocol",
                    "sessionToken",
                    "reviewerPseudonym",
                    "slotJudgments",
                    "pairJudgments",
                },
                label="Operational probe submission",
            )
            slots = value["slotJudgments"]
            pair = value["pairJudgments"]
            if (
                submit_confirmed
                or not ready_confirmed
                or value["ipcProtocol"] != C4_STAGE1_REVIEW_IPC_PROTOCOL
                or value["sessionToken"] != session_token
                or value["reviewerPseudonym"] != "operational-probe"
                or type(slots) is not list
                or len(slots) != 2
                or {item.get("slot") for item in slots if type(item) is dict}
                != {item["slot"] for item in candidates}
                or any(
                    type(item) is not dict
                    or set(item) != {"slot", "judgments"}
                    or type(item["judgments"]) is not dict
                    or set(item["judgments"]) != set(_OUTPUT_BOOLEAN_FIELDS)
                    or any(
                        type(flag) is not bool for flag in item["judgments"].values()
                    )
                    for item in slots
                )
                or type(pair) is not dict
                or set(pair) != set(_PAIR_BOOLEAN_FIELDS)
                or any(type(flag) is not bool for flag in pair.values())
            ):
                raise C4Stage1ReviewPresenterError(
                    "The operational probe submission is incomplete"
                )
            submit_confirmed = True
            return {"accepted": True}

        def reject_cancel(_source: object, _request: object) -> dict[str, bool]:
            raise C4Stage1ReviewPresenterError(
                "The operational probe unexpectedly cancelled"
            )

        def route_request(route: Any) -> None:
            control.checkpoint("operational route request")
            url = getattr(getattr(route, "request", None), "url", None)
            matching = [
                name for name, expected in _ASSET_URLS.items() if url == expected
            ]
            if len(matching) != 1 or url in served_urls:
                route.abort("blockedbyclient")
                raise C4Stage1ReviewPresenterError(
                    "The operational UI probe requested an unpinned resource"
                )
            name = matching[0]
            served_urls.add(url)
            headers = {
                "Cache-Control": "no-store",
                "Content-Length": str(len(assets[name])),
                "Content-Type": _MEDIA_TYPES[name],
                "X-Content-Type-Options": "nosniff",
            }
            if name == "index.html":
                headers["Content-Security-Policy"] = (
                    self._runtime_manifest.content_security_policy
                )
            route.fulfill(status=200, headers=headers, body=assets[name])

        control.checkpoint("operational UI context configuration start")
        browser_context.set_default_timeout(
            control.remaining_ms("operational UI default timeout")
        )
        browser_context.route("**/*", route_request)
        page = (
            browser_context.pages[0]
            if browser_context.pages
            else browser_context.new_page()
        )
        page_holder.append(page)
        browser_context.expose_binding(_GET_PACKET_BINDING, get_packet)
        browser_context.expose_binding(_MARK_READY_BINDING, mark_ready)
        browser_context.expose_binding(_SUBMIT_BINDING, submit)
        browser_context.expose_binding(_CANCEL_BINDING, reject_cancel)
        browser_context.add_init_script(_host_init_script())
        control.checkpoint("operational UI context configuration completion")
        page.goto(
            _INDEX_URL,
            wait_until="domcontentloaded",
            timeout=control.remaining_ms("operational UI navigation timeout"),
        )
        control.checkpoint("operational UI navigation completion")
        self._wait_for_function_bounded(
            page,
            "() => window.__reiReviewHostState && window.__reiReviewHostState.uiReady",
            control,
            label="operational UI readiness",
        )
        control.checkpoint("operational UI form fill start")
        page.locator("#reviewer-pseudonym").fill("operational-probe")
        for output_index in range(2):
            for field in _OUTPUT_BOOLEAN_FIELDS:
                page.locator(
                    f'input[name="outputs.{output_index}.{field}"][value="false"]'
                ).check()
        for field in _PAIR_BOOLEAN_FIELDS:
            page.locator(f'input[name="pair.{field}"][value="false"]').check()
        control.checkpoint("operational UI form fill completion")
        page.locator("#submit-review").click()
        control.checkpoint("operational UI submit click completion")
        self._wait_for_function_bounded(
            page,
            "() => window.__reiReviewHostState && "
            "window.__reiReviewHostState.submitted && "
            "window.__reiReviewHostState.terminal",
            control,
            label="operational UI terminal submission",
        )
        if (
            served_urls != set(_ASSET_URLS.values())
            or not packet_delivered
            or not ready_confirmed
            or not submit_confirmed
        ):
            raise C4Stage1ReviewPresenterError(
                "The operational UI probe did not complete its submission contract"
            )

    def verify_runtime_pin(
        self,
        expected: C4Stage1ReviewBrowserRuntimePin,
        *,
        control: _DeadlineControl | None = None,
    ) -> bool:
        owns_control = control is None
        control = control or self._new_deadline_control(self._timeout_ms)
        manager: ContextManager[Any] | None = None
        try:
            control.checkpoint("browser runtime pin validation start")
            expected = C4Stage1ReviewBrowserRuntimePin.model_validate(
                expected.model_dump(mode="python", round_trip=True)
            )
            external_runtime = self._verify_external_runtime(
                control, expected=expected.external_runtime
            )
            self._resolve_exact_runtime_identity(control)
            manager = self._playwright_factory()
            control.checkpoint("runtime-pin Playwright manager creation")
            playwright = manager.__enter__()
            control.checkpoint("runtime-pin Playwright driver entry")
            actual = self._capture_executable_pin(
                playwright.chromium, control, external_runtime
            )
            self._exit_playwright_manager(manager, control, label="runtime pin")
            manager = None
            self._verify_external_runtime(control, expected=expected.external_runtime)
            if actual != expected or self._browser_runtime_pin != expected:
                raise C4Stage1ReviewPresenterError(
                    "The browser runtime changed after the operational probe"
                )
            control.checkpoint("browser runtime pin validation completion")
            return True
        finally:
            if manager is not None:
                try:
                    self._exit_playwright_manager(manager, control, label="runtime pin")
                except Exception:
                    control.request_hard_termination("runtime-pin-driver-exit-failed")
            if owns_control:
                control.finish()

    def cancel_active(self) -> bool:
        """Signal only; the owner thread closes sync Playwright objects."""

        with self._lock:
            control = self._active_control
            active = self._active
        if control is None:
            return active
        control.cancelled.set()
        return True

    def __call__(
        self,
        context: C4Stage1DisplayContext,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
        *,
        cancellation_event: threading.Event | None = None,
    ) -> bool:
        """Present one review; return true only for a complete explicit submission."""

        control = self._new_deadline_control(
            self._timeout_ms,
            cancellation_event=cancellation_event,
        )
        try:
            return self._present_with_control(
                control,
                context,
                source_png_bytes,
                outputs,
            )
        finally:
            control.finish()

    def _present_with_control(
        self,
        control: _DeadlineControl,
        context: C4Stage1DisplayContext,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
    ) -> bool:
        registered = False
        session_dir: Path | None = None
        pending: bytes | None = None
        submitted_at: datetime | None = None
        cancelled = False
        try:
            control.checkpoint("display input validation start")
            context = self._validate_inputs(context, source_png_bytes, outputs)
            control.checkpoint("display input validation completion")
            with self._lock:
                if self._active:
                    raise C4Stage1ReviewPresenterError(
                        "A C4 Stage 1 presenter session is already active"
                    )
                if context.context_id in self._attempted_context_ids:
                    raise C4Stage1ReviewPresenterError(
                        "This C4 Stage 1 display context was already attempted"
                    )
                self._active = True
                self._active_control = control
                self._attempted_context_ids.add(context.context_id)
                registered = True
            control.checkpoint("review runtime manifest verification start")
            manifest = verify_c4_stage1_review_runtime_manifest(
                self._repository_root, self._runtime_manifest
            )
            control.checkpoint("review runtime manifest verification completion")
            self._validate_context_runtime_binding(context, manifest)
            control.checkpoint("display runtime binding completion")
            assets = self._read_exact_assets(manifest, control=control)
            self.verify_runtime_pin(self.browser_runtime_pin, control=control)
            control.checkpoint("display profile creation start")
            session_dir = self._create_external_session_dir()
            control.checkpoint("display profile creation completion")
            pending, cancelled, submitted_at = self._run_browser(
                context=context,
                source_png_bytes=source_png_bytes,
                outputs=outputs,
                assets=assets,
                session_dir=session_dir,
                control=control,
            )
        except C4Stage1ReviewPresenterError:
            raise
        except Exception as exc:
            raise C4Stage1ReviewPresenterError(
                "The C4 Stage 1 offline review failed closed"
            ) from exc
        finally:
            cleanup_failure: Exception | None = None
            if session_dir is not None:
                try:
                    self._remove_profile_under_control(
                        session_dir, control, label="display"
                    )
                except Exception as exc:  # pragma: no cover - platform lock failure
                    cleanup_failure = exc
                    control.request_hard_termination("display-profile-cleanup-failed")
            if registered:
                with self._lock:
                    self._active = False
                    if self._active_control is control:
                        self._active_control = None
            if cleanup_failure is not None:
                if isinstance(
                    cleanup_failure, C4Stage1ReviewPresenterError
                ) and "absolute C4 Stage 1 presentation deadline" in str(
                    cleanup_failure
                ):
                    raise cleanup_failure
                raise C4Stage1ReviewPresenterError(
                    "The isolated C4 Stage 1 browser session could not be removed"
                ) from cleanup_failure
        self._verify_external_runtime(
            control, expected=self.browser_runtime_pin.external_runtime
        )
        if cancelled:
            control.checkpoint("cancelled display completion")
            return False
        if pending is None or submitted_at is None:
            raise C4Stage1ReviewPresenterError(
                "The C4 Stage 1 review ended without a complete submission"
            )
        with self._lock:
            if context.context_id in self._submissions:
                raise C4Stage1ReviewPresenterError(
                    "A C4 Stage 1 submission already exists for this context"
                )
            self._submissions[context.context_id] = pending, submitted_at
        control.checkpoint("sealed display completion")
        return True

    def present(
        self,
        context: C4Stage1DisplayContext,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
        *,
        cancellation_event: threading.Event | None = None,
    ) -> bool:
        """Delegate the service presenter port to the callable implementation."""

        return self(
            context,
            source_png_bytes,
            outputs,
            cancellation_event=cancellation_event,
        )

    def peek_submission(self, context_id: str) -> tuple[bytes, datetime]:
        """Return one canonical submission without consuming it."""

        context_id = _strict_text(context_id, label="context_id", maximum=256)
        with self._lock:
            try:
                return self._submissions[context_id]
            except KeyError:
                raise C4Stage1ReviewPresenterError(
                    "No unretrieved C4 Stage 1 submission exists for this context"
                ) from None

    def discard_submission(
        self,
        context_id: str,
        *,
        expected_submission: bytes,
        expected_submitted_at: datetime,
    ) -> bool:
        """Forget only the exact submission already committed by the service."""

        context_id = _strict_text(context_id, label="context_id", maximum=256)
        with self._lock:
            current = self._submissions.get(context_id)
            if current is None:
                return False
            if current != (expected_submission, expected_submitted_at):
                raise C4Stage1ReviewPresenterError(
                    "The retained C4 Stage 1 submission changed before discard"
                )
            del self._submissions[context_id]
            return True

    def take_submission(self, context_id: str) -> tuple[bytes, datetime]:
        """Compatibility wrapper for non-service presenter tests."""

        value, submitted_at = self.peek_submission(context_id)
        if not self.discard_submission(
            context_id,
            expected_submission=value,
            expected_submitted_at=submitted_at,
        ):
            raise C4Stage1ReviewPresenterError(
                "No unretrieved C4 Stage 1 submission exists for this context"
            )
        return value, submitted_at

    @staticmethod
    def _validate_inputs(
        context: C4Stage1DisplayContext,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
    ) -> C4Stage1DisplayContext:
        if not isinstance(context, C4Stage1DisplayContext):
            raise TypeError("context must be a C4Stage1DisplayContext")
        try:
            context = C4Stage1DisplayContext.model_validate(
                context.model_dump(mode="python", round_trip=True)
            )
            build_c4_stage1_display_port_acknowledgement(
                context,
                source_png_bytes=source_png_bytes,
                outputs=outputs,
            )
        except (TypeError, ValueError) as exc:
            raise C4Stage1ReviewPresenterError(
                "C4 Stage 1 presenter inputs differ from the display context"
            ) from exc
        return context

    @staticmethod
    def _validate_context_runtime_binding(
        context: C4Stage1DisplayContext,
        manifest: C4Stage1ReviewRuntimeManifest,
    ) -> None:
        if (
            context.ui_implementation_id != manifest.presenter_implementation_id
            or context.ui_revision != manifest.presenter_revision
            or not hmac.compare_digest(
                context.ui_bundle_sha256, manifest.ui_bundle_sha256
            )
            or not hmac.compare_digest(
                context.content_security_policy_sha256,
                C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256,
            )
            or not hmac.compare_digest(
                context.content_security_policy_sha256,
                manifest.content_security_policy_sha256,
            )
        ):
            raise C4Stage1ReviewPresenterError(
                "C4 Stage 1 display context differs from the pinned review runtime"
            )

    def _read_exact_assets(
        self,
        manifest: C4Stage1ReviewRuntimeManifest,
        *,
        control: _DeadlineControl,
    ) -> dict[str, bytes]:
        values: dict[str, bytes] = {}
        for asset in manifest.assets:
            control.checkpoint("review UI asset capture start")
            relative = Path(asset.relative_path)
            path = self._repository_root / relative
            try:
                path_lstat = os.lstat(path)
                if (
                    not stat.S_ISREG(path_lstat.st_mode)
                    or stat.S_ISLNK(path_lstat.st_mode)
                    or _is_reparse_point(path_lstat)
                    or path_lstat.st_nlink != 1
                ):
                    raise OSError
                value = path.read_bytes()
                final_stat = os.stat(path)
            except OSError as exc:
                raise C4Stage1ReviewPresenterError(
                    "A pinned C4 Stage 1 review asset is not an ordinary file"
                ) from exc
            if (
                not os.path.samestat(path_lstat, final_stat)
                or len(value) != asset.byte_size
                or not hmac.compare_digest(_sha256(value), asset.sha256)
            ):
                raise C4Stage1ReviewPresenterError(
                    "A pinned C4 Stage 1 review asset changed before browser launch"
                )
            values[relative.name] = value
            control.checkpoint("review UI asset capture completion")
        if set(values) != set(_ASSET_URLS):
            raise C4Stage1ReviewPresenterError(
                "The C4 Stage 1 review asset inventory is incomplete"
            )
        return values

    def _create_external_session_dir(self) -> Path:
        try:
            raw_parent = self._user_data_dir.parent
            parent_stat = os.lstat(raw_parent)
            parent = raw_parent.resolve(strict=True)
        except OSError as exc:
            raise C4Stage1ReviewPresenterError(
                "The browser session parent must be an existing directory"
            ) from exc
        if (
            not stat.S_ISDIR(parent_stat.st_mode)
            or stat.S_ISLNK(parent_stat.st_mode)
            or _is_reparse_point(parent_stat)
        ):
            raise C4Stage1ReviewPresenterError(
                "The browser session parent must be an ordinary directory"
            )
        target = (parent / self._user_data_dir.name).resolve(strict=False)
        if target == self._repository_root or target.is_relative_to(
            self._repository_root
        ):
            raise C4Stage1ReviewPresenterError(
                "The browser user-data directory must be external to the repository"
            )
        sealed_roots = (
            self._runtime_provenance_root,
            self._external_runtime_root,
            self._external_browser_root,
        )
        if any(
            target == root or target.is_relative_to(root) or root.is_relative_to(target)
            for root in sealed_roots
        ):
            raise C4Stage1ReviewPresenterError(
                "The browser user-data directory must be disjoint from sealed runtimes"
            )
        if target.exists() or target.is_symlink():
            raise C4Stage1ReviewPresenterError(
                "The browser user-data directory must be fresh"
            )
        try:
            os.mkdir(target, mode=0o700)
            created = os.lstat(target)
        except OSError as exc:
            raise C4Stage1ReviewPresenterError(
                "The isolated browser user-data directory could not be created"
            ) from exc
        if (
            not stat.S_ISDIR(created.st_mode)
            or stat.S_ISLNK(created.st_mode)
            or _is_reparse_point(created)
        ):
            raise C4Stage1ReviewPresenterError(
                "The isolated browser user-data path is not an ordinary directory"
            )
        return target

    def _remove_external_session_dir(self, session_dir: Path) -> None:
        target = session_dir.resolve(strict=True)
        if (
            target != session_dir
            or target == self._repository_root
            or target.is_relative_to(self._repository_root)
        ):
            raise C4Stage1ReviewPresenterError(
                "Refusing to remove an unexpected browser user-data directory"
            )
        shutil.rmtree(target)
        if target.exists():
            raise C4Stage1ReviewPresenterError(
                "The browser user-data directory still exists after cleanup"
            )

    def _run_browser(
        self,
        *,
        context: C4Stage1DisplayContext,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
        assets: dict[str, bytes],
        session_dir: Path,
        control: _DeadlineControl,
    ) -> tuple[bytes | None, bool, datetime | None]:
        state = _BrowserSessionState()
        control.checkpoint("blinded browser material construction start")
        blinded = self._build_blinded_presentation(
            source_png_bytes=source_png_bytes,
            outputs=outputs,
        )
        packet = blinded.browser_packet()
        control.checkpoint("blinded browser material construction completion")
        served_urls: set[str] = set()
        page_holder: list[Any] = []

        def fail(message: str) -> None:
            state.failure = state.failure or message

        def validate_source(source: object) -> None:
            control.checkpoint("review host binding")
            if type(source) is not dict or not page_holder:
                raise C4Stage1ReviewPresenterError(
                    "The review host binding source is invalid"
                )
            page = source.get("page")
            frame = source.get("frame")
            if (
                page is not page_holder[0]
                or getattr(page, "url", None) != _INDEX_URL
                or getattr(frame, "url", None) != _INDEX_URL
            ):
                raise C4Stage1ReviewPresenterError(
                    "The review host binding came from an unexpected page"
                )

        def guarded(
            callback: Callable[[object], Any],
        ) -> Callable[[object, object], Any]:
            def invoke(source: object, payload: object) -> Any:
                try:
                    validate_source(source)
                    if state.failure is not None or state.terminal_kind is not None:
                        raise C4Stage1ReviewPresenterError(
                            state.failure
                            or "The review host session is already terminal"
                        )
                    return callback(payload)
                except Exception as exc:
                    fail(str(exc) or "The review host binding failed")
                    raise

            return invoke

        @guarded
        def get_packet(request: object) -> dict[str, Any]:
            request = _strict_record(
                request,
                {"ipcProtocol", "serviceSchemaRevision", "ledgerSchemaRevision"},
                label="Review packet request",
            )
            if (
                request
                != {
                    "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                    "serviceSchemaRevision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
                    "ledgerSchemaRevision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
                }
                or state.packet_delivered
            ):
                raise C4Stage1ReviewPresenterError(
                    "The review packet request differs from the pinned IPC"
                )
            state.packet_delivered = True
            return packet

        @guarded
        def mark_ready(request: object) -> dict[str, bool]:
            request = _strict_record(
                request,
                {"ipcProtocol", "sessionToken"},
                label="Review-ready request",
            )
            if (
                not state.packet_delivered
                or state.ui_ready
                or request
                != {
                    "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                    "sessionToken": blinded.session_token,
                }
            ):
                raise C4Stage1ReviewPresenterError(
                    "The visible review UI was not initialized exactly once"
                )
            state.ui_ready = True
            return {"ready": True}

        @guarded
        def submit_review(submission: object) -> dict[str, bool]:
            if not state.ui_ready:
                raise C4Stage1ReviewPresenterError(
                    "The review UI was not initialized before submission"
                )
            state.pending_submission = self._validate_submission(
                context, blinded, submission
            )
            submitted_at = self._utc_clock()
            if (
                not isinstance(submitted_at, datetime)
                or submitted_at.tzinfo is None
                or submitted_at.utcoffset() is None
            ):
                raise C4Stage1ReviewPresenterError(
                    "The presenter submission clock is invalid"
                )
            state.submitted_at = submitted_at.astimezone(timezone.utc)
            state.terminal_kind = "submitted"
            return {"accepted": True}

        @guarded
        def cancel_review(request: object) -> dict[str, bool]:
            request = _strict_record(
                request,
                {
                    "ipcProtocol",
                    "sessionToken",
                },
                label="Review cancellation",
            )
            if not state.ui_ready or request != {
                "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                "sessionToken": blinded.session_token,
            }:
                raise C4Stage1ReviewPresenterError(
                    "The review cancellation differs from the pinned session"
                )
            state.terminal_kind = "cancelled"
            return {"cancelled": True}

        def route_request(route: Any) -> None:
            control.checkpoint("review route request")
            url = getattr(getattr(route, "request", None), "url", None)
            matching = [
                name for name, expected in _ASSET_URLS.items() if url == expected
            ]
            if len(matching) != 1 or url in served_urls:
                state.blocked_request_url = str(url)
                fail("The offline browser requested a non-pinned resource")
                route.abort("blockedbyclient")
                return
            name = matching[0]
            served_urls.add(url)
            headers = {
                "Cache-Control": "no-store",
                "Content-Length": str(len(assets[name])),
                "Content-Type": _MEDIA_TYPES[name],
                "X-Content-Type-Options": "nosniff",
            }
            if name == "index.html":
                headers["Content-Security-Policy"] = (
                    self._runtime_manifest.content_security_policy
                )
            route.fulfill(status=200, headers=headers, body=assets[name])

        browser_context: Any | None = None
        manager: ContextManager[Any] | None = None
        try:
            control.checkpoint("display Playwright manager creation start")
            manager = self._playwright_factory()
            control.checkpoint("display Playwright manager creation completion")
            control.checkpoint("display Playwright driver entry start")
            playwright = manager.__enter__()
            control.checkpoint("display Playwright driver entry completion")
            if self._capture_executable_pin(
                playwright.chromium,
                control,
                self.browser_runtime_pin.external_runtime,
            ) != (self.browser_runtime_pin):
                raise C4Stage1ReviewPresenterError(
                    "The browser executable changed immediately before launch"
                )
            control.checkpoint("display browser launch start")
            browser_context = playwright.chromium.launch_persistent_context(
                str(session_dir),
                headless=False,
                offline=True,
                accept_downloads=False,
                service_workers="block",
                timeout=control.remaining_ms("display browser launch timeout"),
                args=list(_NO_PERSIST_BROWSER_ARGS),
            )
            control.checkpoint("display browser launch completion")
            browser_context.set_default_timeout(
                control.remaining_ms("display default timeout")
            )
            browser_context.set_offline(True)
            browser_context.route("**/*", route_request)
            page = (
                browser_context.pages[0]
                if browser_context.pages
                else browser_context.new_page()
            )
            page_holder.append(page)
            browser_context.expose_binding(_GET_PACKET_BINDING, get_packet)
            browser_context.expose_binding(_MARK_READY_BINDING, mark_ready)
            browser_context.expose_binding(_SUBMIT_BINDING, submit_review)
            browser_context.expose_binding(_CANCEL_BINDING, cancel_review)
            browser_context.add_init_script(_host_init_script())
            control.checkpoint("display browser configuration completion")
            page.goto(
                _INDEX_URL,
                wait_until="domcontentloaded",
                timeout=control.remaining_ms("display navigation timeout"),
            )
            control.checkpoint("display navigation completion")
            self._wait_for_function_bounded(
                page,
                "() => window.__reiReviewHostState && "
                "(window.__reiReviewHostState.uiReady || "
                "window.__reiReviewHostState.failed || "
                "window.__reiReviewHostState.terminal)",
                control,
                label="display UI readiness",
            )
            if (
                state.failure is not None
                or state.blocked_request_url is not None
                or served_urls != set(_ASSET_URLS.values())
                or not state.packet_delivered
                or not state.ui_ready
                or state.terminal_kind is not None
            ):
                raise C4Stage1ReviewPresenterError(
                    state.failure
                    or "The pinned review UI did not initialize completely"
                )
            self._wait_for_function_bounded(
                page,
                "() => window.__reiReviewHostState && "
                "window.__reiReviewHostState.terminal",
                control,
                label="display terminal action",
            )
            if state.terminal_kind == "submitted":
                if state.pending_submission is None or state.submitted_at is None:
                    raise C4Stage1ReviewPresenterError(
                        "The browser signalled terminal before submission binding confirmation"
                    )
            elif state.terminal_kind != "cancelled":
                raise C4Stage1ReviewPresenterError(
                    state.failure
                    or "The browser signalled terminal without a confirmed host binding"
                )
            self._close_browser_context(browser_context, control, label="headed review")
            browser_context = None
            self._exit_playwright_manager(manager, control, label="headed review")
            manager = None
        except C4Stage1ReviewPresenterError:
            raise
        except Exception as exc:
            raise C4Stage1ReviewPresenterError(
                state.failure or "The headed review browser closed or timed out"
            ) from exc
        finally:
            if browser_context is not None:
                try:
                    self._close_browser_context(
                        browser_context, control, label="headed review"
                    )
                except Exception:
                    fail("The headed review browser did not close cleanly")
                    control.request_hard_termination("headed-review-close-failed")
            if manager is not None:
                try:
                    self._exit_playwright_manager(
                        manager, control, label="headed review"
                    )
                except Exception:
                    fail("The headed review Playwright driver did not exit cleanly")
                    control.request_hard_termination("headed-review-driver-exit-failed")

        if (
            state.failure is not None
            or state.blocked_request_url is not None
            or served_urls != set(_ASSET_URLS.values())
        ):
            raise C4Stage1ReviewPresenterError(
                state.failure or "The browser escaped the pinned offline request set"
            )
        if state.terminal_kind == "cancelled" and state.pending_submission is None:
            return None, True, None
        if (
            state.terminal_kind != "submitted"
            or state.pending_submission is None
            or state.submitted_at is None
        ):
            raise C4Stage1ReviewPresenterError(
                "The review browser ended without one complete terminal action"
            )
        return state.pending_submission, False, state.submitted_at

    @staticmethod
    def _build_blinded_presentation(
        *,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
    ) -> _BlindedPresentation:
        secret = secrets.token_bytes(32)

        def opaque(prefix: str, label: bytes) -> str:
            return (
                prefix
                + hmac.new(
                    secret,
                    b"rei-c4-stage1-browser-blinding-v1\x00" + label,
                    hashlib.sha256,
                ).hexdigest()
            )

        source_slot = opaque("slot-", b"reference")
        source_blinded = _blind_png(
            source_png_bytes,
            nonce=hmac.new(secret, b"png\x00reference", hashlib.sha256).digest(),
        )
        candidates = [
            _BlindedCandidate(
                slot=opaque("slot-", f"candidate-{index}".encode("ascii")),
                context_index=index,
                instruction=output.instruction,
                png_bytes=_blind_png(
                    output.png_bytes,
                    nonce=hmac.new(
                        secret,
                        f"png\x00candidate-{index}".encode("ascii"),
                        hashlib.sha256,
                    ).digest(),
                ),
            )
            for index, output in enumerate(outputs)
        ]
        candidates.sort(key=lambda item: item.slot)
        return _BlindedPresentation(
            session_token=opaque("session-", b"presentation"),
            source_slot=source_slot,
            source_png_bytes=source_blinded,
            candidates=(candidates[0], candidates[1]),
        )

    @staticmethod
    def _validate_submission(
        context: C4Stage1DisplayContext,
        blinded: _BlindedPresentation,
        submission: object,
    ) -> bytes:
        submission = _strict_record(
            submission,
            {
                "ipcProtocol",
                "sessionToken",
                "reviewerPseudonym",
                "slotJudgments",
                "pairJudgments",
            },
            label="Review submission",
        )
        if (
            submission["ipcProtocol"] != C4_STAGE1_REVIEW_IPC_PROTOCOL
            or submission["sessionToken"] != blinded.session_token
        ):
            raise C4Stage1ReviewPresenterError(
                "Review submission differs from the displayed packet"
            )
        reviewer = _strict_text(
            submission["reviewerPseudonym"],
            label="reviewerPseudonym",
            maximum=200,
        )
        raw_outputs = submission["slotJudgments"]
        if type(raw_outputs) is not list or len(raw_outputs) != 2:
            raise C4Stage1ReviewPresenterError(
                "Review submission must contain exactly two outputs"
            )
        candidate_by_slot = {item.slot: item for item in blinded.candidates}
        judgments_by_index: dict[int, dict[str, Any]] = {}
        for displayed_index, raw in enumerate(raw_outputs):
            raw = _strict_record(
                raw,
                {"slot", "judgments"},
                label=f"Slot {displayed_index + 1} submission",
            )
            candidate = candidate_by_slot.get(raw["slot"])
            if candidate is None or candidate.context_index in judgments_by_index:
                raise C4Stage1ReviewPresenterError(
                    "Review submission contains an unknown or duplicate opaque slot"
                )
            judgments_by_index[candidate.context_index] = _strict_record(
                raw["judgments"],
                set(_OUTPUT_BOOLEAN_FIELDS),
                label=f"Slot {displayed_index + 1} judgments",
            )
        if set(judgments_by_index) != {0, 1}:
            raise C4Stage1ReviewPresenterError(
                "Review submission does not cover both opaque slots"
            )
        normalized_outputs: list[dict[str, Any]] = []
        for index, expected in enumerate(context.outputs):
            judgments = judgments_by_index[index]
            normalized_outputs.append(
                {
                    "blindCode": expected.blind_code,
                    "instructionSha256": expected.instruction_sha256,
                    "outputSha256": expected.output_sha256,
                    "judgments": {
                        field: _strict_bool(
                            judgments[field],
                            label=f"outputs.{index}.{field}",
                        )
                        for field in _OUTPUT_BOOLEAN_FIELDS
                    },
                }
            )
        pair = _strict_record(
            submission["pairJudgments"],
            set(_PAIR_BOOLEAN_FIELDS),
            label="Pair judgments",
        )
        fixed = {
            "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
            "serviceSchemaRevision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
            "ledgerSchemaRevision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
            "packetId": context.packet_id,
            "packetSha256": context.packet_sha256,
            "sourceImageSha256": context.source_image_sha256,
        }
        normalized = {
            **fixed,
            "reviewerPseudonym": reviewer,
            "outputs": normalized_outputs,
            "pairJudgments": {
                field: _strict_bool(pair[field], label=f"pair.{field}")
                for field in _PAIR_BOOLEAN_FIELDS
            },
        }
        value = canonical_json_bytes(normalized)
        if len(value) > _MAX_SUBMISSION_CANONICAL_BYTES:
            raise C4Stage1ReviewPresenterError(
                "The canonical review submission exceeds its byte bound"
            )
        return value


__all__ = [
    "C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION",
    "C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION",
    "C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION",
    "C4Stage1OfflineReviewPresenter",
    "C4Stage1ReviewBrowserRuntimePin",
    "C4Stage1ReviewExternalRuntimePin",
    "C4Stage1ReviewPresenterError",
    "C4Stage1ReviewSealedTreeIdentity",
]
