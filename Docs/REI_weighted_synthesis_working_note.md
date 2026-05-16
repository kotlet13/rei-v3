# REI weighted synthesis working note

Status: working clarification from the 2026-05-16 model-eval discussion.

Purpose: record the current project direction for Ego synthesis, character weights, and future evals. This note does not replace `rei_kanon.md` or `rei_app_spec.md`; it clarifies how to interpret them when building and testing LLM synthesis.

## Existing anchors

- `rei_kanon.md` defines character as the stable distribution of power between Racio, Emocio, and Instinkt.
- `rei_kanon.md` separates stable character from dynamic state.
- `rei_app_spec.md` already defines hierarchical weights for character profiles.
- `Docs/REI_LLM_prompt_pack_v3_best_practices.md` says that `>` means more influence in the simulated Ego and `=` means equal influence.
- `rei_app_spec.md` warns against mixing character and current state.

## Core correction

Final synthesis is not a winner-takes-all choice between Racio, Emocio, and Instinkt.

Final synthesis is always a compromise between all three minds. The character profile determines the relative weight of each mind inside that compromise.

Therefore, terms such as `leading_mind`, `dominant_mind`, or `winning_mind` should be treated carefully. They are acceptable only as shorthand for the center of gravity of the compromise, not as proof that the other minds disappeared.

Preferred terms:

- `synthesis_weight_bias`
- `compromise_center`
- `weighted_influence`
- `synthesis_tilt`
- `influence_distribution`
- `hijack`

## Character vs situation

Racio lead is not caused by a technical, financial, or material situation.

Racio lead is caused by a Racio-led character profile.

The situation determines which signals become active: facts, losses, fears, images, desires, boundaries, social meaning, bodily unease, and so on. The situation does not by itself decide which mind has the most authority in the final compromise.

Examples:

- In a Racio-led character, even a frightening situation should remain strongly tilted toward Racio's way of resolving: material benefit, evidence, calculation, sequence, utility, and explicit consequence.
- In an Instinkt-led character, even a technical situation can become safety-first, control-first, protection-first, or loss-avoidant.
- In an Emocio-led character, even a material decision can be organized around image, desire, vitality, recognition, belonging, or the felt meaning of the outcome.

Situation can increase the intensity of a mind's signal. It should not silently rewrite the character hierarchy.

## Profile interpretation

### `R > E = I`

Racio has the dominant weight. Emocio and Instinkt are present, but their role is secondary. They may correct, warn, color, or add friction, but the compromise should remain substantially tilted toward Racio.

The final synthesis should usually preserve material usefulness, calculation, structure, and explicit trade-off as the main organizing principle.

### `R = E > I`

Racio and Emocio must form the main compromise together. Instinkt is present but has less weight.

The final synthesis should not collapse into pure planning or pure desire. It should show a real negotiation between material utility and emotional/image value, while Instinkt remains a smaller warning or constraint.

### `R > E > I`

Racio has the strongest weight, Emocio has meaningful secondary influence, and Instinkt has the least influence.

The final synthesis should be clearly Racio-tilted, but not emotionally sterile. Emocio may shape the goal, motivation, or presentation. Instinkt may warn, but should not become the center unless the output is explicitly describing distortion, non-acceptance, or instability.

### `R = E = I`

The thirteenth character is not a soft average. It uses a two-of-three style majority while preserving serious objections from the third mind.

The final synthesis may shift by situation more than in hierarchical profiles, but all three minds must remain visible.

## Eval implications

Future model evals should not primarily ask: "Did the scenario produce the expected leading mind?"

They should ask:

1. Did the final synthesis preserve the character's intended influence weights?
2. Did all three minds remain present in the compromise?
3. Did the situation activate the right type of content without overwriting the character hierarchy?
4. Did a lower-weight mind hijack the compromise?
5. Did the synthesis explain how the compromise was formed?
6. Did repeated stock phrases replace real character-specific compromise?

The previous `leading_mind` metric is useful only as a rough diagnostic. It should be reinterpreted as a proxy for synthesis tilt, not as the core truth of REI behavior.

## Prompt implications

The Ego Integrator prompt should emphasize:

- Use the character profile as the main weighting rule for compromise.
- Include all three minds in the final synthesis.
- Let the situation determine signal content and signal intensity.
- Do not let the situation by itself change which mind has the greatest influence.
- A lower-weight mind may object, warn, desire, or correct, but should not become the compromise center unless the profile, conflict model, or explicit instability justifies it.
- Explain the final synthesis as a weighted compromise, not as one mind defeating the others.

## Practical warning from current local-model tests

The completed local-model run showed that final synthesis can overuse Instinkt-like safety language, especially when any risk, loss, uncertainty, or boundary appears.

This should not be solved only by changing models. The prompt and evaluation logic should distinguish:

- legitimate Instinkt signal,
- Instinkt-heavy character weighting,
- temporary fear activation,
- and Instinkt hijacking the compromise against the character profile.

Likewise, repeated phrases such as "bounded test", "minimum safety condition", and "responsible planning" should not become canned replacements for actual weighted synthesis.

## Working rule for future conversations

When discussing or implementing REI synthesis in this project, assume that the user's intended direction is:

Final output = all three minds present + character-weighted compromise + situation-activated content.

Do not treat scenario domain as the source of Racio, Emocio, or Instinkt authority. Treat character profile as the source of authority, and situation as the source of activated material.
