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
- commit: `dca1d621d648cbbc7c4ba3e12fe6e69a56c92632`
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
  `output/exploration/emocio_four_image_screen/x1_20260716T045904Z`
- manifest SHA-256:
  `614fdad52944e9f16adb29fa51d5dabd330640588fad45232d1cc988ca19094a`
- human decision: pending review of `contact_sheet.png` and
  `review_template.md`.
- authority: `exploratory_no_authority`; no semantic, production, or external-
  evidence authority was granted.
- next allowed step: none until the user completes the X1 human review.

## X1 follow-up — source and conditioning exploration

- date: 2026-07-16
- commit: no tracked implementation commit; generated exploratory artifacts
  remained outside Git.
- hypothesis: the original source geometry and over-constrained prompts, rather
  than image editing as a whole, caused the first action-conditioned failures.
- experiment: replace the ambiguous source with a human-reviewed doorway scene,
  exclude OmniGen by user decision, compare FLUX and LongCat prompt forms, and
  retain every output without hidden best-of-N selection.
- visible result: the user selected LongCat as the most logical candidate after
  reviewing a two-pass ENTER result and a one-pass REMAIN result. The selected
  workflow uses two frozen English edits for ENTER and one frozen Chinese no-op
  edit for REMAIN; this is a workflow pin, not a claim that Chinese is generally
  superior.
- selected source SHA-256:
  `3112384b360e5d8375519253947dd6ab94192559be1e0615bf58674d69bce29f`
- selected-pair record SHA-256:
  `592112bdbdc3461f58ec342487291025eaa4130120f634c69499994e4a47ab92`
- human decision: continue with LongCat only and run the smallest sensible
  three-seed repeatability screen.
- authority: exploratory only; the parent research-quality goal remains
  blocked.
- next allowed step: V1 LongCat seed screen on a dedicated feature branch.

## V1 — LongCat three-seed screen

- date: 2026-07-16
- branch: `codex/emocio-exploration-v2`
- commit: `45f1040e898e337885d974c589ad36a0f06a20b9`
- hypothesis: the frozen LongCat workflow may produce reviewable ENTER and
  REMAIN states for at least two of the three precommitted root seeds.
- experiment: roots `424240`, `424241`, and `424242`; for each root, ENTER pass
  1, ENTER cleanup from the native pass-1 bytes, and REMAIN from the original
  source. This produced six final review images and three diagnostic
  intermediates in exactly nine model calls. No retry, fallback, prompt change,
  extra seed, language variant, model change, or automated semantic judge was
  used.
- visible result: run `v1_20260716T083028Z` completed 9/9 calls in 200.4 seconds
  with technical status `passed`. Source and preflight hashes remained
  unchanged. Root `424240` reproduced the five historical native/review PNG
  hashes byte-for-byte. The six final panels are complete and readable; their
  semantic usefulness is intentionally pending human review.
- output path:
  `output/exploration/emocio_longcat_seed_screen/v1_20260716T083028Z`
- manifest SHA-256:
  `14443b9f9570316715a62bcd1f7effaa638c93e66fa2926e45446abd3f4ea0ba`
- focused tests: `2 passed`; compile check, `git diff --check`, and independent
  technical artifact audit passed.
- human decision: option-level review completed. The user judged ENTER
  successful in 2/3 roots: `424240` and `424242` were accepted; `424241` failed
  because the navy-sweater person disappeared. All three REMAIN outputs were
  accepted, so 2/3 roots have both final outputs accepted. Pair-specific rubric
  fields were not separately scored, and no further phase was authorized.
- authority: `exploratory_no_authority`; semantic review by Codex is false;
  semantic, production, and external-evidence authority remain false; the
  parent goal remains blocked.
- next allowed step: none until a new explicit user direction.

## V1 follow-up — English REMAIN stabilization

- date: 2026-07-16
- branch: `codex/emocio-english-remain-v1`
- implementation commit: `e642349c66327b829cc766c97365bd3e11b17423`
- hypothesis: one frozen, explicit English preservation prompt may retain the
  already accepted REMAIN state in at least two of the three precommitted V1
  roots, without relying on Chinese instructions.
- experiment: LongCat only, original frozen source, roots `424240`, `424241`,
  and `424242`, and the existing derived REMAIN seeds. Each call received the
  same ASCII English prompt, SHA-256
  `bea218feca5c63a89846d89b7882fba1b097fb45d828eb08c50ce42f63ac1564`.
  Exactly three source-to-REMAIN calls ran in the frozen order, with no ENTER
  calls, retry, fallback, prompt change, extra seed, language variant, model
  change, or best-of-N selection.
