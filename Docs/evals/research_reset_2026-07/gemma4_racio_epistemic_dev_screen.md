# Gemma 4 Racio epistemic G3 development screen — 2026-07-17

This is the bounded G3 development screen authorized for eight precommitted
semantic roots in Slovenian and English. It is not a promotion decision, a
runtime-integration decision, or an aggregate semantic pass/fail result. The
ten dimensions below remain independent.

## Scope and provenance

- Suite: `rei-racio-gemma4-epistemic-dev-v1`; 16 cases in the fixed order
  H1, H3, H7, H11, H15, R1, R3, R5, with SL then EN for each root.
- Sealed source commit: `d9027d97faec36f1d2c806a5efe5e935ed931014`.
- Corpus manifest SHA-256:
  `07172858ac94a5e78dc4bf2d49e14030f5ad85021e62c120265e356063f9a6de`.
- Provider revision: `rei-racio-gemma4-epistemic-g2-chat-v6`; endpoint
  `/api/chat`; Ollama `0.31.2`.
- Model: `gemma4:31b`; exact digest
  `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`.
- Frozen instruction SHA-256:
  `4137891d92dec4b90875ee755f7ca5d67fc9d93e733180a85803a6b891840b91`;
  output-schema SHA-256:
  `16602d51fb48f6b64b415ea22693bae16ebf67a97a9ca52703cdd58ca4cae49e`.
- Frozen evaluator SHA-256:
  `b30ad1695d68b781932352c6b9c5429191544fd48be5f09edb9752851c4b6d03`.
- Seed `314159`; temperature `0.0`; top-p `0.95`; top-k `64`;
  `num_ctx=65536`; `num_gpu=999`; `num_predict=16384`; timeout `600s`;
  thinking enabled and private; stream/raw disabled; keep-alive `10m`.
- Execution window: `2026-07-17T11:32:38.713249Z` through
  `2026-07-17T11:39:17.752127Z`.
- G3 calls/retries/fallbacks: `16 / 0 / 0`; provider successes/failures:
  `16 / 0`. Runtime evidence recorded context `65536` and `100% GPU` for
  every successful response.
- All 16 call-spec hashes were frozen before the first dispatch and are stored
  in the [preflight ledger](../semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/attempt_ledger/001_preflight_complete.json).
- Sanitized per-case evidence, validated outputs, call records, evaluations,
  and bilingual receipts are stored in the
  [evidence bundle](../semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/).
  The [cold-validation receipt](../semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/cold_validation.json),
  which is excluded from its own 204-file evidence fingerprint, records
  independent replay of all 16 execution lineages, all 16 case
  evaluations, and all eight bilingual evaluations. Private thinking text and
  raw response envelopes were not persisted.

The generated [summary](../semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/summary.json)
contains only provider failure-code counts under its compact
`individual_failures` key, so that empty object must not be read as absence of
semantic findings. Section 10 below is sourced from the canonical
[report](../semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/report.json)
and the 16 per-case evaluations.

## 1. Structural contract

- `structural_output_valid`: 16 true, 0 false.
- `citation_scope_valid`: 16 true, 0 false.
- `input_packet_unchanged`: 16 true, 0 false.
- `hard_contract_pass`: 16 true, 0 false.
- Every call produced a validated structured output, response evidence, and a
  successful `ProviderCallRecord`. Every case also has its own bilingual pair
  evaluation receipt.

This is only the structural hard gate. It is not evidence that the action,
option, motive, confidence, or bilingual semantics are correct.

## 2. Action interpretation

Action interpretation was supported in 8 cases and unsupported in 8. Action
citation support was valid in all 16 cases; a citation can be in scope while
the inferred action label is still unsupported by evaluator gold.

| Case | Model action | Expected action |
|---|---|---|
| `g3_h1_sl` | `protect` | `connect` |
| `g3_h1_en` | `approach` | `connect` |
| `g3_h3_sl` | `set_boundary` | `protect` |
| `g3_h7_sl` | `seek_safety` | `set_boundary` |
| `g3_h15_sl` | `protect` | `set_boundary` |
| `g3_h15_en` | `protect` | `set_boundary` |
| `g3_r1_sl` | `conserve` | `attack` |
| `g3_r5_sl` | `seek_attachment` | `perform` |

