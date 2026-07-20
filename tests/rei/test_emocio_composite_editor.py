from __future__ import annotations

import hashlib
import json
import struct
import sys
import types
import zlib
from pathlib import Path

import pytest

from app.backend.rei.emocio.artifacts import LocalPngArtifactStore
from app.backend.rei.emocio.composite_editor import (
    CompositeEditorMember,
    CompositeEditorScreenResult,
    LazyLocalCompositeEditorBackend,
    build_editor_renderer,
    render_composite_editor_screen,
    render_editor_member_screen,
    verify_editor_snapshot,
)
from app.backend.rei.emocio.diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersRuntimeConfig,
    LazyDiffusersBackend,
    build_diffusers_snapshot_manifest,
    canonical_snapshot_manifest_bytes,
)
from app.backend.rei.emocio.firered_editor import (
    FIRERED_MODEL_ID,
    FIRERED_MODEL_REVISION,
    firered_editor_runtime_config,
)
from app.backend.rei.emocio.longcat_editor import (
    LONGCAT_MODEL_ID,
    LONGCAT_MODEL_REVISION,
    longcat_editor_runtime_config,
)
from app.backend.rei.emocio.packets import build_emocio_packet
from app.backend.rei.emocio.prompting import (
    BilingualStructuredScenePromptCompiler,
    VisualPromptProfile,
)
from app.backend.rei.emocio.scene_graph import compile_emocio_scenes
from app.backend.rei.models.emocio import EmocioWorld, ImageArtifact
from app.backend.rei.models.provider import ProviderIdentity
from app.backend.rei.models.rendering import ImageRenderRequest
from app.backend.rei.models.rendering import ImageSourceReference
from app.backend.rei.models.scene import DecisionOption, EvidenceItem, SceneEvent
from app.backend.rei.providers.language_policy import LocalModelLanguagePolicyError
from scripts.run_rei_emocio_editor_screen import (
    _matrix_cells,
    _prompt_compiler,
    _scene as screen_scene,
    _verify_pinned_prompt_token_audit,
    _world as screen_world,
    main as screen_main,
)
from scripts.run_rei_emocio_visual_smoke import (
    MODEL_ID as FLUX_MODEL_ID,
    MODEL_REVISION as FLUX_MODEL_REVISION,
    _provider_identity as flux_provider_identity,
)


def _png(
    width: int = 4,
    height: int = 3,
    rgba: tuple[int, int, int, int] = (25, 80, 140, 255),
) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    scanline = bytes((0,)) + bytes(rgba) * width
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", header),
            chunk(b"IDAT", zlib.compress(scanline * height, level=9)),
            chunk(b"IEND", b""),
        )
    )


def _snapshot(root: Path, *, repo_id: str, revision: str) -> str:
    root.mkdir()
    (root / "model_index.json").write_text(
        '{"_class_name":"TestPipeline"}\n',
        encoding="utf-8",
    )
    weights = root / "transformer"
    weights.mkdir()
    (weights / "model.safetensors").write_bytes(b"test-only-weights")
    manifest = build_diffusers_snapshot_manifest(
        root,
        repo_id=repo_id,
        revision=revision,
    )
    manifest_bytes = canonical_snapshot_manifest_bytes(manifest)
    (root / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME).write_bytes(manifest_bytes)
    return hashlib.sha256(manifest_bytes).hexdigest()


def _compiled_scenes():
    scene = SceneEvent(
        event_id="composite_editor_event",
        raw_input="Self decides whether to cross the studio threshold.",
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="composite_editor_evidence",
                modality="image",
                content="self at the studio threshold",
                grounded=True,
                source_ref="test:composite-editor",
                confidence=1.0,
            ),
        ),
        options=(
            DecisionOption(
                option_id="enter_circle",
                label="enter",
                description="cross the threshold",
            ),
            DecisionOption(
                option_id="remain_edge",
                label="remain",
                description="stay behind the threshold",
            ),
        ),
        actors=("self", "group"),
        constraints=("preserve identity",),
        unknowns=("group response",),
    )
    world = EmocioWorld(
        world_id="composite_editor_world",
        visual_memories=("studio doorway",),
        desired_scenes=("shared circle",),
        broken_scenes=("isolation",),
        social_identity_motifs=("belonging",),
        attraction_patterns=("warm light",),
        motor_patterns=("one visible step",),
    )
    packet = build_emocio_packet(scene)
    return compile_emocio_scenes(scene, packet, world)


