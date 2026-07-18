# Current Project State

## Executive state - 2026-07-18

- Native REI architecture: stable.
- Global research quality: still blocked.
- Gemma V3 technical contract: accepted.
- P3: `1/1` technical confirmation.
- G3C: `16/16` successful calls; retry/fallback `0/0`.
- Action family: `13/16`.
- Exact action subtype: `11/16`.
- Unique option mapping: `12/12`.
- Required abstention: `4/4`.
- Direct motive coverage: `12/14`.
- Unsupported motive overclaims: `2`.
- Bilingual action family: `8/8`.
- Bilingual action subtype: `7/8`.
- Gemma status: shadow-ready, not promoted.
- Default active interpreter: deterministic.
- Authority: no governance, conscious-decision, behavior, or MindWorld
  authority.
- Next infrastructure phase: Gemma text shadow integration on a new branch.
- Next research phase: G4 untouched holdout on a separate branch.

## Runtime and authority boundary

`app.backend.rei.engine.ReiNativeEngine` remains the active runtime and uses
the deterministic Racio interpreter and deterministic native providers by
default. The Gemma V3 provider is experimental and inactive unless a future,
separately approved shadow integration explicitly opts in.

Gemma output cannot select character authority, create a governance mandate,
commit a conscious decision, resolve a behavior resultant, or update a
MindWorld. G3C is a development rerun of a previously studied corpus, not an
untouched holdout, and supports no generalization claim. G4 remains required
before any active-interpreter promotion can be considered.

## Current open limitations

- Global research quality remains blocked pending untouched validation.
- The official Qwen C3 pair remains `23/32 + 23/32` and was not accepted.
- LongCat visual results remain exploratory and have no native-influence
  authority.
- Instinkt raw-scene understanding remains open.
- Ego untagged semantic-motif understanding remains open.
- Shadow readiness is permission for a later isolated integration phase, not
  runtime or decision authority.

## Research evidence index

Detailed chronology remains in
[`research_log.md`](Docs/evals/research_reset_2026-07/research_log.md). The
current Gemma evidence is recorded in:

- [P3 technical confirmation](Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_v3_p3_confirmation.md)
- [G3C V3 development rerun](Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_v3_g3c.md)
- [G3C integration readiness](Docs/evals/research_reset_2026-07/g3c_integration_readiness.md)
- [Frozen G3 V2 development screen](Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_dev_screen.md)
- [G3A semantic adjudication](Docs/evals/research_reset_2026-07/g3_semantic_adjudication.md)
- [G3B/G3B.1 V3 contract record](Docs/evals/research_reset_2026-07/g3b_epistemic_contract_v3.md)
- [C3 failure audit](Docs/evals/research_reset_2026-07/c3_failure_audit.md)

Frozen reports and evidence are historical records and are not rewritten by
later evaluator or human decisions.

## Active execution boundary

- engine: `app.backend.rei.engine.ReiNativeEngine`
- deterministic cycle runner: `scripts/run_rei_native_cycle.py`
- governance matrix runner: `scripts/run_rei_native_profile_matrix.py`
- GUI server: `app.gui.server:app`
- run artifacts: `output/runs/{run_id}/`
- append-only Ego traces: `output/ego_traces/`
- native tests: `tests/rei/`
- immutable legacy archive:
  `archive/rei_v3_text_llm_baseline_2026-07-13/`

There is no active `rei_next` or `gui_next` package. Active code does not
import the archive.

## Architecture contract

1. Racio, Emocio, and Instinkt receive profile-blind native inputs and conclude
   independently.
2. Emocio's structured visual world and Instinkt's virtual body remain
   authoritative without an optional renderer.
3. Racio sees observable manifestations only; evaluator truth is excluded from
   conscious input.
4. Character governance is ordinal and has no LLM tie-breaker.
5. Governance mandate, Racio-owned conscious decision, and behavior resultant
   remain distinct records.
6. Ego is append-only and has no decision or vote API.
7. Run storage is create-only, content-addressed, manifest-closed, and
   cold-verifiable.

## Deterministic verification

```powershell
python -m pytest -q
python scripts/run_rei_native_cycle.py
python scripts/run_rei_native_profile_matrix.py
```

The profile matrix is 12 frozen native bundles x 13 canonical profiles = 156
rows. It exercises governance and downstream conscious/behavior processing
without rerunning a native processor or contacting a model.

The native cutover and archive rollback record remains
[`rei_native_architecture_acceptance_2026-07-13.md`](Docs/evals/rei_native_architecture_acceptance_2026-07-13.md).
Do not import or modify archived source to implement active behavior.
