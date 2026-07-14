from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.engine import ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection


class EgoFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        cls.provider = ProviderSelection(provider_mode="deterministic", use_llm=False)

    def test_profile_situation_and_resultant_are_distinct_fields(self) -> None:
        response, _diagnostics = self.engine.run_rei_cycle(
            "I want to quit my job and start a business, but I keep delaying. "
            "I say I need more data, but I also feel excited by freedom and afraid of losing stability.",
            character_profile="E>(R=I)",
            provider=self.provider,
        )
        ego = response.ego_resultant

        self.assertEqual(ego.profile_leader, "emocio")
        self.assertEqual(ego.profile_leader_minds, ["emocio"])
        self.assertEqual(ego.situational_driver, "instinkt")
        self.assertEqual(ego.resultant_leader_under_pressure, "instinkt")
        self.assertEqual(ego.leading_mind, ego.resultant_leader_under_pressure)
        self.assertTrue(ego.profile_influence_explanation)
        self.assertIn(ego.racio_role, {"clear_analysis", "rationalizer", "overcontroller", "translator", "suppressed", "unknown"})
        self.assertIn(ego.emocio_role, {"motivator", "image_hunger", "shame_driver", "status_driver", "connector", "suppressed", "unknown"})
        self.assertIn(ego.instinkt_role, {"protector", "freeze_driver", "boundary_guard", "panic_driver", "attachment_guard", "suppressed", "unknown"})
        self.assertIn(ego.decision_stability, {"stable", "fragile", "unstable", "unknown"})

    def test_equal_profile_does_not_default_to_racio(self) -> None:
        response, _diagnostics = self.engine.run_rei_cycle(
            "A developer must choose between three technical architectures. The decision depends on timeline, "
            "maintenance cost, and known constraints.",
            character_profile="R=E=I",
            provider=self.provider,
        )

        self.assertEqual(response.ego_resultant.profile_leader, "tie")
        self.assertEqual(
            response.ego_resultant.profile_leader_minds,
            ["racio", "emocio", "instinkt"],
        )


if __name__ == "__main__":
    unittest.main()