def _source_artifact(compiled, source_png: bytes) -> ImageArtifact:
    return ImageArtifact(
        image_id="image_test_composite_current",
        request_id="image_request_test_composite_current",
        render_call_id="render_call_test_composite_current",
        source_spec_id=compiled.current_scene.scene_id,
        provider_id="test_current_renderer",
        model="test/current-renderer",
        model_revision="0123456789abcdef0123456789abcdef01234567",
        seed=11,
        input_spec_hash=compiled.current_scene.content_hash(),
        content_sha256=hashlib.sha256(source_png).hexdigest(),
        media_type="image/png",
        grounded=False,
        prompt="Test-only current scene.",
        negative_prompt="",
        path="emocio/images/image_test_composite_current.png",
        width=4,
        height=3,
        generated_only_elements=("test-only details",),
        grounded_mask_path=None,
    )


class RecordingBackend:
    def __init__(self, config, output: bytes) -> None:
        self.config = config
        self.output = output
        self.requests: list[ImageRenderRequest] = []
        self.sources: list[bytes] = []

    def pipeline_spec(self, mode):
        return self.config.pipeline_spec(mode)

    def render(self, request, *, source_png):
        assert source_png is not None
        self.requests.append(request)
        self.sources.append(source_png)
        return self.output


class IncompatibleBackend:
    def __init__(self, config) -> None:
        self.config = config

    def pipeline_spec(self, mode):
        return self.config.pipeline_spec(mode)

    def render(self, request, *, source_png):
        assert request.mode == "image_to_image"
        assert source_png is not None
        raise TypeError("C4-DO-NOT-PERSIST upstream API detail")


def _member(config, snapshot, backend, root: Path) -> CompositeEditorMember:
    store = LocalPngArtifactStore(root)
    renderer = build_editor_renderer(config, backend=backend, artifact_store=store)
    return CompositeEditorMember(
        config=config,
        snapshot=snapshot,
        renderer=renderer,
        artifact_store=store,
    )


