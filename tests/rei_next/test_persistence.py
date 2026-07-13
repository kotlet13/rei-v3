from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

import pytest

from app.backend.rei_next.persistence import (
    RUN_TREE_DIRECTORIES,
    ArtifactExistsError,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStore,
    FileArtifactStore,
    StoredArtifact,
    stored_artifact_id,
    validate_relative_path,
    validate_run_id,
    validate_stored_artifact,
)


def test_file_store_writes_canonical_json_and_complete_run_tree(tmp_path: Path) -> None:
    runs_root = tmp_path / "output" / "runs"
    store = FileArtifactStore(runs_root)
    run_root = store.ensure_run_tree("run_ž_1")

    assert isinstance(store, ArtifactStore)
    assert store.root == runs_root.resolve()
    assert store.identity.kind == "artifact_store"
    assert all(
        run_root.joinpath(*relative.split("/")).is_dir()
        for relative in RUN_TREE_DIRECTORIES
    )

    artifact = store.write_json(
        "run_ž_1",
        "native/bundle.json",
        {"z": [3, 2], "a": "ž"},
    )
    expected_bytes = b'{"a":"\xc5\xbe","z":[3,2]}'
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()

    assert store.artifact_path("run_ž_1", "native/bundle.json").read_bytes() == (
        expected_bytes
    )
    assert artifact == StoredArtifact(
        storage_id=stored_artifact_id(
            run_id="run_ž_1",
            relative_path="native/bundle.json",
            content_sha256=expected_hash,
            size_bytes=len(expected_bytes),
        ),
        run_id="run_ž_1",
        relative_path="native/bundle.json",
        content_sha256=expected_hash,
        size_bytes=len(expected_bytes),
    )
    assert validate_stored_artifact(artifact) is artifact
    assert store.inspect(
        "run_ž_1",
        "native/bundle.json",
        expected=artifact,
    ) == artifact
    assert store.read_verified(artifact) == expected_bytes


