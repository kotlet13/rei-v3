from __future__ import annotations
import os,sys
from pathlib import Path
os.environ["CUBLAS_WORKSPACE_CONFIG"]=":4096:8"
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"research/emocio_vwm_mvp_e3/python"))
from emocio_vwm_mvp_e3.runner import main
if __name__=="__main__":raise SystemExit(main())
