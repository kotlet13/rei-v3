"""Run or cold-validate the sealed Gemma 4 epistemic V3 G3C screen.

The corpus owns all sixteen packets, evaluator gold records, bilingual pairs,
and provider call specifications before execution.  Normal invocation is
model-free.  ``--execute`` performs exactly one local chat dispatch per case;
``--cold-validate`` never creates a provider or contacts Ollama.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.rei.communication.epistemic_interpreter import (  # noqa: E402
    MOTIVE_SUBTYPES_BY_FAMILY,
)
from app.backend.rei.communication.epistemic_interpreter_v3 import (  # noqa: E402
    ACTION_PARENT_FALLBACKS_V3,
    ACTION_SUBTYPES_BY_FAMILY_V3,
    RacioEpistemicDraftV3,
    RacioEpistemicInterpretationV3,
    RacioEpistemicPacketV3,
    RacioEpistemicStructuralSidecarV3,
    canonicalize_racio_epistemic_draft_v3,
)
from app.backend.rei.evaluation.racio_epistemic_v3 import (  # noqa: E402
    EpistemicCaseGoldV3,
    RacioEpistemicBilingualEvaluationV3,
    RacioEpistemicCaseEvaluationV3,
    evaluate_racio_epistemic_bilingual_pair_v3,
    evaluate_racio_epistemic_case_v3,
)
from app.backend.rei.ids import (  # noqa: E402
    canonical_json_bytes,
    content_id,
    sha256_hex,
    utc_now,
)
from app.backend.rei.models.provider import (  # noqa: E402
    ProviderCallRecord,
    ProviderCallSpec,
    ensure_call_record_contract,
)
from app.backend.rei.providers.native import SystemExecutionClock  # noqa: E402
from app.backend.rei.providers.ollama import (  # noqa: E402
    DEFAULT_OLLAMA_BASE_URL,
    OllamaApiClient,
    OllamaJsonTransport,
    UrllibOllamaTransport,
)
from app.backend.rei.providers.ollama_gemma4_epistemic import (  # noqa: E402
    GEMMA4_EPISTEMIC_KEEP_ALIVE,
    GEMMA4_EPISTEMIC_MODEL,
    GEMMA4_EPISTEMIC_NUM_CTX,
    GEMMA4_EPISTEMIC_NUM_GPU,
    GEMMA4_EPISTEMIC_NUM_PREDICT,
    GEMMA4_EPISTEMIC_SEED,
    GEMMA4_EPISTEMIC_TEMPERATURE,
    GEMMA4_EPISTEMIC_TIMEOUT_SECONDS,
    GEMMA4_EPISTEMIC_TOP_K,
    GEMMA4_EPISTEMIC_TOP_P,
)
from app.backend.rei.providers.ollama_gemma4_epistemic_v3 import (  # noqa: E402
    GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256,
    GEMMA4_EPISTEMIC_V3_MODEL_DIGEST,
    GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION,
    GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256,
    Gemma4EpistemicV3Execution,
    Gemma4EpistemicV3ExecutionError,
    Gemma4EpistemicV3ResponseEvidence,
    OllamaGemma4EpistemicV3Provider,
)


CORPUS_DIR = (
    ROOT
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "gemma4_epistemic_v3_g3c_2026_07_17"
)
DEFAULT_MANIFEST_PATH = CORPUS_DIR / "manifest.json"
SEALED_OUTPUT_ROOT = (
    ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "g3c-gemma4-racio-epistemic-v3-2026-07-17"
)
SEALED_OUTPUT_ROOT_REPO_RELATIVE = (
    "Docs/evals/semantic_lab_v1/"
    "g3c-gemma4-racio-epistemic-v3-2026-07-17"
)
FROZEN_G3_V2_REPORT = (
    ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "g3-gemma4-racio-epistemic-2026-07-17"
    / "report.json"
)
FROZEN_G3_V2_REPORT_SHA256 = (
    "b10b73738216d49f9c909d5f6180fb5179520b90d8bc675e5eba69ceef105d5c"
)
FROZEN_G3A_REPORT = (
    ROOT
    / "Docs"
    / "evals"
    / "research_reset_2026-07"
    / "g3_semantic_adjudication.md"
)
FROZEN_G3A_REPORT_SHA256 = (
    "3eca5caac6762b5fd604973c30cb5ff2b75ebb165580ef9153a37bef9c1ea0a9"
)
EXPECTED_MANIFEST_SHA256 = (
    "6933e919a48af7a2de6aff1490e745bc13e4ae7742e2c1e1e8a049ddc4aa9298"
)
SUITE_ID = "rei-racio-gemma4-epistemic-v3-g3c-2026-07-17"
MANIFEST_SCHEMA_VERSION = "rei-racio-g3c-v3-manifest-v1"
PACKET_RECORD_SCHEMA_VERSION = "rei-racio-g3c-v3-packet-record-v1"
GOLD_RECORD_SCHEMA_VERSION = "rei-racio-g3c-v3-gold-record-v1"
CALL_RECORD_SCHEMA_VERSION = "rei-racio-g3c-v3-call-spec-record-v1"
PAIR_REGISTRY_SCHEMA_VERSION = "rei-racio-g3c-v3-pair-registry-v1"
CASE_COUNT = 16
PAIR_COUNT = 8
EXPECTED_ROOT_LABELS = ("H1", "H3", "H7", "H11", "H15", "R1", "R3", "R5")
EXPECTED_CASE_IDENTITIES = (
    ("g3_h1_sl", "H1", "g3_pair_h1", "c3h_case_001", "c3h_root_emocio_three_scenes", "canonical_sl_only"),
    ("g3_h1_en", "H1", "g3_pair_h1", "c3h_case_002", "c3h_root_emocio_three_scenes", "operational_en_only"),
    ("g3_h3_sl", "H3", "g3_pair_h3", "c3h_case_005", "c3h_root_new_year_readiness", "canonical_sl_only"),
    ("g3_h3_en", "H3", "g3_pair_h3", "c3h_case_006", "c3h_root_new_year_readiness", "operational_en_only"),
    ("g3_h7_sl", "H7", "g3_pair_h7", "c3h_case_013", "c3h_root_spoznanje_loss", "canonical_sl_only"),
    ("g3_h7_en", "H7", "g3_pair_h7", "c3h_case_014", "c3h_root_spoznanje_loss", "operational_en_only"),
    ("g3_h11_sl", "H11", "g3_pair_h11", "c3h_case_021", "c3h_root_three_modal_path", "canonical_sl_only"),
    ("g3_h11_en", "H11", "g3_pair_h11", "c3h_case_022", "c3h_root_three_modal_path", "operational_en_only"),
    ("g3_h15_sl", "H15", "g3_pair_h15", "c3h_case_029", "c3h_root_same_boundary_route", "canonical_sl_only"),
    ("g3_h15_en", "H15", "g3_pair_h15", "c3h_case_030", "c3h_root_same_boundary_route", "operational_en_only"),
    ("g3_r1_sl", "R1", "g3_pair_r1", "c3_case_001", "c3_root_broken_scene_anger", "canonical_sl_only"),
    ("g3_r1_en", "R1", "g3_pair_r1", "c3_case_002", "c3_root_broken_scene_anger", "operational_en_only"),
    ("g3_r3_sl", "R3", "g3_pair_r3", "c3_case_005", "c3_root_attachment_loss", "canonical_sl_only"),
    ("g3_r3_en", "R3", "g3_pair_r3", "c3_case_006", "c3_root_attachment_loss", "operational_en_only"),
    ("g3_r5_sl", "R5", "g3_pair_r5", "c3_case_009", "c3_root_motor_visual", "canonical_sl_only"),
    ("g3_r5_en", "R5", "g3_pair_r5", "c3_case_010", "c3_root_motor_visual", "operational_en_only"),
)

_PACKET_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "root_label",
        "bilingual_pair_id",
        "source_case_id",
        "source_root_id",
        "packet",
    }
)
_GOLD_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "root_label",
        "bilingual_pair_id",
        "source_case_id",
        "source_root_id",
        "gold",
    }
)
_CALL_RECORD_KEYS = frozenset({"schema_version", "case_id", "call_spec"})
_PAIR_REGISTRY_KEYS = frozenset({"schema_version", "suite_id", "pairs"})
_PAIR_KEYS = frozenset(
    {
        "bilingual_pair_id",
        "root_label",
        "sl_case_id",
        "en_case_id",
        "canonical_evidence_sha256",
    }
)
_IDENTITY_KEYS = (
    "case_id",
    "root_label",
    "bilingual_pair_id",
    "source_case_id",
    "source_root_id",
)
_CORPUS_FILES = (
    "packets.jsonl",
    "gold.jsonl",
    "bilingual_pairs.json",
    "call_specs.jsonl",
)
_SAFE_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,199}$")
_GLOBAL_FAILURE_CODES = frozenset(
    {
        "request_contract_failure",
        "runtime_identity_mismatch",
        "gpu_placement_failure",
    }
)
_FORBIDDEN_AGGREGATE_KEYS = frozenset(
    {
        "aggregate_pass",
        "aggregate_score",
        "aggregate_semantic_pass",
        "aggregate_semantic_score",
        "overall_pass",
        "overall_score",
        "overall_semantic_pass",
        "overall_semantic_score",
        "passed",
        "quality_gate_pass",
        "quality_pass",
        "semantic_pass",
        "semantic_score",
    }
)
_FORBIDDEN_PRIVATE_CONTENT_KEYS = frozenset(
    {"thinking", "final_json", "raw_response", "response_envelope", "validation_error"}
)
_FAILURE_ARTIFACT_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "call_id",
        "failure_code",
        "failure_stage",
        "validation_boundary",
        "sanitized_diagnostics",
        "rejected_content_persisted",
        "thinking_content_persisted",
        "raw_response_envelope_persisted",
    }
)
_MISSING_ARTIFACT_KINDS = {
    "model_draft_missing.json": "validated_model_draft_v3",
    "structured_output_missing.json": "canonical_interpretation_v3",
    "structural_sidecar_missing.json": "structural_sidecar_v3",
    "response_evidence_missing.json": "successful_response_evidence",
}
_SCOPED_SOURCE_PATHS = (
    "scripts/run_gemma4_racio_epistemic_v3_g3c.py",
    "app/backend/rei/communication/epistemic_interpreter_v3.py",
    "app/backend/rei/evaluation/racio_epistemic_v3.py",
    "app/backend/rei/providers/ollama_gemma4_epistemic_v3.py",
    "app/backend/rei/providers/ollama_gemma4_chat_transport.py",
    "app/backend/rei/providers/ollama_gemma4_epistemic.py",
    "Docs/evals/semantic_lab_v1/"
    "g3-gemma4-racio-epistemic-2026-07-17/report.json",
    "Docs/evals/research_reset_2026-07/g3_semantic_adjudication.md",
    *(
        f"knowledge/canon_v2/semantic_lab_v1/"
        f"gemma4_epistemic_v3_g3c_2026_07_17/{name}"
        for name in ("manifest.json", *_CORPUS_FILES)
    ),
)


@dataclass(frozen=True, slots=True)
class G3CCase:
    case_id: str
    root_label: str
    bilingual_pair_id: str
    source_case_id: str
    source_root_id: str
    packet: RacioEpistemicPacketV3
    gold: EpistemicCaseGoldV3
    call_spec: ProviderCallSpec


@dataclass(frozen=True, slots=True)
class G3CPair:
    bilingual_pair_id: str
    root_label: str
    sl_case_id: str
    en_case_id: str
    canonical_evidence_sha256: str


@dataclass(frozen=True, slots=True)
class G3CSuite:
    manifest_path: Path
    manifest_sha256: str
    manifest: Mapping[str, Any]
    pair_registry: Mapping[str, Any]
    cases: tuple[G3CCase, ...]
    pairs: tuple[G3CPair, ...]


class CountingOllamaTransport:
    """Count endpoint dispatches while retaining no request or response."""

    def __init__(self, inner: OllamaJsonTransport) -> None:
        self._inner = inner
        self._counts: Counter[str] = Counter()

    def request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        self._counts[urlsplit(url).path] += 1
        return self._inner.request_json(
            method=method,
            url=url,
            payload=payload,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
        )

    @property
    def chat_count(self) -> int:
        return self._counts["/api/chat"]

    def sanitized_counts(self) -> dict[str, int]:
        return dict(sorted(self._counts.items()))


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if frozenset(value) != expected:
        raise ValueError(f"{label} fields differ from the sealed contract")


def _json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if type(value) is not dict:
        raise ValueError(f"{label} must be a JSON object")
    return value


def _read_canonical_json(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    value = _json_object(payload, label=str(path))
    if payload != canonical_json_bytes(value) + b"\n":
        raise ValueError(f"{path} is not canonical JSON")
    return value


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_bytes().splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"Blank JSONL record at {path}:{line_number}")
        record = _json_object(line, label=f"{path}:{line_number}")
        if line != canonical_json_bytes(record):
            raise ValueError(f"Non-canonical JSONL record at {path}:{line_number}")
        records.append(record)
    return tuple(records)


def _write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_json_bytes(value) + b"\n")


def _current_frozen_profile() -> dict[str, Any]:
    if _file_sha256(FROZEN_G3_V2_REPORT) != FROZEN_G3_V2_REPORT_SHA256:
        raise ValueError("Frozen G3 V2 report differs from its historical hash")
    if _file_sha256(FROZEN_G3A_REPORT) != FROZEN_G3A_REPORT_SHA256:
        raise ValueError("Frozen G3A report differs from its historical hash")
    return {
        "provider_revision": GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION,
        "model": GEMMA4_EPISTEMIC_MODEL,
        "model_digest": GEMMA4_EPISTEMIC_V3_MODEL_DIGEST,
        "instruction_sha256": GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256,
        "draft_schema_sha256": GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256,
        "canonical_interpretation_schema_sha256": sha256_hex(
            RacioEpistemicInterpretationV3.model_json_schema()
        ),
        "contract_sha256": _file_sha256(
            ROOT / "app/backend/rei/communication/epistemic_interpreter_v3.py"
        ),
        "evaluator_sha256": _file_sha256(
            ROOT / "app/backend/rei/evaluation/racio_epistemic_v3.py"
        ),
        "provider_sha256": _file_sha256(
            ROOT / "app/backend/rei/providers/ollama_gemma4_epistemic_v3.py"
        ),
        "base_provider_sha256": _file_sha256(
            ROOT / "app/backend/rei/providers/ollama_gemma4_epistemic.py"
        ),
        "chat_transport_sha256": _file_sha256(
            ROOT / "app/backend/rei/providers/ollama_gemma4_chat_transport.py"
        ),
        "frozen_g3_v2_report_sha256": _file_sha256(FROZEN_G3_V2_REPORT),
        "frozen_g3a_report_sha256": _file_sha256(FROZEN_G3A_REPORT),
        "action_taxonomy_sha256": sha256_hex(
            {
                family: sorted(subtypes)
                for family, subtypes in sorted(ACTION_SUBTYPES_BY_FAMILY_V3.items())
            }
        ),
        "action_fallback_sha256": sha256_hex(
            {
                family: sorted(values)
                for family, values in sorted(ACTION_PARENT_FALLBACKS_V3.items())
            }
        ),
        "motive_taxonomy_sha256": sha256_hex(
            {
                family: sorted(subtypes)
                for family, subtypes in sorted(MOTIVE_SUBTYPES_BY_FAMILY.items())
            }
        ),
        "sidecar_schema_sha256": sha256_hex(
            RacioEpistemicStructuralSidecarV3.model_json_schema()
        ),
        "canonicalizer_semantic_repair_allowed": False,
        "sidecar_semantic_evidence": False,
        "sidecar_governance_effect": False,
        "seed": GEMMA4_EPISTEMIC_SEED,
        "temperature": GEMMA4_EPISTEMIC_TEMPERATURE,
        "top_p": GEMMA4_EPISTEMIC_TOP_P,
        "top_k": GEMMA4_EPISTEMIC_TOP_K,
        "num_ctx": GEMMA4_EPISTEMIC_NUM_CTX,
        "num_gpu": GEMMA4_EPISTEMIC_NUM_GPU,
        "num_predict": GEMMA4_EPISTEMIC_NUM_PREDICT,
        "timeout_seconds": GEMMA4_EPISTEMIC_TIMEOUT_SECONDS,
        "keep_alive": GEMMA4_EPISTEMIC_KEEP_ALIVE,
        "endpoint": f"{DEFAULT_OLLAMA_BASE_URL}/api/chat",
        "require_full_gpu": True,
        "stream": False,
        "raw": False,
        "think": True,
        "retry_count": 0,
        "fallback": "none",
    }


def _canonical_evidence_sha256(packet: RacioEpistemicPacketV3) -> str:
    payload = packet.model_dump(
        mode="python",
        round_trip=True,
        exclude={"packet_id", "packet_hash", "presentation_mode"},
    )
    return sha256_hex(payload)


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {
            *(str(key) for key in value),
            *(nested for item in value.values() for nested in _all_keys(item)),
        }
    if isinstance(value, (list, tuple)):
        return {nested for item in value for nested in _all_keys(item)}
    return set()


def _assert_no_private_response_content(value: Any, *, label: str) -> None:
    forbidden = _FORBIDDEN_PRIVATE_CONTENT_KEYS.intersection(_all_keys(value))
    if forbidden:
        raise ValueError(
            f"G3C private response content key persisted in {label}: "
            f"{sorted(forbidden)}"
        )


def _validate_sanitized_failure(
    *,
    failure: Mapping[str, Any],
    case: G3CCase,
    result: Mapping[str, Any],
) -> None:
    _strict_keys(failure, _FAILURE_ARTIFACT_KEYS, "G3C sanitized failure")
    failure_code = result["failure_code"]
    stage = failure["failure_stage"]
    if (
        failure["schema_version"] != "rei-racio-g3c-v3-provider-failure-v1"
        or failure["case_id"] != case.case_id
        or failure["call_id"] != case.call_spec.call_id
        or failure["failure_code"] != failure_code
        or stage not in {
            "transport",
            "draft_v3_validation",
            "canonicalizer_v3_validation",
        }
        or failure["validation_boundary"] != _validation_boundary(stage)
        or failure["rejected_content_persisted"] is not False
        or failure["thinking_content_persisted"] is not False
        or failure["raw_response_envelope_persisted"] is not False
        or type(failure["sanitized_diagnostics"]) is not dict
    ):
        raise ValueError(f"G3C failure artifact differs for {case.case_id}")
    if stage == "draft_v3_validation" and failure_code != "structured_output_invalid":
        raise ValueError(f"G3C DraftV3 failure code differs for {case.case_id}")
    if (
        stage == "canonicalizer_v3_validation"
        and failure_code != "conscious_access_rejected"
    ):
        raise ValueError(f"G3C canonicalizer failure code differs for {case.case_id}")
    expected_validation_stage = {
        "structured_output_invalid": "draft_v3_validation",
        "conscious_access_rejected": "canonicalizer_v3_validation",
    }.get(failure_code)
    if expected_validation_stage is not None and stage != expected_validation_stage:
        raise ValueError(f"G3C failure code/stage pair differs for {case.case_id}")
    if stage == "transport" and failure_code not in {
        "request_contract_failure",
        "runtime_identity_mismatch",
        "gpu_placement_failure",
        "generation_contract_failure",
        "thinking_separation_failure",
        "unexpected_provider_failure",
    }:
        raise ValueError(f"G3C transport failure code differs for {case.case_id}")
    diagnostics = failure["sanitized_diagnostics"]
    _assert_no_private_response_content(
        diagnostics, label=f"sanitized failure {case.case_id}"
    )
    if stage in {"draft_v3_validation", "canonicalizer_v3_validation"}:
        diagnostic_sha256 = diagnostics.get("validation_diagnostic_sha256")
        if not isinstance(diagnostic_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", diagnostic_sha256
        ):
            raise ValueError(
                f"G3C validation diagnostic hash differs for {case.case_id}"
            )


def _validate_provider_boundary(case: G3CCase) -> None:
    payload = case.packet.provider_payload()
    encoded = case.packet.provider_payload_bytes().decode("utf-8").casefold()
    forbidden_values = (
        case.case_id,
        case.root_label,
        case.bilingual_pair_id,
        case.source_case_id,
        case.source_root_id,
        *case.gold.hidden_provider_tokens,
        case.gold.profile_id,
    )
    if any(value.casefold() in encoded for value in forbidden_values):
        raise ValueError(f"Provider payload leaks sealed identity for {case.case_id}")
    forbidden_keys = {
        "atomic_evidence_unit_id",
        "perceptual_unit_count",
        "gloss_audit",
        "audit_hash",
        "evaluator_only_canary",
        "native_truth_id",
        "profile_id",
    }
    if forbidden_keys.intersection(_all_keys(payload)):
        raise ValueError(f"Provider payload leaks V3 attestation for {case.case_id}")


def _parameter_values(call: ProviderCallSpec) -> dict[str, Any]:
    return {
        item.name: json.loads(item.canonical_json_value)
        for item in call.parameters
    }


def _verify_static_call_spec(case: G3CCase) -> None:
    call = case.call_spec
    profile = _current_frozen_profile()
    if (
        call.request_id != case.packet.packet_id
        or call.input_artifact_ids != (case.packet.packet_id,)
        or call.provider.model != profile["model"]
        or call.provider.model_revision != profile["model_digest"]
        or call.seed != profile["seed"]
        or call.timeout_seconds != profile["timeout_seconds"]
        or call.fallback_policy.mode != "none"
        or call.provider.implementation_revision.split(";", 1)[0]
        != profile["provider_revision"]
    ):
        raise ValueError(f"Static call-spec identity differs for {case.case_id}")
    parameters = _parameter_values(call)
    expected = {
        "canonicalizer_semantic_repair_allowed": False,
        "draft_schema_sha256": profile["draft_schema_sha256"],
        "instruction_sha256": profile["instruction_sha256"],
        "model": profile["model"],
        "model_digest": profile["model_digest"],
        "num_ctx": profile["num_ctx"],
        "num_gpu": profile["num_gpu"],
        "num_predict": profile["num_predict"],
        "packet_hash": case.packet.packet_hash,
        "provider_payload_sha256": hashlib.sha256(
            case.packet.provider_payload_bytes()
        ).hexdigest(),
        "retry_count": 0,
        "structural_sidecar_governance_effect": False,
        "structural_sidecar_semantic_evidence": False,
        "temperature": profile["temperature"],
        "think": True,
        "top_k": profile["top_k"],
        "top_p": profile["top_p"],
    }
    if any(parameters.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Static call-spec parameters differ for {case.case_id}")
    if not isinstance(parameters.get("request_payload_sha256"), str):
        raise ValueError(f"Static call-spec lacks request hash for {case.case_id}")


def _manifest_file_map(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    entries = manifest.get("files")
    if type(entries) is not list or len(entries) != len(_CORPUS_FILES):
        raise ValueError("G3C manifest must seal exactly four corpus files")
    result: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if type(entry) is not dict or frozenset(entry) != {
            "path",
            "sha256",
            "record_count",
        }:
            raise ValueError("G3C manifest file entry is invalid")
        if entry["path"] in result:
            raise ValueError("G3C manifest contains a duplicate file")
        result[entry["path"]] = entry
    if tuple(result) != _CORPUS_FILES:
        raise ValueError("G3C manifest corpus file order differs from its seal")
    return result


def _validate_manifest_shape(manifest: Mapping[str, Any]) -> None:
    expected_keys = frozenset(
        {
            "schema_version",
            "suite_id",
            "corpus_version",
            "suite_role",
            "sealed_before_model_run",
            "post_seal_prompt_tuning_allowed",
            "model_generated_gold",
            "training_export",
            "counts",
            "files",
            "output_root",
            "case_order",
            "pair_order",
            "packet_hashes",
            "gold_sha256",
            "provider_payload_sha256",
            "call_spec_hashes",
            "frozen_profile",
        }
    )
    _strict_keys(manifest, expected_keys, "G3C manifest")
    exact = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "suite_id": SUITE_ID,
        "corpus_version": "2026-07-17",
        "suite_role": "single_frozen_g3c_rerun",
        "sealed_before_model_run": True,
        "post_seal_prompt_tuning_allowed": False,
        "model_generated_gold": False,
        "training_export": False,
        "output_root": SEALED_OUTPUT_ROOT_REPO_RELATIVE,
    }
    for key, expected in exact.items():
        if manifest[key] != expected or type(manifest[key]) is not type(expected):
            raise ValueError(f"G3C manifest {key} differs from its seal")
    if manifest["counts"] != {
        "cases": CASE_COUNT,
        "roots": PAIR_COUNT,
        "slovenian": PAIR_COUNT,
        "english": PAIR_COUNT,
        "bilingual_pairs": PAIR_COUNT,
    }:
        raise ValueError("G3C manifest counts differ from 8 x 2")
    _manifest_file_map(manifest)
    if manifest["frozen_profile"] != _current_frozen_profile():
        raise ValueError("G3C manifest differs from the current frozen V3 profile")


def load_g3c_suite(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    expected_manifest_sha256: str | None = EXPECTED_MANIFEST_SHA256,
) -> G3CSuite:
    path = manifest_path.expanduser().resolve()
    manifest_payload = path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    if (
        expected_manifest_sha256 is not None
        and manifest_sha256 != expected_manifest_sha256
    ):
        raise ValueError("G3C manifest differs from the pinned SHA-256")
    manifest = _json_object(manifest_payload, label=str(path))
    if manifest_payload != canonical_json_bytes(manifest) + b"\n":
        raise ValueError("G3C manifest must be canonical JSON")
    _validate_manifest_shape(manifest)
    file_map = _manifest_file_map(manifest)
    for name, entry in file_map.items():
        corpus_path = path.parent / name
        if _file_sha256(corpus_path) != entry["sha256"]:
            raise ValueError(f"G3C corpus hash differs for {name}")

    packet_records = _read_jsonl(path.parent / "packets.jsonl")
    gold_records = _read_jsonl(path.parent / "gold.jsonl")
    call_records = _read_jsonl(path.parent / "call_specs.jsonl")
    pair_registry = _read_canonical_json(path.parent / "bilingual_pairs.json")
    if not (
        len(packet_records) == len(gold_records) == len(call_records) == CASE_COUNT
    ):
        raise ValueError("G3C corpus must contain exactly 16 aligned records")
    expected_counts = {
        "packets.jsonl": CASE_COUNT,
        "gold.jsonl": CASE_COUNT,
        "bilingual_pairs.json": PAIR_COUNT,
        "call_specs.jsonl": CASE_COUNT,
    }
    if any(file_map[name]["record_count"] != count for name, count in expected_counts.items()):
        raise ValueError("G3C manifest record counts differ from the seal")
    _strict_keys(pair_registry, _PAIR_REGISTRY_KEYS, "G3C pair registry")
    if (
        pair_registry["schema_version"] != PAIR_REGISTRY_SCHEMA_VERSION
        or pair_registry["suite_id"] != SUITE_ID
        or type(pair_registry["pairs"]) is not list
        or len(pair_registry["pairs"]) != PAIR_COUNT
    ):
        raise ValueError("G3C pair registry header differs from its seal")

    cases: list[G3CCase] = []
    for index, (packet_record, gold_record, call_record) in enumerate(
        zip(packet_records, gold_records, call_records, strict=True)
    ):
        _strict_keys(packet_record, _PACKET_RECORD_KEYS, f"packet record {index}")
        _strict_keys(gold_record, _GOLD_RECORD_KEYS, f"gold record {index}")
        _strict_keys(call_record, _CALL_RECORD_KEYS, f"call record {index}")
        if packet_record["schema_version"] != PACKET_RECORD_SCHEMA_VERSION:
            raise ValueError(f"Packet record {index} has the wrong schema")
        if gold_record["schema_version"] != GOLD_RECORD_SCHEMA_VERSION:
            raise ValueError(f"Gold record {index} has the wrong schema")
        if call_record["schema_version"] != CALL_RECORD_SCHEMA_VERSION:
            raise ValueError(f"Call record {index} has the wrong schema")
        if any(packet_record[key] != gold_record[key] for key in _IDENTITY_KEYS):
            raise ValueError(f"Packet/gold identity differs at record {index}")
        if call_record["case_id"] != packet_record["case_id"]:
            raise ValueError(f"Packet/call identity differs at record {index}")
        for key in _IDENTITY_KEYS:
            if not isinstance(packet_record[key], str) or not packet_record[key].strip():
                raise ValueError(f"G3C record {index} has an invalid {key}")
        if not _SAFE_SEGMENT.fullmatch(packet_record["case_id"]):
            raise ValueError(f"G3C case ID is unsafe at record {index}")
        packet = RacioEpistemicPacketV3.model_validate_json(
            canonical_json_bytes(packet_record["packet"])
        )
        gold = EpistemicCaseGoldV3.model_validate_json(
            canonical_json_bytes(gold_record["gold"])
        )
        call = ProviderCallSpec.model_validate_json(
            canonical_json_bytes(call_record["call_spec"])
        )
        if (
            gold.case_id != packet_record["case_id"]
            or gold.bilingual_pair_id != packet_record["bilingual_pair_id"]
            or gold.expected_source_mind != packet.source_mind
            or gold.expected_presentation_mode != packet.presentation_mode
        ):
            raise ValueError(f"G3C typed identity differs at record {index}")
        case = G3CCase(
            case_id=packet_record["case_id"],
            root_label=packet_record["root_label"],
            bilingual_pair_id=packet_record["bilingual_pair_id"],
            source_case_id=packet_record["source_case_id"],
            source_root_id=packet_record["source_root_id"],
            packet=packet,
            gold=gold,
            call_spec=call,
        )
        _validate_provider_boundary(case)
        _verify_static_call_spec(case)
        cases.append(case)

    case_by_id = {case.case_id: case for case in cases}
    if len(case_by_id) != CASE_COUNT:
        raise ValueError("G3C case IDs must be unique")
    observed_identities = tuple(
        (
            case.case_id,
            case.root_label,
            case.bilingual_pair_id,
            case.source_case_id,
            case.source_root_id,
            case.packet.presentation_mode,
        )
        for case in cases
    )
    if observed_identities != EXPECTED_CASE_IDENTITIES:
        raise ValueError("G3C cases differ from the eight frozen G3 root mappings")
    if manifest["case_order"] != [case.case_id for case in cases]:
        raise ValueError("G3C case order differs from the JSONL seal")

    pairs: list[G3CPair] = []
    for index, raw_pair in enumerate(pair_registry["pairs"]):
        if type(raw_pair) is not dict:
            raise ValueError(f"G3C pair {index} must be an object")
        _strict_keys(raw_pair, _PAIR_KEYS, f"G3C pair {index}")
        pair = G3CPair(**raw_pair)
        if not _SAFE_SEGMENT.fullmatch(pair.bilingual_pair_id):
            raise ValueError(f"G3C pair ID is unsafe at record {index}")
        try:
            sl_case = case_by_id[pair.sl_case_id]
            en_case = case_by_id[pair.en_case_id]
        except KeyError as exc:
            raise ValueError(f"G3C pair {pair.bilingual_pair_id} cites unknown case") from exc
        if (
            sl_case.bilingual_pair_id != pair.bilingual_pair_id
            or en_case.bilingual_pair_id != pair.bilingual_pair_id
            or sl_case.root_label != pair.root_label
            or en_case.root_label != pair.root_label
            or sl_case.packet.presentation_mode != "canonical_sl_only"
            or en_case.packet.presentation_mode != "operational_en_only"
        ):
            raise ValueError(f"G3C pair {pair.bilingual_pair_id} wrapper is invalid")
        sl_identity = _canonical_evidence_sha256(sl_case.packet)
        en_identity = _canonical_evidence_sha256(en_case.packet)
        if sl_identity != en_identity or pair.canonical_evidence_sha256 != sl_identity:
            raise ValueError(f"G3C pair {pair.bilingual_pair_id} evidence identity differs")
        pairs.append(pair)
    if len({pair.bilingual_pair_id for pair in pairs}) != PAIR_COUNT:
        raise ValueError("G3C pair IDs must be unique")
    if tuple(pair.root_label for pair in pairs) != EXPECTED_ROOT_LABELS:
        raise ValueError("G3C bilingual pairs differ from the frozen root order")
    if manifest["pair_order"] != [pair.bilingual_pair_id for pair in pairs]:
        raise ValueError("G3C pair order differs from the registry seal")

    expected_maps = {
        "packet_hashes": {case.case_id: case.packet.packet_hash for case in cases},
        "gold_sha256": {case.case_id: sha256_hex(case.gold) for case in cases},
        "provider_payload_sha256": {
            case.case_id: hashlib.sha256(case.packet.provider_payload_bytes()).hexdigest()
            for case in cases
        },
        "call_spec_hashes": {
            case.case_id: case.call_spec.content_hash() for case in cases
        },
    }
    for key, expected in expected_maps.items():
        if manifest[key] != expected:
            raise ValueError(f"G3C manifest {key} differs from typed records")
    return G3CSuite(
        manifest_path=path,
        manifest_sha256=manifest_sha256,
        manifest=manifest,
        pair_registry=pair_registry,
        cases=tuple(cases),
        pairs=tuple(pairs),
    )


def _require_committed_suite(suite: G3CSuite) -> str:
    if suite.manifest_path != DEFAULT_MANIFEST_PATH.resolve():
        raise ValueError("G3C execution requires the canonical committed corpus")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *_SCOPED_SOURCE_PATHS],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        raise ValueError("G3C scoped source files must be committed before execution")
    for cached in (False, True):
        command = ["git", "diff", "--quiet"]
        if cached:
            command.append("--cached")
        command.extend(["HEAD", "--", *_SCOPED_SOURCE_PATHS])
        if subprocess.run(command, cwd=ROOT, check=False).returncode != 0:
            raise ValueError("G3C scoped source differs from its committed source")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("G3C source commit is not a full Git SHA")
    return commit


def _failed_call_record(
    *,
    call: ProviderCallSpec,
    started_at: Any,
    finished_at: Any,
    failure_code: str,
) -> ProviderCallRecord:
    record = ProviderCallRecord(
        call_id=call.call_id,
        spec_hash=call.content_hash(),
        request_id=call.request_id,
        input_artifact_ids=call.input_artifact_ids,
        provider=call.provider,
        seed=call.seed,
        parameters=call.parameters,
        timeout_seconds=call.timeout_seconds,
        started_at=started_at,
        primary_finished_at=finished_at,
        finished_at=finished_at,
        status="failed",
        primary_status="failed",
        output_artifact_ids=(),
        warnings=(f"sanitized_failure_code:{failure_code}",),
        safety_notice=call.safety_notice,
    )
    ensure_call_record_contract(call, record)
    return record


def _validation_boundary(stage: str) -> str:
    return {
        "draft_v3_validation": "during_json_pydantic_validation",
        "canonicalizer_v3_validation": "after_json_pydantic_validation",
    }.get(stage, "before_json_pydantic_validation")


def _safe_failure(exc: Exception) -> tuple[str, dict[str, Any]]:
    if isinstance(exc, Gemma4EpistemicV3ExecutionError):
        failure_code = exc.failure_code
        stage = exc.failure_stage
        diagnostics = dict(exc.p3_diagnostics())
        validation_error = diagnostics.pop("validation_error", None)
        diagnostics.pop("failure_code", None)
        safe_diagnostics = {
            key: value
            for key, value in diagnostics.items()
            if key
            not in {
                "final_json",
                "thinking",
                "raw_response",
                "response_envelope",
            }
        }
        if validation_error is not None:
            safe_diagnostics["validation_diagnostic_sha256"] = hashlib.sha256(
                validation_error.encode("utf-8")
            ).hexdigest()
    else:
        failure_code = "unexpected_provider_failure"
        stage = "transport"
        safe_diagnostics = {"exception_type": type(exc).__name__}
    return failure_code, {
        "failure_code": failure_code,
        "failure_stage": stage,
        "validation_boundary": _validation_boundary(stage),
        "sanitized_diagnostics": safe_diagnostics,
        "rejected_content_persisted": False,
        "thinking_content_persisted": False,
        "raw_response_envelope_persisted": False,
    }


def build_uncertainty_receipt(
    *, case: G3CCase, output: RacioEpistemicInterpretationV3 | None
) -> dict[str, Any]:
    report = None if output is None else output.racio_reported_uncertainty
    return {
        "schema_version": "rei-racio-g3c-v3-uncertainty-receipt-v1",
        "case_id": case.case_id,
        "bilingual_pair_id": case.bilingual_pair_id,
        "structure_status": "not_available" if report is None else "valid",
        "racio_reported_uncertainty": (
            None if report is None else report.model_dump(mode="json")
        ),
        "evaluator_reference": {
            "option_determinacy": case.gold.option_determinacy,
            "motive_identifiability": case.gold.motive_identifiability,
        },
        "used_as_hard_gate": False,
        "mechanically_repaired": False,
    }


def _bool_counts(values: list[bool]) -> dict[str, int]:
    return {"true": sum(values), "false": len(values) - sum(values)}


def _value_counts(values: list[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values).items()))


def _ratio(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": (
            None if denominator == 0 else round(numerator / denominator, 12)
        ),
    }


def _assert_no_aggregate(value: Any) -> None:
    if isinstance(value, Mapping):
        if set(value).intersection(_FORBIDDEN_AGGREGATE_KEYS):
            raise ValueError("G3C artifact contains an aggregate semantic result")
        for item in value.values():
            _assert_no_aggregate(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_aggregate(item)


def build_g3c_report(
    *,
    cases: tuple[G3CCase, ...],
    case_results: tuple[Mapping[str, Any], ...],
    pair_results: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    case_by_id = {case.case_id: case for case in cases}
    evaluations = [item["evaluation"] for item in case_results]
    evaluated_pairs = [item for item in pair_results if item["status"] == "evaluated"]
    pair_evaluations = [item["evaluation"] for item in evaluated_pairs]

    def selected_rows(mode: str | None = None) -> list[Mapping[str, Any]]:
        return [
            row
            for row in case_results
            if mode is None or row["presentation_mode"] == mode
        ]

    def action_coverage(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
        family_numerator = 0
        family_denominator = 0
        subtype_numerator = 0
        subtype_denominator = 0
        for row in rows:
            gold = case_by_id[row["case_id"]].gold
            target_families = {item.family for item in gold.exact_action_targets}
            target_keys = {item.key for item in gold.exact_action_targets}
            assessments = row["evaluation"]["action_hypothesis_assessments"]
            credited_families = {
                item["family"] for item in assessments if item["family_credit"]
            }
            credited_keys = {
                (item["family"], item["subtype"])
                for item in assessments
                if item["subtype_credit"]
            }
            family_numerator += len(target_families.intersection(credited_families))
            family_denominator += len(target_families)
            subtype_numerator += len(target_keys.intersection(credited_keys))
            subtype_denominator += len(target_keys)
        return {
            "family": _ratio(family_numerator, family_denominator),
            "exact_subtype": _ratio(subtype_numerator, subtype_denominator),
        }

    def motive_coverage(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
        family_numerator = 0
        family_denominator = 0
        subtype_numerator = 0
        subtype_denominator = 0
        for row in rows:
            gold = case_by_id[row["case_id"]].gold
            target_families = {item.family for item in gold.direct_motive_targets}
            target_keys = {item.key for item in gold.direct_motive_targets}
            assessments = row["evaluation"]["motive_hypothesis_assessments"]
            credited_families = {
                item["family"] for item in assessments if item["family_credit"]
            }
            credited_keys = {
                (item["family"], item["subtype"])
                for item in assessments
                if item["reference_supported"]
            }
            family_numerator += len(target_families.intersection(credited_families))
            family_denominator += len(target_families)
            subtype_numerator += len(target_keys.intersection(credited_keys))
            subtype_denominator += len(target_keys)
        return {
            "direct_family": _ratio(family_numerator, family_denominator),
            "direct_exact_subtype": _ratio(
                subtype_numerator, subtype_denominator
            ),
        }

    def pair_ratio(field: str, nested: str | None = None) -> dict[str, Any]:
        values = [
            item[field] if nested is None else item[field][nested]
            for item in pair_evaluations
        ]
        return {
            **_ratio(sum(value is True for value in values), len(values)),
            "not_evaluable_pairs": PAIR_COUNT - len(values),
        }

    all_rows = selected_rows()
    sl_rows = selected_rows("canonical_sl_only")
    en_rows = selected_rows("operational_en_only")
    successful_rows = [
        row for row in all_rows if row["provider_status"] == "succeeded"
    ]
    successful_sl_rows = [
        row for row in sl_rows if row["provider_status"] == "succeeded"
    ]
    successful_en_rows = [
        row for row in en_rows if row["provider_status"] == "succeeded"
    ]
    all_action_assessments = [
        item
        for row in all_rows
        for item in row["evaluation"]["action_hypothesis_assessments"]
    ]
    all_motive_assessments = [
        item
        for row in all_rows
        for item in row["evaluation"]["motive_hypothesis_assessments"]
    ]

    emitted_option_rows = [
        row for row in all_rows if row["option_inference_present"] is True
    ]
    unique_rows = [
        row
        for row in successful_rows
        if case_by_id[row["case_id"]].gold.option_determinacy == "unique"
    ]
    planned_unique_rows = [
        row
        for row in all_rows
        if case_by_id[row["case_id"]].gold.option_determinacy == "unique"
    ]
    abstention_rows = [
        row
        for row in successful_rows
        if case_by_id[row["case_id"]].gold.required_abstention
    ]
    planned_abstention_rows = [
        row
        for row in all_rows
        if case_by_id[row["case_id"]].gold.required_abstention
    ]
    unsupported_option_states = {
        "mismatched",
        "mapping_without_visible_support",
        "overcommitted",
    }
    option_metrics = {
        "semantic_denominator_scope": "validated_provider_outputs_only",
        "output_evaluable_case_count": len(successful_rows),
        "missing_output_case_count": len(all_rows) - len(successful_rows),
        "unique_option_mapping": _ratio(
            sum(row["evaluation"]["option_mapping"] == "mapped" for row in unique_rows),
            len(unique_rows),
        ),
        "planned_unique_option_cases": len(planned_unique_rows),
        "unique_option_cases_without_validated_output": (
            len(planned_unique_rows) - len(unique_rows)
        ),
        "required_abstention": _ratio(
            sum(
                row["evaluation"]["required_abstention"]
                == "required_and_observed"
                for row in abstention_rows
            ),
            len(abstention_rows),
        ),
        "planned_required_abstention_cases": len(planned_abstention_rows),
        "required_abstention_cases_without_validated_output": (
            len(planned_abstention_rows) - len(abstention_rows)
        ),
        "option_specific_evidence_support": _ratio(
            sum(
                row["evaluation"]["option_citation_support"] is True
                for row in emitted_option_rows
            ),
            len(emitted_option_rows),
        ),
        "option_specific_citation_failure_count": sum(
            row["evaluation"]["option_citation_support"] is False
            for row in emitted_option_rows
        ),
        "unsupported_option_selection_count": sum(
            row["evaluation"]["option_mapping"] in unsupported_option_states
            for row in emitted_option_rows
        ),
        "mapping_state_counts": _value_counts(
            [row["evaluation"]["option_mapping"] for row in all_rows]
        ),
        "bilingual_option_consistency": pair_ratio(
            "option_mapping_consistency"
        ),
    }

    direct_supported_motives = sum(
        item["reference_supported"] is True for item in all_motive_assessments
    )
    motive_precision = _ratio(
        direct_supported_motives, len(all_motive_assessments)
    )
    nonidentifiable_rows = [
        row
        for row in successful_rows
        if case_by_id[row["case_id"]].gold.motive_identifiability
        == "not_identifiable"
    ]
    planned_nonidentifiable_rows = [
        row
        for row in all_rows
        if case_by_id[row["case_id"]].gold.motive_identifiability
        == "not_identifiable"
    ]
    empty_motive_correct = sum(
        row["provider_status"] == "succeeded"
        and row["motive_hypothesis_count"] == 0
        for row in nonidentifiable_rows
    )
    motive_metrics = {
        "semantic_denominator_scope": "validated_provider_outputs_only",
        "output_evaluable_case_count": len(successful_rows),
        "missing_output_case_count": len(all_rows) - len(successful_rows),
        "target_level_coverage": motive_coverage(successful_rows),
        "planned_target_level_coverage": motive_coverage(all_rows),
        "sl_target_level_coverage": motive_coverage(successful_sl_rows),
        "en_target_level_coverage": motive_coverage(successful_en_rows),
        "directly_supported_motive_family_coverage": motive_coverage(
            successful_rows
        )["direct_family"],
        "directly_supported_motive_subtype_coverage": motive_coverage(
            successful_rows
        )["direct_exact_subtype"],
        "directly_supported_motive_precision": motive_precision,
        "motive_precision": motive_precision,
        "motive_hypothesis_citation_support": _ratio(
            sum(item["citation_support"] is True for item in all_motive_assessments),
            len(all_motive_assessments),
        ),
        "contextually_supported_hypothesis_count": sum(
            item["support_mode"] == "contextually_supported"
            for item in all_motive_assessments
        ),
        "speculative_hypothesis_count": sum(
            item["support_mode"] == "speculative"
            for item in all_motive_assessments
        ),
        "unsupported_motive_overclaim_count": sum(
            row["evaluation"]["motive_unsupported_overclaims"] for row in all_rows
        ),
        "unsupported_motive_overclaims": sum(
            row["evaluation"]["motive_unsupported_overclaims"] for row in all_rows
        ),
        "high_confidence_unsupported_motive_count": sum(
            row["evaluation"]["high_confidence_unsupported_motive_count"]
            for row in all_rows
        ),
        "high_confidence_unsupported_motives": sum(
            row["evaluation"]["high_confidence_unsupported_motive_count"]
            for row in all_rows
        ),
        "high_confidence_threshold": 0.5,
        "empty_motive_correctness": _ratio(
            empty_motive_correct, len(nonidentifiable_rows)
        ),
        "planned_nonidentifiable_case_count": len(planned_nonidentifiable_rows),
        "nonidentifiable_cases_without_validated_output": (
            len(planned_nonidentifiable_rows) - len(nonidentifiable_rows)
        ),
        "unknown_preservation_counts": _value_counts(
            [row["evaluation"]["unknown_preservation"]["motive"] for row in all_rows]
        ),
        "required_unknown_preservation": _ratio(
            sum(
                row["evaluation"]["unknown_preservation"]["motive"]
                == "preserved"
                for row in nonidentifiable_rows
            ),
            len(nonidentifiable_rows),
        ),
        "sl_unsupported_overclaim_count": sum(
            row["evaluation"]["motive_unsupported_overclaims"] for row in sl_rows
        ),
        "en_unsupported_overclaim_count": sum(
            row["evaluation"]["motive_unsupported_overclaims"] for row in en_rows
        ),
        "bilingual_family_consistency": pair_ratio(
            "bilingual_family_consistency", "motive"
        ),
        "bilingual_subtype_consistency": pair_ratio(
            "bilingual_subtype_consistency", "motive"
        ),
    }

    def uncertainty_states(
        rows: list[Mapping[str, Any]], field: str
    ) -> dict[str, int]:
        values: list[str] = []
        for row in rows:
            reported = row["uncertainty_receipt"]["racio_reported_uncertainty"]
            if reported is None:
                raise ValueError(
                    "Uncertainty state counts require a validated provider output"
                )
            state = reported[field]
            if state not in {"uncertain", "not_uncertain", "not_reported"}:
                raise ValueError("Racio uncertainty differs from its three-state contract")
            values.append(state)
        return _value_counts(values)

    def uncertainty_cross_tab(reference: str, field: str) -> dict[str, Any]:
        table: dict[str, Counter[str]] = {}
        for row in successful_rows:
            gold = case_by_id[row["case_id"]].gold
            reference_value = str(getattr(gold, reference))
            reported = row["uncertainty_receipt"]["racio_reported_uncertainty"]
            if reported is None:
                raise ValueError(
                    "Uncertainty comparison requires a validated provider output"
                )
            state = reported[field]
            table.setdefault(reference_value, Counter())[state] += 1
        return {
            key: dict(sorted(counts.items()))
            for key, counts in sorted(table.items())
        }

    uncertainty_metrics = {
        "used_as_hard_gate": False,
        "mechanically_repaired": False,
        "semantic_denominator_scope": "validated_provider_outputs_only",
        "output_evaluable_case_count": len(successful_rows),
        "self_report_unavailable_case_count": len(all_rows) - len(successful_rows),
        "option_mapping_self_report_states": uncertainty_states(
            successful_rows, "option_mapping"
        ),
        "motive_interpretation_self_report_states": uncertainty_states(
            successful_rows, "motive_interpretation"
        ),
        "sl_option_mapping_self_report_states": uncertainty_states(
            successful_sl_rows, "option_mapping"
        ),
        "en_option_mapping_self_report_states": uncertainty_states(
            successful_en_rows, "option_mapping"
        ),
        "sl_motive_interpretation_self_report_states": uncertainty_states(
            successful_sl_rows, "motive_interpretation"
        ),
        "en_motive_interpretation_self_report_states": uncertainty_states(
            successful_en_rows, "motive_interpretation"
        ),
        "option_determinacy_comparison": uncertainty_cross_tab(
            "option_determinacy", "option_mapping"
        ),
        "motive_support_comparison": uncertainty_cross_tab(
            "motive_identifiability", "motive_interpretation"
        ),
        "bilingual_option_self_report_consistency": pair_ratio(
            "uncertainty_consistency", "option"
        ),
        "bilingual_motive_self_report_consistency": pair_ratio(
            "uncertainty_consistency", "motive"
        ),
        "bilingual_consistency": {
            "option_mapping": pair_ratio("uncertainty_consistency", "option"),
            "motive_interpretation": pair_ratio(
                "uncertainty_consistency", "motive"
            ),
        },
        "by_case": {
            row["case_id"]: row["uncertainty_receipt"] for row in all_rows
        },
    }

    action_metrics = {
        "semantic_denominator_scope": "validated_provider_outputs_only",
        "output_evaluable_case_count": len(successful_rows),
        "missing_output_case_count": len(all_rows) - len(successful_rows),
        "target_level_coverage": action_coverage(successful_rows),
        "planned_target_level_coverage": action_coverage(all_rows),
        "sl_target_level_coverage": action_coverage(successful_sl_rows),
        "en_target_level_coverage": action_coverage(successful_en_rows),
        "action_family_coverage": action_coverage(successful_rows)["family"],
        "exact_action_subtype_coverage": action_coverage(successful_rows)[
            "exact_subtype"
        ],
        "sl_action_family_support": action_coverage(successful_sl_rows)["family"],
        "en_action_family_support": action_coverage(successful_en_rows)["family"],
        "sl_exact_subtype_support": action_coverage(successful_sl_rows)[
            "exact_subtype"
        ],
        "en_exact_subtype_support": action_coverage(successful_en_rows)[
            "exact_subtype"
        ],
        "action_hypothesis_citation_support": _ratio(
            sum(item["citation_support"] is True for item in all_action_assessments),
            len(all_action_assessments),
        ),
        "family_fallback_count": sum(
            item["family_fallback"] is not None for item in all_action_assessments
        ),
        "direct_manifestation_count": sum(
            item["support_mode"] == "direct_manifestation"
            for item in all_action_assessments
        ),
        "functional_inference_count": sum(
            item["support_mode"] == "functional_inference"
            for item in all_action_assessments
        ),
        "speculative_action_count": sum(
            item["support_mode"] == "speculative"
            for item in all_action_assessments
        ),
        "unsupported_action_overclaim_count": sum(
            row["evaluation"]["action_unsupported_overclaims"] for row in all_rows
        ),
        "action_unsupported_overclaims": sum(
            row["evaluation"]["action_unsupported_overclaims"] for row in all_rows
        ),
        "bilingual_family_consistency": pair_ratio(
            "bilingual_family_consistency", "action"
        ),
        "bilingual_subtype_consistency": pair_ratio(
            "bilingual_subtype_consistency", "action"
        ),
        "family_support_by_case": {
            row["case_id"]: row["evaluation"]["action_family_support"]
            for row in all_rows
        },
        "exact_subtype_support_by_case": {
            row["case_id"]: row["evaluation"]["action_subtype_support"]
            for row in all_rows
        },
        "hypothesis_assessments_by_case": {
            row["case_id"]: row["evaluation"]["action_hypothesis_assessments"]
            for row in all_rows
        },
    }

    structural_status = {
        "attempted_calls": sum(row["dispatch_count"] == 1 for row in all_rows),
        "successful_calls": sum(
            row["provider_status"] == "succeeded" for row in all_rows
        ),
        "failed_calls": sum(row["provider_status"] == "failed" for row in all_rows),
        "retries": sum(row["retry_count"] for row in all_rows),
        "fallbacks": sum(row["fallback"] != "none" for row in all_rows),
        "structural_validity": _bool_counts(
            [row["evaluation"]["structural_output_valid"] for row in all_rows]
        ),
        "draft_v3_validity": _value_counts(
            [row["draft_v3_status"] for row in all_rows]
        ),
        "canonicalizer_validity": _value_counts(
            [row["canonicalizer_v3_status"] for row in all_rows]
        ),
        "hidden_truth_leakage_count": sum(
            row["evaluation"]["hidden_truth_leakage_count"] for row in all_rows
        ),
        "profile_leakage_count": sum(
            row["evaluation"]["profile_leakage_count"] for row in all_rows
        ),
        "citation_scope": _value_counts(
            [
                (
                    "not_reached"
                    if row["provider_status"] != "succeeded"
                    else (
                        "valid"
                        if row["evaluation"]["citation_scope_valid"]
                        else "invalid"
                    )
                )
                for row in all_rows
            ]
        ),
        "citation_scope_failure_count": sum(
            row["provider_status"] == "succeeded"
            and row["evaluation"]["citation_scope_valid"] is False
            for row in all_rows
        ),
        "option_specific_citation_failure_count": option_metrics[
            "option_specific_citation_failure_count"
        ],
        "input_packet_unchanged": _bool_counts(
            [row["evaluation"]["input_packet_unchanged"] for row in all_rows]
        ),
        "hard_contract_pass": _bool_counts(
            [row["evaluation"]["hard_contract_pass"] for row in all_rows]
        ),
    }

    unknown_preservation_metrics = {
        "action": _value_counts(
            [item["unknown_preservation"]["action"] for item in evaluations]
        ),
        "motive": _value_counts(
            [item["unknown_preservation"]["motive"] for item in evaluations]
        ),
        "required_motive_preservation": motive_metrics[
            "required_unknown_preservation"
        ],
    }
    metric_contract = {
        "action_family_coverage": action_metrics["action_family_coverage"],
        "action_subtype_coverage": action_metrics[
            "exact_action_subtype_coverage"
        ],
        "action_unsupported_overclaims": action_metrics[
            "action_unsupported_overclaims"
        ],
        "option_mapping": {
            "unique_option_mapping": option_metrics["unique_option_mapping"],
            "state_counts": option_metrics["mapping_state_counts"],
        },
        "required_abstention": option_metrics["required_abstention"],
        "motive_family_coverage": motive_metrics[
            "directly_supported_motive_family_coverage"
        ],
        "motive_subtype_coverage": motive_metrics[
            "directly_supported_motive_subtype_coverage"
        ],
        "motive_precision": motive_metrics["motive_precision"],
        "high_confidence_unsupported_motives": motive_metrics[
            "high_confidence_unsupported_motives"
        ],
        "unknown_preservation": unknown_preservation_metrics,
        "bilingual_family_consistency": {
            "action": action_metrics["bilingual_family_consistency"],
            "motive": motive_metrics["bilingual_family_consistency"],
        },
        "bilingual_subtype_consistency": {
            "action": action_metrics["bilingual_subtype_consistency"],
            "motive": motive_metrics["bilingual_subtype_consistency"],
        },
        "uncertainty_consistency": uncertainty_metrics[
            "bilingual_consistency"
        ],
    }

    frozen_v2 = _read_canonical_json(FROZEN_G3_V2_REPORT)
    v2_sections = frozen_v2["sections"]
    v2_overclaims = v2_sections["6. Unsupported overclaims"]
    v2_bilingual = v2_sections["9. Slovenian-English consistency"]
    comparison = {
        "historical_sources": {
            "frozen_g3_v2_report_sha256": FROZEN_G3_V2_REPORT_SHA256,
            "g3a_adjudication_sha256": FROZEN_G3A_REPORT_SHA256,
            "v2_re_evaluated_with_v3_evaluator": False,
            "frozen_g3_changed": False,
        },
        "action_family_interpretation": {
            "frozen_v2_official": "not_represented",
            "g3a_descriptive_context_only": {
                "sl": {"supported": 5, "denominator": 8},
                "en": {"supported": 8, "denominator": 8},
            },
            "g3c_v3": {
                "combined": action_metrics["target_level_coverage"]["family"],
                "sl": action_metrics["sl_target_level_coverage"]["family"],
                "en": action_metrics["en_target_level_coverage"]["family"],
            },
        },
        "exact_action_subtype_interpretation": {
            "frozen_v2_official_action_support": v2_sections[
                "2. Action interpretation"
            ]["action_support"],
            "g3a_descriptive_context_only": {
                "sl": {"supported": 2, "denominator": 8},
                "en": {"supported": 6, "denominator": 8},
            },
            "g3c_v3": {
                "combined": action_metrics["target_level_coverage"][
                    "exact_subtype"
                ],
                "sl": action_metrics["sl_target_level_coverage"][
                    "exact_subtype"
                ],
                "en": action_metrics["en_target_level_coverage"][
                    "exact_subtype"
                ],
            },
            "denominators_are_not_declared_equivalent": True,
        },
        "option_mapping": {
            "frozen_v2": v2_sections["3. Option mapping"],
            "g3c_v3": option_metrics,
        },
        "required_abstention": {
            "frozen_v2": v2_sections["4. Required abstention"],
            "g3c_v3": option_metrics["required_abstention"],
        },
        "motive_coverage": {
            "frozen_v2_support_categories": v2_sections[
                "5. Motive hypotheses"
            ]["motive_support"],
            "g3c_v3_direct_target_coverage": {
                "combined": motive_metrics["target_level_coverage"],
                "sl": motive_metrics["sl_target_level_coverage"],
                "en": motive_metrics["en_target_level_coverage"],
            },
            "denominators_are_not_declared_equivalent": True,
        },
        "motive_overclaims": {
            "frozen_v2_flagged_total": sum(
                v2_overclaims["count_by_case"].values()
            ),
            "frozen_v2_cases_with_nonzero": v2_overclaims[
                "case_count_with_nonzero"
            ],
            "g3a_adjudicated_true_total": 14,
            "g3a_note": (
                "R3 SL was adjudicated as a gold-too-narrow flag; frozen G3 "
                "remains unchanged"
            ),
            "g3c_v3_total": motive_metrics[
                "unsupported_motive_overclaim_count"
            ],
            "g3c_v3_sl": motive_metrics["sl_unsupported_overclaim_count"],
            "g3c_v3_en": motive_metrics["en_unsupported_overclaim_count"],
            "g3c_v3_output_evaluable_case_count": motive_metrics[
                "output_evaluable_case_count"
            ],
            "g3c_v3_missing_output_case_count": motive_metrics[
                "missing_output_case_count"
            ],
            "direct_historical_comparison_available": (
                motive_metrics["missing_output_case_count"] == 0
            ),
            "comparison_caution": (
                None
                if motive_metrics["missing_output_case_count"] == 0
                else "G3C overclaims describe validated outputs only; missing outputs "
                "are not zero-overclaim semantic successes"
            ),
        },
        "bilingual_consistency": {
            "frozen_v2": {
                "action": v2_bilingual["action_consistent"],
                "option": v2_bilingual["option_consistent"],
                "motive_family": v2_bilingual["motive_family_consistent"],
                "motive_subtype": v2_bilingual["motive_subtype_consistent"],
            },
            "g3c_v3": {
                "action_family": action_metrics["bilingual_family_consistency"],
                "action_subtype": action_metrics[
                    "bilingual_subtype_consistency"
                ],
                "option": option_metrics["bilingual_option_consistency"],
                "motive_family": motive_metrics[
                    "bilingual_family_consistency"
                ],
                "motive_subtype": motive_metrics[
                    "bilingual_subtype_consistency"
                ],
            },
        },
        "uncertainty_consistency": {
            "frozen_v2": v2_bilingual["reported_uncertainty_consistent"],
            "g3c_v3_option": uncertainty_metrics[
                "bilingual_option_self_report_consistency"
            ],
            "g3c_v3_motive": uncertainty_metrics[
                "bilingual_motive_self_report_consistency"
            ],
        },
    }

    report = {
        "schema_version": "rei-racio-g3c-v3-report-v1",
        "study_context": {
            "development_rerun": True,
            "untouched_holdout": False,
            "generalization_claim": False,
            "model_promoted": False,
            "governance_authority": False,
            "runtime_authority": False,
        },
        "metric_contract": metric_contract,
        "sections": {
            "1. Structural contract": structural_status,
            "2. Action family and subtype": action_metrics,
            "3. Action unsupported overclaims": {
                "semantic_denominator_scope": "validated_provider_outputs_only",
                "output_evaluable_case_count": action_metrics[
                    "output_evaluable_case_count"
                ],
                "missing_output_case_count": action_metrics[
                    "missing_output_case_count"
                ],
                "emitted_action_hypothesis_count": len(all_action_assessments),
                "total": action_metrics["unsupported_action_overclaim_count"],
                "count_by_case": {
                    row["case_id"]: row["evaluation"][
                        "action_unsupported_overclaims"
                    ]
                    for row in case_results
                }
            },
            "4. Option mapping and abstention": option_metrics,
            "5. Motive coverage and precision": {
                **motive_metrics,
                "by_case": {
                    row["case_id"]: {
                        "family": row["evaluation"]["motive_family_coverage"],
                        "subtype": row["evaluation"]["motive_subtype_coverage"],
                        "precision": row["evaluation"]["motive_precision"],
                        "contextual_count": row["evaluation"][
                            "contextual_motive_hypothesis_count"
                        ],
                        "speculative_count": row["evaluation"][
                            "speculative_motive_hypothesis_count"
                        ],
                    }
                    for row in case_results
                }
            },
            "6. Motive overclaims and minimality": {
                "semantic_denominator_scope": "validated_provider_outputs_only",
                "output_evaluable_case_count": motive_metrics[
                    "output_evaluable_case_count"
                ],
                "missing_output_case_count": motive_metrics[
                    "missing_output_case_count"
                ],
                "emitted_motive_hypothesis_count": len(all_motive_assessments),
                "unsupported_total": motive_metrics[
                    "unsupported_motive_overclaim_count"
                ],
                "high_confidence_unsupported_total": motive_metrics[
                    "high_confidence_unsupported_motive_count"
                ],
                "by_case": {
                    row["case_id"]: {
                        "unsupported": row["evaluation"][
                            "motive_unsupported_overclaims"
                        ],
                        "redundant_nonminimal": row["evaluation"][
                            "motive_redundant_nonminimal_count"
                        ],
                        "high_confidence_unsupported": row["evaluation"][
                            "high_confidence_unsupported_motive_count"
                        ],
                        "assessments": row["evaluation"][
                            "motive_hypothesis_assessments"
                        ],
                    }
                    for row in case_results
                }
            },
            "7. Unknown preservation": unknown_preservation_metrics,
            "8. Racio-reported uncertainty": uncertainty_metrics,
            "9. Slovenian-English consistency": {
                "evaluated_pair_count": len(evaluated_pairs),
                "not_evaluable_pair_count": len(pair_results) - len(evaluated_pairs),
                "family_consistency": {
                    "action": _bool_counts(
                        [
                            item["bilingual_family_consistency"]["action"]
                            for item in pair_evaluations
                        ]
                    ),
                    "motive": _bool_counts(
                        [
                            item["bilingual_family_consistency"]["motive"]
                            for item in pair_evaluations
                        ]
                    ),
                },
                "subtype_consistency": {
                    "action": _bool_counts(
                        [
                            item["bilingual_subtype_consistency"]["action"]
                            for item in pair_evaluations
                        ]
                    ),
                    "motive": _bool_counts(
                        [
                            item["bilingual_subtype_consistency"]["motive"]
                            for item in pair_evaluations
                        ]
                    ),
                },
                "option_consistency": option_metrics[
                    "bilingual_option_consistency"
                ],
                "option_uncertainty_consistency": uncertainty_metrics[
                    "bilingual_option_self_report_consistency"
                ],
                "motive_uncertainty_consistency": uncertainty_metrics[
                    "bilingual_motive_self_report_consistency"
                ],
                "canonical_evidence_identity_consistency": pair_ratio(
                    "canonical_evidence_identity_consistent"
                ),
                "source_mind_consistency": pair_ratio("source_mind_consistent"),
                "citation_identity_consistency": pair_ratio(
                    "citation_identity_consistency"
                ),
                "action_support_mode_consistency": pair_ratio(
                    "action_support_mode_consistency"
                ),
                "motive_support_mode_consistency": pair_ratio(
                    "motive_support_mode_consistency"
                ),
                "pair_artifacts": list(pair_results),
            },
            "10. Individual failures": {
                "provider_failure_codes": _value_counts(
                    [
                        row["failure_code"]
                        for row in case_results
                        if row["failure_code"] is not None
                    ]
                ),
                "cases": [
                    {
                        "case_id": row["case_id"],
                        "provider_status": row["provider_status"],
                        "failure_code": row["failure_code"],
                        "failure_stage": row["failure_stage"],
                        "validation_boundary": row["validation_boundary"],
                        "research_observations": row["evaluation"][
                            "research_observations"
                        ],
                    }
                    for row in case_results
                    if row["failure_code"] is not None
                    or row["evaluation"]["research_observations"]
                ],
            },
            "11. Confidence values": {
                "by_case": {
                    row["case_id"]: row["confidence_values"] for row in all_rows
                },
                "high_confidence_unsupported_threshold": 0.5,
            },
            "12. Frozen G3 V2 versus G3C V3": comparison,
        },
    }
    _assert_no_aggregate(report)
    return report


def _build_summary(
    *,
    report: Mapping[str, Any],
    case_results: tuple[Mapping[str, Any], ...],
    pair_results: tuple[Mapping[str, Any], ...],
    chat_dispatch_count: int,
) -> dict[str, Any]:
    success_count = sum(item["provider_status"] == "succeeded" for item in case_results)
    sections = report["sections"]
    summary = {
        "study_context": report["study_context"],
        "metric_contract": report["metric_contract"],
        "technical_completeness": {
            "planned_call_count": CASE_COUNT,
            "chat_dispatch_count": chat_dispatch_count,
            "retry_count": 0,
            "fallback_count": 0,
            "case_result_count": len(case_results),
            "provider_success_count": success_count,
            "provider_failure_count": CASE_COUNT - success_count,
            "bilingual_pair_artifact_count": len(pair_results),
            "evaluated_bilingual_pair_count": sum(
                item["status"] == "evaluated" for item in pair_results
            ),
            "not_evaluable_bilingual_pair_count": sum(
                item["status"] == "not_evaluable" for item in pair_results
            ),
            "all_attempts_accounted": len(case_results) == CASE_COUNT,
            "one_dispatch_per_case": chat_dispatch_count == CASE_COUNT,
            "thinking_content_persisted": False,
            "raw_response_envelope_persisted": False,
        },
        "independent_dimension_counts": {
            "structural_contract": sections["1. Structural contract"],
            "action_family_and_subtype": sections[
                "2. Action family and subtype"
            ],
            "action_unsupported_overclaims": sections[
                "3. Action unsupported overclaims"
            ],
            "option_mapping_and_abstention": sections[
                "4. Option mapping and abstention"
            ],
            "motive_coverage_and_precision": sections[
                "5. Motive coverage and precision"
            ],
            "motive_overclaims_and_minimality": sections[
                "6. Motive overclaims and minimality"
            ],
            "unknown_preservation": sections["7. Unknown preservation"],
            "racio_reported_uncertainty": sections[
                "8. Racio-reported uncertainty"
            ],
            "slovenian_english_consistency": sections[
                "9. Slovenian-English consistency"
            ],
            "individual_failures": sections["10. Individual failures"][
                "provider_failure_codes"
            ],
            "confidence_values": sections["11. Confidence values"],
            "frozen_v2_vs_g3c_v3": sections[
                "12. Frozen G3 V2 versus G3C V3"
            ],
        },
    }
    _assert_no_aggregate(summary)
    return summary


def _confidence_values(
    output: RacioEpistemicInterpretationV3 | None,
) -> dict[str, Any] | None:
    if output is None:
        return None
    option = output.option_inference
    return {
        "action_hypotheses": [
            {
                "family": item.family,
                "subtype": item.subtype,
                "family_fallback": item.family_fallback,
                "support_mode": item.support_mode,
                "confidence": item.confidence,
            }
            for item in output.action_hypotheses
        ],
        "option_inference": (
            None
            if option is None
            else {
                "option_id": option.option_id,
                "confidence": option.confidence,
            }
        ),
        "motive_hypotheses": [
            {
                "family": item.family,
                "subtype": item.subtype,
                "support_mode": item.support_mode,
                "confidence": item.confidence,
            }
            for item in output.motive_hypotheses
        ],
    }


def _validation_statuses(
    failure_payload: Mapping[str, Any] | None,
) -> tuple[str, str, str | None, str | None]:
    if failure_payload is None:
        return "valid", "valid", None, None
    stage = str(failure_payload["failure_stage"])
    boundary = str(failure_payload["validation_boundary"])
    if stage == "draft_v3_validation":
        return "invalid", "not_reached", stage, boundary
    if stage == "canonicalizer_v3_validation":
        return "valid", "invalid", stage, boundary
    return "not_reached", "not_reached", stage, boundary


def _build_case_result(
    *,
    case: G3CCase,
    draft: RacioEpistemicDraftV3 | None,
    output: RacioEpistemicInterpretationV3 | None,
    provider_status: str,
    failure_code: str | None,
    failure_payload: Mapping[str, Any] | None,
    evaluation: RacioEpistemicCaseEvaluationV3,
    uncertainty: Mapping[str, Any],
) -> dict[str, Any]:
    if (provider_status == "succeeded") != (
        draft is not None and output is not None and failure_payload is None
    ):
        raise ValueError("G3C case-result success lineage is inconsistent")
    if (provider_status == "failed") != (
        draft is None and output is None and failure_payload is not None
    ):
        raise ValueError("G3C case-result failure lineage is inconsistent")
    if provider_status == "succeeded" and failure_code is not None:
        raise ValueError("Successful G3C case cannot carry a failure code")
    if provider_status == "failed" and (
        failure_code is None or failure_payload["failure_code"] != failure_code
    ):
        raise ValueError("Failed G3C case must carry its sanitized failure code")
    draft_status, canonicalizer_status, failure_stage, validation_boundary = (
        _validation_statuses(failure_payload)
    )
    call = case.call_spec
    result = {
        "schema_version": "rei-racio-g3c-v3-case-result-v1",
        "case_id": case.case_id,
        "root_label": case.root_label,
        "bilingual_pair_id": case.bilingual_pair_id,
        "presentation_mode": case.packet.presentation_mode,
        "provider_status": provider_status,
        "failure_code": failure_code,
        "failure_stage": failure_stage,
        "validation_boundary": validation_boundary,
        "draft_v3_status": draft_status,
        "canonicalizer_v3_status": canonicalizer_status,
        "dispatch_count": 1,
        "retry_count": 0,
        "fallback": "none",
        "packet_id": case.packet.packet_id,
        "packet_hash": case.packet.packet_hash,
        "provider_payload_sha256": hashlib.sha256(
            case.packet.provider_payload_bytes()
        ).hexdigest(),
        "call_id": call.call_id,
        "call_spec_hash": call.content_hash(),
        "draft_sha256": None if draft is None else sha256_hex(draft),
        "output_sha256": None if output is None else sha256_hex(output),
        "option_inference_present": (
            None if output is None else output.option_inference is not None
        ),
        "motive_hypothesis_count": (
            None if output is None else len(output.motive_hypotheses)
        ),
        "confidence_values": _confidence_values(output),
        "structural_sidecar": (
            None
            if output is None
            else RacioEpistemicStructuralSidecarV3.from_output(output).model_dump(
                mode="json"
            )
        ),
        "evaluation": evaluation.model_dump(mode="json"),
        "uncertainty_receipt": dict(uncertainty),
    }
    _assert_no_aggregate(result)
    return result


def _build_pair_result(
    *,
    pair: G3CPair,
    case_by_id: Mapping[str, G3CCase],
    outputs: Mapping[str, RacioEpistemicInterpretationV3],
) -> dict[str, Any]:
    if pair.sl_case_id in outputs and pair.en_case_id in outputs:
        evaluation = evaluate_racio_epistemic_bilingual_pair_v3(
            bilingual_pair_id=pair.bilingual_pair_id,
            sl_packet=case_by_id[pair.sl_case_id].packet,
            sl_output=outputs[pair.sl_case_id],
            en_packet=case_by_id[pair.en_case_id].packet,
            en_output=outputs[pair.en_case_id],
        )
        return {
            "schema_version": "rei-racio-g3c-v3-pair-result-v1",
            "bilingual_pair_id": pair.bilingual_pair_id,
            "status": "evaluated",
            "sl_case_id": pair.sl_case_id,
            "en_case_id": pair.en_case_id,
            "evaluation": evaluation.model_dump(mode="json"),
        }
    return {
        "schema_version": "rei-racio-g3c-v3-pair-result-v1",
        "bilingual_pair_id": pair.bilingual_pair_id,
        "status": "not_evaluable",
        "sl_case_id": pair.sl_case_id,
        "en_case_id": pair.en_case_id,
        "reason": "one_or_both_validated_outputs_unavailable",
        "available_output_case_ids": sorted(
            case_id
            for case_id in (pair.sl_case_id, pair.en_case_id)
            if case_id in outputs
        ),
    }


def _missing_receipt(kind: str, failure_code: str) -> dict[str, Any]:
    return {
        "schema_version": "rei-racio-g3c-v3-missing-artifact-v1",
        "artifact_kind": kind,
        "reason": "provider_call_failed",
        "failure_code": failure_code,
    }


def execute_g3c_screen(
    *,
    suite: G3CSuite,
    output_dir: Path,
    source_commit: str,
    environ: Mapping[str, str] | None = None,
    inner_transport: OllamaJsonTransport | None = None,
    discover_provider: Callable[
        [OllamaApiClient], OllamaGemma4EpistemicV3Provider
    ]
    | None = None,
    enforce_sealed_output_root: bool = True,
) -> dict[str, Any]:
    target = output_dir.expanduser().resolve()
    if enforce_sealed_output_root and target != SEALED_OUTPUT_ROOT.resolve():
        raise ValueError(
            "G3C execution output root differs from the manifest-sealed path"
        )
    target.mkdir(parents=True, exist_ok=False)
    ledger_dir = target / "attempt_ledger"
    ledger_dir.mkdir()
    profile = _current_frozen_profile()
    _write_new_json(
        ledger_dir / "000_planned.json",
        {
            "schema_version": "rei-racio-g3c-v3-attempt-event-v1",
            "event": "planned_before_provider_discovery",
            "source_commit": source_commit,
            "manifest_sha256": suite.manifest_sha256,
            "case_order": [case.case_id for case in suite.cases],
            "pair_order": [pair.bilingual_pair_id for pair in suite.pairs],
            "sealed_call_spec_hashes": {
                case.case_id: case.call_spec.content_hash() for case in suite.cases
            },
            "planned_call_count": CASE_COUNT,
            "chat_dispatch_count": 0,
            "retry_count": 0,
            "fallback": "none",
            "frozen_profile": profile,
        },
    )

    counting = CountingOllamaTransport(inner_transport or UrllibOllamaTransport())
    client = OllamaApiClient(
        base_url=DEFAULT_OLLAMA_BASE_URL,
        allow_remote=False,
        transport=counting,
    )
    if discover_provider is None:
        active_environ = os.environ if environ is None else environ
        discover_provider = lambda active_client: (
            OllamaGemma4EpistemicV3Provider.discover(
                client=active_client,
                environ=active_environ,
            )
        )
    try:
        provider = discover_provider(client)
    except Exception as exc:
        _write_new_json(
            ledger_dir / "001_global_integrity_failure.json",
            {
                "schema_version": "rei-racio-g3c-v3-attempt-event-v1",
                "event": "provider_discovery_failed",
                "exception_type": type(exc).__name__,
                "chat_dispatch_count": counting.chat_count,
            },
        )
        raise
    if counting.chat_count != 0:
        raise ValueError("G3C provider discovery dispatched an unauthorized chat")

    for case in suite.cases:
        generated = provider.build_call_spec(case.packet)
        if generated != case.call_spec:
            raise ValueError(f"Provider differs from sealed call spec for {case.case_id}")
    if counting.chat_count != 0:
        raise ValueError("G3C call-spec comparison dispatched chat")

    preflight_paths: list[Path] = []
    for case in suite.cases:
        case_dir = target / "cases" / case.case_id
        case_dir.mkdir(parents=True)
        artifacts = {
            "sanitized_packet.json": case.packet,
            "evaluator_gold.json": case.gold,
            "provider_payload.json": case.packet.provider_payload(),
            "call_spec.json": case.call_spec,
        }
        for name, value in artifacts.items():
            artifact_path = case_dir / name
            _write_new_json(artifact_path, value)
            preflight_paths.append(artifact_path)
    pair_registry_path = target / "pair_registry.json"
    _write_new_json(pair_registry_path, suite.pair_registry)
    preflight_paths.append(pair_registry_path)
    artifact_hashes = {
        path.relative_to(target).as_posix(): _file_sha256(path)
        for path in sorted(preflight_paths)
    }
    preflight_base = {
        "schema_version": "rei-racio-g3c-v3-preflight-seal-v1",
        "source_commit": source_commit,
        "manifest_sha256": suite.manifest_sha256,
        "case_order": [case.case_id for case in suite.cases],
        "pair_order": [pair.bilingual_pair_id for pair in suite.pairs],
        "provider_id": provider.identity.provider_id,
        "provider_revision": provider.identity.implementation_revision,
        "frozen_profile": profile,
        "packet_hashes": {
            case.case_id: case.packet.packet_hash for case in suite.cases
        },
        "gold_sha256": {
            case.case_id: sha256_hex(case.gold) for case in suite.cases
        },
        "provider_payload_sha256": {
            case.case_id: hashlib.sha256(
                case.packet.provider_payload_bytes()
            ).hexdigest()
            for case in suite.cases
        },
        "call_spec_hashes": {
            case.case_id: case.call_spec.content_hash() for case in suite.cases
        },
        "preflight_artifact_sha256": artifact_hashes,
        "output_root_creation_mode": "exclusive_create_only",
        "chat_dispatch_count": 0,
        "retry_count": 0,
        "fallback": "none",
    }
    preflight_id = content_id("racio_g3c_v3_preflight", preflight_base)
    preflight_payload = {"preflight_id": preflight_id, **preflight_base}
    preflight_payload["preflight_hash"] = sha256_hex(preflight_payload)
    preflight_path = target / "preflight_seal.json"
    _write_new_json(preflight_path, preflight_payload)
    _write_new_json(
        ledger_dir / "001_preflight_complete.json",
        {
            "schema_version": "rei-racio-g3c-v3-attempt-event-v1",
            "event": "static_call_specs_and_root_frozen_before_first_chat",
            "preflight_id": preflight_id,
            "preflight_hash": preflight_payload["preflight_hash"],
            "chat_dispatch_count": counting.chat_count,
            "transport_endpoint_counts": counting.sanitized_counts(),
        },
    )
    if counting.chat_count != 0:
        raise ValueError("G3C preflight dispatched an unauthorized chat")

    runtime_results: list[dict[str, Any]] = []
    outputs: dict[str, RacioEpistemicInterpretationV3] = {}
    for index, case in enumerate(suite.cases):
        call = case.call_spec
        before_count = counting.chat_count
        before_bytes = case.packet.canonical_json_bytes()
        before_hash = case.packet.content_hash()
        _write_new_json(
            ledger_dir / f"{2 + index * 2:03d}_{case.case_id}_before.json",
            {
                "schema_version": "rei-racio-g3c-v3-attempt-event-v1",
                "event": "before_single_dispatch",
                "case_id": case.case_id,
                "call_id": call.call_id,
                "chat_dispatch_count": before_count,
            },
        )
        started_at = utc_now()
        execution: Gemma4EpistemicV3Execution | None = None
        caught: Exception | None = None
        try:
            execution = provider.execute(
                case.packet,
                call=call,
                clock=SystemExecutionClock(),
            )
        except Exception as exc:
            caught = exc
        finished_at = utc_now()
        dispatch_delta = counting.chat_count - before_count
        failure_code: str | None = None
        failure_payload: dict[str, Any] | None = None
        if caught is not None:
            failure_code, failure_payload = _safe_failure(caught)
        _write_new_json(
            ledger_dir / f"{3 + index * 2:03d}_{case.case_id}_after.json",
            {
                "schema_version": "rei-racio-g3c-v3-attempt-event-v1",
                "event": "after_single_dispatch",
                "case_id": case.case_id,
                "call_id": call.call_id,
                "dispatch_delta": dispatch_delta,
                "chat_dispatch_count": counting.chat_count,
                "provider_status": "succeeded" if caught is None else "failed",
                "failure_code": failure_code,
            },
        )
        if dispatch_delta != 1:
            _write_new_json(
                target / "global_integrity_failure.json",
                {
                    "schema_version": "rei-racio-g3c-v3-global-failure-v1",
                    "case_id": case.case_id,
                    "failure_code": "dispatch_count_invariant_failure",
                    "observed_dispatch_delta": dispatch_delta,
                },
            )
            raise ValueError("A G3C case did not dispatch exactly once")
        unchanged = (
            case.packet.canonical_json_bytes() == before_bytes
            and case.packet.content_hash() == before_hash
        )
        case_dir = target / "cases" / case.case_id
        if execution is not None:
            if execution.call_spec != call:
                raise ValueError("V3 execution returned a different sealed call spec")
            ensure_call_record_contract(call, execution.call_record)
            output = execution.output.validate_against(case.packet)
            outputs[case.case_id] = output
            sidecar = RacioEpistemicStructuralSidecarV3.from_output(output)
            _write_new_json(case_dir / "model_draft.json", execution.draft)
            _write_new_json(case_dir / "structured_output.json", output)
            _write_new_json(case_dir / "structural_sidecar.json", sidecar)
            _write_new_json(
                case_dir / "response_evidence.json", execution.response_evidence
            )
            record = execution.call_record
            provider_status = "succeeded"
            draft = execution.draft
        else:
            assert failure_code is not None and failure_payload is not None
            output = None
            record = _failed_call_record(
                call=call,
                started_at=started_at,
                finished_at=finished_at,
                failure_code=failure_code,
            )
            for name, kind in (
                ("model_draft_missing.json", "validated_model_draft_v3"),
                ("structured_output_missing.json", "canonical_interpretation_v3"),
                ("structural_sidecar_missing.json", "structural_sidecar_v3"),
                ("response_evidence_missing.json", "successful_response_evidence"),
            ):
                _write_new_json(case_dir / name, _missing_receipt(kind, failure_code))
            _write_new_json(
                case_dir / "sanitized_failure.json",
                {
                    "schema_version": "rei-racio-g3c-v3-provider-failure-v1",
                    "case_id": case.case_id,
                    "call_id": call.call_id,
                    **failure_payload,
                },
            )
            provider_status = "failed"
            draft = None
        _write_new_json(case_dir / "provider_call_record.json", record)
        evaluation = evaluate_racio_epistemic_case_v3(
            packet=case.packet,
            gold=case.gold,
            output=output,
            input_packet_unchanged=unchanged,
        )
        uncertainty = build_uncertainty_receipt(case=case, output=output)
        result = _build_case_result(
            case=case,
            draft=draft,
            output=output,
            provider_status=provider_status,
            failure_code=failure_code,
            failure_payload=failure_payload,
            evaluation=evaluation,
            uncertainty=uncertainty,
        )
        _write_new_json(case_dir / "case_evaluation.json", evaluation)
        _write_new_json(case_dir / "uncertainty_receipt.json", uncertainty)
        _write_new_json(case_dir / "case_result.json", result)
        runtime_results.append(result)
        if failure_code in _GLOBAL_FAILURE_CODES:
            _write_new_json(
                target / "global_integrity_failure.json",
                {
                    "schema_version": "rei-racio-g3c-v3-global-failure-v1",
                    "case_id": case.case_id,
                    "failure_code": failure_code,
                    "chat_dispatch_count": counting.chat_count,
                },
            )
            raise ValueError("Global G3C provider integrity failed")

    case_by_id = {case.case_id: case for case in suite.cases}
    pair_results: list[dict[str, Any]] = []
    for pair in suite.pairs:
        pair_result = _build_pair_result(
            pair=pair, case_by_id=case_by_id, outputs=outputs
        )
        _write_new_json(
            target / "bilingual_pairs" / f"{pair.bilingual_pair_id}.json",
            pair_result,
        )
        for case_id in (pair.sl_case_id, pair.en_case_id):
            _write_new_json(
                target / "cases" / case_id / "bilingual_pair_evaluation.json",
                pair_result,
            )
        pair_results.append(pair_result)

    report = build_g3c_report(
        cases=suite.cases,
        case_results=tuple(runtime_results),
        pair_results=tuple(pair_results),
    )
    summary = _build_summary(
        report=report,
        case_results=tuple(runtime_results),
        pair_results=tuple(pair_results),
        chat_dispatch_count=counting.chat_count,
    )
    _write_new_json(target / "report.json", report)
    _write_new_json(target / "summary.json", summary)
    return summary


def _expected_inventory(
    *, suite: G3CSuite, case_results: Mapping[str, Mapping[str, Any]]
) -> set[str]:
    expected = {
        "pair_registry.json",
        "preflight_seal.json",
        "report.json",
        "summary.json",
        "attempt_ledger/000_planned.json",
        "attempt_ledger/001_preflight_complete.json",
    }
    for index, case in enumerate(suite.cases):
        expected.update(
            {
                f"attempt_ledger/{2 + index * 2:03d}_{case.case_id}_before.json",
                f"attempt_ledger/{3 + index * 2:03d}_{case.case_id}_after.json",
            }
        )
        prefix = f"cases/{case.case_id}/"
        expected.update(
            prefix + name
            for name in (
                "sanitized_packet.json",
                "evaluator_gold.json",
                "provider_payload.json",
                "call_spec.json",
                "provider_call_record.json",
                "case_evaluation.json",
                "uncertainty_receipt.json",
                "case_result.json",
                "bilingual_pair_evaluation.json",
            )
        )
        if case_results[case.case_id]["provider_status"] == "succeeded":
            expected.update(
                prefix + name
                for name in (
                    "model_draft.json",
                    "structured_output.json",
                    "structural_sidecar.json",
                    "response_evidence.json",
                )
            )
        else:
            expected.update(
                prefix + name
                for name in (
                    "model_draft_missing.json",
                    "structured_output_missing.json",
                    "structural_sidecar_missing.json",
                    "response_evidence_missing.json",
                    "sanitized_failure.json",
                )
            )
    expected.update(
        f"bilingual_pairs/{pair.bilingual_pair_id}.json" for pair in suite.pairs
    )
    return expected


def cold_validate_g3c_output(
    *,
    suite: G3CSuite,
    output_dir: Path,
    persist_receipt: bool = True,
) -> dict[str, Any]:
    """Cold-validate one complete G3C tree without provider discovery."""

    target = output_dir.expanduser().resolve()
    if (target / "cold_validation.json").exists():
        raise FileExistsError("G3C cold-validation receipt already exists")
    if _read_canonical_json(target / "pair_registry.json") != suite.pair_registry:
        raise ValueError("Persisted G3C pair registry differs from the corpus")
    preflight = _read_canonical_json(target / "preflight_seal.json")
    preflight_hash = preflight.pop("preflight_hash", None)
    if preflight_hash != sha256_hex(preflight):
        raise ValueError("G3C preflight seal hash differs")
    preflight_id = preflight.pop("preflight_id", None)
    if preflight_id != content_id("racio_g3c_v3_preflight", preflight):
        raise ValueError("G3C preflight ID differs")
    if (
        preflight["manifest_sha256"] != suite.manifest_sha256
        or preflight["case_order"] != [case.case_id for case in suite.cases]
        or preflight["pair_order"] != [pair.bilingual_pair_id for pair in suite.pairs]
        or preflight["frozen_profile"] != _current_frozen_profile()
        or preflight["chat_dispatch_count"] != 0
    ):
        raise ValueError("G3C preflight seal differs from the frozen suite")
    for relative, expected_hash in preflight["preflight_artifact_sha256"].items():
        if _file_sha256(target / relative) != expected_hash:
            raise ValueError(f"G3C preflight artifact differs: {relative}")

    outputs: dict[str, RacioEpistemicInterpretationV3] = {}
    raw_case_results: dict[str, dict[str, Any]] = {}
    recomputed_evaluations = 0
    execution_lineages = 0
    for case in suite.cases:
        case_dir = target / "cases" / case.case_id
        packet = RacioEpistemicPacketV3.model_validate_json(
            canonical_json_bytes(
                _read_canonical_json(case_dir / "sanitized_packet.json")
            )
        )
        gold = EpistemicCaseGoldV3.model_validate_json(
            canonical_json_bytes(
                _read_canonical_json(case_dir / "evaluator_gold.json")
            )
        )
        call = ProviderCallSpec.model_validate_json(
            canonical_json_bytes(_read_canonical_json(case_dir / "call_spec.json"))
        )
        if packet != case.packet or gold != case.gold or call != case.call_spec:
            raise ValueError(f"G3C preflight typed artifact differs for {case.case_id}")
        if _read_canonical_json(case_dir / "provider_payload.json") != packet.provider_payload():
            raise ValueError(f"G3C provider payload differs for {case.case_id}")
        result = _read_canonical_json(case_dir / "case_result.json")
        record = ProviderCallRecord.model_validate_json(
            canonical_json_bytes(
                _read_canonical_json(case_dir / "provider_call_record.json")
            )
        )
        ensure_call_record_contract(call, record)
        output: RacioEpistemicInterpretationV3 | None
        draft: RacioEpistemicDraftV3 | None
        failure_payload: Mapping[str, Any] | None
        if result["provider_status"] == "succeeded":
            draft = RacioEpistemicDraftV3.model_validate_json(
                canonical_json_bytes(
                    _read_canonical_json(case_dir / "model_draft.json")
                )
            )
            output = RacioEpistemicInterpretationV3.model_validate_json(
                canonical_json_bytes(
                    _read_canonical_json(case_dir / "structured_output.json")
                )
            )
            sidecar = RacioEpistemicStructuralSidecarV3.model_validate_json(
                canonical_json_bytes(
                    _read_canonical_json(case_dir / "structural_sidecar.json")
                )
            )
            evidence = Gemma4EpistemicV3ResponseEvidence.model_validate_json(
                canonical_json_bytes(
                    _read_canonical_json(case_dir / "response_evidence.json")
                )
            )
            if canonicalize_racio_epistemic_draft_v3(packet, draft) != output:
                raise ValueError(f"G3C canonicalizer replay differs for {case.case_id}")
            if sidecar != RacioEpistemicStructuralSidecarV3.from_output(output):
                raise ValueError(f"G3C sidecar differs for {case.case_id}")
            Gemma4EpistemicV3Execution(
                draft=draft,
                output=output,
                call_spec=call,
                call_record=record,
                response_evidence=evidence,
            )
            output.validate_against(packet)
            outputs[case.case_id] = output
            execution_lineages += 1
            failure_payload = None
        elif result["provider_status"] == "failed":
            draft = None
            output = None
            if (
                record.status != "failed"
                or record.primary_status != "failed"
                or record.output_artifact_ids
                or record.warnings
                != (f"sanitized_failure_code:{result['failure_code']}",)
            ):
                raise ValueError(f"G3C failed record differs for {case.case_id}")
            failure = _read_canonical_json(case_dir / "sanitized_failure.json")
            _validate_sanitized_failure(
                failure=failure, case=case, result=result
            )
            failure_payload = failure
            for name, kind in _MISSING_ARTIFACT_KINDS.items():
                missing = _read_canonical_json(case_dir / name)
                if missing != _missing_receipt(kind, result["failure_code"]):
                    raise ValueError(f"G3C missing receipt differs for {case.case_id}")
        else:
            raise ValueError(f"G3C case status is invalid for {case.case_id}")
        evaluation = evaluate_racio_epistemic_case_v3(
            packet=packet,
            gold=gold,
            output=output,
            input_packet_unchanged=True,
        )
        persisted_evaluation = RacioEpistemicCaseEvaluationV3.model_validate_json(
            canonical_json_bytes(
                _read_canonical_json(case_dir / "case_evaluation.json")
            )
        )
        if evaluation != persisted_evaluation or result["evaluation"] != evaluation.model_dump(
            mode="json"
        ):
            raise ValueError(f"G3C evaluation replay differs for {case.case_id}")
        uncertainty = build_uncertainty_receipt(case=case, output=output)
        if (
            _read_canonical_json(case_dir / "uncertainty_receipt.json") != uncertainty
            or result["uncertainty_receipt"] != uncertainty
        ):
            raise ValueError(f"G3C uncertainty receipt differs for {case.case_id}")
        expected_result = _build_case_result(
            case=case,
            draft=draft,
            output=output,
            provider_status=result["provider_status"],
            failure_code=result["failure_code"],
            failure_payload=failure_payload,
            evaluation=evaluation,
            uncertainty=uncertainty,
        )
        if result != expected_result:
            raise ValueError(f"G3C case result differs for {case.case_id}")
        raw_case_results[case.case_id] = result
        recomputed_evaluations += 1

    pair_results: list[dict[str, Any]] = []
    case_by_id = {case.case_id: case for case in suite.cases}
    recomputed_pairs = 0
    for pair in suite.pairs:
        persisted = _read_canonical_json(
            target / "bilingual_pairs" / f"{pair.bilingual_pair_id}.json"
        )
        expected_pair = _build_pair_result(
            pair=pair, case_by_id=case_by_id, outputs=outputs
        )
        if persisted != expected_pair:
            raise ValueError(f"G3C pair replay differs for {pair.bilingual_pair_id}")
        if persisted["status"] == "evaluated":
            RacioEpistemicBilingualEvaluationV3.model_validate_json(
                canonical_json_bytes(persisted["evaluation"])
            )
            recomputed_pairs += 1
        for case_id in (pair.sl_case_id, pair.en_case_id):
            if _read_canonical_json(
                target / "cases" / case_id / "bilingual_pair_evaluation.json"
            ) != persisted:
                raise ValueError(f"G3C case pair receipt differs for {case_id}")
        pair_results.append(persisted)

    ordered_case_results = tuple(raw_case_results[case.case_id] for case in suite.cases)
    report = build_g3c_report(
        cases=suite.cases,
        case_results=ordered_case_results,
        pair_results=tuple(pair_results),
    )
    if _read_canonical_json(target / "report.json") != report:
        raise ValueError("G3C report differs from cold recomputation")
    summary = _build_summary(
        report=report,
        case_results=ordered_case_results,
        pair_results=tuple(pair_results),
        chat_dispatch_count=CASE_COUNT,
    )
    if _read_canonical_json(target / "summary.json") != summary:
        raise ValueError("G3C summary differs from cold recomputation")

    planned = _read_canonical_json(
        target / "attempt_ledger" / "000_planned.json"
    )
    expected_planned = {
        "schema_version": "rei-racio-g3c-v3-attempt-event-v1",
        "event": "planned_before_provider_discovery",
        "source_commit": preflight["source_commit"],
        "manifest_sha256": suite.manifest_sha256,
        "case_order": [case.case_id for case in suite.cases],
        "pair_order": [pair.bilingual_pair_id for pair in suite.pairs],
        "sealed_call_spec_hashes": {
            case.case_id: case.call_spec.content_hash() for case in suite.cases
        },
        "planned_call_count": CASE_COUNT,
        "chat_dispatch_count": 0,
        "retry_count": 0,
        "fallback": "none",
        "frozen_profile": _current_frozen_profile(),
    }
    if planned != expected_planned:
        raise ValueError("G3C planned attempt ledger differs")
    preflight_event = _read_canonical_json(
        target / "attempt_ledger" / "001_preflight_complete.json"
    )
    if frozenset(preflight_event) != {
        "schema_version",
        "event",
        "preflight_id",
        "preflight_hash",
        "chat_dispatch_count",
        "transport_endpoint_counts",
    } or any(
        (
            preflight_event["schema_version"]
            != "rei-racio-g3c-v3-attempt-event-v1",
            preflight_event["event"]
            != "static_call_specs_and_root_frozen_before_first_chat",
            preflight_event["preflight_id"] != preflight_id,
            preflight_event["preflight_hash"] != preflight_hash,
            preflight_event["chat_dispatch_count"] != 0,
            type(preflight_event["transport_endpoint_counts"]) is not dict,
            preflight_event["transport_endpoint_counts"].get("/api/chat", 0) != 0,
        )
    ):
        raise ValueError("G3C preflight attempt ledger differs")

    for index, case in enumerate(suite.cases):
        before = _read_canonical_json(
            target / "attempt_ledger" / f"{2 + index * 2:03d}_{case.case_id}_before.json"
        )
        after = _read_canonical_json(
            target / "attempt_ledger" / f"{3 + index * 2:03d}_{case.case_id}_after.json"
        )
        result = raw_case_results[case.case_id]
        expected_before = {
            "schema_version": "rei-racio-g3c-v3-attempt-event-v1",
            "event": "before_single_dispatch",
            "case_id": case.case_id,
            "call_id": case.call_spec.call_id,
            "chat_dispatch_count": index,
        }
        expected_after = {
            "schema_version": "rei-racio-g3c-v3-attempt-event-v1",
            "event": "after_single_dispatch",
            "case_id": case.case_id,
            "call_id": case.call_spec.call_id,
            "dispatch_delta": 1,
            "chat_dispatch_count": index + 1,
            "provider_status": result["provider_status"],
            "failure_code": result["failure_code"],
        }
        if before != expected_before or after != expected_after:
            raise ValueError(f"G3C dispatch ledger differs for {case.case_id}")

    expected_inventory = _expected_inventory(
        suite=suite, case_results=raw_case_results
    )
    actual_inventory = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file() and path.name != "cold_validation.json"
    }
    if actual_inventory != expected_inventory:
        raise ValueError("G3C evidence inventory differs from the closed layout")
    digest_rows = [
        {
            "path": relative,
            "sha256": _file_sha256(target / relative),
        }
        for relative in sorted(actual_inventory)
    ]
    for relative in sorted(actual_inventory):
        _assert_no_private_response_content(
            _read_canonical_json(target / relative), label=relative
        )
    receipt = {
        "schema_version": "rei-racio-g3c-v3-cold-validation-v1",
        "status": "verified",
        "source_commit": preflight["source_commit"],
        "model_call_count": 0,
        "retry_count": 0,
        "fallback_count": 0,
        "case_evaluations_recomputed": recomputed_evaluations,
        "bilingual_evaluations_recomputed": recomputed_pairs,
        "bilingual_not_evaluable_count": PAIR_COUNT - recomputed_pairs,
        "provider_execution_lineages_revalidated": execution_lineages,
        "evidence_file_count": len(actual_inventory),
        "evidence_bytes": sum((target / item).stat().st_size for item in actual_inventory),
        "ordered_file_digest_set_sha256": sha256_hex(digest_rows),
        "receipt_excluded_from_evidence_counts": True,
        "thinking_content_persisted": False,
        "raw_response_envelope_persisted": False,
    }
    if persist_receipt:
        _write_new_json(target / "cold_validation.json", receipt)
    return receipt


def model_free_verify(suite: G3CSuite) -> dict[str, Any]:
    return {
        "mode": "model_free_verification",
        "manifest_sha256": suite.manifest_sha256,
        "case_count": len(suite.cases),
        "bilingual_pair_count": len(suite.pairs),
        "static_call_spec_count": len({case.call_spec.call_id for case in suite.cases}),
        "model_call_count": 0,
        "corpus_profile_and_static_calls_verified": True,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--cold-validate", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if (args.execute or args.cold_validate) and args.output_dir is None:
        parser.error("execution and cold validation require --output-dir")
    if not (args.execute or args.cold_validate) and args.output_dir is not None:
        parser.error("--output-dir requires --execute or --cold-validate")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    suite = load_g3c_suite(args.manifest)
    if args.cold_validate:
        result = cold_validate_g3c_output(suite=suite, output_dir=args.output_dir)
    elif args.execute:
        result = execute_g3c_screen(
            suite=suite,
            output_dir=args.output_dir,
            source_commit=_require_committed_suite(suite),
        )
    else:
        result = model_free_verify(suite)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
