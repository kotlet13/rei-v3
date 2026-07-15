# C4 visual remediation protocol — 2026-07-15

## Outcome

**PRECOMMITTED IMPLEMENTATION HYPOTHESES ONLY — NOT DEFAULT, SEMANTICALLY
ACCEPTED OR PRODUCTION-AUTHORIZED MODELS.**

This protocol replaces the capacity-invalid full FireRed screen with a bounded
two-family remediation path. It selects `LongCat-Image-Edit-Turbo` as the
primary editor hypothesis and `OmniGen-v1-diffusers` as the independent
alternate-renderer hypothesis. No selected candidate may influence native
Emocio cognition until the complete reviewed C4 gate passes and a separate
repository authority artifact is approved.

The protocol was prepared directly on `main` from base commit `486401b`. It
must be committed and pushed before either new snapshot is downloaded or
either candidate is invoked.

## Fresh official-source comparison

The comparison was refreshed on 2026-07-15 before model installation or use.
Vendor claims are shortlist evidence only; local frozen evaluation decides the
REI result.

| Candidate | Official observation | Project disposition |
|---|---|---|
| LongCat-Image-Edit-Turbo | Apache-2.0; distilled `LongCat-Image-Edit`; eight NFEs; official CPU-offload path reports about 18 GB VRAM | **Primary bounded hypothesis.** Best current fit between local edit capability, expected quality and matrix capacity. |
| OmniGen v1 Diffusers | MIT; unified local image editing; official Diffusers path supports seeded input-image editing and source-size output; exact snapshot is about 8.1 GB | **Independent alternate hypothesis.** Lower expected quality than LongCat, but a different model family with bounded local execution and no remote or custom-code requirement. |
| FireRed-Image-Edit 1.1 | Apache-2.0; strongest published vendor comparison among the reviewed open candidates and explicit identity-consistency focus | Retained as quality-ceiling and negative capacity evidence only. The measured local two-step call took about 940 seconds; the frozen full run was estimated at about 295 GPU-hours. |
| Qwen-Image-Edit-2511 | Apache-2.0; improved drift, identity consistency and geometric reasoning | Not selected for this remediation because its large Qwen edit stack does not resolve the measured offload/capacity problem. |
| FLUX.2 Klein 4B | Apache-2.0; compact unified generation/editing at about 13 GB VRAM | Already technically integrated and semantically rejected after source-subject loss/action collapse; retained as negative evidence. |
| Boogu-Image-0.1-Edit-Turbo | Apache-2.0; four-step local editor | Rejected for the gate because its own card warns that strict subject, identity, layout and detail preservation are not yet stable. |
| Step Image Edit 2 | Officially described as a fast hosted editor | Rejected because no local open-weight path is provided; API-only execution violates the offline snapshot boundary. |
| DreamLite mobile/base | Fast local architecture and Diffusers path | Rejected because weights are gated and CC BY-NC/research-only; access and redistribution constraints are narrower than the selected candidates. |
| OmniGen2 | Apache-2.0; local editing at about 17 GB VRAM | Not selected for this first screen: the official snapshot/runtime is substantially larger and its own guidance notes identity drift, English preference and possible multi-attempt selection. |

No LoRA, QLoRA, training, training-data generation, best-of-N selection or
model-judge-only acceptance is allowed by this protocol.

## Exact candidate pins

| Role | Repository | Exact Hub revision | License | Files | Full tree bytes | Runtime |
|---|---|---|---|---:|---:|---|
| primary editor | `meituan-longcat/LongCat-Image-Edit-Turbo` | `6a7262de5549f0bf0ec54c08ef7d283ef41f3214` | Apache-2.0 | 37 | 29,322,428,829 | `LongCatImageEditPipeline`, Diffusers 0.39.0 |
| alternate editor | `Shitao/OmniGen-v1-diffusers` | `016e2f61d12a98303f6bbdf122687694d7984268` | MIT | 11 | 8,088,956,424 | `OmniGenPipeline`, Diffusers 0.39.0 |

Both repositories are public and ungated at the pinned revisions. File counts
and byte totals include every exact-revision Hub tree entry, not only LFS/Xet
objects. The later REI inventory must independently hash every materialized
non-cache file.

The candidate execution environment remains external to the repository and is
currently pinned to Python 3.11, PyTorch 2.13.0+cu130, Diffusers 0.39.0,
Transformers 5.13.0, Accelerate 1.14.0, Safetensors 0.8.0 and Pillow 12.3.0.
Any dependency change requires a new protocol addendum before inference.

