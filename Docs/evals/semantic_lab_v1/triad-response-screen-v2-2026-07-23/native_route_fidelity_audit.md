# TRIAD-CANON-R1 — source-grounded native-route fidelity audit

Date: 2026-07-23

Branch baseline: `codex/triad-response-screen-v1`

Baseline commit: `f149fdb94e83fdd8fa82973b684dbad70292bfbe`

Model calls: `0`

## Scope and evidence status

This is a model-free fidelity audit before any S2R replay. It does not change or reinterpret frozen TRIAD-S1 or TRIAD-S2 evidence. It does not reconstruct a bundle, execute a processor, replay a character profile, choose an expected option, or make a model-promotion claim.

The audit distinguishes three claim statuses:

- `direct_source`: a close paraphrase of an identified source passage;
- `source_synthesis`: a bounded synthesis of two or more source passages; it is not a verbatim source rule;
- `implementation_hypothesis`: a research contract proposed for operational testing, not an established source truth.

Information architecture is material to the result:

- `knowledge/canon_v2` is the active canonical research trail.
- `knowledge/canon` is historical. In particular, `knowledge/canon/processors_v2.yaml` declares `status: experimental_canon_only` and `runtime_effect: none`; it is used below only as corroborating historical research context.
- The structured Emocio scene, eleven-dimension valuation, typed Instinkt body state, option rollouts, and their selection policies are explicitly implementation hypotheses in the active processor canon. Passing their technical contracts does not establish semantic fidelity.

## Sources reviewed

| Source | Locator used | Role in this audit |
|---|---|---|
| `Docs/REI osnova Racio.docx` | page 1, title and the two paragraphs under the title | Direct Racio identity, route capacities, greed, absence of compassion, and route/behavior distinction |
| `Docs/REI osnova Emocio.docx` | page 1, paragraph under the title | Direct image, novelty, travel, enjoyment, movement, attention, competition, and attack signals |
| `Docs/REI osnova Instinkt.docx` | page 1, paragraph under the title | Direct danger, protection, flight, distrust, care, attachment, fear of loss, and remembered-feeling signals |
| `Docs/REI osnove.docx` | page 1, paragraphs 2–5; page 2, final two paragraphs | Independent systems, person-specific worlds, equal mind value, and contextual strengths |
| `Docs/Eros - pogovori.pdf` | pages 16, 30, 47, 49, 54, 86, 103, 106, 111, 175, and 185 | Direct/synthetic route separation, Emocio images and non-acceptance, Racio calculation, Instinkt danger scanning, withdrawal, and non-acceptance |
| `knowledge/canon_v2/claims.jsonl` | claim IDs `C-RACIO-001/002`, `C-EMOCIO-001/002`, `C-INSTINKT-001/002`, `C-ROUTE-001`, `C-MINDS-001`, `C-WORLD-001`, and `C-ACCEPT-001/002/003` | Active claim status and source trace |
| `knowledge/canon_v2/racio.yaml` | `native_domains`, `input_packet`, `native_conclusion` | Active Racio implementation hypotheses |
| `knowledge/canon_v2/emocio.yaml` | `scene_model`, `valuation`, `native_conclusion` | Active Emocio implementation hypotheses |
| `knowledge/canon_v2/instinkt.yaml` | `input_packet`, `body_state`, `association`, `option_rollout`, `native_conclusion` | Active Instinkt implementation hypotheses |
| `knowledge/canon_v2/acceptance.yaml` | `invariants`, `acceptance_relation`, `nonacceptance_observability` | Active acceptance/non-acceptance separation |
| `knowledge/canon/processors_v2.yaml` | `processors.racio`, `processors.emocio`, `processors.instinkt`, `global_invariants` | Historical experimental processor synthesis only |

The DOCX locators refer to the visible document page and paragraph position, not the ZIP/XML paragraph index. The PDF locators refer to the printed PDF page number.

Frozen audit targets were
`Docs/evals/semantic_lab_v1/triad-s2-candidate-2026-07-23/corpus_candidate.json`
(`cases[*].racio_input`, `emocio_input`, and `instinkt_input`) and
`Docs/evals/semantic_lab_v1/triad-response-screen-v2-2026-07-23/cases/<case_id>/native_outputs.json`
(`racio`, `emocio`, and `instinkt`). They were read as historical execution
evidence and were not edited.

## Route contract: Racio

### Core route claims

| ID | Route claim | Source and locator | Status | Operational boundary |
|---|---|---|---|---|
| R-01 | Racio works from explicit facts and preserves explicit unknowns. | `knowledge/canon_v2/racio.yaml`, `native_domains.facts_and_unknowns`; `knowledge/canon_v2/claims.jsonl`, `C-RACIO-002` | `implementation_hypothesis` | A packet may expose facts and unknowns; an output must not turn an unknown into a fact. |
| R-02 | Words and numbers are native Racio material. | `Docs/REI osnova Racio.docx`, page 1, first paragraph under title; `knowledge/canon_v2/claims.jsonl`, `C-RACIO-001` | `direct_source` | Numeric and textual relations may drive the route without visual or bodily preference. |
| R-03 | Time, sequence, prediction, and planning are native Racio capacities. | `Docs/REI osnova Racio.docx`, page 1, first paragraph under title; `Docs/Eros - pogovori.pdf`, page 54 | `direct_source` | The route should state temporal order and planned consequences when evidence permits. |
| R-04 | Probability is an operational representation of Racio uncertainty, not a sourced requirement for a calibrated numeric probability. | `knowledge/canon_v2/racio.yaml`, `native_domains.planning` and `native_conclusion.uncertainty`; `knowledge/canon_v2/claims.jsonl`, `C-RACIO-002` | `implementation_hypothesis` | Qualitative likelihood is allowed; invented numeric probability is not. |
| R-05 | Racio compares material or strategic benefit and explicit consequences. | `Docs/Eros - pogovori.pdf`, page 47; `knowledge/canon_v2/racio.yaml`, `native_domains.utility_and_consequences` | `source_synthesis` | “Utility” must be tied to an explicit goal, material effect, enforceable position, or strategic consequence. |
| R-06 | Ownership and enforceability are candidate Racio questions where the source event contains claims, contracts, assets, or obligations. | `knowledge/canon_v2/racio.yaml`, `native_domains.facts_and_unknowns`, `causality`, and `utility_and_consequences` | `implementation_hypothesis` | Do not assume a right is enforceable merely because evidence of authorship or a written date exists. |
| R-07 | Leverage and control are candidate strategic variables, not automatic goods. | `Docs/Eros - pogovori.pdf`, page 47; `knowledge/canon_v2/racio.yaml`, `native_domains.utility_and_consequences` | `source_synthesis` | Include them only when evidence identifies what can be controlled and why it serves the explicit goal. |
| R-08 | Opportunity cost belongs in a Racio packet when finite money, time, or options are consumed. | `knowledge/canon_v2/racio.yaml`, `native_domains.planning` and `utility_and_consequences` | `implementation_hypothesis` | The omitted alternative must be grounded; “rare” alone is not utility. |
| R-09 | Long-term consequences are a Racio route signal. | `Docs/Eros - pogovori.pdf`, page 54 | `direct_source` | A long-term consequence must remain distinguishable from a present emotional image or present bodily alarm. |
| R-10 | Self-interest and greed are source-grounded Racio motives. | `Docs/REI osnova Racio.docx`, page 1, first paragraph under title; `Docs/Eros - pogovori.pdf`, pages 103 and 175 | `direct_source` | Greed is not a universal expected choice and must not be converted into “always maximize money.” |
| R-11 | Compassion is not a native Racio motive; another person’s welfare may enter only as an explicit goal, commitment, material consequence, or instrumental benefit. | `Docs/REI osnova Racio.docx`, page 1, first paragraph under title; `Docs/Eros - pogovori.pdf`, page 47 | `source_synthesis` | A need, relationship, or pleasurable image cannot silently become Racio utility. |
| R-12 | The same outward option can result from a different native route. | `Docs/REI osnova Racio.docx`, page 1, second paragraph under title; `knowledge/canon_v2/claims.jsonl`, `C-ROUTE-001` | `direct_source` | Option agreement is not route agreement. |

