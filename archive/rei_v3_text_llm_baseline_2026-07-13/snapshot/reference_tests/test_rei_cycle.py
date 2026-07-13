from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.acceptance import assess_acceptance
from rei.contract_loader import canonical_defaults_for
from rei.engine import ReiEngine
from rei.json_utils import extract_json_object, validate_required_keys
from rei.knowledge import KnowledgeIndex
from rei.models import EmocioSignal, InstinktSignal, ProviderSelection, RacioSignal, Scenario
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

    def test_ego_payload_summary_is_compact(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        signal = engine._fallback_rei_racio_signal(Scenario(prompt="I do not want to attend the meeting."))
        full_payload = signal.model_dump(mode="json")
        summary = engine._ego_signal_summary(signal)

        self.assertLess(len(str(summary)), len(str(full_payload)))
        self.assertIn("known_facts", summary)
        self.assertIn("rationalization_risk", summary)
        for excluded in (
            "native_language",
            "source_refs",
            "safety_flags",
            "truth_model",
            "defense_mode",
            "justice_model",
            "accepting_expression",
            "non_accepting_distortion",
        ):
            self.assertNotIn(excluded, summary)

    def test_coerce_attaches_canonical_fields_from_contract(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        payload = {
            "perception": "The meeting needs agenda and cost checks.",
            "known_facts": ["A meeting is scheduled."],
            "unknowns": ["agenda", "cost"],
            "logical_options": ["ask for agenda", "decline", "request notes"],
            "timeline_or_sequence": "Ask, compare cost, decide.",
            "utility_model": "Minimize wasted time.",
            "preferred_action": "Ask for agenda before attending.",
            "rationalization_risk": "Planning could hide avoidance.",
            "rationalization_target": "Discomfort could be called logic.",
            "translation_of_other_minds_risk": "Body alarm could be flattened.",
            "confidence": 0.77,
            "uncertainty": "Only text is available.",
            "native_language": ["bogus"],
            "world_filter": "bogus",
            "primary_motive": "bogus",
            "truth_model": "bogus",
            "defense_mode": "bogus",
            "justice_model": "bogus",
            "accepting_expression": "bogus",
            "non_accepting_distortion": "bogus",
            "blind_spot": "bogus",
            "source_refs": ["bogus"],
        }
        signal = engine._coerce_racio_signal(payload, Scenario(prompt="I do not want to attend the meeting."))
        defaults = canonical_defaults_for("racio")

        self.assertEqual(signal.perception, payload["perception"])
        self.assertEqual(signal.native_language, defaults["native_language"])
        self.assertEqual(signal.world_filter, defaults["world_filter"])
        self.assertEqual(signal.primary_motive, defaults["primary_motive"])
        self.assertEqual(signal.truth_model, defaults["truth_model"])
        self.assertEqual(signal.accepting_expression, defaults["accepting_expression"])
        self.assertEqual(signal.non_accepting_distortion, defaults["non_accepting_distortion"])
        self.assertEqual(signal.source_refs, defaults["source_refs"])

    def test_deterministic_meeting_cycle_stays_non_romantic(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        response, diagnostics = engine.run_rei_cycle(
            "I do not want to attend the meeting.",
            character_profile="R=E=I",
            provider=ProviderSelection(provider_mode="deterministic", use_llm=False),
        )
        serialized = response.model_dump_json()

        self.assertEqual(diagnostics["fallbacks"], [])
        self.assertTrue(any("agenda" in item and "cost" in item for item in response.signals.racio.unknowns))
        self.assertIn("recognition", response.signals.emocio_translated.recognition_need.lower())
        self.assertIn("trust", response.signals.instinkt_translated.trust_boundary.lower())
        self.assertNotEqual(response.acceptance.task_delegation["instinkt_action_tag"], "return")
        self.assertNotIn("fear of being alone", serialized)
        self.assertNotIn("beautiful-image hope", response.acceptance.non_acceptance_pattern)


if __name__ == "__main__":
    unittest.main()
