from __future__ import annotations

import struct
import sys
import types
import zlib
from pathlib import Path

import pytest

from app.backend.rei.emocio.artifacts import LocalPngArtifactStore
from app.backend.rei.emocio.diffusers_renderer import (
    RENDERER_TIMEOUT_FAILURE_CODE,
    DiffusersImageRenderer,
    DiffusersRuntimeConfig,
    LazyDiffusersBackend,
)
from app.backend.rei.models.emocio import VisualSceneSpec
from app.backend.rei.models.provider import (
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
)
from app.backend.rei.models.rendering import ImagePipelineSpec, ImageRenderRequest


def _png(width: int = 4, height: int = 3) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", checksum)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = bytes((0,)) + bytes((20, 70, 130, 255)) * width
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", header),
            chunk(b"IDAT", zlib.compress(row * height, level=9)),
            chunk(b"IEND", b""),
        )
    )


def _identity() -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="timeout_test_renderer",
        kind="image_renderer",
        implementation="tests.rei.TimeoutBackend",
        implementation_revision="1",
        uses_model=True,
        model="test/timeout-image-model",
        model_revision="0123456789abcdef0123456789abcdef01234567",
    )


def _scene() -> VisualSceneSpec:
    return VisualSceneSpec(
        scene_id="timeout_test_scene",
        scene_kind="current",
        option_id=None,
        entities=("observer",),
        self_position="centered",
        attention_structure=(),
        group_belonging="unknown",
        status_relations=(),
        movement=(),
        composition=("stable",),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=(),
        inferred_elements=("test-only scene",),
    )


def _pipeline(identity: ProviderIdentity) -> ImagePipelineSpec:
    return ImagePipelineSpec(
        implementation=identity.implementation,
        implementation_revision=identity.implementation_revision,
    )


def _request(
    identity: ProviderIdentity,
    *,
    pipeline: ImagePipelineSpec | None = None,
) -> ImageRenderRequest:
    return ImageRenderRequest.create(
        mode="text_to_image",
        source_spec=_scene(),
        provider=identity,
        pipeline=pipeline or _pipeline(identity),
        seed=23,
        prompt="timeout test structured scene",
        negative_prompt="",
        width=4,
        height=3,
        num_inference_steps=4,
        guidance_scale=1.0,
    )


def _call(
    request: ImageRenderRequest,
    *,
    timeout_seconds: float = 2.75,
) -> ProviderCallSpec:
    return ProviderCallSpec(
        call_id=f"call_{request.request_id}",
        request_id=request.request_id,
        input_artifact_ids=request.input_artifact_ids,
        provider=request.provider,
        seed=request.seed,
        parameters=request.provider_parameters,
        timeout_seconds=timeout_seconds,
        fallback_policy=ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason="Renderer timeout failures must fail closed.",
        ),
    )


class TimedBackend:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[ImageRenderRequest, bytes | None, float]] = []

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes:
        del request, source_png
        raise AssertionError("The legacy render path must not run for a timed backend")

    def render_with_timeout(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
        timeout_seconds: float,
    ) -> bytes:
        self.calls.append((request, source_png, timeout_seconds))
        if self.fail:
            raise TimeoutError("synthetic cooperative deadline")
        return _png(request.width, request.height)


def _renderer(
    tmp_path: Path,
    *,
    backend: object,
    identity: ProviderIdentity,
    pipeline: ImagePipelineSpec,
) -> DiffusersImageRenderer:
    return DiffusersImageRenderer(
        identity=identity,
        backend=backend,  # type: ignore[arg-type]
        artifact_store=LocalPngArtifactStore(tmp_path / "artifacts"),
        pipeline_specs={
            "text_to_image": pipeline,
            "image_to_image": pipeline,
        },
    )


def test_timed_backend_receives_exact_timeout_and_verified_cache_bypasses_it(
    tmp_path: Path,
) -> None:
    identity = _identity()
    pipeline = _pipeline(identity)
    backend = TimedBackend()
    renderer = _renderer(
        tmp_path,
        backend=backend,
        identity=identity,
        pipeline=pipeline,
    )
    request = _request(identity)
    call = _call(request, timeout_seconds=2.75)

    first = renderer.render(request, call=call)
    backend.fail = True
    replay = renderer.render(request, call=call)

    assert first.artifact is not None
    assert replay.artifact == first.artifact
    assert backend.calls == [(request, None, 2.75)]
    assert replay.call_record.warnings == ("cache_hit_verified",)


def test_timeout_is_structured_timed_out_without_artifact_cache_or_fallback(
    tmp_path: Path,
) -> None:
    identity = _identity()
    pipeline = _pipeline(identity)
    backend = TimedBackend(fail=True)
    renderer = _renderer(
        tmp_path,
        backend=backend,
        identity=identity,
        pipeline=pipeline,
    )
    request = _request(identity)
    call = _call(request)

    outcome = renderer.render(request, call=call)

    assert outcome.artifact is None
    assert outcome.failure_code == RENDERER_TIMEOUT_FAILURE_CODE
    assert outcome.call_record.status == "timed_out"
    assert outcome.call_record.primary_status == "timed_out"
    assert outcome.call_record.fallback is None
    assert outcome.call_record.output_artifact_ids == ()
    assert not tuple((tmp_path / "artifacts").rglob("*.png"))
    assert not (
        tmp_path
        / "artifacts"
        / "emocio"
        / "cache"
        / f"{request.request_id}.json"
    ).exists()


