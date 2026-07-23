from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]

CLAIMS_RELATIVE_PATH = Path("knowledge/canon/claims_v2.jsonl")
PROCESSORS_RELATIVE_PATH = Path("knowledge/canon/processors_v2.yaml")
CHARACTERS_RELATIVE_PATH = Path("knowledge/canon/character_rules_v2.yaml")
OPEN_QUESTIONS_RELATIVE_PATH = Path("knowledge/canon/open_questions_v2.md")
GLOSSARY_RELATIVE_PATH = Path("knowledge/glossary/rei_terms_v2.yaml")
WEIGHTED_NOTE_RELATIVE_PATH = Path("Docs/REI_weighted_synthesis_working_note.md")

CANON_ARTIFACT_PATHS = (
    CLAIMS_RELATIVE_PATH,
    PROCESSORS_RELATIVE_PATH,
    CHARACTERS_RELATIVE_PATH,
    OPEN_QUESTIONS_RELATIVE_PATH,
    GLOSSARY_RELATIVE_PATH,
)

CLAIM_REQUIRED_KEYS = {
    "claim_id",
    "status",
    "kind",
    "scope",
    "sl",
    "en_gloss",
    "source_file",
    "page",
    "source_locator",
    "translation_notes",
    "risk_class",
}
ALLOWED_CLAIM_STATUSES = {
    "direct_source",
    "source_synthesis",
    "implementation_hypothesis",
    "open_question",
    "deprecated_hypothesis",
}
ALLOWED_CLAIM_KINDS = {"OD", "EK", "IZ"}
ALLOWED_RISK_CLASSES = {
    "core",
    "medical_claim",
    "metaphysical_claim",
    "social_generalization",
    "historical_claim",
    "manipulation_sensitive",
    "exclude_from_training",
}
CLAIM_ID_PATTERN = re.compile(r"^C-[A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d{3}$")

EXPECTED_PROCESSOR_INVARIANTS = {
    "R": {
        "direct_conscious_access": True,
        "native_verbal_access": True,
        "translated_by_racio": False,
    },
    "E": {
        "direct_conscious_access": False,
        "native_verbal_access": False,
        "translated_by_racio": True,
    },
    "I": {
        "direct_conscious_access": False,
        "native_verbal_access": False,
        "translated_by_racio": True,
    },
}

EXPECTED_CHARACTER_IDS = {
    "R",
    "E",
    "I",
    "R>E>I",
    "R>I>E",
    "E>R>I",
    "E>I>R",
    "I>R>E",
    "I>E>R",
    "RE",
    "RI",
    "EI",
    "REI",
}
MIND_IDS = {"R", "E", "I"}

EXPECTED_GLOSSARY_TERMS = {
    "Racio",
    "Emocio",
    "Instinkt",
    "razum",
    "značaj",
    "svet",
    "sprejemanje",
    "nesprejemanje",
    "spoznanje",
    "kulisa",
    "vodilni razum",
    "vzporedna razuma",
}
GLOSSARY_REQUIRED_KEYS = {
    "term_id",
    "canonical_sl",
    "definition_sl",
    "en_gloss",
    "do_not_translate_as",
    "usage_example_sl",
    "everyday_usage_note_sl",
    "source_claim_ids",
}

FORBIDDEN_BENCHMARK_PHRASES = (
    "quit job",
    "runway",
    "side hustle",
    "side venture",
    "revenue milestone",
    "first business change scenario",
    "first business scenario",
    "all in transition",
)


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _path_label(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _read_required_text(path: Path, root: Path, errors: list[str]) -> str | None:
    label = _path_label(path, root)
    if not path.is_file():
        errors.append(f"{label}: required artifact is missing")
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label}: cannot read UTF-8 text: {exc}")
        return None
    if not text.strip():
        errors.append(f"{label}: artifact is empty")
    return text


def _load_yaml(path: Path, root: Path, errors: list[str]) -> Any:
    text = _read_required_text(path, root, errors)
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        errors.append(f"{_path_label(path, root)}: invalid YAML: {exc}")
        return None