The other eight action interpretations were supported.

## 3. Option mapping

- All 12 cases with a unique option mapped to the acceptable option.
- All four underdetermined cases returned the required abstention.
- Option citation support was valid in all 16 cases.
- Option mapping was bilingual-consistent in all eight pairs.

The option result is reported independently of the weaker action and motive
dimensions.

## 4. Required abstention

Required abstention was observed in all four applicable cases:
`g3_h15_sl`, `g3_h15_en`, `g3_r1_sl`, and `g3_r1_en`. Each returned
`inferred_option_id=null` and `option_confidence=0.0`. The remaining 12 cases
were correctly classified as not requiring abstention.

## 5. Motive hypotheses

| Evaluator status | Count | Cases |
|---|---:|---|
| `supported` | 4 | H15 SL/EN; R5 SL/EN |
| `hierarchy_compatible` | 1 | H11 SL |
| `partially_supported` | 9 | H1 SL/EN; H3 SL/EN; H7 SL/EN; H11 EN; R3 SL/EN |
| `unknown_preserved` | 1 | R1 SL |
| `unsupported` | 1 | R1 EN |

Motive-family and exact-hypothesis coverage were both `1.0` in 15 cases and
`0.0` only in `g3_r1_en`. Motive citation failure count was zero in all 16
cases. Full coverage means that an expected hypothesis was present; it does
not erase additional unsupported hypotheses, which remain counted separately
as overclaims.

## 6. Unsupported overclaims

The evaluator counted 15 unsupported motive hypotheses across 10 cases.

| Case | Unsupported motive overclaims |
|---|---:|
| `g3_h1_sl` | 1 |
| `g3_h1_en` | 2 |
| `g3_h3_sl` | 1 |
| `g3_h3_en` | 2 |
| `g3_h7_sl` | 1 |
| `g3_h7_en` | 1 |
| `g3_h11_en` | 1 |
| `g3_r1_en` | 2 |
| `g3_r3_sl` | 2 |
| `g3_r3_en` | 2 |

The count was zero for `g3_h11_sl`, both H15 cases, `g3_r1_sl`, and both R5
cases.

## 7. Confidence

- Action confidence was within the evaluator bound in 16/16 cases.
- Option confidence was within the evaluator bound in 16/16 cases.
- Motive confidence was within the evaluator bound in 15/16 cases.
- `g3_r1_en` was the only motive-confidence violation: evaluator gold permits
  no motive hypothesis (`maximum_motive_confidence=0.0`), while the output
  assigned `0.4` and `0.3` to two unsupported motives.
- H11's hierarchical gold intentionally has no hard maximum-motive-confidence
  cap; its `1.0` value is therefore descriptive rather than accepted by a
  confidence hard gate.

Per-case values are action / option / motive confidences:

| Case | A | O | M |
|---|---:|---:|---|
| `g3_h1_sl` | 0.8 | 0.7 | [0.7, 0.5] |
| `g3_h1_en` | 0.8 | 0.8 | [0.7, 0.5, 0.4] |
| `g3_h3_sl` | 0.8 | 0.8 | [0.7, 0.5] |
| `g3_h3_en` | 0.6 | 0.7 | [0.7, 0.5, 0.3] |
| `g3_h7_sl` | 0.8 | 0.8 | [0.7, 0.6] |
| `g3_h7_en` | 0.8 | 0.8 | [0.7, 0.5] |
| `g3_h11_sl` | 1.0 | 1.0 | [1.0] |
| `g3_h11_en` | 1.0 | 1.0 | [1.0, 0.8] |
| `g3_h15_sl` | 0.8 | 0.0 | [0.9] |
| `g3_h15_en` | 0.8 | 0.0 | [0.9] |
| `g3_r1_sl` | 0.6 | 0.0 | [] |
| `g3_r1_en` | 0.6 | 0.0 | [0.4, 0.3] |
| `g3_r3_sl` | 1.0 | 1.0 | [1.0, 0.7, 0.5] |
| `g3_r3_en` | 1.0 | 1.0 | [1.0, 0.8, 0.6] |
| `g3_r5_sl` | 1.0 | 1.0 | [1.0] |
| `g3_r5_en` | 0.8 | 0.9 | [0.7] |

