from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import app.backend.rei.evaluation.racio_interpreter_benchmark as c3_benchmark
import app.backend.rei.evaluation.c3_official_suite as official_c3
from app.backend.rei.communication.structured_interpreter import (
    DeterministicStructuredRacioInterpreterProvider,
    StructuredRacioInterpreterOutput,
)
from app.backend.rei.evaluation.racio_interpreter_benchmark import (
    C3BenchmarkManifestV2,
    C3ExecutionProvenance,
    C3FailureEvidence,
    C3_REGRESSION_FAMILY_IDS,
    build_execution_provenance,
    evaluate_c3_benchmark_case,
    evaluate_c3_benchmark_run,
    load_c3_racio_interpreter_benchmark,
)
from app.backend.rei.ids import canonical_json_bytes, content_id, sha256_hex
from app.backend.rei.models.provider import (
    ProviderCallRecord,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ProviderParameter,
)
from app.backend.rei.providers.ollama import (
    OllamaActiveModel,
    OllamaRacioSettings,
    OllamaResponseError,
    OllamaRuntimeModel,
    OllamaTransportError,
)
from app.backend.rei.providers.ollama_interpreter import (
    OllamaInterpreterExecutionError,
    OllamaStructuredRacioInterpreterResponseEvidence,
)
from app.backend.rei.providers.native import build_provider_call_spec
from scripts.build_c3_racio_holdout import build_corpus_bytes, write_corpus
import scripts.build_c3_racio_holdout as holdout_builder
from scripts.run_racio_interpreter_benchmark import (
    classify_c3_execution_failure,
    deterministic_results,
)


PROTOCOL_COMMIT = "a" * 40
INSTRUCTION_SHA256 = "b" * 64
OUTPUT_SCHEMA_SHA256 = "c" * 64
MODEL_DIGEST = "07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522"
FIXED_TIME = datetime(2026, 7, 15, tzinfo=timezone.utc)


def _write_holdout(tmp_path: Path) -> Path:
    root = tmp_path / "c3_racio_interpreter_holdout_v1"
    write_corpus(
        root,
        protocol_freeze_commit=PROTOCOL_COMMIT,
        instruction_sha256=INSTRUCTION_SHA256,
        output_schema_sha256=OUTPUT_SCHEMA_SHA256,
    )
    return root


