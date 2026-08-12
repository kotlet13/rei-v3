# E3R — LPWM positive-control harness remediation

E3R is the direct protocol successor to frozen E3 result commit
`3d56eeaad45ce21eae36049b9bfe63cc3b52b045`. E3 remains an immutable
`positive_control_failed` historical result: its official checkpoint load and
forward completed, but its diagnostic adapter duplicated the time dimension
while reshaping `obj_on`. It therefore did not evaluate the model's positive
control and did not start target training.

E3R changes only the control/evaluation adapter and evidence capture. The
pinned LPWM source, official checkpoint and hparams, official Sketchy sequence,
target dataset, target model configuration, seed, 2400-step budget, optimizer,
hard gates, and visual-only boundary do not change. The target is forbidden
until a complete, real official positive control passes.

The shared shape boundary in `shape_contract.py` distinguishes encoder
particles (`K_enc`, used for active-particle diagnostics) from decoder masks
(`K_dec`, used for mask coverage), and never assumes they are equal. The shared
evaluator validates the alpha singleton channel before removing it. It uses
the upstream public background reconstruction output and fail-closes on the
legacy/non-public alternative.

The protocol commit is model-free. Running `scripts/run_emocio_vwm_e3r.py`
requires the exact pushed protocol SHA and the already-pinned local research
environment. Adapter success is not LPWM model fit, and positive-control
success is not a working Emocio.
