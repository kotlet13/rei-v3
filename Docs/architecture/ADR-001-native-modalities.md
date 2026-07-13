# ADR-001: Native modalities for Racio, Emocio and Instinkt

Status: Accepted
Date: 2026-07-13
Scope: B1 documentation contract

Acceptance of this ADR does not change the claim statuses recorded in `knowledge/canon_v2/claims.jsonl`.

## Context

The archived runtime gives all three minds the same text-shaped input and models each with a textual LLM call. That cannot preserve the REI distinction between symbolic/language processing, visual-scenic processing and embodied/protective processing. Observable behavior also cannot reliably identify the route that produced it.

## Decision

Racio, Emocio and Instinkt are autonomous processors with their own input representation, world, memory, route and native conclusion.

- Racio processes symbols, language, numbers, sequence and explicit consequences.
- Emocio constructs and compares structured current, desired, broken and option-rollout scenes.
- Instinkt evolves virtual body state, associations and protective option rollouts.

In controlled profile simulations, processors are profile-blind. Character governance runs only after all three conclusions have been frozen in one immutable bundle.

Emocio reaches its conclusion before manifestation and Racio interpretation. Optional rendering is subordinate to the structured scene model; generated details remain inferred and cannot become grounded evidence or change the frozen conclusion.

Instinkt reaches its conclusion from body/association state before verbalization. Any verbal fear, danger or protection statement is a Racio interpretation, not Instinkt's literal inner speech. An LLM may later assist a bounded adapter, but it cannot be Instinkt's hidden decision center.

Evidence boundary: source review supports Racio's verbal/numeric route, Emocio's image-oriented route, Instinkt's protective route, and the indirect conscious access of E/I. Structured current/desired/broken scenes, visual valuation, motor rollouts, virtual body, interoception, homeostasis and body rollouts are software operationalizations with `implementation_hypothesis` status.

## Rejected alternatives

- One shared text prompt or textual LLM architecture for all three minds.
- Inferring processor origin from the expected outward action.
- Letting character profile leak into native processor prompts in controlled mode.
- Creating Emocio's conclusion from Racio's description of an image.
- Treating an image generator as Emocio or generated detail as evidence.
- Treating Instinkt as a textual safety adviser.

## Consequences

- Packets, worlds, conclusions and artifacts are modality-specific.
- Native processing can be evaluated independently from governance.
- The same frozen bundle can be replayed across all 13 character profiles.
- Manifestation, interpretation and translation error become separately observable.
- Deterministic adapters are required before external providers are introduced.
- Visual valuation and virtual-body dynamics remain implementation hypotheses until tested.

## Invariants

1. Native processors do not read character rank in controlled mode.
2. A processor route is not inferred from behavior alone.
3. E/I native conclusions precede Racio interpretation.
4. A frozen bundle is immutable.
5. RacioInterpreter does not receive hidden native motives as ground truth.
6. Generated imagery cannot add grounded facts or modify a conclusion.
7. Renderer failure leaves structured Emocio state and conclusion unchanged.

## Claim trace

`C-CHAR-002`, `C-ROUTE-001`, `C-RACIO-001`, `C-EMOCIO-001`, `C-INSTINKT-001`, `C-PERCEPT-001`, `C-CONSC-001`, `C-NATIVE-001`, `C-NATIVE-002`, `C-PROV-001`, `C-BUNDLE-001`, `C-EMOCIO-003`, `C-EMOCIO-004`, `C-INSTINKT-003`, `C-INSTINKT-004`.

## Open questions

- What is the minimum observable proof of three independent routes without exposing hidden chain-of-thought?
- Which visual valuation dimensions survive empirical architectural evaluation?
- Which virtual-body dynamics are sufficient without making medical claims?
- Which canonical serialization and hash algorithm will B2 adopt?

See `knowledge/canon_v2/open_questions.md` (`OQ-NATIVE-001`, `OQ-EMOCIO-001`, `OQ-INSTINKT-001`, `OQ-SCHEMA-001`).