def _safe_repo_source(root: Path, value: object) -> Path | None:
    if not _is_nonempty_string(value):
        return None
    source = Path(str(value))
    if source.is_absolute():
        return None
    candidate = (root / source).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def validate_source_reference(
    root: Path,
    reference: object,
    location: str,
    errors: list[str],
    *,
    kind: str | None = None,
) -> None:
    """Validate one primary or supporting source reference.

    EK claims and every PDF reference require a positive physical page. OD and
    IZ references may instead use a precise document/section locator.
    """

    if not isinstance(reference, Mapping):
        errors.append(f"{location}: source reference must be a mapping")
        return

    source_file = reference.get("source_file")
    source_path = _safe_repo_source(root, source_file)
    if source_path is None:
        errors.append(f"{location}: source_file must be a safe, non-empty repo-relative path")
    elif not source_path.is_file():
        errors.append(f"{location}: source_file does not exist: {source_file!r}")

    page = reference.get("page")
    has_positive_page = isinstance(page, int) and not isinstance(page, bool) and page > 0
    if page is not None and not has_positive_page:
        errors.append(f"{location}: page must be null or a positive integer")

    has_locator = _is_nonempty_string(reference.get("source_locator"))
    suffix = Path(str(source_file)).suffix.casefold() if _is_nonempty_string(source_file) else ""
    requires_page = kind == "EK" or suffix == ".pdf"
    if requires_page and not has_positive_page:
        errors.append(f"{location}: EK and PDF sources require a positive page")
    elif not has_positive_page and not has_locator:
        errors.append(f"{location}: provide a positive page or non-empty source_locator")


def load_and_validate_claims(root: Path, errors: list[str]) -> tuple[list[dict[str, Any]], set[str]]:
    path = root / CLAIMS_RELATIVE_PATH
    text = _read_required_text(path, root, errors)
    if text is None:
        return [], set()

    claims: list[dict[str, Any]] = []
    claim_ids: set[str] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        location = f"{CLAIMS_RELATIVE_PATH.as_posix()}:{line_number}"
        try:
            claim = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"{location}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(claim, dict):
            errors.append(f"{location}: each JSONL line must be an object")
            continue
        claims.append(claim)

        missing = sorted(CLAIM_REQUIRED_KEYS - set(claim))
        if missing:
            errors.append(f"{location}: missing required keys: {', '.join(missing)}")

        claim_id = claim.get("claim_id")
        if not _is_nonempty_string(claim_id) or not CLAIM_ID_PATTERN.fullmatch(str(claim_id)):
            errors.append(
                f"{location}: claim_id must be a stable ID like C-CHAR-001; got {claim_id!r}"
            )
        elif str(claim_id) in claim_ids:
            errors.append(f"{location}: duplicate claim_id {claim_id!r}")
        else:
            claim_ids.add(str(claim_id))

        status = claim.get("status")
        if status not in ALLOWED_CLAIM_STATUSES:
            errors.append(f"{location}: invalid status {status!r}")
        kind = claim.get("kind")
        if kind not in ALLOWED_CLAIM_KINDS:
            errors.append(f"{location}: invalid kind {kind!r}; expected OD, EK, or IZ")
        risk_class = claim.get("risk_class")
        if risk_class not in ALLOWED_RISK_CLASSES:
            errors.append(f"{location}: invalid risk_class {risk_class!r}")

        for key in ("scope", "sl", "en_gloss"):
            if not _is_nonempty_string(claim.get(key)):
                errors.append(f"{location}: {key} must be a non-empty string")
        if _is_nonempty_string(claim.get("sl")) and _is_nonempty_string(claim.get("en_gloss")):
            if str(claim["sl"]).strip().casefold() == str(claim["en_gloss"]).strip().casefold():
                errors.append(f"{location}: sl and en_gloss must be distinct texts")

        if "translation_notes" in claim and not isinstance(claim.get("translation_notes"), str):
            errors.append(f"{location}: translation_notes must be a string")
        if "source_locator" in claim and not isinstance(claim.get("source_locator"), str):
            errors.append(f"{location}: source_locator must be a string")

        validate_source_reference(
            root,
            claim,
            location,
            errors,
            kind=str(kind) if isinstance(kind, str) else None,
        )

        if "supporting_sources" in claim:
            supporting_sources = claim.get("supporting_sources")
            if not isinstance(supporting_sources, list) or not supporting_sources:
                errors.append(f"{location}: supporting_sources must be a non-empty list")
            else:
                for index, reference in enumerate(supporting_sources):
                    validate_source_reference(
                        root,
                        reference,
                        f"{location}.supporting_sources[{index}]",
                        errors,
                    )

    if not claims:
        errors.append(f"{CLAIMS_RELATIVE_PATH.as_posix()}: no claims found")
    for index, claim in enumerate(claims, start=1):
        if "derived_from_claim_ids" not in claim:
            continue
        _validate_claim_refs(
            claim.get("derived_from_claim_ids"),
            claim_ids,
            f"{CLAIMS_RELATIVE_PATH.as_posix()}:{index}.derived_from_claim_ids",
            errors,
        )
    return claims, claim_ids


