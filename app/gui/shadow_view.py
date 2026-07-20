"""Read-only presentation adapter for frozen text-shadow evidence.

The adapter has no runtime provider dependency.  It accepts only compiled-in
evidence IDs, verifies their closed inventories and privacy boundary, invokes a
bounded cold verifier lazily, and returns an allowlisted GUI projection.  It
never executes a REI processor, imports a concrete Gemma/Ollama provider, or
writes into an evidence root.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from types import MappingProxyType
from typing import Any, Callable, Mapping

from app.backend.rei.ids import content_id, sha256_hex


SHADOW_EVIDENCE_SCHEMA_VERSION = "rei-gemma4-shadow-evidence-view-v1"
SHADOW_EVIDENCE_INDEX_SCHEMA_VERSION = "rei-gemma4-shadow-evidence-index-v1"
DEFAULT_SHADOW_EVIDENCE_ID = "en1-runtime"
MAX_EVIDENCE_FILES = 128
MAX_EVIDENCE_TOTAL_BYTES = 1024 * 1024
MAX_EVIDENCE_FILE_BYTES = 128 * 1024
MAX_EXTERNAL_RECEIPT_BYTES = 4 * 1024

_SMOKE_MANIFEST_NAME = "smoke_evidence_manifest.json"
_S1R_RECEIPT_RELATIVE = PurePosixPath(
    "Docs/evals/research_reset_2026-07/"
    "gemma4_text_shadow_s1r_post_verification_receipt.json"
)
_EN1_RECEIPT_RELATIVE = PurePosixPath(
    "Docs/evals/research_reset_2026-07/"
    "gemma4_english_runtime_shadow_smoke_receipt.json"
)
_WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])"
)
_POSIX_LOCAL_PATH = re.compile(
    r"(?<![A-Za-z0-9])/(?:home|Users|tmp|private|var/tmp)/"
)
_FORBIDDEN_PRIVATE_KEYS = {
    "thinking",
    "raw_traceback",
    "raw_response",
    "raw_response_envelope",
    "native_truth",
    "evaluator_gold",
}
_ALLOWED_THINKING_KEYS = {
    "thinking_present",
    "thinking_sha256",
    "thinking_byte_count",
    "thinking_token_count",
    "thinking_channel",
    "thinking_content_persisted",
}
_CONCRETE_PROVIDER_MODULE_MARKERS = (
    ".providers.ollama",
    ".providers.gemma4_text_shadow",
)


class ShadowEvidenceIntegrityError(ValueError):
    """Frozen shadow evidence cannot be safely displayed."""


@dataclass(frozen=True, slots=True)
class _EvidenceRegistration:
    evidence_id: str
    relative_root: PurePosixPath
    label: str
    selector_label: str
    phase: str
    summary: str
    kind: str
    language: str
    run_id: str
    receipt_required: bool
    receipt_relative: PurePosixPath | None
    verification_profile: str
    manifest_id_prefix: str | None = None
    receipt_id_prefix: str | None = None


_EVIDENCE_REGISTRY: Mapping[str, _EvidenceRegistration] = MappingProxyType(
    {
        "en1-runtime": _EvidenceRegistration(
            evidence_id="en1-runtime",
            relative_root=PurePosixPath(
                "Docs/evals/semantic_lab_v1/"
                "en1-gemma4-text-shadow-2026-07-20"
            ),
            label="EN1 · current English runtime shadow",
            selector_label="EN1 · English runtime shadow",
            phase="EN1",
            summary=(
                "Current English local-model boundary: Emocio fully abstained, "
                "while Instinkt returned one bounded action-only hypothesis."
            ),
            kind="current_runtime",
            language="en",
            run_id="en1-gemma4-text-shadow-cycle",
            receipt_required=True,
            receipt_relative=_EN1_RECEIPT_RELATIVE,
            verification_profile="en1",
            manifest_id_prefix="gemma4_en_shadow_manifest",
            receipt_id_prefix="gemma4_english_shadow_receipt",
        ),
        "s1-partial": _EvidenceRegistration(
            evidence_id="s1-partial",
            relative_root=PurePosixPath(
                "Docs/evals/semantic_lab_v1/"
                "s1-gemma4-text-shadow-2026-07-19"
            ),
            label="S1 · historical Slovene partial failure",
            selector_label="S1 · historical Slovene partial failure",
            phase="S1",
            summary=(
                "The Emocio shadow failed within its bounded lane while the Instinkt "
                "shadow succeeded; the authoritative deterministic cycle succeeded "
                "in full."
            ),
            kind="historical",
            language="sl",
            run_id="s1-gemma4-text-shadow-cycle",
            receipt_required=False,
            receipt_relative=None,
            verification_profile="s1",
        ),
        "s1r-reconciled": _EvidenceRegistration(
            evidence_id="s1r-reconciled",
            relative_root=PurePosixPath(
                "Docs/evals/semantic_lab_v1/"
                "s1r-gemma4-text-shadow-2026-07-19"
            ),
            label="S1R · historical Slovene reconciled success",
            selector_label="S1R · historical Slovene reconciled success",
            phase="S1R",
            summary=(
                "Emocio fully abstained on epistemic grounds, while Instinkt returned "
                "one bounded action-only hypothesis."
            ),
            kind="historical",
            language="sl",
            run_id="s1-gemma4-text-shadow-cycle",
            receipt_required=True,
            receipt_relative=_S1R_RECEIPT_RELATIVE,
            verification_profile="s1",
        ),
    }
)
SHADOW_EVIDENCE_IDS = tuple(_EVIDENCE_REGISTRY)


@dataclass(frozen=True, slots=True)
class _EvidenceSnapshot:
    root: Path
    manifest: dict[str, Any]
    files: Mapping[str, bytes]
    inventory: tuple[tuple[str, str, int], ...]
    total_bytes: int


ColdVerifier = Callable[
    [Path, _EvidenceRegistration],
    tuple[Mapping[str, Any], Mapping[str, Any] | None],
]


def is_registered_shadow_evidence_id(value: str) -> bool:
    return type(value) is str and value in _EVIDENCE_REGISTRY


def _is_reparse_stat(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse_flag)


def _reject_reparse_components(path: Path, *, label: str) -> None:
    absolute = path.expanduser().absolute()
    for component in reversed((absolute, *absolute.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ShadowEvidenceIntegrityError(
                f"{label} path metadata is unavailable"
            ) from exc
        if _is_reparse_stat(metadata):
            raise ShadowEvidenceIntegrityError(
                f"{label} cannot traverse a link or reparse point"
            )


def _regular_directory(path: Path, *, label: str) -> Path:
    _reject_reparse_components(path, label=label)
    try:
        before = path.lstat()
        resolved = path.resolve(strict=True)
        after = resolved.lstat()
    except OSError as exc:
        raise ShadowEvidenceIntegrityError(f"{label} is unavailable") from exc
    if (
        _is_reparse_stat(before)
        or _is_reparse_stat(after)
        or not stat.S_ISDIR(before.st_mode)
        or not stat.S_ISDIR(after.st_mode)
        or not os.path.samestat(before, after)
    ):
        raise ShadowEvidenceIntegrityError(f"{label} must be one regular directory")
    return resolved


def _registered_root(repository_root: str | Path, registration: _EvidenceRegistration) -> Path:
    repository = _regular_directory(
        Path(repository_root), label="Shadow evidence repository root"
    )
    candidate = repository.joinpath(*registration.relative_root.parts)
    root = _regular_directory(candidate, label="Registered shadow evidence root")
    try:
        root.relative_to(repository)
    except ValueError as exc:
        raise ShadowEvidenceIntegrityError(
            "Registered shadow evidence escaped the repository root"
        ) from exc
    return root


def _registered_receipt(
    repository_root: str | Path,
    registration: _EvidenceRegistration,
) -> Path:
    if registration.receipt_relative is None:
        raise ShadowEvidenceIntegrityError(
            "Shadow evidence registration has no external receipt"
        )
    repository = _regular_directory(
        Path(repository_root), label="Shadow evidence repository root"
    )
    candidate = repository.joinpath(*registration.receipt_relative.parts)
    _reject_reparse_components(candidate, label="Shadow verification receipt")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(repository)
    except (OSError, ValueError) as exc:
        raise ShadowEvidenceIntegrityError(
            "Shadow verification receipt escaped the repository root"
        ) from exc
    return candidate


def _read_bounded(path: Path, *, maximum_bytes: int, label: str) -> bytes:
    _reject_reparse_components(path, label=label)
    descriptor: int | None = None
    try:
        before = path.lstat()
        if _is_reparse_stat(before) or not stat.S_ISREG(before.st_mode):
            raise ShadowEvidenceIntegrityError(
                f"{label} must be one regular non-link file"
            )
        if before.st_size < 0 or before.st_size > maximum_bytes:
            raise ShadowEvidenceIntegrityError(f"{label} exceeds its bounded size")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(before, opened)
            or opened.st_size != before.st_size
        ):
            raise ShadowEvidenceIntegrityError(f"{label} changed before opening")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            payload = handle.read(maximum_bytes + 1)
        after = path.lstat()
    except ShadowEvidenceIntegrityError:
        raise
    except OSError as exc:
        raise ShadowEvidenceIntegrityError(f"{label} could not be read safely") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (
        _is_reparse_stat(after)
        or not stat.S_ISREG(after.st_mode)
        or not os.path.samestat(opened, after)
        or len(payload) != opened.st_size
        or len(payload) > maximum_bytes
    ):
        raise ShadowEvidenceIntegrityError(f"{label} changed while being read")
    return payload


def _strict_json(payload: bytes, *, label: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ShadowEvidenceIntegrityError(
            f"{label} contains a non-finite JSON constant: {value}"
        )

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ShadowEvidenceIntegrityError(
                    f"{label} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except ShadowEvidenceIntegrityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShadowEvidenceIntegrityError(
            f"{label} is not strict UTF-8 JSON"
        ) from exc


def _walk_json(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _verify_private_content_absent(relative_path: str, payload: bytes) -> None:
    if not relative_path.endswith(".json"):
        return
    document = _strict_json(payload, label="Shadow evidence JSON")
    for value in _walk_json(document):
        if isinstance(value, dict):
            keys = {str(key) for key in value}
            if keys.intersection(_FORBIDDEN_PRIVATE_KEYS):
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence contains a forbidden private field"
                )
            unexpected_thinking = {
                key
                for key in keys
                if "thinking" in key.casefold() and key not in _ALLOWED_THINKING_KEYS
            }
            if unexpected_thinking:
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence contains an unreviewed thinking field"
                )
        elif isinstance(value, str):
            if _WINDOWS_ABSOLUTE_PATH.search(value) or _POSIX_LOCAL_PATH.search(value):
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence contains a local absolute path"
                )
            if "Traceback (most recent call last)" in value:
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence contains a raw traceback"
                )


def _scan_evidence_root(root: Path) -> tuple[dict[str, bytes], int]:
    pending = [root]
    paths: list[tuple[str, Path, int]] = []
    while pending:
        directory = pending.pop()
        _reject_reparse_components(directory, label="Shadow evidence directory")
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise ShadowEvidenceIntegrityError(
                "Shadow evidence directory cannot be enumerated"
            ) from exc
        for child in children:
            try:
                metadata = child.lstat()
            except OSError as exc:
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence entry metadata is unavailable"
                ) from exc
            if _is_reparse_stat(metadata):
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence cannot contain a link or reparse point"
                )
            if stat.S_ISDIR(metadata.st_mode):
                pending.append(child)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence can contain only regular files"
                )
            try:
                relative = child.relative_to(root).as_posix()
            except ValueError as exc:
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence entry escaped its registered root"
                ) from exc
            if metadata.st_size > MAX_EVIDENCE_FILE_BYTES:
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence file exceeds the per-file byte limit"
                )
            paths.append((relative, child, metadata.st_size))
            if len(paths) > MAX_EVIDENCE_FILES:
                raise ShadowEvidenceIntegrityError(
                    "Shadow evidence exceeds the file-count limit"
                )
    total_bytes = sum(size for _relative, _path, size in paths)
    if total_bytes > MAX_EVIDENCE_TOTAL_BYTES:
        raise ShadowEvidenceIntegrityError(
            "Shadow evidence exceeds the total byte limit"
        )
    files: dict[str, bytes] = {}
    for relative, path, _size in sorted(paths):
        payload = _read_bounded(
            path,
            maximum_bytes=MAX_EVIDENCE_FILE_BYTES,
            label="Shadow evidence file",
        )
        _verify_private_content_absent(relative, payload)
        files[relative] = payload
    return files, total_bytes


def _preflight_evidence_root(
    repository_root: str | Path,
    registration: _EvidenceRegistration,
) -> _EvidenceSnapshot:
    root = _registered_root(repository_root, registration)
    files, total_bytes = _scan_evidence_root(root)
    manifest_payload = files.get(_SMOKE_MANIFEST_NAME)
    if manifest_payload is None:
        raise ShadowEvidenceIntegrityError("Shadow evidence lacks its closed manifest")
    manifest = _strict_json(manifest_payload, label="Shadow evidence manifest")
    if not isinstance(manifest, dict):
        raise ShadowEvidenceIntegrityError("Shadow evidence manifest must be an object")
    if (
        manifest.get("phase") != registration.phase
        or manifest.get("no_authority") is not True
        or manifest.get("development_smoke_only") is not True
        or manifest.get("model_promoted") is not False
    ):
        raise ShadowEvidenceIntegrityError(
            "Shadow evidence manifest differs from the replay boundary"
        )
    records = manifest.get("artifacts")
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ShadowEvidenceIntegrityError("Shadow evidence inventory is invalid")
    expected_paths = set(files).difference({_SMOKE_MANIFEST_NAME})
    inventory: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for record in records:
        relative = record.get("relative_path")
        digest = record.get("content_sha256")
        size = record.get("size_bytes")
        no_authority = record.get("no_authority")
        if (
            not isinstance(relative, str)
            or not relative
            or "\\" in relative
            or PurePosixPath(relative).is_absolute()
            or ".." in PurePosixPath(relative).parts
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or type(size) is not int
            or size < 0
            or type(no_authority) is not bool
            or relative in seen
        ):
            raise ShadowEvidenceIntegrityError("Shadow evidence inventory is invalid")
        payload = files.get(relative)
        if payload is None:
            raise ShadowEvidenceIntegrityError(
                "Shadow evidence inventory references an absent file"
            )
        expected_no_authority = not relative.startswith("control/")
        if (
            len(payload) != size
            or hashlib.sha256(payload).hexdigest() != digest
            or no_authority is not expected_no_authority
        ):
            raise ShadowEvidenceIntegrityError(
                "Shadow evidence differs from its closed inventory"
            )
        seen.add(relative)
        inventory.append((relative, digest, size))
    if seen != expected_paths:
        raise ShadowEvidenceIntegrityError(
            "Shadow evidence root is not closed by its inventory"
        )
    return _EvidenceSnapshot(
        root=root,
        manifest=manifest,
        files=MappingProxyType(files),
        inventory=tuple(sorted(inventory)),
        total_bytes=total_bytes,
    )


def _preflight_external_receipt(
    repository_root: str | Path,
    registration: _EvidenceRegistration,
) -> tuple[dict[str, Any], bytes]:
    path = _registered_receipt(repository_root, registration)
    payload = _read_bounded(
        path,
        maximum_bytes=MAX_EXTERNAL_RECEIPT_BYTES,
        label="Shadow verification receipt",
    )
    assert registration.receipt_relative is not None
    _verify_private_content_absent(registration.receipt_relative.as_posix(), payload)
    receipt = _strict_json(payload, label="Shadow verification receipt")
    if not isinstance(receipt, dict):
        raise ShadowEvidenceIntegrityError(
            "Shadow verification receipt must be one JSON object"
        )
    return receipt, payload


def _concrete_provider_modules_loaded() -> tuple[str, ...]:
    import sys

    return tuple(
        sorted(
            name
            for name in sys.modules
            if any(marker in name.casefold() for marker in _CONCRETE_PROVIDER_MODULE_MARKERS)
        )
    )


def _committed_cold_verify(
    output_root: Path,
    registration: _EvidenceRegistration,
) -> tuple[Mapping[str, Any], Mapping[str, Any] | None]:
    """Invoke the frozen verifier only after bounded local preflight succeeds."""

    before = _concrete_provider_modules_loaded()
    try:
        if registration.verification_profile == "en1":
            manifest, receipt = _cold_verify_en1(output_root, registration)
        else:
            verifier = importlib.import_module(
                "scripts.run_gemma4_racio_text_shadow_smoke"
            )
            manifest = verifier._cold_verification_checks(output_root)
            receipt = None
            if registration.receipt_required:
                receipt = verifier._verify_cold_receipt(
                    output_root,
                    manifest=manifest,
                    receipt_path=verifier.S1R_POST_VERIFICATION_RECEIPT,
                )
    except Exception as exc:
        raise ShadowEvidenceIntegrityError(
            "Committed shadow evidence failed cold verification"
        ) from exc
    after = _concrete_provider_modules_loaded()
    if after != before:
        raise ShadowEvidenceIntegrityError(
            "Shadow evidence verification imported a concrete model provider"
        )
    if not isinstance(manifest, Mapping) or (
        receipt is not None and not isinstance(receipt, Mapping)
    ):
        raise ShadowEvidenceIntegrityError(
            "Committed shadow verifier returned an invalid receipt"
        )
    return manifest, receipt


def _repository_from_registered_root(
    output_root: Path,
    registration: _EvidenceRegistration,
) -> Path:
    repository = output_root
    for _part in registration.relative_root.parts:
        repository = repository.parent
    return repository


def _cold_verify_en1(
    output_root: Path,
    registration: _EvidenceRegistration,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Verify EN1 locally without importing a provider-bearing smoke runner."""

    manifest_payload = _read_bounded(
        output_root / _SMOKE_MANIFEST_NAME,
        maximum_bytes=MAX_EVIDENCE_FILE_BYTES,
        label="EN1 evidence manifest",
    )
    manifest = _strict_json(manifest_payload, label="EN1 evidence manifest")
    if not isinstance(manifest, dict):
        raise ShadowEvidenceIntegrityError("EN1 evidence manifest must be an object")
    manifest_base = {
        key: value
        for key, value in manifest.items()
        if key not in {"manifest_id", "manifest_sha256"}
    }
    manifest_payload_for_hash = {
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    }
    if (
        registration.manifest_id_prefix is None
        or manifest.get("manifest_id")
        != content_id(registration.manifest_id_prefix, manifest_base)
        or manifest.get("manifest_sha256") != sha256_hex(manifest_payload_for_hash)
    ):
        raise ShadowEvidenceIntegrityError(
            "EN1 manifest is not valid content-addressed evidence"
        )

    repository = _repository_from_registered_root(output_root, registration)
    receipt, _receipt_bytes = _preflight_external_receipt(repository, registration)
    receipt_base = {
        key: value
        for key, value in receipt.items()
        if key not in {"receipt_id", "receipt_sha256"}
    }
    receipt_payload_for_hash = {
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    }
    if (
        registration.receipt_id_prefix is None
        or receipt.get("receipt_id")
        != content_id(registration.receipt_id_prefix, receipt_base)
        or receipt.get("receipt_sha256") != sha256_hex(receipt_payload_for_hash)
        or receipt.get("manifest_id") != manifest.get("manifest_id")
        or receipt.get("manifest_sha256") != manifest.get("manifest_sha256")
        or receipt.get("execution_head") != manifest.get("execution_head")
        or receipt.get("evidence_root_integrity_status") != "succeeded"
        or receipt.get("receipt_status") != "succeeded"
        or receipt.get("no_authority") is not True
        or receipt.get("model_promoted") is not False
        or receipt.get("holdout") is not False
        or receipt.get("thinking_content_persisted") is not False
    ):
        raise ShadowEvidenceIntegrityError(
            "EN1 external receipt does not close the verified evidence"
        )
    return manifest, receipt