- visible result: run `english_v1_20260716T092856Z` completed 3/3 calls in
  69.9 seconds with technical status `passed`. Every call used the pinned
  source SHA-256, native outputs were 1184 × 896, review outputs were
  1024 × 768, and the source, preflight, runner, and snapshot manifest remained
  unchanged. The three review panels are complete. The user subsequently
  reviewed all listed preservation criteria and accepted all 3/3 images.
- output path:
  `output/exploration/emocio_longcat_english_remain/english_v1_20260716T092856Z`
- manifest SHA-256:
  `b536de3c4253d45b835e8d1b5c16b313fcc643729593f1a41f532dbda420606b`
- recorded human-review SHA-256:
  `eb4a33f51f2f4f13707611e642fe6aed1f3cf07c16378f1f0124d26f9bc14b66`
- focused tests: `3 passed`; compile check and `git diff --check` passed before
  inference. An independent technical artifact audit passed with no hash,
  lineage, dimension, call-order, or authority mismatch; it remained separate
  from human semantic review.
- human decision: review completed. Roots `424240`, `424241`, and `424242` were
  all accepted. The user confirmed the same four people, the mustard-jacket
  subject and both sneakers fully on the corridor side, the other three adults
  inside the room, acceptable clothing/position/composition preservation, and
  no blocking extra or missing actor or object. Result: 3/3 accepted, exceeding
  the precommitted minimum of at least 2/3.
- authority: `exploratory_no_authority`; semantic review by Codex is false;
  semantic, production, and external-evidence authority remain false; the
  parent goal remains blocked.
- next allowed step: no phase auto-continues; explicit user direction is still
  required before another research phase or merge is proposed.

## X2 — human review decision and Gemma 4 selection

- date: 2026-07-16
- audit branch: `codex/racio-failure-audit`
- audit branch SHA: `78c8bd0c5087c18e4790a542c176b3fd0a0788c0`
- hypothesis: separating direct action and option evidence from cited motive
  hypotheses will make Racio evaluation more epistemically faithful than one
  exact option/action/motive boolean.
- human decision: the X2 audit is accepted with explicit H3, H7, and H11 human
  amendments. The frozen Qwen result remains `23/32 + 23/32`, does not pass, and
  becomes a frozen historical comparison baseline.
- H3 amendment: the visible surface is `desired_scene_absent`, not automatic
  body or boundary alarm; the legacy `broken_scene` gold is too broad for v2.
- H7 amendment: `set_boundary` is an action and does not prove a
  `boundary_alarm` motive.
- H11 amendment: protective alarms form a candidate hierarchy in which
  `boundary_alarm` may be a supported subtype of a broader protective family.
- model decision: `gemma4:31b` is the next and only new candidate for the
  model-backed RacioInterpreter in this cycle. No fallback, ensemble, or new
  Qwen call is authorized.
- model calls in G0: `0`.
- authority: human review authorizes only the bounded G0–G3 development block;
  it grants no semantic, production, default-model, PR, or merge authority.
- next allowed step: G1 — add the parallel epistemic output contract/evaluator
  v2 and complete a deterministic 8–12-case pass-symmetry audit before any
  Gemma call.

## G2 — six Gemma 4 technical probes stopped before the development screen

- date: 2026-07-17
- branch: `codex/racio-gemma4-epistemic-interpreter`
- model: local `gemma4:31b`, exact Ollama digest
  `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`
- runtime identity: Ollama `0.31.2`, `Q4_K_M`, 31,273,089,132 parameters,
  19,868,981,791 serialized bytes, context capability `262144`
- request profile: context `65536`, `num_gpu=999`, seed `314159`, temperature
  `0`, top-p `0.95`, top-k `64`, `num_predict=2048`, stream/raw false,
  keep-alive `10m`, retry `0`, fallback `none`
- first technical probe: exactly one `/api/generate` call using the trivial
  sanitized Slovenian packet; it is not part of any semantic score
- packet SHA-256:
  `fd280f75a1bcd2d70fbc4122c43bbc8a61293f8c411a5ab375301f14646c4059`
- provider payload SHA-256:
  `bc9df98eddac77530d4653a7ebed178f7b060072b3136e77bc6bca15afc7a63f`
- call-spec SHA-256:
  `3780a7250860a4469a911d3d06ca4b5ed15be22514d261031c528e66e5e7d4a3`
- instruction SHA-256:
  `8c496c2be42d16c370eda4a3eb823bd16ccf5b07c2e71f5b21105ffeab90819e`
- model-facing schema SHA-256:
  `92515d2e697ae5892524f5674c708d1b360b280773f125fb8cd902adf05e9385`
- observed placement after the call: `gemma4:31b`, context `65536`, `100% GPU`
- result: `thinking_separation_failure`; Ollama returned no separate non-empty
  thinking field, so the provider rejected the response before structured
  semantic evaluation
- privacy: no thinking text, final response, or raw response envelope was
  printed, stored, or added to Git; no thinking hash exists because the field
  was absent or empty
