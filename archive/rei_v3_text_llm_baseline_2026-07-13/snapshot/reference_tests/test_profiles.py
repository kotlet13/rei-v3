from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.profiles import is_equal_profile, profile_leader_label, profile_weights, strongest_minds


class ProfileHelperTests(unittest.TestCase):
    def test_equal_profile_is_tie_safe(self) -> None:
        profile, weights = profile_weights("R=E=I")

        self.assertEqual(profile, "R=E=I")
        self.assertEqual(strongest_minds(weights), ["racio", "emocio", "instinkt"])
        self.assertEqual(profile_leader_label(weights), "tie")
        self.assertTrue(is_equal_profile("REI"))

    def test_pair_profile_is_mixed_leader(self) -> None:
        profile, weights = profile_weights("R=E>I")

        self.assertEqual(profile, "(R=E)>I")
        self.assertEqual(strongest_minds(weights), ["racio", "emocio"])
        self.assertEqual(profile_leader_label(weights), "mixed")


if __name__ == "__main__":
    unittest.main()
