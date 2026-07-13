from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_ROOTS = (
    ROOT / "app" / "backend" / "rei",
    ROOT / "app" / "gui",
    ROOT / "scripts",
    ROOT / "tests" / "rei",
    ROOT / "knowledge" / "canon_v2",
)
TEXT_SUFFIXES = {".css", ".html", ".js", ".md", ".py", ".yaml", ".yml"}
LEGACY_ENTRYPOINTS = (
    "export_rei_ft_dataset.py",
    "filter_rei_cases.py",
    "generate_rei_ft_dataset.py",
    "import_rei_profile_matrix_review_dataset.py",
    "run_rei_profile_matrix.py",
    "validate_rei_ft_dataset.py",
    "verify_rei_contract_pack.py",
)
LEGACY_TESTS = (
    "test_acceptance.py",
    "test_ego_fields.py",
    "test_ft_dataset.py",
    "test_normalization.py",
    "test_processor_distinctness.py",
    "test_processor_eval.py",
    "test_profiles.py",
    "test_rei_canonical_contracts.py",
    "test_rei_cycle.py",
    "test_rei_cycle_regression_contract.py",
    "test_rei_profile_matrix.py",
)


def test_transitional_packages_are_fully_promoted() -> None:
    assert not (ROOT / "app" / "backend" / ("rei" + "_next")).exists()
    assert not (ROOT / "app" / ("gui" + "_next")).exists()
    assert (ROOT / "app" / "backend" / "rei" / "engine.py").is_file()
    assert (ROOT / "app" / "gui" / "server.py").is_file()

    findings: list[str] = []
    for root in ACTIVE_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.casefold() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in ("rei" + "_next", "gui" + "_next"):
                if marker in text:
                    findings.append(f"{path.relative_to(ROOT).as_posix()}: {marker}")
    assert not findings, "Transitional references remain active:\n" + "\n".join(findings)


def test_legacy_entrypoints_and_duplicate_tests_exist_only_in_archive() -> None:
    for name in LEGACY_ENTRYPOINTS:
        assert not (ROOT / "scripts" / name).exists()
    for name in LEGACY_TESTS:
        assert not (ROOT / "tests" / name).exists()

    snapshot = ROOT / "archive" / "rei_v3_text_llm_baseline_2026-07-13" / "snapshot"
    assert (snapshot / "scripts" / "run_rei_profile_matrix.py").is_file()
    for name in LEGACY_TESTS:
        assert (snapshot / "reference_tests" / name).is_file()