def test_generic_backend_retains_legacy_synchronous_render_path(
    tmp_path: Path,
) -> None:
    class LegacyBackend:
        def __init__(self) -> None:
            self.calls = 0

        def render(
            self,
            request: ImageRenderRequest,
            *,
            source_png: bytes | None,
        ) -> bytes:
            assert source_png is None
            self.calls += 1
            return _png(request.width, request.height)

    identity = _identity()
    pipeline = _pipeline(identity)
    backend = LegacyBackend()
    renderer = _renderer(
        tmp_path,
        backend=backend,
        identity=identity,
        pipeline=pipeline,
    )
    request = _request(identity)

    outcome = renderer.render(request, call=_call(request, timeout_seconds=0.25))

    assert outcome.call_record.status == "succeeded"
    assert outcome.artifact is not None
    assert backend.calls == 1


def _install_fake_diffusers_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    clock: dict[str, float],
    expire_during_load: bool,
) -> type:
    class FakeGenerator:
        def __init__(self, *, device: str) -> None:
            self.device = device

        def manual_seed(self, seed: int):
            self.seed = seed
            return self

    class FakeOutputImage:
        def save(self, output, *, format: str) -> None:
            assert format == "PNG"
            output.write(_png())

    class FakeFlux2KleinPipeline:
        invocations: list[dict[str, object]] = []
        destinations: list[str] = []

        @classmethod
        def from_pretrained(cls, _model: str, **_options):
            if expire_during_load:
                clock["now"] = 2.0
            return cls()

        def to(self, device: str):
            self.destinations.append(device)
            return self

        def __call__(self, **options):
            self.invocations.append(options)
            clock["now"] = 2.0
            callback = options["callback_on_step_end"]
            callback(self, 0, None, {})
            return types.SimpleNamespace(images=[FakeOutputImage()])

    fake_torch = types.ModuleType("torch")
    fake_torch.bfloat16 = "fake-bfloat16"
    fake_torch.Generator = FakeGenerator
    fake_diffusers = types.ModuleType("diffusers")
    fake_diffusers.Flux2KleinPipeline = FakeFlux2KleinPipeline
    fake_image_module = types.ModuleType("PIL.Image")
    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = fake_image_module
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image_module)
    monkeypatch.setattr("importlib.metadata.version", lambda _package: "0.39.0")
    monkeypatch.setattr(
        "app.backend.rei.emocio.diffusers_renderer.time.monotonic",
        lambda: clock["now"],
    )
    return FakeFlux2KleinPipeline


def _lazy_flux_backend_and_request() -> tuple[LazyDiffusersBackend, ImageRenderRequest]:
    backend = LazyDiffusersBackend(
        DiffusersRuntimeConfig(
            device="cuda",
            torch_dtype="bfloat16",
            local_files_only=True,
            enable_attention_slicing=False,
            pipeline_family="flux2_klein",
        )
    )
    identity = _identity().model_copy(
        update={"implementation": "diffusers.Flux2KleinPipeline"}
    )
    request = _request(identity, pipeline=backend.pipeline_spec("text_to_image"))
    return backend, request


def test_lazy_backend_checks_deadline_at_every_diffusion_step_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"now": 0.0}
    fake_pipeline = _install_fake_diffusers_runtime(
        monkeypatch,
        clock=clock,
        expire_during_load=False,
    )
    backend, request = _lazy_flux_backend_and_request()

    with pytest.raises(TimeoutError, match="diffusion_step_0_complete"):
        backend.render_with_timeout(
            request,
            source_png=None,
            timeout_seconds=1.0,
        )

    assert len(fake_pipeline.invocations) == 1
    invocation = fake_pipeline.invocations[0]
    assert callable(invocation["callback_on_step_end"])
    assert invocation["callback_on_step_end_tensor_inputs"] == []


def test_lazy_backend_checks_deadline_after_pipeline_load_without_hard_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"now": 0.0}
    fake_pipeline = _install_fake_diffusers_runtime(
        monkeypatch,
        clock=clock,
        expire_during_load=True,
    )
    backend, request = _lazy_flux_backend_and_request()

    with pytest.raises(TimeoutError, match="pipeline_load_complete"):
        backend.render_with_timeout(
            request,
            source_png=None,
            timeout_seconds=1.0,
        )

    assert fake_pipeline.destinations == []
    assert backend._pipelines == {}
    parameters = {
        item.name: item.canonical_json_value
        for item in backend.pipeline_spec("text_to_image").parameters
    }
    assert parameters["timeout_enforcement_mode"] == (
        '"cooperative_monotonic_deadline"'
    )
    assert parameters["timeout_hard_cancellation"] == "false"
    assert "each_diffusion_step_end" in parameters["timeout_interruption_points"]
