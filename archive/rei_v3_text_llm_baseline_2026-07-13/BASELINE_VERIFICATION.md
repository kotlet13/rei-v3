# Baseline verification

## Identity and environment

- Observation date: `2026-07-13`
- Source commit: `05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`
- Source branch at preflight: `codex/pre-canonical-v2-snapshot`
- Archive work branch: `codex/architecture/rei-native-composition`
- OS: `Microsoft Windows NT 10.0.26200.0`
- Python used for the prepared isolated environment: `3.11.15`
- pytest installed in `app/backend/.venv`: `9.1.1`
- Git for Windows: `2.54.0.windows.1`
- WSL Ollama runtime observed by version query: `0.30.8`

The generic `python` command initially resolved to an unrelated Codex tool
environment and did not contain pytest. A repository-local, ignored
`app/backend/.venv` was therefore prepared from Python 3.11.15 with the exact
working-tree requirements and pytest 9.1.1. Those working requirements include
the user's uncommitted `PyYAML==6.0.3` addition; the source commit itself pins
only FastAPI, Uvicorn, and Pydantic. No tracked application dependency pin was
changed during this archive-only phase.

The prepared environment initially contained a CPython 3.12
`pydantic-core` binary inside the Python 3.11 venv. It was repaired by
reinstalling Pydantic 2.12.5's exact compatibility dependency,
`pydantic-core==2.41.5`, as a CPython 3.11 Windows wheel. This changed only the
ignored test environment.

## Version currency check

Official sources were checked on `2026-07-13` before choosing or executing any
technology/model path:

- current stable Python: `3.14.6` ([Python downloads](https://www.python.org/downloads/));
- current Git for Windows: `2.55.0(2)` ([Git for Windows](https://git-scm.com/install/windows));
- current pytest: `9.1.1` ([pytest changelog](https://docs.pytest.org/en/stable/changelog.html));
- current Ollama: `0.31.2` ([Ollama release](https://github.com/ollama/ollama/releases/tag/v0.31.2));
- current FastAPI/Uvicorn/Pydantic/PyYAML releases: `0.139.0`, `0.51.0`,
  `2.13.4`, and `6.0.3` respectively ([FastAPI](https://pypi.org/project/fastapi/),
  [Uvicorn](https://pypi.org/project/uvicorn/),
  [Pydantic](https://pypi.org/project/pydantic/),
  [PyYAML](https://pypi.org/project/PyYAML/)).

The source commit deliberately pins FastAPI `0.115.14`, Uvicorn `0.35.0`, and
Pydantic `2.12.5`. Upgrading those pins or the Python runtime would change the
baseline environment, so this archive-only phase retains the project pins and
uses the still-supported local Python 3.11.15. Pytest 9.1.1 is current and was
installed only in the ignored repository environment. Although the standalone
`pydantic-core` project has newer releases, the retained Pydantic 2.12.5 pin
requires `pydantic-core==2.41.5`; the compatible wheel was therefore used
instead of an incompatible latest core
([PyPI](https://pypi.org/project/pydantic_core/2.41.5/)).

The official Ollama registry still publishes `granite4.1:30b` as a 17 GB,
128K-context text model with registry digest prefix `3f3e5df8a021`; IBM's
official model card identifies the Apache-2.0 Granite 4.1 30B instruct release
dated 2026-04-29. The archived 64K setting is within the published Ollama
context window. Slovenian is not in IBM's listed supported-language set; the
baseline matrix itself uses English scenarios and contracts. Local model
availability/digest was not queried, and no local LLM inference was run. After
approving structural tests, the user explicitly required A0/A1 to continue
without any local LLM calls.

## Preflight state

The worktree was already dirty before archive work. Existing tracked edits,
tracked deletions, untracked canon/native planning files, and `tmp/` artifacts
were preserved. The snapshot is sourced from the selected Git commit, not from
those worktree paths. `MANIFEST.json` records the generation-time dirty tree,
which contains both the preserved preflight changes and the in-progress A1
files; the preflight state was inspected separately before A1 edits began.

The architecture plan referenced `07a2640...` on `origin/main`; the actual HEAD
was the divergent `05996b2...`. The latter is therefore the source of truth for
this archive. Its behavior-bearing runtime files match the shared parent
`995b572...`; its additional tracked content is planning and dataset material.

## Verification commands

The architecture plan normally orders baseline verification before archive
generation. The user's higher-priority execution gate required all testing to
pause until explicit confirmation, so A1 files were first prepared without
execution. After confirmation, the tests and deterministic run below were
performed, the results were written here, and the archive was regenerated and
rehashed. No local LLM or image generation was included.

### Full structural suite

The first unfiltered dirty-worktree run used a repo-local temp directory because
the default Windows pytest temp root was not readable:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
app\backend\.venv\Scripts\python.exe -m pytest -q `
  --basetemp output\pytest-a1-active-20260713-01
```

Initial result: **1 failed, 74 passed, 3 subtests passed**. The sole failure was
the user's then-untracked `tests/v2/test_canon_claim_registry.py`: five canon
claims referenced the tracked
`plans/REI_v3_Codex_canonical_v2_QLoRA_plan_2026-07-10.md`, which was already
deleted in the user's worktree before A1. After explicit user direction, those
five `source_file` values were retargeted to the byte-identical archived plan at
`plans/archive/REI_v3_Codex_canonical_v2_QLoRA_plan_2026-07-10.md` rather than
restoring the superseded plan to the active plans root.

The direct validator and literal unfiltered kickoff command were then rerun with
repo-local `TEMP`/`TMP` environment variables:

```powershell
$tempRoot = Join-Path (Resolve-Path .).Path output\temp-a1-final-20260713-02
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
$env:TEMP = $tempRoot
$env:TMP = $tempRoot
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
app\backend\.venv\Scripts\python.exe scripts\validate_rei_canon_v2.py
app\backend\.venv\Scripts\python.exe -m pytest -q
```

Final result: validator **OK**; pytest **PASSED — 75 passed, 3 subtests
passed**. **Kickoff gate status: PASSED.**

The A1-controlled active suite excludes only those untracked v2 tests:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
app\backend\.venv\Scripts\python.exe -m pytest -q `
  --ignore=tests\v2 `
  --basetemp output\pytest-a1-controlled-20260713-01
```

Result: **PASSED — 64 passed, 3 subtests passed**. This includes the new archive
boundary tests.

The source-commit reference suite was then run from `snapshot/` with explicit
`reference_tests` collection:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
$repo = (Resolve-Path .).Path
$python = (Resolve-Path app\backend\.venv\Scripts\python.exe).Path
$basetemp = Join-Path $repo output\pytest-a1-archive-20260713-01
Push-Location archive\rei_v3_text_llm_baseline_2026-07-13\snapshot
& $python -m pytest -q reference_tests --basetemp $basetemp
Pop-Location
```

Result: **PASSED — 60 passed, 3 subtests passed**.

### Deterministic profile matrix

The archived source runner was executed with the model-disabled provider and
all output kept outside the archive:

```powershell
app\backend\.venv\Scripts\python.exe `
  archive\rei_v3_text_llm_baseline_2026-07-13\snapshot\scripts\run_rei_profile_matrix.py `
  --provider deterministic `
  --output-dir output\archive-baseline-deterministic-a1 `
  --docs-summary-dir output\archive-baseline-deterministic-a1-docs
```

Status: **PASSED**. Run ID `20260713_092820` completed all 156 cases with zero
fallbacks, missing-required-key cases, processor-identity violations, false
positives, false negatives, evaluator warnings, or actionable failures. Total
model tokens: `0`; `ProviderSelection` used `provider_mode="deterministic"` and
`use_llm=False`. Here `fallback_count=0` means that no exception/provider
fallback event was recorded; the signals themselves still came from the
deterministic baseline path by design.

### Archive hash verification

The archive tool computes SHA-256 for every non-self-referential payload file
and re-reads each file after writing. An independent PowerShell pass then parsed
every `FILES.sha256` entry and recomputed it with `Get-FileHash -Algorithm
SHA256`.

```powershell
$root = (Resolve-Path archive\rei_v3_text_llm_baseline_2026-07-13).Path
Get-Content (Join-Path $root FILES.sha256) | ForEach-Object {
  if ($_ -notmatch '^([0-9a-f]{64})  (.+)$') { throw "Invalid checksum line: $_" }
  $expected = $Matches[1]
  $relative = $Matches[2]
  $actual = (Get-FileHash -Algorithm SHA256 `
    -LiteralPath (Join-Path $root $relative)).Hash.ToLowerInvariant()
  if ($actual -ne $expected) { throw "SHA-256 mismatch: $relative" }
}
```

Status: **PASSED**. There are 75 hashed files plus the intentionally
self-excluded `FILES.sha256`: 69 source-snapshot records, four hand-authored
archive documents, `SOURCE_COMMIT`, and `MANIFEST.json`. The manifest separately
records metadata and SHA-256 for 13 source PDF/DOCX documents that were not
copied.

### Live local-LLM smoke

Status: **NOT RUN — EXPLICITLY EXCLUDED BY USER DIRECTION**. No model
availability/digest query, inference request, `ollama ps` placement check, or
model download was performed as part of A0/A1. The earlier runtime version
query did not load or invoke a model.

A one-case smoke and a new 156-case LLM run are both outside this verification.

## Last known full 156-case evidence

The last clone-visible full result is
`Docs/evals/rei_profile_matrix_summary_2026-05-18.md`:

- run ID: `20260517_214607`;
- provider/model: Ollama / `granite4.1:30b`;
- context: `65536`;
- GPU layers option: `999`;
- cases: `156`;
- fallbacks: `0`;
- missing-key cases: `0`;
- processor identity violations: `0`;
- total tokens: `1,498,792`.

The source-commit `CURRENT.md` points to a later known local full run under
`output/reports/rei_profile_matrix/20260519_153731_granite4_1_30b_64k_gpu999_postfix/`.
Its local summary reports 156 cases, zero fallbacks, zero missing-key cases,
zero identity violations, one false positive, eight hard plus one soft false
negative (nine actionable failures), 66 evaluator-warning cases, and 1,501,216
tokens. Because the raw run is not clone-reproducible and is excluded from this
archive, the 2026-05-18 document above remains the last clone-visible full run.
The tracked 2026-05-19 daily summary contains only 40 cases and must not be
treated as the full matrix.

## Reproduction limits

- Repository-level `output/` reports and raw case files are excluded by archive
  policy, whether tracked historically or local-only.
- Local prompt overrides, GUI history, logs, caches, `.venv`, and model blobs
  are intentionally excluded.
- A model tag such as `granite4.1:30b` does not freeze the exact model digest.
- The baseline does not record a generation seed, and live providers/runtimes
  can change output across versions.
- The source commit pins application libraries but not pytest, Python, Git,
  Ollama, transitive wheels, or the operating-system image.
- Original PDF/DOCX research documents are not duplicated; their hashes are
  recorded in the manifest.
- The actual source commit diverges from the plan's expected source commit, as
  documented above.
- Hash verification proves archive integrity, not semantic equivalence of a
  future local-LLM run.

## Known architectural limitations

- three text processors receive the same text plus profile/influence data;
- character authority uses continuous numeric weights;
- acceptance and situational activation are keyword/regex heuristics;
- confidence and a situational bonus can change the fallback resultant;
- EgoResultant is a separate synthesis call rather than a time-spanning Ego
  composition;
- deterministic mode validates fallback mechanics, not LLM semantics;
- GUI and baseline runner follow different provider/coercion paths.
