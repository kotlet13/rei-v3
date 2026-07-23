"""Content-addressed C4 Stage 1 screen and DINO bridge contracts.

This module is intentionally model-free.  It freezes every input and policy
needed by the bounded editor screen before a candidate output can exist, and it
defines the narrow DINOv2 collapse-detector result without granting human,
semantic, grounded-evidence or production authority.
"""

from __future__ import annotations

import base64
import hashlib
import math
from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from ..emocio.c4_stage1_editor import (
    C4_STAGE1_OPTION_SCENE_IDS,
    C4_STAGE1_OPTION_SEEDS,
    C4Stage1EditorSpec,
)
from ..emocio.dinov2_encoder import (
    dinov2_base_encoding_spec,
    dinov2_base_provider_identity,
)
from ..emocio.vector_encoding import verified_float32_le_vector
from ..emocio.longcat_turbo_editor import longcat_turbo_stage1_spec
from ..emocio.omnigen_editor import omnigen_stage1_spec
from ..ids import content_id
from ..models.common import (
    ArtifactRelativePath,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
)
from ..models.provider import ProviderIdentity
from ..models.emocio import ImageArtifact
from ..providers.protocols import StoredArtifact, VerifiedImageEncoding
from .c4_stage1_fixture import C4Stage1Fixture, C4Stage1PromptBinding


C4_STAGE1_PROTOCOL_PATH = (
    "Docs/evals/semantic_lab_v1/c4_visual_remediation_protocol_2026-07-15.md"
)
C4_STAGE1_ADDENDUM_PATH = (
    "Docs/evals/semantic_lab_v1/c4_stage1_model_free_integration_addendum_2026-07-15.md"
)
C4_STAGE1_PROTOCOL_SHA256 = (
    "c404e8fae86a83a23c22190f318b8406333034c518a1777d82e674384ab2f241"
)
C4_STAGE1_ADDENDUM_SHA256 = (
    "1a7b26be4b484925ba319f3c6ec095a8dec6b3ce17dcbaf186b5eb2aa3324809"
)
C4_STAGE1_DINO_EPSILON = 0.01
C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256 = (
    "786481f81ca90d17eada5cd387835e457f1e531e93ec38a7671368dbb8249ba1"
)
C4_STAGE1_PRIMARY_SNAPSHOT_MANIFEST_PATH = (
    "Docs/evals/semantic_lab_v1/c4-stage1-preflight-2026-07-15/"
    "longcat_turbo_snapshot_manifest.json"
)
C4_STAGE1_ALTERNATE_SNAPSHOT_MANIFEST_PATH = (
    "Docs/evals/semantic_lab_v1/c4-stage1-preflight-2026-07-15/"
    "omnigen_snapshot_manifest.json"
)


