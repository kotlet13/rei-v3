"""Frozen native bundle and run-level provenance contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex, utc_now
from .character import CharacterProfileId
from .common import (
    CommitDigest,
    ArtifactRelativePath,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    SafetyNotice,
    UtcTimestamp,
)
from .emocio import EmocioInputPacket, EmocioNativeConclusion, EmocioVisualState
from .instinkt import (
    BodyState,
    InstinktInputPacket,
    InstinktNativeConclusion,
    InstinktOptionRollout,
)
from .provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderIdentity,
    ensure_call_record_contract,
)
from .racio import RacioInputPacket, RacioNativeConclusion
from .scene import SceneEvent


class LineageArtifactHash(FrozenModel):
    """Compact immutable reference to a validated intermediate artifact."""

    artifact_id: NonEmptyId
    sha256: HashDigest


class NativeMindBundle(FrozenArtifactModel):
    """The three immutable native conclusions before interpretation."""

    schema_version: Literal["rei-native-mind-bundle-v1"] = (
        "rei-native-mind-bundle-v1"
    )
    bundle_id: NonEmptyId
    scene_id: NonEmptyId
    scene_hash: HashDigest
    allowed_option_ids: tuple[NonEmptyId, ...]
    racio_packet_hash: HashDigest
    emocio_packet_hash: HashDigest
    instinkt_packet_hash: HashDigest
    emocio_visual_state_id: NonEmptyId
    emocio_visual_state_hash: HashDigest
    instinkt_body_state_id: NonEmptyId
    instinkt_body_state_hash: HashDigest
    instinkt_rollout_hashes: tuple[LineageArtifactHash, ...]
    racio: RacioNativeConclusion
    emocio: EmocioNativeConclusion
    instinkt: InstinktNativeConclusion
    created_at: UtcTimestamp
    immutable_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        scene: SceneEvent,
        racio_packet: RacioInputPacket,
        emocio_packet: EmocioInputPacket,
        instinkt_packet: InstinktInputPacket,
        emocio_visual_state: EmocioVisualState,
        instinkt_body_state: BodyState,
        instinkt_rollouts: tuple[InstinktOptionRollout, ...],
        racio: RacioNativeConclusion,
        emocio: EmocioNativeConclusion,
        instinkt: InstinktNativeConclusion,
        created_at: UtcTimestamp | None = None,
    ) -> NativeMindBundle:
        racio_packet.validate_against(scene)
        emocio_packet.validate_against(scene)
        instinkt_packet.validate_against(scene, instinkt_body_state)
        emocio_visual_state.validate_against(emocio_packet, scene)
        racio.validate_against(racio_packet)
        emocio.validate_against(emocio_packet, emocio_visual_state)
        instinkt.validate_against(
            instinkt_packet,
            instinkt_body_state,
            instinkt_rollouts,
        )
        source_scene_ids = {
            racio.source_scene_id,
            emocio.source_scene_id,
            instinkt.source_scene_id,
        }
        if source_scene_ids != {scene.event_id}:
            raise ValueError("All native conclusions must originate from the bundled scene")
        allowed_option_ids = tuple(sorted(option.option_id for option in scene.options))
        selected_option_ids = {
            conclusion.option_id
            for conclusion in (racio, emocio, instinkt)
            if conclusion.option_id is not None
        }
        unknown_option_ids = selected_option_ids - set(allowed_option_ids)
        if unknown_option_ids:
            raise ValueError("Native conclusions may select only SceneEvent options")
        base = {
            "schema_version": "rei-native-mind-bundle-v1",
            "scene_id": scene.event_id,
            "scene_hash": scene.scene_hash(),
            "allowed_option_ids": allowed_option_ids,
            "racio_packet_hash": racio_packet.content_hash(),
            "emocio_packet_hash": emocio_packet.content_hash(),
            "instinkt_packet_hash": instinkt_packet.content_hash(),
            "emocio_visual_state_id": emocio_visual_state.visual_state_id,
            "emocio_visual_state_hash": emocio_visual_state.content_hash(),
            "instinkt_body_state_id": instinkt_body_state.body_state_id,
            "instinkt_body_state_hash": instinkt_body_state.content_hash(),
            "instinkt_rollout_hashes": tuple(
                LineageArtifactHash(
                    artifact_id=rollout.rollout_id,
                    sha256=rollout.content_hash(),
                )
                for rollout in sorted(
                    instinkt_rollouts,
                    key=lambda item: item.rollout_id,
                )
            ),
            "racio": racio,
            "emocio": emocio,
            "instinkt": instinkt,
            "created_at": created_at or utc_now(),
        }
        bundle_id = content_id("bundle", base)
        payload = {"bundle_id": bundle_id, **base}
        return cls(**payload, immutable_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_immutable_hash(self) -> Self:
        source_scene_ids = {
            self.racio.source_scene_id,
            self.emocio.source_scene_id,
            self.instinkt.source_scene_id,
        }
        if source_scene_ids != {self.scene_id}:
            raise ValueError("Bundle conclusions must share the recorded source scene")
        if tuple(sorted(set(self.allowed_option_ids))) != self.allowed_option_ids:
            raise ValueError("Bundle allowed_option_ids must be sorted and unique")
        selected_option_ids = {
            conclusion.option_id
            for conclusion in (self.racio, self.emocio, self.instinkt)
            if conclusion.option_id is not None
        }
        if not selected_option_ids.issubset(self.allowed_option_ids):
            raise ValueError("Bundle conclusions may select only recorded scene options")
        if self.instinkt.source_body_state_id != self.instinkt_body_state_id:
            raise ValueError("Bundle Instinkt conclusion must share its source BodyState")
        rollout_ids = tuple(item.artifact_id for item in self.instinkt_rollout_hashes)
        if rollout_ids != tuple(sorted(set(rollout_ids))):
            raise ValueError("Bundle Instinkt rollout hashes must be sorted and unique")
        if (
            self.instinkt.decisive_rollout_id is not None
            and self.instinkt.decisive_rollout_id not in rollout_ids
        ):
            raise ValueError("Bundle must hash the decisive Instinkt rollout")
        id_payload = {
            "schema_version": self.schema_version,
            "scene_id": self.scene_id,
            "scene_hash": self.scene_hash,
            "allowed_option_ids": self.allowed_option_ids,
            "racio_packet_hash": self.racio_packet_hash,
            "emocio_packet_hash": self.emocio_packet_hash,
            "instinkt_packet_hash": self.instinkt_packet_hash,
            "emocio_visual_state_id": self.emocio_visual_state_id,
            "emocio_visual_state_hash": self.emocio_visual_state_hash,
            "instinkt_body_state_id": self.instinkt_body_state_id,
            "instinkt_body_state_hash": self.instinkt_body_state_hash,
            "instinkt_rollout_hashes": self.instinkt_rollout_hashes,
            "racio": self.racio,
            "emocio": self.emocio,
            "instinkt": self.instinkt,
            "created_at": self.created_at,
        }
        if self.bundle_id != content_id("bundle", id_payload):
            raise ValueError("bundle_id does not match the canonical bundle content")
        expected = self.content_hash(exclude_fields=frozenset({"immutable_hash"}))
        if self.immutable_hash != expected:
            raise ValueError("immutable_hash does not match the canonical bundle payload")
        return self

    def validate_against(self, scene: SceneEvent) -> None:
        """Verify the bundle's compact scene provenance against a trusted event."""

        if self.scene_id != scene.event_id or self.scene_hash != scene.scene_hash():
            raise ValueError("Bundle does not match the supplied SceneEvent")
        option_ids = tuple(sorted(option.option_id for option in scene.options))
        if self.allowed_option_ids != option_ids:
            raise ValueError("Bundle option scope does not match the supplied SceneEvent")

    def validate_packets(
        self,
        *,
        scene: SceneEvent,
        racio_packet: RacioInputPacket,
        emocio_packet: EmocioInputPacket,
        instinkt_packet: InstinktInputPacket,
    ) -> None:
        """Verify source packet hashes and per-processor option scope."""

        self.validate_against(scene)
        racio_packet.validate_against(scene)
        emocio_packet.validate_against(scene)
        instinkt_packet.validate_scene(scene)
        if (
            self.racio_packet_hash != racio_packet.content_hash()
            or self.emocio_packet_hash != emocio_packet.content_hash()
            or self.instinkt_packet_hash != instinkt_packet.content_hash()
        ):
            raise ValueError("Bundle source packet hashes do not match")
        allowed = set(self.allowed_option_ids)
        if any(
            set(packet_option_ids) != allowed
            for packet_option_ids in (
                racio_packet.allowed_option_ids,
                emocio_packet.allowed_option_ids,
                instinkt_packet.option_ids,
            )
        ):
            raise ValueError("Bundle source packets must share its complete option scope")
        self.racio.validate_against(racio_packet)
        self.emocio.validate_packet(emocio_packet)
        self.instinkt.validate_packet(instinkt_packet)

    def validate_native_lineage(
        self,
        *,
        scene: SceneEvent,
        racio_packet: RacioInputPacket,
        emocio_packet: EmocioInputPacket,
        instinkt_packet: InstinktInputPacket,
        emocio_visual_state: EmocioVisualState,
        instinkt_body_state: BodyState,
        instinkt_rollouts: tuple[InstinktOptionRollout, ...],
    ) -> None:
        """Close every compact packet and intermediate-artifact hash reference."""

        self.validate_packets(
            scene=scene,
            racio_packet=racio_packet,
            emocio_packet=emocio_packet,
            instinkt_packet=instinkt_packet,
        )
        instinkt_packet.validate_against(scene, instinkt_body_state)
        emocio_visual_state.validate_against(emocio_packet, scene)
        self.emocio.validate_against(emocio_packet, emocio_visual_state)
        self.instinkt.validate_against(
            instinkt_packet,
            instinkt_body_state,
            instinkt_rollouts,
        )
        if (
            self.emocio_visual_state_id != emocio_visual_state.visual_state_id
            or self.emocio_visual_state_hash != emocio_visual_state.content_hash()
        ):
            raise ValueError("Bundle Emocio visual-state provenance does not match")
        if (
            self.instinkt_body_state_id != instinkt_body_state.body_state_id
            or self.instinkt_body_state_hash != instinkt_body_state.content_hash()
        ):
            raise ValueError("Bundle Instinkt BodyState provenance does not match")
        rollout_hashes = tuple(
            LineageArtifactHash(
                artifact_id=rollout.rollout_id,
                sha256=rollout.content_hash(),
            )
            for rollout in sorted(instinkt_rollouts, key=lambda item: item.rollout_id)
        )
        if self.instinkt_rollout_hashes != rollout_hashes:
            raise ValueError("Bundle Instinkt rollout provenance does not match")