- user amendment: after the first stop, the user explicitly authorized exactly
  one additional endpoint experiment through native `/api/chat`. This raises
  the bounded cycle ceiling from 17 to 18 calls without authorizing a retry.
- second technical probe: exactly one `/api/chat` call with the same packet,
  digest, instruction, schema, seed, sampling settings, context, and GPU pin;
  the request used system/user messages and sent no unsupported `raw` field
- chat request-payload SHA-256:
  `168adfe902992f90eaded111946747bf7e665bf2d990b9418eb8da8a7757f371`
- chat messages SHA-256:
  `f0e6c6aa1d5398a964e51cc5f10e4640fc830c7ad2413af67e9431898ae90dd5`
- chat call-spec SHA-256:
  `f82edfa196a9de8967ff329a2eeace6cfdb75f56f6676e52029ea83a408669f9`
- chat result: the response passed clean-stop/model/envelope checks, contained
  separate non-empty thinking and final content, and passed post-call exact
  runtime/context/full-GPU checks. It then failed closed as
  `structured_output_invalid` when final content did not validate as
  `RacioEpistemicInterpretationV2`.
- second-probe privacy: no thinking text, final content, or raw response
  envelope was printed, persisted, or added to Git. The one-shot harness exited
  on the sanitized exception, so response/thinking fingerprints were not
  durably captured.
- model-free diagnostic amendment: provider revision
  `rei-racio-gemma4-epistemic-g2-chat-v3` keeps the v2 schema and semantic gate
  fail-closed but makes a future structured-output failure reviewable through
  an exact issue count, sanitized Pydantic error type, schema-whitelisted field
  path, value-free diagnostic fingerprint, and final-response SHA-256/byte
  count. Unknown model-controlled field names collapse to `*`; raw Pydantic
  input, messages, context, final content, and thinking remain unavailable.
- leakage regression: the sanitized exception is raised only after leaving the
  Pydantic exception context; tests require both `__cause__` and `__context__`
  to be absent and verify stable fingerprints across different secret values.
  This amendment made no model call and cannot diagnose the already-discarded
  second response retroactively.
- diagnostic authorization: the user explicitly authorized an evidence-driven
  `/api/chat` diagnosis. It is bounded here to one classification probe and,
  only after a concrete model-free diagnostic refinement, one deterministic
  confirmation probe. Neither is a retry; prompt/schema/sampling changes,
  fallback, another model, and G3 dispatch remain forbidden in this sequence.
- third technical probe: exactly one `g2-chat-v3` `/api/chat` call used the
  current reproducible provider unit-test packet. This packet is not claimed
  to reproduce the discarded second-probe packet byte-for-byte.
- third-probe packet SHA-256:
  `1ec04b21901b29318f2825e4742d8f7e59fe1556a9286d2d99699ee8ab2e70c0`
- third-probe provider-payload SHA-256:
  `8c459e0f8c4a005a589b8a722e8fa8c4df509cd7fc6b0589be1e26f46311a0ad`
- third-probe request-payload SHA-256:
  `e578fa18b42366728fc65d3d20314896cd1712f0c606a09cca43985f7844a583`
- third-probe messages SHA-256:
  `48f7d4e9400f83910579e88073446fcd092409f53dd72c60827d5bdc2322abe1`
- third-probe call-spec SHA-256:
  `fa407defb302cde63263dde7f1718e03d8a3c6b21292872e3928454df031ce18`
- third-probe result: one `/api/chat` dispatch, clean separate thinking and
  final fields, then one `structured_output_invalid` issue of type
  `value_error` at `$`; diagnostic SHA-256
  `9ac3f3295e1e4cd1326880219a9bc6577ac83cd5282e9da022ceadd27a77cd2a`.
- third-probe rejected envelope: 4,004 bytes, SHA-256
  `58d6e6e6956d63e4c481622174f4a7a1c1a218c670eccb7b01789b1aa8242694`;
  rejected final: 387 bytes, SHA-256
  `edb1917fe549227e9f2494c7e5ddeaf92276c815eb5bbeff858a56d5ec373f0f`;
  thinking: 3,180 bytes, SHA-256
  `b545794c05ac2fac900c49fdebfa3f313db81efc6f016eb2633c611518d6157b`.
- third-probe runtime: provider pre/post checks passed and independent
  `wsl ollama ps` showed `gemma4:31b`, context `65536`, and `100% GPU`.
  No raw thinking, final content, envelope, Pydantic context, or traceback was
  printed or persisted.
- model-free invariant refinement: provider revision
  `rei-racio-gemma4-epistemic-g2-chat-v4` maps only exact built-in `ValueError`
  instances with one exact static validator message to a closed invariant code.
  All other context shapes remain `unclassified`; raw context/messages are
  neither copied nor hashed. Focused G1+G2 tests pass `84/84`.
