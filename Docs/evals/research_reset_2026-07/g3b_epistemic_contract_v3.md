# G3B model-free epistemic contract/evaluator v3 — 2026-07-17

This document records the bounded G3B design authorized after human acceptance
of G3A. G3B introduces an isolated v3 communication contract and evaluator. It
does not rewrite v1 or v2, alter frozen G3/G3A evidence, call a model, rerun G3,
start G4, integrate a runtime, promote Gemma, or grant any governance authority.

## Version boundary

V3 is implemented in new sibling modules. The frozen modules remain untouched:

- the C3 v1 structured output and action enum;
- the Racio epistemic v2 packet and interpretation;
- the v2 evaluator;
- the Gemma provider, instruction, schema, sidecar policy, and runner;
- all committed G3 evidence and the G3A adjudication.

V1 and v2 artifacts continue to validate only through their historical
contracts. V3 does not silently coerce or rewrite them.

## Action contract

V3 separates `family`, exact `subtype`, and Racio-claimed `support_mode`.

| Family | Exact v3 subtypes |
|---|---|
| `approach_engage` | `approach`, `connect`, `seek_contact`, `maintain_contact` |
| `protection_regulation` | `set_boundary`, `seek_safety`, `withdraw_contact`, `freeze`, `conserve`, `maintain_boundary` |
| `confrontation` | `attack`, `compete`, `remove_obstacle` |
| `execution_expression` | `perform`, `improvise`, `coordinate`, `maintain_execution` |

Action support modes are:

- `direct_manifestation`;
- `functional_inference`;
- `speculative`.

The following resolutions are explicit:

- `protect` is represented as the generic fallback for
  `protection_regulation`, not as an exact sibling of `set_boundary` or
  `seek_safety`. It gains accepted parent credit only when evaluator gold
  precommits that fallback for the case.
- Legacy action `seek_attachment` is not a v3 subtype. Its surface action is
  represented as the motive-neutral `seek_contact`.
- Bare `maintain` is not a v3 subtype. It must resolve from manifested evidence
  to `maintain_contact`, `maintain_boundary`, or `maintain_execution`.
- Legacy `unknown` is represented by no action hypothesis and a bounded unknown
  reason, never by an `unknown` family or subtype.
- `withdraw_contact` is an exact `protection_regulation` subtype. Bare
  `withdraw` is not automatically mapped because spatial retreat and ending
  interpersonal contact are not the same action.
- `attack` and `compete` remain different exact subtypes. Sharing
  `confrontation` can produce family support, never exact-subtype equivalence.

At most two canonically ordered action hypotheses are structurally valid. Each
has its own citations and confidence. Same-family membership can contribute
family coverage, but an unlisted sibling remains an unsupported subtype claim.
An explicitly accepted sibling or parent fallback may avoid an overclaim while
still receiving zero exact-subtype credit.

## Motive contract and minimality

V3 keeps motive family/subtype identity separate from action and adds these
support modes:

- `directly_supported`;
- `contextually_supported`;
- `speculative`.

Only `directly_supported` with the required independent, cited, non-action
evidence contributes to reference motive coverage or the supported numerator
of motive precision. Contextual plausibility, speculation, and lower confidence
never become direct support.

Motive family and exact-subtype coverage are independent. A directly supported
claim in a precommitted family can receive family credit while an unlisted
sibling subtype receives zero subtype credit and remains an unsupported
overclaim.

The reference default is zero or one motive hypothesis. A second or third
hypothesis can receive support only when it has its own qualifying non-action
evidence that was not already consumed by a higher-ranked qualifying motive
hypothesis.
Reusing action evidence is classified separately from an unsupported identity;
reusing another motive's evidence is classified as non-minimal redundancy.

Evidence ownership follows canonical confidence order for every precommitted,
fully cited direct, contextual, or speculative motive identity. Consequently a
higher-ranked lower-support hypothesis cannot leave the same signal available
to a lower-ranked direct claim. Gold with multiple direct targets is rejected
unless every target has at least one independently owned non-action evidence
unit, preventing an evaluator denominator that no valid output could satisfy.

