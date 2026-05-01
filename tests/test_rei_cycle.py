from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.acceptance import assess_acceptance
from rei.engine import ReiEngine
from rei.json_utils import extract_json_object, validate_required_keys
from rei.knowledge import KnowledgeIndex
from rei.models import EmocioSignal, InstinktSignal, ProviderSelection, RacioSignal
from rei.profiles import profile_weights


class ReiCycleTests(unittest.TestCase):
    def test_profile_weights(self) -> None:
        profile, weights = profile_weights("R=E=I")
        self.assertEqual(profile, "R=E=I")
        self.assertAlmostEqual(weights["racio"], weights["emocio"])
        self.assertAlmostEqual(weights["emocio"], weights["instinkt"])

        profile, weights = profile_weights("I>E>R")
        self.assertEqual(profile, "I>E>R")
        self.assertGreater(weights["instinkt"], weights["emocio"])
        self.assertGreater(weights["emocio"], weights["racio"])

        profile, _weights = profile_weights("not-a-profile")
        self.assertEqual(profile, "R=E=I")

    def test_json_utils(self) -> None:
        parsed = extract_json_object('noise {"a": 1, "b": {"c": 2}} tail')
        self.assertEqual(parsed["b"]["c"], 2)
        self.assertEqual(validate_required_keys(parsed, ["a", "missing"]), ["missing"])

    def test_schema_translation_flags(self) -> None:
        racio = RacioSignal(
            perception="facts first",
            known_facts=["one fact"],
            unknowns=["one unknown"],
            logical_options=["test"],
            timeline_or_sequence="first test",
            primary_motive="clarity",
            preferred_action="make a plan",
            accepted_expression="clear planning",
            non_accepted_expression="over-control",
            resistance_to_other_minds="rejects non-verbal signals",
            what_this_mind_needs="facts",
            risk_if_ignored="chaos",
            risk_if_dominant="rationalization",
            rationalization_risk="delay may sound like responsibility",
            confidence=0.5,
            uncertainty="limited input",
        )
        self.assertTrue(racio.is_conscious)
        self.assertFalse(racio.translated_by_racio)

        with self.assertRaises(ValidationError):
            EmocioSignal(
                translated_by_racio=False,
                perception="scene",
                current_image="now",
                desired_image="alive",
                broken_image="shame",
                social_meaning="status",
                attraction_or_rejection="attraction",
                pride_or_shame="pride",
                competition_signal="rivalry",
                attack_impulse="sharpness",
                primary_motive="image",
                preferred_action="open",
                accepted_expression="warm expression",
                non_accepted_expression="display",
                resistance_to_other_minds="hates closure",
                what_this_mind_needs="dignity",
                risk_if_ignored="resentment",
                risk_if_dominant="impulse",
                confidence=0.5,
                uncertainty="limited input",
            )

        with self.assertRaises(ValidationError):
            InstinktSignal(
                is_conscious=True,
                perception="risk",
                threat_map="loss",
                loss_map="stability",
                body_alarm="pause",
                boundary_issue="unclear",
                trust_issue="unproven",
                attachment_issue="distance",
                scarcity_signal="money",
                flight_or_freeze_signal="freeze",
                minimum_safety_condition="reversible test",
                primary_motive="safety",
                preferred_action="pause",
                accepted_expression="boundary",
                non_accepted_expression="avoidance",
                resistance_to_other_minds="resists exposure",
                what_this_mind_needs="safety",
                risk_if_ignored="panic",
                risk_if_dominant="closure",
                confidence=0.5,
                uncertainty="limited input",
            )

    def test_acceptance_detects_desire_vs_safety(self) -> None:
        assessment = assess_acceptance(
            {"preferred_action": "make a plan", "unknowns": []},
            {"preferred_action": "move and launch quickly", "desired_image": "freedom"},
            {"preferred_action": "pause and check safety", "minimum_safety_condition": "runway"},
        )
        self.assertEqual(assessment.overall_level, "mixed")
        self.assertIn("Emocio wants movement", assessment.main_conflict)

    def test_deterministic_rei_cycle_shape(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        response, diagnostics = engine.run_rei_cycle(
            "I want to quit my job and start a business, but I keep delaying.",
            character_profile="I>E>R",
            provider=ProviderSelection(provider_mode="deterministic", use_llm=False),
        )
        self.assertEqual(response.mode, "rei_cycle")
        self.assertFalse(response.signals.emocio_translated.is_conscious)
        self.assertTrue(response.signals.emocio_translated.translated_by_racio)
        self.assertFalse(response.signals.instinkt_translated.is_conscious)
        self.assertTrue(response.signals.instinkt_translated.translated_by_racio)
        self.assertTrue(response.signals.racio.is_conscious)
        self.assertIn("likely_action_under_pressure", response.ego_resultant.model_dump())
        self.assertEqual(diagnostics["profile_normalized"], "I>E>R")


if __name__ == "__main__":
    unittest.main()
