"""Create the complete byte-level lineage for the frozen E2 protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
E2_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e2"
OUTPUT = E2_ROOT / "protocol_lineage.json"
REPO_FILES = (
    ".gitattributes",
    "scripts/acquire_emocio_vwm_e2_metric_weights.ps1",
    "scripts/bootstrap_emocio_vwm_e2_env.ps1",
    "scripts/freeze_emocio_vwm_e2_dataset.py",
    "scripts/run_emocio_vwm_e2.py",
    "scripts/seal_emocio_vwm_e2_protocol.py",
    "tests/research/test_emocio_vwm_e2_protocol.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path: Path, *, root: str, relative: str) -> dict[str, object]:
    return {"root": root, "path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> int:
    files = [
        record(path, root="e2", relative=path.relative_to(E2_ROOT).as_posix())
        for path in sorted(E2_ROOT.rglob("*"))
        if path.is_file() and path != OUTPUT and "__pycache__" not in path.parts
    ]
    files.extend(
        record(REPO_ROOT / relative, root="repo", relative=relative)
        for relative in REPO_FILES
    )
    files.sort(key=lambda item: (str(item["root"]), str(item["path"])))
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    output = {
        "schema_version": "rei-emocio-vwm-e2-protocol-lineage-v1",
        "algorithm": "sha256",
        "file_count": len(files),
        "protocol_tree_sha256": hashlib.sha256(payload).hexdigest(),
        "files": files,
    }
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"file_count": len(files), "protocol_tree_sha256": output["protocol_tree_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