def _mapping_at_key(data: Any, key: str) -> Any:
    if isinstance(data, Mapping) and key in data:
        return data[key]
    return data


def _extract_processor_entries(data: Any) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    container = _mapping_at_key(data, "processors")
    entries: dict[str, Mapping[str, Any]] = {}
    structural_errors: list[str] = []
    if isinstance(container, Mapping):
        for raw_id, raw_entry in container.items():
            if not isinstance(raw_id, str) or not isinstance(raw_entry, Mapping):
                structural_errors.append("processor mapping must use string IDs and mapping values")
                continue
            entries[raw_id] = raw_entry
        return entries, structural_errors
    if isinstance(container, list):
        for index, raw_entry in enumerate(container):
            if not isinstance(raw_entry, Mapping):
                structural_errors.append(f"processor entry {index} must be a mapping")
                continue
            mind_id = raw_entry.get("mind_id", raw_entry.get("id"))
            if not _is_nonempty_string(mind_id):
                structural_errors.append(f"processor entry {index} has no mind_id")
                continue
            if str(mind_id) in entries:
                structural_errors.append(f"duplicate processor mind ID {mind_id!r}")
                continue
            entries[str(mind_id)] = raw_entry
        return entries, structural_errors
    return {}, ["processors must be a mapping or list"]


def _validate_claim_refs(
    refs: object,
    claim_ids: set[str],
    location: str,
    errors: list[str],
) -> None:
    if not isinstance(refs, list) or not refs:
        errors.append(f"{location}: source_claim_ids must be a non-empty list")
        return
    for ref in refs:
        if not _is_nonempty_string(ref):
            errors.append(f"{location}: source_claim_ids contains a non-string or empty value")
        elif ref not in claim_ids:
            errors.append(f"{location}: unresolved source claim ID {ref!r}")


def _validate_all_claim_ref_fields(
    value: object,
    claim_ids: set[str],
    artifact: Path,
    errors: list[str],
    location: str = "$",
) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if key == "source_claim_ids":
                _validate_claim_refs(
                    child,
                    claim_ids,
                    f"{artifact.as_posix()}:{child_location}",
                    errors,
                )
            else:
                _validate_all_claim_ref_fields(
                    child, claim_ids, artifact, errors, child_location
                )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_all_claim_ref_fields(
                child, claim_ids, artifact, errors, f"{location}[{index}]"
            )


def validate_processors(root: Path, claim_ids: set[str], errors: list[str]) -> None:
    path = root / PROCESSORS_RELATIVE_PATH
    data = _load_yaml(path, root, errors)
    if data is None:
        return
    processors, structural_errors = _extract_processor_entries(data)
    for error in structural_errors:
        errors.append(f"{PROCESSORS_RELATIVE_PATH.as_posix()}: {error}")
    _validate_all_claim_ref_fields(data, claim_ids, PROCESSORS_RELATIVE_PATH, errors)

    actual_ids = set(processors)
    missing = sorted(MIND_IDS - actual_ids)
    extra = sorted(actual_ids - MIND_IDS)
    if missing:
        errors.append(
            f"{PROCESSORS_RELATIVE_PATH.as_posix()}: missing processors: {', '.join(missing)}"
        )
    if extra:
        errors.append(
            f"{PROCESSORS_RELATIVE_PATH.as_posix()}: unexpected processor IDs: {', '.join(extra)}"
        )

    for mind, expected in EXPECTED_PROCESSOR_INVARIANTS.items():
        location = f"{PROCESSORS_RELATIVE_PATH.as_posix()}:{mind}"
        entry = processors.get(mind)
        if not isinstance(entry, Mapping):
            if mind in processors:
                errors.append(f"{location}: processor entry must be a mapping")
            continue
        if "source_claim_ids" not in entry:
            errors.append(f"{location}: source_claim_ids is required")
        for key, expected_value in expected.items():
            if entry.get(key) is not expected_value:
                errors.append(
                    f"{location}: {key} must be {expected_value!r}; got {entry.get(key)!r}"
                )


