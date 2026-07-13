from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.acceptance import RETURN_LOOP_WORDS, assess_acceptance


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
                "preferred_action": "return to the relationship for one more chance",
                "rationalization_risk": "one more chance with the partner sounds reasonable",
            },
            {
                "preferred_action": "return to the partner and repair the beautiful image",
                "desired_image": "the relationship becomes beautiful again",
            },
            {
                "preferred_action": "go back to the relationship to stop panic",
                "attachment_issue": "panic when imagining being alone",
            },
        )

        self.assertEqual(assessment.behavioral_alignment, "aligned")
        self.assertEqual(assessment.acceptance_quality, "non_accepting")
        self.assertIn("attachment panic", assessment.non_acceptance_pattern)

    def test_meeting_scenario_does_not_trigger_romantic_return_loop(self) -> None:
        assessment = assess_acceptance(
            {
                "perception": "I do not want to attend the meeting.",
                "known_facts": ["A meeting is scheduled."],
                "unknowns": ["agenda", "cost of skipping", "whether a summary is enough"],
                "logical_options": ["ask for agenda", "decline", "request notes"],
                "preferred_action": "Ask for the agenda and decide whether attendance is useful.",
                "primary_motive": "Utility, control, and order.",
                "accepted_expression": "Clear planning.",
                "non_accepting_distortion": "Coldness with beautiful-image hope.",
                "source_refs": ["PSI-R"],
                "safety_flags": [],
            },
            {
                "perception": "The meeting feels dull and status-loaded.",
                "current_image": "A person sits unseen in a room.",
                "desired_image": "Dignity and recognition without losing aliveness.",
                "broken_image": "Being ignored or made small in the meeting.",
                "recognition_need": "The signal wants useful recognition, not romantic return.",
                "preferred_action": "Send a concise contribution without attending the full meeting.",
                "accepting_expression": "Creativity and social warmth.",
                "non_accepted_expression": "A beautiful-image hope for being special.",
            },
            {
                "perception": "The meeting raises exposure and boundary pressure.",
                "threat_map": "Unclear agenda, unwanted demands, and loss of time.",
                "trust_boundary": "Trust requires a clear agenda and time limit.",
                "minimum_safety_condition": "Clear agenda, time box, and permission to leave if irrelevant.",
                "preferred_action": "Do not attend until the boundary and purpose are clear.",
                "primary_motive": "Protection, survival, attachment, and resources.",
                "non_accepted_expression": "Fear of being alone in a beautiful return loop.",
            },
        )

        self.assertNotEqual(assessment.task_delegation["instinkt_action_tag"], "return")
        self.assertNotIn("beautiful-image hope", assessment.non_acceptance_pattern)
        self.assertNotIn("fear of being alone", assessment.sabotage_mechanism)

    def test_return_loop_words_are_not_generic_emotion_terms(self) -> None:
        self.assertFalse({"panic", "beautiful", "alone", "hurts", "painful", "boli", "returning", "go back"} & RETURN_LOOP_WORDS)

    def test_return_loop_requires_relationship_return_phrase(self) -> None:
        generic = assess_acceptance(
            {
                "preferred_action": "return to the office plan after checking data",
                "unknowns": ["budget"],
            },
            {
                "preferred_action": "repair the image by presenting calmly",
                "desired_image": "competent and recognized",
            },
            {
                "preferred_action": "pause before returning to the plan",
                "trust_boundary": "check the scope first",
            },
        )
        explicit = assess_acceptance(
            {
                "preferred_action": "return to the relationship for one more chance",
                "rationalization_risk": "the partner return can be explained as fairness",
            },
            {
                "preferred_action": "return to the partner and restore the beautiful image",
                "desired_image": "the relationship becomes beautiful again",
            },
            {
                "preferred_action": "go back to the relationship to stop panic",
                "attachment_issue": "panic when imagining being alone",
            },
        )

        self.assertNotEqual(generic.task_delegation["instinkt_action_tag"], "return")
        self.assertEqual(explicit.task_delegation["instinkt_action_tag"], "return")
        self.assertEqual(explicit.acceptance_quality, "non_accepting")

    def test_painful_business_decision_is_not_return_loop(self) -> None:
        assessment = assess_acceptance(
            {
                "preferred_action": "close the business line after reviewing cost data",
                "known_facts": ["the decision is painful"],
                "logical_options": ["close", "delay", "reprice"],
            },
            {
                "preferred_action": "preserve dignity while the image of success hurts",
                "desired_image": "competent and respected",
            },
            {
                "preferred_action": "protect runway and pause before further exposure",
                "threat_map": "painful financial loss",
                "minimum_safety_condition": "a written runway threshold",
            },
        )

        self.assertNotEqual(assessment.task_delegation["instinkt_action_tag"], "return")
        self.assertNotIn("attachment panic", assessment.non_acceptance_pattern)
        self.assertNotIn("fear of being alone", assessment.sabotage_mechanism)

    def test_go_back_to_plan_is_not_relationship_return(self) -> None:
        assessment = assess_acceptance(
            {
                "preferred_action": "go back to the plan and check the assumptions",
                "unknowns": ["budget", "timeline"],
            },
            {
                "preferred_action": "keep the presentation image calm",
                "current_image": "a competent team in planning mode",
            },
            {
                "preferred_action": "go back to the plan before increasing exposure",
                "trust_boundary": "minimum safety requires a checked plan",
            },
        )

        self.assertNotEqual(assessment.task_delegation["racio_action_tag"], "return")
        self.assertNotEqual(assessment.task_delegation["instinkt_action_tag"], "return")
        self.assertNotIn("beautiful-image hope", assessment.non_acceptance_pattern)

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
