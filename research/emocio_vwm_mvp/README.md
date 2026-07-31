# Emocio Visual World Model MVP

This directory is an isolated research surface. It does not participate in the
active REI runtime and does not change Racio, Instinkt, Ego, governance,
character replay, or the existing Emocio processor.

The research question is deliberately narrow: can a pinned LPWM learn stable,
stochastic, visual-only futures for a controlled public-credit scene without
receiving scenario text or evaluator semantics?

## Fixed boundary

The Three.js world graph and episode state are evaluator-only ground truth.
The LPWM-facing staging directory may contain only:

- RGB observation frames or an RGB observation video;
- one RGB visual self-reference when the arm is enabled;
- one RGB goal image when the arm is enabled.

The LPWM call receives no prompt, scenario name, role name, entity identifier,
option description, character value, scene graph, caption, sidecar metadata, or
hidden semantic label. Language conditioning is fixed to `false`. The allowed
model path is latent-action sampling, optionally with image-goal conditioning.

Grounded observations and imagined completions use different namespaces and
lineage records. Imagined artifacts always carry `reality_authority: false`.
No generated future may update grounded state.

## Governance status

This bundle is the exploration phase. It freezes the medium, contracts,
dataset plan, acceptance thresholds, LPWM source pin, and model-free checks.
LPWM technical-overfit and social model-fit execution are a later validation
phase and require human review of this phase first.

The exploration command is:

```powershell
python scripts/run_emocio_vwm_exploration.py --output output/emocio_vwm_mvp/exploration
```

The command renders evaluator-owned preview clips and model-visible clean-media
staging examples. It never downloads model weights and never invokes LPWM.

## Separate LPWM environment

The official LPWM source is pinned by `specs/lpwm_pin.json`. A source checkout
and virtual environment must live outside this repository. The preflight is
read-only and rejects an unpinned source tree, a missing explicitly supplied
checkpoint, language conditioning, or any request containing semantic fields.

No weights are vendored. No code path in this bundle downloads weights.

## Verdicts

Only these final values are permitted:

- `medium_failed`
- `model_fit_failed`
- `model_fit_promising`
- `not_executed_resource_block`

Green model-free tests are technical contract evidence, not semantic
acceptance. LPWM failure at technical overfit or social model fit is recorded
as `model_fit_failed`; thresholds and model identity are never changed within
that result.
