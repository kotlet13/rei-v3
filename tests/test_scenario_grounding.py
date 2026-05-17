from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.weighted_audit import scenario_grounding_audit


class ScenarioGroundingTests(unittest.TestCase):
    def test_low_grounding_warning_when_expected_terms_are_absent(self) -> None:
        audit = scenario_grounding_audit(
            "The choice is emotionally meaningful and should remain balanced.",
            "pure-budget-allocation",
            ["budget", "testing", "design", "infrastructure", "marketing"],
        )

        self.assertEqual(audit["score"], 0.0)
        self.assertTrue(audit["low_scenario_grounding_warning"])

    def test_grounding_passes_when_scenario_terms_are_present(self) -> None:
        audit = scenario_grounding_audit(
            "The budget allocation protects testing and infrastructure while leaving design visible.",
            "pure-budget-allocation",
            ["budget", "testing", "design", "infrastructure", "marketing"],
        )

        self.assertEqual(audit["score"], 0.8)
        self.assertFalse(audit["low_scenario_grounding_warning"])
        self.assertEqual(audit["matched_terms"], ["budget", "testing", "design", "infrastructure"])


if __name__ == "__main__":
    unittest.main()
