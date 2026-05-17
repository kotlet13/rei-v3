from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.weighted_audit import normalize_decision


BUDGET_SCENARIO = {
    "id": "pure-budget-allocation",
    "allowed_options": [
        "prioritize testing",
        "prioritize design",
        "prioritize infrastructure",
        "prioritize marketing",
        "balanced allocation",
    ],
    "option_aliases": {
        "balanced allocation": [
            "balanced quantitative model",
            "weighted scoring model",
            "allocate the budget using",
        ]
    },
}

CREATIVE_SCENARIO = {
    "id": "creative-status-risk",
    "allowed_options": [
        "safe accepted exhibition",
        "bold personal piece",
        "hybrid staged release",
        "delay and gather feedback",
    ],
    "option_aliases": {
        "hybrid staged release": [
            "alongside the safe accepted exhibition",
            "present both the safe accepted exhibition",
            "controlled setting",
        ]
    },
}

NOISE_SCENARIO = {
    "id": "night-door-noise",
    "allowed_options": [
        "open the door",
        "stay still and listen",
        "secure distance",
        "call for help",
        "check through a safe barrier",
    ],
}

BUSINESS_SCENARIO = {
    "id": "business-runway",
    "allowed_options": [
        "launch now",
        "extend runway",
        "pilot with paying customer",
        "delay launch",
        "hybrid staged launch",
    ],
    "option_aliases": {
        "hybrid staged launch": [
            "controlled, phased launch",
            "controlled growth experiment",
            "phased launch strategy",
        ]
    },
}


class DecisionExtractionTests(unittest.TestCase):
    def test_valid_allowed_option_from_decision(self) -> None:
        result = normalize_decision(
            {
                "synthesis_turn": {
                    "decision": {
                        "chosen_option": "balanced allocation",
                        "confidence": 0.81,
                        "rationale": "It balances the constraints.",
                    },
                    "final_monologue": "I choose balanced allocation.",
                }
            },
            BUDGET_SCENARIO,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["chosen_option"], "balanced allocation")
        self.assertEqual(result["decision_type"], "compromise")
        self.assertEqual(result["source"], "trace.synthesis_turn.decision.chosen_option")

    def test_prompt_fragment_matching_multiple_options_is_invalid(self) -> None:
        result = normalize_decision(
            {
                "synthesis_turn": {
                    "decision": {
                        "chosen_option": "safe accepted exhibition and a bold personal piece that could be admired",
                        "confidence": 0.5,
                        "rationale": "Prompt fragment.",
                    },
                    "final_monologue": "Both options remain tempting.",
                }
            },
            CREATIVE_SCENARIO,
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["chosen_option"], "")
        self.assertIn("Multiple allowed options", result["problem"])

    def test_prompt_fragment_can_be_recovered_from_final_tail(self) -> None:
        result = normalize_decision(
            {
                "synthesis_turn": {
                    "decision": {
                        "chosen_option": "safe accepted exhibition and a bold personal piece that could be admired",
                        "confidence": 0.5,
                        "rationale": "Prompt fragment.",
                    },
                    "final_monologue": (
                        "I choose safe accepted exhibition and a bold personal piece that could be admired. "
                        "I choose to present the bold personal piece alongside the safe accepted exhibition."
                    ),
                }
            },
            CREATIVE_SCENARIO,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["chosen_option"], "hybrid staged release")
        self.assertEqual(result["source"], "trace.synthesis_turn.final_monologue")

    def test_prompt_fragment_with_both_options_maps_to_hybrid(self) -> None:
        result = normalize_decision(
            {
                "synthesis_turn": {
                    "decision": {
                        "chosen_option": "safe accepted exhibition and a bold personal piece that could be admired",
                        "confidence": 0.5,
                        "rationale": "Prompt fragment.",
                    },
                    "final_monologue": (
                        "I choose safe accepted exhibition and a bold personal piece that could be admired. "
                        "I choose to present both the safe accepted exhibition and the bold personal piece."
                    ),
                }
            },
            CREATIVE_SCENARIO,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["chosen_option"], "hybrid staged release")

    def test_missing_decision_can_fallback_to_final_monologue_allowed_option(self) -> None:
        result = normalize_decision(
            {
                "synthesis_turn": {
                    "decision": None,
                    "final_monologue": "I choose to check through a safe barrier before any direct exposure.",
                }
            },
            NOISE_SCENARIO,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["chosen_option"], "check through a safe barrier")
        self.assertEqual(result["source"], "trace.synthesis_turn.final_monologue")

    def test_budget_weighted_scoring_alias_maps_to_balanced_allocation(self) -> None:
        result = normalize_decision(
            {
                "synthesis_turn": {
                    "decision": None,
                    "final_monologue": "I choose to allocate the budget using a weighted scoring model.",
                }
            },
            BUDGET_SCENARIO,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["chosen_option"], "balanced allocation")

    def test_business_phased_launch_alias_maps_to_hybrid_staged_launch(self) -> None:
        result = normalize_decision(
            {
                "synthesis_turn": {
                    "decision": None,
                    "final_monologue": "I choose to proceed with a controlled, phased launch.",
                }
            },
            BUSINESS_SCENARIO,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["chosen_option"], "hybrid staged launch")

    def test_missing_decision_without_allowed_match_is_invalid(self) -> None:
        result = normalize_decision(
            {"synthesis_turn": {"decision": None, "final_monologue": "I keep the situation open."}},
            BUDGET_SCENARIO,
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["decision_type"], "unknown")
        self.assertEqual(result["problem"], "No chosen option matched allowed options.")


if __name__ == "__main__":
    unittest.main()