def _extract_character_entries(data: Any) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    container = data
    if isinstance(data, Mapping):
        for key in ("characters", "profiles", "rules", "character_rules"):
            if key in data:
                container = data[key]
                break

    entries: dict[str, Mapping[str, Any]] = {}
    structural_errors: list[str] = []
    if isinstance(container, Mapping):
        for raw_id, raw_entry in container.items():
            if not isinstance(raw_id, str) or not isinstance(raw_entry, Mapping):
                structural_errors.append("character mapping must use string IDs and mapping values")
                continue
            entries[raw_id] = raw_entry
        return entries, structural_errors

    if isinstance(container, list):
        for index, raw_entry in enumerate(container):
            if not isinstance(raw_entry, Mapping):
                structural_errors.append(f"character entry {index} must be a mapping")
                continue
            profile_id = raw_entry.get(
                "character_id", raw_entry.get("profile_id", raw_entry.get("id"))
            )
            if not _is_nonempty_string(profile_id):
                structural_errors.append(f"character entry {index} has no profile_id")
                continue
            if str(profile_id) in entries:
                structural_errors.append(f"duplicate character profile ID {profile_id!r}")
                continue
            entries[str(profile_id)] = raw_entry
        return entries, structural_errors

    return {}, ["character rules must be a mapping or list"]