def normalized_utf8_document_bytes(value: bytes) -> bytes:
    """Return the portable LF-normalized bytes used by a document pin."""

    if type(value) is not bytes:
        raise TypeError("Document payload must be immutable bytes")
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Pinned document must be valid UTF-8") from exc
    if "\x00" in text:
        raise ValueError("Pinned document cannot contain NUL")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _dino_round_score(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("C4 Stage 1 DINO comparison produced a non-finite score")
    return round(min(1.0, max(0.0, value)), 12)


def _dino_separation_from_vector_bytes(
    values: tuple[bytes, bytes],
) -> float:
    if type(values) is not tuple or len(values) != 2:
        raise ValueError("C4 Stage 1 DINO result requires exactly two vectors")
    decoded = tuple(
        verified_float32_le_vector(value, expected_dimensions=768)[0]
        for value in values
    )
    left, right = decoded
    left_scale = max(abs(value) for value in left)
    right_scale = max(abs(value) for value in right)
    if left_scale == 0.0 or right_scale == 0.0:
        raise ValueError("C4 Stage 1 DINO comparison forbids zero vectors")
    scaled_left = tuple(value / left_scale for value in left)
    scaled_right = tuple(value / right_scale for value in right)
    numerator = math.fsum(
        left_value * right_value
        for left_value, right_value in zip(scaled_left, scaled_right, strict=True)
    )
    denominator = math.sqrt(
        math.fsum(value * value for value in scaled_left)
    ) * math.sqrt(math.fsum(value * value for value in scaled_right))
    cosine = round(min(1.0, max(-1.0, numerator / denominator)), 12)
    similarity = _dino_round_score((cosine + 1.0) / 2.0)
    return _dino_round_score(1.0 - similarity)


def _decode_dino_vector_bundle(values: tuple[str, str]) -> tuple[bytes, bytes]:
    decoded: list[bytes] = []
    for value in values:
        try:
            payload = base64.b64decode(value.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError(
                "C4 Stage 1 DINO vector bundle is not canonical base64"
            ) from exc
        if base64.b64encode(payload).decode("ascii") != value:
            raise ValueError("C4 Stage 1 DINO vector bundle is not canonical base64")
        verified_float32_le_vector(payload, expected_dimensions=768)
        decoded.append(payload)
    return decoded[0], decoded[1]


class C4Stage1DocumentPin(FrozenArtifactModel):
    """Portable normalized-content pin for one controlling repository document."""

    schema_version: Literal["rei-c4-stage1-document-pin-v1"] = (
        "rei-c4-stage1-document-pin-v1"
    )
    document_pin_id: NonEmptyId
    role: Literal["protocol", "model_free_addendum"]
    relative_path: ArtifactRelativePath
    normalized_utf8_sha256: HashDigest
    normalized_size_bytes: Annotated[int, Field(gt=0, le=4 * 1024 * 1024)]
    normalization_policy: Literal["utf8-lf-v1"] = "utf8-lf-v1"

    @classmethod
    def create(
        cls,
        *,
        role: Literal["protocol", "model_free_addendum"],
        relative_path: str,
        payload: bytes,
    ) -> C4Stage1DocumentPin:
        normalized = normalized_utf8_document_bytes(payload)
        body = {
            "schema_version": "rei-c4-stage1-document-pin-v1",
            "role": role,
            "relative_path": relative_path,
            "normalized_utf8_sha256": hashlib.sha256(normalized).hexdigest(),
            "normalized_size_bytes": len(normalized),
            "normalization_policy": "utf8-lf-v1",
        }
        return cls(
            document_pin_id=content_id("c4_stage1_document_pin", body),
            **body,
        )

    @model_validator(mode="after")
    def validate_pin(self) -> Self:
        expected_path = {
            "protocol": C4_STAGE1_PROTOCOL_PATH,
            "model_free_addendum": C4_STAGE1_ADDENDUM_PATH,
        }[self.role]
        expected_digest = {
            "protocol": C4_STAGE1_PROTOCOL_SHA256,
            "model_free_addendum": C4_STAGE1_ADDENDUM_SHA256,
        }[self.role]
        if self.relative_path != expected_path:
            raise ValueError("Stage 1 document path differs from its frozen role")
        if self.normalized_utf8_sha256 != expected_digest:
            raise ValueError("Stage 1 document digest differs from its frozen pin")
        expected_id = content_id(
            "c4_stage1_document_pin",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"document_pin_id"},
            ),
        )
        if self.document_pin_id != expected_id:
            raise ValueError("Stage 1 document pin ID differs from content")
        return self


class C4Stage1ContentPin(FrozenModel):
    """Typed reference to one separately content-addressed policy artifact."""

    kind: Literal[
        "review_schema",
        "review_operator_policy",
        "display_policy",
        "review_runtime",
        "review_service_readiness",
        "telemetry_policy",
    ]
    artifact_id: NonEmptyId
    artifact_hash: HashDigest
    schema_version: NonEmptyId


class C4Stage1SourcePin(FrozenArtifactModel):
    """Frozen current-scene source and prompt-profile identity."""

    schema_version: Literal["rei-c4-stage1-source-pin-v1"] = (
        "rei-c4-stage1-source-pin-v1"
    )
    source_pin_id: NonEmptyId
    current_artifact_id: Literal["image_d1e97e56432b23038b8a01f6fdc24d42"]
    current_scene_id: Literal["visual_scene_2caca3e7e6424d6bafa3b365d935c4c5"]
    current_scene_hash: Literal[
        "c795bdd82b0b01ba54f453b7881a636de5ff118f692e250af5b6d32c4ddb5a65"
    ]
    source_png_sha256: Literal[
        "72c9fec75d838f0db9a9abc71cbd86c4f4e637c8f54f05c0ea629e12e0f6da58"
    ]
    source_png_size_bytes: Literal[987133]
    source_width: Literal[1024] = 1024
    source_height: Literal[768] = 768
    source_provenance_sha256: Literal[
        "0c4f56b487213c1592ebdde0c69a0b850620bc94add1a910f321fea36107107f"
    ]
    root_seed: Literal[424240] = 424240
    prompt_language: Literal["en"] = "en"
    prompt_style_id: Literal["documentary_cinematic_v1"] = "documentary_cinematic_v1"
    prompt_profile_hash: Literal[
        "26908b02adc969b1c894b46f69bbd1c81a92464cc62b1e74b4217d9edd06a3c8"
    ]
    generated_image_is_external_evidence: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        source_png_size_bytes: int,
        source_provenance_sha256: str,
    ) -> C4Stage1SourcePin:
        body = {
            "schema_version": "rei-c4-stage1-source-pin-v1",
            "current_artifact_id": "image_d1e97e56432b23038b8a01f6fdc24d42",
            "current_scene_id": "visual_scene_2caca3e7e6424d6bafa3b365d935c4c5",
            "current_scene_hash": (
                "c795bdd82b0b01ba54f453b7881a636de5ff118f692e250af5b6d32c4ddb5a65"
            ),
            "source_png_sha256": (
                "72c9fec75d838f0db9a9abc71cbd86c4f4e637c8f54f05c0ea629e12e0f6da58"
            ),
            "source_png_size_bytes": source_png_size_bytes,
            "source_width": 1024,
            "source_height": 768,
            "source_provenance_sha256": source_provenance_sha256,
            "root_seed": 424240,
            "prompt_language": "en",
            "prompt_style_id": "documentary_cinematic_v1",
            "prompt_profile_hash": (
                "26908b02adc969b1c894b46f69bbd1c81a92464cc62b1e74b4217d9edd06a3c8"
            ),
            "generated_image_is_external_evidence": False,
        }
        return cls(source_pin_id=content_id("c4_stage1_source_pin", body), **body)

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        expected = content_id(
            "c4_stage1_source_pin",
            self.model_dump(mode="python", round_trip=True, exclude={"source_pin_id"}),
        )
        if self.source_pin_id != expected:
            raise ValueError("Stage 1 source pin ID differs from content")
        return self


