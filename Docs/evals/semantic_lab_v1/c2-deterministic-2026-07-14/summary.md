# C2 semantic evaluation summary

- Run ID: `c2-deterministic-2026-07-14`
- Source manifest SHA-256: `a2aed73eac97d68b90236da15d214b6121c84378800e85764fc267dba75bc7cc`
- Evaluator version: `c2-v1`
- Evaluator model calls: `0`
- Results: `32`
- Passing results: `8`
- Failing results: `24`
- Manually reviewed cases: `32`

> Metrics remain separated by dimension. This report does not compute a global REI score or a cross-dimension rank.

## Metrics by dimension

| Dimension | Metrics | Passed | Failed | N/A | Issues |
|---|---:|---:|---:|---:|---:|
| `schema_validity` | 24 | 23 | 1 | 0 | 1 |
| `provenance_completeness` | 24 | 18 | 6 | 0 | 6 |
| `allowed_option_validity` | 15 | 11 | 2 | 2 | 3 |
| `source_evidence_coverage` | 15 | 12 | 3 | 0 | 3 |
| `unsupported_claims` | 23 | 19 | 4 | 0 | 4 |
| `profile_leakage` | 23 | 22 | 1 | 0 | 1 |
| `hidden_ground_truth_leakage` | 23 | 22 | 1 | 0 | 1 |
| `confidence_calibration` | 23 | 21 | 2 | 0 | 2 |
| `abstention_correctness` | 15 | 14 | 1 | 0 | 1 |
| `slovenian_terminology` | 18 | 16 | 2 | 0 | 2 |
| `native_route_semantics` | 28 | 23 | 5 | 0 | 5 |
| `communication_fidelity` | 72 | 42 | 26 | 4 | 26 |
| `bilingual_consistency` | 12 | 10 | 2 | 0 | 2 |
| `ego_longitudinal` | 40 | 32 | 8 | 0 | 8 |
| `option_choice` | 0 | 0 | 0 | 0 | 0 |
| `character_causality` | 0 | 0 | 0 | 0 | 0 |
| `conscious_behavior_divergence` | 0 | 0 | 0 | 0 | 0 |
| `spoznanje` | 0 | 0 | 0 | 0 | 0 |
| `visual_robustness` | 0 | 0 | 0 | 0 | 0 |
| `body_mapper_agreement` | 0 | 0 | 0 | 0 | 0 |
| `longitudinal_motif_precision` | 5 | 3 | 1 | 1 | 0 |
| `latency` | 0 | 0 | 0 | 0 | 0 |
| `vram` | 0 | 0 | 0 | 0 | 0 |
| `ram` | 0 | 0 | 0 | 0 | 0 |
| `artifact_size` | 0 | 0 | 0 | 0 | 0 |
| `failure_mode` | 0 | 0 | 0 | 0 | 0 |

## Issues

