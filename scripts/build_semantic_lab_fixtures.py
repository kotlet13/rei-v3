from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.backend.rei.models.scene import SceneEvent  # noqa: E402


VARIANT_MODES = (
    "sl_canonical",
    "sl_paraphrase",
    "en_operational_gloss",
    "keyword_trap",
    "same_behavior_different_route",
    "same_route_different_behavior",
    "missing_information",
    "contradictory_surface_cue",
)

PERTURBATION_FIELDS = {
    "keyword_trap": "keyword_trap",
    "same_behavior_different_route": "surface_behavior",
    "same_route_different_behavior": "alternate_behavior",
    "missing_information": "omitted_information",
    "contradictory_surface_cue": "contradictory_surface_cue",
}

FORBIDDEN_DATA_KEYS = {
    "authority_tier",
    "authority_tiers",
    "character_profile",
    "expected_character",
    "profile_id",
    "profile_weight",
    "training_split",
}

REQUIRED_FAMILY_FIELDS = {
    "schema_version",
    "family_id",
    "title_sl",
    "purpose",
    "source_locators",
    "grounded_scene",
    "canonical_input_sl",
    "sl_paraphrase",
    "operational_gloss_en",
    "variant_modes",
    "person_world_variants",
    "current_state_variants",
    "acceptance_variants",
    "language_variants",
    "perturbation_values",
    "route_expectations",
    "expected_route_ids",
    "forbidden_shortcuts",
    "review_status",
}


