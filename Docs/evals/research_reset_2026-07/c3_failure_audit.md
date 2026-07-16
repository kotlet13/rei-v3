# X2 — C3 failure audit

**Date:** 2026-07-16
**Branch:** `codex/racio-failure-audit`
**Audit base commit:** `f0cad7c828d8a24987b927fc32ab586f05b7fb70`
**Status:** awaiting human review
**Authority:** evidence-only research audit; no semantic, production, or model-promotion authority

## 1. Disposition and phase boundary

This X2 phase manually reviews every semantic failure in the frozen official
`qwen3.6:35b` C3 pair. It makes no model call and changes no prompt, schema,
evaluator, corpus, gold label, registry, or runtime.

The central finding is that the aggregate `23/32` scores conflate three
different phenomena:

1. **eleven lead-A records with clear model errors**, while the two lead-B
   records also contain unsupported motive overclaims;
2. **four underdetermined cases** in which the public surface does not identify
   the single exact gold option/motive;
3. **three lead motive-overlap cases**, plus two clear-error records that also
   need an overlap-aware target.

The model is therefore not retroactively passed. The current exact gate is also
not accepted as the sole measure of Racio quality. X3 remains unauthorized until
the user reviews the classifications and metric proposal below.

No new model call, retry, prompt tuning, training dataset, LoRA/QLoRA/SFT,
holdout mutation, or retroactive rescoring occurred.

## 2. Frozen evidence and provenance

The authoritative pair is:

`Docs/evals/semantic_lab_v1/c3-racio-official-pair-qwen3-6-35b-2026-07-15/`

| Evidence | Frozen value |
|---|---|
| Pair ID | `c3-racio-official-pair-qwen3-6-35b-2026-07-15` |
| Protocol freeze | `d74891cdeed407a50098d28d6f4e9024b28156e7` |
| Execution source | `707cb2037da70291d4d311004bc15d8f3927b150` |
| Evidence publication | `e66f14cae97fbe628b0a9bcb60225bbf83aaca9d` |
| Pair provenance SHA-256 | `b168ec16fbfb45b7a64a47ba549fde3a0841c416e4fa4f891dbe6758fc2513bf` |
| Model | `qwen3.6:35b` |
| Model digest | `07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522` |
| Instruction SHA-256 | `c5ea5a0936bbab5e9bb481e53443eb9119cb5bf2c1d58737f3bb0214ebcfb1b0` |
| Output-schema SHA-256 | `7b51eeadc1e13223016a1ab95aab88b9141ed7d11a5400bd05cf25988645bd1c` |
| Seed / temperature | `314159` / `0.0` |
| Context / GPU offload | `65536` / `num_gpu=999`, recorded 100% GPU |
| Calls | 64 successful calls, no retry or fallback |

### 2.1 Untouched holdout

| Artifact | SHA-256 |
|---|---|
| `knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1/manifest.json` | `32a57a8dc0601ad01ca9eb169786e0888f13c036488762f9cfa6b69a0b7233f2` |
| `public_cases.jsonl` | `ef41a1844a0544ec88ba9233e28cb6ba995c9c4a7e5b1f8df559101b5db9bfa5` |
| `gold.jsonl` | `41b707205202656ebeabf669f349d3b61d3d2c80f7177d2e3d96d2a9e9754842` |
| `holdout/results.jsonl` | `bd39514572f59c14810d129cb4091f445bdd723e24bb7ff5cf46971bfcf57dfd` |
| `holdout/metrics.json` | `a986df10ced9e5b50f27cb3670918673347d13c1be4de433da5ca65e4356183e` |
| `holdout/provenance.json` | `b5fe0b74df8b8d4f85eefe2b01d084d1a935041c0eea5fc17e9e7a14c95706c3` |

### 2.2 Frozen regression