### Racio contract verdict

The contract is suitable for a next development screen only if every utility item names its explicit beneficiary and goal, every strategic claim has grounded consequences, and unsupported compassion, attraction, safety, or “compromise” language is rejected as route contamination. It must not hardcode Racio to a middle option.

## Route contract: Emocio

### Core route claims

| ID | Route claim | Source and locator | Status | Operational boundary |
|---|---|---|---|---|
| E-01 | Emocio thinks through images and a whole-scene mosaic. | `Docs/REI osnova Emocio.docx`, page 1, paragraph under title; `knowledge/canon_v2/claims.jsonl`, `C-EMOCIO-001` | `direct_source` | Structured scenes are an implementation proxy, not image-native cognition. |
| E-02 | The self occupies the center of Emocio’s own image. | `Docs/Eros - pogovori.pdf`, page 49 | `direct_source` | “Self-centered image” is a scene relation; it does not by itself mean public display or moral selfishness. |
| E-03 | Current, desired, and broken images are source-grounded Emocio distinctions. | `Docs/Eros - pogovori.pdf`, page 30 | `direct_source` | A desired scene must describe an Emocio-native image rather than importing a Racio plan or Instinkt safety target. |
| E-04 | Attention and recognition are Emocio route-relevant, but the need for external confirmation is intensified by non-acceptance. | `Docs/REI osnova Emocio.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, pages 49 and 185 | `source_synthesis` | A screen must vary audience and recognition instead of assuming every Emocio route requires publicity. |
| E-05 | Attraction, enjoyment, and pleasurable experience are native Emocio signals. | `Docs/REI osnova Emocio.docx`, page 1, paragraph under title | `direct_source` | Attraction must be represented as an image/experience signal, not as Racio utility or Instinkt safety. |
| E-06 | Movement, immediacy, improvisation, and new experience are native Emocio signals. | `Docs/REI osnova Emocio.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, page 54 | `direct_source` | Movement can support several options; it cannot be equated with a specific label. |
| E-07 | Competition is a core Emocio route signal. | `Docs/REI osnova Emocio.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, page 16 | `direct_source` | Competition need not imply public humiliation or aggression. |
| E-08 | Visible victory and status are a bounded synthesis of centrality, competition, recognition, and surpassing a rival. | `Docs/Eros - pogovori.pdf`, pages 16, 49, 86, and 106 | `source_synthesis` | A status/victory claim must name the observer, rival, and visible change. |
| E-09 | Emocio seeks immediate realization of the desired image. | `Docs/Eros - pogovori.pdf`, page 30 | `direct_source` | Time-to-image-repair is a route variable and must not be replaced by generic “later correction.” |
| E-10 | Emocio identifies and attacks or removes obstacles to its image. | `Docs/REI osnova Emocio.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, pages 47 and 54 | `direct_source` | Obstacle removal must state what leaves the image; it cannot be a generic safety reduction. |
| E-11 | Justice framed as possession, victory, or strength is a candidate Emocio representation. | `Docs/Eros - pogovori.pdf`, pages 47, 86, and 106 | `source_synthesis` | “Balanced positions” or abstract equality is not automatically Emocio-native; the scene must show possession, victory, strength, recognition, or self-position. |
| E-12 | Emocio can identify with a group while the self remains an important member whose group success is experienced as its own. | `Docs/Eros - pogovori.pdf`, page 16 | `direct_source` | Belonging alone is insufficient; the self’s role in the group image must be explicit. |
| E-13 | The eleven-dimensional scene valuation and exact atom matching are research implementations, not source truth. | `knowledge/canon_v2/emocio.yaml`, `valuation.dimensions`, `valuation.matching_policy`, and `valuation.aggregate_policy`; `knowledge/canon_v2/claims.jsonl`, `C-EMOCIO-002` | `implementation_hypothesis` | A distinct vector proves implementation capacity only, not source-faithful Emocio reasoning. |

### Non-acceptance intensification

| ID | Intensification claim | Source and locator | Status | Must not be treated as core |
|---|---|---|---|---|
| E-NA-01 | Non-acceptance can intensify the need for external validation, public attention, and confirmation. | `Docs/Eros - pogovori.pdf`, page 49 | `direct_source` | An accepting Emocio still centers self in its image but may not seek external attention. |
| E-NA-02 | Non-acceptance can intensify excessive competition. | `Docs/Eros - pogovori.pdf`, pages 86, 103, 106, and 175 | `direct_source` | Core competition is not automatically excessive competition. |
| E-NA-03 | Non-acceptance can intensify aggression and destructive defeat of obstacles or rivals. | `Docs/Eros - pogovori.pdf`, pages 16, 54, and 111 | `source_synthesis` | Attack capacity is core; destructive public defeat is not always required. |

No score or acceptance inference is proposed here. The distinction only prevents a future screen from defining “true Emocio” as maximally public, aggressive, or validation-seeking.

### Emocio contract verdict

A source-faithful structured proxy must make self-position, audience, attention, recognition, rival, visible victory/status, immediacy, movement, attraction, and obstacle persistence explicit where relevant. Safety, stable reserves, balance, enforceability, and long-term cost may appear as shared consequences, but they must not silently define the desired Emocio image.

## Route contract: Instinkt

### Core route claims

