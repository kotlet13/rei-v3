# Gemma 4 text shadow S1 reconciliation

This record reconciles the first S1 backend shadow smoke without rewriting its
closed evidence. The original S1 result remains historical and unchanged.

- Original reviewed branch head: `6130942c7726240773d7298d6583a77d38a82650`.
- The Emocio lane returned a valid DraftV3 full abstention but failed during
  canonicalizer validation with `An epistemic v3 interpretation requires
  citations`.
- The Instinkt lane succeeded. The original smoke therefore recorded E/I
  statuses `failed/succeeded` with calls/retries/fallbacks `2/0/0`.
- The failure exposed a structural invariant bug: a nonempty visible packet
  incorrectly required a global citation even when Racio made no action,
  option, or motive claim. Full abstention must instead retain an empty exact
  union of claim-local citations and all three bounded unknown reasons.
- The first cold-verification attempt also exposed a verifier bug. Its Windows
  path expression matched `p:/` inside persisted
  `http://127.0.0.1:11434/api/chat` URLs. The reconciled detector still rejects
  local drive paths while allowing URI schemes.
- After the detector fix, a read-only `--cold-verify` of the original S1 root
  succeeded, including both native run manifests, the no-authority ledger,
  the closed smoke inventory, seal ancestry, and the private-content scan.
- `Docs/evals/semantic_lab_v1/s1-gemma4-text-shadow-2026-07-19/` was not
  modified. Its 115 committed files remain the original S1 evidence.

S1R is a repeated technical development smoke. It is not a semantic holdout,
does not promote Gemma, and grants no governance, decision, behavior,
MindWorld, or Ego-composition authority.
