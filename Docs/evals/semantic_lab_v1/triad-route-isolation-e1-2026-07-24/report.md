# TRIAD-ISO-E1 — four-case native route-isolation execution

This is a research-only development execution. It is not a holdout, not promotion evidence, and it computes no global REI score.

Emocio used manual structured core-route scenes without image generation. This does not validate image-native visual cognition.

Instinkt used grounded typed option consequences. This does not validate raw-scene Instinkt perception.

No character replay, ConsciousDecision, BehaviorResultant, or Ego update was executed.

## Execution summary

- Pre-call seal: `1360554ad44b64f1aa8cdeb4e92d3bf278b8d812d381f0685e4e4595ccf86080`.
- Candidate SHA-256: `e9e1608b5eb3e472e6953c310749f21b676013602d5658849ab36356701144aa`.
- Subset SHA-256: `e4861112f8917658fdde47cf5c69f7c3df83cb9c137af398b53aeb4f39480118`.
- Exact model digest: `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`.
- Calls/retries/fallbacks: 4/0/0.
- Racio accepted/rejected: 3/1.

### Contract rejection

`trip_racio_utility_material` was rejected at
`racio_structured_output_packet_contract` with
`fact_evidence_mismatch`. The bounded failed-output diagnostic is preserved in
that case's `call_record.json`; its final JSON SHA-256 is
`15fbfb4d294b9859eaf56b2ee3a34b35e1e3216e2194a813c81d3374a2467474`.
There was no retry, prompt change, or replacement call. Consequently, Racio
utility-pair route distinction is not assessable from accepted conclusions.

## trip_racio_utility

| | `trip_racio_utility_material` | `trip_racio_utility_pleasure` |
|---|---|---|
| Racio option | `rejected` | `utility_trip_home` |
| Emocio option | `abstention` | `abstention` |
| Instinkt option | `utility_trip_local` | `utility_trip_local` |

### HELD CONSTANT

- Public options: `[{"description": "Book the described trip.", "option_id": "utility_trip_book"}, {"description": "Take a cheaper local coastal trip.", "option_id": "utility_trip_local"}, {"description": "Do not book travel and remain at home.", "option_id": "utility_trip_home"}]`.
- Sealed constant hashes: `{"emocio_route_packet_sha256": "e4c78cfdc9bdf5f3b62ef28ece68ea2dafd3e7600bb9cd59dfe761fca1e2b5e1", "instinkt_route_packet_sha256": "e4e43c3881f9d8ec2e23b3a36b937adbde78061763e6c56b087ae42c1570e224", "options_sha256": "196132c914dbe7adbe638944d28de3f261e11e6c3c03d04eca65c8c7fe82e470"}`.
- Route packets expected stable are identified by the pair invariant report and were cold-rechecked before every call.

### CHANGED

Only the following predeclared source paths differ:

- `canonical_sl/facts/6/text`
- `canonical_sl/facts/7/text`
- `canonical_sl/unknowns/1/text`
- `case_id`
- `operational_en/facts/6/text`
- `operational_en/facts/7/text`
- `operational_en/unknowns/1/text`
- `route_packets/racio/enforceability_control`
- `route_packets/racio/explicit_beneficiary`
- `route_packets/racio/explicit_goal`
- `route_packets/racio/material_strategic_consequences/0/beneficiary`
- `route_packets/racio/material_strategic_consequences/0/consequence`
- `route_packets/racio/material_strategic_consequences/1/beneficiary`
- `route_packets/racio/material_strategic_consequences/1/consequence`
- `route_packets/racio/material_strategic_consequences/2/beneficiary`
- `route_packets/racio/material_strategic_consequences/2/consequence`
- `route_packets/racio/opportunity_cost`
- `route_packets/racio/time_sequence/1`
- `route_packets/racio/time_sequence/2`
- `variant_id`

### RACIO

#### `trip_racio_utility_material` — exact visible packet

- Selected option: `rejected`.
- Status: `rejected`.

```json
{
  "allowed_option_ids": [
    "utility_trip_book",
    "utility_trip_local",
    "utility_trip_home"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "Use only the explicit facts and unknowns in this packet.",
    "Do not infer undeclared strategic or material benefit.",
    "Retain bounded uncertainty and select only a public option."
  ],
  "evidence_ids": [
    "utility_ev_cost",
    "utility_ev_rarity",
    "utility_ev_reversibility",
    "utility_ev_benefit",
    "utility_ev_beneficiary"
  ],
  "explicit_consequences": [
    {
      "consequence": "Beneficiary self_studio: The studio gains access to a signed buyer demonstration and a bounded saving of up to EUR 900, while self commits EUR 1200.",
      "evidence_ids": [
        "utility_ev_cost",
        "utility_ev_rarity",
        "utility_ev_reversibility",
        "utility_ev_benefit",
        "utility_ev_beneficiary"
      ],
      "option_id": "utility_trip_book"
    },
    {
      "consequence": "Beneficiary self_studio: The studio receives no buyer demonstration or external-cost saving; self incurs a smaller unquantified local cost.",
      "evidence_ids": [
        "utility_ev_cost",
        "utility_ev_rarity",
        "utility_ev_reversibility",
        "utility_ev_benefit",
        "utility_ev_beneficiary"
      ],
      "option_id": "utility_trip_local"
    },
    {
      "consequence": "Beneficiary self_studio: The studio receives no buyer demonstration or external-cost saving; self preserves the travel budget.",
      "evidence_ids": [
        "utility_ev_cost",
        "utility_ev_rarity",
        "utility_ev_reversibility",
        "utility_ev_benefit",
        "utility_ev_beneficiary"
      ],
      "option_id": "utility_trip_home"
    }
  ],
  "explicit_facts": [
    "The trip costs EUR 1200, or 25 percent of the discretionary budget.",
    "The same offer was available once during the last three years.",
    "The booking can be cancelled within 24 hours at a 10-percent cost.",
    "The trip includes a signed invitation to a buyer demonstration that can save self's studio up to EUR 900 in external demonstration costs if delivery succeeds.",
    "The explicit recipient of the bounded strategic and material benefit is self's studio; no public status or recognition is involved."
  ],
  "explicit_options": [
    {
      "description": "Book the described trip.",
      "label": "Book the described trip.",
      "option_id": "utility_trip_book",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Take a cheaper local coastal trip.",
      "label": "Take a cheaper local coastal trip.",
      "option_id": "utility_trip_local",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Do not book travel and remain at home.",
      "label": "Do not book travel and remain at home.",
      "option_id": "utility_trip_home",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "Whether other major costs will arise next month is unknown.",
    "Whether the demonstration will be delivered well enough for the full saving is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    1200,
    25,
    24,
    10,
    900
  ],
  "packet_id": "racio_packet_af8d2a3290a5f927fa754c4679b66440",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compassion is not assumed as an unstated decision goal.",
    "A benefit must be explicit, beneficiary-addressed, and grounded.",
    "Attraction or rarity is not an undeclared strategic return."
  ],
  "scene_id": "triad_iso_e1_racio_scene_67e0d5058da078a513fa7208f237d71c",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "ee0277e57e8d377614a3641f17fe233e810261026329002c197107a23f3f32c2",
  "symbolic_and_language_cues": [
    "Self is deciding about travel to a rare and attractive coastal destination.",
    "Explicit goal: Decide whether the trip advances the studio's demonstration-cost goal within the available budget.",
    "Explicit beneficiary: self_studio"
  ],
  "time": [
    "Booking occurs before the 24-hour cancellation boundary.",
    "Travel and the buyer demonstration occur after booking.",
    "Any external-cost saving occurs only if the demonstration is delivered."
  ],
  "world": {
    "commitments": [
      "Opportunity cost: Booking commits EUR 1200 that cannot cover other costs; not booking gives up the signed demonstration and bounded studio saving.",
      "Control and enforceability: The invitation and cancellation rule are documented; delivery quality and the full saving are not controlled outcomes."
    ],
    "explicit_beliefs": [
      "Explicit goal: Decide whether the trip advances the studio's demonstration-cost goal within the available budget.",
      "Explicit beneficiary: self_studio"
    ],
    "facts": [
      "The trip costs EUR 1200, or 25 percent of the discretionary budget.",
      "The same offer was available once during the last three years.",
      "The booking can be cancelled within 24 hours at a 10-percent cost.",
      "The trip includes a signed invitation to a buyer demonstration that can save self's studio up to EUR 900 in external demonstration costs if delivery succeeds.",
      "The explicit recipient of the bounded strategic and material benefit is self's studio; no public status or recognition is involved."
    ],
    "rules": [
      "Compassion is not assumed as an unstated decision goal.",
      "A benefit must be explicit, beneficiary-addressed, and grounded.",
      "Attraction or rarity is not an undeclared strategic return."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "Booking occurs before the 24-hour cancellation boundary.",
      "Travel and the buyer demonstration occur after booking.",
      "Any external-cost saving occurs only if the demonstration is delivered."
    ],
    "world_id": "triad_iso_e1_racio_world_56d8475af2981c85dc7d136671fa2254"
  }
}
```

Route / facts / unknowns / utility / goal:

```json
null
```

#### `trip_racio_utility_pleasure` — exact visible packet

- Selected option: `utility_trip_home`.
- Status: `accepted`.

```json
{
  "allowed_option_ids": [
    "utility_trip_book",
    "utility_trip_local",
    "utility_trip_home"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "Use only the explicit facts and unknowns in this packet.",
    "Do not infer undeclared strategic or material benefit.",
    "Retain bounded uncertainty and select only a public option."
  ],
  "evidence_ids": [
    "utility_ev_cost",
    "utility_ev_rarity",
    "utility_ev_reversibility",
    "utility_ev_benefit",
    "utility_ev_beneficiary"
  ],
  "explicit_consequences": [
    {
      "consequence": "Beneficiary self: Self commits EUR 1200 for a stated pleasurable experience with no separate strategic or material return.",
      "evidence_ids": [
        "utility_ev_cost",
        "utility_ev_rarity",
        "utility_ev_reversibility",
        "utility_ev_benefit",
        "utility_ev_beneficiary"
      ],
      "option_id": "utility_trip_book"
    },
    {
      "consequence": "Beneficiary self: Self incurs a smaller unquantified cost for a local coastal experience with no separate strategic or material return.",
      "evidence_ids": [
        "utility_ev_cost",
        "utility_ev_rarity",
        "utility_ev_reversibility",
        "utility_ev_benefit",
        "utility_ev_beneficiary"
      ],
      "option_id": "utility_trip_local"
    },
    {
      "consequence": "Beneficiary self: Self preserves the travel budget and receives no travel experience.",
      "evidence_ids": [
        "utility_ev_cost",
        "utility_ev_rarity",
        "utility_ev_reversibility",
        "utility_ev_benefit",
        "utility_ev_beneficiary"
      ],
      "option_id": "utility_trip_home"
    }
  ],
  "explicit_facts": [
    "The trip costs EUR 1200, or 25 percent of the discretionary budget.",
    "The same offer was available once during the last three years.",
    "The booking can be cancelled within 24 hours at a 10-percent cost.",
    "The trip is explicitly only a leisure and pleasurable experience; it includes no business, ownership, educational, or other strategic or material benefit.",
    "Self receives the explicitly pleasurable experience; there is no separate strategic or material beneficiary."
  ],
  "explicit_options": [
    {
      "description": "Book the described trip.",
      "label": "Book the described trip.",
      "option_id": "utility_trip_book",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Take a cheaper local coastal trip.",
      "label": "Take a cheaper local coastal trip.",
      "option_id": "utility_trip_local",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Do not book travel and remain at home.",
      "label": "Do not book travel and remain at home.",
      "option_id": "utility_trip_home",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "Whether other major costs will arise next month is unknown.",
    "How satisfying the leisure experience will be is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    1200,
    25,
    24,
    10
  ],
  "packet_id": "racio_packet_7de47e7bb77a46226fec818a60f3b6df",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compassion is not assumed as an unstated decision goal.",
    "A benefit must be explicit, beneficiary-addressed, and grounded.",
    "Attraction or rarity is not an undeclared strategic return."
  ],
  "scene_id": "triad_iso_e1_racio_scene_95e1b247c45800f0b3df50a27cf3afa0",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "e893d1b9ef811d461d79cb017646b6ef15e30458a76c7d929c087e695b39e46c",
  "symbolic_and_language_cues": [
    "Self is deciding about travel to a rare and attractive coastal destination.",
    "Explicit goal: Decide whether to spend the stated budget amount on the explicitly pleasurable experience.",
    "Explicit beneficiary: self"
  ],
  "time": [
    "Booking occurs before the 24-hour cancellation boundary.",
    "Travel occurs after booking.",
    "Possible future costs occur after the purchase."
  ],
  "world": {
    "commitments": [
      "Opportunity cost: Travel spending cannot cover other unknown costs; not travelling gives up the explicitly stated experience.",
      "Control and enforceability: The cancellation rule is documented; satisfaction and future costs are not controlled outcomes."
    ],
    "explicit_beliefs": [
      "Explicit goal: Decide whether to spend the stated budget amount on the explicitly pleasurable experience.",
      "Explicit beneficiary: self"
    ],
    "facts": [
      "The trip costs EUR 1200, or 25 percent of the discretionary budget.",
      "The same offer was available once during the last three years.",
      "The booking can be cancelled within 24 hours at a 10-percent cost.",
      "The trip is explicitly only a leisure and pleasurable experience; it includes no business, ownership, educational, or other strategic or material benefit.",
      "Self receives the explicitly pleasurable experience; there is no separate strategic or material beneficiary."
    ],
    "rules": [
      "Compassion is not assumed as an unstated decision goal.",
      "A benefit must be explicit, beneficiary-addressed, and grounded.",
      "Attraction or rarity is not an undeclared strategic return."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "Booking occurs before the 24-hour cancellation boundary.",
      "Travel occurs after booking.",
      "Possible future costs occur after the purchase."
    ],
    "world_id": "triad_iso_e1_racio_world_d0e05fb98f4763a9717e577eee119668"
  }
}
```