def _artifact_json(
    snapshot: _EvidenceSnapshot,
    relative_path: PurePosixPath,
    *,
    expected: type,
    required: bool = True,
) -> Any:
    portable = relative_path.as_posix()
    payload = snapshot.files.get(portable)
    if payload is None:
        if not required:
            return None
        raise ShadowEvidenceIntegrityError(
            "Verified shadow evidence lacks a required presentation artifact"
        )
    value = _strict_json(payload, label="Shadow presentation artifact")
    if not isinstance(value, expected):
        raise ShadowEvidenceIntegrityError(
            "Shadow presentation artifact has an invalid JSON shape"
        )
    return value


def _one_by_mind(items: list[Any], source_mind: str, *, label: str) -> dict[str, Any]:
    matches = tuple(
        item
        for item in items
        if isinstance(item, dict) and item.get("source_mind") == source_mind
    )
    if len(matches) != 1:
        raise ShadowEvidenceIntegrityError(f"{label} does not close source mind")
    return matches[0]


def _text_projection(value: Any) -> dict[str, str | None]:
    source = value if isinstance(value, dict) else {}
    canonical = source.get("canonical_sl")
    operational = source.get("operational_en")
    return {
        "canonical_sl": canonical if isinstance(canonical, str) else None,
        "operational_en": operational if isinstance(operational, str) else None,
    }


