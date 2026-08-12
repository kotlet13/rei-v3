from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E3R = ROOT / "research/emocio_vwm_mvp_e3r"
FILES = [
    E3R / "README.md",
    E3R / "specs/e3r_protocol_freeze.json",
    E3R / "python/emocio_vwm_mvp_e3r/__init__.py",
    E3R / "python/emocio_vwm_mvp_e3r/preflight.py",
    E3R / "python/emocio_vwm_mvp_e3r/shape_contract.py",
    E3R / "python/emocio_vwm_mvp_e3r/evaluator.py",
    E3R / "python/emocio_vwm_mvp_e3r/model_adapter.py",
    E3R / "python/emocio_vwm_mvp_e3r/runner.py",
    ROOT / "scripts/run_emocio_vwm_e3r.py",
    ROOT / "scripts/seal_emocio_vwm_e3r_protocol.py",
    ROOT / "tests/research/test_emocio_vwm_e3r_protocol.py",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


records = [
    {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
    for path in FILES
]
tree = hashlib.sha256(
    "".join(f'{item["path"]}\0{item["bytes"]}\0{item["sha256"]}\n' for item in records).encode()
).hexdigest()
(E3R / "protocol_lineage.json").write_text(
    json.dumps(
        {
            "schema_version": "rei-emocio-vwm-e3r-protocol-lineage-v1",
            "algorithm": "sha256",
            "file_count": len(records),
            "protocol_tree_sha256": tree,
            "files": records,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
