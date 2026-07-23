"""Restart-safe, model-free preparation for the bounded C4 Stage 1 screen.

The module creates the last durable boundary before any image editor can be
started.  Local executable, snapshot and source paths are runtime-only.  Every
portable input, policy and request is content-addressed, written create-only,
and cold-verified from an exact run inventory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Annotated, Callable, Literal, Mapping, Protocol, Self

from pydantic import Field, model_validator

from ..emocio.c4_stage1_editor import (
    C4_STAGE1_MAX_PNG_BYTES,
    C4_STAGE1_MAX_SNAPSHOT_FILES,
    C4_STAGE1_OPTION_SCENE_IDS,
    C4Stage1DependencyVersions,
    C4Stage1EditorSpec,
    C4Stage1LocalSnapshotBinding,
    C4Stage1WorkerRequest,
    VerifiedC4Stage1Snapshot,
    inspect_c4_stage1_png_bytes,
    verify_c4_stage1_snapshot,
)
from ..emocio.diffusers_renderer import (
    DiffusersSnapshotManifest,
    canonical_snapshot_manifest_bytes,
)
from ..emocio.dinov2_encoder import dinov2_base_provider_identity
from ..emocio.longcat_turbo_editor import (
    LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256,
    build_longcat_turbo_worker_request,
    longcat_turbo_stage1_spec,
)
from ..emocio.omnigen_editor import (
    OMNIGEN_SNAPSHOT_MANIFEST_SHA256,
    build_omnigen_worker_request,
    omnigen_stage1_spec,
)
from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    CommitDigest,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
)
from ..persistence.artifacts import FileArtifactStore
from ..providers.protocols import StoredArtifact
from .c4_blind_review import (
    C4BlindHumanReviewSchema,
    C4HumanReviewOperatorPolicy,
    build_c4_blind_human_review_schema,
    build_c4_human_review_operator_policy,
)
from .c4_stage1_fixture import C4Stage1Fixture, build_c4_stage1_fixture
from .c4_stage1_review import (
    C4Stage1DisplayAttesterPolicy,
    build_c4_stage1_display_attester_policy,
    c4_stage1_display_policy_content_pin,
)
from .c4_stage1_review_runtime import (
    C4Stage1ReviewRuntimeManifest,
    verify_c4_stage1_review_runtime_manifest,
)
from .c4_stage1_review_service import C4Stage1ReviewServiceReadiness
from .c4_stage1_screen import (
    C4_STAGE1_ADDENDUM_PATH,
    C4_STAGE1_ALTERNATE_SNAPSHOT_MANIFEST_PATH,
    C4_STAGE1_PRIMARY_SNAPSHOT_MANIFEST_PATH,
    C4_STAGE1_PROTOCOL_PATH,
    C4Stage1ContentPin,
    C4Stage1DinoPolicy,
    C4Stage1DocumentPin,
    C4Stage1ScreenContract,
    C4Stage1SourcePin,
    normalized_utf8_document_bytes,
)
from .c4_stage1_telemetry import (
    C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES,
    C4_STAGE1_TELEMETRY_CADENCE_SECONDS,
    C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS,
    C4_STAGE1_TELEMETRY_MAX_SAMPLES,
    C4Stage1TelemetryPolicy,
    c4_stage1_telemetry_policy,
)
from .resource_telemetry import ResourceTelemetryCudaDeviceIdentity


C4_STAGE1_CUDA_STOP_BYTES = C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES
C4_STAGE1_PREPARED_ANCHOR_PATH = "diagnostics/c4_stage1_prepared_attempt.json"
C4_STAGE1_BOOTSTRAP_SCRIPT_PATH = "scripts/run_rei_c4_stage1_bootstrap.py"
C4_STAGE1_WORKER_SCRIPT_PATH = "scripts/run_rei_c4_stage1_worker.py"
C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH = (
    "scripts/run_rei_c4_stage1_dino_bootstrap.py"
)
C4_STAGE1_DINO_WORKER_SCRIPT_PATH = "scripts/run_rei_c4_stage1_dino_worker.py"
C4_STAGE1_ORIGIN_URL = "https://github.com/kotlet13/rei-v3.git"
C4_STAGE1_GIT_SCOPE_PATHS = (
    "app/backend/rei",
    ":(glob)scripts/run_rei_c4_stage1*.py",
    ":(glob)tests/evaluation/test_c4_stage1*.py",
    "tests/evaluation/test_process_tree_runner.py",
    "tests/evaluation/test_resource_telemetry.py",
    ":(glob)tests/rei/test_c4_stage1*.py",
    C4_STAGE1_PROTOCOL_PATH,
    C4_STAGE1_ADDENDUM_PATH,
    C4_STAGE1_PRIMARY_SNAPSHOT_MANIFEST_PATH,
    C4_STAGE1_ALTERNATE_SNAPSHOT_MANIFEST_PATH,
)
C4_STAGE1_FIXED_WORKER_ENVIRONMENT = (
    ("CUDA_DEVICE_ORDER", "PCI_BUS_ID"),
    ("DIFFUSERS_OFFLINE", "1"),
    ("HF_HUB_OFFLINE", "1"),
    ("PYTHONDONTWRITEBYTECODE", "1"),
    ("PYTHONUTF8", "1"),
    ("TOKENIZERS_PARALLELISM", "false"),
    ("TRANSFORMERS_OFFLINE", "1"),
)
C4_STAGE1_INHERITED_WORKER_ENVIRONMENT_NAMES = (
    "APPDATA",
    "CUDA_PATH",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
)

_MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
_MAX_PROVENANCE_BYTES = 4 * 1024 * 1024
_MAX_WORKER_SCRIPT_BYTES = 4 * 1024 * 1024
_MAX_WORKER_PYTHON_BYTES = 64 * 1024 * 1024
_MAX_GIT_EXECUTABLE_BYTES = 64 * 1024 * 1024
_MAX_WORKER_METADATA_BYTES = 32 * 1024
_MAX_RUNTIME_INVENTORY_FILES = 2_000_000
_MAX_RUNTIME_INVENTORY_DIRECTORIES = 500_000
_MAX_RUNTIME_INVENTORY_BYTES = 128 * 1024 * 1024 * 1024
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_WORKER_RUNTIME_PROBE_POLICY = "isolated-no-site-explicit-distribution-path-v2"
_WORKER_RUNTIME_INVENTORY_POLICY = "complete-venv-and-base-runtime-streaming-sha256-v1"
_STAGING_PARENT_POLICY = "unlinked-ancestry-fresh-child-root-v1"
_DINO_GIT_SCOPE_PATHSPEC = ":(glob)scripts/run_rei_c4_stage1*.py"
_MODULE_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_WORKER_RUNTIME_DISTRIBUTIONS = (
    ("torch", "torch"),
    ("diffusers", "diffusers"),
    ("transformers", "transformers"),
    ("accelerate", "accelerate"),
    ("safetensors", "safetensors"),
    ("pillow", "Pillow"),
)


class C4Stage1PreparationError(RuntimeError):
    """A sanitized pre-inference boundary failed closed."""


class C4Stage1ColdVerificationError(RuntimeError):
    """A prepared attempt no longer matches its durable exact inventory."""


class C4Stage1GitRuntimePin(FrozenArtifactModel):
    """Path-free identity of the trusted Git executable used by the gate."""

    schema_version: Literal["rei-c4-stage1-git-runtime-pin-v1"] = (
        "rei-c4-stage1-git-runtime-pin-v1"
    )
    git_runtime_id: NonEmptyId
    git_runtime_sha256: HashDigest
    git_executable_sha256: HashDigest
    git_executable_size_bytes: Annotated[int, Field(gt=0, le=_MAX_GIT_EXECUTABLE_BYTES)]
    git_version: NonEmptyId
    trusted_location_class: Literal[
        "windows-program-files-git-bin",
        "posix-usr-bin-git",
    ]
    trusted_location_policy: Literal[
        "fixed-platform-location-ordinary-non-reparse-v1"
    ] = "fixed-platform-location-ordinary-non-reparse-v1"
    executable_ancestry_non_reparse_verified: Literal[True] = True
    executable_regular_non_reparse_verified: Literal[True] = True
    executable_path_stored: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        git_executable_sha256: str,
        git_executable_size_bytes: int,
        git_version: str,
        trusted_location_class: Literal[
            "windows-program-files-git-bin",
            "posix-usr-bin-git",
        ],
    ) -> C4Stage1GitRuntimePin:
        if not git_version.startswith("git version ") or any(
            ord(character) < 32 for character in git_version
        ):
            raise ValueError("Stage 1 Git version identity is invalid")
        body = {
            "schema_version": "rei-c4-stage1-git-runtime-pin-v1",
            "git_executable_sha256": git_executable_sha256,
            "git_executable_size_bytes": git_executable_size_bytes,
            "git_version": git_version,
            "trusted_location_class": trusted_location_class,
            "trusted_location_policy": (
                "fixed-platform-location-ordinary-non-reparse-v1"
            ),
            "executable_ancestry_non_reparse_verified": True,
            "executable_regular_non_reparse_verified": True,
            "executable_path_stored": False,
        }
        return cls(
            git_runtime_id=content_id("c4_stage1_git_runtime", body),
            git_runtime_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_git_runtime(self) -> Self:
        if not self.git_version.startswith("git version ") or any(
            ord(character) < 32 for character in self.git_version
        ):
            raise ValueError("Stage 1 Git version identity is invalid")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"git_runtime_id", "git_runtime_sha256"},
        )
        if self.git_runtime_id != content_id(
            "c4_stage1_git_runtime", body
        ) or self.git_runtime_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 Git runtime differs from canonical content")
        return self


class C4Stage1RepositoryGate(FrozenArtifactModel):
    """Proof that the inference boundary is committed and present on main."""

    schema_version: Literal["rei-c4-stage1-repository-gate-v1"] = (
        "rei-c4-stage1-repository-gate-v1"
    )
    repository_gate_id: NonEmptyId
    repository_gate_sha256: HashDigest
    git_runtime: C4Stage1GitRuntimePin
    origin_url: Literal["https://github.com/kotlet13/rei-v3.git"] = C4_STAGE1_ORIGIN_URL
    branch: Literal["main"] = "main"
    head_commit: CommitDigest
    local_origin_main_commit: CommitDigest
    remote_origin_main_commit: CommitDigest
    scoped_paths: tuple[str, ...] = C4_STAGE1_GIT_SCOPE_PATHS
    scoped_worktree_clean: Literal[True] = True
    local_and_remote_main_equal_head: Literal[True] = True
    remote_origin_queried_live: Literal[True] = True
    tracked_scope_flags_verified: Literal[True] = True
    skip_worktree_or_assume_unchanged_allowed: Literal[False] = False
    unrelated_worktree_changes_allowed: Literal[True] = True
    pull_request_or_feature_branch_required: Literal[False] = False
    force_push_allowed: Literal[False] = False
    model_calls_before_gate: Literal[0] = 0

    @classmethod
    def create(
        cls,
        *,
        git_runtime: C4Stage1GitRuntimePin,
        head_commit: str,
        local_origin_main_commit: str,
        remote_origin_main_commit: str,
    ) -> C4Stage1RepositoryGate:
        if not (head_commit == local_origin_main_commit == remote_origin_main_commit):
            raise ValueError(
                "Stage 1 requires HEAD, origin/main and remote main to match"
            )
        git_runtime = C4Stage1GitRuntimePin.model_validate(
            git_runtime.model_dump(mode="python", round_trip=True)
        )
        body = {
            "schema_version": "rei-c4-stage1-repository-gate-v1",
            "git_runtime": git_runtime,
            "origin_url": C4_STAGE1_ORIGIN_URL,
            "branch": "main",
            "head_commit": head_commit,
            "local_origin_main_commit": local_origin_main_commit,
            "remote_origin_main_commit": remote_origin_main_commit,
            "scoped_paths": C4_STAGE1_GIT_SCOPE_PATHS,
            "scoped_worktree_clean": True,
            "local_and_remote_main_equal_head": True,
            "remote_origin_queried_live": True,
            "tracked_scope_flags_verified": True,
            "skip_worktree_or_assume_unchanged_allowed": False,
            "unrelated_worktree_changes_allowed": True,
            "pull_request_or_feature_branch_required": False,
            "force_push_allowed": False,
            "model_calls_before_gate": 0,
        }
        return cls(
            repository_gate_id=content_id("c4_stage1_repository_gate", body),
            repository_gate_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_gate(self) -> Self:
        C4Stage1GitRuntimePin.model_validate(
            self.git_runtime.model_dump(mode="python", round_trip=True)
        )
        if not (
            self.head_commit
            == self.local_origin_main_commit
            == self.remote_origin_main_commit
        ):
            raise ValueError("Stage 1 repository refs are no longer equal")
        if self.scoped_paths != C4_STAGE1_GIT_SCOPE_PATHS:
            raise ValueError("Stage 1 repository gate omits a controlling path")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"repository_gate_id", "repository_gate_sha256"},
        )
        if self.repository_gate_id != content_id(
            "c4_stage1_repository_gate", body
        ) or self.repository_gate_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 repository gate differs from canonical content")
        return self


class C4Stage1DinoEntrypointScriptPin(FrozenModel):
    """One exact committed DINO entrypoint copied into pre-output evidence."""

    role: Literal["dino-bootstrap", "dino-worker"]
    repository_relative_path: Literal[
        "scripts/run_rei_c4_stage1_dino_bootstrap.py",
        "scripts/run_rei_c4_stage1_dino_worker.py",
    ]
    content_sha256: HashDigest
    size_bytes: Annotated[int, Field(gt=0, le=_MAX_WORKER_SCRIPT_BYTES)]

    @classmethod
    def create(
        cls,
        *,
        role: Literal["dino-bootstrap", "dino-worker"],
        payload: bytes,
    ) -> C4Stage1DinoEntrypointScriptPin:
        if type(payload) is not bytes or not payload:
            raise TypeError("Stage 1 DINO entrypoint must be non-empty exact bytes")
        if len(payload) > _MAX_WORKER_SCRIPT_BYTES:
            raise ValueError("Stage 1 DINO entrypoint exceeds its fixed byte bound")
        relative_path = (
            C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH
            if role == "dino-bootstrap"
            else C4_STAGE1_DINO_WORKER_SCRIPT_PATH
        )
        return cls(
            role=role,
            repository_relative_path=relative_path,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )

    @model_validator(mode="after")
    def validate_script_pin(self) -> Self:
        expected_path = (
            C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH
            if self.role == "dino-bootstrap"
            else C4_STAGE1_DINO_WORKER_SCRIPT_PATH
        )
        if self.repository_relative_path != expected_path:
            raise ValueError("Stage 1 DINO entrypoint role differs from its path")
        return self


class C4Stage1DinoEntrypointPin(FrozenArtifactModel):
    """Path-free Git-gate binding for the exact DINO bootstrap and worker."""

    schema_version: Literal["rei-c4-stage1-dino-entrypoint-pin-v1"] = (
        "rei-c4-stage1-dino-entrypoint-pin-v1"
    )
    dino_entrypoint_pin_id: NonEmptyId
    dino_entrypoint_pin_sha256: HashDigest
    repository_gate_id: NonEmptyId
    repository_gate_sha256: HashDigest
    repository_head_commit: CommitDigest
    git_scope_pathspec: Literal[":(glob)scripts/run_rei_c4_stage1*.py"] = (
        _DINO_GIT_SCOPE_PATHSPEC
    )
    scripts: tuple[
        C4Stage1DinoEntrypointScriptPin,
        C4Stage1DinoEntrypointScriptPin,
    ]
    exact_committed_worktree_bytes_pinned: Literal[True] = True
    create_only_prepared_copies_required: Literal[True] = True
    local_paths_stored: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        repository_gate: C4Stage1RepositoryGate,
        bootstrap_script: bytes,
        worker_script: bytes,
    ) -> C4Stage1DinoEntrypointPin:
        repository_gate = C4Stage1RepositoryGate.model_validate(
            repository_gate.model_dump(mode="python", round_trip=True)
        )
        if _DINO_GIT_SCOPE_PATHSPEC not in repository_gate.scoped_paths:
            raise ValueError("Stage 1 repository gate omits DINO entrypoints")
        scripts = (
            C4Stage1DinoEntrypointScriptPin.create(
                role="dino-bootstrap",
                payload=bootstrap_script,
            ),
            C4Stage1DinoEntrypointScriptPin.create(
                role="dino-worker",
                payload=worker_script,
            ),
        )
        body = {
            "schema_version": "rei-c4-stage1-dino-entrypoint-pin-v1",
            "repository_gate_id": repository_gate.repository_gate_id,
            "repository_gate_sha256": repository_gate.repository_gate_sha256,
            "repository_head_commit": repository_gate.head_commit,
            "git_scope_pathspec": _DINO_GIT_SCOPE_PATHSPEC,
            "scripts": scripts,
            "exact_committed_worktree_bytes_pinned": True,
            "create_only_prepared_copies_required": True,
            "local_paths_stored": False,
        }
        return cls(
            dino_entrypoint_pin_id=content_id("c4_stage1_dino_entrypoint", body),
            dino_entrypoint_pin_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_entrypoint_pin(self) -> Self:
        if (
            tuple(item.role for item in self.scripts)
            != ("dino-bootstrap", "dino-worker")
            or tuple(item.repository_relative_path for item in self.scripts)
            != (
                C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH,
                C4_STAGE1_DINO_WORKER_SCRIPT_PATH,
            )
        ):
            raise ValueError("Stage 1 DINO entrypoint inventory is not exact")
        for script in self.scripts:
            C4Stage1DinoEntrypointScriptPin.model_validate(
                script.model_dump(mode="python", round_trip=True)
            )
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"dino_entrypoint_pin_id", "dino_entrypoint_pin_sha256"},
        )
        if self.dino_entrypoint_pin_id != content_id(
            "c4_stage1_dino_entrypoint", body
        ) or self.dino_entrypoint_pin_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 DINO entrypoint pin differs from content")
        return self


class C4Stage1RuntimeTreeInventoryPin(FrozenModel):
    """Path-free exact-byte identity of one complete runtime tree."""

    schema_version: Literal["rei-c4-stage1-runtime-tree-inventory-pin-v1"] = (
        "rei-c4-stage1-runtime-tree-inventory-pin-v1"
    )
    tree_role: Literal["worker-venv", "base-runtime"]
    tree_content_sha256: HashDigest
    file_count: Annotated[int, Field(gt=0, le=_MAX_RUNTIME_INVENTORY_FILES)]
    directory_count: Annotated[int, Field(gt=0, le=_MAX_RUNTIME_INVENTORY_DIRECTORIES)]
    total_size_bytes: Annotated[int, Field(gt=0, le=_MAX_RUNTIME_INVENTORY_BYTES)]
    pth_file_count: Annotated[int, Field(ge=0, le=_MAX_RUNTIME_INVENTORY_FILES)]
    inventory_policy: Literal[
        "stable-streaming-sha256-all-regular-files-and-directories-v1"
    ] = "stable-streaming-sha256-all-regular-files-and-directories-v1"
    relative_names_committed_in_digest: Literal[True] = True
    relative_names_stored: Literal[False] = False
    root_path_stored: Literal[False] = False
    regular_files_only: Literal[True] = True
    links_reparse_points_and_hardlinks_allowed: Literal[False] = False
    sitecustomize_or_usercustomize_allowed: Literal[False] = False
    pth_files_included_in_digest: Literal[True] = True
    pth_files_executed: Literal[False] = False


class C4Stage1WorkerRuntimePin(FrozenArtifactModel):
    """Path-free identity of the exact external Python worker runtime."""

    schema_version: Literal["rei-c4-stage1-worker-runtime-pin-v2"] = (
        "rei-c4-stage1-worker-runtime-pin-v2"
    )
    worker_runtime_id: NonEmptyId
    worker_runtime_sha256: HashDigest
    worker_python_sha256: HashDigest
    worker_python_size_bytes: Annotated[int, Field(gt=0, le=_MAX_WORKER_PYTHON_BYTES)]
    python_implementation: Literal["CPython"] = "CPython"
    python_full_version: NonEmptyId
    dependencies: C4Stage1DependencyVersions
    metadata_probe_policy: Literal["isolated-no-site-explicit-distribution-path-v2"] = (
        _WORKER_RUNTIME_PROBE_POLICY
    )
    worker_venv_inventory: C4Stage1RuntimeTreeInventoryPin
    base_runtime_inventory: C4Stage1RuntimeTreeInventoryPin
    runtime_inventory_policy: Literal[
        "complete-venv-and-base-runtime-streaming-sha256-v1"
    ] = _WORKER_RUNTIME_INVENTORY_POLICY
    runtime_inventory_sha256: HashDigest
    runtime_inventory_file_count: Annotated[
        int, Field(gt=0, le=2 * _MAX_RUNTIME_INVENTORY_FILES)
    ]
    runtime_inventory_directory_count: Annotated[
        int, Field(gt=0, le=2 * _MAX_RUNTIME_INVENTORY_DIRECTORIES)
    ]
    runtime_inventory_size_bytes: Annotated[
        int, Field(gt=0, le=2 * _MAX_RUNTIME_INVENTORY_BYTES)
    ]
    runtime_tree_count: Literal[2] = 2
    runtime_paths_stored: Literal[False] = False
    site_activation_disabled: Literal[True] = True
    explicit_distribution_discovery: Literal[True] = True
    runtime_customization_modules_rejected: Literal[True] = True
    pth_files_never_executed: Literal[True] = True
    complete_runtime_trees_inventory_verified: Literal[True] = True
    inventory_recapture_required_before_every_spawn: Literal[True] = True
    isolated_interpreter_probe: Literal[True] = True
    model_packages_imported_in_parent: Literal[False] = False
    worker_python_path_stored: Literal[False] = False
    network_access_required: Literal[False] = False
    runtime_reverification_required_before_spawn: Literal[True] = True
    model_calls_before_runtime_pin: Literal[0] = 0

    @classmethod
    def create(
        cls,
        *,
        worker_python_sha256: str,
        worker_python_size_bytes: int,
        python_full_version: str,
        dependencies: C4Stage1DependencyVersions,
        worker_venv_inventory: C4Stage1RuntimeTreeInventoryPin,
        base_runtime_inventory: C4Stage1RuntimeTreeInventoryPin,
    ) -> C4Stage1WorkerRuntimePin:
        dependencies = C4Stage1DependencyVersions.model_validate(
            dependencies.model_dump(mode="python", round_trip=True)
        )
        worker_venv_inventory = C4Stage1RuntimeTreeInventoryPin.model_validate(
            worker_venv_inventory.model_dump(mode="python", round_trip=True)
        )
        base_runtime_inventory = C4Stage1RuntimeTreeInventoryPin.model_validate(
            base_runtime_inventory.model_dump(mode="python", round_trip=True)
        )
        if (
            worker_venv_inventory.tree_role != "worker-venv"
            or base_runtime_inventory.tree_role != "base-runtime"
        ):
            raise ValueError("Stage 1 runtime inventories have the wrong roles")
        runtime_inventory_body = {
            "policy": _WORKER_RUNTIME_INVENTORY_POLICY,
            "worker_venv_inventory": worker_venv_inventory,
            "base_runtime_inventory": base_runtime_inventory,
        }
        body = {
            "schema_version": "rei-c4-stage1-worker-runtime-pin-v2",
            "worker_python_sha256": worker_python_sha256,
            "worker_python_size_bytes": worker_python_size_bytes,
            "python_implementation": "CPython",
            "python_full_version": python_full_version,
            "dependencies": dependencies,
            "metadata_probe_policy": _WORKER_RUNTIME_PROBE_POLICY,
            "worker_venv_inventory": worker_venv_inventory,
            "base_runtime_inventory": base_runtime_inventory,
            "runtime_inventory_policy": _WORKER_RUNTIME_INVENTORY_POLICY,
            "runtime_inventory_sha256": _canonical_sha256(runtime_inventory_body),
            "runtime_inventory_file_count": (
                worker_venv_inventory.file_count + base_runtime_inventory.file_count
            ),
            "runtime_inventory_directory_count": (
                worker_venv_inventory.directory_count
                + base_runtime_inventory.directory_count
            ),
            "runtime_inventory_size_bytes": (
                worker_venv_inventory.total_size_bytes
                + base_runtime_inventory.total_size_bytes
            ),
            "runtime_tree_count": 2,
            "runtime_paths_stored": False,
            "site_activation_disabled": True,
            "explicit_distribution_discovery": True,
            "runtime_customization_modules_rejected": True,
            "pth_files_never_executed": True,
            "complete_runtime_trees_inventory_verified": True,
            "inventory_recapture_required_before_every_spawn": True,
            "isolated_interpreter_probe": True,
            "model_packages_imported_in_parent": False,
            "worker_python_path_stored": False,
            "network_access_required": False,
            "runtime_reverification_required_before_spawn": True,
            "model_calls_before_runtime_pin": 0,
        }
        return cls(
            worker_runtime_id=content_id("c4_stage1_worker_runtime", body),
            worker_runtime_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_runtime_pin(self) -> Self:
        dependencies = C4Stage1DependencyVersions.model_validate(
            self.dependencies.model_dump(mode="python", round_trip=True)
        )
        expected_prefix = dependencies.python + "."
        if not (
            self.python_full_version == dependencies.python
            or self.python_full_version.startswith(expected_prefix)
        ):
            raise ValueError("Stage 1 worker Python version differs from its pin")
        if (
            self.worker_venv_inventory.tree_role != "worker-venv"
            or self.base_runtime_inventory.tree_role != "base-runtime"
        ):
            raise ValueError("Stage 1 runtime inventories have the wrong roles")
        inventory_body = {
            "policy": _WORKER_RUNTIME_INVENTORY_POLICY,
            "worker_venv_inventory": self.worker_venv_inventory,
            "base_runtime_inventory": self.base_runtime_inventory,
        }
        if (
            self.runtime_inventory_sha256 != _canonical_sha256(inventory_body)
            or self.runtime_inventory_file_count
            != self.worker_venv_inventory.file_count
            + self.base_runtime_inventory.file_count
            or self.runtime_inventory_directory_count
            != self.worker_venv_inventory.directory_count
            + self.base_runtime_inventory.directory_count
            or self.runtime_inventory_size_bytes
            != self.worker_venv_inventory.total_size_bytes
            + self.base_runtime_inventory.total_size_bytes
        ):
            raise ValueError("Stage 1 runtime inventory summary is not canonical")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"worker_runtime_id", "worker_runtime_sha256"},
        )
        if self.worker_runtime_id != content_id(
            "c4_stage1_worker_runtime", body
        ) or self.worker_runtime_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 worker runtime differs from canonical content")
        return self


class C4Stage1LaunchPolicy(FrozenArtifactModel):
    """Portable identity of the child entry point and its closed environment."""

    schema_version: Literal["rei-c4-stage1-launch-policy-v1"] = (
        "rei-c4-stage1-launch-policy-v1"
    )
    launch_policy_id: NonEmptyId
    launch_policy_sha256: HashDigest
    bootstrap_script_relative_path: Literal[
        "scripts/run_rei_c4_stage1_bootstrap.py"
    ] = C4_STAGE1_BOOTSTRAP_SCRIPT_PATH
    bootstrap_script_sha256: HashDigest
    bootstrap_script_size_bytes: Annotated[
        int, Field(gt=0, le=_MAX_WORKER_SCRIPT_BYTES)
    ]
    worker_script_relative_path: Literal["scripts/run_rei_c4_stage1_worker.py"] = (
        C4_STAGE1_WORKER_SCRIPT_PATH
    )
    worker_script_sha256: HashDigest
    worker_script_size_bytes: Annotated[int, Field(gt=0, le=_MAX_WORKER_SCRIPT_BYTES)]
    dependencies: C4Stage1DependencyVersions = C4Stage1DependencyVersions()
    worker_runtime: C4Stage1WorkerRuntimePin
    cuda_device: ResourceTelemetryCudaDeviceIdentity
    command_identity: NonEmptyId
    interpreter_isolation_flags: tuple[Literal["-I"], Literal["-S"]] = (
        "-I",
        "-S",
    )
    bootstrap_is_direct_python_entrypoint: Literal[True] = True
    command_identity_scope: Literal["worker-entrypoint-and-runtime-only-v1"] = (
        "worker-entrypoint-and-runtime-only-v1"
    )
    per_worker_process_request_identity_required: Literal[True] = True
    runtime_request_details_stored: Literal[False] = False
    working_directory_identity: Literal["rei-v3-committed-main-root"] = (
        "rei-v3-committed-main-root"
    )
    environment_identity: NonEmptyId
    fixed_environment: tuple[tuple[str, str], ...]
    inherited_environment_names: tuple[str, ...] = (
        C4_STAGE1_INHERITED_WORKER_ENVIRONMENT_NAMES
    )
    executable_or_local_paths_stored: Literal[False] = False
    remote_download_allowed: Literal[False] = False
    fallback_allowed: Literal[False] = False
    model_calls_before_launch_policy: Literal[0] = 0

    @classmethod
    def create(
        cls,
        worker_script: bytes,
        *,
        bootstrap_script: bytes,
        cuda_device: ResourceTelemetryCudaDeviceIdentity,
        worker_runtime: C4Stage1WorkerRuntimePin,
    ) -> C4Stage1LaunchPolicy:
        if type(worker_script) is not bytes or not worker_script:
            raise TypeError("Stage 1 worker script must be non-empty immutable bytes")
        if type(bootstrap_script) is not bytes or not bootstrap_script:
            raise TypeError(
                "Stage 1 bootstrap script must be non-empty immutable bytes"
            )
        cuda_device = ResourceTelemetryCudaDeviceIdentity.model_validate(
            cuda_device.model_dump(mode="python", round_trip=True)
        )
        if (
            cuda_device.status != "resolved"
            or cuda_device.logical_device_index != 0
            or cuda_device.physical_gpu_uuid is None
        ):
            raise ValueError("Stage 1 launch policy requires an exact CUDA identity")
        worker_runtime = C4Stage1WorkerRuntimePin.model_validate(
            worker_runtime.model_dump(mode="python", round_trip=True)
        )
        fixed_environment = tuple(
            sorted(
                (
                    *C4_STAGE1_FIXED_WORKER_ENVIRONMENT,
                    ("CUDA_VISIBLE_DEVICES", cuda_device.physical_gpu_uuid),
                )
            )
        )
        bootstrap_sha = hashlib.sha256(bootstrap_script).hexdigest()
        script_sha = hashlib.sha256(worker_script).hexdigest()
        command_identity = content_id(
            "c4_stage1_worker_command",
            {
                "interpreter_isolation_flags": ("-I", "-S"),
                "bootstrap_relative_path": C4_STAGE1_BOOTSTRAP_SCRIPT_PATH,
                "bootstrap_sha256": bootstrap_sha,
                "worker_relative_path": C4_STAGE1_WORKER_SCRIPT_PATH,
                "worker_sha256": script_sha,
                "worker_runtime_id": worker_runtime.worker_runtime_id,
                "worker_runtime_sha256": worker_runtime.worker_runtime_sha256,
                "scope": "worker-entrypoint-and-runtime-only-v1",
                "per_worker_process_request_identity_required": True,
                "runtime_request_details_stored": False,
            },
        )
        environment_identity = content_id(
            "c4_stage1_worker_environment",
            {
                "fixed": fixed_environment,
                "inherited_names": C4_STAGE1_INHERITED_WORKER_ENVIRONMENT_NAMES,
                "cuda_device": cuda_device,
                "worker_runtime_id": worker_runtime.worker_runtime_id,
                "worker_runtime_sha256": worker_runtime.worker_runtime_sha256,
            },
        )
        body = {
            "schema_version": "rei-c4-stage1-launch-policy-v1",
            "bootstrap_script_relative_path": C4_STAGE1_BOOTSTRAP_SCRIPT_PATH,
            "bootstrap_script_sha256": bootstrap_sha,
            "bootstrap_script_size_bytes": len(bootstrap_script),
            "worker_script_relative_path": C4_STAGE1_WORKER_SCRIPT_PATH,
            "worker_script_sha256": script_sha,
            "worker_script_size_bytes": len(worker_script),
            "dependencies": C4Stage1DependencyVersions(),
            "worker_runtime": worker_runtime,
            "cuda_device": cuda_device,
            "command_identity": command_identity,
            "interpreter_isolation_flags": ("-I", "-S"),
            "bootstrap_is_direct_python_entrypoint": True,
            "command_identity_scope": "worker-entrypoint-and-runtime-only-v1",
            "per_worker_process_request_identity_required": True,
            "runtime_request_details_stored": False,
            "working_directory_identity": "rei-v3-committed-main-root",
            "environment_identity": environment_identity,
            "fixed_environment": fixed_environment,
            "inherited_environment_names": (
                C4_STAGE1_INHERITED_WORKER_ENVIRONMENT_NAMES
            ),
            "executable_or_local_paths_stored": False,
            "remote_download_allowed": False,
            "fallback_allowed": False,
            "model_calls_before_launch_policy": 0,
        }
        return cls(
            launch_policy_id=content_id("c4_stage1_launch_policy", body),
            launch_policy_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_launch_policy(self) -> Self:
        cuda_device = ResourceTelemetryCudaDeviceIdentity.model_validate(
            self.cuda_device.model_dump(mode="python", round_trip=True)
        )
        worker_runtime = C4Stage1WorkerRuntimePin.model_validate(
            self.worker_runtime.model_dump(mode="python", round_trip=True)
        )
        expected_fixed = tuple(
            sorted(
                (
                    *C4_STAGE1_FIXED_WORKER_ENVIRONMENT,
                    ("CUDA_VISIBLE_DEVICES", cuda_device.physical_gpu_uuid),
                )
            )
        )
        expected_command_identity = content_id(
            "c4_stage1_worker_command",
            {
                "interpreter_isolation_flags": ("-I", "-S"),
                "bootstrap_relative_path": C4_STAGE1_BOOTSTRAP_SCRIPT_PATH,
                "bootstrap_sha256": self.bootstrap_script_sha256,
                "worker_relative_path": C4_STAGE1_WORKER_SCRIPT_PATH,
                "worker_sha256": self.worker_script_sha256,
                "worker_runtime_id": worker_runtime.worker_runtime_id,
                "worker_runtime_sha256": worker_runtime.worker_runtime_sha256,
                "scope": "worker-entrypoint-and-runtime-only-v1",
                "per_worker_process_request_identity_required": True,
                "runtime_request_details_stored": False,
            },
        )
        expected_environment_identity = content_id(
            "c4_stage1_worker_environment",
            {
                "fixed": expected_fixed,
                "inherited_names": C4_STAGE1_INHERITED_WORKER_ENVIRONMENT_NAMES,
                "cuda_device": cuda_device,
                "worker_runtime_id": worker_runtime.worker_runtime_id,
                "worker_runtime_sha256": worker_runtime.worker_runtime_sha256,
            },
        )
        if (
            cuda_device.status != "resolved"
            or cuda_device.logical_device_index != 0
            or cuda_device.physical_gpu_uuid is None
            or self.dependencies != worker_runtime.dependencies
            or self.interpreter_isolation_flags != ("-I", "-S")
            or self.command_identity != expected_command_identity
            or self.environment_identity != expected_environment_identity
            or self.fixed_environment != expected_fixed
            or self.inherited_environment_names
            != C4_STAGE1_INHERITED_WORKER_ENVIRONMENT_NAMES
        ):
            raise ValueError(
                "Stage 1 worker environment differs from the closed policy"
            )
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"launch_policy_id", "launch_policy_sha256"},
        )
        if self.launch_policy_id != content_id(
            "c4_stage1_launch_policy", body
        ) or self.launch_policy_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 launch policy differs from canonical content")
        return self


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _content_pin(
    kind: Literal["review_schema", "review_operator_policy"],
    artifact: C4BlindHumanReviewSchema | C4HumanReviewOperatorPolicy,
) -> C4Stage1ContentPin:
    artifact_id = (
        artifact.schema_id
        if isinstance(artifact, C4BlindHumanReviewSchema)
        else artifact.policy_id
    )
    return C4Stage1ContentPin(
        kind=kind,
        artifact_id=artifact_id,
        artifact_hash=artifact.content_hash(),
        schema_version=artifact.schema_version,
    )


def _telemetry_content_pin(
    policy: C4Stage1TelemetryPolicy,
) -> C4Stage1ContentPin:
    policy = C4Stage1TelemetryPolicy.model_validate(
        policy.model_dump(mode="python", round_trip=True)
    )
    return C4Stage1ContentPin(
        kind="telemetry_policy",
        artifact_id=policy.telemetry_policy_id,
        artifact_hash=policy.content_hash(),
        schema_version=policy.schema_version,
    )


def _review_runtime_content_pin(
    runtime: C4Stage1ReviewRuntimeManifest,
) -> C4Stage1ContentPin:
    runtime = C4Stage1ReviewRuntimeManifest.model_validate(
        runtime.model_dump(mode="python", round_trip=True)
    )
    return C4Stage1ContentPin(
        kind="review_runtime",
        artifact_id=runtime.runtime_manifest_id,
        artifact_hash=runtime.content_hash(),
        schema_version=runtime.schema_version,
    )


def _review_service_readiness_content_pin(
    readiness: C4Stage1ReviewServiceReadiness,
) -> C4Stage1ContentPin:
    readiness = C4Stage1ReviewServiceReadiness.model_validate(
        readiness.model_dump(mode="python", round_trip=True)
    )
    return C4Stage1ContentPin(
        kind="review_service_readiness",
        artifact_id=readiness.readiness_receipt_id,
        artifact_hash=readiness.content_hash(),
        schema_version=readiness.schema_version,
    )


class C4Stage1ReviewCommitments(FrozenModel):
    """Public commitments only; neither operator nor display secret is accepted."""

    review_runtime_manifest: C4Stage1ReviewRuntimeManifest
    review_service_readiness: C4Stage1ReviewServiceReadiness
    operator_hmac_key_commitments_sha256: tuple[HashDigest, HashDigest]
    display_policy_nonce: HashDigest
    ui_bundle_sha256: HashDigest
    content_security_policy: str = Field(min_length=1, max_length=4096)
    presenter_implementation_id: NonEmptyId
    presenter_revision: NonEmptyId
    display_attester_id: NonEmptyId
    display_signing_key_commitment_sha256: HashDigest
    direct_secret_material_present: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        review_runtime_manifest: C4Stage1ReviewRuntimeManifest,
        review_service_readiness: C4Stage1ReviewServiceReadiness,
        display_policy_nonce: str,
    ) -> C4Stage1ReviewCommitments:
        runtime = C4Stage1ReviewRuntimeManifest.model_validate(
            review_runtime_manifest.model_dump(mode="python", round_trip=True)
        )
        readiness = C4Stage1ReviewServiceReadiness.model_validate(
            review_service_readiness.model_dump(mode="python", round_trip=True)
        )
        return cls(
            review_runtime_manifest=runtime,
            review_service_readiness=readiness,
            operator_hmac_key_commitments_sha256=(
                readiness.operator_signing_key_commitment_sha256s
            ),
            display_policy_nonce=display_policy_nonce,
            ui_bundle_sha256=runtime.ui_bundle_sha256,
            content_security_policy=runtime.content_security_policy,
            presenter_implementation_id=runtime.presenter_implementation_id,
            presenter_revision=runtime.presenter_revision,
            display_attester_id=readiness.readiness_receipt_id,
            display_signing_key_commitment_sha256=(
                readiness.display_signing_key_commitment_sha256
            ),
            direct_secret_material_present=False,
        )

    @model_validator(mode="after")
    def validate_commitments(self) -> Self:
        runtime = C4Stage1ReviewRuntimeManifest.model_validate(
            self.review_runtime_manifest.model_dump(mode="python", round_trip=True)
        )
        readiness = C4Stage1ReviewServiceReadiness.model_validate(
            self.review_service_readiness.model_dump(mode="python", round_trip=True)
        )
        values = (
            *self.operator_hmac_key_commitments_sha256,
            self.display_policy_nonce,
            self.ui_bundle_sha256,
            self.display_signing_key_commitment_sha256,
        )
        if len(set(values)) != len(values):
            raise ValueError("Stage 1 review commitments must be independent")
        if (
            self.operator_hmac_key_commitments_sha256
            != readiness.operator_signing_key_commitment_sha256s
            or self.ui_bundle_sha256 != runtime.ui_bundle_sha256
            or self.content_security_policy != runtime.content_security_policy
            or self.presenter_implementation_id != runtime.presenter_implementation_id
            or self.presenter_revision != runtime.presenter_revision
            or self.display_attester_id != readiness.readiness_receipt_id
            or self.display_signing_key_commitment_sha256
            != readiness.display_signing_key_commitment_sha256
            or readiness.presenter_implementation_id
            != runtime.presenter_implementation_id
            or readiness.presenter_revision != runtime.presenter_revision
            or readiness.ui_bundle_sha256 != runtime.ui_bundle_sha256
            or readiness.content_security_policy_sha256
            != runtime.content_security_policy_sha256
            or readiness.ipc_schema != runtime.ipc_protocol
            or readiness.ledger_schema != runtime.ledger_schema_revision
            or readiness.schema_version != runtime.service_schema_revision
        ):
            raise ValueError(
                "Stage 1 review commitments differ from the pinned runtime service"
            )
        return self


class C4Stage1ReviewServicePreflightPort(Protocol):
    """Live public service boundary used before preparation and every spawn."""

    @property
    def readiness(self) -> C4Stage1ReviewServiceReadiness: ...

    def health(self) -> Mapping[str, object]: ...


def verify_c4_stage1_live_review_boundary(
    *,
    repository_root: str | Path,
    repository_gate: C4Stage1RepositoryGate,
    review_runtime_manifest: C4Stage1ReviewRuntimeManifest,
    review_service_readiness: C4Stage1ReviewServiceReadiness,
    review_service: C4Stage1ReviewServicePreflightPort,
    expected_completed_review_count: Literal[0, 2],
) -> tuple[C4Stage1ReviewRuntimeManifest, C4Stage1ReviewServiceReadiness]:
    """Re-hash the UI and require one exact live service cohort state."""

    if type(expected_completed_review_count) is not int or (
        expected_completed_review_count not in (0, 2)
    ):
        raise ValueError("Stage 1 completed review count must be zero or two")
    runtime = verify_c4_stage1_review_runtime_manifest(
        Path(repository_root), review_runtime_manifest
    )
    repository_gate = C4Stage1RepositoryGate.model_validate(
        repository_gate.model_dump(mode="python", round_trip=True)
    )
    expected = C4Stage1ReviewServiceReadiness.model_validate(
        review_service_readiness.model_dump(mode="python", round_trip=True)
    )
    try:
        actual = C4Stage1ReviewServiceReadiness.model_validate(
            review_service.readiness.model_dump(mode="python", round_trip=True)
        )
        health = review_service.health()
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 live review service is unavailable"
        ) from exc
    if actual != expected:
        raise C4Stage1PreparationError(
            "Stage 1 live review service differs from its public commitment"
        )
    try:
        live_repository_gate = C4Stage1RepositoryGate.model_validate_json(
            actual.repository_gate.repository_gate_canonical_json
        )
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 review service repository gate is invalid"
        ) from exc
    if live_repository_gate != repository_gate:
        raise C4Stage1PreparationError(
            "Stage 1 review service was not started from the prepared checkout gate"
        )
    if not isinstance(health, Mapping):
        raise C4Stage1PreparationError("Stage 1 review health is not a mapping")
    ledger_counts = health.get("ledger_counts")
    operator_signing_cohort_complete = health.get("operator_signing_cohort_complete")
    operator_signing_cohort_id = health.get("operator_signing_cohort_id")
    operator_signing_cohort_sha256 = health.get("operator_signing_cohort_sha256")
    expected_ledger_names = {
        "display_attestation_uses",
        "display_receipt_uses",
        "operator_policy_uses",
        "presenter_submissions",
        "operator_signing_leases",
    }
    if (
        health.get("schema_version") != expected.schema_version
        or health.get("ready") is not True
        or health.get("sqlite_integrity") != "ok"
        or health.get("sqlite_journal_mode") != "wal"
        or health.get("sqlite_synchronous") != "FULL"
        or health.get("secret_commitments_match_state") is not True
        or health.get("display_presenter_attached") is not True
        or health.get("repository_gate_matches_startup") is not True
        or health.get("presenter_boundary_roots_match_startup") is not True
        or health.get("browser_runtime_matches_readiness") is not True
        or health.get("ipc_response_auth_required") is not True
        or health.get("presenter_submission_auth_required") is not True
        or health.get("operator_signing_lease_required") is not True
        or type(operator_signing_cohort_complete) is not bool
        or health.get("service_is_model_free") is not True
        or health.get("semantic_quality_gate_passed") is not False
        or health.get("production_authority_granted") is not False
        or health.get("model_judge_calls") != 0
        or not isinstance(ledger_counts, Mapping)
        or set(ledger_counts) != expected_ledger_names
        or any(type(value) is not int or value < 0 for value in ledger_counts.values())
        or (
            any(
                value != expected_completed_review_count
                for value in ledger_counts.values()
            )
        )
        or (operator_signing_cohort_complete != (expected_completed_review_count == 2))
        or (
            expected_completed_review_count == 0
            and (
                operator_signing_cohort_id is not None
                or operator_signing_cohort_sha256 is not None
            )
        )
        or (
            expected_completed_review_count == 2
            and (
                type(operator_signing_cohort_id) is not str
                or not operator_signing_cohort_id
                or type(operator_signing_cohort_sha256) is not str
                or len(operator_signing_cohort_sha256) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in operator_signing_cohort_sha256
                )
            )
        )
    ):
        raise C4Stage1PreparationError(
            "Stage 1 live review service health is not fresh and exact"
        )
    return runtime, actual


@dataclass(frozen=True, slots=True)
class C4Stage1RuntimePaths:
    """Operator-supplied local bindings that never enter portable artifacts."""

    repository_root: Path = field(repr=False)
    worker_python: Path = field(repr=False)
    source_png: Path = field(repr=False)
    source_provenance: Path = field(repr=False)
    primary_snapshot: Path = field(repr=False)
    alternate_snapshot: Path = field(repr=False)
    staging_parent: Path = field(repr=False)

    def __post_init__(self) -> None:
        for name in (
            "repository_root",
            "worker_python",
            "source_png",
            "source_provenance",
            "primary_snapshot",
            "alternate_snapshot",
            "staging_parent",
        ):
            value = Path(getattr(self, name))
            if not value.is_absolute():
                raise ValueError(f"Stage 1 runtime path {name} must be absolute")
            object.__setattr__(self, name, value)


class C4Stage1PreparedWorker(FrozenArtifactModel):
    """One exact provider/option request in provider-major protocol order."""

    schema_version: Literal["rei-c4-stage1-prepared-worker-v1"] = (
        "rei-c4-stage1-prepared-worker-v1"
    )
    prepared_worker_id: NonEmptyId
    provider_order_index: Literal[0, 1]
    option_order_index: Literal[0, 1]
    editor_role: Literal["primary", "alternate"]
    option_id: Literal["enter_circle", "remain_edge"]
    operator_policy_id: NonEmptyId
    worker_request: C4Stage1WorkerRequest
    output_artifact_ids: tuple[NonEmptyId, ...] = ()
    output_count: Literal[0] = 0
    model_calls_before_preparation: Literal[0] = 0

    @classmethod
    def create(
        cls,
        *,
        provider_order_index: Literal[0, 1],
        option_order_index: Literal[0, 1],
        editor_role: Literal["primary", "alternate"],
        option_id: Literal["enter_circle", "remain_edge"],
        operator_policy_id: str,
        worker_request: C4Stage1WorkerRequest,
    ) -> C4Stage1PreparedWorker:
        body = {
            "schema_version": "rei-c4-stage1-prepared-worker-v1",
            "provider_order_index": provider_order_index,
            "option_order_index": option_order_index,
            "editor_role": editor_role,
            "option_id": option_id,
            "operator_policy_id": operator_policy_id,
            "worker_request": worker_request,
            "output_artifact_ids": (),
            "output_count": 0,
            "model_calls_before_preparation": 0,
        }
        return cls(
            prepared_worker_id=content_id("c4_stage1_prepared_worker", body),
            **body,
        )

    @model_validator(mode="after")
    def validate_prepared_worker(self) -> Self:
        expected_role = ("primary", "alternate")[self.provider_order_index]
        expected_option = ("enter_circle", "remain_edge")[self.option_order_index]
        request = C4Stage1WorkerRequest.model_validate(
            self.worker_request.model_dump(mode="python", round_trip=True)
        )
        if (
            self.editor_role != expected_role
            or self.option_id != expected_option
            or request.editor_spec.editor_role != self.editor_role
            or request.render_request.source_spec_id
            != C4_STAGE1_OPTION_SCENE_IDS[self.option_order_index]
        ):
            raise ValueError("Stage 1 prepared worker order differs from its request")
        if self.output_artifact_ids or self.output_count != 0:
            raise ValueError("Prepared Stage 1 worker cannot expose an output")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"prepared_worker_id"},
        )
        if self.prepared_worker_id != content_id("c4_stage1_prepared_worker", body):
            raise ValueError("Prepared Stage 1 worker differs from canonical content")
        return self


class C4Stage1PreparedAttempt(FrozenArtifactModel):
    """Durable exact-inventory anchor written before the first worker spawn."""

    schema_version: Literal["rei-c4-stage1-prepared-attempt-v2"] = (
        "rei-c4-stage1-prepared-attempt-v2"
    )
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    run_id: NonEmptyId
    attempt_id: NonEmptyId
    repository_gate: C4Stage1RepositoryGate
    dino_entrypoint_pin: C4Stage1DinoEntrypointPin
    launch_policy: C4Stage1LaunchPolicy
    worker_runtime: C4Stage1WorkerRuntimePin
    cuda_device: ResourceTelemetryCudaDeviceIdentity
    source_provenance_sha256: HashDigest
    source_provenance_storage_policy: Literal["hash-only-runtime-binding-v1"] = (
        "hash-only-runtime-binding-v1"
    )
    source_provenance_bytes_stored: Literal[False] = False
    staging_parent_policy: Literal["unlinked-ancestry-fresh-child-root-v1"] = (
        _STAGING_PARENT_POLICY
    )
    staging_parent_ancestry_verified: Literal[True] = True
    staging_parent_path_stored: Literal[False] = False
    runtime_bindings_reverification_required_before_spawn: Literal[True] = True
    telemetry_policy: C4Stage1TelemetryPolicy
    review_schema: C4BlindHumanReviewSchema
    review_operator_policies: tuple[
        C4HumanReviewOperatorPolicy,
        C4HumanReviewOperatorPolicy,
    ]
    display_policy: C4Stage1DisplayAttesterPolicy
    review_runtime_manifest: C4Stage1ReviewRuntimeManifest
    review_service_readiness: C4Stage1ReviewServiceReadiness
    screen_contract: C4Stage1ScreenContract
    workers: tuple[
        C4Stage1PreparedWorker,
        C4Stage1PreparedWorker,
        C4Stage1PreparedWorker,
        C4Stage1PreparedWorker,
    ]
    artifact_inventory_before_anchor: tuple[StoredArtifact, ...]
    exact_inventory_required_before_spawn: Literal[True] = True
    local_runtime_paths_stored: Literal[False] = False
    output_artifact_ids: tuple[NonEmptyId, ...] = ()
    output_count: Literal[0] = 0
    first_model_call_requires_exact_prepared_attempt_confirmation: Literal[True] = True
    generated_images_are_external_evidence: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_calls_before_prepared_anchor: Literal[0] = 0

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        repository_gate: C4Stage1RepositoryGate,
        launch_policy: C4Stage1LaunchPolicy,
        worker_runtime: C4Stage1WorkerRuntimePin,
        cuda_device: ResourceTelemetryCudaDeviceIdentity,
        source_provenance_sha256: str,
        telemetry_policy: C4Stage1TelemetryPolicy,
        review_schema: C4BlindHumanReviewSchema,
        review_operator_policies: tuple[
            C4HumanReviewOperatorPolicy,
            C4HumanReviewOperatorPolicy,
        ],
        display_policy: C4Stage1DisplayAttesterPolicy,
        review_runtime_manifest: C4Stage1ReviewRuntimeManifest,
        review_service_readiness: C4Stage1ReviewServiceReadiness,
        screen_contract: C4Stage1ScreenContract,
        workers: tuple[
            C4Stage1PreparedWorker,
            C4Stage1PreparedWorker,
            C4Stage1PreparedWorker,
            C4Stage1PreparedWorker,
        ],
        artifact_inventory_before_anchor: tuple[StoredArtifact, ...],
        dino_entrypoint_pin: C4Stage1DinoEntrypointPin | None = None,
    ) -> C4Stage1PreparedAttempt:
        if dino_entrypoint_pin is None:
            dino_entrypoint_pin = _default_dino_entrypoint_pin(repository_gate)
        dino_entrypoint_pin = C4Stage1DinoEntrypointPin.model_validate(
            dino_entrypoint_pin.model_dump(mode="python", round_trip=True)
        )
        attempt_id = content_id(
            "c4_stage1_attempt",
            {
                "run_id": run_id,
                "repository_gate_id": repository_gate.repository_gate_id,
                "dino_entrypoint_pin_id": (
                    dino_entrypoint_pin.dino_entrypoint_pin_id
                ),
                "screen_contract_id": screen_contract.screen_contract_id,
                "review_runtime_manifest_id": (
                    review_runtime_manifest.runtime_manifest_id
                ),
                "review_service_readiness_id": (
                    review_service_readiness.readiness_receipt_id
                ),
                "launch_policy_id": launch_policy.launch_policy_id,
                "worker_runtime_id": worker_runtime.worker_runtime_id,
                "cuda_measurement_subject_id": cuda_device.measurement_subject_id,
                "source_provenance_sha256": source_provenance_sha256,
                "worker_ids": tuple(item.prepared_worker_id for item in workers),
            },
        )
        body = {
            "schema_version": "rei-c4-stage1-prepared-attempt-v2",
            "run_id": run_id,
            "attempt_id": attempt_id,
            "repository_gate": repository_gate,
            "dino_entrypoint_pin": dino_entrypoint_pin,
            "launch_policy": launch_policy,
            "worker_runtime": worker_runtime,
            "cuda_device": cuda_device,
            "source_provenance_sha256": source_provenance_sha256,
            "source_provenance_storage_policy": "hash-only-runtime-binding-v1",
            "source_provenance_bytes_stored": False,
            "staging_parent_policy": _STAGING_PARENT_POLICY,
            "staging_parent_ancestry_verified": True,
            "staging_parent_path_stored": False,
            "runtime_bindings_reverification_required_before_spawn": True,
            "telemetry_policy": telemetry_policy,
            "review_schema": review_schema,
            "review_operator_policies": review_operator_policies,
            "display_policy": display_policy,
            "review_runtime_manifest": review_runtime_manifest,
            "review_service_readiness": review_service_readiness,
            "screen_contract": screen_contract,
            "workers": workers,
            "artifact_inventory_before_anchor": artifact_inventory_before_anchor,
            "exact_inventory_required_before_spawn": True,
            "local_runtime_paths_stored": False,
            "output_artifact_ids": (),
            "output_count": 0,
            "first_model_call_requires_exact_prepared_attempt_confirmation": True,
            "generated_images_are_external_evidence": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
            "model_calls_before_prepared_anchor": 0,
        }
        return cls(
            prepared_attempt_id=content_id("c4_stage1_prepared_attempt", body),
            prepared_attempt_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_prepared_attempt(self) -> Self:
        dino_entrypoint_pin = C4Stage1DinoEntrypointPin.model_validate(
            self.dino_entrypoint_pin.model_dump(mode="python", round_trip=True)
        )
        worker_runtime = C4Stage1WorkerRuntimePin.model_validate(
            self.worker_runtime.model_dump(mode="python", round_trip=True)
        )
        schema_pin = _content_pin("review_schema", self.review_schema)
        operator_pins = tuple(
            _content_pin("review_operator_policy", policy)
            for policy in self.review_operator_policies
        )
        expected_attempt_id = content_id(
            "c4_stage1_attempt",
            {
                "run_id": self.run_id,
                "repository_gate_id": self.repository_gate.repository_gate_id,
                "dino_entrypoint_pin_id": (
                    dino_entrypoint_pin.dino_entrypoint_pin_id
                ),
                "screen_contract_id": self.screen_contract.screen_contract_id,
                "review_runtime_manifest_id": (
                    self.review_runtime_manifest.runtime_manifest_id
                ),
                "review_service_readiness_id": (
                    self.review_service_readiness.readiness_receipt_id
                ),
                "launch_policy_id": self.launch_policy.launch_policy_id,
                "worker_runtime_id": worker_runtime.worker_runtime_id,
                "cuda_measurement_subject_id": (
                    self.cuda_device.measurement_subject_id
                ),
                "source_provenance_sha256": self.source_provenance_sha256,
                "worker_ids": tuple(item.prepared_worker_id for item in self.workers),
            },
        )
        if (
            self.attempt_id != expected_attempt_id
            or dino_entrypoint_pin.repository_gate_id
            != self.repository_gate.repository_gate_id
            or dino_entrypoint_pin.repository_gate_sha256
            != self.repository_gate.repository_gate_sha256
            or dino_entrypoint_pin.repository_head_commit
            != self.repository_gate.head_commit
            or self.cuda_device.logical_device_index != 0
            or self.cuda_device != self.launch_policy.cuda_device
            or worker_runtime != self.launch_policy.worker_runtime
            or self.cuda_device.status != "resolved"
            or self.source_provenance_sha256
            != self.screen_contract.source.source_provenance_sha256
            or self.screen_contract.review_schema != schema_pin
            or self.screen_contract.review_operator_policies != operator_pins
            or self.screen_contract.display_policy
            != c4_stage1_display_policy_content_pin(self.display_policy)
            or self.screen_contract.review_runtime
            != _review_runtime_content_pin(self.review_runtime_manifest)
            or self.screen_contract.review_service_readiness
            != _review_service_readiness_content_pin(self.review_service_readiness)
            or self.screen_contract.telemetry_policy
            != _telemetry_content_pin(self.telemetry_policy)
            or tuple(
                policy.hmac_key_commitment_sha256
                for policy in self.review_operator_policies
            )
            != self.review_service_readiness.operator_signing_key_commitment_sha256s
            or self.display_policy.ui_bundle_sha256
            != self.review_runtime_manifest.ui_bundle_sha256
            or self.display_policy.content_security_policy
            != self.review_runtime_manifest.content_security_policy
            or self.display_policy.presenter_implementation_id
            != self.review_runtime_manifest.presenter_implementation_id
            or self.display_policy.presenter_revision
            != self.review_runtime_manifest.presenter_revision
            or self.display_policy.display_attester_id
            != self.review_service_readiness.readiness_receipt_id
            or self.display_policy.display_signing_key_commitment_sha256
            != self.review_service_readiness.display_signing_key_commitment_sha256
            or self.review_service_readiness.ui_bundle_sha256
            != self.review_runtime_manifest.ui_bundle_sha256
            or self.review_service_readiness.content_security_policy_sha256
            != self.review_runtime_manifest.content_security_policy_sha256
            or self.review_service_readiness.presenter_implementation_id
            != self.review_runtime_manifest.presenter_implementation_id
            or self.review_service_readiness.presenter_revision
            != self.review_runtime_manifest.presenter_revision
            or self.review_service_readiness.ipc_schema
            != self.review_runtime_manifest.ipc_protocol
            or self.review_service_readiness.ledger_schema
            != self.review_runtime_manifest.ledger_schema_revision
            or self.review_service_readiness.schema_version
            != self.review_runtime_manifest.service_schema_revision
        ):
            raise ValueError("Prepared Stage 1 policies differ from screen contract")
        if any(
            policy.run_id != self.run_id for policy in self.review_operator_policies
        ):
            raise ValueError("Prepared Stage 1 operator policy belongs to another run")
        expected_worker_order = (
            (0, 0, "primary", "enter_circle"),
            (0, 1, "primary", "remain_edge"),
            (1, 0, "alternate", "enter_circle"),
            (1, 1, "alternate", "remain_edge"),
        )
        actual_worker_order = tuple(
            (
                item.provider_order_index,
                item.option_order_index,
                item.editor_role,
                item.option_id,
            )
            for item in self.workers
        )
        if actual_worker_order != expected_worker_order:
            raise ValueError("Prepared Stage 1 worker order differs from protocol")
        expected_policy_ids = tuple(
            policy.policy_id for policy in self.review_operator_policies
        )
        if tuple(
            self.workers[index * 2].operator_policy_id for index in range(2)
        ) != expected_policy_ids or any(
            self.workers[index * 2].operator_policy_id
            != self.workers[index * 2 + 1].operator_policy_id
            for index in range(2)
        ):
            raise ValueError("Prepared workers differ from one-time operator policies")
        paths = tuple(
            item.relative_path for item in self.artifact_inventory_before_anchor
        )
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("Prepared Stage 1 inventory is not exact canonical order")
        if any(
            item.run_id != self.run_id for item in self.artifact_inventory_before_anchor
        ):
            raise ValueError("Prepared Stage 1 inventory cites another run")
        if C4_STAGE1_PREPARED_ANCHOR_PATH in paths:
            raise ValueError("Prepared Stage 1 inventory cannot contain its own anchor")
        if self.output_artifact_ids or self.output_count != 0:
            raise ValueError("Prepared Stage 1 attempt cannot expose output artifacts")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"prepared_attempt_id", "prepared_attempt_sha256"},
        )
        if self.prepared_attempt_id != content_id(
            "c4_stage1_prepared_attempt", body
        ) or self.prepared_attempt_sha256 != _canonical_sha256(body):
            raise ValueError("Prepared Stage 1 attempt differs from canonical content")
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1PreparedAttemptOutcome:
    prepared_attempt: C4Stage1PreparedAttempt
    prepared_anchor_storage: StoredArtifact

    def __post_init__(self) -> None:
        attempt = C4Stage1PreparedAttempt.model_validate(
            self.prepared_attempt.model_dump(mode="python", round_trip=True)
        )
        storage = StoredArtifact.model_validate(
            self.prepared_anchor_storage.model_dump(mode="python", round_trip=True)
        )
        expected = canonical_json_bytes(attempt)
        if (
            storage.run_id != attempt.run_id
            or storage.relative_path != C4_STAGE1_PREPARED_ANCHOR_PATH
            or storage.content_sha256 != hashlib.sha256(expected).hexdigest()
            or storage.size_bytes != len(expected)
        ):
            raise ValueError("Prepared Stage 1 anchor storage differs from content")


GitCommandRunner = Callable[[tuple[str, ...], Path], str]


def _default_git_command_runner(arguments: tuple[str, ...], root: Path) -> str:
    try:
        completed = subprocess.run(
            arguments,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30.0,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise C4Stage1PreparationError(
            "Stage 1 repository verification command failed"
        ) from exc
    if completed.returncode != 0:
        raise C4Stage1PreparationError("Stage 1 repository verification command failed")
    try:
        return completed.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 repository verification output is not UTF-8"
        ) from exc


def capture_c4_stage1_repository_gate(
    repository_root: str | Path,
    *,
    command_runner: GitCommandRunner = _default_git_command_runner,
    injected_git_runtime: C4Stage1GitRuntimePin | None = None,
) -> C4Stage1RepositoryGate:
    """Require committed, scoped-clean code on live remote ``main``."""

    root = Path(repository_root)
    if not root.is_absolute() or not root.is_dir():
        raise C4Stage1PreparationError(
            "Stage 1 repository root must be an absolute directory"
        )
    if command_runner is _default_git_command_runner:
        if injected_git_runtime is not None:
            raise C4Stage1PreparationError(
                "Stage 1 production Git gate rejects an injected runtime pin"
            )
        executable_path, git_runtime = _capture_trusted_git_runtime(root)
        executable = os.fspath(executable_path)
    else:
        if injected_git_runtime is None:
            raise C4Stage1PreparationError(
                "Stage 1 injected Git runner requires an exact runtime pin"
            )
        git_runtime = C4Stage1GitRuntimePin.model_validate(
            injected_git_runtime.model_dump(mode="python", round_trip=True)
        )
        executable = "stage1-injected-git-runner"

    def run(*arguments: str) -> str:
        value = command_runner((executable, *arguments), root)
        if "\x00" in value:
            raise C4Stage1PreparationError(
                "Stage 1 repository verification returned NUL"
            )
        return value

    branch = run("symbolic-ref", "--quiet", "--short", "HEAD").strip()
    if branch != "main":
        raise C4Stage1PreparationError("Stage 1 execution is allowed only on main")
    head = run("rev-parse", "--verify", "HEAD^{commit}").strip()
    local_origin = run(
        "rev-parse", "--verify", "refs/remotes/origin/main^{commit}"
    ).strip()
    origin_url = run("remote", "get-url", "origin").strip()
    push_origin_url = run("remote", "get-url", "--push", "origin").strip()
    if origin_url != C4_STAGE1_ORIGIN_URL or push_origin_url != C4_STAGE1_ORIGIN_URL:
        raise C4Stage1PreparationError(
            "Stage 1 origin URL differs from the exact repository pin"
        )
    remote_lines = tuple(
        line.strip()
        for line in run(
            "ls-remote",
            "--exit-code",
            C4_STAGE1_ORIGIN_URL,
            "refs/heads/main",
        ).splitlines()
        if line.strip()
    )
    if len(remote_lines) != 1:
        raise C4Stage1PreparationError("Stage 1 remote main ref is ambiguous")
    remote_parts = remote_lines[0].split()
    if len(remote_parts) != 2 or remote_parts[1] != "refs/heads/main":
        raise C4Stage1PreparationError("Stage 1 remote main ref is malformed")
    remote = remote_parts[0]
    dirty = run(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *C4_STAGE1_GIT_SCOPE_PATHS,
    )
    if dirty:
        raise C4Stage1PreparationError(
            "Stage 1 controlling code or documents are not committed"
        )
    tracked_lines = tuple(
        line
        for line in run(
            "ls-files",
            "-v",
            "--",
            *C4_STAGE1_GIT_SCOPE_PATHS,
        ).splitlines()
        if line
    )
    if not tracked_lines:
        raise C4Stage1PreparationError("Stage 1 controlling scope has no tracked files")
    for line in tracked_lines:
        if len(line) < 3 or line[1] != " ":
            raise C4Stage1PreparationError("Stage 1 tracked scope flags are malformed")
        tag = line[0]
        if tag == "S" or tag.islower():
            raise C4Stage1PreparationError(
                "Stage 1 controlling file hides worktree changes"
            )
    try:
        return C4Stage1RepositoryGate.create(
            git_runtime=git_runtime,
            head_commit=head,
            local_origin_main_commit=local_origin,
            remote_origin_main_commit=remote,
        )
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 main and remote repository gate failed"
        ) from exc


def build_c4_stage1_worker_environment(
    launch_policy: C4Stage1LaunchPolicy,
    *,
    parent_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the closed child environment without persisting local values."""

    launch_policy = C4Stage1LaunchPolicy.model_validate(
        launch_policy.model_dump(mode="python", round_trip=True)
    )
    source = os.environ if parent_environment is None else parent_environment
    environment = {
        name: source[name]
        for name in launch_policy.inherited_environment_names
        if name in source
    }
    environment.update(dict(launch_policy.fixed_environment))
    return environment