## Download and snapshot boundary

After this protocol commit is present on `origin/main`, an operator may:

1. download each repository at its exact 40-hex revision into a new external
   cache directory outside the repository;
2. run `hf cache verify` against that exact revision;
3. compare the exact remote tree with all non-CLI-cache local paths;
4. write a canonical REI manifest containing path, byte size and SHA-256 for
   every file;
5. re-hash and verify the complete manifest before importing Torch or
   Diffusers.

Runtime and CI must never download weights. Model loading is offline,
`local_files_only=True`, from an absolute verified snapshot. Missing, added,
changed, linked or Windows reparse-point entries fail closed. Neither provider
may silently fall back to the other provider, FLUX, a remote endpoint or
`structured_only`.

## Frozen stage 1 capacity and semantic screen

Stage 1 uses the existing byte-pinned current scene from the C4 editor-screen
evidence. Each candidate receives the exact same PNG bytes, scene spec,
English documentary profile, canonical option order, root-derived option
seeds and the two option edits `enter_circle` and `remain_edge`.

| Frozen source field | Exact value |
|---|---|
| current artifact | `image_d1e97e56432b23038b8a01f6fdc24d42` |
| current scene | `visual_scene_2caca3e7e6424d6bafa3b365d935c4c5` |
| current scene hash | `c795bdd82b0b01ba54f453b7881a636de5ff118f692e250af5b6d32c4ddb5a65` |
| source PNG SHA-256 | `72c9fec75d838f0db9a9abc71cbd86c4f4e637c8f54f05c0ea629e12e0f6da58` |
| source dimensions | 1024 × 768 |
| root seed | `424240` |
| `enter_circle` scene / derived seed | `visual_scene_acbc451d7b30336076e5c1e5bd31e02b` / `1366714956115613163` |
| `remain_edge` scene / derived seed | `visual_scene_12e01b7dc48013135871ba28868f8180` / `297232311612386773` |
| prompt profile | English / `documentary_cinematic_v1` / `26908b02adc969b1c894b46f69bbd1c81a92464cc62b1e74b4217d9edd06a3c8` |

| Setting | LongCat Turbo | OmniGen v1 |
|---|---:|---:|
| inference steps | 8 | 50 |
| generator | CPU-seeded | CPU-seeded |
| output dimensions | exact source dimensions | exact source dimensions |
| per-option hard wall timeout | 180 seconds | 180 seconds |
| complete member timeout | 420 seconds | 420 seconds |
| maximum resident CUDA memory | 31,500 MiB | 31,500 MiB |
| fallback | none | none |

The complete Stage 1 call surface is frozen as follows.

### LongCat Turbo call

- load: exact verified local snapshot, `local_files_only=True`, safetensors,
  BF16, `enable_model_cpu_offload()`, offline environment, no remote code;
- prompt: exact `c4_editor_compact_v1` compiled option prompt with profile hash
  `26908b02adc969b1c894b46f69bbd1c81a92464cc62b1e74b4217d9edd06a3c8`;
- call kwargs: `image=<verified RGB source>`, `prompt=<compiled prompt>`,
  `negative_prompt=""`, `num_inference_steps=8`, `guidance_scale=1.0`,
  `num_images_per_prompt=1`, `generator=<CPU generator at derived option seed>`,
  `output_type="pil"`, `return_dict=True`;
- output policy: the native near-one-megapixel output is converted to RGB and
  deterministically normalized to exactly 1024 × 768 with Pillow Lanczos;
  direct model output and normalized PNG hashes/dimensions are both recorded.

### OmniGen v1 call

- load: exact verified local snapshot, `local_files_only=True`, safetensors,
  BF16, direct CUDA placement, model CPU offload disabled, no remote code;
- prompt: the literal prefix `<img><|image_1|></img>\n` followed by the exact
  same `c4_editor_compact_v1` compiled option prompt and profile hash;
- call kwargs: `prompt=<prefixed prompt>`,
  `input_images=[<verified RGB source>]`, `height=None`, `width=None`,
  `num_inference_steps=50`, `max_input_image_size=1024`, `timesteps=None`,
  `guidance_scale=2.0`, `img_guidance_scale=1.6`,
  `use_input_image_size_as_output=True`, `num_images_per_prompt=1`,
  `generator=<CPU generator at derived option seed>`, `latents=None`,
  `output_type="pil"`, `return_dict=True`;
