# Emocio VWM E1R protocol correction

E1R is a new commit layered on immutable E1 commit
`a1a8e0922a9fb1fd21893b46087cc0e9155146d9`. It corrects the protocol before
any LPWM call. It does not install LPWM, acquire a checkpoint, train a model,
run inference, or modify the active REI runtime.

## Epistemic scope

The REI canon says Emocio reasons with images, scenes, mosaics, embodied
expression, movement, attention, competition, attraction, and desired images.
The research interpretation is that a visual world model might implement part
of scene maintenance and multiple-future imagination. Three.js plus pinned
LPWM with latent-action/image-goal conditioning is only a replaceable
implementation hypothesis. E1 and E1R establish only controlled-medium and
boundary suitability; they do not establish LPWM model fit, desire, semantic
understanding, a working Emocio, REI theory validity, or runtime readiness.

The corrected evidence classes are:

- `observed_grounded`: source-event evidence; the only class with reality
  authority;
- `authored_counterfactual`: deterministic laboratory continuation used as
  authored research material, never as source-event fact;
- `authored_goal`: a non-authoritative target image;
- `imagined_completion`: a future LPWM sample, always non-authoritative.

Public and private immediate authored results remain pending. No response keeps
the current official attribution. An official self-attribution appears only in
an authored goal or an imagined completion.

Run E1R with:

```powershell
$env:REI_CHROMIUM_EXECUTABLE = "C:\path\to\pinned\chrome.exe"
python scripts/run_emocio_vwm_e1r.py --output output/emocio_vwm_mvp/e1r
```

The executable bytes must match `specs/renderer_pin.json`. Rendering fails
closed on a browser hash mismatch. The pinned software-WebGL configuration is
used to make the same-environment two-run tree stable; later cross-environment
rerenders are diagnostics and do not replace a reviewed evidence artifact.

The runner creates two independent trees, compares every artifact, and emits a
hash-closed bundle. LPWM preflight is read-only and fails closed until an
approved checkpoint digest, exact environment manifest, and CUDA smoke record
are present.

Visual review attempt 1 remains a hash-bound failure. Attempt 2 is an
owner-supplied review by an external AI assistant and passed the corrected
medium. The research owner explicitly approved this provenance for the E1R
review gate on 2026-08-10. It is not represented as a human review:
`human_review_performed` remains `false`.