| ID | Route claim | Source and locator | Status | Operational boundary |
|---|---|---|---|---|
| I-01 | Instinkt scans possible dangers and negative outcomes. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, page 185 | `direct_source` | A packet must expose the kinds of danger; a generic adverse label is insufficient. |
| I-02 | Possible loss is a native Instinkt route signal. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title; `knowledge/canon_v2/instinkt.yaml`, `option_rollout` | `source_synthesis` | Loss must identify the protected target and evidence. |
| I-03 | Distrust, doubt, and uncertainty are native Instinkt signals. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title | `direct_source` | Uncertainty is not itself evidence that the most static option wins. |
| I-04 | Bodily alarm is a research representation of source-grounded fear and protection. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title; `knowledge/canon_v2/instinkt.yaml`, `body_state` and `option_rollout` | `source_synthesis` | Numeric body-state fields are implementation hypotheses and require grounded cue/effect lineage. |
| I-05 | Scarcity and preserving necessary resources are Instinkt-relevant. | `Docs/REI osnove.docx`, page 2, final paragraph; `Docs/Eros - pogovori.pdf`, page 54 | `direct_source` | “Resource preserved” must be balanced against attachment, need, danger, and reversibility evidence. |
| I-06 | Attachment and fear of losing close people are native Instinkt signals. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title | `direct_source` | Relationship outcome cannot be omitted when the person is a close attachment figure. |
| I-07 | Trust belongs in an operational Instinkt packet. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title; `knowledge/canon_v2/instinkt.yaml`, `input_packet` and `option_rollout` | `source_synthesis` | Trust requires a history or grounded present cue; it cannot be inferred from the option label. |
| I-08 | Boundaries are a candidate operational expression of protection, distrust, and defense. | `knowledge/canon_v2/instinkt.yaml`, `input_packet` and `option_rollout`; `knowledge/canon/processors_v2.yaml`, `processors.instinkt.core_native_domains` (historical) | `implementation_hypothesis` | A written contract may strengthen a boundary but does not guarantee trust, repayment, or attachment security. |
| I-09 | Escape, withdrawal, and reversibility are native or source-synthesized Instinkt route signals. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, pages 87 and 111 | `source_synthesis` | Flight/withdrawal is distinct from Emocio attack; “stay home” is not a universal escape result. |
| I-10 | Familiarity, home, and control are candidate protective variables, not a hardcoded choice. | `Docs/Eros - pogovori.pdf`, pages 30 and 185; `knowledge/canon_v2/instinkt.yaml`, `body_state.predictability` and `escape_availability` | `implementation_hypothesis` | The source does not justify `Instinkt = stay home`; familiar danger can be worse than unfamiliar safety. |
| I-11 | Remembered feelings from similar situations can inform Instinkt, but such memory is indirect and unreliable. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, pages 12 and 41; `knowledge/canon_v2/instinkt.yaml`, `association` | `source_synthesis` | A prior association must remain evidence-bounded and may increase uncertainty rather than dictate an option. |
| I-12 | Care, another person’s need, and social/equality-oriented justice are candidate Instinkt route signals. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, page 47 | `source_synthesis` | Care and need require attachment/social evidence; abstract “balanced positions” is not enough. Equality-oriented justice remains weaker than the direct danger/attachment claims. |
| I-13 | Typed cue categories, numeric deltas, predicted loss, recoverability, and protective cost are research implementations. | `knowledge/canon_v2/instinkt.yaml`, `input_packet`, `body_state`, `option_rollout`, and `native_conclusion`; `knowledge/canon_v2/claims.jsonl`, `C-INSTINKT-002` | `implementation_hypothesis` | Distinct effect signatures prove mapper capacity only, not source-faithful Instinkt perception or judgment. |

### Non-acceptance intensification

| ID | Intensification claim | Source and locator | Status | Must not be treated as core |
|---|---|---|---|---|
| I-NA-01 | Non-acceptance can intensify envy. | `Docs/Eros - pogovori.pdf`, pages 86, 103, 106, and 175 | `direct_source` | The older base DOCX names envy as a key motive, but the later Eros passages specifically locate envy under non-acceptance; the latter distinction governs this candidate contract. |
| I-NA-02 | Non-acceptance may intensify suspicion and hostile interpretation. | `Docs/REI osnova Instinkt.docx`, page 1, paragraph under title; `Docs/Eros - pogovori.pdf`, page 86 | `source_synthesis` | Distrust scanning is core; hostile certainty is not. |
| I-NA-03 | Guilt pressure is a possible non-acceptance behavior, but its exclusive Instinkt ownership is not established by the reviewed sources. | `Docs/Eros - pogovori.pdf`, pages 35, 54, and 109 | `implementation_hypothesis` | Do not put guilt pressure into the core route or use it without a dedicated source test. |
| I-NA-04 | Withdrawal can become punitive under non-acceptance, but “punitive” is a research interpretation. | `Docs/Eros - pogovori.pdf`, pages 87, 111, and 166 | `source_synthesis` | Defensive withdrawal is source-grounded; intent to punish must not be assumed. |

No score or acceptance inference is proposed here.

### Instinkt contract verdict

A source-faithful typed proxy must enumerate physical, social, attachment, resource, trust, boundary, escape, and recoverability consequences that are actually relevant to the case. Packet-wide danger or resource cues cannot substitute for option-specific consequences. It must not hardcode Instinkt to home, refusal, or inactivity.

## Cross-route guardrails

| Guardrail | Source and locator | Status |
|---|---|---|
| The three minds are independent systems with different properties and equal value. | `Docs/REI osnove.docx`, page 1, paragraphs 2–5 and page 2, final two paragraphs; `knowledge/canon_v2/claims.jsonl`, `C-MINDS-001` | `direct_source` |
| A person-specific world must not be mistaken for a universal route rule. | `Docs/REI osnove.docx`, page 1, paragraph 2; `knowledge/canon_v2/claims.jsonl`, `C-WORLD-001` | `direct_source` |
| Same option does not establish same route. | `Docs/REI osnova Racio.docx`, page 1, second paragraph under title; `knowledge/canon_v2/claims.jsonl`, `C-ROUTE-001` | `direct_source` |
| Character profile never determines a native route. | `knowledge/canon/processors_v2.yaml`, `global_invariants` (historical); current runtime architecture contract | `implementation_hypothesis` |
| Acceptance/non-acceptance is separate from authority, agreement, safety, and reversibility. | `knowledge/canon_v2/acceptance.yaml`, `invariants`; `knowledge/canon_v2/claims.jsonl`, `C-ACCEPT-001/002/003` | `implementation_hypothesis` |
| Public visibility, home safety, and compromise are input properties, not mind-to-option mappings. | This audit’s synthesis of `Docs/Eros - pogovori.pdf`, pages 30, 47, 49, 54, and 185 | `source_synthesis` |

## S2 field-by-field audit

Classification labels:

- `R-native`, `E-native`, `I-native`: the field directly exposes the named route capacity.
- `shared consequence fact`: the fact may legitimately be visible to more than one route, provided each route interprets it independently.
- `cross_mind_contamination`: a desired state, value marker, or inferred consequence is imported from another route without an Emocio/Instinkt-native grounding.
- `under-specified`: a route-relevant variable is missing or ambiguous.
- `implementation-neutral`: technical scope, IDs, ordering, language, or option enumeration without route content.

