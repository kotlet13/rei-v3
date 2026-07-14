# Runtime artifacts

Runtime outputs are deliberately not copied into this archive. They may contain
large, machine-specific, or overwritten intermediate results. The archive
policy excludes repository-level `output/` and `logs/` even where historical
files were tracked; the later full run named below is local-only.

Known references:

- Last clone-visible full matrix summary:
  `snapshot/Docs/evals/rei_profile_matrix_summary_2026-05-18.md`
- Later tracked daily summary with only 40 cases:
  `snapshot/Docs/evals/rei_profile_matrix_summary_2026-05-19.md`
- Pre-existing local full-run pointer (not archived):
  `output/reports/rei_profile_matrix/20260519_153731_granite4_1_30b_64k_gpu999_postfix/`
- A1 deterministic verification run (not archived):
  `output/archive-baseline-deterministic-a1/`
- A1 pytest temporary trees (not archived): repo-local `output/pytest-a1-*`
  directories used to avoid the unreadable global Windows pytest temp root.

Excluded artifact classes include `output/`, logs, caches, local prompt
overrides, GUI history, model blobs, `.venv`, and temporary files. Recreate new
artifacts from the tagged baseline only after verifying the environment and
obtaining the applicable execution approval. A1 generated the approved
deterministic and pytest artifacts above; no image generation or local LLM call
occurred.