- unsupported negative-prompt input is not synthesized or passed;
- output policy: output must already be RGB 1024 × 768; no resize, crop or
  best-of-N selection is allowed, and any mismatch fails closed.

Every listed argument and output policy must also be represented in a
content-addressed provider pipeline spec. Any difference from this section
requires a new pre-inference protocol revision.

Execution must occur in a child process so the parent can terminate the whole
process tree after the hard wall timeout. A cooperative in-process deadline is
not sufficient for this gate. A timeout, OOM, snapshot mismatch, non-PNG
output, wrong dimensions, missing provenance or GPU-memory breach publishes no
image and stops expansion for that candidate.

Stage 1 is a development/capacity screen, not the C4 holdout. Before any Stage
1 inference, the repository must contain and test a canonical review schema
that fixes the following record and decision procedure.

- A human reviewer sees the verified current source, the exact option
  instruction and the two candidate outputs under content-derived blind codes;
  provider/model names and the other provider's result are hidden.
- Pair presentation order is the ascending SHA-256 of each blind code. The
  stored record binds reviewer pseudonym, review timestamp, blind-code mapping
  revealed only after submission, source/output hashes and rubric version.
- Each output records strict booleans for `source_subject_present`,
  `identity_preserved`, `unchanged_composition_preserved`,
  `option_action_correct`, `no_extra_actor`,
  `no_generated_external_evidence_claim` and `reviewer_uncertain`.
- Each option pair records `actions_visibly_distinct` and
  `same_source_bytes_confirmed`.
- Human semantic pass requires every positive boolean above to be `true` and
  `reviewer_uncertain=false`. Missing, skipped or uncertain review fails closed;
  a model judge cannot populate the human fields.

Both option outputs require the sealed review record to establish:

- source subject is present and recognizable;
- identity, unchanged scene elements and composition are retained;
- `enter_circle` visibly crosses into the marked threshold;
- `remain_edge` visibly stays outside it;
- the two actions are not collapsed or merely byte-different;
- no extra actor, grounded fact or external-evidence claim is introduced;
- the exact current PNG is the source for both outputs.

DINOv2 remains the pinned first collapse detector and its `0.01` action-
separation epsilon is unchanged. DINOv2 is not a substitute for the sealed
human review and may not infer social truth or grounded facts.

Technical Stage 1 pass requires both model calls and all snapshot, source,
prompt, output, timeout, memory, telemetry and provenance checks to pass.
Semantic Stage 1 pass requires the exact human rule above plus DINOv2 direct
rollout separation strictly greater than `0.01` and no action-collapse
disposition. Only a candidate that passes both may proceed. One passing
candidate is insufficient to close C4: both independent families must pass
before the cross-renderer gate can be evaluated.

## Frozen stage 2 screening matrix

Stage 2 preserves the existing factor definition:

```text
2 independent editors × 3 seeds × 4 language/style profiles × 2 option orders
= 48 editor-member cells and 96 option-render calls
```

The four profiles are Slovenian and English crossed with documentary
cinematic and graphic-novel styles. Matching cells reuse exactly the same
current PNG. Seeds, prompt strings and hashes, source identity, option order,
model revision, complete snapshot manifest, runtime versions, settings,
timings, process RSS, system RAM and CUDA allocation/residency are recorded for
every member.

The one-fixture 48-cell screen is explicitly a candidate screen, not the full
plan-level claim for every Emocio semantic-lab route. It may reject a candidate
but cannot grant production authority.

Stage 2 passes only if all of the following are true:

- all 48 required editor-member cells and all 96 option-render calls complete
  without technical, provenance, timeout, memory or output failure;
- all 48 blinded human pair reviews pass the exact Stage 1 boolean rule, with
  zero subject loss, composition loss, wrong action, added actor, uncertainty
  or contamination finding;
- all 48 DINOv2 option-pair comparisons have direct rollout separation strictly
  greater than `0.01` and no action-collapse disposition;
- every one of the 24 seed/language/style/order factor combinations contains
  one passing pair from each renderer family, so cross-renderer semantic action
  agreement is exactly `24/24`;
- the same option remains semantically correct in all three seeds, both styles,
  both languages and both orders; because every cell must pass, no tolerance,
  majority vote or missing-cell substitution is allowed;
- `structured_only` outputs are byte-identical to the frozen baseline and all
  generated-image authority fields remain false.

