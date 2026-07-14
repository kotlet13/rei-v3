# C4 visual model selection addendum — split editor screen — 2026-07-14

## Outcome

**SELECTED FOR A CONTROLLED C4 ROBUSTNESS SCREEN ONLY — NOT ACCEPTED AS A
DEFAULT, SEMANTICALLY VALID OR PRODUCTION-AUTHORIZED MODEL.**

The original FLUX.2 Klein 4B integration remains technically accepted and
semantically rejected for option-rollout use. Its reviewed outputs alternated
between action collapse and source-subject loss. This addendum selects two
independent image-editing candidates for the next controlled comparison:
LongCat-Image-Edit as the primary editor candidate and FireRed-Image-Edit 1.1
as the second renderer family required by the precommitted C4 robustness gate.

Selection means that their exact snapshots and a fail-closed local adapter may
be prepared. It does not mean either model passed human review, DINOv2 collapse
checks, bilingual stability, order stability or the complete C4 gate.

As of the execution recorded below, both candidates have passed one bounded
technical fail-fast smoke. The complete robustness matrix remains **0/48
editor-member cells**, so the semantic quality gate remains open and no
production authority has been granted.

## Exact candidate pins

| Screen member | Repository | Exact Hub revision | Pipeline at Diffusers 0.39.0 | License | Status |
|---|---|---|---|---|---|
| primary editor | `meituan-longcat/LongCat-Image-Edit` | `7b54ef423aa7854be7861600024be5c56ab7875a` | `LongCatImageEditPipeline` | Apache-2.0 | implementation hypothesis |
| independent second editor | `FireRedTeam/FireRed-Image-Edit-1.1` | `3bc3f2a12722fd9883eb6357500de191d56baaf5` | `QwenImageEditPlusPipeline` | Apache-2.0 | implementation hypothesis |

The exact-revision Hugging Face trees contain 37 files and 29,322,429,940
bytes for LongCat, and 35 files and 57,720,463,164 bytes for FireRed. Those are
remote snapshot totals, not approximate free-space estimates.

LongCat's one transformer file is 12,541,410,152 bytes with Hub LFS SHA-256
`7ad9bfe2ca5f32ec85a01c8860d1bc4f472682bc30c9f63c45fd2a61c0804fcd`.
FireRed's transformer is split into five files. Their Hub LFS SHA-256 values,
in shard order, are:

1. `cd6f0d78a3a8c21792538d0abae604bd7abbca1508a2e8c778ea359f5fabd180`
2. `bb6b283ea5954aa16e8df94fbbd37368c48c07ff3cfcf3a514117333c3753463`
3. `e0602f9a002cf2807080bfb6d055cbcd6991887be7e89c82fa9411f938195923`
4. `ae1d1ec1a35f5f59b086c1947dbf62d67d972d25cf7c771640921c9aa97ee492`
5. `9d304d6539e7dad0647346cecf68d1fd5dc0efc7319626cdde2fdfc3e1533417`

## Materialized external snapshots

No model weight is stored in the repository. The exact revisions were
materialized under the external cache root
`C:\Users\Kotlet\.cache\rei-v3-c4` with explicit `hf download --revision`
commands. The final canonical REI inventory evidence is:

| Candidate | External snapshot directory | REI manifest SHA-256 | Files | Inventoried bytes |
|---|---|---:|---:|---:|
| LongCat-Image-Edit | `C:\Users\Kotlet\.cache\rei-v3-c4\longcat-image-edit-7b54ef423aa7854be7861600024be5c56ab7875a` | `91c47db962c1d1edb23724abb424bcfa70338224220829bdfa083986532502d7` | 37 | 29,322,429,940 |
| FireRed-Image-Edit 1.1 | `C:\Users\Kotlet\.cache\rei-v3-c4\firered-image-edit-1.1-3bc3f2a12722fd9883eb6357500de191d56baaf5` | `68f575583c64b48f4c5f8679818cc647bed7431165158ab69e23a7b8786a78fe` | 35 | 57,720,463,164 |