The tables audit the frozen inputs. They do not modify them and do not convert actual S2 selections into expected answers.

### A. `factory_overtemperature`

#### Field classification

| Frozen field or assertion | Classification | Fidelity finding |
|---|---|---|
| `+11 C in six minutes`, `8 C sensor difference`, three-minute decision window | `R-native`, `shared consequence fact` | Strong time/number/rapid-change material. |
| Correct sensor unknown; existing damage unknown | `R-native`, `I-native`, `shared consequence fact` | Correctly bounded unknowns; sensor trust and damage severity remain unspecified. |
| Further heating can damage equipment; shutdown causes financial loss | `shared consequence fact` | R can compare utility, I can scan loss, and E can visualize an obstacle; it does not predetermine an option. |
| Public option scope and source/evidence IDs | `implementation-neutral` | Correctly profile-blind. |
| Racio: numeric cues, timelines, “unknowns are not facts” | `R-native` | Strong core route seed. |
| Racio: empty `explicit_consequences`, empty world facts/beliefs | `under-specified` | Cost magnitude, damage threshold, sensor reliability, restart time, and production opportunity cost are absent. |
| Emocio current: rising gauge beside intact machinery | `shared consequence fact` | A valid scene, but self-position, audience, recognition, competition, and victory are absent. |
| Emocio desired: stable gauge, intact machinery, clear operator position | `cross_mind_contamination`, `under-specified` | Stability and intact equipment primarily encode I protection/R operational outcome. “Clear position” is too vague to establish E status or visible victory. |
| Emocio broken: damaged equipment under red warning | `shared consequence fact`, `under-specified` | It shows a broken scene but not loss of status, defeated self-image, or rival/obstacle relationship. |
| Shutdown counterfactual: controlled stop, operator at shutdown controls, heat input removed | `E-native`, `shared consequence fact` | Decisive movement and obstacle removal are E-relevant; hazard removal and loss are shared. |
| Shutdown counterfactual: “operator accountable,” intact equipment, financial loss remains | `shared consequence fact`, `under-specified` | Accountability is not yet visible status or recognition; who observes it is absent. |
| Verify counterfactual: operator between displays, compares sensors, timer visible | `E-native`, `R-native`, `shared consequence fact` | Improvisational movement and rapid comparison are available; victory/status and obstacle removal are unresolved. |
| Continue counterfactual: line moving, operator at controls, heat/damage/sensor obstacles persist | `E-native`, `shared consequence fact` | Movement exists, but it is not evidence of victory or desired-image realization. |
| Instinkt starting body state | `I-native`, `implementation_hypothesis` | Typed proxy is allowed; its numeric values are not direct source truth. |
| Shutdown consequence: heat exposure stops; resource loss | `I-native`, `shared consequence fact` | Grounded danger/escape and scarcity trade-off. |
| Verify consequence: brief exposure while readings are compared | `I-native`, `shared consequence fact`, `under-specified` | Duration is grounded, but severity and retreat path during verification are absent. |
| Continue consequence: rising-heat exposure continues | `I-native`, `shared consequence fact` | Clear danger persistence. |
| All Instinkt consequences omit shutdown/restart recoverability, personnel exposure, damage magnitude, and safe egress | `under-specified` | The route can distinguish effects but cannot fully compare loss and recovery. |

#### Frozen execution observation

Racio was rejected with `fact_evidence_mismatch`; therefore S2 contains no accepted Racio route for this case. Emocio selected `factory_shutdown`, but `desired_scene_match`, `movement`, and `status` were all `0.0`; the narrow aggregate difference came mainly from novelty and attack/breakthrough affordance. Instinkt selected `factory_shutdown` on distinct danger/resource effects. These are observations, not expected-option labels.

#### Option-level route signals

| Option | Signals supporting the option | Signals opposing the option | Missing data | What could change a native decision |
|---|---|---|---|---|
| `factory_shutdown` | R: stops a potentially escalating process; I: ends heat exposure and offers an escape/protection action; E: decisive control movement removes a visible obstacle. | R: certain shutdown loss and restart cost; E: no stated audience, victory, improvisational success, or status gain; I: resource loss and unknown shutdown/restart risks. | Loss magnitude, restart time, damage threshold, personnel danger, public status stakes, operator recognition. | Higher verified damage probability or personnel exposure supports shutdown routes; a very large irreversible shutdown loss plus reliable low reading can oppose them; visible decisive leadership can strengthen E without determining its answer. |
| `factory_verify` | R: reduces sensor uncertainty within the stated window; E: active comparison/improvisation; I: retains a possible escape while limiting exposure duration. | R/I: heat continues during verification; E: obstacle is not yet removed and no visible victory is described. | Temperature acceleration, sensor calibration history, safe verification procedure, whether three minutes is within equipment tolerance, audience/status context. | Reliable rapid diagnostics and tolerable exposure support verification; evidence that three minutes crosses a damage threshold opposes it. |
| `factory_continue` | R: avoids certain shutdown loss if the primary reading is wrong; E: preserves immediate movement/production; I: no grounded protective advantage is stated. | R: rising trend and unresolved sensor conflict; E: obstacle persists and no victory is shown; I: danger exposure continues with unknown damage. | Production value per minute, safe threshold, automatic interlocks, personnel risk, reversibility. | Strong evidence that the primary sensor is faulty and the process remains below a safe limit can support continuation; worsening rate or low recoverability opposes it. |

#### Route verdict

- Racio: **not assessable from S2 output** because the only native Racio result was rejected; the input had strong R-native rapid-change material but insufficient explicit consequence structure.
- Emocio: **not source-faithful enough for acceptance**. Counterfactuals were distinct, but the desired/broken world was mostly stability/damage rather than victory, status, decisive self-image, improvisation, or recognized obstacle removal.
- Instinkt: **credible partial core route**. Danger, loss, shutdown/escape, and continued exposure were represented, but recoverability and the full protected-target scope were incomplete.

### B. `loan_to_friend`

#### Field classification

