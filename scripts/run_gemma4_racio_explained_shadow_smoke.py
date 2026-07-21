"""Run the sealed EN2 Gemma shadow smoke with cited abstention explanations."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
for import_root in (ROOT, BACKEND_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


from rei.ids import sha256_hex  # noqa: E402
from rei.providers.ollama_gemma4_epistemic_en_explained import (  # noqa: E402
    GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION_SHA256,
    GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION,
    GEMMA4_EPISTEMIC_EN_EXPLAINED_SCHEMA_SHA256,
)
from rei.communication.epistemic_interpreter_en_explained import (  # noqa: E402
    RacioEpistemicExplainedDraftEnV1,
)
from scripts import run_gemma4_racio_english_shadow_smoke as base  # noqa: E402


# Updated to the final model-free implementation commit before the pre-call seal.
IMPLEMENTATION_COMMIT = "1f118c0d64cfb1ac02357dcf1a299d2c16041041"
PHASE = "EN2"
EVENT_ID = "en2_gemma4_explained_shadow_event"
RUN_ID = "en2-gemma4-explained-shadow-cycle"
EGO_ID = "en2-gemma4-explained-shadow-ego"
SEAL_PATH = (
    ROOT
    / "Docs"
    / "evals"
    / "research_reset_2026-07"
    / "gemma4_english_explained_shadow_smoke_seal.json"
)
OUTPUT_ROOT = (
    ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "en2-gemma4-explained-shadow-2026-07-21"
)
RECEIPT_PATH = (
    ROOT
    / "Docs"
    / "evals"
    / "research_reset_2026-07"
    / "gemma4_english_explained_shadow_smoke_receipt.json"
)
EXPECTED_OUTPUT_ROOT = (
    "Docs/evals/semantic_lab_v1/en2-gemma4-explained-shadow-2026-07-21"
)
RUNNER_RELATIVE_PATH = "scripts/run_gemma4_racio_explained_shadow_smoke.py"
FOCUSED_TEST_RELATIVE_PATH = (
    "tests/rei/test_english_explained_shadow_smoke.py"
)
MANIFEST_ID_PREFIX = "gemma4_en2_shadow_manifest"
RECEIPT_ID_PREFIX = "gemma4_en2_shadow_receipt"


def _configure_base() -> None:
    base.IMPLEMENTATION_COMMIT = IMPLEMENTATION_COMMIT
    base.PHASE = PHASE
    base.EVENT_ID = EVENT_ID
    base.RUN_ID = RUN_ID
    base.EGO_ID = EGO_ID
    base.SEAL_PATH = SEAL_PATH
    base.OUTPUT_ROOT = OUTPUT_ROOT
    base.RECEIPT_PATH = RECEIPT_PATH
    base.EXPECTED_OUTPUT_ROOT = EXPECTED_OUTPUT_ROOT
    base.PROVIDER_REVISION = GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION
    base.INSTRUCTION_SHA256 = (
        GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION_SHA256
    )
    base.DRAFT_SCHEMA_SHA256 = GEMMA4_EPISTEMIC_EN_EXPLAINED_SCHEMA_SHA256
    base.DRAFT_MODEL_SCHEMA_SHA256 = sha256_hex(
        RacioEpistemicExplainedDraftEnV1.model_json_schema()
    )
    base.RUNNER_PATH = Path(__file__).resolve()
    base.RUNNER_RELATIVE_PATH = RUNNER_RELATIVE_PATH
    base.FOCUSED_TEST_RELATIVE_PATH = FOCUSED_TEST_RELATIVE_PATH
    base.SEALED_SOURCE_PATHS = (
        "scripts/run_gemma4_racio_english_shadow_smoke.py",
        RUNNER_RELATIVE_PATH,
        FOCUSED_TEST_RELATIVE_PATH,
    )
    base.MANIFEST_ID_PREFIX = MANIFEST_ID_PREFIX
    base.RECEIPT_ID_PREFIX = RECEIPT_ID_PREFIX


def main(argv: list[str] | None = None) -> int:
    _configure_base()
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