def _is_reparse_or_link(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_unlinked_ancestry(path: Path) -> None:
    if not path.is_absolute() or path != _absolute_lexical(path):
        raise C4Stage1PreparationError(
            "Stage 1 runtime path must be an absolute lexical path"
        )
    parts = path.parts
    if not parts:
        raise C4Stage1PreparationError("Stage 1 runtime path is empty")
    current = Path(parts[0])
    for part in parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise C4Stage1PreparationError(
                "Stage 1 runtime path ancestry is unavailable"
            ) from exc
        if _is_reparse_or_link(metadata):
            raise C4Stage1PreparationError(
                "Stage 1 runtime path ancestry contains a link or reparse point"
            )


def verify_c4_stage1_staging_parent(staging_parent: str | Path) -> Path:
    """Verify the runtime-only parent used for fresh per-worker staging roots."""

    root = Path(staging_parent)
    _assert_unlinked_ancestry(root)
    try:
        metadata = os.lstat(root)
    except OSError as exc:
        raise C4Stage1PreparationError("Stage 1 staging parent is unavailable") from exc
    if _is_reparse_or_link(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise C4Stage1PreparationError(
            "Stage 1 staging parent must be an ordinary non-reparse directory"
        )
    return root


def _stable_read_regular(path: Path, *, maximum_bytes: int) -> bytes:
    if not path.is_absolute():
        raise C4Stage1PreparationError("Stage 1 input path must be absolute")
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise C4Stage1PreparationError("Stage 1 input is unreadable") from exc
    if (
        _is_reparse_or_link(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
    ):
        raise C4Stage1PreparationError(
            "Stage 1 input must be a regular non-linked file"
        )
    if not 0 < before.st_size <= maximum_bytes:
        raise C4Stage1PreparationError("Stage 1 input exceeds its byte bound")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise C4Stage1PreparationError("Stage 1 input cannot be opened safely") from exc
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
            raise C4Stage1PreparationError("Stage 1 input changed while opening")
        while True:
            remaining = maximum_bytes + 1 - len(value)
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            value.extend(chunk)
            if len(value) > maximum_bytes:
                raise C4Stage1PreparationError("Stage 1 input exceeds its byte bound")
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise C4Stage1PreparationError("Stage 1 input changed while reading") from exc
    if (
        opened is None
        or final_handle is None
        or _is_reparse_or_link(after)
        or before.st_nlink != 1
        or opened.st_nlink != 1
        or final_handle.st_nlink != 1
        or after.st_nlink != 1
        or not os.path.samestat(opened, final_handle)
        or not os.path.samestat(opened, after)
        or opened.st_mtime_ns != final_handle.st_mtime_ns
        or opened.st_mtime_ns != after.st_mtime_ns
        or opened.st_ctime_ns != final_handle.st_ctime_ns
        or opened.st_ctime_ns != after.st_ctime_ns
        or opened.st_size != len(value)
    ):
        raise C4Stage1PreparationError("Stage 1 input changed while reading")
    return bytes(value)


def _default_dino_entrypoint_pin(
    repository_gate: C4Stage1RepositoryGate,
) -> C4Stage1DinoEntrypointPin:
    """Build the exact pin for synthetic callers that omit an explicit pin."""

    return C4Stage1DinoEntrypointPin.create(
        repository_gate=repository_gate,
        bootstrap_script=_stable_read_regular(
            _MODULE_REPOSITORY_ROOT / C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH,
            maximum_bytes=_MAX_WORKER_SCRIPT_BYTES,
        ),
        worker_script=_stable_read_regular(
            _MODULE_REPOSITORY_ROOT / C4_STAGE1_DINO_WORKER_SCRIPT_PATH,
            maximum_bytes=_MAX_WORKER_SCRIPT_BYTES,
        ),
    )


def _stable_hash_runtime_file(path: Path) -> tuple[str, int]:
    """Stream one runtime file while rejecting link swaps and hard links."""

    try:
        before = os.lstat(path)
    except OSError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory file is unreadable"
        ) from exc
    if (
        _is_reparse_or_link(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size < 0
        or before.st_size > _MAX_RUNTIME_INVENTORY_BYTES
    ):
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory requires ordinary non-linked files"
        )
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory file cannot be opened safely"
        ) from exc
    digest = hashlib.sha256()
    total = 0
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
            raise C4Stage1PreparationError(
                "Stage 1 runtime inventory file changed while opening"
            )
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_RUNTIME_INVENTORY_BYTES:
                raise C4Stage1PreparationError(
                    "Stage 1 runtime inventory exceeds its byte bound"
                )
            digest.update(chunk)
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory file changed while reading"
        ) from exc
    if (
        opened is None
        or final_handle is None
        or _is_reparse_or_link(after)
        or before.st_nlink != 1
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
        or opened.st_size != total
        or final_handle.st_size != total
        or after.st_size != total
    ):
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory file changed while reading"
        )
    return digest.hexdigest(), total


