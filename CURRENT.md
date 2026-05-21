# Current Baseline

The project is now organized around one active baseline entrypoint:

```powershell
python scripts\run_rei_profile_matrix.py --model granite4.1:30b --num-ctx 65536 --num-gpu 999
```

This is the current source of truth for evaluating REI-v3 logic and motorics.

## Active Baseline

- id: `rei-profile-matrix-156`
- contract: `rei-profile-matrix-156-v1`
- script: `scripts/run_rei_profile_matrix.py`
- engine entrypoint under test: `ReiEngine.run_rei_cycle`
- provider/model: `ollama` / `granite4.1:30b`
- Ollama options: `num_ctx=65536`, `num_gpu=999`
- matrix: 13 profiles x 12 scenarios = 156 cases
- docs summary output: `Docs/evals/rei_profile_matrix_summary_{YYYY-MM-DD}.md`

## Active Dependency Boundary

The active baseline keeps only the code needed by `scripts/run_rei_profile_matrix.py` and its support tests:

- `app/backend/rei/acceptance.py`
- `app/backend/rei/contract_loader.py`
- `app/backend/rei/engine.py`
- `app/backend/rei/json_utils.py`
- `app/backend/rei/knowledge.py`
- `app/backend/rei/models.py`
- `app/backend/rei/normalization.py`
- `app/backend/rei/processor_contracts.py`
- `app/backend/rei/processor_eval.py`
- `app/backend/rei/profiles.py`
- `app/backend/rei/prompts.py`
- `app/backend/rei/providers.py`
- `knowledge/`
- `Docs/evals/`

## Archived Non-Baseline Surfaces

Non-baseline UI/API/runner surfaces were moved to:

- `archive/non_baseline_2026-05-21/`

That archive includes the browser UI, FastAPI entrypoint, playground adapter, runtime manifest API, old matrix/probe runners, weighted-synthesis audit helpers, old tests for those surfaces, old API/UI specs, old REI v2 material, and prior upgrade/reference packs.

## Baseline Run

Use explicit Ollama GPU offload:

```powershell
$env:REI_OLLAMA_NUM_CTX = "65536"
$env:REI_OLLAMA_NUM_GPU = "999"
python scripts\run_rei_profile_matrix.py --model granite4.1:30b --num-ctx 65536 --num-gpu 999
```

The script writes full run artifacts under:

- `output/reports/rei_profile_matrix/{run_id}/`

It also copies the markdown summary into:

- `Docs/evals/rei_profile_matrix_summary_{YYYY-MM-DD}.md`

Important: filtered or smoke runs can also write into `Docs/evals`. Treat a docs summary as the 156-case baseline only when its `Cases` field is `156`.

Latest known full 156-case run:

- `output/reports/rei_profile_matrix/20260519_153731_granite4_1_30b_64k_gpu999_postfix/summary.md`

## Verification

Last local structural verification on 2026-05-21:

- `python -m pytest -q`
