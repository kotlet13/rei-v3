# C4 real DINOv2 visual-valuation smoke — 2026-07-14

## Outcome

**TECHNICAL ENCODER/VALUATION SCOPE PASSED; VISUAL FUSION REFUSED.**

The pinned offline DINOv2 adapter encoded all five byte-verified images from
the final FLUX.2 Klein renderer attempt. Every result retained the exact image,
request, provider call, model revision, vector bytes and SHA-256 lineage. The
visual valuation then detected near-identical option rollouts and returned
`review_action_collapse`; the candidate is therefore not allowed to influence
an Emocio native conclusion.

This is the intended fail-closed result. It confirms the technical C4.3 path,
not semantic acceptance of the renderer candidate. Full seed, style, language
and renderer robustness review remains open.

## Pinned execution

| Field | Exact value |
|---|---|
| encoder | `facebook/dinov2-base` |
| revision | `f9e44c814b77203eaa57a6bdbbd535f21ede1415` |
| provider | `provider_65781a4384ab344396b6599ee59728a8` |
| snapshot manifest | `786481f81ca90d17eada5cd387835e457f1e531e93ec38a7671368dbb8249ba1` |
| snapshot verification | full SHA-256 before every call and after inference |
| snapshot trust boundary | trusted local filesystem |
| feature | CLS token, 768 dimensions, L2-normalized float32 little-endian |
| image processor | pinned `pil` backend |
| deterministic runtime | reasserted before every inference |
| PyTorch | `2.13.0+cu130` |
| Torchvision | `0.28.0` |
| Pillow | `12.3.0` |
| Transformers | `5.13.0` |
| device | NVIDIA GeForce RTX 5090, CUDA |
| network boundary | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` |
| policy config | `visual_policy_config_6515948ecb9889666d1dd0dc2e741d42` |
| policy | `visual_valuation_policy_d0f88857d195481f576fb414838ab873` |
| source render batch | `render_batch_a153af31a1465cfb2964f094aed31697` |
| source visual state | `emocio_state_a306d40b26c9ca65f1d5ddeb86953ead` |
| source visual state hash | `59fb47055ecd982954c7895f4386c69544bd2dd112ab44451d276abdd3e59543` |
| elapsed encoder + valuation time | 7.737375 seconds |

The production smoke runner was invoked in create-only mode:

```powershell
python scripts/run_rei_emocio_visual_valuation_smoke.py `
  --renderer-output-directory <verified-renderer-output> `
  --snapshot-directory <verified-dinov2-snapshot> `
  --snapshot-manifest-sha256 786481f81ca90d17eada5cd387835e457f1e531e93ec38a7671368dbb8249ba1 `
  --output-directory <new-output-directory> `
  --expected-render-batch-id render_batch_a153af31a1465cfb2964f094aed31697 `
  --expected-render-batch-hash e68c799557f7595f109ef1dbd4977597a2d183044dcdaa37da1d67adb9e4ce91 `
  --expected-root-seed 424242 `
  --expected-renderer-provider-id provider_f9be5d4210751d6581ee2dffad9691ea `
  --expected-renderer-model black-forest-labs/FLUX.2-klein-4B `
  --expected-renderer-revision e7b7dc27f91deacad38e78976d1f2b499d76a294 `
  --expected-prompt-profile-hash 26908b02adc969b1c894b46f69bbd1c81a92464cc62b1e74b4217d9edd06a3c8 `
  --device cuda `
  --timeout-seconds 120
```

The runner revalidates the canonical scene, packet, compiled scene specs and
render batch before model loading. It writes the grounded boundary, imagined
artifacts, exact visual state, verified encodings, bound observations,
valuation, rollout memory and smoke evidence as separate canonical JSON
artifacts. Every observation carries the complete revalidated render batch;
the evaluator requires one exact batch per seed, one renderer/prompt cohort,
mode-specific pipeline closure, the exact current-image rollout source and one
encoding spec. Structured option scores are recalculated from the visual state
instead of trusting caller-provided values. Vector files are content-addressed
`.f32` artifacts. The output also copies the exact canonical source-renderer
JSON and verified PNG bytes, then seals every output file in a content-addressed
`bundle_manifest.json`. Smoke evidence records SHA-256 values for the runner,
encoder, vector, valuation, memory, structured-valuation, renderer-validation,
provider/model contracts and policy files used by the run.

The 120-second value is a cooperative monotonic deadline checked around image
and snapshot verification, inference, vector canonicalization and persistence.
It is not hard cancellation of a blocked CUDA kernel. The evidence records
`hard_cancellation=false`; production isolation remains required for a hard
wall-clock kill guarantee.

