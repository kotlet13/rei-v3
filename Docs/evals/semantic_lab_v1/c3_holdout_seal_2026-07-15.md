# C3 holdout seal — 2026-07-15

## Status

**SEALED / NOT RUN**

The untouched C3 holdout is sealed against protocol-freeze commit
`d74891cdeed407a50098d28d6f4e9024b28156e7`. No official candidate model
call, Ollama model pull, or model download has been made for this sealed run.

## Sealed holdout artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1/manifest.json` | 6946 | `32a57a8dc0601ad01ca9eb169786e0888f13c036488762f9cfa6b69a0b7233f2` |
| `knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1/public_cases.jsonl` | 28394 | `ef41a1844a0544ec88ba9233e28cb6ba995c9c4a7e5b1f8df559101b5db9bfa5` |
| `knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1/gold.jsonl` | 20106 | `41b707205202656ebeabf669f349d3b61d3d2c80f7177d2e3d96d2a9e9754842` |

The official suite order is immutable:

1. untouched v2 holdout — manifest SHA-256
   `32a57a8dc0601ad01ca9eb169786e0888f13c036488762f9cfa6b69a0b7233f2`;
2. unchanged v1 regression — manifest SHA-256
   `1cbb5607acc95426673feddb9891567b5a46e5f4988f8cc171a6636069bbab4b`.

## Frozen candidate and execution boundary

The runner has a frozen, non-overridable profile:

| Field | Frozen value |
|---|---|
| Model | `qwen3.6:35b` |
| Ollama digest | `07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522` |
| Seed / temperature | `314159` / `0.0` |
| Context / GPU offload | `65536` / `999`, full GPU required |
| Prediction ceiling / timeout | `1536` / `600.0` seconds |
| Keep-alive | `10m` |
| Endpoint | local `/api/generate`; remote execution forbidden |
| Retry / fallback | none / none |
| Git executable | `C:\Program Files\Git\mingw64\bin\git.exe` |
| Git executable SHA-256 | `cab4c4eea1d869cf9f7be73868dc9a90ad2df1b1b673e5f8c8714a576c25ea96` |

The stdlib bootstrap rejects repository-local Git shadow candidates, invokes
the pinned Git executable by absolute path, and redirects all project bytecode
lookups to a fresh empty cache namespace with bytecode writes disabled before
any project module is imported.

The official run is eligible only from the pushed seal/pin commit directly on
`main`, with clean scoped sources and `HEAD == origin/main`. That execution
commit must be the direct child of protocol-freeze commit
`d74891cdeed407a50098d28d6f4e9024b28156e7`.

Deterministic baseline evidence and model-free unit/regression evidence are
already available for the sealed corpus and protocol. They are pre-run
contract evidence only; they are not an official pair result or a model-quality
claim.

## Exact next command

Run from the repository root only after the seal/pin commit is pushed and all
execution preconditions hold:

```powershell
$env:REI_OLLAMA_NUM_CTX = "65536"
$env:REI_OLLAMA_NUM_GPU = "999"
uv run --python 3.11 --with "pydantic>=2,<3" --with "PyYAML>=6,<7" python -I -S scripts/run_c3_racio_official_pair.py
```
