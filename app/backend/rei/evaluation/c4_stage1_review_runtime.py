"""Content-addressed runtime manifest for the C4 Stage 1 offline review UI.

The review presenter is executable evaluation evidence, not a loose web asset.
This module therefore inventories the complete three-file bundle, rejects any
missing, additional, linked, reparse-point, hard-linked or changed entry, and
binds the exact bytes to the presenter and host protocol revisions.  Capture
and verification are model-free and perform no network access.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    ArtifactRelativePath,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
)
from .c4_blind_review import (
    C4_OUTPUT_POSITIVE_FIELDS,
    C4_OUTPUT_UNCERTAINTY_FIELD,
    C4_PAIR_POSITIVE_FIELDS,
)


C4_STAGE1_REVIEW_RUNTIME_SCHEMA = "rei-c4-stage1-review-runtime-manifest-v1"
C4_STAGE1_REVIEW_UI_BUNDLE_SCHEMA = "rei-c4-stage1-review-ui-bundle-v1"
C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID = "rei-c4-stage1-offline-review-ui"
C4_STAGE1_REVIEW_PRESENTER_REVISION = "c4-stage1-review-ui-v1"
C4_STAGE1_REVIEW_IPC_PROTOCOL = "rei-c4-stage1-review-ipc-v1"
C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION = "rei-c4-stage1-review-service-v2"
C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION = "rei-c4-stage1-review-ledger-v2"
C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; base-uri 'none'; child-src 'none'; connect-src 'none'; "
    "font-src 'none'; form-action 'none'; frame-ancestors 'none'; img-src blob:; "
    "manifest-src 'none'; media-src 'none'; navigate-to 'none'; object-src 'none'; "
    "script-src 'self'; style-src 'self'; worker-src 'none'"
)
C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256 = (
    "e55e1752e12f1543790ec4ef4189a13e419fd152ca3572efccacd40dce7944ad"
)
C4_STAGE1_REVIEW_UI_BUNDLE_SHA256 = (
    "a6c0a268af2fe35ce9981518f9081a4ed852a93f0b3e45d61fae22c3b0e00b8f"
)

_REVIEW_UI_DIRECTORY = Path("app/backend/rei/evaluation/c4_stage1_review_ui")
_REVIEW_UI_ASSET_NAMES = ("index.html", "review.css", "review.js")
_MAX_ASSET_BYTES = 512 * 1024
_MAX_MANIFEST_CANONICAL_BYTES = 64 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

_OUTPUT_BOOLEAN_FIELDS = (
    *C4_OUTPUT_POSITIVE_FIELDS,
    C4_OUTPUT_UNCERTAINTY_FIELD,
)
_PAIR_BOOLEAN_FIELDS = C4_PAIR_POSITIVE_FIELDS
_ContentSecurityPolicy = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4096),
]
_FORBIDDEN_VISIBLE_IDENTITY_TOKENS = (
    "longcat",
    "omnigen",
    "meituan",
    "shitao",
    "provider",
    "model",
)
_FORBIDDEN_ACTIVE_NETWORK_TOKENS = (
    "http://",
    "https://",
    "fetch(",
    "fetch (",
    "xmlhttprequest",
    "websocket",
    "eventsource",
    "sendbeacon",
    "rtcpeerconnection",
    "importscripts",
    "localstorage",
    "sessionstorage",
    "indexeddb",
    "document.cookie",
    "window.open(",
)

# The revision is deliberately byte-pinned.  Changing any asset requires a new
# presenter revision and a corresponding pre-output screen commitment.
_EXPECTED_ASSET_RECORDS: tuple[tuple[str, str, int, str], ...] = (
    (
        "app/backend/rei/evaluation/c4_stage1_review_ui/index.html",
        "text/html; charset=utf-8",
        8235,
        "56f444301db1901c227b939cca0503f29b1848ee35bb2f3d7397bd87d3076e76",
    ),
    (
        "app/backend/rei/evaluation/c4_stage1_review_ui/review.css",
        "text/css; charset=utf-8",
        3539,
        "0f08b314970c8546655b6a9003e3c9c6a79c5d2517ee0b7cf7ebfa9dceb868a5",
    ),
    (
        "app/backend/rei/evaluation/c4_stage1_review_ui/review.js",
        "text/javascript; charset=utf-8",
        9908,
        "2d7115e0ea5ebdf1473c60de32c40069f02ad37195f90d6445f4d95baa049f5c",
    ),
)


class C4Stage1ReviewRuntimeError(ValueError):
    """The pinned offline review runtime is unavailable or differs from policy."""


class C4Stage1ReviewUiAsset(FrozenModel):
    """One exact ordinary-file entry in the offline review UI bundle."""

    relative_path: ArtifactRelativePath
    media_type: Literal[
        "text/html; charset=utf-8",
        "text/css; charset=utf-8",
        "text/javascript; charset=utf-8",
    ]
    byte_size: Annotated[int, Field(gt=0, le=_MAX_ASSET_BYTES)]
    sha256: HashDigest
    regular_file_verified: Literal[True] = True
    link_reparse_or_hardlink_present: Literal[False] = False
    exact_bytes_rehashed: Literal[True] = True

    @model_validator(mode="after")
    def validate_asset(self) -> Self:
        expected = {
            path: (media_type, byte_size, digest)
            for path, media_type, byte_size, digest in _EXPECTED_ASSET_RECORDS
        }.get(self.relative_path)
        if expected is None or expected != (
            self.media_type,
            self.byte_size,
            self.sha256,
        ):
            raise ValueError("C4 Stage 1 review UI asset differs from its revision")
        if (
            self.regular_file_verified is not True
            or self.link_reparse_or_hardlink_present is not False
            or self.exact_bytes_rehashed is not True
        ):
            raise ValueError("C4 Stage 1 review UI asset weakens exact inventory")
        return self


class C4Stage1ReviewRuntimeManifest(FrozenArtifactModel):
    """Exact offline presenter and host-protocol commitment for Stage 1 review."""

    schema_version: Literal["rei-c4-stage1-review-runtime-manifest-v1"] = (
        C4_STAGE1_REVIEW_RUNTIME_SCHEMA
    )
    runtime_manifest_id: NonEmptyId
    runtime_manifest_sha256: HashDigest
    assets: tuple[C4Stage1ReviewUiAsset, ...] = Field(min_length=3, max_length=3)
    ui_bundle_sha256: HashDigest
    content_security_policy: _ContentSecurityPolicy
    content_security_policy_sha256: HashDigest
    presenter_implementation_id: Literal["rei-c4-stage1-offline-review-ui"] = (
        C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
    )
    presenter_revision: Literal["c4-stage1-review-ui-v1"] = (
        C4_STAGE1_REVIEW_PRESENTER_REVISION
    )
    ipc_protocol: Literal["rei-c4-stage1-review-ipc-v1"] = C4_STAGE1_REVIEW_IPC_PROTOCOL
    service_schema_revision: Literal["rei-c4-stage1-review-service-v2"] = (
        C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION
    )
    ledger_schema_revision: Literal["rei-c4-stage1-review-ledger-v2"] = (
        C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION
    )
    output_boolean_fields: tuple[NonEmptyId, ...]
    pair_boolean_fields: tuple[NonEmptyId, ...]
    asset_count: Literal[3] = 3
    source_image_count: Literal[1] = 1
    blind_output_count: Literal[2] = 2
    required_review_boolean_count: Literal[16] = 16
    exact_asset_inventory_required: Literal[True] = True
    missing_or_additional_assets_allowed: Literal[False] = False
    links_reparse_points_or_hardlinks_allowed: Literal[False] = False
    offline_only: Literal[True] = True
    network_access_allowed: Literal[False] = False
    inline_executable_content_allowed: Literal[False] = False
    visible_provider_or_model_identity_tokens_present: Literal[False] = False
    exact_source_and_two_outputs_required: Literal[True] = True
    instruction_per_blind_output_required: Literal[True] = True
    review_boolean_defaults_allowed: Literal[False] = False
    explicit_submit_control_required: Literal[True] = True
    explicit_cancel_control_required: Literal[True] = True
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_runtime_manifest(self) -> Self:
        expected_assets = tuple(
            C4Stage1ReviewUiAsset(
                relative_path=path,
                media_type=media_type,
                byte_size=byte_size,
                sha256=digest,
                regular_file_verified=True,
                link_reparse_or_hardlink_present=False,
                exact_bytes_rehashed=True,
            )
            for path, media_type, byte_size, digest in _EXPECTED_ASSET_RECORDS
        )
        for asset in self.assets:
            C4Stage1ReviewUiAsset.model_validate(
                asset.model_dump(mode="python", round_trip=True)
            )
        if self.assets != expected_assets:
            raise ValueError("C4 Stage 1 review UI inventory is not exact")
        bundle_payload = {
            "schema_version": C4_STAGE1_REVIEW_UI_BUNDLE_SCHEMA,
            "assets": tuple(
                asset.model_dump(
                    mode="python",
                    round_trip=True,
                    exclude={
                        "regular_file_verified",
                        "link_reparse_or_hardlink_present",
                        "exact_bytes_rehashed",
                    },
                )
                for asset in self.assets
            ),
        }
        if (
            self.ui_bundle_sha256 != _canonical_sha256(bundle_payload)
            or self.ui_bundle_sha256 != C4_STAGE1_REVIEW_UI_BUNDLE_SHA256
        ):
            raise ValueError("C4 Stage 1 review UI bundle digest differs from assets")
        if (
            self.content_security_policy != C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY
            or self.content_security_policy_sha256
            != _bytes_sha256(self.content_security_policy.encode("utf-8"))
            or self.content_security_policy_sha256
            != C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256
        ):
            raise ValueError("C4 Stage 1 review CSP differs from the pinned bytes")
        if (
            self.presenter_implementation_id
            != C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
            or self.presenter_revision != C4_STAGE1_REVIEW_PRESENTER_REVISION
            or self.ipc_protocol != C4_STAGE1_REVIEW_IPC_PROTOCOL
            or self.service_schema_revision != C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION
            or self.ledger_schema_revision != C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION
            or self.output_boolean_fields != _OUTPUT_BOOLEAN_FIELDS
            or self.pair_boolean_fields != _PAIR_BOOLEAN_FIELDS
            or self.asset_count != 3
            or self.source_image_count != 1
            or self.blind_output_count != 2
            or self.required_review_boolean_count != 16
            or self.exact_asset_inventory_required is not True
            or self.missing_or_additional_assets_allowed is not False
            or self.links_reparse_points_or_hardlinks_allowed is not False
            or self.offline_only is not True
            or self.network_access_allowed is not False
            or self.inline_executable_content_allowed is not False
            or self.visible_provider_or_model_identity_tokens_present is not False
            or self.exact_source_and_two_outputs_required is not True
            or self.instruction_per_blind_output_required is not True
            or self.review_boolean_defaults_allowed is not False
            or self.explicit_submit_control_required is not True
            or self.explicit_cancel_control_required is not True
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_calls != 0
        ):
            raise ValueError("C4 Stage 1 review runtime weakens the frozen boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"runtime_manifest_id", "runtime_manifest_sha256"},
        )
        if self.runtime_manifest_id != content_id(
            "c4_s1_review_runtime", payload
        ) or self.runtime_manifest_sha256 != _canonical_sha256(payload):
            raise ValueError("C4 Stage 1 review runtime address differs from content")
        if len(canonical_json_bytes(self)) > _MAX_MANIFEST_CANONICAL_BYTES:
            raise ValueError("C4 Stage 1 review runtime manifest is too large")
        return self


class _ReviewHtmlContractParser(HTMLParser):
    """Small structural parser used only to fail closed on the frozen HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.csp_values: list[str] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.script_defer: list[bool] = []
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.radios: list[dict[str, str | None]] = []
        self.buttons: dict[str, dict[str, str | None]] = {}
        self.reviewer_input: dict[str, str | None] | None = None
        self.form_count = 0
        self.inline_script_present = False
        self._inside_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if len({name for name, _ in attrs}) != len(attrs):
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review HTML contains duplicate attributes"
            )
        values = dict(attrs)
        if "style" in values or any(name.startswith("on") for name in values):
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review HTML contains inline executable content"
            )
        element_id = values.get("id")
        if element_id is not None:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)
        if tag == "meta" and values.get("http-equiv", "").lower() == (
            "content-security-policy"
        ):
            content = values.get("content")
            if content is not None:
                self.csp_values.append(content)
        elif tag == "link" and values.get("rel") == "stylesheet":
            href = values.get("href")
            if href is not None:
                self.stylesheets.append(href)
        elif tag == "script":
            self._inside_script = True
            src = values.get("src")
            if src is not None:
                self.scripts.append(src)
                self.script_defer.append("defer" in values)
        elif tag == "input" and values.get("type") == "radio":
            self.radios.append(values)
        elif tag == "input" and values.get("id") == "reviewer-pseudonym":
            self.reviewer_input = values
        elif tag == "button" and element_id is not None:
            self.buttons[element_id] = values
        elif tag == "form":
            self.form_count += 1
            if "action" in values or "target" in values:
                raise C4Stage1ReviewRuntimeError(
                    "C4 Stage 1 review form cannot navigate"
                )
        if tag in {"a", "base", "embed", "iframe", "object"}:
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review HTML contains an external navigation surface"
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._inside_script = False

    def handle_data(self, data: str) -> None:
        if self._inside_script and data.strip():
            self.inline_script_present = True


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _bytes_sha256(canonical_json_bytes(value))


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE
    )


