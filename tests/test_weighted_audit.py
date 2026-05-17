from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.weighted_audit import audit_weighted_synthesis, stock_phrase_hits, summarize_stock_phrase_cases


def fake_trace(**synthesis_overrides: object) -> dict[str, object]:
    synthesis = {
        "processor_weights": {"R": 0.5, "E": 0.25, "I": 0.25},
        "weighted_contributions": {"R": 0.55, "E": 0.25, "I": 0.2},
        "contribution_ranking": ["R", "E", "I"],
        "synthesis_tilt": "R",
        "underrepresented_signal": "I",
        "hijack_risk": "watch: Instinkt pressure is present but does not overwrite hierarchy.",
        "final_monologue": (
            "Racio keeps the plan tied to evidence, cost, and sequence. "
            "Emocio keeps meaning and recognition visible. "
            "Instinkt checks risk, boundary, and safety."
        ),
        "main_conflict": "All three processors remain visible.",
        "main_agreement": "The weighted compromise keeps all signals in view.",
        "decision": {
            "chosen_option": "balanced allocation",
            "confidence": 0.72,
            "rationale": "It preserves utility, meaning, and safety.",
        },
    }
    synthesis.update(synthesis_overrides)
    return {"synthesis_turn": synthesis}


class WeightedAuditTests(unittest.TestCase):
    def test_weighted_audit_accepts_complete_contributions(self) -> None:
        audit = audit_weighted_synthesis(fake_trace(), profile="R", scenario_id="pure-budget-allocation")

        self.assertTrue(audit["has_processor_weights"])
        self.assertTrue(audit["all_three_minds_present_in_contributions"])
        self.assertTrue(audit["all_three_minds_visible_in_final_monologue"])
        self.assertTrue(audit["ranking_matches_contributions"])
        self.assertTrue(audit["tilt_matches_ranking"])
        self.assertAlmostEqual(audit["contribution_sum"], 1.0)
        self.assertEqual(audit["normalized_contributions"], {"R": 0.55, "E": 0.25, "I": 0.2})

    def test_missing_contribution_is_flagged(self) -> None:
        audit = audit_weighted_synthesis(
            fake_trace(weighted_contributions={"R": 0.7, "E": 0.3}, contribution_ranking=["R", "E"]),
            profile="R",
            scenario_id="pure-budget-allocation",
        )

        self.assertFalse(audit["all_three_minds_present_in_contributions"])
        self.assertFalse(audit["ranking_matches_contributions"])

    def test_missing_final_mind_marker_creates_mechanical_warning(self) -> None:
        audit = audit_weighted_synthesis(
            fake_trace(final_monologue="Racio keeps the plan tied to evidence and sequence."),
            profile="R",
            scenario_id="pure-budget-allocation",
        )

        self.assertFalse(audit["all_three_minds_visible_in_final_monologue"])
        self.assertEqual(audit["missing_mind_mentions_in_final_monologue"], ["E", "I"])
        self.assertTrue(audit["mechanical_profile_match_warning"])

    def test_rei_without_two_of_three_explanation_warns(self) -> None:
        audit = audit_weighted_synthesis(
            fake_trace(final_monologue="I choose balanced allocation because the evidence and sequence are clearest."),
            profile="REI",
            scenario_id="pure-budget-allocation",
        )

        self.assertFalse(audit["rei_two_of_three_explanation_present"])
        self.assertTrue(audit["rei_arbitrary_tilt_warning"])

    def test_stock_phrase_summary_tracks_cases(self) -> None:
        trace = fake_trace(final_monologue="Use a bounded test, then a reversible step. Reversible choices avoid blocked moves.")
        hits = stock_phrase_hits(trace)
        self.assertEqual(hits["reversible"], 2)
        self.assertEqual(hits["bounded test"], 1)
        self.assertEqual(hits["blocked"], 1)

        summary = summarize_stock_phrase_cases(
            [
                {
                    "case_index": 1,
                    "scenario_id": "pure-budget-allocation",
                    "profile": "R",
                    "evaluation": {"rei_audit": {"stock_phrase_hits": hits}},
                }
            ]
        )

        self.assertEqual(summary["stock_phrase_density"], 4.0)
        self.assertTrue(summary["density_warning"])
        self.assertEqual(summary["worst_repetition_cases"][0]["case_id"], "001")


if __name__ == "__main__":
    unittest.main()
