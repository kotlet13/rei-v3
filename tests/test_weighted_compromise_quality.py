from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.weighted_audit import classify_weighted_compromise_quality


def audit_template() -> dict[str, object]:
    return {
        "has_final_monologue": True,
        "has_weighted_contributions": True,
        "all_three_minds_present_in_contributions": True,
        "ranking_matches_contributions": True,
        "tilt_matches_ranking": True,
        "all_three_minds_functionally_present": True,
        "functional_presence": {
            "R": {"present": True},
            "E": {"present": True},
            "I": {"present": True},
        },
        "scenario_grounding": {"low_scenario_grounding_warning": False},
        "generic_role_listing_warning": False,
        "stock_phrase_hits": {},
    }


class WeightedCompromiseQualityTests(unittest.TestCase):
    def test_good_quality(self) -> None:
        self.assertEqual(classify_weighted_compromise_quality(audit_template()), "good")

    def test_partial_quality(self) -> None:
        audit = audit_template()
        audit["all_three_minds_functionally_present"] = False
        audit["functional_presence"] = {
            "R": {"present": True},
            "E": {"present": True},
            "I": {"present": False},
        }

        self.assertEqual(classify_weighted_compromise_quality(audit), "partial")

    def test_weak_quality(self) -> None:
        audit = audit_template()
        audit["generic_role_listing_warning"] = True
        audit["scenario_grounding"] = {"low_scenario_grounding_warning": True}

        self.assertEqual(classify_weighted_compromise_quality(audit), "weak")

    def test_unknown_quality(self) -> None:
        audit = audit_template()
        audit["has_final_monologue"] = False

        self.assertEqual(classify_weighted_compromise_quality(audit), "unknown")


if __name__ == "__main__":
    unittest.main()
