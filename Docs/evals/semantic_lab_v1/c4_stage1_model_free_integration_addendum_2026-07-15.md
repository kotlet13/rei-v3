# C4 Stage 1 model-free integration addendum — 2026-07-15

## Outcome

**PRE-INFERENCE CONTRACT CLARIFICATION ONLY — NO MODEL LOAD, INFERENCE,
SEMANTIC ACCEPTANCE OR PRODUCTION AUTHORITY.**

This addendum records the exact downloaded snapshot evidence and replaces the
ambiguous Stage 1 CUDA-memory wording with a measurement that the local runner
can actually enforce. It does not change either provider, prompt, seed, option
order, call argument, output rule, timeout, review rule, DINOv2 epsilon or
stage-expansion rule frozen by
`c4_visual_remediation_protocol_2026-07-15.md`.

The controlling protocol was committed as
`71becac849fce4e7af2f03453696d0cd025badd8` and pushed to `origin/main` before
either snapshot was materialized. The current implementation phase remains
model-free and must itself be reviewed, committed and pushed to `main` before
the first Stage 1 model call.

## Exact external snapshots

Both snapshots were downloaded outside the repository at the exact protocol
revisions. Hugging Face CLI verification checked every vendor file. Its
extra-file warning referred only to the CLI's local cache metadata and the REI
manifest stored beside the snapshot; those paths are excluded from the
material snapshot inventory. A separate REI pass then opened and hashed every
material file and compared the complete path, size and SHA-256 inventory.

The complete portable manifests are committed with this addendum:

| Role | Repository and revision | Material files | Material bytes | Canonical manifest SHA-256 |
|---|---|---:|---:|---|
| primary | `meituan-longcat/LongCat-Image-Edit-Turbo@6a7262de5549f0bf0ec54c08ef7d283ef41f3214` | 37 | 29,322,428,829 | `4a447342e10a7b214f43818e666af6a25b8c757650f7f8b6ff4317fca0f24783` |
| alternate | `Shitao/OmniGen-v1-diffusers@016e2f61d12a98303f6bbdf122687694d7984268` | 11 | 8,088,956,424 | `3522d2bb368a4a304045432d6641abb69a4b73d876d8f904d36efe9458998bce` |

The manifest SHA-256 values are over UTF-8 canonical JSON with sorted keys and
compact separators, not over checkout-dependent line endings. Runtime must
parse the committed manifest, reproduce that canonical digest, verify the
external snapshot through single opened handles with pre/post identity checks,
and perform a final exact inventory scan before any provider import callback.
Missing, added, changed, linked or reparse-point entries fail closed.

The external renderer environment remains exactly Python 3.11, PyTorch
`2.13.0+cu130`, Diffusers `0.39.0`, Transformers `5.13.0`, Accelerate `1.14.0`,
Safetensors `0.8.0` and Pillow `12.3.0`. These versions were inspected from
installed package metadata without importing the model libraries. Any change
requires another pre-inference addendum.

No snapshot path is part of a portable contract or committed artifact. An
absolute operator-supplied path is runtime configuration and must resolve to
the exact manifest above.

## Enforceable CUDA-memory boundary

The protocol table's phrase `maximum resident CUDA memory` is superseded for
Stage 1 by the following precise rule:

```text
sampled whole-device CUDA used-memory stop threshold = 31,500 MiB
```

The parent-owned sampler must take an initial endpoint before releasing the
requested workload, sample at the committed bounded cadence while the child is
alive, reserve capacity for a final endpoint, and finalize durable evidence on
every success or failure path. If any valid whole-device sample is strictly
greater than 31,500 MiB, the parent terminates the contained process tree and
the candidate fails without publishing an image. Missing initial/final
endpoints, unavailable required CUDA identity/readings, sampler failure,
sample-limit exhaustion, join timeout, persistence failure or cold-readback
failure also fail the technical gate.

The child additionally reports PyTorch peak allocated and reserved bytes when
the provider runtime is active. Parent samples and child peaks are supporting
lower-bound observations: neither proves an unsampled transient maximum, and
whole-device used memory is not an exclusive per-process attribution. Reports
must preserve those limitations and may not restate the result as a proven
resident or transient maximum.

## Durable pre-inference boundary

Before Stage 1 inference is allowed, the repository must commit and test all of
the following as one content-addressed, model-free boundary:

- exact provider and pipeline specs for both pinned families, including every
  frozen load, call and output rule;
- a top-level Stage 1 contract that binds this addendum, both complete snapshot
  manifests, frozen source bytes, scene/profile/prompts, seeds, provider order,
  timeouts, sampled-memory policy, DINOv2 epsilon and review policy before any
  output exists;
- a parent-owned hard process-tree runner and child request/result boundary with
  no remote download, silent fallback, best-of-N or partial image publication;
- create-only telemetry intent, durable background samples, process execution
  record, terminal finalization receipt and exact attempt inventory on every
  terminal path;
- an immutable-display receipt made from the exact verified PNG bytes handed to
  a separately keyed live display verifier, bound into the Stage 1 operator
  claim and sealed review submission before review can pass;
- model-free DINOv2 bridge schemas and adversarial tests; DINOv2 remains a
  collapse detector and cannot populate human fields or grant authority.

Cold verification can prove stored bytes and references. It cannot prove that
a human watched, understood or cognitively evaluated physical monitor pixels;
all such authority fields remain `false` unless the separately attested review
workflow establishes only the narrower facts it is designed to record.

## Stop and rollback

This phase must not import either pipeline, allocate model tensors or produce a
candidate image. A failed preflight leaves the snapshots as disposable external
caches and publishes no Stage 1 result. Rollback is a normal revert of the
model-free code, manifests and this addendum; deterministic baselines and the
historical LongCat/FireRed negative evidence remain unchanged.