class C4Stage1OptionInput(FrozenArtifactModel):
    """Exact base prompt and scene/seed binding shared by both providers."""

    schema_version: Literal["rei-c4-stage1-option-input-v1"] = (
        "rei-c4-stage1-option-input-v1"
    )
    option_input_id: NonEmptyId
    option_id: Literal["enter_circle", "remain_edge"]
    scene_spec_id: NonEmptyId
    scene_spec_hash: HashDigest
    derived_seed: Annotated[int, Field(ge=0, le=0x7FFFFFFFFFFFFFFF)]
    prompt_policy: Literal["c4_editor_compact_v1"] = "c4_editor_compact_v1"
    base_prompt: NonEmptyText
    base_prompt_sha256: HashDigest
    base_prompt_utf8_bytes: Annotated[int, Field(gt=0, le=64 * 1024)]
    profile_hash: Literal[
        "26908b02adc969b1c894b46f69bbd1c81a92464cc62b1e74b4217d9edd06a3c8"
    ]

    @classmethod
    def create(
        cls,
        *,
        option_id: Literal["enter_circle", "remain_edge"],
        scene_spec_id: str,
        scene_spec_hash: str,
        derived_seed: int,
        base_prompt: str,
    ) -> C4Stage1OptionInput:
        encoded = base_prompt.encode("utf-8")
        body = {
            "schema_version": "rei-c4-stage1-option-input-v1",
            "option_id": option_id,
            "scene_spec_id": scene_spec_id,
            "scene_spec_hash": scene_spec_hash,
            "derived_seed": derived_seed,
            "prompt_policy": "c4_editor_compact_v1",
            "base_prompt": base_prompt,
            "base_prompt_sha256": hashlib.sha256(encoded).hexdigest(),
            "base_prompt_utf8_bytes": len(encoded),
            "profile_hash": (
                "26908b02adc969b1c894b46f69bbd1c81a92464cc62b1e74b4217d9edd06a3c8"
            ),
        }
        return cls(option_input_id=content_id("c4_stage1_option_input", body), **body)

    @classmethod
    def from_prompt_binding(
        cls,
        binding: C4Stage1PromptBinding,
    ) -> C4Stage1OptionInput:
        binding = C4Stage1PromptBinding.model_validate(
            binding.model_dump(mode="python", round_trip=True)
        )
        return cls.create(
            option_id=binding.option_id,
            scene_spec_id=binding.scene.scene_id,
            scene_spec_hash=binding.scene_hash,
            derived_seed=binding.derived_seed,
            base_prompt=binding.prompt,
        )

    @model_validator(mode="after")
    def validate_input(self) -> Self:
        expected_scene = {
            "enter_circle": (
                "visual_scene_acbc451d7b30336076e5c1e5bd31e02b",
                "7e9b9f91e0ea2f0504548d178b36ccbf0bbc8664b7e38b8ab4ea4e9be960ea57",
                1366714956115613163,
                "3c046f45c9c66bc35e6c1b4890f24cc021e6c692d5ca6b7288951db6d2c54cba",
            ),
            "remain_edge": (
                "visual_scene_12e01b7dc48013135871ba28868f8180",
                "48af410ba6f01adf5540044dbbe6d1bad4e3e08ddeb60ef772f7924a49e39272",
                297232311612386773,
                "a92224abe970e7deafef346085bc8751d76aea1d484f4268c66131a05c25c25e",
            ),
        }[self.option_id]
        if (
            self.scene_spec_id,
            self.scene_spec_hash,
            self.derived_seed,
            self.base_prompt_sha256,
        ) != expected_scene:
            raise ValueError(
                "Stage 1 option scene, seed or prompt differs from protocol"
            )
        encoded = self.base_prompt.encode("utf-8")
        if self.base_prompt_utf8_bytes != len(encoded) or (
            self.base_prompt_sha256 != hashlib.sha256(encoded).hexdigest()
        ):
            raise ValueError("Stage 1 base prompt bytes differ from their pin")
        expected_id = content_id(
            "c4_stage1_option_input",
            self.model_dump(
                mode="python", round_trip=True, exclude={"option_input_id"}
            ),
        )
        if self.option_input_id != expected_id:
            raise ValueError("Stage 1 option input ID differs from content")
        return self


