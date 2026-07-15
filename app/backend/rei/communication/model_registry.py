"""Strict, data-only registry for explicit Racio interpreter model lookup.

The registry records benchmark candidates.  It deliberately contains no
default or production selection; a caller must supply both the model ID and
the full runtime digest for every lookup.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from ..models.common import FrozenModel, HashDigest, NonEmptyText


REGISTRY_SCHEMA_VERSION = "rei-racio-interpreter-model-registry-v1"
REGISTRY_VERSION = "c3-v4"
RACIO_INTERPRETER_MODEL_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4]
    / "config"
    / "racio_interpreter_models.yaml"
)

InterpreterModality = Literal["structured_text", "vision"]
InterpreterRuntime = Literal["ollama"]
SlovenianBaselineStatus = Literal[
    "not_benchmarked",
    "semantic_lab_benchmarked",
]
InterpreterBenchmarkStatus = Literal[
    "c3_candidate",
    "vlm_adapter_candidate",
    "benchmarked",
    "rejected",
]


class InterpreterHardwareRequirements(FrozenModel):
    """Minimum local hardware envelope recorded for one candidate."""

    minimum_vram_gib: int = Field(ge=1)
    gpu_offload_policy: Literal["full_gpu_preferred"]


class RacioInterpreterModelCandidate(FrozenModel):
    """One benchmark candidate, never an implicit runtime selection."""

    model_id: NonEmptyText
    model_digest: HashDigest
    runtime: InterpreterRuntime
    modality_support: tuple[InterpreterModality, ...] = Field(min_length=1)
    slovenian_baseline: SlovenianBaselineStatus
    max_context: int = Field(ge=1)
    hardware_requirements: InterpreterHardwareRequirements
    license: Literal["Apache-2.0"]
    benchmark_status: InterpreterBenchmarkStatus

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if self.modality_support != tuple(sorted(set(self.modality_support))):
            raise ValueError(
                "Interpreter modalities must be unique and canonically sorted"
            )
        if "structured_text" not in self.modality_support:
            raise ValueError(
                "Every Racio interpreter candidate requires structured text support"
            )
        if (
            self.benchmark_status == "vlm_adapter_candidate"
            and "vision" not in self.modality_support
        ):
            raise ValueError("A VLM adapter candidate must declare vision support")
        return self


class RacioInterpreterModelRegistry(FrozenModel):
    """Versioned candidate registry with no default or selected-model field."""

    schema_version: Literal["rei-racio-interpreter-model-registry-v1"]
    registry_version: Literal["c3-v4"]
    candidates: tuple[RacioInterpreterModelCandidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        model_ids = tuple(candidate.model_id for candidate in self.candidates)
        digests = tuple(candidate.model_digest for candidate in self.candidates)
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("Racio interpreter model IDs must be unique")
        if len(set(digests)) != len(digests):
            raise ValueError("Racio interpreter model digests must be unique")
        if model_ids != tuple(sorted(model_ids)):
            raise ValueError(
                "Racio interpreter candidates must use canonical model-ID order"
            )
        return self

    def require_candidate(
        self,
        *,
        model_id: str,
        digest: str,
    ) -> RacioInterpreterModelCandidate:
        """Resolve only an exact operator-supplied model ID and full digest."""

        _validate_lookup_key(model_id=model_id, digest=digest)
        for candidate in self.candidates:
            if candidate.model_id == model_id and candidate.model_digest == digest:
                return candidate
        raise LookupError(
            "No Racio interpreter candidate matches the explicit model ID and digest"
        )


def _validate_lookup_key(*, model_id: str, digest: str) -> None:
    if (
        not isinstance(model_id, str)
        or not model_id.strip()
        or model_id != model_id.strip()
    ):
        raise ValueError("Model lookup requires an exact non-empty model ID")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("Model lookup requires a full lowercase 64-hex digest")


def load_racio_interpreter_model_registry(
    path: str | Path | None = None,
) -> RacioInterpreterModelRegistry:
    """Load JSON-compatible YAML 1.2 using only the standard JSON parser."""

    source = (
        RACIO_INTERPRETER_MODEL_REGISTRY_PATH
        if path is None
        else Path(path).expanduser()
    ).resolve(strict=True)
    if not source.is_file():
        raise ValueError("Racio interpreter model registry must be a regular file")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Racio interpreter model registry must contain one object")
    # JSON-mode validation retains strict scalar checks while mapping JSON arrays
    # to the immutable tuple contracts above.
    return RacioInterpreterModelRegistry.model_validate_json(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def require_racio_interpreter_model_candidate(
    registry: RacioInterpreterModelRegistry,
    *,
    model_id: str,
    digest: str,
) -> RacioInterpreterModelCandidate:
    """Public lookup helper that still requires both exact identity values."""

    return registry.require_candidate(model_id=model_id, digest=digest)


__all__ = [
    "InterpreterBenchmarkStatus",
    "InterpreterHardwareRequirements",
    "InterpreterModality",
    "InterpreterRuntime",
    "RACIO_INTERPRETER_MODEL_REGISTRY_PATH",
    "REGISTRY_SCHEMA_VERSION",
    "REGISTRY_VERSION",
    "RacioInterpreterModelCandidate",
    "RacioInterpreterModelRegistry",
    "SlovenianBaselineStatus",
    "load_racio_interpreter_model_registry",
    "require_racio_interpreter_model_candidate",
]
