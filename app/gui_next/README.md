# REI Native Composition Workbench

`app/gui_next/` is the B12 inspection surface for the native REI architecture.
It is intentionally separate from the legacy prompt and dataset GUI until the
B13 cutover.

The workbench exposes four layers:

- **Native** — Racio facts and utility, Emocio visual scenes/image slots, and
  Instinkt body trajectories.
- **Communication** — Emocio/Instinkt manifestations and Racio's
  interpretations. Native comparison truth appears only behind the explicitly
  labelled evaluator-debug switch.
- **Character** — structural and effective authority, processor availability,
  governance, conscious decision, and behavior resultant.
- **Ego** — measure, trace timeline, composition snapshot, Racio
  self-narrative, spoznanja, and three modality-specific projections.

## Run locally

From the repository root:

```powershell
app\backend\.venv\Scripts\python.exe -m uvicorn app.gui_next.server:app --host 127.0.0.1 --port 8766
```

Then open `http://127.0.0.1:8766`.

The default action runs the checked-in deterministic B11 fixture. It does not
contact Ollama, load a model, render an image, use the GPU, or create training
data. Every run uses create-only artifact storage.

Override the local stores when needed:

```powershell
$env:REI_GUI_NEXT_RUNS_ROOT = "tmp/gui-next/runs"
$env:REI_GUI_NEXT_EGO_TRACES_ROOT = "tmp/gui-next/ego-traces"
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
- `POST /api/cycles?debug=false` accepts an exact
  `ReiNativeCycleRequest` and runs only the deterministic provider set.
- `GET /api/runs/{run_id}/images/{image_id}` serves only a manifest-verified
  PNG artifact.

No dataset, training, prompt-override, Ollama, or free-form filesystem route is
part of this application.

## Verified dependency baseline

The B12 implementation was checked on 2026-07-13 against the then-current
stable releases: FastAPI 0.139.0, Uvicorn 0.51.0, Pydantic 2.13.4, PyYAML
6.0.3, and Playwright CLI 0.1.17. The UI itself is dependency-free static
HTML, CSS, and JavaScript.
