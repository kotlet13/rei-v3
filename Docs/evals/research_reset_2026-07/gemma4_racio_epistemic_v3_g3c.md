# Gemma 4 Racio epistemic V3 G3C development rerun — 2026-07-17

This is the bounded G3C rerun of the same eight semantic roots used by frozen
G3, expressed through the frozen V3 contract. It is a **development rerun**,
not an untouched holdout. It makes no generalization claim, does not promote
Gemma, and has no governance or runtime authority. No aggregate semantic score
or aggregate pass/fail result is calculated.

## Scope and provenance

- Roots and order: H1, H3, H7, H11, H15, R1, R3, R5; one
  `canonical_sl_only` and one `operational_en_only` call per root, for 16
  separately dispatched calls.
- P3 base commit:
  `ea96de2a59355073a25e7699481d841d84e8f762`.
- Pre-call seal commit:
  `18d636b0be765843d2d5914e6a739b475a84c67e`.
- Frozen corpus [manifest](../../../knowledge/canon_v2/semantic_lab_v1/gemma4_epistemic_v3_g3c_2026_07_17/manifest.json)
  SHA-256:
  `6933e919a48af7a2de6aff1490e745bc13e4ae7742e2c1e1e8a049ddc4aa9298`.
- Preflight ID:
  `racio_g3c_v3_preflight_4ec360355b2d9e88b183bd1061451a8c`;
  preflight hash:
  `5e22b7220d27cd3d136f70e4b9bb8cde5ecad138a6ed6ebd04982130e3941e4e`.
- Provider revision: `rei-racio-gemma4-epistemic-v3-chat-v1`; endpoint:
  `/api/chat`; Ollama version: `0.31.2`.
- Model: `gemma4:31b`; exact digest:
  `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`.
- Instruction SHA-256:
  `470bb45de824a438aafdbb3efeae924c71d2bfce844eddf69597443b06bfc30d`.
- DraftV3 schema SHA-256:
  `321cecc980ec82346260b6ef3910a69a5f9b91233f101526254ff3e392704d6a`;
  canonical InterpretationV3 schema SHA-256:
  `02eeda6446ff5a304ffb50c791f96da282326bc75d5c334c57784ce719602a50`.
- Seed `314159`; temperature `0.0`; top-p `0.95`; top-k `64`;
  `num_ctx=65536`; `num_gpu=999`; `num_predict=16384`; timeout `600s`;
  retry `0`; fallback `none`; thinking enabled and kept separate from final
  JSON.
- Execution window: `2026-07-17T21:57:25.404811Z` through
  `2026-07-17T22:04:36.700851Z`.
- Every response evidence record confirms requested and active context
  `65536`, requested `num_gpu=999`, active placement `100% GPU`, the exact
  model digest, and a separated thinking channel.
- The complete [evidence bundle](../semantic_lab_v1/g3c-gemma4-racio-epistemic-v3-2026-07-17/)
  contains per-case packets, provider payloads, call specs, call records,
  DraftV3, canonical outputs, response evidence, sidecars, case evaluations,
  uncertainty receipts, and bilingual evaluations.
- Canonical [report JSON](../semantic_lab_v1/g3c-gemma4-racio-epistemic-v3-2026-07-17/report.json)
  SHA-256:
  `9924cb59648be20abd2f67f1116278db5b9e703077c30b796426c8c7a822e676`;
  [summary JSON](../semantic_lab_v1/g3c-gemma4-racio-epistemic-v3-2026-07-17/summary.json)
  SHA-256:
  `3c7589671f869479ea30cbcbc80175f1a244ec7a08489f43b50c39cf957c7e39`.
- The model-free [cold-validation receipt](../semantic_lab_v1/g3c-gemma4-racio-epistemic-v3-2026-07-17/cold_validation.json)
  revalidated 16 provider execution lineages, 16 case evaluations, and all
  eight bilingual evaluations. Its 254-file evidence fingerprint is
  `2f3acb502c8ca134512c2c7ea3da1f4046b86e8963436402dc56318e191d7a18`.

## 1. Contract

- Attempted/successful/failed calls: `16 / 16 / 0`.
- Retries/fallbacks: `0 / 0`.
- Structural validity: `16/16`.
- DraftV3 validity: `16/16`.
- Canonicalizer validity: `16/16`.
- Citation-scope failures: `0`.
- Option-specific citation failures: `0`.
- Hidden-truth leakage: `0`; profile leakage: `0`.
- Input packet unchanged: `16/16`; structural hard contract: `16/16`.
- Private thinking text and raw response envelopes persisted: `false / false`.
- The structural sidecar remained a non-semantic artifact with no governance
  effect.

This is a technical contract result only. It does not imply semantic
acceptance.

## 2. Action

| Dimension | Combined | SL | EN |
|---|---:|---:|---:|
| Action family coverage | 13/16 (81.25%) | 6/8 (75.0%) | 7/8 (87.5%) |
| Exact subtype coverage | 11/16 (68.75%) | 5/8 (62.5%) | 6/8 (75.0%) |

- Emitted action hypotheses: `20`.
- Support modes: `19` direct manifestation, `1` functional inference, `0`
  speculative.
