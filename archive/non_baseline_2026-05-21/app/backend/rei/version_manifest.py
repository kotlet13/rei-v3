from __future__ import annotations

from typing import Any


PROJECT_NAME = "REI v3"
PROJECT_VERSION = "0.4.0"
ACTIVE_STACK_ID = "rei-v3-observation-stack"
ACTIVE_STACK_LABEL = "REI v3 Observation Framework"
ACTIVE_LOGIC_CONTRACT = "rei-logic-v1"
ACTIVE_MOTORICS_CONTRACT = "rei-motorics-v1"
PLAYGROUND_API_CONTRACT = "playground-observation-v1"
REI_CYCLE_ENGINE_CONTRACT = "rei-cycle-v1"
CANONICAL_PROCESSOR_CONTRACT = "rei-canon-contracts-v1"
PROFILE_MATRIX_BASELINE_CONTRACT = "rei-profile-matrix-156-v1"
FRONTEND_APP_VERSION = "0.3.0"
LEGACY_SIMULATION_API_CONTRACT = "legacy-simulation-api-v0"


RUNTIME_MANIFEST: dict[str, Any] = {
    "project": {
        "name": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "active_stack_id": ACTIVE_STACK_ID,
        "active_stack_label": ACTIVE_STACK_LABEL,
    },
    "active_logic": {
        "id": "rei-v3-current-logic",
        "version": PROJECT_VERSION,
        "contract_id": ACTIVE_LOGIC_CONTRACT,
        "definition": (
            "Current reasoning contract: canonical Racio, Emocio, Instinkt, "
            "and EgoResultant meaning; profile weighting; acceptance assessment; "
            "runtime JSON shapes; and prompt construction."
        ),
        "components": [
            {
                "id": "canonical-processor-contracts",
                "path": "knowledge/canon/processor_contracts.json",
                "schema_version": CANONICAL_PROCESSOR_CONTRACT,
                "role": "Canonical R/E/I and EgoResultant definitions and required output keys.",
            },
            {
                "id": "prompt-contract-loader",
                "path": "app/backend/rei/contract_loader.py",
                "role": "Builds compact runtime prompts, full audit prompts, and canonical defaults from the contract pack.",
            },
            {
                "id": "runtime-prompts",
                "path": "app/backend/rei/prompts.py",
                "role": "Exports the active processor and EgoResultant system prompts used by the engine.",
            },
            {
                "id": "runtime-output-models",
                "path": "app/backend/rei/models.py",
                "role": "Defines REISignal, RacioSignal, EmocioSignal, InstinktSignal, EgoResultant, and REICycleResponse shapes.",
            },
            {
                "id": "profile-weighting",
                "path": "app/backend/rei/profiles.py",
                "role": "Normalizes public REI profiles and turns them into processor influence weights.",
            },
            {
                "id": "acceptance-assessment",
                "path": "app/backend/rei/acceptance.py",
                "role": "Derives acceptance, conflict, sabotage, and task-delegation fields from the three processor signals.",
            },
        ],
        "boundaries": [
            "Logic defines what Racio, Emocio, Instinkt, EgoResultant, profile weights, and acceptance fields mean.",
            "Logic does not define HTTP routes, streaming, saved observations, UI panels, or provider transport.",
            "Playground option scoring and trialogue display are presentation heuristics, not canonical REI logic.",
            "Legacy simulation endpoints and archived UI files must not be treated as current logic.",
        ],
    },
    "active_motorics": {
        "id": "rei-v3-current-motorics",
        "version": PROJECT_VERSION,
        "contract_id": ACTIVE_MOTORICS_CONTRACT,
        "definition": (
            "Current execution mechanism: the concrete path that turns a scenario "
            "and selected profile into processor calls, acceptance, EgoResultant, "
            "playground response, stream events, saved observations, and UI state."
        ),
        "components": [
            {
                "id": "cycle-entrypoint",
                "path": "app/backend/rei/engine.py",
                "entrypoint": "rei.engine.ReiEngine.run_rei_cycle",
                "role": "Runs the active REI cycle and returns REICycleResponse.",
            },
            {
                "id": "processor-call-motor",
                "path": "app/backend/rei/engine.py",
                "entrypoint": "rei.engine.ReiEngine._llm_rei_signal",
                "role": "Builds per-processor user payloads, calls the selected provider, validates JSON, and coerces signals.",
            },
            {
                "id": "ego-resultant-call-motor",
                "path": "app/backend/rei/engine.py",
                "entrypoint": "rei.engine.ReiEngine._llm_ego_resultant",
                "role": "Builds the EgoResultant payload from R/E/I signals, acceptance, profile, and weights.",
            },
            {
                "id": "provider-transport",
                "path": "app/backend/rei/providers.py",
                "role": "Sends chat JSON requests to Ollama or LM Studio and receives raw provider responses.",
            },
            {
                "id": "playground-adapter",
                "path": "app/backend/rei/playground.py",
                "role": "Wraps the engine for current UI workflows, streaming, option display, profile comparison, and saved observations.",
            },
            {
                "id": "fastapi-current-routes",
                "path": "app/backend/main.py",
                "role": "Exposes /api/v1/version and /api/v1/playground routes for the active UI.",
            },
            {
                "id": "frontend-runtime",
                "path": "app/frontend/src/App.tsx",
                "role": "Current browser UI that consumes the playground contract.",
            },
        ],
        "execution_order": [
            "Normalize selected profile into canonical profile and influence weights.",
            "Build the scenario payload from title, situation, decision options, and stakes.",
            "Run Racio, Emocio, and Instinkt provider calls when enabled; otherwise use deterministic fallbacks.",
            "Validate and coerce processor JSON into runtime signal models.",
            "Assess acceptance and task delegation from the three processor signals.",
            "Build a fallback EgoResultant, then replace it with provider EgoResultant when enabled and valid.",
            "Return REICycleResponse through the playground adapter.",
            "Derive UI option evaluations, trialogue display, profile comparisons, and optional observation history.",
        ],
        "boundaries": [
            "Motorics defines how the latest logic is executed and transported.",
            "Motorics does not redefine processor meaning; it must use the active logic contract.",
            "The active UI must enter through /api/v1/playground and /api/v1/version.",
            "Deprecated /api/v1/simulate and /api/v1/rei-cycle routes are compatibility surfaces only.",
        ],
    },
    "baseline_evaluation": {
        "id": "rei-profile-matrix-156",
        "version": "1.0.0",
        "contract_id": PROFILE_MATRIX_BASELINE_CONTRACT,
        "status": "baseline",
        "script": "scripts/run_rei_profile_matrix.py",
        "entrypoint": "scripts.run_rei_profile_matrix.main",
        "engine_entrypoint": "rei.engine.ReiEngine.run_rei_cycle",
        "docs_summary_dir": "Docs/evals",
        "case_count": 156,
        "profile_count": 13,
        "scenario_count": 12,
        "default_provider": "ollama",
        "default_model": "granite4.1:30b",
        "default_num_ctx": 65536,
        "default_num_gpu": 999,
        "default_command": (
            "python scripts/run_rei_profile_matrix.py --model granite4.1:30b "
            "--num-ctx 65536 --num-gpu 999"
        ),
        "outputs": [
            "output/reports/rei_profile_matrix/{run_id}/run.json",
            "output/reports/rei_profile_matrix/{run_id}/cases.json",
            "output/reports/rei_profile_matrix/{run_id}/cases.jsonl",
            "output/reports/rei_profile_matrix/{run_id}/summary.json",
            "output/reports/rei_profile_matrix/{run_id}/summary.md",
            "Docs/evals/rei_profile_matrix_summary_{YYYY-MM-DD}.md",
        ],
        "latest_known_full_run": {
            "run_id": "20260519_153731",
            "output_dir": "output/reports/rei_profile_matrix/20260519_153731_granite4_1_30b_64k_gpu999_postfix",
            "summary": "output/reports/rei_profile_matrix/20260519_153731_granite4_1_30b_64k_gpu999_postfix/summary.md",
            "summary_json": "output/reports/rei_profile_matrix/20260519_153731_granite4_1_30b_64k_gpu999_postfix/summary.json",
            "case_count": 156,
            "model": "granite4.1:30b",
            "num_ctx": 65536,
            "num_gpu": 999,
        },
        "notes": [
            "This is the baseline evaluation script for profile/character sensitivity across the active run_rei_cycle motor.",
            "Default full run is 13 profiles x 12 scenarios = 156 cases.",
            "Filtered or smoke runs can also write into Docs/evals; do not treat the newest dated Docs/evals file as a full 156 baseline unless its Cases field is 156.",
        ],
    },
    "active": {
        "engine": {
            "id": "rei-cycle-engine",
            "version": PROJECT_VERSION,
            "contract_id": REI_CYCLE_ENGINE_CONTRACT,
            "path": "app/backend/rei/engine.py",
            "entrypoint": "rei.engine.ReiEngine.run_rei_cycle",
            "notes": "Current active Racio / Emocio / Instinkt / EgoResultant cycle engine.",
        },
        "playground_api": {
            "id": "playground-api",
            "version": "1.0.0",
            "contract_id": PLAYGROUND_API_CONTRACT,
            "base_path": "/api/v1/playground",
            "path": "app/backend/rei/playground.py",
            "uses_engine_contract": REI_CYCLE_ENGINE_CONTRACT,
            "endpoints": [
                "GET /api/v1/playground/profiles",
                "POST /api/v1/playground/run",
                "POST /api/v1/playground/run-stream",
                "GET /api/v1/playground/observations",
                "GET /api/v1/playground/observations/{observation_id}",
            ],
            "notes": "Current active observation, profile comparison, stream, and saved-history API.",
        },
        "frontend": {
            "id": "observation-framework-ui",
            "version": FRONTEND_APP_VERSION,
            "contract_id": PLAYGROUND_API_CONTRACT,
            "path": "app/frontend/src/App.tsx",
            "api_client_path": "app/frontend/src/api.ts",
            "consumes_api_contract": PLAYGROUND_API_CONTRACT,
            "notes": "Current active UI. Archived UI variants are not wired to the backend.",
        },
    },
    "legacy": [
        {
            "id": "legacy-fastapi-simulation-endpoints",
            "path": "app/backend/main.py",
            "status": "deprecated-compatibility",
            "contract_id": LEGACY_SIMULATION_API_CONTRACT,
            "endpoints": [
                "GET /api/v1/minds",
                "GET /api/v1/characters",
                "POST /api/v1/simulate",
                "POST /api/v1/rei-cycle",
            ],
            "notes": "Kept for old tests and archived UI only. The active UI should use /api/v1/playground and /api/v1/version.",
        },
        {
            "id": "legacy-ui-2026-05-19",
            "path": "archive/legacy-ui-2026-05-19",
            "status": "archived",
            "notes": "Older frontend kept for reference only.",
        },
        {
            "id": "rei-v2-engine",
            "path": "prejšnji poskusi/rei_v2/rei_emulator.py",
            "status": "archived",
            "notes": "Earlier emulator lineage, not connected to the active API.",
        },
        {
            "id": "next-upgrade-patch-pack",
            "path": "rei_v3_next_upgrade_patch_pack",
            "status": "reference",
            "notes": "Upgrade/reference pack and duplicate contract tests, not the active runtime package.",
        },
    ],
    "last_verified": {
        "date": "2026-05-21",
        "tests": "python -m pytest -q",
        "frontend_build": "wsl.exe --cd /mnt/c/Users/Kotlet/Codex/github/rei-v3/app/frontend npm run build",
        "latest_llm_matrix_summary": "Docs/evals/rei_profile_matrix_summary_2026-05-19.md",
    },
}


def runtime_manifest() -> dict[str, Any]:
    return RUNTIME_MANIFEST
