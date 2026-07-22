# EN3 observable English shadow cycle

Status: completed development smoke; shadow-only; no authority; not a holdout;
no model promotion.

## Sealed execution

- Execution head: `a6a6a9319595bb210c96d8e1934edfd68ddcf1e6`
- Evidence-preservation commit: `5edc3cb270fda1ded8e2b5ac9e5356c80e19c498`
- Model: `gemma4:31b`
- Exact digest: `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`
- Provider revision: `rei-racio-gemma4-epistemic-v3-en-explained-chat-v1`
- Calls / retries / fallbacks: `2 / 0 / 0`
- Call order: Emocio, then Instinkt
- Context / placement: `65536 / 100% GPU`
- Thinking content persisted: `false`

## Result

The authoritative deterministic cycle completed unchanged. Both attempted
shadow lanes are now observable even when Draft validation rejects the final
Gemma response.

Emocio returned no action, option, or motive claim. Its final response was
rejected at `draft_v3_validation`. The option-abstention citation list contained
the out-of-scope value `observation_000//not_found` and was not in canonical
sorted order. The exact bounded validator message was:

`Claim-absence explanation citations must be sorted and unique`

The exact rejected final content, its content hash, and the exact validation
error are preserved as no-authority failure evidence. No accepted Emocio
shadow interpretation was published.

Instinkt succeeded with one bounded action claim, one option inference, and
one contextual motive hypothesis. Its accepted result remains diagnostic only.

## Evidence closure

- Root: `Docs/evals/semantic_lab_v1/en3-gemma4-observable-shadow-2026-07-22`
- Manifest ID: `gemma4_en3_shadow_manifest_c5da1c493700732c96d5882970cbdeb5`
- Receipt ID: `gemma4_en3_shadow_receipt_1d495f5c19884e7d68543a4bb735c36f`
- Root and external receipt cold verification: succeeded
- Model calls during GUI registration and replay verification: `0`

The GUI default replay is `en3-observable`. It exposes the exact model request,
the exact rejected Emocio final content and validation error, and the accepted
Instinkt result without loading or calling a model provider.