- fourth technical probe: exactly one v4 confirmation `/api/chat` call passed
  the frozen preflight hashes from the third probe. The v4 call-spec SHA-256 was
  `75413d2e2a2b447ebf7a5c9f004e3b052f576c7df9f1d8152b59bcdbb0f7c904`.
- fourth-probe result: one root `value_error` was classified as
  `ambiguity_state_mismatch`; diagnostic SHA-256
  `0038d951c6fbd56e538ad6256d1f85b11f55890b6dcfc0c436610be22734c9cb`.
  The final response was byte-identical to the third probe: 387 bytes and
  SHA-256
  `edb1917fe549227e9f2494c7e5ddeaf92276c815eb5bbeff858a56d5ec373f0f`.
- fourth-probe rejected envelope: 3,723 bytes, SHA-256
  `46d1411cce835765073d8606b7e90a834c48b2d16d487d4922bf9b8568a88dba`;
  thinking: 2,912 bytes, SHA-256
  `1256e59c960a3093f2b749a4c1e7c96d5e5a77c05d2881615e1d61efaca3fa85`.
  The private thinking differed, but the validated final-response bytes did
  not; runtime/context/full-GPU checks again passed with one dispatch and no
  retry or fallback.
- diagnosis: the v2 validator requires `unresolved_ambiguity` to follow a
  mechanical four-way mapping from `inferred_option_id` nullability and whether
  `motive_hypotheses` contains more than one item. The v4 instruction and JSON
  schema enumerated allowed ambiguity strings but did not expose that mapping.
  The stable mismatch is therefore a model-facing instruction/contract gap,
  not an empty response, endpoint, GPU, JSON syntax, or field-type failure.
- model-free correction: provider revision
  `rei-racio-gemma4-epistemic-g2-chat-v5` exposes the existing four-way mapping
  verbatim in the instruction and the `unresolved_ambiguity` schema description.
  It does not relax or alter the v2 validator. Focused G1+G2 tests remain
  `84/84`.
- fifth technical probe: the isolated v5 correction experiment froze packet,
  model, seed, sampling, context, and GPU settings. Its new hashes were:
  instruction
  `3e4716e0a8d9d2a86eeaacf41a2632a3fceae6f1d06f419eccdeb2d48e20bef3`,
  schema
  `16c2d8298b732fedd39764e169815c4f29bb6d85a0196720e9743dba4c40fc98`,
  messages
  `f22cfc0994dc6d21d07012384d160369a3e820c757fa4246f6af2d5757ac381f`,
  request
  `21c17a4e23b117a5407e8b2c4a6c1e027d4255ddfdbfbf682013503a1bae730f`,
  and call spec
  `a08a9a58580dbffc44b7d9c23dc7368135e1b8eb6ef19a1693e3f610729db11a`.
- fifth-probe result: the explicit mapping did not alter the final response. It
  remained 387 bytes with SHA-256
  `edb1917fe549227e9f2494c7e5ddeaf92276c815eb5bbeff858a56d5ec373f0f`
  and failed with the same `ambiguity_state_mismatch` and diagnostic SHA-256
  `0038d951c6fbd56e538ad6256d1f85b11f55890b6dcfc0c436610be22734c9cb`.
  The rejected envelope was 3,267 bytes, SHA-256
  `bd58b590fe7f1249dcc84ba3ec3a8f82e409d848ce702c0e3b8c8c4dbefb4a6e`;
  thinking was 2,463 bytes, SHA-256
  `85b2a9a25e7cea43886188b2fa4567154382e586fbd9812b9a2db7cfe8a5e22c`.
- sixth technical probe: because the fifth probe preserved the exact final
  hash, one at-most-one observer repeated the frozen v5 request. Packet,
  instruction, schema, messages, request, and call-spec hashes matched the
  fifth probe; exactly one `/api/chat` dispatch occurred with zero retries and
  zero fallbacks. The observer derived only closed state categories in memory
  before normal provider validation. It did not print or persist the raw
  envelope, thinking, final JSON, decoded JSON, or traceback.
- sixth-probe safe state: final hash and size again matched exactly;
  `option_state=selected`, `motive_count=0`,
  `motive_bucket=zero_or_one`, `observed_ambiguity=option`, and
  `expected_ambiguity=none`. This is the concrete contradiction behind the
  root invariant. The rejected envelope was 4,361 bytes, SHA-256
  `0ff65d8c0fab38899ad3ad4afa6560d40d8c9f8c1e60ac34b1ddfab5a9301ee8`;
  thinking was 3,503 bytes, SHA-256
  `baad5f8285b9cdf1f1d7801d3321dd96597da82da8eb30929aa4d540d1d022ed`.