def test_composite_screen_reuses_exact_source_and_closes_authority(tmp_path: Path) -> None:
    longcat_root = tmp_path / "longcat-snapshot"
    firered_root = tmp_path / "firered-snapshot"
    longcat_digest = _snapshot(
        longcat_root,
        repo_id=LONGCAT_MODEL_ID,
        revision=LONGCAT_MODEL_REVISION,
    )
    firered_digest = _snapshot(
        firered_root,
        repo_id=FIRERED_MODEL_ID,
        revision=FIRERED_MODEL_REVISION,
    )
    longcat_config = longcat_editor_runtime_config(
        snapshot_path=longcat_root,
        snapshot_manifest_sha256=longcat_digest,
    )
    firered_config = firered_editor_runtime_config(
        snapshot_path=firered_root,
        snapshot_manifest_sha256=firered_digest,
    )
    longcat_snapshot = verify_editor_snapshot(longcat_config)
    firered_snapshot = verify_editor_snapshot(firered_config)
    longcat_backend = RecordingBackend(longcat_config, _png(rgba=(180, 20, 20, 255)))
    firered_backend = RecordingBackend(firered_config, _png(rgba=(20, 180, 20, 255)))
    runner_scene = screen_scene()
    runner_packet = build_emocio_packet(runner_scene)
    compiled = compile_emocio_scenes(
        runner_scene,
        runner_packet,
        screen_world(),
    )
    profile = VisualPromptProfile.create(
        language="en",
        style_id="test_composite_style",
        style_directive="Test-only stable identity and clear spatial action.",
    )
    source = _png()
    source_artifact = _source_artifact(compiled, source)

    result = render_composite_editor_screen(
        members=(
            _member(
                longcat_config,
                longcat_snapshot,
                longcat_backend,
                tmp_path / "longcat-artifacts",
            ),
            _member(
                firered_config,
                firered_snapshot,
                firered_backend,
                tmp_path / "firered-artifacts",
            ),
        ),
        source_scene=compiled.current_scene,
        source_artifact=source_artifact,
        option_rollouts=compiled.option_rollouts,
        source_png=source,
        root_seed=424242,
        prompt_compiler=BilingualStructuredScenePromptCompiler(profile),
        num_inference_steps=2,
        guidance_scale=4.5,
        negative_prompt="",
        timeout_seconds=10.0,
    )

    assert result.technical_execution_passed is True
    assert result.semantic_review_status == "requires_human_review"
    assert result.semantic_quality_gate_passed is False
    assert result.production_authority_granted is False
    assert result.generated_images_are_external_evidence is False
    assert len(result.members) == 2
    expected_source_digest = hashlib.sha256(source).hexdigest()
    assert {
        hashlib.sha256(payload).hexdigest()
        for payload in (*longcat_backend.sources, *firered_backend.sources)
    } == {expected_source_digest}
    assert len(longcat_backend.requests) == len(firered_backend.requests) == 2
    for longcat_request, firered_request in zip(
        longcat_backend.requests,
        firered_backend.requests,
        strict=True,
    ):
        assert longcat_request.prompt == firered_request.prompt
        assert longcat_request.seed == firered_request.seed
        assert longcat_request.source_spec_hash == firered_request.source_spec_hash
        assert longcat_request.source_image is not None
        assert firered_request.source_image is not None
        assert longcat_request.source_image.content_sha256 == expected_source_digest
        assert firered_request.source_image.content_sha256 == expected_source_digest
        assert longcat_request.source_image.image_id == source_artifact.image_id
        assert firered_request.source_image.image_id == source_artifact.image_id
    for member in result.members:
        for item in member.batch.items:
            assert item.call_spec.fallback_policy.mode == "none"
            assert item.artifact is not None
            assert item.artifact.grounded is False
    replay = CompositeEditorScreenResult.model_validate_json(
        result.canonical_json_bytes()
    )
    assert replay == result

    alternate_source_artifact = source_artifact.model_copy(
        update={
            "image_id": "image_wrong_source_lineage",
            "path": "emocio/images/image_wrong_source_lineage.png",
        }
    )
    alternate_member = render_editor_member_screen(
        member=_member(
            longcat_config,
            longcat_snapshot,
            longcat_backend,
            tmp_path / "alternate-source-artifacts",
        ),
        source_scene=compiled.current_scene,
        source_artifact=alternate_source_artifact,
        option_rollouts=compiled.option_rollouts,
        source_png=source,
        root_seed=424242,
        prompt_compiler=BilingualStructuredScenePromptCompiler(profile),
        num_inference_steps=2,
        guidance_scale=4.5,
        negative_prompt="",
        timeout_seconds=10.0,
    )
    with pytest.raises(ValueError, match="exact source lineage"):
        CompositeEditorScreenResult.create(
            source=ImageSourceReference.from_artifact_with_scene_lineage(
                source_artifact
            ),
            source_artifact=source_artifact,
            source_scene=compiled.current_scene,
            root_seed=424242,
            prompt_profile=profile,
            option_order=tuple(
                scene.scene_id for scene in compiled.option_rollouts
            ),
            members=(alternate_member, result.members[1]),
        )

    first_member = result.members[0]
    first_item = first_member.batch.items[0]
    wrong_request = first_item.request.model_copy(update={"style_id": "wrong_style"})
    wrong_item = first_item.model_copy(update={"request": wrong_request})
    wrong_batch = first_member.batch.model_copy(
        update={"items": (wrong_item, *first_member.batch.items[1:])}
    )
    wrong_member = first_member.model_copy(update={"batch": wrong_batch})
    wrong_screen = result.model_copy(
        update={"members": (wrong_member, *result.members[1:])}
    )
    with pytest.raises(ValueError, match="prompt metadata differs"):
        wrong_screen.validate_screen()