Before either REI manifest was written, `hf cache verify` checked the local
directories against the exact remote revisions. Hugging Face CLI 1.22.0
reported all 37 LongCat and all 35 FireRed checksums as matching, with no
missing remote file. Its `--fail-on-extra-files` mode also counted the CLI's
own `.cache/huggingface/*` local-dir metadata as remote-absent and therefore
returned a known false-positive failure. The diagnostic LongCat list contained
only that transient `.cache` subtree. An independent comparison of each
exact-revision tree against all non-cache local paths then reported zero
missing and zero unexpected paths, with exact byte totals for both snapshots.

The REI manifests record every non-cache file's path, byte size and SHA-256.
After manifest creation, the new adapter independently re-hashed both complete
inventories and reproduced the table above. It rejects missing, added,
changed, linked or Windows reparse-point entries before importing Torch or
Diffusers.

## Screen adapter contract

The screen adapter is intentionally narrower than the production renderer:

- both candidates receive the same byte-verified current-scene PNG, exact
  rollout scene spec, compiled prompt, root-derived scene seed and option
  order;
- each provider identity records the exact model repository and 40-hex Hub
  revision, while each request records the canonical snapshot-manifest digest;
- dependencies are pinned to Diffusers 0.39.0, PyTorch 2.13.0, Transformers
  5.13.0, Accelerate 1.14.0, Safetensors 0.8.0 and Pillow 12.3.0;
- models load only from the verified absolute local snapshot, with
  `local_files_only=True`, offline environment flags and no remote fallback;
- inference uses BF16, a CPU-seeded generator and mandatory
  `enable_model_cpu_offload()` on the CUDA execution path;
- LongCat maps the recorded request scale to `guidance_scale`; FireRed maps it
  to `true_cfg_scale` and receives the requested source dimensions;
- LongCat internally renders near one megapixel according to source aspect
  ratio. For byte-contract compatibility, any nonmatching editor output is
  deterministically normalized back to the exact source dimensions with
  Pillow Lanczos resampling, and this policy is part of the pipeline spec;
- every provider call uses `fallback_policy.mode=none`; a failure publishes no
  image artifact and cannot silently select the other editor;
- all generated images remain ungrounded internal artifacts. The typed screen
  result fixes `semantic_quality_gate_passed=false`,
  `production_authority_granted=false` and
  `generated_images_are_external_evidence=false`.

The runner defaults to a one-cell preflight-only invocation. Real GPU work in
the `cell`, single-editor `smoke` or explicit `matrix` mode requires the
`--execute` switch. It verifies the caller-provided source PNG against an
explicit SHA-256 and a canonical prior `ImageArtifact` or complete render
batch. The artifact ID, current-scene ID/hash, dimensions and ungrounded status
must all agree before preflight can pass. The runner refuses an existing output
directory, so every run is create-only. It never launches the full matrix from
the default path.

## Provenance-closed current source

The historical reviewed current-scene file was unavailable locally, so the
screen did not substitute an undocumented image. A new current was generated
from the canonical C4 current-scene spec with the already pinned
`black-forest-labs/FLUX.2-klein-4B` snapshot at exact revision
`e7b7dc27f91deacad38e78976d1f2b499d76a294`. The run used root seed `424239`,
BF16, model CPU offload and a CPU generator at 1024 x 768. It remains an
ungrounded generated artifact and carries no semantic or production authority.