Non-minimal redundancy is an orthogonal assessment field. An additional
hypothesis with no qualifying non-action evidence is redundant even when its
primary finding is a support-mode or identity error; action-only citations
cannot bypass this rule.

An empty hypothesis set preserves unknown motive state when evaluator gold says
the motive is not identifiable. Racio's three-state uncertainty self-report
remains independent and is never mechanically inferred from output shape,
confidence, determinacy, or evaluator findings.

Evaluator gold distinguishes `identifiable`, `contextually_bounded`, and
`not_identifiable`. The middle state permits precommitted contextual
possibilities without manufacturing a direct reference target. A contextual or
speculative output can preserve that non-direct unknown state, while a direct
claim violates it and is assessed separately as a support-mode overclaim.

## R3 SL `connection` decision

G3 and G3A remain historically unchanged. V3 resolves the open human question
without a retroactive edit:

1. Seeking or checking contact/closeness at the visible action layer is
   `approach_engage/seek_contact`, not an attachment-labelled action.
2. `motor_social/connection` remains available only as an Emocio social motive.
3. An Instinkt `attachment_pull` or manifested insecure attachment does not by
   itself directly demonstrate that Emocio motive. For R3-like evidence it is
   at most `contextually_supported` or `speculative`.
4. Consequently, R3 SL `connection` does not contribute to v3 reference
   supported coverage or precision. Claiming it as `directly_supported` is a
   support-mode overclaim. A directly manifested social motive would require a
   separate, precommitted non-action evidence unit.

This resolves the semantic layer without changing the frozen G3 output, v2
evaluation, or G3A report.

## Bilingual evidence and gloss audit

One v3 observation contains one packet-local `observation_id`, one opaque
`signal_alias`, authoritative `canonical_sl`, and at most one
`operational_en`. The gloss does not create a second observation or evidence
unit. Presentation modes may expose canonical SL, operational EN, or both, but
citations always address the same observation ID.

Operational EN is valid only with a human-reviewed audit bound to exact text
hashes. The audit:

- normalizes Unicode with NFKC and case folding and rejects control/format
  characters;
- scans reserved action, motive, support, evaluator, and causality markers;
- requires aligned semantic signatures and aligned collisions;
- requires no added action claim, motive claim, or causal claim;
- requires unchanged role, semantic strength, polarity, and modality.

The collision lexicon contains aligned Slovene and English markers for every
v3 action family, motive family, motive subtype, support mode, evaluator term,
and the bounded action terminology exercised by the contract tests.

The same audited bilingual text boundary applies to observation text, public
option descriptions, and packet uncertainty, so an H11-like option gloss cannot
bypass the audit. Audit receipts and hashes are excluded from provider-visible
payloads.

Canonical evidence identity and option/observation aliases must match before a
bilingual pair can be compared. The evaluator compares raw emitted family,
subtype, and support-mode sets, including speculative hypotheses, so English
enumeration cannot be hidden by a supported-only projection.

A bilingual comparison additionally requires a `canonical_sl_only` SL member
and an `operational_en_only` EN member. Two copies of one presentation cannot be
reported as a successful bilingual pair. Citation identity is compared by
hypothesis key rather than confidence ordering, so ranking differences do not
create a false citation mismatch.

## Structural sidecar and non-authority

The v3 structural sidecar contains exactly:

```text
option_id_present
motive_hypothesis_count
```

It is derived only from validated output shape. It contains no action family,
subtype, support mode, confidence, citation, uncertainty, bilingual, semantic,
gold, or governance field. It is not accepted by the evaluator.

V3 is not exported through runtime adapters and is not imported by engine,
governance, conscious-decision, behavior, or provider code. No v3 result can
affect governance, `ConsciousDecision`, `BehaviorResultant`, or `MindWorld` in
G3B.