- Family fallbacks: `0`.
- Action citation support: `18/20`.
- Unsupported action overclaims: `7`.
- Bilingual family consistency: `8/8`; bilingual exact-subtype consistency:
  `7/8`.

The seven action overclaims were:

- H1 SL/EN: `approach` received family-level acceptable-sibling credit, but
  exact `seek_contact` credit was absent and the additional `connect` claim was
  not precommitted as exact or acceptable.
- H3 EN: `conserve` used `direct_manifestation` where the gold allowed only
  `functional_inference`.
- H3 SL: `freeze` was the wrong subtype and also used the wrong support mode.
- H7 SL/EN: exact `set_boundary` was present, but the additional
  `withdraw_contact` hypothesis lacked its required citation support.
- H15 SL: exact `set_boundary` used `functional_inference` where direct
  manifestation was required.

Family membership never supplied exact-subtype credit.

## 3. Option

- Unique option mapping: `12/12`.
- Required abstention: `4/4`.
- Option-specific evidence support: `12/12` emitted option inferences.
- Unsupported option selections: `0`.
- Bilingual option consistency: `8/8`.

Option credit used only citations local to `OptionInferenceV3`; the global
citation union was not sufficient for credit.

## 4. Motive

| Dimension | Combined | SL | EN |
|---|---:|---:|---:|
| Directly supported motive-family coverage | 12/14 (85.71%) | 5/7 (71.43%) | 7/7 (100%) |
| Directly supported exact-subtype coverage | 12/14 (85.71%) | 5/7 (71.43%) | 7/7 (100%) |

- Emitted motive hypotheses: `15` — `13` directly supported-mode claims, `2`
  contextual-mode claims, and `0` speculative-mode claims.
- Directly supported precision: `12/15` (80.0%).
- Motive citation support: `14/15`.
- Unsupported motive overclaims: `2`, both in SL and both at confidence
  `>= 0.5`.
- Empty-motive correctness for the two `not_identifiable` cases: `1/2`.
- Required unknown preservation: `1/2`.

The three non-reference-supported motive results were:

- H3 SL: contextual `scene/desired_scene_mismatch` at confidence `0.7`; the
  frozen target was direct `scene/desired_scene_absent`. This was an
  unsupported high-confidence overclaim.
- H15 SL: contextual `protection/boundary_alarm` at confidence `0.8`. The
  identity was precommitted, but contextual support does not receive direct
  reference credit. It was not counted as an unsupported overclaim.
- R1 SL: directly-supported-mode `protection/boundary_alarm` at confidence
  `0.8` without qualifying citation support. The case required motive unknown
  preservation, so this was both a high-confidence unsupported overclaim and
  an unknown-preservation violation.

Contextual hypotheses did not count as directly supported successes.

## 5. Confidence

- Action: 20 values, range `0.8–0.9`.
- Option: 12 values, all `0.9`.
- Motive: 15 values, range `0.7–0.9`.
- High-confidence unsupported motive threshold: `0.5`; count: `2`.

Every exact per-claim confidence remains available in its case
`case_result.json` and canonical structured output. Confidence did not repair
unsupported semantics.

## 6. Racio-reported uncertainty

All 16 outputs had valid three-state self-report structure. No failure case
introduced a synthetic fourth state, and no state was mechanically repaired.

| Field | `uncertain` | `not_uncertain` | `not_reported` |
|---|---:|---:|---:|
| Option mapping | 4 | 8 | 4 |
| Motive interpretation | 8 | 2 | 6 |

Descriptive comparison with evaluator references:

- All four evaluator-underdetermined option cases reported `uncertain`.
- Among 12 evaluator-unique option cases, eight reported `not_uncertain` and
  four `not_reported`.
- Among 14 motive-identifiable cases, seven reported `uncertain`, two
  `not_uncertain`, and five `not_reported`.
- The two motive-not-identifiable cases reported `uncertain` once and
  `not_reported` once.
- Bilingual consistency was `6/8` for option self-report and `5/8` for motive
  self-report.

Racio-reported uncertainty was recorded and compared descriptively. It was not
used as a hard pass/fail gate.

## 7. Slovenian-English consistency

| Dimension | Consistent pairs |
|---|---:|
| Action family | 8/8 |
| Exact action subtype | 7/8 |
| Action support mode | 6/8 |
| Option mapping | 8/8 |
| Motive family | 7/8 |
| Motive subtype | 6/8 |
| Motive support mode | 5/8 |
| Citation identity | 2/8 |
| Option uncertainty | 6/8 |
| Motive uncertainty | 5/8 |

Canonical evidence identity and source-mind consistency were both `8/8`.
Pair-level semantic differences were concentrated in:

- H3: action subtype/support mode, motive subtype/support mode, and citations.
- H15: action and motive support mode, plus citations.
- R1: motive family/subtype/support mode, citations, and motive uncertainty.
- H7 and H11: option-uncertainty differences.
- H11 and R5: motive-uncertainty differences.

The audited English gloss did not create a new observation identity, but equal
evidence identity did not force equal model claims or equal cited subsets.