| Artifact | SHA-256 |
|---|---|
| `knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter/manifest.json` | `1cbb5607acc95426673feddb9891567b5a46e5f4988f8cc171a6636069bbab4b` |
| `public_cases.jsonl` | `cc7f0c7dc5530af06372090b966b29e57f391196935e24a8d9ac7055cdb4f0ec` |
| `gold.jsonl` | `32fcede3cd445a7ba3160ee1592ba4eb1822c9efa9d16735d334c213e7b973f1` |
| `regression/results.jsonl` | `67501ae4999d3ad9a447e85d0f882800b8d30085d9c75c79378035d150eb83c2` |
| `regression/metrics.json` | `1aafe13b495362842b021e199b4d6e532e366b4dd536075d5b79d6843b64ff84` |
| `regression/provenance.json` | `074282a5b8f70026129faf36c8bd0c12395f2dbe3576b5db62fea6c414c1d0f1` |

A reviewed failure means `passed=false` in the corresponding `results.jsonl`.
Both `failures.jsonl` files are empty because they record provider/execution
failures; there were none. They are not the semantic-failure inventory.

## 3. Completeness accounting

| Suite | Cases | Passed | Semantic failures | Option misses | Action misses | Motive misses | Bilingual consistency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Untouched holdout | 32 | 23 | 9 | 2 | 2 | 7 | 14/16 pairs |
| Frozen regression | 32 | 23 | 9 | 2 | 4 | 5 | 15/16 pairs |
| Combined | 64 | 46 | 18 | 4 | 6 | 12 | 29/32 pairs |

All 18 failed cases are frozen as `accepting` and `unambiguous`. Every one has
valid structured output, citations, input immutability, no hidden/profile
leakage, and valid provenance. Their only recorded per-case issue is
`semantic_gate_failure`.

All 18 failed outputs have `alternative_hypotheses=[]`, while their mean
confidence is `0.869` and every confidence is between `0.85` and `0.95`. This is
an epistemic-quality signal that the old exact score does not measure.

Failed holdout IDs:

`c3h_case_001`, `c3h_case_002`, `c3h_case_005`, `c3h_case_006`,
`c3h_case_013`, `c3h_case_014`, `c3h_case_021`, `c3h_case_029`,
`c3h_case_030`.

Failed regression IDs:

`c3_case_001`, `c3_case_002`, `c3_case_005`, `c3_case_006`, `c3_case_009`,
`c3_case_017`, `c3_case_018`, `c3_case_021`, `c3_case_022`.

## 4. Audit method

Each judgment used only the provider-visible public surface first:

- source mind and language;
- visible observation names, values, and clarity;
- public option IDs and descriptions;
- channel quality and public uncertainty.

Root/family names, evaluator-only native truth, profile, canary, and gold were
not treated as evidence. Gold and model output were compared only after the
public-surface judgment.

`Gold support` below means:

- **U — unique:** the public surface supports the full gold triple and no
  comparably plausible competing interpretation;
- **S — supported, not unique:** the gold is defensible but another option or
  motive is also defensible;
- **N — not identifiable:** the public surface does not justify the single gold
  option/motive.

Primary classifications use the reset-plan categories:

| Code | Meaning |
|---|---|
| A | obvious model error |
| B | signal does not contain enough information for the gold motive |
| C | gold motive is too narrow |
| D | motive categories overlap |
| E | a top-k hypothesis set would be the right target |
| F | abstention would be the right target |
| G | schema/adapter problem |
| H | bilingual formulation/behavior problem |

One lead code is assigned per failure for completeness accounting. The A–H
categories themselves are not mutually exclusive: secondary codes describe
additional evidence diagnoses or the recommended target.

## 5. Untouched holdout: public surfaces