class C4Stage1EditorPin(FrozenModel):
    """Top-level binding to one complete editor spec and snapshot inventory."""

    role: Literal["primary", "alternate"]
    spec_id: NonEmptyId
    spec_hash: HashDigest
    repo_id: NonEmptyId
    revision: NonEmptyId
    snapshot_manifest_relative_path: ArtifactRelativePath
    snapshot_manifest_sha256: HashDigest
    snapshot_file_count: Annotated[int, Field(gt=0)]
    snapshot_total_bytes: Annotated[int, Field(gt=0)]

    @classmethod
    def from_spec(cls, spec: C4Stage1EditorSpec) -> C4Stage1EditorPin:
        if spec.editor_role not in {"primary", "alternate"}:
            raise ValueError("Stage 1 screen forbids test editor specs")
        expected = (
            longcat_turbo_stage1_spec(spec.snapshot_manifest_sha256)
            if spec.editor_role == "primary"
            else omnigen_stage1_spec(spec.snapshot_manifest_sha256)
        )
        if spec != expected:
            raise ValueError("Stage 1 editor spec differs from its exact adapter")
        return cls(
            role=spec.editor_role,
            spec_id=spec.spec_id,
            spec_hash=spec.content_hash(),
            repo_id=spec.repo_id,
            revision=spec.revision,
            snapshot_manifest_relative_path=(
                C4_STAGE1_PRIMARY_SNAPSHOT_MANIFEST_PATH
                if spec.editor_role == "primary"
                else C4_STAGE1_ALTERNATE_SNAPSHOT_MANIFEST_PATH
            ),
            snapshot_manifest_sha256=spec.snapshot_manifest_sha256,
            snapshot_file_count=spec.snapshot_file_count,
            snapshot_total_bytes=spec.snapshot_total_bytes,
        )

    @model_validator(mode="after")
    def validate_editor_pin(self) -> Self:
        expected_spec = (
            longcat_turbo_stage1_spec()
            if self.role == "primary"
            else omnigen_stage1_spec()
        )
        expected_path = (
            C4_STAGE1_PRIMARY_SNAPSHOT_MANIFEST_PATH
            if self.role == "primary"
            else C4_STAGE1_ALTERNATE_SNAPSHOT_MANIFEST_PATH
        )
        if (
            self.spec_id,
            self.spec_hash,
            self.repo_id,
            self.revision,
            self.snapshot_manifest_relative_path,
            self.snapshot_manifest_sha256,
            self.snapshot_file_count,
            self.snapshot_total_bytes,
        ) != (
            expected_spec.spec_id,
            expected_spec.content_hash(),
            expected_spec.repo_id,
            expected_spec.revision,
            expected_path,
            expected_spec.snapshot_manifest_sha256,
            expected_spec.snapshot_file_count,
            expected_spec.snapshot_total_bytes,
        ):
            raise ValueError("Stage 1 editor pin differs from its exact provider")
        return self


