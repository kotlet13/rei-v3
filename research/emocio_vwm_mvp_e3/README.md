# Emocio VWM E3 — LPWM objectness qualification

E3 tests one narrow implementation hypothesis: whether unchanged LPWM, trained from scratch with the initial upstream Sketchy-style regime, can form active spatially meaningful particles on a semantically neutral REI-v3 visual medium. It does not test social understanding, status, recognition, symbolism, desire, image goals, a visual self, Racio vision, or a working Emocio.

The REI canon, its research interpretation, LPWM as a replaceable implementation hypothesis, and this concrete object-layer test are separate claim levels. Even a pass would qualify only the LPWM object layer for a later, separately approved dynamics gate.

The frozen dataset remains external. `model_visible` contains only opaque RGB PNG sequences. Scene graphs, IDs, exact label maps, union masks, transforms, colors, and counts are evaluator-only. The official Sketchy checkpoint is a positive control only and is forbidden for target initialization.

E2R remains immutable: it completed 1,200 optimizer steps, produced zero active particles, was classified `collapsed_objectness`, failed four hard gates, and separately encountered the preserved post-training packaging `KeyError: 'lpwm_smoke'`. E3 uses a fixture-tested independent packager.
