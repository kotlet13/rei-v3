from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProcessorMatrixRunnerTests(unittest.TestCase):
    def test_deterministic_processor_runner_writes_expected_outputs(self) -> None:
        test_runs_dir = ROOT / "output" / "test-runs"
        test_runs_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_runs_dir) as tmp:
            output_dir = Path(tmp)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_processor_matrix.py"),
                    "--provider",
                    "deterministic",
                    "--max-cases",
                    "3",
                    "--strict",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )

            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["total"], 3)
            self.assertEqual(summary["completed"], 3)
            self.assertTrue(summary["strict_pass"], completed.stdout)
            self.assertEqual(summary["metrics"]["fallback_count"], 0)
            self.assertGreaterEqual(summary["metrics"]["average_overall_score"], 0.75)
            for name in ["summary.json", "results.jsonl", "aggregate_summary.md", "aggregate_summary.json", "progress.log"]:
                self.assertTrue((output_dir / name).exists(), completed.stdout)
            self.assertFalse(Path(summary["results_jsonl"]).is_absolute())
            self.assertIn("Global Metrics", (output_dir / "aggregate_summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