| Surface | Failed cases | Visible observations | Public options |
|---|---|---|---|
| H1 | `001/002` | desired-scene mismatch: empty hall vs collaborative group; urge `connect` | O1 create a path toward the collaborative scene; O2 continue in the solitary broken direction |
| H3 | `005/006` | desired scene absent: low attraction to planned exercise; urge `protect` | O1 start the written exercise schedule; O2 defer and recheck cooperation |
| H7 | `013/014` | recurring broken scene: harmful collaboration; urge `set_boundary` | O1 continue the harmful collaboration; O2 end it after repeated occurrences |
| H11 | `021` | `boundary_alarm=0.86`; urge `seek_safety` | O1 longer exposed route; O2 shorter protected route with better retreat |
| H15 | `029/030` | `boundary_alarm=0.92`; urge `set_boundary` | O1 verbally say no; O2 physically step back; both protect the same boundary |

The Slovenian and English cases in each surface are semantically paired.
`c3h_case_022`, the passing English partner of failed `c3h_case_021`, is used
only for bilingual context and is not counted as a failure.

## 6. Untouched holdout: all nine failures

Notation in the frozen triples is `option / action / motive`. `Alt` is the
model's recorded `alternative_hypotheses`, not a human reconstruction.

| Case | Lang / mind | Surface | Gold triple | Model triple (confidence) | Alt | Exact O/A/M | Gold support | Class | Audit judgment and gate disposition |
|---|---|---|---|---|---|---|---|---|---|
| `c3h_case_001` | sl / E | H1 | O1 / connect / broken_scene | O1 / connect / motor_pattern (0.85) | `[]` | 1/1/0 | U | **A** | The frozen definition maps desired-scene mismatch to `broken_scene` and permits `motor_pattern` only when no stronger broken-scene cue exists. This is a clear motive error. |
| `c3h_case_002` | en / E | H1 | O1 / connect / broken_scene | O1 / connect / motor_pattern (0.85) | `[]` | 1/1/0 | U | **A** | Same clear motive error as the Slovenian pair member. Acknowledging inaccessible deeper context does not override the visible mismatch rule. |
| `c3h_case_005` | sl / E | H3 | O2 / protect / broken_scene | O2 / seek_safety / boundary_alarm (0.85) | `[]` | 1/0/0 | S | **A**; D,E,H | O2 is grounded, but the visible action is literally `protect`; `seek_safety` is an error. The selected `boundary_alarm` is also unsupported because no aversion, `set_boundary`, or withdrawal cue is visible. Plausible overlap is between gold and unchosen `body_alarm`. |
| `c3h_case_006` | en / E | H3 | O2 / protect / broken_scene | O2 / unknown / boundary_alarm (0.85) | `[]` | 1/0/0 | S | **A**; D,E,H | Clear `protect` does not justify `unknown`, and the selected `boundary_alarm` is unsupported. The paired Slovenian output instead chose `seek_safety`, so H is also flagged. |
| `c3h_case_013` | sl / E | H7 | O2 / set_boundary / broken_scene | O2 / set_boundary / boundary_alarm (0.85) | `[]` | 1/1/0 | S | **D**; E | `broken_scene_recurrence` directly supports gold, while `set_boundary` directly supports the model motive. Exact top-1 motive is not an adequate sole gate. |
| `c3h_case_014` | en / E | H7 | O2 / set_boundary / broken_scene | O2 / set_boundary / boundary_alarm (0.85) | `[]` | 1/1/0 | S | **D**; E | Same overlap and disposition as the Slovenian pair member. |
| `c3h_case_021` | sl / I | H11 | O2 / seek_safety / body_alarm | O2 / seek_safety / boundary_alarm (0.85) | `[]` | 1/1/0 | S | **D**; E,H | `seek_safety` supports `body_alarm`; the explicitly named `boundary_alarm` supports the model. The English partner chose `body_alarm` and passed, so bilingual behavior is unstable. |
| `c3h_case_029` | sl / I | H15 | O2 / set_boundary / boundary_alarm | O1 / set_boundary / boundary_alarm (0.95) | `[]` | 0/1/1 | N | **F** | Nothing visible selects verbal refusal versus physical retreat. Correct evaluation should permit option abstention while preserving action/motive, not demand O2. |
| `c3h_case_030` | en / I | H15 | O2 / set_boundary / boundary_alarm | O1 / set_boundary / boundary_alarm (0.95) | `[]` | 0/1/1 | N | **F** | Same underdetermination. The model's confident O1 is also epistemically overcommitted; a null option with explicit uncertainty is preferable. |

