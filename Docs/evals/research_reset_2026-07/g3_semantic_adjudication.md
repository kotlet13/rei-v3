# G3A semantic adjudication — 2026-07-17

This document records the bounded human-semantic adjudication of the completed
Gemma 4 Racio epistemic G3 development screen. It uses only the committed
[G3 report](gemma4_racio_epistemic_dev_screen.md) and the committed
[G3 evidence bundle](../semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/).
No model was called, no frozen artifact or gold label was changed, and no
aggregate semantic score is derived here.

The purpose is to distinguish genuine interpretation failures from limitations
of the current flat evaluator taxonomy, to adjudicate every motive-overclaim
flag against the cited manifestations, and to decide whether the next bounded
design phases may be proposed for separate human review. This is not a Gemma
promotion decision and does not start another phase.

## Scope and method

The review covers:

- all eight action mismatches reported by the frozen G3 evaluator;
- all 15 motive hypotheses reported as unsupported overclaims;
- all six cases with zero reported motive overclaims;
- all eight Slovenian-English pairs;
- symmetric controls, including correct outputs and partially supported cases.

Action support is separated into two questions:

1. Does the manifested evidence support the proposed action family?
2. Does it support the exact action subtype?

Family support does not imply subtype support. Neither kind of action support
is evidence for a motive. For motives, `direct support` means that the cited
manifestation independently supports the motive hypothesis. A motive is not
directly supported merely because it could plausibly explain an action or
because it was emitted at lower confidence.

All counts below are descriptive dimension-level tallies. They are deliberately
not combined into a pass rate or an aggregate semantic result.

## Provisional action-family hypothesis

The family/subtype split proposed in the post-G3 plan is useful as a replaceable
evaluator-design hypothesis:

| Proposed family | Candidate subtypes |
|---|---|
| `approach_engage` | `approach`, `connect`, `seek_attachment`, proposed `perform_toward_target` |
| `protection_regulation` | `protect`, `set_boundary`, `seek_safety`, `withdraw`, `freeze`, `conserve` |
| `confrontation` | `attack`, `compete`, proposed `remove_obstacle` |
| `execution_expression` | `perform`, `improvise`, proposed `coordinate` |

This grouping explains meaningful distinctions that an exact-enum comparison
currently collapses. It is not a new REI canon and is not yet complete:

- current labels such as `maintain`, `unknown`, and `withdraw_contact` still
  require an explicit placement or an out-of-taxonomy rule;
- `perform_toward_target` overlaps with `perform` and needs an operational
  boundary;
- `protect` behaves like a generic or parent-like label in H15, despite being
  listed beside more specific subtypes;
- `seek_attachment` embeds a motive-like term in an action label; a surface
  action label such as `seek_contact` would reduce action-to-motive leakage;
- sibling membership must not make every sibling interchangeable. Family,
  subtype, and support mode (`direct`, `functional`, or `speculative`) need
  independent evaluation.

## Action mismatch adjudication

| Case | Visible manifestation | Expected subtype / family | Model subtype / family | Classification | Human-semantic decision |
|---|---|---|---|---|---|
| `g3_h1_sl` | Clear impulse to approach the group and establish contact | `connect` / `approach_engage` | `protect` / `protection_regulation` | `true_model_error` | Reject family and subtype. Nothing manifested protection; the paired EN result makes language sensitivity a bounded concern. |
| `g3_h1_en` | “Clear impulse to approach the group and establish contact” | `connect` / `approach_engage` | `approach` / `approach_engage` | `gold_too_narrow` | Accept family and the directly manifested sibling. Do not call it exact `connect` support. |
| `g3_h3_sl` | Clear protective impulse not to force the start and to hold execution for now | `protect` / `protection_regulation` | `set_boundary` / `protection_regulation` | `bilingual_drift` | Accept family; reject exact subtype because no boundary is manifested. This is a same-family mismatch; EN selected `protect`. |
| `g3_h7_sl` | Explicit impulse to set a boundary and stop the harmful pattern | `set_boundary` / `protection_regulation` | `seek_safety` / `protection_regulation` | `bilingual_drift` | Accept family; reject exact subtype. This is a same-family mismatch; safety is a plausible consequence, while EN selected `set_boundary`. |
| `g3_h15_sl` | Personal-space crossing, need to protect the same boundary, and explicit boundary-setting impulse | `set_boundary` / `protection_regulation` | `protect` / `protection_regulation` | `acceptable_parent` | Accept family and parent-level resolution; retain subtype as less specific than the manifestation. |
| `g3_h15_en` | Same personal-space crossing, protection need, and boundary-setting impulse | `set_boundary` / `protection_regulation` | `protect` / `protection_regulation` | `acceptable_parent` | Same decision as SL; the pair is semantically aligned at parent level. |
| `g3_r1_sl` | Very strong anger and an explicit impulse to attack or enter confrontation | `attack` / `confrontation` | `conserve` / `protection_regulation` | `true_model_error` | Reject family and subtype. EN selected `attack`, making language sensitivity a bounded concern. |
| `g3_r5_sl` | Strong attraction toward making the prepared movement real and an explicit impulse to perform it | `perform` / `execution_expression` | `seek_attachment` / `approach_engage` | `true_model_error` | Reject family and subtype. No attachment-seeking action is manifested; EN selected `perform`, making language sensitivity a bounded concern. |

