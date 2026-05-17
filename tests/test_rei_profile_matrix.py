from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.engine import LOW_BUT_POSSIBLE_RACIO_RISK, ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import Scenario
from scripts import run_rei_profile_matrix as matrix


def payload(
    *,
    ego: dict[str, Any] | None = None,
    racio: dict[str, Any] | None = None,
    emocio: dict[str, Any] | None = None,
    instinkt: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "signals": {
            "racio": racio or {},
            "emocio_translated": emocio or {},
            "instinkt_translated": instinkt or {},
        },
        "ego_resultant": ego or {},
        "acceptance": {
            "task_delegation": {
                "racio_action_tag": (tags or {}).get("racio", ""),
                "emocio_action_tag": (tags or {}).get("emocio", ""),
                "instinkt_action_tag": (tags or {}).get("instinkt", ""),
            }
        },
    }


def minimal_case(**overrides: Any) -> dict[str, Any]:
    case = {
        "case_index": 1,
        "scenario_id": "meeting_avoidance",
        "profile_input": "R",
        "profile_normalized": "R>(E=I)",
        "fallback_count": 0,
        "missing_required_keys": {
            "runtime_processors": {"racio": [], "emocio": [], "instinkt": []},
            "full_processors": {"racio": [], "emocio": [], "instinkt": []},
            "ego": [],
        },
        "raw_call_missing_required_keys": [
            {"label": "racio:1", "missing": []},
            {"label": "emocio:1", "missing": []},
            {"label": "instinkt:1", "missing": []},
            {"label": "ego_resultant:1", "missing": []},
        ],
        "processor_distinctness": {"max_overlap": 0.1},
        "profile_leader": "racio",
        "situational_driver": "racio",
        "resultant_leader_under_pressure": "racio",
        "leading_mind": "racio",
        "action_tendency": "ask for agenda",
        "action_tendency_class": "approach_confront",
        "raw_resultant_leader_under_pressure": "racio",
        "raw_leading_mind": "racio",
        "rei_resultant_adjusted_to_mixed": False,
        "false_positive_flags": {"processor_identity_unstable": {"racio": False, "emocio": False, "instinkt": False}},
        "false_negative_flags": {
            "expected_patterns_missing": [],
            "relationship_return_missing": False,
            "body_freeze_missing": False,
            "boundary_pressure_missing": False,
            "rationalization_missing": False,
            "quit_job_signature_missing": False,
        },
        "false_negative_severity": {
            "hard_false_negative": [],
            "soft_false_negative": [],
            "evaluator_warning": [],
        },
        "token_count": {"totals": {"prompt": 0, "eval": 0, "total": 0}, "calls": []},
        "output": {"ego_resultant": {}},
    }
    case.update(overrides)
    return case


class ReiProfileMatrixScoringTests(unittest.TestCase):
    def test_missing_required_key_count_ignores_empty_lists(self) -> None:
        summary = matrix.aggregate([minimal_case()])

        self.assertEqual(summary["missing_required_key_case_count"], 0)
        self.assertEqual(summary["true_missing_required_key_count"], 0)

    def test_rationalization_low_is_not_hard_false_negative(self) -> None:
        scenario = next(item for item in matrix.SCENARIOS if item["id"] == "quit_job_start_business")
        response = payload(
            racio={
                "rationalization_risk": "Low but possible.",
                "translation_of_other_minds_risk": "low; Racio may still make fear sound clean.",
            },
            tags={"racio": "hold"},
        )

        flags = matrix.false_negative_flags(scenario, response)
        severity = matrix.active_false_negative_severity(flags)

        self.assertEqual(flags["rationalization_missing"], "evaluator_warning")
        self.assertNotIn("rationalization_missing", severity["hard_false_negative"])

    def test_racio_risk_fields_are_never_na(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        signal = engine._coerce_racio_signal(
            {
                "perception": "The decision needs facts.",
                "known_facts": ["one fact"],
                "unknowns": ["one unknown"],
                "logical_options": ["wait"],
                "timeline_or_sequence": "Wait, inspect, decide.",
                "utility_model": "Minimize regret.",
                "preferred_action": "Wait briefly.",
                "rationalization_risk": "N/A",
                "rationalization_target": "unclear",
                "translation_of_other_minds_risk": "no risk",
                "confidence": 0.4,
                "uncertainty": "limited input",
            },
            Scenario(prompt="I need to decide."),
        )

        self.assertEqual(signal.rationalization_risk, LOW_BUT_POSSIBLE_RACIO_RISK)
        self.assertEqual(signal.translation_of_other_minds_risk, LOW_BUT_POSSIBLE_RACIO_RISK)

    def test_rei_profile_does_not_default_to_racio_without_coalition(self) -> None:
        for scenario_id in ["quit_job_start_business", "conflict_with_coworker"]:
            with self.subTest(scenario_id=scenario_id):
                fields = matrix.case_fields(
                    payload(
                        ego={
                            "profile_leader": "tie",
                            "situational_driver": "instinkt",
                            "resultant_leader_under_pressure": "racio",
                            "leading_mind": "racio",
                            "trusted_mind_or_coalition": "racio",
                            "action_tendency": "explain the decision cleanly",
                        }
                    ),
                    profile_input="REI",
                )

                self.assertEqual(fields["resultant_leader_under_pressure"], "mixed")
                self.assertEqual(fields["leading_mind"], "mixed")
                self.assertTrue(fields["rei_resultant_adjusted_to_mixed"])

    def test_creative_project_boundary_pressure_is_allowed(self) -> None:
        scenario = next(item for item in matrix.SCENARIOS if item["id"] == "creative_project_obsession")
        flags = matrix.false_positive_flags(
            scenario,
            payload(
                ego={"action_tendency": "protect time and health boundaries"},
                instinkt={"boundary_issue": "Boundary violation risk around health and relationships."},
                tags={"instinkt": "protect"},
            ),
        )

        self.assertFalse(flags["boundary_pressure_on_unexpected_scenario"])

    def test_romantic_return_loop_true_positive_detected(self) -> None:
        response = payload(
            ego={"action_tendency": "go back to the relationship for one more chance"},
            instinkt={"attachment_issue": "panic when imagining being alone with no partner"},
            emocio={"desired_image": "hope it will become beautiful again"},
            tags={"instinkt": "return"},
        )

        self.assertTrue(matrix.relationship_return_detected(response))


if __name__ == "__main__":
    unittest.main()
