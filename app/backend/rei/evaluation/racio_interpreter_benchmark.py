"""Frozen C3 benchmark for Racio interpretation over public access packets.

The benchmark corpus is physically split between provider-visible packet inputs
and evaluator-only gold.  Loading verifies raw file hashes before joining the
records.  The model/provider never receives a gold record or trusted lineage.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Literal, Self

from pydantic import Field, model_validator

from ..communication.conscious_access import (
    ConsciousAccessArtifact,
    ConsciousAccessObservation,
    ConsciousAccessOption,
    ConsciousAccessPacket,
    InterpreterAblationMode,
)
from ..communication.structured_interpreter import (
    StructuredRacioInterpreterEvidence,
    StructuredRacioInterpreterOutput,
)
from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    ArtifactRelativePath,
    CommitDigest,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderIdentity,
    ensure_call_record_contract,
)


BENCHMARK_ID = "rei-c3-racio-interpreter-benchmark-v1"
BENCHMARK_SCHEMA_VERSION = "rei-c3-racio-interpreter-benchmark-manifest-v1"
HOLDOUT_BENCHMARK_ID = "rei-c3-racio-interpreter-holdout-v1"
HOLDOUT_BENCHMARK_SCHEMA_VERSION = (
    "rei-c3-racio-interpreter-benchmark-manifest-v2"
)
OFFICIAL_MANIFEST_SHA256 = (
    "1cbb5607acc95426673feddb9891567b5a46e5f4988f8cc171a6636069bbab4b"
)
DATA_ROOT = (
    Path(__file__).resolve().parents[4]
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "c3_racio_interpreter"
)
MANIFEST_PATH = DATA_ROOT / "manifest.json"
HOLDOUT_DATA_ROOT = (
    Path(__file__).resolve().parents[4]
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "c3_racio_interpreter_holdout_v1"
)
HOLDOUT_MANIFEST_PATH = HOLDOUT_DATA_ROOT / "manifest.json"
MAX_C3_MANIFEST_BYTES = 256 * 1024
MAX_C3_DATA_FILE_BYTES = 2 * 1024 * 1024

ProviderMode = Literal["deterministic", "ollama"]
C3FailureCode = Literal[
    "transport_failure",
    "request_contract_failure",
    "runtime_identity_mismatch",
    "gpu_placement_failure",
    "generation_contract_failure",
    "structured_output_invalid",
    "conscious_access_rejected",
    "unexpected_provider_failure",
]
AmbiguityClass = Literal["unambiguous", "ambiguous"]
AcceptanceMode = Literal["accepting", "mixed", "conflicted"]
BenchmarkMotiveClass = Literal[
    "broken_scene",
    "attachment",
    "motor_pattern",
    "body_alarm",
    "boundary_alarm",
    "unknown",
]
BenchmarkActionTendency = Literal[
    "attack",
    "seek_attachment",
    "perform",
    "seek_safety",
    "connect",
    "protect",
    "set_boundary",
    "unknown",
]

_PROVIDER_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "source_mind",
        "language",
        "ablation_mode",
        "visible_observations",
        "omitted_observation_ids",
        "degraded_observation_ids",
        "visible_artifacts",
        "visible_artifact_ids",
        "public_option_scope",
        "channel_quality",
        "uncertainty",
        "calibration_constraints",
    }
)
_FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "acceptance_mode",
        "acceptance_state_id",
        "ambiguity_class",
        "audit_id",
        "character_profile",
        "evaluator_only_canary",
        "expected_action_tendency",
        "expected_motive_class",
        "expected_option_id",
        "family_id",
        "bilingual_pair_id",
        "hidden_native_motive",
        "native_conclusion",
        "native_truth_id",
        "packet_hash",
        "packet_id",
        "profile_id",
        "source_manifestation_hash",
        "source_manifestation_id",
        "variant_id",
    }
)


def _is_reparse_stat(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse_flag)


def _reject_reparse_components(path: Path, *, label: str) -> None:
    absolute = path.expanduser().absolute()
    for component in reversed((absolute, *absolute.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"{label} path metadata is unavailable") from exc
        if _is_reparse_stat(metadata):
            raise ValueError(f"{label} path cannot traverse a link or reparse point")


def _read_bounded(path: Path, *, maximum_bytes: int, label: str) -> bytes:
    source = path.expanduser()
    _reject_reparse_components(source, label=label)
    try:
        before = source.lstat()
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    if _is_reparse_stat(before) or not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular non-link file")
    if before.st_size <= 0 or before.st_size > maximum_bytes:
        raise ValueError(f"{label} exceeds its bounded file size")

    descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(source, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(before, opened)
            or opened.st_size != before.st_size
        ):
            raise ValueError(f"{label} changed before it was opened")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            payload = handle.read(maximum_bytes + 1)
        after = source.lstat()
    except OSError as exc:
        raise ValueError(f"{label} could not be read safely") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (
        _is_reparse_stat(after)
        or not stat.S_ISREG(after.st_mode)
        or not os.path.samestat(opened, after)
        or len(payload) != opened.st_size
        or len(payload) > maximum_bytes
    ):
        raise ValueError(f"{label} changed or exceeded bounds while reading")
    return payload


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for nested in value.values():
            keys.update(_walk_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(_walk_keys(nested))
    return keys


class C3PacketInput(FrozenModel):
    source_mind: Literal["E", "I"]
    language: LanguageCode
    ablation_mode: InterpreterAblationMode = "structured_only"
    visible_observations: tuple[ConsciousAccessObservation, ...]
    omitted_observation_ids: tuple[NonEmptyId, ...] = ()
    visible_artifacts: tuple[ConsciousAccessArtifact, ...] = ()
    public_option_scope: tuple[ConsciousAccessOption, ...]
    channel_quality: Score01
    uncertainty: NonEmptyText

    def build_packet(self) -> ConsciousAccessPacket:
        return ConsciousAccessPacket.create(
            source_mind=self.source_mind,
            language=self.language,
            ablation_mode=self.ablation_mode,
            visible_observations=self.visible_observations,
            omitted_observation_ids=self.omitted_observation_ids,
            visible_artifacts=self.visible_artifacts,
            public_option_scope=self.public_option_scope,
            channel_quality=self.channel_quality,
            uncertainty=self.uncertainty,
        )


class C3PublicBenchmarkCase(FrozenModel):
    schema_version: Literal["rei-c3-racio-interpreter-public-case-v1"]
    case_id: NonEmptyId
    root_id: NonEmptyId
    packet_input: C3PacketInput


class C3GoldBenchmarkCase(FrozenModel):
    schema_version: Literal["rei-c3-racio-interpreter-gold-case-v1"]
    case_id: NonEmptyId
    root_id: NonEmptyId
    family_id: NonEmptyId
    variant_id: NonEmptyId
    expected_source_mind: Literal["E", "I"]
    expected_language: LanguageCode
    acceptance_mode: AcceptanceMode
    ambiguity_class: AmbiguityClass
    expected_option_id: NonEmptyId | None
    expected_action_tendency: BenchmarkActionTendency
    expected_motive_class: BenchmarkMotiveClass
    maximum_ambiguous_confidence: Score01 | None
    bilingual_pair_id: NonEmptyId
    native_truth_id: NonEmptyId
    profile_id: NonEmptyId
    evaluator_only_canary: NonEmptyText

    @model_validator(mode="after")
    def validate_expectation(self) -> Self:
        if self.ambiguity_class == "unambiguous":
            if self.expected_option_id is None:
                raise ValueError("An unambiguous C3 case requires an expected option")
            if self.acceptance_mode != "accepting":
                raise ValueError("An unambiguous C3 case must be accepting")
            if self.maximum_ambiguous_confidence is not None:
                raise ValueError(
                    "An unambiguous C3 case cannot define an ambiguity threshold"
                )
        else:
            if self.acceptance_mode == "accepting":
                raise ValueError("An ambiguous C3 case must be mixed or conflicted")
            if self.expected_option_id is not None:
                raise ValueError("An ambiguous C3 case must keep option gold null")
            if self.maximum_ambiguous_confidence is None:
                raise ValueError("An ambiguous C3 case requires a confidence threshold")
            if (
                self.expected_action_tendency != "unknown"
                or self.expected_motive_class != "unknown"
            ):
                raise ValueError("Ambiguous C3 action and motive gold must be unknown")
        return self

    @property
    def hidden_provider_tokens(self) -> tuple[str, ...]:
        return (
            self.native_truth_id,
            self.evaluator_only_canary,
        )


class C3BenchmarkFile(FrozenModel):
    path: NonEmptyText
    sha256: HashDigest
    case_count: int = Field(ge=1)


class C3BenchmarkCounts(FrozenModel):
    cases: Literal[32]
    roots: Literal[8]
    emocio: Literal[16]
    instinkt: Literal[16]
    slovenian: Literal[16]
    english: Literal[16]
    unambiguous: Literal[16]
    ambiguous: Literal[16]
    accepting: Literal[16]
    mixed: Literal[8]
    conflicted: Literal[8]
    bilingual_pairs: Literal[16]


class C3BenchmarkManifest(FrozenModel):
    schema_version: Literal["rei-c3-racio-interpreter-benchmark-manifest-v1"]
    benchmark_id: Literal["rei-c3-racio-interpreter-benchmark-v1"]
    corpus_version: Literal["2026-07-14"]
    gold_origin: Literal["manually_authored"]
    model_generated_gold: Literal[False]
    training_export: Literal[False]
    counts: C3BenchmarkCounts
    ambiguity_confidence_threshold: Score01
    bilingual_confidence_tolerance: Score01
    files: tuple[C3BenchmarkFile, C3BenchmarkFile]
    root_ids: tuple[NonEmptyId, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if tuple(item.path for item in self.files) != (
            "public_cases.jsonl",
            "gold.jsonl",
        ):
            raise ValueError("C3 benchmark must keep public cases and gold separate")
        if any(item.case_count != 32 for item in self.files):
            raise ValueError("Every C3 benchmark file must declare exactly 32 cases")
        if self.root_ids != tuple(sorted(set(self.root_ids))) or len(self.root_ids) != 8:
            raise ValueError("C3 benchmark must declare eight sorted unique roots")
        return self


C3_REGRESSION_FAMILY_IDS: tuple[str, ...] = (
    "sf_attachment_loss_fear",
    "sf_boundary_and_escape",
    "sf_broken_desired_scene_anger",
    "sf_claustrophobia_body_alarm",
    "sf_emocio_delegation_overreach",
    "sf_listen_to_instinct_signal",
    "sf_motor_vs_visual_emocio",
    "sf_words_and_other_channels",
)


class C3SourceGroundingPin(FrozenModel):
    """Frozen link from one holdout root to its reviewed C1 fixture route."""

    root_id: NonEmptyId
    family_id: NonEmptyId
    fixture_path: ArtifactRelativePath
    fixture_sha256: HashDigest
    fixture_review_status: Literal["canon_approved"]
    fixture_variant_count: Literal[8]
    source_mind: Literal["E", "I"]
    source_option_id: NonEmptyId
    source_route_tags: tuple[NonEmptyId, ...] = Field(min_length=1)
    holdout_option_id: Literal["option_001", "option_002"]
    expected_action_tendency: BenchmarkActionTendency
    expected_motive_class: BenchmarkMotiveClass
    mapping_rationale: NonEmptyText

    @model_validator(mode="after")
    def validate_pin(self) -> Self:
        expected_path = (
            f"tests/fixtures/semantic_lab_v1/{self.family_id}.json"
        )
        if self.fixture_path != expected_path:
            raise ValueError("C3 source fixture path must be canonical for its family")
        if len(set(self.source_route_tags)) != len(self.source_route_tags):
            raise ValueError("C3 source route tags must be unique")
        if self.expected_action_tendency == "unknown":
            raise ValueError("C3 source pin action mapping cannot be unknown")
        if self.expected_motive_class == "unknown":
            raise ValueError("C3 source pin motive mapping cannot be unknown")
        return self


class C3BenchmarkManifestV2(FrozenModel):
    """Sealed holdout manifest bound to a pre-run provider protocol commit."""

    schema_version: Literal["rei-c3-racio-interpreter-benchmark-manifest-v2"]
    benchmark_id: Literal["rei-c3-racio-interpreter-holdout-v1"]
    corpus_version: Literal["2026-07-15"]
    suite_role: Literal["untouched_holdout"]
    protocol_freeze_commit: CommitDigest
    instruction_sha256: HashDigest
    output_schema_sha256: HashDigest
    calibration_policy_id: Literal["c3-conscious-access-calibration-v1"]
    gold_origin: Literal["manually_authored"]
    model_generated_gold: Literal[False]
    training_export: Literal[False]
    sealed_before_candidate_run: Literal[True]
    post_seal_prompt_tuning_allowed: Literal[False]
    counts: C3BenchmarkCounts
    ambiguity_confidence_threshold: Score01
    bilingual_confidence_tolerance: Score01
    source_family_ids: tuple[NonEmptyId, ...] = Field(min_length=8, max_length=8)
    source_grounding_pins: tuple[C3SourceGroundingPin, ...] = Field(
        min_length=8,
        max_length=8,
    )
    files: tuple[C3BenchmarkFile, C3BenchmarkFile]
    root_ids: tuple[NonEmptyId, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if len(self.protocol_freeze_commit) != 40:
            raise ValueError("C3 holdout protocol freeze must use a 40-hex commit")
        if tuple(item.path for item in self.files) != (
            "public_cases.jsonl",
            "gold.jsonl",
        ):
            raise ValueError("C3 holdout must keep public cases and gold separate")
        if any(item.case_count != 32 for item in self.files):
            raise ValueError("Every C3 holdout file must declare exactly 32 cases")
        if self.root_ids != tuple(sorted(set(self.root_ids))) or len(self.root_ids) != 8:
            raise ValueError("C3 holdout must declare eight sorted unique roots")
        if self.source_family_ids != tuple(sorted(set(self.source_family_ids))):
            raise ValueError("C3 holdout source families must be sorted and unique")
        if set(self.source_family_ids) & set(C3_REGRESSION_FAMILY_IDS):
            raise ValueError("C3 holdout source families must be absent from regression")
        pins = self.source_grounding_pins
        if pins != tuple(sorted(pins, key=lambda item: item.root_id)):
            raise ValueError("C3 source-grounding pins must be sorted by root ID")
        if len({pin.root_id for pin in pins}) != len(pins):
            raise ValueError("C3 source-grounding pin roots must be unique")
        if len({pin.family_id for pin in pins}) != len(pins):
            raise ValueError("C3 source-grounding pin families must be unique")
        if len({pin.fixture_path for pin in pins}) != len(pins):
            raise ValueError("C3 source-grounding fixture paths must be unique")
        if len({pin.fixture_sha256 for pin in pins}) != len(pins):
            raise ValueError("C3 source-grounding fixture hashes must be unique")
        if tuple(sorted(pin.root_id for pin in pins)) != self.root_ids:
            raise ValueError("C3 source-grounding roots differ from manifest roots")
        if tuple(sorted(pin.family_id for pin in pins)) != self.source_family_ids:
            raise ValueError("C3 source-grounding families differ from manifest families")
        expected_count_links = {
            "roots": len(pins),
            "cases": len(pins) * 4,
            "unambiguous": len(pins) * 2,
            "ambiguous": len(pins) * 2,
            "bilingual_pairs": len(pins) * 2,
        }
        count_payload = self.counts.model_dump(mode="python")
        if any(
            count_payload[field] != expected
            for field, expected in expected_count_links.items()
        ):
            raise ValueError("C3 source-grounding pins differ from manifest counts")
        return self


C3Manifest = C3BenchmarkManifest | C3BenchmarkManifestV2


class C3BenchmarkCase(FrozenModel):
    public: C3PublicBenchmarkCase
    gold: C3GoldBenchmarkCase
    packet: ConsciousAccessPacket

    @model_validator(mode="after")
    def validate_join(self) -> Self:
        if (
            self.public.case_id != self.gold.case_id
            or self.public.root_id != self.gold.root_id
        ):
            raise ValueError("C3 public case and evaluator gold do not share identity")
        if (
            self.packet.source_mind != self.gold.expected_source_mind
            or self.packet.language != self.gold.expected_language
        ):
            raise ValueError("C3 packet source mind or language differs from gold")
        return self


class C3BenchmarkSuite(FrozenModel):
    manifest: C3Manifest
    manifest_file_hash: HashDigest
    cases: tuple[C3BenchmarkCase, ...]


def _read_jsonl(
    payload: bytes,
    *,
    source: Path,
    model_type: type[FrozenModel],
) -> list[FrozenModel]:
    records: list[FrozenModel] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(model_type.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(
                f"Invalid C3 benchmark record {source}:{line_number}"
            ) from exc
    return records


def _validate_suite_counts(
    manifest: C3Manifest,
    cases: tuple[C3BenchmarkCase, ...],
) -> None:
    counts = {
        "cases": len(cases),
        "roots": len({case.public.root_id for case in cases}),
        "emocio": sum(case.packet.source_mind == "E" for case in cases),
        "instinkt": sum(case.packet.source_mind == "I" for case in cases),
        "slovenian": sum(case.packet.language == "sl" for case in cases),
        "english": sum(case.packet.language == "en" for case in cases),
        "unambiguous": sum(
            case.gold.ambiguity_class == "unambiguous" for case in cases
        ),
        "ambiguous": sum(case.gold.ambiguity_class == "ambiguous" for case in cases),
        "accepting": sum(case.gold.acceptance_mode == "accepting" for case in cases),
        "mixed": sum(case.gold.acceptance_mode == "mixed" for case in cases),
        "conflicted": sum(case.gold.acceptance_mode == "conflicted" for case in cases),
        "bilingual_pairs": len({case.gold.bilingual_pair_id for case in cases}),
    }
    if counts != manifest.counts.model_dump(mode="python"):
        raise ValueError(f"C3 benchmark counts differ from manifest: {counts}")
    if {case.public.root_id for case in cases} != set(manifest.root_ids):
        raise ValueError("C3 benchmark root set differs from manifest")
    root_counts = {
        root_id: sum(case.public.root_id == root_id for case in cases)
        for root_id in manifest.root_ids
    }
    if set(root_counts.values()) != {4}:
        raise ValueError("Every C3 semantic root must contribute exactly four cases")
    pair_counts: dict[str, set[str]] = {}
    pair_cases: dict[str, list[C3BenchmarkCase]] = {}
    for case in cases:
        pair_counts.setdefault(case.gold.bilingual_pair_id, set()).add(
            case.packet.language
        )
        pair_cases.setdefault(case.gold.bilingual_pair_id, []).append(case)
        if (
            case.gold.ambiguity_class == "ambiguous"
            and case.gold.maximum_ambiguous_confidence
            != manifest.ambiguity_confidence_threshold
        ):
            raise ValueError("C3 ambiguity thresholds must match the manifest")
    if any(languages != {"sl", "en"} for languages in pair_counts.values()):
        raise ValueError("Every C3 bilingual pair requires one SL and one EN case")
    for paired in pair_cases.values():
        signatures = {
            (
                item.public.root_id,
                item.gold.family_id,
                item.gold.expected_source_mind,
                item.gold.acceptance_mode,
                item.gold.ambiguity_class,
                item.gold.expected_option_id,
                item.gold.expected_action_tendency,
                item.gold.expected_motive_class,
                item.gold.maximum_ambiguous_confidence,
            )
            for item in paired
        }
        if len(paired) != 2 or len(signatures) != 1:
            raise ValueError("C3 bilingual pair gold must be semantically identical")

    unique_gold_fields = {
        "variant_id": [case.gold.variant_id for case in cases],
        "native_truth_id": [case.gold.native_truth_id for case in cases],
        "profile_id": [case.gold.profile_id for case in cases],
        "evaluator_only_canary": [
            case.gold.evaluator_only_canary for case in cases
        ],
    }
    for field_name, values in unique_gold_fields.items():
        if len(set(values)) != len(values):
            raise ValueError(f"C3 gold {field_name} values must be unique")
    if isinstance(manifest, C3BenchmarkManifestV2):
        if {case.gold.family_id for case in cases} != set(manifest.source_family_ids):
            raise ValueError("C3 holdout gold families differ from its source-family pin")
        pins_by_root = {
            pin.root_id: pin for pin in manifest.source_grounding_pins
        }
        root_families = {
            root_id: {
                case.gold.family_id
                for case in cases
                if case.public.root_id == root_id
            }
            for root_id in manifest.root_ids
        }
        if any(len(families) != 1 for families in root_families.values()) or {
            next(iter(families)) for families in root_families.values()
        } != set(manifest.source_family_ids):
            raise ValueError("C3 holdout roots and source families must be bijective")
        for root_id in manifest.root_ids:
            rooted = tuple(
                case for case in cases if case.public.root_id == root_id
            )
            pin = pins_by_root[root_id]
            if {case.gold.family_id for case in rooted} != {pin.family_id}:
                raise ValueError(
                    "C3 holdout root family differs from source-grounding pin"
                )
            if {case.gold.expected_source_mind for case in rooted} != {
                pin.source_mind
            }:
                raise ValueError(
                    "C3 holdout root mind differs from source-grounding pin"
                )
            ambiguity_counts = {
                ambiguity: sum(
                    case.gold.ambiguity_class == ambiguity for case in rooted
                )
                for ambiguity in ("unambiguous", "ambiguous")
            }
            if ambiguity_counts != {"unambiguous": 2, "ambiguous": 2}:
                raise ValueError(
                    "Every C3 holdout root needs one bilingual clear/ambiguous pair"
                )
            unambiguous = tuple(
                case
                for case in rooted
                if case.gold.ambiguity_class == "unambiguous"
            )
            mapped_gold = {
                (
                    case.gold.expected_option_id,
                    case.gold.expected_action_tendency,
                    case.gold.expected_motive_class,
                )
                for case in unambiguous
            }
            if mapped_gold != {
                (
                    pin.holdout_option_id,
                    pin.expected_action_tendency,
                    pin.expected_motive_class,
                )
            }:
                raise ValueError(
                    "C3 holdout gold differs from source-grounding mapping"
                )
        correct_option_counts = {
            option_id: sum(
                case.gold.ambiguity_class == "unambiguous"
                and case.gold.expected_option_id == option_id
                for case in cases
            )
            for option_id in ("option_001", "option_002")
        }
        if correct_option_counts != {"option_001": 8, "option_002": 8}:
            raise ValueError("C3 holdout correct options must be balanced 8/8")
        represented_actions = {
            case.gold.expected_action_tendency
            for case in cases
            if case.gold.ambiguity_class == "unambiguous"
        }
        if represented_actions != {
            "connect",
            "perform",
            "protect",
            "seek_safety",
            "set_boundary",
        }:
            raise ValueError("C3 holdout action coverage differs from its protocol")
        represented_motives = {
            case.gold.expected_motive_class
            for case in cases
            if case.gold.ambiguity_class == "unambiguous"
        }
        if represented_motives != {
            "body_alarm",
            "boundary_alarm",
            "broken_scene",
            "motor_pattern",
        }:
            raise ValueError("C3 holdout motive coverage differs from its protocol")


def _validate_provider_boundary(
    case: C3BenchmarkCase,
    *,
    forbidden_tokens: tuple[str, ...],
) -> None:
    payload = case.packet.provider_payload()
    if set(payload) != _PROVIDER_PAYLOAD_KEYS:
        raise ValueError("C3 provider payload differs from its explicit allowlist")
    leaked_keys = _walk_keys(payload) & _FORBIDDEN_PROVIDER_KEYS
    if leaked_keys:
        raise ValueError(f"C3 provider payload contains forbidden keys: {leaked_keys}")
    encoded = case.packet.provider_payload_bytes().decode("utf-8")
    if any(token in encoded for token in forbidden_tokens):
        raise ValueError("C3 provider payload contains evaluator-only lineage")


def load_c3_racio_interpreter_benchmark(
    manifest_path: str | Path = MANIFEST_PATH,
) -> C3BenchmarkSuite:
    manifest_source = Path(manifest_path).expanduser()
    manifest_payload = _read_bounded(
        manifest_source,
        maximum_bytes=MAX_C3_MANIFEST_BYTES,
        label="C3 benchmark manifest",
    )
    try:
        manifest_object = json.loads(manifest_payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid C3 benchmark manifest JSON") from exc
    if not isinstance(manifest_object, dict):
        raise ValueError("C3 benchmark manifest must contain one object")
    schema_version = manifest_object.get("schema_version")
    if schema_version == BENCHMARK_SCHEMA_VERSION:
        manifest: C3Manifest = C3BenchmarkManifest.model_validate_json(
            manifest_payload
        )
    elif schema_version == HOLDOUT_BENCHMARK_SCHEMA_VERSION:
        manifest = C3BenchmarkManifestV2.model_validate_json(manifest_payload)
    else:
        raise ValueError("Unsupported C3 benchmark manifest schema")
    data_root = manifest_source.absolute().parent
    declared_files = {item.path: item for item in manifest.files}
    file_payloads: dict[str, bytes] = {}
    for relative_path, declared in declared_files.items():
        source = data_root / relative_path
        if source.absolute().parent != data_root:
            raise ValueError("C3 benchmark files must stay directly below data root")
        payload = _read_bounded(
            source,
            maximum_bytes=MAX_C3_DATA_FILE_BYTES,
            label=f"C3 benchmark file {relative_path}",
        )
        if hashlib.sha256(payload).hexdigest() != declared.sha256:
            raise ValueError(f"C3 benchmark file hash mismatch: {relative_path}")
        file_payloads[relative_path] = payload

    public_records = _read_jsonl(
        file_payloads["public_cases.jsonl"],
        source=data_root / "public_cases.jsonl",
        model_type=C3PublicBenchmarkCase,
    )
    gold_records = _read_jsonl(
        file_payloads["gold.jsonl"],
        source=data_root / "gold.jsonl",
        model_type=C3GoldBenchmarkCase,
    )
    public_by_id = {record.case_id: record for record in public_records}
    gold_by_id = {record.case_id: record for record in gold_records}
    if len(public_by_id) != len(public_records) or len(gold_by_id) != len(gold_records):
        raise ValueError("C3 benchmark case IDs must be unique")
    if set(public_by_id) != set(gold_by_id):
        raise ValueError("C3 public cases and gold must have identical case IDs")
    cases = tuple(
        C3BenchmarkCase(
            public=public_by_id[case_id],
            gold=gold_by_id[case_id],
            packet=public_by_id[case_id].packet_input.build_packet(),
        )
        for case_id in sorted(public_by_id)
    )
    _validate_suite_counts(manifest, cases)
    all_hidden_tokens = tuple(
        token
        for case in cases
        for token in (
            *case.gold.hidden_provider_tokens,
            case.gold.profile_id,
            case.public.case_id,
            case.public.root_id,
            case.gold.family_id,
            case.gold.variant_id,
            case.gold.bilingual_pair_id,
        )
    )
    for case in cases:
        _validate_provider_boundary(case, forbidden_tokens=all_hidden_tokens)
    return C3BenchmarkSuite(
        manifest=manifest,
        manifest_file_hash=hashlib.sha256(manifest_payload).hexdigest(),
        cases=cases,
    )


class C3ExecutionProvenance(FrozenModel):
    provider_identity: ProviderIdentity
    provider_id: NonEmptyId
    provider_uses_model: bool
    model_id: NonEmptyText | None = None
    model_digest: HashDigest | None = None
    call_id: NonEmptyId
    call_spec: ProviderCallSpec
    call_spec_hash: HashDigest
    call_record: ProviderCallRecord | None = None
    call_record_hash: HashDigest | None = None
    response_evidence_id: NonEmptyId | None = None
    response_evidence_hash: HashDigest | None = None
    response_evidence_json: NonEmptyText | None = None
    request_payload_hash: HashDigest | None = None
    # Compatibility key: new executions store a stable C3FailureCode here.
    # Historical successful artifacts already serialize this key as null.
    execution_error_type: NonEmptyId | None = None

    @model_validator(mode="after")
    def validate_model_identity(self) -> Self:
        if self.provider_identity.provider_id != self.provider_id:
            raise ValueError("C3 provenance provider identity differs from provider ID")
        if self.call_spec.provider != self.provider_identity:
            raise ValueError("C3 provenance call spec uses another provider")
        if (
            self.call_spec.call_id != self.call_id
            or self.call_spec.content_hash() != self.call_spec_hash
        ):
            raise ValueError("C3 provenance call spec identity/hash differs")
        if self.provider_uses_model != self.provider_identity.uses_model:
            raise ValueError("C3 provenance model flag differs from provider identity")
        if (
            self.model_id != self.provider_identity.model
            or self.model_digest != self.provider_identity.model_revision
        ):
            raise ValueError("C3 provenance model identity differs from provider")
        if self.provider_uses_model != (
            self.model_id is not None and self.model_digest is not None
        ):
            raise ValueError("C3 provenance model identity is incomplete")
        if (self.response_evidence_id is None) != (
            self.response_evidence_hash is None
        ):
            raise ValueError("C3 response evidence ID/hash must appear together")
        if (self.response_evidence_id is None) != (
            self.response_evidence_json is None
        ):
            raise ValueError("C3 response evidence JSON must accompany its ID/hash")
        if (self.call_record is None) != (self.call_record_hash is None):
            raise ValueError("C3 call record and hash must appear together")
        if self.call_record is not None:
            if self.call_record.content_hash() != self.call_record_hash:
                raise ValueError("C3 provenance call record hash differs")
            ensure_call_record_contract(self.call_spec, self.call_record)
        typed_evidence: FrozenArtifactModel | None = None
        if self.response_evidence_json is not None:
            decoded = json.loads(self.response_evidence_json)
            if canonical_json_bytes(decoded).decode("utf-8") != self.response_evidence_json:
                raise ValueError("C3 response evidence JSON must be canonical")
            if sha256_hex(decoded) != self.response_evidence_hash:
                raise ValueError("C3 response evidence JSON differs from its hash")
            if not isinstance(decoded, dict):
                raise ValueError("C3 response evidence must contain one object")
            schema_version = decoded.get("schema_version")
            try:
                if schema_version == (
                    "rei-structured-racio-interpreter-evidence-v1"
                ):
                    typed_evidence = StructuredRacioInterpreterEvidence.model_validate_json(
                        self.response_evidence_json
                    )
                elif schema_version == (
                    "rei-ollama-structured-racio-interpreter-response-v1"
                ):
                    from ..providers.ollama_interpreter import (
                        OllamaStructuredRacioInterpreterResponseEvidence,
                    )

                    typed_evidence = (
                        OllamaStructuredRacioInterpreterResponseEvidence.model_validate_json(
                            self.response_evidence_json
                        )
                    )
                else:
                    raise ValueError("Unsupported C3 response evidence schema")
            except ValueError as exc:
                raise ValueError("C3 response evidence is not a valid typed artifact") from exc
            if (
                getattr(typed_evidence, "result_id", None)
                != self.response_evidence_id
                or typed_evidence.content_hash() != self.response_evidence_hash
            ):
                raise ValueError(
                    "C3 response evidence identity/hash differs from embedded artifact"
                )
            if (
                getattr(typed_evidence, "packet_id", None)
                != self.call_spec.request_id
                or getattr(typed_evidence, "call_id", None) != self.call_id
                or getattr(typed_evidence, "call_spec_hash", None)
                != self.call_spec_hash
                or getattr(typed_evidence, "provider_id", None) != self.provider_id
            ):
                raise ValueError("C3 response evidence differs from provider call")
            if isinstance(typed_evidence, StructuredRacioInterpreterEvidence):
                if self.provider_uses_model or self.request_payload_hash is not None:
                    raise ValueError(
                        "Deterministic C3 evidence cannot claim model request payload"
                    )
            else:
                parameter_values = {
                    parameter.name: json.loads(parameter.canonical_json_value)
                    for parameter in self.call_spec.parameters
                }
                requested_num_ctx = parameter_values.get("num_ctx")
                requested_num_gpu = parameter_values.get("num_gpu")
                require_full_gpu = parameter_values.get("require_full_gpu")
                if (
                    not self.provider_uses_model
                    or getattr(typed_evidence, "model", None) != self.model_id
                    or getattr(typed_evidence, "model_revision", None)
                    != self.model_digest
                    or getattr(typed_evidence, "request_payload_hash", None)
                    != self.request_payload_hash
                ):
                    raise ValueError(
                        "Ollama C3 response evidence differs from model request"
                    )
                if (
                    not isinstance(requested_num_ctx, int)
                    or isinstance(requested_num_ctx, bool)
                    or requested_num_ctx < 1
                    or not isinstance(requested_num_gpu, int)
                    or isinstance(requested_num_gpu, bool)
                    or requested_num_gpu < 0
                    or not isinstance(require_full_gpu, bool)
                    or getattr(typed_evidence, "requested_num_ctx", None)
                    != requested_num_ctx
                    or getattr(typed_evidence, "requested_num_gpu", None)
                    != requested_num_gpu
                    or getattr(typed_evidence, "active_context_length", None)
                    != requested_num_ctx
                ):
                    raise ValueError(
                        "Ollama C3 placement evidence differs from call parameters"
                    )
                if require_full_gpu and (
                    getattr(typed_evidence, "active_size_vram_bytes", None)
                    != getattr(typed_evidence, "active_size_bytes", None)
                    or getattr(typed_evidence, "active_gpu_percent_rounded", None)
                    != 100
                ):
                    raise ValueError(
                        "Ollama C3 evidence does not prove required full-GPU placement"
                    )
        elif self.request_payload_hash is not None:
            raise ValueError("C3 request payload hash requires response evidence")
        if self.execution_error_type is None:
            if self.call_record is None or self.response_evidence_id is None:
                raise ValueError(
                    "A successful C3 execution requires record and response evidence"
                )
            if self.call_record.status != "succeeded" or (
                self.call_record.output_artifact_ids
                != (self.response_evidence_id,)
            ):
                raise ValueError("C3 response evidence must close the successful call")
        elif self.call_record is not None or self.response_evidence_id is not None:
            raise ValueError("A raised C3 execution cannot claim completed evidence")
        return self


def build_execution_provenance(
    *,
    identity: ProviderIdentity,
    call: ProviderCallSpec,
    call_record: ProviderCallRecord | None,
    response_evidence: FrozenArtifactModel | None,
    execution_failure_code: C3FailureCode | None = None,
) -> C3ExecutionProvenance:
    evidence_id = None
    evidence_hash = None
    evidence_json = None
    request_payload_hash = None
    if response_evidence is not None:
        evidence_id = getattr(response_evidence, "result_id", None)
        if not isinstance(evidence_id, str):
            raise ValueError("C3 provider response evidence requires a result_id")
        evidence_hash = response_evidence.content_hash()
        evidence_json = response_evidence.canonical_json_bytes().decode("utf-8")
        request_payload_hash = getattr(response_evidence, "request_payload_hash", None)
    return C3ExecutionProvenance(
        provider_identity=identity,
        provider_id=identity.provider_id,
        provider_uses_model=identity.uses_model,
        model_id=identity.model,
        model_digest=identity.model_revision,
        call_id=call.call_id,
        call_spec=call,
        call_spec_hash=call.content_hash(),
        call_record=call_record,
        call_record_hash=(call_record.content_hash() if call_record is not None else None),
        response_evidence_id=evidence_id,
        response_evidence_hash=evidence_hash,
        response_evidence_json=evidence_json,
        request_payload_hash=request_payload_hash,
        execution_error_type=execution_failure_code,
    )


class C3FailureEvidence(FrozenArtifactModel):
    """Sanitized content-addressed evidence for one failed provider attempt."""

    schema_version: Literal["rei-c3-racio-interpreter-failure-v1"] = (
        "rei-c3-racio-interpreter-failure-v1"
    )
    failure_id: NonEmptyId
    run_id: NonEmptyId
    benchmark_id: Literal[
        "rei-c3-racio-interpreter-benchmark-v1",
        "rei-c3-racio-interpreter-holdout-v1",
    ]
    case_id: NonEmptyId
    packet_id: NonEmptyId
    packet_hash: HashDigest
    call_id: NonEmptyId
    call_spec_hash: HashDigest
    provider_id: NonEmptyId
    provider_revision: NonEmptyText
    model_id: NonEmptyText | None = None
    model_digest: HashDigest | None = None
    failure_code: C3FailureCode
    provider_payload_sha256: HashDigest
    rejected_response_sha256: HashDigest | None = None
    rejected_response_byte_count: int | None = Field(default=None, ge=0)
    retry_attempted: Literal[False] = False
    fallback_used: Literal[False] = False
    failure_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        benchmark_id: str,
        case_id: str,
        packet: ConsciousAccessPacket,
        call: ProviderCallSpec,
        failure_code: C3FailureCode,
        rejected_response_sha256: str | None = None,
        rejected_response_byte_count: int | None = None,
    ) -> "C3FailureEvidence":
        base = {
            "schema_version": "rei-c3-racio-interpreter-failure-v1",
            "run_id": run_id,
            "benchmark_id": benchmark_id,
            "case_id": case_id,
            "packet_id": packet.packet_id,
            "packet_hash": packet.content_hash(),
            "call_id": call.call_id,
            "call_spec_hash": call.content_hash(),
            "provider_id": call.provider.provider_id,
            "provider_revision": call.provider.implementation_revision,
            "model_id": call.provider.model,
            "model_digest": call.provider.model_revision,
            "failure_code": failure_code,
            "provider_payload_sha256": sha256_hex(packet.provider_payload()),
            "rejected_response_sha256": rejected_response_sha256,
            "rejected_response_byte_count": rejected_response_byte_count,
            "retry_attempted": False,
            "fallback_used": False,
        }
        failure_id = content_id("c3_interpreter_failure", base)
        payload = {"failure_id": failure_id, **base}
        return cls(**payload, failure_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        if (self.model_id is None) != (self.model_digest is None):
            raise ValueError("C3 failure model identity must appear together")
        if (self.rejected_response_sha256 is None) != (
            self.rejected_response_byte_count is None
        ):
            raise ValueError("C3 rejected-response hash and size must appear together")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"failure_id", "failure_hash"},
        )
        if self.failure_id != content_id("c3_interpreter_failure", base):
            raise ValueError("C3 failure ID differs from sanitized content")
        payload = {"failure_id": self.failure_id, **base}
        if self.failure_hash != sha256_hex(payload):
            raise ValueError("C3 failure hash differs from sanitized content")
        return self


class C3BenchmarkCaseResult(FrozenArtifactModel):
    schema_version: Literal["rei-c3-racio-interpreter-case-result-v1"] = (
        "rei-c3-racio-interpreter-case-result-v1"
    )
    result_id: NonEmptyId
    case_id: NonEmptyId
    root_id: NonEmptyId
    bilingual_pair_id: NonEmptyId
    provider_mode: ProviderMode
    source_mind: Literal["E", "I"]
    language: LanguageCode
    ambiguity_class: AmbiguityClass
    packet_id: NonEmptyId
    packet_hash: HashDigest
    provider_payload_hash: HashDigest
    output: StructuredRacioInterpreterOutput | None
    structured_output_valid: bool
    citation_scope_valid: bool
    hidden_truth_leakage_count: int = Field(ge=0)
    profile_leakage_count: int = Field(ge=0)
    input_packet_unchanged: bool
    provenance_scope_valid: bool
    option_exact: bool
    action_exact: bool
    motive_exact: bool
    ambiguity_gate_pass: bool
    passed: bool
    issues: tuple[NonEmptyId, ...]
    provenance: C3ExecutionProvenance
    result_hash: HashDigest

    @model_validator(mode="after")
    def validate_result_hash(self) -> Self:
        id_payload = self.model_dump(
            mode="python", round_trip=True, exclude={"result_id", "result_hash"}
        )
        if self.result_id != content_id("c3_interpreter_eval", id_payload):
            raise ValueError("C3 benchmark result ID differs from content")
        if self.result_hash != self.content_hash(
            exclude_fields=frozenset({"result_hash"})
        ):
            raise ValueError("C3 benchmark result hash differs from content")
        return self


def evaluate_c3_benchmark_case(
    *,
    case: C3BenchmarkCase,
    provider_mode: ProviderMode,
    output: StructuredRacioInterpreterOutput | None,
    provenance: C3ExecutionProvenance,
    input_packet_unchanged: bool,
) -> C3BenchmarkCaseResult:
    packet = case.packet
    gold = case.gold
    structured_valid = output is not None and provenance.execution_error_type is None
    citation_valid = False
    if structured_valid and output is not None:
        try:
            output.validate_against(packet)
        except ValueError:
            citation_valid = False
        else:
            citation_valid = True

    encoded = packet.provider_payload_bytes().decode("utf-8")
    hidden_leaks = sum(token in encoded for token in gold.hidden_provider_tokens)
    profile_leaks = int(gold.profile_id in encoded)
    evidence_payload = (
        json.loads(provenance.response_evidence_json)
        if provenance.response_evidence_json is not None
        else None
    )
    evidence_output_bound = evidence_payload is None
    if evidence_payload is not None and output is not None:
        if evidence_payload.get("schema_version") == (
            "rei-ollama-structured-racio-interpreter-response-v1"
        ):
            evidence_output_bound = (
                evidence_payload.get("structured_output_hash") == sha256_hex(output)
                and evidence_payload.get("cited_observation_ids")
                == list(output.cited_observation_ids)
            )
        elif evidence_payload.get("schema_version") == (
            "rei-structured-racio-interpreter-evidence-v1"
        ):
            typed_evidence = StructuredRacioInterpreterEvidence.model_validate_json(
                provenance.response_evidence_json
            )
            evidence_output_bound = typed_evidence.output == output
    expected_model_usage = provider_mode == "ollama"
    provenance_scope_valid = (
        provenance.call_spec.request_id == packet.packet_id
        and provenance.call_spec.input_artifact_ids == (packet.packet_id,)
        and provenance.call_spec.fallback_policy.mode == "none"
        and provenance.provider_identity.kind == "text_reasoner"
        and provenance.provider_uses_model == expected_model_usage
        and evidence_output_bound
        and (
            evidence_payload is None
            or (
                evidence_payload.get("packet_id") == packet.packet_id
                and evidence_payload.get("packet_hash") == packet.content_hash()
                and evidence_payload.get("call_id") == provenance.call_id
                and evidence_payload.get("call_spec_hash")
                == provenance.call_spec_hash
                and evidence_payload.get("provider_id") == provenance.provider_id
            )
        )
    )
    option_exact = output is not None and output.inferred_option_id == gold.expected_option_id
    action_exact = (
        output is not None
        and output.inferred_action_tendency == gold.expected_action_tendency
    )
    motive_exact = (
        output is not None and output.inferred_motive_class == gold.expected_motive_class
    )
    if gold.ambiguity_class == "ambiguous":
        assert gold.maximum_ambiguous_confidence is not None
        ambiguity_gate = output is not None and (
            option_exact
            and action_exact
            and motive_exact
            and output.confidence <= gold.maximum_ambiguous_confidence
        )
        semantic_gate = ambiguity_gate
    else:
        ambiguity_gate = True
        semantic_gate = option_exact and action_exact and motive_exact

    structural_gate = (
        structured_valid
        and citation_valid
        and hidden_leaks == 0
        and profile_leaks == 0
        and input_packet_unchanged
        and provenance_scope_valid
    )
    passed = structural_gate and semantic_gate
    checks = (
        (structured_valid, "invalid_structured_output"),
        (citation_valid, "citation_scope_failure"),
        (hidden_leaks == 0, "hidden_truth_leakage"),
        (profile_leaks == 0, "profile_leakage"),
        (input_packet_unchanged, "input_packet_mutation"),
        (provenance_scope_valid, "provenance_scope_failure"),
        (semantic_gate, "semantic_gate_failure"),
    )
    issues = tuple(code for ok, code in checks if not ok)
    base = {
        "schema_version": "rei-c3-racio-interpreter-case-result-v1",
        "case_id": case.public.case_id,
        "root_id": case.public.root_id,
        "bilingual_pair_id": gold.bilingual_pair_id,
        "provider_mode": provider_mode,
        "source_mind": packet.source_mind,
        "language": packet.language,
        "ambiguity_class": gold.ambiguity_class,
        "packet_id": packet.packet_id,
        "packet_hash": packet.content_hash(),
        "provider_payload_hash": sha256_hex(packet.provider_payload()),
        "output": output,
        "structured_output_valid": structured_valid,
        "citation_scope_valid": citation_valid,
        "hidden_truth_leakage_count": hidden_leaks,
        "profile_leakage_count": profile_leaks,
        "input_packet_unchanged": input_packet_unchanged,
        "provenance_scope_valid": provenance_scope_valid,
        "option_exact": option_exact,
        "action_exact": action_exact,
        "motive_exact": motive_exact,
        "ambiguity_gate_pass": ambiguity_gate,
        "passed": passed,
        "issues": issues,
        "provenance": provenance,
    }
    result_id = content_id("c3_interpreter_eval", base)
    payload = {"result_id": result_id, **base}
    return C3BenchmarkCaseResult(**payload, result_hash=sha256_hex(payload))


class C3BenchmarkRunMetrics(FrozenModel):
    benchmark_id: Literal[
        "rei-c3-racio-interpreter-benchmark-v1",
        "rei-c3-racio-interpreter-holdout-v1",
    ]
    provider_mode: ProviderMode
    case_count: int
    model_call_count: int
    structured_output_valid_count: int
    citation_scope_failure_count: int
    hidden_truth_leakage_count: int
    profile_leakage_count: int
    input_packet_mutation_count: int
    provenance_scope_failure_count: int
    unambiguous_count: int
    unambiguous_exact_option_count: int
    unambiguous_exact_action_count: int
    unambiguous_exact_motive_count: int
    ambiguous_count: int
    ambiguous_gate_pass_count: int
    bilingual_pair_count: int
    bilingual_consistent_pair_count: int
    passed_case_count: int
    baseline_unambiguous_exact_option_count: int | None
    model_outperforms_baseline: bool | None
    structural_gate_pass: bool
    quality_gate_pass: bool


def _validate_recomputed_results(
    *,
    suite: C3BenchmarkSuite,
    provider_mode: ProviderMode,
    results: tuple[C3BenchmarkCaseResult, ...],
    label: str,
) -> None:
    cases_by_id = {case.public.case_id: case for case in suite.cases}
    for result in results:
        try:
            cold = C3BenchmarkCaseResult.model_validate_json(
                result.canonical_json_bytes()
            )
        except ValueError as exc:
            raise ValueError(f"C3 {label} result artifact is invalid") from exc
        if cold != result:
            raise ValueError(f"C3 {label} result differs after cold validation")
        case = cases_by_id.get(result.case_id)
        if case is None:
            raise ValueError(f"C3 {label} result references an unknown case")
        recomputed = evaluate_c3_benchmark_case(
            case=case,
            provider_mode=provider_mode,
            output=result.output,
            provenance=result.provenance,
            input_packet_unchanged=result.input_packet_unchanged,
        )
        if recomputed != result:
            raise ValueError(f"C3 {label} result differs from recomputed evaluation")


def evaluate_c3_benchmark_run(
    *,
    suite: C3BenchmarkSuite,
    provider_mode: ProviderMode,
    results: tuple[C3BenchmarkCaseResult, ...],
    model_call_count: int,
    baseline_results: tuple[C3BenchmarkCaseResult, ...] | None = None,
) -> C3BenchmarkRunMetrics:
    expected_ids = {case.public.case_id for case in suite.cases}
    result_ids = {result.case_id for result in results}
    if len(results) != 32 or result_ids != expected_ids:
        raise ValueError("C3 benchmark results must cover all 32 frozen cases exactly")
    if len(result_ids) != len(results):
        raise ValueError("C3 benchmark result case IDs must be unique")
    if any(result.provider_mode != provider_mode for result in results):
        raise ValueError("C3 result provider modes differ from the requested run")
    _validate_recomputed_results(
        suite=suite,
        provider_mode=provider_mode,
        results=results,
        label="candidate",
    )
    expected_model_call_count = 32 if provider_mode == "ollama" else 0
    if model_call_count != expected_model_call_count:
        raise ValueError(
            "C3 model call count must be exactly 32 for Ollama and zero otherwise"
        )

    pair_results: dict[str, dict[str, C3BenchmarkCaseResult]] = {}
    for result in results:
        pair_results.setdefault(result.bilingual_pair_id, {})[result.language] = result
    bilingual_consistent = 0
    for language_results in pair_results.values():
        if set(language_results) != {"sl", "en"}:
            continue
        sl = language_results["sl"]
        en = language_results["en"]
        if sl.output is None or en.output is None:
            continue
        semantically_equal = (
            sl.output.source_mind == en.output.source_mind
            and sl.output.inferred_option_id == en.output.inferred_option_id
            and sl.output.inferred_action_tendency == en.output.inferred_action_tendency
            and sl.output.inferred_motive_class == en.output.inferred_motive_class
            and (sl.output.inferred_option_id is None)
            == (en.output.inferred_option_id is None)
            and abs(sl.output.confidence - en.output.confidence)
            <= suite.manifest.bilingual_confidence_tolerance
        )
        bilingual_consistent += int(semantically_equal)

    unambiguous = tuple(
        result for result in results if result.ambiguity_class == "unambiguous"
    )
    ambiguous = tuple(
        result for result in results if result.ambiguity_class == "ambiguous"
    )
    valid_count = sum(result.structured_output_valid for result in results)
    citation_failures = sum(not result.citation_scope_valid for result in results)
    hidden_leaks = sum(result.hidden_truth_leakage_count for result in results)
    profile_leaks = sum(result.profile_leakage_count for result in results)
    mutations = sum(not result.input_packet_unchanged for result in results)
    provenance_failures = sum(not result.provenance_scope_valid for result in results)
    ambiguity_passes = sum(result.ambiguity_gate_pass for result in ambiguous)
    option_correct = sum(result.option_exact for result in unambiguous)
    action_correct = sum(result.action_exact for result in unambiguous)
    motive_correct = sum(result.motive_exact for result in unambiguous)

    baseline_correct: int | None = None
    outperforms: bool | None = None
    if provider_mode == "ollama":
        if baseline_results is None:
            raise ValueError("Model-backed C3 gate requires paired baseline results")
        baseline_ids = {result.case_id for result in baseline_results}
        if len(baseline_results) != 32 or baseline_ids != expected_ids:
            raise ValueError("C3 baseline results must cover the same frozen cases")
        if any(result.provider_mode != "deterministic" for result in baseline_results):
            raise ValueError("C3 paired baseline must be deterministic")
        _validate_recomputed_results(
            suite=suite,
            provider_mode="deterministic",
            results=baseline_results,
            label="baseline",
        )
        baseline_correct = sum(
            result.option_exact
            for result in baseline_results
            if result.ambiguity_class == "unambiguous"
        )
        outperforms = option_correct > baseline_correct
    elif baseline_results is not None:
        raise ValueError("Deterministic C3 mode cannot claim a second baseline")

    structural_gate = (
        valid_count == 32
        and citation_failures == 0
        and hidden_leaks == 0
        and profile_leaks == 0
        and mutations == 0
        and provenance_failures == 0
        and model_call_count == expected_model_call_count
        and len(ambiguous) == 16
        and ambiguity_passes == 16
        and len(pair_results) == 16
        and bilingual_consistent == 16
    )
    passed_case_count = sum(result.passed for result in results)
    quality_gate = structural_gate and (
        provider_mode == "deterministic"
        or (
            outperforms is True
            and (
                suite.manifest.benchmark_id == BENCHMARK_ID
                or passed_case_count == len(results)
            )
        )
    )
    return C3BenchmarkRunMetrics(
        benchmark_id=suite.manifest.benchmark_id,
        provider_mode=provider_mode,
        case_count=len(results),
        model_call_count=model_call_count,
        structured_output_valid_count=valid_count,
        citation_scope_failure_count=citation_failures,
        hidden_truth_leakage_count=hidden_leaks,
        profile_leakage_count=profile_leaks,
        input_packet_mutation_count=mutations,
        provenance_scope_failure_count=provenance_failures,
        unambiguous_count=len(unambiguous),
        unambiguous_exact_option_count=option_correct,
        unambiguous_exact_action_count=action_correct,
        unambiguous_exact_motive_count=motive_correct,
        ambiguous_count=len(ambiguous),
        ambiguous_gate_pass_count=ambiguity_passes,
        bilingual_pair_count=len(pair_results),
        bilingual_consistent_pair_count=bilingual_consistent,
        passed_case_count=passed_case_count,
        baseline_unambiguous_exact_option_count=baseline_correct,
        model_outperforms_baseline=outperforms,
        structural_gate_pass=structural_gate,
        quality_gate_pass=quality_gate,
    )


__all__ = [
    "BENCHMARK_ID",
    "BENCHMARK_SCHEMA_VERSION",
    "HOLDOUT_BENCHMARK_ID",
    "HOLDOUT_BENCHMARK_SCHEMA_VERSION",
    "HOLDOUT_DATA_ROOT",
    "HOLDOUT_MANIFEST_PATH",
    "DATA_ROOT",
    "MANIFEST_PATH",
    "OFFICIAL_MANIFEST_SHA256",
    "C3BenchmarkCase",
    "C3BenchmarkCaseResult",
    "C3BenchmarkManifest",
    "C3BenchmarkManifestV2",
    "C3BenchmarkRunMetrics",
    "C3BenchmarkSuite",
    "C3ExecutionProvenance",
    "C3FailureCode",
    "C3FailureEvidence",
    "C3GoldBenchmarkCase",
    "C3PublicBenchmarkCase",
    "C3SourceGroundingPin",
    "build_execution_provenance",
    "evaluate_c3_benchmark_case",
    "evaluate_c3_benchmark_run",
    "load_c3_racio_interpreter_benchmark",
]