No mismatch is best explained by packet ambiguity. The packets are sufficiently
explicit for the decisions above. Five of the eight exact mismatches remain
inside the proposed expected family: H1 EN, H3 SL, H7 SL, and both H15 cases.
Three are wrong-family errors: H1 SL, R1 SL, and R5 SL.

### Symmetric exact-action controls

The other eight action results remain credible exact-subtype controls:

| Cases | Exact action | Family | Control assessment |
|---|---|---|---|
| `g3_h3_en` | `protect` | `protection_regulation` | Directly matches the protective impulse. |
| `g3_h7_en` | `set_boundary` | `protection_regulation` | Directly matches explicit boundary setting. |
| `g3_h11_sl`, `g3_h11_en` | `seek_safety` | `protection_regulation` | Directly matches the safer-position/retreat direction. |
| `g3_r1_en` | `attack` | `confrontation` | Directly matches attack/confrontation. |
| `g3_r3_sl`, `g3_r3_en` | `seek_attachment` | `approach_engage` | Matches contact/closeness seeking, while retaining the label-design concern above. |
| `g3_r5_en` | `perform` | `execution_expression` | Directly matches execution of the prepared movement. |

These controls are useful but lexically close to available enum labels. They do
not establish out-of-corpus generalization.

### Descriptive action tallies after family separation

| Dimension | SL | EN |
|---|---:|---:|
| Manifested action family supported | 5/8 | 8/8 |
| Exact action subtype supported | 2/8 | 6/8 |

Across bilingual pairs, family resolution is consistent in 5/8 pairs and exact
subtype resolution in 3/8. These are separate descriptive observations, not a
combined action score.

## Motive-overclaim adjudication

The frozen evaluator flagged 15 additional motive hypotheses. Under the strict
independent-evidence criterion, 14 remain true overclaims. One,
`g3_r3_sl` `motor_social/connection`, is directly supported by its cited
manifestation and is classified as `gold_too_narrow`. This adjudication does
not rewrite the frozen evaluator output or gold.

In the table, `action-only` means that the cited support amounts to an action
or raw urge from which the motive was inferred. `Plausible` is intentionally
separate from `direct`: a plausible hidden explanation is still unsupported.