ArtifactHashRole = Literal[
    "native_bundle",
    "racio_native",
    "emocio_native",
    "instinkt_native",
]


class ArtifactHashRecord(FrozenModel):
    artifact_id: NonEmptyId
    role: ArtifactHashRole
    sha256: HashDigest


class SeedRecord(FrozenModel):
    call_id: NonEmptyId
    attempt: Literal["primary", "fallback"] = "primary"
    provider_id: NonEmptyId
    seed: int


class RunArtifactRecord(FrozenModel):
    """Durable content-addressed inventory entry for one run file."""

    schema_version: Literal["rei-native-stored-artifact-v1"] = (
        "rei-native-stored-artifact-v1"
    )
    storage_id: NonEmptyId
    run_id: NonEmptyId
    relative_path: ArtifactRelativePath
    content_sha256: HashDigest
    size_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_storage_id(self) -> Self:
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"storage_id"}
        )
        if self.storage_id != content_id("stored", payload):
            raise ValueError("Run artifact storage ID differs from canonical metadata")
        return self


EmocioMaterializedArtifactRole = Literal["image", "vector"]


class EmocioMaterializedArtifactRecord(FrozenModel):
    """One verified binary handed from configured Emocio into run storage."""

    artifact_id: NonEmptyId
    role: EmocioMaterializedArtifactRole
    relative_path: ArtifactRelativePath
    content_sha256: HashDigest
    size_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_emocio_binary_path(self) -> Self:
        if len(self.relative_path.split("/")) != 3:
            raise ValueError(
                "Materialized Emocio binary must be a direct file in its role directory"
            )
        if self.role == "image":
            if not self.relative_path.startswith("emocio/images/") or not (
                self.relative_path.endswith(".png")
            ):
                raise ValueError(
                    "Materialized Emocio image must use emocio/images/*.png"
                )
        elif not self.relative_path.startswith("emocio/embeddings/") or not (
            self.relative_path.endswith(".f32")
        ):
            raise ValueError(
                "Materialized Emocio vector must use emocio/embeddings/*.f32"
            )
        return self