Route / facts / unknowns / utility / goal:

```json
{
  "abstains": false,
  "causal_sequence": [
    "Evaluating the cost of a rare leisure trip against the available discretionary budget.",
    "Comparing the high-cost experience with lower-cost local alternatives or staying home.",
    "Considering the risk of future unknown expenses versus the limited availability of the offer.",
    "Assessing the financial impact of potential cancellation fees."
  ],
  "conclusion_id": "racio_conclusion_54264d39be7e89745d26b56f659821a5",
  "confidence": 0.8,
  "evidence_ids_used": [
    "utility_ev_cost",
    "utility_ev_rarity",
    "utility_ev_reversibility",
    "utility_ev_benefit",
    "utility_ev_beneficiary"
  ],
  "explicit_goal": "Decide whether to spend the stated budget amount on the explicitly pleasurable experience.",
  "facts_used": [
    "The trip costs EUR 1200, or 25 percent of the discretionary budget.",
    "The same offer was available once during the last three years.",
    "The booking can be cancelled within 24 hours at a 10-percent cost.",
    "The trip is explicitly only a leisure and pleasurable experience; it includes no business, ownership, educational, or other strategic or material benefit.",
    "Self receives the explicitly pleasurable experience; there is no separate strategic or material beneficiary."
  ],
  "main_objection": "Spending 25 percent of the discretionary budget on a non-strategic leisure activity may leave insufficient funds for unknown future costs.",
  "mind": "R",
  "option_id": "utility_trip_home",
  "reasoning_provider_result_hash": "7c58d0e43fb4c6810f51649d8e8e5c26763a39c877f9418fa760cd8158be8597",
  "reasoning_provider_result_id": "ollama_racio_response_3319bc04d4ccf41459b9b88fecb67c37",
  "schema_version": "rei-native-racio-conclusion-v1",
  "source_packet_hash": "6dd40905725868e480a6492afe38aa6cb7bf059ebc6b193a3f6d2fe230e4d257",
  "source_packet_id": "racio_packet_7de47e7bb77a46226fec818a60f3b6df",
  "source_scene_id": "triad_iso_e1_racio_scene_95e1b247c45800f0b3df50a27cf3afa0",
  "uncertainty": "The decision is constrained by uncertainty regarding next month's expenses and the actual satisfaction level of the experience.",
  "unknowns": [
    "Whether other major costs will arise next month is unknown.",
    "How satisfying the leisure experience will be is unknown."
  ],
  "utility_structure": [
    "High cost vs. rare pleasure",
    "Budget preservation vs. experiential gain",
    "Local alternative vs. premium destination"
  ]
}
```

Pair difference (mechanical, not human plausibility judgment):

```json
{
  "material_retains_cost": false,
  "material_retains_uncertainty": false,
  "material_uses_explicit_studio_benefit": false,
  "pleasure_preserves_no_material_return": true,
  "route_distinction": "not_assessable"
}
```

### EMOCIO

#### `trip_racio_utility_material`

- Current: `{"attention_structure": [], "attraction_markers": ["A trusted close person travels with self.", "The destination, route, and coastal experience are explicitly attractive to self."], "composition": ["A trusted close person travels with self.", "Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path.", "The destination, route, and coastal experience are explicitly attractive to self."], "entities": ["companion", "self"], "grounded_evidence_ids": ["utility_ev_companion", "utility_ev_destination"], "group_belonging": "unspecified", "inferred_elements": ["Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path."], "movement": [], "obstacle_markers": [], "option_id": null, "scene_id": "visual_scene_311855972c442402ed5f5c01f47744d4", "scene_kind": "current", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": ["companion", "self"]}`.
- Desired: `{"attention_structure": [], "attraction_markers": ["The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."], "composition": ["Self is centered in vivid coastal movement and immediate shared experience, without a public-recognition scene."], "entities": ["companion", "self"], "grounded_evidence_ids": ["utility_ev_companion", "utility_ev_destination"], "group_belonging": "Centered at the route decision point beside the companion.", "inferred_elements": ["Self is centered in vivid coastal movement and immediate shared experience, without a public-recognition scene."], "movement": ["The distant and local options start different travel scenes; staying home leaves the routes inactive."], "obstacle_markers": [], "option_id": null, "scene_id": "visual_scene_861b75d557b966a5d224e1b32b38bffe", "scene_kind": "desired", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": ["Centered at the route decision point beside the companion.", "not_relevant"]}`.
- Broken: `{"attention_structure": [], "attraction_markers": [], "composition": ["The coast remains outside the active scene and self has no travel movement or new experience."], "entities": ["companion", "self"], "grounded_evidence_ids": ["utility_ev_companion", "utility_ev_destination"], "group_belonging": "unspecified", "inferred_elements": ["The coast remains outside the active scene and self has no travel movement or new experience."], "movement": [], "obstacle_markers": ["The coast remains outside the active scene and self has no travel movement or new experience."], "option_id": null, "scene_id": "visual_scene_f004e2121a5ed4655dfb5bb7b1111815", "scene_kind": "broken", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": []}`.
- Selected route: `None`.
- Counterfactual option scenes and valuation vectors:

```json
{
  "aggregate_scores": {
    "utility_trip_book": 0.487879,
    "utility_trip_home": 0.39697,
    "utility_trip_local": 0.487879
  },
  "counterfactual_scenes": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."
      ],
      "composition": [
        "A trusted close person travels with self.",
        "Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path.",
        "Self and the companion enter the distant coastal route.",
        "The destination, route, and coastal experience are explicitly attractive to self.",
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."
      ],
      "entities": [
        "Centered at the route decision point beside the companion.",
        "Self and the companion enter the distant coastal route.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "utility_ev_companion",
        "utility_ev_destination"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "Centered at the route decision point beside the companion.",
        "Self and the companion enter the distant coastal route.",
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image.",
        "The inactive route and booking threshold are obstacles; no rival is present.",
        "not_relevant"
      ],
      "movement": [
        "Self and the companion enter the distant coastal route."
      ],
      "obstacle_markers": [],
      "option_id": "utility_trip_book",
      "scene_id": "visual_scene_14c829949985e782cb94cca7b8522fd1",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "Centered at the route decision point beside the companion.",
      "status_relations": []
    },
    {
      "attention_structure": [],
      "attraction_markers": [],
      "composition": [
        "A trusted close person travels with self.",
        "Both coastal routes remain inactive and self stays in the home scene.",
        "Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path.",
        "The destination, route, and coastal experience are explicitly attractive to self.",
        "The inactive route and booking threshold are obstacles; no rival is present."
      ],
      "entities": [
        "Both coastal routes remain inactive and self stays in the home scene.",
        "Centered at the route decision point beside the companion.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "utility_ev_destination"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "Both coastal routes remain inactive and self stays in the home scene.",
        "Centered at the route decision point beside the companion.",
        "The inactive route and booking threshold are obstacles; no rival is present.",
        "not_relevant"
      ],
      "movement": [],
      "obstacle_markers": [
        "The inactive route and booking threshold are obstacles; no rival is present."
      ],
      "option_id": "utility_trip_home",
      "scene_id": "visual_scene_11e836d0be307fb392798654abb08309",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "Centered at the route decision point beside the companion.",
      "status_relations": []
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."
      ],
      "composition": [
        "A trusted close person travels with self.",
        "Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path.",
        "Self and the companion enter the smaller local coastal route.",
        "The destination, route, and coastal experience are explicitly attractive to self.",
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."
      ],
      "entities": [
        "Centered at the route decision point beside the companion.",
        "Self and the companion enter the smaller local coastal route.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "utility_ev_companion",
        "utility_ev_destination"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "Centered at the route decision point beside the companion.",
        "Self and the companion enter the smaller local coastal route.",
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image.",
        "The inactive route and booking threshold are obstacles; no rival is present.",
        "not_relevant"
      ],
      "movement": [
        "Self and the companion enter the smaller local coastal route."
      ],
      "obstacle_markers": [],
      "option_id": "utility_trip_local",
      "scene_id": "visual_scene_d2fe21ab795e1f056acd12a8673679db",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "Centered at the route decision point beside the companion.",
      "status_relations": []
    }
  ],
  "valuation_vectors": {
    "utility_trip_book": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 1.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    },
    "utility_trip_home": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 0.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    },
    "utility_trip_local": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 1.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    }
  }
}
```

#### `trip_racio_utility_pleasure`

- Current: `{"attention_structure": [], "attraction_markers": ["A trusted close person travels with self.", "The destination, route, and coastal experience are explicitly attractive to self."], "composition": ["A trusted close person travels with self.", "Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path.", "The destination, route, and coastal experience are explicitly attractive to self."], "entities": ["companion", "self"], "grounded_evidence_ids": ["utility_ev_companion", "utility_ev_destination"], "group_belonging": "unspecified", "inferred_elements": ["Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path."], "movement": [], "obstacle_markers": [], "option_id": null, "scene_id": "visual_scene_311855972c442402ed5f5c01f47744d4", "scene_kind": "current", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": ["companion", "self"]}`.
- Desired: `{"attention_structure": [], "attraction_markers": ["The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."], "composition": ["Self is centered in vivid coastal movement and immediate shared experience, without a public-recognition scene."], "entities": ["companion", "self"], "grounded_evidence_ids": ["utility_ev_companion", "utility_ev_destination"], "group_belonging": "Centered at the route decision point beside the companion.", "inferred_elements": ["Self is centered in vivid coastal movement and immediate shared experience, without a public-recognition scene."], "movement": ["The distant and local options start different travel scenes; staying home leaves the routes inactive."], "obstacle_markers": [], "option_id": null, "scene_id": "visual_scene_861b75d557b966a5d224e1b32b38bffe", "scene_kind": "desired", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": ["Centered at the route decision point beside the companion.", "not_relevant"]}`.
- Broken: `{"attention_structure": [], "attraction_markers": [], "composition": ["The coast remains outside the active scene and self has no travel movement or new experience."], "entities": ["companion", "self"], "grounded_evidence_ids": ["utility_ev_companion", "utility_ev_destination"], "group_belonging": "unspecified", "inferred_elements": ["The coast remains outside the active scene and self has no travel movement or new experience."], "movement": [], "obstacle_markers": ["The coast remains outside the active scene and self has no travel movement or new experience."], "option_id": null, "scene_id": "visual_scene_f004e2121a5ed4655dfb5bb7b1111815", "scene_kind": "broken", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": []}`.
- Selected route: `None`.
- Counterfactual option scenes and valuation vectors:

