# C4 real renderer smoke — 2026-07-14

## Outcome

**TECHNICAL RENDERER SCOPE PASSED; SEMANTIC MODEL QUALITY GATE OPEN.**

The pinned FLUX.2 Klein 4B current-first renderer completed an offline batch of
five 512 × 512 images with exact model, snapshot, seed, prompt-profile, source
image and provider-call provenance. Every option rollout reused the same
byte-verified current image. Generated images remained internal imagined
artifacts and never became external evidence.

Human review did not accept the renderer candidate for semantic rollout use.
Across controlled prompt iterations the model alternated between losing the
central source subject and producing visually collapsed option actions. The
architecture and technical adapter are retained; `visual_cognition` must not
trust this model until encoder-backed collapse detection and the full C4
robustness review pass.

## Pinned execution

| Field | Exact value |
|---|---|
| model | `black-forest-labs/FLUX.2-klein-4B` |
| revision | `e7b7dc27f91deacad38e78976d1f2b499d76a294` |
| Diffusers | `0.39.0` |
| PyTorch | `2.13.0+cu130` |
| Transformers | `5.13.0` |
| GPU | NVIDIA GeForce RTX 5090, compute capability 12.0 |
| snapshot manifest | `fb1ecb3a4d7fe439949b83f0e183438ab35a6df2bc01d66c5d3cd9966a4c7183` |
| snapshot inventory | 24 files, 15,988,901,735 bytes |
| root seed | `424242` |
| settings | 512 × 512, 4 steps, guidance 1.0, cooperative timeout 180 s |
| network boundary | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, verified local snapshot |
| peak allocated GPU memory | 16,711,031,808 bytes |

The timeout is a synchronous cooperative monotonic deadline checked around
snapshot verification, pipeline load, device transfer, inference and each
diffusion step. It is explicitly not hard cancellation of an active CUDA
kernel. No thread, future or background render continues after return.

## Final technical run

The final create-only run completed in 23.232194 seconds:

- batch: `render_batch_a153af31a1465cfb2964f094aed31697`;
- status: `succeeded`;
- artifacts: 5 of 5;
- exact current source reused for every rollout: true;
- prompt profile matched every request: true;
- grounded-evidence contamination: none;
- pass scope: `technical_renderer_lineage_and_provenance_only`;
- semantic review status: `requires_human_review`.

Final artifact IDs and SHA-256 values, in canonical current, desired, broken,
`enter_circle`, `remain_edge` order:

| Role | Artifact ID | PNG SHA-256 |
|---|---|---|
| current | `image_432c0a4b0122006c73d9ecb1f78a968f` | `34fe46897ee3201575ee2f237f5432d48363c062680042d1d1671581feee234d` |
| desired | `image_39ecce4e127e3aa58179c657548edca8` | `e04f9d9666bf4fc7043fa28b09bc0abc1759e087152415e01fd272676f8917ab` |
| broken | `image_a7c9c094b2bc054655a4274da080f5c0` | `a590931074588bb6b41c6e8f9b2e718204bc34d0626594251204193a62557801` |
| `enter_circle` | `image_808c0969dc1336716101fe5774cbd7b8` | `d7cb0442c946fe706ed8a09f40691157308659875d0d2a4aec4fb600ab66d729` |
| `remain_edge` | `image_d4c80b389f32f499732b93fa8d70a7fe` | `76576b1f96bbcd4be10afc90690c93e145101445c0db9f68f9e3ee4e8619f120` |

Different PNG hashes prove only different bytes, not different semantics.

## Human visual review trail

| Attempt | Technical result | Human semantic observation |
|---:|---|---|
| 1 | passed | Both option rollouts depicted entering; action collapse. |
| 2 | passed | Actions diverged, but `remain_edge` removed the central source subject. |
| 3 | passed | Stronger preservation text still removed the central source subject. |
| 4 | passed | Subject identity was retained, but both option actions became effectively stationary. |
| 5 | passed | A concise primary-edit instruction retained identity but did not create a reliable action distinction. |
| 6 | passed | Explicit threshold-distance deltas still yielded near-identical rollout actions; the generated current scene itself placed the subject inside the threshold. |

This trail is intentionally retained as negative evidence. The smoke runner's
`passed` field is scoped only to technical rendering, lineage and provenance;
it also emits `semantic_quality_gate_passed=false` and requires human review.

## Contract and regression evidence

The repository suite completed with **839 passed** after the final hardening.
It includes:

- historical T2I and classic-strength img2img identity compatibility;
- explicit C4 reference-image lineage;
- byte-closed cache hits and corrupt-cache fail-closed behavior;
- directory-symlink and Windows reparse-point snapshot rejection;
- exact current-image reuse across every rollout;
- SL/EN prompt provenance and rollout guard parity;
- timeout status, no-artifact and no-fallback behavior;
- unchanged `structured_only` contracts.

## Decision

C4.2 is accepted as a provenance-closed local renderer implementation. FLUX.2
Klein 4B remains an `implementation_hypothesis`, not an accepted default. The
next C4 slice must add the pinned DINOv2 encoder, typed visual comparison and an
explicit uncertainty/collapse path before generated images may affect an
Emocio native conclusion. Full seed/style/language/option-order robustness and
human review remain C4 phase gates.