- final G2 diagnosis: on this frozen diagnostic packet, the repeated Gemma
  response contained individually schema-valid fields but an internally
  contradictory redundant derived field. Prompt and schema descriptions alone
  did not correct it. For these probes, the provider and Pydantic validator
  behaved correctly by failing closed; the observed failure was not caused by
  an empty response, endpoint, thinking separation, JSON syntax, digest,
  context, or GPU placement.
- no successful response evidence or `ProviderCallRecord` was created; the
  one-attempt count is established by the bounded probe dispatch and external
  runtime observation.
- calls/retries/fallbacks: `6 / 0 / 0`
- development screen: not started; Gemma development calls: `0/16`
- authority: this is a technical failure observation, not a semantic model
  rejection or acceptance
- next allowed step: stop for a design decision. The minimal recommended fix is
  to remove the mechanically derived `unresolved_ambiguity` field from the
  model-facing draft and compute it deterministically from the selected option
  and validated motive count as provider-derived state before constructing the
  unchanged v2 output.
  Do not make another model call or auto-continue into G3 without approval.

## G2 model-free REI boundary correction — 2026-07-17

- theory review: the preceding recommendation was not accepted literally.
  Deriving an ambiguity claim from option nullability and motive count would
  hide the exact contradiction exposed by probes 3–6 and would treat output
  shape as objective semantic evidence. The user authorized the narrower
  REI-compatible contract correction only.
- provider revision: `rei-racio-gemma4-epistemic-g2-chat-v6`; no Ollama or
  other model call occurred while producing this revision.
- Racio-owned semantics: `racio_reported_uncertainty` is a required structure
  with separate option-mapping and motive-interpretation states: `uncertain`,
  `not_uncertain`, or `not_reported`. The last state preserves an absent Racio
  self-assessment without turning it into a missing transport field. The
  structure has no default and no validator coupling it to option ID, motive
  count, or confidence. A selected option plus `uncertain` and a null option
  plus `not_uncertain` or `not_reported` all remain representable.
- provider-owned structure: response evidence v2 adds a content-addressed
  `provider_derived` sidecar containing only `option_id_present` and
  `motive_hypothesis_count`. Its derived values explicitly exclude packet,
  thinking, evaluator gold, and Racio-reported uncertainty. Its lineage hash
  intentionally covers the complete validated Racio output, including that
  report. The sidecar is marked as neither semantic evidence nor governance
  input and is bound to the exact output hash and policy hash. Response
  evidence embeds that sanitized typed output so cold validation can recompute
  both derived values; content addressing alone is not treated as derivation
  proof.
- evaluator boundary: the semantic case evaluator never receives the sidecar.
  The bilingual diagnostic compares only the two model-owned uncertainty
  structures. Option determinacy and motive support remain evaluator-owned.
  Per-case semantic calibration of the self-report is deliberately deferred;
  it neither changes the current hard gate nor establishes model quality.
- fail-closed hardening: the provider now rejects duplicate JSON object keys at
  any nesting depth before Pydantic semantic validation and exposes only the
  static `duplicate_json_key` diagnostic. Legacy `unresolved_ambiguity` and
  model-sent provider projection fields remain forbidden extras and are never
  rewritten or silently removed.
- fixed Slovene contract text now attributes non-inference and hypotheses to
  Racio rather than claiming that observations objectively determine or
  support a motive.
- model-free focused verification: `109/109` tests passed across the v2 contract,
  evaluator, provider, provenance sidecar, all eight option-presence × motive-
  count shapes, tri-state omission, complete-JSON duplicate guards, cold
  projection replay, and packet/provider/model lineage tamper checks.
- broader model-free evaluation regression: `381/381` tests passed with a
  repository-local pytest basetemp. The run excluded only C3 official
  source-gate tests, which intentionally require their frozen clean-main
  context, and `test_c4_stage1_*`, whose unmerged C4 modules are absent from
  this feature worktree. The C3 holdout-protocol suite was included. An earlier
  unfiltered attempt had only those collection/source-gate and system-temp
  constraints and is not used as acceptance evidence.
- historical probe hashes and the earlier `ambiguity_state_mismatch` diagnosis
  remain unchanged as evidence of the superseded v2 draft's technical failure.
- calls/retries/fallbacks remain `6 / 0 / 0`; development screen remains not
  started and Gemma development calls remain `0/16`.
- authority: this correction is still an `implementation_hypothesis`, not
  semantic acceptance, model-capability evidence, or authorization to proceed.
- next allowed step: human review of the v6 contract and model-free evidence.
  A new Gemma confirmation call or G3 dispatch requires a new explicit user
  authorization; no phase auto-continues.

## G2 v6 confirmation and 16k profile correction - 2026-07-17

