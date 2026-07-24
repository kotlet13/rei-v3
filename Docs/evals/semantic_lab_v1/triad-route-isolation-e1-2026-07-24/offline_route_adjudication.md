# TRIAD-ISO-R1 offline route adjudication

TRIAD-ISO-E1 remains a frozen historical mixed result. This addendum contains no model calls, native processor reruns, character replay, promotion claim, or global REI score.

## Seal reconciliation

- `ce64…` is the TRIAD-S2 seal stored in `Docs/evals/semantic_lab_v1/triad-response-screen-v2-2026-07-23/pre_call_seal.json`.
- The committed TRIAD-ISO-E1 seal is `1360554ad44b64f1aa8cdeb4e92d3bf278b8d812d381f0685e4e4595ccf86080`.
- Verdict: operator-response cross-phase misattribution. No E1 seal artifact or seal calculation is defective.

## Formal JSON-mode verification

- Status: `passed`.
- Pydantic validation mode: JSON.
- Domain validators relaxed: no.
- Frozen files: 19; byte inventory unchanged: true.
- Frozen inventory SHA-256: `ea6bb560b646839dae38961deacf24b8ce370642d3965b767c18759876f44d1b`.

## Racio material rejection

- Exact failure: `fact_evidence_mismatch`.
- `evidence_ids_used` contains `utility_ev_rarity`, while `facts_used` does not contain the corresponding rarity fact. The citation therefore falls outside the allowed citation union for used facts.
- Unsupported evidence IDs: `["utility_ev_rarity"]`.
- Used facts lacking required citations: `[]`.
- The exact fact/evidence contract remains unchanged; the original output remains rejected. The prospective diagnostic contains no thinking.

## Racio commensurability

- Current material packet: `partially_commensurable`.
- Budget base: `under_specified`.
- EUR 1200 trip spend and EUR 900 bounded benefit share a currency unit, but reserve impact remains under-specified without an explicit or bounded absolute budget base.
- Under-specification requires explicit uncertainty and a bounded confidence; it does not hardcode abstention.
- A net-benefit claim is forbidden whenever compared quantities lack a common unit.

## Emocio route diagnosis

- E1 produced 4/4 Emocio abstentions.
- Utility book/local and protective book/local were exact aggregate ties.
- Distant and local attraction both collapsed to 1.0 although the local route was explicitly smaller.
- Movement remained 0.0 despite structured movement fields.
- Desired-scene match remained 0.0.
- Companion presence caused novelty/breakthrough aggregate drift despite the explicit `no extra enjoyment` boundary.
- Isolation stability and semantic fidelity are distinct: utility identity is an isolation PASS; Emocio cognition is not yet a semantic PASS.

## Research-only Emocio representation replay

| Case | Old ties | New ties | Old option | New option | Old abstention diagnosis |
|---|---|---|---|---|---|
| `trip_racio_utility_material` | `utility_trip_book,utility_trip_local` | `` | `None` | `utility_trip_book` | `representation_collapse` |
| `trip_racio_utility_pleasure` | `utility_trip_book,utility_trip_local` | `` | `None` | `utility_trip_book` | `representation_collapse` |
| `trip_protective_context_exposed` | `trip_book,trip_local` | `` | `None` | `trip_book` | `representation_collapse` |
| `trip_protective_context_supported` | `trip_book,trip_local` | `` | `None` | `trip_book` | `representation_collapse` |

The corrected projection uses stable typed relations for self position, scene target, ordinal attraction, movement, immediacy, obstacle state, and desired/broken relations. It contains no expected winner or option-specific tuning. An option change is neither success nor failure by itself; source-grounded route capacity is the result.

## Instinkt route adjudication and sensitivity

- Accepted E1 isolation result: exposed → supported changed the route; book protective cost fell from 0.658125 to 0.554750. An option flip was not required.
- `discretionary budget` does not license `necessary cash reserve`.
- Known verified distance is distinct from unfamiliar/uncertain danger.
- Non-refundable resource exposure remains independently represented.

| Case | Original option | Corrected option | Selection changed |
|---|---|---|---|
| `trip_racio_utility_material` | `utility_trip_local` | `utility_trip_local` | false |
| `trip_racio_utility_pleasure` | `utility_trip_local` | `utility_trip_local` | false |
| `trip_protective_context_exposed` | `trip_home` | `trip_home` | false |
| `trip_protective_context_supported` | `trip_home` | `trip_book` | true |

The sensitivity replay retained every frozen consequence fact, removed only unsupported semantic upgrades, and did not tune numeric deltas for an option flip.

## Corrected unsealed candidate

- SHA-256: `77724ec00a06a6da5d0ff8d42443f01704173c633d7033359f14807c683abfa3`.
- Utility cases add an explicit EUR 4800 discretionary-budget base.
- Emocio carries typed semantic route relations.
- Instinkt retains the discretionary-budget meaning and does not treat verified distance as automatic danger.
- Status: unsealed; execution is not authorized.

## Stop state

- Model calls: 0.
- Character replay rows: 0.
- Remaining six route-isolation cases: not executed.
- G4: not started.
- PR/merge: not performed by this phase.