### 6.1 Holdout pair judgments

- **H1:** option/action are reliable and the frozen motive definition makes the
  model's `motor_pattern` a clear error.
- **H3:** both languages contain a real action error, plus a motive-overlap and
  bilingual-consistency issue; their selected `boundary_alarm` is itself
  unsupported.
- **H7:** exact motive scoring confuses two simultaneously visible causal
  descriptions.
- **H11:** body/boundary taxonomy overlaps and the two languages choose
  different sides of that overlap.
- **H15:** the case is mislabeled as unambiguous at the option level; modality
  is not manifested.

## 7. Frozen regression: public surfaces

| Surface | Failed cases | Visible observations | Public options |
|---|---|---|---|
| R1 | `001/002` | `anger_intensity=0.9`; urge `attack` | O1 pause and check the cause of a broken desired scene; O2 end contact immediately without checking |
| R3 | `005/006` | `attachment_pull=0.9`; urge `seek_attachment` | O1 withdraw/end contact; O2 seek safe contact and check closeness |
| R5 | `009` | `attraction_intensity=0.85`; urge `perform` | O1 remain with the image only; O2 perform the prepared motor step |
| R9 | `017/018` | urge `connect`; social pull toward connection | O1 make contact and state the request; O2 ignore the multi-channel signal |
| R11 | `021/022` | `felt_tension=0.8`; urge `protect` | O1 continue without checking; O2 pause, protect the boundary, and check circumstances |

`c3_case_010`, the passing English partner of failed `c3_case_009`, is used
only for bilingual context and is not counted as a failure.

## 8. Frozen regression: all nine failures

| Case | Lang / mind | Surface | Gold triple | Model triple (confidence) | Alt | Exact O/A/M | Gold support | Class | Audit judgment and gate disposition |
|---|---|---|---|---|---|---|---|---|---|
| `c3_case_001` | sl / E | R1 | O1 / attack / broken_scene | O2 / attack / body_alarm (0.85) | `[]` | 0/1/0 | N | **B**; A,F | Anger and attack do not identify pause/check versus end-contact, and no manifested observation establishes a broken scene. The gold motive appears only inside O1's description, making the inference circular. Correct output should abstain and keep motive `unknown`; the selected `body_alarm` is also an unsupported model overclaim. |
| `c3_case_002` | en / E | R1 | O1 / attack / broken_scene | O2 / attack / body_alarm (0.85) | `[]` | 0/1/0 | N | **B**; A,F | Same underdetermination. The model's body-alarm claim is overconfident and unsupported by the frozen motive definitions. |
| `c3_case_005` | sl / I | R3 | O2 / seek_attachment / attachment | O2 / seek_safety / attachment (0.85) | `[]` | 1/0/1 | U | **A** | The public urge is exactly `seek_attachment`, an allowed schema value. `seek_safety` is a genuine action-classification error. |
| `c3_case_006` | en / I | R3 | O2 / seek_attachment / attachment | O2 / seek_safety / attachment (0.90) | `[]` | 1/0/1 | U | **A** | Same genuine action error in English; no schema restriction forced it. |
| `c3_case_009` | sl / E | R5 | O2 / perform / motor_pattern | O2 / perform / attachment (0.95) | `[]` | 1/1/0 | U | **A**; H | The explicit perform cue and absence of an explicit closeness/safe-contact cue support `motor_pattern` under the frozen definitions. English chose `motor_pattern` and passed. |
| `c3_case_017` | sl / E | R9 | O1 / connect / motor_pattern | O1 / connect / attachment (0.85) | `[]` | 1/1/0 | U | **A** | The frozen definition explicitly maps connect motor/social execution to `motor_pattern`; `attachment` requires explicit attachment, closeness, or safe contact, none of which is present. This is a clear motive error. |
| `c3_case_018` | en / E | R9 | O1 / connect / motor_pattern | O1 / connect / attachment (0.85) | `[]` | 1/1/0 | U | **A** | Same clear motive error as the Slovenian pair member. |
| `c3_case_021` | sl / I | R11 | O2 / protect / body_alarm | O2 / set_boundary / body_alarm (0.85) | `[]` | 1/0/1 | U | **A** | The manifested action is exactly `protect`; `set_boundary` is related but not the same frozen enum and is a genuine model error. |
| `c3_case_022` | en / I | R11 | O2 / protect / body_alarm | O2 / set_boundary / body_alarm (0.85) | `[]` | 1/0/1 | U | **A** | Same genuine action error in English. |

