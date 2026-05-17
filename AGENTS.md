# Agent Notes

## Ollama GPU Offload

For local Ollama REI test runs with large models, explicitly set GPU offload instead of relying on Ollama's automatic layer estimate.

Use:

```powershell
$env:REI_OLLAMA_NUM_CTX = "65536"
$env:REI_OLLAMA_NUM_GPU = "999"
```

Or pass the equivalent script flags when available:

```powershell
python scripts\run_rei_runtime_llm_matrix.py --model granite4.1:30b --num-ctx 65536 --num-gpu 999
```

Why: on this machine, Granite 4.1 30B at 64k context previously landed partly on CPU unless `num_gpu=999` was sent in Ollama options. With `num_gpu=999`, `wsl ollama ps` showed `granite4.1:30b` as `100% GPU` at context `65536`.

Check the active placement with:

```powershell
wsl ollama ps
```

The backend provider reads `REI_OLLAMA_NUM_GPU` and maps it to Ollama's `num_gpu` option.