@pytest.mark.parametrize(
    "run_id",
    (
        "",
        ".",
        "..",
        "/absolute",
        "\\absolute",
        "C:/absolute",
        "C:\\absolute",
        "//server/share",
        "\\\\server\\share",
        "run/child",
        "run\\child",
        " run",
        "run ",
        "run.",
        "run:name",
        "run\x00name",
        "CON",
        "con.json",
        "AUX.txt",
        "COM1",
        "RunA",
        "RUN_A",
        "run_A",
        "run\u006e\u030c",
        "lpt9.log",
        "CONIN$",
        "run~1",
        "a" * 256,
        "run\ud800",
        "\U0001f600" * 130,
        "com¹.txt",
    ),
)
def test_run_id_rejects_unsafe_and_windows_device_names(run_id: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        validate_run_id(run_id)


@pytest.mark.parametrize(
    "relative_path",
    (
        "",
        ".",
        "..",
        "/native/bundle.json",
        "\\native\\bundle.json",
        "C:/native/bundle.json",
        "C:\\native\\bundle.json",
        "//server/share.json",
        "native//bundle.json",
        "native/./bundle.json",
        "native/../bundle.json",
        "native\\bundle.json",
        "native/CON.json",
        "native/aux.txt",
        "native/COM1.bin",
        "native/conout$.txt",
        "native/LPT².log",
        "native/trailing.",
        "native/trailing ",
        "native/control\x1f.json",
        "native/Foo.json",
        "Native/foo.json",
        "other/not-in-run-tree.json",
        "native/.rei-artifact-collision.tmp",
        "native/file~1.json",
        f"native/{'a' * 256}.json",
        "native/bad\ud800.json",
    ),
)
def test_relative_path_rejects_escape_slash_variants_and_device_names(
    relative_path: str,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        validate_relative_path(relative_path)


def test_create_is_atomic_concurrent_and_never_overwrites(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "runs")

    def write(content: bytes) -> StoredArtifact | Exception:
        try:
            return store.write_bytes("run_atomic", "diagnostics/report.md", content)
        except Exception as exc:  # the result is asserted below
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(write, (b"first", b"second")))

    successes = tuple(item for item in results if isinstance(item, StoredArtifact))
    conflicts = tuple(item for item in results if isinstance(item, ArtifactExistsError))
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert store.read_verified(successes[0]) in {b"first", b"second"}

    with pytest.raises(ArtifactExistsError):
        store.write_bytes("run_atomic", "diagnostics/report.md", b"replacement")
    with pytest.raises(ValueError, match="never permits overwrite"):
        store.write_bytes(
            "run_atomic",
            "diagnostics/other.md",
            b"replacement",
            overwrite=True,
        )


def test_create_is_atomic_across_processes(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    code = """
from pathlib import Path
import sys
from app.backend.rei_next.persistence import ArtifactExistsError, FileArtifactStore
try:
    FileArtifactStore(Path(sys.argv[1])).write_bytes(
        "run_process", "diagnostics/report.md", sys.argv[2].encode("ascii")
    )
except ArtifactExistsError:
    print("exists")
else:
    print("created")
"""
    processes = tuple(
        subprocess.Popen(
            [sys.executable, "-c", code, str(root), payload],
            cwd=Path(__file__).resolve().parents[2],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for payload in ("first", "second")
    )
    completed = tuple(process.communicate(timeout=30) for process in processes)
    assert all(process.returncode == 0 for process in processes), completed
    assert sorted(stdout.strip() for stdout, _ in completed) == ["created", "exists"]
    assert (root / "run_process" / "diagnostics" / "report.md").read_bytes() in {
        b"first",
        b"second",
    }


def test_restart_lookup_and_tamper_detection_verify_bytes_and_metadata(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    first = FileArtifactStore(root)
    artifact = first.write_bytes(
        "run_restart",
        "communication/interpretations.json",
        b"[]",
    )

    restarted = FileArtifactStore(root)
    assert restarted.read_bytes(artifact.storage_id) == b"[]"
    assert restarted.inspect(
        artifact.run_id,
        artifact.relative_path,
        expected=artifact,
    ) == artifact

    target = restarted.artifact_path(artifact.run_id, artifact.relative_path)
    target.write_bytes(b"[{}]")
    with pytest.raises(ArtifactIntegrityError):
        restarted.read_verified(artifact)
    with pytest.raises(ArtifactIntegrityError):
        restarted.inspect(
            artifact.run_id,
            artifact.relative_path,
            expected=artifact,
        )
    with pytest.raises(ArtifactNotFoundError):
        FileArtifactStore(root).read_bytes(artifact.storage_id)


def test_restart_lookup_streams_artifacts_larger_than_previous_scan_limit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    content = b"x" * (64 * 1024 * 1024 + 1)
    artifact = FileArtifactStore(root).write_bytes(
        "run_large",
        "emocio/images/large.bin",
        content,
    )

    restarted = FileArtifactStore(root)
    assert restarted.inspect(artifact.run_id, artifact.relative_path) == artifact
    assert restarted.read_bytes(artifact.storage_id) == content


def test_content_addressed_metadata_rejects_self_consistent_field_tampering(
    tmp_path: Path,
) -> None:
    store = FileArtifactStore(tmp_path / "runs")
    artifact = store.write_bytes("run_metadata", "ego/measure.json", b"{}")

    wrong_id = artifact.model_copy(update={"storage_id": "stored_" + "0" * 32})
    wrong_hash = artifact.model_copy(update={"content_sha256": "f" * 64})
    with pytest.raises(ArtifactIntegrityError, match="canonical metadata"):
        validate_stored_artifact(wrong_id)
    with pytest.raises(ArtifactIntegrityError, match="canonical metadata"):
        store.read_verified(wrong_hash)


def test_symlink_or_reparse_parent_cannot_escape_run_root(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "runs")
    run_root = store.ensure_run_tree("run_link")
    outside = tmp_path / "outside"
    outside.mkdir()
    native = run_root / "native"
    native.rmdir()
    try:
        native.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("This platform does not permit directory symlinks for the test user")

    with pytest.raises(ArtifactIntegrityError, match="symlink or reparse point"):
        store.write_bytes("run_link", "native/escape.bin", b"must stay inside")
    assert not (outside / "escape.bin").exists()


def test_read_rejects_leaf_symlink_replacement(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "runs")
    artifact = store.write_bytes("run_leaf_link", "native/racio.json", b"{}")
    target = store.artifact_path(artifact.run_id, artifact.relative_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"{}")
    target.unlink()
    try:
        target.symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("This platform does not permit file symlinks for the test user")

    with pytest.raises(ArtifactIntegrityError, match="symlink or reparse point"):
        store.read_verified(artifact)


def test_configured_root_cannot_adopt_symlink_or_reparse_target(tmp_path: Path) -> None:
    outside = tmp_path / "outside_root"
    outside.mkdir()
    configured = tmp_path / "configured_root"
    try:
        configured.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("This platform does not permit directory symlinks for the test user")

    with pytest.raises(ValueError, match="root ancestry.*symlink|reparse"):
        FileArtifactStore(configured)


def test_expected_size_rejects_oversized_sparse_tamper_before_read(
    tmp_path: Path,
) -> None:
    store = FileArtifactStore(tmp_path / "runs")
    artifact = store.write_bytes("run_sparse", "ego/measure.json", b"{}")
    target = store.artifact_path(artifact.run_id, artifact.relative_path)
    with target.open("wb") as handle:
        handle.truncate(65 * 1024 * 1024)

    with pytest.raises(ArtifactIntegrityError, match="size differs"):
        store.read_verified(artifact)
