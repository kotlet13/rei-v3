# REI Native Composition Workbench

`app/gui/` is the active inspection surface for the native REI architecture.
The legacy textual prompt/dataset GUI is preserved only in the immutable A1
archive snapshot.

The workbench exposes six inspection views:

- **Semantic Lab** — the read-only C1/C2 source-grounded catalogue, expected
  and actual routes, reviewer state, failure tags, and Slovenian/English text.
- **Racio** — the exact manifestations and communication requests available to
  Racio. Native comparison truth appears only behind the explicitly labelled
  evaluator-debug switch, together with `TranslationGap` records.
- **Emocio** — structured scene specifications, image slots, visual
  observations and similarity valuation when those stages actually ran, plus
  renderer-added ungrounded elements.
- **Instinkt** — body state, cue evidence, predicted or explicitly manual body
  effects, association matches, rollout trajectories, alarm and uncertainty.
- **Character** — structural and effective authority, processor availability,
  governance, conscious decision, and behavior resultant. It is an inspection
  view, not a diagnostic surface.
- **Ego** — append-only measures and corrections, decisions, outcomes,
  translation gaps, recurring motifs, unresolved tensions, spoznanja, Racio
  self-narrative, and three modality-specific projections.

The C7 benchmark statuses remain separate: the model-free technical contract
gate is not presented as evidence that the research-quality gate passed.

## Run locally

From the repository root:

```powershell
app\backend\.venv\Scripts\python.exe -m uvicorn app.gui.server:app --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765`.

The default action runs the checked-in deterministic fixture. It does not
contact Ollama, load a model, render an image, use the GPU, or create training
data. Every run uses create-only artifact storage.

Override the local stores when needed:

```powershell
$env:REI_GUI_RUNS_ROOT = "output/gui/runs"
$env:REI_GUI_EGO_TRACES_ROOT = "output/gui/ego-traces"
```

## Image behavior

Every `VisualSceneSpec` gets a visible image well. If rendering was disabled,
the well says so and keeps the structured scene authoritative. A raster image
is served only when its exact PNG path is present in a cold-verified V2 run
manifest and its bytes match the recorded SHA-256 metadata. The GUI never
invents a placeholder image or loads a remote image.

## HTTP surface

- `GET /api/bootstrap` returns the frozen fixture, the 13 canonical character
  contracts, and runtime capability flags without executing the engine.
- `GET /api/semantic-lab` verifies and projects the checked-in C1, C2, and C7
  evidence without modifying or re-running it.
- `POST /api/cycles?debug=false` accepts an exact
  `ReiNativeCycleRequest` up to 1 MiB and runs only the deterministic provider
  set.
- `GET /api/ego-runs/{partition_id}/{run_id}/images/{image_id}` serves only a
  manifest-verified PNG artifact from that hashed Ego run partition.

No dataset, training/export, prompt-override, Ollama, model, image-generation,
Character-diagnosis, or free-form filesystem route is part of this
application. Missing model-backed or visual stages are rendered as explicit
`not executed` states; the GUI does not silently substitute a fallback result.

The complete HTTP surface is loopback-only by default. A remote deployment
must explicitly set `REI_GUI_ALLOW_REMOTE=true`. Evaluator ground truth
requested with `debug=true` remains separately protected and remote access to
it requires both `REI_GUI_ALLOW_REMOTE=true` and
`REI_GUI_ALLOW_REMOTE_DEBUG=true`. The warning
`Racio ground trutha ni prejel.` remains visible because debug truth is an
evaluator comparison, never an interpreter input.

Remote opt-in is an unauthenticated, trusted-single-user mode. `ego_id` is a
namespace, not an authorization token or secret: a remote caller that knows an
ID can read and append that Ego timeline. Do not expose this mode to an
untrusted network. A deployment outside one trusted-user boundary must add
authentication and authorization at a correctly configured reverse proxy; it
is not supported by the workbench itself.

Longitudinal GUI sessions are deliberately bounded to 30 measures. Run
artifacts are partitioned by a SHA-256 namespace derived from `ego_id`.
Restart recovery enumerates at most 64 entries in that Ego partition, uses
bounded candidate reads, and fully verifies only matching run manifests.
Native bundles are limited to 2 MiB before persistence, so every accepted
bundle remains readable by recovery. This is a local inspection/recovery
policy, not an unbounded multi-user history service.

## Verified dependency baseline

The workbench was checked on 2026-07-13 against the then-current
stable releases: FastAPI 0.139.0, Uvicorn 0.51.0, Pydantic 2.13.4, and
Playwright CLI 0.1.17. The UI itself is dependency-free static
HTML, CSS, and JavaScript.