def _runtime_relative_name(parts: tuple[str, ...]) -> str:
    try:
        value = "/".join(parts)
        value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory contains a non-portable name"
        ) from exc
    if not value or value.startswith("/") or "\\" in value:
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory contains a non-portable name"
        )
    return value


def _is_runtime_customization_name(parts: tuple[str, ...]) -> bool:
    for part in parts:
        normalized = part.casefold().split(".", 1)[0]
        if normalized in {"sitecustomize", "usercustomize"}:
            return True
    return False


def _same_runtime_entry_metadata(
    before: os.stat_result,
    after: os.stat_result,
) -> bool:
    return (
        os.path.samestat(before, after)
        and before.st_mode == after.st_mode
        and before.st_size == after.st_size
        and before.st_nlink == after.st_nlink
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_ctime_ns == after.st_ctime_ns
    )


def _update_runtime_inventory_digest(
    digest: object,
    *,
    kind: Literal["directory", "file"],
    relative_name: str,
    size_bytes: int | None = None,
    content_sha256: str | None = None,
) -> None:
    record: dict[str, object] = {
        "kind": kind,
        "relative_name": relative_name,
    }
    if kind == "file":
        record.update(
            {
                "size_bytes": size_bytes,
                "content_sha256": content_sha256,
            }
        )
    payload = canonical_json_bytes(record)
    digest.update(len(payload).to_bytes(8, "big"))  # type: ignore[attr-defined]
    digest.update(payload)  # type: ignore[attr-defined]


