# ADR-004: Ego is a temporal composition, not an agent

Status: Accepted
Date: 2026-07-13
Scope: B1 documentation contract

Acceptance of this ADR does not change the claim statuses recorded in `knowledge/canon_v2/claims.jsonl`.

## Context

REI material describes the experienced “I” and world as arising through the three minds. Later synthesis treats Ego as their result rather than an additional processor. Modeling Ego as another LLM integrator would add a fourth source of preference and erase the distinction between a cycle result and a life-spanning pattern.

## Decision

Source-supported boundary: Ego is derived from the three minds and is not a fourth processor or independent decision-maker. This architecture's temporal Measure/Trace/Snapshot representation is an accepted software operationalization with status `implementation_hypothesis`, not a direct-source claim.

Ego has no native processor, sensory packet, proposal, vote or decision API. It is represented through derived longitudinal artifacts:

- `EgoMeasure`: one full REI cycle;
- `EgoTrace`: append-only history of measures and correction events;
- `EgoCompositionSnapshot`: a derived reading of recurring motifs, conflicts, translation errors, tensions, commitments and `simulated_spoznanja`;
- modality-specific projections of history back to Racio, Emocio and Instinkt.

Every snapshot cites the measure IDs that support it. Previous measures are immutable; corrections are new events. An optional `EgoReflector` may produce sourced hypotheses only. It cannot participate in the current decision or modify the native bundle, governance mandate, conscious decision or behavior.

## Rejected alternatives

- `EgoAgent`, `EgoVote`, `EgoPreferredOption`, `EgoLeadingMind` or `EgoDecisionMaker`.
- A fourth LLM Ego Integrator.
- Ego as Racio or as an objective observer.
- Ego reduced to a single `DecisionResultant`.
- A mutable summary that rewrites history.
- “Življenje” implemented as an agent, prompt or decision-maker.

## Consequences

- One-cycle resultanta and longitudinal identity composition are distinct.
- Provenance, history and correction events become first-class artifacts.
- R/E/I can receive different projections of the same trace without a fourth opinion.
- Reflection remains auditable hypothesis generation, not governance.
- Exact projection and snapshot algorithms remain B2+ implementation hypotheses.

## Invariants

1. Ego creates no `MindProposal` or native conclusion.
2. Ego has no vote, preferred option, leading mind or decision method.
3. Each measure represents one cycle and is immutable once appended.
4. Corrections append; they never overwrite a previous measure.
5. Snapshots are derived, cite evidence measure IDs and are not sources of truth.
6. Projections are modality-specific and do not add a fourth judgment.
7. Reflector output cannot affect the current cycle.

## Claim trace

`C-WORLD-001`, `C-MINDS-001`, `C-SPOZ-001`, `C-RESULT-001`, `C-EGO-001`, `C-EGO-002`, `C-EGO-003`, `C-LIFE-001`, `C-SAFETY-001`.

## Open questions

- Which Ego fields are canonical concepts and which are descriptive software conveniences?
- How is a composition snapshot calculated reproducibly from a trace?
- What are the exact R/E/I projection schemas and update semantics?
- How should the metaphor of “Jaz in its world” relate to temporal composition?
- The metaphysical role of “Življenje” remains outside executable scope.

See `knowledge/canon_v2/open_questions.md` (`OQ-EGO-001`, `OQ-EGO-002`, `OQ-PROJECTION-001`, `OQ-LIFE-001`).
