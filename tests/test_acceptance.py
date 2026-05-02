from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.acceptance import assess_acceptance


class AcceptanceAssessmentTests(unittest.TestCase):
    def test_rationalized_delay(self) -> None:
        assessment = assess_acceptance(
            {
                "preferred_action": "delay until more data is collected",
                "rationalization_risk": "more research can justify not moving",
                "unknowns": ["financial runway data"],
            },
            {
                "preferred_action": "launch and move toward freedom",
                "desired_image": "alive and free",
                "pride_or_shame": "pride wants the business image",
            },
            {
                "preferred_action": "wait and protect stability",
                "threat_map": "loss of stability",
                "minimum_safety_condition": "runway first",
            },
        )

        self.assertEqual(assessment.behavioral_alignment, "split")
        self.assertEqual(assessment.acceptance_quality, "mixed")
        self.assertEqual(assessment.non_acceptance_pattern, "rationalized safety freeze")

    def test_attachment_return_loop_is_not_acceptance(self) -> None:
        assessment = assess_acceptance(
            {
                "preferred_action": "return for one more chance",
                "rationalization_risk": "one more chance sounds reasonable",
            },
            {
                "preferred_action": "return and repair the beautiful image",
                "desired_image": "the relationship becomes beautiful again",
            },
            {
                "preferred_action": "return to stop panic",
                "attachment_issue": "panic when imagining being alone",
            },
        )

        self.assertEqual(assessment.behavioral_alignment, "aligned")
        self.assertEqual(assessment.acceptance_quality, "non_accepting")
        self.assertIn("attachment panic", assessment.non_acceptance_pattern)

    def test_healthy_bounded_action_is_accepting(self) -> None:
        assessment = assess_acceptance(
            {
                "preferred_action": "run a bounded reversible pilot",
                "rationalization_risk": "none visible",
                "unknowns": [],
            },
            {
                "preferred_action": "try one small test that still feels alive",
                "desired_image": "dignified aliveness through a small test",
            },
            {
                "preferred_action": "allow a bounded reversible pilot",
                "minimum_safety_condition": "stop condition and low exposure",
            },
        )

        self.assertEqual(assessment.behavioral_alignment, "aligned")
        self.assertEqual(assessment.acceptance_quality, "accepting")

    def test_public_freeze(self) -> None:
        assessment = assess_acceptance(
            {
                "known_facts": ["body freezes when people are judging"],
                "preferred_action": "give the public talk",
                "rationalization_risk": "career logic may ignore the body alarm",
            },
            {
                "preferred_action": "show up and receive recognition",
                "desired_image": "recognition and applause",
            },
            {
                "preferred_action": "freeze and disappear",
                "body_alarm": "body freezes",
                "flight_or_freeze_signal": "disappear from judgment",
            },
        )

        self.assertEqual(assessment.behavioral_alignment, "split")
        self.assertEqual(assessment.acceptance_quality, "mixed")
        self.assertEqual(assessment.non_acceptance_pattern, "body alarm overrides conscious plan")


if __name__ == "__main__":
    unittest.main()
