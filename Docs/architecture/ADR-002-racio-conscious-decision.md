# ADR-002: Racio mediates conscious decision and narration

Status: Accepted
Date: 2026-07-13
Scope: B1 documentation contract; B5 native Racio implementation; B9 interpreter contract

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

## Claim trace

`C-PERCEPT-001`, `C-CONSC-001`, `C-CONSC-002`, `C-RACIO-001`, `C-RACIO-003`, `C-CONSC-003`, `C-GOV-001`, `C-BEHAV-001`, `C-EGO-001`.

## Open questions

- How should translation fidelity be evaluated without making hidden chain-of-thought an API?
- What is the exact B2 schema for `RacioInputPacket`?
- Which interpretation alternatives and uncertainty scales are stable across providers?

See `knowledge/canon_v2/open_questions.md` (`OQ-TRANSLATION-001`, `OQ-RACIO-001`, `OQ-RANGE-001`).