def _visible_input(packet: dict[str, Any]) -> dict[str, Any]:
    language = packet.get("language")
    if language == "en":
        observations: list[dict[str, Any]] = []
        for item in packet.get("visible_observations", []):
            if not isinstance(item, dict):
                raise ShadowEvidenceIntegrityError(
                    "Shadow packet observations are invalid"
                )
            model_text = item.get("text")
            if model_text is not None and not isinstance(model_text, str):
                raise ShadowEvidenceIntegrityError(
                    "English shadow observation text is invalid"
                )
            observations.append(
                {
                    "observation_id": item.get("observation_id"),
                    "model_text": model_text,
                    "channel": item.get("provenance"),
                    "provenance": item.get("provenance"),
                    "visibility": item.get("perception_status"),
                    "perception_status": item.get("perception_status"),
                    "signal_alias": item.get("signal_alias"),
                    "atomic_evidence_unit_id": item.get(
                        "atomic_evidence_unit_id"
                    ),
                }
            )
        public_options: list[dict[str, Any]] = []
        for item in packet.get("public_option_scope", []):
            if not isinstance(item, dict) or not isinstance(
                item.get("description"), str
            ):
                raise ShadowEvidenceIntegrityError(
                    "English shadow packet options are invalid"
                )
            public_options.append(
                {
                    "option_id": item.get("option_id"),
                    "model_text": item.get("description"),
                }
            )
        return {
            "language": "en",
            "observations": observations,
            "public_options": public_options,
            "uncertainty": packet.get("uncertainty"),
            "channel_quality": packet.get("channel_quality"),
            "degraded_observation_ids": list(
                packet.get("degraded_observation_ids", [])
            ),
            "omitted_observation_ids": list(
                packet.get("omitted_observation_ids", [])
            ),
            "presentation_mode": "english_only",
            "raw_details": packet,
        }

    observations: list[dict[str, Any]] = []
    for item in packet.get("visible_observations", []):
        if not isinstance(item, dict):
            raise ShadowEvidenceIntegrityError("Shadow packet observations are invalid")
        text = _text_projection(item.get("text"))
        observations.append(
            {
                "observation_id": item.get("observation_id"),
                "canonical_sl": text["canonical_sl"],
                "operational_en": text["operational_en"],
                "channel": item.get("provenance"),
                "provenance": item.get("provenance"),
                "visibility": item.get("perception_status"),
                "perception_status": item.get("perception_status"),
                "signal_alias": item.get("signal_alias"),
                "atomic_evidence_unit_id": item.get("atomic_evidence_unit_id"),
            }
        )
    public_options: list[dict[str, Any]] = []
    for item in packet.get("public_option_scope", []):
        if not isinstance(item, dict):
            raise ShadowEvidenceIntegrityError("Shadow packet options are invalid")
        text = _text_projection(item.get("text"))
        public_options.append(
            {
                "option_id": item.get("option_id"),
                "canonical_sl": text["canonical_sl"],
                "operational_en": text["operational_en"],
            }
        )
    return {
        "language": "sl",
        "observations": observations,
        "public_options": public_options,
        "channel_quality": packet.get("channel_quality"),
        "degraded_observation_ids": list(packet.get("degraded_observation_ids", [])),
        "omitted_observation_ids": list(packet.get("omitted_observation_ids", [])),
        "presentation_mode": packet.get("presentation_mode"),
        "raw_details": packet,
    }