class EmocioExecutionManifestRecord(FrozenArtifactModel):
    """Manifest link from one configured Emocio call to all nested work."""

    schema_version: Literal["rei-native-emocio-execution-manifest-v1"] = (
        "rei-native-emocio-execution-manifest-v1"
    )
    record_id: NonEmptyId
    outer_call_id: NonEmptyId
    processor_config_id: NonEmptyId
    processor_config_hash: HashDigest
    processor_config_path: Literal["emocio/processor_config.json"] = (
        "emocio/processor_config.json"
    )
    processing_artifact_id: NonEmptyId
    processing_artifact_hash: HashDigest
    processing_artifact_path: Literal["emocio/processing_result.json"] = (
        "emocio/processing_result.json"
    )
    renderer_call_ids: tuple[NonEmptyId, ...] = ()
    encoder_call_ids: tuple[NonEmptyId, ...] = ()
    materialized_artifacts: tuple[EmocioMaterializedArtifactRecord, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        outer_call_id: str,
        processor_config_id: str,
        processor_config_hash: str,
        processing_artifact_id: str,
        processing_artifact_hash: str,
        renderer_call_ids: tuple[str, ...] = (),
        encoder_call_ids: tuple[str, ...] = (),
        materialized_artifacts: tuple[EmocioMaterializedArtifactRecord, ...] = (),
    ) -> EmocioExecutionManifestRecord:
        payload = {
            "schema_version": "rei-native-emocio-execution-manifest-v1",
            "outer_call_id": outer_call_id,
            "processor_config_id": processor_config_id,
            "processor_config_hash": processor_config_hash,
            "processor_config_path": "emocio/processor_config.json",
            "processing_artifact_id": processing_artifact_id,
            "processing_artifact_hash": processing_artifact_hash,
            "processing_artifact_path": "emocio/processing_result.json",
            "renderer_call_ids": renderer_call_ids,
            "encoder_call_ids": encoder_call_ids,
            "materialized_artifacts": tuple(
                sorted(
                    materialized_artifacts,
                    key=lambda item: (item.relative_path, item.artifact_id),
                )
            ),
        }
        return cls(
            record_id=content_id("emocio_execution_manifest", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_emocio_execution_record(self) -> Self:
        if len(set(self.renderer_call_ids)) != len(self.renderer_call_ids):
            raise ValueError("Emocio renderer call IDs must be unique")
        if len(set(self.encoder_call_ids)) != len(self.encoder_call_ids):
            raise ValueError("Emocio encoder call IDs must be unique")
        if set(self.renderer_call_ids).intersection(self.encoder_call_ids):
            raise ValueError("Emocio renderer and encoder call IDs must be disjoint")
        artifact_order = tuple(
            (item.relative_path, item.artifact_id)
            for item in self.materialized_artifacts
        )
        if artifact_order != tuple(sorted(artifact_order)):
            raise ValueError(
                "Materialized Emocio artifacts must use canonical path/ID order"
            )
        artifact_ids = tuple(
            item.artifact_id for item in self.materialized_artifacts
        )
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError(
                "Materialized Emocio artifact IDs must be unique"
            )
        artifacts_by_path: dict[str, EmocioMaterializedArtifactRecord] = {}
        for item in self.materialized_artifacts:
            previous = artifacts_by_path.setdefault(item.relative_path, item)
            if (
                previous.role != item.role
                or previous.content_sha256 != item.content_sha256
                or previous.size_bytes != item.size_bytes
            ):
                raise ValueError(
                    "One materialized Emocio path cannot name conflicting bytes"
                )
        expected_id = content_id(
            "emocio_execution_manifest",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"record_id"},
            ),
        )
        if self.record_id != expected_id:
            raise ValueError(
                "Emocio execution manifest ID differs from canonical content"
            )
        return self


