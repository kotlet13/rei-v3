"""Run the bounded, human-reviewed X1 Emocio four-image exploration.

This is deliberately an exploration runner, not a validation or authority
path.  It performs at most four model calls in the frozen provider/option
order and writes only under ``output/exploration``.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.backend.rei.emocio.c4_stage1_editor import (  # noqa: E402
    C4_STAGE1_SOURCE_PNG_SHA256,
    VerifiedC4Stage1Snapshot,
    inspect_c4_stage1_png_bytes,
)
from app.backend.rei.emocio.longcat_turbo_editor import (  # noqa: E402
    LONGCAT_TURBO_MODEL_ID,
    LONGCAT_TURBO_MODEL_REVISION,
    LONGCAT_TURBO_PIPELINE_CLASS,
    LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256,
    build_longcat_turbo_worker_request,
    execute_longcat_turbo_stage1,
    longcat_turbo_stage1_spec,
)
from app.backend.rei.emocio.omnigen_editor import (  # noqa: E402
    OMNIGEN_MODEL_ID,
    OMNIGEN_MODEL_REVISION,
    OMNIGEN_PIPELINE_CLASS,
    OMNIGEN_SNAPSHOT_MANIFEST_SHA256,
    build_omnigen_worker_request,
    execute_omnigen_stage1,
    omnigen_stage1_spec,
)
from app.backend.rei.evaluation.c4_stage1_fixture import (  # noqa: E402
    C4Stage1Fixture,
    C4Stage1PromptBinding,
    build_c4_stage1_fixture,
)


ProviderName = Literal["longcat", "omnigen"]
SNAPSHOT_MANIFEST_FILENAME = ".rei_snapshot_manifest.json"
@dataclass(frozen=True, slots=True)
class ExplorationCall:
    order_index: int
    provider: ProviderName
    option_id: Literal["enter_circle", "remain_edge"]
    output_filename: str

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.option_id}"


CALL_PLAN = (
    ExplorationCall(0, "longcat", "enter_circle", "longcat_enter_circle.png"),
    ExplorationCall(1, "longcat", "remain_edge", "longcat_remain_edge.png"),
    ExplorationCall(2, "omnigen", "enter_circle", "omnigen_enter_circle.png"),
    ExplorationCall(3, "omnigen", "remain_edge", "omnigen_remain_edge.png"),
)


@dataclass(frozen=True, slots=True)
class ExplorationConfig:
    repo_root: Path
    source_path: Path
    longcat_snapshot: Path
    omnigen_snapshot: Path
    output_root: Path
    run_id: str
    repo_commit_sha: str


@dataclass(frozen=True, slots=True)
class ModelExecution:
    png: bytes
    peak_allocated_bytes: int | None
    peak_reserved_bytes: int | None
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class ExplorationResult:
    run_dir: Path
    manifest_path: Path
    manifest_sha256: str
    passed: bool
    model_call_count: int


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _prepare_run_directory(config: ExplorationConfig) -> Path:
    allowed = (config.repo_root / "output" / "exploration").resolve()
    required_root = (allowed / "emocio_four_image_screen").resolve()
    output_root = config.output_root.resolve()
    if output_root != required_root:
        raise ValueError(
            "X1 output root must be output/exploration/emocio_four_image_screen"
        )
    run_dir = (output_root / config.run_id).resolve()
    if not _is_relative_to(run_dir, allowed):
        raise ValueError("X1 run directory escapes output/exploration")
    if run_dir.exists():
        raise FileExistsError(f"X1 run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_in_run(run_dir: Path, filename: str, payload: bytes) -> Path:
    target = (run_dir / filename).resolve()
    if target.parent != run_dir.resolve():
        raise ValueError("X1 output must be a direct member of its run directory")
    target.write_bytes(payload)
    return target


def _runtime_versions() -> dict[str, str]:
    versions = {
        "python": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
    }
    for package, key in (
        ("torch", "torch"),
        ("diffusers", "diffusers"),
        ("transformers", "transformers"),
        ("accelerate", "accelerate"),
        ("safetensors", "safetensors"),
        ("Pillow", "pillow"),
    ):
        try:
            versions[key] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[key] = "unavailable"
    return versions


def _review_template() -> bytes:
    sections = [
        "# X1 human review template",
        "",
        "Do not treat generated images as external evidence or semantic authority.",
        "",
    ]
    for call in CALL_PLAN:
        sections.extend(
            (
                f"## {call.output_filename}",
                "",
                "- source_subject_present: yes / partial / no",
                "- identity_preserved: 0 / 1 / 2",
                "- composition_preserved: 0 / 1 / 2",
                "- option_action_correct: 0 / 1 / 2",
                "- extra_actor_or_object: yes / no",
                "- internally_useful_as_emocio_scene: yes / uncertain / no",
                "- notes:",
                "",
            )
        )
    for provider in ("LongCat", "OmniGen"):
        sections.extend(
            (
                f"## {provider} pair",
                "",
                "- two_options_visibly_distinct: yes / uncertain / no",
                "- same_underlying_scene: yes / uncertain / no",
                "- promising_for_next_experiment: yes / no",
                "",
            )
        )
    return ("\n".join(sections) + "\n").encode("utf-8")


def _contact_sheet(run_dir: Path) -> bytes:
    image_module = importlib.import_module("PIL.Image")
    draw_module = importlib.import_module("PIL.ImageDraw")
    thumb_size = (512, 384)
    label_height = 34
    rows = (
        (
            ("Source", "source.png"),
            ("LongCat - enter", "longcat_enter_circle.png"),
            ("LongCat - remain", "longcat_remain_edge.png"),
        ),
        (
            ("Source", "source.png"),
            ("OmniGen - enter", "omnigen_enter_circle.png"),
            ("OmniGen - remain", "omnigen_remain_edge.png"),
        ),
    )
    sheet = image_module.new(
        "RGB", (thumb_size[0] * 3, (thumb_size[1] + label_height) * 2), "white"
    )
    draw = draw_module.Draw(sheet)
    for row_index, row in enumerate(rows):
        for column_index, (label, filename) in enumerate(row):
            x = column_index * thumb_size[0]
            y = row_index * (thumb_size[1] + label_height)
            draw.text((x + 8, y + 9), label, fill="black")
            path = run_dir / filename
            if path.is_file():
                with image_module.open(path) as opened:
                    panel = opened.convert("RGB")
                    panel.thumbnail(thumb_size, image_module.Resampling.LANCZOS)
                    canvas = image_module.new("RGB", thumb_size, "#e8e8e8")
                    offset = (
                        (thumb_size[0] - panel.width) // 2,
                        (thumb_size[1] - panel.height) // 2,
                    )
                    canvas.paste(panel, offset)
            else:
                canvas = image_module.new("RGB", thumb_size, "#d9d9d9")
                draw_module.Draw(canvas).text((12, 12), "technical failure", fill="black")
            sheet.paste(canvas, (x, y + label_height))
    import io

    target = io.BytesIO()
    sheet.save(target, format="PNG", optimize=False, compress_level=9)
    return target.getvalue()


class RealModelExecutor:
    """Load each frozen model once and expose only its two X1 calls."""

    def __init__(self, config: ExplorationConfig, fixture: C4Stage1Fixture) -> None:
        self.config = config
        self.fixture = fixture
        self.model_call_count = 0
        self.model_call_order: list[str] = []
        self._pipeline: Any | None = None
        self._provider: ProviderName | None = None
        self._torch: Any | None = None
        self._image_module: Any | None = None
        self._load_failures: dict[ProviderName, str] = {}
        self._next_call_index = 0

    def _snapshot(self, provider: ProviderName) -> tuple[Path, str]:
        if provider == "longcat":
            return self.config.longcat_snapshot, LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256
        return self.config.omnigen_snapshot, OMNIGEN_SNAPSHOT_MANIFEST_SHA256

    def _release(self) -> None:
        pipeline = self._pipeline
        self._pipeline = None
        self._provider = None
        if pipeline is not None:
            free_hooks = getattr(pipeline, "maybe_free_model_hooks", None)
            if callable(free_hooks):
                try:
                    free_hooks()
                except Exception:
                    pass
            del pipeline
        gc.collect()
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()

    def _load(self, provider: ProviderName) -> None:
        if self._provider == provider and self._pipeline is not None:
            return
        if provider in self._load_failures:
            raise ProviderLoadError(
                f"{provider} load previously failed; X1 forbids a load retry"
            )
        self._release()
        try:
            snapshot, expected_manifest = self._snapshot(provider)
            snapshot = snapshot.resolve(strict=True)
            manifest = snapshot / SNAPSHOT_MANIFEST_FILENAME
            if _sha256_file(manifest) != expected_manifest:
                raise RuntimeError(f"{provider} snapshot manifest digest differs")
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["DIFFUSERS_OFFLINE"] = "1"
            torch_module = importlib.import_module("torch")
            diffusers_module = importlib.import_module("diffusers")
            image_module = importlib.import_module("PIL.Image")
            class_name = (
                LONGCAT_TURBO_PIPELINE_CLASS
                if provider == "longcat"
                else OMNIGEN_PIPELINE_CLASS
            )
            pipeline_class = getattr(diffusers_module, class_name)
            pipeline = pipeline_class.from_pretrained(
                str(snapshot),
                local_files_only=True,
                use_safetensors=True,
                torch_dtype=torch_module.bfloat16,
            )
            if provider == "longcat":
                pipeline.enable_model_cpu_offload()
            else:
                pipeline.to("cuda")
            self._pipeline = pipeline
            self._provider = provider
            self._torch = torch_module
            self._image_module = image_module
        except Exception as exc:
            self._load_failures[provider] = f"{type(exc).__name__}: {exc}"
            self._release()
            raise ProviderLoadError(self._load_failures[provider]) from exc

    def _counting_pipeline(self, call: ExplorationCall) -> Any:
        parent = self
        delegate = self._pipeline

        class CountingPipeline:
            def __call__(self, *args: Any, **kwargs: Any) -> Any:
                if parent.model_call_count >= len(CALL_PLAN):
                    raise RuntimeError("X1 permits at most four model calls")
                if call != CALL_PLAN[parent._next_call_index]:
                    raise RuntimeError("X1 model call differs from the literal plan")
                if call.key in parent.model_call_order:
                    raise RuntimeError("X1 forbids retrying a model/option call")
                parent.model_call_count += 1
                parent.model_call_order.append(call.key)
                parent._next_call_index += 1
                return delegate(*args, **kwargs)

        return CountingPipeline()

    def execute(
        self,
        call: ExplorationCall,
        binding: C4Stage1PromptBinding,
        source_png: bytes,
    ) -> ModelExecution:
        try:
            self._load(call.provider)
        except ProviderLoadError:
            self._next_call_index = max(self._next_call_index, call.order_index + 1)
            raise
        assert self._torch is not None and self._image_module is not None
        torch_module = self._torch
        if torch_module.cuda.is_available():
            torch_module.cuda.reset_peak_memory_stats()
        if call.provider == "longcat":
            spec = longcat_turbo_stage1_spec()
            request = build_longcat_turbo_worker_request(
                editor_spec=spec,
                verified_snapshot=VerifiedC4Stage1Snapshot.create(spec),
                scene=binding.scene,
                source_image=self.fixture.source_image,
                seed=binding.derived_seed,
                prompt=binding.prompt,
                profile_hash=self.fixture.prompt_profile_hash,
            )
            output = execute_longcat_turbo_stage1(
                request,
                source_png,
                pipeline=self._counting_pipeline(call),
                torch_module=torch_module,
                image_module=self._image_module,
            )
        else:
            spec = omnigen_stage1_spec()
            request = build_omnigen_worker_request(
                editor_spec=spec,
                verified_snapshot=VerifiedC4Stage1Snapshot.create(spec),
                scene=binding.scene,
                source_image=self.fixture.source_image,
                seed=binding.derived_seed,
                prompt=binding.prompt,
                profile_hash=self.fixture.prompt_profile_hash,
            )
            output = execute_omnigen_stage1(
                request,
                source_png,
                pipeline=self._counting_pipeline(call),
                torch_module=torch_module,
                image_module=self._image_module,
            )
        allocated = reserved = None
        if torch_module.cuda.is_available():
            allocated = int(torch_module.cuda.max_memory_allocated())
            reserved = int(torch_module.cuda.max_memory_reserved())
        return ModelExecution(
            png=output.staged_png,
            peak_allocated_bytes=allocated,
            peak_reserved_bytes=reserved,
        )

    def close(self) -> None:
        self._release()


class ProviderLoadError(RuntimeError):
    """A provider-local failure before an inference call was attempted."""


def run_exploration(
    config: ExplorationConfig,
    *,
    executor: Any | None = None,
) -> ExplorationResult:
    source_path = config.source_path.resolve(strict=True)
    source_png = source_path.read_bytes()
    source_hash = _sha256_bytes(source_png)
    if source_hash != C4_STAGE1_SOURCE_PNG_SHA256:
        raise ValueError("X1 source PNG digest differs from the frozen pin")
    if inspect_c4_stage1_png_bytes(source_png) != (1024, 768):
        raise ValueError("X1 source PNG must be exactly 1024x768")
    fixture = build_c4_stage1_fixture()
    if any(
        (
            fixture.generated_images_are_external_evidence,
            fixture.semantic_authority_granted,
            fixture.production_authority_granted,
        )
    ):
        raise RuntimeError("X1 fixture unexpectedly grants authority")
    run_dir = _prepare_run_directory(config)
    source_copy = _write_in_run(run_dir, "source.png", source_png)
    review_path = _write_in_run(run_dir, "review_template.md", _review_template())
    active_executor = executor or RealModelExecutor(config, fixture)
    started_at = datetime.now(UTC)
    call_records: list[dict[str, Any]] = []
    bindings = {item.option_id: item for item in fixture.prompts}
    halt_remaining_calls = False
    try:
        for call in CALL_PLAN:
            binding = bindings[call.option_id]
            record: dict[str, Any] = {
                "order_index": call.order_index,
                "provider": call.provider,
                "option_id": call.option_id,
                "seed": binding.derived_seed,
                "prompt_sha256": binding.prompt_sha256,
                "source_png_sha256": source_hash,
                "output_filename": call.output_filename,
                "status": "failed",
                "warning": None,
                "error": None,
            }
            if halt_remaining_calls:
                record.update(
                    status="not_attempted",
                    error="earlier inference/runtime failure made continuation unsafe",
                    duration_seconds=0.0,
                )
                call_records.append(record)
                continue
            call_started = time.perf_counter()
            try:
                execution = active_executor.execute(call, binding, source_png)
                dimensions = inspect_c4_stage1_png_bytes(execution.png)
                output_path = _write_in_run(
                    run_dir, call.output_filename, execution.png
                )
                record.update(
                    status="succeeded",
                    output_png_sha256=_sha256_file(output_path),
                    output_size_bytes=output_path.stat().st_size,
                    output_width=dimensions[0],
                    output_height=dimensions[1],
                    peak_vram_allocated_bytes=execution.peak_allocated_bytes,
                    peak_vram_reserved_bytes=execution.peak_reserved_bytes,
                    warning=execution.warning,
                )
            except ProviderLoadError as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                halt_remaining_calls = True
            record["duration_seconds"] = round(
                time.perf_counter() - call_started, 6
            )
            call_records.append(record)
    finally:
        active_executor.close()
    contact_path = _write_in_run(run_dir, "contact_sheet.png", _contact_sheet(run_dir))
    source_mutated = _sha256_file(source_path) != source_hash
    source_copy_mutated = _sha256_file(source_copy) != source_hash
    model_call_count = int(active_executor.model_call_count)
    passed = (
        len(call_records) == 4
        and all(item["status"] == "succeeded" for item in call_records)
        and model_call_count == 4
        and not source_mutated
        and not source_copy_mutated
    )
    model_descriptors = {
        "longcat": {
            "model_id": LONGCAT_TURBO_MODEL_ID,
            "revision": LONGCAT_TURBO_MODEL_REVISION,
            "snapshot_manifest_sha256": LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256,
        },
        "omnigen": {
            "model_id": OMNIGEN_MODEL_ID,
            "revision": OMNIGEN_MODEL_REVISION,
            "snapshot_manifest_sha256": OMNIGEN_SNAPSHOT_MANIFEST_SHA256,
        },
    }
    manifest = {
        "schema_version": "rei-emocio-four-image-exploration-v1",
        "run_id": config.run_id,
        "repo_commit_sha": config.repo_commit_sha,
        "script_sha256": _sha256_file(Path(__file__)),
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "technical_status": "passed" if passed else "failed",
        "exploratory_no_authority": True,
        "generated_images_are_external_evidence": False,
        "semantic_review_performed_by_codex": False,
        "semantic_authority_granted": False,
        "production_authority_granted": False,
        "external_evidence_authority_granted": False,
        "source_mutated": source_mutated or source_copy_mutated,
        "source": {
            "artifact_id": fixture.source_image.image_id,
            "png_sha256": source_hash,
            "width": 1024,
            "height": 768,
        },
        "runtime_versions": _runtime_versions(),
        "snapshot_check": "trusted_existing_manifest_digest_only",
        "models": model_descriptors,
        "call_attempt_count": sum(
            item["status"] != "not_attempted" for item in call_records
        ),
        "model_call_count": model_call_count,
        "model_call_order": list(active_executor.model_call_order),
        "calls": call_records,
        "artifacts": {
            "source.png": _sha256_file(source_copy),
            "contact_sheet.png": _sha256_file(contact_path),
            "review_template.md": _sha256_file(review_path),
        },
    }
    manifest_path = _write_in_run(run_dir, "manifest.json", _canonical_json(manifest))
    return ExplorationResult(
        run_dir=run_dir,
        manifest_path=manifest_path,
        manifest_sha256=_sha256_file(manifest_path),
        passed=passed,
        model_call_count=model_call_count,
    )


def _git_head(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _default_paths() -> tuple[Path, Path, Path]:
    cache = Path.home() / ".cache"
    source = (
        cache
        / "rei-v3-c4-screen-20260714"
        / "current-flux2-klein-seed424239-1024x768"
        / "artifacts"
        / "emocio"
        / "images"
        / "image_d1e97e56432b23038b8a01f6fdc24d42.png"
    )
    snapshots = cache / "rei-v3-c4-remediation-20260715"
    longcat = snapshots / (
        "longcat-image-edit-turbo-6a7262de5549f0bf0ec54c08ef7d283ef41f3214"
    )
    omnigen = snapshots / (
        "omnigen-v1-diffusers-016e2f61d12a98303f6bbdf122687694d7984268"
    )
    return source, longcat, omnigen


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    source, longcat, omnigen = _default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=source)
    parser.add_argument("--longcat-snapshot", type=Path, default=longcat)
    parser.add_argument("--omnigen-snapshot", type=Path, default=omnigen)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "output" / "exploration" / "emocio_four_image_screen",
    )
    parser.add_argument("--run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = args.run_id or datetime.now(UTC).strftime("x1_%Y%m%dT%H%M%SZ")
    config = ExplorationConfig(
        repo_root=REPO_ROOT,
        source_path=args.source,
        longcat_snapshot=args.longcat_snapshot,
        omnigen_snapshot=args.omnigen_snapshot,
        output_root=args.output_root,
        run_id=run_id,
        repo_commit_sha=_git_head(REPO_ROOT),
    )
    result = run_exploration(config)
    print(f"run_dir={result.run_dir}")
    print(f"manifest_sha256={result.manifest_sha256}")
    print(f"model_call_count={result.model_call_count}")
    print(f"technical_status={'passed' if result.passed else 'failed'}")
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
