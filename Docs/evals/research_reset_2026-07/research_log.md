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
