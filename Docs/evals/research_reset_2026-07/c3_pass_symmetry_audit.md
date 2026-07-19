# G1 — C3 pass-symmetry audit

**Date:** 2026-07-17

**Branch:** `codex/racio-gemma4-epistemic-interpreter`

**Base audit SHA:** `78c8bd0c5087c18e4790a542c176b3fd0a0788c0`

**Status:** completed development audit; no score, semantic authority, or
model-promotion authority

## 1. Purpose and boundary

X2 reviewed all 18 frozen C3 semantic failures. This G1 audit applies the same
public-surface-first method to a deterministic symmetry sample of 12 frozen
passing records before the v2 evaluator or Gemma development corpus is used.

No model call, prompt change, schema change, gold change, rescore, retry,
fallback, training export, or Qwen invocation occurred. The official
`23/32 + 23/32` result remains unchanged.

## 2. Evidence

| Artifact | Frozen SHA-256 |
|---|---|
| Holdout public cases | `ef41a1844a0544ec88ba9233e28cb6ba995c9c4a7e5b1f8df559101b5db9bfa5` |
| Holdout gold | `41b707205202656ebeabf669f349d3b61d3d2c80f7177d2e3d96d2a9e9754842` |
| Holdout results | `bd39514572f59c14810d129cb4091f445bdd723e24bb7ff5cf46971bfcf57dfd` |
| Regression public cases | `cc7f0c7dc5530af06372090b966b29e57f391196935e24a8d9ac7055cdb4f0ec` |
| Regression gold | `32fcede3cd445a7ba3160ee1592ba4eb1822c9efa9d16735d334c213e7b973f1` |
| Regression results | `67501ae4999d3ad9a447e85d0f882800b8d30085d9c75c79378035d150eb83c2` |

## 3. Precommitted deterministic selection

For each suite, cases were grouped into three strata using only frozen case
metadata and pass status:

1. accepting, unambiguous, source mind E;
2. accepting, unambiguous, source mind I;
3. ambiguous, with both language members passing.

Within each stratum, the lexicographically first complete Slovenian/English
pair whose two members passed was selected. The selection was frozen before
reading the selected model outputs semantically.

| Suite | Stratum | Selected pair | Selected records |
|---|---|---|---|
| Holdout | clear E | `c3h_pair_005` | `c3h_case_009`, `c3h_case_010` |
| Holdout | clear I | `c3h_pair_009` | `c3h_case_017`, `c3h_case_018` |
| Holdout | ambiguous | `c3h_pair_002` | `c3h_case_003`, `c3h_case_004` |
| Regression | clear E | `c3_pair_013` | `c3_case_025`, `c3_case_026` |
| Regression | clear I | `c3_pair_007` | `c3_case_013`, `c3_case_014` |
| Regression | ambiguous | `c3_pair_002` | `c3_case_003`, `c3_case_004` |

This yields exactly 12 records: six per suite, six per language, eight source-E,
four source-I, and four records whose correct option behavior is abstention.

## 4. Public-surface-first review

The public packet was reviewed before gold and model output. Option descriptions
were treated only as mapping aids after a direction was visible; they were not
accepted as evidence of a hidden motive.

| Pair | Public surface | Frozen output | Epistemic audit |
|---|---|---|---|
| `c3h_pair_002` | Desired-scene mismatch is visible; decisive motor direction is degraded. | null option / unknown action / unknown motive, confidence `0.35` | Clean abstention. The available signal does not select an option or action, and the model preserves that limit. |
| `c3h_pair_005` | Motor-pattern readiness `0.91` and direct `perform` tendency. | option 1 / perform / motor pattern, confidence `0.90` | Action, option, and motive are directly supported by visible observations. This remains epistemically sound under v2. |
| `c3h_pair_009` | Resource insecurity `0.89` and direct `protect` tendency. | option 1 / protect / body alarm, confidence `0.85` | Action and option are supported. Exact `body_alarm` is legacy-taxonomy broad: v2 should prefer the visible `resource_alarm` subtype rather than infer a general body alarm from `protect`. |
| `c3_pair_002` | Anger intensity is visible; decisive motor direction is degraded. | null option / unknown action / unknown motive, confidence `0.35` | Clean abstention. The model does not use option text to invent the missing broken-scene motive. |
| `c3_pair_007` | Explicit boundary alarm `0.90` and direct `seek_safety` tendency. | option 1 / seek safety / body alarm, confidence `0.85` (sl), `0.90` (en) | Action and option are supported. The motive is protection-family compatible but less precise than the visible `boundary_alarm`; exact top-1 equality hides the hierarchy. |
| `c3_pair_013` | Generic aversion `0.80` and direct `set_boundary` tendency. | option 2 / set boundary / boundary alarm, confidence `0.85` (sl), `0.95` (en) | Action and option are supported. The motive is not uniquely established: generic aversion plus an action name must not automatically become `boundary_alarm`. The English motive confidence is especially overcommitted. |

## 5. Findings by dimension

### Structural safety

All 12 records have valid structure and citations, unchanged input packets,
valid provider provenance, and zero hidden/profile leakage. This confirms the
old technical contract for the sample, not semantic authority.

### Action

- Four ambiguous records correctly return `unknown` because the decisive action
  observation is degraded.
- All eight clear records identify the directly visible action tendency.
- No sampled action error was hidden by motive scoring.

### Option and abstention

- All four ambiguous records correctly abstain.
- All eight clear records map their visible action/direction to a supported
  public option.
- The audit found no sampled case where option text alone was needed to recover
  the action.

### Motive hypotheses

- The two motor-delegation records have a directly supported legacy motive.
- The two scarcity records expose a missing `resource_alarm` subtype.
- The two claustrophobia records show a broad/specific protective hierarchy.
- The two delegation-boundary records may be exact-correct only because the old
  evaluator merges action and motive; their visible generic aversion does not
  make `boundary_alarm` unique.
- All 12 outputs have `alternative_hypotheses=[]`. That is appropriate for the
  four explicit unknown outputs but loses useful hierarchy/uncertainty in the
  clear-I and delegation-boundary records.

### Confidence and bilingual behavior

The structured fields are bilingual-consistent in all six sampled pairs. The
confidence deltas are `0.00`, `0.00`, `0.00`, `0.00`, `0.05`, and `0.10`.
However, consistency does not make a motive supported. In particular,
`c3_case_026` assigns `0.95` to a non-unique motive inference.

## 6. G1 design consequence

The symmetry sample confirms both sides of X2:

- the old evaluator has genuinely useful passing behavior for direct action,
  option mapping, and explicit abstention;
- some exact passes are only legacy-taxonomy passes and are not fully
  epistemically sound.

V2 must therefore keep structural safety as a hard contract while reporting
action, option, abstention, cited motive support, hierarchy compatibility,
unsupported overclaims, confidence, and bilingual consistency separately. It
must not produce one replacement REI score or retroactively rescore C3 v1.

## 7. Authority

- Records reviewed: `12`
- New model calls: `0`
- Frozen result or gold mutations: `0`
- Qwen score changed: `no`
- Semantic authority granted: `no`
- Production authority granted: `no`
- Model promoted: `no`
- Next bounded step: complete the parallel v2 contract/evaluator and focused
  tests, then proceed to the Gemma-only technical preflight.