def _ordinary_directory(path: Path, *, label: str) -> os.stat_result:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeError(f"{label} is unavailable") from exc
    if _is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise C4Stage1ReviewRuntimeError(
            f"{label} must be an ordinary non-reparse directory"
        )
    return metadata


def _asset_directory(repository_root: Path) -> tuple[Path, os.stat_result]:
    if not repository_root.is_absolute():
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review repository root must be absolute"
        )
    _ordinary_directory(repository_root, label="C4 Stage 1 review repository root")
    current = repository_root
    metadata: os.stat_result | None = None
    for part in _REVIEW_UI_DIRECTORY.parts:
        current /= part
        metadata = _ordinary_directory(
            current, label="C4 Stage 1 review UI path ancestry"
        )
    if metadata is None:
        raise C4Stage1ReviewRuntimeError("C4 Stage 1 review UI path is empty")
    return current, metadata


def _stable_read_asset(path: Path) -> bytes:
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review UI asset is missing"
        ) from exc
    if (
        _is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 0 < before.st_size <= _MAX_ASSET_BYTES
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review UI assets must be ordinary non-linked files"
        )
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review UI asset cannot be opened safely"
        ) from exc
    value = bytearray()
    opened: os.stat_result | None = None
    final_handle: os.stat_result | None = None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or not os.path.samestat(before, opened)
            or before.st_size != opened.st_size
            or before.st_mtime_ns != opened.st_mtime_ns
            or before.st_ctime_ns != opened.st_ctime_ns
        ):
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review UI asset changed while opening"
            )
        while True:
            remaining = _MAX_ASSET_BYTES + 1 - len(value)
            chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, remaining))
            if not chunk:
                break
            value.extend(chunk)
            if len(value) > _MAX_ASSET_BYTES:
                raise C4Stage1ReviewRuntimeError(
                    "C4 Stage 1 review UI asset exceeds its byte bound"
                )
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review UI asset changed while reading"
        ) from exc
    if (
        opened is None
        or final_handle is None
        or _is_link_or_reparse(after)
        or opened.st_nlink != 1
        or final_handle.st_nlink != 1
        or after.st_nlink != 1
        or not stat.S_ISREG(after.st_mode)
        or not os.path.samestat(opened, final_handle)
        or not os.path.samestat(opened, after)
        or opened.st_mtime_ns != final_handle.st_mtime_ns
        or opened.st_mtime_ns != after.st_mtime_ns
        or opened.st_ctime_ns != final_handle.st_ctime_ns
        or opened.st_ctime_ns != after.st_ctime_ns
        or opened.st_size != len(value)
        or final_handle.st_size != len(value)
        or after.st_size != len(value)
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review UI asset changed while reading"
        )
    return bytes(value)


