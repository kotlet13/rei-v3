from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.engine import ReiNativeCycleRequest, ReiNativeEngine
from app.backend.rei.instinkt.effect_mapper import (
    ModelBackedEffectInferenceDisabledError,
)
from app.backend.rei.models.instinkt import (
    InstinktAssociation,
    InstinktCueEvidenceBinding,
    InstinktCueEvidenceCitation,
    InstinktProjectionObservation,
    InstinktWorld,
    instinkt_projection_memory_token,
)
from app.backend.rei.models.scene import DecisionOption, EvidenceItem, SceneEvent
from app.backend.rei.providers.native import DeterministicExecutionClock


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"


def _request() -> ReiNativeCycleRequest:
    base = ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())
    scene = SceneEvent(
        event_id="c5_engine_threat_event",
        raw_input="A synthetic physical threat permits leaving or staying.",
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="c5_engine_threat_e1",
                modality="text",
                content="A physical threat and immediate danger are visibly present.",
                grounded=True,
                source_ref="fixture:c5-engine",
                confidence=1.0,
            ),
        ),
        options=(
            DecisionOption(
                option_id="option_leave",
                label="leave",
                description="Leave and avoid the threat.",
            ),
            DecisionOption(
                option_id="option_stay",
                label="stay",
                description="Stay and approach the danger.",
            ),
        ),
        actors=("self",),
    )
    payload = base.model_dump(mode="python", round_trip=True)
    cue_text = "physical threat danger"
    cue_start = scene.evidence[0].content.casefold().index("physical threat")
    cue_citation = InstinktCueEvidenceCitation.create(
        evidence=scene.evidence[0],
        start_char=cue_start,
        end_char=cue_start + len("physical threat"),
    )
    payload.update(
        {
            "run_id": "c5_engine_rule_based",
            "ego_id": "c5_engine_ego",
            "scene": scene,
            "instinkt_effect_source": "rule_based",
            "instinkt_effect_specs": (),
            "instinkt_world": InstinktWorld.create(),
            "instinkt_associations": (),
            "instinkt_physical_cues": (cue_text,),
            "instinkt_uncertainty_cues": (),
            "instinkt_boundary_cues": (),
            "instinkt_escape_cues": (),
            "instinkt_explicit_body_cues": (),
            "instinkt_evidence_ids": ("c5_engine_threat_e1",),
            "instinkt_cue_evidence_bindings": (
                InstinktCueEvidenceBinding.create(
                    lane="physical_cues",
                    cue_class="physical_threat",
                    cue=cue_text,
                    assertion_status="asserted_positive",
                    citations=(cue_citation,),
                ),
            ),
            "symbolic_and_language_cues": None,
            "explicit_consequences": (),
            "historical_bundles": (),
        }
    )
    return ReiNativeCycleRequest.model_validate(payload)


def _run(tmp_path: Path, request: ReiNativeCycleRequest):
    engine = ReiNativeEngine.with_file_stores(
        runs_root=tmp_path / "runs",
        ego_traces_root=tmp_path / "ego",
        clock=DeterministicExecutionClock(request.started_at),
    )
    return engine.run_cycle(request), tmp_path / "runs" / request.run_id


def test_rule_based_mapper_runs_before_unchanged_body_simulator(tmp_path: Path) -> None:
    request = _request()
    result, run_root = _run(tmp_path, request)

    assert result.instinkt_effect_source == "rule_based"
    assert result.instinkt_effect_ruleset is not None
    assert len(result.instinkt_effect_predictions) == len(request.scene.options)
    assert len(result.instinkt_effect_compilations) == len(request.scene.options)
    assert not any(item.abstains for item in result.instinkt_effect_predictions)
    assert tuple(
        item.option_body_effect for item in result.instinkt_effect_compilations
    ) == result.instinkt_execution.option_effects
    assert result.instinkt_execution.conclusion.option_id == "option_leave"
    for relative in (
        "scene/instinkt_world.json",
        "instinkt/effect_source.json",
        "instinkt/effect_ruleset.json",
        "instinkt/effect_predictions.json",
        "instinkt/effect_compilations.json",
    ):
        assert (run_root / relative).is_file()
        assert relative in {
            item.relative_path for item in result.manifest.artifact_inventory
        }


