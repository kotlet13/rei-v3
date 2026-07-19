"""Run the sealed 16-call Gemma 4 Racio epistemic development screen.

Without ``--execute`` this command performs only model-free corpus and profile
verification.  Execution is intentionally one-shot: all sixteen call specs are
frozen before the first ``/api/chat`` dispatch, and a counting transport proves
that every case receives exactly one dispatch with no retry or fallback.
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

from app.backend.rei.communication.conscious_access import (
    ConsciousAccessObservation,
    ConsciousAccessOption,
)
from app.backend.rei.communication.epistemic_interpreter import (
    MOTIVE_SUBTYPES_BY_FAMILY,
    RacioEpistemicInterpretationV2,
    RacioEpistemicPacketV2,
)
from app.backend.rei.evaluation.racio_epistemic import (
    EpistemicCaseGoldV2,
    evaluate_racio_epistemic_bilingual_pair,
    evaluate_racio_epistemic_case,
)
from app.backend.rei.ids import canonical_json_bytes, sha256_hex, utc_now
from app.backend.rei.models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ensure_call_record_contract,
)
from app.backend.rei.providers import ollama_gemma4_epistemic as gemma_provider
from app.backend.rei.providers.native import SystemExecutionClock
from app.backend.rei.providers.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    OllamaApiClient,
    OllamaJsonTransport,
    UrllibOllamaTransport,
)
from app.backend.rei.providers.ollama_gemma4_epistemic import (
    GEMMA4_EPISTEMIC_INSTRUCTION,
    GEMMA4_EPISTEMIC_KEEP_ALIVE,
    GEMMA4_EPISTEMIC_MODEL,
    GEMMA4_EPISTEMIC_NUM_CTX,
    GEMMA4_EPISTEMIC_NUM_GPU,
    GEMMA4_EPISTEMIC_NUM_PREDICT,
    GEMMA4_EPISTEMIC_PROVIDER_REVISION,
    GEMMA4_EPISTEMIC_SEED,
    GEMMA4_EPISTEMIC_TEMPERATURE,
    GEMMA4_EPISTEMIC_TIMEOUT_SECONDS,
    GEMMA4_EPISTEMIC_TOP_K,
    GEMMA4_EPISTEMIC_TOP_P,
    Gemma4EpistemicExecutionError,
    OllamaGemma4EpistemicProvider,
)


CORPUS_DIR = (
    ROOT
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "gemma4_epistemic_dev_v1"
)
DEFAULT_MANIFEST_PATH = CORPUS_DIR / "manifest.json"
EXPECTED_MANIFEST_SHA256 = (
    "07172858ac94a5e78dc4bf2d49e14030f5ad85021e62c120265e356063f9a6de"
)
EXPECTED_MODEL_DIGEST = (
    "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7"
)
PUBLIC_SCHEMA_VERSION = "rei-racio-gemma4-epistemic-dev-public-record-v1"
GOLD_SCHEMA_VERSION = "rei-racio-gemma4-epistemic-dev-gold-record-v1"
MANIFEST_SCHEMA_VERSION = "rei-racio-gemma4-epistemic-dev-manifest-v1"
SUITE_ID = "rei-racio-gemma4-epistemic-dev-v1"
CASE_COUNT = 16
PAIR_COUNT = 8
CONFIDENCE_TOLERANCE = 0.1
EXECUTION_BRANCH = "codex/racio-gemma4-epistemic-interpreter"
_SCOPED_EXECUTION_PATHS = (
    "scripts/run_gemma4_racio_epistemic_dev.py",
    "app/backend/rei/providers/ollama_gemma4_epistemic.py",
    "app/backend/rei/communication/epistemic_interpreter.py",
    "app/backend/rei/evaluation/racio_epistemic.py",
    "knowledge/canon_v2/semantic_lab_v1/gemma4_epistemic_dev_v1/manifest.json",
    "knowledge/canon_v2/semantic_lab_v1/gemma4_epistemic_dev_v1/public_cases.jsonl",
    "knowledge/canon_v2/semantic_lab_v1/gemma4_epistemic_dev_v1/gold.jsonl",
)

_PUBLIC_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "root_label",
        "source_case_id",
        "source_root_id",
        "bilingual_pair_id",
        "packet_input",
    }
)
_GOLD_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "root_label",
        "source_case_id",
        "source_root_id",
        "bilingual_pair_id",
        "gold",
    }
)
_IDENTITY_KEYS = (
    "case_id",
    "root_label",
    "source_case_id",
    "source_root_id",
    "bilingual_pair_id",
)
_PACKET_INPUT_KEYS = frozenset(
    {
        "source_mind",
        "language",
        "visible_observations",
        "omitted_observation_ids",
        "public_option_scope",
        "channel_quality",
        "uncertainty",
    }
)
_OBSERVATION_KEYS = frozenset(
    {
        "observation_id",
        "signal_name",
        "perception_status",
        "perceived_value_json",
        "provenance",
        "public_artifact_ids",
    }
)
_OPTION_KEYS = frozenset({"option_id", "description"})
_SAFE_PATH_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,199}$")
_GLOBAL_INTEGRITY_FAILURES = frozenset(
    {
        "request_contract_failure",
        "runtime_identity_mismatch",
        "gpu_placement_failure",
    }
)
_FORBIDDEN_AGGREGATE_KEYS = frozenset(
    {
        "aggregate_semantic_pass",
        "aggregate_semantic_score",
        "overall_semantic_pass",
        "overall_semantic_score",
        "quality_gate_pass",
        "semantic_pass",
        "semantic_score",
    }
)


@dataclass(frozen=True, slots=True)
class Gemma4DevCase:
    case_id: str
    root_label: str
    source_case_id: str
    source_root_id: str
    bilingual_pair_id: str
    packet: RacioEpistemicPacketV2
    gold: EpistemicCaseGoldV2


@dataclass(frozen=True, slots=True)
class Gemma4DevSuite:
    manifest_path: Path
    manifest_sha256: str
    manifest: Mapping[str, Any]
    cases: tuple[Gemma4DevCase, ...]


class CountingOllamaTransport:
    """Count endpoint dispatches while retaining neither requests nor responses."""

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
        path = urlsplit(url).path
        self._counts[path] += 1
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


def _json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if type(value) is not dict:
        raise ValueError(f"{label} must be a JSON object")
    return value


def _strict_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if frozenset(value) != expected:
        raise ValueError(f"{label} fields differ from the frozen wrapper contract")


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_bytes().splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"Blank JSONL record at {path}:{line_number}")
        record = _json_object(line, label=f"{path}:{line_number}")
        if canonical_json_bytes(record) != line:
            raise ValueError(f"Non-canonical JSONL record at {path}:{line_number}")
        records.append(record)
    return tuple(records)


def _build_packet(packet_input: Mapping[str, Any]) -> RacioEpistemicPacketV2:
    _strict_keys(packet_input, _PACKET_INPUT_KEYS, "packet_input")
    raw_observations = packet_input["visible_observations"]
    raw_options = packet_input["public_option_scope"]
    if type(raw_observations) is not list or type(raw_options) is not list:
        raise ValueError("Packet observations and options must be JSON arrays")
    observations: list[ConsciousAccessObservation] = []
    for index, raw in enumerate(raw_observations):
        if type(raw) is not dict:
            raise ValueError(f"Observation {index} must be a JSON object")
        allowed_keys = _OBSERVATION_KEYS
        required_keys = allowed_keys - {"public_artifact_ids"}
        if not required_keys.issubset(raw) or not set(raw).issubset(allowed_keys):
            raise ValueError(f"Observation {index} fields differ from the contract")
        perceived = raw["perceived_value_json"]
        if perceived is not None and not isinstance(perceived, str):
            perceived = canonical_json_bytes(perceived).decode("utf-8")
        observations.append(
            ConsciousAccessObservation(
                observation_id=raw["observation_id"],
                signal_name=raw["signal_name"],
                perception_status=raw["perception_status"],
                perceived_value_json=perceived,
                provenance=raw["provenance"],
                public_artifact_ids=tuple(raw.get("public_artifact_ids", ())),
            )
        )
    options: list[ConsciousAccessOption] = []
    for index, raw in enumerate(raw_options):
        if type(raw) is not dict:
            raise ValueError(f"Option {index} must be a JSON object")
        _strict_keys(raw, _OPTION_KEYS, f"option {index}")
        options.append(ConsciousAccessOption(**raw))
    omitted = packet_input["omitted_observation_ids"]
    if type(omitted) is not list:
        raise ValueError("omitted_observation_ids must be a JSON array")
    return RacioEpistemicPacketV2.create(
        source_mind=packet_input["source_mind"],
        language=packet_input["language"],
        visible_observations=tuple(observations),
        omitted_observation_ids=tuple(omitted),
        public_option_scope=tuple(options),
        channel_quality=packet_input["channel_quality"],
        uncertainty=packet_input["uncertainty"],
    )


def _current_frozen_profile() -> dict[str, Any]:
    return {
        "provider_revision": GEMMA4_EPISTEMIC_PROVIDER_REVISION,
        "model": GEMMA4_EPISTEMIC_MODEL,
        "model_digest": EXPECTED_MODEL_DIGEST,
        "instruction_sha256": sha256_hex(GEMMA4_EPISTEMIC_INSTRUCTION),
        "output_schema_sha256": sha256_hex(gemma_provider._output_schema()),
        "contract_sha256": _file_sha256(
            ROOT / "app/backend/rei/communication/epistemic_interpreter.py"
        ),
        "motive_taxonomy_sha256": sha256_hex(
            {
                family: sorted(subtypes)
                for family, subtypes in sorted(MOTIVE_SUBTYPES_BY_FAMILY.items())
            }
        ),
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
        "evaluator_sha256": _file_sha256(
            ROOT / "app/backend/rei/evaluation/racio_epistemic.py"
        ),
        "provider_sha256": _file_sha256(
            ROOT / "app/backend/rei/providers/ollama_gemma4_epistemic.py"
        ),
    }


def _manifest_file_map(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    files = manifest.get("files")
    if type(files) is not list or len(files) != 2:
        raise ValueError("Development manifest must seal exactly two corpus files")
    result: dict[str, Mapping[str, Any]] = {}
    for item in files:
        if type(item) is not dict or frozenset(item) != {
            "path",
            "sha256",
            "case_count",
        }:
            raise ValueError("Development manifest file entry is invalid")
        path = item["path"]
        if path in result or path not in {"public_cases.jsonl", "gold.jsonl"}:
            raise ValueError("Development manifest file order or path is invalid")
        result[path] = item
    if tuple(result) != ("public_cases.jsonl", "gold.jsonl"):
        raise ValueError("Development manifest must order public cases before gold")
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
            "bilingual_confidence_tolerance",
            "files",
            "case_order",
            "root_labels",
            "packet_hashes",
            "provider_payload_sha256",
            "frozen_profile",
        }
    )
    _strict_keys(manifest, expected_keys, "development manifest")
    exact = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "suite_id": SUITE_ID,
        "corpus_version": "2026-07-17",
        "suite_role": "development_screen",
        "sealed_before_model_run": True,
        "post_seal_prompt_tuning_allowed": False,
        "model_generated_gold": False,
        "training_export": False,
        "bilingual_confidence_tolerance": CONFIDENCE_TOLERANCE,
    }
    for key, expected in exact.items():
        actual = manifest[key]
        if actual != expected or type(actual) is not type(expected):
            raise ValueError(f"Development manifest {key} differs from its seal")
    if manifest["counts"] != {
        "cases": CASE_COUNT,
        "roots": PAIR_COUNT,
        "slovenian": PAIR_COUNT,
        "english": PAIR_COUNT,
        "bilingual_pairs": PAIR_COUNT,
    }:
        raise ValueError("Development manifest counts differ from 8 x 2")
    _manifest_file_map(manifest)
    if manifest["frozen_profile"] != _current_frozen_profile():
        raise ValueError("Development manifest differs from the immutable G3 profile")


def _validate_provider_boundary(case: Gemma4DevCase) -> None:
    encoded = case.packet.provider_payload_bytes().decode("utf-8")
    lowered = encoded.casefold()
    identity_values = (
        case.case_id,
        case.root_label,
        case.source_case_id,
        case.source_root_id,
        case.bilingual_pair_id,
    )
    if any(value.casefold() in lowered for value in identity_values):
        raise ValueError(f"Provider payload leaks wrapper identity for {case.case_id}")
    hidden_values = (*case.gold.hidden_provider_tokens, case.gold.profile_id)
    if any(value.casefold() in lowered for value in hidden_values):
        raise ValueError(f"Provider payload leaks evaluator-only data for {case.case_id}")
    gemma_provider._validate_sanitized_packet(case.packet)


def load_development_suite(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    expected_manifest_sha256: str = EXPECTED_MANIFEST_SHA256,
) -> Gemma4DevSuite:
    path = manifest_path.expanduser().resolve()
    payload = path.read_bytes()
    manifest_sha256 = hashlib.sha256(payload).hexdigest()
    if manifest_sha256 != expected_manifest_sha256:
        raise ValueError("Gemma 4 development manifest differs from the pinned SHA-256")
    manifest = _json_object(payload, label=str(path))
    if canonical_json_bytes(manifest) + b"\n" != payload:
        raise ValueError("Gemma 4 development manifest must be canonical JSON")
    _validate_manifest_shape(manifest)
    file_entries = _manifest_file_map(manifest)
    for name, entry in file_entries.items():
        corpus_path = path.parent / name
        corpus_payload = corpus_path.read_bytes()
        if hashlib.sha256(corpus_payload).hexdigest() != entry["sha256"]:
            raise ValueError(f"Gemma 4 development corpus hash differs for {name}")
    public_records = _read_jsonl(path.parent / "public_cases.jsonl")
    gold_records = _read_jsonl(path.parent / "gold.jsonl")
    if len(public_records) != CASE_COUNT or len(gold_records) != CASE_COUNT:
        raise ValueError("Gemma 4 development corpus must contain exactly 16 cases")
    if any(entry["case_count"] != CASE_COUNT for entry in file_entries.values()):
        raise ValueError("Gemma 4 development file counts must both equal 16")

    cases: list[Gemma4DevCase] = []
    for index, (public, gold_record) in enumerate(
        zip(public_records, gold_records, strict=True)
    ):
        _strict_keys(public, _PUBLIC_RECORD_KEYS, f"public record {index}")
        _strict_keys(gold_record, _GOLD_RECORD_KEYS, f"gold record {index}")
        if public["schema_version"] != PUBLIC_SCHEMA_VERSION:
            raise ValueError(f"Public record {index} has the wrong schema")
        if gold_record["schema_version"] != GOLD_SCHEMA_VERSION:
            raise ValueError(f"Gold record {index} has the wrong schema")
        if any(public[key] != gold_record[key] for key in _IDENTITY_KEYS):
            raise ValueError(f"Public/gold identity differs at record {index}")
        for key in _IDENTITY_KEYS:
            if not isinstance(public[key], str) or not public[key].strip():
                raise ValueError(f"Record {index} has an invalid {key}")
        if not _SAFE_PATH_SEGMENT.fullmatch(public["case_id"]):
            raise ValueError(f"Case ID is not safe for artifact paths: {index}")
        if not _SAFE_PATH_SEGMENT.fullmatch(public["bilingual_pair_id"]):
            raise ValueError(f"Pair ID is not safe for artifact paths: {index}")
        packet_input = public["packet_input"]
        if type(packet_input) is not dict:
            raise ValueError(f"Public packet_input {index} must be an object")
        packet = _build_packet(packet_input)
        if type(gold_record["gold"]) is not dict:
            raise ValueError(f"Gold payload {index} must be an object")
        gold = EpistemicCaseGoldV2.model_validate_json(
            canonical_json_bytes(gold_record["gold"])
        )
        if (
            gold.case_id != public["case_id"]
            or gold.bilingual_pair_id != public["bilingual_pair_id"]
        ):
            raise ValueError(f"Gold payload identity differs at record {index}")
        case = Gemma4DevCase(
            case_id=public["case_id"],
            root_label=public["root_label"],
            source_case_id=public["source_case_id"],
            source_root_id=public["source_root_id"],
            bilingual_pair_id=public["bilingual_pair_id"],
            packet=packet,
            gold=gold,
        )
        _validate_provider_boundary(case)
        cases.append(case)

    case_order = tuple(case.case_id for case in cases)
    if manifest["case_order"] != list(case_order) or len(set(case_order)) != CASE_COUNT:
        raise ValueError("Development case order differs from the sealed JSONL order")
    root_labels = tuple(sorted({case.root_label for case in cases}))
    if manifest["root_labels"] != list(root_labels) or len(root_labels) != PAIR_COUNT:
        raise ValueError("Development roots differ from the manifest seal")
    packet_hashes = {case.case_id: case.packet.packet_hash for case in cases}
    if manifest["packet_hashes"] != packet_hashes:
        raise ValueError("Development packet hashes differ from the manifest seal")
    payload_hashes = {
        case.case_id: hashlib.sha256(case.packet.provider_payload_bytes()).hexdigest()
        for case in cases
    }
    if manifest["provider_payload_sha256"] != payload_hashes:
        raise ValueError("Development provider payload hashes differ from the seal")

    pairs: dict[str, list[Gemma4DevCase]] = {}
    for case in cases:
        pairs.setdefault(case.bilingual_pair_id, []).append(case)
    if len(pairs) != PAIR_COUNT:
        raise ValueError("Development suite must contain exactly eight bilingual pairs")
    for pair_id, paired in pairs.items():
        if len(paired) != 2 or {case.packet.language for case in paired} != {"sl", "en"}:
            raise ValueError(f"Bilingual pair {pair_id} must contain one SL and one EN case")
        if len({case.root_label for case in paired}) != 1:
            raise ValueError(f"Bilingual pair {pair_id} crosses semantic roots")
        semantic_gold = {
            json.dumps(
                case.gold.model_dump(
                    mode="json",
                    exclude={
                        "case_id",
                        "bilingual_pair_id",
                        "expected_language",
                        "source_claim_ids",
                        "native_truth_id",
                        "profile_id",
                        "evaluator_only_canary",
                    },
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
            for case in paired
        }
        if len(semantic_gold) != 1:
            raise ValueError(f"Bilingual pair {pair_id} has inconsistent semantic gold")
    return Gemma4DevSuite(
        manifest_path=path,
        manifest_sha256=manifest_sha256,
        manifest=manifest,
        cases=tuple(cases),
    )


def _require_committed_corpus(suite: Gemma4DevSuite) -> str:
    if suite.manifest_path != DEFAULT_MANIFEST_PATH.resolve():
        raise ValueError("Executable G3 screen requires the canonical committed corpus")
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if branch != EXECUTION_BRANCH:
        raise ValueError(f"G3 execution requires branch {EXECUTION_BRANCH}")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *_SCOPED_EXECUTION_PATHS],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        raise ValueError("G3 scoped source files must be committed before execution")
    for cached in (False, True):
        command = ["git", "diff", "--quiet"]
        if cached:
            command.append("--cached")
        command.extend(["HEAD", "--", *_SCOPED_EXECUTION_PATHS])
        if subprocess.run(command, cwd=ROOT, check=False).returncode != 0:
            raise ValueError("G3 scoped source files differ from the committed source")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("G3 source commit is not a full Git SHA")
    return commit


def _write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_json_bytes(value) + b"\n")


def _parameter_values(call: ProviderCallSpec) -> dict[str, Any]:
    return {
        parameter.name: json.loads(parameter.canonical_json_value)
        for parameter in call.parameters
    }


def _verify_call_spec(
    *,
    case: Gemma4DevCase,
    call: ProviderCallSpec,
    provider: OllamaGemma4EpistemicProvider,
) -> None:
    profile = _current_frozen_profile()
    if (
        call.request_id != case.packet.packet_id
        or call.input_artifact_ids != (case.packet.packet_id,)
        or call.provider != provider.identity
        or call.provider.model != profile["model"]
        or call.provider.model_revision != profile["model_digest"]
        or call.seed != profile["seed"]
        or call.timeout_seconds != profile["timeout_seconds"]
        or call.fallback_policy.mode != "none"
    ):
        raise ValueError(f"Call spec identity differs for {case.case_id}")
    revision = call.provider.implementation_revision.split(";", 1)[0]
    if revision != profile["provider_revision"]:
        raise ValueError(f"Provider revision differs for {case.case_id}")
    parameters = _parameter_values(call)
    expected_parameters = {
        "format_schema_sha256": profile["output_schema_sha256"],
        "instruction_sha256": profile["instruction_sha256"],
        "endpoint": profile["endpoint"],
        "keep_alive": profile["keep_alive"],
        "model": profile["model"],
        "model_digest": profile["model_digest"],
        "num_ctx": profile["num_ctx"],
        "num_gpu": profile["num_gpu"],
        "num_predict": profile["num_predict"],
        "raw_request_field_sent": profile["raw"],
        "require_full_gpu": profile["require_full_gpu"],
        "retry_count": profile["retry_count"],
        "stream": profile["stream"],
        "temperature": profile["temperature"],
        "think": profile["think"],
        "top_k": profile["top_k"],
        "top_p": profile["top_p"],
        "packet_hash": case.packet.packet_hash,
        "provider_payload_sha256": hashlib.sha256(
            case.packet.provider_payload_bytes()
        ).hexdigest(),
    }
    if any(parameters.get(key) != value for key, value in expected_parameters.items()):
        raise ValueError(f"Call spec parameters differ for {case.case_id}")


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


def build_uncertainty_comparison(
    *,
    case: Gemma4DevCase,
    output: RacioEpistemicInterpretationV2 | None,
) -> dict[str, Any]:
    report = None if output is None else output.racio_reported_uncertainty
    return {
        "schema_version": "rei-racio-gemma4-uncertainty-comparison-v1",
        "case_id": case.case_id,
        "bilingual_pair_id": case.bilingual_pair_id,
        "structure_status": "not_available" if report is None else "valid",
        "racio_reported_uncertainty": (
            None if report is None else report.model_dump(mode="json")
        ),
        "evaluator_reference": {
            "option_determinacy": case.gold.option_determinacy,
            "motive_support_level": case.gold.motive_support_level,
        },
        "descriptive_comparison": {
            "option_mapping": (
                "provider_output_unavailable"
                if report is None
                else (
                    f"racio_{report.option_mapping}_versus_"
                    f"evaluator_{case.gold.option_determinacy}"
                )
            ),
            "motive_interpretation": (
                "provider_output_unavailable"
                if report is None
                else (
                    f"racio_{report.motive_interpretation}_versus_"
                    f"evaluator_{case.gold.motive_support_level}"
                )
            ),
        },
        "used_as_hard_gate": False,
        "mechanically_repaired": False,
    }


def _validation_boundary(failure_code: str) -> str:
    if failure_code == "structured_output_invalid":
        return "during_json_pydantic_validation"
    if failure_code == "conscious_access_rejected":
        return "after_json_pydantic_validation"
    return "before_json_pydantic_validation"


def _safe_failure(exc: Exception) -> tuple[str, dict[str, Any]]:
    if isinstance(exc, Gemma4EpistemicExecutionError):
        code = exc.failure_code
        diagnostics = dict(exc.sanitized_diagnostics())
    else:
        code = "unexpected_provider_failure"
        diagnostics = {
            "failure_code": code,
            "exception_type": type(exc).__name__,
        }
    return code, {
        "failure_code": code,
        "validation_boundary": _validation_boundary(code),
        "sanitized_diagnostics": diagnostics,
        "rejected_content_persisted": False,
        "thinking_content_persisted": False,
        "raw_response_envelope_persisted": False,
    }


def _bool_counts(values: list[bool]) -> dict[str, int]:
    return {
        "true": sum(value is True for value in values),
        "false": sum(value is False for value in values),
    }


def _value_counts(values: list[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values).items()))


def build_development_report(
    *,
    case_results: tuple[Mapping[str, Any], ...],
    pair_results: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    evaluations = [result["evaluation"] for result in case_results]
    uncertainty = [result["uncertainty_comparison"] for result in case_results]
    evaluated_pairs = [item for item in pair_results if item["status"] == "evaluated"]
    pair_evaluations = [item["evaluation"] for item in evaluated_pairs]
    failure_rows = [
        {
            "case_id": result["case_id"],
            "provider_status": result["provider_status"],
            "failure_code": result["failure_code"],
            "research_observations": result["evaluation"]["research_observations"],
        }
        for result in case_results
        if result["failure_code"] is not None
        or result["evaluation"]["research_observations"]
    ]
    sections: dict[str, Any] = {
        "1. Structural contract": {
            "structural_output_valid": _bool_counts(
                [item["structural_output_valid"] for item in evaluations]
            ),
            "citation_scope_valid": _bool_counts(
                [item["citation_scope_valid"] for item in evaluations]
            ),
            "hard_contract_pass": _bool_counts(
                [item["hard_contract_pass"] for item in evaluations]
            ),
            "input_packet_unchanged": _bool_counts(
                [item["input_packet_unchanged"] for item in evaluations]
            ),
        },
        "2. Action interpretation": {
            "action_support": _value_counts(
                [item["action_support"] for item in evaluations]
            ),
            "action_citation_support": _bool_counts(
                [item["action_citation_support"] for item in evaluations]
            ),
        },
        "3. Option mapping": {
            "option_determinacy": _value_counts(
                [item["option_determinacy"] for item in evaluations]
            ),
            "option_mapping": _value_counts(
                [item["option_mapping"] for item in evaluations]
            ),
            "option_citation_support": _bool_counts(
                [item["option_citation_support"] for item in evaluations]
            ),
        },
        "4. Required abstention": {
            "abstention_quality": _value_counts(
                [item["abstention_quality"] for item in evaluations]
            ),
        },
        "5. Motive hypotheses": {
            "motive_support": _value_counts(
                [item["motive_support"] for item in evaluations]
            ),
            "coverage_by_case": {
                result["case_id"]: {
                    "hypothesis": result["evaluation"]["motive_hypothesis_coverage"],
                    "family": result["evaluation"]["motive_family_coverage"],
                }
                for result in case_results
            },
            "citation_failure_count_by_case": {
                result["case_id"]: result["evaluation"][
                    "motive_citation_failure_count"
                ]
                for result in case_results
            },
        },
        "6. Unsupported overclaims": {
            "count_by_case": {
                result["case_id"]: result["evaluation"][
                    "unsupported_motive_overclaim_count"
                ]
                for result in case_results
            },
            "case_count_with_zero": sum(
                item["unsupported_motive_overclaim_count"] == 0
                for item in evaluations
            ),
            "case_count_with_nonzero": sum(
                item["unsupported_motive_overclaim_count"] > 0
                for item in evaluations
            ),
        },
        "7. Confidence": {
            "action_within_bound": _bool_counts(
                [item["action_confidence_within_bound"] for item in evaluations]
            ),
            "option_within_bound": _bool_counts(
                [item["option_confidence_within_bound"] for item in evaluations]
            ),
            "motives_within_bound": _bool_counts(
                [item["motive_confidences_within_bound"] for item in evaluations]
            ),
            "values_by_case": {
                result["case_id"]: result["confidence_values"]
                for result in case_results
            },
        },
        "8. Racio-reported uncertainty": {
            "used_as_hard_gate": False,
            "mechanically_repaired": False,
            "structure_status": _value_counts(
                [item["structure_status"] for item in uncertainty]
            ),
            "option_mapping_states": _value_counts(
                [
                    item["racio_reported_uncertainty"]["option_mapping"]
                    for item in uncertainty
                    if item["racio_reported_uncertainty"] is not None
                ]
            ),
            "motive_interpretation_states": _value_counts(
                [
                    item["racio_reported_uncertainty"]["motive_interpretation"]
                    for item in uncertainty
                    if item["racio_reported_uncertainty"] is not None
                ]
            ),
            "descriptive_case_comparisons": uncertainty,
            "bilingual_consistency": _bool_counts(
                [item["reported_uncertainty_consistent"] for item in pair_evaluations]
            ),
            "bilingual_not_evaluable": len(pair_results) - len(evaluated_pairs),
        },
        "9. Slovenian-English consistency": {
            "evaluated_pair_count": len(evaluated_pairs),
            "not_evaluable_pair_count": len(pair_results) - len(evaluated_pairs),
            "source_mind_consistent": _bool_counts(
                [item["source_mind_consistent"] for item in pair_evaluations]
            ),
            "action_consistent": _bool_counts(
                [item["action_consistent"] for item in pair_evaluations]
            ),
            "option_consistent": _bool_counts(
                [item["option_consistent"] for item in pair_evaluations]
            ),
            "motive_family_consistent": _bool_counts(
                [item["motive_family_consistent"] for item in pair_evaluations]
            ),
            "motive_subtype_consistent": _bool_counts(
                [item["motive_subtype_consistent"] for item in pair_evaluations]
            ),
            "citation_consistent": _bool_counts(
                [item["citation_consistent"] for item in pair_evaluations]
            ),
            "reported_uncertainty_consistent": _bool_counts(
                [item["reported_uncertainty_consistent"] for item in pair_evaluations]
            ),
            "pair_artifacts": pair_results,
        },
        "10. Individual failures": {
            "provider_failure_codes": _value_counts(
                [
                    result["failure_code"]
                    for result in case_results
                    if result["failure_code"] is not None
                ]
            ),
            "cases": failure_rows,
        },
    }
    return {
        "schema_version": "rei-racio-gemma4-epistemic-dev-report-v1",
        "sections": sections,
    }


def _independent_dimension_counts(report: Mapping[str, Any]) -> dict[str, Any]:
    sections = report["sections"]
    return {
        "structural_contract": sections["1. Structural contract"],
        "action_interpretation": sections["2. Action interpretation"],
        "option_mapping": sections["3. Option mapping"],
        "required_abstention": sections["4. Required abstention"],
        "motive_hypotheses": {
            "motive_support": sections["5. Motive hypotheses"]["motive_support"],
            "citation_failure_presence": {
                "zero": sum(
                    value == 0
                    for value in sections["5. Motive hypotheses"][
                        "citation_failure_count_by_case"
                    ].values()
                ),
                "nonzero": sum(
                    value > 0
                    for value in sections["5. Motive hypotheses"][
                        "citation_failure_count_by_case"
                    ].values()
                ),
            },
        },
        "unsupported_overclaims": {
            key: value
            for key, value in sections["6. Unsupported overclaims"].items()
            if key.startswith("case_count_")
        },
        "confidence": {
            key: value
            for key, value in sections["7. Confidence"].items()
            if key.endswith("within_bound")
        },
        "racio_reported_uncertainty": {
            key: value
            for key, value in sections["8. Racio-reported uncertainty"].items()
            if key
            in {
                "structure_status",
                "option_mapping_states",
                "motive_interpretation_states",
                "bilingual_consistency",
                "bilingual_not_evaluable",
            }
        },
        "slovenian_english_consistency": {
            key: value
            for key, value in sections["9. Slovenian-English consistency"].items()
            if key.endswith("_consistent")
            or key in {"evaluated_pair_count", "not_evaluable_pair_count"}
        },
        "individual_failures": sections["10. Individual failures"][
            "provider_failure_codes"
        ],
    }


def _assert_no_aggregate_semantic_result(value: Any) -> None:
    if isinstance(value, Mapping):
        forbidden = set(value).intersection(_FORBIDDEN_AGGREGATE_KEYS)
        if forbidden:
            raise ValueError("G3 artifacts contain a forbidden aggregate semantic result")
        for item in value.values():
            _assert_no_aggregate_semantic_result(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_aggregate_semantic_result(item)


def execute_development_screen(
    *,
    suite: Gemma4DevSuite,
    output_dir: Path,
    source_commit: str,
    environ: Mapping[str, str] | None = None,
    inner_transport: OllamaJsonTransport | None = None,
    discover_provider: Callable[[OllamaApiClient], OllamaGemma4EpistemicProvider]
    | None = None,
) -> dict[str, Any]:
    target = output_dir.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=False)
    ledger_dir = target / "attempt_ledger"
    ledger_dir.mkdir()
    profile = _current_frozen_profile()
    _write_new_json(
        ledger_dir / "000_planned.json",
        {
            "schema_version": "rei-racio-gemma4-attempt-ledger-event-v1",
            "event": "planned_before_provider_discovery",
            "source_commit": source_commit,
            "manifest_sha256": suite.manifest_sha256,
            "case_order": [case.case_id for case in suite.cases],
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
    active_environ = os.environ if environ is None else environ
    if discover_provider is None:
        discover_provider = lambda active_client: OllamaGemma4EpistemicProvider.discover(
            client=active_client,
            expected_digest=EXPECTED_MODEL_DIGEST,
            environ=active_environ,
        )
    try:
        provider = discover_provider(client)
    except Exception as exc:
        _write_new_json(
            ledger_dir / "001_global_integrity_failure.json",
            {
                "schema_version": "rei-racio-gemma4-attempt-ledger-event-v1",
                "event": "provider_discovery_failed",
                "exception_type": type(exc).__name__,
                "chat_dispatch_count": counting.chat_count,
            },
        )
        raise
    if counting.chat_count != 0:
        raise ValueError("Provider discovery dispatched an unauthorized chat call")

    calls: list[ProviderCallSpec] = []
    for case in suite.cases:
        call = provider.build_call_spec(case.packet)
        _verify_call_spec(case=case, call=call, provider=provider)
        calls.append(call)
    if counting.chat_count != 0 or len(calls) != CASE_COUNT:
        raise ValueError("G3 preflight did not freeze all 16 specs before chat")

    for case, call in zip(suite.cases, calls, strict=True):
        case_dir = target / "cases" / case.case_id
        case_dir.mkdir(parents=True)
        _write_new_json(case_dir / "sanitized_packet.json", case.packet)
        _write_new_json(case_dir / "provider_payload.json", case.packet.provider_payload())
        _write_new_json(case_dir / "call_spec.json", call)
    _write_new_json(
        ledger_dir / "001_preflight_complete.json",
        {
            "schema_version": "rei-racio-gemma4-attempt-ledger-event-v1",
            "event": "all_call_specs_frozen_before_first_chat",
            "provider_id": provider.identity.provider_id,
            "provider_revision": provider.identity.implementation_revision,
            "call_spec_hashes": {
                case.case_id: call.content_hash()
                for case, call in zip(suite.cases, calls, strict=True)
            },
            "chat_dispatch_count": counting.chat_count,
            "transport_endpoint_counts": counting.sanitized_counts(),
        },
    )

    runtime_results: list[dict[str, Any]] = []
    outputs: dict[str, RacioEpistemicInterpretationV2] = {}
    for index, (case, call) in enumerate(zip(suite.cases, calls, strict=True)):
        before_count = counting.chat_count
        before_bytes = case.packet.canonical_json_bytes()
        before_hash = case.packet.content_hash()
        _write_new_json(
            ledger_dir / f"{2 + index * 2:03d}_{case.case_id}_before.json",
            {
                "schema_version": "rei-racio-gemma4-attempt-ledger-event-v1",
                "event": "before_single_dispatch",
                "case_id": case.case_id,
                "call_id": call.call_id,
                "chat_dispatch_count": before_count,
            },
        )
        started_at = utc_now()
        execution = None
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
                "schema_version": "rei-racio-gemma4-attempt-ledger-event-v1",
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
                    "schema_version": "rei-racio-gemma4-global-integrity-failure-v1",
                    "case_id": case.case_id,
                    "failure_code": "dispatch_count_invariant_failure",
                    "observed_dispatch_delta": dispatch_delta,
                },
            )
            raise ValueError("A G3 case did not produce exactly one chat dispatch")

        unchanged = (
            case.packet.canonical_json_bytes() == before_bytes
            and case.packet.content_hash() == before_hash
        )
        case_dir = target / "cases" / case.case_id
        if execution is not None:
            if execution.call_spec != call:
                raise ValueError("Provider execution returned a different call spec")
            ensure_call_record_contract(call, execution.call_record)
            output = execution.output
            output.validate_against(case.packet)
            outputs[case.case_id] = output
            record = execution.call_record
            _write_new_json(case_dir / "structured_output.json", output)
            _write_new_json(case_dir / "response_evidence.json", execution.response_evidence)
            provider_status = "succeeded"
        else:
            assert failure_code is not None and failure_payload is not None
            output = None
            record = _failed_call_record(
                call=call,
                started_at=started_at,
                finished_at=finished_at,
                failure_code=failure_code,
            )
            _write_new_json(
                case_dir / "structured_output_missing.json",
                {
                    "schema_version": "rei-racio-gemma4-missing-artifact-v1",
                    "artifact_kind": "validated_structured_output",
                    "reason": "provider_call_failed",
                    "failure_code": failure_code,
                },
            )
            _write_new_json(
                case_dir / "response_evidence_missing.json",
                {
                    "schema_version": "rei-racio-gemma4-missing-artifact-v1",
                    "artifact_kind": "successful_response_evidence",
                    "reason": "provider_call_failed",
                    "failure_code": failure_code,
                },
            )
            _write_new_json(
                case_dir / "sanitized_failure.json",
                {
                    "schema_version": "rei-racio-gemma4-provider-failure-v1",
                    "case_id": case.case_id,
                    "call_id": call.call_id,
                    **failure_payload,
                },
            )
            provider_status = "failed"
        _write_new_json(case_dir / "provider_call_record.json", record)

        evaluation = evaluate_racio_epistemic_case(
            packet=case.packet,
            gold=case.gold,
            output=output,
            input_packet_unchanged=unchanged,
        )
        uncertainty = build_uncertainty_comparison(case=case, output=output)
        confidence_values = (
            None
            if output is None
            else {
                "action_confidence": output.action_confidence,
                "option_confidence": output.option_confidence,
                "motive_confidences": [
                    {
                        "family": item.family,
                        "subtype": item.subtype,
                        "confidence": item.confidence,
                    }
                    for item in output.motive_hypotheses
                ],
            }
        )
        result = {
            "schema_version": "rei-racio-gemma4-epistemic-dev-case-result-v1",
            "case_id": case.case_id,
            "root_label": case.root_label,
            "bilingual_pair_id": case.bilingual_pair_id,
            "language": case.packet.language,
            "provider_status": provider_status,
            "failure_code": failure_code,
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
            "confidence_values": confidence_values,
            "evaluation": evaluation.model_dump(mode="json"),
            "uncertainty_comparison": uncertainty,
        }
        _assert_no_aggregate_semantic_result(result)
        _write_new_json(case_dir / "case_evaluation.json", evaluation)
        _write_new_json(case_dir / "uncertainty_comparison.json", uncertainty)
        _write_new_json(case_dir / "case_result.json", result)
        runtime_results.append(result)
        if failure_code in _GLOBAL_INTEGRITY_FAILURES:
            _write_new_json(
                target / "global_integrity_failure.json",
                {
                    "schema_version": "rei-racio-gemma4-global-integrity-failure-v1",
                    "case_id": case.case_id,
                    "failure_code": failure_code,
                    "chat_dispatch_count": counting.chat_count,
                },
            )
            raise ValueError("Global G3 provider integrity failed")

    pair_results: list[dict[str, Any]] = []
    pair_ids = tuple(dict.fromkeys(case.bilingual_pair_id for case in suite.cases))
    for pair_id in pair_ids:
        paired = tuple(case for case in suite.cases if case.bilingual_pair_id == pair_id)
        sl_case = next(case for case in paired if case.packet.language == "sl")
        en_case = next(case for case in paired if case.packet.language == "en")
        if sl_case.case_id in outputs and en_case.case_id in outputs:
            evaluation = evaluate_racio_epistemic_bilingual_pair(
                bilingual_pair_id=pair_id,
                sl_packet=sl_case.packet,
                sl_output=outputs[sl_case.case_id],
                en_packet=en_case.packet,
                en_output=outputs[en_case.case_id],
                confidence_tolerance=suite.manifest[
                    "bilingual_confidence_tolerance"
                ],
            )
            pair_result = {
                "schema_version": "rei-racio-gemma4-bilingual-pair-result-v1",
                "bilingual_pair_id": pair_id,
                "status": "evaluated",
                "sl_case_id": sl_case.case_id,
                "en_case_id": en_case.case_id,
                "evaluation": evaluation.model_dump(mode="json"),
            }
        else:
            pair_result = {
                "schema_version": "rei-racio-gemma4-bilingual-pair-result-v1",
                "bilingual_pair_id": pair_id,
                "status": "not_evaluable",
                "sl_case_id": sl_case.case_id,
                "en_case_id": en_case.case_id,
                "reason": "one_or_both_validated_outputs_unavailable",
                "available_output_case_ids": sorted(
                    case.case_id for case in paired if case.case_id in outputs
                ),
            }
        _write_new_json(target / "bilingual_pairs" / f"{pair_id}.json", pair_result)
        for case in paired:
            _write_new_json(
                target
                / "cases"
                / case.case_id
                / "bilingual_pair_evaluation.json",
                pair_result,
            )
        pair_results.append(pair_result)

    report = build_development_report(
        case_results=tuple(runtime_results),
        pair_results=tuple(pair_results),
    )
    _assert_no_aggregate_semantic_result(report)
    technical = {
        "planned_call_count": CASE_COUNT,
        "chat_dispatch_count": counting.chat_count,
        "retry_count": 0,
        "fallback_count": 0,
        "case_result_count": len(runtime_results),
        "provider_success_count": len(outputs),
        "provider_failure_count": CASE_COUNT - len(outputs),
        "bilingual_pair_artifact_count": len(pair_results),
        "evaluated_bilingual_pair_count": sum(
            item["status"] == "evaluated" for item in pair_results
        ),
        "not_evaluable_bilingual_pair_count": sum(
            item["status"] == "not_evaluable" for item in pair_results
        ),
        "all_attempts_accounted": len(runtime_results) == CASE_COUNT,
        "one_dispatch_per_case": counting.chat_count == CASE_COUNT,
        "thinking_content_persisted": False,
        "raw_response_envelope_persisted": False,
    }
    summary = {
        "technical_completeness": technical,
        "independent_dimension_counts": _independent_dimension_counts(report),
    }
    _assert_no_aggregate_semantic_result(summary)
    _write_new_json(target / "report.json", report)
    _write_new_json(target / "summary.json", summary)
    return summary


def _model_free_summary(suite: Gemma4DevSuite) -> dict[str, Any]:
    return {
        "technical_completeness": {
            "mode": "model_free_verification",
            "manifest_sha256": suite.manifest_sha256,
            "case_count": len(suite.cases),
            "bilingual_pair_count": len(
                {case.bilingual_pair_id for case in suite.cases}
            ),
            "model_call_count": 0,
            "corpus_and_profile_verified": True,
        },
        "independent_dimension_counts": {},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.execute and args.output_dir is None:
        parser.error("--execute requires a create-only --output-dir")
    if not args.execute and args.output_dir is not None:
        parser.error("--output-dir is accepted only with --execute")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    suite = load_development_suite(args.manifest)
    if not args.execute:
        print(json.dumps(_model_free_summary(suite), ensure_ascii=False, sort_keys=True))
        return 0
    source_commit = _require_committed_corpus(suite)
    summary = execute_development_screen(
        suite=suite,
        output_dir=args.output_dir,
        source_commit=source_commit,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