class C4Stage1DinoPolicy(FrozenArtifactModel):
    """Pinned collapse-detector policy; never a human or grounded-fact judge."""

    schema_version: Literal["rei-c4-stage1-dino-policy-v1"] = (
        "rei-c4-stage1-dino-policy-v1"
    )
    dino_policy_id: NonEmptyId
    encoder: ProviderIdentity
    encoder_snapshot_manifest_sha256: Literal[
        "786481f81ca90d17eada5cd387835e457f1e531e93ec38a7671368dbb8249ba1"
    ] = C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256
    encoder_spec_sha256: HashDigest
    direct_rollout_separation_epsilon: Literal[0.01] = C4_STAGE1_DINO_EPSILON
    pass_comparison: Literal["strictly_greater_than"] = "strictly_greater_than"
    method: Literal["minimum_direct_rollout_separation"] = (
        "minimum_direct_rollout_separation"
    )
    human_review_substitute: Literal[False] = False
    social_truth_inference_allowed: Literal[False] = False
    grounded_fact_inference_allowed: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(cls, encoder: ProviderIdentity) -> C4Stage1DinoPolicy:
        encoder_spec_sha256 = dinov2_base_encoding_spec(
            snapshot_manifest_sha256=(C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256),
            device="cuda",
        ).content_hash()
        body = {
            "schema_version": "rei-c4-stage1-dino-policy-v1",
            "encoder": encoder,
            "encoder_snapshot_manifest_sha256": (
                C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256
            ),
            "encoder_spec_sha256": encoder_spec_sha256,
            "direct_rollout_separation_epsilon": C4_STAGE1_DINO_EPSILON,
            "pass_comparison": "strictly_greater_than",
            "method": "minimum_direct_rollout_separation",
            "human_review_substitute": False,
            "social_truth_inference_allowed": False,
            "grounded_fact_inference_allowed": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(dino_policy_id=content_id("c4_stage1_dino_policy", body), **body)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        expected_spec_sha256 = dinov2_base_encoding_spec(
            snapshot_manifest_sha256=(C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256),
            device="cuda",
        ).content_hash()
        if (
            self.encoder != dinov2_base_provider_identity()
            or self.encoder_spec_sha256 != expected_spec_sha256
        ):
            raise ValueError("Stage 1 DINO policy differs from pinned DINOv2 Base")
        expected = content_id(
            "c4_stage1_dino_policy",
            self.model_dump(mode="python", round_trip=True, exclude={"dino_policy_id"}),
        )
        if self.dino_policy_id != expected:
            raise ValueError("Stage 1 DINO policy ID differs from content")
        return self


class C4Stage1ScreenContract(FrozenArtifactModel):
    """Complete pre-output contract for exactly the bounded two-family screen."""

    schema_version: Literal["rei-c4-stage1-screen-contract-v2"] = (
        "rei-c4-stage1-screen-contract-v2"
    )
    screen_contract_id: NonEmptyId
    protocol: C4Stage1DocumentPin
    model_free_addendum: C4Stage1DocumentPin
    fixture: C4Stage1Fixture
    source: C4Stage1SourcePin
    options: tuple[C4Stage1OptionInput, C4Stage1OptionInput]
    editors: tuple[C4Stage1EditorPin, C4Stage1EditorPin]
    provider_execution_order: tuple[Literal["primary"], Literal["alternate"]] = (
        "primary",
        "alternate",
    )
    review_schema: C4Stage1ContentPin
    review_operator_policies: tuple[C4Stage1ContentPin, C4Stage1ContentPin]
    display_policy: C4Stage1ContentPin
    review_runtime: C4Stage1ContentPin
    review_service_readiness: C4Stage1ContentPin
    telemetry_policy: C4Stage1ContentPin
    dino_policy: C4Stage1DinoPolicy
    per_option_hard_timeout_seconds: Literal[180.0] = 180.0
    per_member_hard_timeout_seconds: Literal[420.0] = 420.0
    sampled_whole_device_cuda_stop_mib: Literal[31500] = 31_500
    sampled_memory_is_transient_maximum_proof: Literal[False] = False
    output_artifact_ids: tuple[NonEmptyId, ...] = ()
    output_count: Literal[0] = 0
    human_review_required: Literal[True] = True
    immutable_display_receipt_required: Literal[True] = True
    durable_telemetry_required: Literal[True] = True
    no_fallback: Literal[True] = True
    stage2_expansion_authorized: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        protocol: C4Stage1DocumentPin,
        model_free_addendum: C4Stage1DocumentPin,
        fixture: C4Stage1Fixture,
        source: C4Stage1SourcePin,
        editor_specs: tuple[C4Stage1EditorSpec, C4Stage1EditorSpec],
        review_schema: C4Stage1ContentPin,
        review_operator_policies: tuple[
            C4Stage1ContentPin,
            C4Stage1ContentPin,
        ],
        display_policy: C4Stage1ContentPin,
        review_runtime: C4Stage1ContentPin,
        review_service_readiness: C4Stage1ContentPin,
        telemetry_policy: C4Stage1ContentPin,
        dino_policy: C4Stage1DinoPolicy,
    ) -> C4Stage1ScreenContract:
        body: dict[str, Any] = {
            "schema_version": "rei-c4-stage1-screen-contract-v2",
            "protocol": protocol,
            "model_free_addendum": model_free_addendum,
            "fixture": fixture,
            "source": source,
            "options": tuple(
                C4Stage1OptionInput.from_prompt_binding(item)
                for item in fixture.prompts
            ),
            "editors": tuple(
                C4Stage1EditorPin.from_spec(item) for item in editor_specs
            ),
            "provider_execution_order": ("primary", "alternate"),
            "review_schema": review_schema,
            "review_operator_policies": review_operator_policies,
            "display_policy": display_policy,
            "review_runtime": review_runtime,
            "review_service_readiness": review_service_readiness,
            "telemetry_policy": telemetry_policy,
            "dino_policy": dino_policy,
            "per_option_hard_timeout_seconds": 180.0,
            "per_member_hard_timeout_seconds": 420.0,
            "sampled_whole_device_cuda_stop_mib": 31_500,
            "sampled_memory_is_transient_maximum_proof": False,
            "output_artifact_ids": (),
            "output_count": 0,
            "human_review_required": True,
            "immutable_display_receipt_required": True,
            "durable_telemetry_required": True,
            "no_fallback": True,
            "stage2_expansion_authorized": False,
            "semantic_quality_gate_passed": False,
            "generated_images_are_external_evidence": False,
            "production_authority_granted": False,
        }
        return cls(
            screen_contract_id=content_id("c4_stage1_screen_contract", body),
            **body,
        )

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.protocol.role != "protocol" or (
            self.model_free_addendum.role != "model_free_addendum"
        ):
            raise ValueError("Stage 1 document roles are incomplete")
        if tuple(item.option_id for item in self.options) != (
            "enter_circle",
            "remain_edge",
        ):
            raise ValueError("Stage 1 option order differs from the frozen protocol")
        fixture = C4Stage1Fixture.model_validate(
            self.fixture.model_dump(mode="python", round_trip=True)
        )
        if (
            tuple(
                C4Stage1OptionInput.from_prompt_binding(item)
                for item in fixture.prompts
            )
            != self.options
        ):
            raise ValueError("Stage 1 option inputs differ from the frozen fixture")
        if (
            self.source.current_artifact_id != fixture.source_image.image_id
            or self.source.current_scene_id != fixture.current_scene.scene_id
            or self.source.current_scene_hash != fixture.current_scene_hash
            or self.source.source_png_sha256 != fixture.source_image.content_sha256
            or self.source.root_seed != fixture.root_seed
            or self.source.prompt_profile_hash != fixture.prompt_profile_hash
        ):
            raise ValueError("Stage 1 source pin differs from the frozen fixture")
        if tuple(item.role for item in self.editors) != (
            "primary",
            "alternate",
        ):
            raise ValueError("Stage 1 provider order differs from the frozen protocol")
        expected_policy_kinds = (
            (self.review_schema.kind, "review_schema"),
            *(
                (policy.kind, "review_operator_policy")
                for policy in self.review_operator_policies
            ),
            (self.display_policy.kind, "display_policy"),
            (self.review_runtime.kind, "review_runtime"),
            (
                self.review_service_readiness.kind,
                "review_service_readiness",
            ),
            (self.telemetry_policy.kind, "telemetry_policy"),
        )
        if any(actual != expected for actual, expected in expected_policy_kinds):
            raise ValueError("Stage 1 policy reference has the wrong role")
        if len({item.artifact_id for item in self.review_operator_policies}) != 2 or (
            len({item.artifact_hash for item in self.review_operator_policies}) != 2
        ):
            raise ValueError(
                "Stage 1 requires one distinct one-time operator policy per provider"
            )
        if self.output_artifact_ids or self.output_count != 0:
            raise ValueError(
                "Pre-output Stage 1 contract cannot bind candidate outputs"
            )
        expected = content_id(
            "c4_stage1_screen_contract",
            self.model_dump(
                mode="python", round_trip=True, exclude={"screen_contract_id"}
            ),
        )
        if self.screen_contract_id != expected:
            raise ValueError("Stage 1 screen contract ID differs from content")
        return self


