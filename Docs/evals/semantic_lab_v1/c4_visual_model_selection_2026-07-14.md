# C4 visual model selection — 2026-07-14

## Outcome

**SELECTED FOR C4 IMPLEMENTATION AND EVALUATION — NOT ACCEPTED AS A DEFAULT OR
PRODUCTION MODEL.**

The local C4 candidate stack is FLUX.2 Klein 4B for text-to-image and
reference-image editing, plus DINOv2 Base for narrow image-feature extraction.
This is an `implementation_hypothesis`: the choice prioritizes a unified local
path, fit on the available 32 GiB GPU, deterministic provenance and permissive
licensing. It does not establish visual quality, REI semantic validity or a
phase-level pass. Activation remains conditional on the C4 quality gate.

## Pinned candidate stack

| Role | Repository | Exact Hub revision | License | Selection status |
|---|---|---|---|---|
| renderer/editor | `black-forest-labs/FLUX.2-klein-4B` | `e7b7dc27f91deacad38e78976d1f2b499d76a294` | Apache-2.0 | C4 implementation hypothesis |
| image encoder | `facebook/dinov2-base` | `f9e44c814b77203eaa57a6bdbbd535f21ede1415` | Apache-2.0 | C4 implementation hypothesis |

The pinned FLUX consolidated checkpoint
`flux-2-klein-4b.safetensors` has Hugging Face LFS SHA-256
`ec3d4e733a771f61c052fb4856c48b336c55eaf2c65487c2a1faeb9bbda7a343`
and size 7,751,105,712 bytes at the selected revision. This digest identifies
that consolidated file only; a Diffusers component snapshot must additionally
record the exact revision and digests of the component files actually loaded.

The pinned DINOv2 file `model.safetensors` has Hugging Face LFS SHA-256
`d73036b56966966d07975d696bde331762f37297e2f095de8cea0040c3aa0841`
at the selected revision.

## Materialized local snapshot evidence

The create-only local snapshot inventories used on 2026-07-14 are:

| Candidate | Canonical manifest SHA-256 | Files | Total inventoried bytes |
|---|---:|---:|---:|
| FLUX.2 Klein 4B Diffusers components | `fb1ecb3a4d7fe439949b83f0e183438ab35a6df2bc01d66c5d3cd9966a4c7183` | 24 | 15,988,901,735 |
| DINOv2 Base Transformers snapshot | `786481f81ca90d17eada5cd387835e457f1e531e93ec38a7671368dbb8249ba1` | 4 | 346,349,943 |

The FLUX transformer component actually loaded by Diffusers has SHA-256
`9f29f9edcfdae452a653ffb51a534ca4decd389952c225724ff3b94042612a6e`
and size 7,751,109,744 bytes. This is deliberately distinguished from the
consolidated checkpoint digest above. The DINOv2 `model.safetensors` digest is
the pinned `d73036…` value above. Absolute machine cache paths are runtime
configuration and are excluded from portable request identity; the manifests,
repository IDs, exact revisions and every loaded file digest are not.

The verifier rejects a missing, added, changed, linked or Windows reparse-point
entry before importing Diffusers. The real FLUX smoke revalidated this complete
inventory offline before model load.

## Why this renderer/editor

The official FLUX.2 Klein material describes one distilled architecture for
text-to-image generation and image/reference editing. The official Diffusers
pipeline exposes reference images through the `image` input and deterministic
sampling through a seeded generator. That matches C4's current-scene-first
rollout better than maintaining unrelated T2I and editor checkpoints.

The 4B model card reports approximately 13 GB of VRAM for inference. This leaves
material headroom on the local 32 GiB GPU for the pipeline, input image,
encoder and runtime overhead. The Hub revision is public, ungated and licensed
Apache-2.0. These are deployment-fit observations, not evidence that the model
passes C4 semantic or stability requirements.

## Why this encoder

DINOv2 Base is an Apache-2.0 image-feature-extraction model with an official
Transformers path. C4 initially needs only narrow, auditable comparisons:
current↔desired, rollout↔desired, rollout↔broken and cross-seed consistency.
The encoder is not approved to infer social truth, grounded facts, motives or
character properties from generated images.

## Alternatives considered

