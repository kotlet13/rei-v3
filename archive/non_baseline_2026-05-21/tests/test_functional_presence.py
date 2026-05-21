from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.weighted_audit import audit_weighted_synthesis, extract_functional_mind_evidence


def trace(final_monologue: str) -> dict[str, object]:
    return {
        "synthesis_turn": {
            "processor_weights": {"R": 0.5, "E": 0.3, "I": 0.2},
            "weighted_contributions": {"R": 0.5, "E": 0.3, "I": 0.2},
            "contribution_ranking": ["R", "E", "I"],
            "synthesis_tilt": "R",
            "underrepresented_signal": "I",
            "hijack_risk": "low: synthesis tilt remains inside the character profile's top influence.",
            "final_monologue": final_monologue,
            "main_conflict": "",
            "main_agreement": "",
            "decision": {"chosen_option": "balanced allocation", "confidence": 0.8, "rationale": "ok"},
        }
    }


class FunctionalPresenceTests(unittest.TestCase):
    def test_generic_role_listing_does_not_pass_functional_presence(self) -> None:
        audit = audit_weighted_synthesis(
            trace("Racio contributes structure. Emocio contributes meaning. Instinkt contributes safety."),
            profile="R",
            scenario_id="pure-budget-allocation",
            grounding_terms=["budget", "testing", "design"],
        )

        self.assertFalse(audit["all_three_minds_functionally_present"])
        self.assertTrue(audit["generic_role_listing_warning"])
        self.assertTrue(audit["role_name_only_warning"])
        self.assertIn(audit["weighted_compromise_quality"], {"weak", "partial"})

    def test_functional_presence_passes_when_all_minds_do_distinct_work(self) -> None:
        text = (
            "Racio keeps the budget allocation tied to cost, sequence, and tradeoff. "
            "Emocio preserves the visible value of design quality and stakeholder recognition. "
            "Instinkt keeps the infrastructure risk and delivery boundary from being ignored."
        )

        audit = audit_weighted_synthesis(
            trace(text),
            profile="R",
            scenario_id="pure-budget-allocation",
            grounding_terms=["budget", "design", "infrastructure", "allocation"],
        )

        self.assertTrue(audit["all_three_minds_functionally_present"])
        self.assertGreaterEqual(audit["functional_presence_score"], 0.4)
        self.assertFalse(audit["generic_role_listing_warning"])

    def test_extract_functional_mind_evidence_reports_groups_and_missing(self) -> None:
        evidence = extract_functional_mind_evidence("The plan uses cost, sequence, risk, boundary, pride, and recognition.")

        self.assertTrue(evidence["R"]["present"])
        self.assertTrue(evidence["E"]["present"])
        self.assertTrue(evidence["I"]["present"])
        self.assertIn("facts_or_evidence", evidence["R"]["missing_functions"])


if __name__ == "__main__":
    unittest.main()
