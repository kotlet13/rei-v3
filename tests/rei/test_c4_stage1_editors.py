from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import ValidationError

from app.backend.rei.emocio import c4_stage1_editor as stage1
from app.backend.rei.ids import content_id
from app.backend.rei.emocio.c4_stage1_editor import (
    C4Stage1ChildRuntimeProvenance,
    C4Stage1EditorSpec,
    C4Stage1ImageEvidence,
    C4Stage1LocalSnapshotBinding,
    C4Stage1WorkerRequest,
    C4Stage1WorkerResult,
    VerifiedC4Stage1Snapshot,
    inspect_c4_stage1_png_bytes,
    verify_c4_stage1_snapshot,
)
from app.backend.rei.emocio.diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersSnapshotFile,
    DiffusersSnapshotManifest,
    canonical_snapshot_manifest_bytes,
)
from app.backend.rei.emocio.longcat_turbo_editor import (
    LONGCAT_TURBO_MODEL_ID,
    LONGCAT_TURBO_MODEL_REVISION,
    build_longcat_turbo_worker_request,
    execute_longcat_turbo_stage1,
    longcat_turbo_pipeline_spec,
    longcat_turbo_provider_identity,
    longcat_turbo_stage1_spec,
    run_longcat_turbo_stage1_lazy,
)
from app.backend.rei.emocio.omnigen_editor import (
    OMNIGEN_MODEL_ID,
    OMNIGEN_MODEL_REVISION,
    OMNIGEN_PROMPT_PREFIX,
    build_omnigen_worker_request,
    execute_omnigen_stage1,
    omnigen_pipeline_spec,
    omnigen_provider_identity,
    omnigen_stage1_spec,
    run_omnigen_stage1_lazy,
)
from app.backend.rei.evaluation.c4_stage1_fixture import (
    C4_STAGE1_CURRENT_SCENE_HASH,
    C4_STAGE1_CURRENT_SCENE_ID,
    C4_STAGE1_OPTION_ORDER,
    C4_STAGE1_PROFILE_HASH,
    C4_STAGE1_ROOT_SEED,
    C4_STAGE1_SOURCE_ARTIFACT_ID,
    C4_STAGE1_SOURCE_PNG_SHA256,
    build_c4_stage1_fixture,
    C4Stage1Fixture,
)
from app.backend.rei.models.rendering import ImageSourceReference


def _chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def _png(
    width: int = 1024,
    height: int = 768,
    rgb: tuple[int, int, int] = (25, 80, 140),
) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = bytes((0,)) + bytes(rgb) * width
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", header),
            _chunk(b"IDAT", zlib.compress(row * height, level=9)),
            _chunk(b"IEND", b""),
        )
    )


def _test_spec(
    *,
    provider: str,
    manifest_sha256: str = "0" * 64,
) -> C4Stage1EditorSpec:
    if provider == "longcat":
        identity = longcat_turbo_provider_identity()
        pipeline = longcat_turbo_pipeline_spec(manifest_sha256)
        repo_id = LONGCAT_TURBO_MODEL_ID
        revision = LONGCAT_TURBO_MODEL_REVISION
    else:
        identity = omnigen_provider_identity()
        pipeline = omnigen_pipeline_spec(manifest_sha256)
        repo_id = OMNIGEN_MODEL_ID
        revision = OMNIGEN_MODEL_REVISION
    return C4Stage1EditorSpec.create(
        editor_role="test",
        provider=identity,
        pipeline=pipeline,
        repo_id=repo_id,
        revision=revision,
        license_spdx="Apache-2.0" if provider == "longcat" else "MIT",
        snapshot_manifest_sha256=manifest_sha256,
        snapshot_file_count=2,
        snapshot_total_bytes=2,
    )


