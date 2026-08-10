# E2 blind visual review template

Review only the shuffled visual samples supplied by the review coordinator.
Do not inspect evaluator manifests, route names, training logs, seed scores, or
the selected-sample rule before recording the ratings.

- Reviewer ID:
- Review date:
- Shuffle manifest SHA-256:
- Sample set complete: yes / no

For every clip, record:

| Blind sample | Identity continuity (0-4) | Person count stable (0-4) | Duplicates absent (0-4) | Goal-sensitive future visible (0-4) | Notes |
|---|---:|---:|---:|---:|---|
| | | | | | |

Global checks:

- The clips are distinguishable across stochastic seeds: yes / partial / no
- Same-seed repeats are visually identical: yes / no
- Image-goal changes produce a visible change while the observation prefix is fixed: yes / partial / no
- Any clip appears to encode text or semantic labels: yes / no
- Any imagined completion could be mistaken for grounded source evidence: yes / no

This review does not alter the frozen numeric gates. It is review evidence for
the narrow technical-overfit result and cannot establish social model fit, a
working Emocio, or reality authority for imagined frames.
