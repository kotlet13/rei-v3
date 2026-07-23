# C4 Stage 1 review-runtime bootstrap protocol — 2026-07-15

Status: model-free bootstrap protocol. This document and its focused tests do
not install packages, download Chromium, launch a browser, or call a model.

## Frozen runtime

The Windows review runtime is self-contained beneath one fresh external root.
The bootstrap makes an ordinary-file copy of the complete CPython 3.11 AMD64
base distribution as `base-python/`, excluding mutable `__pycache__`, `.pyc`,
and `.pyo` material. It then creates `venv/` with `venv --copies` from that
copied base. The live interpreter is `venv/Scripts/python.exe`, and its
`sys.base_prefix` must resolve to the copied `base-python/`; it must not execute
stdlib or DLL files from the original interpreter tree.

The runtime uses a separate absolute `PLAYWRIGHT_BROWSERS_PATH`. The complete
base-plus-venv runtime, browser cache, and provenance roots must all be fresh,
mutually non-overlapping, outside the repository and original Python base, and
outside every declared artifact, model, and review-state root.

The exact package set is:

| Package | Version | Windows wheel SHA-256 | Bytes |
| --- | ---: | --- | ---: |
| `playwright` | 1.61.0 | `35c6cc4589a5d00964a59d7b3e59641e0aac0c02f15479a7af77d20f6bc79597` | 37,844,846 |
| `greenlet` | 3.1.1 | `48ca08c771c268a768087b408658e216133aecd835c0ded47ce955381105ba39` | 298,930 |
| `pyee` | 13.0.0 | `48195a3cddb3b1515ce0695ed76036b5ccc2ef3a9f963ff9f77aec0139845498` | 15,730 |
| `typing-extensions` | 4.16.0 | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` | 45,571 |
| `pydantic` | 2.13.4 | `45a282cde31d808236fd7ea9d919b128653c8b38b393d1c4ab335c62924d9aba` | 472,262 |
| `pydantic-core` | 2.46.4 | `6f2eeda33a839975441c86a4119e1383c50b47faf0cbb5176985565c6bb02c33` | 2,071,114 |
| `annotated-types` | 0.7.0 | `1f02e8b43a8fbbc3f3e0d4f0f4bfc8131bcb4eebe8849b8e5c773f3a1c582a53` | 13,643 |
| `typing-inspection` | 0.4.2 | `4ed1cacbdc298c220f1bd249ed5287caa16f34d44ef4e9c3d0cbad5b521545e7` | 14,611 |

Playwright 1.61.0 declares `pyee>=13,<14` and `greenlet>=3.1.1,<4`; the
protocol chooses the published lower bounds. Pyee 13.0.0 requires
`typing-extensions` without a version range, so the protocol freezes the
current official PyPI release at the protocol cutoff, 4.16.0. Primary metadata:
[Playwright 1.61.0](https://pypi.org/pypi/playwright/1.61.0/json),
[greenlet 3.1.1](https://pypi.org/pypi/greenlet/3.1.1/json),
[pyee 13.0.0](https://pypi.org/pypi/pyee/13.0.0/json), and
[typing-extensions 4.16.0](https://pypi.org/pypi/typing-extensions/4.16.0/json).

The review service, presenter, and review CLI import Pydantic from this exact
external interpreter; relying on the repository's development environment is
forbidden. Pydantic 2.13.4 officially requires `pydantic-core==2.46.4`,
`annotated-types>=0.6.0`, `typing-extensions>=4.14.1`, and
`typing-inspection>=0.4.2`. The protocol freezes `annotated-types` 0.7.0 and
the lower-bound `typing-inspection` 0.4.2; the existing
`typing-extensions` 4.16.0 pin satisfies Pydantic, pydantic-core, and
typing-inspection. Primary metadata: [Pydantic 2.13.4](https://pypi.org/pypi/pydantic/2.13.4/json),
[pydantic-core 2.46.4](https://pypi.org/pypi/pydantic-core/2.46.4/json),
[annotated-types 0.7.0](https://pypi.org/pypi/annotated-types/0.7.0/json), and
[typing-inspection 0.4.2](https://pypi.org/pypi/typing-inspection/0.4.2/json).

The matching browser is Chromium revision `1228`, browser version
`149.0.7827.55`, from Playwright's official
[`browsers.json`](https://raw.githubusercontent.com/microsoft/playwright/v1.61.0/packages/playwright-core/browsers.json).
The Windows executable layout
`chromium-1228/chrome-win64/chrome.exe` follows the same release's official
[registry implementation](https://raw.githubusercontent.com/microsoft/playwright/v1.61.0/packages/playwright-core/src/server/registry/index.ts).

## Operation

`plan` validates the base interpreter and all path boundaries, then prints a
path-redacted plan. It creates no directories and uses no network. `execute`
is rejected without the additional `--execute` flag. Its bounded process-tree
steps are:

1. copy the complete bytecode-free standalone Python base;
2. create the copy-only virtual environment against that copied base and
   verify its actual `sys.prefix`, `sys.base_prefix`, and `pyvenv.cfg` binding;
3. download the eight direct PyPI wheel URLs into an external wheelhouse;
4. verify every wheel's exact filename, size, and SHA-256;
5. install only that wheelhouse with `--no-index --no-deps --require-hashes`;
6. verify installed package versions, exact dist-info identity files, and the
   installed `browsers.json` pin;
7. use the sealed interpreter to import every pinned third-party module plus
   the presenter, review-run, and review-service modules without launching a
   browser or model;
8. run the matching `python -m playwright install chromium` with the dedicated
   `PLAYWRIGHT_BROWSERS_PATH`;
9. capture stable, complete base-plus-venv and browser file/executable
   manifests; and
10. create the three-file external provenance directory.

Every child has a hard wall-clock and output bound. Links, reparse points,
hard-linked files, special files, path overlap, pre-existing output roots, and
post-capture mutation fail closed. Provenance stores path identities rather
than local paths and never stores raw commands, environment values, child
output, credentials, or model material.

`verify` is network-free. It requires the same explicit roots and base Python,
checks the create-only three-file provenance inventory, recalculates content
identities, and recaptures both complete trees and executable hashes. Each
tree carries a full SHA-256 aggregate over sorted canonical relative-path
records; local paths and mtimes are not aggregate inputs.

The shared stdlib-only API
`rei.evaluation.c4_stage1_review_environment.verify_presenter_runtime` accepts
the provenance, runtime, and browser roots plus a required `checkpoint()`
callback. It calls that callback around directory and file work and at every
4 MiB hash chunk, so the presenter can enforce one absolute deadline and
cancellation boundary before its operational probe and every display. It
returns a path-free summary containing the provenance ID/hash, both manifest
IDs/hashes and tree aggregates, counts/bytes/no-link/no-bytecode policies,
Python executable identities, installed distribution identities,
`browsers.json`, and Chromium executable identity. It launches no process and
sets `sys.dont_write_bytecode`.

## Durable review-service delivery boundary

The authenticated service uses `rei-c4-stage1-review-service-v2` and
`rei-c4-stage1-review-ledger-v2`; the wire protocol remains
`rei-c4-stage1-review-ipc-v1`. Service v2 adds a bounded, authenticated result
journal for exactly seven stateful operations:

- `display`;
- `take_presentation_submission`;
- `consume_display_attestation`;
- `consume_display_receipt`;
- `issue_operator_signing_lease`;
- `sign_operator_claim_cohort`; and
- `consume_operator_policy`.

For these operations, the server derives the stable request identity from a
domain separator and canonical JSON containing only the service epoch, IPC
schema, operation, body length, and body SHA-256. Transport nonce and time are
excluded. A completed row stores the exact canonical result bytes, digest,
size, effect kind and identity, completion time, and a service HMAC over the
full request/result binding. The authority effect and completed result are
committed in the same SQLite transaction.

`display` is reserved as authenticated `in_progress` immediately before the
presenter is invoked. Such a row is terminal: a lost or cancelled presentation
is never launched again under the same request identity. Submission delivery
uses presenter peek, atomic journal completion, and only then exact discard.
The two-review signing result preserves the original request order and is
recoverable byte-for-byte after restart; reversing the request is a different
request and is rejected after cohort seal.

The client permits one retry only for a transport failure or an absent,
truncated, or oversized response. The retry uses a fresh authenticated nonce
and timestamp but the identical canonical request body. Signed application
errors and complete malformed or unauthenticated responses are not retried.

Startup and health revalidate every row's request identity, canonical result,
HMAC, operation cardinality, and one-to-one authority effect. A pristine state
has zero result rows. A sealed two-review cohort has exactly eleven base rows,
plus zero, one, or two operator-policy delivery rows, for an absolute maximum
of thirteen. Missing, modified, orphaned, over-cardinality, or unexpected
`in_progress` state fails closed.

## Boundary with the human review

Bootstrap install verification proves the exact package inputs, Playwright
browser descriptor, installation marker, Chromium executable bytes, and full
runtime trees. It deliberately records:

- `browser_process_launch_performed=false`;
- `headed_full_ui_smoke_performed=false`; and
- `headed_full_ui_smoke_authority=authenticated-review-service-only`.

The later authenticated review service must independently reverify this
runtime and perform the real headed, offline, full-UI smoke/presentation. A
successful bootstrap alone grants neither semantic nor production authority.
