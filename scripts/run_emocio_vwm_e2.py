"""Repository entry point for the frozen E2 runner."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e2" / "python"
sys.path.insert(0, str(PACKAGE_ROOT))

from emocio_vwm_mvp_e2.runner import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
