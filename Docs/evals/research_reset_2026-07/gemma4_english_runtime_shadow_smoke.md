# Gemma 4 English runtime shadow smoke

Status: technically passed development smoke. This is not a holdout, model
promotion, or authority grant.

## Sealed execution

- execution head: `3979b7884eb9b5196d47bc4ad188f4dfab60cad2`
- language policy: English-only local-model input
- model: `gemma4:31b`
- provider revision: `rei-racio-gemma4-epistemic-v3-en-chat-v1`
- calls/retries/fallbacks: `2/0/0`
- context: `65536`
- GPU placement: `100%`
- E result: succeeded, full epistemic abstention
- I result: succeeded, action-only `protection_regulation/conserve` claim with
  `functional_inference` support; option and motive remained unknown
- DraftV3 and canonical interpretation validity: `2/2`
- authoritative cycle unchanged: `true`
- thinking content persisted: `false`
- governance, decision, behavior, MindWorld, and Ego authority: `none`

## Offline evidence reconciliation

Both authorized model calls completed before the first manifest issuance. The
initial issuance then failed because the manifest content-ID prefix was 36
characters long, while the global content-ID contract permits at most 32.
Successful execution evidence was preserved unchanged in commit
`2d2ddd20d2b3f60a2e50c4301312c7bb1b5d97f0`.

Commit `4314767a7c0770dbc9b42c58b61106d2b492ac1b` replaced only the invalid
caller prefix with `gemma4_en_shadow_manifest` and added a model-free,
create-only offline completion path. The global content-ID contract was not
changed. Offline completion performed zero provider or model calls and changed
zero existing evidence files; it added only the missing manifest and external
receipt.

- manifest ID: `gemma4_en_shadow_manifest_559dc432abe2a49c8f7897f076647b9e`
- manifest SHA-256: `2f8555a866259d86604fd27ad333c1fba764fc21e6bc3ce5be52a11cf759d5d5`
- receipt ID: `gemma4_english_shadow_receipt_9faebda91fa84456a33a4306161e69a6`
- receipt SHA-256: `4d759822a325e38a1015b26c4e74460988d01005f03eab69e121e271be23af47`
- evidence-root cold verification: succeeded
- model calls during reconciliation: `0`

The deterministic interpreter remains authoritative. Gemma remains shadow-only
and unpromoted.