def test_editor_runtime_pins_bf16_cpu_offload_and_exact_models(tmp_path: Path) -> None:
    longcat = longcat_editor_runtime_config(
        snapshot_path=tmp_path / "longcat",
        snapshot_manifest_sha256="a" * 64,
    )
    firered = firered_editor_runtime_config(
        snapshot_path=tmp_path / "firered",
        snapshot_manifest_sha256="b" * 64,
    )
    assert longcat.repo_id == LONGCAT_MODEL_ID
    assert longcat.revision == LONGCAT_MODEL_REVISION
    assert firered.repo_id == FIRERED_MODEL_ID
    assert firered.revision == FIRERED_MODEL_REVISION
    assert longcat.guidance_argument == "guidance_scale"
    assert firered.guidance_argument == "true_cfg_scale"
    for config in (longcat, firered):
        parameters = {
            item.name: json.loads(item.canonical_json_value)
            for item in config.pipeline_spec("image_to_image").parameters
        }
        assert parameters["torch_dtype"] == "bfloat16"
        assert parameters["torch_version"] == "2.13.0"
        assert parameters["diffusers_version"] == "0.39.0"
        assert parameters["transformers_version"] == "5.13.0"
        assert parameters["accelerate_version"] == "1.14.0"
        assert parameters["safetensors_version"] == "0.8.0"
        assert parameters["pillow_version"] == "12.3.0"
        assert parameters["enable_model_cpu_offload"] is True
        assert parameters["generator_device"] == "cpu"
        assert parameters["local_files_only"] is True
        assert parameters["network_access"] is False
        assert parameters["mode_supported"] is True