def _snapshot(
    root: Path,
    *,
    repo_id: str = LONGCAT_TURBO_MODEL_ID,
    revision: str = LONGCAT_TURBO_MODEL_REVISION,
) -> tuple[C4Stage1EditorSpec, C4Stage1LocalSnapshotBinding, Path]:
    root.mkdir()
    model_index = root / "model_index.json"
    model_index.write_bytes(b"{}")
    transformer = root / "transformer"
    transformer.mkdir()
    weights = transformer / "model.safetensors"
    weights.write_bytes(b"test-weights")
    files = tuple(
        DiffusersSnapshotFile(
            relative_path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size_bytes=path.stat().st_size,
        )
        for path in (model_index, weights)
    )
    manifest = DiffusersSnapshotManifest(
        repo_id=repo_id,
        revision=revision,
        files=files,
    )
    manifest_bytes = canonical_snapshot_manifest_bytes(manifest)
    (root / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME).write_bytes(manifest_bytes)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    spec = C4Stage1EditorSpec.create(
        editor_role="test",
        provider=longcat_turbo_provider_identity(),
        pipeline=longcat_turbo_pipeline_spec(manifest_sha256),
        repo_id=repo_id,
        revision=revision,
        license_spdx="Apache-2.0",
        snapshot_manifest_sha256=manifest_sha256,
        snapshot_file_count=len(files),
        snapshot_total_bytes=sum(item.size_bytes for item in files),
    )
    return spec, C4Stage1LocalSnapshotBinding.create(spec, root), weights


def _source_reference(payload: bytes) -> ImageSourceReference:
    fixture = build_c4_stage1_fixture()
    return ImageSourceReference(
        image_id="test_source_image",
        content_sha256=hashlib.sha256(payload).hexdigest(),
        media_type="image/png",
        path="test/source.png",
        width=1024,
        height=768,
        grounded=False,
        originating_scene_spec_id=fixture.current_scene.scene_id,
        originating_scene_spec_hash=fixture.current_scene_hash,
    )


def _worker_request(provider: str, source_png: bytes):
    fixture = build_c4_stage1_fixture()
    prompt = fixture.prompts[0]
    spec = _test_spec(provider=provider)
    verified = VerifiedC4Stage1Snapshot.create(spec)
    builder = (
        build_longcat_turbo_worker_request
        if provider == "longcat"
        else build_omnigen_worker_request
    )
    return builder(
        editor_spec=spec,
        verified_snapshot=verified,
        scene=prompt.scene,
        source_image=_source_reference(source_png),
        seed=prompt.derived_seed,
        prompt=prompt.prompt,
        profile_hash=fixture.prompt_profile_hash,
    )


class _FakeGenerator:
    def __init__(self, *, device: str) -> None:
        self.device = device
        self.seed = None

    def manual_seed(self, seed: int):
        self.seed = seed
        return self


class _FakeTorch:
    Generator = _FakeGenerator


class _FakePipeline:
    def __init__(self, image: Image.Image) -> None:
        self.image = image
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(images=[self.image])


def _reidentified_runtime(
    runtime: C4Stage1ChildRuntimeProvenance,
    **updates: object,
) -> C4Stage1ChildRuntimeProvenance:
    payload = runtime.model_dump(
        mode="json",
        round_trip=True,
        exclude={"runtime_provenance_id"},
    )
    payload.update(updates)
    payload["runtime_provenance_id"] = content_id(
        "c4_stage1_child_runtime",
        payload,
    )
    return C4Stage1ChildRuntimeProvenance.model_validate_json(json.dumps(payload))


def test_frozen_fixture_rebuilds_exact_source_prompts_seeds_and_order() -> None:
    fixture = build_c4_stage1_fixture()

    assert fixture.current_scene.scene_id == C4_STAGE1_CURRENT_SCENE_ID
    assert fixture.current_scene_hash == C4_STAGE1_CURRENT_SCENE_HASH
    assert fixture.source_image.image_id == C4_STAGE1_SOURCE_ARTIFACT_ID
    assert fixture.source_image.content_sha256 == C4_STAGE1_SOURCE_PNG_SHA256
    assert fixture.prompt_profile_hash == C4_STAGE1_PROFILE_HASH
    assert fixture.root_seed == C4_STAGE1_ROOT_SEED
    assert fixture.option_order == C4_STAGE1_OPTION_ORDER
    assert tuple(item.derived_seed for item in fixture.prompts) == (
        1_366_714_956_115_613_163,
        297_232_311_612_386_773,
    )
    assert tuple(item.prompt_sha256 for item in fixture.prompts) == (
        "3c046f45c9c66bc35e6c1b4890f24cc021e6c692d5ca6b7288951db6d2c54cba",
        "a92224abe970e7deafef346085bc8751d76aea1d484f4268c66131a05c25c25e",
    )


