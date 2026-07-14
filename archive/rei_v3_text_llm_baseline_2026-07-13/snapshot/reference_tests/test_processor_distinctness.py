from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.models import ProviderSelection
from rei.processor_eval import compare_processor_outputs, run_processor_signal, score_processor_signal


class ProcessorDistinctnessTests(unittest.TestCase):
    def test_role_contamination_is_flagged_per_mind(self) -> None:
        racio_signal = {
            "mind": "racio",
            "is_conscious": True,
            "translated_by_racio": False,
            "perception": "A beautiful body alarm speaks from the abyss.",
            "facts": ["one fact"],
            "unknowns": ["one unknown"],
            "options": ["one option"],
            "preferred_action": "make a plan",
            "rationalization_risk": "delay",
            "what_it_may_ignore": "desire",
            "confidence": 0.5,
        }
        emocio_signal = {
            "mind": "emocio",
            "is_conscious": False,
            "translated_by_racio": True,
            "perception": "Build a risk matrix and step-by-step budget.",
            "current_image": "flat",
            "desired_image": "alive",
            "broken_image": "small",
            "shame_or_pride": "shame",
            "attraction_or_rejection": "attraction",
            "preferred_action": "move",
            "what_it_may_ignore": "facts",
            "confidence": 0.5,
        }
        instinkt_signal = {
            "mind": "instinkt",
            "is_conscious": False,
            "translated_by_racio": True,
            "perception": "A poetic oracle in a fantasy kingdom wants admiration.",
            "threat_map": "threat",
            "loss_map": "loss",
            "body_alarm": "alarm",
            "boundary_or_trust_issue": "trust",
            "minimum_safety_condition": "safety",
            "preferred_action": "pause",
            "what_it_may_ignore": "image",
            "confidence": 0.5,
        }

        self.assertTrue(score_processor_signal("racio", racio_signal)["style_violations"])
        self.assertTrue(score_processor_signal("emocio", emocio_signal)["style_violations"])
        self.assertTrue(score_processor_signal("instinkt", instinkt_signal)["style_violations"])

    def test_deterministic_processors_stay_distinct(self) -> None:
        provider = ProviderSelection(provider_mode="deterministic", use_llm=False)
        prompt = "A person wants to quit a stable job for a creative business but fears instability."
        signals = {
            mind: run_processor_signal(mind, prompt, provider)[0]
            for mind in ["racio", "emocio", "instinkt"]
        }

        comparison = compare_processor_outputs(signals)

        self.assertTrue(comparison["distinctness_pass"], comparison)
        self.assertLess(comparison["max_overlap"], 0.45)


if __name__ == "__main__":
    unittest.main()
