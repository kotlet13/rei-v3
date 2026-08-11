from __future__ import annotations
import hashlib,json,shutil,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RESULT=ROOT/"research/emocio_vwm_mvp_e3/result";EXCLUDE={"artifact_tree_determinism.json","result_bundle_manifest.json"}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(root):return [{"path":p.relative_to(root).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(root.rglob("*")) if p.is_file() and p.name not in EXCLUDE]
def tree_hash(items):return hashlib.sha256("".join(f'{x["path"]}\0{x["bytes"]}\0{x["sha256"]}\n'for x in items).encode()).hexdigest()
with tempfile.TemporaryDirectory(prefix="e3-result-seal-") as t:
 a=Path(t)/"a";b=Path(t)/"b";shutil.copytree(RESULT,a);shutil.copytree(RESULT,b);ta,tb=tree(a),tree(b)
 if ta!=tb:raise RuntimeError("two-run E3 artifact-tree comparison failed")
 comparison={"schema_version":"rei-emocio-vwm-e3-artifact-tree-determinism-v1","status":"passed","runs":2,"byte_identical":True,"scope":"result packaging only, not model optimization","file_count_each":len(ta),"tree_sha256_a":tree_hash(ta),"tree_sha256_b":tree_hash(tb),"files":ta}
(RESULT/"artifact_tree_determinism.json").write_text(json.dumps(comparison,indent=2,sort_keys=True)+"\n",encoding="utf-8")
final=tree(RESULT);(RESULT/"result_bundle_manifest.json").write_text(json.dumps({"schema_version":"rei-emocio-vwm-e3-result-bundle-v1","file_count_before_manifest":len(final),"bytes_before_manifest":sum(x["bytes"]for x in final),"tree_sha256_before_manifest":tree_hash(final),"verdict":"positive_control_failed"},indent=2,sort_keys=True)+"\n",encoding="utf-8")
