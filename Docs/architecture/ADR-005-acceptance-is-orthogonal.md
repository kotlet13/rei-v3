# ADR-005: Acceptance is orthogonal to character and agreement

Status: Accepted
Date: 2026-07-13
Scope: B1 documentation contract; B9 record-only communication audit; B10 explicit conscious/behavior policy

Acceptance of this ADR does not change the claim statuses recorded in `knowledge/canon_v2/claims.jsonl`.

## Context

Legacy heuristics equate acceptance with safe, bounded or reversible language. REI source review instead links sprejemanje to cooperation, tolerance and delegation among the minds. It does not imply equal rank, agreement, happiness, truth or a particular outward action.

## Decision

Model acceptance as directed relations among R, E and I. A relation may describe visibility, interpretation fidelity, tolerance, delegation willingness, sabotage risk and conflict carryover.

Source-supported boundary: sources support cooperation, tolerance and delegation. The six directed relations and their dimensions are the initial software model with status `implementation_hypothesis`; they are not asserted as a direct-source psychological schema.

Acceptance can affect how well minds hear and translate each other, whether a task can be delegated and whether conscious intent becomes coordinated behavior. It cannot change character tiers, choose the correct goal, require agreement or prescribe a small/safe/reversible step.

Controlled simulations receive `AcceptanceState` explicitly. The first implementation does not infer it from keywords. `TranslationGap` is a diagnostic comparison between frozen E/I conclusions and Racio interpretations; its ground truth is not given to Racio.

## Rejected alternatives

- Acceptance as agreement, happiness, resignation or compliance.
- Acceptance as a character weight or rank modifier.
- Inferring acceptance from “bounded”, “safe”, “small” or “reversible”.
- Treating disagreement as proof of non-acceptance.
- Treating outward agreement as proof of acceptance.
- Letting acceptance silently replace governance with a compromise.

## Consequences

- Disagreement can be accepting, and agreement can be suppressive or sabotaged.
- Translation fidelity and delegation can vary by direction.
- Behavior may diverge from governance or conscious decision without changing structural character.
- Initial behavior mapping is an explicit configurable hypothesis, not an LLM judgment or source fact.

## Invariants

1. Acceptance never changes `authority_tiers`.
2. Acceptance does not add votes or resolve a joint-top tie by itself.
3. Acceptance does not establish objective correctness.
4. Delegation preserves structural character.
5. Sabotage affects coordination/behavior, not authority.
6. Controlled tests do not infer acceptance from prose keywords.
7. Translation diagnostic ground truth is hidden from RacioInterpreter.
8. B10 behavior resolution cannot consume the B9 acceptance-fidelity audit,
   hidden native motives, confidence or character weights.
9. A B10 behavior status remains visible even when its option equals both the
   mandate and conscious option.

## B9 record-only audit note

B9 uses only the frozen `R_to_E` or `R_to_I` relation, with Racio as observer,
for the corresponding source-mind assessment. This is a record-only link with
`implementation_hypothesis` status. It computes no composite score or threshold
and cannot filter observations, alter an interpreter prompt or output, change a
`TranslationGap`, or affect governance or behavior.

The plan's `test_high_fidelity_reduces_translation_gap` is permitted only as a
fully disclosed controlled pair of scripted fixtures. It cannot prove a general
monotonic or causal relationship. Semantic mapping remains open under
`OQ-TRANSLATION-001` and `OQ-ACCEPTANCE-001`/`002`; model-backed interpretation
and behavior mapping remain outside B9.

## B10 explicit behavior-policy note

B10 freezes the first replaceable behavior policy as
`b10-behavior-resolution-table-v1`, revision `1`, with status
`implementation_hypothesis`. It is paired with
`b10-conscious-commit-table-v1`, revision `1`. The exhaustive ordered table is
stored in `knowledge/canon_v2/acceptance.yaml`; the order is part of the
contract, not an incidental code branch.

An actionable mandate has status `resolved`, `delegated` or
`functionally_overridden` and a non-null option. Unknown acceptance or a
non-actionable mandate has highest priority and yields a deferred conscious
decision plus unresolved behavior. For an actionable mandate:

- `accepting` commits and executes the mandate;
- `mixed` commits and executes it when R is a structural source or a verified
  interpretation of a structural E/I source selects the mandate option;
- otherwise `mixed` commits Racio's own available native option and records
  oscillating behavior, or defers and delays when Racio has no option;
- `conflicted` commits Racio's own available option while behavior is
  sabotaged, including when that option happens to equal the mandate; without a
  Racio option, both decision and behavior are blocked.

The table receives `AcceptanceState.overall_mode` explicitly. It does not
derive the mode from directed-relation scores and does not use thresholds,
keywords, confidence, character weights, the B9 acceptance-fidelity audit,
`TranslationGap` or hidden native motives. It cannot change the governance
mandate, effective authority or structural character. Exact option equality is
recorded independently from execution status, so agreement can remain visibly
non-accepting and disagreement can remain accepting. Delegated execution keeps
the delegate as operational controller without changing authority tiers.

The resolver verifies the scene- and AcceptanceState-bound interpretation
inputs, reselects the ordered rule, and checks the conscious option against its
declared source (mandate or Racio native conclusion). It does not trust a stored
rule label. Revision-1 row semantics, controller rules, tensions and action
templates cannot be changed under the same policy ID/revision.

This B10 table is an auditable software hypothesis, not a psychological law.
Any future replacement must use a new policy ID or revision and retain the
ability to replay runs made under revision `1`.

## Claim trace

`C-ACCEPT-001`, `C-ACCEPT-002`, `C-ACCEPT-003`, `C-DELEG-001`, `C-STATE-001`, `C-CONSC-001`, `C-GOV-001`, `C-BEHAV-001`, `C-BEHAV-002`.

## Open questions

- How can acceptance be measured reliably from limited evidence?
- Where is the boundary between ordinary disagreement and non-acceptance?
- Which relation dimensions and ranges are stable enough for B2 contracts?
- Which evidence should justify recalibrating or replacing the frozen B10 behavior table without presenting it as theory?

See `knowledge/canon_v2/open_questions.md` (`OQ-ACCEPTANCE-001`, `OQ-ACCEPTANCE-002`, `OQ-RANGE-001`, `OQ-BEHAVIOR-001`).