def test_rule_based_second_cycle_keeps_history_out_of_current_cue_lanes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "rule_based_longitudinal"
    first_request = _request()
    first_engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego",
        clock=DeterministicExecutionClock(first_request.started_at),
    )
    first = first_engine.run_cycle(first_request)
    second_request = first_request.model_copy(
        update={
            "run_id": "c5_engine_rule_based_cycle_2",
            "started_at": first_request.started_at + timedelta(seconds=1),
            "historical_bundles": (first.native_bundle,),
        }
    )
    second_engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego",
        clock=DeterministicExecutionClock(second_request.started_at),
    )
    second = second_engine.run_cycle(second_request)

    assert all(not item.abstains for item in first.instinkt_effect_predictions)
    assert all(not item.abstains for item in second.instinkt_effect_predictions)
    assert second.prior_trace == first.ego_trace
    assert second.prior_projections == first.projections
    assert second.instinkt_packet.previous_instinkt_projection_ids == (
        first.projections.instinkt.projection_id,
    )
    assert second.instinkt_packet.previous_instinkt_projection_hashes == (
        first.projections.instinkt.projection_hash,
    )
    for lane in (
        "physical_cues",
        "uncertainty_cues",
        "trust_cues",
        "boundary_cues",
        "attachment_cues",
        "scarcity_cues",
        "escape_cues",
        "explicit_body_cues",
    ):
        assert getattr(second.instinkt_packet, lane) == getattr(
            second_request, f"instinkt_{lane}"
        )

    history_records = second.instinkt_execution.associations
    projection_token = instinkt_projection_memory_token(
        first.projections.instinkt.projection_id,
        first.projections.instinkt.projection_hash,
    )
    assert history_records
    assert all(
        isinstance(item, InstinktProjectionObservation)
        and item.source_projection_id == first.projections.instinkt.projection_id
        and item.source_projection_hash == first.projections.instinkt.projection_hash
        and projection_token in item.cue_signature
        for item in history_records
    )
    assert all(
        rollout.association_matches
        and all(
            match.source_record_kind == "projection_observation"
            and projection_token in match.overlap_tokens
            for match in rollout.association_matches
        )
        for rollout in second.instinkt_execution.rollouts
    )
    assert len(second.ego_trace.measures) == 2


def test_model_backed_stub_fails_explicitly_even_without_options(
    tmp_path: Path,
) -> None:
    base = _request()
    payload = base.model_dump(mode="python", round_trip=True)
    payload.update(
        {
            "run_id": "c5_engine_model_stub_no_options",
            "scene": base.scene.model_copy(update={"options": ()}),
            "instinkt_effect_source": "model_backed",
            "instinkt_effect_specs": (),
        }
    )
    request = ReiNativeCycleRequest.model_validate(payload)

    with pytest.raises(
        ModelBackedEffectInferenceDisabledError,
        match="disabled C5 stub",
    ):
        _run(tmp_path, request)


def test_rule_based_engine_uses_request_scoped_typed_associations(
    tmp_path: Path,
) -> None:
    base = _request()
    association = InstinktAssociation(
        association_id="c5_engine_threat_association",
        cue_signature=("physical threat",),
        body_state_before=base.body_state,
        felt_intensity=0.8,
        protected_target="virtual bodily integrity",
        experienced_loss="threat harm",
        action_taken="leave",
        outcome="safe exit",
        trust_delta=0.0,
        attachment_delta=0.0,
        boundary_delta=0.0,
        decay=0.0,
    )
    payload = base.model_dump(mode="python", round_trip=True)
    payload.update(
        {
            "run_id": "c5_engine_typed_association",
            "instinkt_world": InstinktWorld.create(
                associations=(association.association_id,)
            ),
            "instinkt_associations": (association,),
        }
    )
    request = ReiNativeCycleRequest.model_validate(payload)

    result, _ = _run(tmp_path, request)
    threat_evidence = tuple(
        evidence
        for prediction in result.instinkt_effect_predictions
        for evidence in prediction.evidence
        if evidence.cue_class == "physical_threat"
    )

    assert threat_evidence
    assert all(
        item.association_ids == (association.association_id,)
        and item.association_basis == "matched_association"
        and item.association_matches[0].association_hash
        == association.content_hash()
        for item in threat_evidence
    )