class C4Stage1DinoOptionEvidence(FrozenModel):
    option_id: Literal["enter_circle", "remain_edge"]
    prepared_worker_id: NonEmptyId
    prepared_worker_sha256: HashDigest
    worker_request_id: NonEmptyId
    worker_request_sha256: HashDigest
    candidate_receipt_id: NonEmptyId
    candidate_receipt_sha256: HashDigest
    candidate_staged_output_storage: StoredArtifact
    image: ImageArtifact
    image_artifact_id: NonEmptyId
    image_sha256: HashDigest
    image_width: Literal[1024] = 1024
    image_height: Literal[768] = 768
    embedding_artifact_id: NonEmptyId
    embedding_artifact_hash: HashDigest
    vector_sha256: HashDigest
    encoding: VerifiedImageEncoding

    @model_validator(mode="after")
    def validate_encoding_lineage(self) -> Self:
        encoding = VerifiedImageEncoding.model_validate(
            self.encoding.model_dump(mode="python", round_trip=True)
        )
        image = ImageArtifact.model_validate(
            self.image.model_dump(mode="python", round_trip=True)
        )
        staged = StoredArtifact.model_validate(
            self.candidate_staged_output_storage.model_dump(
                mode="python", round_trip=True
            )
        )
        encoding.request.validate_image(image)
        option_index = ("enter_circle", "remain_edge").index(self.option_id)
        expected_spec = dinov2_base_encoding_spec(
            snapshot_manifest_sha256=(C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256),
            device="cuda",
        )
        if (
            encoding.call.provider != dinov2_base_provider_identity()
            or encoding.request.provider != dinov2_base_provider_identity()
            or image.image_id
            != content_id(
                "image",
                {
                    "request_id": image.request_id,
                    "content_sha256": image.content_sha256,
                },
            )
            or image.image_id != self.image_artifact_id
            or image.content_sha256 != self.image_sha256
            or image.media_type != "image/png"
            or (image.width, image.height) != (self.image_width, self.image_height)
            or image.source_spec_id != C4_STAGE1_OPTION_SCENE_IDS[option_index]
            or image.seed != C4_STAGE1_OPTION_SEEDS[option_index]
            or image.grounded is not False
            or image.path != staged.relative_path
            or staged.content_sha256 != self.image_sha256
            or staged.size_bytes <= 0
            or image.generated_only_elements
            != ("c4_stage1_unverified_generated_candidate",)
            or image.grounded_mask_path is not None
            or encoding.image_id != self.image_artifact_id
            or encoding.request.image_content_sha256 != self.image_sha256
            or (encoding.request.width, encoding.request.height)
            != (self.image_width, self.image_height)
            or encoding.dimensions != 768
            or encoding.request.spec != expected_spec
            or encoding.encoding_id != self.embedding_artifact_id
            or encoding.content_hash() != self.embedding_artifact_hash
            or encoding.vector_hash != self.vector_sha256
            or encoding.call_spec.seed != 0
            or encoding.call_spec.fallback_policy.mode != "none"
            or encoding.call.status != "succeeded"
            or encoding.call.primary_status != "succeeded"
            or encoding.call.fallback is not None
        ):
            raise ValueError(
                "C4 Stage 1 DINO evidence differs from verified DINOv2 lineage"
            )
        return self