| Frozen field or assertion | Classification | Fidelity finding |
|---|---|---|
| Urgent repair invoice | `I-native`, `shared consequence fact` | The friend’s need can matter to care/attachment; it is not automatically R utility or E attraction. |
| Two prior repayments over three months late | `R-native`, `I-native`, `shared consequence fact` | Supports planning/enforceability and trust/distrust. |
| Full sum equals 45% of own reserve | `R-native`, `I-native`, `shared consequence fact` | Supports opportunity cost and scarcity. |
| Repayment timing and relationship effect unknown | `R-native`, `I-native`, `E-native`, `shared consequence fact` | Correctly leaves both enforceability and relationship image unresolved. |
| Racio rule compares need, history, exposure, and contract | `R-native`, `cross_mind_contamination` | History/exposure/contract are R-native; “need” requires an explicit R goal or instrumental relationship value. |
| Racio world has no explicit goal, consequence values, enforceability terms, or opportunity costs | `under-specified` | The model had no grounded basis for treating the repair need as Racio utility. |
| Emocio current: two people facing across a table | `E-native`, `shared consequence fact` | A usable social scene; attention, self-center, enjoyment, recognition, and competition remain absent. |
| Emocio desired: continued connection with stable reserve | `cross_mind_contamination` | Continued connection can be E belonging, but stable reserve is R/I unless independently grounded as an E image. |
| Emocio broken: empty chair plus depleted reserve | `E-native`, `I-native`, `cross_mind_contamination` | Empty chair can visualize lost connection; depleted reserve imports scarcity into the desired-image policy. |
| Full-loan counterfactual: connection remains, full amount crosses table, reserve drops | `E-native`, `shared consequence fact` | Movement and connection are E-relevant; reserve exposure is shared. Repayment/relationship unknowns are properly retained. |
| Limited-contract counterfactual: smaller transfer, written date, partial reserve | `shared consequence fact`, `cross_mind_contamination` | The written boundary and retained reserve are mainly R/I. The E-specific image change beyond continued connection is weak. |
| Decline counterfactual: no transfer, reserve stable, relationship unknown | `shared consequence fact`, `cross_mind_contamination` | Stable reserve is allowed as consequence but was also an attraction marker, which biases E with a non-E goal. |
| Instinkt full: 45% reserve exposure, no new contractual boundary | `I-native`, `shared consequence fact` | Grounded scarcity and boundary signals. |
| Instinkt limited: bounded exposure and written boundary | `I-native`, `shared consequence fact`, `under-specified` | Boundary is grounded, but amount and likely effect on trust/attachment are not. |
| Instinkt decline: reserve unchanged, relationship consequence unknown | `I-native`, `shared consequence fact`, `under-specified` | Resource is represented; friend’s need, guilt, attachment loss, and relationship recoverability are omitted. |
| Attachment strength, fear of losing friend, friend’s need, own scarcity, trust history, guilt, boundary effectiveness, and money recoverability | `under-specified` | These are required differentiators for a faithful Instinkt route. |

#### Frozen execution observation

Racio, Emocio, and Instinkt all selected `loan_limited_contract`. The same option does not establish the same route. Racio’s output treated declining as ignoring the urgent need without an explicit Racio goal. Emocio’s desired image embedded stable reserve. Instinkt compared resource exposure and boundary but did not receive the attachment/care route variables needed to test a genuinely different protective judgment.

#### Option-level route signals

| Option | Signals supporting the option | Signals opposing the option | Missing data | What could change a native decision |
|---|---|---|---|---|
| `loan_full` | R: may serve an explicit relationship or repayment goal if such a goal exists; E: strongest immediate image of connection/helping movement; I: may protect a close attachment figure in genuine need. | R: 45% exposure, late history, no new enforceability; E: no evidence that the full transfer creates recognition, enjoyment, or desired self-image; I: scarcity, distrust, weak boundary, uncertain recovery. | Attachment strength, explicit R goal, income/reserve obligations, repayment capacity, collateral/enforcement, friend response, guilt and care cues. | Strong attachment/need and high money recoverability can support it; low enforceability, severe own scarcity, or weak relationship evidence oppose it. |
| `loan_limited_contract` | R: bounded exposure plus explicit terms; I: adds a boundary while partly helping; E: preserves an image of connection and action if that image is grounded. | R: contract may be unenforceable and amount may not solve the repair; E: written terms/reserve retention are not inherently E-native; I: boundary may not restore trust and partial aid may still threaten scarcity or attachment. | Exact amount, legal/enforcement status, repair sufficiency, friend’s reaction, repayment capacity, boundary credibility. | Enforceable sufficient terms can strengthen R; a trusted close friend and credible boundary can strengthen I; a humiliating or relationship-breaking contract can oppose E/I. |
| `loan_decline` | R: preserves opportunity set and reserve; I: preserves scarce resources and a hard boundary; E: could protect self-position if refusal sustains a grounded desired image. | R: may sacrifice an explicit strategic relationship benefit; E: may break connection; I: may threaten a close attachment and leave genuine need unaddressed. | Relationship distance, attachment loss probability, alternative aid, own obligations, friend’s need severity, recoverability of relationship. | Distant acquaintance/low attachment and severe own scarcity support decline routes; close attachment, urgent danger, and safe alternative boundaries can oppose it. |

#### Route verdict

- Racio: **partial and contaminated**. Numbers, history, exposure, and contract were appropriate; the friend’s need entered utility without an explicit Racio goal, and enforceability/opportunity-cost data were incomplete.
- Emocio: **not source-faithful enough for acceptance**. “Stable reserve” was treated as a desired/attractive image without an Emocio-world basis, while the self-image, attention, enjoyment, recognition, and immediate social transformation were weak.
- Instinkt: **effect-distinguishable but materially under-specified**. Scarcity and boundaries were present; attachment, care, guilt, trust history, and recoverability were not.

### C. `public_credit_conflict`

#### Field classification

| Frozen field or assertion | Classification | Fidelity finding |
|---|---|---|
| Public sole-credit claim, timestamped contrary authorship evidence, leader present, meeting active | `R-native`, `E-native`, `I-native`, `shared consequence fact` | R sees evidence/ownership/timing, E sees status/attention/competition, I sees social danger/boundary/trust. |
| Public-confrontation consequences and leader assessment unknown | `R-native`, `I-native`, `shared consequence fact` | Correct unknowns; audience reaction and humiliation severity are still absent. |
| Racio compares evidence visibility, timing, and unknown social consequences | `R-native` | Appropriate core seed. |
| Racio has no explicit ownership goal, enforceability consequence, leader decision process, leverage, opportunity cost, or long-term career effect | `under-specified` | “Leader awareness” is not equivalent to enforceable correction. |
| Emocio current memory: “one speaker centered beside shared work” | `E-native`, `under-specified` | It does not say whether self or colleague is centered. |
| Emocio desired: authorship record visible with “balanced positions” | `cross_mind_contamination`, `under-specified` | Visibility can be E-native. “Balanced positions” is abstract equality and does not establish self-center, recognition, victory, strength, or obstacle defeat. |
| Emocio broken: one figure erased from shared-work composition | `E-native`, `under-specified` | The erased figure is not explicitly identified as self. Audience and status loss are implicit, not grounded. |
| Public counterfactual: record shown during meeting; author beside projection; claim contested before leader/group | `E-native`, `shared consequence fact` | Strong audience, center, recognition, competition, immediacy, and obstacle-attack signals; result of confrontation and humiliation risk remain unknown. |
| Private counterfactual: leader sees evidence later; public statement remains uncorrected | `R-native`, `I-native`, `shared consequence fact` | It can serve controlled evidence transfer and lower exposure, but it does not restore the public broken image during the meeting. |
| Private attraction marker: “balanced positions” | `cross_mind_contamination` | This marker materially imports an ungrounded equality/stability goal into Emocio valuation. |
| No-response counterfactual: colleague remains centered; self away; record unseen | `E-native`, `shared consequence fact` | Clear non-restoration of self-position/recognition; it may still have I protective value if exposure risk dominates. |
| Instinkt public: public exposure and boundary added | `I-native`, `shared consequence fact`, `under-specified` | Exposure and boundary are grounded; humiliation, retaliation, trust, escape, and reversibility are not. |
| Instinkt private: exposure limited to leader and later authorship boundary | `I-native`, `shared consequence fact`, `under-specified` | Lower audience is grounded; “preserves a later boundary” is a prospective inference, not guaranteed by evidence. |
| Instinkt no response: public claim unaddressed | `I-native`, `shared consequence fact`, `under-specified` | Boundary loss is represented, but short-term exposure relief and long-term loss/recoverability are not. |

