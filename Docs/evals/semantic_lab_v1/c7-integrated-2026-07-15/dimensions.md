# C7 integrated semantic and longitudinal benchmark

- Report ID: `c7_integrated_benchmark_57c1db13906284edd641ac7cfbc6f5dc`
- Technical contract: **PASS**
- Research quality: **BLOCKED**
- Aggregate REI score: **absent by contract**
- Current model calls: **0**
- Semantic authority: **false**
- Production authority: **false**

The dimensions below are intentionally not collapsed into a rank or score.
Historical observations retain their original scope; bounded software passes
do not become claims about people or semantic model approval.

| Dimension | Status | Observation | Scope limitation |
|---|---|---:|---|
| `processor_route_identity` | `passed` | 468/468 bounded_rows | All 468 rows reuse frozen native bundle and governance identities; native processors are not rerun in this controlled cohort. |
| `source_grounding` | `blocked` | 29/32 historical_structured_outputs | The historical model run produced 29/32 valid structured outputs and three citation-scope failures, so research grounding is not passed. |
| `option_choice` | `blocked` | 16/16 historical_unambiguous_cases | Exact option choice is 16/16 only on the unambiguous subset; the complete C3 structural and ambiguity gates remain failed. |
| `abstention` | `blocked` | 13/16 historical_ambiguous_cases | The frozen model-backed ambiguity gate passed 13/16; the C2 negative fixture taxonomy is preserved but is not relabeled as model quality. |
| `translation_fidelity` | `blocked` | 14/16 historical_unambiguous_motive_cases | Motive fidelity is 14/16 in unambiguous C3 cases and no VLM arm was executed, so translation fidelity is not research-ready. |
| `character_causality` | `passed` | 4/4 deterministic_simulator_cases | Pass is limited to deterministic simulator intervention and same-world counterfactual probes; population and full-history claims are excluded. |
| `conscious_behavior_divergence` | `passed` | 209/468 synthetic_profile_rows | Divergence is reported as a categorical outcome distribution across three synthetic acceptance modes, not as a quality target. |
| `spoznanje` | `passed` | 85/85 expected_simulated_cycles | All 85 expected C6 simulated spoznanje cycles were reproduced; this is a bounded deterministic contract. |
| `cross_language_consistency` | `blocked` | 14/16 historical_bilingual_pairs | The best pinned C3 model run is consistent on 14/16 pairs and has no paired VLM comparator. |
| `visual_robustness` | `blocked` | 0/48 required_editor_member_cells | The complete reviewed visual robustness matrix remains unexecuted at 0/48; technical one-cell smokes do not substitute for it. |
| `body_mapper_agreement` | `passed` | 36/36 bounded_positive_cases | Manual/auto outcomes agree on all 36 bounded cases; the selected subset is 33/33 and the remaining cases are matching abstentions. |
| `longitudinal_motif_precision` | `passed` | 40/40 structured_tag_motifs | Precision 40/40 is restricted to stage-1 structured tags; the semantic motif hypothesis arm remains a separate explicit blocker. |
| `latency` | `observed` | 3.06543888086 historical_mean_seconds_per_response | Historical response telemetry exists for 29 of 32 model calls; three failed calls emitted no response evidence and RAM was not measured. |
| `vram` | `observed` | 19040451951 historical_max_bytes | Historical response telemetry exists for 29 of 32 model calls; three failed calls emitted no response evidence and RAM was not measured. |
| `ram` | `not_measured` | not measured | No trustworthy RAM measurement exists across the required ablation arms; C7 does not infer RAM from VRAM or model size. |
| `artifact_size` | `observed` | 1398099 pinned_source_bytes | Value is the exact byte sum of the 11 pinned input artifacts; each generated C7 artifact is reported separately in provenance. |
| `failure_mode` | `passed` | 5/5 typed_reproducible_blockers | Every readiness blocker is emitted as a typed reproducible failure record; this does not mean the blocked quality dimensions passed. |

## Research-readiness blockers

- `c3_model_quality_gate_failed`: The pinned Qwen3.5 27B v5 run outperformed the deterministic baseline but failed structural and quality gates: 29/32 structured outputs, 13/16 ambiguity gates and 14/16 bilingual pairs.
- `c4_semantic_visual_gate_open`: C4 technical integration passed, but the complete visual robustness matrix remains 0/48 and semantic, production and external-evidence authority remain closed.
- `vlm_interpreter_arm_not_executed`: No authority-bearing structured-versus-VLM interpreter comparison exists; C7 performs no replacement model call.
- `semantic_motif_arm_not_executed`: C6 validates structured-tag motifs only; a semantic motif hypothesis arm has not been executed or independently reviewed.
- `uniform_resource_telemetry_missing`: Latency and VRAM are historical C3 observations for 29 responses; RAM and uniform telemetry across all ablation arms were not measured.

## Ablation disposition

| Family | Status | Arms | Interaction effects |
|---|---|---|---|
| `racio_provider` | `blocked` | `deterministic` (observed), `qwen3.5_27b_v5` (failed) | not measured |
| `emocio_cognition_mode` | `blocked` | `structured_only` (passed), `render_observe` (failed), `visual_cognition` (blocked) | not measured |
| `instinkt_effect_source` | `passed` | `manual_effects` (passed), `auto_mapper` (passed) | not measured |
| `interpreter_input_mode` | `blocked` | `structured_only` (observed), `vlm` (blocked) | not measured |
| `ego_motif_mode` | `blocked` | `structured_motif` (passed), `semantic_motif_hypothesis` (blocked) | not measured |
| `acceptance_mode` | `passed` | `accepting` (passed), `mixed` (passed), `conflicted` (passed) | not measured |