def _capture_runtime_tree_inventory(
    root: Path,
    *,
    tree_role: Literal["worker-venv", "base-runtime"],
) -> C4Stage1RuntimeTreeInventoryPin:
    """Hash every entry in a runtime tree without retaining a local path."""

    _assert_unlinked_ancestry(root)
    try:
        root_metadata = os.lstat(root)
    except OSError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory root is unavailable"
        ) from exc
    if _is_reparse_or_link(root_metadata) or not stat.S_ISDIR(root_metadata.st_mode):
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory root must be an ordinary directory"
        )

    digest = hashlib.sha256()
    digest.update(b"rei-c4-stage1-runtime-tree-inventory-v1\0")
    digest.update(tree_role.encode("ascii"))
    counters = {
        "files": 0,
        "directories": 1,
        "bytes": 0,
        "pth": 0,
    }

    def scan(directory: Path, relative_parts: tuple[str, ...]) -> None:
        try:
            directory_before = os.lstat(directory)
            with os.scandir(directory) as iterator:
                names_before = tuple(sorted(entry.name for entry in iterator))
        except OSError as exc:
            raise C4Stage1PreparationError(
                "Stage 1 runtime inventory cannot enumerate a directory"
            ) from exc
        if _is_reparse_or_link(directory_before) or not stat.S_ISDIR(
            directory_before.st_mode
        ):
            raise C4Stage1PreparationError(
                "Stage 1 runtime inventory contains a link or reparse point"
            )
        completed_entry_metadata: dict[str, os.stat_result] = {}
        for name in names_before:
            child = directory / name
            child_parts = (*relative_parts, name)
            if _is_runtime_customization_name(child_parts):
                raise C4Stage1PreparationError(
                    "Stage 1 runtime customization modules are forbidden"
                )
            relative_name = _runtime_relative_name(child_parts)
            try:
                child_metadata = os.lstat(child)
            except OSError as exc:
                raise C4Stage1PreparationError(
                    "Stage 1 runtime inventory changed while enumerating"
                ) from exc
            if _is_reparse_or_link(child_metadata):
                raise C4Stage1PreparationError(
                    "Stage 1 runtime inventory contains a link or reparse point"
                )
            if stat.S_ISDIR(child_metadata.st_mode):
                counters["directories"] += 1
                if counters["directories"] > _MAX_RUNTIME_INVENTORY_DIRECTORIES:
                    raise C4Stage1PreparationError(
                        "Stage 1 runtime inventory exceeds its directory bound"
                    )
                _update_runtime_inventory_digest(
                    digest,
                    kind="directory",
                    relative_name=relative_name,
                )
                scan(child, child_parts)
            else:
                if not stat.S_ISREG(child_metadata.st_mode):
                    raise C4Stage1PreparationError(
                        "Stage 1 runtime inventory contains a non-regular entry"
                    )
                content_sha256, size_bytes = _stable_hash_runtime_file(child)
                counters["files"] += 1
                counters["bytes"] += size_bytes
                if (
                    counters["files"] > _MAX_RUNTIME_INVENTORY_FILES
                    or counters["bytes"] > _MAX_RUNTIME_INVENTORY_BYTES
                ):
                    raise C4Stage1PreparationError(
                        "Stage 1 runtime inventory exceeds its file or byte bound"
                    )
                if name.casefold().endswith(".pth"):
                    counters["pth"] += 1
                _update_runtime_inventory_digest(
                    digest,
                    kind="file",
                    relative_name=relative_name,
                    size_bytes=size_bytes,
                    content_sha256=content_sha256,
                )
            try:
                completed_entry_metadata[name] = os.lstat(child)
            except OSError as exc:
                raise C4Stage1PreparationError(
                    "Stage 1 runtime inventory changed while enumerating"
                ) from exc
        try:
            directory_after = os.lstat(directory)
            with os.scandir(directory) as iterator:
                names_after = tuple(sorted(entry.name for entry in iterator))
        except OSError as exc:
            raise C4Stage1PreparationError(
                "Stage 1 runtime inventory changed while enumerating"
            ) from exc
        if (
            _is_reparse_or_link(directory_after)
            or not stat.S_ISDIR(directory_after.st_mode)
            or not _same_runtime_entry_metadata(directory_before, directory_after)
            or names_before != names_after
        ):
            raise C4Stage1PreparationError(
                "Stage 1 runtime inventory changed while enumerating"
            )
        for name, completed_metadata in completed_entry_metadata.items():
            try:
                final_metadata = os.lstat(directory / name)
            except OSError as exc:
                raise C4Stage1PreparationError(
                    "Stage 1 runtime inventory changed while enumerating"
                ) from exc
            if not _same_runtime_entry_metadata(
                completed_metadata,
                final_metadata,
            ):
                raise C4Stage1PreparationError(
                    "Stage 1 runtime inventory changed while enumerating"
                )

    scan(root, ())
    if counters["files"] == 0 or counters["bytes"] == 0:
        raise C4Stage1PreparationError(
            "Stage 1 runtime inventory tree must contain runtime bytes"
        )
    return C4Stage1RuntimeTreeInventoryPin(
        tree_role=tree_role,
        tree_content_sha256=digest.hexdigest(),
        file_count=counters["files"],
        directory_count=counters["directories"],
        total_size_bytes=counters["bytes"],
        pth_file_count=counters["pth"],
    )


