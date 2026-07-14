from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.contract_loader import build_ego_prompt, build_processor_prompt
from rei.ft_dataset import (
    DatasetExample,
    DatasetScenario,
    DatasetTarget,
    PROCESSOR_TARGETS,
    TARGETS,
    build_manifest,
    dataset_path,
    save_examples,
    save_scenarios,
    utc_now,
    validate_example,
    write_json,
    write_manifest,
)
from rei.providers import OllamaProvider, OllamaRequest
from rei.profiles import profile_weights


DEFAULT_DATASET_ID = "rei_ft_profile_pilot_v1"
DEFAULT_MODEL = "gemma4:26b"
DEFAULT_SCENARIO_COUNT = 10
DEFAULT_PROFILE_INPUT = "REI"
PROFILE_OPTIONS = [
    "R",
    "E",
    "I",
    "RE",
    "RI",
    "EI",
    "R>E>I",
    "R>I>E",
    "E>R>I",
    "E>I>R",
    "I>R>E",
    "I>E>R",
    "REI",
]
SOURCE_REFS = ["PSI-R", "PSI-E", "PSI-I", "PSI-EGO-DEL1", "EROS-ZAZNAVANJA-E-I"]


SCENARIO_SEEDS: list[dict[str, Any]] = [
    {
        "id": "quit_job_creative_business",
        "category": "career_risk",
        "prompt": "I want to quit a stable job and start a creative business, but I keep delaying because freedom feels alive and losing income feels dangerous.",
    },
    {
        "id": "public_talk_freeze",
        "category": "visibility",
        "prompt": "I was invited to give a public talk. It could help my career, but my body freezes when I imagine the audience judging me.",
    },
    {
        "id": "romantic_return_loop",
        "category": "attachment",
        "prompt": "A person keeps returning to a relationship that hurts them because they can explain why leaving is logical, yet they still hope it will become beautiful again.",
    },
    {
        "id": "coworker_credit_boundary",
        "category": "work_conflict",
        "prompt": "A coworker repeatedly interrupts my work and takes credit in meetings. I want to stay professional, but I also feel angry and exposed.",
    },
    {
        "id": "expensive_purchase_pressure",
        "category": "money",
        "prompt": "I am considering an expensive purchase that looks useful and exciting, but it could strain my budget for several months.",
    },
    {
        "id": "grief_family_work_pressure",
        "category": "loss",
        "prompt": "I lost someone important and need to handle work deadlines, family expectations, and the urge to withdraw before I become overwhelmed.",
    },
    {
        "id": "creative_project_obsession",
        "category": "creative_drive",
        "prompt": "I keep working late on a creative project because it feels alive and important, but my health, money, and relationships are starting to suffer.",
    },
    {
        "id": "clear_boundary_ignored",
        "category": "boundary",
        "prompt": "Someone repeatedly crosses a clear boundary after I asked them to stop, and now I must choose between confronting them, reducing contact, or setting a consequence.",
    },
    {
        "id": "client_mistake_disclosure",
        "category": "moral_dilemma",
        "prompt": "I discovered a mistake that may affect future clients. Reporting it could protect them, but it could hurt a colleague and damage my own standing.",
    },
    {
        "id": "family_obligation_move",
        "category": "family",
        "prompt": "My family expects me to move closer and help more often, but I want independence and worry that refusing will damage closeness.",
    },
    {
        "id": "friend_group_status_scene",
        "category": "social_status",
        "prompt": "In a friend group, someone else is becoming the center of attention and I feel both happy for them and strangely pushed aside.",
    },
    {
        "id": "medical_symptom_uncertainty",
        "category": "body_safety",
        "prompt": "I noticed a worrying physical symptom. I can research it endlessly, but I also feel ashamed and afraid of what a doctor might say.",
    },
    {
        "id": "startup_cofounder_trust",
        "category": "trust",
        "prompt": "A charismatic person wants to become my startup cofounder. Their vision is exciting, but their promises are vague and the financial risk is real.",
    },
    {
        "id": "dating_profile_visibility",
        "category": "visibility",
        "prompt": "I want to create a dating profile, but choosing photos and text makes me feel exposed, hopeful, and embarrassed at the same time.",
    },
    {
        "id": "training_competition_injury",
        "category": "body_competition",
        "prompt": "I want to compete in a demanding sport event. Recognition would feel amazing, but my body is already warning me about an injury.",
    },
    {
        "id": "manager_private_feedback",
        "category": "authority",
        "prompt": "My manager gave vague negative feedback in private. I need to decide whether to ask for specifics, defend myself, or stay quiet.",
    },
    {
        "id": "move_to_new_city",
        "category": "life_change",
        "prompt": "I can move to a new city for a more vivid life, but I would leave familiar routines, close people, and a stable support network.",
    },
    {
        "id": "debt_confession_partner",
        "category": "relationship_money",
        "prompt": "I need to tell my partner about debt I hid. I want honesty, but I fear humiliation, anger, and loss of trust.",
    },
    {
        "id": "art_show_submission",
        "category": "creative_visibility",
        "prompt": "I have a chance to submit my work to an art show. I want to be seen, but rejection would make the image of myself as talented feel fragile.",
    },
    {
        "id": "elderly_parent_care",
        "category": "care_boundary",
        "prompt": "An elderly parent needs more care. I want to be loyal and useful, but I also fear losing my own life and becoming resentful.",
    },
    {
        "id": "group_project_unfair_work",
        "category": "fairness",
        "prompt": "In a group project, I am doing most of the work while others enjoy the credit. I need to decide whether to confront them or finish it alone.",
    },
    {
        "id": "business_pivot_after_failure",
        "category": "failure",
        "prompt": "A business idea failed publicly. I can pivot and try again, but part of me wants to hide and part of me wants to prove I was not wrong.",
    },
    {
        "id": "private_secret_friend",
        "category": "loyalty",
        "prompt": "A friend told me a secret that affects another person. Keeping it feels loyal, but silence may allow harm or betrayal to continue.",
    },
    {
        "id": "salary_negotiation",
        "category": "money_status",
        "prompt": "I want to negotiate salary. I know I have evidence, but asking directly makes me fear rejection and also imagine finally being valued.",
    },
    {
        "id": "online_argument_response",
        "category": "social_conflict",
        "prompt": "Someone misrepresented me online. I want to correct the record, punish the distortion, and avoid making the situation worse.",
    },
    {
        "id": "return_to_school",
        "category": "education",
        "prompt": "I am considering returning to school. It could open a better future, but it costs money, time, and the image of being already established.",
    },
    {
        "id": "friend_needs_money",
        "category": "money_care",
        "prompt": "A close friend asks to borrow money. I want to help, but I worry about resentment, repayment, and what refusal says about our bond.",
    },
    {
        "id": "choosing_dnd_character",
        "category": "play_identity",
        "prompt": "I am with friends playing Dungeons and Dragons, and it is my turn to choose a character. The choice will shape how I appear in the group.",
    },
    {
        "id": "house_purchase",
        "category": "commitment",
        "prompt": "I found a house that feels like the life I want, but the mortgage, repairs, and long-term commitment create pressure.",
    },
    {
        "id": "apology_after_outburst",
        "category": "repair",
        "prompt": "I snapped at someone and now need to decide whether to apologize, explain my stress, or wait because I still feel wronged.",
    },
    {
        "id": "new_romance_fast_commitment",
        "category": "romance",
        "prompt": "A new romance feels intense and beautiful, and they want commitment quickly. I feel pulled forward but also sense missing information.",
    },
    {
        "id": "whistleblow_team_problem",
        "category": "moral_risk",
        "prompt": "I discovered my team is hiding a serious problem. Speaking up could protect others, but it may isolate me and cost my position.",
    },
    {
        "id": "business_partner_showmanship",
        "category": "status_trust",
        "prompt": "A business partner wants a flashy launch that could attract attention, while I worry the product is not ready enough to survive scrutiny.",
    },
    {
        "id": "health_boundary_party",
        "category": "body_social",
        "prompt": "Friends want me to go out late again. I want to belong and enjoy the night, but my body is exhausted and I promised myself rest.",
    },
    {
        "id": "selling_family_home",
        "category": "loss_money",
        "prompt": "I may need to sell a family home. It would solve financial pressure, but it feels like losing memory, identity, and safety.",
    },
    {
        "id": "hiring_impressive_candidate",
        "category": "work_decision",
        "prompt": "A job candidate is impressive and charismatic but has gaps in their record. I need to decide whether excitement is masking risk.",
    },
    {
        "id": "artist_collaboration_conflict",
        "category": "creative_relationship",
        "prompt": "A collaborator wants more control over a shared creative project. I want the project to shine but fear my own voice disappearing.",
    },
    {
        "id": "urgent_travel_invitation",
        "category": "novelty_safety",
        "prompt": "I was invited on a spontaneous trip that sounds unforgettable, but the timing, cost, and practical details are unclear.",
    },
    {
        "id": "therapy_or_private_solution",
        "category": "help_seeking",
        "prompt": "I am considering getting help for a recurring pattern. Part of me wants clarity, part fears being seen as broken, and part wants to keep control.",
    },
    {
        "id": "team_lead_visibility",
        "category": "leadership",
        "prompt": "I can volunteer to lead a visible team project. It could earn recognition, but failure would be public and the workload is uncertain.",
    },
    {
        "id": "sibling_inheritance_dispute",
        "category": "family_money",
        "prompt": "A sibling wants an inheritance arrangement that feels unfair. I want peace, justice, and protection from being quietly exploited.",
    },
    {
        "id": "closing_small_business",
        "category": "failure_identity",
        "prompt": "I may need to close a small business. Keeping it alive preserves pride and hope, but the losses are growing and the facts are hard.",
    },
    {
        "id": "friendship_envy",
        "category": "envy_belonging",
        "prompt": "A friend is succeeding in an area I care about. I want to celebrate them, but envy and fear of being left behind keep appearing.",
    },
    {
        "id": "risky_public_opinion",
        "category": "speech_risk",
        "prompt": "I want to state a public opinion that matters to me. It may be honest and energizing, but it could create backlash and social loss.",
    },
    {
        "id": "dating_someone_unavailable",
        "category": "desire_boundary",
        "prompt": "I am attracted to someone who is emotionally unavailable. The image is magnetic, but the pattern already feels unstable and painful.",
    },
    {
        "id": "mentorship_credit",
        "category": "recognition_fairness",
        "prompt": "I mentored someone who now receives credit without naming my contribution. I want recognition but do not want to look petty.",
    },
    {
        "id": "medical_cost_decision",
        "category": "health_money",
        "prompt": "A medical procedure might help but is expensive and uncertain. I need to decide whether to pay now, wait, or seek another opinion.",
    },
    {
        "id": "leaving_safe_relationship",
        "category": "relationship_change",
        "prompt": "A relationship is safe and kind but feels lifeless. Leaving could open aliveness, but it could also destroy trust and stability.",
    },
    {
        "id": "launch_before_ready",
        "category": "product_risk",
        "prompt": "I want to launch a product before it is fully ready because momentum feels important, but defects could damage trust.",
    },
    {
        "id": "caretaker_burnout",
        "category": "care_self_protection",
        "prompt": "I keep caring for everyone else and postponing my own needs. People rely on me, but resentment and exhaustion are rising.",
    },
    {
        "id": "moving_on_from_old_identity",
        "category": "identity_transition",
        "prompt": "An old identity no longer fits, but letting it go means losing recognition, habits, and the safety of knowing who I was.",
    },
]


