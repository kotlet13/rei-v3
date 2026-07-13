# REI-v3 textual architecture baseline

This archive freezes the textual three-processor REI-v3 architecture before
the native-modalities and Ego-composition rewrite. It is a historical and
rollback artifact, not an importable Python package and not a declaration that
the archived design is canonical.

## Identity

- Archive ID: `rei_v3_text_llm_baseline_2026-07-13`
- Source commit: `05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`
- Source branch at preflight: `codex/pre-canonical-v2-snapshot`
- Baseline tag: `rei-v3-text-llm-baseline-2026-07-13`
- Active entrypoint: `ReiEngine.run_rei_cycle`
- Baseline runner: `scripts/run_rei_profile_matrix.py`
- Baseline shape: 13 profiles x 12 scenarios = 156 cases

The architecture plan expected
`07a26401e0b2707a79018efc2fdd7194d3062566` on `origin/main`. The actual
checked-out source was the divergent sibling commit `05996b2...`, which adds a
canonical-v2/QLoRA plan and draft pilot dataset on top of the shared runtime
commit `995b572...`. The worktree was not reset; this archive intentionally
uses Git blobs from the actual source commit rather than copying dirty files.

## Contents

- `ARCHITECTURE.md`: an evidence-based description of the archived runtime.
- `BASELINE_VERIFICATION.md`: environment, commands, results, and limitations.
- `SOURCE_COMMIT`: the full source commit ID.
- `MANIFEST.json`: source identity, copied files, exclusions, and verification metadata.
- `FILES.sha256`: SHA-256 checksums for the non-self-referential archive payload.
- `snapshot/`: selected files materialized from the source Git commit.
- `snapshot/reference_tests/`: the source `tests/` tree, renamed so it is not active pytest input.
- `artifacts/README.md`: pointers to intentionally excluded runtime artifacts.

The snapshot contains the source-commit versions of:

- `app/backend/rei/`;
- `app/gui/`;
- `scripts/`;
- `tests/` as `snapshot/reference_tests/`;
- `knowledge/`;
- tracked `datasets/` files;
- `Docs/evals/`;
- tracked plans from the actual root `plans/` directory;
- `app/backend/requirements.txt` and `pytest.ini`;
- `README.md`, `CURRENT.md`, and `.gitignore`.

The archived `snapshot/plans/REI_v3_Codex_first_execution_prompt.md` is the
unaltered source-commit version. The active root copy received its
`SUPERSEDED` banner only as part of A1, after the historical payload boundary
had been fixed.

## Deliberate exclusions

The archive does not contain:

- any pre-existing `archive/` tree, including `archive/non_baseline_2026-05-21/`;
- `output/` run products;
- caches, logs, `.venv`, model blobs, or temporary files;
- local GUI prompt overrides or test history;
- untracked or modified worktree content that was not part of the source commit;
- the original research PDF/DOCX files under `Docs/`.

Tracked source documents are not duplicated. Their source paths, byte sizes,
and SHA-256 digests are recorded under `source_documents` in `MANIFEST.json`:

- `Docs/Eros - pogovori.pdf`
- `Docs/REI osnova Emocio.docx`
- `Docs/REI osnova Instinkt.docx`
- `Docs/REI osnova Racio.docx`
- `Docs/REI osnove.docx`
- `Docs/antropološki dokaz.docx`
- `Docs/erosov značaj.docx`
- `Docs/geološki dokaz.docx`
- `Docs/glasbeni dokaz.docx`
- `Docs/matematični dokaz.docx`
- `Docs/psihološki dokaz.docx`
- `Docs/sedmi dokaz.docx`
- `Docs/zgodovinski dokaz.docx`

## Reproduction

From a checkout that contains the baseline tag, regenerate the payload with:

```powershell
python scripts/archive_rei_architecture.py `
  --archive-id rei_v3_text_llm_baseline_2026-07-13 `
  --source-ref rei-v3-text-llm-baseline-2026-07-13 `
  --source-branch codex/pre-canonical-v2-snapshot `
  --force
```

The tool enumerates files with `git ls-files`, reads bytes from the selected
Git object, writes deterministic snapshot paths, computes SHA-256 values, and
re-reads the files to verify them. During `--force` regeneration it preserves
the four hand-authored archive documents already present in this target and
includes them in `FILES.sha256`. It never treats the current worktree as the
source snapshot payload.

`FILES.sha256` intentionally excludes itself to avoid an impossible recursive
checksum. A successful regeneration performs the full post-write verification;
`BASELINE_VERIFICATION.md` records the independent verification performed for
this freeze. The repository's scoped `.gitattributes` rule marks this archive
as `-text`, preventing checkout-time line-ending conversion from invalidating
the byte-level checksums.

## Rollback

Create an isolated checkout rather than resetting a dirty worktree:

```powershell
git worktree add --detach ..\rei-v3-text-baseline `
  rei-v3-text-llm-baseline-2026-07-13
```

The explicit commit can be used if the local tag is unavailable:

```powershell
git worktree add --detach ..\rei-v3-text-baseline `
  05996b2b4a34cf6dd654e032d5dbc26bb5373ef0
```

If neither Git object is available, `snapshot/` remains a filesystem recovery
copy. Restore it into a new isolated directory and rename
`snapshot/reference_tests/` back to `tests/`; do not place the recovered files
on the active runtime import path.

Install the pinned source-commit requirements, restore any intentionally
external runtime artifacts separately, verify `FILES.sha256`, and run the
reference tests only inside that isolated checkout. A live LLM run additionally
depends on the Ollama runtime, exact model bytes, context settings, GPU offload,
and provider behavior described in `BASELINE_VERIFICATION.md`.
