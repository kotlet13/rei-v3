"""E3 result sealing; deliberately independent of E2/E2R bundle keys."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def seal(source:Path,destination:Path,required:tuple[str,...])->dict:
    missing=[x for x in required if not (source/x).is_file()]
    if missing: raise RuntimeError(f"missing E3 artifacts: {missing}")
    destination.mkdir(parents=True,exist_ok=False); records=[]
    for rel in required:
        p=source/rel;q=destination/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes());records.append({"path":rel,"bytes":q.stat().st_size,"sha256":sha(q)})
    out={"schema_version":"rei-emocio-vwm-e3-result-bundle-v1","files":records};(destination/"result_bundle_manifest.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8");return out
