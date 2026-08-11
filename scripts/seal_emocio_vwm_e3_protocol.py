from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];E3=ROOT/"research/emocio_vwm_mvp_e3"
FILES=[E3/"README.md",E3/"lab/index.html",E3/"lab/main.js",E3/"tools/render_dataset.mjs",E3/"tools/freeze_dataset.py",E3/"specs/dataset_freeze.json",E3/"specs/frozen_dataset_manifest.json",E3/"specs/model_config.json",E3/"specs/execution_plan.json",E3/"specs/metrics_freeze.json",E3/"specs/e3_protocol_freeze.json",E3/"python/emocio_vwm_mvp_e3/__init__.py",E3/"python/emocio_vwm_mvp_e3/preflight.py",E3/"python/emocio_vwm_mvp_e3/model_adapter.py",E3/"python/emocio_vwm_mvp_e3/metrics.py",E3/"python/emocio_vwm_mvp_e3/packaging.py",E3/"python/emocio_vwm_mvp_e3/runner.py",ROOT/"scripts/run_emocio_vwm_e3.py",ROOT/"scripts/seal_emocio_vwm_e3_protocol.py",ROOT/"tests/research/test_emocio_vwm_e3_protocol.py"]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
for p in FILES:
 rel=p.relative_to(ROOT).as_posix();records.append({"path":rel,"bytes":p.stat().st_size,"sha256":sha(p)})
tree=hashlib.sha256("".join(f'{x["path"]}\0{x["bytes"]}\0{x["sha256"]}\n'for x in records).encode()).hexdigest()
(E3/"protocol_lineage.json").write_text(json.dumps({"schema_version":"rei-emocio-vwm-e3-protocol-lineage-v1","algorithm":"sha256","file_count":len(records),"protocol_tree_sha256":tree,"files":records},indent=2,sort_keys=True)+"\n",encoding="utf-8")