def test_api_incompatibility_fails_closed_with_redacted_stable_code(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "longcat-snapshot"
    digest = _snapshot(
        snapshot_root,
        repo_id=LONGCAT_MODEL_ID,
        revision=LONGCAT_MODEL_REVISION,
    )
    config = longcat_editor_runtime_config(
        snapshot_path=snapshot_root,
        snapshot_manifest_sha256=digest,
    )
    snapshot = verify_editor_snapshot(config)
    runner_scene = screen_scene()
    packet = build_emocio_packet(runner_scene)
    compiled = compile_emocio_scenes(runner_scene, packet, screen_world())
    source_png = _png()
    compiler = BilingualStructuredScenePromptCompiler(
        VisualPromptProfile.create(
            language="en",
            style_id="test_api_incompatibility",
            style_directive="Test-only stable identity and clear spatial action.",
        )
    )

    result = render_editor_member_screen(
        member=_member(
            config,
            snapshot,
            IncompatibleBackend(config),
            tmp_path / "artifacts",
        ),
        source_scene=compiled.current_scene,
        source_artifact=_source_artifact(compiled, source_png),
        option_rollouts=compiled.option_rollouts[:1],
        source_png=source_png,
        root_seed=424240,
        prompt_compiler=compiler,
        num_inference_steps=2,
        guidance_scale=4.5,
        negative_prompt="",
        timeout_seconds=10.0,
    )

    assert result.batch.status == "failed"
    assert len(result.batch.items) == 1
    outcome = result.batch.items[0]
    assert outcome.artifact is None
    assert outcome.call_record.fallback is None
    assert outcome.failure_code == "renderer_api_incompatibility"
    assert outcome.failure_message == (
        "Image renderer provider failed closed (renderer_api_incompatibility)"
    )
    durable = result.batch.canonical_json_bytes()
    assert b"C4-DO-NOT-PERSIST" not in durable
    assert b"upstream API detail" not in durable


def test_lazy_backend_reverifies_snapshot_before_runtime_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_root = tmp_path / "longcat-snapshot"
    digest = _snapshot(
        snapshot_root,
        repo_id=LONGCAT_MODEL_ID,
        revision=LONGCAT_MODEL_REVISION,
    )
    config = longcat_editor_runtime_config(
        snapshot_path=snapshot_root,
        snapshot_manifest_sha256=digest,
    )
    backend = LazyLocalCompositeEditorBackend(config)
    backend.verify_snapshot()
    (snapshot_root / "transformer" / "model.safetensors").write_bytes(
        b"tampered-after-verification"
    )

    imported = False
    import app.backend.rei.emocio.composite_editor as composite_module

    def unexpected_version(_distribution: str) -> str:
        nonlocal imported
        imported = True
        return "0"

    monkeypatch.setattr(composite_module, "version", unexpected_version)
    with pytest.raises(
        ValueError,
        match="snapshot inventory or file digest differs",
    ):
        backend._load_pipeline()
    assert imported is False


def test_matrix_definition_and_compact_prompt_contract_are_complete() -> None:
    runner_scene = screen_scene()
    compiled = compile_emocio_scenes(
        runner_scene,
        build_emocio_packet(runner_scene),
        screen_world(),
    )
    cells = tuple(_matrix_cells(compiled))
    token_audit = _verify_pinned_prompt_token_audit(compiled)

    assert len(cells) == 12
    assert len(token_audit) == 8
    assert max(item["token_count"] for item in token_audit) == 494
    assert all(item["token_count"] <= 512 for item in token_audit)
    assert len(cells) * 2 == 24
    assert len(compiled.option_rollouts) == 2
    assert len(cells) * 2 * len(compiled.option_rollouts) == 48
    assert {cell[2] for cell in cells} == {"en"}
    assert len({cell[0] for cell in cells}) == 12
    assert {cell[1] for cell in cells} == {424240, 424241, 424242}
    assert {cell[3] for cell in cells} == {
        "documentary_cinematic_v1",
        "graphic_novel_v1",
    }
    assert {cell[4] for cell in cells} == {"canonical", "reversed"}

    required_segments = (
        "evidence_boundary=",
        "localized_boundary=",
        "style_id=",
        "style_directive=",
        "scene_data_boundary=",
        "PRIMARY IMAGE EDIT[",
        "primary_edit_execution=",
        "desired_scene_boundary=",
        "option_id[",
        "grounded_evidence_ids[",
        "inferred_elements[",
        "prompt_budget_policy=c4_editor_compact_v1",
        "final_evidence_boundary=",
    )
    canonical_order = tuple(item.scene_id for item in compiled.option_rollouts)
    for cell in cells:
        option_order_mode, compiler, rollouts = cell[4], cell[6], cell[7]
        actual_order = tuple(item.scene_id for item in rollouts)
        assert actual_order == (
            canonical_order
            if option_order_mode == "canonical"
            else tuple(reversed(canonical_order))
        )
        for rollout in rollouts:
            prompt = compiler.compile(rollout)
            assert all(segment in prompt for segment in required_segments)
            assert prompt.count("prompt_budget_policy=c4_editor_compact_v1") == 1
            assert prompt.endswith(
                "final_evidence_boundary=Generated details are imagined and are not "
                "external evidence."
            )


def test_snapshot_tamper_fails_before_optional_runtime_import(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    digest = _snapshot(
        root,
        repo_id=LONGCAT_MODEL_ID,
        revision=LONGCAT_MODEL_REVISION,
    )
    config = longcat_editor_runtime_config(
        snapshot_path=root,
        snapshot_manifest_sha256=digest,
    )
    (root / "transformer" / "model.safetensors").write_bytes(b"tampered")
    with pytest.raises(
        ValueError,
        match="inventory or file digest differs",
    ):
        verify_editor_snapshot(config)


def test_flux_runtime_opt_in_cpu_offload_uses_cpu_generator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_root = tmp_path / "flux"
    manifest_digest = _snapshot(
        snapshot_root,
        repo_id=FLUX_MODEL_ID,
        revision=FLUX_MODEL_REVISION,
    )
    loads: list[dict[str, object]] = []
    generators: list[tuple[str, int]] = []
    offload_count = 0

    class FakeGenerator:
        def __init__(self, *, device: str) -> None:
            self.device = device

        def manual_seed(self, seed: int):
            generators.append((self.device, seed))
            return self

    class FakeOutputImage:
        def save(self, target, *, format: str) -> None:
            assert format == "PNG"
            target.write(_png())

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, path: str, **kwargs):
            loads.append({"path": path, **kwargs})
            return cls()

        def enable_model_cpu_offload(self) -> None:
            nonlocal offload_count
            offload_count += 1

        def __call__(self, **_kwargs):
            return types.SimpleNamespace(images=[FakeOutputImage()])

    fake_torch = types.ModuleType("torch")
    fake_torch.bfloat16 = object()
    fake_torch.Generator = FakeGenerator
    fake_diffusers = types.ModuleType("diffusers")
    fake_diffusers.Flux2KleinPipeline = FakePipeline
    fake_image = types.ModuleType("PIL.Image")
    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = fake_image
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image)
    monkeypatch.setattr("importlib.metadata.version", lambda _package: "0.39.0")

    config = DiffusersRuntimeConfig(
        device="cuda",
        torch_dtype="bfloat16",
        local_files_only=True,
        enable_attention_slicing=False,
        enable_model_cpu_offload=True,
        pipeline_family="flux2_klein",
        local_snapshot_path=str(snapshot_root.resolve()),
        expected_snapshot_manifest_sha256=manifest_digest,
    )
    backend = LazyDiffusersBackend(config)
    compiled = _compiled_scenes()
    request = ImageRenderRequest.create(
        mode="text_to_image",
        source_spec=compiled.current_scene,
        provider=ProviderIdentity.model_validate(
            flux_provider_identity().model_dump(mode="python", round_trip=True)
        ),
        pipeline=backend.pipeline_spec("text_to_image"),
        seed=424239,
        prompt="Generate the frozen current scene.",
        negative_prompt="",
        prompt_language="en",
        width=4,
        height=3,
        num_inference_steps=2,
        guidance_scale=1.0,
    )

    assert backend.render(request, source_png=None) == _png()
    assert offload_count == 1
    assert generators == [("cpu", 424239)]
    assert loads[0]["path"] == str(snapshot_root.resolve())
    parameters = {
        item.name: json.loads(item.canonical_json_value)
        for item in backend.pipeline_spec("text_to_image").parameters
    }
    assert parameters["enable_model_cpu_offload"] is True
    assert parameters["generator_device"] == "cpu"