## 8. Frozen G3 V2 versus G3C V3

Frozen G3 was not changed and was not retroactively re-evaluated with the V3
evaluator. The dimensions below are reported side by side; denominators with
different semantics are not declared equivalent.

| Dimension | Frozen G3 V2 / G3A | G3C V3 |
|---|---|---|
| Action family | Not represented in frozen V2; G3A descriptive family support SL 5/8, EN 8/8 | SL 6/8, EN 7/8; combined 13/16 |
| Exact action subtype | Frozen V2 action support 8/16; G3A descriptive exact support SL 2/8, EN 6/8 | SL 5/8, EN 6/8; combined 11/16 |
| Option mapping | 12 mapped, 4 required abstentions | 12/12 unique mappings; 4/4 abstentions |
| Option citations | 16/16 global V2 option citation support | 12/12 emitted option inferences with option-local support |
| Motive coverage | V2 categories: 4 supported, 1 hierarchy-compatible, 9 partial, 1 unknown-preserved, 1 unsupported | Direct family and subtype coverage 12/14; SL 5/7, EN 7/7 |
| Motive overclaims | 15 frozen V2 flags; G3A adjudicated 14 as true overclaims | 2 unsupported overclaims; SL 2, EN 0 |
| Bilingual action | 3/8 V2 action-consistent | V3 family 8/8; exact subtype 7/8 |
| Bilingual option | 8/8 | 8/8 |
| Bilingual motive | V2 family 7/8, subtype 4/8 | V3 family 7/8, subtype 6/8 |
| Bilingual uncertainty | 7/8 combined V2 self-report consistency | V3 option 6/8; motive 5/8 |

The V3 design sharply reduced unsupported motive overclaims and improved exact
action and motive-subtype visibility, while exposing weaker support-mode,
citation-identity, and uncertainty consistency. This is a dimensional
observation, not a promotion claim.

## 9. Individual failures

There were no provider, DraftV3, or canonicalizer failures. The table records
case-level semantic findings independently. `F/S` means family/exact-subtype
credit; `U O/M` is Racio's option/motive uncertainty self-report. R1 has no
direct motive target, so its motive F/S cell is `n/a`; the evaluator's vacuous
coverage value for a zero-target dimension is not presented as positive
credit.

| Case | A F/S | A over | Option | M F/S | M over | Motive unknown | U O/M | Semantic findings |
|---|---:|---:|---|---:|---:|---|---|---|
| `g3_h1_sl` | 1/0 | 1 | mapped | 1/1 | 0 | n/a | not_uncertain / uncertain | exact action miss; extra action overclaim |
| `g3_h1_en` | 1/0 | 1 | mapped | 1/1 | 0 | n/a | not_uncertain / uncertain | exact action miss; extra action overclaim |
| `g3_h3_sl` | 0/0 | 1 | mapped | 0/0 | 1 | n/a | not_uncertain / uncertain | action family/subtype/support-mode failure; high-confidence motive overclaim |
| `g3_h3_en` | 0/0 | 1 | mapped | 1/1 | 0 | n/a | not_uncertain / uncertain | action support-mode failure |
| `g3_h7_sl` | 1/1 | 1 | mapped | 1/1 | 0 | n/a | not_reported / uncertain | additional unsupported action |
| `g3_h7_en` | 1/1 | 1 | mapped | 1/1 | 0 | n/a | not_uncertain / uncertain | additional unsupported action |
| `g3_h11_sl` | 1/1 | 0 | mapped | 1/1 | 0 | n/a | not_uncertain / not_uncertain | none at case level |
| `g3_h11_en` | 1/1 | 0 | mapped | 1/1 | 0 | n/a | not_reported / not_reported | none at case level |
| `g3_h15_sl` | 0/0 | 1 | abstained | 0/0 | 0 | n/a | uncertain / not_reported | action support-mode failure; contextual motive received no direct credit |
| `g3_h15_en` | 1/1 | 0 | abstained | 1/1 | 0 | n/a | uncertain / not_reported | none at case level |
| `g3_r1_sl` | 1/1 | 0 | abstained | n/a | 1 | violated | uncertain / uncertain | high-confidence unsupported motive; required unknown violated |
| `g3_r1_en` | 1/1 | 0 | abstained | n/a | 0 | preserved | uncertain / not_reported | none at case level |
| `g3_r3_sl` | 1/1 | 0 | mapped | 1/1 | 0 | n/a | not_reported / not_reported | none at case level |
| `g3_r3_en` | 1/1 | 0 | mapped | 1/1 | 0 | n/a | not_reported / not_reported | none at case level |
| `g3_r5_sl` | 1/1 | 0 | mapped | 1/1 | 0 | n/a | not_uncertain / not_uncertain | none at case level |
| `g3_r5_en` | 1/1 | 0 | mapped | 1/1 | 0 | n/a | not_uncertain / uncertain | none at case level |

## Stop state

G3C completed as a technically valid 16-call development rerun. The result
does not promote Gemma and does not authorize governance, runtime, or GUI use.
No prompt or provider correction, G4 corpus, shadow integration, runtime
integration, PR, or merge was started.
