from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from scripts.run_granite_weighted_short import (  # noqa: E402
    artifact_integrity,
    artifact_paths,
    count_jsonl_lines,
    strict_violations,
    summarize,
    write_json,
    write_jsonl,
)


def completed_row(case_index: int = 1) -> dict[str, object]:
    return {
        "case_index": case_index,
        "scenario_id": "pure-budget-allocation",
        "scenario_title": "Pure budget allocation",
        "scenario_prompt": "Allocate a fixed budget.",
        "profile": "R",
        "profile_top_minds": ["R"],
        "elapsed_seconds": 0.01,
        "trace": {"synthesis_turn": {"final_monologue": "Racio, Emocio, and Instinkt are all visible."}},
        "evaluation": {
            "synthesis_tilt": "R",
            "tilt_matches_profile_top": True,
            "decision": {"valid": True},
            "rei_audit": {
                "has_processor_weights": True,
                "has_weighted_contributions": True,
                "has_contribution_ranking": True,
                "has_synthesis_tilt": True,
                "has_underrepresented_signal": True,
                "has_final_monologue": True,
                "all_three_minds_present_in_contributions": True,
                "ranking_matches_contributions": True,
                "tilt_matches_ranking": True,
                "contribution_sum_valid": True,
                "missing_mind_mentions_in_final_monologue": [],
                "stock_phrase_hits": {},
            },
        },
        "diagnostics": {},
    }


class GraniteWeightedRunnerArtifactTests(unittest.TestCase):
    def test_results_jsonl_line_count_matches_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            results_path = output_dir / "results.jsonl"
            write_jsonl(results_path, {"case_index": 1})
            write_jsonl(results_path, {"case_index": 2})

            self.assertEqual(count_jsonl_lines(results_path), 2)

    def test_artifact_integrity_reports_complete_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = artifact_paths(Path(tmp))
            write_jsonl(paths["results_jsonl"], {"case_index": 1})
            write_json(paths["summary"], {"ok": True})
            paths["report"].write_text("# Report\n", encoding="utf-8")
            paths["progress"].write_text("done\n", encoding="utf-8")
            write_json(paths["scenario_plan"], {"cases": []})

            integrity = artifact_integrity(paths, expected_jsonl_lines=1)

            self.assertTrue(integrity["results_jsonl_exists"])
            self.assertEqual(integrity["results_jsonl_lines"], 1)
            self.assertTrue(integrity["results_jsonl_complete"])
            self.assertTrue(integrity["report_exists"])
            self.assertTrue(integrity["summary_exists"])
            self.assertTrue(integrity["progress_exists"])

    def test_summarize_includes_integrity_and_validity_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = artifact_paths(Path(tmp))
            row = completed_row()
            write_jsonl(paths["results_jsonl"], row)
            write_json(paths["summary"], {"ok": True})
            paths["report"].write_text("# Report\n", encoding="utf-8")
            paths["progress"].write_text("done\n", encoding="utf-8")

            summary = summarize(
                [row],
                {
                    "run_id": "test",
                    "model": "deterministic",
                    "planned_cases": 1,
                    "scenario_ids": ["pure-budget-allocation"],
                    "profiles": ["R"],
                },
                paths,
            )

            self.assertEqual(summary["artifact_integrity"]["results_jsonl_lines"], 1)
            self.assertTrue(summary["weighted_integrity"]["all_cases_have_three_contributions"])
            self.assertEqual(summary["decision_validity"]["rate"], 1.0)

    def test_strict_artifacts_fail_when_jsonl_missing(self) -> None:
        row = completed_row()
        summary = {
            "artifact_integrity": {
                "results_jsonl_exists": False,
                "results_jsonl_lines": 0,
                "results_jsonl_complete": False,
                "report_exists": True,
                "summary_exists": True,
            }
        }

        violations = strict_violations(summary, [row], strict_artifacts=True, strict_weighted=False)

        self.assertIn("results.jsonl missing or empty", violations)

    def test_strict_weighted_fails_missing_required_field(self) -> None:
        row = completed_row()
        row["evaluation"]["rei_audit"]["has_final_monologue"] = False  # type: ignore[index]

        violations = strict_violations({}, [row], strict_artifacts=False, strict_weighted=True)

        self.assertIn("case 001 missing weighted fields: has_final_monologue", violations)

    def test_strict_functional_fails_low_functional_rate(self) -> None:
        summary = {
            "functional_presence_summary": {
                "rate": 0.5,
                "scenario_grounding_rate": 1.0,
                "role_name_only_warning_count": 0,
                "generic_role_listing_warning_count": 0,
            },
            "weighted_compromise_quality_counts": {"weak": 0},
        }

        violations = strict_violations(
            summary,
            [completed_row()],
            strict_artifacts=False,
            strict_weighted=False,
            strict_functional=True,
            min_functional_presence_rate=0.8,
            min_scenario_grounding_rate=0.8,
        )

        self.assertIn("functional mind presence rate 0.5 is below 0.8", violations)


if __name__ == "__main__":
    unittest.main()
