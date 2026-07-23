"""Create one canonical public commitment file from the live review service."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
_AUTHORITY_ENTRYPOINT = ROOT / "scripts" / "run_rei_c4_stage1_review.py"


_WINDOWS_REPARSE_ATTRIBUTE = 0x0400


def _absolute(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("C4 Stage 1 paths must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-runtime-root", type=_absolute, required=True)
    parser.add_argument("--review-browser-root", type=_absolute, required=True)
    parser.add_argument(
        "--review-runtime-provenance-root", type=_absolute, required=True
    )
    parser.add_argument("--confirmed-review-runtime-provenance-id", required=True)
    parser.add_argument("--confirmed-review-runtime-provenance-sha256", required=True)
    parser.add_argument("--confirmed-review-runtime-manifest-id", required=True)
    parser.add_argument("--confirmed-review-runtime-manifest-sha256", required=True)
    parser.add_argument("--confirmed-review-runtime-python-sha256", required=True)
    parser.add_argument("--repository-root", type=_absolute, default=ROOT)
    parser.add_argument("--review-service-host", default="127.0.0.1")
    parser.add_argument("--review-service-port", type=int, required=True)
    parser.add_argument("--review-service-auth-secret", type=_absolute, required=True)
    parser.add_argument("--review-service-timeout-seconds", type=float, default=3606.0)
    parser.add_argument("--review-presenter-timeout-ms", type=int, default=3_600_000)
    parser.add_argument("--output", type=_absolute, required=True)
    return parser


def _load_stdlib_preflight_support() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_rei_c4_stage1_review_authority_preflight",
        _AUTHORITY_ENTRYPOINT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Review authority preflight support is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_application_modules() -> object:
    global C4Stage1ReviewCommitments
    global C4Stage1ReviewServiceClient
    global capture_c4_stage1_repository_gate
    global capture_c4_stage1_review_runtime_manifest
    global verify_c4_stage1_live_review_boundary
    from rei.evaluation import c4_stage1_review_environment
    from rei.evaluation.c4_stage1_attempt import (
        C4Stage1ReviewCommitments,
        capture_c4_stage1_repository_gate,
        verify_c4_stage1_live_review_boundary,
    )
    from rei.evaluation.c4_stage1_review_runtime import (
        capture_c4_stage1_review_runtime_manifest,
    )
    from rei.evaluation.c4_stage1_review_service import (
        C4Stage1ReviewServiceClient,
    )

    return c4_stage1_review_environment


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _write_new_ordinary(path: Path, payload: bytes) -> None:
    parent = path.parent.resolve(strict=True)
    if parent != path.parent:
        raise ValueError("Commitment output ancestry must be lexical and unlinked")
    parent_metadata = os.lstat(parent)
    if _is_link_or_reparse(parent_metadata) or not stat.S_ISDIR(
        parent_metadata.st_mode
    ):
        raise ValueError("Commitment parent must be an ordinary directory")
    target = parent / path.name
    if target != path or target.exists() or target.is_symlink():
        raise ValueError("Commitment output must be one fresh lexical path")
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(target, flags, 0o600)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ValueError("Commitment output is not an ordinary file")
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short commitment write")
            view = view[written:]
        os.fsync(descriptor)
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    final_path = os.lstat(target)
    if (
        _is_link_or_reparse(final_path)
        or final_path.st_nlink != 1
        or not os.path.samestat(opened, final_handle)
        or not os.path.samestat(opened, final_path)
        or final_path.st_size != len(payload)
    ):
        raise ValueError("Commitment output changed while writing")


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        preflight_support = _load_stdlib_preflight_support()
        preflight = preflight_support._stdlib_runtime_preflight(arguments)
        preflight_support._activate_verified_application_paths(preflight)
        review_environment = _load_application_modules()
        preflight_support._verify_with_application(
            preflight,
            review_environment,
        )
        repository_root = arguments.repository_root.resolve(strict=True)
        if repository_root != ROOT.resolve(strict=True):
            raise ValueError(
                "Commitments must verify the checkout that supplies this CLI"
            )
        output_parent = arguments.output.parent.resolve(strict=True)
        if output_parent == repository_root or output_parent.is_relative_to(
            repository_root
        ):
            raise ValueError("Commitments must be written outside the repository")
        runtime = capture_c4_stage1_review_runtime_manifest(repository_root)
        repository_gate = capture_c4_stage1_repository_gate(repository_root)
        service = C4Stage1ReviewServiceClient(
            arguments.review_service_host,
            arguments.review_service_port,
            auth_secret_path=arguments.review_service_auth_secret,
            timeout_seconds=arguments.review_service_timeout_seconds,
            presenter_timeout_ms=arguments.review_presenter_timeout_ms,
        )
        runtime, readiness = verify_c4_stage1_live_review_boundary(
            repository_root=repository_root,
            repository_gate=repository_gate,
            review_runtime_manifest=runtime,
            review_service_readiness=service.readiness,
            review_service=service,
            expected_completed_review_count=0,
        )
        commitments = C4Stage1ReviewCommitments.create(
            review_runtime_manifest=runtime,
            review_service_readiness=readiness,
            display_policy_nonce=secrets.token_hex(32),
        )
        _write_new_ordinary(arguments.output, commitments.canonical_json_bytes())
        sys.stdout.write(
            json.dumps(
                {
                    "action": "review_commitments_created",
                    "output": str(arguments.output),
                    "review_runtime_manifest_id": runtime.runtime_manifest_id,
                    "review_service_readiness_id": readiness.readiness_receipt_id,
                    "model_calls": 0,
                },
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return 0
    except Exception as exc:
        sys.stderr.write(
            f"C4 Stage 1 review commitments stopped: {type(exc).__name__}\n"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
