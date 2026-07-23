# TRIAD-ISO-P1 route-isolation corpus preflight

Date: 2026-07-23

Candidate:
`Docs/evals/semantic_lab_v1/triad-route-isolation-p1-2026-07-23/route_isolation_corpus_candidate.json`

Candidate status: `candidate_unsealed`

Execution authorized: `false`

Model calls: `0`

Replay: `0`

Character replay: `0`

## Result

**PASS**

The candidate contains five contrast-pair families and ten fully expanded
source cases. Model-free structural and manual semantic checks found no
pair-invariant violation, answer leakage, profile leakage, cross-mind desired
goal, non-acceptance intensification, option-order dependency, or additional
English fact.

This pass establishes corpus preflight only. It is not a pre-call execution
seal, native-route result, untouched holdout, promotion evidence, or execution
authorization.

## Preflight method

The preflight used a bounded read-only PowerShell validation over the candidate
JSON plus manual source/projection review. No new validator framework or test
module was added.

Automated checks:

- valid JSON and declared counts;
- exactly two variants per pair;
- exact changed fact/unknown ID set equals the pair’s declared variant set;
- all non-target fact and unknown texts are byte-equal within each language;
- option IDs, descriptions, and order are byte-equal within each pair;
- SL/EN fact, unknown, and option ID parity;
- required Racio, Emocio, and Instinkt packet fields present in every case;
- every public option covered by Racio consequences, Emocio visible changes,
  and Instinkt consequences;
- all Emocio/Instinkt evidence references resolve to source evidence IDs;
- set-based option coverage remains identical under reversed option order;
- forbidden answer, profile, and governance keys absent;
- `preferred`, `best`, `safest`, and `compromise` labels absent;
- named non-acceptance intensification phrases absent;
- Emocio desired scenes contain none of the known imported goals checked here:
  stable reserve, safety ranking, enforceability, balanced positions, or
  repayment boundary.

Manual checks:

- each English statement is a hand-written projection of the corresponding
  Slovenian statement and adds no actor, amount, motive, consequence, or
  certainty;
- each explicit Racio benefit names a beneficiary and grounded goal or
  consequence;
- each Emocio desired scene is image/attention/recognition/attraction/movement
  content rather than an imported safety, reserve, or contract objective;
- each Instinkt packet exposes the relevant protected target, loss, trust,
  attachment/care, scarcity, boundary, escape, familiarity, and recoverability
  fields, using `not_relevant` or a bounded unknown when inactive;
- none of the pairs encodes a required option outcome.

## Count and identity checks

| Check | Result |
|---|---:|
| Pair families | `5` |
| Variants per pair | `2` |
| Total source cases | `10` |
| Public options per case | `3` |
| Model calls | `0` |
| Processor executions | `0` |
| Replays | `0` |
| Character replays | `0` |

## Exact pair diff

### `public_credit_audience`

Changed source fact IDs, and only these:

- `credit_ev_audience`
- `credit_ev_positions`
- `credit_ev_recognition`

Unchanged facts:

- sole-authorship claim;
- timestamped authorship record;
- leader’s official correction mechanism;
- material/enforceability consequences;
- absence of added retaliation.

Unknowns are unchanged. Options are unchanged:
`credit_public_confront`, `credit_private_evidence`,
`credit_no_response`.

The visible variant names the leader and six project-team members, makes
self/rival position explicit, and makes group recognition possible. The
audience-absent variant contains only self, colleague, and leader and has no
wider recognition. No public-confrontation result is prescribed.

### `trip_protective_context`

Changed source fact IDs, and only these:

- `protective_ev_companion`
- `protective_ev_environment`
- `protective_ev_lodging_transport`
- `protective_ev_return_path`

Changed bounded unknown ID:

- `protective_unknown_return`

The return-path unknown exists only where the physical return route is not
confirmed. Unchanged facts:

- 38-percent price;
- financial non-refundability;
- destination attraction;
- EUR 400 training replacement;
- rarity.

The future-cost unknown is unchanged. Options are unchanged:
`trip_book`, `trip_local`, `trip_home`.

The exposed variant is alone, unfamiliar, provider-unverified, and
return-uncertain. The supported variant has a trusted close companion,
documented route, verified lodging/transport, and confirmed physical return.
No inference is made that either context requires a particular option.

### `loan_attachment_distance`

Changed source fact IDs, and only these:

- `loan_ev_relationship`
- `loan_ev_attachment`

Unchanged facts:

- genuine EUR 9000 repair need;
- two late repayments;
- 45-percent reserve exposure;
- EUR 3000 written-contract terms;
- absence of strategic/material relationship benefit for Racio.

All unknowns are unchanged. Options are unchanged:
`loan_full`, `loan_limited_contract`, `loan_decline`.

The close variant contains twelve years of shared history, strong attachment,
and reported fear of relationship loss. The distant variant contains three
meetings and no shared attachment history. Genuine need remains present in both,
so direct-source Instinkt compassion is not reduced to close attachment.

### `trip_racio_utility`

Changed source fact IDs, and only these:

- `utility_ev_benefit`
- `utility_ev_beneficiary`

Changed bounded unknown ID:

- `utility_unknown_demo_result`