def _trusted_git_executable_path() -> tuple[
    Path,
    Literal["windows-program-files-git-bin", "posix-usr-bin-git"],
]:
    if os.name == "nt":
        return (
            Path(r"C:\Program Files\Git\bin\git.exe"),
            "windows-program-files-git-bin",
        )
    if os.name == "posix":
        return Path("/usr/bin/git"), "posix-usr-bin-git"
    raise C4Stage1PreparationError("Stage 1 has no trusted Git location")


def _capture_trusted_git_runtime(
    repository_root: Path,
) -> tuple[Path, C4Stage1GitRuntimePin]:
    executable, location_class = _trusted_git_executable_path()
    _assert_unlinked_ancestry(executable)
    try:
        metadata = os.lstat(executable)
    except OSError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 trusted Git executable is unavailable"
        ) from exc
    if _is_reparse_or_link(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise C4Stage1PreparationError(
            "Stage 1 trusted Git executable must be ordinary and non-reparse"
        )
    before = _stable_read_regular(
        executable,
        maximum_bytes=_MAX_GIT_EXECUTABLE_BYTES,
    )
    version = _default_git_command_runner(
        (os.fspath(executable), "--version"),
        repository_root,
    ).strip()
    after = _stable_read_regular(
        executable,
        maximum_bytes=_MAX_GIT_EXECUTABLE_BYTES,
    )
    if before != after:
        raise C4Stage1PreparationError(
            "Stage 1 trusted Git executable changed during capture"
        )
    try:
        runtime = C4Stage1GitRuntimePin.create(
            git_executable_sha256=hashlib.sha256(before).hexdigest(),
            git_executable_size_bytes=len(before),
            git_version=version,
            trusted_location_class=location_class,
        )
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 trusted Git runtime identity is invalid"
        ) from exc
    return executable, runtime