def test_runner_defaults_to_one_preflight_cell_without_inference(tmp_path: Path) -> None:
    source = _png()
    source_path = tmp_path / "current.png"
    source_path.write_bytes(source)
    runner_scene = screen_scene()
    runner_packet = build_emocio_packet(runner_scene)
    compiled = compile_emocio_scenes(
        runner_scene,
        runner_packet,
        screen_world(),
    )
    provenance_path = tmp_path / "current-artifact.json"
    provenance_path.write_bytes(
        _source_artifact(compiled, source).canonical_json_bytes()
    )
    longcat_root = tmp_path / "longcat"
    firered_root = tmp_path / "firered"
    longcat_digest = _snapshot(
        longcat_root,
        repo_id=LONGCAT_MODEL_ID,
        revision=LONGCAT_MODEL_REVISION,
    )
    firered_digest = _snapshot(
        firered_root,
        repo_id=FIRERED_MODEL_ID,
        revision=FIRERED_MODEL_REVISION,
    )
    output = tmp_path / "preflight"
    status = screen_main(
        [
            "--source-png",
            str(source_path),
            "--source-sha256",
            hashlib.sha256(source).hexdigest(),
            "--source-provenance-json",
            str(provenance_path),
            "--longcat-snapshot-directory",
            str(longcat_root),
            "--longcat-snapshot-manifest-sha256",
            longcat_digest,
            "--firered-snapshot-directory",
            str(firered_root),
            "--firered-snapshot-manifest-sha256",
            firered_digest,
            "--output-directory",
            str(output),
        ]
    )
    assert status == 0
    evidence = json.loads((output / "preflight.json").read_text(encoding="utf-8"))
    assert evidence["execution_requested"] is False
    assert evidence["execution_cell_count"] == 1
    assert evidence["full_robustness_matrix_required_cells"] == 24
    assert evidence["full_robustness_matrix_executed"] is False
    assert evidence["model_cpu_offload_required"] is True
    assert len(evidence["pinned_longcat_prompt_token_audit"]) == 8
    assert evidence["timeout_enforcement_mode"].endswith("no_hard_cancellation")
    assert evidence["semantic_quality_gate_passed"] is False
    assert evidence["production_authority_granted"] is False
    assert not (output / "editor_screen_result.json").exists()


