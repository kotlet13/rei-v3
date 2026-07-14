# Agent Notes

## Main-Only Development

All current and future work in this repository must be performed directly on
the `main` branch. Do not create, switch to, or publish feature branches unless
the user explicitly replaces this instruction.

Before starting a phase, verify that the working branch is `main` and reconcile
it with `origin/main`. Keep unrelated user-owned working-tree changes unstaged.
After an approved implementation phase, commit and push the scoped changes
directly to `main`.

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
