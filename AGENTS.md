# Agent Notes

## Research Phase Governance

All new research work must be performed on a dedicated feature branch. Direct
pushes to `main` are forbidden, and every human-reviewable research phase must
stop for user review before another phase starts or any merge is proposed.

Project-governance instructions may be changed only by explicit user request.
An agent may not remove review gates, require direct-main development, or
authorize itself to continue into another phase.

Exploration must precede validation. Model-free infrastructure, green tests,
and technical contract compliance are not semantic acceptance by themselves.
No phase auto-continues. Keep unrelated user-owned working-tree changes
unstaged, and do not merge a research branch without explicit user review.

Do not generate training datasets or introduce QLoRA, LoRA, SFT, or another
training workflow without a new explicit user-approved plan.

## Ollama GPU Offload

For local Ollama REI test runs with large models, explicitly set GPU offload instead of relying on Ollama's automatic layer estimate.

Use:

```powershell
$env:REI_OLLAMA_NUM_CTX = "65536"
$env:REI_OLLAMA_NUM_GPU = "999"
```

Pass the equivalent flags to the B14 native Ollama smoke runner once that
runner is present. Do not use `scripts\run_rei_native_profile_matrix.py` for
this purpose: the canonical 12 × 13 matrix is deliberately model-free and
never contacts Ollama. The exact post-B14 command is recorded in
`Docs/evals/rei_native_architecture_acceptance_2026-07-13.md`.

Why: on this machine, Granite 4.1 30B at 64k context previously landed partly on CPU unless `num_gpu=999` was sent in Ollama options. With `num_gpu=999`, `wsl ollama ps` showed `granite4.1:30b` as `100% GPU` at context `65536`.

Check the active placement with:

```powershell
wsl ollama ps
```

Any active native Ollama provider must read `REI_OLLAMA_NUM_GPU` and map it to
Ollama's `num_gpu` option; it must also record the effective value in provider
provenance.
