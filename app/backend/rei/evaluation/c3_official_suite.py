"""Seal-only registration for the official C3 holdout/regression pair.

The pre-existing evaluator remains byte-identical to the protocol-freeze
commit.  This module adds only the post-freeze holdout pin and cold loader.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

from ..communication.conscious_access import (
    CONSCIOUS_ACCESS_CALIBRATION_POLICY_ID,
)
from ..communication.structured_interpreter import (
    StructuredRacioInterpreterOutput,
)
from ..ids import sha256_hex
from ..providers.ollama_interpreter import (
    RACIO_INTERPRETER_STRUCTURED_INSTRUCTION,
)
from .racio_interpreter_benchmark import (
    BENCHMARK_ID,
    BENCHMARK_SCHEMA_VERSION,
    HOLDOUT_BENCHMARK_ID,
    HOLDOUT_MANIFEST_PATH,
    MANIFEST_PATH,
    MAX_C3_DATA_FILE_BYTES,
    OFFICIAL_MANIFEST_SHA256,
    C3_REGRESSION_FAMILY_IDS,
    C3BenchmarkManifest,
    C3BenchmarkManifestV2,
    C3BenchmarkSuite,
    _read_bounded,
    load_c3_racio_interpreter_benchmark,
)


OFFICIAL_REGRESSION_MANIFEST_SHA256 = OFFICIAL_MANIFEST_SHA256
OFFICIAL_HOLDOUT_MANIFEST_SHA256 = (
    "32a57a8dc0601ad01ca9eb169786e0888f13c036488762f9cfa6b69a0b7233f2"
)
PROTOCOL_FREEZE_COMMIT = "d74891cdeed407a50098d28d6f4e9024b28156e7"
OFFICIAL_C3_INSTRUCTION_SHA256 = (
    "c5ea5a0936bbab5e9bb481e53443eb9119cb5bf2c1d58737f3bb0214ebcfb1b0"
)
OFFICIAL_C3_OUTPUT_SCHEMA_SHA256 = (
    "7b51eeadc1e13223016a1ab95aab88b9141ed7d11a5400bd05cf25988645bd1c"
)
OFFICIAL_C3_SUITE_ORDER: Final[tuple[tuple[Path, str], ...]] = (
    (HOLDOUT_MANIFEST_PATH, OFFICIAL_HOLDOUT_MANIFEST_SHA256),
    (MANIFEST_PATH, OFFICIAL_REGRESSION_MANIFEST_SHA256),
)


def _validate_official_holdout_source_pins(
    manifest: C3BenchmarkManifestV2,
) -> None:
    repository_root = Path(__file__).resolve().parents[4]
    for pin in manifest.source_grounding_pins:
        fixture_source = repository_root / pin.fixture_path
        fixture_payload = _read_bounded(
            fixture_source,
            maximum_bytes=MAX_C3_DATA_FILE_BYTES,
            label=f"Official C3 source fixture {pin.family_id}",
        )
        if hashlib.sha256(fixture_payload).hexdigest() != pin.fixture_sha256:
            raise ValueError(
                f"Official C3 source fixture differs from pin: {pin.family_id}"
            )


def load_official_c3_suite_pair() -> tuple[C3BenchmarkSuite, C3BenchmarkSuite]:
    """Load canonical holdout then regression suites from exact frozen pins."""

    holdout = load_c3_racio_interpreter_benchmark(HOLDOUT_MANIFEST_PATH)
    regression = load_c3_racio_interpreter_benchmark(MANIFEST_PATH)
    loaded_order = (
        (HOLDOUT_MANIFEST_PATH, holdout.manifest_file_hash),
        (MANIFEST_PATH, regression.manifest_file_hash),
    )
    if loaded_order != OFFICIAL_C3_SUITE_ORDER:
        raise ValueError("Official C3 suite manifest path/hash registration differs")

    holdout_manifest = holdout.manifest
    regression_manifest = regression.manifest
    if not isinstance(holdout_manifest, C3BenchmarkManifestV2) or (
        holdout_manifest.benchmark_id != HOLDOUT_BENCHMARK_ID
        or holdout_manifest.suite_role != "untouched_holdout"
    ):
        raise ValueError("Official C3 holdout role or benchmark identity differs")
    if not isinstance(regression_manifest, C3BenchmarkManifest) or (
        regression_manifest.benchmark_id != BENCHMARK_ID
        or regression_manifest.schema_version != BENCHMARK_SCHEMA_VERSION
    ):
        raise ValueError("Official C3 regression identity or schema differs")

    if (
        holdout_manifest.protocol_freeze_commit != PROTOCOL_FREEZE_COMMIT
        or holdout_manifest.instruction_sha256 != OFFICIAL_C3_INSTRUCTION_SHA256
        or holdout_manifest.instruction_sha256
        != sha256_hex(RACIO_INTERPRETER_STRUCTURED_INSTRUCTION)
        or holdout_manifest.output_schema_sha256 != OFFICIAL_C3_OUTPUT_SCHEMA_SHA256
        or holdout_manifest.output_schema_sha256
        != sha256_hex(StructuredRacioInterpreterOutput.model_json_schema())
        or holdout_manifest.calibration_policy_id
        != CONSCIOUS_ACCESS_CALIBRATION_POLICY_ID
    ):
        raise ValueError("Official C3 holdout protocol contract differs")
    _validate_official_holdout_source_pins(holdout_manifest)

    regression_families = {case.gold.family_id for case in regression.cases}
    if regression_families != set(C3_REGRESSION_FAMILY_IDS):
        raise ValueError("Official C3 regression family set differs from frozen v1")
    return holdout, regression


def load_official_c3_racio_interpreter_suites() -> tuple[
    C3BenchmarkSuite, C3BenchmarkSuite
]:
    """Compatibility name for the canonical official C3 suite pair."""

    return load_official_c3_suite_pair()


__all__ = [
    "OFFICIAL_C3_INSTRUCTION_SHA256",
    "OFFICIAL_C3_OUTPUT_SCHEMA_SHA256",
    "OFFICIAL_C3_SUITE_ORDER",
    "OFFICIAL_HOLDOUT_MANIFEST_SHA256",
    "OFFICIAL_REGRESSION_MANIFEST_SHA256",
    "PROTOCOL_FREEZE_COMMIT",
    "load_official_c3_racio_interpreter_suites",
    "load_official_c3_suite_pair",
]
