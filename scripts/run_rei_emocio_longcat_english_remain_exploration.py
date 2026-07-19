"""Run a frozen three-call LongCat REMAIN exploration in English.

This bounded exploratory runner never retries, selects a best result, changes
the prompt between calls, or grants semantic or production authority.
"""

from __future__ import annotations

import argparse
import importlib
import io
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.backend.rei.emocio.renderer import derive_scene_seed  # noqa: E402
from scripts.run_rei_emocio_longcat_seed_exploration import (  # noqa: E402
    LONGCAT_TURBO_MODEL_ID,
    LONGCAT_TURBO_MODEL_REVISION,
    LONGCAT_TURBO_PIPELINE_CLASS,
    LONGCAT_TURBO_SNAPSHOT_MANIFEST_SHA256,
    ModelExecution,
    RealLongCatExecutor,
    SNAPSHOT_MANIFEST_FILENAME,
    _canonical_json,
    _png_bytes,
    _runtime_versions,
    _sha256_bytes,
    _sha256_file,
)

REQUIRED_BRANCH = "codex/emocio-english-remain-v1"
SOURCE_PNG_SHA256 = "3112384b360e5d8375519253947dd6ab94192559be1e0615bf58674d69bce29f"
ROOT_SEEDS = (424240, 424241, 424242)
REMAIN_SCENE_ID = "visual_scene_12e01b7dc48013135871ba28868f8180"
PINNED_REMAIN_SEEDS = {
    424240: 297232311612386773,
    424241: 5194805190723478124,
    424242: 711246560132348517,
}

ENGLISH_REMAIN_PROMPT = (
    "Keep the entire input image unchanged. Preserve exactly four people in their "
    "current positions: the bald man in the mustard-yellow jacket stands on the "
    "gray corridor floor with both white sneakers fully on the corridor side of the "
    "silver threshold, facing the three other adults who remain inside the room. "
    "Preserve the camera viewpoint, doorway, lighting, clothing, and room layout."
)
PROMPT_SHA256 = "bea218feca5c63a89846d89b7882fba1b097fb45d828eb08c50ce42f63ac1564"


@dataclass(frozen=True, slots=True)
class EnglishRemainCall:
    order_index: int
    root_seed: int
    seed: int

    @property
    def key(self) -> str:
        return f"{self.root_seed}:remain_english"

    @property
    def prompt(self) -> str:
        return ENGLISH_REMAIN_PROMPT


def build_call_plan() -> tuple[EnglishRemainCall, ...]:
    calls: list[EnglishRemainCall] = []
    for order_index, root_seed in enumerate(ROOT_SEEDS):
        seed = derive_scene_seed(root_seed, REMAIN_SCENE_ID)
        if seed != PINNED_REMAIN_SEEDS[root_seed]:
            raise RuntimeError(f"derived REMAIN seed differs for root {root_seed}")
        calls.append(EnglishRemainCall(order_index, root_seed, seed))
    return tuple(calls)


CALL_PLAN = build_call_plan()


@dataclass(frozen=True, slots=True)
class EnglishRemainConfig:
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
class EnglishRemainResult:
    run_dir: Path
    manifest_path: Path
    manifest_sha256: str
    technical_passed: bool
    model_call_count: int


