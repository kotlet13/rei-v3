# C3 Racio interpreter remediation protocol — 2026-07-15

## Disposition

**PROTOCOL FROZEN FOR PRE-RUN REVIEW; MODEL QUALITY REMAINS BLOCKED.**

This protocol adds an untouched v2 holdout contract, sanitized failure
evidence and one explicitly pinned candidate. It does not run a model, select a
default interpreter or change the historical C3 acceptance disposition. The
commit containing this document is the protocol-freeze commit; its full SHA is
recorded in the subsequently sealed holdout manifest so the corpus cannot
claim authority from later prompt or schema changes.

At this checkpoint the official runner still rejects v2 because only the
historical v1 manifest hash is registered. That is intentional fail-closed
staging, not a runnable holdout. The immediately following seal/pin commit must
register the exact generated v2 hash and enforce every protocol pin before the
first model call.

All work and subsequent evidence commits are performed directly on `main`.
Unrelated working-tree files remain outside the phase commit.

## Candidate pin

The only newly opened structured-text candidate is:

| Field | Frozen value |
|---|---|
| Model | `qwen3.6:35b` |
| Ollama digest | `07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522` |
| Registry status | `c3_candidate` |
| Modalities | `structured_text`, `vision` |
| License | Apache-2.0 |
| Context ceiling | 262,144 tokens |
| Conservative benchmark VRAM envelope | 32 GiB; not a vendor minimum |
| Production/default selection | none |

Primary-source research:

- [Qwen3.6-35B-A3B model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)
  documents the open-weight 35B-total/3B-active MoE, visual input support,
  262,144-token context and Apache-2.0 license.
- [Official Ollama qwen3.6 tags](https://registry.ollama.com/library/qwen3.6/tags)
  identify the `qwen3.6:35b` text-and-image artifact and its exact digest.

Registry presence is only permission for an explicit benchmark call. There is
no implicit model load and no production selection.

## Frozen provider protocol

| Contract | Value |
|---|---|
| Provider revision | `rei-ollama-racio-interpreter-c3-v6` |
| Instruction SHA-256 | `c5ea5a0936bbab5e9bb481e53443eb9119cb5bf2c1d58737f3bb0214ebcfb1b0` |
| Output-schema SHA-256 | `7b51eeadc1e13223016a1ab95aab88b9141ed7d11a5400bd05cf25988645bd1c` |
| Calibration policy | `c3-conscious-access-calibration-v1` |
| Seed | `314159` |
| Temperature | `0.0` |
| Context | `65536` |
| GPU offload | `num_gpu=999`; full GPU required |
| Prediction ceiling | `num_predict=1536` |
| Timeout | `600.0` seconds |
| Keep-alive | `10m` |
| Endpoint | `http://127.0.0.1:11434/api/generate` |
| Remote endpoint | forbidden; `allow_remote=false` |
| Response bound | 4 MiB Ollama JSON envelope |
| Retry/fallback | none |
| Provider case attempts | 32 per suite; `/api/generate` dispatches are counted separately |

The provider still receives only the public conscious-access packet and strict
JSON schema. Native truth, Character/profile data, evaluator labels and holdout
lineage remain outside the request. The v6 change categorizes rejected attempts
and fingerprints the complete canonical rejected-response envelope without
retaining its contents. New runs use
`rei-c3-racio-interpreter-run-provenance-v2`; historical v1 provenance files
remain byte-identical.

## Untouched holdout contract

The deterministic serializer defines 32 manually authored cases:

```text
8 source-grounded semantic families ×
  (SL/EN unambiguous pair + SL/EN ambiguous pair)
```

Required distribution:

- 16 Emocio and 16 Instinkt cases;
- 16 Slovene and 16 English cases;
- 16 unambiguous and 16 ambiguous cases;
- 16 accepting, 8 mixed and 8 conflicted cases;
- 16 bilingual pairs;
- five source-grounded non-unknown action classes;
- four source-grounded non-unknown motive classes;
- unambiguous correct-option positions balanced 8/8.

The holdout uses eight families absent from the v1 regression corpus. Public
cases and evaluator gold are physically separate and hash-pinned. Gold is
manually authored, never model generated and never exported for training. The
serializer is create-only and writes canonical UTF-8/LF bytes.

`seek_attachment`/`attachment` remain intentionally regression-only because the
only source-grounded family for them is already in C3-v1. Their coverage is
therefore required from the second, frozen regression run rather than obtained
by leaking a regression family into the untouched holdout.

The v2 model gate requires every one of the 32 cases to pass. This is stricter
than the historical v1 gate and is an operational implementation hypothesis,
not an empirical psychology claim.

## Required execution order

1. Commit and push this protocol without a candidate run.
2. Generate the holdout from that full 40-hex protocol commit and the frozen
   instruction/schema hashes.
3. Review, commit and push the exact holdout bytes and official suite pin.
4. Make no provider, prompt, schema, calibration or corpus changes.
5. Run the untouched holdout first.
6. Run the frozen v1 regression suite second with the identical candidate and
   call settings.
7. Preserve both outcomes, including failures; do not tune and rerun against
   the same holdout.

The seal/pin commit must make the runner fail closed unless the holdout's
protocol commit is an ancestor of the execution commit and its
instruction/schema/calibration pins equal the actual provider call contract.
It must also enforce the complete local call profile above and the
holdout-before-regression order. Both suite manifest hashes must be official
pins, not operator-supplied exceptions.

## Acceptance boundary

C3 model quality may be unblocked only if:

- the v2 holdout reports `quality_gate_pass=true` and `passed_case_count=32`;
- the untouched holdout has 32/32 valid structured outputs, 16/16 ambiguity
  gates, 16/16 bilingual consistency and zero leakage/mutation/provenance
  failures;
- the frozen v1 regression suite independently reports
  `quality_gate_pass=true` under the same provider configuration;
- every rejected attempt has exactly one sanitized, content-addressed failure
  record and no retry or fallback;
- full GPU placement is evidenced with `num_ctx=65536`, `num_gpu=999`, the
  exact active digest and `size_vram == size`.

A passing experimental candidate still does not become a default or production
model. VLM, C4 visual, semantic-motif, uniform telemetry and C7-v2 gates remain
separate work.

## Validation before protocol commit

The protocol commit requires model-free unit/regression tests, compile checks,
the unchanged v1 manifest hash and clean scoped sources. No Ollama generation
is part of this checkpoint.
