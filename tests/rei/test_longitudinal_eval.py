from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.ego.trace_store import InMemoryEgoTraceStore
from app.backend.rei.engine import ReiNativeCycleRequest, ReiNativeEngine
from app.backend.rei.evaluation.longitudinal_eval import (
    LONGITUDINAL_REPORT_FILENAMES,
    MAX_LONGITUDINAL_CORPUS_BYTES,
    _InMemoryEvaluationArtifactStore,
    LongitudinalEvaluationReport,
    LongitudinalSequenceResult,
    build_longitudinal_scenarios,
    evaluate_longitudinal_corpus,
    load_longitudinal_corpus,
    render_longitudinal_report,
)
from app.backend.rei.governance.profiles import parse_character_profile
from app.backend.rei.ids import content_id, sha256_hex
from app.backend.rei.providers.deterministic import (
    build_deterministic_native_providers,
)
from app.backend.rei.providers.native import DeterministicExecutionClock


ROOT = Path(__file__).resolve().parents[2]
CORPUS = (
    ROOT
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "c6_longitudinal"
    / "corpus.json"
)
TEMPLATE = ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
CHECKED_REPORT = (
    ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "c6-longitudinal-2026-07-14"
)


@pytest.fixture(scope="module")
def full_report() -> LongitudinalEvaluationReport:
    return evaluate_longitudinal_corpus(
        corpus_path=CORPUS,
        template_fixture_path=TEMPLATE,
    )


def test_human_authored_corpus_has_ten_named_bounded_sequences() -> None:
    corpus = load_longitudinal_corpus(CORPUS)
    scenarios = build_longitudinal_scenarios(
        corpus_path=CORPUS,
        template_fixture_path=TEMPLATE,
    )

    assert corpus.human_authored is True
    assert corpus.model_generated_gold is False
    assert corpus.training_export is False
    assert len(corpus.sequences) == len(scenarios) == 10
    assert len({item.sequence_id for item in corpus.sequences}) == 10
    assert all(10 <= len(item.steps) <= 30 for item in corpus.sequences)
    assert all(len(item.steps) == 10 for item in scenarios)
    assert all(item.expected_motifs for item in scenarios)
    assert all(item.scenario_hash for item in scenarios)

    evidence_ids: list[str] = []
    for corpus_sequence, scenario in zip(corpus.sequences, scenarios, strict=True):
        for index, (prompt, step) in enumerate(
            zip(corpus_sequence.steps, scenario.steps, strict=True)
        ):
            expected_source = (
                f"c6-corpus:{corpus_sequence.sequence_id}:step:{index:02d}"
            )
            supplied = tuple(
                item
                for item in step.scene.evidence
                if item.source_ref == expected_source
            )
            assert len(supplied) == 1
            evidence = supplied[0]
            assert evidence.content == prompt
            assert evidence.grounded is True
            assert evidence.provenance_kind == "supplied"
            evidence_ids.append(evidence.evidence_id)
            if step.external_outcome is not None:
                assert step.external_outcome.evidence_ids == (evidence.evidence_id,)
    assert len(evidence_ids) == len(set(evidence_ids)) == 100