def test_exact_specs_pin_full_dependencies_and_exclude_runtime_paths(
    tmp_path: Path,
) -> None:
    local_path = str(tmp_path.resolve())
    for spec in (longcat_turbo_stage1_spec(), omnigen_stage1_spec()):
        serialized = spec.canonical_json_bytes().decode("utf-8")
        assert local_path not in serialized
        assert "2.13.0+cu130" in serialized
        assert spec.max_cuda_memory_bytes == 31_500 * 1024 * 1024
        assert spec.fallback == "none"
        assert spec.remote_code_allowed is False
        binding = C4Stage1LocalSnapshotBinding.create(spec, tmp_path.resolve())
        assert binding.snapshot_path == tmp_path.resolve()
        assert "snapshot_path" not in type(spec).model_fields
        assert "snapshot_path" not in serialized

    with pytest.raises(ValueError, match="manifest differs"):
        longcat_turbo_stage1_spec("1" * 64)
    with pytest.raises(ValueError, match="manifest differs"):
        omnigen_stage1_spec("2" * 64)


def test_exact_pipeline_specs_capture_every_provider_specific_boundary() -> None:
    longcat = {
        item.name: json.loads(item.canonical_json_value)
        for item in longcat_turbo_pipeline_spec("a" * 64).parameters
    }
    assert longcat["call.negative_prompt"] == ""
    assert longcat["call.num_inference_steps"] == 8
    assert longcat["load.enable_model_cpu_offload"] is True
    assert longcat["output.direct_rgb_png_evidence"] is True

    omni = {
        item.name: json.loads(item.canonical_json_value)
        for item in omnigen_pipeline_spec("b" * 64).parameters
    }
    assert omni["call.prompt_prefix"] == OMNIGEN_PROMPT_PREFIX
    assert omni["call.negative_prompt_argument"] is False
    assert omni["call.height"] is None and omni["call.width"] is None
    assert omni["call.img_guidance_scale"] == 1.6
    assert omni["load.enable_model_cpu_offload"] is False
    assert "no_resize_no_crop" in omni["output.normalization"]


def test_snapshot_verifier_completes_final_inventory_before_callback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec, binding, _ = _snapshot(tmp_path / "snapshot")
    scans = 0
    original = stage1._snapshot_inventory

    def counted(root: Path):
        nonlocal scans
        scans += 1
        return original(root)

    monkeypatch.setattr(stage1, "_snapshot_inventory", counted)
    callback_observations: list[int] = []
    verified = verify_c4_stage1_snapshot(
        spec,
        binding,
        after_verification=lambda: callback_observations.append(scans),
    )

    assert verified == VerifiedC4Stage1Snapshot.create(spec)
    assert callback_observations == [2]


def test_snapshot_verifier_rejects_tamper_and_never_invokes_callback(
    tmp_path: Path,
) -> None:
    spec, binding, weights = _snapshot(tmp_path / "snapshot")
    weights.write_bytes(b"changed-weights")
    callbacks: list[str] = []

    with pytest.raises(ValueError, match="size differs|digest differs"):
        verify_c4_stage1_snapshot(
            spec,
            binding,
            after_verification=lambda: callbacks.append("unsafe"),
        )

    assert callbacks == []


def test_snapshot_verifier_detects_change_at_post_fstat_and_skips_callback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec, binding, weights = _snapshot(tmp_path / "snapshot")
    original = stage1._finish_stable_regular
    callbacks: list[str] = []
    mutated = False

    def mutate_before_post_fstat(descriptor, path, initial_identity):
        nonlocal mutated
        if path == weights and not mutated:
            mutated = True
            with weights.open("ab") as target:
                target.write(b"x")
                target.flush()
                os.fsync(target.fileno())
        return original(descriptor, path, initial_identity)

    monkeypatch.setattr(stage1, "_finish_stable_regular", mutate_before_post_fstat)
    with pytest.raises(ValueError, match="changed while reading"):
        verify_c4_stage1_snapshot(
            spec,
            binding,
            after_verification=lambda: callbacks.append("unsafe"),
        )

    assert mutated is True
    assert callbacks == []


def test_snapshot_verifier_rejects_added_directory_and_link(
    tmp_path: Path,
) -> None:
    spec, binding, weights = _snapshot(tmp_path / "snapshot")
    (binding.snapshot_path / "unexpected").mkdir()
    with pytest.raises(ValueError, match="directory inventory"):
        verify_c4_stage1_snapshot(spec, binding)

    (binding.snapshot_path / "unexpected").rmdir()
    link = binding.snapshot_path / "linked.safetensors"
    try:
        link.symlink_to(weights)
    except OSError:
        pytest.skip("Platform policy does not permit creating a test symlink")
    with pytest.raises(ValueError, match="links and reparse points"):
        verify_c4_stage1_snapshot(spec, binding)