| Field | Verified value |
|---|---|
| render batch | `render_batch_7a28234ae5efb53703accc656feb590f` |
| current scene ID | `visual_scene_2caca3e7e6424d6bafa3b365d935c4c5` |
| current scene hash | `c795bdd82b0b01ba54f453b7881a636de5ff118f692e250af5b6d32c4ddb5a65` |
| current artifact ID | `image_d1e97e56432b23038b8a01f6fdc24d42` |
| derived artifact seed | `8430348583773671458` |
| PNG SHA-256 | `72c9fec75d838f0db9a9abc71cbd86c4f4e637c8f54f05c0ea629e12e0f6da58` |
| dimensions | 1024 x 768 |
| elapsed time | 61.825458 seconds |
| peak CUDA allocation | 9,529,827,840 bytes |
| canonical provenance | `C:\Users\Kotlet\.cache\rei-v3-c4-screen-20260714\current-flux2-klein-seed424239-1024x768\render_batch.json` |

The artifact bytes, dimensions, scene lineage and canonical JSON container were
independently rechecked before either editor smoke was run.

## LongCat prompt-budget correction

The first LongCat fail-fast attempts correctly failed closed before inference.
The complete structured prompts were longer than LongCat's pinned 512-token
limit: the audited English prompts occupied 579-585 tokens and the Slovenian
prompts 848-854 tokens. Diffusers 0.39.0 then reached an upstream error in
`LongCatImageEditPipeline._encode_prompt` (`len(len(all_tokens))`) on that
over-limit branch. No artifact or fallback was published, and the persisted
failure classification is the redacted `renderer_api_incompatibility` code.

The correction is the shared deterministic `c4_editor_compact_v1` compiler,
not a site-package patch, model swap or provider fallback. It retains complete
semantic segments for the evidence boundary, language boundary, style ID and
directive, inert scene-data boundary, primary edit, preservation instruction,
desired-scene boundary, scene kind, option ID, entities, composition, grounded
evidence IDs, inferred elements and final evidence boundary. Both editors
receive the exact same compact prompt.

An offline audit with the pinned LongCat tokenizer produced these exact counts:

| Language | Style | Enter | Remain |
|---|---|---:|---:|
| Slovenian | documentary cinematic | 489 | 492 |
| Slovenian | graphic novel | 491 | 494 |
| English | documentary cinematic | 359 | 362 |
| English | graphic novel | 361 | 364 |

All eight language/style/option prompts are therefore at or below the exact
512-token budget; the maximum is 494.

The runner freezes the SHA-256 of each of those eight exact prompt strings
beside its audited token count. Preflight fails if any prompt changes without a
new pinned-tokenizer audit; character count is never presented as token count.

## Bounded technical fail-fast execution

Both real-model smokes used the same verified source artifact above, root seed
`424240`, derived option seed `1366714956115613163`, English documentary style,
canonical option order, the first option only, two inference steps, BF16, model
CPU offload, local-only snapshots and `fallback_policy.mode=none`.

| Editor | Result | Batch | Artifact | PNG SHA-256 | Elapsed | Peak CUDA allocation |
|---|---|---|---|---|---:|---:|
| LongCat | technical pass | `render_batch_14343b8517818dcea688e2ebeea39a74` | `image_393b633a51e93337da3f14dbb8d283ff` | `74384305733bc6ff9580427d65d557b3ff58531e486755323e922c9587a910fd` | 33.828380 s | 18,489,318,400 bytes |
| FireRed | technical pass | `render_batch_baed40ba3627bd575a6937a151926337` | `image_8416e759af22549fa5f381ae7b55fc8b` | `97699da4625e3b2b692012696708362821241e8c22731085d894c65e3cf94657` | 940.303813 s | 41,861,181,952 bytes |

The successful LongCat evidence is under
`C:\Users\Kotlet\.cache\rei-v3-c4-screen-20260714\smoke-longcat-seed424240-1024x768-attempt3`;
the unsuffixed LongCat directory is an earlier fail-closed attempt. The
successful FireRed evidence is under
`C:\Users\Kotlet\.cache\rei-v3-c4-screen-20260714\smoke-firered-seed424240-1024x768`.

