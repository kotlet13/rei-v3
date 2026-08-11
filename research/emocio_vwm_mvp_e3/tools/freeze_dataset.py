"""Seal the one-shot E3 dataset without importing Torch or LPWM."""
from __future__ import annotations
import hashlib, json, shutil, sys
from pathlib import Path

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def main() -> None:
    dataset=Path(sys.argv[1]).resolve(); repo=Path(__file__).resolve().parents[3]
    if repo==dataset or repo in dataset.parents: raise RuntimeError("dataset must be external")
    manifest=dataset/"dataset_manifest.json"; data=json.loads(manifest.read_text(encoding="utf-8"))
    files=[]
    for p in sorted(x for x in dataset.rglob("*") if x.is_file() and x!=manifest):
        files.append({"path":p.relative_to(dataset).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p)})
    tree=hashlib.sha256("".join(f'{x["path"]}\0{x["bytes"]}\0{x["sha256"]}\n' for x in files).encode()).hexdigest()
    spec=repo/"research"/"emocio_vwm_mvp_e3"/"specs"; spec.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(manifest,spec/"frozen_dataset_manifest.json")
    freeze={"schema_version":"rei-emocio-vwm-e3-dataset-freeze-v1","external_root_sanitized":"${REI_E3_DATASET_ROOT}","dataset_manifest_sha256":digest(manifest),"dataset_tree_sha256":tree,"file_count":len(files)+1,"content_bytes":sum(x["bytes"] for x in files)+manifest.stat().st_size,"individual_hashes_embedded_in":"frozen_dataset_manifest.json","generator_sha256":data["generator_sha256"],"browser_executable_sha256":data["browser_executable_sha256"],"seed":data["seed"],"splits":data["splits"],"episodes":data["episodes"],"frames_per_episode":data["frames_per_episode"]}
    (spec/"dataset_freeze.json").write_text(json.dumps(freeze,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__": main()