| Result | Dimension | Severity | Code | Detail |
|---|---|---|---|---|
| `semantic_eval_2c711e042f0ccd1d27f506dd5a72af5c` | `bilingual_consistency` | error | `en_signature_mismatch` | Bilingual evaluation failed: en_signature_mismatch. |
| `semantic_eval_2c711e042f0ccd1d27f506dd5a72af5c` | `bilingual_consistency` | error | `cross_language_semantic_mismatch` | Bilingual evaluation failed: cross_language_semantic_mismatch. |
| `semantic_eval_9bc3ddd76ba179e8f28da13705576027` | `slovenian_terminology` | error | `bilingual_terminology_mismatch` | Bilingual evaluation failed: bilingual_terminology_mismatch. |
| `semantic_eval_9bd231d46801081bf45037b4f0dfcd59` | `ego_longitudinal` | error | `translation_gap_continuity_mismatch` | Longitudinal Ego evaluation failed: translation_gap_continuity_mismatch. |
| `semantic_eval_9bd231d46801081bf45037b4f0dfcd59` | `ego_longitudinal` | error | `unresolved_tension_continuity_mismatch` | Longitudinal Ego evaluation failed: unresolved_tension_continuity_mismatch. |
| `semantic_eval_3e7a522d035da286eedc859da50657a2` | `ego_longitudinal` | error | `false_motif` | Longitudinal Ego evaluation failed: false_motif. |
| `semantic_eval_3e7a522d035da286eedc859da50657a2` | `ego_longitudinal` | error | `missed_motif` | Longitudinal Ego evaluation failed: missed_motif. |
| `semantic_eval_3e7a522d035da286eedc859da50657a2` | `ego_longitudinal` | error | `motif_without_multi_measure_support` | Longitudinal Ego evaluation failed: motif_without_multi_measure_support. |
| `semantic_eval_e20f6abd6beda689f4dd41d084977619` | `ego_longitudinal` | error | `missed_motif` | Longitudinal Ego evaluation failed: missed_motif. |
| `semantic_eval_d3c731c0b3c86b86aa2f0669a8f8f983` | `ego_longitudinal` | error | `modality_projection_mismatch` | Longitudinal Ego evaluation failed: modality_projection_mismatch. |
| `semantic_eval_d3c731c0b3c86b86aa2f0669a8f8f983` | `ego_longitudinal` | error | `self_narrative_composition_conflation` | Longitudinal Ego evaluation failed: self_narrative_composition_conflation. |
| `semantic_eval_02430e84be05074fd2730a3f9c5410d9` | `communication_fidelity` | error | `option_misclassification` | Communication evaluation failed: option_misclassification. |
| `semantic_eval_02430e84be05074fd2730a3f9c5410d9` | `communication_fidelity` | error | `motive_misclassification` | Communication evaluation failed: motive_misclassification. |
| `semantic_eval_02430e84be05074fd2730a3f9c5410d9` | `communication_fidelity` | error | `omission_detected` | Typed evidence classifies this interpretation as omission. |
| `semantic_eval_55c49d18dff435f884db089ba401e7c3` | `provenance_completeness` | error | `incomplete_or_out_of_scope_provenance` | Communication evaluation failed: incomplete_or_out_of_scope_provenance. |
| `semantic_eval_55c49d18dff435f884db089ba401e7c3` | `unsupported_claims` | error | `unsupported_claim` | Communication evaluation failed: unsupported_claim. |
| `semantic_eval_55c49d18dff435f884db089ba401e7c3` | `communication_fidelity` | error | `option_misclassification` | Communication evaluation failed: option_misclassification. |
| `semantic_eval_55c49d18dff435f884db089ba401e7c3` | `communication_fidelity` | error | `motive_misclassification` | Communication evaluation failed: motive_misclassification. |
| `semantic_eval_55c49d18dff435f884db089ba401e7c3` | `communication_fidelity` | error | `action_misclassification` | Communication evaluation failed: action_misclassification. |
| `semantic_eval_55c49d18dff435f884db089ba401e7c3` | `communication_fidelity` | error | `missing_alternative_hypothesis` | Communication evaluation failed: missing_alternative_hypothesis. |
| `semantic_eval_55c49d18dff435f884db089ba401e7c3` | `communication_fidelity` | error | `projection_detected` | Typed evidence classifies this interpretation as projection. |
| `semantic_eval_a2e0361a00f06326d4eb36819da0ce76` | `communication_fidelity` | error | `option_misclassification` | Communication evaluation failed: option_misclassification. |
| `semantic_eval_a2e0361a00f06326d4eb36819da0ce76` | `communication_fidelity` | error | `motive_misclassification` | Communication evaluation failed: motive_misclassification. |
| `semantic_eval_a2e0361a00f06326d4eb36819da0ce76` | `communication_fidelity` | error | `action_misclassification` | Communication evaluation failed: action_misclassification. |
| `semantic_eval_a2e0361a00f06326d4eb36819da0ce76` | `communication_fidelity` | error | `missing_alternative_hypothesis` | Communication evaluation failed: missing_alternative_hypothesis. |
| `semantic_eval_a2e0361a00f06326d4eb36819da0ce76` | `communication_fidelity` | error | `misclassification_detected` | Typed evidence classifies this interpretation as misclassification. |
| `semantic_eval_8ea61d710c42d7ad2ebed806056f199b` | `communication_fidelity` | error | `option_misclassification` | Communication evaluation failed: option_misclassification. |
| `semantic_eval_8ea61d710c42d7ad2ebed806056f199b` | `communication_fidelity` | error | `motive_misclassification` | Communication evaluation failed: motive_misclassification. |
| `semantic_eval_8ea61d710c42d7ad2ebed806056f199b` | `communication_fidelity` | error | `action_misclassification` | Communication evaluation failed: action_misclassification. |
| `semantic_eval_8ea61d710c42d7ad2ebed806056f199b` | `communication_fidelity` | error | `missing_alternative_hypothesis` | Communication evaluation failed: missing_alternative_hypothesis. |
| `semantic_eval_8ea61d710c42d7ad2ebed806056f199b` | `communication_fidelity` | error | `minimization_detected` | Typed evidence classifies this interpretation as minimization. |
| `semantic_eval_043bbe6f670926796831bcf9a3390c91` | `provenance_completeness` | error | `incomplete_or_out_of_scope_provenance` | Communication evaluation failed: incomplete_or_out_of_scope_provenance. |
| `semantic_eval_043bbe6f670926796831bcf9a3390c91` | `unsupported_claims` | error | `unsupported_claim` | Communication evaluation failed: unsupported_claim. |
| `semantic_eval_043bbe6f670926796831bcf9a3390c91` | `communication_fidelity` | error | `option_misclassification` | Communication evaluation failed: option_misclassification. |
| `semantic_eval_043bbe6f670926796831bcf9a3390c91` | `communication_fidelity` | error | `motive_misclassification` | Communication evaluation failed: motive_misclassification. |
| `semantic_eval_043bbe6f670926796831bcf9a3390c91` | `communication_fidelity` | error | `action_misclassification` | Communication evaluation failed: action_misclassification. |
| `semantic_eval_043bbe6f670926796831bcf9a3390c91` | `communication_fidelity` | error | `missing_alternative_hypothesis` | Communication evaluation failed: missing_alternative_hypothesis. |
| `semantic_eval_043bbe6f670926796831bcf9a3390c91` | `confidence_calibration` | error | `overconfident_interpretation` | Communication evaluation failed: overconfident_interpretation. |
| `semantic_eval_043bbe6f670926796831bcf9a3390c91` | `communication_fidelity` | error | `rationalization_detected` | Typed evidence classifies this interpretation as rationalization. |
| `semantic_eval_5a02a4a18aafb383a9b7a80f400b16ea` | `communication_fidelity` | error | `unknown_detected` | Typed evidence classifies this interpretation as unknown. |
| `semantic_eval_9005822cba9eb44845e3d8df9e4a4dd5` | `communication_fidelity` | error | `option_misclassification` | Communication evaluation failed: option_misclassification. |
| `semantic_eval_9005822cba9eb44845e3d8df9e4a4dd5` | `communication_fidelity` | error | `partial_detected` | Typed evidence classifies this interpretation as partial. |
| `semantic_eval_a1a6d425e547fec20f4ff31755233739` | `source_evidence_coverage` | error | `missing_source_evidence` | Canonical route evidence is absent from candidate claims. |
| `semantic_eval_ed43be5dca26fa2bb69ad07e21302671` | `slovenian_terminology` | error | `slovenian_terminology_mismatch` | Required canonical Slovene terminology is missing or altered. |
| `semantic_eval_41d4ce6bf8c874b3c7e90511d89fe52f` | `allowed_option_validity` | error | `invalid_option_id` | Candidate option differs from the canonical scoped option. |
| `semantic_eval_41d4ce6bf8c874b3c7e90511d89fe52f` | `abstention_correctness` | error | `incorrect_abstention` | Candidate abstention differs from the trusted case. |
| `semantic_eval_41d4ce6bf8c874b3c7e90511d89fe52f` | `native_route_semantics` | error | `native_route_mismatch` | Structured route semantics differ from the canonical case. |
| `semantic_eval_4b3da7bc704470f9365f610520129172` | `profile_leakage` | error | `profile_leakage` | Actual provider/interpreter inputs expose profile artifacts. |
| `semantic_eval_89bbf3d3eeb11d2265221b8bf87ad520` | `provenance_completeness` | error | `incomplete_or_out_of_scope_provenance` | Claim or input lineage is missing or outside trusted scope. |
| `semantic_eval_89bbf3d3eeb11d2265221b8bf87ad520` | `unsupported_claims` | error | `unsupported_claim` | Candidate contains unsupported claims. |
| `semantic_eval_a4f5e0e9c2092721befc08065299c3ae` | `provenance_completeness` | error | `incomplete_or_out_of_scope_provenance` | Claim or input lineage is missing or outside trusted scope. |
| `semantic_eval_a4f5e0e9c2092721befc08065299c3ae` | `allowed_option_validity` | error | `invalid_option_id` | Candidate option differs from the canonical scoped option. |
| `semantic_eval_a4f5e0e9c2092721befc08065299c3ae` | `source_evidence_coverage` | error | `missing_source_evidence` | Canonical route evidence is absent from candidate claims. |
| `semantic_eval_a4f5e0e9c2092721befc08065299c3ae` | `unsupported_claims` | error | `unsupported_claim` | Candidate contains unsupported claims. |
| `semantic_eval_a4f5e0e9c2092721befc08065299c3ae` | `native_route_semantics` | error | `native_route_mismatch` | Structured route semantics differ from the canonical case. |
| `semantic_eval_a4f5e0e9c2092721befc08065299c3ae` | `native_route_semantics` | error | `emocio_scene_or_renderer_boundary_failure` | Emocio scene facets are missing, the mind is wrong, or renderer-only material was treated as fact. |
| `semantic_eval_895ffcda18e77d2ad5078f77d638fb49` | `confidence_calibration` | error | `miscalibrated_confidence` | Confidence is incompatible with observed route correctness. |
| `semantic_eval_0c6dfebb0fa590c9f966e0eda1b4c53f` | `provenance_completeness` | error | `incomplete_or_out_of_scope_provenance` | Candidate cites source artifacts absent from trusted exposure. |
| `semantic_eval_26249ec0697346e404c9495f55ba3f71` | `allowed_option_validity` | error | `invalid_option_id` | Candidate option differs from the canonical scoped option. |
| `semantic_eval_26249ec0697346e404c9495f55ba3f71` | `native_route_semantics` | error | `native_route_mismatch` | Structured route semantics differ from the canonical case. |
| `semantic_eval_863095aff0771d1efd80131c8b16840e` | `schema_validity` | error | `schema_invalid` | Candidate schema validation failed with 9 error(s). |
| `semantic_eval_3aceba11acf4e9258bfa05e124e63fa5` | `provenance_completeness` | error | `incomplete_or_out_of_scope_provenance` | Claim or input lineage is missing or outside trusted scope. |
| `semantic_eval_3aceba11acf4e9258bfa05e124e63fa5` | `source_evidence_coverage` | error | `missing_source_evidence` | Canonical route evidence is absent from candidate claims. |
| `semantic_eval_3aceba11acf4e9258bfa05e124e63fa5` | `hidden_ground_truth_leakage` | error | `hidden_ground_truth_leakage` | Actual inputs expose evaluator-only native truth. |
| `semantic_eval_3aceba11acf4e9258bfa05e124e63fa5` | `native_route_semantics` | error | `native_route_mismatch` | Structured route semantics differ from the canonical case. |

## Evaluated provider provenance

| Result | Provider | Provider revision | Model | Model revision | Seed |
|---|---|---|---|---|---:|
| — | — | — | — | — | — |

## Artifacts

- `summary.md`
- `metrics.json`
- `failures.jsonl`
- `confusion_matrices.json`
- `bilingual_consistency.json`
- `human_review_summary.md`
