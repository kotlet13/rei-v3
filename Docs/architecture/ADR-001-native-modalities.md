# ADR-001: Native modalities for Racio, Emocio and Instinkt

Status: Accepted
Date: 2026-07-13
Scope: B1 documentation contract; B5–B8 native processor and renderer implementations; B9 communication contract

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
8. Instinkt body state and associative memory cannot read or mutate structural
   character or authority tiers.

## B6 implementation note

B6 implements Emocio as a deterministic structured-scene processor. A
profile-blind packet is compiled into current, desired, broken and per-option
rollout scenes before an equal-weight 11-dimension fixture valuation selects a
unique maximum or explicitly abstains on a tie. The rule uses exact structured
atoms and no text keyword classifier. It is an uncalibrated
`implementation_hypothesis`, not a claim about human affect.

The native conclusion is frozen before the optional renderer boundary.
`NullRenderer` is the B6 adapter; no image model is selected or invoked. Any
renderer output is ungrounded presentation data and cannot revise packet,
visual state, valuation or native option.

## B7 implementation note

B7 connects the optional boundary to a provider-neutral, per-scene render
request and a lazy local Diffusers adapter. A render request closes the frozen
scene hash, exact provider/model and pipeline revision, runtime/load settings,
prompt, dimensions, deterministically derived per-scene seed and optional
img2img source provenance before execution. The
batch outcome retains successful, partial, failed and disabled attempts with
their call records; no renderer result is fed back into scene compilation or
valuation.

The local PNG store writes without replacing an existing path and verifies the
actual byte SHA-256, complete chunk CRC/IDAT/IEND structure and dimensions.
Img2img source bytes are reverified before the call.
The image ID binds the request ID and content digest, while every generated
image remains `grounded=false`. Provider failure or invalid output is recorded
after the native conclusion and leaves its ID/hash and selected option intact.

No final image model is selected. Runtime configuration must supply a model
repository and immutable 40-hex Hub commit. The optional pinned stack verified
from official releases on 2026-07-13 is PyTorch 2.13.0, Diffusers 0.39.0,
Transformers 5.13.0, Accelerate 1.14.0, safetensors 0.8.0 and Pillow 12.3.0.
All B7 tests use an injected byte-only fake backend, so no model-backed image
generation or GPU execution is part of the phase verification.
Model files must be acquired separately; the runtime adapter uses
`local_files_only=true` and never downloads weights during a render call.

## B8 implementation note

B8 implements Instinkt as a bounded deterministic virtual-body simulator, not
as a textual adviser. Its entrypoint accepts a scene, a profile-blind packet,
one explicit typed `OptionBodyEffect` per packet option, a source `BodyState`
and optional bounded associative memory. It does not accept character/profile
authority and does not classify raw scene or cue text. Every numeric rule in
this section is an uncalibrated `implementation_hypothesis`, not an empirical
psychological, medical or physiological claim.

The body has 13 fixed finite dimensions in `[0, 1]`; input deltas are in
`[-1, 1]`. A rollout defaults to exactly 3 steps (configurable 1–8),
`max_options` defaults to 16 (1–32), and the absolute per-step delta defaults
to `0.25` (greater than zero and at most one). For every dimension and step:

```text
step_delta = clamp(effect_total_delta / rollout_steps,
                   -max_abs_delta_per_step,
                   +max_abs_delta_per_step)
next = clamp(previous + step_delta, 0, 1)
```

There is no convergence or unbounded agent loop. Transitions replay from their
typed effect and content-addressed configuration. A rollout must contain the
configured number of contiguous transitions and must replay its trajectory,
memory inputs, loss and recoverability within absolute tolerance `1e-12`.

The initial loss and recovery functions are:

```text
predicted_loss = clamp01(
  0.50*base_predicted_loss
  + 0.15*(1-physical_integrity) + 0.10*pain + 0.10*tension
  + 0.05*(1-boundary_integrity) + 0.05*(1-resource_security)
  + 0.05*(1-attachment_security) + 0.20*loss_memory_strength)

recoverability = clamp01(
  0.50*base_recoverability
  + 0.15*energy + 0.10*escape_availability + 0.10*predictability
  + 0.05*trust + 0.05*attachment_security + 0.05*resource_security
  - 0.20*loss_memory_strength)
```

The core loss, recovery and conclusion-intensity weight groups must each sum
to `1.0`. `loss_memory_strength` is the maximum `retrieval_score` among the
retrieved matches that carry an experienced loss, or `0.0`; raw memory
intensity cannot bypass retrieval quality.

