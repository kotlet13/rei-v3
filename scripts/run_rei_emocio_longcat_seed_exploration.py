"""Run the bounded V1 LongCat screen: three seeds and at most nine calls.

This exploratory runner never retries, selects a best result, or grants authority.
"""

from __future__ import annotations

import argparse
import gc
import importlib
import io
import os
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

from app.backend.rei.emocio.longcat_turbo_editor import (  # noqa: E402
    LONGCAT_TURBO_MODEL_ID,
    LONGCAT_TURBO_MODEL_REVISION,
    LONGCAT_TURBO_PIPELINE_CLASS,
    LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256,
)
from app.backend.rei.emocio.renderer import derive_scene_seed  # noqa: E402
from scripts.run_rei_emocio_four_image_exploration import (  # noqa: E402
    _canonical_json,
    _runtime_versions,
    _sha256_bytes,
    _sha256_file,
)

REQUIRED_BRANCH = "codex/emocio-exploration-v2"
SOURCE_PNG_SHA256 = "3112384b360e5d8375519253947dd6ab94192559be1e0615bf58674d69bce29f"
SNAPSHOT_MANIFEST_FILENAME = ".rei_snapshot_manifest.json"
ROOT_SEEDS = (424240, 424241, 424242)
ENTER_SCENE_ID = "visual_scene_acbc451d7b30336076e5c1e5bd31e02b"
REMAIN_SCENE_ID = "visual_scene_12e01b7dc48013135871ba28868f8180"
PINNED_SEEDS = {
    424240: (1366714956115613163, 297232311612386773),
    424241: (7949927431006041388, 5194805190723478124),
    424242: (522636512094338117, 711246560132348517),
}

ENTER_PROMPT = (
    "Final image: the same bald man in the mustard-yellow jacket stands naturally "
    "in the empty center foreground of the room, facing the three adults, with his "
    "full body visible and both white sneakers planted on the wooden floor about "
    "one metre beyond the silver threshold. The gray corridor foreground is empty. "
    "Preserve exactly four people, their identities and clothing, the camera "
    "viewpoint, open doorway, lighting, and room layout."
)
CLEANUP_PROMPT = (
    "Remove the leftmost dark-haired man in the navy sweater beside the open wooden "
    "door. Keep the bald man in the mustard-yellow jacket and the other three people, "
    "doorway, threshold, camera, lighting, and room unchanged. Final image: exactly "
    "four people."
)
REMAIN_PROMPT = "\u4fdd\u6301\u8f93\u5165\u56fe\u50cf\u5b8c\u5168\u4e0d\u53d8\u3002"
PROMPT_SHA256 = {
    "enter_pass1": "1c571918990344150f3d7175241fb4b7b89965fce082d637d6caaac07066667c",
    "enter_cleanup": "3928121da90426d6a7b46eefe28d734df3ddf67f119fade9fd8434c487a7bd5d",
    "remain": "9a600bc0b63dd196865f4f808566a92c576218fcf5074b6fd9b3a4c7ced97bb1",
}
Stage = Literal["enter_pass1", "enter_cleanup", "remain"]

@dataclass(frozen=True, slots=True)
class SeedCall:
    order_index: int
    root_seed: int
    stage: Stage
    option_id: Literal["enter_circle", "remain_edge"]
    seed: int

    @property
    def key(self) -> str:
        return f"{self.root_seed}:{self.stage}"

    @property
    def prompt(self) -> str:
        return {
            "enter_pass1": ENTER_PROMPT,
            "enter_cleanup": CLEANUP_PROMPT,
            "remain": REMAIN_PROMPT,
        }[self.stage]


def build_call_plan() -> tuple[SeedCall, ...]:
    calls: list[SeedCall] = []
    for root_seed in ROOT_SEEDS:
        enter_seed = derive_scene_seed(root_seed, ENTER_SCENE_ID)
        remain_seed = derive_scene_seed(root_seed, REMAIN_SCENE_ID)
        if (enter_seed, remain_seed) != PINNED_SEEDS[root_seed]:
            raise RuntimeError(f"derived seeds differ for root {root_seed}")
        calls.extend(
            (
                SeedCall(len(calls), root_seed, "enter_pass1", "enter_circle", enter_seed),
                SeedCall(len(calls) + 1, root_seed, "enter_cleanup", "enter_circle", enter_seed),
                SeedCall(len(calls) + 2, root_seed, "remain", "remain_edge", remain_seed),
            )
        )
    return tuple(calls)