def _authoritative_view(interpretation: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "succeeded",
        "action_tendency": interpretation.get("inferred_action_tendency"),
        "inferred_option_id": interpretation.get("inferred_option_id"),
        "motive_summary": interpretation.get("inferred_motive"),
        "confidence": interpretation.get("confidence"),
        "interpretation_id": interpretation.get("interpretation_id"),
        "supporting_observation_ids": list(
            interpretation.get("supporting_observation_ids", [])
        ),
        "raw_details": interpretation,
    }


def _presentation_shape(
    status: Any,
    structured: Mapping[str, Any] | None,
) -> str:
    if status == "failed":
        return "failed"
    if status == "not_attempted":
        return "not_attempted"
    if structured is None:
        raise ShadowEvidenceIntegrityError(
            "Successful shadow result lacks its accepted interpretation"
        )
    actions = structured.get("action_hypotheses", [])
    option = structured.get("option_inference")
    motives = structured.get("motive_hypotheses", [])
    if not actions and option is None and not motives:
        return "full_abstention"
    if actions and option is None and not motives:
        return "action_only"
    return "bounded_claims"


def _shadow_view(
    result: dict[str, Any],
    interpretation: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    structured = None
    if interpretation is not None:
        candidate = interpretation.get("structured_output")
        if not isinstance(candidate, dict):
            raise ShadowEvidenceIntegrityError(
                "Shadow interpretation lacks its structured output"
            )
        structured = candidate
    status = result.get("status")
    shape = _presentation_shape(status, structured)
    failure = None
    if status == "failed":
        failure = {
            "stage": result.get("failure_stage"),
            "code": result.get("failure_code"),
            "summary": result.get("failure_summary"),
        }
    uncertainty = (
        {}
        if structured is None
        else dict(structured.get("racio_reported_uncertainty", {}))
    )
    accepted = status == "succeeded" and interpretation is not None
    return shape, {
        "status": status,
        "no_authority": result.get("no_authority"),
        "action_hypotheses": (
            [] if structured is None else list(structured.get("action_hypotheses", []))
        ),
        "option_inference": (
            None if structured is None else structured.get("option_inference")
        ),
        "motive_hypotheses": (
            [] if structured is None else list(structured.get("motive_hypotheses", []))
        ),
        "unknown_reasons": {
            "action": None if structured is None else structured.get("action_unknown_reason"),
            "option": None if structured is None else structured.get("option_unknown_reason"),
            "motive": None if structured is None else structured.get("motive_unknown_reason"),
        },
        "uncertainty": uncertainty,
        "failure": failure,
        "accepted_interpretation_published": accepted,
        "raw_details": {
            "result": result,
            "interpretation": interpretation,
        },
    }


def _diagnostic_view(
    authoritative: dict[str, Any],
    shadow: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> dict[str, Any]:
    def agreement(field: str) -> dict[str, Any]:
        value = None if comparison is None else comparison.get(field)
        return {"comparable": type(value) is bool, "value": value}

    action_citations = [
        list(item.get("cited_observation_ids", []))
        for item in shadow["action_hypotheses"]
        if isinstance(item, dict)
    ]
    motive_citations = [
        list(item.get("cited_observation_ids", []))
        for item in shadow["motive_hypotheses"]
        if isinstance(item, dict)
    ]
    option = shadow["option_inference"]
    option_citations = (
        list(option.get("cited_observation_ids", []))
        if isinstance(option, dict)
        else []
    )
    return {
        "option_agreement": agreement("option_mapping_matches"),
        "action_family_agreement": agreement("action_family_matches"),
        "action_subtype_agreement": agreement("action_subtype_matches"),
        "motive_family_overlap": {
            "comparable": False,
            "value": None,
            "reason": "Frozen evidence does not map deterministic motive text to V3 motive enums.",
        },
        "motive_subtype_overlap": {
            "comparable": False,
            "value": None,
            "reason": "Frozen evidence does not map deterministic motive text to V3 motive enums.",
        },
        "citation_differences": {
            "comparable": False,
            "reason": "Authoritative and V3 citations use different frozen namespaces.",
            "authoritative_supporting_observation_ids": list(
                authoritative.get("supporting_observation_ids", [])
            ),
            "shadow_action_citations": action_citations,
            "shadow_option_citations": option_citations,
            "shadow_motive_citations": motive_citations,
        },
        "uncertainty_differences": {
            "comparable": False,
            "reason": "The deterministic V1 interpretation has no V3 three-state self-report.",
            "authoritative": None,
            "shadow": shadow["uncertainty"],
        },
        "raw_details": comparison,
    }


def _debug_ground_truth(gap: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": "DEBUG / EVALUATOR GROUND TRUTH",
        "warning": "Racio did not receive evaluator ground truth.",
        "source_mind": gap.get("source_mind"),
        "native_option_id": gap.get("native_option_id"),
        "native_action_tendency": gap.get("native_action_tendency"),
        "native_motive_summary": gap.get("native_motive_summary"),
        "gap_status": gap.get("gap_status"),
        "distortion_type": gap.get("distortion_type"),
        "option_match": gap.get("option_match"),
        "motive_fidelity": gap.get("motive_fidelity"),
        "fidelity_components": list(gap.get("fidelity_components", [])),
    }


def _lane_view(
    snapshot: _EvidenceSnapshot,
    *,
    source_mind: str,
    stem: str,
    mind_label: str,
    interpretations: list[Any],
    gaps: list[Any] | None,
    debug: bool,
    registration: _EvidenceRegistration,
) -> dict[str, Any]:
    run_relative = PurePosixPath("runs") / registration.run_id
    control = PurePosixPath("control") / run_relative / "communication"
    shadow_root = (
        PurePosixPath("shadow") / run_relative / "communication_shadow"
    )
    authoritative = _authoritative_view(
        _one_by_mind(interpretations, source_mind, label="Authoritative interpretations")
    )
    packet = _artifact_json(
        snapshot,
        shadow_root / f"{stem}_packet_v3.json",
        expected=dict,
    )
    result = _artifact_json(
        snapshot,
        shadow_root / f"{stem}_result.json",
        expected=dict,
    )
    if result.get("source_mind") != source_mind or result.get("no_authority") is not True:
        raise ShadowEvidenceIntegrityError("Shadow result violates its lane boundary")
    interpretation = _artifact_json(
        snapshot,
        shadow_root / f"{stem}_interpretation_v3.json",
        expected=dict,
        required=result.get("status") == "succeeded",
    )
    comparison = _artifact_json(
        snapshot,
        shadow_root / f"{stem}_comparison.json",
        expected=dict,
        required=result.get("status") == "succeeded",
    )
    shape, shadow = _shadow_view(result, interpretation)
    lane: dict[str, Any] = {
        "source_mind": source_mind,
        "mind_label": mind_label,
        "presentation_shape": shape,
        "visible_input": _visible_input(packet),
        "authoritative": authoritative,
        "shadow": shadow,
        "diagnostic_comparison": _diagnostic_view(
            authoritative, shadow, comparison
        ),
    }
    if debug:
        if gaps is None:
            raise ShadowEvidenceIntegrityError("Debug evidence was not loaded")
        lane["debug_evaluator_ground_truth"] = _debug_ground_truth(
            _one_by_mind(gaps, source_mind, label="Evaluator translation gaps")
        )
    # Keep the control-lane locator explicit in code without exposing it in output.
    assert control.as_posix().endswith("communication")
    return lane


def _assert_safe_projection(payload: Mapping[str, Any], *, debug: bool) -> None:
    for value in _walk_json(payload):
        if isinstance(value, str) and (
            _WINDOWS_ABSOLUTE_PATH.search(value) or _POSIX_LOCAL_PATH.search(value)
        ):
            raise ShadowEvidenceIntegrityError(
                "Shadow GUI projection contains a local absolute path"
            )
        if isinstance(value, dict):
            keys = {str(key) for key in value}
            if "thinking" in keys or "raw_response_envelope" in keys:
                raise ShadowEvidenceIntegrityError(
                    "Shadow GUI projection contains private model content"
                )
            if not debug and any(key.startswith("native_") for key in keys):
                raise ShadowEvidenceIntegrityError(
                    "Normal shadow GUI projection contains evaluator truth"
                )


def build_shadow_evidence_view(
    repository_root: str | Path,
    evidence_id: str,
    *,
    debug: bool = False,
    cold_verifier: ColdVerifier | None = None,
) -> dict[str, Any]:
    """Cold-verify and project one compiled-in frozen evidence replay."""

    registration = _EVIDENCE_REGISTRY.get(evidence_id)
    if registration is None:
        raise KeyError(evidence_id)
    before = _preflight_evidence_root(repository_root, registration)
    receipt_before = (
        _preflight_external_receipt(repository_root, registration)
        if registration.receipt_required
        else None
    )
    verifier = _committed_cold_verify if cold_verifier is None else cold_verifier
    try:
        cold_manifest, receipt = verifier(before.root, registration)
    except ShadowEvidenceIntegrityError:
        raise
    except Exception as exc:
        raise ShadowEvidenceIntegrityError(
            "Committed shadow evidence failed cold verification"
        ) from exc
    after = _preflight_evidence_root(repository_root, registration)
    if before.inventory != after.inventory or before.total_bytes != after.total_bytes:
        raise ShadowEvidenceIntegrityError(
            "Shadow evidence changed during cold verification"
        )
    if cold_manifest.get("manifest_id") != after.manifest.get("manifest_id"):
        raise ShadowEvidenceIntegrityError(
            "Cold verifier returned a different evidence manifest"
        )
    if registration.receipt_required and receipt is None:
        raise ShadowEvidenceIntegrityError("External receipt was not verified")
    if registration.receipt_required:
        receipt_after = _preflight_external_receipt(
            repository_root, registration
        )
        if receipt_before is None or receipt_before[1] != receipt_after[1]:
            raise ShadowEvidenceIntegrityError(
                "External receipt changed during verification"
            )
        if dict(receipt or {}) != receipt_after[0]:
            raise ShadowEvidenceIntegrityError(
                "Cold verifier returned a different external receipt"
            )

    control_communication = (
        PurePosixPath("control")
        / PurePosixPath("runs")
        / registration.run_id
        / "communication"
    )
    interpretations = _artifact_json(
        after,
        control_communication / "interpretations.json",
        expected=list,
    )
    gaps = (
        _artifact_json(
            after,
            control_communication / "translation_gaps.json",
            expected=list,
        )
        if debug
        else None
    )
    lanes = {
        "emocio": _lane_view(
            after,
            source_mind="E",
            stem="emocio",
            mind_label="Emocio",
            interpretations=interpretations,
            gaps=gaps,
            debug=debug,
            registration=registration,
        ),
        "instinkt": _lane_view(
            after,
            source_mind="I",
            stem="instinkt",
            mind_label="Instinkt",
            interpretations=interpretations,
            gaps=gaps,
            debug=debug,
            registration=registration,
        ),
    }
    receipt_id = None if receipt is None else receipt.get("receipt_id")
    receipt_sha256 = None if receipt is None else receipt.get("receipt_sha256")
    payload: dict[str, Any] = {
        "schema_version": SHADOW_EVIDENCE_SCHEMA_VERSION,
        "evidence_id": registration.evidence_id,
        "label": registration.label,
        "phase": registration.phase,
        "summary": registration.summary,
        "kind": registration.kind,
        "language": registration.language,
        "historical": registration.kind == "historical",
        "language_boundary": (
            "current_english_model_boundary"
            if registration.kind == "current_runtime"
            else "historical_slovene_model_boundary"
        ),
        "integrity": {
            "status": "cold_verified",
            "manifest_id": after.manifest.get("manifest_id"),
            "manifest_sha256": after.manifest.get("manifest_sha256"),
            "receipt_required": registration.receipt_required,
            "receipt_verified": receipt is not None,
            "receipt_id": receipt_id,
            "receipt_sha256": receipt_sha256,
            "evidence_root_closed": True,
            "file_count": len(after.files),
            "total_bytes": after.total_bytes,
        },
        "no_authority": True,
        "live_model_execution": False,
        "authority": "none",
        "model_calls": 0,
        "lanes": lanes,
    }
    _assert_safe_projection(payload, debug=debug)
    return payload


def build_shadow_evidence_index(
    repository_root: str | Path,
    *,
    cold_verifier: ColdVerifier | None = None,
) -> dict[str, Any]:
    """Return the verified replay index with no execution authority."""

    evidence: list[dict[str, Any]] = []
    for evidence_id in SHADOW_EVIDENCE_IDS:
        registration = _EVIDENCE_REGISTRY[evidence_id]
        detail = build_shadow_evidence_view(
            repository_root,
            evidence_id,
            cold_verifier=cold_verifier,
        )
        evidence.append(
            {
                "evidence_id": detail["evidence_id"],
                "label": detail["label"],
                "selector_label": registration.selector_label,
                "phase": detail["phase"],
                "summary": detail["summary"],
                "kind": detail["kind"],
                "language": detail["language"],
                "historical": detail["historical"],
                "language_boundary": detail["language_boundary"],
                "presentation_shapes": {
                    key: lane["presentation_shape"]
                    for key, lane in detail["lanes"].items()
                },
                "no_authority": True,
                "integrity_status": detail["integrity"]["status"],
            }
        )
    payload = {
        "schema_version": SHADOW_EVIDENCE_INDEX_SCHEMA_VERSION,
        "default_evidence_id": DEFAULT_SHADOW_EVIDENCE_ID,
        "evidence": evidence,
        "read_only": True,
        "live_model_execution": False,
        "authority": "none",
        "model_calls": 0,
    }
    _assert_safe_projection(payload, debug=False)
    return payload


__all__ = [
    "DEFAULT_SHADOW_EVIDENCE_ID",
    "MAX_EVIDENCE_FILE_BYTES",
    "MAX_EVIDENCE_FILES",
    "MAX_EVIDENCE_TOTAL_BYTES",
    "MAX_EXTERNAL_RECEIPT_BYTES",
    "SHADOW_EVIDENCE_IDS",
    "SHADOW_EVIDENCE_INDEX_SCHEMA_VERSION",
    "SHADOW_EVIDENCE_SCHEMA_VERSION",
    "ShadowEvidenceIntegrityError",
    "build_shadow_evidence_index",
    "build_shadow_evidence_view",
    "is_registered_shadow_evidence_id",
]