## Independent evaluator dimensions

The case evaluator reports, without an aggregate semantic score:

- structural validity, citation scope, packet immutability, hidden-truth
  leakage, and profile leakage;
- action family support/coverage;
- action subtype support/coverage;
- action unsupported overclaims;
- option mapping;
- required abstention;
- motive family coverage;
- motive subtype coverage;
- motive precision;
- unknown preservation;
- per-hypothesis support-mode and evidence assessments.

The bilingual evaluator independently reports:

- bilingual action-family consistency;
- bilingual motive-family consistency;
- bilingual action-subtype consistency;
- bilingual motive-subtype consistency;
- action and motive support-mode consistency;
- option consistency;
- citation/evidence-identity consistency;
- literal option and motive uncertainty consistency, including
  `not_reported` as its own state.

No field named `passed`, `semantic_pass`, `quality_gate_pass`, or `rei_score`
exists on the v3 semantic evaluation results. Any structural hard gate remains
explicitly limited to contract integrity and has no governance effect.

## Verification

The implementation was verified without contacting Ollama or any other model
endpoint:

- the focused v3 contract/evaluator suite: `43 passed`;
- the combined v3, frozen v1/v2 contract, frozen G3 runner, and model-free
  provider suites: `162 passed`;
- Python compilation/import checks for both new v3 modules: passed;
- model calls, retries, and fallbacks: `0 / 0 / 0`.

The regression tests cold-validate all 16 frozen G3 packets, outputs, and case
evaluations plus all eight frozen bilingual pair evaluations through their
historical v2 models. They also pin the relevant v1/v2 and provider schema
hashes, demonstrating that v3 did not rewrite those contracts.

G3B stops after the isolated contract, evaluator, documentation, tests, commit,
and feature-branch push. G3C, G4, shadow runtime integration, PR, and merge all
require separate authorization.

## G3B.1 finalization

G3B.1 is the single authorized finalization of v3 before any v3 model call,
provider response, or runtime artifact exists. It refines only the isolated v3
contract/evaluator. The preceding G3B record remains the historical design
decision; v1, v2, frozen G3 evidence, and G3A adjudication remain unchanged.

### Option-specific evidence

The two parallel option scalars are replaced by one optional claim:

```text
OptionInferenceV3
├── option_id
├── cited_observation_ids
└── confidence
```

An option selection requires nonempty, canonical, visible citations and
positive confidence. When no selection is made, `option_inference` is absent
and `option_unknown_reason` must equal the single bounded contract value. A
selection and an option-unknown reason are mutually exclusive.

The evaluator derives option support exclusively from
`option_inference.cited_observation_ids`. Global `cited_observation_ids` remains
a union/diagnostic scope list and must contain every claim-local citation, but
it cannot grant option credit. An action or motive citation therefore cannot
silently support option mapping.

### Final protective action semantics

`protection_regulation/retreat` is added as an exact subtype. The three nearby
actions have different identities:

- `seek_safety`: a direction or goal toward a safer state; it does not require
  physical withdrawal;
- `retreat`: manifested physical or spatial increase of distance; it does not
  assert interpersonal disconnection or a safety motive;
- `withdraw_contact`: reduction or termination of interpersonal contact; it
  does not require spatial movement.

Bare legacy `withdraw` remains unmapped at the communication boundary. An
evaluator gold entry may record `legacy_source_action="withdraw"` only while
explicitly resolving it to exact `retreat` or exact `withdraw_contact`.
`seek_safety`, a sibling role, or a family fallback is not a valid legacy
resolution.

The following short definitions are normative for v3:

| Action | Normative manifested meaning |
|---|---|
| `approach` | Movement or orientation closer to a target, without claiming that contact was established. |
| `connect` | Actual establishment of contact or a communication channel. |
| `seek_contact` | An attempt or direction toward establishing or restoring contact; success is not required and the label is motive-neutral. |
| `maintain_contact` | Preservation of contact that already exists. |
| `seek_safety` | Direction or goal toward a safer state, without necessarily retreating. |
| `retreat` | Physical or spatial increase of distance, without claiming contact termination or a safety motive. |
| `withdraw_contact` | Reduction or termination of interpersonal contact, without necessarily moving in space. |
| `protect` family fallback | Parent-level `protection_regulation` only when exact subtype evidence is insufficient and evaluator gold precommits the fallback. |
| `attack` | Manifested direct aggressive action toward a target; no motive is inferred from the action alone. |
| `compete` | Manifested competition or comparative opposition; it is not an attack synonym. |
| `perform` | Execution or expression of an act or task. |
| `coordinate` | Alignment of roles, timing, or actions across actors or components. |

Family support never implies exact-subtype support. In particular,
`seek_safety`, `retreat`, and `withdraw_contact` can share family credit while
remaining mutually non-exact.

### Observation atomicity

One `observation_id` represents exactly one semantically perceptible unit.
Compound manifestations are an upstream producer/pre-packet responsibility and
must be split before packet construction. G3B.1 does not introduce a scene
parser or attempt to infer atomicity from prose.

Each observation carries non-provider-facing corpus-attestation metadata:

- one unique `atomic_evidence_unit_id`;
- `perceptual_unit_count=1`.

The packet rejects duplicate observation IDs, duplicate atomic-unit IDs, and a
declared unit count other than one. Two genuinely different signals require two
observation IDs and two atomic-unit IDs, even if their surface descriptions are
textually identical. Conversely, one atomic signal may not be cloned under two
observation IDs merely to support multiple motives.

The attestation metadata is neither a second evidence identity nor citability
surface. It is omitted from provider payloads; the only model-facing and
citeable identity remains `observation_id`.

### Runtime/evaluation bilingual boundary

Human-audited `operational_en` is required only for bilingual evaluation or a
precommitted reviewed corpus. A future general shadow runtime must use
`canonical_sl_only`; G3B.1 does not implement that runtime.

A future machine-generated gloss may exist only as an explicitly marked,
unreviewed shadow artifact outside the audited packet/evaluator boundary. Such
a gloss cannot:

- count as bilingual quality evidence;
- enter governance or decision authority;
- create a new observation or atomic evidence identity;
- satisfy the human-reviewed bilingual audit.

### Model-facing draft requirement for the next provider phase

The next separately authorized provider phase must make Gemma return a simpler
`RacioEpistemicDraftV3`. G3B.1 deliberately implements neither that draft
schema, a provider, nor a canonicalizer.

The future deterministic canonicalizer may perform only:

- canonical sorting;
- insertion of the standard bounded unknown-reason values when the draft
  explicitly abstains or supplies an empty claim shape;
- canonical serialization.

It may not add, remove, rename, or select semantic claims; change family,
subtype, support mode, citations, confidence, or option identity; repair an
invalid semantic output; infer missing evidence; or otherwise turn a failed
draft into an accepted interpretation.

### G3B.1 scope and authority

The structural sidecar remains limited to `option_id_present` and
`motive_hypothesis_count`. V3 outputs remain isolated from providers, runtime,
GUI, governance, `ConsciousDecision`, `BehaviorResultant`, and `MindWorld`.
There is no aggregate semantic score and no model promotion.

G3B.1 verification completed without contacting Ollama or another model
endpoint:

- focused finalized-v3 contract/evaluator suite: `58 passed`;
- combined finalized-v3, frozen v1/v2 contract, frozen G3 runner, and
  model-free provider suites: `177 passed`;
- Python compilation/import checks for the finalized v3 modules: passed;
- model calls, retries, and fallbacks: `0 / 0 / 0`.

G3B.1 stops after its tests, dedicated commit, and feature-branch push. Provider
implementation, G3C, G4, shadow integration, PR, and merge require separate
authorization.