def _jsonl_payload(records: list[dict]) -> bytes:
    return (
        "".join(
            json.dumps(
                record,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
            for record in records
        )
    ).encode("utf-8")


def _inject_provider_visible_token(root: Path, token: str) -> None:
    public_path = root / "public_cases.jsonl"
    records = [
        json.loads(line)
        for line in public_path.read_text(encoding="utf-8").splitlines()
    ]
    records[0]["packet_input"]["uncertainty"] = token
    public_payload = _jsonl_payload(records)
    public_path.write_bytes(public_payload)

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    next(item for item in manifest["files"] if item["path"] == public_path.name)[
        "sha256"
    ] = hashlib.sha256(public_payload).hexdigest()
    manifest_path.write_bytes(
        (
            json.dumps(
                manifest,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    )


def _perfect_model_results(suite, *, wrong_motive_case_id: str | None = None):
    identity_payload = {
        "kind": "text_reasoner",
        "implementation": "tests.PerfectC3HoldoutProvider",
        "implementation_revision": "v1",
        "uses_model": True,
        "model": "qwen3.6:35b",
        "model_revision": MODEL_DIGEST,
    }
    identity = ProviderIdentity(
        provider_id=content_id("provider", identity_payload),
        **identity_payload,
    )
    wrong_pair_id = next(
        (
            case.gold.bilingual_pair_id
            for case in suite.cases
            if case.public.case_id == wrong_motive_case_id
        ),
        None,
    )
    results = []
    for case in suite.cases:
        packet = case.packet
        gold = case.gold
        output = StructuredRacioInterpreterOutput(
            source_mind=packet.source_mind,
            cited_observation_ids=(packet.visible_observations[0].observation_id,),
            inferred_option_id=gold.expected_option_id,
            inferred_action_tendency=gold.expected_action_tendency,
            inferred_motive_class=(
                "body_alarm"
                if case.gold.bilingual_pair_id == wrong_pair_id
                else gold.expected_motive_class
            ),
            confidence=0.2 if gold.ambiguity_class == "ambiguous" else 0.8,
            alternative_hypotheses=("A bounded alternative remains possible.",),
            unresolved_ambiguity=(
                "The visible signals remain inconclusive."
                if gold.ambiguity_class == "ambiguous"
                else None
            ),
        ).validate_against(packet)
        call = build_provider_call_spec(
            identity=identity,
            request_id=packet.packet_id,
            input_artifact_ids=(packet.packet_id,),
            seed=314159,
            parameters=(
                ProviderParameter(name="num_ctx", canonical_json_value="65536"),
                ProviderParameter(name="num_gpu", canonical_json_value="999"),
                ProviderParameter(
                    name="require_full_gpu",
                    canonical_json_value="true",
                ),
            ),
            fallback_policy=ProviderFallbackPolicy(
                mode="none",
                no_fallback_reason="Synthetic quality-gate evidence has no fallback.",
            ),
        )
        settings = OllamaRacioSettings(
            model="qwen3.6:35b",
            num_ctx=65536,
            num_gpu=999,
            require_full_gpu=True,
        )
        runtime = OllamaRuntimeModel(
            server_version="test",
            model="qwen3.6:35b",
            digest=MODEL_DIGEST,
            size_bytes=1,
            quantization_level=None,
            context_length=262144,
            capabilities=("completion",),
        )
        placement = OllamaActiveModel(
            model="qwen3.6:35b",
            digest=MODEL_DIGEST,
            size_bytes=1,
            size_vram_bytes=1,
            context_length=65536,
            gpu_percent_rounded=100,
        )
        request_payload = {"model": "qwen3.6:35b", "case": case.public.case_id}
        response_payload = {
            "response": output.canonical_json_bytes().decode("utf-8"),
            "done_reason": "stop",
        }
        evidence = OllamaStructuredRacioInterpreterResponseEvidence.create(
            packet=packet,
            call=call,
            runtime=runtime,
            settings=settings,
            request_payload=request_payload,
            response=response_payload,
            output=output,
            placement=placement,
        )
        record = ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=call.request_id,
            input_artifact_ids=call.input_artifact_ids,
            provider=call.provider,
            seed=call.seed,
            parameters=call.parameters,
            timeout_seconds=call.timeout_seconds,
            started_at=FIXED_TIME,
            primary_finished_at=FIXED_TIME,
            finished_at=FIXED_TIME,
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(evidence.result_id,),
            safety_notice=call.safety_notice,
        )
        provenance = build_execution_provenance(
            identity=identity,
            call=call,
            call_record=record,
            response_evidence=evidence,
        )
        result = evaluate_c3_benchmark_case(
            case=case,
            provider_mode="ollama",
            output=output,
            provenance=provenance,
            input_packet_unchanged=True,
        )
        assert result.passed is (case.gold.bilingual_pair_id != wrong_pair_id)
        results.append(result)
    return tuple(results)


def test_official_c3_suite_registration_loads_holdout_then_regression() -> None:
    assert c3_benchmark.OFFICIAL_MANIFEST_SHA256 == (
        official_c3.OFFICIAL_REGRESSION_MANIFEST_SHA256
    )
    assert official_c3.OFFICIAL_C3_SUITE_ORDER == (
        (
            c3_benchmark.HOLDOUT_MANIFEST_PATH,
            official_c3.OFFICIAL_HOLDOUT_MANIFEST_SHA256,
        ),
        (
            c3_benchmark.MANIFEST_PATH,
            official_c3.OFFICIAL_REGRESSION_MANIFEST_SHA256,
        ),
    )

    holdout, regression = official_c3.load_official_c3_suite_pair()
    assert official_c3.load_official_c3_racio_interpreter_suites() == (
        holdout,
        regression,
    )

    assert isinstance(holdout.manifest, C3BenchmarkManifestV2)
    assert holdout.manifest.benchmark_id == c3_benchmark.HOLDOUT_BENCHMARK_ID
    assert holdout.manifest.suite_role == "untouched_holdout"
    assert holdout.manifest.protocol_freeze_commit == official_c3.PROTOCOL_FREEZE_COMMIT
    assert holdout.manifest_file_hash == (official_c3.OFFICIAL_HOLDOUT_MANIFEST_SHA256)
    assert regression.manifest.benchmark_id == c3_benchmark.BENCHMARK_ID
    assert regression.manifest.schema_version == c3_benchmark.BENCHMARK_SCHEMA_VERSION
    assert regression.manifest_file_hash == (
        official_c3.OFFICIAL_REGRESSION_MANIFEST_SHA256
    )
    assert tuple(suite.manifest.benchmark_id for suite in (holdout, regression)) == (
        c3_benchmark.HOLDOUT_BENCHMARK_ID,
        c3_benchmark.BENCHMARK_ID,
    )


def test_official_c3_suite_loader_rejects_source_fixture_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read = official_c3._read_bounded

    def drifted_read(path, *, maximum_bytes, label):
        payload = original_read(
            path,
            maximum_bytes=maximum_bytes,
            label=label,
        )
        source = Path(path)
        if source.name == "sf_new_year_resolution.json" and (
            source.parent.name == "semantic_lab_v1"
        ):
            return payload + b"\n"
        return payload

    monkeypatch.setattr(official_c3, "_read_bounded", drifted_read)
    with pytest.raises(ValueError, match="source fixture differs from pin"):
        official_c3.load_official_c3_suite_pair()


@pytest.mark.parametrize("suite_name", ("holdout", "regression"))
def test_official_c3_suite_loader_rejects_manifest_hash_substitution(
    monkeypatch: pytest.MonkeyPatch,
    suite_name: str,
) -> None:
    holdout = load_c3_racio_interpreter_benchmark(c3_benchmark.HOLDOUT_MANIFEST_PATH)
    regression = load_c3_racio_interpreter_benchmark(c3_benchmark.MANIFEST_PATH)
    if suite_name == "holdout":
        holdout = holdout.model_copy(update={"manifest_file_hash": "0" * 64})
    else:
        regression = regression.model_copy(update={"manifest_file_hash": "0" * 64})

    def fake_loader(path):
        if path == c3_benchmark.HOLDOUT_MANIFEST_PATH:
            return holdout
        if path == c3_benchmark.MANIFEST_PATH:
            return regression
        raise AssertionError(f"unexpected manifest path: {path}")

    monkeypatch.setattr(
        official_c3,
        "load_c3_racio_interpreter_benchmark",
        fake_loader,
    )
    with pytest.raises(ValueError, match="path/hash registration differs"):
        official_c3.load_official_c3_suite_pair()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("protocol_freeze_commit", "0" * 40),
        ("instruction_sha256", "0" * 64),
        ("output_schema_sha256", "0" * 64),
        ("calibration_policy_id", "changed-calibration-policy"),
    ),
)
def test_official_c3_suite_loader_rejects_protocol_substitution(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    holdout = load_c3_racio_interpreter_benchmark(c3_benchmark.HOLDOUT_MANIFEST_PATH)
    regression = load_c3_racio_interpreter_benchmark(c3_benchmark.MANIFEST_PATH)
    forged_manifest = holdout.manifest.model_copy(update={field: value})
    forged_holdout = holdout.model_copy(update={"manifest": forged_manifest})

    def fake_loader(path):
        if path == c3_benchmark.HOLDOUT_MANIFEST_PATH:
            return forged_holdout
        if path == c3_benchmark.MANIFEST_PATH:
            return regression
        raise AssertionError(f"unexpected manifest path: {path}")

    monkeypatch.setattr(
        official_c3,
        "load_c3_racio_interpreter_benchmark",
        fake_loader,
    )
    with pytest.raises(ValueError, match="protocol contract differs"):
        official_c3.load_official_c3_suite_pair()


@pytest.mark.parametrize(
    ("suite_name", "updates", "message"),
    (
        ("holdout", {"suite_role": "regression"}, "holdout role"),
        (
            "holdout",
            {"benchmark_id": "rei-c3-racio-interpreter-benchmark-v1"},
            "holdout role",
        ),
        (
            "regression",
            {"benchmark_id": "rei-c3-racio-interpreter-holdout-v1"},
            "regression identity",
        ),
    ),
)
def test_official_c3_suite_loader_rejects_role_or_id_substitution(
    monkeypatch: pytest.MonkeyPatch,
    suite_name: str,
    updates: dict[str, str],
    message: str,
) -> None:
    holdout = load_c3_racio_interpreter_benchmark(c3_benchmark.HOLDOUT_MANIFEST_PATH)
    regression = load_c3_racio_interpreter_benchmark(c3_benchmark.MANIFEST_PATH)
    if suite_name == "holdout":
        holdout = holdout.model_copy(
            update={"manifest": holdout.manifest.model_copy(update=updates)}
        )
    else:
        regression = regression.model_copy(
            update={"manifest": regression.manifest.model_copy(update=updates)}
        )

    def fake_loader(path):
        if path == c3_benchmark.HOLDOUT_MANIFEST_PATH:
            return holdout
        if path == c3_benchmark.MANIFEST_PATH:
            return regression
        raise AssertionError(f"unexpected manifest path: {path}")

    monkeypatch.setattr(
        official_c3,
        "load_c3_racio_interpreter_benchmark",
        fake_loader,
    )
    with pytest.raises(ValueError, match=message):
        official_c3.load_official_c3_suite_pair()


def test_holdout_builder_is_create_only_and_v2_manifest_is_sealed(
    tmp_path: Path,
) -> None:
    root = _write_holdout(tmp_path)
    suite = load_c3_racio_interpreter_benchmark(root / "manifest.json")

    assert isinstance(suite.manifest, C3BenchmarkManifestV2)
    assert suite.manifest.benchmark_id == "rei-c3-racio-interpreter-holdout-v1"
    assert suite.manifest.suite_role == "untouched_holdout"
    assert suite.manifest.protocol_freeze_commit == PROTOCOL_COMMIT
    assert suite.manifest.instruction_sha256 == INSTRUCTION_SHA256
    assert suite.manifest.output_schema_sha256 == OUTPUT_SCHEMA_SHA256
    assert suite.manifest.sealed_before_candidate_run is True
    assert suite.manifest.post_seal_prompt_tuning_allowed is False
    assert suite.manifest.model_generated_gold is False
    assert suite.manifest.training_export is False
    assert len(suite.cases) == 32
    assert not set(suite.manifest.source_family_ids) & set(C3_REGRESSION_FAMILY_IDS)

    with pytest.raises(FileExistsError):
        write_corpus(
            root,
            protocol_freeze_commit=PROTOCOL_COMMIT,
            instruction_sha256=INSTRUCTION_SHA256,
            output_schema_sha256=OUTPUT_SCHEMA_SHA256,
        )


def test_source_grounding_pins_match_exact_reviewed_fixture_bytes(
    tmp_path: Path,
) -> None:
    suite = load_c3_racio_interpreter_benchmark(
        _write_holdout(tmp_path) / "manifest.json"
    )
    pins = {pin.family_id: pin for pin in suite.manifest.source_grounding_pins}

    assert set(pins) == set(holdout_builder.SOURCE_FIXTURE_SHA256)
    assert {pin.root_id for pin in pins.values()} == set(suite.manifest.root_ids)
    for family_id, expected_hash in holdout_builder.SOURCE_FIXTURE_SHA256.items():
        pin = pins[family_id]
        fixture_path = Path(pin.fixture_path)
        assert pin.fixture_review_status == "canon_approved"
        assert pin.fixture_variant_count == 8
        assert pin.fixture_sha256 == expected_hash
        assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == expected_hash


def test_builder_rejects_changed_source_fixture_bytes(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixtures"
    shutil.copytree(holdout_builder.SEMANTIC_LAB_FIXTURE_ROOT, fixture_root)
    target = fixture_root / "sf_new_year_resolution.json"
    target.write_bytes(target.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="SHA-256 differs"):
        build_corpus_bytes(
            protocol_freeze_commit=PROTOCOL_COMMIT,
            instruction_sha256=INSTRUCTION_SHA256,
            output_schema_sha256=OUTPUT_SCHEMA_SHA256,
            fixture_root=fixture_root,
        )


def test_builder_validates_selected_canonical_interpretation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family_id = "sf_new_year_resolution"
    fixture_root = tmp_path / "fixtures"
    shutil.copytree(holdout_builder.SEMANTIC_LAB_FIXTURE_ROOT, fixture_root)
    fixture_path = fixture_root / f"{family_id}.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    canonical = next(
        variant for variant in fixture["variants"] if variant["mode"] == "sl_canonical"
    )
    selected = next(
        item
        for item in canonical["interpretation_variants"]
        if item["source_mind"] == "E"
    )
    selected["expected_option_id"] = "option_start_plan"
    fixture_path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    changed_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    fixture_manifest_path = fixture_root / "manifest.json"
    fixture_manifest = json.loads(fixture_manifest_path.read_text(encoding="utf-8"))
    next(item for item in fixture_manifest["files"] if item["family_id"] == family_id)[
        "sha256"
    ] = changed_hash
    fixture_manifest_path.write_text(
        json.dumps(fixture_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setitem(
        holdout_builder.SOURCE_FIXTURE_SHA256,
        family_id,
        changed_hash,
    )

    with pytest.raises(ValueError, match="canonical interpretation pin differs"):
        build_corpus_bytes(
            protocol_freeze_commit=PROTOCOL_COMMIT,
            instruction_sha256=INSTRUCTION_SHA256,
            output_schema_sha256=OUTPUT_SCHEMA_SHA256,
            fixture_root=fixture_root,
        )


@pytest.mark.parametrize("manifest_payload", (b"[]", b"null", b'"manifest"'))
def test_loader_rejects_non_object_manifest(
    tmp_path: Path,
    manifest_payload: bytes,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(manifest_payload)

    with pytest.raises(ValueError, match="must contain one object"):
        load_c3_racio_interpreter_benchmark(manifest_path)


def test_holdout_builder_bytes_are_deterministic_lf_only_and_physically_split(
    tmp_path: Path,
) -> None:
    expected = build_corpus_bytes(
        protocol_freeze_commit=PROTOCOL_COMMIT,
        instruction_sha256=INSTRUCTION_SHA256,
        output_schema_sha256=OUTPUT_SCHEMA_SHA256,
    )
    root = _write_holdout(tmp_path)
    actual = {path.name: path.read_bytes() for path in root.iterdir()}

    assert actual == expected
    assert all(b"\r\n" not in payload for payload in actual.values())
    assert b"expected_option_id" not in actual["public_cases.jsonl"]
    assert b"evaluator_only_canary" not in actual["public_cases.jsonl"]
    assert b"expected_option_id" in actual["gold.jsonl"]
    assert b"evaluator_only_canary" in actual["gold.jsonl"]


def test_holdout_is_balanced_and_every_evaluator_identifier_stays_private(
    tmp_path: Path,
) -> None:
    root = _write_holdout(tmp_path)
    suite = load_c3_racio_interpreter_benchmark(root / "manifest.json")
    counts = suite.manifest.counts.model_dump(mode="python")

    assert counts == {
        "cases": 32,
        "roots": 8,
        "emocio": 16,
        "instinkt": 16,
        "slovenian": 16,
        "english": 16,
        "unambiguous": 16,
        "ambiguous": 16,
        "accepting": 16,
        "mixed": 8,
        "conflicted": 8,
        "bilingual_pairs": 16,
    }
    unambiguous = [
        case for case in suite.cases if case.gold.ambiguity_class == "unambiguous"
    ]
    assert (
        sum(case.gold.expected_option_id == "option_001" for case in unambiguous) == 8
    )
    assert (
        sum(case.gold.expected_option_id == "option_002" for case in unambiguous) == 8
    )

    forbidden_tokens = {
        token
        for case in suite.cases
        for token in (
            case.public.case_id,
            case.public.root_id,
            case.gold.family_id,
            case.gold.variant_id,
            case.gold.bilingual_pair_id,
            case.gold.native_truth_id,
            case.gold.profile_id,
            case.gold.evaluator_only_canary,
        )
    }
    for case in suite.cases:
        encoded = case.packet.provider_payload_bytes().decode("utf-8")
        assert not any(token in encoded for token in forbidden_tokens)


@pytest.mark.parametrize(
    "identity_field",
    (
        "case_id",
        "root_id",
        "family_id",
        "variant_id",
        "bilingual_pair_id",
        "native_truth_id",
        "profile_id",
        "evaluator_only_canary",
    ),
)
def test_loader_rejects_provider_visible_evaluator_identity_mutation(
    tmp_path: Path,
    identity_field: str,
) -> None:
    root = _write_holdout(tmp_path)
    public_record = json.loads(
        (root / "public_cases.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    gold_record = json.loads(
        (root / "gold.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    token = (public_record | gold_record)[identity_field]
    _inject_provider_visible_token(root, token)

    with pytest.raises(ValueError, match="evaluator-only lineage"):
        load_c3_racio_interpreter_benchmark(root / "manifest.json")


def test_v2_model_gate_requires_every_case_not_only_structural_counts(
    tmp_path: Path,
) -> None:
    suite = load_c3_racio_interpreter_benchmark(
        _write_holdout(tmp_path) / "manifest.json"
    )
    baseline = deterministic_results(suite)
    perfect = _perfect_model_results(suite)
    metrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="ollama",
        results=perfect,
        model_call_count=32,
        baseline_results=baseline,
    )
    assert metrics.structural_gate_pass is True
    assert metrics.passed_case_count == 32
    assert metrics.quality_gate_pass is True

    forged_base = perfect[0].model_dump(
        mode="python",
        round_trip=True,
        exclude={"result_id", "result_hash"},
    )
    forged_base["motive_exact"] = False
    forged_base["passed"] = False
    forged_id = content_id("c3_interpreter_eval", forged_base)
    forged_payload = {"result_id": forged_id, **forged_base}
    forged = type(perfect[0])(
        **forged_payload,
        result_hash=sha256_hex(forged_payload),
    )
    with pytest.raises(ValueError, match="recomputed evaluation"):
        evaluate_c3_benchmark_run(
            suite=suite,
            provider_mode="ollama",
            results=(forged, *perfect[1:]),
            model_call_count=32,
            baseline_results=baseline,
        )

    one_semantic_failure = _perfect_model_results(
        suite,
        wrong_motive_case_id=suite.cases[0].public.case_id,
    )
    failed_metrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="ollama",
        results=one_semantic_failure,
        model_call_count=32,
        baseline_results=baseline,
    )
    assert failed_metrics.structural_gate_pass is True
    assert failed_metrics.passed_case_count == 30
    assert failed_metrics.quality_gate_pass is False


def test_result_cold_validation_rejects_declared_evidence_id_substitution(
    tmp_path: Path,
) -> None:
    suite = load_c3_racio_interpreter_benchmark(
        _write_holdout(tmp_path) / "manifest.json"
    )
    results = deterministic_results(suite)
    original = results[0]
    provenance = original.provenance
    assert provenance.call_record is not None
    fake_evidence_id = "structured_racio_interpreter_" + "f" * 32
    forged_record = provenance.call_record.model_copy(
        update={"output_artifact_ids": (fake_evidence_id,)}
    )
    forged_provenance = provenance.model_copy(
        update={
            "call_record": forged_record,
            "call_record_hash": forged_record.content_hash(),
            "response_evidence_id": fake_evidence_id,
        }
    )
    forged_result = original.model_copy(update={"provenance": forged_provenance})
    result_base = forged_result.model_dump(
        mode="python",
        round_trip=True,
        exclude={"result_id", "result_hash"},
    )
    forged_result_id = content_id("c3_interpreter_eval", result_base)
    forged_payload = {"result_id": forged_result_id, **result_base}
    forged_result = forged_result.model_copy(
        update={
            "result_id": forged_result_id,
            "result_hash": sha256_hex(forged_payload),
        }
    )

    with pytest.raises(ValueError, match="result artifact is invalid"):
        evaluate_c3_benchmark_run(
            suite=suite,
            provider_mode="deterministic",
            results=(forged_result, *results[1:]),
            model_call_count=0,
        )


@pytest.mark.parametrize("mutation", ("context", "full_gpu"))
def test_typed_provenance_rejects_readdressed_placement_claims(
    tmp_path: Path,
    mutation: str,
) -> None:
    suite = load_c3_racio_interpreter_benchmark(
        _write_holdout(tmp_path) / "manifest.json"
    )
    result = _perfect_model_results(suite)[0]
    provenance = result.provenance
    assert provenance.response_evidence_json is not None
    assert provenance.call_record is not None
    evidence = json.loads(provenance.response_evidence_json)
    if mutation == "context":
        evidence["requested_num_ctx"] = 32768
        evidence["active_context_length"] = 32768
        expected_message = "placement evidence differs"
    else:
        evidence["active_gpu_percent_rounded"] = 99
        expected_message = "full-GPU placement"
    evidence_without_id = {
        key: value for key, value in evidence.items() if key != "result_id"
    }
    evidence["result_id"] = content_id(
        "ollama_interpreter_response",
        evidence_without_id,
    )
    evidence_json = json.dumps(
        evidence,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    forged_record = provenance.call_record.model_copy(
        update={"output_artifact_ids": (evidence["result_id"],)}
    )
    provenance_payload = provenance.model_dump(mode="python", round_trip=True)
    provenance_payload.update(
        {
            "call_record": forged_record.model_dump(mode="python", round_trip=True),
            "call_record_hash": forged_record.content_hash(),
            "response_evidence_id": evidence["result_id"],
            "response_evidence_hash": sha256_hex(evidence),
            "response_evidence_json": evidence_json,
        }
    )

    with pytest.raises(ValidationError, match=expected_message):
        C3ExecutionProvenance.model_validate_json(
            canonical_json_bytes(provenance_payload)
        )


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (OllamaTransportError("secret transport path"), "transport_failure"),
        (ValueError("secret request"), "unexpected_provider_failure"),
        (OllamaResponseError("secret response"), "generation_contract_failure"),
        (RuntimeError("secret unexpected"), "unexpected_provider_failure"),
        (
            OllamaInterpreterExecutionError(
                "structured_output_invalid", "secret raw JSON"
            ),
            "structured_output_invalid",
        ),
        (
            OllamaInterpreterExecutionError(
                "conscious_access_rejected", "secret hidden alias"
            ),
            "conscious_access_rejected",
        ),
        (
            OllamaInterpreterExecutionError(
                "runtime_identity_mismatch", "secret runtime"
            ),
            "runtime_identity_mismatch",
        ),
        (
            OllamaInterpreterExecutionError(
                "gpu_placement_failure", "secret placement"
            ),
            "gpu_placement_failure",
        ),
    ),
)
def test_failure_classifier_exposes_only_stable_codes(
    error: Exception,
    expected: str,
) -> None:
    assert classify_c3_execution_failure(error) == expected


def test_failure_evidence_is_content_addressed_and_contains_no_exception_text(
    tmp_path: Path,
) -> None:
    suite = load_c3_racio_interpreter_benchmark(
        _write_holdout(tmp_path) / "manifest.json"
    )
    case = suite.cases[0]
    provider = DeterministicStructuredRacioInterpreterProvider()
    call = provider.build_call_spec(case.packet)
    evidence = C3FailureEvidence.create(
        run_id="c3-holdout-failure-test",
        benchmark_id=suite.manifest.benchmark_id,
        case_id=case.public.case_id,
        packet=case.packet,
        call=call,
        failure_code="structured_output_invalid",
    )

    cold = C3FailureEvidence.model_validate_json(evidence.canonical_json_bytes())
    assert cold == evidence
    encoded = evidence.canonical_json_bytes().decode("utf-8")
    assert "exception" not in encoded
    assert "message" not in encoded
    assert "raw_response" not in encoded
    assert "secret" not in encoded
    assert evidence.retry_attempted is False
    assert evidence.fallback_used is False
    assert evidence.provider_revision == call.provider.implementation_revision

    payload = evidence.model_dump(mode="python", round_trip=True)
    payload["exception_message"] = "must never be stored"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        C3FailureEvidence.model_validate(payload)


def test_holdout_manifest_rejects_regression_family_reuse(tmp_path: Path) -> None:
    root = _write_holdout(tmp_path)
    payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    payload["source_family_ids"][0] = C3_REGRESSION_FAMILY_IDS[0]

    with pytest.raises(ValidationError, match="absent from regression"):
        C3BenchmarkManifestV2.model_validate_json(
            json.dumps(payload, ensure_ascii=False)
        )


def test_loader_rejects_source_pin_to_gold_mapping_substitution(
    tmp_path: Path,
) -> None:
    root = _write_holdout(tmp_path)
    manifest_path = root / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    pin = payload["source_grounding_pins"][0]
    pin["holdout_option_id"] = (
        "option_002" if pin["holdout_option_id"] == "option_001" else "option_001"
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(ValueError, match="source-grounding mapping"):
        load_c3_racio_interpreter_benchmark(manifest_path)


def test_protocol_seal_rejects_operator_supplied_unfrozen_hashes() -> None:
    with pytest.raises(ValueError, match="differs from frozen protocol"):
        holdout_builder.verify_repository_protocol_pins(
            protocol_freeze_commit=PROTOCOL_COMMIT,
            instruction_sha256="d" * 64,
            output_schema_sha256=holdout_builder.EXPECTED_OUTPUT_SCHEMA_SHA256,
        )


def test_protocol_seal_rejects_dirty_scoped_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command, **kwargs):
        del kwargs
        if command[:3] == ["git", "branch", "--show-current"]:
            return SimpleNamespace(stdout="main\n", returncode=0)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=f"{PROTOCOL_COMMIT}\n", returncode=0)
        if command[:4] == ["git", "rev-parse", "--verify", "origin/main"]:
            return SimpleNamespace(stdout=f"{PROTOCOL_COMMIT}\n", returncode=0)
        if command[:2] == ["git", "status"]:
            return SimpleNamespace(
                stdout=" M scripts/build_c3_racio_holdout.py\n",
                returncode=0,
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(holdout_builder.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="committed and clean"):
        holdout_builder.verify_repository_protocol_pins(
            protocol_freeze_commit=PROTOCOL_COMMIT,
            instruction_sha256=holdout_builder.EXPECTED_INSTRUCTION_SHA256,
            output_schema_sha256=holdout_builder.EXPECTED_OUTPUT_SCHEMA_SHA256,
        )


def test_protocol_seal_rejects_dirty_package_initializer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command, **kwargs):
        del kwargs
        if command[:3] == ["git", "branch", "--show-current"]:
            return SimpleNamespace(stdout="main\n", returncode=0)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=f"{PROTOCOL_COMMIT}\n", returncode=0)
        if command[:4] == ["git", "rev-parse", "--verify", "origin/main"]:
            return SimpleNamespace(stdout=f"{PROTOCOL_COMMIT}\n", returncode=0)
        if command[:2] == ["git", "status"]:
            assert "app/backend/rei" in command
            return SimpleNamespace(
                stdout=" M app/backend/rei/models/__init__.py\n",
                returncode=0,
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(holdout_builder.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="committed and clean"):
        holdout_builder.verify_repository_protocol_pins(
            protocol_freeze_commit=PROTOCOL_COMMIT,
            instruction_sha256=holdout_builder.EXPECTED_INSTRUCTION_SHA256,
            output_schema_sha256=holdout_builder.EXPECTED_OUTPUT_SCHEMA_SHA256,
        )


def test_protocol_seal_requires_main_already_pushed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        holdout_builder.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="codex/feature\n",
            returncode=0,
        ),
    )
    with pytest.raises(ValueError, match="directly on main"):
        holdout_builder.verify_repository_protocol_pins(
            protocol_freeze_commit=PROTOCOL_COMMIT,
            instruction_sha256=holdout_builder.EXPECTED_INSTRUCTION_SHA256,
            output_schema_sha256=holdout_builder.EXPECTED_OUTPUT_SCHEMA_SHA256,
        )