class C4Stage1DinoPairResult(FrozenArtifactModel):
    """Narrow fake-or-real DINO pair result with exact threshold semantics."""

    schema_version: Literal["rei-c4-stage1-dino-pair-v1"] = "rei-c4-stage1-dino-pair-v1"
    dino_pair_result_id: NonEmptyId
    run_id: NonEmptyId
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    prepared_anchor_storage: StoredArtifact
    member_publication_receipt_id: NonEmptyId
    member_publication_receipt_sha256: HashDigest
    member_publication_receipt_storage: StoredArtifact
    provider_slot_id: NonEmptyId
    screen_contract_id: NonEmptyId
    screen_contract_hash: HashDigest
    editor_role: Literal["primary", "alternate"]
    editor_spec_id: NonEmptyId
    dino_policy_id: NonEmptyId
    dino_policy_hash: HashDigest
    outputs: tuple[C4Stage1DinoOptionEvidence, C4Stage1DinoOptionEvidence]
    vector_float32_le_base64: tuple[NonEmptyText, NonEmptyText]
    direct_rollout_separation: Annotated[float, Field(ge=0.0, le=2.0)]
    direct_rollout_separation_epsilon: Literal[0.01] = C4_STAGE1_DINO_EPSILON
    action_collapse_detected: bool
    dino_gate_passed: bool
    human_review_substitute: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        screen_contract: C4Stage1ScreenContract,
        run_id: str,
        prepared_attempt_id: str,
        prepared_attempt_sha256: str,
        prepared_anchor_storage: StoredArtifact,
        member_publication_receipt_id: str,
        member_publication_receipt_sha256: str,
        member_publication_receipt_storage: StoredArtifact,
        provider_slot_id: str,
        editor_role: Literal["primary", "alternate"],
        editor_spec_id: str,
        dino_policy: C4Stage1DinoPolicy,
        outputs: tuple[C4Stage1DinoOptionEvidence, C4Stage1DinoOptionEvidence],
        vector_bytes: tuple[bytes, bytes],
    ) -> C4Stage1DinoPairResult:
        expected_editor = next(
            item for item in screen_contract.editors if item.role == editor_role
        )
        if editor_spec_id != expected_editor.spec_id:
            raise ValueError("DINO pair editor differs from its declared provider role")
        direct_rollout_separation = _dino_separation_from_vector_bytes(vector_bytes)
        vector_float32_le_base64 = tuple(
            base64.b64encode(value).decode("ascii") for value in vector_bytes
        )
        collapse = direct_rollout_separation <= C4_STAGE1_DINO_EPSILON
        body = {
            "schema_version": "rei-c4-stage1-dino-pair-v1",
            "run_id": run_id,
            "prepared_attempt_id": prepared_attempt_id,
            "prepared_attempt_sha256": prepared_attempt_sha256,
            "prepared_anchor_storage": prepared_anchor_storage,
            "member_publication_receipt_id": member_publication_receipt_id,
            "member_publication_receipt_sha256": (member_publication_receipt_sha256),
            "member_publication_receipt_storage": (member_publication_receipt_storage),
            "provider_slot_id": provider_slot_id,
            "screen_contract_id": screen_contract.screen_contract_id,
            "screen_contract_hash": screen_contract.content_hash(),
            "editor_role": editor_role,
            "editor_spec_id": editor_spec_id,
            "dino_policy_id": dino_policy.dino_policy_id,
            "dino_policy_hash": dino_policy.content_hash(),
            "outputs": outputs,
            "vector_float32_le_base64": vector_float32_le_base64,
            "direct_rollout_separation": direct_rollout_separation,
            "direct_rollout_separation_epsilon": C4_STAGE1_DINO_EPSILON,
            "action_collapse_detected": collapse,
            "dino_gate_passed": not collapse,
            "human_review_substitute": False,
            "generated_images_are_external_evidence": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(
            dino_pair_result_id=content_id("c4_stage1_dino_pair", body),
            **body,
        )

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        prepared_anchor = StoredArtifact.model_validate(
            self.prepared_anchor_storage.model_dump(mode="python", round_trip=True)
        )
        publication_storage = StoredArtifact.model_validate(
            self.member_publication_receipt_storage.model_dump(
                mode="python", round_trip=True
            )
        )
        if tuple(item.option_id for item in self.outputs) != (
            "enter_circle",
            "remain_edge",
        ):
            raise ValueError("DINO pair output order differs from Stage 1")
        if (
            prepared_anchor.run_id != self.run_id
            or prepared_anchor.relative_path
            != "diagnostics/c4_stage1_prepared_attempt.json"
            or publication_storage.run_id != self.run_id
            or publication_storage.relative_path
            != (
                "diagnostics/"
                f"{self.member_publication_receipt_id}.member-publication.json"
            )
            or any(
                output.candidate_staged_output_storage.run_id != self.run_id
                for output in self.outputs
            )
            or len({output.candidate_receipt_id for output in self.outputs}) != 2
            or len({output.prepared_worker_id for output in self.outputs}) != 2
            or len({output.worker_request_id for output in self.outputs}) != 2
        ):
            raise ValueError("DINO pair publication lineage is inconsistent")
        vector_bytes = _decode_dino_vector_bundle(self.vector_float32_le_base64)
        if any(
            hashlib.sha256(payload).hexdigest() != output.vector_sha256
            for output, payload in zip(self.outputs, vector_bytes, strict=True)
        ):
            raise ValueError("DINO pair vector bytes differ from encoding evidence")
        if self.direct_rollout_separation != _dino_separation_from_vector_bytes(
            vector_bytes
        ):
            raise ValueError("DINO pair separation differs from exact vector bytes")
        expected_editor_spec_id = (
            longcat_turbo_stage1_spec().spec_id
            if self.editor_role == "primary"
            else omnigen_stage1_spec().spec_id
        )
        expected_provider_id = (
            longcat_turbo_stage1_spec().provider.provider_id
            if self.editor_role == "primary"
            else omnigen_stage1_spec().provider.provider_id
        )
        if self.editor_spec_id != expected_editor_spec_id or any(
            output.image.provider_id != expected_provider_id for output in self.outputs
        ):
            raise ValueError("DINO pair editor differs from its declared provider role")
        collapsed = self.direct_rollout_separation <= (
            self.direct_rollout_separation_epsilon
        )
        if self.action_collapse_detected != collapsed or (
            self.dino_gate_passed != (not collapsed)
        ):
            raise ValueError("DINO pair disposition differs from the frozen epsilon")
        expected = content_id(
            "c4_stage1_dino_pair",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"dino_pair_result_id"},
            ),
        )
        if self.dino_pair_result_id != expected:
            raise ValueError("DINO pair result ID differs from content")
        return self


__all__ = [
    "C4_STAGE1_ADDENDUM_PATH",
    "C4_STAGE1_ADDENDUM_SHA256",
    "C4_STAGE1_ALTERNATE_SNAPSHOT_MANIFEST_PATH",
    "C4_STAGE1_DINO_EPSILON",
    "C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256",
    "C4_STAGE1_PRIMARY_SNAPSHOT_MANIFEST_PATH",
    "C4_STAGE1_PROTOCOL_PATH",
    "C4_STAGE1_PROTOCOL_SHA256",
    "C4Stage1ContentPin",
    "C4Stage1DinoOptionEvidence",
    "C4Stage1DinoPairResult",
    "C4Stage1DinoPolicy",
    "C4Stage1DocumentPin",
    "C4Stage1EditorPin",
    "C4Stage1OptionInput",
    "C4Stage1ScreenContract",
    "C4Stage1SourcePin",
    "normalized_utf8_document_bytes",
]