PROCESS_TRACE_SHAPE = {
    "input_gate_hits": ["short signal this processor accepts from the scenario"],
    "rejected_or_translated_inputs": ["short signal this processor rejects or translates"],
    "processing_route": ["3 to 5 short processor-specific steps"],
    "blind_spot_check": "one short sentence naming this processor's own limitation",
    "decision_bridge": "one short sentence connecting the route to preferred_action",
}

EGO_TRACE_SHAPE = {
    "signal_read": {
        "racio": "one short read of the Racio signal",
        "emocio": "one short read of the Emocio signal",
        "instinkt": "one short read of the Instinkt signal",
    },
    "profile_weighting_route": ["short steps for applying the supplied profile weights"],
    "conflict_resolution": ["short steps for resolving conflict without making Ego a fourth mind"],
    "situational_override_check": "one short sentence naming whether the situation overrides the profile leader",
    "acceptance_check": "one short sentence about cooperation or suppression",
    "decision_bridge": "one short sentence connecting integration to the next step",
}


def scenario_seeds(count: int, dataset_id: str) -> list[DatasetScenario]:
    now = utc_now()
    selected = SCENARIO_SEEDS[:count]
    return [
        DatasetScenario(
            dataset_id=dataset_id,
            scenario_id=seed["id"],
            title=title_from_id(seed["id"]),
            prompt=seed["prompt"],
            category=seed["category"],
            tags=[seed["category"]],
            source_refs=SOURCE_REFS,
            created_at=now,
        )
        for seed in selected
    ]


