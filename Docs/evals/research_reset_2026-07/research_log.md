# REI research reset log

## R0 — governance reset

- date: 2026-07-16
- commit: `52150ced16b612245070c46aff607d268c015f3b`
- hypothesis: restoring feature-branch and human-review gates will put
  exploratory evidence ahead of further validation hardening.
- experiment: freeze the audit-heavy `main` snapshot, replace the main-only
  governance rule, mark the former plan historical, and publish an honest
  research-status header.
- visible result: the two focused architecture suites passed (6 tests), and
  `git diff --check` passed before the R0 commit.
- human decision: reset and X1 were explicitly authorized; review is required
  after X1.
- next allowed step: X1 — bounded four-image Emocio exploratory screen.

## X1 — four-image Emocio exploratory screen

- date: 2026-07-16
- commit: this entry's X1 commit (resolve from Git history)
- hypothesis: at least one of the two preselected image-edit families may turn
  the same frozen current scene into two preserved but meaningfully different
  option-conditioned future scenes.
- experiment: exactly four calls in the frozen order LongCat `enter_circle`,
  LongCat `remain_edge`, OmniGen `enter_circle`, OmniGen `remain_edge`; no
  retry, prompt change, extra seed, fallback, DINO, or additional model.
- visible result: run `x1_20260716T045904Z` completed all four calls in 238.9
  seconds with technical status `passed`, no recorded warning/error, source
  SHA-256 unchanged, and four 1024 × 768 PNG outputs. The contact sheet was
  technically checked only for readable labels and complete panel placement;
  Codex did not perform the semantic review.
- output path:
  `C:\Users\Kotlet\Codex\github\rei-v3\output\exploration\emocio_four_image_screen\x1_20260716T045904Z`
- manifest SHA-256:
  `614fdad52944e9f16adb29fa51d5dabd330640588fad45232d1cc988ca19094a`
- human decision: pending review of `contact_sheet.png` and
  `review_template.md`.
- authority: `exploratory_no_authority`; no semantic, production, or external-
  evidence authority was granted.
- next allowed step: none until the user completes the X1 human review.

## X1 follow-up — source and conditioning exploration

- date: 2026-07-16
- commit: no tracked implementation commit; generated exploratory artifacts
  remained outside Git.
- hypothesis: the original source geometry and over-constrained prompts, rather
  than image editing as a whole, caused the first action-conditioned failures.
- experiment: replace the ambiguous source with a human-reviewed doorway scene,
  exclude OmniGen by user decision, compare FLUX and LongCat prompt forms, and
  retain every output without hidden best-of-N selection.
- visible result: the user selected LongCat as the most logical candidate after
  reviewing a two-pass ENTER result and a one-pass REMAIN result. The selected
  workflow uses two frozen English edits for ENTER and one frozen Chinese no-op
  edit for REMAIN; this is a workflow pin, not a claim that Chinese is generally
  superior.
- selected source SHA-256:
  `3112384b360e5d8375519253947dd6ab94192559be1e0615bf58674d69bce29f`
- selected-pair record SHA-256:
  `592112bdbdc3461f58ec342487291025eaa4130120f634c69499994e4a47ab92`
- human decision: continue with LongCat only and run the smallest sensible
  three-seed repeatability screen.
- authority: exploratory only; the parent research-quality goal remains
  blocked.
- next allowed step: V1 LongCat seed screen on a dedicated feature branch.

## V1 — LongCat three-seed screen

- date: 2026-07-16
- branch: `codex/emocio-exploration-v2`
- commit: this entry's V1 commit (resolve from Git history)
- hypothesis: the frozen LongCat workflow may produce reviewable ENTER and
  REMAIN states for at least two of the three precommitted root seeds.
- experiment: roots `424240`, `424241`, and `424242`; for each root, ENTER pass
  1, ENTER cleanup from the native pass-1 bytes, and REMAIN from the original
  source. This produced six final review images and three diagnostic
  intermediates in exactly nine model calls. No retry, fallback, prompt change,
  extra seed, language variant, model change, or automated semantic judge was
  used.
- visible result: run `v1_20260716T083028Z` completed 9/9 calls in 200.4 seconds
  with technical status `passed`. Source and preflight hashes remained
  unchanged. Root `424240` reproduced the five historical native/review PNG
  hashes byte-for-byte. The six final panels are complete and readable; their
  semantic usefulness is intentionally pending human review.
- output path:
  `C:\Users\Kotlet\Codex\github\rei-v3\tmp\codex-worktrees\emocio-exploration-v2\output\exploration\emocio_longcat_seed_screen\v1_20260716T083028Z`
- manifest SHA-256:
  `14443b9f9570316715a62bcd1f7effaa638c93e66fa2926e45446abd3f4ea0ba`
- focused tests: `2 passed`; compile check, `git diff --check`, and independent
  technical artifact audit passed.
- human decision: option-level review completed. The user judged ENTER
  successful in 2/3 roots: `424240` and `424242` were accepted; `424241` failed
  because the navy-sweater person disappeared. All three REMAIN outputs were
  accepted, so 2/3 roots have both final outputs accepted. Pair-specific rubric
  fields were not separately scored, and no further phase was authorized.
- authority: `exploratory_no_authority`; semantic review by Codex is false;
  semantic, production, and external-evidence authority remain false; the
  parent goal remains blocked.
- next allowed step: none until a new explicit user direction.

## V1 follow-up — English REMAIN stabilization

- date: 2026-07-16
- branch: `codex/emocio-english-remain-v1`
- implementation commit: `e642349c66327b829cc766c97365bd3e11b17423`
- hypothesis: one frozen, explicit English preservation prompt may retain the
  already accepted REMAIN state in at least two of the three precommitted V1
  roots, without relying on Chinese instructions.
- experiment: LongCat only, original frozen source, roots `424240`, `424241`,
  and `424242`, and the existing derived REMAIN seeds. Each call received the
  same ASCII English prompt, SHA-256
  `bea218feca5c63a89846d89b7882fba1b097fb45d828eb08c50ce42f63ac1564`.
  Exactly three source-to-REMAIN calls ran in the frozen order, with no ENTER
  calls, retry, fallback, prompt change, extra seed, language variant, model
  change, or best-of-N selection.
- visible result: run `english_v1_20260716T092856Z` completed 3/3 calls in
  69.9 seconds with technical status `passed`. Every call used the pinned
  source SHA-256, native outputs were 1184 × 896, review outputs were
  1024 × 768, and the source, preflight, runner, and snapshot manifest remained
  unchanged. The three review panels are complete; semantic acceptance remains
  pending user review.
- output path:
  `C:\Users\Kotlet\Codex\github\rei-v3\tmp\codex-worktrees\emocio-english-remain-v1\output\exploration\emocio_longcat_english_remain\english_v1_20260716T092856Z`
- manifest SHA-256:
  `b536de3c4253d45b835e8d1b5c16b313fcc643729593f1a41f532dbda420606b`
- focused tests: `3 passed`; compile check and `git diff --check` passed before
  inference. An independent technical artifact audit passed with no hash,
  lineage, dimension, call-order, or authority mismatch; it remained separate
  from human semantic review.
- human decision: pending review of `contact_sheet.png` and
  `review_template.md`; the precommitted minimum is at least 2/3 accepted
  English REMAIN images.
- authority: `exploratory_no_authority`; semantic review by Codex is false;
  semantic, production, and external-evidence authority remain false; the
  parent goal remains blocked.
- next allowed step: none until the user completes this human review.