class NativeBundleAssemblyRecord(FrozenArtifactModel):
    """Deterministic core step that freezes three provider outputs into a bundle."""

    schema_version: Literal["rei-native-bundle-assembly-v1"] = (
        "rei-native-bundle-assembly-v1"
    )
    assembly_id: NonEmptyId
    implementation: NonEmptyText
    implementation_revision: NonEmptyText
    racio_conclusion_id: NonEmptyId
    emocio_conclusion_id: NonEmptyId
    instinkt_conclusion_id: NonEmptyId
    bundle_id: NonEmptyId
    started_at: UtcTimestamp
    finished_at: UtcTimestamp

    @model_validator(mode="after")
    def validate_assembly(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("Native bundle assembly cannot finish before it starts")
        conclusion_ids = (
            self.racio_conclusion_id,
            self.emocio_conclusion_id,
            self.instinkt_conclusion_id,
        )
        if len(set(conclusion_ids)) != len(conclusion_ids):
            raise ValueError("Native assembly conclusion IDs must be distinct")
        if self.bundle_id in conclusion_ids:
            raise ValueError("Native bundle ID must differ from conclusion IDs")
        return self


RunMode = Literal["controlled_profile_matrix", "person_longitudinal"]
RunStatus = Literal["created", "running", "completed", "failed"]
NativeArtifactSource = Literal["produced", "inherited"]


class RunManifest(FrozenArtifactModel):
    schema_version: Literal[
        "rei-native-run-manifest-v1", "rei-native-run-manifest-v2"
    ] = (
        "rei-native-run-manifest-v1"
    )
    manifest_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    run_id: NonEmptyId
    parent_run_id: NonEmptyId | None = None
    parent_run_hash: HashDigest | None = None
    source_commit: CommitDigest
    canon_version: NonEmptyText
    mode: RunMode
    profile_id: CharacterProfileId
    acceptance_state_id: NonEmptyId
    acceptance_config_hash: HashDigest
    providers: tuple[ProviderIdentity, ...] = ()
    provider_call_specs: tuple[ProviderCallSpec, ...] = ()
    provider_calls: tuple[ProviderCallRecord, ...] = ()
    seeds: tuple[SeedRecord, ...] = ()
    native_artifact_hashes: tuple[ArtifactHashRecord, ...] = ()
    native_artifact_source: NativeArtifactSource
    native_assembly: NativeBundleAssemblyRecord | None = None
    emocio_execution: EmocioExecutionManifestRecord | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    started_at: UtcTimestamp
    finished_at: UtcTimestamp | None = None
    status: RunStatus = "created"
    warnings: tuple[str, ...] = ()
    safety_flags: tuple[str, ...] = ()
    safety_notice: SafetyNotice = SafetyNotice()
    artifact_inventory: tuple[RunArtifactRecord, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    artifact_inventory_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    manifest_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        provider_ids = tuple(item.provider_id for item in self.providers)
        if len(set(provider_ids)) != len(provider_ids):
            raise ValueError("RunManifest provider IDs must be unique")
        call_ids = tuple(item.call_id for item in self.provider_calls)
        if len(set(call_ids)) != len(call_ids):
            raise ValueError("RunManifest provider call IDs must be unique")
        spec_ids = tuple(item.call_id for item in self.provider_call_specs)
        if len(set(spec_ids)) != len(spec_ids):
            raise ValueError("RunManifest provider call spec IDs must be unique")
        provider_by_id = {provider.provider_id: provider for provider in self.providers}
        unknown_call_providers = {
            call.provider.provider_id for call in self.provider_calls
        } - set(provider_by_id)
        unknown_call_providers.update(
            spec.provider.provider_id
            for spec in self.provider_call_specs
            if spec.provider.provider_id not in provider_by_id
        )
        unknown_call_providers.update(
            call.fallback.provider.provider_id
            for call in self.provider_calls
            if call.fallback is not None
            and call.fallback.provider.provider_id not in provider_by_id
        )
        unknown_call_providers.update(
            spec.fallback_policy.plan.provider.provider_id
            for spec in self.provider_call_specs
            if spec.fallback_policy.plan is not None
            and spec.fallback_policy.plan.provider.provider_id not in provider_by_id
        )
        if unknown_call_providers:
            raise ValueError("Every provider call must reference a declared provider")
        for call in self.provider_calls:
            if provider_by_id[call.provider.provider_id] != call.provider:
                raise ValueError("Provider call identity differs from its manifest entry")
            if call.fallback is not None and (
                provider_by_id[call.fallback.provider.provider_id]
                != call.fallback.provider
            ):
                raise ValueError("Fallback identity differs from its manifest entry")
        for spec in self.provider_call_specs:
            if provider_by_id[spec.provider.provider_id] != spec.provider:
                raise ValueError("Provider call spec differs from its manifest identity")
            if spec.fallback_policy.plan is not None and (
                provider_by_id[spec.fallback_policy.plan.provider.provider_id]
                != spec.fallback_policy.plan.provider
            ):
                raise ValueError("Fallback spec differs from its manifest identity")
        spec_by_id = {spec.call_id: spec for spec in self.provider_call_specs}
        call_by_id = {call.call_id: call for call in self.provider_calls}
        for call in self.provider_calls:
            spec = spec_by_id.get(call.call_id)
            if spec is None:
                raise ValueError("Every provider call record requires its original spec")
            ensure_call_record_contract(spec, call)
        renderer_call_ids = tuple(
            call.call_id
            for call in self.provider_calls
            if call.provider.kind == "image_renderer"
        )
        encoder_call_ids = tuple(
            call.call_id
            for call in self.provider_calls
            if call.provider.kind == "image_encoder"
        )
        if self.emocio_execution is None:
            if renderer_call_ids or encoder_call_ids:
                raise ValueError(
                    "Nested visual provider calls require an Emocio execution record"
                )
        else:
            execution = EmocioExecutionManifestRecord.model_validate(
                self.emocio_execution.model_dump(
                    mode="python",
                    round_trip=True,
                )
            )
            outer_spec = spec_by_id.get(execution.outer_call_id)
            outer_call = call_by_id.get(execution.outer_call_id)
            if outer_spec is None or outer_call is None:
                raise ValueError(
                    "Emocio execution record requires its exact outer call"
                )
            if outer_call.provider.kind != "visual_world_model":
                raise ValueError(
                    "Emocio outer call must use a visual-world-model provider"
                )
            if execution.processor_config_id not in outer_spec.input_artifact_ids:
                raise ValueError(
                    "Configured Emocio outer call omits its processor config input"
                )
            if (
                execution.processing_artifact_id
                not in outer_call.output_artifact_ids
            ):
                raise ValueError(
                    "Configured Emocio outer call omits its processing artifact output"
                )
            if execution.renderer_call_ids != renderer_call_ids:
                raise ValueError(
                    "Emocio renderer calls differ from their manifest execution order"
                )
            if execution.encoder_call_ids != encoder_call_ids:
                raise ValueError(
                    "Emocio encoder calls differ from their manifest execution order"
                )
            nested_call_ids = (*renderer_call_ids, *encoder_call_ids)
            if execution.outer_call_id in nested_call_ids:
                raise ValueError("Emocio outer call cannot also be a nested call")
            for call_id in nested_call_ids:
                nested_spec = spec_by_id.get(call_id)
                nested_call = call_by_id.get(call_id)
                if nested_spec is None or nested_call is None:
                    raise ValueError(
                        "Every nested Emocio call requires exact spec and record"
                    )
                if (
                    nested_call.started_at < outer_call.started_at
                    or nested_call.finished_at > outer_call.finished_at
                ):
                    raise ValueError(
                        "Nested Emocio calls must execute inside the outer call interval"
                    )
            ordered_nested_calls = tuple(
                call_by_id[call_id] for call_id in nested_call_ids
            )
            for previous, current in zip(
                ordered_nested_calls,
                ordered_nested_calls[1:],
            ):
                if current.started_at < previous.finished_at:
                    raise ValueError(
                        "Nested Emocio calls must preserve causal execution order"
                    )
            expected_image_ids = {
                artifact_id
                for call_id in renderer_call_ids
                for artifact_id in call_by_id[call_id].output_artifact_ids
            }
            expected_vector_ids = {
                artifact_id
                for call_id in encoder_call_ids
                for artifact_id in call_by_id[call_id].output_artifact_ids
            }
            recorded_image_ids = {
                item.artifact_id
                for item in execution.materialized_artifacts
                if item.role == "image"
            }
            recorded_vector_ids = {
                item.artifact_id
                for item in execution.materialized_artifacts
                if item.role == "vector"
            }
            if recorded_image_ids != expected_image_ids:
                raise ValueError(
                    "Materialized Emocio images differ from renderer outputs"
                )
            if recorded_vector_ids != expected_vector_ids:
                raise ValueError(
                    "Materialized Emocio vectors differ from encoder outputs"
                )
            if self.native_assembly is not None and set(
                outer_call.output_artifact_ids
            ) != {
                self.native_assembly.emocio_conclusion_id,
                execution.processing_artifact_id,
            }:
                raise ValueError(
                    "Configured Emocio outer outputs must be conclusion plus "
                    "processing artifact"
                )
        expected_seeds: dict[tuple[str, str], tuple[str, int]] = {}
        for call in self.provider_calls:
            if call.seed is not None:
                expected_seeds[(call.call_id, "primary")] = (
                    call.provider.provider_id,
                    call.seed,
                )
            if (
                call.fallback is not None
                and call.fallback.status != "skipped"
                and call.fallback.seed is not None
            ):
                expected_seeds[(call.call_id, "fallback")] = (
                    call.fallback.provider.provider_id,
                    call.fallback.seed,
                )
        recorded_seeds = {
            (item.call_id, item.attempt): (item.provider_id, item.seed)
            for item in self.seeds
        }
        if len(recorded_seeds) != len(self.seeds):
            raise ValueError("RunManifest seed records must be unique per call attempt")
        if recorded_seeds != expected_seeds:
            raise ValueError("RunManifest seeds must exactly match provider call seeds")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("RunManifest cannot finish before it starts")
        for call in self.provider_calls:
            if call.started_at < self.started_at:
                raise ValueError("Provider calls cannot start before their run")
            if self.finished_at is not None and call.finished_at > self.finished_at:
                raise ValueError("Provider calls cannot finish after their run")
        if self.native_assembly is not None:
            if self.native_assembly.started_at < self.started_at:
                raise ValueError("Native assembly cannot start before its run")
            if (
                self.finished_at is not None
                and self.native_assembly.finished_at > self.finished_at
            ):
                raise ValueError("Native assembly cannot finish after its run")
        if self.status in {"completed", "failed"} and self.finished_at is None:
            raise ValueError("A terminal run must include finished_at")
        if self.status in {"created", "running"} and self.finished_at is not None:
            raise ValueError("A non-terminal run cannot include finished_at")
        hash_ids = tuple(item.artifact_id for item in self.native_artifact_hashes)
        if len(set(hash_ids)) != len(hash_ids):
            raise ValueError("Native artifact hash IDs must be unique")
        hash_roles = tuple(item.role for item in self.native_artifact_hashes)
        if len(set(hash_roles)) != len(hash_roles):
            raise ValueError("Native artifact hash roles must be unique")
        if self.parent_run_id == self.run_id:
            raise ValueError("A run cannot cite itself as its parent")
        if (self.parent_run_id is None) != (self.parent_run_hash is None):
            raise ValueError("Parent run ID and hash must be recorded together")
        if self.native_artifact_source == "inherited":
            if self.parent_run_id is None:
                raise ValueError("Inherited native artifacts require a parent run link")
            if self.native_assembly is not None:
                raise ValueError("Inherited native artifacts cannot claim local assembly")
        if self.status == "completed":
            required_roles = {
                "native_bundle",
                "racio_native",
                "emocio_native",
                "instinkt_native",
            }
            if set(hash_roles) != required_roles:
                raise ValueError("Completed runs must record all four native hash roles")
            if set(call_ids) != set(spec_ids):
                raise ValueError("Completed runs must close every provider call spec")
            if self.native_artifact_source == "produced":
                if not self.provider_calls:
                    raise ValueError(
                        "Locally produced native artifacts require provider calls"
                    )
                if self.native_assembly is None:
                    raise ValueError(
                        "Locally produced native artifacts require bundle assembly provenance"
                    )
                hashes_by_role = {
                    item.role: item.artifact_id
                    for item in self.native_artifact_hashes
                }
                expected_artifacts = {
                    "native_bundle": self.native_assembly.bundle_id,
                    "racio_native": self.native_assembly.racio_conclusion_id,
                    "emocio_native": self.native_assembly.emocio_conclusion_id,
                    "instinkt_native": self.native_assembly.instinkt_conclusion_id,
                }
                if hashes_by_role != expected_artifacts:
                    raise ValueError(
                        "Native hashes must match the explicit bundle assembly artifacts"
                    )
                conclusion_ids = {
                    self.native_assembly.racio_conclusion_id,
                    self.native_assembly.emocio_conclusion_id,
                    self.native_assembly.instinkt_conclusion_id,
                }
                successful_calls = tuple(
                    call
                    for call in self.provider_calls
                    if call.status in {"succeeded", "fell_back"}
                )
                produced_conclusion_ids = {
                    artifact_id
                    for call in successful_calls
                    for artifact_id in call.output_artifact_ids
                    if artifact_id in conclusion_ids
                }
                if produced_conclusion_ids != conclusion_ids:
                    raise ValueError(
                        "Every assembled native conclusion must be a successful provider output"
                    )
                for conclusion_id in conclusion_ids:
                    producers = tuple(
                        call
                        for call in successful_calls
                        if conclusion_id in call.output_artifact_ids
                    )
                    if len(producers) != 1:
                        raise ValueError(
                            "Each native conclusion must have exactly one provider producer"
                        )
                    if producers[0].finished_at > self.native_assembly.started_at:
                        raise ValueError(
                            "Native assembly cannot start before its provider inputs exist"
                        )
                if any(
                    self.native_assembly.bundle_id in call.output_artifact_ids
                    for call in self.provider_calls
                ):
                    raise ValueError(
                        "Only the deterministic assembly step may produce the native bundle"
                    )
            else:
                native_artifact_ids = set(hash_ids)
                if any(
                    native_artifact_ids.intersection(call.output_artifact_ids)
                    for call in self.provider_calls
                ):
                    raise ValueError(
                        "Inherited native artifacts cannot be claimed as local provider outputs"
                    )
        if self.schema_version == "rei-native-run-manifest-v1":
            if (
                self.manifest_id is not None
                or self.artifact_inventory
                or self.artifact_inventory_hash is not None
                or self.manifest_hash is not None
            ):
                raise ValueError("V1 RunManifest cannot carry the V2 durable inventory")
            return self
        if (
            self.manifest_id is None
            or not self.artifact_inventory
            or self.artifact_inventory_hash is None
            or self.manifest_hash is None
        ):
            raise ValueError("V2 RunManifest requires identity, inventory and hashes")
        paths = tuple(item.relative_path for item in self.artifact_inventory)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("Run artifact inventory paths must be sorted and unique")
        if any(item.run_id != self.run_id for item in self.artifact_inventory):
            raise ValueError("Run artifact inventory entries belong to another run")
        if self.emocio_execution is not None:
            inventory_by_path = {
                item.relative_path: item for item in self.artifact_inventory
            }
            execution = self.emocio_execution
            config_entry = inventory_by_path.get(execution.processor_config_path)
            result_entry = inventory_by_path.get(execution.processing_artifact_path)
            if (
                config_entry is None
                or config_entry.content_sha256
                != execution.processor_config_hash
            ):
                raise ValueError(
                    "Emocio processor config differs from durable inventory"
                )
            if (
                result_entry is None
                or result_entry.content_sha256
                != execution.processing_artifact_hash
            ):
                raise ValueError(
                    "Emocio processing artifact differs from durable inventory"
                )
            for materialized in execution.materialized_artifacts:
                entry = inventory_by_path.get(materialized.relative_path)
                if (
                    entry is None
                    or entry.content_sha256 != materialized.content_sha256
                    or entry.size_bytes != materialized.size_bytes
                ):
                    raise ValueError(
                        "Materialized Emocio binary differs from durable inventory"
                    )
        if any(
            path in {"run_manifest.json", "diagnostics/prepared_manifest.json"}
            for path in paths
        ):
            raise ValueError("Manifest files cannot inventory themselves")
        if self.artifact_inventory_hash != sha256_hex(self.artifact_inventory):
            raise ValueError("Run artifact inventory hash differs from its entries")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"manifest_id", "manifest_hash"},
        )
        if self.manifest_id != content_id("run_manifest", id_payload):
            raise ValueError("Run manifest ID differs from canonical V2 content")
        payload = {"manifest_id": self.manifest_id, **id_payload}
        if self.manifest_hash != sha256_hex(payload):
            raise ValueError("Run manifest hash differs from canonical V2 content")
        return self

    @classmethod
    def finalize_v2(
        cls,
        provisional: RunManifest,
        inventory: tuple[RunArtifactRecord, ...],
    ) -> RunManifest:
        """Finalize a validated V1 manifest over a durable pre-manifest inventory."""

        if provisional.schema_version != "rei-native-run-manifest-v1":
            raise ValueError("Only a provisional V1 manifest can be finalized")
        ordered = tuple(sorted(inventory, key=lambda item: item.relative_path))
        base = provisional.model_dump(mode="python", round_trip=True)
        base["schema_version"] = "rei-native-run-manifest-v2"
        base["artifact_inventory"] = ordered
        base["artifact_inventory_hash"] = sha256_hex(ordered)
        manifest_id = content_id("run_manifest", base)
        payload = {"manifest_id": manifest_id, **base}
        return cls(**payload, manifest_hash=sha256_hex(payload))

    def validate_inherited_native_artifacts(
        self,
        parent_manifest: RunManifest,
    ) -> None:
        """Verify inherited native hashes against the exact completed parent manifest."""

        if self.native_artifact_source != "inherited":
            raise ValueError("Run does not declare inherited native artifacts")
        if self.status != "completed":
            raise ValueError("Only a completed run can validate inherited native artifacts")
        if parent_manifest.status != "completed":
            raise ValueError("Native artifacts can be inherited only from a completed run")
        parent_finished_at = parent_manifest.finished_at
        if parent_finished_at is None:
            raise ValueError("Completed parent run is missing its finish timestamp")
        if parent_finished_at > self.started_at:
            raise ValueError("Parent run must finish before inherited child work starts")
        if (
            self.parent_run_id != parent_manifest.run_id
            or self.parent_run_hash != parent_manifest.content_hash()
        ):
            raise ValueError("Parent manifest identity or hash does not match")
        inherited = {
            item.role: (item.artifact_id, item.sha256)
            for item in self.native_artifact_hashes
        }
        parent_native = {
            item.role: (item.artifact_id, item.sha256)
            for item in parent_manifest.native_artifact_hashes
        }
        if inherited != parent_native:
            raise ValueError("Inherited native artifact hashes differ from the parent")


__all__ = [
    "ArtifactHashRecord",
    "ArtifactHashRole",
    "EmocioExecutionManifestRecord",
    "EmocioMaterializedArtifactRecord",
    "EmocioMaterializedArtifactRole",
    "LineageArtifactHash",
    "NativeArtifactSource",
    "NativeMindBundle",
    "NativeBundleAssemblyRecord",
    "RunManifest",
    "RunArtifactRecord",
    "RunMode",
    "RunStatus",
    "SeedRecord",
]
