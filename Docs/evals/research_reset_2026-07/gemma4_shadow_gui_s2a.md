# Gemma text-shadow GUI S2A browser smoke

Date: 2026-07-19

Main base: `bc8c83d1534a2aad9f5f41d2a69c6bafb9ac7239`

Branch: `codex/racio-gemma4-shadow-gui`

This was a read-only replay of the committed S1 and S1R evidence. It made no
REI cycle request, provider request, Ollama request, or model call.

## Checks

- Microsoft Edge was driven through Playwright against the loopback-only GUI.
- Keyboard `ArrowRight` navigation moved focus and selection from Semantic Lab
  to the existing Racio Interpretation panel.
- S1R Emocio displayed a successful, non-error full abstention with no claims
  or fabricated citations and all bounded unknown reasons.
- S1R Instinkt displayed the action-only claim, its action citation, and
  unknown option and motive states.
- S1 Emocio displayed the bounded `canonicalizer_failure` while preserving the
  visible authoritative deterministic success and unpublished-shadow status.
- The evaluator-debug toggle exposed its warning and ground truth only while
  enabled; disabling it removed the debug region and refetched non-debug data.
- Expanded safe raw shadow details contained neither thinking content nor a
  local absolute path.
- At 1440 × 1000 the authoritative and shadow cards used two columns. At
  390 × 844 they stacked into one column with zero horizontal page overflow.
- Browser console: 0 errors, 0 warnings.
- Browser network: only static assets plus GET requests to bootstrap, Semantic
  Lab, and the registered shadow-evidence endpoints; no POST request and no
  model/provider endpoint.

Local ignored screenshots:

- `output/playwright/s2a-shadow-gui/desktop-s1r.png`
- `output/playwright/s2a-shadow-gui/mobile-s1r.png`

Result: passed. This is presentation evidence only, not a holdout, promotion,
or grant of authority.