WorkerRuntimeMetadataRunner = Callable[[Path], Mapping[str, str]]


def _default_worker_runtime_metadata_runner(
    worker_python: Path,
) -> Mapping[str, str]:
    package_pairs = repr(_WORKER_RUNTIME_DISTRIBUTIONS)
    probe = f"""import sys
sys.dont_write_bytecode = True
import importlib.metadata as metadata
import json
import os
import platform
import re

pairs = {package_pairs}
worker_executable = os.path.abspath(sys.executable)
worker_venv_root = os.path.dirname(os.path.dirname(worker_executable))
if os.name == "nt":
    site_packages = os.path.join(worker_venv_root, "Lib", "site-packages")
else:
    site_packages = os.path.join(
        worker_venv_root,
        "lib",
        f"python{{sys.version_info.major}}.{{sys.version_info.minor}}",
        "site-packages",
    )
normalize = lambda value: re.sub(r"[-_.]+", "-", value).casefold()
distributions = tuple(metadata.distributions(path=[site_packages]))
versions = {{}}
for key, distribution_name in pairs:
    matches = tuple(
        item
        for item in distributions
        if normalize(item.metadata["Name"] or "") == normalize(distribution_name)
    )
    if len(matches) != 1:
        raise RuntimeError("frozen runtime distribution is not unique")
    versions[key] = matches[0].version
out = {{
    "python": f"{{sys.version_info.major}}.{{sys.version_info.minor}}",
    "python_full_version": platform.python_version(),
    "python_implementation": platform.python_implementation(),
    "_runtime_worker_venv_root": worker_venv_root,
    "_runtime_base_root": os.path.abspath(sys.base_prefix),
    "_runtime_site_packages": site_packages,
}}
out.update(versions)
sys.stdout.write(json.dumps(out, sort_keys=True, separators=(",", ":")))
"""
    environment = {
        name: os.environ[name]
        for name in C4_STAGE1_INHERITED_WORKER_ENVIRONMENT_NAMES
        if name in os.environ
    }
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
        }
    )
    try:
        completed = subprocess.run(
            (os.fspath(worker_python), "-I", "-S", "-c", probe),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30.0,
            shell=False,
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise C4Stage1PreparationError(
            "Stage 1 worker runtime metadata probe failed"
        ) from exc
    if (
        completed.returncode != 0
        or not completed.stdout
        or len(completed.stdout) > _MAX_WORKER_METADATA_BYTES
    ):
        raise C4Stage1PreparationError("Stage 1 worker runtime metadata probe failed")
    try:
        payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise C4Stage1PreparationError(
            "Stage 1 worker runtime metadata is invalid"
        ) from exc
    if not isinstance(payload, dict):
        raise C4Stage1PreparationError("Stage 1 worker runtime metadata is invalid")
    return payload


def capture_c4_stage1_worker_runtime(
    worker_python: str | Path,
    *,
    metadata_runner: WorkerRuntimeMetadataRunner = (
        _default_worker_runtime_metadata_runner
    ),
) -> C4Stage1WorkerRuntimePin:
    """Pin the full venv/base runtime bytes without importing model packages."""

    path = Path(worker_python)
    _assert_unlinked_ancestry(path)
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise C4Stage1PreparationError("Stage 1 worker Python is unavailable") from exc
    if (
        _is_reparse_or_link(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise C4Stage1PreparationError(
            "Stage 1 worker Python must be one ordinary non-linked file"
        )
    worker_python_bytes = _stable_read_regular(
        path,
        maximum_bytes=_MAX_WORKER_PYTHON_BYTES,
    )
    try:
        observed = dict(metadata_runner(path))
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 worker runtime metadata probe failed"
        ) from exc
    runtime_path_keys = {
        "_runtime_worker_venv_root",
        "_runtime_base_root",
        "_runtime_site_packages",
    }
    expected_keys = {
        "python",
        "python_full_version",
        "python_implementation",
        *(key for key, _ in _WORKER_RUNTIME_DISTRIBUTIONS),
        *runtime_path_keys,
    }
    if set(observed) != expected_keys or any(
        type(value) is not str or not value for value in observed.values()
    ):
        raise C4Stage1PreparationError("Stage 1 worker runtime metadata is incomplete")
    if any(
        len(observed[key]) > 200 for key in expected_keys - runtime_path_keys
    ) or any(len(observed[key]) > 32_767 for key in runtime_path_keys):
        raise C4Stage1PreparationError("Stage 1 worker runtime metadata is incomplete")
    dependency_payload = {
        "python": observed["python"],
        **{
            key: observed[key]
            for key, _distribution_name in _WORKER_RUNTIME_DISTRIBUTIONS
        },
    }
    try:
        dependencies = C4Stage1DependencyVersions.model_validate(dependency_payload)
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 worker dependency versions differ from the frozen protocol"
        ) from exc
    if observed["python_implementation"] != "CPython":
        raise C4Stage1PreparationError(
            "Stage 1 worker Python implementation differs from the frozen protocol"
        )
    if path.parent.name.casefold() not in {"scripts", "bin"}:
        raise C4Stage1PreparationError(
            "Stage 1 worker Python must belong to a virtual environment"
        )
    worker_venv_root = path.parent.parent
    expected_site_packages = (
        worker_venv_root / "Lib" / "site-packages"
        if os.name == "nt"
        else worker_venv_root / "lib" / f"python{observed['python']}" / "site-packages"
    )
    observed_venv_root = Path(observed["_runtime_worker_venv_root"])
    observed_base_root = Path(observed["_runtime_base_root"])
    observed_site_packages = Path(observed["_runtime_site_packages"])
    for runtime_path in (
        observed_venv_root,
        observed_base_root,
        observed_site_packages,
    ):
        if not runtime_path.is_absolute() or runtime_path != _absolute_lexical(
            runtime_path
        ):
            raise C4Stage1PreparationError(
                "Stage 1 runtime metadata contains an invalid runtime path"
            )

    def same_lexical_path(left: Path, right: Path) -> bool:
        return os.path.normcase(os.fspath(left)) == os.path.normcase(os.fspath(right))

    if not same_lexical_path(
        observed_venv_root, worker_venv_root
    ) or not same_lexical_path(observed_site_packages, expected_site_packages):
        raise C4Stage1PreparationError(
            "Stage 1 runtime metadata escaped the worker virtual environment"
        )
    normalized_venv = os.path.normcase(os.fspath(worker_venv_root))
    normalized_base = os.path.normcase(os.fspath(observed_base_root))
    try:
        common = os.path.commonpath((normalized_venv, normalized_base))
    except ValueError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 runtime roots cannot be compared"
        ) from exc
    if common in {normalized_venv, normalized_base}:
        raise C4Stage1PreparationError(
            "Stage 1 worker and base runtime trees must be disjoint"
        )
    try:
        site_metadata = os.lstat(expected_site_packages)
    except OSError as exc:
        raise C4Stage1PreparationError(
            "Stage 1 worker site-packages directory is unavailable"
        ) from exc
    if _is_reparse_or_link(site_metadata) or not stat.S_ISDIR(site_metadata.st_mode):
        raise C4Stage1PreparationError(
            "Stage 1 worker site-packages must be an ordinary directory"
        )
    _stable_read_regular(
        worker_venv_root / "pyvenv.cfg",
        maximum_bytes=_MAX_WORKER_METADATA_BYTES,
    )
    worker_venv_inventory = _capture_runtime_tree_inventory(
        worker_venv_root,
        tree_role="worker-venv",
    )
    base_runtime_inventory = _capture_runtime_tree_inventory(
        observed_base_root,
        tree_role="base-runtime",
    )
    try:
        return C4Stage1WorkerRuntimePin.create(
            worker_python_sha256=hashlib.sha256(worker_python_bytes).hexdigest(),
            worker_python_size_bytes=len(worker_python_bytes),
            python_full_version=observed["python_full_version"],
            dependencies=dependencies,
            worker_venv_inventory=worker_venv_inventory,
            base_runtime_inventory=base_runtime_inventory,
        )
    except Exception as exc:
        raise C4Stage1PreparationError("Stage 1 worker runtime pin is invalid") from exc


def verify_c4_stage1_pre_spawn_runtime_bindings(
    paths: C4Stage1RuntimePaths,
    prepared_attempt: C4Stage1PreparedAttempt,
    *,
    cuda_device: ResourceTelemetryCudaDeviceIdentity,
    metadata_runner: WorkerRuntimeMetadataRunner = (
        _default_worker_runtime_metadata_runner
    ),
) -> None:
    """Reverify path-only bindings immediately before every child spawn."""

    if not isinstance(paths, C4Stage1RuntimePaths):
        raise TypeError("Stage 1 pre-spawn verification requires runtime paths")
    if not isinstance(cuda_device, ResourceTelemetryCudaDeviceIdentity):
        raise TypeError("Stage 1 pre-spawn verification requires a CUDA identity")
    prepared = C4Stage1PreparedAttempt.model_validate(
        prepared_attempt.model_dump(mode="python", round_trip=True)
    )
    observed_cuda = ResourceTelemetryCudaDeviceIdentity.model_validate(
        cuda_device.model_dump(mode="python", round_trip=True)
    )
    if observed_cuda != prepared.cuda_device:
        raise C4Stage1PreparationError(
            "Stage 1 CUDA identity changed after prepared receipt"
        )
    verify_c4_stage1_staging_parent(paths.staging_parent)
    observed_runtime = capture_c4_stage1_worker_runtime(
        paths.worker_python,
        metadata_runner=metadata_runner,
    )
    if observed_runtime != prepared.worker_runtime:
        raise C4Stage1PreparationError(
            "Stage 1 worker runtime changed after prepared receipt"
        )
    provenance = _stable_read_regular(
        paths.source_provenance,
        maximum_bytes=_MAX_PROVENANCE_BYTES,
    )
    if hashlib.sha256(provenance).hexdigest() != prepared.source_provenance_sha256:
        raise C4Stage1PreparationError(
            "Stage 1 source provenance changed after prepared receipt"
        )
    for relative_path, expected_sha256, expected_size, label in (
        (
            C4_STAGE1_BOOTSTRAP_SCRIPT_PATH,
            prepared.launch_policy.bootstrap_script_sha256,
            prepared.launch_policy.bootstrap_script_size_bytes,
            "bootstrap",
        ),
        (
            C4_STAGE1_WORKER_SCRIPT_PATH,
            prepared.launch_policy.worker_script_sha256,
            prepared.launch_policy.worker_script_size_bytes,
            "worker",
        ),
    ):
        script_path = paths.repository_root / relative_path
        _assert_unlinked_ancestry(script_path)
        script = _stable_read_regular(
            script_path,
            maximum_bytes=_MAX_WORKER_SCRIPT_BYTES,
        )
        if (
            hashlib.sha256(script).hexdigest() != expected_sha256
            or len(script) != expected_size
        ):
            raise C4Stage1PreparationError(
                f"Stage 1 {label} script changed after prepared receipt"
            )


