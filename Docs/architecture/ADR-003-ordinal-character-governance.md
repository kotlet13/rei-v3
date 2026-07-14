# ADR-003: Character governance is stable and ordinal

Status: Accepted
Date: 2026-07-13
Scope: B1 documentation contract

Acceptance of this ADR does not change the claim statuses recorded in `knowledge/canon_v2/claims.jsonl`.

## Context

The archived runtime uses decimal profile weights and situational bonuses. Source review instead supports a stable relative rank: the magnitude of a numerical difference is not decisive, current state does not redefine character, and equal-rank cases require explicit rules.

## Decision

Represent character as `authority_tiers: list[list[MindId]]`, with one of four governance rules: `single_top`, `ordered_top`, `joint_top`, `two_of_three`.

All 13 profiles are canonical:

```text
R>(E=I)  E>(R=I)  I>(R=E)
(R=E)>I  (R=I)>E  (E=I)>R
R>E>I    R>I>E    E>R>I    E>I>R    I>R>E    I>E>R
R=E=I
```

Governance operates on the same frozen native bundle. Single/ordered top profiles give the highest tier the mandate while retaining lower-tier objections. For a disagreeing leading pair, the initial deterministic policy records the mandate as `unresolved`; a universal resolution rule remains open, and the subordinate mind is never an automatic tie-breaker. At `R=E=I`, two equal conclusions prevail, all three equal conclusions produce `simulated_spoznanje`, and three different conclusions remain unresolved.

Functional unavailability is represented separately as effective authority and never mutates structural character. Bounded pair negotiation of at most two additional information-bearing rounds is a configurable implementation hypothesis, not source canon.

## Rejected alternatives

- Decimal weights or a smooth weighted compromise.
- `profile_weight * confidence`.
- Situational, keyword, stress, mood or loudness bonuses that change rank.
- An extra Racio vote because Racio is conscious.
- A subordinate mind, LLM or hidden policy as pair tie-breaker.
- Treating delegation or temporary task control as a character change.

## Consequences

- Governance is deterministic, inspectable and replayable.
- “Unresolved” is a valid state rather than an error to hide.
- Structural rank, current state, delegation and functional availability have separate records.
- The same person-character can yield different decisions through different worlds and histories.

## Invariants

1. Intensity, confidence, mood, stress and keywords never alter structural tiers.
2. Functional override alters effective tiers only for explicit unavailability.
3. Delegation preserves structural authority.
4. Lower minds remain visible as objections, corrections or execution capacity.
5. Joint-top conflict has no automatic tie-breaker.
6. `R=E=I` uses one vote per native conclusion; Racio receives no bonus.
7. `simulated_spoznanje` requires convergence of all three conclusions, not merely the same action.

## Claim trace

`C-CHAR-001`, `C-CHAR-002`, `C-CHAR-003`, `C-CHAR-004`, `C-CHAR-005`, `C-CHAR-006`, `C-ARB-001`, `C-ARB-002`, `C-DELEG-001`, `C-STATE-001`, `C-MINDS-001`, `C-PAIR-001`, `C-GOV-001`, `C-GOV-002`, `C-SPOZ-001`, `C-LEGACY-001`.

## Open questions

- Sources do not yet provide a universal rule for every disagreement between two equal leading minds.
- What evidence distinguishes delegation, substitution and functional unavailability?
- What availability threshold and authorization may create effective override?
- How should legacy decimal-weight reports be displayed without reintroducing weights into decisions?

See `knowledge/canon_v2/open_questions.md` (`OQ-PAIR-001`, `OQ-DELEGATION-001`, `OQ-AVAILABILITY-001`, `OQ-LEGACY-001`).
