# REI v3 Native Composition v1

**Released:** 2026-07-14

**Status:** accepted integration baseline

**Main merge SHA:** `4e479b96d1ca7194cde50dfec66cf1c12d0b0b1e`

**Release tag:** `rei-v3-native-composition-v1`

**Release tag object:** `97dbcd5aa4c0dd5062beec894b989776b7fdf9ba`

## Scope

This release makes the native-modality, Ego-composition architecture the
active REI v3 baseline:

```text
Racio native
Emocio native
Instinkt native
        ↓
frozen NativeMindBundle
        ↓
ordinal CharacterAuthority
        ↓
GovernanceMandate
        ↓
Racio interpretation and conscious commitment
        ↓
ConsciousDecision
        ↓
BehaviorResultant
        ↓
EgoMeasure → EgoTrace → EgoCompositionSnapshot
```

Racio, Emocio and Instinkt complete profile-blind native processing before
governance. Character authority is ordinal. The governance mandate, conscious
decision and behavior resultant are separate records. Racio is the only
conscious decision type. Ego is append-only composition across cycles and has
no vote or decision API.

The release includes a deterministic cycle runner, a model-free frozen-bundle
12 × 13 governance matrix, an active native-composition GUI, strict provider
and artifact provenance, and model-independent GitHub Actions coverage.

## Integration identity

- pull request: `https://github.com/kotlet13/rei-v3/pull/1`;
- merge mode: merge commit, without squash or rebase;
- merge parents: `07a26401e0b2707a79018efc2fdd7194d3062566` and
  `35172c5beee9fa2619258bacd099b96c9ac854e4`;
- B14 acceptance record:
  `Docs/evals/rei_native_architecture_acceptance_2026-07-13.md`;
- integration addendum:
  `Docs/evals/rei_native_architecture_integration_addendum_2026-07-14.md`.

## Test evidence

Local pre-merge verification:

- complete discoverable suite: 643 passed;
- controlled native/archive/cutover suite: 632 passed;
- deterministic native cycle: all invariants passed, 45 stored artifacts;
- profile matrix: 156 rows, 12 fixtures, 13 profiles and 0 native processor
  executions;
- GUI: Native, Communication, Character and Ego panels rendered;
- debug Communication mobile view: 390 px document at a 390 px viewport;
- browser console: 0 errors and 0 warnings.

Post-merge verification on `main`:

- complete discoverable suite: 643 passed in 25.31 seconds;
- fresh create-only deterministic cycle: all invariants passed and 45 stored
  artifacts;
- profile matrix: 156 rows, 0 native processor executions, matrix hash
  `b7249e1d4b4f7aeccdbb48718c1aaaf96e6ea49ed0d8f64b598ed7781974ee31`;
- GitHub Actions push run `29306858266`: all three jobs succeeded.

CI does not contact Ollama, download a renderer model, run QLoRA or mutate
committed artifacts.

## Rollback anchor

The former textual three-LLM/EgoResultant baseline remains available at the
annotated tag:

```text
rei-v3-text-llm-baseline-2026-07-13
```

The tag object is `ea04d0ef0da3bd3d6036eefbe552731a2083461e` and it
resolves to commit `05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`.

Follow B14 section 14 and create a separate worktree from the tag. Do not reset
the active checkout, move either tag or force-push `main`.

## Known limitations

- Deterministic providers remain the accepted default baseline.
- One controlled Granite Racio run proves the provider path, not semantic
  quality or production-model fitness.
- Slovenian model quality has not yet been validated.
- A real visual cognition path, VLM interpretation, learned body-effect mapping
  and semantic longitudinal evaluation are not included.
- The Ego GUI panel can horizontally overflow at 390 px when long
  trace/projection identifiers are visible; the accepted debug Communication
  mobile view does not overflow.
- Model response provenance stores the canonical envelope hash and selected
  fields, not a complete replayable raw response envelope.
- QLoRA, LoRA, SFT, training dataset generation and final model selection are
  deliberately out of scope.

## Next phases

1. **C1 — semantic laboratory:** source-grounded scenario families, variations,
   review state and deterministic fixture generation.
2. **C2 — semantic evaluator:** route, interpretation, leakage, bilingual and
   human-review metrics.
3. **C3 — Racio interpreter:** conscious-access filtering and model-backed
   interpretation without hidden native truth.
4. **C4 — Emocio visual cognition:** explicit structured, render-observe and
   visual-cognition modes with strict evidence boundaries.
5. **C5 — Instinkt body-effect mapper:** grounded, provenance-bearing automatic
   cue-to-body predictions with abstention.
6. **C6 — longitudinal Ego:** modality-specific world updates, projections and
   source-grounded recurring motifs across cycles.

Each phase starts from a fresh `main`, retains a deterministic baseline and is
reviewed independently before the next phase.

## Research-use warning

REI v3 is a research simulator and an implementation of explicit architectural
hypotheses. It is not an empirically validated model of a real person, must not
be used to diagnose or classify people, and does not provide medical,
therapeutic or metaphysical conclusions.
