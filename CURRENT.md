# Current Project State

## Executive state - 2026-07-19

- Native REI architecture: stable.
- Global research quality: still blocked pending G4 and other untouched
  validations.
- Gemma V3 provider: technically accepted.
- Gemma text shadow backend: implemented.
- S1R real smoke: passed.
- Calls/retries/fallbacks: `2/0/0`.
- E result: full abstention.
- I result: action-only.
- DraftV3/canonicalizer validity: `2/2`.
- Authoritative cycle: unchanged.
- Default active interpreter: deterministic.
- Shadow activation: explicit opt-in only.
- Gemma authority: none over governance, conscious decision, behavior,
  MindWorld, or Ego composition.
- Gemma status: shadow-only, not promoted.
- S1/S1R evidence: cold-verified and receipt-closed.
- Next infrastructure phase after merge: S2 shadow GUI on a new branch.
- Next research phase: G4 untouched holdout on a separate branch.
- Standalone MindWorld updaters were not exercised by the real S1R smoke and
  remain part of later longitudinal acceptance.

## Runtime and authority boundary

`app.backend.rei.engine.ReiNativeEngine` remains the active runtime. It uses
the deterministic Racio interpreter and deterministic native providers by
default. Gemma shadow execution exists only when an explicit dependency and
`gemma4_text_shadow` mode are configured; provider or model availability alone
cannot activate it.

Shadow output is diagnostic only. It cannot select CharacterAuthority or
EffectiveAuthority, create a GovernanceMandate, alter the authoritative
RacioInterpretation, commit a ConsciousDecision, change a RacioSelfNarrative
or BehaviorResultant, participate in Ego composition, or update MindWorld.
Shadow success and bounded failure both leave the authoritative cycle intact.

S1R is a real backend integration smoke, not an untouched holdout. It provides
no generalization claim and no basis for model promotion. G4 remains required
on a separate research branch.

## Current open work

- G4 untouched semantic validation remains required.
- S2 GUI work is not part of the backend integration and requires a new
  infrastructure branch after merge.
- Standalone longitudinal MindWorld updater acceptance remains open.
- LongCat visual results remain exploratory and have no native-influence
  authority.
- Instinkt raw-scene and Ego untagged semantic-motif understanding remain
  open research problems.

## Evidence index

Detailed chronology remains in
[`research_log.md`](Docs/evals/research_reset_2026-07/research_log.md). Current
technical and integration evidence is recorded in:

- [G3C V3 development rerun](Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_v3_g3c.md)
- [G3C integration readiness](Docs/evals/research_reset_2026-07/g3c_integration_readiness.md)
- [S1/S1R reconciliation](Docs/evals/research_reset_2026-07/gemma4_text_shadow_s1_reconciliation.md)
- [S1R post-verification receipt](Docs/evals/research_reset_2026-07/gemma4_text_shadow_s1r_post_verification_receipt.json)
- [Original S1 evidence root](Docs/evals/semantic_lab_v1/s1-gemma4-text-shadow-2026-07-19/)
- [S1R evidence root](Docs/evals/semantic_lab_v1/s1r-gemma4-text-shadow-2026-07-19/)

Frozen reports and evidence remain historical records and are not rewritten by
later evaluator, integration, or human decisions.

## Verification boundary

```powershell
python -m pytest -q
python scripts/run_rei_native_cycle.py
python scripts/run_rei_native_profile_matrix.py
```

The profile matrix is 12 frozen native bundles x 13 canonical profiles = 156
rows. It exercises governance and downstream conscious/behavior processing
without rerunning a native processor or contacting a model.

Active code does not import the immutable archive at
`archive/rei_v3_text_llm_baseline_2026-07-13/`. Run storage remains
create-only, content-addressed, manifest-closed, and cold-verifiable.