def test_snapshot_verifier_rejects_hard_linked_files(tmp_path: Path) -> None:
    spec, binding, weights = _snapshot(tmp_path / "snapshot")
    hard_link = binding.snapshot_path / "hard-linked.safetensors"
    try:
        os.link(weights, hard_link)
    except OSError:
        pytest.skip("Platform policy does not permit creating a test hard link")
    with pytest.raises(ValueError, match="hard-linked"):
        verify_c4_stage1_snapshot(spec, binding)


def test_strict_raw_png_boundary_rejects_crc_metadata_and_trailing_bytes() -> None:
    payload = _png(width=4, height=3)
    assert inspect_c4_stage1_png_bytes(payload) == (4, 3)

    bad_crc = bytearray(payload)
    bad_crc[-5] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        inspect_c4_stage1_png_bytes(bytes(bad_crc))

    ihdr_end = 8 + 12 + 13
    with_metadata = payload[:ihdr_end] + _chunk(b"tEXt", b"secret") + payload[ihdr_end:]
    with pytest.raises(ValueError, match="ancillary"):
        inspect_c4_stage1_png_bytes(with_metadata)
    with pytest.raises(ValueError, match="trailing"):
        inspect_c4_stage1_png_bytes(payload + b"secret")


def test_longcat_fake_pipeline_receives_exact_kwargs_and_records_both_outputs() -> None:
    source_png = _png()
    request = _worker_request("longcat", source_png)
    pipeline = _FakePipeline(Image.new("RGBA", (800, 600), (100, 20, 30, 255)))

    output = execute_longcat_turbo_stage1(
        request,
        source_png,
        pipeline=pipeline,
        torch_module=_FakeTorch,
        image_module=Image,
    )

    assert set(pipeline.kwargs) == {
        "image",
        "prompt",
        "negative_prompt",
        "num_inference_steps",
        "guidance_scale",
        "num_images_per_prompt",
        "generator",
        "output_type",
        "return_dict",
    }
    assert pipeline.kwargs["prompt"] == request.render_request.prompt
    assert pipeline.kwargs["negative_prompt"] == ""
    assert pipeline.kwargs["num_inference_steps"] == 8
    assert pipeline.kwargs["guidance_scale"] == 1.0
    assert pipeline.kwargs["generator"].device == "cpu"
    assert pipeline.kwargs["generator"].seed == request.render_request.seed
    assert inspect_c4_stage1_png_bytes(output.direct_png) == (800, 600)
    assert inspect_c4_stage1_png_bytes(output.staged_png) == (1024, 768)
    assert output.evidence.direct_png_sha256 != output.evidence.staged_png_sha256


@pytest.mark.parametrize("provider", ("longcat", "omnigen"))
def test_real_provider_worker_request_rejects_any_frozen_prompt_drift(
    provider: str,
) -> None:
    fixture = build_c4_stage1_fixture()
    prompt = fixture.prompts[0]
    if provider == "longcat":
        spec = longcat_turbo_stage1_spec()
        builder = build_longcat_turbo_worker_request
    else:
        spec = omnigen_stage1_spec()
        builder = build_omnigen_worker_request
    verified = VerifiedC4Stage1Snapshot.create(spec)
    request = builder(
        editor_spec=spec,
        verified_snapshot=verified,
        scene=prompt.scene,
        source_image=fixture.source_image,
        seed=prompt.derived_seed,
        prompt=prompt.prompt,
        profile_hash=fixture.prompt_profile_hash,
    )
    assert request.render_request.prompt == prompt.prompt

    with pytest.raises(ValidationError, match="frozen fixture"):
        builder(
            editor_spec=spec,
            verified_snapshot=verified,
            scene=prompt.scene,
            source_image=fixture.source_image,
            seed=prompt.derived_seed,
            prompt=prompt.prompt + " drift",
            profile_hash=fixture.prompt_profile_hash,
        )