#### Required public-credit reconciliation

- **Does `balanced positions` belong to Emocio?** Not as written. The reviewed sources support self-centered image, visible recognition, competition, victory/strength, and group identification. Abstract balance/equality is at best a shared or Instinkt/social-justice synthesis. In S2 it is `cross_mind_contamination`.
- **Does private correction restore the publicly broken image?** No. The frozen counterfactual explicitly says the public statement remains uncorrected during the meeting. It may create later strategic correction or a private boundary, but it does not realize the same public Emocio image.
- **Who is centered now?** Under-specified. The current memory says only “one speaker.” The source fact identifies the colleague as speaker, but the structured current scene did not explicitly bind center to colleague.
- **Who is centered after each option?** Public: self/author beside projection, with colleague still in the contested scene. Private: self beside leader but outside the group. No response: colleague remains centered; self is away from projection.
- **Who sees victory?** Public: leader and meeting group could see a contest, but the outcome is unknown. Private: only leader sees the evidence; no public victory is shown. No response: no self-victory is shown.
- **Is the rival publicly defeated?** Not grounded for any option. Public confrontation initiates contest; it does not establish defeat. Private review and no response do not publicly defeat the rival.
- **Speed of image repair:** public is immediate but outcome-unknown; private is delayed and non-public; no response provides no stated repair.
- **Audience size:** public includes leader and group; private includes leader only; no response leaves the original group exposure intact without a corrective act.
- **Attention and recognition:** public exposes evidence to the group; private limits recognition to leader; no response leaves attention on colleague.
- **Competition and obstacle removal:** public directly contests the rival claim and exposes the hidden record; private removes only the record’s invisibility to leader; no response removes neither.
- **Public-humiliation risk:** present as a route-relevant Instinkt unknown but not quantified or separated into humiliation of self, colleague, or both.

#### Frozen execution observation

Racio, Emocio, and Instinkt all selected `credit_private_evidence`. The convergence is not source-grounded route convergence. Emocio’s result was materially helped by the ungrounded `balanced positions` attraction marker even though the private scene left the public image uncorrected. Instinkt had useful exposure/boundary distinctions but insufficient humiliation, trust, retaliation, and recovery evidence.

#### Option-level route signals

| Option | Signals supporting the option | Signals opposing the option | Missing data | What could change a native decision |
|---|---|---|---|---|
| `credit_public_confront` | R: immediate use of timestamped evidence while decision-makers are present; E: largest audience, rapid self-recentering, recognition contest, direct obstacle attack; I: restores a boundary against appropriation. | R: unknown social/career cost and uncertain leader response; E: public defeat is not guaranteed; I: maximum exposure, humiliation/retaliation risk, weak escape once initiated. | Audience size/reaction, leader authority, record conclusiveness, retaliation cost, self/colleague humiliation, recovery path. | Strong enforceability and supportive leader/audience can support R/E; high retaliation with low reversibility can oppose I/R; explicit public-status goal strengthens E without fixing the answer. |
| `credit_private_evidence` | R: controlled evidence presentation to a relevant authority; I: bounded audience and retained boundary; E: self gains leader attention and may preserve group connection. | R: leader may not correct record; E: public image remains broken and rival not publicly defeated; I: delayed correction may deepen loss and leader trust is unknown. | Leader’s correction power, whether public correction follows, time-to-correction, private retaliation risk, value of public recognition. | A guaranteed public correction after private review supports R and may repair E later; refusal to correct or a time-critical reputation loss opposes it. |
| `credit_no_response` | R: avoids immediate confrontation cost if authorship has no strategic consequence; I: avoids immediate public exposure; E: no clear core support in the frozen scene. | R: ownership claim remains unenforced; E: self remains displaced and obstacle persists; I: boundary loss and future distrust may grow. | Long-term career/material consequence, alternative record channel, exposure decay, attachment/group importance, reversibility. | Evidence that the claim has no material/status effect can support non-response; durable public attribution loss or repeated appropriation opposes it. |

#### Route verdict

- Racio: **credible but incomplete**. Evidence visibility, timing, and unknown consequences were native; ownership, enforceability, leverage, and long-term consequences were not explicit enough.
- Emocio: **contaminated and not acceptable as a fidelity result**. Counterfactual scenes were distinct, but `balanced positions` imported an ungrounded value and the selected private route did not restore the public broken image.
- Instinkt: **partial**. Exposure and boundary were represented; humiliation danger, trust, retaliation, escape, and recoverability were missing.

### D. `spontaneous_trip`

#### Field classification