def _load_exact_manifest(
    path: Path,
    *,
    expected_sha256: str,
) -> tuple[DiffusersSnapshotManifest, bytes]:
    raw = _stable_read_regular(path, maximum_bytes=_MAX_DOCUMENT_BYTES)
    try:
        manifest = DiffusersSnapshotManifest.model_validate_json(raw)
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 committed snapshot manifest is invalid"
        ) from exc
    canonical = canonical_snapshot_manifest_bytes(manifest)
    if hashlib.sha256(canonical).hexdigest() != expected_sha256:
        raise C4Stage1PreparationError(
            "Stage 1 committed snapshot manifest differs from its exact pin"
        )
    if not 0 < len(manifest.files) <= C4_STAGE1_MAX_SNAPSHOT_FILES:
        raise C4Stage1PreparationError("Stage 1 snapshot manifest has invalid coverage")
    return manifest, canonical


def _build_worker_requests(
    fixture: C4Stage1Fixture,
    *,
    specs: tuple[C4Stage1EditorSpec, C4Stage1EditorSpec],
    verified_snapshots: tuple[
        VerifiedC4Stage1Snapshot,
        VerifiedC4Stage1Snapshot,
    ],
    operator_policies: tuple[
        C4HumanReviewOperatorPolicy,
        C4HumanReviewOperatorPolicy,
    ],
) -> tuple[
    C4Stage1PreparedWorker,
    C4Stage1PreparedWorker,
    C4Stage1PreparedWorker,
    C4Stage1PreparedWorker,
]:
    prepared: list[C4Stage1PreparedWorker] = []
    builders = (build_longcat_turbo_worker_request, build_omnigen_worker_request)
    roles = ("primary", "alternate")
    for provider_index, (spec, verified, builder, policy, role) in enumerate(
        zip(
            specs,
            verified_snapshots,
            builders,
            operator_policies,
            roles,
            strict=True,
        )
    ):
        for option_index, prompt in enumerate(fixture.prompts):
            request = builder(
                editor_spec=spec,
                verified_snapshot=verified,
                scene=prompt.scene,
                source_image=fixture.source_image,
                seed=prompt.derived_seed,
                prompt=prompt.prompt,
                profile_hash=fixture.prompt_profile_hash,
            )
            prepared.append(
                C4Stage1PreparedWorker.create(
                    provider_order_index=provider_index,  # type: ignore[arg-type]
                    option_order_index=option_index,  # type: ignore[arg-type]
                    editor_role=role,  # type: ignore[arg-type]
                    option_id=prompt.option_id,
                    operator_policy_id=policy.policy_id,
                    worker_request=request,
                )
            )
    return tuple(prepared)  # type: ignore[return-value]


def _artifact_json_path(label: str, artifact_id: str) -> str:
    return f"diagnostics/{artifact_id}.{label}.json"


def _protocol_copy_path(pin: C4Stage1DocumentPin) -> str:
    return f"diagnostics/{pin.document_pin_id}.{pin.role}.md"


def _manifest_copy_path(role: Literal["primary", "alternate"]) -> str:
    return f"diagnostics/{role}.snapshot-manifest.json"


def _worker_script_copy_path(policy: C4Stage1LaunchPolicy) -> str:
    return f"diagnostics/{policy.launch_policy_id}.worker.py"


def _bootstrap_script_copy_path(policy: C4Stage1LaunchPolicy) -> str:
    return f"diagnostics/{policy.launch_policy_id}.bootstrap.py"


def _dino_script_copy_path(
    pin: C4Stage1DinoEntrypointPin,
    role: Literal["dino-bootstrap", "dino-worker"],
) -> str:
    suffix = "bootstrap.py" if role == "dino-bootstrap" else "worker.py"
    return f"diagnostics/{pin.dino_entrypoint_pin_id}.{suffix}"


def _prepared_json_payloads(
    *,
    repository_gate: C4Stage1RepositoryGate,
    dino_entrypoint_pin: C4Stage1DinoEntrypointPin,
    launch_policy: C4Stage1LaunchPolicy,
    worker_runtime: C4Stage1WorkerRuntimePin,
    telemetry_policy: C4Stage1TelemetryPolicy,
    review_schema: C4BlindHumanReviewSchema,
    operator_policies: tuple[
        C4HumanReviewOperatorPolicy,
        C4HumanReviewOperatorPolicy,
    ],
    display_policy: C4Stage1DisplayAttesterPolicy,
    review_runtime_manifest: C4Stage1ReviewRuntimeManifest,
    review_service_readiness: C4Stage1ReviewServiceReadiness,
    screen_contract: C4Stage1ScreenContract,
    workers: tuple[
        C4Stage1PreparedWorker,
        C4Stage1PreparedWorker,
        C4Stage1PreparedWorker,
        C4Stage1PreparedWorker,
    ],
) -> dict[str, bytes]:
    values: tuple[tuple[str, FrozenModel], ...] = (
        (
            _artifact_json_path("repository-gate", repository_gate.repository_gate_id),
            repository_gate,
        ),
        (
            _artifact_json_path(
                "dino-entrypoint-pin", dino_entrypoint_pin.dino_entrypoint_pin_id
            ),
            dino_entrypoint_pin,
        ),
        (
            _artifact_json_path("launch-policy", launch_policy.launch_policy_id),
            launch_policy,
        ),
        (
            _artifact_json_path("worker-runtime", worker_runtime.worker_runtime_id),
            worker_runtime,
        ),
        (
            _artifact_json_path(
                "telemetry-policy", telemetry_policy.telemetry_policy_id
            ),
            telemetry_policy,
        ),
        (
            _artifact_json_path("review-schema", review_schema.schema_id),
            review_schema,
        ),
        *tuple(
            (
                _artifact_json_path("operator-policy", policy.policy_id),
                policy,
            )
            for policy in operator_policies
        ),
        (
            _artifact_json_path("display-policy", display_policy.display_policy_id),
            display_policy,
        ),
        (
            _artifact_json_path(
                "review-runtime", review_runtime_manifest.runtime_manifest_id
            ),
            review_runtime_manifest,
        ),
        (
            _artifact_json_path(
                "review-service-readiness",
                review_service_readiness.readiness_receipt_id,
            ),
            review_service_readiness,
        ),
        (
            _artifact_json_path("screen-contract", screen_contract.screen_contract_id),
            screen_contract,
        ),
        *tuple(
            (
                _artifact_json_path(
                    "worker-request", item.worker_request.worker_request_id
                ),
                item.worker_request,
            )
            for item in workers
        ),
    )
    payloads = {path: canonical_json_bytes(value) for path, value in values}
    if len(payloads) != len(values):
        raise ValueError("Stage 1 prepared artifact paths are not unique")
    return payloads


def prepare_c4_stage1_attempt(
    *,
    run_id: str,
    paths: C4Stage1RuntimePaths,
    review_commitments: C4Stage1ReviewCommitments,
    cuda_device: ResourceTelemetryCudaDeviceIdentity,
    artifact_store: FileArtifactStore,
    review_service: C4Stage1ReviewServicePreflightPort,
    git_command_runner: GitCommandRunner = _default_git_command_runner,
    injected_git_runtime: C4Stage1GitRuntimePin | None = None,
    worker_metadata_runner: WorkerRuntimeMetadataRunner = (
        _default_worker_runtime_metadata_runner
    ),
) -> C4Stage1PreparedAttemptOutcome:
    """Verify and persist every pre-output boundary without loading a model."""

    if not isinstance(paths, C4Stage1RuntimePaths):
        raise TypeError("Stage 1 preparation requires runtime-only path bindings")
    if not isinstance(artifact_store, FileArtifactStore):
        raise TypeError("Stage 1 preparation requires FileArtifactStore")
    review_commitments = C4Stage1ReviewCommitments.model_validate(
        review_commitments.model_dump(mode="python", round_trip=True)
    )
    cuda_device = ResourceTelemetryCudaDeviceIdentity.model_validate(
        cuda_device.model_dump(mode="python", round_trip=True)
    )
    if cuda_device.status != "resolved" or cuda_device.logical_device_index != 0:
        raise C4Stage1PreparationError("Stage 1 requires a resolved CUDA identity")
    if artifact_store.run_path(run_id).exists():
        raise C4Stage1PreparationError("Stage 1 run ID must name a fresh run tree")

    repository_gate = capture_c4_stage1_repository_gate(
        paths.repository_root,
        command_runner=git_command_runner,
        injected_git_runtime=injected_git_runtime,
    )
    review_runtime_manifest, review_service_readiness = (
        verify_c4_stage1_live_review_boundary(
            repository_root=paths.repository_root,
            repository_gate=repository_gate,
            review_runtime_manifest=(review_commitments.review_runtime_manifest),
            review_service_readiness=(review_commitments.review_service_readiness),
            review_service=review_service,
            expected_completed_review_count=0,
        )
    )
    verify_c4_stage1_staging_parent(paths.staging_parent)
    worker_runtime = capture_c4_stage1_worker_runtime(
        paths.worker_python,
        metadata_runner=worker_metadata_runner,
    )
    protocol_raw = _stable_read_regular(
        paths.repository_root / C4_STAGE1_PROTOCOL_PATH,
        maximum_bytes=_MAX_DOCUMENT_BYTES,
    )
    addendum_raw = _stable_read_regular(
        paths.repository_root / C4_STAGE1_ADDENDUM_PATH,
        maximum_bytes=_MAX_DOCUMENT_BYTES,
    )
    protocol = C4Stage1DocumentPin.create(
        role="protocol",
        relative_path=C4_STAGE1_PROTOCOL_PATH,
        payload=protocol_raw,
    )
    addendum = C4Stage1DocumentPin.create(
        role="model_free_addendum",
        relative_path=C4_STAGE1_ADDENDUM_PATH,
        payload=addendum_raw,
    )
    _, primary_manifest_bytes = _load_exact_manifest(
        paths.repository_root / C4_STAGE1_PRIMARY_SNAPSHOT_MANIFEST_PATH,
        expected_sha256=LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256,
    )
    _, alternate_manifest_bytes = _load_exact_manifest(
        paths.repository_root / C4_STAGE1_ALTERNATE_SNAPSHOT_MANIFEST_PATH,
        expected_sha256=OMNIGEN_SNAPSHOT_MANIFEST_SHA256,
    )
    source_png = _stable_read_regular(
        paths.source_png,
        maximum_bytes=C4_STAGE1_MAX_PNG_BYTES,
    )
    if (
        hashlib.sha256(source_png).hexdigest()
        != "72c9fec75d838f0db9a9abc71cbd86c4f4e637c8f54f05c0ea629e12e0f6da58"
        or len(source_png) != 987_133
        or inspect_c4_stage1_png_bytes(source_png) != (1024, 768)
    ):
        raise C4Stage1PreparationError("Stage 1 source PNG differs from its exact pin")
    source_provenance = _stable_read_regular(
        paths.source_provenance,
        maximum_bytes=_MAX_PROVENANCE_BYTES,
    )
    source_provenance_sha256 = hashlib.sha256(source_provenance).hexdigest()
    source_pin = C4Stage1SourcePin.create(
        source_png_size_bytes=len(source_png),
        source_provenance_sha256=source_provenance_sha256,
    )

    specs = (longcat_turbo_stage1_spec(), omnigen_stage1_spec())
    bindings = (
        C4Stage1LocalSnapshotBinding.create(specs[0], paths.primary_snapshot),
        C4Stage1LocalSnapshotBinding.create(specs[1], paths.alternate_snapshot),
    )
    try:
        verified_snapshots = tuple(
            verify_c4_stage1_snapshot(spec, binding)
            for spec, binding in zip(specs, bindings, strict=True)
        )
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 external snapshot verification failed"
        ) from exc

    fixture = build_c4_stage1_fixture()
    schema = build_c4_blind_human_review_schema()
    operator_policies = tuple(
        build_c4_human_review_operator_policy(
            schema,
            run_id=run_id,
            candidate_slot_id=content_id(
                "c4_stage1_blind_candidate",
                {"run_id": run_id, "provider_order_index": index},
            ),
            source_image_sha256=fixture.source_image.content_sha256,
            hmac_key_commitment_sha256=key_commitment,
        )
        for index, key_commitment in enumerate(
            review_commitments.operator_hmac_key_commitments_sha256
        )
    )
    display_policy = build_c4_stage1_display_attester_policy(
        policy_nonce=review_commitments.display_policy_nonce,
        ui_bundle_sha256=review_commitments.ui_bundle_sha256,
        content_security_policy=review_commitments.content_security_policy,
        presenter_implementation_id=(review_commitments.presenter_implementation_id),
        presenter_revision=review_commitments.presenter_revision,
        display_attester_id=review_commitments.display_attester_id,
        display_signing_key_commitment_sha256=(
            review_commitments.display_signing_key_commitment_sha256
        ),
    )
    telemetry_policy = c4_stage1_telemetry_policy()
    screen_contract = C4Stage1ScreenContract.create(
        protocol=protocol,
        model_free_addendum=addendum,
        fixture=fixture,
        source=source_pin,
        editor_specs=specs,
        review_schema=_content_pin("review_schema", schema),
        review_operator_policies=tuple(
            _content_pin("review_operator_policy", policy)
            for policy in operator_policies
        ),
        display_policy=c4_stage1_display_policy_content_pin(display_policy),
        review_runtime=_review_runtime_content_pin(review_runtime_manifest),
        review_service_readiness=_review_service_readiness_content_pin(
            review_service_readiness
        ),
        telemetry_policy=_telemetry_content_pin(telemetry_policy),
        dino_policy=C4Stage1DinoPolicy.create(dinov2_base_provider_identity()),
    )
    bootstrap_script = _stable_read_regular(
        paths.repository_root / C4_STAGE1_BOOTSTRAP_SCRIPT_PATH,
        maximum_bytes=_MAX_WORKER_SCRIPT_BYTES,
    )
    worker_script = _stable_read_regular(
        paths.repository_root / C4_STAGE1_WORKER_SCRIPT_PATH,
        maximum_bytes=_MAX_WORKER_SCRIPT_BYTES,
    )
    dino_bootstrap_script = _stable_read_regular(
        paths.repository_root / C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH,
        maximum_bytes=_MAX_WORKER_SCRIPT_BYTES,
    )
    dino_worker_script = _stable_read_regular(
        paths.repository_root / C4_STAGE1_DINO_WORKER_SCRIPT_PATH,
        maximum_bytes=_MAX_WORKER_SCRIPT_BYTES,
    )
    dino_entrypoint_pin = C4Stage1DinoEntrypointPin.create(
        repository_gate=repository_gate,
        bootstrap_script=dino_bootstrap_script,
        worker_script=dino_worker_script,
    )
    launch_policy = C4Stage1LaunchPolicy.create(
        worker_script,
        bootstrap_script=bootstrap_script,
        cuda_device=cuda_device,
        worker_runtime=worker_runtime,
    )
    workers = _build_worker_requests(
        fixture,
        specs=specs,
        verified_snapshots=verified_snapshots,  # type: ignore[arg-type]
        operator_policies=operator_policies,  # type: ignore[arg-type]
    )

    json_payloads = _prepared_json_payloads(
        repository_gate=repository_gate,
        dino_entrypoint_pin=dino_entrypoint_pin,
        launch_policy=launch_policy,
        worker_runtime=worker_runtime,
        telemetry_policy=telemetry_policy,
        review_schema=schema,
        operator_policies=operator_policies,  # type: ignore[arg-type]
        display_policy=display_policy,
        review_runtime_manifest=review_runtime_manifest,
        review_service_readiness=review_service_readiness,
        screen_contract=screen_contract,
        workers=workers,
    )
    binary_payloads = {
        fixture.source_image.path: source_png,
        _protocol_copy_path(protocol): normalized_utf8_document_bytes(protocol_raw),
        _protocol_copy_path(addendum): normalized_utf8_document_bytes(addendum_raw),
        _manifest_copy_path("primary"): primary_manifest_bytes,
        _manifest_copy_path("alternate"): alternate_manifest_bytes,
        _bootstrap_script_copy_path(launch_policy): bootstrap_script,
        _worker_script_copy_path(launch_policy): worker_script,
        _dino_script_copy_path(
            dino_entrypoint_pin, "dino-bootstrap"
        ): dino_bootstrap_script,
        _dino_script_copy_path(
            dino_entrypoint_pin, "dino-worker"
        ): dino_worker_script,
    }
    payloads = {**json_payloads, **binary_payloads}
    if len(payloads) != len(json_payloads) + len(binary_payloads):
        raise C4Stage1PreparationError("Stage 1 prepared artifact paths collide")

    stored: list[StoredArtifact] = []
    try:
        for relative_path, payload in sorted(payloads.items()):
            stored.append(
                artifact_store.write_bytes(
                    run_id,
                    relative_path,
                    payload,
                    overwrite=False,
                )
            )
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 prepared artifact persistence failed"
        ) from exc
    prepared = C4Stage1PreparedAttempt.create(
        run_id=run_id,
        repository_gate=repository_gate,
        dino_entrypoint_pin=dino_entrypoint_pin,
        launch_policy=launch_policy,
        worker_runtime=worker_runtime,
        cuda_device=cuda_device,
        source_provenance_sha256=source_provenance_sha256,
        telemetry_policy=telemetry_policy,
        review_schema=schema,
        review_operator_policies=operator_policies,  # type: ignore[arg-type]
        display_policy=display_policy,
        review_runtime_manifest=review_runtime_manifest,
        review_service_readiness=review_service_readiness,
        screen_contract=screen_contract,
        workers=workers,
        artifact_inventory_before_anchor=tuple(
            sorted(stored, key=lambda item: item.relative_path)
        ),
    )
    try:
        anchor_storage = artifact_store.write_json(
            run_id,
            C4_STAGE1_PREPARED_ANCHOR_PATH,
            prepared,
            overwrite=False,
        )
    except Exception as exc:
        raise C4Stage1PreparationError(
            "Stage 1 prepared anchor persistence failed"
        ) from exc
    outcome = C4Stage1PreparedAttemptOutcome(
        prepared_attempt=prepared,
        prepared_anchor_storage=anchor_storage,
    )
    cold = cold_verify_c4_stage1_prepared_attempt(
        FileArtifactStore(artifact_store.root, create=False),
        anchor_storage,
        require_exact_pre_spawn_inventory=True,
    )
    if cold.prepared_attempt != prepared:
        raise C4Stage1PreparationError("Stage 1 prepared cold replay differs")
    return outcome


