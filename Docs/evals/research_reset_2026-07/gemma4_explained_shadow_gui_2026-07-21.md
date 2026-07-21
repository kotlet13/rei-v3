# Gemma explained shadow and GUI reconciliation

Status: development smoke and read-only presentation evidence; not a holdout, promotion, or authority grant.

## Outcome

- Model calls / retries / fallbacks: `2 / 0 / 0`.
- Execution head: `a385158c852c0ab30ab837880c660ee7dd5fad15`.
- Model: `gemma4:31b` at digest `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`.
- Context / GPU request: `65536 / 999`; full-GPU placement remained required.
- Authoritative REI cycle: unchanged.
- Emocio lane: failed at `draft_v3_validation`; no accepted Gemma interpretation was published.
- Instinkt lane: succeeded with one action claim, one option selection, and one contextual motive hypothesis.
- Thinking content: not persisted.
- Evidence root and external receipt: cold-verified.

The new contract requires a concise, cited Gemma explanation whenever an action, option, or motive claim is absent. The real smoke did not produce a reviewable explanation: the Emocio response failed the closed draft schema, while the Instinkt response populated all three claim kinds. This limitation is displayed directly and is not repaired or hidden.

## Exact model input

Both calls used the same system instruction, output schema, model profile, and sampling. Only the packet-local user message differed.

- Provider revision: `rei-racio-gemma4-epistemic-v3-en-explained-chat-v1`.
- System instruction SHA-256: `ae9578804373008564e934c1eeacdf5584310b240d8783506ca708d1743888cc`.
- Draft schema SHA-256: `ace4cd708e283d5ca7561085e42461a8b50badf40c2a90e2def3ec1322ce3cca`.
- Seed / temperature / top-p / top-k: `314159 / 0.0 / 0.95 / 64`.
- `num_predict`: `16384`.
- Request order: `E`, then `I`.

Emocio exact dispatched request hash:

`241f08323136a88ab79e1c33687c5e2967dac17a8da429e40ef6a856f51e93aa`

Instinkt exact dispatched request hash:

`0c65ffdeb6b48e530c76371b95da80155013cee91a62cb0bd1a593f432659224`

The successful Instinkt response evidence stores the complete sanitized request verbatim. The failed Emocio lane did not publish response evidence, so the GUI reconstructs its request from the frozen Emocio packet and the identical persisted request envelope, then refuses to display it unless the reconstruction matches the dispatched request hash above exactly.

The GUI exposes, in expandable sections for each lane:

1. the exact system instruction;
2. the exact packet-local user JSON;
3. the exact JSON output schema;
4. the model, sampling, context, GPU and thinking-channel settings;
5. the complete sanitized `/api/chat` request;
6. the request SHA-256 and whether it was persisted or hash-verified reconstruction.

## Instinkt result

Gemma returned:

- action: `protection_regulation / conserve`, `functional_inference`, confidence `0.8`, citing `observation_006`;
- option: `option_001`, confidence `0.7`, citing `observation_006`;
- motive: `protection / boundary_alarm`, `contextually_supported`, confidence `0.6`, citing `observation_003`;
- uncertainty self-report: `not_reported` for both option mapping and motive interpretation.

These claims remain diagnostic shadow output with `no_authority=true`. They do not affect governance, conscious decision, behavior, MindWorld, or Ego composition.

## GUI presentation boundary

- `EN2 · explained English shadow` is the default current replay.
- `EN1` is retained as historical English evidence.
- `S1` and `S1R` remain historical Slovene evidence.
- Emocio, Instinkt, and Racio are never translated or substituted.
- Model-authored output, deterministic canonicalizer additions, authoritative Racio output, and exact model input are separate sections.
- No aggregate quality score is shown.
- Evidence replay performs zero model calls.