## 8. Racio-reported uncertainty

The self-report structure was valid in 16/16 cases. No case used
`not_reported`. No value was mechanically repaired, and no self-report value
was used as a hard pass/fail gate.

| Root | SL self-report (option / motive) | EN self-report (option / motive) | Evaluator reference (option / motive) |
|---|---|---|---|
| H1 | `not_uncertain` / `uncertain` | same | `unique` / `unique` |
| H3 | `not_uncertain` / `uncertain` | same | `unique` / `unique` |
| H7 | `not_uncertain` / `not_uncertain` | same | `unique` / `unique` |
| H11 | `not_uncertain` / `not_uncertain` | same | `unique` / `hierarchical` |
| H15 | `uncertain` / `not_uncertain` | same | `underdetermined` / `unique` |
| R1 | `uncertain` / `uncertain` | same | `underdetermined` / `not_identifiable` |
| R3 | `not_uncertain` / `not_uncertain` | same | `unique` / `unique` |
| R5 | `not_uncertain` / `not_uncertain` | `not_uncertain` / `uncertain` | `unique` / `unique` |

Descriptively, the option self-report is `not_uncertain` in all 12 unique
cases and `uncertain` in all four underdetermined cases. Motive self-report is
`uncertain` in seven cases and `not_uncertain` in nine. H1 and H3 are
conservative relative to unique motive gold; R1 reports uncertainty where the
motive is not identifiable; R5 EN reports uncertainty where motive gold is
unique. Bilingual uncertainty consistency is 7/8, with the R5 motive state as
the only mismatch. These are self-reports, not objective correctness evidence,
and calibration remains a separate future evaluation.

## 9. Slovenian-English consistency

| Dimension | Consistent pairs | Mismatched pairs |
|---|---:|---|
| Source mind | 8/8 | none |
| Option mapping | 8/8 | none |
| Action | 3/8 | H1, H3, H7, R1, R5 |
| Motive family | 7/8 | R1 |
| Motive subtype | 4/8 | H1, H3, H11, R1 |
| Citation set | 7/8 | R1 |
| Racio-reported uncertainty | 7/8 | R5 |
| Action confidence | 6/8 | H3, R5 |
| Option confidence | 8/8 | none |
| Motive confidence | 3/8 | H1, H3, H11, R1, R5 |

Pair consistency is not semantic correctness. H15 is action-consistent because
both languages returned the same unsupported `protect` label. H1 returned two
different unsupported action labels. H3, H7, R1, and R5 each had one supported
and one unsupported action label.

## 10. Individual failures

There were no provider failures. Evaluator research observations were recorded
for 14 cases; `g3_h11_sl` and `g3_r5_en` had none.

| Case | Independent evaluator findings |
|---|---|
| `g3_h1_sl` | action support failure; partial motive support; 1 overclaim |
| `g3_h1_en` | action support failure; partial motive support; 2 overclaims |
| `g3_h3_sl` | action support failure; partial motive support; 1 overclaim |
| `g3_h3_en` | partial motive support; 2 overclaims |
| `g3_h7_sl` | action support failure; partial motive support; 1 overclaim |
| `g3_h7_en` | partial motive support; 1 overclaim |
| `g3_h11_en` | partial motive support; 1 overclaim |
| `g3_h15_sl` | action support failure |
| `g3_h15_en` | action support failure |
| `g3_r1_sl` | action support failure |
| `g3_r1_en` | unsupported motive support; 2 overclaims; motive-confidence bound violation |
| `g3_r3_sl` | partial motive support; 2 overclaims |
| `g3_r3_en` | partial motive support; 2 overclaims |
| `g3_r5_sl` | action support failure |

No aggregate semantic score or pass/fail result is derived from this table or
from any other section. Gemma is not promoted, no runtime integration is
started, and this screen does not authorize another phase.