Associative memory defaults to capacity 32 (1–256), retrieval limit 4 (1–32
and no greater than capacity), minimum effective strength `0.05` in `[0, 1]`,
and a per-call cycle-advance ceiling of 10,000 (configurable 1–1,000,000;
each advance accepts an integer from zero through that ceiling). Matching is
exact after only `strip`/`casefold` normalization, deduplication and sorting.
It uses:

```text
effective_strength = clamp01(felt_intensity - decay*age_cycles)
overlap_ratio = exact_overlap_count / unique_signature_token_count
retrieval_score = effective_strength * overlap_ratio
```

Matches sort by score descending, strength descending and association ID
ascending, then truncate to the retrieval limit. Capacity eviction removes the
lowest current effective strength, then the oldest insertion, then the lowest
association ID; duplicate association IDs are rejected.

Protective policy minimizes:

```text
protective_cost = predicted_loss
  + 0.25*(1-recoverability)
  + 0.15*final_tension
  + 0.10*final_uncertainty
```

The default penalties sum to `0.50`, and configuration rejects a penalty sum
above `0.50`; the resulting cost contract is `[0, 1.5]`. Every option within
`tie_epsilon` of the minimum is tied. The default epsilon is `1e-12` (allowed
`[0, 1]`); two or more tied options produce explicit `abstained_tie` with no
secondary tie-break. An empty option set produces `abstained_no_options`, no
scores or decisive rollout, and conclusion intensity `0.0`.

For a selected rollout, conclusion intensity is
`clamp01(0.60*predicted_loss + 0.25*final_tension + 0.15*final_arousal)`;
a tie uses the maximum tied-rollout intensity. Manifestation uses the decisive
rollout's final body state when selected and the original source state when
abstaining, with:

```text
felt_tension = tension
fear_intensity = clamp01(0.50*intensity + 0.30*tension + 0.20*arousal)
attachment_pull = clamp01((1-attachment_security)*intensity)
withdrawal_urge = intensity for withdraw or seek_safety, otherwise 0
freeze_intensity = intensity for freeze, otherwise 0
boundary_alarm = clamp01(1-boundary_integrity)
```

The configuration, typed effect, each transition, association match, rollout,
policy and manifestation are content-addressed and hash-validated. Lineage
closes the exact packet, source body, effect, configuration, association
records, conclusion and—when selected—decisive rollout. Manifestation exposes
only a structured tendency label rather than an inner monologue. All artifacts
are frozen, and neither body dynamics nor memory can modify structural
character or authority tiers.

## B9 communication-contract note

B9 consolidates manifestation, interpretation and diagnostic comparison in
`knowledge/canon_v2/communication.yaml`. Emocio and Instinkt expose only bounded
manifestations after their native conclusions are frozen. Emocio projection,
structured observation, content lineage, scripted interpretation, exact typed
action-tendency fidelity and distortion classification are replaceable
`implementation_hypothesis` policies. Images remain ungrounded, while B8's
Instinkt manifestation is consumed without recomputing its conclusion.

The same contract excludes native conclusions, the bundle, gap and hidden
motive from `RacioInterpreter`; preserves wrong or absent translation; and uses
only `R_to_E` or `R_to_I` for a record-only acceptance audit. It selects or
calls no local LLM, GPU-backed interpreter or model. A deterministic no-model
`FakeVisionLanguageInterpreter` only proves exact provider lineage for visible
Emocio image IDs; its text remains explicitly renderer-added and ungrounded.
Semantic calibration stays open, and committer, narrator, conscious decision
and behavior remain outside B9.

## Claim trace

`C-CHAR-002`, `C-ROUTE-001`, `C-RACIO-001`, `C-EMOCIO-001`, `C-INSTINKT-001`, `C-PERCEPT-001`, `C-CONSC-001`, `C-NATIVE-001`, `C-NATIVE-002`, `C-PROV-001`, `C-BUNDLE-001`, `C-EMOCIO-003`, `C-EMOCIO-004`, `C-INSTINKT-003`, `C-INSTINKT-004`.

## Open questions

- What is the minimum observable proof of three independent routes without exposing hidden chain-of-thought?
- Which visual valuation dimensions survive empirical architectural evaluation?
- Which virtual-body dynamics are sufficient without making medical claims?
- Which canonical serialization and hash algorithm will B2 adopt?

See `knowledge/canon_v2/open_questions.md` (`OQ-NATIVE-001`, `OQ-EMOCIO-001`, `OQ-INSTINKT-001`, `OQ-SCHEMA-001`).
