# Gemma 4 Racio epistemic V3 P3 confirmation

Date: 2026-07-17

Branch: `codex/racio-gemma4-epistemic-interpreter`

Base: `769bef3070f511f34ee97cc3dcabf40ecbb9d4ca`

Status: technical confirmation passed; stopped before G3C

## Scope

P3 adds the minimal `RacioEpistemicDraftV3`, a deterministic nonsemantic
canonicalizer, a narrow one-attempt Gemma chat transport, and a V3 provider
bridge. The historical V2 provider remains byte-identical at SHA-256
`51b10fb2ac67491250d5cdb69d584b16bb33aa9765ffce9d7f29aa346fa854a8`.
The change touches exactly three source files and two test files. Focused
model-free verification passed `161/161` tests.

The precommitted packet is a transparent `canonical_sl_only` transport case,
not a semantic holdout and not part of future G3C metrics. It contains one
atomic spatial-retreat observation, two opposing public options, no independent
motive evidence, and a bounded uncertainty statement.

## Frozen pre-call provenance

- provider revision: `rei-racio-gemma4-epistemic-v3-chat-v1`
- provider ID: `provider_17dcc6c0b72e73c3edb665e03bcb7baa`
- model/digest: `gemma4:31b` / `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`
- endpoint/server: `http://127.0.0.1:11434/api/chat` / Ollama `0.31.2`
- instruction SHA-256: `470bb45de824a438aafdbb3efeae924c71d2bfce844eddf69597443b06bfc30d`
- DraftV3 schema SHA-256: `321cecc980ec82346260b6ef3910a69a5f9b91233f101526254ff3e392704d6a`
- packet ID: `racio_epistemic_packet_v3_a30be5ac03149c982d9b0f1ec80ff755`
- packet SHA-256: `e13b268ae91605638943094a643534689b9e833f2240c9b778fac77bfd990de4`
- provider payload SHA-256: `45d123f7b1c1e1d1c9d24dc2d7199685cb49a8421e4dde140aed0963867a1d66`
- chat messages SHA-256: `9e21989e4122696b727f825d32a643efbe80c8a855eca862bb42e933d35fa05c`
- request payload SHA-256: `ae22e3d62bf51b38054099e4e06ea57c79cd8e5e2bb2bdad6fc424b29b55c5c3`
- call ID: `provider_call_1552cece0961239a5ed87e8341f3def9`
- call-spec SHA-256: `46b7858e9bbce09f6627685525cfa13b8f162b4d20e5943448b740af2222f1ba`
- preflight SHA-256: `f70d59e087ff17f982c20aea0ba0ec611efa071396e6e70b03ab61d5340305c2`

The frozen profile is seed `314159`, temperature `0.0`, top-p `0.95`, top-k
`64`, context `65536`, `num_gpu=999`, `num_predict=16384`, retry `0`, and
fallback `none`. Preflight performed only `/api/version`, `/api/tags`, and
`/api/show`; `/api/chat` dispatch count was `0`.

## Outcome

The single authorized `/api/chat` call passed with calls/retries/fallbacks
`1/0/0`. It returned `done_reason=stop`, kept thinking separate, produced a
strict DraftV3, and canonicalized without semantic repair into a valid
InterpretationV3.

The draft reported one `protection_regulation/retreat` action at confidence
`0.9`, selected `option_001` at confidence `0.9` with its own
`observation_001` citation, returned no motive hypothesis, and self-reported
option mapping as `not_uncertain` and motive interpretation as `not_reported`.
The canonical output retained the same semantic claims, computed the exact
global citation union `["observation_001"]`, and inserted only the standard
bounded motive-unknown reason. These are technical outputs, not semantic or
calibration acceptance.

- DraftV3 SHA-256: `42fd718cefa995a7637e7acf53e8f15655f5abfe5db3b64b5a0fc949456ab2ba`
- InterpretationV3 SHA-256: `286cb5b4e27874cb083b1a2dbaed811d9763d17956b5ec424f085d77a5cad505`
- response evidence ID: `gemma4_epistemic_v3_response_4efca5d774c39511c4003f2b9c29fa49`
- response evidence SHA-256: `80f9ee924ec38352678c0fd96329f2cd239987e3fec72d4a5f4b2eb584370cc7`
- `ProviderCallRecord` SHA-256: `ed08427bf69f631f4ed9fa06063df0bd51c1d3b4947817cc253c2642b9709e3a`
- response envelope: `3486` bytes, SHA-256 `cfa9dde5fa914ea561f26a06914a94482db2ae110e3acfb118cac5b69e7cba4e`
- validated final JSON: `566` bytes, SHA-256 `6bfa7651bd5c55f9e639264596d5897ec7643a3488e2031fabecea2eaf520034`
- private thinking fingerprint: `2461` bytes, SHA-256 `2cb045aa5c1d4337f956605f32fddb791d8c4a92ae32ece1ef191c0582161387`

Thinking content was neither printed nor persisted. Runtime evidence confirmed
the exact model digest, active context `65536`, requested `num_gpu=999`, and
byte-exact full-GPU placement (`20,166,119,259 / 20,166,119,259` bytes,
rounded `100%`). The structural sidecar contains only
`option_id_present=true` and `motive_hypothesis_count=0`; it remains explicitly
nonsemantic and has no governance effect.

P3 does not promote Gemma, start G3C, enter runtime/governance, or contribute
semantic metrics. Work stops at this human-review boundary.