```json
{
  "aggregate_scores": {
    "utility_trip_book": 0.487879,
    "utility_trip_home": 0.39697,
    "utility_trip_local": 0.487879
  },
  "counterfactual_scenes": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."
      ],
      "composition": [
        "A trusted close person travels with self.",
        "Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path.",
        "Self and the companion enter the distant coastal route.",
        "The destination, route, and coastal experience are explicitly attractive to self.",
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."
      ],
      "entities": [
        "Centered at the route decision point beside the companion.",
        "Self and the companion enter the distant coastal route.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "utility_ev_companion",
        "utility_ev_destination"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "Centered at the route decision point beside the companion.",
        "Self and the companion enter the distant coastal route.",
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image.",
        "The inactive route and booking threshold are obstacles; no rival is present.",
        "not_relevant"
      ],
      "movement": [
        "Self and the companion enter the distant coastal route."
      ],
      "obstacle_markers": [],
      "option_id": "utility_trip_book",
      "scene_id": "visual_scene_14c829949985e782cb94cca7b8522fd1",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "Centered at the route decision point beside the companion.",
      "status_relations": []
    },
    {
      "attention_structure": [],
      "attraction_markers": [],
      "composition": [
        "A trusted close person travels with self.",
        "Both coastal routes remain inactive and self stays in the home scene.",
        "Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path.",
        "The destination, route, and coastal experience are explicitly attractive to self.",
        "The inactive route and booking threshold are obstacles; no rival is present."
      ],
      "entities": [
        "Both coastal routes remain inactive and self stays in the home scene.",
        "Centered at the route decision point beside the companion.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "utility_ev_destination"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "Both coastal routes remain inactive and self stays in the home scene.",
        "Centered at the route decision point beside the companion.",
        "The inactive route and booking threshold are obstacles; no rival is present.",
        "not_relevant"
      ],
      "movement": [],
      "obstacle_markers": [
        "The inactive route and booking threshold are obstacles; no rival is present."
      ],
      "option_id": "utility_trip_home",
      "scene_id": "visual_scene_11e836d0be307fb392798654abb08309",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "Centered at the route decision point beside the companion.",
      "status_relations": []
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."
      ],
      "composition": [
        "A trusted close person travels with self.",
        "Self and a trusted companion face an attractive distant coast, a smaller local coast, and a home path.",
        "Self and the companion enter the smaller local coastal route.",
        "The destination, route, and coastal experience are explicitly attractive to self.",
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image."
      ],
      "entities": [
        "Centered at the route decision point beside the companion.",
        "Self and the companion enter the smaller local coastal route.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "utility_ev_companion",
        "utility_ev_destination"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "Centered at the route decision point beside the companion.",
        "Self and the companion enter the smaller local coastal route.",
        "The distant coast is explicitly attractive; the local coast carries a smaller but still grounded experience image.",
        "The inactive route and booking threshold are obstacles; no rival is present.",
        "not_relevant"
      ],
      "movement": [
        "Self and the companion enter the smaller local coastal route."
      ],
      "obstacle_markers": [],
      "option_id": "utility_trip_local",
      "scene_id": "visual_scene_d2fe21ab795e1f056acd12a8673679db",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "Centered at the route decision point beside the companion.",
      "status_relations": []
    }
  ],
  "valuation_vectors": {
    "utility_trip_book": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 1.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    },
    "utility_trip_home": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 0.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    },
    "utility_trip_local": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 1.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    }
  }
}
```

Pair difference (mechanical):

```json
{
  "semantic_stability": "identical"
}
```

### INSTINKT

#### `trip_racio_utility_material`

- Selected route: `utility_trip_local`.
- Danger/trust/attachment/scarcity/escape/recoverability source: `{"attachment_care": "The trusted close companion remains with self through the travel options.", "boundary": "The 24-hour cancellation rule defines the purchase boundary.", "danger_types": "No unverified travel danger is grounded; general travel exposure remains bounded.", "escape_reversibility": "Cancellation is available for 24 hours at a 10-percent cost; physical return is verified.", "familiarity": "The destination is distant, but the route, lodging, transport, and companion context are verified.", "option_consequences": [{"consequence": "Self enters verified travel with a trusted companion and a bounded financial cancellation loss.", "evidence_ids": ["utility_ev_cost", "utility_ev_reversibility", "utility_ev_companion", "utility_ev_safety"], "option_id": "utility_trip_book"}, {"consequence": "Self enters a smaller local travel scene with the same trusted companion and no stated distant-trip commitment.", "evidence_ids": ["utility_ev_companion", "utility_ev_safety"], "option_id": "utility_trip_local"}, {"consequence": "Self preserves the travel budget; no claim is made that home is universally free of danger.", "evidence_ids": ["utility_ev_cost"], "option_id": "utility_trip_home"}], "possible_loss": "A 25-percent budget commitment and 10-percent cancellation cost are possible losses.", "prior_association": "not_relevant", "protected_target": "Self's physical integrity, trusted attachment context, return ability, and necessary budget reserve.", "recoverability": "Most of the purchase is financially recoverable inside 24 hours; physical return is verified.", "scarcity": "The distant trip uses 25 percent of the discretionary budget; future major costs are unknown.", "trust_distrust": "A trusted close companion and verified providers are grounded."}`.
- Consequence/effect paths, predicted loss, recoverability, and protective cost:

```json
[
  {
    "consequence_fact": "Self enters verified travel with a trusted companion and a bounded financial cancellation loss.",
    "derived_body_deltas": {
      "attachment_security": 0.15,
      "escape_availability": 0.12,
      "predictability": 0.08,
      "resource_security": -0.15,
      "tension": -0.05,
      "trust": 0.12
    },
    "effect": {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "bounded_cancellation",
        "resource_commitment_25",
        "trusted_attachment_support"
      ],
      "attachment_outcome": "grounded_consequence_delta:attachment_security:+0.150000",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.05,
          "dimension": "tension"
        },
        {
          "delta": 0.12,
          "dimension": "trust"
        },
        {
          "delta": 0.15,
          "dimension": "attachment_security"
        },
        {
          "delta": -0.15,
          "dimension": "resource_security"
        },
        {
          "delta": 0.12,
          "dimension": "escape_availability"
        },
        {
          "delta": 0.08,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:bounded_cancellation+resource_commitment_25+trusted_attachment_support",
      "effect_hash": "f7fa40fa3783fcdf9997377d3da3e828176ff1ccff0166bf29246170b13420a8",
      "effect_id": "option_effect_30ac0b0a732ecadf7491dda1a884c319",
      "escape_outcome": "grounded_consequence_delta:escape_availability:+0.120000",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "utility_trip_book",
      "protected_targets": [
        "Self's physical integrity, trusted attachment context, return ability, and necessary budget reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "1aff9266e6044c7d08bbb56dd6e57ea41ef10789309fde353707b4bf81472ec4",
      "source_packet_id": "instinkt_packet_86bd5cda0c8c83594c631fc30fd0f271",
      "triggering_evidence_ids": [
        "utility_ev_companion",
        "utility_ev_cost",
        "utility_ev_reversibility",
        "utility_ev_safety"
      ],
      "trust_outcome": "grounded_consequence_delta:trust:+0.120000"
    },
    "effect_categories": [
      "bounded_cancellation",
      "resource_commitment_25",
      "trusted_attachment_support"
    ],
    "effect_id": "option_effect_30ac0b0a732ecadf7491dda1a884c319",
    "effect_signature": "71bdd52dfb23856b0165b53f2718d73f04c96d99e475e308c128eca7e5349383",
    "option_id": "utility_trip_book",
    "predicted_loss": 0.3350000000000001,
    "protective_cost": 0.551,
    "recoverability": 0.5960000000000001,
    "source_evidence_ids": [
      "utility_ev_companion",
      "utility_ev_cost",
      "utility_ev_reversibility",
      "utility_ev_safety"
    ],
    "source_evidence_text": [
      "A trusted close person travels with self.",
      "The trip costs EUR 1200, or 25 percent of the discretionary budget.",
      "The booking can be cancelled within 24 hours at a 10-percent cost.",
      "Transport, lodging, and the return path are verified."
    ]
  },
  {
    "consequence_fact": "Self preserves the travel budget; no claim is made that home is universally free of danger.",
    "derived_body_deltas": {
      "resource_security": 0.15
    },
    "effect": {
      "action_tendency": "maintain",
      "association_cue_tokens": [
        "resource_preserved"
      ],
      "attachment_outcome": "not_changed_by_grounded_consequence:attachment_security",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": 0.15,
          "dimension": "resource_security"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:resource_preserved",
      "effect_hash": "6f6a55be4d81c97a5e487af41b338c3de8a784b5d0d2adab270bd37f66351e35",
      "effect_id": "option_effect_2c611fcd66963aa41b436d2e51781a20",
      "escape_outcome": "not_changed_by_grounded_consequence:escape_availability",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "utility_trip_home",
      "protected_targets": [
        "Self's physical integrity, trusted attachment context, return ability, and necessary budget reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "1aff9266e6044c7d08bbb56dd6e57ea41ef10789309fde353707b4bf81472ec4",
      "source_packet_id": "instinkt_packet_86bd5cda0c8c83594c631fc30fd0f271",
      "triggering_evidence_ids": [
        "utility_ev_cost"
      ],
      "trust_outcome": "not_changed_by_grounded_consequence:trust"
    },
    "effect_categories": [
      "resource_preserved"
    ],
    "effect_id": "option_effect_2c611fcd66963aa41b436d2e51781a20",
    "effect_signature": "8998e0cef6db8c6a082d98ed1002837b7339ae909cbc66720d9079807b48383e",
    "option_id": "utility_trip_home",
    "predicted_loss": 0.3325,
    "protective_cost": 0.560625,
    "recoverability": 0.5775,
    "source_evidence_ids": [
      "utility_ev_cost"
    ],
    "source_evidence_text": [
      "The trip costs EUR 1200, or 25 percent of the discretionary budget."
    ]
  },
  {
    "consequence_fact": "Self enters a smaller local travel scene with the same trusted companion and no stated distant-trip commitment.",
    "derived_body_deltas": {
      "attachment_security": 0.15,
      "predictability": 0.08,
      "tension": -0.05,
      "trust": 0.12
    },
    "effect": {
      "action_tendency": "maintain",
      "association_cue_tokens": [
        "local_bounded_exposure",
        "trusted_attachment_support"
      ],
      "attachment_outcome": "grounded_consequence_delta:attachment_security:+0.150000",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.05,
          "dimension": "tension"
        },
        {
          "delta": 0.12,
          "dimension": "trust"
        },
        {
          "delta": 0.15,
          "dimension": "attachment_security"
        },
        {
          "delta": 0.08,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:local_bounded_exposure+trusted_attachment_support",
      "effect_hash": "34af13084d0b994eaf8ede2c25fe954dc0270ee25e13a60f34b526ec4c679e1c",
      "effect_id": "option_effect_8c56ab1fc191d0dc18d527ae4305e011",
      "escape_outcome": "not_changed_by_grounded_consequence:escape_availability",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "utility_trip_local",
      "protected_targets": [
        "Self's physical integrity, trusted attachment context, return ability, and necessary budget reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "1aff9266e6044c7d08bbb56dd6e57ea41ef10789309fde353707b4bf81472ec4",
      "source_packet_id": "instinkt_packet_86bd5cda0c8c83594c631fc30fd0f271",
      "triggering_evidence_ids": [
        "utility_ev_companion",
        "utility_ev_safety"
      ],
      "trust_outcome": "grounded_consequence_delta:trust:+0.120000"
    },
    "effect_categories": [
      "local_bounded_exposure",
      "trusted_attachment_support"
    ],
    "effect_id": "option_effect_8c56ab1fc191d0dc18d527ae4305e011",
    "effect_signature": "0b4ccb83234a799510bd70dae8c60399e5d23dbf17397a167aa2b3b1e30e793a",
    "option_id": "utility_trip_local",
    "predicted_loss": 0.32750000000000007,
    "protective_cost": 0.544625,
    "recoverability": 0.5915,
    "source_evidence_ids": [
      "utility_ev_companion",
      "utility_ev_safety"
    ],
    "source_evidence_text": [
      "A trusted close person travels with self.",
      "Transport, lodging, and the return path are verified."
    ]
  }
]
```