def test_omnigen_fake_pipeline_receives_exact_kwargs_without_negative_or_resize() -> (
    None
):
    source_png = _png()
    request = _worker_request("omnigen", source_png)
    pipeline = _FakePipeline(Image.new("RGB", (1024, 768), (10, 30, 80)))

    output = execute_omnigen_stage1(
        request,
        source_png,
        pipeline=pipeline,
        torch_module=_FakeTorch,
        image_module=Image,
    )

    assert set(pipeline.kwargs) == {
        "prompt",
        "input_images",
        "height",
        "width",
        "num_inference_steps",
        "max_input_image_size",
        "timesteps",
        "guidance_scale",
        "img_guidance_scale",
        "use_input_image_size_as_output",
        "num_images_per_prompt",
        "generator",
        "latents",
        "output_type",
        "return_dict",
    }
    assert "negative_prompt" not in pipeline.kwargs
    assert pipeline.kwargs["prompt"] == (
        OMNIGEN_PROMPT_PREFIX + request.render_request.prompt
    )
    assert pipeline.kwargs["input_images"][0].mode == "RGB"
    assert pipeline.kwargs["height"] is None
    assert pipeline.kwargs["width"] is None
    assert pipeline.kwargs["generator"].device == "cpu"
    assert output.direct_png == output.staged_png


@pytest.mark.parametrize(
    ("mode", "size", "error"),
    (("RGBA", (1024, 768), "already be RGB"), ("RGB", (800, 600), "1024x768")),
)
def test_omnigen_fails_closed_on_native_output_mismatch(
    mode: str,
    size: tuple[int, int],
    error: str,
) -> None:
    source_png = _png()
    request = _worker_request("omnigen", source_png)
    pipeline = _FakePipeline(Image.new(mode, size))
    with pytest.raises(ValueError, match=error):
        execute_omnigen_stage1(
            request,
            source_png,
            pipeline=pipeline,
            torch_module=_FakeTorch,
            image_module=Image,
        )


def test_worker_result_requires_path_free_runtime_provenance_and_redacts_failure() -> (
    None
):
    source_png = _png()
    request = _worker_request("longcat", source_png)
    output = execute_longcat_turbo_stage1(
        request,
        source_png,
        pipeline=_FakePipeline(Image.new("RGB", (1024, 768))),
        torch_module=_FakeTorch,
        image_module=Image,
    )
    runtime = C4Stage1ChildRuntimeProvenance.create(
        request,
        pipeline_class="LongCatImageEditPipeline",
        placement="model_cpu_offload",
        model_cpu_offload_enabled=True,
        torch_peak_allocated_bytes=100,
        torch_peak_reserved_bytes=200,
    )
    result = C4Stage1WorkerResult.succeeded(request, output.evidence, runtime)
    assert result.validate_against(request) is result
    assert result.publish_authorized is False
    assert result.published_artifact_id is None
    assert result.runtime_provenance.pytorch_peaks_are_supporting_lower_bound is True
    assert b"C:\\" not in result.canonical_json_bytes()

    failure = C4Stage1WorkerResult.failed(
        request,
        failure_code="snapshot_mismatch",
        failure_message=(
            r"token=secret C:\private\snapshot\weights.safetensors "
            r"C:\output\candidate.png"
        ),
    )
    serialized = failure.canonical_json_bytes()
    assert failure.image_evidence is None
    assert b"secret" not in serialized
    assert b"private" not in serialized
    assert b"candidate.png" not in serialized

    with pytest.raises(ValueError, match="failure code is invalid") as error:
        C4Stage1WorkerResult.failed(
            request,
            failure_code=r"C:\private\secret",
        )
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    ("provider", "wrong_policy"),
    (
        ("longcat", "omnigen_strict_identity_rgb_1024x768"),
        ("omnigen", "longcat_rgb_lanczos_1024x768"),
    ),
)
def test_worker_result_rejects_reidentified_cross_provider_output_policy(
    provider: str,
    wrong_policy: str,
) -> None:
    source_png = _png()
    request = _worker_request(provider, source_png)
    direct_png = _png(rgb=(30, 50, 70))
    staged_png = direct_png if provider == "longcat" else _png(rgb=(70, 50, 30))
    evidence = C4Stage1ImageEvidence.create(
        direct_png=direct_png,
        staged_png=staged_png,
        normalization_policy=wrong_policy,
    )
    if provider == "longcat":
        runtime = C4Stage1ChildRuntimeProvenance.create(
            request,
            pipeline_class="LongCatImageEditPipeline",
            placement="model_cpu_offload",
            model_cpu_offload_enabled=True,
            torch_peak_allocated_bytes=100,
            torch_peak_reserved_bytes=200,
        )
    else:
        runtime = C4Stage1ChildRuntimeProvenance.create(
            request,
            pipeline_class="OmniGenPipeline",
            placement="direct_cuda",
            model_cpu_offload_enabled=False,
            torch_peak_allocated_bytes=100,
            torch_peak_reserved_bytes=200,
        )
    result = C4Stage1WorkerResult.succeeded(request, evidence, runtime)

    assert result.worker_result_id == content_id(
        "c4_stage1_worker_result",
        result.model_dump(
            mode="python",
            round_trip=True,
            exclude={"worker_result_id"},
        ),
    )
    with pytest.raises(ValueError, match="evidence policy differs"):
        result.validate_against(request)