def _verify_html_contract(value: str) -> None:
    parser = _ReviewHtmlContractParser()
    try:
        parser.feed(value)
        parser.close()
    except C4Stage1ReviewRuntimeError:
        raise
    except Exception as exc:
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review HTML is not structurally valid"
        ) from exc
    required_ids = {
        "review-form",
        "source-image",
        "source-digest",
        "output-image-0",
        "output-image-1",
        "output-code-0",
        "output-code-1",
        "output-digest-0",
        "output-digest-1",
        "output-instruction-0",
        "output-instruction-1",
        "reviewer-pseudonym",
        "review-status",
        "cancel-review",
        "submit-review",
    }
    if (
        parser.csp_values != [C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY]
        or parser.stylesheets != ["review.css"]
        or parser.scripts != ["review.js"]
        or parser.script_defer != [True]
        or parser.inline_script_present
        or parser.form_count != 1
        or parser.duplicate_ids
        or not required_ids.issubset(parser.ids)
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review HTML differs from the offline presentation contract"
        )
    expected_groups = {
        *(
            f"outputs.{index}.{field}"
            for index in range(2)
            for field in _OUTPUT_BOOLEAN_FIELDS
        ),
        *(f"pair.{field}" for field in _PAIR_BOOLEAN_FIELDS),
    }
    actual_groups: dict[str, list[dict[str, str | None]]] = {}
    for attributes in parser.radios:
        name = attributes.get("name")
        if name is None:
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review contains an unnamed judgment"
            )
        actual_groups.setdefault(name, []).append(attributes)
    if set(actual_groups) != expected_groups:
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review boolean inventory differs from the rubric"
        )
    for controls in actual_groups.values():
        if (
            len(controls) != 2
            or {item.get("value") for item in controls} != {"true", "false"}
            or any("required" not in item or "checked" in item for item in controls)
        ):
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review booleans must be required and have no defaults"
            )
    reviewer = parser.reviewer_input
    if (
        reviewer is None
        or reviewer.get("name") != "reviewer_pseudonym"
        or reviewer.get("type") != "text"
        or "required" not in reviewer
        or "value" in reviewer
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review requires an unpopulated reviewer pseudonym"
        )
    submit = parser.buttons.get("submit-review")
    cancel = parser.buttons.get("cancel-review")
    if (
        submit is None
        or submit.get("type") != "submit"
        or cancel is None
        or cancel.get("type") != "button"
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review requires explicit submit and cancel controls"
        )