def test_matrix_execution_requires_explicit_soft_timeout_before_io(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="requires an explicit cooperative --timeout-seconds",
    ):
        screen_main(
            [
                "--source-png",
                str(tmp_path / "missing-source.png"),
                "--source-sha256",
                "0" * 64,
                "--source-provenance-json",
                str(tmp_path / "missing-provenance.json"),
                "--longcat-snapshot-directory",
                str(tmp_path / "missing-longcat"),
                "--longcat-snapshot-manifest-sha256",
                "1" * 64,
                "--firered-snapshot-directory",
                str(tmp_path / "missing-firered"),
                "--firered-snapshot-manifest-sha256",
                "2" * 64,
                "--output-directory",
                str(tmp_path / "unused-output"),
                "--screen-mode",
                "matrix",
                "--execute",
            ]
        )


@pytest.mark.parametrize(
    ("kind", "expected_guidance", "passes_dimensions"),
    (
        ("longcat", "guidance_scale", False),
        ("firered", "true_cfg_scale", True),
    ),
)
def test_lazy_backend_fake_runtime_enforces_offload_and_call_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    expected_guidance: str,
    passes_dimensions: bool,
) -> None:
    if kind == "longcat":
        repo_id, revision = LONGCAT_MODEL_ID, LONGCAT_MODEL_REVISION
        config_factory = longcat_editor_runtime_config
    else:
        repo_id, revision = FIRERED_MODEL_ID, FIRERED_MODEL_REVISION
        config_factory = firered_editor_runtime_config
    snapshot_root = tmp_path / kind
    manifest_digest = _snapshot(
        snapshot_root,
        repo_id=repo_id,
        revision=revision,
    )
    config = config_factory(
        snapshot_path=snapshot_root,
        snapshot_manifest_sha256=manifest_digest,
    )
    calls: list[dict[str, object]] = []
    loads: list[dict[str, object]] = []
    offload_count = 0

    class FakeGenerator:
        def __init__(self, *, device: str) -> None:
            self.device = device
            self.seed: int | None = None

        def manual_seed(self, seed: int):
            self.seed = seed
            return self

    class FakeOpenedImage:
        size = (4, 3)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def convert(self, _mode: str):
            return self

        def copy(self):
            return self

    class FakeOutputImage:
        def __init__(self) -> None:
            self.size = (8, 6)

        def convert(self, _mode: str):
            return self

        def resize(self, size, _resampling):
            self.size = size
            return self

        def save(self, target, *, format: str, optimize: bool) -> None:
            assert format == "PNG"
            assert optimize is False
            target.write(_png(self.size[0], self.size[1], rgba=(40, 50, 60, 255)))

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, path: str, **kwargs):
            loads.append({"path": path, **kwargs})
            return cls()

        def enable_model_cpu_offload(self) -> None:
            nonlocal offload_count
            offload_count += 1

        def __call__(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(images=[FakeOutputImage()])

    fake_torch = types.ModuleType("torch")
    fake_torch.bfloat16 = object()
    fake_torch.Generator = FakeGenerator
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: True)
    fake_diffusers = types.ModuleType("diffusers")
    fake_diffusers.LongCatImageEditPipeline = FakePipeline
    fake_diffusers.QwenImageEditPlusPipeline = FakePipeline
    fake_image = types.ModuleType("PIL.Image")
    fake_image.open = lambda _source: FakeOpenedImage()
    fake_image.Resampling = types.SimpleNamespace(LANCZOS="lanczos")
    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = fake_image
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image)
    import app.backend.rei.emocio.composite_editor as composite_module

    versions = {
        "accelerate": "1.14.0",
        "diffusers": "0.39.0",
        "Pillow": "12.3.0",
        "safetensors": "0.8.0",
        "torch": "2.13.0+cu130",
        "transformers": "5.13.0",
    }
    monkeypatch.setattr(composite_module, "version", versions.__getitem__)

    compiled = _compiled_scenes()
    source_png = _png()
    source = ImageSourceReference(
        image_id="fake_current_image",
        content_sha256=hashlib.sha256(source_png).hexdigest(),
        media_type="image/png",
        path="emocio/sources/fake_current_image.png",
        width=4,
        height=3,
        grounded=False,
        originating_scene_spec_id=compiled.current_scene.scene_id,
        originating_scene_spec_hash=compiled.current_scene.content_hash(),
    )
    request = ImageRenderRequest.create(
        mode="image_to_image",
        source_spec=compiled.option_rollouts[0],
        provider=config.provider_identity(),
        pipeline=config.pipeline_spec("image_to_image"),
        seed=73,
        prompt="Perform the exact test-only option edit.",
        negative_prompt="",
        prompt_language="en",
        width=4,
        height=3,
        num_inference_steps=2,
        guidance_scale=4.5,
        source_image=source,
        strength=None,
        conditioning_method="reference_image",
    )
    backend = LazyLocalCompositeEditorBackend(config)
    result = backend.render_with_timeout(
        request,
        source_png=source_png,
        timeout_seconds=10.0,
    )

    assert result == _png(rgba=(40, 50, 60, 255))
    assert offload_count == 1
    assert len(loads) == 1
    assert loads[0]["path"] == str(snapshot_root.resolve())
    assert loads[0]["torch_dtype"] is fake_torch.bfloat16
    assert loads[0]["local_files_only"] is True
    assert loads[0]["use_safetensors"] is True
    assert len(calls) == 1
    assert calls[0][expected_guidance] == 4.5
    assert calls[0]["generator"].device == "cpu"
    assert calls[0]["generator"].seed == 73
    assert ("height" in calls[0], "width" in calls[0]) == (
        passes_dimensions,
        passes_dimensions,
    )