- user contract decision: Racio's `uncertain`, `not_uncertain`, and
  `not_reported` states retain the approved self-report meanings. They remain
  independent of option, confidence, motive, sidecar, and evaluator fields.
  The provider-derived sidecar remains structural-only and has no semantic,
  governance, `ConsciousDecision`, or `BehaviorResultant` authority. The first
  G3 screen will record and compare the self-report descriptively but will not
  score its per-case calibration as a hard gate.
- seventh technical probe: exactly one authorized v6 `/api/chat` call used the
  frozen packet and `num_predict=2048`. The packet, provider-payload,
  instruction, schema, messages, request, and call-spec SHA-256 values were,
  respectively,
  `1ec04b21901b29318f2825e4742d8f7e59fe1556a9286d2d99699ee8ab2e70c0`,
  `8c459e0f8c4a005a589b8a722e8fa8c4df509cd7fc6b0589be1e26f46311a0ad`,
  `4137891d92dec4b90875ee755f7ca5d67fc9d93e733180a85803a6b891840b91`,
  `16602d51fb48f6b64b415ea22693bae16ebf67a97a9ca52703cdd58ca4cae49e`,
  `be4f17f8835c5ac8e7f39b8e4431cd3125622aa16c6c270bab22b572f7dd9e8a`,
  `16490104645212f2a773f15101de3dc5d1699b7dee50a5b0ad8f0ac3fd65cbbe`,
  and
  `6e9da81d9b858f1dc6a54008eda2602cc78cec515d2298a115039f4ed3744879`.
- seventh-probe result: one dispatch, zero retries, and zero fallbacks failed
  as `generation_contract_failure` before JSON/Pydantic validation. The
  rejected envelope was 8,196 bytes with SHA-256
  `9da83c33afcbf4e6f1d24fb5d6512d04675b250e67e9a9984ea0f4c15d39443c`;
  separate private thinking was 7,732 bytes with SHA-256
  `a6b05df7e3595662fffdbcc0f9785d1fbcc47773c25204a2d30ce1a064247491`.
  No final-response fingerprint, successful response evidence, or
  `ProviderCallRecord` was created. No raw response or thinking content was
  printed or persisted.
- user-authorized profile correction: commit
  `0f931151d50f7e06ec1db45ba9a00a35895a35f9` changed only the pinned
  `num_predict` value from `2048` to `16384`. Provider revision remains
  `rei-racio-gemma4-epistemic-g2-chat-v6`; the exact profile difference is
  frozen in request and call-spec provenance. Focused model-free verification
  passed `109/109` tests before the next dispatch.
- eighth technical probe: exactly one newly authorized `/api/chat` call kept
  the same packet, provider payload, instruction, schema, messages, model
  digest, seed, temperature, top-p, top-k, context, GPU setting, endpoint, and
  no-fallback policy. Only `num_predict=16384` changed the request SHA-256 to
  `0b6581dab147d4df96f0a6c9c694af077f225b89407157f5e1a2303ff76045e3`
  and the call-spec SHA-256 to
  `b1d7c134aaf066c7d6d38c529051fd67fc9f9608557ec9b3b2fa76a02c4b2541`.
  Call ID was `provider_call_2148b1f337222420f537b0dcf1b8422b`.
- eighth-probe result: `done_reason=stop`; strict JSON/Pydantic and conscious-
  access validation passed. The structured output SHA-256 was
  `9cf1527b6289b3a1aa955d39c5897f42a8309d2f16debcaa9267507492ea5df5`.
  It cited `observation_001`, returned action `set_boundary` at confidence
  `1.0`, selected `option_001` at confidence `1.0`, returned no motive
  hypothesis with the required unknown reason, and self-reported option
  mapping as `not_uncertain` and motive interpretation as `not_reported`.
  These values are recorded technical output, not semantic acceptance or a
  calibration judgment.
- successful response evidence ID:
  `gemma4_epistemic_response_b66ec431c6dcae651f18da3c046f3864`; evidence
  content SHA-256:
  `31d9ab053328c645c01009373f4b532e605b92a1507ddf2051686412bdf6e108`.
  The envelope was 4,957 bytes with SHA-256
  `c92456feec6ebc6e546d9c2d40ecf8afa00fc47e897f81f83a2a142e3fe0605f`;
  the validated final was 461 bytes with SHA-256
  `5dfba140a0e7ee88777f006182e8b6d334a5fcd3457b3857b252e8b3f383fae4`.
  Private thinking content was not persisted; its permitted fingerprint is
  4,030 bytes and SHA-256
  `c120e25a42804b3e8ff9f1ae3a72e09d006b86ed514e8cdce94a5c3c6dc7899b`.
- the provider-derived sidecar recorded only `option_id_present=true` and
  `motive_hypothesis_count=0`, with `semantic_evidence=false` and
  `governance_effect=false`. Runtime evidence recorded exact digest
  `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`,
  context `65536`, `num_gpu=999`, and byte-exact `100% GPU` placement.