| # | Case | Hypothesis | Cited observation(s) | Direct | Plausible | Action-only | Relation to gold | Final classification and decision |
|---:|---|---|---|---|---|---|---|---|
| 1 | `g3_h1_sl` | `motor_social/connection` | `observation_002` | no | yes | yes | unrelated | `true_overclaim`; reject. Approach/contact as an action does not independently establish a connection motive. |
| 2 | `g3_h1_en` | `motor_social/connection` | `observation_002` | no | yes | yes | unrelated | `true_overclaim`; reject for the same reason as SL. |
| 3 | `g3_h1_en` | `scene/desired_scene_absent` | `observation_001` | no | yes | no | sibling of `desired_scene_mismatch` | `true_overclaim`; reject. The scene is elsewhere and mismatched, not absent. The English gloss may have encouraged sibling expansion. |
| 4 | `g3_h3_sl` | `protection/boundary_alarm` | `observation_002` | no | yes | yes | unrelated | `true_overclaim`; reject. A protective defer/hold action does not manifest a boundary alarm. |
| 5 | `g3_h3_en` | `protection/general_body_alarm` | `observation_002` | no | yes | yes | unrelated | `true_overclaim`; reject. No body-wide alarm is manifested. |
| 6 | `g3_h3_en` | `protection/resource_alarm` | `observation_001`, `observation_002` | no | no | no | unrelated | `true_overclaim`; reject. No resource or loss signal is present. |
| 7 | `g3_h7_sl` | `protection/boundary_alarm` | `observation_002` | no | yes | yes | unrelated | `true_overclaim`; reject. Boundary-setting action alone is not a boundary-alarm motive. |
| 8 | `g3_h7_en` | `protection/boundary_alarm` | `observation_002` | no | yes | yes | unrelated | `true_overclaim`; reject for the same reason as SL. |
| 9 | `g3_h11_en` | `protection/escape_alarm` | `observation_002` | no | yes | yes | sibling of accepted `boundary_alarm` | `true_overclaim`; reject under the current strict contract. The cited safer-position/retreat urge does not independently manifest an alarm. |
| 10 | `g3_r1_en` | `protection/general_body_alarm` | `observation_001` | no | yes | no | unrelated (no identifiable motive gold) | `true_overclaim`; reject. Strong anger with an invisible cause does not identify a body-alarm motive. |
| 11 | `g3_r1_en` | `motor_social/competition` | `observation_002` | no | yes | yes | unrelated (no identifiable motive gold) | `true_overclaim`; reject. Attack/confrontation does not establish competition. |
| 12 | `g3_r3_sl` | `motor_social/connection` | `observation_001` | yes | yes | no | unrelated (cross-family alternative to `attachment_alarm`) | `gold_too_narrow`; retain as a lower-priority supported alternative. The cited bodily pull toward safe contact and closeness independently supports connection. |
| 13 | `g3_r3_sl` | `scene/desired_scene_absent` | `observation_002` | no | yes | no | unrelated | `true_overclaim`; reject. Seeking attachment/checking availability does not manifest an absent desired scene. |
| 14 | `g3_r3_en` | `motor_social/connection` | `observation_002` | no | yes | yes | unrelated (cross-family alternative to `attachment_alarm`) | `true_overclaim`; reject at this citation level. Unlike SL, EN cites only the raw attachment-seeking action. |
| 15 | `g3_r3_en` | `scene/desired_scene_absent` | `observation_002` | no | yes | no | unrelated | `true_overclaim`; reject. No absent desired scene is manifested. |

None of the 15 flagged additions is accepted merely because it is a parent,
child, or sibling. H11 EN is a close sibling and could become a
`contextually_supported` near-miss in a future contract, but hierarchy cannot
turn an unsupported citation into direct evidence. The different R3 SL and EN
connection decisions are evidence-level, not language favoritism: SL cites an
independently supportive observation, while EN cites only the action urge.

### Zero-overclaim symmetric controls

All six cases with zero frozen overclaim flags are fair controls under the same
strict standard:

| Case | Output reviewed | Evidence decision |
|---|---|---|
| `g3_h11_sl` | `protection/boundary_alarm` at `observation_001` | Directly supported; the evaluator's hierarchical acceptance is reasonable. |
| `g3_h15_sl` | `protection/boundary_alarm` at `observation_001` | Directly supported by personal-space crossing and strong tension, independently of the boundary-setting urge. |
| `g3_h15_en` | `protection/boundary_alarm` at `observation_001` | Same direct support as SL. |
| `g3_r1_sl` | No motive hypothesis; unknown reason retained | Correctly preserves non-identifiability even though its action label is wrong. |
| `g3_r5_sl` | `motor_social/motor_execution` at `observation_001` and `observation_002` | Directly supported; motive handling remains valid despite the wrong action label. |
| `g3_r5_en` | `motor_social/motor_execution` at `observation_001` and `observation_002` | Directly supported and paired with the correct action. |

