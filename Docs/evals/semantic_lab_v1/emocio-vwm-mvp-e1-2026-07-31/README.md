# Emocio VWM MVP — exploration E1

Date: 2026-07-31

Branch: `codex/emocio-visual-world-model-mvp`

Direct base: `1300e1d6e1a94a4baae20152e895141543fbcd37`

LPWM source pin: `4cf53c403433e64c01652ac2adbec66231a46dea`

## Outcome

The controlled Three.js medium and visual-only boundary passed every frozen
model-free exploration check. LPWM was not invoked. The recorded verdict is
`not_executed_resource_block` because the separate pinned environment has no
installed LPWM dependencies and no explicitly supplied local checkpoint.

This is not a positive semantic result. The grounded videos in this bundle are
Three.js evaluator references, not imagined LPWM completions. `lineage.json`
contains an empty imagined-artifact set and assigns imagined output no reality
authority.

## Review entry points

- `bundle_manifest.json`: complete artifact index;
- `dataset_manifest.json`: episode, frame, video, and clean-call hashes;
- `specs/world_manifest.json`: evaluator-only world ground truth;
- `metrics.json`: medium checks and explicit non-execution of model tests;
- `lpwm_preflight.json`: pinned source, environment, checkpoint, and GPU state;
- `lineage.json`: grounded/imagined separation;
- `contact_sheets/grounded_key_mosaic.png`: key-frame visual QA;
- `human_review.md`: sealed-review template for later model outputs;
- `verdict.json`: phase verdict and stop gate.
- `checksums.json`: SHA-256 and byte size for every generated bundle file.

Reproduce into ignored working output with:

```powershell
python scripts/run_emocio_vwm_exploration.py `
  --output output/emocio_vwm_mvp/exploration
```

Per repository governance, this phase stops here for human review. Technical
overfit, social model fit, training-split generation, and blind review have not
started.
