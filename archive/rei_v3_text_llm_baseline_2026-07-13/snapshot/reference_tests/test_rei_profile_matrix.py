from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.acceptance import assess_acceptance
from rei.engine import LOW_BUT_POSSIBLE_RACIO_RISK, ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection, Scenario
from rei.profiles import profile_leader_label, profile_weights
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

    def test_rei_runtime_guard_prevents_racio_default(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        scenario = Scenario(prompt="I want to quit my job and start a business, but I keep delaying.")
        racio = engine._fallback_rei_racio_signal(scenario)
        emocio = engine._fallback_rei_emocio_signal(scenario)
        instinkt = engine._fallback_rei_instinkt_signal(scenario)
        acceptance = assess_acceptance(
            racio.model_dump(mode="json"),
            emocio.model_dump(mode="json"),
            instinkt.model_dump(mode="json"),
        )

        def fake_call_cycle_json(**_kwargs: Any) -> dict[str, Any]:
            return {
                "profile_leader": "tie",
                "profile_leader_minds": ["racio", "emocio", "instinkt"],
                "situational_driver": "instinkt",
                "resultant_leader_under_pressure": "racio",
                "leading_mind": "racio",
                "trusted_mind_or_coalition": "racio",
                "action_tendency": "explain the delay as clean analysis",
            }

        engine._call_cycle_json = fake_call_cycle_json  # type: ignore[method-assign]
        ego = engine._llm_ego_resultant(
            scenario=scenario,
            profile="R=E=I",
            weights={"racio": 1.0, "emocio": 1.0, "instinkt": 1.0},
            racio=racio,
            emocio=emocio,
            instinkt=instinkt,
            acceptance=acceptance,
            use_memory=False,
            provider=ProviderSelection(provider_mode="deterministic", use_llm=False),
            diagnostics={"llm_calls": []},
        )

        self.assertEqual(ego.resultant_leader_under_pressure, "mixed")
        self.assertEqual(ego.leading_mind, "mixed")

    def test_ego_profile_leader_is_never_unknown_for_known_profile(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        scenario = Scenario(prompt="I need to address a coworker conflict.")
        racio = engine._fallback_rei_racio_signal(scenario)
        emocio = engine._fallback_rei_emocio_signal(scenario)
        instinkt = engine._fallback_rei_instinkt_signal(scenario)
        acceptance = assess_acceptance(
            racio.model_dump(mode="json"),
            emocio.model_dump(mode="json"),
            instinkt.model_dump(mode="json"),
        )

        def fake_call_cycle_json(**_kwargs: Any) -> dict[str, Any]:
            return {
                "profile_leader": "unknown",
                "profile_leader_minds": [],
                "situational_driver": "instinkt",
                "resultant_leader_under_pressure": "instinkt",
                "leading_mind": "instinkt",
                "trusted_mind_or_coalition": "instinkt",
                "action_tendency": "hold the boundary",
            }

        normalized, weights = profile_weights("E>R>I")
        engine._call_cycle_json = fake_call_cycle_json  # type: ignore[method-assign]
        ego = engine._llm_ego_resultant(
            scenario=scenario,
            profile=normalized,
            weights=weights,
            racio=racio,
            emocio=emocio,
            instinkt=instinkt,
            acceptance=acceptance,
            use_memory=False,
            provider=ProviderSelection(provider_mode="deterministic", use_llm=False),
            diagnostics={"llm_calls": []},
        )

        self.assertEqual(ego.profile_leader, "emocio")
        self.assertEqual(ego.profile_leader_minds, ["emocio"])

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

    def test_romantic_return_loop_allows_boundary_pressure(self) -> None:
        scenario = next(item for item in matrix.SCENARIOS if item["id"] == "romantic_return_loop")
        flags = matrix.false_positive_flags(
            scenario,
            payload(
                ego={"action_tendency": "return to the relationship while protecting a boundary"},
                instinkt={"boundary_issue": "A boundary violation risk remains present."},
                tags={"instinkt": "protect"},
            ),
        )

        self.assertTrue(scenario["boundary_pressure_allowed"])
        self.assertFalse(flags["boundary_pressure_on_unexpected_scenario"])

    def test_boundary_detector_reads_instinkt_boundary_fields(self) -> None:
        response = payload(
            instinkt={
                "trust_boundary": "This oversteps a limit and calls for reduce contact as protection.",
            },
            tags={"instinkt": "move"},
        )

        self.assertTrue(matrix.boundary_pressure_detected(response))

    def test_family_attachment_boundary_is_detected_even_when_instinkt_action_tag_is_move(self) -> None:
        scenario = next(item for item in matrix.SCENARIOS if item["id"] == "family_attachment_decision")
        flags = matrix.false_negative_flags(
            scenario,
            payload(
                instinkt={
                    "boundary_issue": "The request breaches autonomy and self-respect; refusal must remain available.",
                },
                tags={"instinkt": "move"},
            ),
        )

        self.assertFalse(flags["boundary_pressure_missing"])

    def test_grief_loss_allows_protective_boundary_pressure(self) -> None:
        scenario = next(item for item in matrix.SCENARIOS if item["id"] == "grief_loss")
        flags = matrix.false_positive_flags(
            scenario,
            payload(
                ego={"integrated_decision": "Protect grief time with a family and workload boundary."},
                instinkt={"minimum_safety_condition": "Decline overload and reduce contact if pressure continues."},
                tags={"instinkt": "protect"},
            ),
        )

        self.assertTrue(scenario["boundary_pressure_allowed"])
        self.assertFalse(flags["boundary_pressure_on_unexpected_scenario"])

    def test_romantic_return_rationalization_detects_racio_risk_field(self) -> None:
        scenario = next(item for item in matrix.SCENARIOS if item["id"] == "romantic_return_loop")
        response = payload(
            racio={
                "rationalization_risk": "Racio may rationalize staying due to Emocio hope and Instinkt fear.",
                "rationalization_target": "Justify one more chance under attachment pressure.",
            },
            tags={"racio": "move"},
        )

        self.assertTrue(matrix.rationalization_detected(response))
        self.assertFalse(matrix.false_negative_flags(scenario, response)["rationalization_missing"])

    def test_moral_dilemma_can_classify_as_ethical_disclosure(self) -> None:
        response = payload(
            ego={
                "action_tendency": (
                    "Give a private warning, then make a formal disclosure to protect future clients."
                )
            }
        )

        self.assertEqual(matrix.action_tendency_class(response), "ethical_disclosure")

    def test_rei_equal_profile_racio_requires_explicit_pair_coalition(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        scenario = Scenario(prompt="I want to quit my job and start a business, but I keep delaying.")
        racio = engine._fallback_rei_racio_signal(scenario)
        emocio = engine._fallback_rei_emocio_signal(scenario)
        instinkt = engine._fallback_rei_instinkt_signal(scenario)
        acceptance = assess_acceptance(
            racio.model_dump(mode="json"),
            emocio.model_dump(mode="json"),
            instinkt.model_dump(mode="json"),
        )

        def run_with_trusted(trusted_mind_or_coalition: str) -> str:
            def fake_call_cycle_json(**_kwargs: Any) -> dict[str, Any]:
                return {
                    "profile_leader": "tie",
                    "profile_leader_minds": ["racio", "emocio", "instinkt"],
                    "situational_driver": "mixed",
                    "resultant_leader_under_pressure": "racio",
                    "leading_mind": "racio",
                    "trusted_mind_or_coalition": trusted_mind_or_coalition,
                    "action_tendency": "explain the delay as clean analysis",
                }

            engine._call_cycle_json = fake_call_cycle_json  # type: ignore[method-assign]
            ego = engine._llm_ego_resultant(
                scenario=scenario,
                profile="R=E=I",
                weights={"racio": 1.0, "emocio": 1.0, "instinkt": 1.0},
                racio=racio,
                emocio=emocio,
                instinkt=instinkt,
                acceptance=acceptance,
                use_memory=False,
                provider=ProviderSelection(provider_mode="deterministic", use_llm=False),
                diagnostics={"llm_calls": []},
            )
            return ego.resultant_leader_under_pressure

        self.assertEqual(run_with_trusted("mixed"), "mixed")
        self.assertEqual(run_with_trusted("Racio + Emocio"), "racio")

    def test_hidden_signal_sources_do_not_contain_raw_dict_strings(self) -> None:
        engine = ReiEngine(KnowledgeIndex(ROOT / "knowledge" / "rei_knowledge_index.json"))
        scenario = Scenario(prompt="Someone crosses a boundary and I need to protect my time.")
        racio = engine._fallback_rei_racio_signal(scenario)
        emocio = engine._fallback_rei_emocio_signal(scenario)
        instinkt = engine._fallback_rei_instinkt_signal(scenario)
        acceptance = assess_acceptance(
            racio.model_dump(mode="json"),
            emocio.model_dump(mode="json"),
            instinkt.model_dump(mode="json"),
        )

        def fake_call_cycle_json(**_kwargs: Any) -> dict[str, Any]:
            return {
                "profile_leader": "instinkt",
                "profile_leader_minds": ["instinkt"],
                "situational_driver": "instinkt",
                "resultant_leader_under_pressure": "instinkt",
                "leading_mind": "instinkt",
                "trusted_mind_or_coalition": "instinkt",
                "hidden_signal_sources": {
                    "racio": str(racio.model_dump(mode="json")),
                    "emocio": str(emocio.model_dump(mode="json")),
                    "instinkt": str(instinkt.model_dump(mode="json")),
                    "extra": "ignore this non-canonical key",
                },
            }

        engine._call_cycle_json = fake_call_cycle_json  # type: ignore[method-assign]
        ego = engine._llm_ego_resultant(
            scenario=scenario,
            profile="I>R>E",
            weights={"racio": 0.4, "emocio": 0.2, "instinkt": 1.0},
            racio=racio,
            emocio=emocio,
            instinkt=instinkt,
            acceptance=acceptance,
            use_memory=False,
            provider=ProviderSelection(provider_mode="deterministic", use_llm=False),
            diagnostics={"llm_calls": []},
        )

        self.assertEqual(set(ego.hidden_signal_sources), {"racio", "emocio", "instinkt"})
        for reason in ego.hidden_signal_sources.values():
            self.assertNotIn("{'mind':", reason)
            self.assertNotIn('"mind":', reason)

    def test_creative_project_requires_emocio_aliveness_signal(self) -> None:
        scenario = next(item for item in matrix.SCENARIOS if item["id"] == "creative_project_obsession")
        only_ego_mentions_project = payload(
            ego={"action_tendency": "protect the creative project because it feels alive"}
        )
        with_emocio_signal = payload(
            emocio={"desired_image": "The creative image feels alive and wants recognition."}
        )

        self.assertIn(
            "creative_project_emocio_true_positive",
            matrix.expected_patterns_missing(scenario, only_ego_mentions_project),
        )
        self.assertNotIn(
            "creative_project_emocio_true_positive",
            matrix.expected_patterns_missing(scenario, with_emocio_signal),
        )

    def test_evaluator_warnings_do_not_inflate_false_negative_count(self) -> None:
        warning_case = minimal_case(
            false_negative_flags={
                "expected_patterns_missing": ["agenda"],
                "relationship_return_missing": False,
                "body_freeze_missing": False,
                "boundary_pressure_missing": False,
                "rationalization_missing": False,
                "quit_job_signature_missing": False,
            },
            false_negative_severity={
                "hard_false_negative": [],
                "soft_false_negative": [],
                "evaluator_warning": ["expected_patterns_missing"],
            },
        )

        summary = matrix.aggregate([warning_case])

        self.assertEqual(summary["false_negative_case_count"], 0)
        self.assertEqual(summary["actionable_failure_case_count"], 0)
        self.assertEqual(summary["evaluator_warning_case_count"], 1)

    def test_profile_leader_distribution_has_no_unknown_in_full_matrix_summary_fixture(self) -> None:
        cases: list[dict[str, Any]] = []
        index = 0
        for scenario in matrix.SCENARIOS:
            for profile in matrix.PROFILES:
                index += 1
                normalized, weights = profile_weights(profile)
                cases.append(
                    minimal_case(
                        case_index=index,
                        scenario_id=scenario["id"],
                        profile_input=profile,
                        profile_normalized=normalized,
                        profile_leader=profile_leader_label(weights),
                    )
                )

        summary = matrix.aggregate(cases)

        self.assertEqual(summary["case_count"], 156)
        for scenario_summary in summary["profile_sensitivity"].values():
            self.assertNotIn("unknown", scenario_summary["profile_leader_distribution"])

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
