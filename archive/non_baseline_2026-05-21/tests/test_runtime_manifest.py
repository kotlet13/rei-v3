from __future__ import annotations

import sys
import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.version_manifest import runtime_manifest


class RuntimeManifestTests(unittest.TestCase):
    def test_active_stack_contracts_are_connected(self) -> None:
        manifest = runtime_manifest()
        active = manifest["active"]

        self.assertEqual(
            active["frontend"]["consumes_api_contract"],
            active["playground_api"]["contract_id"],
        )
        self.assertEqual(
            active["playground_api"]["uses_engine_contract"],
            active["engine"]["contract_id"],
        )

    def test_active_stack_paths_exist(self) -> None:
        manifest = runtime_manifest()
        active = manifest["active"]

        for component in active.values():
            with self.subTest(component=component["id"]):
                self.assertTrue((ROOT / component["path"]).exists())

    def test_latest_logic_and_motorics_are_separate_manifest_sections(self) -> None:
        manifest = runtime_manifest()

        self.assertEqual(manifest["active_logic"]["id"], "rei-v3-current-logic")
        self.assertEqual(manifest["active_logic"]["contract_id"], "rei-logic-v1")
        self.assertEqual(manifest["active_motorics"]["id"], "rei-v3-current-motorics")
        self.assertEqual(manifest["active_motorics"]["contract_id"], "rei-motorics-v1")

        logic_ids = {component["id"] for component in manifest["active_logic"]["components"]}
        motorics_ids = {component["id"] for component in manifest["active_motorics"]["components"]}
        self.assertIn("canonical-processor-contracts", logic_ids)
        self.assertIn("runtime-output-models", logic_ids)
        self.assertIn("cycle-entrypoint", motorics_ids)
        self.assertIn("playground-adapter", motorics_ids)
        self.assertIn("frontend-runtime", motorics_ids)

    def test_latest_logic_and_motorics_paths_exist(self) -> None:
        manifest = runtime_manifest()

        for section_name in ("active_logic", "active_motorics"):
            for component in manifest[section_name]["components"]:
                with self.subTest(section=section_name, component=component["id"]):
                    self.assertTrue((ROOT / component["path"]).exists())

    def test_playground_version_endpoint_uses_manifest(self) -> None:
        from main import version

        payload = version()
        self.assertEqual(payload["project"]["active_stack_id"], "rei-v3-observation-stack")
        self.assertEqual(payload["active"]["playground_api"]["base_path"], "/api/v1/playground")
        self.assertEqual(payload["active_logic"]["id"], "rei-v3-current-logic")
        self.assertEqual(payload["active_motorics"]["id"], "rei-v3-current-motorics")

    def test_profile_matrix_156_is_the_baseline_evaluation(self) -> None:
        from scripts import run_rei_profile_matrix as matrix

        manifest = runtime_manifest()
        baseline = manifest["baseline_evaluation"]
        expected_cases = len(matrix.PROFILES) * len(matrix.SCENARIOS)

        self.assertEqual(baseline["id"], "rei-profile-matrix-156")
        self.assertEqual(baseline["contract_id"], "rei-profile-matrix-156-v1")
        self.assertEqual(baseline["script"], "scripts/run_rei_profile_matrix.py")
        self.assertEqual(baseline["engine_entrypoint"], "rei.engine.ReiEngine.run_rei_cycle")
        self.assertEqual(baseline["profile_count"], len(matrix.PROFILES))
        self.assertEqual(baseline["scenario_count"], len(matrix.SCENARIOS))
        self.assertEqual(baseline["case_count"], expected_cases)
        self.assertEqual(expected_cases, 156)
        self.assertEqual(baseline["docs_summary_dir"], "Docs/evals")
        self.assertTrue((ROOT / baseline["script"]).exists())

    def test_legacy_fastapi_routes_are_marked_deprecated(self) -> None:
        from main import app

        routes = {getattr(route, "path", ""): route for route in app.routes}
        for path in ("/api/v1/minds", "/api/v1/characters", "/api/v1/simulate", "/api/v1/rei-cycle"):
            with self.subTest(path=path):
                self.assertTrue(getattr(routes[path], "deprecated", False))

    def test_legacy_surfaces_are_named_in_manifest(self) -> None:
        manifest = runtime_manifest()
        legacy = {item["id"]: item for item in manifest["legacy"]}

        self.assertEqual(
            legacy["legacy-fastapi-simulation-endpoints"]["contract_id"],
            "legacy-simulation-api-v0",
        )
        self.assertEqual(
            legacy["legacy-fastapi-simulation-endpoints"]["status"],
            "deprecated-compatibility",
        )

    def test_archived_legacy_ui_scripts_are_disabled(self) -> None:
        package_path = ROOT / "archive" / "legacy-ui-2026-05-19" / "package.json"
        payload = json.loads(package_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["version"], "0.0.0-archived")
        for script in ("dev", "build", "preview"):
            with self.subTest(script=script):
                self.assertIn("Archived legacy UI", payload["scripts"][script])


if __name__ == "__main__":
    unittest.main()