### 8.1 Regression pair judgments

- **R1:** the evaluator asks for a hidden/circular broken-scene interpretation
  and an option that the manifested signal does not distinguish; abstention and
  `unknown` motive are preferable to top-k guessing.
- **R3:** clear model action error in both languages.
- **R5:** clear Slovenian motive error plus bilingual instability; the English
  partner passed.
- **R9:** the frozen motive definitions make both attachment outputs clear
  model errors.
- **R11:** clear model action error in both languages.

## 9. Bilingual findings

Three semantically paired inputs produced different semantic fields. All three
confidence deltas remained within the permitted tolerance:

| Pair | Slovenian | English | Audit consequence |
|---|---|---|---|
| `c3h_pair_003` | `seek_safety / boundary_alarm`, failed | `unknown / boundary_alarm`, failed | Both miss `protect`; language changes the wrong action. |
| `c3h_pair_011` | `seek_safety / boundary_alarm`, failed | `seek_safety / body_alarm`, passed | Language selects opposite sides of an overlapping motive taxonomy. |
| `c3_pair_005` | `perform / attachment`, failed | `perform / motor_pattern`, passed | Language changes the motive despite equivalent visible signals. |

This supports an H flag for four failed records, but does not prove that wording
alone caused the divergence. The future bilingual metric should compare option,
action, cited evidence, hypothesis sets, uncertainty, and calibrated confidence;
it should not demand literal prose identity.

## 10. Classification synthesis

Lead classifications are an accounting device; secondary A–H applicability can
overlap:

| Lead class | Cases | Count |
|---|---|---:|
| A — clear model error | `c3h_case_001`, `c3h_case_002`, `c3h_case_005`, `c3h_case_006`, `c3_case_005`, `c3_case_006`, `c3_case_009`, `c3_case_017`, `c3_case_018`, `c3_case_021`, `c3_case_022` | 11 |
| B — gold motive is not manifested | `c3_case_001`, `c3_case_002` | 2 |
| D — motive categories overlap | `c3h_case_013`, `c3h_case_014`, `c3h_case_021` | 3 |
| F — option abstention is correct | `c3h_case_029`, `c3h_case_030` | 2 |
| **Total** | all failed records | **18** |

Additional classification applicability is deliberately non-exclusive and may
include a primary classification:

| Flag | Count | Meaning in this audit |
|---|---:|---|
| A | 13 | eleven lead-A records plus unsupported motive overclaims in the two R1 records |
| C | 0 | no failed case needs C once the frozen operational definitions are applied |
| D | 5 | three lead overlap cases plus the two H3 motive comparisons |
| E | 5 | cited motive hypotheses are appropriate for H3, H7, and H11 |
| F | 4 | option abstention is appropriate for H15 and R1; two are primary F |
| G | 0 | expected enums were schema-valid; all structures and adapters validated |
| H | 4 | failed members of the three bilingual-mismatch pairs |

