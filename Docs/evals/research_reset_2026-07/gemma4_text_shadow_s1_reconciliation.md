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

## S1R post-verification receipt reconciliation

The model execution was not repeated. The original S1R accounting remains
exactly two calls, zero retries, and zero fallbacks (`2/0/0`).

- Execution head: `82b219c17eb62a1afbc807159da05244923998dd`.
- Verification head: `e5bbaf3d8da29f2e5474bc49e6f9931bc7c55a34`.
- Receipt issuance originally failed because the content-ID prefix
  `gemma4_text_shadow_cold_verification` was 36 characters long, exceeding the
  global 32-character limit. Its first character and character set were valid;
  length was the sole cause.
- The reconciled caller uses the valid, stable 18-character prefix
  `s1r_verify_receipt`. The global content-ID rule was not changed.
- Read-only integrity verification succeeded for both the historical S1 root
  and the closed S1R root. Their inventory hashes remained unchanged before
  and after receipt issuance.
- External receipt ID:
  `s1r_verify_receipt_f589ffd26f095f610ff27688f727b1d0`.
- External receipt SHA-256:
  `f8338d63a1cc12a1e133ff289630acde13c3fbebdb1dd97069e827519366f843`.
- S1R technical status: `passed`.
- Gemma status: `shadow-only`.
- Authority status: `none`.

The receipt was generated entirely from committed manifests, stored result
artifacts, typed DraftV3/canonicalizer replay, read-only verifier results, and
Git commit identities. Receipt generation made zero provider or model calls
and changed zero files inside either evidence root.

Final model-free closure checks succeeded:

- focused shadow tests: `26 passed`;
- focused V3 contract/provider tests: `76 passed`;
- full test suite: `1811 passed`;
- deterministic native cycle: all invariants passed;
- deterministic profile matrix: `156/156` rows with zero native-processor or
  model executions;
- original S1 root, S1R root, and the external receipt: cold verification
  succeeded.