- the successful `ProviderCallRecord` content SHA-256 is
  `01390e5f50a7b1978af6ee52ec2622e8465d822cd8a3c49f423fe029a4f38af6`;
  it records one direct successful primary call, no fallback, seed `314159`,
  and output artifact
  `gemma4_epistemic_response_b66ec431c6dcae651f18da3c046f3864`.
- cumulative technical calls/retries/fallbacks: `8 / 0 / 0`. The two calls in
  this section were separately user-authorized call specs, not provider
  retries. The G3 development screen remains unstarted at `0/16`.
- authority: the eighth probe is technical confirmation that the v6 provider
  can close its structured contract with the 16k profile. It is not semantic
  model promotion, objective correctness evidence, uncertainty-calibration
  acceptance, or permission to begin G3.
- next allowed step: stop for human review. G3 requires a separate explicit
  phase decision.

## G3 Gemma 4 Racio epistemic development screen - 2026-07-17

- user authorization: execute the bounded G3 screen on exactly eight
  precommitted roots in Slovenian and English, for 16 Gemma calls total. The
  provider revision, instruction, output schema, motive taxonomy, model and
  digest, seed, sampling, context, GPU settings, and evaluator were frozen.
  Retry was zero and fallback was none. No aggregate semantic pass/fail was
  authorized.
- pre-call seal: the naturalized corpus, hidden gold, manifest, one-shot
  runner, and model-free tests were committed at
  `d9027d97faec36f1d2c806a5efe5e935ed931014`. The manifest SHA-256 is
  `07172858ac94a5e78dc4bf2d49e14030f5ad85021e62c120265e356063f9a6de`.
  Before sealing and before any G3 model call, independent review removed an
  accidentally added somatic phrase from both R1 surfaces because it would
  have introduced motive support inconsistent with the precommitted
  `not_identifiable` gold. No prompt or corpus change occurred after model
  results were available.
- model-free preflight: the sealed suite loaded as 16 cases and eight SL/EN
  pairs with zero model calls. The focused provider, evaluator, and runner
  suite passed `119/119`; an additional independent runner audit passed all 10
  one-shot artifact tests. All 16 call specs were frozen before the first chat
  dispatch.
- frozen runtime: provider revision
  `rei-racio-gemma4-epistemic-g2-chat-v6`; model `gemma4:31b`; exact digest
  `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`;
  seed `314159`; temperature `0`; top-p `0.95`; top-k `64`;
  `num_ctx=65536`; `num_gpu=999`; `num_predict=16384`; endpoint `/api/chat`;
  thinking enabled and private; raw and stream disabled. Runtime response
  evidence recorded context `65536` and `100% GPU` placement.
- execution result: exactly 16 `/api/chat` dispatches completed in the sealed
  order. All 16 produced strict JSON/Pydantic-valid outputs, response evidence,
  and successful `ProviderCallRecord` artifacts. G3 calls/retries/fallbacks
  were `16 / 0 / 0`; provider successes/failures were `16 / 0`.
- evidence: 204 generated files were copied byte-for-byte into
  `Docs/evals/semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/`.
  Cold validation replayed all 16 provider execution lineages, all 16 case
  evaluations, and all eight bilingual evaluations. No private thinking text
  or raw response envelope was persisted. The complete ten-section human
  report is `gemma4_racio_epistemic_dev_screen.md`.
- structural contract: all four structural dimensions were true in `16/16`
  cases. This is structural evidence only.
- action interpretation: supported `8/16`; unsupported `8/16`; action citation
  support `16/16`.
- option mapping and abstention: all 12 unique cases mapped correctly and all
  four underdetermined cases abstained as required; option citation support was
  `16/16`; option mapping was bilingual-consistent in `8/8` pairs.
- motives: support states were supported `4`, hierarchy-compatible `1`,
  partially supported `9`, unknown preserved `1`, and unsupported `1`.
  Coverage was `1.0` in 15 cases and `0.0` only in R1 EN. Citation failure
  count was zero in all cases, but the evaluator counted 15 unsupported motive
  hypotheses across 10 cases.
- confidence: action and option values were within evaluator bounds in
  `16/16`; motive values were within bounds in `15/16`. R1 EN emitted two
  unsupported motives above its zero-confidence motive bound.
- Racio self-report: all 16 structures were valid; no value was mechanically
  repaired or used as a hard gate. Option self-report was `not_uncertain` for
  all 12 unique cases and `uncertain` for all four underdetermined cases.
  Motive self-report was `uncertain` in seven and `not_uncertain` in nine.
  Bilingual self-report consistency was `7/8`, with only R5 differing.
- bilingual dimensions: source mind and option were consistent in `8/8`;
  action `3/8`; motive family `7/8`; motive subtype `4/8`; citations `7/8`;
  Racio uncertainty `7/8`. Pair consistency is not correctness; H15 was
  action-consistent because both outputs shared the same unsupported action.