For each smoke, an independent read-back verified the PNG SHA-256, PNG format,
1024 x 768 dimensions, source SHA-256, source dimensions, `fallback=null`,
ungrounded status, closed authority flags, and canonical bytes for
`smoke_result.json`, `member_result.json`, `execution_evidence.json` and the
request cache record. The FireRed PyTorch peak-allocation counter exceeds the
card's physical capacity because it is allocator/offload accounting; live
`nvidia-smi` observation was approximately 32,036 MiB resident with the GPU
near saturation. Both output images still require human semantic review.

## Capacity stop and gate status

The full matrix was deliberately not started. FireRed's two measured diffusion
steps consumed about 885.88 seconds of the smoke. A simple linear extrapolation
to the pinned 50 steps and 48 FireRed option-render calls is approximately 295
GPU-hours, or 12.3 days, before any LongCat work. This is a capacity estimate,
not an inference-time guarantee, but it is sufficient to rule out silently
starting the run as a normal bounded verification task.

Current status is therefore:

- exact snapshot and adapter preflight: **passed**;
- one-option/two-step technical fail-fast for both editors: **passed**;
- full 48-editor-cell robustness matrix: **not executed (0/48)**;
- bilingual, seed and option-order robustness: **not evaluated**;
- human action/identity review and DINOv2 collapse checks: **not evaluated**;
- semantic quality gate: **open / not accepted**;
- production authority and external-evidence authority: **false**.

## Known technical limitations

The adapter deadline is cooperative. It checks before and after model load and
inference but cannot hard-cancel a Diffusers call already executing. Matrix
execution therefore requires an explicit `--timeout-seconds` value and records
the soft-timeout mode in preflight; this is not a process-level cancellation
guarantee. The measured FireRed capacity stop above remains controlling.

The CLI output is create-only and refuses an existing destination. Its nested
writer is not yet hardened against a concurrent local reparse-point or junction
swap, so C4 screening must use a trusted local output parent. This operational
limitation cannot change the hard-coded semantic and production authority
fields, which remain false.

## Required robustness matrix

The candidate gate remains the precommitted 48-cell matrix:

`2 distinct editors × 3 seeds × 4 language/style profiles × 2 option orders`

The four profiles are Slovenian and English crossed with the documentary
cinematic and graphic-novel style directives. This definition contains 24
factor combinations, two editor-member cells per combination and two option
rollouts per editor member: 48 editor-member cells and 96 model calls. The same
current PNG must be used in every matching cell. A technical success means only
that local model loading, request/call provenance and PNG persistence
succeeded. Acceptance still requires human action/identity review, DINOv2
separation and collapse checks, order and seed stability, an unchanged
structured-only baseline and a separate reviewed authority artifact. No such
authority is created here.

## Official sources

- [LongCat-Image-Edit model card](https://huggingface.co/meituan-longcat/LongCat-Image-Edit)
- [LongCat exact-revision metadata](https://huggingface.co/api/models/meituan-longcat/LongCat-Image-Edit/revision/7b54ef423aa7854be7861600024be5c56ab7875a)
- [LongCat pipeline in Diffusers 0.39.0](https://github.com/huggingface/diffusers/blob/v0.39.0/src/diffusers/pipelines/longcat_image/pipeline_longcat_image_edit.py)
- [FireRed-Image-Edit 1.1 model card](https://huggingface.co/FireRedTeam/FireRed-Image-Edit-1.1)
- [FireRed exact-revision metadata](https://huggingface.co/api/models/FireRedTeam/FireRed-Image-Edit-1.1/revision/3bc3f2a12722fd9883eb6357500de191d56baaf5)
- [QwenImageEditPlus pipeline in Diffusers 0.39.0](https://github.com/huggingface/diffusers/blob/v0.39.0/src/diffusers/pipelines/qwenimage/pipeline_qwenimage_edit_plus.py)
- [FireRed official implementation](https://github.com/FireRedTeam/FireRed-Image-Edit)