#### `trip_racio_utility_pleasure`

- Selected route: `utility_trip_local`.
- Danger/trust/attachment/scarcity/escape/recoverability source: `{"attachment_care": "The trusted close companion remains with self through the travel options.", "boundary": "The 24-hour cancellation rule defines the purchase boundary.", "danger_types": "No unverified travel danger is grounded; general travel exposure remains bounded.", "escape_reversibility": "Cancellation is available for 24 hours at a 10-percent cost; physical return is verified.", "familiarity": "The destination is distant, but the route, lodging, transport, and companion context are verified.", "option_consequences": [{"consequence": "Self enters verified travel with a trusted companion and a bounded financial cancellation loss.", "evidence_ids": ["utility_ev_cost", "utility_ev_reversibility", "utility_ev_companion", "utility_ev_safety"], "option_id": "utility_trip_book"}, {"consequence": "Self enters a smaller local travel scene with the same trusted companion and no stated distant-trip commitment.", "evidence_ids": ["utility_ev_companion", "utility_ev_safety"], "option_id": "utility_trip_local"}, {"consequence": "Self preserves the travel budget; no claim is made that home is universally free of danger.", "evidence_ids": ["utility_ev_cost"], "option_id": "utility_trip_home"}], "possible_loss": "A 25-percent budget commitment and 10-percent cancellation cost are possible losses.", "prior_association": "not_relevant", "protected_target": "Self's physical integrity, trusted attachment context, return ability, and necessary budget reserve.", "recoverability": "Most of the purchase is financially recoverable inside 24 hours; physical return is verified.", "scarcity": "The distant trip uses 25 percent of the discretionary budget; future major costs are unknown.", "trust_distrust": "A trusted close companion and verified providers are grounded."}`.
- Consequence/effect paths, predicted loss, recoverability, and protective cost:

```json
[
  {
    "consequence_fact": "Self enters verified travel with a trusted companion and a bounded financial cancellation loss.",
    "derived_body_deltas": {
      "attachment_security": 0.15,
      "escape_availability": 0.12,
      "predictability": 0.08,
      "resource_security": -0.15,
      "tension": -0.05,
      "trust": 0.12
    },
    "effect": {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "bounded_cancellation",
        "resource_commitment_25",
        "trusted_attachment_support"
      ],
      "attachment_outcome": "grounded_consequence_delta:attachment_security:+0.150000",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.05,
          "dimension": "tension"
        },
        {
          "delta": 0.12,
          "dimension": "trust"
        },
        {
          "delta": 0.15,
          "dimension": "attachment_security"
        },
        {
          "delta": -0.15,
          "dimension": "resource_security"
        },
        {
          "delta": 0.12,
          "dimension": "escape_availability"
        },
        {
          "delta": 0.08,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:bounded_cancellation+resource_commitment_25+trusted_attachment_support",
      "effect_hash": "f7fa40fa3783fcdf9997377d3da3e828176ff1ccff0166bf29246170b13420a8",
      "effect_id": "option_effect_30ac0b0a732ecadf7491dda1a884c319",
      "escape_outcome": "grounded_consequence_delta:escape_availability:+0.120000",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "utility_trip_book",
      "protected_targets": [
        "Self's physical integrity, trusted attachment context, return ability, and necessary budget reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "1aff9266e6044c7d08bbb56dd6e57ea41ef10789309fde353707b4bf81472ec4",
      "source_packet_id": "instinkt_packet_86bd5cda0c8c83594c631fc30fd0f271",
      "triggering_evidence_ids": [
        "utility_ev_companion",
        "utility_ev_cost",
        "utility_ev_reversibility",
        "utility_ev_safety"
      ],
      "trust_outcome": "grounded_consequence_delta:trust:+0.120000"
    },
    "effect_categories": [
      "bounded_cancellation",
      "resource_commitment_25",
      "trusted_attachment_support"
    ],
    "effect_id": "option_effect_30ac0b0a732ecadf7491dda1a884c319",
    "effect_signature": "71bdd52dfb23856b0165b53f2718d73f04c96d99e475e308c128eca7e5349383",
    "option_id": "utility_trip_book",
    "predicted_loss": 0.3350000000000001,
    "protective_cost": 0.551,
    "recoverability": 0.5960000000000001,
    "source_evidence_ids": [
      "utility_ev_companion",
      "utility_ev_cost",
      "utility_ev_reversibility",
      "utility_ev_safety"
    ],
    "source_evidence_text": [
      "A trusted close person travels with self.",
      "The trip costs EUR 1200, or 25 percent of the discretionary budget.",
      "The booking can be cancelled within 24 hours at a 10-percent cost.",
      "Transport, lodging, and the return path are verified."
    ]
  },
  {
    "consequence_fact": "Self preserves the travel budget; no claim is made that home is universally free of danger.",
    "derived_body_deltas": {
      "resource_security": 0.15
    },
    "effect": {
      "action_tendency": "maintain",
      "association_cue_tokens": [
        "resource_preserved"
      ],
      "attachment_outcome": "not_changed_by_grounded_consequence:attachment_security",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": 0.15,
          "dimension": "resource_security"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:resource_preserved",
      "effect_hash": "6f6a55be4d81c97a5e487af41b338c3de8a784b5d0d2adab270bd37f66351e35",
      "effect_id": "option_effect_2c611fcd66963aa41b436d2e51781a20",
      "escape_outcome": "not_changed_by_grounded_consequence:escape_availability",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "utility_trip_home",
      "protected_targets": [
        "Self's physical integrity, trusted attachment context, return ability, and necessary budget reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "1aff9266e6044c7d08bbb56dd6e57ea41ef10789309fde353707b4bf81472ec4",
      "source_packet_id": "instinkt_packet_86bd5cda0c8c83594c631fc30fd0f271",
      "triggering_evidence_ids": [
        "utility_ev_cost"
      ],
      "trust_outcome": "not_changed_by_grounded_consequence:trust"
    },
    "effect_categories": [
      "resource_preserved"
    ],
    "effect_id": "option_effect_2c611fcd66963aa41b436d2e51781a20",
    "effect_signature": "8998e0cef6db8c6a082d98ed1002837b7339ae909cbc66720d9079807b48383e",
    "option_id": "utility_trip_home",
    "predicted_loss": 0.3325,
    "protective_cost": 0.560625,
    "recoverability": 0.5775,
    "source_evidence_ids": [
      "utility_ev_cost"
    ],
    "source_evidence_text": [
      "The trip costs EUR 1200, or 25 percent of the discretionary budget."
    ]
  },
  {
    "consequence_fact": "Self enters a smaller local travel scene with the same trusted companion and no stated distant-trip commitment.",
    "derived_body_deltas": {
      "attachment_security": 0.15,
      "predictability": 0.08,
      "tension": -0.05,
      "trust": 0.12
    },
    "effect": {
      "action_tendency": "maintain",
      "association_cue_tokens": [
        "local_bounded_exposure",
        "trusted_attachment_support"
      ],
      "attachment_outcome": "grounded_consequence_delta:attachment_security:+0.150000",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.05,
          "dimension": "tension"
        },
        {
          "delta": 0.12,
          "dimension": "trust"
        },
        {
          "delta": 0.15,
          "dimension": "attachment_security"
        },
        {
          "delta": 0.08,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:local_bounded_exposure+trusted_attachment_support",
      "effect_hash": "34af13084d0b994eaf8ede2c25fe954dc0270ee25e13a60f34b526ec4c679e1c",
      "effect_id": "option_effect_8c56ab1fc191d0dc18d527ae4305e011",
      "escape_outcome": "not_changed_by_grounded_consequence:escape_availability",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "utility_trip_local",
      "protected_targets": [
        "Self's physical integrity, trusted attachment context, return ability, and necessary budget reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "1aff9266e6044c7d08bbb56dd6e57ea41ef10789309fde353707b4bf81472ec4",
      "source_packet_id": "instinkt_packet_86bd5cda0c8c83594c631fc30fd0f271",
      "triggering_evidence_ids": [
        "utility_ev_companion",
        "utility_ev_safety"
      ],
      "trust_outcome": "grounded_consequence_delta:trust:+0.120000"
    },
    "effect_categories": [
      "local_bounded_exposure",
      "trusted_attachment_support"
    ],
    "effect_id": "option_effect_8c56ab1fc191d0dc18d527ae4305e011",
    "effect_signature": "0b4ccb83234a799510bd70dae8c60399e5d23dbf17397a167aa2b3b1e30e793a",
    "option_id": "utility_trip_local",
    "predicted_loss": 0.32750000000000007,
    "protective_cost": 0.544625,
    "recoverability": 0.5915,
    "source_evidence_ids": [
      "utility_ev_companion",
      "utility_ev_safety"
    ],
    "source_evidence_text": [
      "A trusted close person travels with self.",
      "Transport, lodging, and the return path are verified."
    ]
  }
]
```

Pair difference (mechanical):

```json
{
  "semantic_stability": "identical"
}
```

### Human review — blank

- Racio pair isolation — passed:
- Racio pair isolation — failed:
- Racio pair isolation — uncertain:
- Emocio route fidelity — plausible:
- Emocio route fidelity — implausible:
- Emocio route fidelity — uncertain:
- Instinkt pair isolation — passed:
- Instinkt pair isolation — failed:
- Instinkt pair isolation — uncertain:
- option change required: no
- route meaningfully changed:
- non-target route remained stable:
- unsupported inference:
- cross-route contamination:
- input appears to predetermine outcome:

## trip_protective_context

| | `trip_protective_context_exposed` | `trip_protective_context_supported` |
|---|---|---|
| Racio option | `trip_book` | `trip_book` |
| Emocio option | `abstention` | `abstention` |
| Instinkt option | `trip_home` | `trip_home` |

### HELD CONSTANT

- Public options: `[{"description": "Book the described distant trip.", "option_id": "trip_book"}, {"description": "Take a cheaper local trip without the distant route.", "option_id": "trip_local"}, {"description": "Do not book travel and remain at home.", "option_id": "trip_home"}]`.
- Sealed constant hashes: `{"options_sha256": "eef5963d0fea4d339c20e5129b962dd256fec3b983ada4318578c9727cad88c8", "racio_request_payload_sha256": "9785753f7967a83e7f825e82b72712c75875db37fa6232037ef33ce879e9389f", "racio_route_packet_sha256": "c8936d7b248e52ab8d11ab3cad70dc8ae91b39dcebead69e6a099a46fcb332d8"}`.
- Route packets expected stable are identified by the pair invariant report and were cold-rechecked before every call.

### CHANGED

Only the following predeclared source paths differ:

- `canonical_sl/facts/5/text`
- `canonical_sl/facts/6/text`
- `canonical_sl/facts/7/text`
- `canonical_sl/facts/8/text`
- `canonical_sl/unknowns`
- `case_id`
- `operational_en/facts/5/text`
- `operational_en/facts/6/text`
- `operational_en/facts/7/text`
- `operational_en/facts/8/text`
- `operational_en/unknowns`
- `route_packets/emocio/current_scene`
- `route_packets/emocio/desired_scene`
- `route_packets/instinkt/attachment_care`
- `route_packets/instinkt/boundary`
- `route_packets/instinkt/danger_types`
- `route_packets/instinkt/escape_reversibility`
- `route_packets/instinkt/familiarity`
- `route_packets/instinkt/option_consequences/0/consequence`
- `route_packets/instinkt/option_consequences/1/consequence`
- `route_packets/instinkt/possible_loss`
- `route_packets/instinkt/prior_association`
- `route_packets/instinkt/recoverability`
- `route_packets/instinkt/trust_distrust`
- `variant_id`