def _find_float_paths(value: object, path: str = "$") -> Iterable[str]:
    if isinstance(value, float):
        yield path
    elif isinstance(value, Mapping):
        for key, child in value.items():
            yield from _find_float_paths(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _find_float_paths(child, f"{path}[{index}]")


def validate_characters(root: Path, claim_ids: set[str], errors: list[str]) -> None:
    path = root / CHARACTERS_RELATIVE_PATH
    data = _load_yaml(path, root, errors)
    if data is None:
        return
    entries, structural_errors = _extract_character_entries(data)
    for error in structural_errors:
        errors.append(f"{CHARACTERS_RELATIVE_PATH.as_posix()}: {error}")
    _validate_all_claim_ref_fields(data, claim_ids, CHARACTERS_RELATIVE_PATH, errors)

    actual_ids = set(entries)
    missing = sorted(EXPECTED_CHARACTER_IDS - actual_ids)
    extra = sorted(actual_ids - EXPECTED_CHARACTER_IDS)
    if missing:
        errors.append(
            f"{CHARACTERS_RELATIVE_PATH.as_posix()}: missing character IDs: {', '.join(missing)}"
        )
    if extra:
        errors.append(
            f"{CHARACTERS_RELATIVE_PATH.as_posix()}: unexpected character IDs: {', '.join(extra)}"
        )

    for float_path in _find_float_paths(data):
        errors.append(
            f"{CHARACTERS_RELATIVE_PATH.as_posix()}:{float_path}: floats are forbidden in ordinal character rules"
        )

    for profile_id, entry in entries.items():
        location = f"{CHARACTERS_RELATIVE_PATH.as_posix()}:{profile_id}"
        tiers = entry.get("authority_tiers")
        if not isinstance(tiers, list) or not tiers:
            errors.append(f"{location}: authority_tiers must be a non-empty list")
        else:
            flattened: list[object] = []
            for index, tier in enumerate(tiers):
                if not isinstance(tier, list) or not tier:
                    errors.append(f"{location}: authority_tiers[{index}] must be a non-empty list")
                    continue
                flattened.extend(tier)
            if (
                len(flattened) != 3
                or any(not isinstance(mind, str) for mind in flattened)
                or set(flattened) != MIND_IDS
            ):
                errors.append(
                    f"{location}: authority_tiers must cover R, E, and I exactly once; got {flattened!r}"
                )
        if "source_claim_ids" not in entry:
            errors.append(f"{location}: source_claim_ids is required")


def _extract_glossary_terms(data: Any) -> tuple[list[Mapping[str, Any]], list[str]]:
    container = _mapping_at_key(data, "terms")
    structural_errors: list[str] = []
    if isinstance(container, list):
        terms = []
        for index, entry in enumerate(container):
            if isinstance(entry, Mapping):
                terms.append(entry)
            else:
                structural_errors.append(f"term entry {index} must be a mapping")
        return terms, structural_errors
    if isinstance(container, Mapping):
        terms = []
        for canonical_sl, entry in container.items():
            if not isinstance(canonical_sl, str) or not isinstance(entry, Mapping):
                structural_errors.append("term mapping must use string keys and mapping values")
                continue
            normalized_entry = dict(entry)
            normalized_entry.setdefault("canonical_sl", canonical_sl)
            terms.append(normalized_entry)
        return terms, structural_errors
    return [], ["glossary terms must be a list or mapping"]


def validate_glossary(root: Path, claim_ids: set[str], errors: list[str]) -> None:
    path = root / GLOSSARY_RELATIVE_PATH
    data = _load_yaml(path, root, errors)
    if data is None:
        return
    _validate_all_claim_ref_fields(data, claim_ids, GLOSSARY_RELATIVE_PATH, errors)
    terms, structural_errors = _extract_glossary_terms(data)
    for error in structural_errors:
        errors.append(f"{GLOSSARY_RELATIVE_PATH.as_posix()}: {error}")

    seen_terms: set[str] = set()
    seen_ids: set[str] = set()
    for index, term in enumerate(terms):
        location = f"{GLOSSARY_RELATIVE_PATH.as_posix()}:term[{index}]"
        missing = sorted(GLOSSARY_REQUIRED_KEYS - set(term))
        if missing:
            errors.append(f"{location}: missing required keys: {', '.join(missing)}")
        for key in (
            "term_id",
            "canonical_sl",
            "definition_sl",
            "en_gloss",
            "usage_example_sl",
            "everyday_usage_note_sl",
        ):
            if not _is_nonempty_string(term.get(key)):
                errors.append(f"{location}: {key} must be a non-empty string")
        blocked = term.get("do_not_translate_as")
        if not isinstance(blocked, list) or not blocked or not all(_is_nonempty_string(item) for item in blocked):
            errors.append(f"{location}: do_not_translate_as must be a non-empty list of strings")

        canonical_sl = term.get("canonical_sl")
        if _is_nonempty_string(canonical_sl):
            canonical_text = str(canonical_sl)
            if canonical_text in seen_terms:
                errors.append(f"{location}: duplicate canonical_sl {canonical_text!r}")
            seen_terms.add(canonical_text)
        term_id = term.get("term_id")
        if _is_nonempty_string(term_id):
            identifier = str(term_id)
            if identifier in seen_ids:
                errors.append(f"{location}: duplicate term_id {identifier!r}")
            seen_ids.add(identifier)

    missing_terms = sorted(EXPECTED_GLOSSARY_TERMS - seen_terms)
    extra_terms = sorted(seen_terms - EXPECTED_GLOSSARY_TERMS)
    if missing_terms:
        errors.append(
            f"{GLOSSARY_RELATIVE_PATH.as_posix()}: missing canonical terms: {', '.join(missing_terms)}"
        )
    if extra_terms:
        errors.append(
            f"{GLOSSARY_RELATIVE_PATH.as_posix()}: unexpected canonical terms: {', '.join(extra_terms)}"
        )


def normalize_for_benchmark_scan(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    normalized = normalized.replace("_", " ")
    return " ".join(normalized.split())


def find_forbidden_benchmark_phrases(root: Path, errors: list[str] | None = None) -> list[str]:
    findings: list[str] = []
    for relative_path in CANON_ARTIFACT_PATHS:
        path = root / relative_path
        if not path.is_file():
            if errors is not None:
                errors.append(f"{relative_path.as_posix()}: required artifact is missing")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            if errors is not None:
                errors.append(f"{relative_path.as_posix()}: cannot scan UTF-8 text: {exc}")
            continue
        padded_text = f" {normalize_for_benchmark_scan(text)} "
        for phrase in FORBIDDEN_BENCHMARK_PHRASES:
            normalized_phrase = normalize_for_benchmark_scan(phrase)
            if f" {normalized_phrase} " in padded_text:
                findings.append(
                    f"{relative_path.as_posix()}: contains forbidden benchmark phrase {phrase!r}"
                )
    return findings


def validate_weighted_note(root: Path, errors: list[str]) -> None:
    path = root / WEIGHTED_NOTE_RELATIVE_PATH
    text = _read_required_text(path, root, errors)
    if text is None:
        return
    normalized = normalize_for_benchmark_scan(text)
    if "deprecated_hypothesis" not in text.casefold():
        errors.append(
            f"{WEIGHTED_NOTE_RELATIVE_PATH.as_posix()}: missing deprecated_hypothesis marker"
        )
    if "partially superseded" not in normalized:
        errors.append(
            f"{WEIGHTED_NOTE_RELATIVE_PATH.as_posix()}: missing 'partially superseded' notice"
        )


def validate_canon_v2(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    _, claim_ids = load_and_validate_claims(root, errors)
    validate_processors(root, claim_ids, errors)
    validate_characters(root, claim_ids, errors)
    validate_glossary(root, claim_ids, errors)
    _read_required_text(root / OPEN_QUESTIONS_RELATIVE_PATH, root, errors)
    validate_weighted_note(root, errors)
    errors.extend(find_forbidden_benchmark_phrases(root))
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the source-traceable bilingual REI canon v2 artifacts."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root (defaults to the repository containing this script).",
    )
    args = parser.parse_args(argv)

    errors = validate_canon_v2(args.root)
    if errors:
        print(f"REI canon v2 validation failed with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("REI canon v2 validation OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