| Frozen field or assertion | Classification | Fidelity finding |
|---|---|---|
| Four-hour expiry, non-refundable booking, 38% discretionary budget, once in three years | `R-native`, `I-native`, `shared consequence fact` | Strong time, scarcity, irreversibility, and rarity facts. |
| Distant coast and local route visual | `E-native`, `shared consequence fact` | Supports attraction, movement, novelty, and scene comparison. |
| Future costs and satisfaction unknown | `R-native`, `E-native`, `I-native`, `shared consequence fact` | Correctly bounded but too coarse for route fidelity. |
| Operational raw input calls the trip “attractive” | `E-native` | Appropriate for E; R must not silently convert this into utility. |
| Racio rule says compare rarity, irreversibility, budget, unknown costs “without assuming enjoyment” | `R-native` | Correct guardrail. |
| Racio has no explicit strategic/material benefit or explicit goal assigning value to experience | `under-specified` | The frozen packet does not explain why rarity is Racio utility. |
| Emocio current/visual memory: open coastline beyond ticket | `E-native` | Strong attraction/new-experience image. |
| Emocio desired: expanded horizon, vivid movement, retained footing | `E-native`, `cross_mind_contamination` | Horizon/movement are E-native; retained footing is a safety/resource proxy without an E-world basis. |
| Emocio broken: closed horizon beside emptied budget marker | `E-native`, `cross_mind_contamination` | Closed horizon is E-native; emptied budget is R/I scarcity imported into the broken image. |
| Book counterfactual: distant coast active, movement begins, horizon opens | `E-native` | Strong new-experience, attraction, and movement route. |
| Book counterfactual: budget drops; costs/satisfaction unknown | `shared consequence fact` | Legitimate consequence, but not an Emocio preference by itself. |
| Local counterfactual: nearby movement, distant horizon unvisited, smaller spend | `E-native`, `shared consequence fact` | Meaningfully distinct E scene; “retained footing” attraction marker is ungrounded. |
| Home counterfactual: routes inactive, no movement, budget stable | `E-native`, `shared consequence fact` | Provides a closed/no-movement scene; stable budget was incorrectly also an attraction marker. |
| Instinkt book: high resource exposure, irreversibility, movement | `I-native`, `shared consequence fact` | Distinct but narrow; movement is treated as alarm without travel-context danger evidence. |
| Instinkt local: bounded exposure, reversible commitment, local movement | `I-native`, `shared consequence fact` | Distinct resource/escape route, though actual reversibility was not explicitly in source evidence. |
| Instinkt home: resource preserved, movement absent | `I-native`, `cross_mind_contamination` | Resource preservation is grounded; `movement_absent` becomes mechanically protective and risks hardcoding home. |
| Physical safety, unfamiliarity, trusted companion, distance from home, separation from attachment figures, return/escape path, health, lodging/transport trust, predictability, prior associations, and responsibilities at home | `under-specified` | Their absence prevents a faithful Instinkt travel route. |

#### Frozen execution observation

Racio and Emocio selected `trip_book`; Instinkt selected `trip_home`. Racio’s utility list called the rare experience “high utility,” the local route a “compromise,” and staying home “safe utility.” Those labels exceed the explicit Racio goal and import E attraction and I safety. Emocio had a plausible movement/attraction direction, but safety/budget markers contaminated the desired/broken world. Instinkt distinguished effects but mostly evaluated reserve and movement absence rather than travel danger, trust, attachment, escape, and familiarity.

#### Option-level route signals

| Option | Signals supporting the option | Signals opposing the option | Missing data | What could change a native decision |
|---|---|---|---|---|
| `trip_book` | R: can be supported by an explicit strategic/material benefit or explicitly adopted experiential goal; E: strongest attraction, novelty, immediate movement, and open-horizon image; I: could be supported by a trusted companion, safe lodging, healthy body, and reliable return route. | R: 38% cost, irreversibility, unknown future costs, no stated strategic return; E: uncertain satisfaction and no social/status evidence; I: unfamiliar/distant/non-refundable exposure and separation risk are unknown. | Strategic benefit, companion, safety, distance, health, lodging/transport trust, return path, attachment separation, responsibilities, prior travel associations. | Adding grounded strategic benefit strengthens R; trusted close company/safe lodging/reversible return can strengthen I; severe health, trust, or home-responsibility risk can oppose it. |
| `trip_local` | R: lower opportunity cost with some experience if experience is an explicit goal; E: movement and novelty remain, though horizon is smaller; I: bounded exposure and easier return can be protective. | R: exact cost/benefit and reversibility are absent; E: rare desired horizon remains unrealized; I: local does not automatically mean safe. | Local cost, refundability, transport safety, social company, novelty, time away, return reliability. | A clearly reversible low-cost route with meaningful novelty supports several routes independently; unsafe transport or negligible experience value opposes it. |
| `trip_home` | R: preserves budget/options if no strategic return exists; I: can preserve resources, home responsibilities, and attachment proximity when those are grounded; E: could support a desired home image if such an image exists. | R: may forgo an explicit strategic opportunity; E: no movement/new experience and closed horizon; I: home is not automatically safe and unfulfilled attachment/need may remain. | Home safety, responsibilities, people at home, alternative use of money, future opportunity probability, desired home scene. | Severe home obligations or uncertain travel safety support staying; an unsafe/empty home context or trusted reversible travel can oppose it. |

#### Route verdict

- Racio: **contaminated and not acceptable as a fidelity result**. The output invented R utility for rarity/experience and used Emocio-like “compromise” plus Instinkt-like “safe utility” without explicit goals.
- Emocio: **plausible core direction but only partial fidelity**. Attraction, novelty, and movement were strong; retained footing and budget stability contaminated desired/broken markers, and several direct scene-match dimensions remained inert.
- Instinkt: **not source-faithful enough for acceptance**. Effects were technically distinct, but the route omitted nearly every travel-specific protective variable and risked `Instinkt = stay home`.

## Consolidated cross-mind contamination findings

| Finding | Affected cases | Severity | Reason |
|---|---|---:|---|
| Safety/stability used as Emocio desired-image content without an Emocio-world basis | Factory, loan, trip | High | Stable gauge, stable reserve, retained footing, and budget stability primarily encode I protection or R material consequence. |
| Abstract equality/balance used as Emocio attraction | Public credit | High | `balanced positions` does not show self-center, recognition, victory, strength, or obstacle defeat and materially favored the private option. |
| Another person’s need treated as Racio utility without an explicit R goal | Loan | High | Compassion/need is not native Racio utility unless explicit or instrumental. |
| Rarity/pleasure treated as Racio utility without a strategic/material or explicit experiential goal | Trip | High | Rare and attractive are E signals unless Racio receives an independent utility basis. |
| “Compromise” and “safe utility” used as Racio value labels | Trip | High | Compromise and safety are input consequences, not intrinsic Racio preferences. |
| Resource preservation and movement absence dominate Instinkt while attachment/trust/escape context is missing | Loan, trip | High | This risks hardcoded refusal/home behavior rather than danger/loss scanning. |
| Public/private exposure labels substitute for the full Instinkt social-risk route | Public credit | Medium | Humiliation, retaliation, trust, withdrawal, boundary recovery, and long-term loss were absent. |
| Technical stability/damage scene substitutes for Emocio victory/status route | Factory | High | Distinct scenes existed, but the core desired image was not distinctly Emocio. |

## Consolidated missing-input findings

### Racio

- Factory: trend/acceleration, sensor reliability, safe thresholds, loss magnitude, restart time, opportunity cost, and recoverability.
- Loan: explicit R goal, exact limited amount, enforceability, borrower capacity, lender obligations, collateral/leverage, enforcement cost, and relationship’s instrumental value.
- Public credit: ownership objective, leader authority, evidentiary conclusiveness, correction mechanism, career/material consequence, retaliation cost, and time value of public correction.
- Trip: explicit strategic/material benefit or explicit experiential goal, opportunity cost, alternative use of funds, future availability estimate, and value of reversibility.

### Emocio