### Partially supported controls without an action error

| Case | Supported core | Unsupported addition(s) | Decision |
|---|---|---|---|
| `g3_h3_en` | `scene/desired_scene_absent` is directly supported by `observation_001`; action `protect` is correct. | `general_body_alarm`, `resource_alarm` | Keep the supported core and reject both additions. |
| `g3_h7_en` | `scene/recurrent_broken_scene` is directly supported by `observation_001`; action `set_boundary` is correct. | `boundary_alarm` | Keep the supported core and reject action-to-motive leakage. |
| `g3_h11_en` | `boundary_alarm` is directly supported; action `seek_safety` is correct. | `escape_alarm` | Preserve the direct hypothesis and reject the sibling inferred from the retreat urge. |
| `g3_r3_en` | `attachment_alarm` is directly supported; action `seek_attachment` is correct. | `connection`, `desired_scene_absent` | Preserve the direct hypothesis and reject both additions at their cited evidence level. |

### Motive-minimality finding

The evidence supports a default of zero or one motive hypothesis. A second or
third hypothesis should be permitted only when each additional hypothesis has
independent cited manifestation evidence that does not merely restate the
action. Lower confidence does not rescue an unsupported claim. A future v3
support mode may preserve contextually plausible alternatives descriptively,
but `speculative` or `contextually_supported` must not count as supported
evidence.

The one candidate gold expansion is R3 SL `motor_social/connection`. It should
be considered during a separate model-free v3 contract/gold design phase, not
retroactively edited into G3.

## Slovenian-English analysis

### Language-level descriptive tallies

| Dimension | SL | EN |
|---|---:|---:|
| Action family support | 5/8 | 8/8 |
| Action subtype support | 2/8 | 6/8 |
| Total emitted motive hypotheses | 12 | 17 |
| Frozen evaluator overclaim flags | 5 | 10 |
| G3A-adjudicated true overclaims | 4 | 10 |
| Cases with at least one frozen overclaim flag | 4/8 | 6/8 |

The difference between five SL flags and four SL true-overclaim decisions is
the R3 SL `connection` reclassification. It remains recorded in the frozen G3
evidence as an evaluator flag.

### Pair review

| Root | SL / EN action | Family support SL / EN | Subtype support SL / EN | Frozen overclaims SL / EN | Pair adjudication |
|---|---|---|---|---|---|
| H1 | `protect` / `approach` | no / yes | no / no | 1 / 2 | EN resolves a directly manifested sibling; SL moves to the wrong family. EN also expands the scene motive. |
| H3 | `set_boundary` / `protect` | yes / yes | no / yes | 1 / 2 | Both preserve protection-regulation; only EN selects the manifested subtype, but EN enumerates two extra motives. |
| H7 | `seek_safety` / `set_boundary` | yes / yes | no / yes | 1 / 1 | Same family and same action-derived motive overclaim; EN is exact at subtype level. |
| H11 | `seek_safety` / `seek_safety` | yes / yes | yes / yes | 0 / 1 | Action is stable. EN adds `escape_alarm`, plausibly encouraged by the operational gloss “retreat.” |
| H15 | `protect` / `protect` | yes / yes | no / no | 0 / 0 | Stable parent-level action and direct boundary-alarm motive in both languages. |
| R1 | `conserve` / `attack` | no / yes | no / yes | 0 / 2 | SL action fails but correctly preserves unknown motive; EN action succeeds but invents two motives. |
| R3 | `seek_attachment` / `seek_attachment` | yes / yes | yes / yes | 2 / 2 | Action is stable. Both enumerate extras, but one SL connection hypothesis has independent cited support and EN's does not. |
| R5 | `seek_attachment` / `perform` | no / yes | no / yes | 0 / 0 | Motive is sound in both; SL action fails. This is also the only pair with a motive-uncertainty self-report mismatch. |

### Competing explanations

1. **Gemma decodes the Slovenian action descriptions less reliably.** The G3
   evidence supports this as a bounded descriptive finding: family support is
   5/8 in SL versus 8/8 in EN, exact support is 2/8 versus 6/8, and all three
   wrong-family errors are SL. It does not prove a general Slovenian capability
   deficit. Several English descriptions contain words almost identical to
   enum labels, while Slovenian requires cross-language label mapping.

