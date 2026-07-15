"""Read-only, integrity-checked C8 Semantic Lab projection.

The GUI must not turn a bounded deterministic result into semantic authority.
This module therefore reads only the frozen C1/C2/C7 evidence already checked
into the repository, cold-validates it, and returns a JSON-ready projection.
It never executes a processor, contacts a model, or writes an artifact.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Iterable

from app.backend.rei.evaluation.integrated_benchmark import (
    C7_EXPECTED_MANIFEST_SHA256,
    C7IntegratedBenchmarkReport,
    C7IntegratedManifest,
)
from app.backend.rei.evaluation.models import (
    SemanticEvaluationResult,
    SemanticEvaluationRun,
)
from app.backend.rei.evaluation.report import render_evaluation_report
from app.backend.rei.ids import canonical_json_bytes, content_id, sha256_hex
from app.backend.rei.models.scene import SceneEvent


SEMANTIC_LAB_SCHEMA_VERSION = "rei-semantic-lab-workbench-v1"
SEMANTIC_LAB_VIEW_ID_KIND = "semantic_lab_workbench"

_C7_MANIFEST_PATH = (
    "knowledge/canon_v2/semantic_lab_v1/c7_integrated/manifest.json"
)
_C7_REPORT_PATH = (
    "Docs/evals/semantic_lab_v1/c7-integrated-2026-07-15/"
    "integrated_benchmark.json"
)
_C7_EXPECTED_REPORT_ID = (
    "c7_integrated_benchmark_57c1db13906284edd641ac7cfbc6f5dc"
)
_C7_EXPECTED_REPORT_HASH = (
    "fb96308989974776e29fbe8c7e1e185211f77155d4726a453e1158b5a3c16adc"
)
_C7_EXPECTED_REPORT_SHA256 = (
    "64224a6c0e9615e7ff1981c334bc97182110014bcc77a1297bc272c311c47394"
)
_C1_FIXTURE_ROOT = "tests/fixtures/semantic_lab_v1"

_MAX_C7_MANIFEST_BYTES = 256 * 1024
_MAX_C1_MANIFEST_BYTES = 128 * 1024
_MAX_C1_FAMILY_BYTES = 256 * 1024
_MAX_C2_METRICS_BYTES = 1024 * 1024
_MAX_C7_REPORT_BYTES = 4 * 1024 * 1024

_EXPECTED_VARIANT_MODES = (
    "sl_canonical",
    "sl_paraphrase",
    "en_operational_gloss",
    "keyword_trap",
    "same_behavior_different_route",
    "same_route_different_behavior",
    "missing_information",
    "contradictory_surface_cue",
)


class SemanticLabIntegrityError(ValueError):
    """Raised when frozen Semantic Lab evidence cannot be trusted."""


def _is_reparse_stat(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse_flag)


def _reject_reparse_components(path: Path, *, label: str) -> None:
    absolute = path.expanduser().absolute()
    for component in reversed((absolute, *absolute.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise SemanticLabIntegrityError(
                f"{label} path metadata is unavailable"
            ) from exc
        if _is_reparse_stat(metadata):
            raise SemanticLabIntegrityError(
                f"{label} cannot traverse a link or reparse point"
            )


def _repository_root(repository_root: str | Path) -> Path:
    requested = Path(repository_root).expanduser()
    _reject_reparse_components(requested, label="Semantic Lab repository root")
    try:
        before = requested.lstat()
        resolved = requested.resolve(strict=True)
        after = resolved.lstat()
    except OSError as exc:
        raise SemanticLabIntegrityError(
            "Semantic Lab repository root is unavailable"
        ) from exc
    if (
        _is_reparse_stat(before)
        or _is_reparse_stat(after)
        or not stat.S_ISDIR(before.st_mode)
        or not stat.S_ISDIR(after.st_mode)
        or not os.path.samestat(before, after)
    ):
        raise SemanticLabIntegrityError(
            "Semantic Lab repository root must be one regular directory"
        )
    return resolved


def _confined_file(root: Path, relative_path: str, *, label: str) -> Path:
    if "\\" in relative_path:
        raise SemanticLabIntegrityError(
            f"{label} must use a portable repository-relative path"
        )
    relative = PurePosixPath(relative_path)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or any(part in {"", "."} for part in relative.parts)
    ):
        raise SemanticLabIntegrityError(f"{label} escaped the repository root")
    candidate = root.joinpath(*relative.parts)
    _reject_reparse_components(candidate, label=label)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise SemanticLabIntegrityError(f"{label} escaped the repository root") from exc
    return candidate


def _read_bounded(path: Path, *, maximum_bytes: int, label: str) -> bytes:
    _reject_reparse_components(path, label=label)
    try:
        before = path.lstat()
    except OSError as exc:
        raise SemanticLabIntegrityError(f"{label} is unavailable") from exc
    if _is_reparse_stat(before) or not stat.S_ISREG(before.st_mode):
        raise SemanticLabIntegrityError(f"{label} must be a regular non-link file")
    if before.st_size <= 0 or before.st_size > maximum_bytes:
        raise SemanticLabIntegrityError(f"{label} exceeds its bounded size")

    descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(before, opened)
            or opened.st_size != before.st_size
        ):
            raise SemanticLabIntegrityError(f"{label} changed before it was opened")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            payload = handle.read(maximum_bytes + 1)
        after = path.lstat()
    except SemanticLabIntegrityError:
        raise
    except OSError as exc:
        raise SemanticLabIntegrityError(f"{label} could not be read safely") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)

    if (
        _is_reparse_stat(after)
        or not stat.S_ISREG(after.st_mode)
        or not os.path.samestat(opened, after)
        or len(payload) != opened.st_size
        or len(payload) > maximum_bytes
    ):
        raise SemanticLabIntegrityError(f"{label} changed while being read")
    return payload


def _reject_constant(value: str) -> None:
    raise SemanticLabIntegrityError(f"Non-finite JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SemanticLabIntegrityError(f"Duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except SemanticLabIntegrityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticLabIntegrityError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise SemanticLabIntegrityError(f"{label} must contain one JSON object")
    return value


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _source_spec(manifest: C7IntegratedManifest, key: str) -> Any:
    matches = tuple(item for item in manifest.source_artifacts if item.artifact_key == key)
    if len(matches) != 1:
        raise SemanticLabIntegrityError(f"C7 manifest lacks one pinned {key} source")
    return matches[0]


def _read_pinned_source(
    root: Path,
    *,
    spec: Any,
    maximum_bytes: int,
    label: str,
) -> tuple[bytes, dict[str, Any]]:
    path = _confined_file(root, spec.path, label=label)
    payload = _read_bounded(path, maximum_bytes=maximum_bytes, label=label)
    digest = _sha256(payload)
    if len(payload) != spec.size_bytes or digest != spec.sha256:
        raise SemanticLabIntegrityError(f"{label} differs from the frozen C7 pin")
    return payload, {
        "path": spec.path,
        "size_bytes": len(payload),
        "sha256": digest,
    }


def _non_empty_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticLabIntegrityError(f"{label} must be non-empty text")
    return value


def _object_list(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise SemanticLabIntegrityError(f"{label} must be a JSON object list")
    return value


def _validate_source_locators(value: Any, *, label: str) -> list[dict[str, Any]]:
    locators = _object_list(value, label=label)
    if not locators:
        raise SemanticLabIntegrityError(f"{label} cannot be empty")
    for locator in locators:
        _non_empty_text(locator.get("source_file"), label=f"{label} source_file")
        _non_empty_text(locator.get("section"), label=f"{label} section")
        _non_empty_text(
            locator.get("excerpt_summary_sl"), label=f"{label} excerpt_summary_sl"
        )
        claim_ids = locator.get("claim_ids")
        if (
            not isinstance(claim_ids, list)
            or not claim_ids
            or any(not isinstance(item, str) or not item for item in claim_ids)
            or len(set(claim_ids)) != len(claim_ids)
        ):
            raise SemanticLabIntegrityError(f"{label} claim IDs are invalid")
        page = locator.get("page")
        if page is not None and (not isinstance(page, int) or page < 1):
            raise SemanticLabIntegrityError(f"{label} page is invalid")
    return locators


def _validate_family(
    document: dict[str, Any],
    *,
    expected_family_id: str,
    variant_modes: tuple[str, ...],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if (
        document.get("schema_version") != "rei-semantic-family-fixture-v1"
        or document.get("family_id") != expected_family_id
        or document.get("review_status") != "canon_approved"
        or document.get("model_generated_gold") is not False
        or document.get("training_export") is not False
    ):
        raise SemanticLabIntegrityError(
            f"C1 family {expected_family_id} differs from its approved contract"
        )
    _non_empty_text(document.get("title_sl"), label="C1 family title_sl")
    _non_empty_text(document.get("purpose"), label="C1 family purpose")
    _non_empty_text(document.get("source_hash"), label="C1 family source_hash")
    locators = _validate_source_locators(
        document.get("source_locators"), label="C1 family source locators"
    )
    try:
        scene = SceneEvent.model_validate_json(
            canonical_json_bytes(document.get("grounded_scene"))
        )
    except ValueError as exc:
        raise SemanticLabIntegrityError(
            f"C1 family {expected_family_id} has an invalid grounded scene"
        ) from exc

    variants = _object_list(document.get("variants"), label="C1 variants")
    if len(variants) != len(variant_modes):
        raise SemanticLabIntegrityError(
            f"C1 family {expected_family_id} must contain eight variants"
        )
    modes = tuple(item.get("mode") for item in variants)
    if modes != variant_modes:
        raise SemanticLabIntegrityError(
            f"C1 family {expected_family_id} variant order differs from the manifest"
        )
    seen_variant_ids: set[str] = set()
    projected_variants: list[dict[str, Any]] = []
    for variant in variants:
        mode = _non_empty_text(variant.get("mode"), label="C1 variant mode")
        variant_id = _non_empty_text(
            variant.get("variant_id"), label="C1 variant ID"
        )
        expected_variant_id = f"{expected_family_id}__{mode}"
        if variant_id != expected_variant_id or variant_id in seen_variant_ids:
            raise SemanticLabIntegrityError(
                f"C1 family {expected_family_id} has a non-canonical variant ID"
            )
        seen_variant_ids.add(variant_id)
        language = variant.get("language")
        expected_language = "en" if mode == "en_operational_gloss" else "sl"
        if language != expected_language:
            raise SemanticLabIntegrityError(
                f"C1 variant {variant_id} has a non-canonical language"
            )
        _non_empty_text(variant.get("input_text"), label="C1 variant input")
        routes = _object_list(
            variant.get("expected_routes"), label="C1 expected routes"
        )
        if not routes:
            raise SemanticLabIntegrityError(f"C1 variant {variant_id} lacks a route")
        route_ids: set[str] = set()
        for route in routes:
            route_id = _non_empty_text(route.get("route_id"), label="C1 route ID")
            if (
                route_id in route_ids
                or route.get("family_id") != expected_family_id
                or route.get("variant_id") != variant_id
                or route.get("schema_version") != "rei-canonical-native-route-v1"
                or route.get("mind") not in {"R", "E", "I"}
            ):
                raise SemanticLabIntegrityError(
                    f"C1 variant {variant_id} has an invalid canonical route"
                )
            route_ids.add(route_id)
        interpretations = _object_list(
            variant.get("interpretation_variants"),
            label="C1 interpretation truth",
        )
        interpretation_ids: set[str] = set()
        for interpretation in interpretations:
            interpretation_id = _non_empty_text(
                interpretation.get("interpretation_id"),
                label="C1 interpretation ID",
            )
            if (
                interpretation_id in interpretation_ids
                or interpretation.get("family_id") != expected_family_id
                or interpretation.get("variant_id") != variant_id
                or interpretation.get("schema_version")
                != "rei-canonical-interpretation-variant-v1"
                or interpretation.get("source_mind") not in {"E", "I"}
            ):
                raise SemanticLabIntegrityError(
                    f"C1 variant {variant_id} has invalid interpretation truth"
                )
            interpretation_ids.add(interpretation_id)
        projected_variants.append(
            {
                "variant_id": variant_id,
                "input_text": variant["input_text"],
                "language": language,
                "mode": mode,
                "perturbation": variant.get("perturbation"),
                "expected_routes": routes,
                "expected_interpretation_truth": interpretations,
                "reviewer_status": "canon_approved",
            }
        )
    return (
        {
            "family_id": expected_family_id,
            "title_sl": document["title_sl"],
            "purpose": document["purpose"],
            "source_locators": locators,
            "grounded_scene": scene.model_dump(mode="json"),
            "reviewer_status": "canon_approved",
            "forbidden_shortcuts": list(document.get("forbidden_shortcuts", ())),
        },
        projected_variants,
    )


def _load_c1_families(
    root: Path,
    *,
    manifest_payload: bytes,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    manifest = _json_object(manifest_payload, label="C1 fixture manifest")
    if (
        manifest.get("schema_version") != "rei-semantic-fixture-manifest-v1"
        or manifest.get("family_count") != 24
        or manifest.get("variant_count") != 192
        or manifest.get("review_status") != "canon_approved"
        or manifest.get("model_generated_gold") is not False
        or manifest.get("training_export") is not False
        or tuple(manifest.get("variant_modes", ())) != _EXPECTED_VARIANT_MODES
    ):
        raise SemanticLabIntegrityError("C1 fixture manifest differs from its contract")
    files = _object_list(manifest.get("files"), label="C1 manifest files")
    if len(files) != 24:
        raise SemanticLabIntegrityError("C1 manifest must enumerate 24 family files")
    family_ids = tuple(item.get("family_id") for item in files)
    if family_ids != tuple(sorted(set(family_ids))):
        raise SemanticLabIntegrityError(
            "C1 family manifest order or identity is non-canonical"
        )

    families: list[dict[str, Any]] = []
    variant_index: dict[str, dict[str, Any]] = {}
    for entry in files:
        family_id = _non_empty_text(entry.get("family_id"), label="C1 family ID")
        relative_name = _non_empty_text(entry.get("path"), label="C1 family path")
        relative = PurePosixPath(relative_name)
        if (
            relative.is_absolute()
            or len(relative.parts) != 1
            or relative.suffix != ".json"
            or relative.name != relative_name
            or entry.get("variant_count") != 8
        ):
            raise SemanticLabIntegrityError("C1 family path escaped its fixture root")
        relative_path = f"{_C1_FIXTURE_ROOT}/{relative_name}"
        path = _confined_file(root, relative_path, label="C1 family fixture")
        payload = _read_bounded(
            path,
            maximum_bytes=_MAX_C1_FAMILY_BYTES,
            label="C1 family fixture",
        )
        digest = _sha256(payload)
        if digest != entry.get("sha256"):
            raise SemanticLabIntegrityError(
                f"C1 family fixture hash differs: {family_id}"
            )
        document = _json_object(payload, label=f"C1 family {family_id}")
        family, variants = _validate_family(
            document,
            expected_family_id=family_id,
            variant_modes=_EXPECTED_VARIANT_MODES,
        )
        family["fixture"] = {
            "path": relative_path,
            "size_bytes": len(payload),
            "sha256": digest,
            "source_hash": document["source_hash"],
        }
        family["variants"] = variants
        families.append(family)
        for variant in variants:
            variant_id = variant["variant_id"]
            if variant_id in variant_index:
                raise SemanticLabIntegrityError("C1 variant IDs must be globally unique")
            variant_index[variant_id] = variant
    if len(variant_index) != 192:
        raise SemanticLabIntegrityError("C1 corpus must contain exactly 192 variants")
    return families, variant_index


def _load_c2_run(payload: bytes) -> tuple[dict[str, Any], SemanticEvaluationRun]:
    report = _json_object(payload, label="C2 metrics report")
    results = report.get("results")
    dimensions = report.get("dimensions")
    if (
        report.get("schema_version") != "rei-semantic-metrics-report-v1"
        or report.get("evaluator_version") != "c2-v1"
        or report.get("result_count") != 32
        or report.get("evaluator_model_calls") != 0
        or not isinstance(results, list)
        or len(results) != 32
        or sum(item.get("passed") is True for item in results if isinstance(item, dict))
        != 8
        or not isinstance(dimensions, dict)
        or len(dimensions) != 26
        or report.get("report_policy")
        != {
            "dimensions_preserved_separately": True,
            "global_rei_score": False,
            "single_cross_dimension_rank": False,
        }
    ):
        raise SemanticLabIntegrityError("C2 metrics report differs from its contract")
    try:
        typed_results = tuple(
            SemanticEvaluationResult.model_validate_json(canonical_json_bytes(item))
            for item in results
        )
        run = SemanticEvaluationRun(
            run_id=report["run_id"],
            source_manifest_hash=report["source_manifest_hash"],
            evaluator_version=report["evaluator_version"],
            results=typed_results,
            manually_reviewed_case_ids=tuple(report["manually_reviewed_case_ids"]),
            ablation_ids=tuple(report["ablation_ids"]),
            resource_telemetry_artifact_ids=tuple(
                report["resource_telemetry_artifact_ids"]
            ),
            evaluator_model_calls=report["evaluator_model_calls"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SemanticLabIntegrityError("C2 results failed cold typed validation") from exc
    if render_evaluation_report(run).get("metrics.json") != payload:
        raise SemanticLabIntegrityError(
            "C2 metrics report differs from byte-identical typed replay"
        )
    return report, run


def _project_c2_result(result: SemanticEvaluationResult) -> dict[str, Any]:
    failure_tags = sorted({issue.issue_code for issue in result.issues})
    return {
        "result_id": result.result_id,
        "subject_id": result.subject_id,
        "subject_kind": result.subject_kind,
        "family_id": result.family_id,
        "variant_id": result.variant_id,
        "mind": result.mind,
        "actual_route_ids": list(result.context.actual_route_ids),
        "expected_route_ids": list(result.context.expected_route_ids),
        "expected_label": result.expected_label,
        "observed_label": result.observed_label,
        "passed": result.passed,
        "reviewer_status": result.context.review_status,
        "failure_tags": failure_tags,
        "issues": [item.model_dump(mode="json") for item in result.issues],
        "evaluator_model_calls": result.evaluator_model_calls,
    }


def _evaluation_projection(
    results: Iterable[SemanticEvaluationResult],
) -> dict[str, Any]:
    ordered = tuple(
        sorted(
            results,
            key=lambda item: (
                item.subject_kind,
                item.subject_id,
                item.result_id,
            ),
        )
    )
    if not ordered:
        return {
            "status": "not_executed",
            "reason": "no_c2_result_for_variant",
            "actual_route_ids": [],
            "actual_labels": [],
            "reviewer_statuses": [],
            "failure_tags": ["c2_not_executed"],
            "results": [],
        }
    projected = [_project_c2_result(item) for item in ordered]
    return {
        "status": "executed",
        "reason": None,
        "actual_route_ids": sorted(
            {
                route_id
                for item in ordered
                for route_id in item.context.actual_route_ids
            }
        ),
        "actual_labels": sorted({item.observed_label for item in ordered}),
        "reviewer_statuses": sorted(
            {
                item.context.review_status
                for item in ordered
                if item.context.review_status is not None
            }
        ),
        "failure_tags": sorted(
            {issue.issue_code for item in ordered for issue in item.issues}
        ),
        "results": projected,
    }


def _attach_c2_results(
    families: list[dict[str, Any]],
    *,
    run: SemanticEvaluationRun,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_variant: dict[str, list[SemanticEvaluationResult]] = defaultdict(list)
    by_family: dict[str, list[SemanticEvaluationResult]] = defaultdict(list)
    unscoped: list[SemanticEvaluationResult] = []
    known_family_ids = {item["family_id"] for item in families}
    variant_family_by_id = {
        variant["variant_id"]: family["family_id"]
        for family in families
        for variant in family["variants"]
    }
    for result in run.results:
        if result.variant_id is not None:
            expected_family_id = variant_family_by_id.get(result.variant_id)
            if (
                expected_family_id is None
                or result.family_id not in known_family_ids
                or result.family_id != expected_family_id
            ):
                raise SemanticLabIntegrityError(
                    "C2 result family and variant binding differs from C1"
                )
            by_variant[result.variant_id].append(result)
        elif result.family_id is not None:
            if result.family_id not in known_family_ids:
                raise SemanticLabIntegrityError("C2 result cites an unknown C1 family")
            by_family[result.family_id].append(result)
        else:
            unscoped.append(result)

    for family in families:
        canonical = next(
            item for item in family["variants"] if item["mode"] == "sl_canonical"
        )
        english = next(
            item
            for item in family["variants"]
            if item["mode"] == "en_operational_gloss"
        )
        side_by_side = {
            "sl": canonical["input_text"],
            "en": english["input_text"],
        }
        family_results = tuple(by_family.get(family["family_id"], ()))
        family["family_evaluation"] = _evaluation_projection(family_results)
        family_failure_tags = set(family["family_evaluation"]["failure_tags"])
        for variant in family["variants"]:
            variant["side_by_side"] = side_by_side
            evaluation = _evaluation_projection(by_variant.get(variant["variant_id"], ()))
            variant["evaluation"] = evaluation
            variant["failure_tags"] = list(evaluation["failure_tags"])
            family_failure_tags.update(evaluation["failure_tags"])
        family["failure_tags"] = sorted(family_failure_tags)
        family["c2_executed_variant_count"] = sum(
            item["evaluation"]["status"] == "executed"
            for item in family["variants"]
        )

    return families, {
        "run_id": run.run_id,
        "source_manifest_hash": run.source_manifest_hash,
        "result_count": len(run.results),
        "passing_result_count": sum(item.passed for item in run.results),
        "executed_variant_count": len(by_variant),
        "not_executed_variant_count": 192 - len(by_variant),
        "family_level_result_count": sum(len(items) for items in by_family.values()),
        "unscoped_result_count": len(unscoped),
        "unscoped_results": [
            _project_c2_result(item)
            for item in sorted(
                unscoped,
                key=lambda item: (item.subject_kind, item.subject_id, item.result_id),
            )
        ],
        "evaluator_model_calls": run.evaluator_model_calls,
        "dimensions_preserved_separately": True,
        "global_rei_score_present": False,
    }


def _load_c7_report(
    root: Path,
    *,
    manifest: C7IntegratedManifest,
    manifest_sha256: str,
) -> tuple[C7IntegratedBenchmarkReport, dict[str, Any]]:
    path = _confined_file(root, _C7_REPORT_PATH, label="C7 integrated report")
    payload = _read_bounded(
        path,
        maximum_bytes=_MAX_C7_REPORT_BYTES,
        label="C7 integrated report",
    )
    payload_sha256 = _sha256(payload)
    if payload_sha256 != _C7_EXPECTED_REPORT_SHA256:
        raise SemanticLabIntegrityError("C7 report bytes differ from the frozen pin")
    try:
        report = C7IntegratedBenchmarkReport.model_validate_json(payload)
    except ValueError as exc:
        raise SemanticLabIntegrityError(
            "C7 integrated report failed cold typed validation"
        ) from exc
    canonical = canonical_json_bytes(report.model_dump(mode="python", round_trip=True))
    if payload != canonical:
        raise SemanticLabIntegrityError("C7 integrated report is not byte-canonical")
    if report.manifest != manifest or report.manifest_sha256 != manifest_sha256:
        raise SemanticLabIntegrityError("C7 report differs from the frozen manifest")
    if (
        report.report_id != _C7_EXPECTED_REPORT_ID
        or report.report_hash != _C7_EXPECTED_REPORT_HASH
    ):
        raise SemanticLabIntegrityError("C7 report identity differs from the frozen pin")
    return report, {
        "path": _C7_REPORT_PATH,
        "size_bytes": len(payload),
        "sha256": payload_sha256,
        "report_id": report.report_id,
        "report_hash": report.report_hash,
    }


def _benchmark_status(report: C7IntegratedBenchmarkReport) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "report_hash": report.report_hash,
        "technical": {
            "contract_passed": report.technical_contract_passed,
        },
        "research": {
            "quality_status": report.research_quality_status,
            "blockers": [
                {
                    "code": item.blocker_code,
                    "detail": item.detail,
                    "affected_ablation_families": list(
                        item.affected_ablation_families
                    ),
                    "affected_metric_dimensions": list(
                        item.affected_metric_dimensions
                    ),
                }
                for item in report.failures
            ],
        },
        "authority": {
            "semantic_granted": report.semantic_authority_granted,
            "production_granted": report.production_authority_granted,
        },
        "model_calls": {
            "current": report.current_model_call_count,
            "historical": report.historical_model_call_count,
        },
        "aggregate_score_present": report.aggregate_score_present,
        "interaction_effects_measured": report.interaction_effects_measured,
        "metric_disposition": {
            "passed": report.passed_metric_count,
            "blocked": report.blocked_metric_count,
            "observed": report.observed_metric_count,
            "not_measured": report.not_measured_metric_count,
        },
    }


def build_semantic_lab_view(repository_root: str | Path) -> dict[str, Any]:
    """Build one deterministic, JSON-ready C8 read model from frozen evidence."""

    root = _repository_root(repository_root)
    manifest_path = _confined_file(
        root, _C7_MANIFEST_PATH, label="C7 integrated manifest"
    )
    manifest_payload = _read_bounded(
        manifest_path,
        maximum_bytes=_MAX_C7_MANIFEST_BYTES,
        label="C7 integrated manifest",
    )
    manifest_sha256 = _sha256(manifest_payload)
    if manifest_sha256 != C7_EXPECTED_MANIFEST_SHA256:
        raise SemanticLabIntegrityError("C7 manifest bytes differ from the frozen pin")
    try:
        c7_manifest = C7IntegratedManifest.model_validate_json(manifest_payload)
    except ValueError as exc:
        raise SemanticLabIntegrityError("C7 manifest failed typed validation") from exc

    c1_spec = _source_spec(c7_manifest, "c1_fixture_manifest")
    c1_payload, c1_integrity = _read_pinned_source(
        root,
        spec=c1_spec,
        maximum_bytes=_MAX_C1_MANIFEST_BYTES,
        label="C1 fixture manifest",
    )
    families, _variant_index = _load_c1_families(
        root,
        manifest_payload=c1_payload,
    )

    c2_spec = _source_spec(c7_manifest, "c2_metrics")
    c2_payload, c2_integrity = _read_pinned_source(
        root,
        spec=c2_spec,
        maximum_bytes=_MAX_C2_METRICS_BYTES,
        label="C2 metrics report",
    )
    c2_document, c2_run = _load_c2_run(c2_payload)
    families, c2_summary = _attach_c2_results(families, run=c2_run)
    c2_summary["dimension_count"] = len(c2_document["dimensions"])

    c7_report, c7_integrity = _load_c7_report(
        root,
        manifest=c7_manifest,
        manifest_sha256=manifest_sha256,
    )
    if (
        c7_report.imported_evidence.c1_family_count != len(families)
        or c7_report.imported_evidence.c1_variant_count
        != sum(len(item["variants"]) for item in families)
        or c7_report.imported_evidence.c2_result_count != len(c2_run.results)
        or c7_report.imported_evidence.c2_evaluator_model_call_count != 0
    ):
        raise SemanticLabIntegrityError("C7 imported C1/C2 facts differ from cold replay")

    base: dict[str, Any] = {
        "schema_version": SEMANTIC_LAB_SCHEMA_VERSION,
        "corpus": {
            "lab_id": "rei-semantic-lab-v1",
            "family_count": len(families),
            "variant_count": sum(len(item["variants"]) for item in families),
            "reviewer_status": "canon_approved",
        },
        "families": families,
        "c2_evaluation": c2_summary,
        "benchmark_status": _benchmark_status(c7_report),
        "execution_policy": {
            "read_only": True,
            "model_calls": 0,
            "training_export": False,
            "model_generated_gold": False,
            "aggregate_rei_score": False,
        },
        "source_integrity": {
            "c7_manifest": {
                "path": _C7_MANIFEST_PATH,
                "size_bytes": len(manifest_payload),
                "sha256": manifest_sha256,
            },
            "c1_manifest": c1_integrity,
            "c2_metrics": c2_integrity,
            "c7_report": c7_integrity,
        },
    }
    view_id = content_id(SEMANTIC_LAB_VIEW_ID_KIND, base)
    identified = {"view_id": view_id, **base}
    return {**identified, "view_hash": sha256_hex(identified)}


load_semantic_lab_view = build_semantic_lab_view


__all__ = [
    "SEMANTIC_LAB_SCHEMA_VERSION",
    "SemanticLabIntegrityError",
    "build_semantic_lab_view",
    "load_semantic_lab_view",
]