| Candidate | Disposition |
|---|---|
| FLUX.2 Klein 9B-KV | Technically attractive for repeated reference-image rollouts, but rejected as the primary local path because its reported roughly 29 GB inference VRAM need leaves little 32 GiB headroom and its BFL non-commercial license is narrower than Apache-2.0. |
| Qwen-Image plus Qwen-Image-Edit | Not selected because generation and editing use separate large checkpoints, increasing local storage/runtime complexity for the single current-scene-first path. |
| Z-Image Turbo | Not selected because the official candidate is text-to-image focused and does not supply the required unified reference-edit path. |
| Stable Diffusion 3.5 Large | Not selected because its Stability Community License is less permissive for this repository's reusable local integration than Apache-2.0, and it does not improve the unified-path rationale. |

Apache-2.0 is preferred here to keep source integration, reproducible local
evaluation and later redistribution decisions separate from non-commercial
model restrictions. No model weights are committed to the repository, and this
selection record is not legal advice or permission to redistribute weights.

## Download and execution boundary

- Runtime and CI must never download model files.
- An operator may pre-populate an external, non-repository cache from the exact
  revisions above before a real local smoke run.
- The model-backed adapter must load from the pinned local snapshot with network
  access disabled or `local_files_only` behavior.
- Missing, incomplete or digest-mismatched files must fail closed. Any return to
  `structured_only` must be explicit in the typed C4 result and provenance; the
  provider itself must not silently select another model.
- CI uses deterministic renderer/encoder doubles and validates configuration;
  it does not contact Hugging Face or materialize large weights.
- Seeds, model revisions, actual file digests, prompts, renderer settings and
  input-image identity must be retained in provider provenance and cache keys.

## Acceptance boundary

The stack remains an implementation hypothesis until all required C4 evidence
exists: a real pinned local smoke, complete image and embedding provenance,
verified current-image reuse for option rollouts, zero grounded-evidence
contamination, explicit visual valuation influence, semantic-lab human review,
seed/style/language/option-order stability and an unchanged structured-only
baseline. Failure of any model-backed gate must preserve the architecture and
must not promote another candidate silently.

The C4.2 real-renderer smoke passed its technical renderer, lineage and
provenance scope. Human review did **not** accept FLUX.2 Klein 4B for semantic
rollout quality: the reviewed spatial-action fixture exposed action collapse
or source-subject loss across prompt iterations. The candidate therefore
remains an implementation hypothesis and cannot be made the default by this
record. See `c4_renderer_smoke_2026-07-14.md` for exact evidence.

## Primary official sources

- [FLUX.2 Klein 4B model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- [FLUX.2 official implementation](https://github.com/black-forest-labs/flux2)
- [Diffusers FLUX.2 pipeline documentation](https://huggingface.co/docs/diffusers/main/api/pipelines/flux2)
- [FLUX exact-revision Hub metadata](https://huggingface.co/api/models/black-forest-labs/FLUX.2-klein-4B/revision/e7b7dc27f91deacad38e78976d1f2b499d76a294)
- [FLUX exact-revision file tree](https://huggingface.co/api/models/black-forest-labs/FLUX.2-klein-4B/tree/e7b7dc27f91deacad38e78976d1f2b499d76a294?recursive=true&expand=true)
- [DINOv2 Base model card](https://huggingface.co/facebook/dinov2-base)
- [DINOv2 official implementation](https://github.com/facebookresearch/dinov2)
- [Transformers DINOv2 documentation](https://huggingface.co/docs/transformers/model_doc/dinov2)
- [DINOv2 exact-revision Hub metadata](https://huggingface.co/api/models/facebook/dinov2-base/revision/f9e44c814b77203eaa57a6bdbbd535f21ede1415)
- [DINOv2 exact-revision file tree](https://huggingface.co/api/models/facebook/dinov2-base/tree/f9e44c814b77203eaa57a6bdbbd535f21ede1415?recursive=true&expand=true)
- [FLUX.2 Klein 9B-KV model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B-KV)
- [Qwen-Image model card](https://huggingface.co/Qwen/Qwen-Image)
- [Qwen-Image-Edit model card](https://huggingface.co/Qwen/Qwen-Image-Edit-2509)
- [Z-Image Turbo model card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)
- [Stable Diffusion 3.5 Large model card](https://huggingface.co/stabilityai/stable-diffusion-3.5-large)
