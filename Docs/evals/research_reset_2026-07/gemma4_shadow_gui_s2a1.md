# Gemma text-shadow GUI S2A.1 browser smoke

Date: 2026-07-20

Branch: `codex/rei-english-runtime-smoke`

Starting head: `da4e91ecfe8a57c30f590a614cf8446d42d8981d`

This was a read-only replay of the committed S1, S1R, and EN1 evidence. It
made no REI cycle request, provider request, Ollama request, or model call.
Runtime, provider, language-contract, and frozen evidence semantics were not
changed.

## Checks

- The shadow evidence registry cold-verified all three allowlisted roots and
  both external receipts.
- `en1-runtime` was the default API and frontend selection.
- The selector separated `CURRENT RUNTIME EVIDENCE` from `HISTORICAL
  EVIDENCE`.
- EN1 displayed English model-facing observations, public options,
  uncertainty, bounded unknown reasons, and Gemma claims.
- EN1 Emocio displayed successful full epistemic abstention with no fabricated
  claim or citation.
- EN1 Instinkt displayed one action-only
  `protection_regulation/conserve` claim with citation `observation_006`; option
  and motive remained unknown.
- Current EN1 API output contained no `canonical_sl`, `notes_sl`, or
  `prompt_sl` field.
- S1 and S1R remained available, unchanged, and visibly marked as historical
  Slovene model-boundary evidence retained for provenance rather than the
  active runtime contract.
- S1 preserved its bounded Emocio failure and authoritative deterministic
  success; S1R preserved full-abstention/action-only lane shapes.
- The local evaluator-debug toggle exposed two isolated ground-truth cards and
  the warning `Racio did not receive evaluator ground truth.` only while
  enabled.
- At 1440 × 1000 the EN1 evidence selector, current-runtime boundary, and
  no-authority status were visible.
- At an approximately 390 px mobile viewport, the two interpretation grids
  stacked to one column and page width had no horizontal overflow.
- Browser console: 0 errors, 0 warnings.
- Browser network: 14 GET requests, 0 POST requests, 0 model/provider endpoint
  requests, and 0 HTTP errors.
- Live model calls during S2A.1: `0`.

Local ignored screenshots:

- `output/playwright/s2a1-shadow-gui/desktop-en1.png`
- `output/playwright/s2a1-shadow-gui/mobile-en1.png`

Result: passed. This is presentation evidence only, not a holdout, promotion,
or grant of authority.