The material variant has a signed buyer-demonstration invitation, a bounded
studio saving of up to EUR 900, and an explicit studio beneficiary. The
pleasure variant explicitly has no strategic/material benefit and names self
only as recipient of the pleasurable experience.

Unchanged facts:

- destination and attraction;
- EUR 1200 / 25-percent cost;
- rarity;
- 24-hour / 10-percent cancellation rule;
- trusted close companion;
- verified physical safety.

The future-cost unknown is unchanged. Options are unchanged:
`utility_trip_book`, `utility_trip_local`, `utility_trip_home`.

No public status or recognition fact is added to either variant.

### `factory_public_status`

Changed source fact IDs, and only these:

- `factory_ev_audience`
- `factory_ev_status`

Unchanged facts:

- 11 C rise in six minutes;
- 8 C sensor difference;
- three-minute window;
- equipment-damage possibility;
- EUR 75000 shutdown loss;
- absence of added retaliation or punishment.

All unknowns are unchanged. Options are unchanged:
`factory_shutdown`, `factory_verify`, `factory_continue`.

The visible variant names the plant manager and eight shift members and makes
non-material operator recognition visible. The anonymous variant records the
same technical event without attribution or status effect. Technical
responsibility, pay, danger, and financial consequences remain unchanged.

## Pair invariants

| Pair | SL option contract | EN option contract | Non-target facts | Result |
|---|---|---|---|---|
| `public_credit_audience` | Exact match | Exact match | Exact match | Pass |
| `trip_protective_context` | Exact match | Exact match | Exact match | Pass |
| `loan_attachment_distance` | Exact match | Exact match | Exact match | Pass |
| `trip_racio_utility` | Exact match | Exact match | Exact match | Pass |
| `factory_public_status` | Exact match | Exact match | Exact match | Pass |

## Leakage audit

### Answer and authority leakage

Absent:

- expected option;
- expected action;
- leading mind;
- gold route;
- profile data;
- governance data;
- outcome ranking labels;
- an assertion that public confrontation, staying home, lending, a middle
  option, or shutdown must win.

### Non-acceptance intensification

The corpus is in core-route mode.

Absent:

- manufactured compulsive external confirmation;
- excessive aggression;
- destructive public defeat;
- inflated superiority display;
- punitive withdrawal;
- extreme envy expression.

Audience contexts are explicitly neutral or supportive, and no retaliation
danger is added. Attack/obstacle-removal capacity is represented only as
ordinary option movement where grounded.

### Cross-mind desired-goal contamination

| Pair | Emocio desired-scene boundary | Result |
|---|---|---|
| `public_credit_audience` | Self-position, named observer, recognition, and visible image correction; no abstract balance | Pass |
| `trip_protective_context` | Attraction, self-centered route image, and movement; safety context is not an attraction marker | Pass |
| `loan_attachment_distance` | Immediate face-to-face image and visible act; reserve and contract are not desired markers | Pass |
| `trip_racio_utility` | Identical attraction/movement image in both variants; strategic benefit is absent from the Emocio desired scene | Pass |
| `factory_public_status` | Decisive visible action and recognition where present; damage/loss is not converted into an Emocio goal | Pass |

Instinkt care is not converted into `always lend`, and Racio benefit is not
derived from compassion, rarity, attraction, or safety.

## Operational English projection

For every case:

- SL and EN evidence ID sets are identical;
- SL and EN unknown ID sets are identical;
- SL and EN option ID order is identical;
- numeric values, actors, uncertainty, and consequence bounds are preserved;
- the English projection does not add motives or outcomes;
- route packets reference IDs rather than relying on translated labels.

Manual semantic review: **Pass**.

## Route packet completeness

All ten cases explicitly contain:

- Racio facts, unknowns, time/sequence, goal, beneficiary,
  material/strategic consequences, opportunity cost, and grounded
  enforceability/control;
- Emocio current/desired/broken scenes, self-position, audience,
  attention/recognition, rival/obstacle, attraction/enjoyment,
  movement/immediacy, and a visible change for every option;
- Instinkt protected target, danger, possible loss, trust, attachment/care,
  scarcity, boundary, escape/reversibility, familiarity, prior association,
  recoverability, and a grounded consequence for every option.

Inactive fields use `not_relevant`; unresolved fields remain bounded unknowns.
Every route has enough information to produce a route or legitimately abstain.
This is an input-capacity judgment only.

## Option-order invariance

The preflight reversed each case’s option-ID sequence in memory and rechecked:

- source option set;
- Racio consequence coverage;
- Emocio visible-change coverage;
- Instinkt consequence coverage.

Coverage remained identical for all ten cases. This check establishes
order-independent corpus structure only; no processor was executed.

## Bounded limitations

- The isolation target is primary, not metaphysically exclusive. For example,
  a trusted companion can be visible to Emocio as well as protective for
  Instinkt. The corpus prevents ungrounded cross-mind goals but does not assume
  a source fact can be perceived by only one mind.
- The English projection has been manually audited, not certified by a
  translation model.
- Candidate packets are not sealed and may still be rejected during human
  semantic review.
- No option quality or native response quality has been measured.

## Stop state

TRIAD-ISO-P1 ends at candidate preflight. No execution seal, provider call,
processor execution, replay, character replay, image generation, G4 work,
merge, or PR is included.
