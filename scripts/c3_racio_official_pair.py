"""Implement the sealed C3 holdout/regression pair after stdlib preflight.

This entry point deliberately exposes no model, corpus, profile, or output
overrides.  It is create-only, runs both deterministic baselines before model
discovery, then executes the untouched holdout before the frozen v1 regression
suite with one provider instance.  A failed holdout quality gate does not skip
the regression run.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import secrets
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal, Self

from pydantic import Field, model_validator


ROOT = Path(__file__).resolve().parents[1]

from app.backend.rei.communication.conscious_access import (  # noqa: E402
    CONSCIOUS_ACCESS_CALIBRATION_POLICY_ID,
)
from app.backend.rei.communication.model_registry import (  # noqa: E402
    RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
    RacioInterpreterModelCandidate,
    load_racio_interpreter_model_registry,
)
from app.backend.rei.communication.structured_interpreter import (  # noqa: E402
    StructuredRacioInterpreterOutput,
)
from app.backend.rei.evaluation.c3_official_suite import (  # noqa: E402
    OFFICIAL_C3_SUITE_ORDER,
    OFFICIAL_HOLDOUT_MANIFEST_SHA256,
    OFFICIAL_REGRESSION_MANIFEST_SHA256,
    PROTOCOL_FREEZE_COMMIT,
    load_official_c3_suite_pair,
)
from app.backend.rei.evaluation.racio_interpreter_benchmark import (  # noqa: E402
    HOLDOUT_MANIFEST_PATH,
    MANIFEST_PATH,
    C3BenchmarkRunMetrics,
    C3BenchmarkCaseResult,
    C3BenchmarkSuite,
    C3FailureEvidence,
    evaluate_c3_benchmark_run,
)
from app.backend.rei.ids import canonical_json_bytes, sha256_hex, utc_now  # noqa: E402
from app.backend.rei.models.common import (  # noqa: E402
    CommitDigest,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    UtcTimestamp,
)
from app.backend.rei.models.provider import ProviderIdentity  # noqa: E402
from app.backend.rei.providers.native import SystemExecutionClock  # noqa: E402
from app.backend.rei.providers.ollama import (  # noqa: E402
    MAX_OLLAMA_RESPONSE_BYTES,
    OllamaApiClient,
    OllamaJsonTransport,
    OllamaRacioSettings,
    UrllibOllamaTransport,
)
from app.backend.rei.providers.ollama_interpreter import (  # noqa: E402
    OLLAMA_INTERPRETER_NO_FALLBACK_REASON,
    OLLAMA_INTERPRETER_PROVIDER_REVISION,
    RACIO_INTERPRETER_STRUCTURED_INSTRUCTION,
    OllamaStructuredRacioInterpreterProvider,
)
from scripts.run_racio_interpreter_benchmark import (  # noqa: E402
    C3BenchmarkRunProvenance,
    _validate_failure_closure,
    deterministic_results,
    execute_provider_suite,
)
from scripts.run_c3_racio_official_pair import (  # noqa: E402
    EXPECTED_SEAL_DELTA,
    SCOPED_EXECUTION_PATHS,
    _require_no_execution_import_collisions,
    _sanitized_git_environment,
    _trusted_git_executable,
    _validate_worktree_against_head,
)


PAIR_ID: Final = "c3-racio-official-pair-qwen3-6-35b-2026-07-15"
OFFICIAL_OUTPUT_ROOT: Final = ROOT / "Docs" / "evals" / "semantic_lab_v1" / PAIR_ID
OFFICIAL_MODEL_ID: Final = "qwen3.6:35b"
OFFICIAL_MODEL_DIGEST: Final = (
    "07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522"
)
OFFICIAL_INSTRUCTION_SHA256: Final = (
    "c5ea5a0936bbab5e9bb481e53443eb9119cb5bf2c1d58737f3bb0214ebcfb1b0"
)
OFFICIAL_OUTPUT_SCHEMA_SHA256: Final = (
    "7b51eeadc1e13223016a1ab95aab88b9141ed7d11a5400bd05cf25988645bd1c"
)
OFFICIAL_SEED: Final = 314159
OFFICIAL_TEMPERATURE: Final = 0.0
OFFICIAL_NUM_CTX: Final = 65536
OFFICIAL_NUM_GPU: Final = 999
OFFICIAL_NUM_PREDICT: Final = 1536
OFFICIAL_TIMEOUT_SECONDS: Final = 600.0
OFFICIAL_KEEP_ALIVE: Final = "10m"
OFFICIAL_BASE_URL: Final = "http://127.0.0.1:11434"
OFFICIAL_PROVIDER_CASE_ATTEMPTS: Final = 64


class C3OfficialPairProfile(FrozenModel):
    schema_version: Literal["rei-c3-official-pair-profile-v1"]
    model_id: Literal["qwen3.6:35b"]
    model_digest: Literal[
        "07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522"
    ]
    registry_status: Literal["c3_candidate"]
    provider_revision: Literal["rei-ollama-racio-interpreter-c3-v6"]
    seed: Literal[314159]
    temperature: Literal[0.0]
    num_ctx: Literal[65536]
    num_gpu: Literal[999]
    num_predict: Literal[1536]
    timeout_seconds: Literal[600.0]
    keep_alive: Literal["10m"]
    base_url: Literal["http://127.0.0.1:11434"]
    allow_remote: Literal[False]
    require_full_gpu: Literal[True]
    maximum_response_bytes: Literal[4194304]
    retry_count: Literal[0]
    fallback_mode: Literal["none"]
    instruction_sha256: Literal[
        "c5ea5a0936bbab5e9bb481e53443eb9119cb5bf2c1d58737f3bb0214ebcfb1b0"
    ]
    output_schema_sha256: Literal[
        "7b51eeadc1e13223016a1ab95aab88b9141ed7d11a5400bd05cf25988645bd1c"
    ]
    calibration_policy_id: Literal["c3-conscious-access-calibration-v1"]


class C3OfficialSuiteDescriptor(FrozenModel):
    suite_role: Literal["untouched_holdout", "frozen_regression"]
    benchmark_id: NonEmptyId
    manifest_path: NonEmptyText
    manifest_sha256: HashDigest
    provider_case_attempt_count: Literal[32]


class C3OfficialPairAttemptLedger(FrozenModel):
    schema_version: Literal["rei-c3-official-pair-attempt-ledger-v1"]
    pair_id: Literal["c3-racio-official-pair-qwen3-6-35b-2026-07-15"]
    source_commit: CommitDigest
    protocol_freeze_commit: CommitDigest
    created_at: UtcTimestamp
    profile: C3OfficialPairProfile
    suite_order: tuple[C3OfficialSuiteDescriptor, C3OfficialSuiteDescriptor]
    provider_instance_count: Literal[1]
    planned_provider_case_attempt_count: Literal[64]

    @model_validator(mode="after")
    def validate_suite_order(self) -> Self:
        if tuple(item.suite_role for item in self.suite_order) != (
            "untouched_holdout",
            "frozen_regression",
        ):
            raise ValueError("Official C3 attempt ledger suite order differs")
        return self


class C3OfficialSuiteOutcome(FrozenModel):
    suite_role: Literal["untouched_holdout", "frozen_regression"]
    benchmark_id: NonEmptyId
    run_id: NonEmptyId
    child_directory: NonEmptyText
    child_provenance_sha256: HashDigest
    provider_case_attempt_count: Literal[32]
    api_generate_dispatch_count: int = Field(ge=0, le=32)
    passed_case_count: int = Field(ge=0, le=32)
    failure_count: int = Field(ge=0, le=32)
    quality_gate_pass: bool


class C3OfficialPairProvenance(FrozenModel):
    schema_version: Literal["rei-c3-official-pair-provenance-v1"]
    pair_id: Literal["c3-racio-official-pair-qwen3-6-35b-2026-07-15"]
    source_commit: CommitDigest
    protocol_freeze_commit: CommitDigest
    completed_at: UtcTimestamp
    attempt_ledger_sha256: HashDigest
    profile: C3OfficialPairProfile
    registry_path: NonEmptyText
    registry_sha256: HashDigest
    model_candidate: RacioInterpreterModelCandidate
    provider_identity: ProviderIdentity
    provider_instance_count: Literal[1]
    provider_case_attempt_count: Literal[64]
    api_generate_dispatch_count: int = Field(ge=0, le=64)
    suite_outcomes: tuple[C3OfficialSuiteOutcome, C3OfficialSuiteOutcome]
    quality_gate_pass: bool

    @model_validator(mode="after")
    def validate_pair_closure(self) -> Self:
        if tuple(item.suite_role for item in self.suite_outcomes) != (
            "untouched_holdout",
            "frozen_regression",
        ):
            raise ValueError("Official C3 result suite order differs")
        if (
            sum(item.provider_case_attempt_count for item in self.suite_outcomes)
            != self.provider_case_attempt_count
        ):
            raise ValueError("Official C3 provider-attempt closure differs")
        if (
            sum(item.api_generate_dispatch_count for item in self.suite_outcomes)
            != self.api_generate_dispatch_count
        ):
            raise ValueError("Official C3 generate-dispatch closure differs")
        expected_gate = all(item.quality_gate_pass for item in self.suite_outcomes)
        if self.quality_gate_pass != expected_gate:
            raise ValueError("Official C3 pair quality disposition differs")
        return self


@dataclass(slots=True)
class CountingOllamaJsonTransport:
    """Count actual generate dispatches separately from provider attempts."""

    delegate: OllamaJsonTransport
    api_generate_dispatch_count: int = 0

    def request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        if method == "POST" and url == f"{OFFICIAL_BASE_URL}/api/generate":
            self.api_generate_dispatch_count += 1
        return self.delegate.request_json(
            method=method,
            url=url,
            payload=payload,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
        )


@dataclass(frozen=True, slots=True)
class DirectoryAnchor:
    path: Path
    metadata: os.stat_result
    parent: DirectoryAnchor | None = field(default=None, repr=False, compare=False)
    name_in_parent: str | None = None
    windows_handle: int | None = field(default=None, repr=False, compare=False)
    posix_descriptor: int | None = field(default=None, repr=False, compare=False)

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        parent: DirectoryAnchor | None = None,
        name_in_parent: str | None = None,
    ) -> DirectoryAnchor:
        metadata = _require_regular_directory(
            path, label="Official C3 directory anchor"
        )
        if os.name == "nt":
            handle = _open_windows_directory_handle(path)
            try:
                _validate_windows_directory_handle(handle, metadata=metadata)
            except BaseException:
                _close_windows_handle(handle)
                raise
            anchor = cls(
                path=path,
                metadata=metadata,
                parent=parent,
                name_in_parent=name_in_parent,
                windows_handle=handle,
            )
        else:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            if parent is not None and parent.posix_descriptor is not None:
                descriptor = os.open(
                    name_in_parent or path.name,
                    flags,
                    dir_fd=parent.posix_descriptor,
                )
            else:
                descriptor = os.open(path, flags)
            try:
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or opened.st_dev != metadata.st_dev
                    or opened.st_ino != metadata.st_ino
                ):
                    raise ValueError("Official C3 directory anchor identity differs")
            except BaseException:
                os.close(descriptor)
                raise
            anchor = cls(
                path=path,
                metadata=metadata,
                parent=parent,
                name_in_parent=name_in_parent,
                posix_descriptor=descriptor,
            )
        try:
            anchor.validate()
        except BaseException:
            anchor.close()
            raise
        return anchor

    def validate(self) -> None:
        if os.name == "nt":
            if self.windows_handle is None:
                raise ValueError("Official C3 Windows directory anchor is closed")
            _validate_windows_directory_handle(
                self.windows_handle,
                metadata=self.metadata,
            )
            current = os.lstat(self.path)
        else:
            if self.posix_descriptor is None:
                raise ValueError("Official C3 POSIX directory anchor is closed")
            opened = os.fstat(self.posix_descriptor)
            if self.parent is not None and self.parent.posix_descriptor is not None:
                current = os.stat(
                    self.name_in_parent or self.path.name,
                    dir_fd=self.parent.posix_descriptor,
                    follow_symlinks=False,
                )
            else:
                current = os.lstat(self.path)
            if (
                opened.st_dev != self.metadata.st_dev
                or opened.st_ino != self.metadata.st_ino
            ):
                raise ValueError("Official C3 directory anchor handle changed")
        if (
            not stat.S_ISDIR(current.st_mode)
            or _metadata_is_reparse(current)
            or current.st_dev != self.metadata.st_dev
            or current.st_ino != self.metadata.st_ino
        ):
            raise ValueError("Official C3 directory anchor path changed")

    def create_child(self, name: str) -> DirectoryAnchor:
        self.validate()
        child_path = self.path / name
        if os.name == "nt":
            child_path.mkdir(parents=False, exist_ok=False)
        else:
            if self.posix_descriptor is None:
                raise ValueError("Official C3 POSIX directory anchor is closed")
            os.mkdir(name, dir_fd=self.posix_descriptor)
        child = DirectoryAnchor.open(
            child_path,
            parent=self,
            name_in_parent=name,
        )
        self.validate()
        return child

    def list_names(self) -> set[str]:
        self.validate()
        if os.name != "nt" and self.posix_descriptor is not None:
            return set(os.listdir(self.posix_descriptor))
        return {item.name for item in self.path.iterdir()}

    def close(self) -> None:
        if self.windows_handle is not None:
            _close_windows_handle(self.windows_handle)
            object.__setattr__(self, "windows_handle", None)
        if self.posix_descriptor is not None:
            os.close(self.posix_descriptor)
            object.__setattr__(self, "posix_descriptor", None)


@dataclass(slots=True)
class ReservedOutputRoot:
    path: Path
    device: int
    inode: int
    anchor: DirectoryAnchor | None = field(default=None, repr=False)
    parent_anchor: DirectoryAnchor | None = field(default=None, repr=False)
    child_anchors: dict[str, DirectoryAnchor] = field(default_factory=dict, repr=False)

    def validate(self) -> Path:
        if self.anchor is not None:
            self.anchor.validate()
        metadata = os.lstat(self.path)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or _metadata_is_reparse(metadata)
            or metadata.st_dev != self.device
            or metadata.st_ino != self.inode
        ):
            raise ValueError("Official C3 output reservation identity changed")
        if self.path.resolve(strict=True) != _resolved_official_output_target():
            raise ValueError("Official C3 output reservation path changed")
        return self.path

    def ensure_anchor(self) -> DirectoryAnchor:
        self.validate()
        if self.anchor is None:
            anchor = DirectoryAnchor.open(self.path)
            if (
                anchor.metadata.st_dev != self.device
                or anchor.metadata.st_ino != self.inode
            ):
                anchor.close()
                raise ValueError("Official C3 output reservation identity changed")
            self.anchor = anchor
        self.anchor.validate()
        return self.anchor

    def register_child(self, name: str, anchor: DirectoryAnchor) -> None:
        if name in self.child_anchors:
            raise ValueError("Official C3 child directory anchor already exists")
        self.child_anchors[name] = anchor

    def require_child(self, name: str) -> DirectoryAnchor:
        anchor = self.child_anchors.get(name)
        if anchor is None:
            root = self.ensure_anchor()
            anchor = DirectoryAnchor.open(
                self.path / name,
                parent=root,
                name_in_parent=name,
            )
            self.child_anchors[name] = anchor
        anchor.validate()
        return anchor

    def close(self) -> None:
        for anchor in reversed(tuple(self.child_anchors.values())):
            anchor.close()
        self.child_anchors.clear()
        if self.anchor is not None:
            self.anchor.close()
            self.anchor = None
        if self.parent_anchor is not None:
            self.parent_anchor.close()
            self.parent_anchor = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def _git_text(*args: str) -> str:
    completed = subprocess.run(
        [
            os.fspath(_trusted_git_executable()),
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            *args,
        ],
        cwd=ROOT,
        env=_sanitized_git_environment(),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_bytes(*args: str) -> bytes:
    completed = subprocess.run(
        [
            os.fspath(_trusted_git_executable()),
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            *args,
        ],
        cwd=ROOT,
        env=_sanitized_git_environment(),
        check=True,
        capture_output=True,
    )
    return completed.stdout


def scoped_source_commit(*, bootstrap_source_commit: str | None = None) -> str:
    """Require the pushed, single-parent seal child on main and clean sources."""

    git_entry = ROOT / ".git"
    git_metadata = os.lstat(git_entry)
    if not stat.S_ISDIR(git_metadata.st_mode) or _metadata_is_reparse(git_metadata):
        raise ValueError("Official C3 Git directory differs from the repository")
    repository_root = Path(_git_text("rev-parse", "--show-toplevel"))
    git_directory = Path(_git_text("rev-parse", "--absolute-git-dir"))
    if repository_root.resolve(strict=True) != ROOT.resolve(strict=True):
        raise ValueError("Official C3 Git toplevel differs from the script repository")
    reported_git_directory = os.path.normcase(os.path.abspath(os.fspath(git_directory)))
    expected_git_directory = os.path.normcase(os.path.abspath(os.fspath(git_entry)))
    if reported_git_directory != expected_git_directory:
        raise ValueError("Official C3 Git directory differs from the repository")
    if _git_text("branch", "--show-current") != "main":
        raise ValueError("Official C3 pair must execute directly on main")
    source_commit = _git_text("rev-parse", "HEAD")
    if len(source_commit) != 40:
        raise ValueError("Official C3 pair requires a full Git source commit")
    if bootstrap_source_commit is not None and bootstrap_source_commit != source_commit:
        raise ValueError("Official C3 source changed after stdlib bootstrap")
    if _git_text("rev-parse", "--verify", "origin/main") != source_commit:
        raise ValueError("Official C3 pair requires HEAD to equal origin/main")
    try:
        _git_text("cat-file", "-e", f"{PROTOCOL_FREEZE_COMMIT}^{{commit}}")
    except subprocess.CalledProcessError as exc:
        raise ValueError("C3 protocol-freeze commit is unavailable") from exc
    parents = _git_text("show", "-s", "--format=%P", source_commit).split()
    if parents != [PROTOCOL_FREEZE_COMMIT]:
        raise ValueError(
            "Official C3 execution commit must be the single direct child of "
            "the protocol-freeze commit"
        )
    changed = tuple(
        sorted(
            item
            for item in _git_text(
                "diff",
                "--name-only",
                "--no-renames",
                PROTOCOL_FREEZE_COMMIT,
                source_commit,
                "--",
            ).splitlines()
            if item
        )
    )
    if changed != EXPECTED_SEAL_DELTA:
        raise ValueError("Official C3 seal commit delta differs from its allowlist")
    status = _git_text(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *SCOPED_EXECUTION_PATHS,
    )
    if status:
        raise ValueError("Official C3 runtime, corpus, and seal sources must be clean")
    _validate_worktree_against_head(source_commit)
    _require_no_execution_import_collisions()
    return source_commit


def _required_exact_integer_environment(name: str, expected: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() != str(expected):
        raise ValueError(f"{name} must be explicitly set to {expected}")
    return expected


def _reject_conflicting_environment() -> None:
    exact_values = {
        "REI_OLLAMA_MODEL": OFFICIAL_MODEL_ID,
        "REI_OLLAMA_BASE_URL": OFFICIAL_BASE_URL,
        "REI_OLLAMA_SEED": str(OFFICIAL_SEED),
        "REI_OLLAMA_NUM_PREDICT": str(OFFICIAL_NUM_PREDICT),
        "REI_OLLAMA_KEEP_ALIVE": OFFICIAL_KEEP_ALIVE,
    }
    for name, expected in exact_values.items():
        raw = os.environ.get(name)
        if raw is not None and raw.strip() != expected:
            raise ValueError(f"{name} conflicts with the sealed C3 profile")
    numeric_values = {
        "REI_OLLAMA_TEMPERATURE": OFFICIAL_TEMPERATURE,
        "REI_OLLAMA_TIMEOUT_SECONDS": OFFICIAL_TIMEOUT_SECONDS,
    }
    for name, expected in numeric_values.items():
        raw = os.environ.get(name)
        if raw is not None:
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError(
                    f"{name} conflicts with the sealed C3 profile"
                ) from exc
            if value != expected:
                raise ValueError(f"{name} conflicts with the sealed C3 profile")
    require_full_gpu = os.environ.get("REI_OLLAMA_REQUIRE_FULL_GPU")
    if require_full_gpu is not None and require_full_gpu.strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise ValueError(
            "REI_OLLAMA_REQUIRE_FULL_GPU conflicts with the sealed C3 profile"
        )


def frozen_profile_from_environment() -> C3OfficialPairProfile:
    _reject_conflicting_environment()
    num_ctx = _required_exact_integer_environment(
        "REI_OLLAMA_NUM_CTX", OFFICIAL_NUM_CTX
    )
    num_gpu = _required_exact_integer_environment(
        "REI_OLLAMA_NUM_GPU", OFFICIAL_NUM_GPU
    )
    return C3OfficialPairProfile(
        schema_version="rei-c3-official-pair-profile-v1",
        model_id=OFFICIAL_MODEL_ID,
        model_digest=OFFICIAL_MODEL_DIGEST,
        registry_status="c3_candidate",
        provider_revision=OLLAMA_INTERPRETER_PROVIDER_REVISION,
        seed=OFFICIAL_SEED,
        temperature=OFFICIAL_TEMPERATURE,
        num_ctx=num_ctx,
        num_gpu=num_gpu,
        num_predict=OFFICIAL_NUM_PREDICT,
        timeout_seconds=OFFICIAL_TIMEOUT_SECONDS,
        keep_alive=OFFICIAL_KEEP_ALIVE,
        base_url=OFFICIAL_BASE_URL,
        allow_remote=False,
        require_full_gpu=True,
        maximum_response_bytes=MAX_OLLAMA_RESPONSE_BYTES,
        retry_count=0,
        fallback_mode="none",
        instruction_sha256=OFFICIAL_INSTRUCTION_SHA256,
        output_schema_sha256=OFFICIAL_OUTPUT_SCHEMA_SHA256,
        calibration_policy_id=CONSCIOUS_ACCESS_CALIBRATION_POLICY_ID,
    )


def _recorded_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError:
        relative = resolved
    return str(relative).replace("\\", "/")


def _validate_candidate(candidate: RacioInterpreterModelCandidate) -> None:
    if (
        candidate.model_id != OFFICIAL_MODEL_ID
        or candidate.model_digest != OFFICIAL_MODEL_DIGEST
        or candidate.runtime != "ollama"
        or candidate.modality_support != ("structured_text", "vision")
        or candidate.slovenian_baseline != "not_benchmarked"
        or candidate.max_context != 262144
        or candidate.hardware_requirements.minimum_vram_gib != 32
        or candidate.hardware_requirements.gpu_offload_policy != "full_gpu_preferred"
        or candidate.license != "Apache-2.0"
        or candidate.benchmark_status != "c3_candidate"
    ):
        raise ValueError("Official C3 registry candidate differs from its frozen pin")


def _validate_protocol_frozen_sources(
    *,
    source_commit: str,
    holdout: C3BenchmarkSuite,
) -> None:
    del source_commit  # exact seal-delta validation freezes every pre-existing path
    for pin in holdout.manifest.source_grounding_pins:
        frozen_bytes = _git_bytes(
            "show", f"{PROTOCOL_FREEZE_COMMIT}:{pin.fixture_path}"
        )
        if hashlib.sha256(frozen_bytes).hexdigest() != pin.fixture_sha256:
            raise ValueError(
                f"Protocol-freeze source fixture differs from pin: {pin.family_id}"
            )


def validate_frozen_contract(
    *,
    source_commit: str,
) -> tuple[
    C3BenchmarkSuite,
    C3BenchmarkSuite,
    RacioInterpreterModelCandidate,
    str,
]:
    if OLLAMA_INTERPRETER_PROVIDER_REVISION != "rei-ollama-racio-interpreter-c3-v6":
        raise ValueError("Official C3 provider revision differs")
    if sha256_hex(RACIO_INTERPRETER_STRUCTURED_INSTRUCTION) != (
        OFFICIAL_INSTRUCTION_SHA256
    ):
        raise ValueError("Official C3 instruction bytes differ")
    if sha256_hex(StructuredRacioInterpreterOutput.model_json_schema()) != (
        OFFICIAL_OUTPUT_SCHEMA_SHA256
    ):
        raise ValueError("Official C3 output schema differs")
    if CONSCIOUS_ACCESS_CALIBRATION_POLICY_ID != ("c3-conscious-access-calibration-v1"):
        raise ValueError("Official C3 calibration policy differs")

    holdout, regression = load_official_c3_suite_pair()
    if OFFICIAL_C3_SUITE_ORDER != (
        (HOLDOUT_MANIFEST_PATH, OFFICIAL_HOLDOUT_MANIFEST_SHA256),
        (MANIFEST_PATH, OFFICIAL_REGRESSION_MANIFEST_SHA256),
    ):
        raise ValueError("Official C3 suite registration order differs")
    if holdout.manifest.protocol_freeze_commit != PROTOCOL_FREEZE_COMMIT:
        raise ValueError("Official C3 holdout protocol commit differs")
    _validate_protocol_frozen_sources(
        source_commit=source_commit,
        holdout=holdout,
    )

    registry_path = RACIO_INTERPRETER_MODEL_REGISTRY_PATH.resolve(strict=True)
    registry = load_racio_interpreter_model_registry(registry_path)
    candidate = registry.require_candidate(
        model_id=OFFICIAL_MODEL_ID,
        digest=OFFICIAL_MODEL_DIGEST,
    )
    _validate_candidate(candidate)
    return (
        holdout,
        regression,
        candidate,
        _regular_file_sha256(
            registry_path,
            maximum_bytes=2 * 1024 * 1024,
            label="Official C3 model registry",
        ),
    )


def verify_execution_state(
    *,
    source_commit: str,
    registry_sha256: str,
) -> None:
    if scoped_source_commit(bootstrap_source_commit=source_commit) != source_commit:
        raise ValueError("Official C3 source commit changed during execution")
    if (
        _regular_file_sha256(
            RACIO_INTERPRETER_MODEL_REGISTRY_PATH.resolve(),
            maximum_bytes=2 * 1024 * 1024,
            label="Official C3 model registry",
        )
        != registry_sha256
    ):
        raise ValueError("Official C3 registry bytes changed during execution")


def build_official_provider(
    *,
    profile: C3OfficialPairProfile,
    candidate: RacioInterpreterModelCandidate,
) -> tuple[
    OllamaStructuredRacioInterpreterProvider,
    CountingOllamaJsonTransport,
]:
    _validate_candidate(candidate)
    transport = CountingOllamaJsonTransport(UrllibOllamaTransport())
    client = OllamaApiClient(
        base_url=profile.base_url,
        allow_remote=profile.allow_remote,
        transport=transport,
    )
    settings = OllamaRacioSettings(
        model=profile.model_id,
        seed=profile.seed,
        temperature=profile.temperature,
        num_ctx=profile.num_ctx,
        num_gpu=profile.num_gpu,
        num_predict=profile.num_predict,
        timeout_seconds=profile.timeout_seconds,
        keep_alive=profile.keep_alive,
        require_full_gpu=profile.require_full_gpu,
    )
    provider = OllamaStructuredRacioInterpreterProvider.discover(
        client=client,
        settings=settings,
        expected_digest=profile.model_digest,
    )
    if (
        provider.settings != settings
        or provider.runtime.model != profile.model_id
        or provider.runtime.digest != profile.model_digest
        or not provider.settings.require_full_gpu
    ):
        raise ValueError("Discovered C3 provider differs from the sealed profile")
    return provider, transport


def _suite_descriptors(
    holdout: C3BenchmarkSuite,
    regression: C3BenchmarkSuite,
) -> tuple[C3OfficialSuiteDescriptor, C3OfficialSuiteDescriptor]:
    return (
        C3OfficialSuiteDescriptor(
            suite_role="untouched_holdout",
            benchmark_id=holdout.manifest.benchmark_id,
            manifest_path=_recorded_path(HOLDOUT_MANIFEST_PATH),
            manifest_sha256=holdout.manifest_file_hash,
            provider_case_attempt_count=32,
        ),
        C3OfficialSuiteDescriptor(
            suite_role="frozen_regression",
            benchmark_id=regression.manifest.benchmark_id,
            manifest_path=_recorded_path(MANIFEST_PATH),
            manifest_sha256=regression.manifest_file_hash,
            provider_case_attempt_count=32,
        ),
    )


def _metadata_is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _open_windows_directory_handle(path: Path) -> int:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(
        os.fspath(path),
        0x00010000 | 0x00000080,  # DELETE | FILE_READ_ATTRIBUTES
        0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
        None,
        3,  # OPEN_EXISTING
        0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error_number = ctypes.get_last_error()
        raise OSError(error_number, ctypes.FormatError(error_number), path)
    return int(handle)


def _windows_directory_identity(handle: int) -> tuple[int, int, int]:
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = (
            ("file_attributes", wintypes.DWORD),
            ("creation_time_low", wintypes.DWORD),
            ("creation_time_high", wintypes.DWORD),
            ("access_time_low", wintypes.DWORD),
            ("access_time_high", wintypes.DWORD),
            ("write_time_low", wintypes.DWORD),
            ("write_time_high", wintypes.DWORD),
            ("volume_serial_number", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("number_of_links", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(ByHandleFileInformation),
    )
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    information = ByHandleFileInformation()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(information)):
        error_number = ctypes.get_last_error()
        raise OSError(error_number, ctypes.FormatError(error_number))
    inode = (information.file_index_high << 32) | information.file_index_low
    return (
        information.volume_serial_number,
        inode,
        information.file_attributes,
    )


def _validate_windows_directory_handle(
    handle: int,
    *,
    metadata: os.stat_result,
) -> None:
    device, inode, attributes = _windows_directory_identity(handle)
    if (
        not attributes & 0x00000010  # FILE_ATTRIBUTE_DIRECTORY
        or attributes & 0x00000400  # FILE_ATTRIBUTE_REPARSE_POINT
        or device != metadata.st_dev
        or inode != metadata.st_ino
    ):
        raise ValueError("Official C3 Windows directory anchor identity differs")


def _close_windows_handle(handle: int) -> None:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    if not kernel32.CloseHandle(handle):
        error_number = ctypes.get_last_error()
        raise OSError(error_number, ctypes.FormatError(error_number))


def _require_regular_directory(path: Path, *, label: str) -> os.stat_result:
    metadata = os.lstat(path)
    if not stat.S_ISDIR(metadata.st_mode) or _metadata_is_reparse(metadata):
        raise ValueError(f"{label} must be a regular non-reparse directory")
    return metadata


def _resolved_official_output_target() -> Path:
    """Resolve the fixed target without following a repository child link."""

    repository_root = ROOT.resolve(strict=True)
    configured = Path(OFFICIAL_OUTPUT_ROOT)
    if not configured.is_absolute():
        configured = ROOT / configured
    try:
        relative_parent = configured.parent.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(
            "Official C3 output must remain inside the repository"
        ) from exc
    cursor = ROOT
    for component in relative_parent.parts:
        cursor /= component
        _require_regular_directory(cursor, label="Official C3 output parent chain")
    resolved_parent = cursor.resolve(strict=True)
    if not resolved_parent.is_relative_to(repository_root):
        raise ValueError("Official C3 output parent escapes the repository")
    return resolved_parent / configured.name


def _rename_windows_handle_no_replace(handle: int, destination: Path) -> None:
    from ctypes import wintypes

    class FileRenameInfoPrefix(ctypes.Structure):
        _fields_ = (
            ("flags", wintypes.DWORD),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
        )

    encoded_name = os.fspath(destination).encode("utf-16-le")
    payload_size = (
        FileRenameInfoPrefix.file_name_length.offset
        + ctypes.sizeof(wintypes.DWORD)
        + len(encoded_name)
        + ctypes.sizeof(wintypes.WCHAR)
    )
    payload = ctypes.create_string_buffer(payload_size)
    prefix = FileRenameInfoPrefix.from_buffer(payload)
    prefix.flags = 0
    prefix.root_directory = None
    prefix.file_name_length = len(encoded_name)
    ctypes.memmove(
        ctypes.addressof(payload)
        + FileRenameInfoPrefix.file_name_length.offset
        + ctypes.sizeof(wintypes.DWORD),
        encoded_name,
        len(encoded_name),
    )
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    if not kernel32.SetFileInformationByHandle(
        handle,
        22,  # FileRenameInfoEx
        payload,
        payload_size,
    ):
        error_number = ctypes.get_last_error()
        if error_number in {80, 183}:  # ERROR_FILE_EXISTS / ERROR_ALREADY_EXISTS
            raise FileExistsError(
                error_number, ctypes.FormatError(error_number), destination
            )
        raise OSError(error_number, ctypes.FormatError(error_number), destination)


def _rename_windows_anchor_no_replace(
    source: DirectoryAnchor,
    destination: Path,
) -> None:
    if source.windows_handle is None:
        raise ValueError("Official C3 Windows publication anchor is closed")
    _rename_windows_handle_no_replace(source.windows_handle, destination)


def _publish_anchored_directory(
    *,
    parent: DirectoryAnchor,
    source: DirectoryAnchor,
    destination_name: str,
) -> None:
    parent.validate()
    source.validate()
    if source.parent is not parent:
        raise ValueError("Official C3 publication anchor has the wrong parent")
    old_path = source.path
    destination = parent.path / destination_name
    if os.name == "nt":
        _rename_windows_anchor_no_replace(source, destination)
    elif sys.platform.startswith("linux"):
        if parent.posix_descriptor is None:
            raise ValueError("Official C3 POSIX publication anchor is closed")
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise OSError(errno.ENOSYS, "renameat2 is required for sealed publication")
        renameat2.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        renameat2.restype = ctypes.c_int
        result = renameat2(
            parent.posix_descriptor,
            os.fsencode(source.name_in_parent or old_path.name),
            parent.posix_descriptor,
            os.fsencode(destination_name),
            1,
        )
        if result != 0:
            error_number = ctypes.get_errno()
            if error_number == errno.EEXIST:
                raise FileExistsError(
                    error_number, os.strerror(error_number), destination
                )
            raise OSError(error_number, os.strerror(error_number), destination)
    else:
        raise OSError(
            errno.ENOTSUP,
            "This platform lacks an approved anchored publication primitive",
        )
    object.__setattr__(source, "path", destination)
    object.__setattr__(source, "name_in_parent", destination_name)
    parent.validate()
    source.validate()
    if os.path.lexists(old_path):
        raise ValueError("Official C3 staging path survived anchored publication")


def _write_windows_atomic_file(
    *,
    parent: DirectoryAnchor,
    temporary_name: str,
    destination_name: str,
    payload: bytes,
    pre_publish: Callable[[str], None] | None,
) -> os.stat_result:
    from ctypes import wintypes

    temporary_path = parent.path / temporary_name
    destination = parent.path / destination_name
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(
        os.fspath(temporary_path),
        0x40000000 | 0x00010000 | 0x00000080,
        0x00000001,
        None,
        1,  # CREATE_NEW
        0x00000080,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error_number = ctypes.get_last_error()
        if error_number in {80, 183}:
            raise FileExistsError(
                error_number,
                ctypes.FormatError(error_number),
                temporary_path,
            )
        raise OSError(error_number, ctypes.FormatError(error_number), temporary_path)
    try:
        kernel32.WriteFile.argtypes = (
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        )
        kernel32.WriteFile.restype = wintypes.BOOL
        offset = 0
        while offset < len(payload):
            chunk = payload[offset : offset + 1024 * 1024]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            if not kernel32.WriteFile(
                handle,
                buffer,
                len(chunk),
                ctypes.byref(written),
                None,
            ):
                error_number = ctypes.get_last_error()
                raise OSError(
                    error_number, ctypes.FormatError(error_number), temporary_path
                )
            if written.value != len(chunk):
                raise OSError("Official C3 atomic file write was incomplete")
            offset += written.value
        kernel32.FlushFileBuffers.argtypes = (wintypes.HANDLE,)
        kernel32.FlushFileBuffers.restype = wintypes.BOOL
        if not kernel32.FlushFileBuffers(handle):
            error_number = ctypes.get_last_error()
            raise OSError(
                error_number, ctypes.FormatError(error_number), temporary_path
            )
        device, inode, attributes = _windows_directory_identity(int(handle))
        metadata = os.lstat(temporary_path)
        if (
            attributes & 0x00000010
            or attributes & 0x00000400
            or not stat.S_ISREG(metadata.st_mode)
            or _metadata_is_reparse(metadata)
            or device != metadata.st_dev
            or inode != metadata.st_ino
        ):
            raise ValueError("Official C3 atomic file identity differs")
        if pre_publish is not None:
            pre_publish(temporary_name)
        parent.validate()
        _rename_windows_handle_no_replace(int(handle), destination)
        published = os.lstat(destination)
        if (
            not stat.S_ISREG(published.st_mode)
            or _metadata_is_reparse(published)
            or published.st_dev != metadata.st_dev
            or published.st_ino != metadata.st_ino
        ):
            raise ValueError("Official C3 atomic file changed during publication")
        parent.validate()
        return published
    finally:
        _close_windows_handle(int(handle))


def _write_anchored_atomic(
    *,
    parent: DirectoryAnchor,
    destination_name: str,
    payload: bytes,
    label: str,
    pre_publish: Callable[[str], None] | None = None,
) -> os.stat_result:
    parent.validate()
    for _ in range(32):
        temporary_name = f".{destination_name}.tmp-{secrets.token_hex(16)}"
        if os.name == "nt":
            try:
                metadata = _write_windows_atomic_file(
                    parent=parent,
                    temporary_name=temporary_name,
                    destination_name=destination_name,
                    payload=payload,
                    pre_publish=pre_publish,
                )
            except FileExistsError as exc:
                if exc.filename == os.fspath(parent.path / temporary_name):
                    continue
                raise
            return metadata

        if parent.posix_descriptor is None:
            raise ValueError("Official C3 POSIX directory anchor is closed")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(
                temporary_name,
                flags,
                0o600,
                dir_fd=parent.posix_descriptor,
            )
        except FileExistsError:
            continue
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError(f"{label} write made no progress")
                view = view[written:]
            os.fsync(descriptor)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError(f"{label} is not a regular file")
            if pre_publish is not None:
                pre_publish(temporary_name)
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is None:
                raise OSError(
                    errno.ENOSYS, "renameat2 is required for sealed publication"
                )
            renameat2.argtypes = (
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            )
            renameat2.restype = ctypes.c_int
            result = renameat2(
                parent.posix_descriptor,
                os.fsencode(temporary_name),
                parent.posix_descriptor,
                os.fsencode(destination_name),
                1,
            )
            if result != 0:
                error_number = ctypes.get_errno()
                if error_number == errno.EEXIST:
                    raise FileExistsError(
                        error_number,
                        os.strerror(error_number),
                        parent.path / destination_name,
                    )
                raise OSError(
                    error_number,
                    os.strerror(error_number),
                    parent.path / destination_name,
                )
        finally:
            os.close(descriptor)
        published = os.stat(
            destination_name,
            dir_fd=parent.posix_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(published.st_mode)
            or published.st_dev != metadata.st_dev
            or published.st_ino != metadata.st_ino
        ):
            raise ValueError(f"{label} changed during atomic publication")
        parent.validate()
        return published
    raise FileExistsError(f"{label} could not reserve unique atomic staging")


def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
    parent_anchor: DirectoryAnchor | None = None,
) -> bytes:
    if parent_anchor is not None:
        parent_anchor.validate()
        if path.parent != parent_anchor.path:
            raise ValueError(f"{label} escaped its directory anchor")
    path_metadata = os.lstat(path)
    if not stat.S_ISREG(path_metadata.st_mode) or _metadata_is_reparse(path_metadata):
        raise ValueError(f"{label} must be a bounded regular non-reparse file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if (
        parent_anchor is not None
        and os.name != "nt"
        and parent_anchor.posix_descriptor is not None
    ):
        descriptor = os.open(
            path.name,
            flags,
            dir_fd=parent_anchor.posix_descriptor,
        )
    else:
        descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or _metadata_is_reparse(before)
            or before.st_size > maximum_bytes
            or before.st_dev != path_metadata.st_dev
            or before.st_ino != path_metadata.st_ino
        ):
            raise ValueError(f"{label} must be a bounded regular non-reparse file")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    final_path_metadata = os.lstat(path)
    if (
        len(payload) > maximum_bytes
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or after.st_dev != final_path_metadata.st_dev
        or after.st_ino != final_path_metadata.st_ino
        or _metadata_is_reparse(final_path_metadata)
    ):
        raise ValueError(f"{label} changed during bounded read")
    if parent_anchor is not None:
        parent_anchor.validate()
    return payload


def _regular_file_sha256(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
    parent_anchor: DirectoryAnchor | None = None,
) -> str:
    return hashlib.sha256(
        _read_regular_file(
            path,
            maximum_bytes=maximum_bytes,
            label=label,
            parent_anchor=parent_anchor,
        )
    ).hexdigest()


def _validate_path_identity(
    path: Path,
    *,
    expected: os.stat_result,
    directory: bool,
    label: str,
) -> None:
    current = os.lstat(path)
    expected_mode = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not expected_mode(current.st_mode)
        or _metadata_is_reparse(current)
        or current.st_dev != expected.st_dev
        or current.st_ino != expected.st_ino
    ):
        raise ValueError(f"{label} identity changed before publication")


def reserve_output_root(
    *,
    source_commit: str,
    profile: C3OfficialPairProfile,
    descriptors: tuple[C3OfficialSuiteDescriptor, C3OfficialSuiteDescriptor],
) -> tuple[ReservedOutputRoot, C3OfficialPairAttemptLedger, str]:
    target = _resolved_official_output_target()
    parent_anchor = DirectoryAnchor.open(target.parent)
    try:
        target_anchor = parent_anchor.create_child(target.name)
    except FileExistsError as exc:
        parent_anchor.close()
        raise FileExistsError(
            "Official C3 pair output already exists; reruns are forbidden"
        ) from exc
    except BaseException:
        parent_anchor.close()
        raise
    target_metadata = target_anchor.metadata
    reservation = ReservedOutputRoot(
        path=target,
        device=target_metadata.st_dev,
        inode=target_metadata.st_ino,
        anchor=target_anchor,
        parent_anchor=parent_anchor,
    )
    try:
        reservation.validate()
        ledger = C3OfficialPairAttemptLedger(
            schema_version="rei-c3-official-pair-attempt-ledger-v1",
            pair_id=PAIR_ID,
            source_commit=source_commit,
            protocol_freeze_commit=PROTOCOL_FREEZE_COMMIT,
            created_at=utc_now(),
            profile=profile,
            suite_order=descriptors,
            provider_instance_count=1,
            planned_provider_case_attempt_count=OFFICIAL_PROVIDER_CASE_ATTEMPTS,
        )
        ledger_path = target / "attempt_ledger.json"
        _write_anchored_atomic(
            parent=target_anchor,
            destination_name=ledger_path.name,
            payload=canonical_json_bytes(ledger) + b"\n",
            label="Official C3 attempt ledger",
        )
        ledger_sha256 = _regular_file_sha256(
            ledger_path,
            maximum_bytes=256 * 1024,
            label="Official C3 attempt ledger",
            parent_anchor=target_anchor,
        )
    except BaseException:
        reservation.close()
        raise
    return reservation, ledger, ledger_sha256


def _canonical_jsonl_bytes(values: tuple[FrozenModel, ...]) -> bytes:
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def _official_suite_artifact_payloads(
    *,
    run_id: str,
    source_commit: str,
    manifest_path: Path,
    suite: C3BenchmarkSuite,
    metrics: C3BenchmarkRunMetrics,
    results: tuple[C3BenchmarkCaseResult, ...],
    baseline_results: tuple[C3BenchmarkCaseResult, ...],
    candidate: RacioInterpreterModelCandidate,
    registry_sha256: str,
    failures: tuple[C3FailureEvidence, ...],
) -> tuple[tuple[tuple[str, bytes], ...], C3BenchmarkRunProvenance]:
    cold_metrics = C3BenchmarkRunMetrics.model_validate_json(
        canonical_json_bytes(metrics)
    )
    recomputed = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="ollama",
        results=results,
        model_call_count=32,
        baseline_results=baseline_results,
    )
    if cold_metrics != metrics or recomputed != metrics:
        raise ValueError("Official C3 metrics differ from recomputed evidence")
    _validate_failure_closure(
        run_id=run_id,
        metrics=metrics,
        results=results,
        registry_path=RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
        candidate=candidate,
        failures=failures,
    )

    results_payload = _canonical_jsonl_bytes(results)
    metrics_payload = canonical_json_bytes(metrics) + b"\n"
    baseline_payload = _canonical_jsonl_bytes(baseline_results)
    failures_payload = _canonical_jsonl_bytes(failures)
    provenance = C3BenchmarkRunProvenance(
        schema_version="rei-c3-racio-interpreter-run-provenance-v2",
        run_id=run_id,
        source_commit=source_commit,
        created_at=utc_now(),
        provider_mode="ollama",
        benchmark_id=metrics.benchmark_id,
        benchmark_manifest_path=_recorded_path(manifest_path),
        benchmark_manifest_hash=suite.manifest_file_hash,
        public_cases_hash=suite.manifest.files[0].sha256,
        gold_hash=suite.manifest.files[1].sha256,
        model_call_count=metrics.model_call_count,
        results_sha256=hashlib.sha256(results_payload).hexdigest(),
        metrics_sha256=hashlib.sha256(metrics_payload).hexdigest(),
        baseline_results_sha256=hashlib.sha256(baseline_payload).hexdigest(),
        failure_count=len(failures),
        failures_sha256=hashlib.sha256(failures_payload).hexdigest(),
        registry_path=_recorded_path(RACIO_INTERPRETER_MODEL_REGISTRY_PATH),
        registry_sha256=registry_sha256,
        model_candidate=candidate,
        quality_gate_pass=metrics.quality_gate_pass,
    )
    provenance_payload = canonical_json_bytes(provenance) + b"\n"
    if C3BenchmarkRunProvenance.model_validate_json(provenance_payload) != provenance:
        raise ValueError("Official C3 provenance differs after cold validation")
    return (
        (
            ("results.jsonl", results_payload),
            ("metrics.json", metrics_payload),
            ("baseline_results.jsonl", baseline_payload),
            ("failures.jsonl", failures_payload),
            ("provenance.json", provenance_payload),
        ),
        provenance,
    )


def _create_suite_staging(
    *,
    output_root: ReservedOutputRoot,
    child_name: Literal["holdout", "regression"],
) -> DirectoryAnchor:
    root_anchor = output_root.ensure_anchor()
    for _ in range(32):
        staging_name = f".{child_name}.staging-{secrets.token_hex(16)}"
        try:
            staging = root_anchor.create_child(staging_name)
        except FileExistsError:
            continue
        try:
            output_root.validate()
            staging.validate()
            return staging
        except BaseException:
            staging.close()
            raise
    raise FileExistsError("Official C3 could not reserve unique suite staging")


def execute_and_publish_suite(
    *,
    output_root: ReservedOutputRoot,
    suite_role: Literal["untouched_holdout", "frozen_regression"],
    child_name: Literal["holdout", "regression"],
    run_id: str,
    manifest_path: Path,
    suite: C3BenchmarkSuite,
    baseline_results: tuple,
    provider: OllamaStructuredRacioInterpreterProvider,
    transport: CountingOllamaJsonTransport,
    candidate: RacioInterpreterModelCandidate,
    source_commit: str,
    registry_sha256: str,
) -> C3OfficialSuiteOutcome:
    reserved_path = output_root.validate()
    before_dispatches = transport.api_generate_dispatch_count
    failures: list[C3FailureEvidence] = []
    results = execute_provider_suite(
        suite=suite,
        provider_mode="ollama",
        provider=provider,
        clock=SystemExecutionClock(),
        run_id=run_id,
        failure_records=failures,
    )
    metrics: C3BenchmarkRunMetrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="ollama",
        results=results,
        model_call_count=32,
        baseline_results=baseline_results,
    )
    dispatch_count = transport.api_generate_dispatch_count - before_dispatches
    if not 0 <= dispatch_count <= 32:
        raise ValueError("Official C3 suite generate-dispatch count is invalid")
    verify_execution_state(
        source_commit=source_commit,
        registry_sha256=registry_sha256,
    )

    payloads, provenance = _official_suite_artifact_payloads(
        run_id=run_id,
        source_commit=source_commit,
        manifest_path=manifest_path,
        suite=suite,
        metrics=metrics,
        results=results,
        baseline_results=baseline_results,
        candidate=candidate,
        registry_sha256=registry_sha256,
        failures=tuple(failures),
    )
    staging_anchor = _create_suite_staging(
        output_root=output_root,
        child_name=child_name,
    )
    try:
        staging = staging_anchor.path
        staging_metadata = staging_anchor.metadata
        child = reserved_path / child_name
        for filename, payload in payloads:
            _validate_path_identity(
                staging,
                expected=staging_metadata,
                directory=True,
                label=f"Official C3 {child_name} staging",
            )
            _write_anchored_atomic(
                parent=staging_anchor,
                destination_name=filename,
                payload=payload,
                label=f"Official C3 {child_name} {filename}",
            )
        outcome = C3OfficialSuiteOutcome(
            suite_role=suite_role,
            benchmark_id=suite.manifest.benchmark_id,
            run_id=run_id,
            child_directory=_recorded_path(child),
            child_provenance_sha256=hashlib.sha256(
                canonical_json_bytes(provenance) + b"\n"
            ).hexdigest(),
            provider_case_attempt_count=32,
            api_generate_dispatch_count=dispatch_count,
            passed_case_count=metrics.passed_case_count,
            failure_count=len(failures),
            quality_gate_pass=metrics.quality_gate_pass,
        )
        _write_anchored_atomic(
            parent=staging_anchor,
            destination_name="suite_outcome.json",
            payload=canonical_json_bytes(outcome) + b"\n",
            label=f"Official C3 {child_name} suite outcome",
        )
        output_root.validate()
        _validate_path_identity(
            staging,
            expected=staging_metadata,
            directory=True,
            label=f"Official C3 {child_name} staging",
        )
        verify_execution_state(
            source_commit=source_commit,
            registry_sha256=registry_sha256,
        )
        root_anchor = output_root.ensure_anchor()
        _publish_anchored_directory(
            parent=root_anchor,
            source=staging_anchor,
            destination_name=child_name,
        )
        output_root.register_child(child_name, staging_anchor)
        output_root.validate()
        verify_execution_state(
            source_commit=source_commit,
            registry_sha256=registry_sha256,
        )
        cold_outcome = C3OfficialSuiteOutcome.model_validate_json(
            _read_regular_file(
                child / "suite_outcome.json",
                maximum_bytes=64 * 1024,
                label="Official C3 suite outcome",
                parent_anchor=staging_anchor,
            )
        )
        if cold_outcome != outcome:
            raise ValueError("Official C3 suite outcome changed during publication")
        return outcome
    except BaseException:
        registered = output_root.child_anchors.get(child_name)
        if registered is staging_anchor:
            del output_root.child_anchors[child_name]
        staging_anchor.close()
        raise


def _read_canonical_model(
    path: Path,
    *,
    model_type: Any,
    maximum_bytes: int,
    label: str,
    expected_sha256: str | None = None,
    parent_anchor: DirectoryAnchor | None = None,
) -> Any:
    payload = _read_regular_file(
        path,
        maximum_bytes=maximum_bytes,
        label=label,
        parent_anchor=parent_anchor,
    )
    if (
        expected_sha256 is not None
        and hashlib.sha256(payload).hexdigest() != expected_sha256
    ):
        raise ValueError(f"{label} hash differs")
    try:
        value = model_type.model_validate_json(payload)
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid typed artifact") from exc
    if payload != canonical_json_bytes(value) + b"\n":
        raise ValueError(f"{label} bytes are not canonical")
    return value


def _read_canonical_jsonl(
    path: Path,
    *,
    model_type: Any,
    maximum_bytes: int,
    label: str,
    allow_empty: bool = False,
    expected_sha256: str | None = None,
    parent_anchor: DirectoryAnchor | None = None,
) -> tuple[Any, ...]:
    payload = _read_regular_file(
        path,
        maximum_bytes=maximum_bytes,
        label=label,
        parent_anchor=parent_anchor,
    )
    if (
        expected_sha256 is not None
        and hashlib.sha256(payload).hexdigest() != expected_sha256
    ):
        raise ValueError(f"{label} hash differs")
    if not payload:
        if allow_empty:
            return ()
        raise ValueError(f"{label} cannot be empty")
    if not payload.endswith(b"\n"):
        raise ValueError(f"{label} must end with one canonical newline")
    lines = payload.splitlines(keepends=True)
    values: list[Any] = []
    for line in lines:
        try:
            value = model_type.model_validate_json(line)
        except ValueError as exc:
            raise ValueError(f"{label} contains an invalid typed artifact") from exc
        if line != canonical_json_bytes(value) + b"\n":
            raise ValueError(f"{label} contains non-canonical bytes")
        values.append(value)
    return tuple(values)


def _is_hash(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _validate_result_profile(
    *,
    result: C3BenchmarkCaseResult,
    profile: C3OfficialPairProfile,
    provider_identity: ProviderIdentity,
) -> None:
    provenance = result.provenance
    call = provenance.call_spec
    if (
        provenance.provider_identity != provider_identity
        or provenance.provider_id != provider_identity.provider_id
        or provenance.model_id != profile.model_id
        or provenance.model_digest != profile.model_digest
        or call.seed != profile.seed
        or call.timeout_seconds != profile.timeout_seconds
        or call.fallback_policy.mode != "none"
        or call.fallback_policy.plan is not None
        or call.fallback_policy.no_fallback_reason
        != OLLAMA_INTERPRETER_NO_FALLBACK_REASON
        or provider_identity.kind != "text_reasoner"
        or provider_identity.implementation
        != ("rei.providers.ollama_interpreter.OllamaStructuredRacioInterpreterProvider")
        or not provider_identity.implementation_revision.startswith(
            f"{profile.provider_revision};ollama="
        )
        or not provider_identity.uses_model
        or provider_identity.model != profile.model_id
        or provider_identity.model_revision != profile.model_digest
    ):
        raise ValueError("Official C3 result differs from the pair provider contract")
    values = {
        parameter.name: json.loads(parameter.canonical_json_value)
        for parameter in call.parameters
    }
    expected_names = {
        "allow_remote",
        "calibration_constraints_sha256",
        "calibration_policy_id",
        "endpoint",
        "format_schema_sha256",
        "instruction_sha256",
        "keep_alive",
        "logprobs",
        "num_ctx",
        "num_gpu",
        "num_predict",
        "ollama_server_version",
        "operator_expected_model_digest",
        "provider_payload_sha256",
        "raw",
        "require_full_gpu",
        "shift",
        "stream",
        "temperature",
        "think",
        "truncate",
    }
    expected_values = {
        "allow_remote": profile.allow_remote,
        "calibration_policy_id": profile.calibration_policy_id,
        "endpoint": f"{profile.base_url}/api/generate",
        "format_schema_sha256": profile.output_schema_sha256,
        "instruction_sha256": profile.instruction_sha256,
        "keep_alive": profile.keep_alive,
        "logprobs": False,
        "num_ctx": profile.num_ctx,
        "num_gpu": profile.num_gpu,
        "num_predict": profile.num_predict,
        "operator_expected_model_digest": profile.model_digest,
        "raw": False,
        "require_full_gpu": profile.require_full_gpu,
        "shift": False,
        "stream": False,
        "temperature": profile.temperature,
        "think": False,
        "truncate": False,
    }
    if set(values) != expected_names or any(
        values[name] != expected for name, expected in expected_values.items()
    ):
        raise ValueError("Official C3 result call parameters differ from profile")
    if (
        not _is_hash(values["calibration_constraints_sha256"])
        or not _is_hash(values["provider_payload_sha256"])
        or not isinstance(values["ollama_server_version"], str)
        or not values["ollama_server_version"].strip()
    ):
        raise ValueError("Official C3 result dynamic call parameters are invalid")


def _validate_published_suite(
    *,
    reservation: ReservedOutputRoot,
    child_name: Literal["holdout", "regression"],
    suite: C3BenchmarkSuite,
    outcome: C3OfficialSuiteOutcome,
    source_commit: str,
    profile: C3OfficialPairProfile,
    registry_sha256: str,
    candidate: RacioInterpreterModelCandidate,
    provider_identity: ProviderIdentity,
) -> None:
    output_root = reservation.validate()
    child = output_root / child_name
    child_anchor = reservation.require_child(child_name)
    expected_files = {
        "baseline_results.jsonl",
        "failures.jsonl",
        "metrics.json",
        "provenance.json",
        "results.jsonl",
        "suite_outcome.json",
    }
    if child_anchor.list_names() != expected_files:
        raise ValueError(f"Official C3 {child_name} artifact set differs")
    cold_outcome = _read_canonical_model(
        child / "suite_outcome.json",
        model_type=C3OfficialSuiteOutcome,
        maximum_bytes=64 * 1024,
        label=f"Official C3 {child_name} outcome",
        parent_anchor=child_anchor,
    )
    if cold_outcome != outcome or outcome.child_directory != _recorded_path(child):
        raise ValueError(f"Official C3 {child_name} outcome differs from publication")

    provenance_path = child / "provenance.json"
    provenance = _read_canonical_model(
        provenance_path,
        model_type=C3BenchmarkRunProvenance,
        maximum_bytes=2 * 1024 * 1024,
        label=f"Official C3 {child_name} provenance",
        expected_sha256=outcome.child_provenance_sha256,
        parent_anchor=child_anchor,
    )
    if (
        provenance.run_id != outcome.run_id
        or provenance.source_commit != source_commit
        or provenance.provider_mode != "ollama"
        or provenance.benchmark_id != outcome.benchmark_id
        or provenance.benchmark_id != suite.manifest.benchmark_id
        or provenance.benchmark_manifest_hash != suite.manifest_file_hash
        or provenance.public_cases_hash != suite.manifest.files[0].sha256
        or provenance.gold_hash != suite.manifest.files[1].sha256
        or provenance.model_call_count != 32
        or provenance.failure_count != outcome.failure_count
        or provenance.registry_path
        != _recorded_path(RACIO_INTERPRETER_MODEL_REGISTRY_PATH)
        or provenance.registry_sha256 != registry_sha256
        or provenance.model_candidate != candidate
        or provenance.quality_gate_pass != outcome.quality_gate_pass
        or provenance.baseline_results_sha256 is None
        or provenance.failures_sha256 is None
    ):
        raise ValueError(f"Official C3 {child_name} provenance closure differs")

    results_path = child / "results.jsonl"
    baseline_path = child / "baseline_results.jsonl"
    failures_path = child / "failures.jsonl"
    metrics_path = child / "metrics.json"
    results = _read_canonical_jsonl(
        results_path,
        model_type=C3BenchmarkCaseResult,
        maximum_bytes=64 * 1024 * 1024,
        label=f"Official C3 {child_name} results",
        expected_sha256=provenance.results_sha256,
        parent_anchor=child_anchor,
    )
    baseline = _read_canonical_jsonl(
        baseline_path,
        model_type=C3BenchmarkCaseResult,
        maximum_bytes=32 * 1024 * 1024,
        label=f"Official C3 {child_name} baseline",
        expected_sha256=provenance.baseline_results_sha256,
        parent_anchor=child_anchor,
    )
    failures = _read_canonical_jsonl(
        failures_path,
        model_type=C3FailureEvidence,
        maximum_bytes=16 * 1024 * 1024,
        label=f"Official C3 {child_name} failures",
        allow_empty=True,
        expected_sha256=provenance.failures_sha256,
        parent_anchor=child_anchor,
    )
    metrics = _read_canonical_model(
        metrics_path,
        model_type=C3BenchmarkRunMetrics,
        maximum_bytes=256 * 1024,
        label=f"Official C3 {child_name} metrics",
        expected_sha256=provenance.metrics_sha256,
        parent_anchor=child_anchor,
    )
    recomputed = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="ollama",
        results=results,
        model_call_count=32,
        baseline_results=baseline,
    )
    if (
        len(results) != 32
        or len(baseline) != 32
        or recomputed != metrics
        or metrics.passed_case_count != outcome.passed_case_count
        or metrics.quality_gate_pass != outcome.quality_gate_pass
        or len(failures) != outcome.failure_count
    ):
        raise ValueError(f"Official C3 {child_name} metrics differ from evidence")
    _validate_failure_closure(
        run_id=outcome.run_id,
        metrics=metrics,
        results=results,
        registry_path=RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
        candidate=candidate,
        failures=failures,
    )
    for result in results:
        _validate_result_profile(
            result=result,
            profile=profile,
            provider_identity=provider_identity,
        )


def _validate_pair_evidence_closure(
    *,
    reservation: ReservedOutputRoot,
    source_commit: str,
    attempt_ledger_sha256: str,
    profile: C3OfficialPairProfile,
    registry_sha256: str,
    candidate: RacioInterpreterModelCandidate,
    provider_identity: ProviderIdentity,
    outcomes: tuple[C3OfficialSuiteOutcome, C3OfficialSuiteOutcome],
    allowed_final_staging: str | None = None,
) -> None:
    output_root = reservation.validate()
    root_anchor = reservation.ensure_anchor()
    expected_names = {
        "attempt_ledger.json",
        "holdout",
        "regression",
    }
    if allowed_final_staging is not None:
        if not allowed_final_staging.startswith(".pair_provenance.json.tmp-"):
            raise ValueError("Official C3 final staging name differs")
        expected_names.add(allowed_final_staging)
    if root_anchor.list_names() != expected_names:
        raise ValueError("Official C3 pre-final artifact set differs")
    ledger_path = output_root / "attempt_ledger.json"
    ledger = _read_canonical_model(
        ledger_path,
        model_type=C3OfficialPairAttemptLedger,
        maximum_bytes=256 * 1024,
        label="Official C3 attempt ledger",
        expected_sha256=attempt_ledger_sha256,
        parent_anchor=root_anchor,
    )
    holdout, regression = load_official_c3_suite_pair()
    if (
        ledger.pair_id != PAIR_ID
        or ledger.source_commit != source_commit
        or ledger.protocol_freeze_commit != PROTOCOL_FREEZE_COMMIT
        or ledger.profile != profile
        or ledger.suite_order != _suite_descriptors(holdout, regression)
        or ledger.provider_instance_count != 1
        or ledger.planned_provider_case_attempt_count != 64
    ):
        raise ValueError("Official C3 attempt ledger contract differs")
    expected_outcomes = (
        ("holdout", holdout, outcomes[0]),
        ("regression", regression, outcomes[1]),
    )
    for child_name, suite, outcome in expected_outcomes:
        _validate_published_suite(
            reservation=reservation,
            child_name=child_name,
            suite=suite,
            outcome=outcome,
            source_commit=source_commit,
            profile=profile,
            registry_sha256=registry_sha256,
            candidate=candidate,
            provider_identity=provider_identity,
        )


def write_final_pair_provenance(
    *,
    output_root: ReservedOutputRoot,
    source_commit: str,
    attempt_ledger_sha256: str,
    profile: C3OfficialPairProfile,
    registry_sha256: str,
    candidate: RacioInterpreterModelCandidate,
    provider_identity: ProviderIdentity,
    outcomes: tuple[C3OfficialSuiteOutcome, C3OfficialSuiteOutcome],
) -> C3OfficialPairProvenance:
    reserved_path = output_root.validate()
    _validate_pair_evidence_closure(
        reservation=output_root,
        source_commit=source_commit,
        attempt_ledger_sha256=attempt_ledger_sha256,
        profile=profile,
        registry_sha256=registry_sha256,
        candidate=candidate,
        provider_identity=provider_identity,
        outcomes=outcomes,
    )
    verify_execution_state(
        source_commit=source_commit,
        registry_sha256=registry_sha256,
    )
    dispatch_count = sum(item.api_generate_dispatch_count for item in outcomes)
    provenance = C3OfficialPairProvenance(
        schema_version="rei-c3-official-pair-provenance-v1",
        pair_id=PAIR_ID,
        source_commit=source_commit,
        protocol_freeze_commit=PROTOCOL_FREEZE_COMMIT,
        completed_at=utc_now(),
        attempt_ledger_sha256=attempt_ledger_sha256,
        profile=profile,
        registry_path=_recorded_path(RACIO_INTERPRETER_MODEL_REGISTRY_PATH),
        registry_sha256=registry_sha256,
        model_candidate=candidate,
        provider_identity=provider_identity,
        provider_instance_count=1,
        provider_case_attempt_count=OFFICIAL_PROVIDER_CASE_ATTEMPTS,
        api_generate_dispatch_count=dispatch_count,
        suite_outcomes=outcomes,
        quality_gate_pass=all(item.quality_gate_pass for item in outcomes),
    )
    cold = C3OfficialPairProvenance.model_validate_json(
        canonical_json_bytes(provenance)
    )
    if cold != provenance:
        raise ValueError("Official C3 pair provenance differs after cold validation")
    final_path = reserved_path / "pair_provenance.json"
    root_anchor = output_root.ensure_anchor()

    def close_evidence_immediately_before_publish(temporary_name: str) -> None:
        output_root.validate()
        verify_execution_state(
            source_commit=source_commit,
            registry_sha256=registry_sha256,
        )
        _validate_pair_evidence_closure(
            reservation=output_root,
            source_commit=source_commit,
            attempt_ledger_sha256=attempt_ledger_sha256,
            profile=profile,
            registry_sha256=registry_sha256,
            candidate=candidate,
            provider_identity=provider_identity,
            outcomes=outcomes,
            allowed_final_staging=temporary_name,
        )

    _write_anchored_atomic(
        parent=root_anchor,
        destination_name=final_path.name,
        payload=canonical_json_bytes(provenance) + b"\n",
        label="Official C3 final pair provenance",
        pre_publish=close_evidence_immediately_before_publish,
    )
    output_root.validate()
    cold_disk = _read_canonical_model(
        final_path,
        model_type=C3OfficialPairProvenance,
        maximum_bytes=2 * 1024 * 1024,
        label="Official C3 pair provenance",
        parent_anchor=root_anchor,
    )
    if cold_disk != provenance:
        raise ValueError("Official C3 final provenance changed during publication")
    if root_anchor.list_names() != {
        "attempt_ledger.json",
        "holdout",
        "regression",
        "pair_provenance.json",
    }:
        raise ValueError("Official C3 final artifact set differs")
    output_root.close()
    return provenance


def run_official_pair(*, bootstrap_source_commit: str) -> C3OfficialPairProvenance:
    source_commit = scoped_source_commit(
        bootstrap_source_commit=bootstrap_source_commit
    )
    profile = frozen_profile_from_environment()
    holdout, regression, candidate, registry_sha256 = validate_frozen_contract(
        source_commit=source_commit
    )

    # Both model-free baselines are completed before output reservation and the
    # one provider discovery.  They cannot observe or depend on model output.
    holdout_baseline = deterministic_results(holdout)
    regression_baseline = deterministic_results(regression)
    descriptors = _suite_descriptors(holdout, regression)
    output_root, _ledger, ledger_sha256 = reserve_output_root(
        source_commit=source_commit,
        profile=profile,
        descriptors=descriptors,
    )

    try:
        provider, transport = build_official_provider(
            profile=profile,
            candidate=candidate,
        )
        verify_execution_state(
            source_commit=source_commit,
            registry_sha256=registry_sha256,
        )
        holdout_outcome = execute_and_publish_suite(
            output_root=output_root,
            suite_role="untouched_holdout",
            child_name="holdout",
            run_id=f"{PAIR_ID}-holdout",
            manifest_path=HOLDOUT_MANIFEST_PATH,
            suite=holdout,
            baseline_results=holdout_baseline,
            provider=provider,
            transport=transport,
            candidate=candidate,
            source_commit=source_commit,
            registry_sha256=registry_sha256,
        )
        # This call is unconditional: a false holdout quality gate is evidence,
        # not permission to skip the frozen regression half of the official pair.
        regression_outcome = execute_and_publish_suite(
            output_root=output_root,
            suite_role="frozen_regression",
            child_name="regression",
            run_id=f"{PAIR_ID}-regression",
            manifest_path=MANIFEST_PATH,
            suite=regression,
            baseline_results=regression_baseline,
            provider=provider,
            transport=transport,
            candidate=candidate,
            source_commit=source_commit,
            registry_sha256=registry_sha256,
        )
        verify_execution_state(
            source_commit=source_commit,
            registry_sha256=registry_sha256,
        )
        return write_final_pair_provenance(
            output_root=output_root,
            source_commit=source_commit,
            attempt_ledger_sha256=ledger_sha256,
            profile=profile,
            registry_sha256=registry_sha256,
            candidate=candidate,
            provider_identity=provider.identity,
            outcomes=(holdout_outcome, regression_outcome),
        )
    finally:
        output_root.close()


def main(
    argv: list[str] | None = None,
    *,
    bootstrap_source_commit: str,
) -> int:
    parse_args(argv)
    provenance = run_official_pair(bootstrap_source_commit=bootstrap_source_commit)
    summary = {
        "api_generate_dispatch_count": provenance.api_generate_dispatch_count,
        "output_root": str(OFFICIAL_OUTPUT_ROOT.resolve()),
        "quality_gate_pass": provenance.quality_gate_pass,
        "regression_quality_gate_pass": (
            provenance.suite_outcomes[1].quality_gate_pass
        ),
        "holdout_quality_gate_pass": provenance.suite_outcomes[0].quality_gate_pass,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if provenance.quality_gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(
        "Use scripts/run_c3_racio_official_pair.py so stdlib preflight runs first."
    )