class SemanticLabBuildError(ValueError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise SemanticLabBuildError(
                f"Invalid JSON in {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise SemanticLabBuildError(
                f"Expected an object in {path}:{line_number}"
            )
        records.append(value)
    return records


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _content_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for nested in value.values():
            keys.update(_walk_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(_walk_keys(nested))
    return keys


def _claim_registry(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = repo_root / "knowledge" / "canon_v2" / "claims.jsonl"
    return {record["claim_id"]: record for record in _read_jsonl(path)}


def _source_index(source_root: Path) -> dict[str, dict[str, Any]]:
    path = source_root / "source_index.jsonl"
    return {record["claim_id"]: record for record in _read_jsonl(path)}


def _review_index(source_root: Path) -> dict[str, dict[str, Any]]:
    path = source_root / "review" / "review_log.jsonl"
    records = _read_jsonl(path)
    reviews: dict[str, dict[str, Any]] = {}
    for record in records:
        family_id = record.get("family_id")
        if not isinstance(family_id, str):
            raise SemanticLabBuildError("Review event is missing family_id")
        if family_id in reviews:
            raise SemanticLabBuildError(
                f"Multiple terminal review records for {family_id}"
            )
        reviews[family_id] = record
    return reviews


def _validate_source_locator(
    *,
    locator: dict[str, Any],
    repo_root: Path,
    claims: dict[str, dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
    family_id: str,
) -> None:
    source_file = locator.get("source_file")
    if not isinstance(source_file, str) or not source_file:
        raise SemanticLabBuildError(f"{family_id}: source_file is required")
    if not (repo_root / source_file).is_file():
        raise SemanticLabBuildError(
            f"{family_id}: source file does not exist: {source_file}"
        )
    claim_ids = locator.get("claim_ids")
    if not isinstance(claim_ids, list) or not claim_ids:
        raise SemanticLabBuildError(f"{family_id}: source claim_ids are required")
    if not isinstance(locator.get("excerpt_summary_sl"), str) or not locator[
        "excerpt_summary_sl"
    ].strip():
        raise SemanticLabBuildError(
            f"{family_id}: Slovene source summary is required"
        )
    for claim_id in claim_ids:
        if claim_id not in claims:
            raise SemanticLabBuildError(f"{family_id}: unknown claim {claim_id}")
        if claim_id not in source_index:
            raise SemanticLabBuildError(
                f"{family_id}: claim missing from semantic source index: {claim_id}"
            )
        canonical = claims[claim_id]
        indexed = source_index[claim_id]
        if canonical.get("source_file") != source_file:
            raise SemanticLabBuildError(
                f"{family_id}: {claim_id} belongs to {canonical.get('source_file')}, "
                f"not {source_file}"
            )
        if indexed.get("source_file") != source_file:
            raise SemanticLabBuildError(
                f"{family_id}: source index mismatch for {claim_id}"
            )
        if canonical.get("source_page") != locator.get("page"):
            raise SemanticLabBuildError(
                f"{family_id}: page mismatch for {claim_id}"
            )


def _validate_family(
    family: dict[str, Any],
    *,
    repo_root: Path,
    claims: dict[str, dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
    reviews: dict[str, dict[str, Any]],
) -> SceneEvent:
    family_id = family.get("family_id")
    if not isinstance(family_id, str) or not family_id.startswith("sf_"):
        raise SemanticLabBuildError(f"Invalid family_id: {family_id!r}")
    missing = REQUIRED_FAMILY_FIELDS - set(family)
    if missing:
        raise SemanticLabBuildError(
            f"{family_id}: missing fields: {', '.join(sorted(missing))}"
        )
    unknown = set(family) - REQUIRED_FAMILY_FIELDS
    if unknown:
        raise SemanticLabBuildError(
            f"{family_id}: unknown fields: {', '.join(sorted(unknown))}"
        )
    if family["schema_version"] != "rei-semantic-scenario-family-v1":
        raise SemanticLabBuildError(f"{family_id}: unsupported schema version")
    if family["review_status"] != "canon_approved":
        raise SemanticLabBuildError(f"{family_id}: family is not canon_approved")
    review = reviews.get(family_id)
    if review is None or review.get("status") != "canon_approved":
        raise SemanticLabBuildError(
            f"{family_id}: terminal canon_approved review event is missing"
        )
    if review.get("model_generated") is not False:
        raise SemanticLabBuildError(f"{family_id}: model-generated review is forbidden")
    if tuple(family["variant_modes"]) != VARIANT_MODES:
        raise SemanticLabBuildError(
            f"{family_id}: expected the canonical eight grouped variants"
        )
    if family["language_variants"] != ["sl", "en"]:
        raise SemanticLabBuildError(
            f"{family_id}: Slovene canonical and English gloss are required"
        )
    if family["acceptance_variants"] != ["accepting", "mixed", "conflicted"]:
        raise SemanticLabBuildError(
            f"{family_id}: all three acceptance modes are required"
        )
    if len(family["person_world_variants"]) < 2 or len(
        family["current_state_variants"]
    ) < 2:
        raise SemanticLabBuildError(
            f"{family_id}: person-world and current-state contrasts are required"
        )
    if set(family["perturbation_values"]) != set(PERTURBATION_FIELDS.values()):
        raise SemanticLabBuildError(
            f"{family_id}: perturbation values do not match the variant contract"
        )
    if "behavior_to_character" not in family["forbidden_shortcuts"]:
        raise SemanticLabBuildError(
            f"{family_id}: behavior-to-character shortcut must be forbidden"
        )
    leaked_keys = _walk_keys(family) & FORBIDDEN_DATA_KEYS
    if leaked_keys:
        raise SemanticLabBuildError(
            f"{family_id}: forbidden profile/training fields: {sorted(leaked_keys)}"
        )
    if not family["canonical_input_sl"].strip() or not family[
        "sl_paraphrase"
    ].strip():
        raise SemanticLabBuildError(f"{family_id}: Slovene text is required")
    if not family["operational_gloss_en"].strip():
        raise SemanticLabBuildError(f"{family_id}: English gloss is required")
    for locator in family["source_locators"]:
        _validate_source_locator(
            locator=locator,
            repo_root=repo_root,
            claims=claims,
            source_index=source_index,
            family_id=family_id,
        )

    # The domain contracts are strict about tuple inputs in Python mode, while
    # canonical JSON arrays correctly deserialize to those immutable tuples.
    scene = SceneEvent.model_validate_json(
        json.dumps(family["grounded_scene"], ensure_ascii=False)
    )
    if scene.language != "sl":
        raise SemanticLabBuildError(f"{family_id}: grounded scene must be Slovene")
    if not scene.evidence or any(
        not item.grounded or item.provenance_kind != "supplied"
        for item in scene.evidence
    ):
        raise SemanticLabBuildError(
            f"{family_id}: fixture evidence must be supplied and grounded"
        )
    evidence_ids = {item.evidence_id for item in scene.evidence}
    option_ids = {item.option_id for item in scene.options}
    expected_route_ids: list[str] = []
    seen_minds: set[str] = set()
    for route in family["route_expectations"]:
        mind = route.get("mind")
        if mind not in {"R", "E", "I"} or mind in seen_minds:
            raise SemanticLabBuildError(
                f"{family_id}: route minds must be unique R/E/I values"
            )
        seen_minds.add(mind)
        expected_route_ids.append(f"{family_id}__route_{mind}")
        if not set(route.get("evidence_ids", ())).issubset(evidence_ids):
            raise SemanticLabBuildError(
                f"{family_id}: route {mind} cites unknown evidence"
            )
        option_id = route.get("option_id")
        if option_id is not None and option_id not in option_ids:
            raise SemanticLabBuildError(
                f"{family_id}: route {mind} cites unknown option {option_id}"
            )
        if not route.get("route_tags") or not route.get("forbidden_reasons"):
            raise SemanticLabBuildError(
                f"{family_id}: route {mind} needs tags and forbidden reasons"
            )
    if family["expected_route_ids"] != expected_route_ids:
        raise SemanticLabBuildError(
            f"{family_id}: expected_route_ids do not match route expectations"
        )
    return scene


def _variant_input(
    family: dict[str, Any], mode: str
) -> tuple[str, str, dict[str, str] | None]:
    if mode == "sl_canonical":
        return "sl", family["canonical_input_sl"], None
    if mode == "sl_paraphrase":
        return "sl", family["sl_paraphrase"], None
    if mode == "en_operational_gloss":
        return "en", family["operational_gloss_en"], None
    field = PERTURBATION_FIELDS[mode]
    return (
        "sl",
        family["canonical_input_sl"],
        {"kind": mode, "value": family["perturbation_values"][field]},
    )


def _interpretation_class(mode: str) -> str:
    if mode == "missing_information":
        return "partial"
    if mode == "contradictory_surface_cue":
        return "unknown"
    return "accurate"


def _acceptance_mode(mode: str) -> str:
    if mode in {"missing_information", "contradictory_surface_cue"}:
        return "conflicted"
    if mode == "keyword_trap":
        return "mixed"
    return "accepting"


def _generated_route(
    family: dict[str, Any],
    route: dict[str, Any],
    *,
    variant_id: str,
) -> dict[str, Any]:
    mind = route["mind"]
    return {
        "schema_version": "rei-canonical-native-route-v1",
        "route_id": f"{variant_id}__route_{mind}",
        "family_id": family["family_id"],
        "variant_id": variant_id,
        "mind": mind,
        "evidence_ids": route["evidence_ids"],
        "world_context_ids": [],
        "route_tags": route["route_tags"],
        "option_id": route["option_id"],
        "decisive_representation": route["decisive_representation"],
        "short_decision_bridge_sl": route["short_decision_bridge_sl"],
        "allowed_variants": route["allowed_variants"],
        "forbidden_reasons": route["forbidden_reasons"],
        "source_locators": family["source_locators"],
    }


def _generated_interpretation(
    family: dict[str, Any],
    route: dict[str, Any],
    *,
    variant_id: str,
    mode: str,
) -> dict[str, Any]:
    mind = route["mind"]
    return {
        "schema_version": "rei-canonical-interpretation-variant-v1",
        "interpretation_id": f"{variant_id}__interpret_{mind}",
        "family_id": family["family_id"],
        "variant_id": variant_id,
        "source_mind": mind,
        "visible_manifestation_ids": [f"{variant_id}__manifestation_{mind}"],
        "acceptance_mode": _acceptance_mode(mode),
        "expected_interpretation_class": _interpretation_class(mode),
        "expected_option_id": route["option_id"],
        "expected_motive_class": route["route_tags"][0],
        "notes_sl": (
            "Racio sme sklepati samo iz navedenega vidnega manifestation ID-ja; "
            "nativni route ostane evaluatorjev ground truth."
        ),
    }


def _family_fixture(family: dict[str, Any]) -> dict[str, Any]:
    variants: list[dict[str, Any]] = []
    for mode in VARIANT_MODES:
        variant_id = f"{family['family_id']}__{mode}"
        language, input_text, perturbation = _variant_input(family, mode)
        routes = [
            _generated_route(family, route, variant_id=variant_id)
            for route in family["route_expectations"]
        ]
        interpretations = [
            _generated_interpretation(
                family,
                route,
                variant_id=variant_id,
                mode=mode,
            )
            for route in family["route_expectations"]
            if route["mind"] in {"E", "I"}
        ]
        variants.append(
            {
                "variant_id": variant_id,
                "mode": mode,
                "language": language,
                "input_text": input_text,
                "perturbation": perturbation,
                "expected_routes": routes,
                "interpretation_variants": interpretations,
            }
        )
    return {
        "schema_version": "rei-semantic-family-fixture-v1",
        "family_id": family["family_id"],
        "title_sl": family["title_sl"],
        "purpose": family["purpose"],
        "source_hash": _content_hash(family),
        "source_locators": family["source_locators"],
        "grounded_scene": family["grounded_scene"],
        "person_world_variants": family["person_world_variants"],
        "current_state_variants": family["current_state_variants"],
        "acceptance_variants": family["acceptance_variants"],
        "forbidden_shortcuts": family["forbidden_shortcuts"],
        "review_status": family["review_status"],
        "model_generated_gold": False,
        "training_export": False,
        "variants": variants,
    }


def expected_outputs(
    *,
    source_root: Path,
    repo_root: Path = REPO_ROOT,
) -> dict[str, bytes]:
    family_path = source_root / "scenario_families" / "families.jsonl"
    families = _read_jsonl(family_path)
    if len(families) < 24:
        raise SemanticLabBuildError("At least 24 scenario families are required")
    family_ids = [family.get("family_id") for family in families]
    if len(family_ids) != len(set(family_ids)):
        raise SemanticLabBuildError("Scenario family IDs must be unique")

    claims = _claim_registry(repo_root)
    source_index = _source_index(source_root)
    reviews = _review_index(source_root)
    fixtures: dict[str, dict[str, Any]] = {}
    for family in families:
        _validate_family(
            family,
            repo_root=repo_root,
            claims=claims,
            source_index=source_index,
            reviews=reviews,
        )
        fixtures[family["family_id"]] = _family_fixture(family)

    outputs = {
        f"{family_id}.json": _canonical_bytes(fixture)
        for family_id, fixture in sorted(fixtures.items())
    }
    manifest_files = [
        {
            "path": path,
            "sha256": _sha256_bytes(content),
            "family_id": path.removesuffix(".json"),
            "variant_count": 8,
        }
        for path, content in sorted(outputs.items())
    ]
    manifest = {
        "schema_version": "rei-semantic-fixture-manifest-v1",
        "lab_id": "rei-semantic-lab-v1",
        "source_file": str(family_path.relative_to(repo_root)).replace("\\", "/"),
        "source_hash": _content_hash(families),
        "family_count": len(fixtures),
        "variant_count": len(fixtures) * len(VARIANT_MODES),
        "variant_modes": list(VARIANT_MODES),
        "review_status": "canon_approved",
        "model_generated_gold": False,
        "training_export": False,
        "files": manifest_files,
    }
    outputs["manifest.json"] = _canonical_bytes(manifest)
    return outputs


def build(
    *,
    source_root: Path,
    output_root: Path,
    repo_root: Path = REPO_ROOT,
    check: bool = False,
) -> dict[str, Any]:
    outputs = expected_outputs(source_root=source_root, repo_root=repo_root)
    expected_paths = set(outputs)
    actual_paths = (
        {
            str(path.relative_to(output_root)).replace("\\", "/")
            for path in output_root.rglob("*")
            if path.is_file()
        }
        if output_root.exists()
        else set()
    )
    unexpected = sorted(actual_paths - expected_paths)
    if unexpected:
        raise SemanticLabBuildError(
            "Unexpected files in fixture root: " + ", ".join(unexpected)
        )

    mismatches: list[str] = []
    for relative_path, expected_content in sorted(outputs.items()):
        target = output_root / relative_path
        if check:
            if not target.is_file() or target.read_bytes() != expected_content:
                mismatches.append(relative_path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected_content)
    if check and mismatches:
        raise SemanticLabBuildError(
            "Committed fixtures differ from canonical generation: "
            + ", ".join(mismatches)
        )
    return {
        "schema_version": "rei-semantic-fixture-build-summary-v1",
        "mode": "check" if check else "build",
        "family_count": len(outputs) - 1,
        "variant_count": (len(outputs) - 1) * len(VARIANT_MODES),
        "file_count": len(outputs),
        "output_root": str(output_root),
        "model_calls": 0,
        "training_exports": 0,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic, source-grounded semantic-lab fixtures. "
            "The builder never calls a model and has no training export."
        )
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=REPO_ROOT / "knowledge" / "semantic_lab_v1",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "semantic_lab_v1",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed fixtures without writing files.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        summary = build(
            source_root=args.source_root.resolve(),
            output_root=args.output_root.resolve(),
            check=args.check,
        )
    except SemanticLabBuildError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