def _verify_script_contract(value: str) -> None:
    required_tokens = (
        C4_STAGE1_REVIEW_IPC_PROTOCOL,
        C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
        C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
        "window.reiReviewHost",
        "getReviewPacket",
        "submitReview",
        "cancelReview",
        'crypto.subtle.digest("SHA-256"',
        'new Blob([image.pngBytes], { type: "image/png" })',
        "outputs.length !== 2",
        "form.reportValidity()",
        *(_OUTPUT_BOOLEAN_FIELDS),
        *(_PAIR_BOOLEAN_FIELDS),
    )
    lowered = value.lower()
    if any(token not in value for token in required_tokens) or any(
        token in lowered for token in _FORBIDDEN_ACTIVE_NETWORK_TOKENS
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review script differs from the offline IPC contract"
        )
    if ".checked" in value:
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review script may not preselect a boolean"
        )


def _verify_asset_contract(values: dict[str, bytes]) -> None:
    decoded: dict[str, str] = {}
    for name, value in values.items():
        try:
            text = value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review UI assets must be UTF-8"
            ) from exc
        if text.startswith("\ufeff") or "\x00" in text:
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review UI asset encoding is not canonical"
            )
        lowered = text.lower()
        if any(token in lowered for token in _FORBIDDEN_VISIBLE_IDENTITY_TOKENS):
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review UI exposes a forbidden identity token"
            )
        if any(token in lowered for token in _FORBIDDEN_ACTIVE_NETWORK_TOKENS):
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review UI contains an active-network surface"
            )
        decoded[name] = text
    _verify_html_contract(decoded["index.html"])
    _verify_script_contract(decoded["review.js"])
    if (
        "url(" in decoded["review.css"].lower()
        or "@import" in decoded["review.css"].lower()
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review stylesheet contains an external resource surface"
        )