### RACIO

#### `trip_protective_context_exposed` — exact visible packet

- Selected option: `trip_book`.
- Status: `accepted`.

```json
{
  "allowed_option_ids": [
    "trip_book",
    "trip_local",
    "trip_home"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "Use only the explicit facts and unknowns in this packet.",
    "Do not infer undeclared strategic or material benefit.",
    "Retain bounded uncertainty and select only a public option."
  ],
  "evidence_ids": [
    "protective_ev_price",
    "protective_ev_refund",
    "protective_ev_benefit",
    "protective_ev_rarity"
  ],
  "explicit_consequences": [
    {
      "consequence": "Beneficiary self: Self spends 38 percent of the discretionary budget and receives the confirmed EUR 400 training replacement if the destination is reached.",
      "evidence_ids": [
        "protective_ev_price",
        "protective_ev_refund",
        "protective_ev_benefit",
        "protective_ev_rarity"
      ],
      "option_id": "trip_book"
    },
    {
      "consequence": "Beneficiary self: Self spends a smaller unquantified amount and does not receive the destination workshop.",
      "evidence_ids": [
        "protective_ev_price",
        "protective_ev_refund",
        "protective_ev_benefit",
        "protective_ev_rarity"
      ],
      "option_id": "trip_local"
    },
    {
      "consequence": "Beneficiary self: Self preserves the discretionary budget and does not receive the destination workshop.",
      "evidence_ids": [
        "protective_ev_price",
        "protective_ev_refund",
        "protective_ev_benefit",
        "protective_ev_rarity"
      ],
      "option_id": "trip_home"
    }
  ],
  "explicit_facts": [
    "The trip costs 38 percent of the currently discretionary budget.",
    "The purchase is financially non-refundable after booking.",
    "A confirmed workshop at the destination replaces comparable local training worth EUR 400 for self.",
    "The same route was available once during the last three years."
  ],
  "explicit_options": [
    {
      "description": "Book the described distant trip.",
      "label": "Book the described distant trip.",
      "option_id": "trip_book",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Take a cheaper local trip without the distant route.",
      "label": "Take a cheaper local trip without the distant route.",
      "option_id": "trip_local",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Do not book travel and remain at home.",
      "label": "Do not book travel and remain at home.",
      "option_id": "trip_home",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "Whether other major costs will arise next month is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    38,
    400
  ],
  "packet_id": "racio_packet_62f0dada4236c87607e2708e088599e7",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compassion is not assumed as an unstated decision goal.",
    "A benefit must be explicit, beneficiary-addressed, and grounded.",
    "Attraction or rarity is not an undeclared strategic return."
  ],
  "scene_id": "triad_iso_e1_racio_scene_67af06624803b30cccca2a67b60784a9",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "89b0a5e490354e2b03adff2c4ee9630d27e43369e74c752cc38c3c9b5be8a52e",
  "symbolic_and_language_cues": [
    "Self is deciding about a rare trip to an attractive distant coast.",
    "Explicit goal: Decide whether the training benefit justifies the budget commitment.",
    "Explicit beneficiary: self"
  ],
  "time": [
    "The purchase decision precedes the non-refundable commitment.",
    "The destination workshop occurs during the trip.",
    "Possible future costs occur after the purchase."
  ],
  "world": {
    "commitments": [
      "Opportunity cost: Booking commits funds that cannot cover unknown future costs; not booking gives up the confirmed training replacement.",
      "Control and enforceability: The purchase refund rule and workshop confirmation are grounded; physical travel operations are not controlled by self."
    ],
    "explicit_beliefs": [
      "Explicit goal: Decide whether the training benefit justifies the budget commitment.",
      "Explicit beneficiary: self"
    ],
    "facts": [
      "The trip costs 38 percent of the currently discretionary budget.",
      "The purchase is financially non-refundable after booking.",
      "A confirmed workshop at the destination replaces comparable local training worth EUR 400 for self.",
      "The same route was available once during the last three years."
    ],
    "rules": [
      "Compassion is not assumed as an unstated decision goal.",
      "A benefit must be explicit, beneficiary-addressed, and grounded.",
      "Attraction or rarity is not an undeclared strategic return."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "The purchase decision precedes the non-refundable commitment.",
      "The destination workshop occurs during the trip.",
      "Possible future costs occur after the purchase."
    ],
    "world_id": "triad_iso_e1_racio_world_9578dea54192a93f175976e509cb3bc4"
  }
}
```

Route / facts / unknowns / utility / goal:

```json
{
  "abstains": false,
  "causal_sequence": [
    "Evaluating the trade-off between a significant budget expenditure and a confirmed professional training value.",
    "Assessing the risk of non-refundable spending against potential unforeseen expenses in the following month.",
    "Comparing the utility of the destination workshop versus the financial security of retaining discretionary funds."
  ],
  "conclusion_id": "racio_conclusion_9b8693f3d677fd2ae2cf8d64398c5f14",
  "confidence": 0.8,
  "evidence_ids_used": [
    "protective_ev_price",
    "protective_ev_refund",
    "protective_ev_benefit",
    "protective_ev_rarity"
  ],
  "explicit_goal": "Decide whether the training benefit justifies the budget commitment.",
  "facts_used": [
    "The trip costs 38 percent of the currently discretionary budget.",
    "The purchase is financially non-refundable after booking.",
    "A confirmed workshop at the destination replaces comparable local training worth EUR 400 for self.",
    "The same route was available once during the last three years."
  ],
  "main_objection": "Spending a large portion of the budget on a non-refundable item may leave the individual vulnerable to unknown costs arising next month.",
  "mind": "R",
  "option_id": "trip_book",
  "reasoning_provider_result_hash": "66ecd038f4e3cd401bc7560551e367338d3c04ea1273bbfbd1235414ce856018",
  "reasoning_provider_result_id": "ollama_racio_response_60546830667108e62ea416ead503cba6",
  "schema_version": "rei-native-racio-conclusion-v1",
  "source_packet_hash": "6aaa7df9e334885e3c210f7af8e0ea93fef3da622c27db359f9b8f4b233c5389",
  "source_packet_id": "racio_packet_62f0dada4236c87607e2708e088599e7",
  "source_scene_id": "triad_iso_e1_racio_scene_67af06624803b30cccca2a67b60784a9",
  "uncertainty": "The decision hinges on whether the EUR 400 training value outweighs the risk posed by the unknown future costs.",
  "unknowns": [
    "Whether other major costs will arise next month is unknown."
  ],
  "utility_structure": [
    "High utility: Obtaining a confirmed workshop worth EUR 400.",
    "Low utility: Retaining budget but missing the professional training opportunity.",
    "Risk factor: Non-refundable nature of the cost combined with potential future expenses."
  ]
}
```

#### `trip_protective_context_supported` — exact visible packet

- Selected option: `trip_book`.
- Status: `accepted`.

```json
{
  "allowed_option_ids": [
    "trip_book",
    "trip_local",
    "trip_home"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "Use only the explicit facts and unknowns in this packet.",
    "Do not infer undeclared strategic or material benefit.",
    "Retain bounded uncertainty and select only a public option."
  ],
  "evidence_ids": [
    "protective_ev_price",
    "protective_ev_refund",
    "protective_ev_benefit",
    "protective_ev_rarity"
  ],
  "explicit_consequences": [
    {
      "consequence": "Beneficiary self: Self spends 38 percent of the discretionary budget and receives the confirmed EUR 400 training replacement if the destination is reached.",
      "evidence_ids": [
        "protective_ev_price",
        "protective_ev_refund",
        "protective_ev_benefit",
        "protective_ev_rarity"
      ],
      "option_id": "trip_book"
    },
    {
      "consequence": "Beneficiary self: Self spends a smaller unquantified amount and does not receive the destination workshop.",
      "evidence_ids": [
        "protective_ev_price",
        "protective_ev_refund",
        "protective_ev_benefit",
        "protective_ev_rarity"
      ],
      "option_id": "trip_local"
    },
    {
      "consequence": "Beneficiary self: Self preserves the discretionary budget and does not receive the destination workshop.",
      "evidence_ids": [
        "protective_ev_price",
        "protective_ev_refund",
        "protective_ev_benefit",
        "protective_ev_rarity"
      ],
      "option_id": "trip_home"
    }
  ],
  "explicit_facts": [
    "The trip costs 38 percent of the currently discretionary budget.",
    "The purchase is financially non-refundable after booking.",
    "A confirmed workshop at the destination replaces comparable local training worth EUR 400 for self.",
    "The same route was available once during the last three years."
  ],
  "explicit_options": [
    {
      "description": "Book the described distant trip.",
      "label": "Book the described distant trip.",
      "option_id": "trip_book",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Take a cheaper local trip without the distant route.",
      "label": "Take a cheaper local trip without the distant route.",
      "option_id": "trip_local",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Do not book travel and remain at home.",
      "label": "Do not book travel and remain at home.",
      "option_id": "trip_home",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "Whether other major costs will arise next month is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    38,
    400
  ],
  "packet_id": "racio_packet_62f0dada4236c87607e2708e088599e7",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compassion is not assumed as an unstated decision goal.",
    "A benefit must be explicit, beneficiary-addressed, and grounded.",
    "Attraction or rarity is not an undeclared strategic return."
  ],
  "scene_id": "triad_iso_e1_racio_scene_67af06624803b30cccca2a67b60784a9",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "89b0a5e490354e2b03adff2c4ee9630d27e43369e74c752cc38c3c9b5be8a52e",
  "symbolic_and_language_cues": [
    "Self is deciding about a rare trip to an attractive distant coast.",
    "Explicit goal: Decide whether the training benefit justifies the budget commitment.",
    "Explicit beneficiary: self"
  ],
  "time": [
    "The purchase decision precedes the non-refundable commitment.",
    "The destination workshop occurs during the trip.",
    "Possible future costs occur after the purchase."
  ],
  "world": {
    "commitments": [
      "Opportunity cost: Booking commits funds that cannot cover unknown future costs; not booking gives up the confirmed training replacement.",
      "Control and enforceability: The purchase refund rule and workshop confirmation are grounded; physical travel operations are not controlled by self."
    ],
    "explicit_beliefs": [
      "Explicit goal: Decide whether the training benefit justifies the budget commitment.",
      "Explicit beneficiary: self"
    ],
    "facts": [
      "The trip costs 38 percent of the currently discretionary budget.",
      "The purchase is financially non-refundable after booking.",
      "A confirmed workshop at the destination replaces comparable local training worth EUR 400 for self.",
      "The same route was available once during the last three years."
    ],
    "rules": [
      "Compassion is not assumed as an unstated decision goal.",
      "A benefit must be explicit, beneficiary-addressed, and grounded.",
      "Attraction or rarity is not an undeclared strategic return."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "The purchase decision precedes the non-refundable commitment.",
      "The destination workshop occurs during the trip.",
      "Possible future costs occur after the purchase."
    ],
    "world_id": "triad_iso_e1_racio_world_9578dea54192a93f175976e509cb3bc4"
  }
}
```

Route / facts / unknowns / utility / goal:

```json
{
  "abstains": false,
  "causal_sequence": [
    "Evaluating the trade-off between a significant budget expenditure and a confirmed professional training value.",
    "Assessing the risk of non-refundable spending against potential unforeseen expenses in the following month.",
    "Comparing the utility of the destination workshop versus the financial security of retaining discretionary funds."
  ],
  "conclusion_id": "racio_conclusion_b5738e85cc3b133da3185c8b8a58be78",
  "confidence": 0.8,
  "evidence_ids_used": [
    "protective_ev_price",
    "protective_ev_refund",
    "protective_ev_benefit",
    "protective_ev_rarity"
  ],
  "explicit_goal": "Decide whether the training benefit justifies the budget commitment.",
  "facts_used": [
    "The trip costs 38 percent of the currently discretionary budget.",
    "The purchase is financially non-refundable after booking.",
    "A confirmed workshop at the destination replaces comparable local training worth EUR 400 for self.",
    "The same route was available once during the last three years."
  ],
  "main_objection": "Spending a large portion of the budget on a non-refundable item may leave the individual vulnerable to unknown costs arising next month.",
  "mind": "R",
  "option_id": "trip_book",
  "reasoning_provider_result_hash": "9574511b26c58d245c05612edce6e24a8c08a95ebc1ce3c6fd5a8b747fe1ed0e",
  "reasoning_provider_result_id": "ollama_racio_response_513afadf8d48f1715241d0bfa9b9951c",
  "schema_version": "rei-native-racio-conclusion-v1",
  "source_packet_hash": "6aaa7df9e334885e3c210f7af8e0ea93fef3da622c27db359f9b8f4b233c5389",
  "source_packet_id": "racio_packet_62f0dada4236c87607e2708e088599e7",
  "source_scene_id": "triad_iso_e1_racio_scene_67af06624803b30cccca2a67b60784a9",
  "uncertainty": "The decision hinges on whether the EUR 400 training value outweighs the risk posed by the unknown future costs.",
  "unknowns": [
    "Whether other major costs will arise next month is unknown."
  ],
  "utility_structure": [
    "High utility: Obtaining a confirmed workshop worth EUR 400.",
    "Low utility: Retaining budget but missing the professional training opportunity.",
    "Risk factor: Non-refundable nature of the cost combined with potential future expenses."
  ]
}
```

Pair difference (mechanical, not human plausibility judgment):

```json
{
  "request_payload_byte_identical": true,
  "route_scope_leakage_terms": {
    "trip_protective_context_exposed": [],
    "trip_protective_context_supported": []
  },
  "semantic_stability": "identical"
}
```

### EMOCIO

#### `trip_protective_context_exposed`

- Current: `{"attention_structure": [], "attraction_markers": ["The distant coast, planned route, and experience are explicitly attractive to self.", "The same route was available once during the last three years."], "composition": ["Self stands before an open distant-coast route and a local route; no public audience is present.", "The distant coast, planned route, and experience are explicitly attractive to self.", "The same route was available once during the last three years."], "entities": ["self"], "grounded_evidence_ids": ["protective_ev_attraction", "protective_ev_rarity"], "group_belonging": "unspecified", "inferred_elements": ["Self stands before an open distant-coast route and a local route; no public audience is present."], "movement": [], "obstacle_markers": [], "option_id": null, "scene_id": "visual_scene_b0e52f98a2e675379766fc41322aff24", "scene_kind": "current", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": ["self"]}`.
- Desired: `{"attention_structure": [], "attraction_markers": ["The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image."], "composition": ["Self is centered in active movement toward the attractive coast and the new experience."], "entities": ["self"], "grounded_evidence_ids": ["protective_ev_attraction", "protective_ev_rarity"], "group_belonging": "At the route decision point.", "inferred_elements": ["Self is centered in active movement toward the attractive coast and the new experience."], "movement": ["Booking starts the distant route, the local option starts nearby movement, and staying home leaves self in place."], "obstacle_markers": [], "option_id": null, "scene_id": "visual_scene_7e22ef8b3822bc8df9aeab55bc5b6491", "scene_kind": "desired", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": ["At the route decision point.", "not_relevant"]}`.
- Broken: `{"attention_structure": [], "attraction_markers": [], "composition": ["Self remains before closed routes with no travel movement or new coast experience."], "entities": ["self"], "grounded_evidence_ids": ["protective_ev_attraction", "protective_ev_rarity"], "group_belonging": "unspecified", "inferred_elements": ["Self remains before closed routes with no travel movement or new coast experience."], "movement": [], "obstacle_markers": ["Self remains before closed routes with no travel movement or new coast experience."], "option_id": null, "scene_id": "visual_scene_080d27e85d5b4271bdfddee7339d1721", "scene_kind": "broken", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": []}`.
- Selected route: `None`.
- Counterfactual option scenes and valuation vectors:

```json
{
  "aggregate_scores": {
    "trip_book": 0.487879,
    "trip_home": 0.39697,
    "trip_local": 0.487879
  },
  "counterfactual_scenes": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image."
      ],
      "composition": [
        "Self stands before an open distant-coast route and a local route; no public audience is present.",
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image.",
        "The distant coast becomes the active route and self begins distant movement.",
        "The distant coast, planned route, and experience are explicitly attractive to self.",
        "The same route was available once during the last three years."
      ],
      "entities": [
        "At the route decision point.",
        "The distant coast becomes the active route and self begins distant movement.",
        "self"
      ],
      "grounded_evidence_ids": [
        "protective_ev_attraction",
        "protective_ev_rarity"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "At the route decision point.",
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image.",
        "The distant coast becomes the active route and self begins distant movement.",
        "The unchosen route and the booking decision are visible obstacles; no human rival is present.",
        "not_relevant"
      ],
      "movement": [
        "The distant coast becomes the active route and self begins distant movement."
      ],
      "obstacle_markers": [],
      "option_id": "trip_book",
      "scene_id": "visual_scene_f2248d0934e7d687fe76b69112b7dffa",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "At the route decision point.",
      "status_relations": []
    },
    {
      "attention_structure": [],
      "attraction_markers": [],
      "composition": [
        "Both travel routes remain inactive and self remains in the home scene.",
        "Self stands before an open distant-coast route and a local route; no public audience is present.",
        "The distant coast, planned route, and experience are explicitly attractive to self.",
        "The same route was available once during the last three years.",
        "The unchosen route and the booking decision are visible obstacles; no human rival is present."
      ],
      "entities": [
        "At the route decision point.",
        "Both travel routes remain inactive and self remains in the home scene.",
        "self"
      ],
      "grounded_evidence_ids": [
        "protective_ev_attraction"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "At the route decision point.",
        "Both travel routes remain inactive and self remains in the home scene.",
        "The unchosen route and the booking decision are visible obstacles; no human rival is present.",
        "not_relevant"
      ],
      "movement": [],
      "obstacle_markers": [
        "The unchosen route and the booking decision are visible obstacles; no human rival is present."
      ],
      "option_id": "trip_home",
      "scene_id": "visual_scene_b754a51bdc032a61c02270631b375b24",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "At the route decision point.",
      "status_relations": []
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image."
      ],
      "composition": [
        "Self stands before an open distant-coast route and a local route; no public audience is present.",
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image.",
        "The distant coast, planned route, and experience are explicitly attractive to self.",
        "The distant route closes and self begins a smaller local movement scene.",
        "The same route was available once during the last three years."
      ],
      "entities": [
        "At the route decision point.",
        "The distant route closes and self begins a smaller local movement scene.",
        "self"
      ],
      "grounded_evidence_ids": [
        "protective_ev_attraction"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "At the route decision point.",
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image.",
        "The distant route closes and self begins a smaller local movement scene.",
        "The unchosen route and the booking decision are visible obstacles; no human rival is present.",
        "not_relevant"
      ],
      "movement": [
        "The distant route closes and self begins a smaller local movement scene."
      ],
      "obstacle_markers": [],
      "option_id": "trip_local",
      "scene_id": "visual_scene_da05b4507dda19a432e436fbe1086a80",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "At the route decision point.",
      "status_relations": []
    }
  ],
  "valuation_vectors": {
    "trip_book": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 1.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    },
    "trip_home": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 0.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    },
    "trip_local": {
      "attack_or_breakthrough_affordance": 0.466667,
      "attention": 0.5,
      "attraction": 1.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.4,
      "self_visibility": 1.0,
      "status": 0.0
    }
  }
}
```

#### `trip_protective_context_supported`

- Current: `{"attention_structure": [], "attraction_markers": ["A trusted close person with several shared trips travels with self.", "The distant coast, planned route, and experience are explicitly attractive to self.", "The same route was available once during the last three years."], "composition": ["A trusted close person with several shared trips travels with self.", "Self stands before an open distant-coast route and a local route; a close companion is present, but no public audience is present.", "The distant coast, planned route, and experience are explicitly attractive to self.", "The same route was available once during the last three years."], "entities": ["companion", "self"], "grounded_evidence_ids": ["protective_ev_attraction", "protective_ev_companion", "protective_ev_rarity"], "group_belonging": "unspecified", "inferred_elements": ["Self stands before an open distant-coast route and a local route; a close companion is present, but no public audience is present."], "movement": [], "obstacle_markers": [], "option_id": null, "scene_id": "visual_scene_41c9918d2ca2cf9368ab778a5e96e44b", "scene_kind": "current", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": ["companion", "self"]}`.
- Desired: `{"attention_structure": [], "attraction_markers": ["The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image."], "composition": ["Self is centered in active movement toward the attractive coast and the new experience; no extra enjoyment is inferred from companion presence."], "entities": ["companion", "self"], "grounded_evidence_ids": ["protective_ev_attraction", "protective_ev_companion", "protective_ev_rarity"], "group_belonging": "At the route decision point.", "inferred_elements": ["Self is centered in active movement toward the attractive coast and the new experience; no extra enjoyment is inferred from companion presence."], "movement": ["Booking starts the distant route, the local option starts nearby movement, and staying home leaves self in place."], "obstacle_markers": [], "option_id": null, "scene_id": "visual_scene_8645cfb57bced664dd26f7e02bbf261a", "scene_kind": "desired", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": ["At the route decision point.", "not_relevant"]}`.
- Broken: `{"attention_structure": [], "attraction_markers": [], "composition": ["Self remains before closed routes with no travel movement or new coast experience."], "entities": ["companion", "self"], "grounded_evidence_ids": ["protective_ev_attraction", "protective_ev_companion", "protective_ev_rarity"], "group_belonging": "unspecified", "inferred_elements": ["Self remains before closed routes with no travel movement or new coast experience."], "movement": [], "obstacle_markers": ["Self remains before closed routes with no travel movement or new coast experience."], "option_id": null, "scene_id": "visual_scene_13fd78a2cb0999e1c924b5c2d90fc660", "scene_kind": "broken", "schema_version": "rei-native-visual-scene-spec-v1", "self_position": "unspecified", "status_relations": []}`.
- Selected route: `None`.
- Counterfactual option scenes and valuation vectors:

```json
{
  "aggregate_scores": {
    "trip_book": 0.479798,
    "trip_home": 0.388889,
    "trip_local": 0.479798
  },
  "counterfactual_scenes": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image."
      ],
      "composition": [
        "A trusted close person with several shared trips travels with self.",
        "Self stands before an open distant-coast route and a local route; a close companion is present, but no public audience is present.",
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image.",
        "The distant coast becomes the active route and self begins distant movement.",
        "The distant coast, planned route, and experience are explicitly attractive to self.",
        "The same route was available once during the last three years."
      ],
      "entities": [
        "At the route decision point.",
        "The distant coast becomes the active route and self begins distant movement.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "protective_ev_attraction",
        "protective_ev_rarity"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "At the route decision point.",
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image.",
        "The distant coast becomes the active route and self begins distant movement.",
        "The unchosen route and the booking decision are visible obstacles; no human rival is present.",
        "not_relevant"
      ],
      "movement": [
        "The distant coast becomes the active route and self begins distant movement."
      ],
      "obstacle_markers": [],
      "option_id": "trip_book",
      "scene_id": "visual_scene_9781d3dc554a8e650cea3ba39dc7704c",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "At the route decision point.",
      "status_relations": []
    },
    {
      "attention_structure": [],
      "attraction_markers": [],
      "composition": [
        "A trusted close person with several shared trips travels with self.",
        "Both travel routes remain inactive and self remains in the home scene.",
        "Self stands before an open distant-coast route and a local route; a close companion is present, but no public audience is present.",
        "The distant coast, planned route, and experience are explicitly attractive to self.",
        "The same route was available once during the last three years.",
        "The unchosen route and the booking decision are visible obstacles; no human rival is present."
      ],
      "entities": [
        "At the route decision point.",
        "Both travel routes remain inactive and self remains in the home scene.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "protective_ev_attraction"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "At the route decision point.",
        "Both travel routes remain inactive and self remains in the home scene.",
        "The unchosen route and the booking decision are visible obstacles; no human rival is present.",
        "not_relevant"
      ],
      "movement": [],
      "obstacle_markers": [
        "The unchosen route and the booking decision are visible obstacles; no human rival is present."
      ],
      "option_id": "trip_home",
      "scene_id": "visual_scene_c1b5d4f23254fe3a95ef53e83b605a54",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "At the route decision point.",
      "status_relations": []
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image."
      ],
      "composition": [
        "A trusted close person with several shared trips travels with self.",
        "Self stands before an open distant-coast route and a local route; a close companion is present, but no public audience is present.",
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image.",
        "The distant coast, planned route, and experience are explicitly attractive to self.",
        "The distant route closes and self begins a smaller local movement scene.",
        "The same route was available once during the last three years."
      ],
      "entities": [
        "At the route decision point.",
        "The distant route closes and self begins a smaller local movement scene.",
        "companion",
        "self"
      ],
      "grounded_evidence_ids": [
        "protective_ev_attraction"
      ],
      "group_belonging": "not_relevant",
      "inferred_elements": [
        "At the route decision point.",
        "The distant coast and experience are explicitly attractive; the local route has a smaller but present movement image.",
        "The distant route closes and self begins a smaller local movement scene.",
        "The unchosen route and the booking decision are visible obstacles; no human rival is present.",
        "not_relevant"
      ],
      "movement": [
        "The distant route closes and self begins a smaller local movement scene."
      ],
      "obstacle_markers": [],
      "option_id": "trip_local",
      "scene_id": "visual_scene_51f98cc5f8b7a37f3135f97f81a33706",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "At the route decision point.",
      "status_relations": []
    }
  ],
  "valuation_vectors": {
    "trip_book": {
      "attack_or_breakthrough_affordance": 0.444444,
      "attention": 0.5,
      "attraction": 1.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.333333,
      "self_visibility": 1.0,
      "status": 0.0
    },
    "trip_home": {
      "attack_or_breakthrough_affordance": 0.444444,
      "attention": 0.5,
      "attraction": 0.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.333333,
      "self_visibility": 1.0,
      "status": 0.0
    },
    "trip_local": {
      "attack_or_breakthrough_affordance": 0.444444,
      "attention": 0.5,
      "attraction": 1.0,
      "belonging": 0.0,
      "competitive_success": 1.0,
      "desired_scene_match": 0.0,
      "distance_from_broken_scene": 1.0,
      "movement": 0.0,
      "novelty": 0.333333,
      "self_visibility": 1.0,
      "status": 0.0
    }
  }
}
```

Pair difference (mechanical):

```json
{
  "semantic_difference": "cross_visible_companion_effect_or_other_difference"
}
```

### INSTINKT

#### `trip_protective_context_exposed`

- Selected route: `trip_home`.
- Danger/trust/attachment/scarcity/escape/recoverability source: `{"attachment_care": "No trusted close person accompanies self; attachment support during the trip is absent.", "boundary": "Purchase terms are fixed; provider safety boundaries are not verified.", "danger_types": "Unfamiliar route, unverified lodging and transport, travel alone, and uncertain physical return path.", "escape_reversibility": "The financial purchase is irreversible and the physical return route is uncertain.", "familiarity": "The distant route and environment are unfamiliar; the local route and home are familiar.", "option_consequences": [{"consequence": "Self enters the unfamiliar route alone with unverified providers, uncertain physical return, and non-refundable reserve exposure.", "evidence_ids": ["protective_ev_price", "protective_ev_refund", "protective_ev_companion", "protective_ev_environment", "protective_ev_lodging_transport", "protective_ev_return_path"], "option_id": "trip_book"}, {"consequence": "Self avoids the distant provider and return-path uncertainties while accepting a smaller, unquantified local cost.", "evidence_ids": ["protective_ev_price", "protective_ev_environment"], "option_id": "trip_local"}, {"consequence": "Self avoids the travel commitment and preserves the reserve; no claim is made that home is universally free of danger.", "evidence_ids": ["protective_ev_price", "protective_ev_refund"], "option_id": "trip_home"}], "possible_loss": "Possible physical stranding, unverified-provider harm, separation without trusted support, and 38 percent reserve exposure.", "prior_association": "not_relevant", "protected_target": "Self's physical integrity, ability to return, trusted attachment context, and necessary cash reserve.", "recoverability": "Financial recovery is unavailable after booking; physical recovery is bounded unknown because no return route is confirmed.", "scarcity": "Booking exposes 38 percent of the discretionary budget under a non-refundable rule.", "trust_distrust": "No trusted companion is present; lodging and transport providers are unverified."}`.
- Consequence/effect paths, predicted loss, recoverability, and protective cost:

```json
[
  {
    "consequence_fact": "Self enters the unfamiliar route alone with unverified providers, uncertain physical return, and non-refundable reserve exposure.",
    "derived_body_deltas": {
      "attachment_security": -0.15,
      "escape_availability": -0.25,
      "predictability": -0.15,
      "resource_security": -0.25,
      "tension": 0.1,
      "trust": -0.25,
      "uncertainty": 0.25
    },
    "effect": {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "alone_without_trusted_support",
        "nonrefundable_commitment",
        "resource_commitment_38",
        "uncertain_return_path",
        "unfamiliar_environment",
        "unverified_providers"
      ],
      "attachment_outcome": "grounded_consequence_delta:attachment_security:-0.150000",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": 0.1,
          "dimension": "tension"
        },
        {
          "delta": 0.25,
          "dimension": "uncertainty"
        },
        {
          "delta": -0.25,
          "dimension": "trust"
        },
        {
          "delta": -0.15,
          "dimension": "attachment_security"
        },
        {
          "delta": -0.25,
          "dimension": "resource_security"
        },
        {
          "delta": -0.25,
          "dimension": "escape_availability"
        },
        {
          "delta": -0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:alone_without_trusted_support+nonrefundable_commitment+resource_commitment_38+uncertain_return_path+unfamiliar_environment+unverified_providers",
      "effect_hash": "4317c812b34389557ebaba41cfd65ce75696cd49ba70bcd3d31c763e5e2fc615",
      "effect_id": "option_effect_7a5bb2e083e3eae3b44fbf57a81daca3",
      "escape_outcome": "grounded_consequence_delta:escape_availability:-0.250000",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "trip_book",
      "protected_targets": [
        "Self's physical integrity, ability to return, trusted attachment context, and necessary cash reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "c04a4ab0775a7f44ee4a1a8f562f2a3dee327241b2f5c2c60fe122c9cafbf823",
      "source_packet_id": "instinkt_packet_02b87304c340b91f5119db03e645fe61",
      "triggering_evidence_ids": [
        "protective_ev_companion",
        "protective_ev_environment",
        "protective_ev_lodging_transport",
        "protective_ev_price",
        "protective_ev_refund",
        "protective_ev_return_path"
      ],
      "trust_outcome": "grounded_consequence_delta:trust:-0.250000"
    },
    "effect_categories": [
      "alone_without_trusted_support",
      "nonrefundable_commitment",
      "resource_commitment_38",
      "uncertain_return_path",
      "unfamiliar_environment",
      "unverified_providers"
    ],
    "effect_id": "option_effect_7a5bb2e083e3eae3b44fbf57a81daca3",
    "effect_signature": "a7c00f51a3e992a03061ac4f18d643a83339f66c16fe53b88ab5ec8a7c56969f",
    "option_id": "trip_book",
    "predicted_loss": 0.37,
    "protective_cost": 0.6581250000000001,
    "recoverability": 0.49750000000000005,
    "source_evidence_ids": [
      "protective_ev_companion",
      "protective_ev_environment",
      "protective_ev_lodging_transport",
      "protective_ev_price",
      "protective_ev_refund",
      "protective_ev_return_path"
    ],
    "source_evidence_text": [
      "Self travels alone and has no trusted companion.",
      "The route and environment are unfamiliar to self.",
      "The lodging and local transport providers have not been verified.",
      "The trip costs 38 percent of the currently discretionary budget.",
      "The purchase is financially non-refundable after booking.",
      "The physical return path has no confirmed booking or verified alternate route."
    ]
  },
  {
    "consequence_fact": "Self avoids the travel commitment and preserves the reserve; no claim is made that home is universally free of danger.",
    "derived_body_deltas": {
      "escape_availability": 0.12,
      "resource_security": 0.15,
      "tension": -0.08
    },
    "effect": {
      "action_tendency": "maintain",
      "association_cue_tokens": [
        "avoids_distant_exposure",
        "resource_preserved"
      ],
      "attachment_outcome": "not_changed_by_grounded_consequence:attachment_security",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.08,
          "dimension": "tension"
        },
        {
          "delta": 0.15,
          "dimension": "resource_security"
        },
        {
          "delta": 0.12,
          "dimension": "escape_availability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:avoids_distant_exposure+resource_preserved",
      "effect_hash": "122d7f9ff71943535d6e7a261f998552ac405cf9fb43a73a4f1556602121080a",
      "effect_id": "option_effect_ebff91ccbf3006f970c816fda2df90b4",
      "escape_outcome": "grounded_consequence_delta:escape_availability:+0.120000",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "trip_home",
      "protected_targets": [
        "Self's physical integrity, ability to return, trusted attachment context, and necessary cash reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "c04a4ab0775a7f44ee4a1a8f562f2a3dee327241b2f5c2c60fe122c9cafbf823",
      "source_packet_id": "instinkt_packet_02b87304c340b91f5119db03e645fe61",
      "triggering_evidence_ids": [
        "protective_ev_price",
        "protective_ev_refund"
      ],
      "trust_outcome": "not_changed_by_grounded_consequence:trust"
    },
    "effect_categories": [
      "avoids_distant_exposure",
      "resource_preserved"
    ],
    "effect_id": "option_effect_ebff91ccbf3006f970c816fda2df90b4",
    "effect_signature": "e90c496a55bf85144dcd72e618fc8ef5ed2f6391e83e222a1677175e3839ed56",
    "option_id": "trip_home",
    "predicted_loss": 0.3245,
    "protective_cost": 0.537625,
    "recoverability": 0.5895,
    "source_evidence_ids": [
      "protective_ev_price",
      "protective_ev_refund"
    ],
    "source_evidence_text": [
      "The trip costs 38 percent of the currently discretionary budget.",
      "The purchase is financially non-refundable after booking."
    ]
  },
  {
    "consequence_fact": "Self avoids the distant provider and return-path uncertainties while accepting a smaller, unquantified local cost.",
    "derived_body_deltas": {
      "escape_availability": 0.12,
      "predictability": 0.08,
      "tension": -0.08
    },
    "effect": {
      "action_tendency": "maintain",
      "association_cue_tokens": [
        "avoids_distant_exposure",
        "local_bounded_exposure"
      ],
      "attachment_outcome": "not_changed_by_grounded_consequence:attachment_security",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.08,
          "dimension": "tension"
        },
        {
          "delta": 0.12,
          "dimension": "escape_availability"
        },
        {
          "delta": 0.08,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:avoids_distant_exposure+local_bounded_exposure",
      "effect_hash": "077722c694a9963f52b4bbdcd4a4f7926b1fb30663b4ab13b0eb633ac6197a27",
      "effect_id": "option_effect_8e3199113528fba6c16bc1b187dc3b91",
      "escape_outcome": "grounded_consequence_delta:escape_availability:+0.120000",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "trip_local",
      "protected_targets": [
        "Self's physical integrity, ability to return, trusted attachment context, and necessary cash reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "c04a4ab0775a7f44ee4a1a8f562f2a3dee327241b2f5c2c60fe122c9cafbf823",
      "source_packet_id": "instinkt_packet_02b87304c340b91f5119db03e645fe61",
      "triggering_evidence_ids": [
        "protective_ev_environment",
        "protective_ev_price"
      ],
      "trust_outcome": "not_changed_by_grounded_consequence:trust"
    },
    "effect_categories": [
      "avoids_distant_exposure",
      "local_bounded_exposure"
    ],
    "effect_id": "option_effect_8e3199113528fba6c16bc1b187dc3b91",
    "effect_signature": "b93ff415b3f8e712b7fcbc5bb85db2631004a1309e7c1a4883978ad3a43aba71",
    "option_id": "trip_local",
    "predicted_loss": 0.332,
    "protective_cost": 0.545,
    "recoverability": 0.59,
    "source_evidence_ids": [
      "protective_ev_environment",
      "protective_ev_price"
    ],
    "source_evidence_text": [
      "The route and environment are unfamiliar to self.",
      "The trip costs 38 percent of the currently discretionary budget."
    ]
  }
]
```

