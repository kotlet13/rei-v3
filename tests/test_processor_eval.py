from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.models import ProviderSelection
from rei.processor_contracts import PROCESSOR_MINIMAL_REQUIRED_KEYS
from rei.processor_eval import run_processor_signal, score_processor_signal


class ProcessorEvalTests(unittest.TestCase):
    def test_deterministic_processor_outputs_match_minimal_contracts(self) -> None:
        provider = ProviderSelection(provider_mode="deterministic", use_llm=False)
        prompt = "A person wants to publish visible creative work but fears ridicule and exposure."

        for mind, required_keys in PROCESSOR_MINIMAL_REQUIRED_KEYS.items():
            with self.subTest(mind=mind):
                signal, diagnostics = run_processor_signal(mind, prompt, provider)
                score = score_processor_signal(mind, signal, diagnostics)

                self.assertEqual(signal["mind"], mind)
                self.assertTrue(set(required_keys).issubset(signal.keys()))
                self.assertTrue(diagnostics["valid_json"])
                self.assertFalse(diagnostics["fallback_used"])
                self.assertEqual(diagnostics["missing_required_keys"], [])
                self.assertEqual(score["rei_violations"], [])
                self.assertGreaterEqual(score["overall_score"], 0.75)

    def test_fallback_penalty_is_visible_in_score(self) -> None:
        provider = ProviderSelection(provider_mode="deterministic", use_llm=False)
        signal, diagnostics = run_processor_signal("racio", "A person delays a hard choice.", provider)
        clean_score = score_processor_signal("racio", signal, diagnostics)
        fallback_score = score_processor_signal("racio", signal, {**diagnostics, "fallback_used": True})

        self.assertLess(fallback_score["overall_score"], clean_score["overall_score"])


if __name__ == "__main__":
    unittest.main()
