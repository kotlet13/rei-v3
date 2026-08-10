# Emocio VWM E2R

E2R is a determinism-compatibility remediation of the frozen LPWM E2
technical-overfit attempt. E2 remains an immutable
`not_executed_resource_block`: strict deterministic CUDA execution rejected
`grid_sampler_2d_backward_cuda` before the first optimizer step.

E2R changes only the execution policy. It uses
`torch.use_deterministic_algorithms(True, warn_only=True)`, disables cuDNN
benchmarking, enables deterministic cuDNN behavior, and sets
`CUBLAS_WORKSPACE_CONFIG=:4096:8` before importing Torch. CUDA `grid_sample`
backward remains potentially nondeterministic; E2R therefore makes no claim of
bitwise-repeatable model optimization.

The LPWM source, from-scratch initialization, frozen visual-only dataset,
environment, model configuration, optimizer, seed, budget, OOM fallback,
sampling plan, hard acceptance gates, and verdict taxonomy are inherited
unchanged from E2. Two fresh one-step reproducibility smokes precede the one
measured 1,200-step run. They are execution checks, not model-fit runs and are
not used for model, seed, or configuration selection.

E2R is technical-overfit research only. It does not start social model-fit and
does not modify the active REI runtime.