def _capture_assets(repository_root: Path) -> tuple[C4Stage1ReviewUiAsset, ...]:
    directory, initial_directory = _asset_directory(repository_root)
    try:
        with os.scandir(directory) as iterator:
            names = tuple(sorted(entry.name for entry in iterator))
    except OSError as exc:
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review UI inventory cannot be enumerated"
        ) from exc
    if names != tuple(sorted(_REVIEW_UI_ASSET_NAMES)):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review UI inventory has missing or additional entries"
        )
    values = {
        name: _stable_read_asset(directory / name) for name in _REVIEW_UI_ASSET_NAMES
    }
    final_directory = _ordinary_directory(
        directory, label="C4 Stage 1 review UI directory"
    )
    if (
        not os.path.samestat(initial_directory, final_directory)
        or initial_directory.st_mtime_ns != final_directory.st_mtime_ns
        or initial_directory.st_ctime_ns != final_directory.st_ctime_ns
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review UI directory changed during inventory"
        )
    _verify_asset_contract(values)
    assets: list[C4Stage1ReviewUiAsset] = []
    for path, media_type, expected_size, expected_sha256 in _EXPECTED_ASSET_RECORDS:
        name = Path(path).name
        value = values[name]
        actual_sha256 = _bytes_sha256(value)
        if len(value) != expected_size or not hmac.compare_digest(
            actual_sha256, expected_sha256
        ):
            raise C4Stage1ReviewRuntimeError(
                "C4 Stage 1 review UI asset differs from the pinned revision"
            )
        assets.append(
            C4Stage1ReviewUiAsset(
                relative_path=path,
                media_type=media_type,
                byte_size=len(value),
                sha256=actual_sha256,
                regular_file_verified=True,
                link_reparse_or_hardlink_present=False,
                exact_bytes_rehashed=True,
            )
        )
    return tuple(assets)