def test_worker_result_rejects_reidentified_nested_runtime_lineage() -> None:
    source_png = _png()
    request = _worker_request("longcat", source_png)
    output = execute_longcat_turbo_stage1(
        request,
        source_png,
        pipeline=_FakePipeline(Image.new("RGB", (1024, 768))),
        torch_module=_FakeTorch,
        image_module=Image,
    )
    runtime = C4Stage1ChildRuntimeProvenance.create(
        request,
        pipeline_class="LongCatImageEditPipeline",
        placement="model_cpu_offload",
        model_cpu_offload_enabled=True,
        torch_peak_allocated_bytes=100,
        torch_peak_reserved_bytes=200,
    )

    provider = runtime.provider.model_dump(mode="json", round_trip=True)
    provider["provider_id"] = "provider_reidentified_adversary"
    pipeline = runtime.pipeline.model_dump(mode="json", round_trip=True)
    pipeline["implementation_revision"] = "0.39.0;reidentified-adversary"
    snapshot_pipeline = runtime.pipeline.model_dump(mode="json", round_trip=True)
    for parameter in snapshot_pipeline["parameters"]:
        if parameter["name"] == "load.snapshot_manifest_sha256":
            parameter["canonical_json_value"] = json.dumps("f" * 64)
            break
    call_parameters = [
        item.model_dump(mode="json", round_trip=True)
        for item in runtime.effective_call_parameters
    ]
    for parameter in call_parameters:
        if parameter["name"] == "guidance_scale":
            parameter["canonical_json_value"] = "1.25"
            break

    mutations = (
        {"provider": provider},
        {"pipeline": pipeline},
        {"pipeline": snapshot_pipeline},
        {"verified_snapshot_id": "verified_snapshot_reidentified_adversary"},
        {"editor_spec_hash": "f" * 64},
        {"effective_seed": runtime.effective_seed + 1},
        {"effective_call_parameters": call_parameters},
    )
    for mutation in mutations:
        reidentified_runtime = _reidentified_runtime(runtime, **mutation)
        result = C4Stage1WorkerResult.succeeded(
            request,
            output.evidence,
            reidentified_runtime,
        )

        assert reidentified_runtime.runtime_provenance_id != (
            runtime.runtime_provenance_id
        )
        with pytest.raises(ValueError, match="runtime provenance differs"):
            result.validate_against(request)


def test_portable_fixture_request_runtime_and_result_round_trip_canonically() -> None:
    fixture = build_c4_stage1_fixture()
    source_png = _png()
    request = _worker_request("longcat", source_png)
    output = execute_longcat_turbo_stage1(
        request,
        source_png,
        pipeline=_FakePipeline(Image.new("RGB", (1024, 768))),
        torch_module=_FakeTorch,
        image_module=Image,
    )
    runtime = C4Stage1ChildRuntimeProvenance.create(
        request,
        pipeline_class="LongCatImageEditPipeline",
        placement="model_cpu_offload",
        model_cpu_offload_enabled=True,
        torch_peak_allocated_bytes=100,
        torch_peak_reserved_bytes=200,
    )
    result = C4Stage1WorkerResult.succeeded(request, output.evidence, runtime)

    for model_type, value in (
        (C4Stage1Fixture, fixture),
        (C4Stage1WorkerRequest, request),
        (C4Stage1ChildRuntimeProvenance, runtime),
        (C4Stage1WorkerResult, result),
    ):
        assert model_type.model_validate_json(value.canonical_json_bytes()) == value


def test_modules_remain_model_free_until_explicit_lazy_entrypoint() -> None:
    assert callable(run_longcat_turbo_stage1_lazy)
    assert callable(run_omnigen_stage1_lazy)
    for name in (
        "app.backend.rei.emocio.longcat_turbo_editor",
        "app.backend.rei.emocio.omnigen_editor",
    ):
        module = sys.modules[name]
        assert "torch" not in module.__dict__
        assert "diffusers" not in module.__dict__