@pytest.mark.parametrize("phantom_in_world", (False, True))
def test_automatic_request_requires_exact_materialized_association_closure(
    phantom_in_world: bool,
) -> None:
    base = _request()
    association = InstinktAssociation(
        association_id="c5_engine_materialized_association",
        cue_signature=("physical threat",),
        body_state_before=base.body_state,
        felt_intensity=0.8,
        protected_target="virtual bodily integrity",
        experienced_loss="threat harm",
        action_taken="leave",
        outcome="safe exit",
        trust_delta=0.0,
        attachment_delta=0.0,
        boundary_delta=0.0,
        decay=0.0,
    )
    payload = base.model_dump(mode="python", round_trip=True)
    payload.update(
        {
            "run_id": (
                "c5_engine_phantom_association"
                if phantom_in_world
                else "c5_engine_unindexed_association"
            ),
            "instinkt_world": InstinktWorld.create(
                associations=(
                    ("phantom_association",)
                    if phantom_in_world
                    else ()
                )
            ),
            "instinkt_associations": (() if phantom_in_world else (association,)),
        }
    )

    with pytest.raises(ValidationError, match="exact materialized record closure"):
        ReiNativeCycleRequest.model_validate(payload)


def test_engine_revalidates_model_copy_before_any_store_write(tmp_path: Path) -> None:
    valid = _request()
    bypassed = valid.model_copy(
        update={
            "run_id": "c5_engine_model_copy_bypass",
            "instinkt_world": InstinktWorld.create(
                associations=("phantom_association",)
            ),
        }
    )
    runs_root = tmp_path / "runs"
    ego_root = tmp_path / "ego"
    engine = ReiNativeEngine.with_file_stores(
        runs_root=runs_root,
        ego_traces_root=ego_root,
        clock=DeterministicExecutionClock(bypassed.started_at),
    )

    with pytest.raises(ValidationError, match="exact materialized record closure"):
        engine.run_cycle(bypassed)

    assert tuple(runs_root.rglob("*")) == ()
    assert tuple(ego_root.rglob("*")) == ()


def test_engine_rejects_model_copy_with_forged_learned_association_id(
    tmp_path: Path,
) -> None:
    valid = _request()
    association = InstinktAssociation(
        association_id="legacy_materialized_association",
        cue_signature=("physical threat danger",),
        body_state_before=valid.body_state,
        felt_intensity=0.8,
        protected_target="virtual bodily integrity",
        experienced_loss="threat harm",
        action_taken="leave",
        outcome="safe exit",
        trust_delta=0.0,
        attachment_delta=0.0,
        boundary_delta=0.0,
        decay=0.0,
    )
    forged = association.model_copy(
        update={"association_id": f"instinkt_association_{'0' * 32}"}
    )
    bypassed = valid.model_copy(
        update={
            "run_id": "c5_engine_forged_association_id",
            "instinkt_world": InstinktWorld.create(
                associations=(forged.association_id,)
            ),
            "instinkt_associations": (forged,),
        }
    )
    runs_root = tmp_path / "runs"
    ego_root = tmp_path / "ego"
    engine = ReiNativeEngine.with_file_stores(
        runs_root=runs_root,
        ego_traces_root=ego_root,
        clock=DeterministicExecutionClock(bypassed.started_at),
    )

    with pytest.raises(ValidationError, match="content-addressed Instinkt association"):
        engine.run_cycle(bypassed)

    assert tuple(runs_root.rglob("*")) == ()
    assert tuple(ego_root.rglob("*")) == ()


def test_rule_based_optionless_scene_preserves_native_no_options_abstention(
    tmp_path: Path,
) -> None:
    base = _request()
    payload = base.model_dump(mode="python", round_trip=True)
    payload.update(
        {
            "run_id": "c5_engine_rule_based_no_options",
            "scene": base.scene.model_copy(update={"options": ()}),
            "instinkt_effect_specs": (),
        }
    )
    request = ReiNativeCycleRequest.model_validate(payload)

    result, run_root = _run(tmp_path, request)

    assert result.instinkt_execution.conclusion.option_id is None
    assert result.instinkt_execution.conclusion.abstains is True
    assert result.instinkt_execution.rollouts == ()
    assert result.instinkt_effect_predictions == ()
    assert result.instinkt_effect_compilations == ()
    assert (run_root / "instinkt/effect_predictions.json").read_text(
        encoding="utf-8"
    ) == "[]"


def test_request_rejects_options_above_instinkt_limit_before_mapper() -> None:
    base = _request()
    payload = base.model_dump(mode="python", round_trip=True)
    payload.update(
        {
            "run_id": "c5_engine_too_many_options",
            "scene": base.scene.model_copy(
                update={
                    "options": tuple(
                        DecisionOption(
                            option_id=f"bounded_option_{index}",
                            label=f"option {index}",
                            description="One bounded synthetic option.",
                        )
                        for index in range(base.instinkt_config.max_options + 1)
                    )
                }
            ),
        }
    )

    with pytest.raises(ValidationError, match="simulation limit"):
        ReiNativeCycleRequest.model_validate(payload)
