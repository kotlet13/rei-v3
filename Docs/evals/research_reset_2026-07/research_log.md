# REI research reset log

## R0 — governance reset

- date: 2026-07-16
- commit: this file's introducing R0 commit (resolve from Git history)
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