def _require_descriptor_payload(
    artifact_store: FileArtifactStore,
    descriptor: StoredArtifact,
    expected: bytes,
) -> None:
    try:
        actual = artifact_store.read_bytes(descriptor.storage_id)
    except Exception as exc:
        raise C4Stage1ColdVerificationError(
            "Stage 1 prepared artifact is not cold-readable"
        ) from exc
    if (
        actual != expected
        or descriptor.content_sha256 != hashlib.sha256(expected).hexdigest()
        or descriptor.size_bytes != len(expected)
    ):
        raise C4Stage1ColdVerificationError(
            "Stage 1 prepared artifact differs from its descriptor"
        )


def _cold_verify_dino_entrypoint_copies(
    artifact_store: FileArtifactStore,
    prepared: C4Stage1PreparedAttempt,
    descriptor_by_path: Mapping[str, StoredArtifact],
) -> None:
    """Cold-read both prepared DINO entrypoint copies against their Git-byte pin."""

    for script_pin in prepared.dino_entrypoint_pin.scripts:
        relative_path = _dino_script_copy_path(
            prepared.dino_entrypoint_pin,
            script_pin.role,
        )
        descriptor = descriptor_by_path.get(relative_path)
        if descriptor is None:
            raise C4Stage1ColdVerificationError(
                "Stage 1 prepared DINO entrypoint copy is absent"
            )
        try:
            script = artifact_store.read_bytes(descriptor.storage_id)
        except Exception as exc:
            raise C4Stage1ColdVerificationError(
                f"Stage 1 prepared {script_pin.role} script is not cold-readable"
            ) from exc
        if (
            hashlib.sha256(script).hexdigest() != script_pin.content_sha256
            or len(script) != script_pin.size_bytes
            or descriptor.run_id != prepared.run_id
            or descriptor.relative_path != relative_path
            or descriptor.content_sha256 != script_pin.content_sha256
            or descriptor.size_bytes != script_pin.size_bytes
        ):
            raise C4Stage1ColdVerificationError(
                f"Stage 1 prepared {script_pin.role} script differs from its exact pin"
            )


def cold_verify_c4_stage1_prepared_attempt(
    artifact_store: FileArtifactStore,
    prepared_anchor_storage: StoredArtifact,
    *,
    require_exact_pre_spawn_inventory: bool,
) -> C4Stage1PreparedAttemptOutcome:
    """Cold-read the prepared anchor and every exact pre-spawn artifact."""

    if not isinstance(artifact_store, FileArtifactStore):
        raise TypeError("Stage 1 cold verification requires FileArtifactStore")
    if type(require_exact_pre_spawn_inventory) is not bool:
        raise TypeError("Stage 1 exact-inventory selector must be a boolean")
    storage = StoredArtifact.model_validate(
        prepared_anchor_storage.model_dump(mode="python", round_trip=True)
    )
    if storage.relative_path != C4_STAGE1_PREPARED_ANCHOR_PATH:
        raise C4Stage1ColdVerificationError(
            "Stage 1 prepared anchor has the wrong relative path"
        )
    try:
        anchor_bytes = artifact_store.read_bytes(storage.storage_id)
        prepared = C4Stage1PreparedAttempt.model_validate_json(anchor_bytes)
    except Exception as exc:
        raise C4Stage1ColdVerificationError(
            "Stage 1 prepared anchor failed cold parsing"
        ) from exc
    if (
        canonical_json_bytes(prepared) != anchor_bytes
        or storage.run_id != prepared.run_id
        or storage.content_sha256 != hashlib.sha256(anchor_bytes).hexdigest()
        or storage.size_bytes != len(anchor_bytes)
    ):
        raise C4Stage1ColdVerificationError(
            "Stage 1 prepared anchor differs from canonical content"
        )

    json_payloads = _prepared_json_payloads(
        repository_gate=prepared.repository_gate,
        dino_entrypoint_pin=prepared.dino_entrypoint_pin,
        launch_policy=prepared.launch_policy,
        worker_runtime=prepared.worker_runtime,
        telemetry_policy=prepared.telemetry_policy,
        review_schema=prepared.review_schema,
        operator_policies=prepared.review_operator_policies,
        display_policy=prepared.display_policy,
        review_runtime_manifest=prepared.review_runtime_manifest,
        review_service_readiness=prepared.review_service_readiness,
        screen_contract=prepared.screen_contract,
        workers=prepared.workers,
    )
    expected_paths = {
        *json_payloads,
        prepared.screen_contract.fixture.source_image.path,
        _protocol_copy_path(prepared.screen_contract.protocol),
        _protocol_copy_path(prepared.screen_contract.model_free_addendum),
        _manifest_copy_path("primary"),
        _manifest_copy_path("alternate"),
        _bootstrap_script_copy_path(prepared.launch_policy),
        _worker_script_copy_path(prepared.launch_policy),
        *(
            _dino_script_copy_path(prepared.dino_entrypoint_pin, script.role)
            for script in prepared.dino_entrypoint_pin.scripts
        ),
    }
    descriptor_by_path = {
        item.relative_path: item for item in prepared.artifact_inventory_before_anchor
    }
    if set(descriptor_by_path) != expected_paths:
        raise C4Stage1ColdVerificationError(
            "Stage 1 prepared inventory paths differ from the contract"
        )
    for relative_path, payload in json_payloads.items():
        _require_descriptor_payload(
            artifact_store,
            descriptor_by_path[relative_path],
            payload,
        )
    _cold_verify_dino_entrypoint_copies(
        artifact_store,
        prepared,
        descriptor_by_path,
    )

    source_descriptor = descriptor_by_path[
        prepared.screen_contract.fixture.source_image.path
    ]
    try:
        source_bytes = artifact_store.read_bytes(source_descriptor.storage_id)
    except Exception as exc:
        raise C4Stage1ColdVerificationError(
            "Stage 1 prepared source is not cold-readable"
        ) from exc
    source = prepared.screen_contract.source
    if (
        hashlib.sha256(source_bytes).hexdigest() != source.source_png_sha256
        or len(source_bytes) != source.source_png_size_bytes
        or inspect_c4_stage1_png_bytes(source_bytes)
        != (source.source_width, source.source_height)
        or source_descriptor.content_sha256 != source.source_png_sha256
        or source_descriptor.size_bytes != source.source_png_size_bytes
    ):
        raise C4Stage1ColdVerificationError(
            "Stage 1 prepared source differs from its exact pin"
        )

    for pin in (
        prepared.screen_contract.protocol,
        prepared.screen_contract.model_free_addendum,
    ):
        descriptor = descriptor_by_path[_protocol_copy_path(pin)]
        try:
            payload = artifact_store.read_bytes(descriptor.storage_id)
        except Exception as exc:
            raise C4Stage1ColdVerificationError(
                "Stage 1 prepared document is not cold-readable"
            ) from exc
        if (
            normalized_utf8_document_bytes(payload) != payload
            or hashlib.sha256(payload).hexdigest() != pin.normalized_utf8_sha256
            or len(payload) != pin.normalized_size_bytes
            or descriptor.content_sha256 != pin.normalized_utf8_sha256
            or descriptor.size_bytes != pin.normalized_size_bytes
        ):
            raise C4Stage1ColdVerificationError(
                "Stage 1 prepared document differs from its normalized pin"
            )

    editor_by_role = {item.role: item for item in prepared.screen_contract.editors}
    for role in ("primary", "alternate"):
        descriptor = descriptor_by_path[_manifest_copy_path(role)]
        try:
            payload = artifact_store.read_bytes(descriptor.storage_id)
            manifest = DiffusersSnapshotManifest.model_validate_json(payload)
        except Exception as exc:
            raise C4Stage1ColdVerificationError(
                "Stage 1 prepared snapshot manifest is invalid"
            ) from exc
        editor = editor_by_role[role]
        if (
            canonical_snapshot_manifest_bytes(manifest) != payload
            or hashlib.sha256(payload).hexdigest() != editor.snapshot_manifest_sha256
            or manifest.repo_id != editor.repo_id
            or manifest.revision != editor.revision
            or len(manifest.files) != editor.snapshot_file_count
            or sum(item.size_bytes for item in manifest.files)
            != editor.snapshot_total_bytes
            or descriptor.content_sha256 != editor.snapshot_manifest_sha256
            or descriptor.size_bytes != len(payload)
        ):
            raise C4Stage1ColdVerificationError(
                "Stage 1 prepared snapshot manifest differs from editor pin"
            )

    for relative_path, expected_sha256, expected_size, label in (
        (
            _bootstrap_script_copy_path(prepared.launch_policy),
            prepared.launch_policy.bootstrap_script_sha256,
            prepared.launch_policy.bootstrap_script_size_bytes,
            "bootstrap",
        ),
        (
            _worker_script_copy_path(prepared.launch_policy),
            prepared.launch_policy.worker_script_sha256,
            prepared.launch_policy.worker_script_size_bytes,
            "worker",
        ),
    ):
        descriptor = descriptor_by_path[relative_path]
        try:
            script = artifact_store.read_bytes(descriptor.storage_id)
        except Exception as exc:
            raise C4Stage1ColdVerificationError(
                f"Stage 1 prepared {label} script is not cold-readable"
            ) from exc
        if (
            hashlib.sha256(script).hexdigest() != expected_sha256
            or len(script) != expected_size
            or descriptor.content_sha256 != expected_sha256
            or descriptor.size_bytes != expected_size
        ):
            raise C4Stage1ColdVerificationError(
                f"Stage 1 prepared {label} script differs from its exact pin"
            )

    if require_exact_pre_spawn_inventory:
        try:
            actual_inventory = artifact_store.inspect_run_inventory_exact(
                prepared.run_id
            )
        except Exception as exc:
            raise C4Stage1ColdVerificationError(
                "Stage 1 prepared run inventory cannot be inspected exactly"
            ) from exc
        expected_inventory = tuple(
            sorted(
                (*prepared.artifact_inventory_before_anchor, storage),
                key=lambda item: item.relative_path,
            )
        )
        if actual_inventory != expected_inventory:
            raise C4Stage1ColdVerificationError(
                "Stage 1 run changed before the first worker spawn"
            )
    return C4Stage1PreparedAttemptOutcome(
        prepared_attempt=prepared,
        prepared_anchor_storage=storage,
    )


__all__ = [
    "C4_STAGE1_BOOTSTRAP_SCRIPT_PATH",
    "C4_STAGE1_CUDA_STOP_BYTES",
    "C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH",
    "C4_STAGE1_DINO_WORKER_SCRIPT_PATH",
    "C4_STAGE1_GIT_SCOPE_PATHS",
    "C4_STAGE1_ORIGIN_URL",
    "C4_STAGE1_PREPARED_ANCHOR_PATH",
    "C4_STAGE1_TELEMETRY_CADENCE_SECONDS",
    "C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS",
    "C4_STAGE1_TELEMETRY_MAX_SAMPLES",
    "C4_STAGE1_WORKER_SCRIPT_PATH",
    "C4Stage1ColdVerificationError",
    "C4Stage1DinoEntrypointPin",
    "C4Stage1DinoEntrypointScriptPin",
    "C4Stage1GitRuntimePin",
    "C4Stage1LaunchPolicy",
    "C4Stage1PreparationError",
    "C4Stage1PreparedAttempt",
    "C4Stage1PreparedAttemptOutcome",
    "C4Stage1PreparedWorker",
    "C4Stage1RepositoryGate",
    "C4Stage1ReviewCommitments",
    "C4Stage1ReviewServicePreflightPort",
    "C4Stage1RuntimePaths",
    "C4Stage1RuntimeTreeInventoryPin",
    "C4Stage1WorkerRuntimePin",
    "WorkerRuntimeMetadataRunner",
    "build_c4_stage1_worker_environment",
    "capture_c4_stage1_repository_gate",
    "capture_c4_stage1_worker_runtime",
    "cold_verify_c4_stage1_prepared_attempt",
    "prepare_c4_stage1_attempt",
    "verify_c4_stage1_live_review_boundary",
    "verify_c4_stage1_pre_spawn_runtime_bindings",
    "verify_c4_stage1_staging_parent",
]
