# Exploration protocol and validation hand-off

## What this phase may establish

This phase may establish that the local visual medium is stable, the evaluator
world is complete, clean-media staging is free of semantic side channels, and
the planned LPWM experiment is reproducible. It may not establish that LPWM has
learned identity, social dynamics, goal sensitivity, or generalization.

The current phase generates only six non-training preview episodes. Their
scene graphs are evaluator artifacts. Their RGB frames, clean MP4 clips,
self-reference images, and goal images demonstrate the proposed model-facing
surface but are not LPWM predictions.

## Frozen validation sequence

After human approval of this exploration phase, validation has two sequential
gates using the same LPWM commit and the frozen `specs/acceptance.json`:

1. Materialize only the `technical_overfit` split from the frozen dataset plan,
   install the pinned LPWM dependencies in the external environment, and train
   an image-goal/latent-action LPWM without language conditioning. If the first
   gate fails, record `model_fit_failed` and stop.
2. Only after the technical-overfit gate passes, materialize the remaining
   approved splits and run social model fit, ablations, held-out evaluation,
   and sealed blind review. Any failed required threshold produces
   `model_fit_failed` and stops the LPWM result.

No alternate model may replace LPWM within that result. A later alternate-model
experiment would need a new branch, plan, acceptance freeze, and result.

## Required validation evidence

- checkpoint SHA-256 and exact LPWM source commit;
- environment/package inventory and CUDA device provenance;
- one hash-closed call record per condition and sampling seed;
- eight visual future clips per call, a key mosaic, and a metric-selected visual
  path with `reality_authority: false`;
- identity stability, person count, duplicate rate, self-anchor ablation,
  stochastic diversity, image-goal sensitivity, and grounded/imagined lineage;
- held-out metrics and a completed sealed human-review sheet;
- exactly one permitted verdict.