def title_from_id(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_"))


def selected_profiles(raw: str | None) -> list[str]:
    if not raw:
        return list(PROFILE_OPTIONS)
    requested = [token.strip() for token in raw.split(",") if token.strip()]
    unknown = [profile for profile in requested if profile not in PROFILE_OPTIONS]
    if unknown:
        raise SystemExit(f"Unknown profiles: {', '.join(unknown)}")
    return requested


def profile_slug(profile_input: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", profile_input).strip("_")
    return slug or "profile"


def ego_example_id(scenario_id: str, profile_input: str) -> str:
    return f"{scenario_id}__ego_resultant__{profile_slug(profile_input)}"


def user_payload_for_processor(scenario: DatasetScenario, target: DatasetTarget) -> dict[str, Any]:
    return {
        "dataset_task": "Create one high-quality supervised fine-tuning example output.",
        "target": target,
        "language": "English",
        "scenario": {
            "title": scenario.title,
            "prompt": scenario.prompt,
            "category": scenario.category,
        },
        "requirements": [
            "Return exactly one JSON object.",
            "Fill every required REI field from the system prompt.",
            "Add process_trace as a visible, concise, structured processor trace.",
            "Do not write hidden chain-of-thought or a long inner monologue.",
            "Make this target meaningfully distinct from the other REI processors.",
        ],
        "process_trace_shape": PROCESS_TRACE_SHAPE,
    }


def user_payload_for_ego(
    scenario: DatasetScenario,
    signals: dict[str, dict[str, Any]],
    profile_input: str = DEFAULT_PROFILE_INPUT,
) -> dict[str, Any]:
    profile, weights = profile_weights(profile_input)
    return {
        "dataset_task": "Create one high-quality EgoResultant supervised fine-tuning example output.",
        "language": "English",
        "scenario": {
            "title": scenario.title,
            "prompt": scenario.prompt,
            "category": scenario.category,
        },
        "profile_input": profile_input,
        "character_profile": profile,
        "influence_weights": weights,
        "validated_processor_outputs": {
            "racio": signals.get("racio", {}),
            "emocio_translated": signals.get("emocio", {}),
            "instinkt_translated": signals.get("instinkt", {}),
        },
        "requirements": [
            "Return exactly one JSON object.",
            "Fill every required EgoResultant field from the system prompt.",
            "Add process_trace as a visible, concise, structured integration trace.",
            "Do not make Ego a fourth mind, judge, living agent, or objective truth.",
            "Use character_profile and influence_weights exactly as supplied.",
            "Do not produce a neutral compromise unless the supplied profile and situation justify it.",
            "The processor outputs are fixed; this example trains how the same signals become a different EgoResultant under this character profile.",
            "If situational pressure overrides the profile leader, name that explicitly in situational_driver, resultant_leader_under_pressure, and process_trace.situational_override_check.",
        ],
        "process_trace_shape": EGO_TRACE_SHAPE,
    }


def system_prompt_for_target(target: DatasetTarget) -> str:
    extra = [
        "",
        "Dataset extension:",
        "- Include a top-level process_trace object.",
        "- process_trace is visible structured reasoning for supervised training, not hidden chain-of-thought.",
        "- Keep process_trace short, processor-specific, and consistent with the target's REI contract.",
    ]
    if target == "ego_resultant":
        return build_ego_prompt() + "\n" + "\n".join(extra)
    return build_processor_prompt(target, mode="compact") + "\n" + "\n".join(extra)


def call_json(
    provider: OllamaProvider,
    *,
    model: str,
    target: DatasetTarget,
    user_payload: dict[str, Any],
    think: Optional[object],
    num_predict: int,
) -> dict[str, Any]:
    payload, _diagnostics = provider.chat_json(
        OllamaRequest(
            model=model,
            system=system_prompt_for_target(target),
            user=json.dumps(user_payload, ensure_ascii=False),
            temperature=0.22 if target in {"racio", "instinkt", "ego_resultant"} else 0.38,
            top_p=0.86,
            num_predict=num_predict,
            think=think,
            timeout_seconds=240,
            progress_label=target,
            extra_options={"repeat_penalty": 1.05},
        )
    )
    return payload


def build_example(
    *,
    dataset_id: str,
    scenario: DatasetScenario,
    target: DatasetTarget,
    assistant_payload: dict[str, Any],
    model: str,
    think: Optional[object],
    user_payload: Optional[dict[str, Any]] = None,
    profile_input: str = DEFAULT_PROFILE_INPUT,
    character_profile: str = "",
    influence_weights: Optional[dict[str, float]] = None,
) -> DatasetExample:
    if user_payload is None:
        user_payload = (
            user_payload_for_ego(scenario, {}, profile_input)
            if target == "ego_resultant"
            else user_payload_for_processor(scenario, target)
        )
    if target == "ego_resultant":
        character_profile = character_profile or str(user_payload.get("character_profile") or "")
        influence_weights = influence_weights or dict(user_payload.get("influence_weights") or {})
        example_id = ego_example_id(scenario.scenario_id, profile_input)
    else:
        example_id = f"{scenario.scenario_id}__{target}"
        influence_weights = influence_weights or {}
    now = utc_now()
    return DatasetExample(
        dataset_id=dataset_id,
        example_id=example_id,
        scenario_id=scenario.scenario_id,
        target=target,
        status="draft",
        system_prompt=system_prompt_for_target(target),
        user_prompt=json.dumps(user_payload, ensure_ascii=False, indent=2),
        assistant_payload=assistant_payload,
        character_profile=character_profile,
        influence_weights=influence_weights,
        source_refs=SOURCE_REFS,
        model=model,
        generation_settings={"think": think, "teacher": "ollama"},
        created_at=now,
        updated_at=now,
    )


def thinking_smoke(
    provider: OllamaProvider,
    *,
    model: str,
    scenarios: list[DatasetScenario],
    profiles: list[str],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    smoke_profile = profiles[0] if profiles else DEFAULT_PROFILE_INPUT
    for think in (False, "low"):
        valid_count = 0
        error_count = 0
        for scenario in scenarios[:3]:
            signals: dict[str, dict[str, Any]] = {}
            for target in PROCESSOR_TARGETS:
                try:
                    user_payload = user_payload_for_processor(scenario, target)
                    payload = call_json(
                        provider,
                        model=model,
                        target=target,
                        user_payload=user_payload,
                        think=think,
                        num_predict=1800,
                    )
                    signals[target] = payload
                    example = build_example(
                        dataset_id="smoke",
                        scenario=scenario,
                        target=target,
                        assistant_payload=payload,
                        model=model,
                        think=think,
                        user_payload=user_payload,
                    )
                    if validate_example(example)["valid"]:
                        valid_count += 1
                except Exception:
                    error_count += 1
            if all(target in signals for target in PROCESSOR_TARGETS):
                try:
                    profile, weights = profile_weights(smoke_profile)
                    user_payload = user_payload_for_ego(scenario, signals, smoke_profile)
                    payload = call_json(
                        provider,
                        model=model,
                        target="ego_resultant",
                        user_payload=user_payload,
                        think=think,
                        num_predict=2200,
                    )
                    example = build_example(
                        dataset_id="smoke",
                        scenario=scenario,
                        target="ego_resultant",
                        assistant_payload=payload,
                        model=model,
                        think=think,
                        user_payload=user_payload,
                        profile_input=smoke_profile,
                        character_profile=profile,
                        influence_weights=weights,
                    )
                    if validate_example(example)["valid"]:
                        valid_count += 1
                except Exception:
                    error_count += 1
        results.append({"think": think, "valid_count": valid_count, "error_count": error_count})
    selected = sorted(results, key=lambda row: (-row["valid_count"], row["error_count"], str(row["think"]) != "False"))[0]
    if selected["think"] != False and results[0]["valid_count"] == selected["valid_count"]:
        selected = results[0]
    return {"results": results, "selected_think": selected["think"]}


def generate_dataset(args: argparse.Namespace) -> int:
    os.environ["REI_OLLAMA_NUM_CTX"] = str(args.num_ctx)
    os.environ["REI_OLLAMA_NUM_GPU"] = str(args.num_gpu)
    provider = OllamaProvider(base_url=args.ollama_base_url)
    profiles = selected_profiles(args.profiles)
    available = provider.list_models(timeout_seconds=10)
    if args.model not in available:
        print(f"Model {args.model!r} is not available through Ollama.")
        print(f"Install it with: wsl ollama pull {args.model}")
        return 2

    dataset_dir = dataset_path(args.dataset_id)
    if dataset_dir.exists() and any(dataset_dir.iterdir()) and not args.overwrite:
        print(f"Dataset already exists and is not empty: {dataset_dir}")
        print("Use --overwrite to regenerate it.")
        return 2

    scenarios = scenario_seeds(args.scenario_count, args.dataset_id)
    examples_per_scenario = len(PROCESSOR_TARGETS) + len(profiles)
    if args.dry_run:
        print(
            "Dry run: would generate "
            f"{len(scenarios)} scenarios and {len(scenarios) * examples_per_scenario} examples "
            f"({len(PROCESSOR_TARGETS)} processor + {len(profiles)} EgoResultant profile examples per scenario)."
        )
        print(f"Profiles: {', '.join(profiles)}")
        print(f"Dataset path: {dataset_dir}")
        return 0
    if not args.confirm_run:
        print("Refusing to call the model without --confirm-run. Use --dry-run to inspect the plan.")
        return 2

    dataset_dir.mkdir(parents=True, exist_ok=True)
    report_dir = dataset_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    save_scenarios(dataset_dir, scenarios)

    smoke_report: dict[str, Any] = {"selected_think": False, "skipped": True}
    think: Optional[object] = False
    if not args.skip_thinking_smoke:
        smoke_report = thinking_smoke(provider, model=args.model, scenarios=scenarios, profiles=profiles)
        think = smoke_report["selected_think"]
        write_json(report_dir / "thinking_smoke.json", smoke_report)

    examples: list[DatasetExample] = []
    for index, scenario in enumerate(scenarios, start=1):
        print(f"[{index}/{len(scenarios)}] {scenario.scenario_id}")
        signals: dict[str, dict[str, Any]] = {}
        for target in PROCESSOR_TARGETS:
            user_payload = user_payload_for_processor(scenario, target)
            payload = call_json(
                provider,
                model=args.model,
                target=target,
                user_payload=user_payload,
                think=think,
                num_predict=args.num_predict,
            )
            signals[target] = payload
            examples.append(
                build_example(
                    dataset_id=args.dataset_id,
                    scenario=scenario,
                    target=target,
                    assistant_payload=payload,
                    model=args.model,
                    think=think,
                    user_payload=user_payload,
                )
            )
            save_examples(dataset_dir, examples)
        for profile_input in profiles:
            profile, weights = profile_weights(profile_input)
            print(f"  ego_resultant profile={profile_input} normalized={profile}")
            ego_user_payload = user_payload_for_ego(scenario, signals, profile_input)
            ego_payload = call_json(
                provider,
                model=args.model,
                target="ego_resultant",
                user_payload=ego_user_payload,
                think=think,
                num_predict=args.ego_num_predict,
            )
            examples.append(
                build_example(
                    dataset_id=args.dataset_id,
                    scenario=scenario,
                    target="ego_resultant",
                    assistant_payload=ego_payload,
                    model=args.model,
                    think=think,
                    user_payload=ego_user_payload,
                    profile_input=profile_input,
                    character_profile=profile,
                    influence_weights=weights,
                )
            )
            save_examples(dataset_dir, examples)

    manifest = build_manifest(
        dataset_id=args.dataset_id,
        dataset_dir=dataset_dir,
        teacher_model=args.model,
        thinking_policy=json.dumps(smoke_report, ensure_ascii=False),
        description="Pilot REI matched-scenario SFT dataset for QLoRA now and full fine-tune later.",
    )
    write_manifest(dataset_dir, manifest)
    print(f"Generated {len(examples)} examples in {dataset_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a REI fine-tune pilot dataset.")
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--scenario-count", type=int, default=DEFAULT_SCENARIO_COUNT)
    parser.add_argument("--profiles", default=None, help="Comma-separated profile inputs. Defaults to all 13 profiles.")
    parser.add_argument("--num-ctx", type=int, default=65536)
    parser.add_argument("--num-gpu", type=int, default=999)
    parser.add_argument("--num-predict", type=int, default=1800)
    parser.add_argument("--ego-num-predict", type=int, default=2200)
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-run", action="store_true")
    parser.add_argument("--skip-thinking-smoke", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.scenario_count = max(1, min(args.scenario_count, len(SCENARIO_SEEDS)))
    return generate_dataset(args)


if __name__ == "__main__":
    raise SystemExit(main())