2. **English encourages motive enumeration.** This is also descriptively
   supported: EN emits five more motive hypotheses and receives five more
   frozen overclaim flags than SL. The effect is not universal—H7 is symmetric
   and R3 enumerates in both languages—but it is strong enough to require a
   minimality rule rather than prompt-by-case repair.

3. **The current action/motive taxonomy is too flat.** This is strongly
   supported as one contributor. The proposed family layer gives a useful
   account of five of eight exact action mismatches, especially H1 EN and H15.
   It cannot explain H1 SL, R1 SL, or R5 SL, which remain genuine wrong-family
   errors. A hierarchy therefore improves evaluator resolution without making
   the model's failures disappear.

The bilingual packet should retain `canonical_sl` as authoritative and pair it
with one human-reviewed `operational_en` gloss under the same observation ID
and as one evidence unit. SL-only and EN-only stress tests should remain. The
English gloss must not replace Slovenian. Before a v3 freeze, glosses should be
audited for enum-token collisions and semantic-strength drift; H11's mapping of
Slovenian `umik` into English “escape/retreat” terminology is the clearest G3
warning.

## Adjudicated findings

- A family/subtype action contract is justified as a provisional evaluator
  design, not as REI ontology.
- Five exact action mismatches become family-supported but remain separately
  classified at subtype level; three wrong-family errors remain model errors.
- Fourteen of 15 frozen motive-overclaim flags remain true overclaims. R3 SL
  `connection` is the sole `gold_too_narrow` decision.
- The six zero-overclaim controls survive the same strict evidence test.
- English produces more motive enumeration; Slovenian shows weaker bounded
  action decoding in this corpus.
- Action labels must never provide motive evidence by themselves.
- No finding here promotes Gemma, authorizes decision authority, changes G3,
  or constitutes an aggregate semantic pass.

## Phase-boundary interpretation

`G3_RERUN_ALLOWED: no` means no rerun is authorized now. It does not prohibit
the single future frozen G3C rerun described by the post-G3 plan after a v3
contract/evaluator is explicitly approved, implemented model-free, reviewed,
and frozen.

`SHADOW_INTEGRATION_ALLOWED: yes` means only that a separately authorized I1
phase may implement no-authority text shadow mode. Deterministic behavior must
remain the default, and shadow output must not affect governance,
`ConsciousDecision`, `BehaviorResultant`, or `MindWorld` state. This document
does not start I1.

`V3_CONTRACT_ALLOWED: yes` means only that a separately authorized, model-free
G3B phase may design the adjudicated family/subtype, support-mode, minimality,
and bilingual rules. Historical v2 must remain unchanged. This document does
not start G3B.

## Verification

- Model calls: `0`.
- Runtime/code/provider/prompt/evaluator changes: `0`.
- Kickoff-suggested test `tests/evaluation/test_racio_gemma4_epistemic_dev.py`
  does not exist on this branch.
- Focused replacement command:
  `python -m pytest tests/evaluation/test_gemma4_epistemic_dev_runner.py -q --basetemp=output/g3a_pytest_20260717`
  — `10 passed in 0.79s`.
- `git diff --check` — passed with no findings.

## Decision block

```text
ACTION_TAXONOMY_DECISION: approve a provisional family/subtype split for v3 contract design, with family, subtype, and support mode evaluated independently; sibling support is not exact support, and action never implies motive
MOTIVE_MINIMALITY_DECISION: approve a default of zero or one motive; allow additional motives only with independent cited non-action support; contextual plausibility and lower confidence do not count as support
BILINGUAL_INPUT_DECISION: approve canonical_sl plus a human-reviewed operational_en gloss as one observation identity and one evidence unit; canonical SL remains authoritative, monolingual stress cases remain, and gloss collisions must be audited
G3_RERUN_ALLOWED: no
SHADOW_INTEGRATION_ALLOWED: yes
V3_CONTRACT_ALLOWED: yes
```

G3A stops here for human review. No G3B, I1, rerun, G4, promotion, PR, or merge
is started by these decisions.
