from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_rei_canon_v2 import (
    CLAIMS_RELATIVE_PATH,
    load_and_validate_claims,
    main,
    validate_canon_v2,
    validate_source_reference,
)


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_STARTER_CLAIM_IDS = {
    "C-CHAR-001",
    "C-CHAR-002",
    "C-CHAR-003",
    "C-CHAR-004",
    "C-ARB-001",
    "C-ARB-002",
    "C-DELEG-001",
    "C-STATE-001",
    "C-PERCEPT-001",
    "C-CONSC-001",
    "C-CONSC-002",
    "C-SPOZ-001",
    "C-ACCEPT-001",
    "C-ROUTE-001",
    "C-LANG-001",
}


def _claim_ids() -> set[str]:
    lines = (ROOT / CLAIMS_RELATIVE_PATH).read_text(encoding="utf-8").splitlines()
    return {
        str(json.loads(line)["claim_id"])
        for line in lines
        if line.strip()
    }


def test_required_starter_claims_are_present() -> None:
    assert REQUIRED_STARTER_CLAIM_IDS <= _claim_ids()


def test_canon_v2_registry_and_references_validate() -> None:
    errors = validate_canon_v2(ROOT)
    assert not errors, "Canon v2 validation errors:\n" + "\n".join(f" - {error}" for error in errors)


def test_validator_cli_returns_nonzero_with_useful_errors(tmp_path: Path, capsys: object) -> None:
    assert main(["--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "validation failed" in captured.err
    assert CLAIMS_RELATIVE_PATH.as_posix() in captured.err


def test_ek_pdf_source_requires_positive_page(tmp_path: Path) -> None:
    (tmp_path / "source.pdf").write_bytes(b"%PDF-placeholder")
    errors: list[str] = []

    validate_source_reference(
        tmp_path,
        {
            "source_file": "source.pdf",
            "page": None,
            "source_locator": "Named section is not enough for an EK PDF.",
        },
        "claim:C-TEST-001",
        errors,
        kind="EK",
    )

    assert any("require a positive page" in error for error in errors)


def test_supporting_source_must_exist(tmp_path: Path) -> None:
    claims_path = tmp_path / CLAIMS_RELATIVE_PATH
    claims_path.parent.mkdir(parents=True)
    source_path = tmp_path / "Docs" / "source.docx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"docx-placeholder")
    claim = {
        "claim_id": "C-TEST-001",
        "status": "direct_source",
        "kind": "OD",
        "scope": "test",
        "sl": "Slovenska trditev.",
        "en_gloss": "English operational gloss.",
        "source_file": "Docs/source.docx",
        "page": 1,
        "source_locator": "First paragraph.",
        "translation_notes": "",
        "risk_class": "core",
        "supporting_sources": [
            {
                "source_file": "Docs/missing.pdf",
                "page": 2,
                "source_locator": "Supporting section.",
            }
        ],
    }
    claims_path.write_text(json.dumps(claim, ensure_ascii=False) + "\n", encoding="utf-8")
    errors: list[str] = []

    load_and_validate_claims(tmp_path, errors)

    assert any("supporting_sources[0]" in error and "does not exist" in error for error in errors)


def test_supporting_document_needs_page_or_locator(tmp_path: Path) -> None:
    (tmp_path / "source.md").write_text("source", encoding="utf-8")
    errors: list[str] = []

    validate_source_reference(
        tmp_path,
        {"source_file": "source.md", "page": None, "source_locator": ""},
        "claim:C-TEST-001.supporting_sources[0]",
        errors,
    )

    assert any("positive page or non-empty source_locator" in error for error in errors)
