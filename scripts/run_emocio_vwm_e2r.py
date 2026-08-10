"""Repository entry point for the frozen E2R runner."""

import os

# This must precede Torch and LPWM imports.
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
E2R_PACKAGE_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e2r" / "python"
E2_PACKAGE_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e2" / "python"
sys.path.insert(0, str(E2_PACKAGE_ROOT))
sys.path.insert(0, str(E2R_PACKAGE_ROOT))

from emocio_vwm_mvp_e2r.runner import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
