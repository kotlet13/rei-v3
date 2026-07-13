from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = ROOT / "archive"
ARCHIVE_TOOL = ROOT / "scripts" / "archive_rei_architecture.py"
ACTIVE_SOURCE_ROOTS = (
    ROOT / "app" / "backend" / "rei",
    ROOT / "app" / "gui",
    ROOT / "scripts",
)
REQUIRED_NO_RECURSE_DIRS = {"archive", "output", ".git", ".venv"}


def _python_files(roots: tuple[Path, ...]) -> list[Path]:
    return sorted(
        path
        for root in roots
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_archive_module(module_name: str | None) -> bool:
    return module_name is not None and module_name.casefold().partition(".")[0] == "archive"


def _literal_dynamic_import(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        call_name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        call_name = node.func.attr
    else:
        return None

    if call_name not in {"__import__", "import_module"}:
        return None

    argument = node.args[0] if node.args else next(
        (keyword.value for keyword in node.keywords if keyword.arg == "name"),
        None,
    )
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    return None


def _archive_import_findings(path: Path) -> list[str]:
    findings: list[str] = []
    relative = path.relative_to(ROOT).as_posix()

    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_archive_module(alias.name):
                    findings.append(f"{relative}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and _is_archive_module(node.module):
                findings.append(f"{relative}:{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Call):
            module_name = _literal_dynamic_import(node)
            if _is_archive_module(module_name):
                findings.append(f"{relative}:{node.lineno}: dynamic import {module_name!r}")

    return findings


def _is_archive_path_literal(value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    return any(component.casefold() == "archive" for component in normalized.split("/"))


def _archive_path_findings(path: Path) -> list[str]:
    relative = path.relative_to(ROOT).as_posix()
    return [
        f"{relative}:{node.lineno}: {node.value!r}"
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _is_archive_path_literal(node.value)
    ]


def test_active_code_does_not_import_archive() -> None:
    files = _python_files(ACTIVE_SOURCE_ROOTS)
    assert files, "No active Python source files were found."

    findings = [
        finding
        for path in files
        for finding in _archive_import_findings(path)
    ]
    assert not findings, "Active code imports archive:\n" + "\n".join(findings)


def test_active_code_does_not_reference_archive_paths() -> None:
    files = [
        path
        for path in _python_files(ACTIVE_SOURCE_ROOTS)
        if path != ARCHIVE_TOOL
    ]
    assert files, "No active Python source files were found."

    findings = [
        finding
        for path in files
        for finding in _archive_path_findings(path)
    ]
    assert not findings, "Active code references archive paths:\n" + "\n".join(findings)


def test_pytest_configuration_isolates_archive(pytestconfig: pytest.Config) -> None:
    testpaths = [value.replace("\\", "/").rstrip("/") for value in pytestconfig.getini("testpaths")]
    assert testpaths == ["tests"]

    ignored = {
        value.replace("\\", "/").rstrip("/")
        for value in pytestconfig.getini("norecursedirs")
    }
    assert REQUIRED_NO_RECURSE_DIRS <= ignored


def test_archive_files_are_not_in_active_collection(request: pytest.FixtureRequest) -> None:
    archive_root = ARCHIVE_ROOT.resolve()
    leaked_nodeids: list[str] = []

    for item in request.session.items:
        item_path = Path(str(item.path)).resolve()
        if item_path == archive_root or archive_root in item_path.parents:
            leaked_nodeids.append(item.nodeid)

    assert not leaked_nodeids, "Archive tests leaked into active pytest collection:\n" + "\n".join(
        leaked_nodeids
    )