CALL_PLAN = build_call_plan()

@dataclass(frozen=True, slots=True)
class SeedScreenConfig:
    repo_root: Path
    source_path: Path
    longcat_snapshot: Path
    output_root: Path
    run_id: str
    repo_commit_sha: str
    repo_branch: str
    expected_source_sha256: str = SOURCE_PNG_SHA256
    expected_snapshot_manifest_sha256: str = LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256

@dataclass(frozen=True, slots=True)
class ModelExecution:
    native_png: bytes
    review_png: bytes
    native_width: int
    native_height: int
    peak_allocated_bytes: int | None
    peak_reserved_bytes: int | None

@dataclass(frozen=True, slots=True)
class SeedScreenResult:
    run_dir: Path
    manifest_path: Path
    manifest_sha256: str
    technical_passed: bool
    model_call_count: int

def _png_bytes(image: Any) -> bytes:
    target = io.BytesIO()
    image.convert("RGB").save(target, format="PNG")
    return target.getvalue()


def _prepare_run_dir(config: SeedScreenConfig) -> Path:
    allowed = (config.repo_root / "output" / "exploration").resolve()
    required = (allowed / "emocio_longcat_seed_screen").resolve()
    if config.output_root.resolve() != required:
        raise ValueError("V1 output root must be output/exploration/emocio_longcat_seed_screen")
    run_dir = (required / config.run_id).resolve()
    if not run_dir.is_relative_to(allowed):
        raise ValueError("V1 output escapes output/exploration")
    if run_dir.exists():
        raise FileExistsError(f"V1 run already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_direct(run_dir: Path, filename: str, payload: bytes) -> Path:
    target = (run_dir / filename).resolve()
    if target.parent != run_dir.resolve():
        raise ValueError("V1 artifacts must be direct run-directory members")
    target.write_bytes(payload)
    return target

def _review_template() -> bytes:
    lines = [
        "# V1 LongCat seed-screen human review",
        "",
        "Six final images are presented. ENTER pass-1 intermediates are diagnostic only.",
        "Generated images are not external evidence and carry no semantic authority.",
        "",
    ]
    for root_seed in ROOT_SEEDS:
        for option in ("enter", "remain"):
            lines.extend(
                (
                    f"## seed_{root_seed}_{option}.png",
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
        lines.extend(
            (
                f"## root seed {root_seed} pair",
                "",
                "- two_options_visibly_distinct: yes / uncertain / no",
                "- same_underlying_scene: yes / uncertain / no",
                "- pair_useful: yes / uncertain / no",
                "",
            )
        )
    lines.extend(
        (
            "## Human phase decision",
            "",
            "- ENTER useful in at least 2/3 seeds: yes / no",
            "- REMAIN useful in at least 2/3 seeds: yes / no",
            "- complete useful pairs in at least 2/3 seeds: yes / no",
            "- authorize another phase: yes / no",
            "- notes:",
            "",
        )
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _contact_sheet(run_dir: Path) -> bytes:
    image_module = importlib.import_module("PIL.Image")
    draw_module = importlib.import_module("PIL.ImageDraw")
    thumb = (512, 384)
    label_height = 36
    sheet = image_module.new(
        "RGB", (thumb[0] * 3, (thumb[1] + label_height) * 3), "white"
    )
    draw = draw_module.Draw(sheet)
    for row, root_seed in enumerate(ROOT_SEEDS):
        panels = (
            (f"Source / root {root_seed}", "source.png"),
            ("ENTER final", f"seed_{root_seed}_enter.png"),
            ("REMAIN", f"seed_{root_seed}_remain.png"),
        )
        for column, (label, filename) in enumerate(panels):
            x = column * thumb[0]
            y = row * (thumb[1] + label_height)
            draw.text((x + 8, y + 10), label, fill="black")
            path = run_dir / filename
            if path.is_file():
                with image_module.open(path) as opened:
                    panel = opened.convert("RGB")
                    panel.thumbnail(thumb, image_module.Resampling.LANCZOS)
                    canvas = image_module.new("RGB", thumb, "#e8e8e8")
                    canvas.paste(
                        panel,
                        ((thumb[0] - panel.width) // 2, (thumb[1] - panel.height) // 2),
                    )
            else:
                canvas = image_module.new("RGB", thumb, "#d9d9d9")
                draw_module.Draw(canvas).text((12, 12), "technical failure", fill="black")
            sheet.paste(canvas, (x, y + label_height))
    return _png_bytes(sheet)


class RealLongCatExecutor:
    def __init__(self, config: SeedScreenConfig) -> None:
        self.config = config
        self.model_call_count = 0
        self.model_call_order: list[str] = []
        self._next_index = 0
        self._pipeline: Any | None = None
        self._torch: Any | None = None
        self._image: Any | None = None

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["DIFFUSERS_OFFLINE"] = "1"
        torch_module = importlib.import_module("torch")
        diffusers_module = importlib.import_module("diffusers")
        image_module = importlib.import_module("PIL.Image")
        pipeline_class = getattr(diffusers_module, LONGCAT_TURBO_PIPELINE_CLASS)
        pipeline = pipeline_class.from_pretrained(
            str(self.config.longcat_snapshot.resolve(strict=True)),
            local_files_only=True,
            use_safetensors=True,
            torch_dtype=torch_module.bfloat16,
        )
        pipeline.enable_model_cpu_offload()
        self._pipeline = pipeline
        self._torch = torch_module
        self._image = image_module

    def execute(self, call: SeedCall, input_png: bytes) -> ModelExecution:
        if self._next_index >= len(CALL_PLAN) or call != CALL_PLAN[self._next_index]:
            raise RuntimeError("V1 call differs from the frozen literal plan")
        if call.key in self.model_call_order:
            raise RuntimeError("V1 forbids retrying a call")
        self._load()
        assert self._pipeline is not None and self._torch is not None
        assert self._image is not None
        torch_module = self._torch
        if torch_module.cuda.is_available():
            torch_module.cuda.reset_peak_memory_stats()
        with self._image.open(io.BytesIO(input_png)) as opened:
            image = opened.convert("RGB")
        self.model_call_count += 1
        self.model_call_order.append(call.key)
        self._next_index += 1
        output = self._pipeline(
            image=image,
            prompt=call.prompt,
            negative_prompt="",
            num_inference_steps=8,
            guidance_scale=1.0,
            num_images_per_prompt=1,
            generator=torch_module.Generator("cpu").manual_seed(call.seed),
            output_type="pil",
            return_dict=True,
        ).images[0].convert("RGB")
        native_png = _png_bytes(output)
        review = output.resize((1024, 768), self._image.Resampling.LANCZOS)
        allocated = reserved = None
        if torch_module.cuda.is_available():
            allocated = int(torch_module.cuda.max_memory_allocated())
            reserved = int(torch_module.cuda.max_memory_reserved())
        return ModelExecution(
            native_png=native_png,
            review_png=_png_bytes(review),
            native_width=output.width,
            native_height=output.height,
            peak_allocated_bytes=allocated,
            peak_reserved_bytes=reserved,
        )

    def close(self) -> None:
        pipeline = self._pipeline
        self._pipeline = None
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


def run_seed_screen(
    config: SeedScreenConfig,
    *,
    executor: Any | None = None,
) -> SeedScreenResult:
    if config.repo_branch != REQUIRED_BRANCH:
        raise ValueError(f"V1 must run on {REQUIRED_BRANCH}")
    for stage, prompt in (
        ("enter_pass1", ENTER_PROMPT),
        ("enter_cleanup", CLEANUP_PROMPT),
        ("remain", REMAIN_PROMPT),
    ):
        if _sha256_bytes(prompt.encode("utf-8")) != PROMPT_SHA256[stage]:
            raise RuntimeError(f"frozen {stage} prompt digest differs")
    source_path = config.source_path.resolve(strict=True)
    source_png = source_path.read_bytes()
    if _sha256_bytes(source_png) != config.expected_source_sha256:
        raise ValueError("V1 source digest differs")
    image_module = importlib.import_module("PIL.Image")
    with image_module.open(io.BytesIO(source_png)) as opened:
        if opened.size != (1024, 768) or opened.convert("RGB").mode != "RGB":
            raise ValueError("V1 source must be RGB-compatible 1024x768")
    snapshot = config.longcat_snapshot.resolve(strict=True)
    snapshot_manifest = snapshot / SNAPSHOT_MANIFEST_FILENAME
    if _sha256_file(snapshot_manifest) != config.expected_snapshot_manifest_sha256:
        raise ValueError("V1 LongCat snapshot manifest digest differs")

    run_dir = _prepare_run_dir(config)
    source_copy = _write_direct(run_dir, "source.png", source_png)
    review_path = _write_direct(run_dir, "review_template.md", _review_template())
    preflight = {
        "schema_version": "rei-emocio-longcat-seed-preflight-v1",
        "run_id": config.run_id,
        "repo_branch": config.repo_branch,
        "repo_commit_sha": config.repo_commit_sha,
        "script_sha256": _sha256_file(Path(__file__)),
        "source_png_sha256": config.expected_source_sha256,
        "model": {
            "model_id": LONGCAT_TURBO_MODEL_ID,
            "revision": LONGCAT_TURBO_MODEL_REVISION,
            "pipeline_class": LONGCAT_TURBO_PIPELINE_CLASS,
            "snapshot_manifest_sha256": config.expected_snapshot_manifest_sha256,
        },
        "settings": {
            "torch_dtype": "bfloat16",
            "model_cpu_offload": True,
            "local_files_only": True,
            "generator_device": "cpu",
            "num_inference_steps": 8,
            "guidance_scale": 1.0,
            "negative_prompt": "",
            "num_images_per_prompt": 1,
            "output_type": "pil",
            "return_dict": True,
            "review_normalization": "RGB then Pillow LANCZOS 1024x768",
        },
        "root_seeds": list(ROOT_SEEDS),
        "prompts": {
            "enter_pass1": {"text": ENTER_PROMPT, "sha256": PROMPT_SHA256["enter_pass1"]},
            "enter_cleanup": {"text": CLEANUP_PROMPT, "sha256": PROMPT_SHA256["enter_cleanup"]},
            "remain": {"text": REMAIN_PROMPT, "sha256": PROMPT_SHA256["remain"]},
        },
        "planned_model_call_count": len(CALL_PLAN),
        "planned_call_order": [call.key for call in CALL_PLAN],
        "retry_policy": "none",
        "fallback_policy": "none",
        "selection_policy": "retain every output; no best-of-N",
        "exploratory_no_authority": True,
        "goal_status_required_after_run": "blocked",
    }
    preflight_path = _write_direct(run_dir, "preflight.json", _canonical_json(preflight))
    preflight_sha256 = _sha256_file(preflight_path)

    active = executor or RealLongCatExecutor(config)
    calls: list[dict[str, Any]] = []
    enter_intermediates: dict[int, bytes] = {}
    halted = False
    started_at = datetime.now(UTC)
    try:
        for call in CALL_PLAN:
            input_png = (
                enter_intermediates[call.root_seed]
                if call.stage == "enter_cleanup"
                else source_png
            )
            record: dict[str, Any] = {
                "order_index": call.order_index,
                "key": call.key,
                "root_seed": call.root_seed,
                "stage": call.stage,
                "option_id": call.option_id,
                "seed": call.seed,
                "prompt_sha256": PROMPT_SHA256[call.stage],
                "input_png_sha256": _sha256_bytes(input_png),
                "status": "not_attempted" if halted else "failed",
                "error": None,
            }
            if halted:
                record["duration_seconds"] = 0.0
                calls.append(record)
                continue
            call_started = time.perf_counter()
            try:
                execution = active.execute(call, input_png)
                if call.stage == "enter_pass1":
                    enter_intermediates[call.root_seed] = execution.native_png
                    native_name = f"seed_{call.root_seed}_enter_pass1_native.png"
                    review_name = f"seed_{call.root_seed}_enter_pass1.png"
                elif call.stage == "enter_cleanup":
                    native_name = f"seed_{call.root_seed}_enter_native.png"
                    review_name = f"seed_{call.root_seed}_enter.png"
                else:
                    native_name = f"seed_{call.root_seed}_remain_native.png"
                    review_name = f"seed_{call.root_seed}_remain.png"
                native_path = _write_direct(run_dir, native_name, execution.native_png)
                review_output = _write_direct(run_dir, review_name, execution.review_png)
                record.update(
                    status="succeeded",
                    native_output_filename=native_name,
                    native_output_png_sha256=_sha256_file(native_path),
                    native_width=execution.native_width,
                    native_height=execution.native_height,
                    review_output_filename=review_name,
                    review_output_png_sha256=_sha256_file(review_output),
                    review_width=1024,
                    review_height=768,
                    peak_vram_allocated_bytes=execution.peak_allocated_bytes,
                    peak_vram_reserved_bytes=execution.peak_reserved_bytes,
                )
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                halted = True
            record["duration_seconds"] = round(time.perf_counter() - call_started, 6)
            calls.append(record)
            _write_direct(run_dir, "partial_calls.json", _canonical_json({"calls": calls}))
    finally:
        active.close()

    contact_path = _write_direct(run_dir, "contact_sheet.png", _contact_sheet(run_dir))
    source_mutated = _sha256_file(source_path) != config.expected_source_sha256
    source_copy_mutated = _sha256_file(source_copy) != config.expected_source_sha256
    preflight_mutated = _sha256_file(preflight_path) != preflight_sha256
    model_call_count = int(active.model_call_count)
    technical_passed = (
        len(calls) == len(CALL_PLAN)
        and all(item["status"] == "succeeded" for item in calls)
        and model_call_count == len(CALL_PLAN)
        and not source_mutated
        and not source_copy_mutated
        and not preflight_mutated
    )
    manifest = {
        "schema_version": "rei-emocio-longcat-seed-exploration-v1",
        "run_id": config.run_id,
        "repo_branch": config.repo_branch,
        "repo_commit_sha": config.repo_commit_sha,
        "script_sha256": _sha256_file(Path(__file__)),
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "technical_status": "passed" if technical_passed else "failed",
        "semantic_status": "pending_human_review",
        "human_review_status": "pending",
        "exploratory_no_authority": True,
        "generated_images_are_external_evidence": False,
        "semantic_review_performed_by_codex": False,
        "semantic_authority_granted": False,
        "production_authority_granted": False,
        "external_evidence_authority_granted": False,
        "goal_status_after_run": "blocked",
        "source_mutated": source_mutated or source_copy_mutated,
        "preflight_mutated": preflight_mutated,
        "source": {
            "filename": "source.png",
            "png_sha256": config.expected_source_sha256,
            "width": 1024,
            "height": 768,
        },
        "runtime_versions": _runtime_versions(),
        "model": preflight["model"],
        "settings": preflight["settings"],
        "root_seeds": list(ROOT_SEEDS),
        "planned_model_call_count": len(CALL_PLAN),
        "model_call_count": model_call_count,
        "model_call_order": list(active.model_call_order),
        "retry_used": False,
        "fallback_used": False,
        "all_outputs_retained": True,
        "calls": calls,
        "artifacts": {
            "preflight.json": preflight_sha256,
            "contact_sheet.png": _sha256_file(contact_path),
            "review_template.md": _sha256_file(review_path),
        },
    }
    manifest_path = _write_direct(run_dir, "manifest.json", _canonical_json(manifest))
    return SeedScreenResult(
        run_dir=run_dir,
        manifest_path=manifest_path,
        manifest_sha256=_sha256_file(manifest_path),
        technical_passed=technical_passed,
        model_call_count=model_call_count,
    )


def _git_value(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _default_source() -> Path:
    return Path.home() / (
        "Codex/github/rei-v3/output/exploration/emocio_flux_longcat_source_reset/"
        "source_reset_20260716T053913Z/source.png"
    )


def _default_snapshot() -> Path:
    return Path.home() / (
        ".cache/rei-v3-c4-remediation-20260715/"
        "longcat-image-edit-turbo-6a7262de5549f0bf0ec54c08ef7d283ef41f3214"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=_default_source())
    parser.add_argument("--longcat-snapshot", type=Path, default=_default_snapshot())
    parser.add_argument("--output-root", type=Path, default=(
        REPO_ROOT / "output/exploration/emocio_longcat_seed_screen"
    ))
    parser.add_argument("--run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    branch = _git_value(REPO_ROOT, "branch", "--show-current")
    config = SeedScreenConfig(
        repo_root=REPO_ROOT,
        source_path=args.source,
        longcat_snapshot=args.longcat_snapshot,
        output_root=args.output_root,
        run_id=args.run_id or datetime.now(UTC).strftime("v1_%Y%m%dT%H%M%SZ"),
        repo_commit_sha=_git_value(REPO_ROOT, "rev-parse", "HEAD"),
        repo_branch=branch,
    )
    result = run_seed_screen(config)
    print(f"run_dir={result.run_dir}")
    print(f"manifest_sha256={result.manifest_sha256}")
    print(f"model_call_count={result.model_call_count}")
    print(f"technical_status={'passed' if result.technical_passed else 'failed'}")
    return 0 if result.technical_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