@pytest.mark.parametrize("prompt_language", (None, "sl"))
def test_composite_editor_rejects_non_english_prompt_before_snapshot_or_model(
    tmp_path: Path,
    prompt_language: str | None,
) -> None:
    config = longcat_editor_runtime_config(
        snapshot_path=tmp_path / "unused-model-snapshot",
        snapshot_manifest_sha256="0" * 64,
    )
    compiled = _compiled_scenes()
    source_png = _png()
    source = ImageSourceReference(
        image_id="language_gate_source",
        content_sha256=hashlib.sha256(source_png).hexdigest(),
        media_type="image/png",
        path="emocio/sources/language_gate_source.png",
        width=4,
        height=3,
        grounded=False,
        originating_scene_spec_id=compiled.current_scene.scene_id,
        originating_scene_spec_hash=compiled.current_scene.content_hash(),
    )
    request = ImageRenderRequest.create(
        mode="image_to_image",
        source_spec=compiled.option_rollouts[0],
        provider=config.provider_identity(),
        pipeline=config.pipeline_spec("image_to_image"),
        seed=73,
        prompt="A bounded test-only option edit.",
        negative_prompt="",
        prompt_language=prompt_language,
        width=4,
        height=3,
        num_inference_steps=2,
        guidance_scale=4.5,
        source_image=source,
        strength=None,
        conditioning_method="reference_image",
    )
    backend = LazyLocalCompositeEditorBackend(config)

    with pytest.raises(LocalModelLanguagePolicyError):
        backend.render(request, source_png=source_png)

    assert backend._snapshot is None
    assert backend._pipeline is None