def test_full_longitudinal_gate_runs_engine_and_preserves_dimensions(
    full_report: LongitudinalEvaluationReport,
) -> None:
    assert full_report.gate_passed is True
    assert full_report.technical_gate_passed is True
    assert full_report.semantic_authority_granted is False
    assert full_report.gate_kind == "bounded_software_contract"
    assert full_report.review_status == "internal_non_blind"
    assert full_report.gold_status == "implementation_hypothesis"
    assert full_report.motif_gate_kind == "structured_tag_motif_stage_1"
    assert (
        full_report.legacy_outcome_scope
        == "evaluation_only_no_c5_outcome_learning_closure"
    )
    assert full_report.measured_body_outcome_status == "open_no_verified_c5_replay"
    assert (
        full_report.visual_signal_scope
        == "post_cycle_internal_evaluation_not_source_cycle_processing"
    )
    assert (
        full_report.instinkt_learning_scope
        == "prediction_sidecar_only_world_mutation_open_until_verified_c5_replay"
    )
    assert full_report.corpus_sha256 == hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    assert full_report.full_corpus is True
    assert full_report.sequence_count == 10
    assert tuple(item.sequence_id for item in full_report.sequences) == tuple(
        sorted(item.sequence_id for item in full_report.sequences)
    )
    assert full_report.total_cycle_count == 100
    assert full_report.minimum_cycle_count == 10
    assert full_report.passing_sequence_count == 10
    assert full_report.append_only_sequence_count == 10
    assert full_report.character_constant_sequence_count == 10
    assert full_report.projection_citation_sequence_count == 10
    assert full_report.history_consumption_cycle_count == 90
    assert full_report.world_transfer_cycle_count == 90
    assert full_report.modality_specific_world_sequence_count == 10
    assert full_report.character_identifier_absence_sequence_count == 10
    assert full_report.pre_governance_character_invariance is True
    assert full_report.history_counterfactual_influence_sequence_count == 10
    assert full_report.projection_signal_integration_complete is True
    assert full_report.verified_visual_signal_cycle_count == 100
    assert full_report.predicted_body_signal_cycle_count == 100
    assert full_report.measured_body_signal_cycle_count == 0
    assert full_report.motif_precision == 1.0
    assert full_report.motif_recall == 1.0
    assert full_report.motif_false_positive_count == 0
    assert full_report.motif_false_negative_count == 0
    assert full_report.narrative_divergence_cycle_count > 0
    assert full_report.self_narrative_divergence_cycle_count > 0
    assert full_report.ego_decision_api_absent is True
    assert "aggregate_score" not in type(full_report).model_fields

    for result in full_report.sequences:
        assert result.cycle_count == len(result.measure_ids) == 10
        assert result.observed_history_consumption_cycles == 9
        assert result.observed_world_transfer_cycles == 9
        assert result.persisted_cycle_count == 10
        assert result.append_only_verified is True
        assert result.character_constant is True
        assert result.projection_citations_valid is True
        assert result.modality_specific_world_updates is True
        assert result.character_identifiers_absent_from_world_updates is True
        assert result.history_counterfactual_influence is True
        assert result.projection_signal_integration_complete is True
        assert result.verified_visual_signal_cycle_count == 10
        assert result.predicted_body_signal_cycle_count == 10
        assert result.measured_body_signal_cycle_count == 0
        assert result.natural_language_motif_authority_granted is False
        assert result.translation_patterns_match is True
        assert result.passes is True


def test_checked_report_is_byte_reproducible_and_content_addressed(
    full_report: LongitudinalEvaluationReport,
) -> None:
    rendered = render_longitudinal_report(full_report)
    assert tuple(rendered) == LONGITUDINAL_REPORT_FILENAMES
    assert tuple(sorted(path.name for path in CHECKED_REPORT.iterdir())) == tuple(
        sorted(LONGITUDINAL_REPORT_FILENAMES)
    )
    for name, payload in rendered.items():
        assert (CHECKED_REPORT / name).read_bytes() == payload
    assert LongitudinalEvaluationReport.model_validate_json(
        rendered["longitudinal_evaluation.json"]
    ) == full_report


def test_paired_character_variants_have_identical_native_pre_governance_surface() -> None:
    template = ReiNativeCycleRequest.model_validate_json(TEMPLATE.read_bytes())
    alternate = template.model_copy(
        update={
            "character": parse_character_profile(
                "I>E>R",
                character_id="c6_paired_character_control",
            )
        }
    )

    def run(request: ReiNativeCycleRequest):
        return ReiNativeEngine(
            artifact_store=_InMemoryEvaluationArtifactStore(),
            ego_trace_store=InMemoryEgoTraceStore(),
            providers=build_deterministic_native_providers(),
            clock=DeterministicExecutionClock(request.started_at),
        ).run_cycle(request)

    first = run(template)
    second = run(alternate)
    assert first.request.character != second.request.character
    assert first.ego_measure.structural_character != second.ego_measure.structural_character
    assert (
        first.racio_packet,
        first.emocio_packet,
        first.instinkt_packet,
        first.racio_execution,
        first.emocio_execution,
        first.instinkt_execution,
        first.native_bundle,
    ) == (
        second.racio_packet,
        second.emocio_packet,
        second.instinkt_packet,
        second.racio_execution,
        second.emocio_execution,
        second.instinkt_execution,
        second.native_bundle,
    )


def test_result_and_report_reject_readdressed_derived_metric_mutants(
    full_report: LongitudinalEvaluationReport,
) -> None:
    sequence_payload = full_report.sequences[0].model_dump(
        mode="python", round_trip=True
    )
    sequence_payload["append_only_verified"] = False
    sequence_base = {
        key: value
        for key, value in sequence_payload.items()
        if key not in {"sequence_result_id", "result_hash"}
    }
    sequence_id = content_id("longitudinal_sequence_result", sequence_base)
    sequence_envelope = {"sequence_result_id": sequence_id, **sequence_base}
    with pytest.raises(ValidationError, match="passes flag"):
        LongitudinalSequenceResult.model_validate(
            {
                **sequence_envelope,
                "result_hash": sha256_hex(sequence_envelope),
            }
        )

    report_payload = full_report.model_dump(mode="python", round_trip=True)
    report_payload["passing_sequence_count"] = 0
    report_base = {
        key: value
        for key, value in report_payload.items()
        if key not in {"report_id", "report_hash"}
    }
    report_id = content_id("longitudinal_evaluation", report_base)
    report_envelope = {"report_id": report_id, **report_base}
    with pytest.raises(ValidationError, match="aggregates"):
        LongitudinalEvaluationReport.model_validate(
            {
                **report_envelope,
                "report_hash": sha256_hex(report_envelope),
            }
        )


