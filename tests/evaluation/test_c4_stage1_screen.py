from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rei.emocio.c4_stage1_editor import C4Stage1EditorSpec
from rei.emocio.dinov2_encoder import dinov2_base_provider_identity
from rei.emocio.longcat_turbo_editor import longcat_turbo_stage1_spec
from rei.emocio.omnigen_editor import omnigen_stage1_spec
from rei.evaluation.c4_stage1_fixture import build_c4_stage1_fixture
from rei.evaluation.c4_stage1_screen import (
    C4_STAGE1_ADDENDUM_PATH,
    C4_STAGE1_PROTOCOL_PATH,
    C4Stage1ContentPin,
    C4Stage1DinoPolicy,
    C4Stage1DocumentPin,
    C4Stage1ScreenContract,
    C4Stage1SourcePin,
    normalized_utf8_document_bytes,
)


ROOT = Path(__file__).resolve().parents[2]


def _document_pin(role: str) -> C4Stage1DocumentPin:
    relative_path = (
        C4_STAGE1_PROTOCOL_PATH if role == "protocol" else C4_STAGE1_ADDENDUM_PATH
    )
    return C4Stage1DocumentPin.create(
        role=role,
        relative_path=relative_path,
        payload=(ROOT / relative_path).read_bytes(),
    )


def _editor_spec(role: str) -> C4Stage1EditorSpec:
    if role == "primary":
        return longcat_turbo_stage1_spec(
            "4a447342e10a7b214f43818e666af6a25b8c757650f7f8b6ff4317fca0f24783"
        )
    return omnigen_stage1_spec(
        "3522d2bb368a4a304045432d6641abb69a4b73d876d8f904d36efe9458998bce"
    )


def _content_pin(kind: str, suffix: str = "fixture") -> C4Stage1ContentPin:
    digest_character = "a" if suffix == "fixture" else "b"
    return C4Stage1ContentPin(
        kind=kind,
        artifact_id=f"{kind}_{suffix}",
        artifact_hash=digest_character * 64,
        schema_version=f"rei-{kind}-fixture-v1",
    )


def _contract() -> C4Stage1ScreenContract:
    source = C4Stage1SourcePin.create(
        source_png_size_bytes=987_133,
        source_provenance_sha256=(
            "0c4f56b487213c1592ebdde0c69a0b850620bc94add1a910f321fea36107107f"
        ),
    )
    fixture = build_c4_stage1_fixture()
    dino = C4Stage1DinoPolicy.create(dinov2_base_provider_identity())
    return C4Stage1ScreenContract.create(
        protocol=_document_pin("protocol"),
        model_free_addendum=_document_pin("model_free_addendum"),
        fixture=fixture,
        source=source,
        editor_specs=(_editor_spec("primary"), _editor_spec("alternate")),
        review_schema=_content_pin("review_schema"),
        review_operator_policies=(
            _content_pin("review_operator_policy"),
            _content_pin("review_operator_policy", "alternate"),
        ),
        display_policy=_content_pin("display_policy"),
        telemetry_policy=_content_pin("telemetry_policy"),
        dino_policy=dino,
    )


def test_document_pins_normalize_line_endings_and_reject_changed_content() -> None:
    assert normalized_utf8_document_bytes(b"a\r\nb\rc\n") == b"a\nb\nc\n"
    protocol = _document_pin("protocol")
    assert protocol.normalized_utf8_sha256 == (
        "c404e8fae86a83a23c22190f318b8406333034c518a1777d82e674384ab2f241"
    )

    with pytest.raises(ValidationError, match="digest differs"):
        C4Stage1DocumentPin.create(
            role="protocol",
            relative_path=C4_STAGE1_PROTOCOL_PATH,
            payload=(ROOT / C4_STAGE1_PROTOCOL_PATH).read_bytes() + b"changed",
        )


def test_pre_output_contract_binds_both_families_and_forbids_output_authority() -> None:
    contract = _contract()

    assert tuple(item.role for item in contract.editors) == ("primary", "alternate")
    assert tuple(item.option_id for item in contract.options) == (
        "enter_circle",
        "remain_edge",
    )
    assert contract.output_artifact_ids == ()
    assert contract.sampled_memory_is_transient_maximum_proof is False
    assert contract.semantic_quality_gate_passed is False
    assert contract.production_authority_granted is False

    with pytest.raises(ValidationError):
        contract.model_copy(
            update={"sampled_whole_device_cuda_stop_mib": 40_000},
            deep=True,
        ).__class__.model_validate(
            contract.model_copy(
                update={"sampled_whole_device_cuda_stop_mib": 40_000},
                deep=True,
            ).model_dump(mode="python", round_trip=True)
        )


def test_dino_policy_is_strict_collapse_only_and_grants_no_authority() -> None:
    contract = _contract()
    policy = contract.dino_policy

    assert policy.direct_rollout_separation_epsilon == 0.01
    assert policy.pass_comparison == "strictly_greater_than"
    assert policy.method == "minimum_direct_rollout_separation"
    assert len(policy.encoder_spec_sha256) == 64
    assert policy.human_review_substitute is False
    assert policy.social_truth_inference_allowed is False
    assert policy.grounded_fact_inference_allowed is False
    assert policy.semantic_authority_granted is False
    assert policy.production_authority_granted is False

    forged = policy.model_copy(update={"encoder_spec_sha256": "0" * 64})
    with pytest.raises(ValidationError):
        C4Stage1DinoPolicy.model_validate(
            forged.model_dump(mode="python", round_trip=True)
        )
