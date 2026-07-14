# ADR-002: Racio mediates conscious decision and narration

Status: Accepted
Date: 2026-07-13
Scope: B1 documentation contract; B5 native Racio implementation; B9 interpreter contract; B10 conscious commitment and narration

Acceptance of this ADR does not change the claim statuses recorded in `knowledge/canon_v2/claims.jsonl`.

## Context

REI sources distinguish Racio's direct access to words and consciousness from Emocio's and Instinkt's non-verbal processing. At the same time, character authority may belong to any mind. A single “decision” object would collapse native origin, structural authority, conscious commitment and explanation.

## Decision

Separate four Racio responsibilities:

- `RacioNativeProcessor`: Racio's autonomous native conclusion;
- `RacioInterpreter`: conscious inference from E/I manifestations;
- `RacioCommitter`: creation of `ConsciousDecision`;
- `RacioNarrator`: later explanation and self-narrative.

Every `ConsciousDecision` has `made_by="R"`. This identifies the conscious channel, not necessarily the source of the governing conclusion. The interpreter sees manifestations, not hidden E/I native motives. It may understand correctly, partially, incorrectly, rationalize, minimize or omit. The narrator cannot mutate the frozen bundle, governance mandate, conscious decision or behavior.

## Rejected alternatives

- Directly conscious textual speech from Emocio or Instinkt.
- Treating Racio as the whole Ego or as automatically correct.
- Giving Racio extra governance authority because it is conscious.
- Converting a governance mandate directly into a conscious decision without interpretation.
- Combining committer and narrator so a plausible story can rewrite the decision.

## Consequences

- Native source, governance mandate, conscious decision, behavior and stated reason remain separate.
- Racio can consciously adopt an E/I-led mandate while misdescribing its motive.
- Translation fidelity and rationalization can be measured after the fact.
- A Racio decision can diverge from governance or behavior without silently changing character.

## Invariants

1. `ConsciousDecision.made_by == "R"`.
2. Direct consciousness gives no extra character vote or truth privilege.
3. Interpreter input excludes diagnostic hidden-motive ground truth.
4. E/I native conclusions remain unchanged by interpretation.
5. Narration is downstream and read-only with respect to decision and behavior.
6. Ego is neither Racio nor a fifth Racio function.
7. B10 commitment branches only on the explicit typed inputs listed in the
   policy and never on confidence, prose keywords or hidden native motives.
8. A coincidentally equal option does not let narration or behavior hide
   non-acceptance.

## B5 implementation note

B5 implements only `RacioNativeProcessor`. Its packet and conclusion are
content-addressed and profile-blind, and facts, unknowns and causal steps remain
separate structured fields. Exact evidence citations are required for supplied
facts. The deterministic provider is an explicitly positional infrastructure
fixture, not a semantic decision model. The optional `TextReasoner` adapter
accepts strict JSON and records the provider result ID and hash. No concrete LLM
is selected in B5, and interpreter, committer and narrator remain downstream.

## B9 interpreter-contract note

B9 specifies only `RacioInterpreter` and its separate `TranslationGap`
evaluator. The consolidated contract is
`knowledge/canon_v2/communication.yaml`. The interpreter receives bounded E/I
manifestations and public observations, never the conclusion bundle, native
conclusions, gap or hidden motive. A wrong, partial or absent translation stays
observable. The no-provider scripted fixture and exact typed action-tendency
comparison are replaceable `implementation_hypothesis` policies; motive strings
remain diagnostic. No local LLM, GPU-backed interpreter or model is selected
or called. The no-model fake VLM is only a lineage fixture for visible Emocio
images and cannot supply native truth. Committer, narrator, conscious decision
and behavior remain outside B9.

## B10 conscious-runtime note

B10 implements the downstream `RacioCommitter` and `RacioNarrator` without
changing the B9 interpreter boundary. The committer consumes Racio's frozen
native conclusion, a public governance projection that excludes
`hidden_native_motives`, typed E/I interpretations, and the explicit
`AcceptanceState`. It does not receive the native E/I conclusions,
`TranslationGap`, `AcceptanceFidelityAssessment`, character weights or
authority tiers. An omitted or unavailable conscious observation remains a
typed B9 interpretation outcome; it is never replaced with hidden native truth.

The public governance projection also excludes the source mandate and
governance-resolution IDs and hashes because those fingerprints include the
diagnostic hidden motives. Full governance artifacts remain in the diagnostic
trace, while the committer sees a public content-addressed view bound only to
the scene, Racio's own conclusion and the IDs/hashes of the consciously visible
E/I manifestations. Those manifestation references are already public B9
inputs; native E/I conclusion fingerprints remain excluded. Changing only
hidden native motives therefore cannot change that public view. Each
interpretation is wrapped with its exact B9 request, current AcceptanceState
ID/hash and the exact public mandate-view ID/hash. The request's manifestation
references must equal the current bundle's validated public manifestation
references, so cross-scene, cross-run or cross-acceptance reuse is rejected
before commitment even when two runs share a scene ID.

An E/I-led mandate requires one typed B9 interpretation for every structural
E/I source before it can enter conscious commitment. `omitted_b9` and
`unavailable_b9` satisfy the provenance requirement without fabricating an
inference; an empty input does not. A mandate with R as a structural source may
use Racio's own frozen native conclusion without an E/I interpretation.

The initial commitment policy is
`b10-conscious-commit-table-v1`, revision `1`, with status
`implementation_hypothesis`. Its exact ordered rules are recorded in
`knowledge/canon_v2/acceptance.yaml`. Every output still has `made_by="R"`.
The policy may copy a confidence value into a diagnostic field, but confidence,
relation thresholds, prose keywords and provider output do not select a branch.
The policy never recomputes or mutates the governance mandate.

The narration policy is `b10-racio-self-narrative-v1`, revision `1`, also an
`implementation_hypothesis`. It runs only after the frozen conscious decision
and behavior resultant exist. It returns a new content-addressed
`RacioSelfNarrative` bound to their exact IDs and hashes. A narrative may omit
a mind or claim a motive that differs from the governance source, but it has no
field or API that can rewrite the decision, resultant, mandate or native bundle.
No provider, local LLM or GPU call is required by either B10 policy.
Canonical revision-1 table semantics are immutable under their policy IDs;
changed semantics require a new ID or revision and produce a different policy
hash. The behavior resolver recomputes the applicable commitment row from the
bound inputs instead of trusting `applied_rule_id` on an output artifact.

## Claim trace

`C-PERCEPT-001`, `C-CONSC-001`, `C-CONSC-002`, `C-RACIO-001`, `C-RACIO-003`, `C-CONSC-003`, `C-GOV-001`, `C-BEHAV-001`, `C-EGO-001`.

## Open questions

- How should translation fidelity be evaluated without making hidden chain-of-thought an API?
- What is the exact B2 schema for `RacioInputPacket`?
- Which interpretation alternatives and uncertainty scales are stable across providers?
- What evidence should justify replacing or recalibrating the B10 commitment and narration policies?

See `knowledge/canon_v2/open_questions.md` (`OQ-TRANSLATION-001`, `OQ-RACIO-001`, `OQ-RANGE-001`).