def capture_c4_stage1_review_runtime_manifest(
    repository_root: str | Path,
) -> C4Stage1ReviewRuntimeManifest:
    """Capture the exact pinned review UI and its offline host revisions."""

    assets = _capture_assets(Path(repository_root))
    base = {
        "schema_version": C4_STAGE1_REVIEW_RUNTIME_SCHEMA,
        "assets": assets,
        "ui_bundle_sha256": C4_STAGE1_REVIEW_UI_BUNDLE_SHA256,
        "content_security_policy": C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY,
        "content_security_policy_sha256": (
            C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256
        ),
        "presenter_implementation_id": (C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID),
        "presenter_revision": C4_STAGE1_REVIEW_PRESENTER_REVISION,
        "ipc_protocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
        "service_schema_revision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
        "ledger_schema_revision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
        "output_boolean_fields": _OUTPUT_BOOLEAN_FIELDS,
        "pair_boolean_fields": _PAIR_BOOLEAN_FIELDS,
        "asset_count": 3,
        "source_image_count": 1,
        "blind_output_count": 2,
        "required_review_boolean_count": 16,
        "exact_asset_inventory_required": True,
        "missing_or_additional_assets_allowed": False,
        "links_reparse_points_or_hardlinks_allowed": False,
        "offline_only": True,
        "network_access_allowed": False,
        "inline_executable_content_allowed": False,
        "visible_provider_or_model_identity_tokens_present": False,
        "exact_source_and_two_outputs_required": True,
        "instruction_per_blind_output_required": True,
        "review_boolean_defaults_allowed": False,
        "explicit_submit_control_required": True,
        "explicit_cancel_control_required": True,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_calls": 0,
    }
    runtime_manifest_id = content_id("c4_s1_review_runtime", base)
    runtime_manifest_sha256 = _canonical_sha256(base)
    return C4Stage1ReviewRuntimeManifest(
        runtime_manifest_id=runtime_manifest_id,
        runtime_manifest_sha256=runtime_manifest_sha256,
        **base,
    )


def verify_c4_stage1_review_runtime_manifest(
    repository_root: str | Path,
    expected: C4Stage1ReviewRuntimeManifest,
) -> C4Stage1ReviewRuntimeManifest:
    """Cold-validate ``expected`` and re-capture all exact runtime bytes."""

    if not isinstance(expected, C4Stage1ReviewRuntimeManifest):
        raise TypeError("expected must be a C4Stage1ReviewRuntimeManifest")
    try:
        expected = C4Stage1ReviewRuntimeManifest.model_validate(
            expected.model_dump(mode="python", round_trip=True)
        )
    except (TypeError, ValueError) as exc:
        raise C4Stage1ReviewRuntimeError(
            "Expected C4 Stage 1 review runtime manifest is invalid"
        ) from exc
    actual = capture_c4_stage1_review_runtime_manifest(repository_root)
    if actual != expected or not hmac.compare_digest(
        actual.runtime_manifest_sha256, expected.runtime_manifest_sha256
    ):
        raise C4Stage1ReviewRuntimeError(
            "C4 Stage 1 review runtime differs from the expected manifest"
        )
    return actual


__all__ = [
    "C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY",
    "C4_STAGE1_REVIEW_IPC_PROTOCOL",
    "C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION",
    "C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID",
    "C4_STAGE1_REVIEW_PRESENTER_REVISION",
    "C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION",
    "C4Stage1ReviewRuntimeError",
    "C4Stage1ReviewRuntimeManifest",
    "C4Stage1ReviewUiAsset",
    "capture_c4_stage1_review_runtime_manifest",
    "verify_c4_stage1_review_runtime_manifest",
]
