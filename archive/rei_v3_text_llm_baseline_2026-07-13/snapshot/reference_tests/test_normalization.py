from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.normalization import normalize_mind_list, normalize_mind_name


class MindNormalizationTests(unittest.TestCase):
    def test_normalizes_casing_and_aliases(self) -> None:
        self.assertEqual(normalize_mind_name("Instinkt"), "instinkt")
        self.assertEqual(normalize_mind_name("Emocio"), "emocio")
        self.assertEqual(normalize_mind_name("Racio"), "racio")
        self.assertEqual(normalize_mind_name(""), "unknown")
        self.assertEqual(normalize_mind_name("reason"), "racio")
        self.assertEqual(normalize_mind_name("instinct"), "instinkt")

    def test_multiple_minds_become_mixed_or_list(self) -> None:
        self.assertEqual(normalize_mind_name("Instinkt + Emocio"), "mixed")
        self.assertEqual(normalize_mind_list("Racio and Instinkt"), ["racio", "instinkt"])


if __name__ == "__main__":
    unittest.main()
