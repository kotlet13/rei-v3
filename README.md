# REI v3 — Native Composition

REI v3 now runs the native-modality architecture described in
`Docs/architecture/REI_NATIVE_COMPOSITION_ARCHITECTURE.md`. Racio, Emocio, and
Instinkt form independent native conclusions before communication or character
governance. Racio remains the only conscious decision type; Ego is an
append-only composition across cycles, not a fourth agent.

See `CURRENT.md` for the exact active boundary and
`Docs/evals/rei_native_architecture_acceptance_2026-07-13.md` for the final B14
verification record.

## Active runtime

- backend package: `app/backend/rei/`
- GUI workbench: `app/gui/`
- deterministic cycle: `scripts/run_rei_native_cycle.py`
- frozen-bundle 12 × 13 matrix: `scripts/run_rei_native_profile_matrix.py`
- canonical architecture data: `knowledge/canon_v2/`
- active tests: `tests/rei/` plus archive/cutover guards in `tests/`

Run one reproducible cycle:

```powershell
python scripts/run_rei_native_cycle.py `
  --runs-root output/runs `
  --ego-traces-root output/ego_traces
```

Run the canonical profile matrix:

```powershell
python scripts/run_rei_native_profile_matrix.py `
  --output output/reports/rei_native_profile_matrix.json
```

Run the active workbench:

```powershell
python -m uvicorn app.gui.server:app --host 127.0.0.1 --port 8765
```

The default cycle and GUI paths are deterministic and do not silently call a
model, renderer, image generator, or training pipeline. Model-backed adapters
must declare exact model provenance, revision, seed, and call records.

## Verification

Use a repository-local temporary root on this Windows machine because the
global pytest temp directory may not be readable:

```powershell
$base = Join-Path (Resolve-Path tmp) ("pytest-" + [guid]::NewGuid())
app\backend\.venv\Scripts\python.exe -m pytest -q --basetemp $base
```

The cutover also has permanent guards for archive hashes, archive isolation,
removed legacy entrypoints, and absence of transitional package references.

## Frozen legacy baseline

The former textual three-LLM `EgoResultant` runtime, its 156-case Granite
profile matrix, prompt/dataset GUI, dataset tooling, and duplicate reference
tests are preserved at:

```text
archive/rei_v3_text_llm_baseline_2026-07-13/
```

That snapshot is sourced from commit
`05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`, carries a complete SHA-256
inventory, and is not imported by active code. Historical datasets and eval
reports may remain in the repository as research records; they are not active
runtime or automatic training inputs.

## Scope and safety

This software is a research simulator. It does not diagnose people, determine
the character of real persons, or treat its outputs as objective psychological
truth. The current upgrade does not train QLoRA or diffusion adapters and does
not turn Ego or Življenje into an autonomous agent.
