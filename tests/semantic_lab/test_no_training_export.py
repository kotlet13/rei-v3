from __future__ import annotations

import ast

from conftest import REPO_ROOT


def test_semantic_lab_has_no_training_or_model_export(family_fixtures, fixture_manifest):
    assert fixture_manifest["training_export"] is False
    assert fixture_manifest["model_generated_gold"] is False
    assert all(fixture["training_export"] is False for fixture in family_fixtures.values())
    assert all(
        fixture["model_generated_gold"] is False
        for fixture in family_fixtures.values()
    )


def test_builder_exposes_no_training_entrypoint():
    path = REPO_ROOT / "scripts" / "build_semantic_lab_fixtures.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    callable_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    assert not {name for name in callable_names if "train" in name or "export" in name}
    assert "--train" not in source
    assert "--export" not in source
    assert "openai" not in source.lower()
    assert "ollama" not in source.lower()