- Factory: self-center, audience, public recognition, visible victory/status, improvisational success, rival/obstacle identity, and speed of image realization.
- Loan: self-image in giving/refusing, attention, enjoyment, recognition, status, desired relationship image, and whether a written boundary strengthens or damages that image.
- Public credit: explicit current center, audience size, recognition target, winner/loser visibility, public image-repair result, obstacle removal, correction speed, and humiliation scene.
- Trip: whether experience is solitary/social, desired self-image, attraction strength, enjoyment cues, recognition/status if any, and why retained footing belongs in E’s own image.

### Instinkt

- Factory: personnel danger, damage magnitude, sensor trust, safe egress, shutdown/restart risk, resource recovery, and known bodily associations.
- Loan: attachment strength, fear of losing the friend, friend’s need, own scarcity obligations, trust history, guilt, boundary credibility, and recoverability of money and relationship.
- Public credit: public-humiliation danger, leader/colleague trust, retaliation, withdrawal path, reversibility, boundary recovery, and long-term social loss.
- Trip: physical safety, unfamiliarity, trusted companion, distance from home, separation from attachment figures, return/escape path, health, lodging/transport trust, predictability, prior associations, and responsibilities at home.

## Route-isolation pairs for a future screen

These are candidate experimental contrasts, not new corpus records and not expected-answer templates. Within each pair, public option IDs and descriptions should remain semantically comparable. Only the listed route-relevant evidence should change.

| Pair | Variant A | Variant B | Held constant | Capacity isolated | Status and source |
|---|---|---|---|---|---|
| Public credit: audience | Correction and authorship evidence are visible to the full meeting audience; audience size and recognition stakes are explicit. | The same correction and evidence occur after the meeting with no audience; enforceability and material consequence remain the same. | Authorship proof, leader authority, option scope, retaliation uncertainty, timing budget | Emocio attention/recognition/public image without changing R ownership evidence | `source_synthesis`; `Docs/Eros - pogovori.pdf`, pages 49 and 185 |
| Trip: protective context | Traveller is alone, route unfamiliar, purchase non-refundable, lodging/transport unverified, return path uncertain. | Traveller is with a trusted close person, lodging/transport verified safe, and return path explicitly reversible. | Destination attraction, price, rarity, options, strategic benefit | Instinkt danger/trust/attachment/escape while holding E attraction and R utility fixed | `source_synthesis`; `Docs/REI osnova Instinkt.docx`, page 1; `Docs/Eros - pogovori.pdf`, pages 54 and 185 |
| Loan: attachment distance | Borrower is a close attachment figure with grounded shared history and explicit fear of relationship loss. | Borrower is a distant acquaintance with no attachment history; need, amount, repayment record, and contract terms are identical. | Financial exposure, need, repayment evidence, options | Instinkt attachment/care versus scarcity/boundary | `direct_source` basis with experimental pairing; `Docs/REI osnova Instinkt.docx`, page 1 |
| Trip: Racio utility | Trip has an explicit, evidenced strategic/material benefit with estimated value and ownership opportunity. | Same trip is explicitly a pure pleasurable experience with no strategic/material benefit. | Attraction, safety, companion, cost, rarity, reversibility, options | Racio explicit utility versus Emocio attraction | `source_synthesis`; `Docs/Eros - pogovori.pdf`, page 47; `Docs/REI osnova Emocio.docx`, page 1 |
| Factory: public status | Same technical decision is observed by a named audience; success/failure changes visible operator status and recognition. | Same technical responsibility and consequences are anonymous; nobody observes or attributes the decision. | Sensor data, time, financial loss, danger, options | Emocio status/recognition while holding R rapid-change analysis and I danger fixed | `source_synthesis`; `Docs/Eros - pogovori.pdf`, pages 49 and 54 |

For every pair:

- a pair member may support more than one option;
- the contrast tests whether a route changes for a route-relevant reason, not whether a prescribed option wins;
- option order must remain irrelevant;
- “public,” “home,” and “compromise” must remain evidence properties, never mind labels.

## Verdict by S2 native route

| Case | Racio verdict | Emocio verdict | Instinkt verdict |
|---|---|---|---|
| `factory_overtemperature` | Not assessable from native output; rejected. Input is promising but consequences are under-specified. | Distinguishable implementation, source-fidelity failure: stability/damage dominated victory/status/improvisation. | Credible partial route; danger/escape/loss present, recoverability incomplete. |
| `loan_to_friend` | Partial and contaminated by unscoped compassion/need; enforceability and opportunity cost incomplete. | Source-fidelity failure: stable reserve imported R/I value into desired image. | Distinguishable but under-specified: attachment, care, trust, guilt, and recovery absent. |
| `public_credit_conflict` | Credible but incomplete: evidence/timing present, ownership/enforceability/long-term effect incomplete. | Source-fidelity failure: `balanced positions` contamination and private route does not repair public image. | Partial: exposure/boundary present; humiliation, trust, retaliation, escape, and recovery absent. |
| `spontaneous_trip` | Source-fidelity failure: rarity/pleasure became utility without explicit R basis. | Plausible core direction but partial: movement/attraction present, safety/budget markers contaminated the image. | Source-fidelity failure: resource/movement proxy omitted travel-specific danger, trust, attachment, and escape. |

No S2 option is declared expected. No global REI score is calculated. The verdicts concern route-input and route-output fidelity only.

## Smallest next development screen

The minimum next screen should be a **model-free route-isolation preflight over five contrast pairs**, followed—only after human review—by a small replay execution.

The preflight should:

1. express each pair as two sealed source packets with identical public option scope and only route-relevant evidence changed;
2. require an explicit Racio goal/utility beneficiary, an Emocio self/audience/recognition/obstacle scene, and an Instinkt protected-target/trust/attachment/escape consequence set;
3. reject Emocio desired markers whose only basis is safety, reserve preservation, abstract balance, or enforceability;
4. reject Instinkt consequences that reduce travel to movement/no movement or lending to reserve exposure alone;
5. reject Racio utility entries derived only from compassion, attraction, rarity, safety, or compromise;
6. produce no expected option and no character replay until route-isolation inputs pass human review.

If execution is later authorized, the smallest informative model-backed subset is two pairs:

- trip with strategic/material benefit versus pure pleasurable experience, to isolate Racio from Emocio;
- trip alone/unfamiliar/non-refundable versus trusted-close/safe/reversible, to isolate Instinkt while holding attraction and utility fixed.

That would be four root cases, at most four Racio calls, four Emocio structured executions, four Instinkt typed executions, and no character replay until the native routes themselves are judged human-readable. This is an `implementation_hypothesis`, not a continuation authorization.

## Stop

TRIAD-CANON-R1 ends with this audit. Frozen TRIAD-S1 and TRIAD-S2 artifacts remain historical capability evidence. No replay, provider change, framework, model call, image generation, G4 work, merge, or PR is authorized or performed.