Pre/post-inference SHA-256 checks reject persistent snapshot mutation before a
vector can be published. The pinned snapshot directory is nevertheless inside
the trusted-local-filesystem boundary: a same-credential adversarial writer
that swaps weights only during model loading and restores them before the
post-check is outside this adapter's guarantee. Such a threat requires an
immutable mount or an isolated model-serving process.

Encoding IDs and exact vector hashes are stable for the pinned input and local
runtime. Observation, comparison and valuation IDs additionally include the
actual provider-call records and timestamps, so they identify one execution
rather than claiming cross-run identity. Replay checks the stored execution
exactly; cross-device bit identity is not claimed.

## Exact encoding evidence

Rows use canonical `current`, `desired`, `broken`, `enter_circle`,
`remain_edge` order.

| Role | Encoding ID | Vector SHA-256 |
|---|---|---|
| current | `image_encoding_c2dd7a521b77a484f33b535517eada87` | `5058e382b7c2e9c8af1dfdf731bda39719e050c86050cf046628b01da11f9e7c` |
| desired | `image_encoding_2227afd397a51705586dd16e57286bdd` | `598b37f57414287abb011dfb5ed53fdac61a601373d8f74cd61c5953b2429f5e` |
| broken | `image_encoding_3dcb22ac2c0665e558e06ad4c4e9adb0` | `7ccc5a14b4294d1b6080c3a77048c263037419cd50468bf89af506df360f919a` |
| `enter_circle` | `image_encoding_489f4b3192985a8dd9491aa524555ae5` | `cd1c90f6834ff962635ef7c62d06e28137274ab933534f0e49d366f299633458` |
| `remain_edge` | `image_encoding_dfe5464492c1552c89038186eaef33d6` | `c3a2401af1db8c9aa2763b7938a7f66111870eaf09c1bafe2f8cef9a3bac14bc` |

## Narrow comparisons and collapse decision

| Comparison | Cosine | Normalized similarity | Separation |
|---|---:|---:|---:|
| current → desired | 0.277405200467 | 0.638702600234 | 0.361297399766 |
| `enter_circle` → desired | 0.289462421500 | 0.644731210750 | 0.355268789250 |
| `enter_circle` → broken | 0.197149095359 | 0.598574547680 | 0.401425452320 |
| `remain_edge` → desired | 0.305925633608 | 0.652962816804 | 0.347037183196 |
| `remain_edge` → broken | 0.200717525096 | 0.600358762548 | 0.399641237452 |
| rollout ↔ rollout | 0.982458640867 | 0.991229320433 | **0.008770679567** |

The implementation-hypothesis collapse epsilon is `0.01`. Direct rollout
separation is `0.008770679567`, below that threshold. The largest difference
between the two desired/broken projection profiles is also only
`0.008231606054`. The result therefore records:

- valuation: `visual_valuation_result_170b408fea87d35f173e6c01d5391ec6`;
- disposition: `review_action_collapse`;
- selectable leading option: none;
- generated images as external evidence: false;
- approved for native influence before full robustness review: false;
- semantic quality gate: not passed.

The slightly higher raw fused score for `remain_edge` remains visible for
diagnosis, but collapse suppresses selection. A generated visual artifact can
affect native cognition only after the documented valuation returns `usable`.
Even then, a separate semantic-robustness approval is required before native
influence. Rollout memory also rejects observed outcome linkage until a typed
execution/decision association can prove which option was actually executed.

## Verification

The reproducible intended commit tree completed with **900 passed** after the
final smoke (`--ignore=tests/v2`). Full current-workspace discovery completed
with **911 passed**, including 11 unstaged user-owned `tests/v2` overlay tests.
A focused post-smoke run covering the encoder, visual valuation, policy config,
visual-world memory and transactional runner completed with **72 passed**. An
independent provenance audit exercised a slightly wider contract set with
**77 passed** and found no remaining P0/P1 blocker. The bundle manifest
independently verified all **24** listed file hashes and sizes; all **15** JSON
files were canonical, with no unlisted files or temporary publication
directories. The smoke itself exited successfully and wrote two rollout memory
records whose meanings derive only from structured scene fields; neither image
pixels nor embeddings can add an external fact.

## Decision

C4.3 is accepted as a provenance-closed encoder, comparison, collapse and
internal-memory slice. The current FLUX.2 Klein rollout candidate remains an
implementation hypothesis and is explicitly barred from visual fusion. The
next slice must integrate this fail-closed result into the Emocio processor and
then run the full multi-seed, multi-style, bilingual and alternate-renderer
robustness matrix.