- individual findings: 14 cases carried one or more evaluator research
  observations; only H11 SL and R5 EN carried none. There were no provider
  failures. The compact generated `summary.json` exposes only provider failure
  code counts under its `individual_failures` key, so the canonical report and
  per-case artifacts are the sources for semantic individual findings.
- cumulative technical calls/retries/fallbacks: `24 / 0 / 0`. G3 development
  calls are complete at `16/16`.
- authority: no aggregate semantic result was computed. Gemma is not promoted,
  runtime integration is not started, and no further phase or model call is
  authorized. Stop for human review.

## G3C human decision - 2026-07-18

- reviewed result: the human accepted the frozen G3C development rerun at
  commit `37940f815bff1b98bbee9d989d0ccb89c8ec8c6c`; the canonical report is
  `gemma4_racio_epistemic_v3_g3c.md`.
- technical decision: the V3 technical contract and Gemma V3 provider
  implementation are accepted. Provider revision
  `rei-racio-gemma4-epistemic-v3-chat-v1` remains frozen.
- semantic decision: the development result is promising, but it is not an
  untouched holdout and grants no generalization claim.
- integration boundary: Gemma is allowed only as an inactive-by-default text
  shadow. It is not promoted and has no governance, runtime-decision,
  conscious-decision, behavior, or MindWorld authority.
- frozen boundary: the V3 contract, provider revision, instruction, DraftV3
  schema, canonicalizer, evaluator, G3C corpus, and G3C results must not change.
- research boundary: there is no G3D. G4 untouched holdout remains required on
  a separate feature branch before any promotion decision.
- next allowed step: M-G3C PR preparation only. This phase permits no model
  call, G4 execution, shadow integration, or provider/prompt tuning.

## S1R-R accepted - 2026-07-19

- human decision: S1 backend text-shadow architecture and the reconciled S1R
  technical smoke are accepted as ready for integration.
- execution head: `82b219c17eb62a1afbc807159da05244923998dd`;
  verification head: `e5bbaf3d8da29f2e5474bc49e6f9931bc7c55a34`;
  accepted S1R-R final branch head:
  `0d4e2d127bd435b0fb3d7e91774330af2e8e1b45`.
- external receipt: ID
  `s1r_verify_receipt_f589ffd26f095f610ff27688f727b1d0`; SHA-256
  `f8338d63a1cc12a1e133ff289630acde13c3fbebdb1dd97069e827519366f843`.
- call accounting remained exactly `2/0/0` calls/retries/fallbacks; receipt
  reconciliation made zero provider or model calls.
- E produced valid full abstention; I produced a bounded action-only
  interpretation. DraftV3 and canonicalizer validity were `2/2`.
- authoritative invariance: the deterministic interpretation and
  authoritative governance, conscious-decision, behavior, MindWorld-input,
  and Ego-composition paths remained unchanged.
- authority boundary: Gemma remains explicit-opt-in, shadow-only, and has no
  governance, conscious-decision, behavior, MindWorld, or Ego-composition
  authority.
- promotion boundary: Gemma is not promoted, and S1R is not an untouched
  holdout or a generalization claim.
- integration decision: the backend is ready for M-S1 integration preparation
  and draft-PR review. S2 and G4 require separate future feature branches and
  their own review gates.

## Active runtime language decision - 2026-07-20

- human decision: every active local-model instruction, prompt, query, packet,
  and structured response boundary must operate in English.
- preserved Slovene scope: original source documents, project goals and plans,
  and exact frozen historical research evidence remain unchanged. They are not
  active model inputs merely because they are present in the repository.
- dispatch behavior: model-backed text and image boundaries require explicit
  `language=en` metadata. Undeclared or explicitly non-English requests fail
  before provider dispatch, with no automatic translation, retry, or fallback.
  The structural gate deliberately does not infer a language from vocabulary;
  trusted active producers carry the obligation to supply English prose.
- response behavior: active provider instructions require English output. The
  gate validates the declared contract and bounded schema, not prose through a
  heuristic language detector; any free-text language quality remains subject
  to explicit evidence review before a later promotion decision.
- Gemma runtime projection: active text shadow uses an English-primary packet,
  English bounded abstention reasons, and provider revision
  `rei-racio-gemma4-epistemic-v3-en-chat-v1`. The frozen historical V3 provider
  revision and S1/S1R/G3C evidence remain byte-stable.
- presentation behavior: active GUI chrome is English. Verbatim Slovene source
  material and historical model evidence remain visible only under explicit
  source/history labels.
- research status: this implementation made zero model calls, grants no
  semantic acceptance, no promotion, and no authority. A later model smoke or
  holdout requires a separately approved phase.