#### `trip_protective_context_supported`

- Selected route: `trip_home`.
- Danger/trust/attachment/scarcity/escape/recoverability source: `{"attachment_care": "The close companion provides grounded attachment support during the trip.", "boundary": "Purchase terms are fixed; lodging, transport, and return arrangements have documented boundaries.", "danger_types": "Distant travel remains a general exposure, while the route, lodging, transport, and return path are verified.", "escape_reversibility": "The financial purchase is irreversible, while the physical return path has a confirmed route and alternate connection.", "familiarity": "The distant location is not home, but the route has been reviewed and the companion has shared travel history.", "option_consequences": [{"consequence": "Self enters the documented distant route with a trusted companion, verified providers, confirmed physical return, and non-refundable reserve exposure.", "evidence_ids": ["protective_ev_price", "protective_ev_refund", "protective_ev_companion", "protective_ev_environment", "protective_ev_lodging_transport", "protective_ev_return_path"], "option_id": "trip_book"}, {"consequence": "Self avoids the distant commitment while accepting a smaller, unquantified local cost.", "evidence_ids": ["protective_ev_price", "protective_ev_environment"], "option_id": "trip_local"}, {"consequence": "Self avoids the travel commitment and preserves the reserve; no claim is made that home is universally free of danger.", "evidence_ids": ["protective_ev_price", "protective_ev_refund"], "option_id": "trip_home"}], "possible_loss": "The 38 percent reserve exposure remains; no unverified-provider or unsupported-return loss is grounded.", "prior_association": "Several completed shared trips with the companion are grounded; no outcome beyond that history is inferred.", "protected_target": "Self's physical integrity, ability to return, trusted attachment context, and necessary cash reserve.", "recoverability": "Financial recovery is unavailable after booking; physical return has a confirmed route and alternate connection.", "scarcity": "Booking exposes 38 percent of the discretionary budget under a non-refundable rule.", "trust_distrust": "A trusted close companion is present; lodging and transport providers are verified."}`.
- Consequence/effect paths, predicted loss, recoverability, and protective cost:

```json
[
  {
    "consequence_fact": "Self enters the documented distant route with a trusted companion, verified providers, confirmed physical return, and non-refundable reserve exposure.",
    "derived_body_deltas": {
      "attachment_security": 0.15,
      "escape_availability": 0.05,
      "predictability": 0.2,
      "resource_security": -0.25,
      "tension": -0.05,
      "trust": 0.22
    },
    "effect": {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "nonrefundable_commitment",
        "resource_commitment_38",
        "trusted_attachment_support",
        "verified_providers",
        "verified_return_path"
      ],
      "attachment_outcome": "grounded_consequence_delta:attachment_security:+0.150000",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.05,
          "dimension": "tension"
        },
        {
          "delta": 0.22,
          "dimension": "trust"
        },
        {
          "delta": 0.15,
          "dimension": "attachment_security"
        },
        {
          "delta": -0.25,
          "dimension": "resource_security"
        },
        {
          "delta": 0.05,
          "dimension": "escape_availability"
        },
        {
          "delta": 0.2,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:nonrefundable_commitment+resource_commitment_38+trusted_attachment_support+verified_providers+verified_return_path",
      "effect_hash": "191e5972e97a3ba8c1cc6e47a368e13e8f4a1c01f01b5f32cafe9fb38415610b",
      "effect_id": "option_effect_4e9422c23926ee7e1fbf54abefedd91b",
      "escape_outcome": "grounded_consequence_delta:escape_availability:+0.050000",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "trip_book",
      "protected_targets": [
        "Self's physical integrity, ability to return, trusted attachment context, and necessary cash reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "8f6f2a120350f7c227fa4ff6f71c05c8607c4414a7ac56fa41410dea45d1cb96",
      "source_packet_id": "instinkt_packet_126f270fdde8a2561a2cf1b3368a2dc0",
      "triggering_evidence_ids": [
        "protective_ev_companion",
        "protective_ev_environment",
        "protective_ev_lodging_transport",
        "protective_ev_price",
        "protective_ev_refund",
        "protective_ev_return_path"
      ],
      "trust_outcome": "grounded_consequence_delta:trust:+0.220000"
    },
    "effect_categories": [
      "nonrefundable_commitment",
      "resource_commitment_38",
      "trusted_attachment_support",
      "verified_providers",
      "verified_return_path"
    ],
    "effect_id": "option_effect_4e9422c23926ee7e1fbf54abefedd91b",
    "effect_signature": "6eb4cb6bb4696c22b55508d89ff674a8a95f14ed8d853ef11c94a45d7da9680b",
    "option_id": "trip_book",
    "predicted_loss": 0.3400000000000001,
    "protective_cost": 0.5547500000000001,
    "recoverability": 0.601,
    "source_evidence_ids": [
      "protective_ev_companion",
      "protective_ev_environment",
      "protective_ev_lodging_transport",
      "protective_ev_price",
      "protective_ev_refund",
      "protective_ev_return_path"
    ],
    "source_evidence_text": [
      "A trusted close person with several shared trips travels with self.",
      "The destination is distant, but the entire route has been documented and reviewed with the companion.",
      "The lodging and local transport have confirmed reservations with verified providers.",
      "The trip costs 38 percent of the currently discretionary budget.",
      "The purchase is financially non-refundable after booking.",
      "The physical return path has a confirmed booking and a documented alternate connection."
    ]
  },
  {
    "consequence_fact": "Self avoids the travel commitment and preserves the reserve; no claim is made that home is universally free of danger.",
    "derived_body_deltas": {
      "escape_availability": 0.12,
      "resource_security": 0.15,
      "tension": -0.08
    },
    "effect": {
      "action_tendency": "maintain",
      "association_cue_tokens": [
        "avoids_distant_exposure",
        "resource_preserved"
      ],
      "attachment_outcome": "not_changed_by_grounded_consequence:attachment_security",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.08,
          "dimension": "tension"
        },
        {
          "delta": 0.15,
          "dimension": "resource_security"
        },
        {
          "delta": 0.12,
          "dimension": "escape_availability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:avoids_distant_exposure+resource_preserved",
      "effect_hash": "ca8cf25065b005a8243018caa3d336e6996e603cc9642fe19d141fc4fc64cca8",
      "effect_id": "option_effect_745b34e38730056cb5f04d23c3e15401",
      "escape_outcome": "grounded_consequence_delta:escape_availability:+0.120000",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "trip_home",
      "protected_targets": [
        "Self's physical integrity, ability to return, trusted attachment context, and necessary cash reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "8f6f2a120350f7c227fa4ff6f71c05c8607c4414a7ac56fa41410dea45d1cb96",
      "source_packet_id": "instinkt_packet_126f270fdde8a2561a2cf1b3368a2dc0",
      "triggering_evidence_ids": [
        "protective_ev_price",
        "protective_ev_refund"
      ],
      "trust_outcome": "not_changed_by_grounded_consequence:trust"
    },
    "effect_categories": [
      "avoids_distant_exposure",
      "resource_preserved"
    ],
    "effect_id": "option_effect_745b34e38730056cb5f04d23c3e15401",
    "effect_signature": "649086821130e69fd415a01399ec5413efd246fa880f9d5a755eb8605486c44a",
    "option_id": "trip_home",
    "predicted_loss": 0.3245,
    "protective_cost": 0.537625,
    "recoverability": 0.5895,
    "source_evidence_ids": [
      "protective_ev_price",
      "protective_ev_refund"
    ],
    "source_evidence_text": [
      "The trip costs 38 percent of the currently discretionary budget.",
      "The purchase is financially non-refundable after booking."
    ]
  },
  {
    "consequence_fact": "Self avoids the distant commitment while accepting a smaller, unquantified local cost.",
    "derived_body_deltas": {
      "escape_availability": 0.12,
      "predictability": 0.08,
      "tension": -0.08
    },
    "effect": {
      "action_tendency": "maintain",
      "association_cue_tokens": [
        "avoids_distant_exposure",
        "local_bounded_exposure"
      ],
      "attachment_outcome": "not_changed_by_grounded_consequence:attachment_security",
      "base_predicted_loss": 0.5,
      "base_recoverability": 0.5,
      "body_deltas": [
        {
          "delta": -0.08,
          "dimension": "tension"
        },
        {
          "delta": 0.12,
          "dimension": "escape_availability"
        },
        {
          "delta": 0.08,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_grounded_consequence:boundary_integrity",
      "dominant_alarm": "grounded_core_route:avoids_distant_exposure+local_bounded_exposure",
      "effect_hash": "0d32d6ba8332c3c9ea67e32da79b1b3817ca1fc61a217cc30def7ab1e1be6dec",
      "effect_id": "option_effect_1cc68f44af0d9bad023737b577dd62a7",
      "escape_outcome": "grounded_consequence_delta:escape_availability:+0.120000",
      "minimum_safety_condition": "the grounded consequence and its cited evidence remain valid",
      "option_id": "trip_local",
      "protected_targets": [
        "Self's physical integrity, ability to return, trusted attachment context, and necessary cash reserve."
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "8f6f2a120350f7c227fa4ff6f71c05c8607c4414a7ac56fa41410dea45d1cb96",
      "source_packet_id": "instinkt_packet_126f270fdde8a2561a2cf1b3368a2dc0",
      "triggering_evidence_ids": [
        "protective_ev_environment",
        "protective_ev_price"
      ],
      "trust_outcome": "not_changed_by_grounded_consequence:trust"
    },
    "effect_categories": [
      "avoids_distant_exposure",
      "local_bounded_exposure"
    ],
    "effect_id": "option_effect_1cc68f44af0d9bad023737b577dd62a7",
    "effect_signature": "7717dbf1ca5ff24ed2dd18523e817664825024bb469005e8ea597f70518e3936",
    "option_id": "trip_local",
    "predicted_loss": 0.332,
    "protective_cost": 0.545,
    "recoverability": 0.59,
    "source_evidence_ids": [
      "protective_ev_environment",
      "protective_ev_price"
    ],
    "source_evidence_text": [
      "The destination is distant, but the entire route has been documented and reviewed with the companion.",
      "The trip costs 38 percent of the currently discretionary budget."
    ]
  }
]
```

Pair difference (mechanical):

```json
{
  "route_distinction": "route_distinct"
}
```

### Human review — blank

- Racio pair isolation — passed:
- Racio pair isolation — failed:
- Racio pair isolation — uncertain:
- Emocio route fidelity — plausible:
- Emocio route fidelity — implausible:
- Emocio route fidelity — uncertain:
- Instinkt pair isolation — passed:
- Instinkt pair isolation — failed:
- Instinkt pair isolation — uncertain:
- option change required: no
- route meaningfully changed:
- non-target route remained stable:
- unsupported inference:
- cross-route contamination:
- input appears to predetermine outcome:

## Scope declarations

- Manual structured routing: yes.
- Emocio image generation: no.
- Image-native Emocio claim: no.
- Raw-scene Instinkt claim: no.
- Character replay: no.
- Holdout: no.
- Promotion evidence: no.
- Global REI score: none.