def test_set_semantics_reject_readdressed_noncanonical_order(
    full_report: LongitudinalEvaluationReport,
) -> None:
    sequence_payload = full_report.sequences[0].model_dump(
        mode="python", round_trip=True
    )
    sequence_payload["expected_motifs"] = tuple(
        reversed(sequence_payload["expected_motifs"])
    )
    sequence_base = {
        key: value
        for key, value in sequence_payload.items()
        if key not in {"sequence_result_id", "result_hash"}
    }
    sequence_id = content_id("longitudinal_sequence_result", sequence_base)
    sequence_envelope = {"sequence_result_id": sequence_id, **sequence_base}
    with pytest.raises(ValidationError, match="canonically sorted"):
        LongitudinalSequenceResult.model_validate(
            {
                **sequence_envelope,
                "result_hash": sha256_hex(sequence_envelope),
            }
        )

    report_payload = full_report.model_dump(mode="python", round_trip=True)
    report_payload["sequences"] = tuple(reversed(report_payload["sequences"]))
    report_base = {
        key: value
        for key, value in report_payload.items()
        if key not in {"report_id", "report_hash"}
    }
    report_id = content_id("longitudinal_evaluation", report_base)
    report_envelope = {"report_id": report_id, **report_base}
    with pytest.raises(ValidationError, match="canonical ID order"):
        LongitudinalEvaluationReport.model_validate(
            {
                **report_envelope,
                "report_hash": sha256_hex(report_envelope),
            }
        )


def test_false_motif_is_counted_and_fails_the_bounded_gate(
    full_report: LongitudinalEvaluationReport,
) -> None:
    source = full_report.sequences[0]
    values = source.model_dump(
        mode="python",
        round_trip=True,
        exclude={"schema_version", "sequence_result_id", "result_hash", "passes"},
    )
    observed = tuple(
        sorted((*source.observed_motifs, "deliberate_false_motif_control"))
    )
    values.update(
        {
            "observed_motifs": observed,
            "motif_false_positive_count": 1,
            "motif_precision": source.motif_true_positive_count
            / (source.motif_true_positive_count + 1),
        }
    )
    mutant = LongitudinalSequenceResult.create(**values)
    assert mutant.motif_false_positive_count == 1
    assert mutant.passes is False

    sequences = (mutant, *full_report.sequences[1:])
    report = LongitudinalEvaluationReport.create(
        corpus_hash=full_report.corpus_hash,
        corpus_sha256=full_report.corpus_sha256,
        template_request_hash=full_report.template_request_hash,
        full_corpus=True,
        sequences=sequences,
        ego_decision_api_absent=full_report.ego_decision_api_absent,
        projection_signal_integration_complete=all(
            item.projection_signal_integration_complete for item in sequences
        ),
        pre_governance_character_invariance=(
            full_report.pre_governance_character_invariance
        ),
    )
    assert report.motif_false_positive_count == 1
    assert report.technical_gate_passed is False
    assert report.gate_passed is False


def test_opaque_prompt_control_changes_raw_corpus_without_semantic_authority(
    tmp_path: Path,
) -> None:
    raw = json.loads(CORPUS.read_text(encoding="utf-8"))
    selected_id = raw["sequences"][0]["sequence_id"]
    raw["sequences"][0]["steps"] = [
        f"OPAQUE_C6_CONTROL_{index:02d}" for index in range(10)
    ]
    opaque_path = tmp_path / "opaque-corpus.json"
    opaque_path.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = evaluate_longitudinal_corpus(
        corpus_path=opaque_path,
        template_fixture_path=TEMPLATE,
        sequence_ids=(selected_id,),
    )
    assert report.corpus_sha256 == hashlib.sha256(opaque_path.read_bytes()).hexdigest()
    assert report.corpus_sha256 != hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    assert report.motif_gate_kind == "structured_tag_motif_stage_1"
    assert report.semantic_authority_granted is False
    assert report.sequences[0].natural_language_motif_authority_granted is False
    assert report.sequences[0].passes is True
    assert report.gate_passed is False  # a selected-row run is not the full gate


def test_corpus_reader_rejects_oversized_input(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized-corpus.json"
    oversized.write_bytes(b"{" + b"x" * MAX_LONGITUDINAL_CORPUS_BYTES)
    with pytest.raises(ValueError, match="bounded file size"):
        load_longitudinal_corpus(oversized)