def _prepare_run_dir(config: EnglishRemainConfig) -> Path:
    allowed = (config.repo_root / "output" / "exploration").resolve()
    required = (allowed / "emocio_longcat_english_remain").resolve()
    if config.output_root.resolve() != required:
        raise ValueError(
            "English REMAIN output root must be "
            "output/exploration/emocio_longcat_english_remain"
        )
    run_dir = (required / config.run_id).resolve()
    if run_dir.parent != required:
        raise ValueError("English REMAIN run_id must name one direct child directory")
    if run_dir.exists():
        raise FileExistsError(f"English REMAIN run already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_direct(run_dir: Path, filename: str, payload: bytes) -> Path:
    target = (run_dir / filename).resolve()
    if target.parent != run_dir.resolve():
        raise ValueError("English REMAIN artifacts must be direct run-directory members")
    target.write_bytes(payload)
    return target


def _review_template() -> bytes:
    lines = [
        "# English LongCat REMAIN human review",
        "",
        "Compare each generated panel with the same frozen source. Generated images",
        "carry no semantic authority until this template is completed by the user.",
        "",
    ]
    for root_seed in ROOT_SEEDS:
        lines.extend(
            (
                f"## seed_{root_seed}_remain_english.png",
                "",
                "- exactly_four_people_present: yes / no",
                "- same_four_people_and_clothing_preserved: yes / uncertain / no",
                "- mustard_subject_and_both_sneakers_fully_on_corridor_side: yes / uncertain / no",
                "- three_other_adults_still_inside_room: yes / uncertain / no",
                "- positions_and_composition_preserved: yes / uncertain / no",
                "- extra_or_missing_actor_or_object: yes / no",
                "- remain_state_accepted: yes / no",
                "- notes:",
                "",
            )
        )
    lines.extend(
        (
            "## Human phase decision",
            "",
            "- accepted REMAIN images: 0 / 1 / 2 / 3",
            "- English REMAIN accepted in at least 2/3 seeds: yes / no",
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
        "RGB", (thumb[0] * 2, (thumb[1] + label_height) * 3), "white"
    )
    draw = draw_module.Draw(sheet)
    for row, root_seed in enumerate(ROOT_SEEDS):
        panels = (
            (f"Source / root {root_seed}", "source.png"),
            ("English REMAIN", f"seed_{root_seed}_remain_english.png"),
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


class RealEnglishRemainExecutor(RealLongCatExecutor):
    def execute(self, call: EnglishRemainCall, input_png: bytes) -> ModelExecution:
        if self._next_index >= len(CALL_PLAN) or call != CALL_PLAN[self._next_index]:
            raise RuntimeError("English REMAIN call differs from the frozen literal plan")
        if call.key in self.model_call_order:
            raise RuntimeError("English REMAIN exploration forbids retrying a call")
        if _sha256_bytes(call.prompt.encode("utf-8")) != PROMPT_SHA256:
            raise RuntimeError("English REMAIN prompt changed before model execution")
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


def run_english_remain_screen(
    config: EnglishRemainConfig,
    *,
    executor: Any | None = None,
) -> EnglishRemainResult:
    if config.repo_branch != REQUIRED_BRANCH:
        raise ValueError(f"English REMAIN exploration must run on {REQUIRED_BRANCH}")
    if not ENGLISH_REMAIN_PROMPT.isascii():
        raise RuntimeError("frozen English REMAIN prompt must contain ASCII only")
    if _sha256_bytes(ENGLISH_REMAIN_PROMPT.encode("utf-8")) != PROMPT_SHA256:
        raise RuntimeError("frozen English REMAIN prompt digest differs")
    script_path = Path(__file__).resolve(strict=True)
    script_sha256 = _sha256_file(script_path)

    source_path = config.source_path.resolve(strict=True)
    source_png = source_path.read_bytes()
    if _sha256_bytes(source_png) != config.expected_source_sha256:
        raise ValueError("English REMAIN source digest differs")
    image_module = importlib.import_module("PIL.Image")
    with image_module.open(io.BytesIO(source_png)) as opened:
        if opened.size != (1024, 768) or opened.convert("RGB").mode != "RGB":
            raise ValueError("English REMAIN source must be RGB-compatible 1024x768")
    snapshot = config.longcat_snapshot.resolve(strict=True)
    snapshot_manifest = snapshot / SNAPSHOT_MANIFEST_FILENAME
    if _sha256_file(snapshot_manifest) != config.expected_snapshot_manifest_sha256:
        raise ValueError("English REMAIN LongCat snapshot manifest digest differs")

    run_dir = _prepare_run_dir(config)
    source_copy = _write_direct(run_dir, "source.png", source_png)
    review_path = _write_direct(run_dir, "review_template.md", _review_template())
    preflight = {
        "schema_version": "rei-emocio-longcat-english-remain-preflight-v1",
        "run_id": config.run_id,
        "repo_branch": config.repo_branch,
        "repo_commit_sha": config.repo_commit_sha,
        "script_sha256": script_sha256,
        "hypothesis": (
            "One frozen explicit English preservation prompt may retain an accepted "
            "REMAIN state in at least two of three precommitted roots."
        ),
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
        "prompt": {
            "language": "en",
            "text": ENGLISH_REMAIN_PROMPT,
            "sha256": PROMPT_SHA256,
        },
        "planned_model_call_count": len(CALL_PLAN),
        "planned_call_order": [call.key for call in CALL_PLAN],
        "planned_seeds": [call.seed for call in CALL_PLAN],
        "input_policy": "original frozen source bytes for every call",
        "retry_policy": "none",
        "fallback_policy": "none",
        "selection_policy": "retain every output; no best-of-N",
        "human_acceptance_rule": "at least 2/3 REMAIN images accepted",
        "exploratory_no_authority": True,
        "goal_status_required_after_run": "blocked",
    }
    preflight_path = _write_direct(run_dir, "preflight.json", _canonical_json(preflight))
    preflight_sha256 = _sha256_file(preflight_path)

    active = executor or RealEnglishRemainExecutor(config)
    calls: list[dict[str, Any]] = []
    halted = False
    started_at = datetime.now(UTC)
    try:
        for call in CALL_PLAN:
            record: dict[str, Any] = {
                "order_index": call.order_index,
                "key": call.key,
                "root_seed": call.root_seed,
                "stage": "remain_english",
                "option_id": "remain_edge",
                "seed": call.seed,
                "prompt_sha256": PROMPT_SHA256,
                "input_png_sha256": _sha256_bytes(source_png),
                "status": "not_attempted" if halted else "failed",
                "error": None,
            }
            if halted:
                record["duration_seconds"] = 0.0
                calls.append(record)
                _write_direct(
                    run_dir, "partial_calls.json", _canonical_json({"calls": calls})
                )
                continue
            call_started = time.perf_counter()
            try:
                execution = active.execute(call, source_png)
                native_name = f"seed_{call.root_seed}_remain_english_native.png"
                review_name = f"seed_{call.root_seed}_remain_english.png"
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
    script_mutated = _sha256_file(script_path) != script_sha256
    snapshot_manifest_mutated = (
        _sha256_file(snapshot_manifest) != config.expected_snapshot_manifest_sha256
    )
    model_call_count = int(active.model_call_count)
    planned_order = [call.key for call in CALL_PLAN]
    technical_passed = (
        len(calls) == len(CALL_PLAN)
        and all(item["status"] == "succeeded" for item in calls)
        and all(
            item["input_png_sha256"] == config.expected_source_sha256 for item in calls
        )
        and all(
            item.get("native_width") == 1184
            and item.get("native_height") == 896
            and item.get("review_width") == 1024
            and item.get("review_height") == 768
            for item in calls
        )
        and model_call_count == len(CALL_PLAN)
        and list(active.model_call_order) == planned_order
        and not source_mutated
        and not source_copy_mutated
        and not preflight_mutated
        and not script_mutated
        and not snapshot_manifest_mutated
    )
    manifest = {
        "schema_version": "rei-emocio-longcat-english-remain-exploration-v1",
        "run_id": config.run_id,
        "repo_branch": config.repo_branch,
        "repo_commit_sha": config.repo_commit_sha,
        "script_sha256": script_sha256,
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
        "script_mutated": script_mutated,
        "snapshot_manifest_mutated": snapshot_manifest_mutated,
        "source": {
            "filename": "source.png",
            "png_sha256": config.expected_source_sha256,
            "width": 1024,
            "height": 768,
        },
        "runtime_versions": _runtime_versions(),
        "model": preflight["model"],
        "settings": preflight["settings"],
        "prompt": preflight["prompt"],
        "root_seeds": list(ROOT_SEEDS),
        "planned_model_call_count": len(CALL_PLAN),
        "model_call_count": model_call_count,
        "planned_model_call_order": planned_order,
        "model_call_order": list(active.model_call_order),
        "retry_used": False,
        "fallback_used": False,
        "all_outputs_retained": True,
        "human_acceptance_rule": preflight["human_acceptance_rule"],
        "calls": calls,
        "artifacts": {
            "preflight.json": preflight_sha256,
            "partial_calls.json": _sha256_file(run_dir / "partial_calls.json"),
            "contact_sheet.png": _sha256_file(contact_path),
            "review_template.md": _sha256_file(review_path),
        },
    }
    manifest_path = _write_direct(run_dir, "manifest.json", _canonical_json(manifest))
    return EnglishRemainResult(
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
    parser.add_argument(
        "--output-root",
        type=Path,
        default=(REPO_ROOT / "output/exploration/emocio_longcat_english_remain"),
    )
    parser.add_argument("--run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = EnglishRemainConfig(
        repo_root=REPO_ROOT,
        source_path=args.source,
        longcat_snapshot=args.longcat_snapshot,
        output_root=args.output_root,
        run_id=args.run_id or datetime.now(UTC).strftime("english_v1_%Y%m%dT%H%M%SZ"),
        repo_commit_sha=_git_value(REPO_ROOT, "rev-parse", "HEAD"),
        repo_branch=_git_value(REPO_ROOT, "branch", "--show-current"),
    )
    result = run_english_remain_screen(config)
    print(f"run_dir={result.run_dir}")
    print(f"manifest_sha256={result.manifest_sha256}")
    print(f"model_call_count={result.model_call_count}")
    print(f"technical_status={'passed' if result.technical_passed else 'failed'}")
    return 0 if result.technical_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
