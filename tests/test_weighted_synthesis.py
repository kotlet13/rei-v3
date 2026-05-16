from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.engine import ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection, PsycheState, Scenario


class WeightedSynthesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        cls.provider = ProviderSelection(provider_mode="deterministic", use_llm=False)

    def test_synthesis_exposes_all_three_weighted_contributions(self) -> None:
        trace, diagnostics = self.engine.simulate(
            Scenario(
                title="Career role choice",
                prompt=(
                    "A person must choose between software engineer, performer, or guardian. "
                    "The decision depends on utility, image, and safety pressure."
                ),
            ),
            PsycheState(character_id="R", acceptance_level=0.62),
            self.provider,
        )

        synthesis = trace.synthesis_turn

        self.assertEqual(set(synthesis.processor_weights), {"R", "E", "I"})
        self.assertEqual(set(synthesis.weighted_contributions), {"R", "E", "I"})
        self.assertEqual(set(synthesis.contribution_ranking), {"R", "E", "I"})
        self.assertAlmostEqual(sum(synthesis.weighted_contributions.values()), 1.0, places=2)
        self.assertEqual(synthesis.synthesis_tilt, "R")
        self.assertGreater(synthesis.weighted_contributions["R"], synthesis.weighted_contributions["E"])
        self.assertGreater(synthesis.weighted_contributions["R"], synthesis.weighted_contributions["I"])
        self.assertIn("weighted compromise", synthesis.final_monologue.lower())
        self.assertIn("Racio", synthesis.final_monologue)
        self.assertIn("Emocio", synthesis.final_monologue)
        self.assertIn("Instinkt", synthesis.final_monologue)
        self.assertEqual(diagnostics["weighted_synthesis"]["synthesis_tilt"], "R")

    def test_decision_rationale_does_not_erase_underrepresented_processor(self) -> None:
        trace, _diagnostics = self.engine.simulate(
            Scenario(
                title="Fantasy role choice",
                prompt=(
                    "In a dangerous kingdom, a person must choose from this list: strategist, "
                    "performer, or guardian. Each role carries status, exposure, and risk."
                ),
            ),
            PsycheState(character_id="E>I>R", acceptance_level=0.55),
            self.provider,
        )

        synthesis = trace.synthesis_turn

        self.assertEqual(synthesis.synthesis_tilt, "E")
        self.assertEqual(synthesis.contribution_ranking[0], "E")
        self.assertEqual(synthesis.contribution_ranking[-1], "R")
        self.assertIn("underrepresented", synthesis.ignored_or_suppressed_processor)
        self.assertNotIn("blocked", synthesis.decision.rationale.lower() if synthesis.decision else "")
        self.assertIn("weighted compromise", synthesis.decision.rationale.lower() if synthesis.decision else "")


if __name__ == "__main__":
    unittest.main()