The important result is not that every miss should be excused. Eleven records
are lead A, and 13 records contain at least one clear model error once the two R1
overclaims are included. A single `passed` boolean still hides that nine records
— including H3 and R1 records that also contain clear errors — require a more
epistemically faithful target or metric.

## 11. Proposed metric decomposition

These are X2 recommendations only. No evaluator is changed here.

### 11.1 Structural safety remains a hard gate

Keep the existing requirements for:

- valid structured output;
- citations within the visible packet;
- no hidden/profile leakage;
- immutable input packet;
- complete provider provenance.

### 11.2 Epistemic validity becomes separately visible

For each interpretation, score:

- whether every claimed option/action/motive cites visible support;
- whether confidence reflects uniqueness versus overlap;
- whether meaningful alternative hypotheses are retained;
- whether uncertainty or abstention is used when the signal is insufficient.

The 18 failures' empty alternatives and high mean confidence should fail or
reduce this layer even where a model's top-1 label is human-plausible.

### 11.3 Option and action are scored independently

- Keep exact action scoring when the public cue literally names the action;
  this preserves six action-error A classifications. Exact motive scoring on a
  uniquely supported surface preserves five further A records: H1, R5, and R9.
- Keep exact option scoring only when visible evidence distinguishes the public
  options.
- Reclassify H15 and R1 as development-visible ambiguous cases for future
  evaluator design; their preferred behavior is option abstention, not a forced
  route.

### 11.4 Motive becomes a cited hypothesis set

The next exploration should allow at most three motive hypotheses. Each needs:

- a motive class;
- cited observation IDs;
- confidence;
- a short bounded explanation.

Use exact top-1 only where the public surface uniquely supports it. For H3, H7,
and H11 overlap cases, score whether an independently precommitted acceptable
motive appears in the cited top-k set. `unknown` remains correct when no motive
class is supported, including R1 as currently manifested.

X2 does not rewrite the frozen gold. Because the holdout is now visible for
development, any X3 tuning requires a newly precommitted untouched holdout
before a generalization claim.

### 11.5 Distortion remains a modeled phenomenon

All 18 reviewed failures are accepting/unambiguous, so this subset does not
justify a new claim about conflicted-state rationalization. A later metric may
represent a distorted motive interpretation as expected behavior only when the
case is precommitted for that purpose; it must not silently turn arbitrary model
errors into passes.

### 11.6 Bilingual consistency compares semantics, not wording

Compare:

- inferred option and action;
- cited observation sets;
- ranked motive-hypothesis classes;
- unresolved ambiguity;
- calibrated confidence.

Do not require literal Slovenian/English explanation equality. Do require a
documented reason when paired outputs cross pass/fail boundaries.

## 12. Human decisions required

Please review these five decisions:

1. Are the six action-error fields and nine unsupported motive selections across
   13 records genuine model errors, while H3 still needs a top-k target and R1
   still needs abstention because those target diagnoses are non-exclusive?
2. Should the two B and two F records be treated as underdetermined, with
   abstention as the preferred behavior?
3. Should the five D/E-applicable records in H3, H7, and H11 move from exact
   top-1 motive scoring to cited top-k motive coverage?
4. Is the proposed X3 output — up to three cited motive hypotheses plus explicit
   unresolved ambiguity — the right next experiment?
5. Do you agree that a new untouched holdout is mandatory before any later
   generalization or model-promotion claim?

Human review may accept, reject, or amend individual classifications. It does
not grant production authority and does not retroactively change the frozen
23/32 outcomes.

## 13. Mandatory stop

- X2 report status: `awaiting_user_review`
- New model calls in X2: `0`
- Prompt/schema/evaluator/gold changes in X2: `0`
- Model promoted: `no`
- Semantic authority granted: `no`
- Production authority granted: `no`
- External-evidence authority granted: `no`
- Next allowed step: none until user review
- X3: requires explicit user authorization after review