Any failed or missing condition makes Stage 2 fail. Outputs remain preserved as
negative evidence, but no threshold, prompt, model argument or gold may be
changed and rerun under the same stage identity.

## Stage 3 semantic-lab coverage

If and only if both candidates pass Stage 2, freeze a separate create-only
corpus manifest covering every semantic-lab example with an Emocio route. The
manifest must be committed before execution and bind each public fixture to a
current/desired/broken scene triple, option edits and review rubric. The same
three seeds, two styles, both languages, both option orders and both renderer
families apply to every included example.

Stage 3 acceptance requires:

- stable semantic action direction across seed, style, language and option
  order;
- cross-renderer agreement without random subject/action collapse;
- zero generated-image contamination of grounded evidence;
- unchanged `structured_only` output and deterministic baselines;
- documented visual influence only through the existing valuation path;
- stored failures and complete resource/provenance evidence;
- a separate human-reviewed approval artifact and explicit repository
  authority pin.

Until that approval exists, `semantic_quality_gate_passed`,
`production_authority_granted` and
`generated_images_are_external_evidence` remain `false`.

## Stop rules and downstream boundary

- Do not expand a failed Stage 1 candidate into Stage 2.
- Do not start Stage 1 until both exact snapshots, hard-kill runner behavior,
  uniform telemetry, blind-order logic, sealed review schema and exact
  rubric-to-pass mapping are committed and tested model-free.
- Do not start Stage 3 until the Stage 2 bundle is complete and independently
  reviewed.
- Do not change prompts, seeds, thresholds, weights or gold after observing a
  stage's candidate outputs. A change requires a new corpus/protocol and fresh
  untouched evidence.
- Do not pin visual influence authority merely because rendering succeeded.
- C3, the real VLM arm, semantic motif arm and C7 remain separate gates. C4
  success alone cannot open C9.

## Protocol verification, limitations and rollback

Model-free preparation checks completed before this file was committed:

- `main` and `origin/main` were equal at base `486401b`;
- Hugging Face CLI 1.22.0 returned the exact candidate revisions, public/gated
  status, file trees and repository byte totals recorded above;
- the external renderer environment imported Diffusers 0.39.0 and exposed
  both `LongCatImageEditPipeline` and `OmniGenPipeline`;
- the frozen current artifact, scene hash, PNG hash, dimensions and derived
  option seeds were re-read from existing canonical C4 evidence;
- documentation `git diff --check` passed.

No model was downloaded or invoked by this phase. No image output, semantic
result, authority record or production choice exists yet. Vendor benchmark and
VRAM claims remain hypotheses until local telemetry and review reproduce the
relevant behavior. Slovenian support is not claimed by either candidate and is
an explicit Stage 2 gate.

Rollback before any snapshot materialization is a normal revert of this
protocol and its plan link. Later external snapshots are disposable caches and
must never be added to Git. The next allowed phase is model-free implementation
and testing of exact snapshot adapters, process-tree hard cancellation,
uniform telemetry and the sealed review schema; only then may Stage 1 run.

## Primary official sources

- [LongCat-Image-Edit-Turbo model card](https://huggingface.co/meituan-longcat/LongCat-Image-Edit-Turbo)
- [LongCat official implementation](https://github.com/meituan-longcat/LongCat-Image)
- [OmniGen official implementation](https://github.com/VectorSpaceLab/OmniGen)
- [Diffusers OmniGen documentation](https://huggingface.co/docs/diffusers/api/pipelines/omnigen)
- [OmniGen v1 Diffusers snapshot](https://huggingface.co/Shitao/OmniGen-v1-diffusers)
- [FireRed-Image-Edit 1.1 model card](https://huggingface.co/FireRedTeam/FireRed-Image-Edit-1.1)
- [FireRed official implementation and benchmark](https://github.com/FireRedTeam/FireRed-Image-Edit)
- [Qwen-Image-Edit-2511 model card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)
- [FLUX.2 Klein 4B model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- [Boogu Edit Turbo model card](https://huggingface.co/Boogu/Boogu-Image-0.1-Edit-Turbo)
- [Step1X/Step Image official repository](https://github.com/stepfun-ai/Step1X-Edit)
- [DreamLite official implementation](https://github.com/ByteVisionLab/DreamLite)
- [OmniGen2 official implementation](https://github.com/VectorSpaceLab/OmniGen2)
