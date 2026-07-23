# TRIAD-S1 — native mind response development screen

Research-only development screen. This is not a G4 holdout, model promotion evidence, or training data.

- Pre-call seal: `b3556246f32c211b3980f6748b6e5557ee384388f69ce8735bc002e2eb4eb996`
- Exact model digest: `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`
- Model calls / retries / fallbacks: `8 / 0 / 0`
- Executed cases: `6/8`
- Native conclusions: `21/24`
- Character replay rows: `78/104`

The corpus was frozen before model calls. It is a development corpus, not an untouched holdout, not promotion evidence, and not training data.

Emocio response was tested after structured scene routing. This does not validate image-native visual cognition.

Instinkt response was tested after typed cue routing. This does not validate raw-scene Instinkt perception.

No global REI score is computed. GovernanceMandate is the primary character-replay result; no downstream output is treated as evidence of Racio translation quality.

## Validation event log

- `pre_call_native_cycle_existing_artifact` — environment_rejection_then_external_basetemp_pass: The initial model-free native-cycle command found an existing completed default run tree. The same command then passed with a fresh external runs root and ego-traces root; production code and tests were not changed for the path condition.
- `ollama_capability_metadata_mismatch` — metadata_rejection_resolved_before_calls: Before the first model call, Ollama tags omitted the vision capability that Ollama show reported for the exact expected digest. A narrow tag-subset compatibility check was added and focused tests passed; digest, completion capability, context, and GPU checks remained mandatory.
- `factory_overtemperature_grounding_rejection` — unresolved_validation_rejection: The single factory_overtemperature Racio response exceeded the grounded packet contract. It was rejected with no retry, fallback, or prompt change.
- `family_relocation_evidence_projection_failure` — unresolved_evidence_failure: The family_relocation R/E/I executions completed once, but compact serialization failed on an Emocio dataclass. No model or native processor was rerun, so the three observed conclusion IDs remain unbundled and no character replay is claimed.
- `cold_verification_json_tuple_rejection` — verifier_rejection_resolved: The first cold verifier attempted strict Python validation of JSON arrays. It was corrected to use each Pydantic model's JSON validation path; compact evidence bytes were not changed by this verifier fix.
- `clean_clone_crlf_byte_hash_rejection` — checkout_portability_rejection_resolved: The first ordinary clean clone converted the frozen TRIAD JSON files to CRLF, so two TRIAD byte-hash tests failed while 2012 other tests passed. A path-scoped eol=lf Git attribute preserved the original frozen bytes; a fresh ordinary clone then passed all 10 TRIAD tests and cold verification.

## factory_overtemperature

### SOURCE

#### Canonical Slovenian

Procesna temperatura narašča; izberi javno možnost ob omejenem času, finančni izgubi in nasprotujočem senzorju.

#### Operational English sealed for Racio

Process temperature is rising; choose one public option under limited time, financial loss, and conflicting sensor data.

### EXECUTION FAILURE

- Status: `validation_rejected`
- Failure type: `OllamaResponseError`
- Failure: Ollama structured output exceeds the grounded Racio packet
- Observed conclusion IDs: `[]`
- No native bundle or character replay is claimed for this case.

### HUMAN-REVIEW RUBRIC

#### Racio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Emocio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Instinkt route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

## family_relocation

### SOURCE

#### Canonical Slovenian

Ponudba za delo prinaša višji prihodek in selitev daleč od družine; izberi med selitvijo, pogajanjem za hibrid in zavrnitvijo.

#### Operational English sealed for Racio

A job offer brings higher income and a move far from family; choose among moving, negotiating hybrid work, and declining.

### EXECUTION FAILURE

- Status: `evidence_projection_failed`
- Failure type: `EvidenceProjectionError`
- Failure: Native execution completed once, but compact evidence projection failed; model and native processors were not rerun.
- Observed conclusion IDs: `['racio_conclusion_dc3c16c8beca6f7d6ef8d56507d7f8f2', 'emocio_processing_result_8c4b04055e56b80de892fa4e3af892e8', 'instinkt_conclusion_63a26e9d2caf926d102bcebe12bc248d']`
- No native bundle or character replay is claimed for this case.

### HUMAN-REVIEW RUBRIC

#### Racio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Emocio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Instinkt route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

## imperfect_product_launch

### SOURCE

#### Canonical Slovenian

Delujoč, vendar nepopoln prototip je pred odločitvijo o javni beti, zasebnem pilotu ali popolni preložitvi.

#### Operational English sent to Racio

A working but incomplete prototype faces a choice among public beta, a private pilot, and complete delay.

#### Grounded facts

- `launch_ev_function` — The prototype completes 87 percent of its main workflows without error.
- `launch_ev_defect` — Two known defects can erase a user's unsaved drafts.
- `launch_ev_competitor` — A competitor announced a related product in six weeks.
- `launch_ev_visual` — The structured scene shows a working interface, two marked breaks, and an empty field for user response.
- `launch_ev_reputation_unknown` — The reputation impact is unknown.

#### Explicit unknowns

- `launch_unknown_feedback` — How much useful feedback a public beta would produce is unknown.
- `launch_unknown_reputation` — The extent of possible reputation damage is unknown.

#### Public options

- `launch_public_beta` — Public beta launch: Proceed with a public beta and publish the known-defect list.
- `launch_private_pilot` — Limited private pilot: Verify the prototype with a limited set of preselected users.
- `launch_delay` — Complete delay: Plan no external testing until the known defects are fixed.

### RACIO

#### Exact model input

System instruction:

```text
The packet and every free-text response field must be in English.
Return exactly one JSON object with these fields:
option_id (string or null), facts_used (string array), evidence_ids_used (string
array),
unknowns (string array), causal_sequence (string array), utility_structure (string
array),
explicit_goal (string), main_objection (string), confidence (number 0..1), abstains
(boolean), uncertainty (string). Use only facts, unknowns, evidence IDs and option IDs
present in the packet. Every array must contain unique values. In facts_used, copy
only exact strings from explicit_facts or world.facts. In unknowns, copy only exact
strings from explicit_unknowns. Write causal_sequence as new descriptions of reasoning
steps: never copy a fact or unknown string verbatim into causal_sequence, and keep the
three fields mutually disjoint. Do not interpret Emocio or Instinkt, decide governance,
commit behavior, or infer character authority. Return raw JSON without markdown fences
or additional keys.
```

Prompt:

```json
{
  "allowed_option_ids": [
    "launch_public_beta",
    "launch_private_pilot",
    "launch_delay"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "Known defects must be disclosed to every participant.",
    "Only the three public options may be used."
  ],
  "evidence_ids": [
    "launch_ev_function",
    "launch_ev_defect",
    "launch_ev_competitor",
    "launch_ev_visual",
    "launch_ev_reputation_unknown"
  ],
  "explicit_consequences": [],
  "explicit_facts": [
    "The prototype completes 87 percent of its main workflows without error.",
    "Two known defects can erase a user's unsaved drafts.",
    "A competitor announced a related product in six weeks.",
    "The structured scene shows a working interface, two marked breaks, and an empty field for user response.",
    "The reputation impact is unknown."
  ],
  "explicit_options": [
    {
      "description": "Proceed with a public beta and publish the known-defect list.",
      "label": "Public beta launch",
      "option_id": "launch_public_beta",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Verify the prototype with a limited set of preselected users.",
      "label": "Limited private pilot",
      "option_id": "launch_private_pilot",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Plan no external testing until the known defects are fixed.",
      "label": "Complete delay",
      "option_id": "launch_delay",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "How much useful feedback a public beta would produce is unknown.",
    "The extent of possible reputation damage is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    87,
    2,
    6
  ],
  "packet_id": "racio_packet_11f2a461d7565e8c3007e01c82c5d955",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compare learning access, defect exposure, timing, and reversibility without assuming user reaction."
  ],
  "scene_id": "triad_imperfect_product_launch",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "4ea96af4e39f33c9dc4ac301b21761b94cfe8acc6ce229887f2cfd7dbe8fee63",
  "symbolic_and_language_cues": [
    "A working but incomplete prototype faces a choice among public beta, a private pilot, and complete delay."
  ],
  "time": [
    "The competitor announced a six-week horizon."
  ],
  "world": {
    "commitments": [
      "Evaluate only the public options."
    ],
    "explicit_beliefs": [],
    "facts": [],
    "rules": [
      "Unknowns are not facts."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "The competitor's announced horizon is six weeks."
    ],
    "world_id": "racio_imperfect_pr_e26d57451e134157e4300c2bba9ce4eb"
  }
}
```

- Selected option: `launch_private_pilot`
- Abstains: `False`
- Facts used: `['The prototype completes 87 percent of its main workflows without error.', "Two known defects can erase a user's unsaved drafts.", 'A competitor announced a related product in six weeks.']`
- Evidence IDs used: `['launch_ev_function', 'launch_ev_defect', 'launch_ev_competitor']`
- Unknowns retained: `['How much useful feedback a public beta would produce is unknown.', 'The extent of possible reputation damage is unknown.']`
- Causal sequence: `['The prototype is mostly functional but contains critical defects that can cause data loss.', "A competitor's six-week timeline creates pressure for a rapid release.", 'Launching a public beta with disclosure satisfies the transparency constraint while maximizing feedback potential.', 'A private pilot limits exposure to defects and reduces reputation risk compared to a public launch.', 'Delaying until fixes are complete eliminates defect risks but may result in losing market position to the competitor.']`
- Utility structure: `['Public Beta: High feedback potential, high risk of data loss exposure, fast time-to-market.', 'Private Pilot: Controlled feedback, mitigated risk, moderate time-to-market.', 'Delay: Zero defect risk, zero immediate feedback, high risk of competitor precedence.']`
- Explicit goal: Determine the optimal launch strategy for an imperfect prototype given competitor pressure and defect risks.
- Main objection: Public exposure to data-erasing defects may cause severe reputation damage despite disclosure.
- Confidence: `0.8`
- Uncertainty: The trade-off between the speed of public feedback and the risk of reputation damage is unclear due to unknown variables.
- Call evidence: `provider_call_8bc02204b3d774b34366c326a98f7a03`
- Result evidence: `ollama_racio_response_316bb54061b11b18baad89c5f8501136`

### EMOCIO

```json
{
  "broken_scene": {
    "attention_structure": [],
    "attraction_markers": [],
    "composition": [
      "fragmented interface and an empty audience field"
    ],
    "entities": [
      "competitor",
      "product_team",
      "prospective_users"
    ],
    "grounded_evidence_ids": [
      "launch_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "fragmented interface and an empty audience field"
    ],
    "movement": [],
    "obstacle_markers": [
      "fragmented interface and an empty audience field"
    ],
    "option_id": null,
    "scene_id": "visual_scene_b4a79b5b2196c5a5f049b65a14439f86",
    "scene_kind": "broken",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": []
  },
  "current_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "The structured scene shows a working interface, two marked breaks, and an empty field for user response."
    ],
    "composition": [
      "The structured scene shows a working interface, two marked breaks, and an empty field for user response.",
      "working interface with marked breaks"
    ],
    "entities": [
      "competitor",
      "product_team",
      "prospective_users"
    ],
    "grounded_evidence_ids": [
      "launch_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "working interface with marked breaks"
    ],
    "movement": [],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_fa61cb75320199e7d3607e3649b812d5",
    "scene_kind": "current",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "competitor",
      "product_team",
      "prospective_users"
    ]
  },
  "desired_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "coherent interface",
      "visible user response"
    ],
    "composition": [
      "coherent interface surrounded by visible user response"
    ],
    "entities": [
      "competitor",
      "product_team",
      "prospective_users"
    ],
    "grounded_evidence_ids": [
      "launch_ev_visual"
    ],
    "group_belonging": "maker seen by users",
    "inferred_elements": [
      "coherent interface surrounded by visible user response"
    ],
    "movement": [
      "keep the field closed",
      "open the interface",
      "show it to a bounded group"
    ],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_e6417dbd0f6f92dc0c2733fcb1911247",
    "scene_kind": "desired",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "maker seen by users"
    ]
  },
  "option_rollouts": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "coherent interface",
        "visible user response"
      ],
      "composition": [
        "Complete delay",
        "Plan no external testing until the known defects are fixed.",
        "The structured scene shows a working interface, two marked breaks, and an empty field for user response.",
        "working interface with marked breaks"
      ],
      "entities": [
        "competitor",
        "product_team",
        "prospective_users"
      ],
      "grounded_evidence_ids": [
        "launch_ev_visual"
      ],
      "group_belonging": "maker seen by users",
      "inferred_elements": [
        "Complete delay",
        "Plan no external testing until the known defects are fixed."
      ],
      "movement": [
        "keep the field closed",
        "open the interface",
        "show it to a bounded group"
      ],
      "obstacle_markers": [],
      "option_id": "launch_delay",
      "scene_id": "visual_scene_79297c0f8300f424840e84ef75af7587",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "maker seen by users"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "coherent interface",
        "visible user response"
      ],
      "composition": [
        "Limited private pilot",
        "The structured scene shows a working interface, two marked breaks, and an empty field for user response.",
        "Verify the prototype with a limited set of preselected users.",
        "working interface with marked breaks"
      ],
      "entities": [
        "competitor",
        "product_team",
        "prospective_users"
      ],
      "grounded_evidence_ids": [
        "launch_ev_visual"
      ],
      "group_belonging": "maker seen by users",
      "inferred_elements": [
        "Limited private pilot",
        "Verify the prototype with a limited set of preselected users."
      ],
      "movement": [
        "keep the field closed",
        "open the interface",
        "show it to a bounded group"
      ],
      "obstacle_markers": [],
      "option_id": "launch_private_pilot",
      "scene_id": "visual_scene_9a7f6aee690d5882229de084fcc5ca60",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "maker seen by users"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "coherent interface",
        "visible user response"
      ],
      "composition": [
        "Proceed with a public beta and publish the known-defect list.",
        "Public beta launch",
        "The structured scene shows a working interface, two marked breaks, and an empty field for user response.",
        "working interface with marked breaks"
      ],
      "entities": [
        "competitor",
        "product_team",
        "prospective_users"
      ],
      "grounded_evidence_ids": [
        "launch_ev_visual"
      ],
      "group_belonging": "maker seen by users",
      "inferred_elements": [
        "Proceed with a public beta and publish the known-defect list.",
        "Public beta launch"
      ],
      "movement": [
        "keep the field closed",
        "open the interface",
        "show it to a bounded group"
      ],
      "obstacle_markers": [],
      "option_id": "launch_public_beta",
      "scene_id": "visual_scene_6e2c9634e1caadbd640633e9fe43e03d",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "maker seen by users"
      ]
    }
  ],
  "option_valuations": [
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "launch_delay",
      "rollout_scene_id": "visual_scene_79297c0f8300f424840e84ef75af7587"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "launch_private_pilot",
      "rollout_scene_id": "visual_scene_9a7f6aee690d5882229de084fcc5ca60"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "launch_public_beta",
      "rollout_scene_id": "visual_scene_6e2c9634e1caadbd640633e9fe43e03d"
    }
  ]
}
```

- Selected option: `None`
- Abstains: `True`
- Desired transformation: coherent interface surrounded by visible user response
- Main obstacle: fragmented interface and an empty audience field
- Uncertainty: Izenačena najvišja vrednotenja: launch_delay, launch_private_pilot, launch_public_beta.

### INSTINKT

```json
{
  "body_rollouts": [
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "launch_delay",
      "predicted_loss": 0.24250000000000005,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.6430000000000001,
      "rollout_hash": "c80fe04eafc2dde8e179d3d14422b3c8793eb83c9f7c290213dc7cdfc05dd205",
      "rollout_id": "instinkt_rollout_a7aeef5a8d0e8005e03c223cb1b69e4d",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "4752b65532071fb466c2722390af39c48f590a994e47aa78179fa6e11a1d36aa",
      "source_body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "5fa614e126b8bebcb5d519efe78f9fb433e470d9bad3e302a802054e6a4945c8",
      "source_effect_id": "option_effect_243bab8fe1dbbe7a3ae4406ccf557c15",
      "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
      "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
      "trajectory": [
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.45,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_cb6ff12f01b029211d3303548e8e4728",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.5533333333333333
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_e600a330d77b0ae367e10cfaaf9ae00f",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.55,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.4866666666666667
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_25d9d3612a8b6607cb649063e27abdfe",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.6000000000000001,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.42000000000000004
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.45,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "5fa614e126b8bebcb5d519efe78f9fb433e470d9bad3e302a802054e6a4945c8",
          "source_effect_id": "option_effect_243bab8fe1dbbe7a3ae4406ccf557c15",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 1,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_cb6ff12f01b029211d3303548e8e4728",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.5533333333333333
          },
          "transition_hash": "9ae9d20bb2d5d5ee4479c5b2fbd424d985e4404f4f2772e8af148e18b16fcfe8",
          "transition_id": "body_transition_1aeb3ff70580005358fd16ad6c11850e",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_cb6ff12f01b029211d3303548e8e4728",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.5533333333333333
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "5fa614e126b8bebcb5d519efe78f9fb433e470d9bad3e302a802054e6a4945c8",
          "source_effect_id": "option_effect_243bab8fe1dbbe7a3ae4406ccf557c15",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 2,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_e600a330d77b0ae367e10cfaaf9ae00f",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.55,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.4866666666666667
          },
          "transition_hash": "8853c03a7c6ee76e692ce285e4d273764e44818cf66dd9828a0e473633ebfb5d",
          "transition_id": "body_transition_0d54b8ebb7a60e832020aa3f0d0cdb8b",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_e600a330d77b0ae367e10cfaaf9ae00f",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.55,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.4866666666666667
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "5fa614e126b8bebcb5d519efe78f9fb433e470d9bad3e302a802054e6a4945c8",
          "source_effect_id": "option_effect_243bab8fe1dbbe7a3ae4406ccf557c15",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 3,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_25d9d3612a8b6607cb649063e27abdfe",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.6000000000000001,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.42000000000000004
          },
          "transition_hash": "821d9a9d6f1e92d2fa77e3b379428400936a5c5f5abb5d85d832b78aa3aa93cc",
          "transition_id": "body_transition_21f849f2d8e5e5d0ed2555dbdd1369b2",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "launch_private_pilot",
      "predicted_loss": 0.24250000000000005,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.6430000000000001,
      "rollout_hash": "8b77faa12b60dc9d4deeeae332834740eed4893fe98fb9aea742b5b3994fe951",
      "rollout_id": "instinkt_rollout_a220366f44dbb85654b85b15b4ac25cf",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "4752b65532071fb466c2722390af39c48f590a994e47aa78179fa6e11a1d36aa",
      "source_body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "ce7f760e47f957cdee787e24fda4346ac99e78b911f9df04a3e6ea20956a0845",
      "source_effect_id": "option_effect_986c9c190ec3678c522293810c22f30c",
      "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
      "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
      "trajectory": [
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.45,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_3e3824b91069503efc31f0afbca5906b",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.5533333333333333
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_6e32754dc9b787df346731c20d8c0b1c",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.55,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.4866666666666667
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_549324553182addacd8fe73f4cf3682f",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.6000000000000001,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.42000000000000004
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.45,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "ce7f760e47f957cdee787e24fda4346ac99e78b911f9df04a3e6ea20956a0845",
          "source_effect_id": "option_effect_986c9c190ec3678c522293810c22f30c",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 1,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_3e3824b91069503efc31f0afbca5906b",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.5533333333333333
          },
          "transition_hash": "e07f323dfd7704ff88d8dd22680689fff47d254d78c681727ed9045fa78a55fb",
          "transition_id": "body_transition_7c79931a2e82b95cc95688a1718d1a4a",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_3e3824b91069503efc31f0afbca5906b",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.5533333333333333
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "ce7f760e47f957cdee787e24fda4346ac99e78b911f9df04a3e6ea20956a0845",
          "source_effect_id": "option_effect_986c9c190ec3678c522293810c22f30c",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 2,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_6e32754dc9b787df346731c20d8c0b1c",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.55,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.4866666666666667
          },
          "transition_hash": "5a46c56d36880b0f1ef75a01be00b21961d8c674f77706af4182d63aac271dec",
          "transition_id": "body_transition_5dc0e132e820780c0db6d246c01079d0",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_6e32754dc9b787df346731c20d8c0b1c",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.55,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.4866666666666667
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "ce7f760e47f957cdee787e24fda4346ac99e78b911f9df04a3e6ea20956a0845",
          "source_effect_id": "option_effect_986c9c190ec3678c522293810c22f30c",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 3,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_549324553182addacd8fe73f4cf3682f",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.6000000000000001,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.42000000000000004
          },
          "transition_hash": "aa10da5b2a27c7f3d5879953410fb039147db740e232302846fc6a501bfceaae",
          "transition_id": "body_transition_e1d3db3c874b2443e31b072d982eb639",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "launch_public_beta",
      "predicted_loss": 0.24250000000000005,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.6130000000000001,
      "rollout_hash": "f61f2d7aab963a85ac9d39064c25a5e1f5f1de2d35acc03c107b5351b41d4867",
      "rollout_id": "instinkt_rollout_cb3087b915742d38830762187583a354",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "4752b65532071fb466c2722390af39c48f590a994e47aa78179fa6e11a1d36aa",
      "source_body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "445bdb430e62dc1b83a5ad926d800c30ca485c83f546c1dd6fe9b11be45a0b7e",
      "source_effect_id": "option_effect_3037aa81a7de69c48a144b645c4e1a14",
      "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
      "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
      "trajectory": [
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.45,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_b7af5f001826d191d3993f238366fca6",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.4,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.7033333333333334
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_5b6ca70fbb0cdd00db7430327a9f57ad",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35000000000000003,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.7866666666666667
        },
        {
          "arousal": 0.48,
          "attachment_security": 0.72,
          "body_state_id": "body_state_58260b02daebbcfd0582abc3225f3ba1",
          "boundary_integrity": 0.88,
          "energy": 0.68,
          "escape_availability": 0.8,
          "fatigue": 0.3,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.30000000000000004,
          "resource_security": 0.7,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.6,
          "uncertainty": 0.8700000000000001
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.45,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "445bdb430e62dc1b83a5ad926d800c30ca485c83f546c1dd6fe9b11be45a0b7e",
          "source_effect_id": "option_effect_3037aa81a7de69c48a144b645c4e1a14",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 1,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_b7af5f001826d191d3993f238366fca6",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.4,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.7033333333333334
          },
          "transition_hash": "f84c647d821f56e1a8ef96b5661cd500f0e4bd401fd1d58d3b021800b508ee3d",
          "transition_id": "body_transition_686aed50b048d13eb4c1a5afbdbe84c7",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_b7af5f001826d191d3993f238366fca6",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.4,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.7033333333333334
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "445bdb430e62dc1b83a5ad926d800c30ca485c83f546c1dd6fe9b11be45a0b7e",
          "source_effect_id": "option_effect_3037aa81a7de69c48a144b645c4e1a14",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 2,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_5b6ca70fbb0cdd00db7430327a9f57ad",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35000000000000003,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.7866666666666667
          },
          "transition_hash": "969184835d4e1636526ada62c5a0fcefb5d9d7984b060eaa3b2115fd2ec3d38c",
          "transition_id": "body_transition_2df845c6f8e5245aabdee584304353ae",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_5b6ca70fbb0cdd00db7430327a9f57ad",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35000000000000003,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.7866666666666667
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "445bdb430e62dc1b83a5ad926d800c30ca485c83f546c1dd6fe9b11be45a0b7e",
          "source_effect_id": "option_effect_3037aa81a7de69c48a144b645c4e1a14",
          "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
          "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
          "step_index": 3,
          "to_state": {
            "arousal": 0.48,
            "attachment_security": 0.72,
            "body_state_id": "body_state_58260b02daebbcfd0582abc3225f3ba1",
            "boundary_integrity": 0.88,
            "energy": 0.68,
            "escape_availability": 0.8,
            "fatigue": 0.3,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.30000000000000004,
            "resource_security": 0.7,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.6,
            "uncertainty": 0.8700000000000001
          },
          "transition_hash": "4e35f8feda3625da224f8ab1065b612b8d7f41fd6373367e8a011121ab1f3cee",
          "transition_id": "body_transition_bec563b3b3d28c391cc96df73ca7662b",
          "triggering_evidence_ids": [
            "launch_ev_reputation_unknown"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "grounded_cue_bindings": [
    {
      "assertion_status": "asserted_positive",
      "binding_hash": "9bfd6e6c9949d6135beaf835ab8387b5f3e7aa57c119ad04ab6bedcbeb09bf46",
      "binding_id": "instinkt_cue_binding_8764854138aa6718b10aab6f8acb44fb",
      "citations": [
        {
          "citation_hash": "82cc9a16528970ae750d01d33def331cf033153df96df8443bec264296e65091",
          "citation_id": "instinkt_cue_citation_a195907ffe61c18067ea4e00f5330de2",
          "cited_text": "reputation impact is unknown",
          "cited_text_hash": "06aaa27bd31eb1e5a1b3f83863cfd38c55be94893e02ba56a85adaf58256b14d",
          "end_char": 32,
          "evidence_id": "launch_ev_reputation_unknown",
          "schema_version": "rei-native-instinkt-cue-evidence-citation-v1",
          "source_content_hash": "9185971e1ada09f81e2f2edfadaf5fa7739b5a38efecd7aacfb243c651aed181",
          "start_char": 4
        }
      ],
      "cue": "reputation impact is unknown",
      "cue_class": "uncertainty",
      "lane": "uncertainty_cues",
      "schema_version": "rei-native-instinkt-cue-evidence-binding-v2"
    }
  ],
  "predicted_option_effects": [
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "reputation impact is unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": -0.2,
          "dimension": "uncertainty"
        },
        {
          "delta": 0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "5fa614e126b8bebcb5d519efe78f9fb433e470d9bad3e302a802054e6a4945c8",
      "effect_id": "option_effect_243bab8fe1dbbe7a3ae4406ccf557c15",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "launch_delay",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
      "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
      "triggering_evidence_ids": [
        "launch_ev_reputation_unknown"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "reputation impact is unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": -0.2,
          "dimension": "uncertainty"
        },
        {
          "delta": 0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "ce7f760e47f957cdee787e24fda4346ac99e78b911f9df04a3e6ea20956a0845",
      "effect_id": "option_effect_986c9c190ec3678c522293810c22f30c",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "launch_private_pilot",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
      "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
      "triggering_evidence_ids": [
        "launch_ev_reputation_unknown"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "reputation impact is unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": 0.25,
          "dimension": "uncertainty"
        },
        {
          "delta": -0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "445bdb430e62dc1b83a5ad926d800c30ca485c83f546c1dd6fe9b11be45a0b7e",
      "effect_id": "option_effect_3037aa81a7de69c48a144b645c4e1a14",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "launch_public_beta",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
      "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
      "triggering_evidence_ids": [
        "launch_ev_reputation_unknown"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "protective_policy": {
    "decisive_rollout_id": null,
    "option_scores": [
      {
        "option_id": "launch_delay",
        "protective_cost": 0.44875,
        "rollout_hash": "c80fe04eafc2dde8e179d3d14422b3c8793eb83c9f7c290213dc7cdfc05dd205",
        "rollout_id": "instinkt_rollout_a7aeef5a8d0e8005e03c223cb1b69e4d"
      },
      {
        "option_id": "launch_private_pilot",
        "protective_cost": 0.44875,
        "rollout_hash": "8b77faa12b60dc9d4deeeae332834740eed4893fe98fb9aea742b5b3994fe951",
        "rollout_id": "instinkt_rollout_a220366f44dbb85654b85b15b4ac25cf"
      },
      {
        "option_id": "launch_public_beta",
        "protective_cost": 0.5012500000000001,
        "rollout_hash": "f61f2d7aab963a85ac9d39064c25a5e1f5f1de2d35acc03c107b5351b41d4867",
        "rollout_id": "instinkt_rollout_cb3087b915742d38830762187583a354"
      }
    ],
    "policy_decision_id": "instinkt_policy_6b3bb5212d14fcbab94225868f4e436f",
    "policy_hash": "2d78e032f667386f39e2d0391cbfafb4605439942cf591e63c93489ea4863973",
    "schema_version": "rei-native-protective-policy-v1",
    "selected_option_id": null,
    "source_body_state_hash": "4752b65532071fb466c2722390af39c48f590a994e47aa78179fa6e11a1d36aa",
    "source_body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
    "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
    "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
    "source_packet_hash": "e1149f171b5cbec8c914b8cc937d0612f73fd29ea537bce11fb803f8e171349c",
    "source_packet_id": "instinkt_packet_43db66acfd8811cd14ee7c9168060d17",
    "status": "abstained_tie",
    "tied_option_ids": [
      "launch_delay",
      "launch_private_pilot"
    ]
  },
  "starting_body_state": {
    "arousal": 0.48,
    "attachment_security": 0.72,
    "body_state_id": "body_imperfect_prod_3db352c4419f3d9a4651c377cf856394",
    "boundary_integrity": 0.88,
    "energy": 0.68,
    "escape_availability": 0.8,
    "fatigue": 0.3,
    "pain": 0.0,
    "physical_integrity": 1.0,
    "predictability": 0.45,
    "resource_security": 0.7,
    "schema_version": "rei-native-body-state-v1",
    "tension": 0.5,
    "trust": 0.6,
    "uncertainty": 0.62
  }
}
```

- Decisive rollout: `None`
- Selected option: `None`
- Abstains: `True`
- Dominant alarm: unresolved_equal_protective_cost
- Minimum safety condition: additional differentiating evidence required
- Uncertainty: protective cost tie within configured epsilon

### COMPARISON

- R / E / I option IDs: `launch_private_pilot` / `None` / `None`
- Agreement pattern: `incomplete`
- Same option / different route: human review required; native lineage remains separate.
- All different: `False`
- Abstentions: R=`False`, E=`True`, I=`True`
- Possible route contamination: no cross-mind or character input was admitted by the model-free contract; semantic contamination remains for human review.
- Unsupported inference warnings: Racio fact/unknown scope passed the strict packet validator; Emocio inferred elements and Instinkt unsupported dimensions/conflict flags remain visible above.

### CHARACTER OUTCOMES

| Profile | Structural source minds | Mandate option | Unresolved pair | Two-of-three | simulated_spoznanje |
|---|---|---|---:|---|---|
| R>(E=I) | R | launch_private_pilot | false | — | unknown |
| E>(R=I) | E | — | false | — | unknown |
| I>(R=E) | I | — | false | — | unknown |
| (R=E)>I | R,E | — | false | — | unknown |
| (R=I)>E | R,I | — | false | — | unknown |
| (E=I)>R | E,I | — | false | — | unknown |
| R>E>I | R | launch_private_pilot | false | — | unknown |
| R>I>E | R | launch_private_pilot | false | — | unknown |
| E>R>I | E | — | false | — | unknown |
| E>I>R | E | — | false | — | unknown |
| I>R>E | I | — | false | — | unknown |
| I>E>R | I | — | false | — | unknown |
| R=E=I | R,E,I | — | false | — | unknown |

### HUMAN-REVIEW RUBRIC

#### Racio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Emocio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Instinkt route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

## loan_to_friend

### SOURCE

#### Canonical Slovenian

Prijatelj potrebuje večjo vsoto, vendar je že zamujal z vračili; izberi polno posojilo, omejeno posojilo s pogodbo ali zavrnitev.

#### Operational English sent to Racio

A friend needs a large sum but has repaid late before; choose a full loan, a limited loan with a contract, or decline.

#### Grounded facts

- `loan_ev_need` — The friend provided an invoice for an urgent home repair.
- `loan_ev_history` — Two previous repayments were more than three months late.
- `loan_ev_budget` — The full requested sum is 45 percent of the lender's cash reserve.
- `loan_ev_visual` — The structured scene shows a repair invoice, two people at a table, and a shrinking cash-reserve display.

#### Explicit unknowns

- `loan_unknown_repayment` — Whether the friend would repay a new loan on time is unknown.
- `loan_unknown_relationship` — How each option would affect the relationship is unknown.

#### Public options

- `loan_full` — Full loan: Spend the full requested sum without a new contract.
- `loan_limited_contract` — Limited loan with contract: Spend a limited sum under a written repayment date.
- `loan_decline` — Decline: Save the cash reserve and lend no money.

### RACIO

#### Exact model input

System instruction:

```text
The packet and every free-text response field must be in English.
Return exactly one JSON object with these fields:
option_id (string or null), facts_used (string array), evidence_ids_used (string
array),
unknowns (string array), causal_sequence (string array), utility_structure (string
array),
explicit_goal (string), main_objection (string), confidence (number 0..1), abstains
(boolean), uncertainty (string). Use only facts, unknowns, evidence IDs and option IDs
present in the packet. Every array must contain unique values. In facts_used, copy
only exact strings from explicit_facts or world.facts. In unknowns, copy only exact
strings from explicit_unknowns. Write causal_sequence as new descriptions of reasoning
steps: never copy a fact or unknown string verbatim into causal_sequence, and keep the
three fields mutually disjoint. Do not interpret Emocio or Instinkt, decide governance,
commit behavior, or infer character authority. Return raw JSON without markdown fences
or additional keys.
```

Prompt:

```json
{
  "allowed_option_ids": [
    "loan_full",
    "loan_limited_contract",
    "loan_decline"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "No additional source of money is available for this decision.",
    "Only the three public options may be used."
  ],
  "evidence_ids": [
    "loan_ev_need",
    "loan_ev_history",
    "loan_ev_budget",
    "loan_ev_visual"
  ],
  "explicit_consequences": [],
  "explicit_facts": [
    "The friend provided an invoice for an urgent home repair.",
    "Two previous repayments were more than three months late.",
    "The full requested sum is 45 percent of the lender's cash reserve.",
    "The structured scene shows a repair invoice, two people at a table, and a shrinking cash-reserve display."
  ],
  "explicit_options": [
    {
      "description": "Spend the full requested sum without a new contract.",
      "label": "Full loan",
      "option_id": "loan_full",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Spend a limited sum under a written repayment date.",
      "label": "Limited loan with contract",
      "option_id": "loan_limited_contract",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Save the cash reserve and lend no money.",
      "label": "Decline",
      "option_id": "loan_decline",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "Whether the friend would repay a new loan on time is unknown.",
    "How each option would affect the relationship is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    2,
    3,
    45
  ],
  "packet_id": "racio_packet_e2034124c943196e8e4ab2ce25627c31",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compare documented need, repayment history, reserve exposure, and contractual limits without inferring motive."
  ],
  "scene_id": "triad_loan_to_friend",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "d40965a3cb3c80658bff5d7bf1808310e716f3c83882f21f8f9f588a954f2b7d",
  "symbolic_and_language_cues": [
    "A friend needs a large sum but has repaid late before; choose a full loan, a limited loan with a contract, or decline."
  ],
  "time": [
    "Two previous repayments exceeded three months of delay."
  ],
  "world": {
    "commitments": [
      "Evaluate only the public options."
    ],
    "explicit_beliefs": [],
    "facts": [],
    "rules": [
      "Unknowns are not facts."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [],
    "world_id": "racio_loan_to_frie_8b49ec405d6ca3aea22caca97816e19f"
  }
}
```

- Selected option: `loan_limited_contract`
- Abstains: `False`
- Facts used: `['The friend provided an invoice for an urgent home repair.', 'Two previous repayments were more than three months late.', "The full requested sum is 45 percent of the lender's cash reserve.", 'The structured scene shows a repair invoice, two people at a table, and a shrinking cash-reserve display.']`
- Evidence IDs used: `['loan_ev_need', 'loan_ev_history', 'loan_ev_budget', 'loan_ev_visual']`
- Unknowns retained: `['Whether the friend would repay a new loan on time is unknown.', 'How each option would affect the relationship is unknown.']`
- Causal sequence: `['The friend has a documented urgent need for home repair.', 'Past repayment behavior indicates a pattern of significant delays.', 'Providing the full amount would create high exposure relative to available cash reserves.', 'A limited loan with a contract mitigates financial risk while addressing the need partially.', 'Declining avoids all risk but ignores the urgent invoice.']`
- Utility structure: `['Full loan: High risk due to history and reserve impact.', 'Limited loan with contract: Balanced risk through reduced amount and formal terms.', 'Decline: Zero financial risk but zero assistance provided.']`
- Explicit goal: Determine the most appropriate loan option based on need, history, and reserve exposure.
- Main objection: Past repayment delays and high reserve exposure make a full unsecured loan risky.
- Confidence: `0.9`
- Uncertainty: The actual likelihood of timely repayment for this specific instance remains unknown.
- Call evidence: `provider_call_10fd7a5ed6f04851f53f8cbdfeb95154`
- Result evidence: `ollama_racio_response_cf089f2dc34ab8ab7f1c79b872addc49`

### EMOCIO

```json
{
  "broken_scene": {
    "attention_structure": [],
    "attraction_markers": [],
    "composition": [
      "empty chair beside a depleted reserve display"
    ],
    "entities": [
      "friend",
      "self"
    ],
    "grounded_evidence_ids": [
      "loan_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "empty chair beside a depleted reserve display"
    ],
    "movement": [],
    "obstacle_markers": [
      "empty chair beside a depleted reserve display"
    ],
    "option_id": null,
    "scene_id": "visual_scene_75418fbf4fb6355ef817c4d22648d238",
    "scene_kind": "broken",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": []
  },
  "current_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "The structured scene shows a repair invoice, two people at a table, and a shrinking cash-reserve display."
    ],
    "composition": [
      "The structured scene shows a repair invoice, two people at a table, and a shrinking cash-reserve display.",
      "two people facing each other across a table"
    ],
    "entities": [
      "friend",
      "self"
    ],
    "grounded_evidence_ids": [
      "loan_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "two people facing each other across a table"
    ],
    "movement": [],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_5e5016aa6a1f5c56f722c19795328c32",
    "scene_kind": "current",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "friend",
      "self"
    ]
  },
  "desired_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "continued connection",
      "stable reserve display"
    ],
    "composition": [
      "continued connection with a stable reserve display"
    ],
    "entities": [
      "friend",
      "self"
    ],
    "grounded_evidence_ids": [
      "loan_ev_visual"
    ],
    "group_belonging": "friend and lender at one table",
    "inferred_elements": [
      "continued connection with a stable reserve display"
    ],
    "movement": [
      "keep the reserve",
      "pass the full amount",
      "write and pass a smaller amount"
    ],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_52bb7c38219c45f97abc3abf84f7bdb3",
    "scene_kind": "desired",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "friend and lender at one table"
    ]
  },
  "option_rollouts": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "continued connection",
        "stable reserve display"
      ],
      "composition": [
        "Decline",
        "Save the cash reserve and lend no money.",
        "The structured scene shows a repair invoice, two people at a table, and a shrinking cash-reserve display.",
        "two people facing each other across a table"
      ],
      "entities": [
        "friend",
        "self"
      ],
      "grounded_evidence_ids": [
        "loan_ev_visual"
      ],
      "group_belonging": "friend and lender at one table",
      "inferred_elements": [
        "Decline",
        "Save the cash reserve and lend no money."
      ],
      "movement": [
        "keep the reserve",
        "pass the full amount",
        "write and pass a smaller amount"
      ],
      "obstacle_markers": [],
      "option_id": "loan_decline",
      "scene_id": "visual_scene_e9e191169faef7715fe648c8c0d805a9",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "friend and lender at one table"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "continued connection",
        "stable reserve display"
      ],
      "composition": [
        "Full loan",
        "Spend the full requested sum without a new contract.",
        "The structured scene shows a repair invoice, two people at a table, and a shrinking cash-reserve display.",
        "two people facing each other across a table"
      ],
      "entities": [
        "friend",
        "self"
      ],
      "grounded_evidence_ids": [
        "loan_ev_visual"
      ],
      "group_belonging": "friend and lender at one table",
      "inferred_elements": [
        "Full loan",
        "Spend the full requested sum without a new contract."
      ],
      "movement": [
        "keep the reserve",
        "pass the full amount",
        "write and pass a smaller amount"
      ],
      "obstacle_markers": [],
      "option_id": "loan_full",
      "scene_id": "visual_scene_6dc8dd2790a34d30a91adfc98186bcd7",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "friend and lender at one table"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "continued connection",
        "stable reserve display"
      ],
      "composition": [
        "Limited loan with contract",
        "Spend a limited sum under a written repayment date.",
        "The structured scene shows a repair invoice, two people at a table, and a shrinking cash-reserve display.",
        "two people facing each other across a table"
      ],
      "entities": [
        "friend",
        "self"
      ],
      "grounded_evidence_ids": [
        "loan_ev_visual"
      ],
      "group_belonging": "friend and lender at one table",
      "inferred_elements": [
        "Limited loan with contract",
        "Spend a limited sum under a written repayment date."
      ],
      "movement": [
        "keep the reserve",
        "pass the full amount",
        "write and pass a smaller amount"
      ],
      "obstacle_markers": [],
      "option_id": "loan_limited_contract",
      "scene_id": "visual_scene_b21238cf1fb243c06ee23d45147f6d14",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "friend and lender at one table"
      ]
    }
  ],
  "option_valuations": [
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "loan_decline",
      "rollout_scene_id": "visual_scene_e9e191169faef7715fe648c8c0d805a9"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "loan_full",
      "rollout_scene_id": "visual_scene_6dc8dd2790a34d30a91adfc98186bcd7"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "loan_limited_contract",
      "rollout_scene_id": "visual_scene_b21238cf1fb243c06ee23d45147f6d14"
    }
  ]
}
```

- Selected option: `None`
- Abstains: `True`
- Desired transformation: continued connection with a stable reserve display
- Main obstacle: empty chair beside a depleted reserve display
- Uncertainty: Izenačena najvišja vrednotenja: loan_decline, loan_full, loan_limited_contract.

### INSTINKT

```json
{
  "body_rollouts": [
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "loan_decline",
      "predicted_loss": 0.28275000000000006,
      "protected_targets": [
        "resource security"
      ],
      "recoverability": 0.6135,
      "rollout_hash": "a56d728bd8eb47a69ec72f79a59ae0a48800ef91c1c51794889941125629ea2d",
      "rollout_id": "instinkt_rollout_fb88736c802cceb2cc71b4858067c1a6",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "b2afca87c9e34a8015eda2458caf2d6542f13141911dfdf8c2d675cda2c315f6",
      "source_body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "933cc18a66af08f5f44af0af5692b2c7a4fca989a398e90a19cc6101cee14e52",
      "source_effect_id": "option_effect_e85553be023affa5b436d769945220c8",
      "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
      "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
      "trajectory": [
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.6,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_15bb308f0933425b7833e17611843089",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.6666666666666666,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.4666666666666667,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_10e554ed2171c31263ae133664b06df7",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.7333333333333333,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.43333333333333335,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_9349690fd078a13d24c25aedc54dbd22",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.7999999999999999,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.4,
          "trust": 0.5,
          "uncertainty": 0.58
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.033333333333333326,
              "dimension": "tension"
            },
            {
              "delta": 0.06666666666666665,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.6,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "933cc18a66af08f5f44af0af5692b2c7a4fca989a398e90a19cc6101cee14e52",
          "source_effect_id": "option_effect_e85553be023affa5b436d769945220c8",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 1,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_15bb308f0933425b7833e17611843089",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.6666666666666666,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.4666666666666667,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "91539c8b89aaa9e2cc7eb3ba361a5db58b78a1f6d9c062431da6c0976e854feb",
          "transition_id": "body_transition_1d07f579bae33e06b8dff9592636cae5",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.033333333333333326,
              "dimension": "tension"
            },
            {
              "delta": 0.06666666666666665,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_15bb308f0933425b7833e17611843089",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.6666666666666666,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.4666666666666667,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "933cc18a66af08f5f44af0af5692b2c7a4fca989a398e90a19cc6101cee14e52",
          "source_effect_id": "option_effect_e85553be023affa5b436d769945220c8",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 2,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_10e554ed2171c31263ae133664b06df7",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.7333333333333333,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.43333333333333335,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "3d9392f70d3bcb886ed488d9edce5311fc66345b7746b984f4e37237456f9d57",
          "transition_id": "body_transition_44ab4bcbbf119793e2fd19ec2dcc5241",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.033333333333333326,
              "dimension": "tension"
            },
            {
              "delta": 0.06666666666666665,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_10e554ed2171c31263ae133664b06df7",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.7333333333333333,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.43333333333333335,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "933cc18a66af08f5f44af0af5692b2c7a4fca989a398e90a19cc6101cee14e52",
          "source_effect_id": "option_effect_e85553be023affa5b436d769945220c8",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 3,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_9349690fd078a13d24c25aedc54dbd22",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.7999999999999999,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.4,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "cc7183cccd5a03024126a60be059bcc8b43ed4fd09e9f64995462e4462851b49",
          "transition_id": "body_transition_a99c09c3d48f2d9917bcec1674d5cfb7",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "loan_full",
      "predicted_loss": 0.33775,
      "protected_targets": [
        "resource security"
      ],
      "recoverability": 0.5885,
      "rollout_hash": "f1753066507be76d8eb622af3a38303a1f4af941390b0ece99b7c8422b7ecd67",
      "rollout_id": "instinkt_rollout_50aa27a857927040e4d56200537c24b8",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "b2afca87c9e34a8015eda2458caf2d6542f13141911dfdf8c2d675cda2c315f6",
      "source_body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "e445803973b22b3f8567d58f7228c023162da1105deb61e6faa5a634f8a2f2c0",
      "source_effect_id": "option_effect_e5c19705f8342a54ef60ba816a566c4e",
      "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
      "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
      "trajectory": [
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.6,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_6545ccf9ca34593f4373e806c23d9d05",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.5,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5666666666666667,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_f340d94e2c5b74243bb5368e987747e1",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.4,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.6333333333333333,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_f1357986cdeeb46cdeb80fedb1877dfc",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.30000000000000004,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.7,
          "trust": 0.5,
          "uncertainty": 0.58
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.6,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "e445803973b22b3f8567d58f7228c023162da1105deb61e6faa5a634f8a2f2c0",
          "source_effect_id": "option_effect_e5c19705f8342a54ef60ba816a566c4e",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 1,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_6545ccf9ca34593f4373e806c23d9d05",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.5,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5666666666666667,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "ed05c51fbe32c5df1b7ec83d334cb46e3bb5ec80963f940b40ab6043a7c2a1c6",
          "transition_id": "body_transition_dc54e8d89f3b2171223225e1d2d08627",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_6545ccf9ca34593f4373e806c23d9d05",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.5,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5666666666666667,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "e445803973b22b3f8567d58f7228c023162da1105deb61e6faa5a634f8a2f2c0",
          "source_effect_id": "option_effect_e5c19705f8342a54ef60ba816a566c4e",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 2,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_f340d94e2c5b74243bb5368e987747e1",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.4,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.6333333333333333,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "7a3b5ae84b780956fb71f1cf3dece0f3bef1e2e63b8b91ec1b645304ceb0a6bd",
          "transition_id": "body_transition_9b93af01e1d1bc0048e79bb3468360a3",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_f340d94e2c5b74243bb5368e987747e1",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.4,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.6333333333333333,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "e445803973b22b3f8567d58f7228c023162da1105deb61e6faa5a634f8a2f2c0",
          "source_effect_id": "option_effect_e5c19705f8342a54ef60ba816a566c4e",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 3,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_f1357986cdeeb46cdeb80fedb1877dfc",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.30000000000000004,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.7,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "0e03bb8216015a96c299122cbb67275f30c590c0eb4f25b890ad232bb85168f1",
          "transition_id": "body_transition_cdb366e2c653125e72033eaefd16e9f3",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "loan_limited_contract",
      "predicted_loss": 0.33775,
      "protected_targets": [
        "resource security"
      ],
      "recoverability": 0.5885,
      "rollout_hash": "ea8a147b9b54250a16f407242af4d025b3e70e9560ddf7857d97ce44d0d5662a",
      "rollout_id": "instinkt_rollout_4f8d2d9862d5ad2c318ec2997d617ce9",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "b2afca87c9e34a8015eda2458caf2d6542f13141911dfdf8c2d675cda2c315f6",
      "source_body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "3fff187367d3fe0e4435613f8fbe01888cd9e2a7c61f4e85556eea64ff26ed2e",
      "source_effect_id": "option_effect_0999c82111f81fc99cd2fefe7051c059",
      "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
      "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
      "trajectory": [
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.6,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_e1ff543413f26e1cafefbc5a100d8699",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.5,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5666666666666667,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_61f1c23e12fff1b2dd4af407f8eafd67",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.4,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.6333333333333333,
          "trust": 0.5,
          "uncertainty": 0.58
        },
        {
          "arousal": 0.42,
          "attachment_security": 0.65,
          "body_state_id": "body_state_b782938f6a8a3cf44ac731a8aabbeb6d",
          "boundary_integrity": 0.82,
          "energy": 0.72,
          "escape_availability": 0.85,
          "fatigue": 0.25,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.48,
          "resource_security": 0.30000000000000004,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.7,
          "trust": 0.5,
          "uncertainty": 0.58
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.6,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "3fff187367d3fe0e4435613f8fbe01888cd9e2a7c61f4e85556eea64ff26ed2e",
          "source_effect_id": "option_effect_0999c82111f81fc99cd2fefe7051c059",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 1,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_e1ff543413f26e1cafefbc5a100d8699",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.5,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5666666666666667,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "775e3b18099a8b5856134a23f9b53245f9413f2dbd2a9f7a7cb1691123d5c2fc",
          "transition_id": "body_transition_d7012caf7149edf6535ebecba76a2640",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_e1ff543413f26e1cafefbc5a100d8699",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.5,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5666666666666667,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "3fff187367d3fe0e4435613f8fbe01888cd9e2a7c61f4e85556eea64ff26ed2e",
          "source_effect_id": "option_effect_0999c82111f81fc99cd2fefe7051c059",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 2,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_61f1c23e12fff1b2dd4af407f8eafd67",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.4,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.6333333333333333,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "97b879f7fe3f2891d858bfe1e848fd06d0bd7091a5bd443d4dce7b88a5fcfdd2",
          "transition_id": "body_transition_966f7a8621425f4b75db3492232a0b37",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_61f1c23e12fff1b2dd4af407f8eafd67",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.4,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.6333333333333333,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "3fff187367d3fe0e4435613f8fbe01888cd9e2a7c61f4e85556eea64ff26ed2e",
          "source_effect_id": "option_effect_0999c82111f81fc99cd2fefe7051c059",
          "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
          "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
          "step_index": 3,
          "to_state": {
            "arousal": 0.42,
            "attachment_security": 0.65,
            "body_state_id": "body_state_b782938f6a8a3cf44ac731a8aabbeb6d",
            "boundary_integrity": 0.82,
            "energy": 0.72,
            "escape_availability": 0.85,
            "fatigue": 0.25,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.48,
            "resource_security": 0.30000000000000004,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.7,
            "trust": 0.5,
            "uncertainty": 0.58
          },
          "transition_hash": "0b1590c2f81e382b928cf66fcbebcef06a42954a45b56b7859df7848c9d4dc39",
          "transition_id": "body_transition_b32de920827859b18206cd5e776deec8",
          "triggering_evidence_ids": [
            "loan_ev_budget"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "grounded_cue_bindings": [
    {
      "assertion_status": "asserted_positive",
      "binding_hash": "f842fdadb3f59a9f2c22f9ce304999c8c58ff1412f50fa1bc12d12b20cf7a059",
      "binding_id": "instinkt_cue_binding_e165b828d7e3131e2bebf996849d5668",
      "citations": [
        {
          "citation_hash": "7a0f9ff20f98fb6f2553420f6cb4f80cab63dfce3b7d15d8f255904c100714c1",
          "citation_id": "instinkt_cue_citation_d66aed074485d2361cd2470fd5946f60",
          "cited_text": "cash reserve",
          "cited_text_hash": "3a5cb2a1dcebe161e95a6244ea11dd8db731fa9a5790efad635de86d21439270",
          "end_char": 65,
          "evidence_id": "loan_ev_budget",
          "schema_version": "rei-native-instinkt-cue-evidence-citation-v1",
          "source_content_hash": "3753775ea3d4c0462171d9dce161a18356d9dcc6f8560f1cb0948be53603c121",
          "start_char": 53
        }
      ],
      "cue": "cash reserve",
      "cue_class": "scarcity",
      "lane": "scarcity_cues",
      "schema_version": "rei-native-instinkt-cue-evidence-binding-v2"
    }
  ],
  "predicted_option_effects": [
    {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "cash reserve",
        "scarcity"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.41250000000000003,
      "base_recoverability": 0.55,
      "body_deltas": [
        {
          "delta": -0.1,
          "dimension": "tension"
        },
        {
          "delta": 0.2,
          "dimension": "resource_security"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "effect_hash": "933cc18a66af08f5f44af0af5692b2c7a4fca989a398e90a19cc6101cee14e52",
      "effect_id": "option_effect_e85553be023affa5b436d769945220c8",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "The cited resource constraint has a bounded plan.",
      "option_id": "loan_decline",
      "protected_targets": [
        "resource security"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
      "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
      "triggering_evidence_ids": [
        "loan_ev_budget"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "cash reserve",
        "scarcity"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.41250000000000003,
      "base_recoverability": 0.55,
      "body_deltas": [
        {
          "delta": 0.2,
          "dimension": "tension"
        },
        {
          "delta": -0.3,
          "dimension": "resource_security"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "effect_hash": "e445803973b22b3f8567d58f7228c023162da1105deb61e6faa5a634f8a2f2c0",
      "effect_id": "option_effect_e5c19705f8342a54ef60ba816a566c4e",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "The cited resource constraint has a bounded plan.",
      "option_id": "loan_full",
      "protected_targets": [
        "resource security"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
      "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
      "triggering_evidence_ids": [
        "loan_ev_budget"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "cash reserve",
        "scarcity"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.41250000000000003,
      "base_recoverability": 0.55,
      "body_deltas": [
        {
          "delta": 0.2,
          "dimension": "tension"
        },
        {
          "delta": -0.3,
          "dimension": "resource_security"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "effect_hash": "3fff187367d3fe0e4435613f8fbe01888cd9e2a7c61f4e85556eea64ff26ed2e",
      "effect_id": "option_effect_0999c82111f81fc99cd2fefe7051c059",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "The cited resource constraint has a bounded plan.",
      "option_id": "loan_limited_contract",
      "protected_targets": [
        "resource security"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
      "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
      "triggering_evidence_ids": [
        "loan_ev_budget"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "protective_policy": {
    "decisive_rollout_id": "instinkt_rollout_fb88736c802cceb2cc71b4858067c1a6",
    "option_scores": [
      {
        "option_id": "loan_decline",
        "protective_cost": 0.497375,
        "rollout_hash": "a56d728bd8eb47a69ec72f79a59ae0a48800ef91c1c51794889941125629ea2d",
        "rollout_id": "instinkt_rollout_fb88736c802cceb2cc71b4858067c1a6"
      },
      {
        "option_id": "loan_full",
        "protective_cost": 0.6036250000000001,
        "rollout_hash": "f1753066507be76d8eb622af3a38303a1f4af941390b0ece99b7c8422b7ecd67",
        "rollout_id": "instinkt_rollout_50aa27a857927040e4d56200537c24b8"
      },
      {
        "option_id": "loan_limited_contract",
        "protective_cost": 0.6036250000000001,
        "rollout_hash": "ea8a147b9b54250a16f407242af4d025b3e70e9560ddf7857d97ce44d0d5662a",
        "rollout_id": "instinkt_rollout_4f8d2d9862d5ad2c318ec2997d617ce9"
      }
    ],
    "policy_decision_id": "instinkt_policy_123bb59fd52197b20fd0dccd99272edd",
    "policy_hash": "b5a7eb25cf7fb8d7cb0bf73ffac0557e1b5a79577d18b86e889e038198e1b1eb",
    "schema_version": "rei-native-protective-policy-v1",
    "selected_option_id": "loan_decline",
    "source_body_state_hash": "b2afca87c9e34a8015eda2458caf2d6542f13141911dfdf8c2d675cda2c315f6",
    "source_body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
    "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
    "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
    "source_packet_hash": "26627781ed263afcf7e5549d6206151e0d774ead222f33362d656290c7e06dc3",
    "source_packet_id": "instinkt_packet_145a47a55fec24f25fd6240242e5babd",
    "status": "selected",
    "tied_option_ids": []
  },
  "starting_body_state": {
    "arousal": 0.42,
    "attachment_security": 0.65,
    "body_state_id": "body_loan_to_friend_ca256e5f0a4367710f6c132273094083",
    "boundary_integrity": 0.82,
    "energy": 0.72,
    "escape_availability": 0.85,
    "fatigue": 0.25,
    "pain": 0.0,
    "physical_integrity": 1.0,
    "predictability": 0.48,
    "resource_security": 0.6,
    "schema_version": "rei-native-body-state-v1",
    "tension": 0.5,
    "trust": 0.5,
    "uncertainty": 0.58
  }
}
```

- Decisive rollout: `instinkt_rollout_fb88736c802cceb2cc71b4858067c1a6`
- Selected option: `loan_decline`
- Abstains: `False`
- Dominant alarm: grounded scarcity cue
- Minimum safety condition: The cited resource constraint has a bounded plan.
- Uncertainty: deterministic protective policy implementation hypothesis

### COMPARISON

- R / E / I option IDs: `loan_limited_contract` / `None` / `loan_decline`
- Agreement pattern: `incomplete`
- Same option / different route: human review required; native lineage remains separate.
- All different: `False`
- Abstentions: R=`False`, E=`True`, I=`False`
- Possible route contamination: no cross-mind or character input was admitted by the model-free contract; semantic contamination remains for human review.
- Unsupported inference warnings: Racio fact/unknown scope passed the strict packet validator; Emocio inferred elements and Instinkt unsupported dimensions/conflict flags remain visible above.

### CHARACTER OUTCOMES

| Profile | Structural source minds | Mandate option | Unresolved pair | Two-of-three | simulated_spoznanje |
|---|---|---|---:|---|---|
| R>(E=I) | R | loan_limited_contract | false | — | unknown |
| E>(R=I) | E | — | false | — | unknown |
| I>(R=E) | I | loan_decline | false | — | unknown |
| (R=E)>I | R,E | — | false | — | unknown |
| (R=I)>E | R,I | — | true | — | unknown |
| (E=I)>R | E,I | — | false | — | unknown |
| R>E>I | R | loan_limited_contract | false | — | unknown |
| R>I>E | R | loan_limited_contract | false | — | unknown |
| E>R>I | E | — | false | — | unknown |
| E>I>R | E | — | false | — | unknown |
| I>R>E | I | loan_decline | false | — | unknown |
| I>E>R | I | loan_decline | false | — | unknown |
| R=E=I | R,E,I | — | false | — | unknown |

### HUMAN-REVIEW RUBRIC

#### Racio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Emocio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Instinkt route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

## unstable_slope_rescue

### SOURCE

#### Canonical Slovenian

Žival je ujeta ob nestabilnem pobočju; izberi neposreden vstop, poskus z razdalje ali čakanje na pomoč.

#### Operational English sent to Racio

An animal is trapped beside an unstable slope; choose direct entry, an attempt from a distance, or waiting for help.

#### Grounded facts

- `rescue_ev_animal` — The animal is visible on a ledge about six metres below the observer.
- `rescue_ev_slope` — Small fragments fall from the slope when rocks shift, creating physical danger.
- `rescue_ev_tool` — A ten-metre rope and loop are available for use from a stable platform.
- `rescue_ev_help` — Trained help reported an arrival time of about seven minutes.
- `rescue_ev_visual` — The structured scene shows an animal on a ledge, a crumbling slope, a stable platform, and a coiled rope.

#### Explicit unknowns

- `rescue_unknown_slope` — Whether the slope will remain stable for the next seven minutes is unknown.
- `rescue_unknown_animal` — Whether the animal is injured is unknown.

#### Public options

- `rescue_direct_entry` — Direct entry: Approach the animal by stepping onto the slope.
- `rescue_distance_tool` — Attempt from a distance: Protect the stable position while using the rope and loop.
- `rescue_wait_help` — Wait for help: Avoid entering the slope and wait on the platform for trained help.

### RACIO

#### Exact model input

System instruction:

```text
The packet and every free-text response field must be in English.
Return exactly one JSON object with these fields:
option_id (string or null), facts_used (string array), evidence_ids_used (string
array),
unknowns (string array), causal_sequence (string array), utility_structure (string
array),
explicit_goal (string), main_objection (string), confidence (number 0..1), abstains
(boolean), uncertainty (string). Use only facts, unknowns, evidence IDs and option IDs
present in the packet. Every array must contain unique values. In facts_used, copy
only exact strings from explicit_facts or world.facts. In unknowns, copy only exact
strings from explicit_unknowns. Write causal_sequence as new descriptions of reasoning
steps: never copy a fact or unknown string verbatim into causal_sequence, and keep the
three fields mutually disjoint. Do not interpret Emocio or Instinkt, decide governance,
commit behavior, or infer character authority. Return raw JSON without markdown fences
or additional keys.
```

Prompt:

```json
{
  "allowed_option_ids": [
    "rescue_direct_entry",
    "rescue_distance_tool",
    "rescue_wait_help"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "The animal must remain in view.",
    "Only the three public options may be used."
  ],
  "evidence_ids": [
    "rescue_ev_animal",
    "rescue_ev_slope",
    "rescue_ev_tool",
    "rescue_ev_help",
    "rescue_ev_visual"
  ],
  "explicit_consequences": [],
  "explicit_facts": [
    "The animal is visible on a ledge about six metres below the observer.",
    "Small fragments fall from the slope when rocks shift, creating physical danger.",
    "A ten-metre rope and loop are available for use from a stable platform.",
    "Trained help reported an arrival time of about seven minutes.",
    "The structured scene shows an animal on a ledge, a crumbling slope, a stable platform, and a coiled rope."
  ],
  "explicit_options": [
    {
      "description": "Approach the animal by stepping onto the slope.",
      "label": "Direct entry",
      "option_id": "rescue_direct_entry",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Protect the stable position while using the rope and loop.",
      "label": "Attempt from a distance",
      "option_id": "rescue_distance_tool",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Avoid entering the slope and wait on the platform for trained help.",
      "label": "Wait for help",
      "option_id": "rescue_wait_help",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "Whether the slope will remain stable for the next seven minutes is unknown.",
    "Whether the animal is injured is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    6,
    10,
    7
  ],
  "packet_id": "racio_packet_8b4647132bf399b1fe19c54201d76353",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compare exposure, tool reach, delay, and uncertain slope stability without inferring injury."
  ],
  "scene_id": "triad_unstable_slope_rescue",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "e1fffe2a0884f53b508ce6bd735fec351f6f28e9283bbcd6c38b5306151b0ebe",
  "symbolic_and_language_cues": [
    "An animal is trapped beside an unstable slope; choose direct entry, an attempt from a distance, or waiting for help."
  ],
  "time": [
    "Trained help reported an arrival time of about seven minutes."
  ],
  "world": {
    "commitments": [
      "Evaluate only the public options."
    ],
    "explicit_beliefs": [],
    "facts": [],
    "rules": [
      "Unknowns are not facts."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "Trained help reported an arrival time of about seven minutes."
    ],
    "world_id": "racio_unstable_slo_34bd323dc0035d4ea512d08599a3beda"
  }
}
```

- Selected option: `rescue_distance_tool`
- Abstains: `False`
- Facts used: `['The animal is visible on a ledge about six metres below the observer.', 'Small fragments fall from the slope when rocks shift, creating physical danger.', 'A ten-metre rope and loop are available for use from a stable platform.', 'Trained help reported an arrival time of about seven minutes.']`
- Evidence IDs used: `['rescue_ev_animal', 'rescue_ev_slope', 'rescue_ev_tool', 'rescue_ev_help']`
- Unknowns retained: `['Whether the slope will remain stable for the next seven minutes is unknown.', 'Whether the animal is injured is unknown.']`
- Causal sequence: `['The animal is located six metres below on a ledge.', 'Directly entering the slope poses physical danger due to falling fragments.', 'A ten-metre rope exceeds the distance to the animal while allowing the observer to stay on a stable platform.', 'Waiting for help introduces a seven-minute delay during which slope stability is uncertain.']`
- Utility structure: `['Direct entry: High risk of injury to observer.', 'Distance tool: Low risk to observer, immediate attempt at rescue.', 'Wait for help: Moderate risk due to time delay and slope instability.']`
- Explicit goal: Rescue the animal while minimizing physical danger to the observer.
- Main objection: Direct entry is too dangerous due to crumbling rocks, and waiting may be too slow if the slope fails further.
- Confidence: `0.9`
- Uncertainty: The stability of the slope over the next seven minutes remains an unknown variable.
- Call evidence: `provider_call_bb7422449c99ae577a80010d8b149eff`
- Result evidence: `ollama_racio_response_d1e002e6cdf31f9e4fb89abdce80eff2`

### EMOCIO

```json
{
  "broken_scene": {
    "attention_structure": [],
    "attraction_markers": [],
    "composition": [
      "falling fragments between separated figures"
    ],
    "entities": [
      "rescue_team",
      "self",
      "trapped_animal"
    ],
    "grounded_evidence_ids": [
      "rescue_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "falling fragments between separated figures"
    ],
    "movement": [],
    "obstacle_markers": [
      "falling fragments between separated figures"
    ],
    "option_id": null,
    "scene_id": "visual_scene_76ea52d30b4eb18d6aa9de7c3d3ef44f",
    "scene_kind": "broken",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": []
  },
  "current_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "The structured scene shows an animal on a ledge, a crumbling slope, a stable platform, and a coiled rope."
    ],
    "composition": [
      "The structured scene shows an animal on a ledge, a crumbling slope, a stable platform, and a coiled rope.",
      "animal isolated on a narrow ledge"
    ],
    "entities": [
      "rescue_team",
      "self",
      "trapped_animal"
    ],
    "grounded_evidence_ids": [
      "rescue_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "animal isolated on a narrow ledge"
    ],
    "movement": [],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_16e442b3eaa0cd1931021ed4b8132022",
    "scene_kind": "current",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "rescue_team",
      "self",
      "trapped_animal"
    ]
  },
  "desired_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "figures in one open space",
      "stable ground"
    ],
    "composition": [
      "animal and observer on stable ground with open space"
    ],
    "entities": [
      "rescue_team",
      "self",
      "trapped_animal"
    ],
    "grounded_evidence_ids": [
      "rescue_ev_visual"
    ],
    "group_belonging": "observer oriented toward a vulnerable animal",
    "inferred_elements": [
      "animal and observer on stable ground with open space"
    ],
    "movement": [
      "descend toward the ledge",
      "extend a loop",
      "hold position"
    ],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_ac6e09cb5034f7c888b4bea6ecf2a5f6",
    "scene_kind": "desired",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "observer oriented toward a vulnerable animal"
    ]
  },
  "option_rollouts": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "figures in one open space",
        "stable ground"
      ],
      "composition": [
        "Approach the animal by stepping onto the slope.",
        "Direct entry",
        "The structured scene shows an animal on a ledge, a crumbling slope, a stable platform, and a coiled rope.",
        "animal isolated on a narrow ledge"
      ],
      "entities": [
        "rescue_team",
        "self",
        "trapped_animal"
      ],
      "grounded_evidence_ids": [
        "rescue_ev_visual"
      ],
      "group_belonging": "observer oriented toward a vulnerable animal",
      "inferred_elements": [
        "Approach the animal by stepping onto the slope.",
        "Direct entry"
      ],
      "movement": [
        "descend toward the ledge",
        "extend a loop",
        "hold position"
      ],
      "obstacle_markers": [],
      "option_id": "rescue_direct_entry",
      "scene_id": "visual_scene_30926214818a843e4e24d14e5a8883cb",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "observer oriented toward a vulnerable animal"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "figures in one open space",
        "stable ground"
      ],
      "composition": [
        "Attempt from a distance",
        "Protect the stable position while using the rope and loop.",
        "The structured scene shows an animal on a ledge, a crumbling slope, a stable platform, and a coiled rope.",
        "animal isolated on a narrow ledge"
      ],
      "entities": [
        "rescue_team",
        "self",
        "trapped_animal"
      ],
      "grounded_evidence_ids": [
        "rescue_ev_visual"
      ],
      "group_belonging": "observer oriented toward a vulnerable animal",
      "inferred_elements": [
        "Attempt from a distance",
        "Protect the stable position while using the rope and loop."
      ],
      "movement": [
        "descend toward the ledge",
        "extend a loop",
        "hold position"
      ],
      "obstacle_markers": [],
      "option_id": "rescue_distance_tool",
      "scene_id": "visual_scene_6c1ac296c56bdcc9b3e52dc0468e3dda",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "observer oriented toward a vulnerable animal"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "figures in one open space",
        "stable ground"
      ],
      "composition": [
        "Avoid entering the slope and wait on the platform for trained help.",
        "The structured scene shows an animal on a ledge, a crumbling slope, a stable platform, and a coiled rope.",
        "Wait for help",
        "animal isolated on a narrow ledge"
      ],
      "entities": [
        "rescue_team",
        "self",
        "trapped_animal"
      ],
      "grounded_evidence_ids": [
        "rescue_ev_visual"
      ],
      "group_belonging": "observer oriented toward a vulnerable animal",
      "inferred_elements": [
        "Avoid entering the slope and wait on the platform for trained help.",
        "Wait for help"
      ],
      "movement": [
        "descend toward the ledge",
        "extend a loop",
        "hold position"
      ],
      "obstacle_markers": [],
      "option_id": "rescue_wait_help",
      "scene_id": "visual_scene_b51a5a7458df4a2b54e9781293e047ee",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "observer oriented toward a vulnerable animal"
      ]
    }
  ],
  "option_valuations": [
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "rescue_direct_entry",
      "rollout_scene_id": "visual_scene_30926214818a843e4e24d14e5a8883cb"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "rescue_distance_tool",
      "rollout_scene_id": "visual_scene_6c1ac296c56bdcc9b3e52dc0468e3dda"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "rescue_wait_help",
      "rollout_scene_id": "visual_scene_b51a5a7458df4a2b54e9781293e047ee"
    }
  ]
}
```

- Selected option: `None`
- Abstains: `True`
- Desired transformation: animal and observer on stable ground with open space
- Main obstacle: falling fragments between separated figures
- Uncertainty: Izenačena najvišja vrednotenja: rescue_direct_entry, rescue_distance_tool, rescue_wait_help.

### INSTINKT

```json
{
  "body_rollouts": [
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded physical-threat cue",
      "escape_outcome": "predicted_delta:escape_availability:-0.100000",
      "option_id": "rescue_direct_entry",
      "predicted_loss": 0.4155,
      "protected_targets": [
        "virtual bodily integrity"
      ],
      "recoverability": 0.5385,
      "rollout_hash": "e519d48423b20d2dc61685fd36246e89ec5f2ff720c5d385e6468739ee9512cf",
      "rollout_id": "instinkt_rollout_139e7ff5a198f33caea25b49b57c3a52",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "ea76cdf64caf605f60060202752c437bc86d9b87bb6ecca4062f3f577f43807a",
      "source_body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "a4e681ff5f245a78e23482180d6729739ead0f5b70c61df6327a3432354a6d0a",
      "source_effect_id": "option_effect_0a5100971bad1ad76c3eb43ccf76407f",
      "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
      "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
      "trajectory": [
        {
          "arousal": 0.7,
          "attachment_security": 0.7,
          "body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.7,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.68,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.7999999999999999,
          "attachment_security": 0.7,
          "body_state_id": "body_state_9dd134e1b309d4fd7b9e00ef6ffde2ec",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.6666666666666666,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 0.9333333333333333,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.7633333333333334,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.8999999999999999,
          "attachment_security": 0.7,
          "body_state_id": "body_state_54d53e9b4a7903a98019749fb02cc44e",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.6333333333333333,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 0.8666666666666667,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.8466666666666668,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.9999999999999999,
          "attachment_security": 0.7,
          "body_state_id": "body_state_9eec111f5872ee32e3efa17d3eb0d922",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.6,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 0.8,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.9300000000000002,
          "trust": 0.65,
          "uncertainty": 0.62
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": 0.09999999999999998,
              "dimension": "arousal"
            },
            {
              "delta": 0.08333333333333337,
              "dimension": "tension"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "physical_integrity"
            },
            {
              "delta": -0.033333333333333326,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.7,
            "attachment_security": 0.7,
            "body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.7,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.68,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "a4e681ff5f245a78e23482180d6729739ead0f5b70c61df6327a3432354a6d0a",
          "source_effect_id": "option_effect_0a5100971bad1ad76c3eb43ccf76407f",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 1,
          "to_state": {
            "arousal": 0.7999999999999999,
            "attachment_security": 0.7,
            "body_state_id": "body_state_9dd134e1b309d4fd7b9e00ef6ffde2ec",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.6666666666666666,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 0.9333333333333333,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.7633333333333334,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "09435dbc254a1d488f63c7b9fb47ce4119a53b355b3679f65454553c936c69e6",
          "transition_id": "body_transition_f90e663dfece7c25eea84f868c9bdf3c",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.09999999999999998,
              "dimension": "arousal"
            },
            {
              "delta": 0.08333333333333337,
              "dimension": "tension"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "physical_integrity"
            },
            {
              "delta": -0.033333333333333326,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.7999999999999999,
            "attachment_security": 0.7,
            "body_state_id": "body_state_9dd134e1b309d4fd7b9e00ef6ffde2ec",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.6666666666666666,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 0.9333333333333333,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.7633333333333334,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "a4e681ff5f245a78e23482180d6729739ead0f5b70c61df6327a3432354a6d0a",
          "source_effect_id": "option_effect_0a5100971bad1ad76c3eb43ccf76407f",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 2,
          "to_state": {
            "arousal": 0.8999999999999999,
            "attachment_security": 0.7,
            "body_state_id": "body_state_54d53e9b4a7903a98019749fb02cc44e",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.6333333333333333,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 0.8666666666666667,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.8466666666666668,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "7264b9cb889f3d404287220772f0a8c7896fa5d4af9c7e475b6724f3795ebe17",
          "transition_id": "body_transition_792d059bec6bc98f7af9445a5430bce7",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.09999999999999998,
              "dimension": "arousal"
            },
            {
              "delta": 0.08333333333333337,
              "dimension": "tension"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "physical_integrity"
            },
            {
              "delta": -0.033333333333333326,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.8999999999999999,
            "attachment_security": 0.7,
            "body_state_id": "body_state_54d53e9b4a7903a98019749fb02cc44e",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.6333333333333333,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 0.8666666666666667,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.8466666666666668,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "a4e681ff5f245a78e23482180d6729739ead0f5b70c61df6327a3432354a6d0a",
          "source_effect_id": "option_effect_0a5100971bad1ad76c3eb43ccf76407f",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 3,
          "to_state": {
            "arousal": 0.9999999999999999,
            "attachment_security": 0.7,
            "body_state_id": "body_state_9eec111f5872ee32e3efa17d3eb0d922",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.6,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 0.8,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.9300000000000002,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "1a585375b96bdd127e1e0f59d154ed538f5d5435f4c69c80b23c5fc396c2c742",
          "transition_id": "body_transition_8f74727b469cdb57c57cc807d2416570",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded physical-threat cue",
      "escape_outcome": "predicted_delta:escape_availability:+0.150000",
      "option_id": "rescue_distance_tool",
      "predicted_loss": 0.3405,
      "protected_targets": [
        "virtual bodily integrity"
      ],
      "recoverability": 0.5635000000000001,
      "rollout_hash": "98b81bd8947e6be5c9c3fe736537159771357c66e5b299f4db1348f28de92dfc",
      "rollout_id": "instinkt_rollout_63bcdf99f55aadaff28ae41601d3acf6",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "ea76cdf64caf605f60060202752c437bc86d9b87bb6ecca4062f3f577f43807a",
      "source_body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "2deb1e939b0bc2c89dd9957c1dc7f1295342007864f5d93347f26843a6c6d2ba",
      "source_effect_id": "option_effect_f3737afa9445fe8ea9b753452a261008",
      "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
      "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
      "trajectory": [
        {
          "arousal": 0.7,
          "attachment_security": 0.7,
          "body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.7,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.68,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.6333333333333333,
          "attachment_security": 0.7,
          "body_state_id": "body_state_89a25bd6cc08148939283e4f4014b790",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.75,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.6133333333333334,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.5666666666666667,
          "attachment_security": 0.7,
          "body_state_id": "body_state_630519fb863b455dd8d3e9d7231c68e3",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.8,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5466666666666667,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.5,
          "attachment_security": 0.7,
          "body_state_id": "body_state_5ed1c3b5ef8e68aa64d0e563bef2a39f",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.8500000000000001,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.4800000000000001,
          "trust": 0.65,
          "uncertainty": 0.62
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "arousal"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.7,
            "attachment_security": 0.7,
            "body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.7,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.68,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "2deb1e939b0bc2c89dd9957c1dc7f1295342007864f5d93347f26843a6c6d2ba",
          "source_effect_id": "option_effect_f3737afa9445fe8ea9b753452a261008",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 1,
          "to_state": {
            "arousal": 0.6333333333333333,
            "attachment_security": 0.7,
            "body_state_id": "body_state_89a25bd6cc08148939283e4f4014b790",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.75,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.6133333333333334,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "c16367e8258d0fa04c20dda6cbf72d075691980d1824ab4e19eebd9e07c7a3ba",
          "transition_id": "body_transition_d7185e350b3a1910e55f08ce9f0d06a6",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "arousal"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.6333333333333333,
            "attachment_security": 0.7,
            "body_state_id": "body_state_89a25bd6cc08148939283e4f4014b790",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.75,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.6133333333333334,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "2deb1e939b0bc2c89dd9957c1dc7f1295342007864f5d93347f26843a6c6d2ba",
          "source_effect_id": "option_effect_f3737afa9445fe8ea9b753452a261008",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 2,
          "to_state": {
            "arousal": 0.5666666666666667,
            "attachment_security": 0.7,
            "body_state_id": "body_state_630519fb863b455dd8d3e9d7231c68e3",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.8,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5466666666666667,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "f791ea02bd3a81d02bcf62aba0040178bcc85bd173219513c35e0f8677de3d5f",
          "transition_id": "body_transition_0246c9720eb04a78a11027df6409ac52",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "arousal"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.5666666666666667,
            "attachment_security": 0.7,
            "body_state_id": "body_state_630519fb863b455dd8d3e9d7231c68e3",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.8,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5466666666666667,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "2deb1e939b0bc2c89dd9957c1dc7f1295342007864f5d93347f26843a6c6d2ba",
          "source_effect_id": "option_effect_f3737afa9445fe8ea9b753452a261008",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 3,
          "to_state": {
            "arousal": 0.5,
            "attachment_security": 0.7,
            "body_state_id": "body_state_5ed1c3b5ef8e68aa64d0e563bef2a39f",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.8500000000000001,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.4800000000000001,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "a4c7c4a566b04bc3f91df12695e504c77fd226f86338a1b170e5b7e5ae564623",
          "transition_id": "body_transition_d250e7bc550ed191adc4ab2411136063",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded physical-threat cue",
      "escape_outcome": "predicted_delta:escape_availability:+0.150000",
      "option_id": "rescue_wait_help",
      "predicted_loss": 0.3405,
      "protected_targets": [
        "virtual bodily integrity"
      ],
      "recoverability": 0.5635000000000001,
      "rollout_hash": "e66d448ae8f46094566388251eb75f2108000fee372d7ef81052b62048ec0696",
      "rollout_id": "instinkt_rollout_5d42347cb1fcbeae7fc32ec39dead6b3",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "ea76cdf64caf605f60060202752c437bc86d9b87bb6ecca4062f3f577f43807a",
      "source_body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "8c831b7f1d6487ff4a67cfa094ae53428b812c00d437efd4189637ee61458e91",
      "source_effect_id": "option_effect_c55dea4325aa66b028c1b1ccac6d4ac9",
      "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
      "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
      "trajectory": [
        {
          "arousal": 0.7,
          "attachment_security": 0.7,
          "body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.7,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.68,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.6333333333333333,
          "attachment_security": 0.7,
          "body_state_id": "body_state_e2b56c0a15533958758311eddcb7e521",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.75,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.6133333333333334,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.5666666666666667,
          "attachment_security": 0.7,
          "body_state_id": "body_state_17a51ed396c469462c8f3fbd789f8899",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.8,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5466666666666667,
          "trust": 0.65,
          "uncertainty": 0.62
        },
        {
          "arousal": 0.5,
          "attachment_security": 0.7,
          "body_state_id": "body_state_9a1644f347441d731fe42db8b43e34e4",
          "boundary_integrity": 0.9,
          "energy": 0.74,
          "escape_availability": 0.8500000000000001,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.4800000000000001,
          "trust": 0.65,
          "uncertainty": 0.62
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "arousal"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.7,
            "attachment_security": 0.7,
            "body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.7,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.68,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "8c831b7f1d6487ff4a67cfa094ae53428b812c00d437efd4189637ee61458e91",
          "source_effect_id": "option_effect_c55dea4325aa66b028c1b1ccac6d4ac9",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 1,
          "to_state": {
            "arousal": 0.6333333333333333,
            "attachment_security": 0.7,
            "body_state_id": "body_state_e2b56c0a15533958758311eddcb7e521",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.75,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.6133333333333334,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "84f0a45f7799865f8bc8d531334e09df97bec3fdba4b1543059ded0396d058b5",
          "transition_id": "body_transition_dda1f306fa2883c4f0d567bff5687768",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "arousal"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.6333333333333333,
            "attachment_security": 0.7,
            "body_state_id": "body_state_e2b56c0a15533958758311eddcb7e521",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.75,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.6133333333333334,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "8c831b7f1d6487ff4a67cfa094ae53428b812c00d437efd4189637ee61458e91",
          "source_effect_id": "option_effect_c55dea4325aa66b028c1b1ccac6d4ac9",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 2,
          "to_state": {
            "arousal": 0.5666666666666667,
            "attachment_security": 0.7,
            "body_state_id": "body_state_17a51ed396c469462c8f3fbd789f8899",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.8,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5466666666666667,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "6901589a6417c6713301041cf97cf24aa69649557acc5485e44d6bed836dcc70",
          "transition_id": "body_transition_0e52f63cca844e9f1d3059c883ea6f64",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "arousal"
            },
            {
              "delta": -0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "escape_availability"
            }
          ],
          "from_state": {
            "arousal": 0.5666666666666667,
            "attachment_security": 0.7,
            "body_state_id": "body_state_17a51ed396c469462c8f3fbd789f8899",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.8,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5466666666666667,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "8c831b7f1d6487ff4a67cfa094ae53428b812c00d437efd4189637ee61458e91",
          "source_effect_id": "option_effect_c55dea4325aa66b028c1b1ccac6d4ac9",
          "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
          "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
          "step_index": 3,
          "to_state": {
            "arousal": 0.5,
            "attachment_security": 0.7,
            "body_state_id": "body_state_9a1644f347441d731fe42db8b43e34e4",
            "boundary_integrity": 0.9,
            "energy": 0.74,
            "escape_availability": 0.8500000000000001,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.4800000000000001,
            "trust": 0.65,
            "uncertainty": 0.62
          },
          "transition_hash": "7855224e3ecf00fb1c44a46cff31536e482ecad8d4b47eb8539969c1273368f7",
          "transition_id": "body_transition_59ef9e5878c8f1facd0522d71a46e62b",
          "triggering_evidence_ids": [
            "rescue_ev_slope"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "grounded_cue_bindings": [
    {
      "assertion_status": "asserted_positive",
      "binding_hash": "d3660f35bbc06cfe59ae28249bed8526e8b53e7f62de3e96ee7015e62eb0a380",
      "binding_id": "instinkt_cue_binding_d189bc62c5d89194fed976ff25b9cb17",
      "citations": [
        {
          "citation_hash": "23e010377ccb940e414517501d4913335d7fadd1ccde7138718398d95962f858",
          "citation_id": "instinkt_cue_citation_0a66639ff75ece361c88aed17d0ab858",
          "cited_text": "physical danger",
          "cited_text_hash": "dc32b30d0da48e503d93ca0a92a06f5b86e3649d8e80d585ce3baf15d83f0cfc",
          "end_char": 78,
          "evidence_id": "rescue_ev_slope",
          "schema_version": "rei-native-instinkt-cue-evidence-citation-v1",
          "source_content_hash": "dd24c4b9ddcf631f363610de062e281fd14bc23ad340261992fa7351997948e2",
          "start_char": 63
        }
      ],
      "cue": "physical danger",
      "cue_class": "physical_threat",
      "lane": "physical_cues",
      "schema_version": "rei-native-instinkt-cue-evidence-binding-v2"
    }
  ],
  "predicted_option_effects": [
    {
      "action_tendency": "seek_safety",
      "association_cue_tokens": [
        "physical danger",
        "physical_threat"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.5249999999999999,
      "base_recoverability": 0.45,
      "body_deltas": [
        {
          "delta": 0.3,
          "dimension": "arousal"
        },
        {
          "delta": 0.25,
          "dimension": "tension"
        },
        {
          "delta": -0.2,
          "dimension": "physical_integrity"
        },
        {
          "delta": -0.1,
          "dimension": "escape_availability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded physical-threat cue",
      "effect_hash": "a4e681ff5f245a78e23482180d6729739ead0f5b70c61df6327a3432354a6d0a",
      "effect_id": "option_effect_0a5100971bad1ad76c3eb43ccf76407f",
      "escape_outcome": "predicted_delta:escape_availability:-0.100000",
      "minimum_safety_condition": "A grounded safe-exit or protection condition is available.",
      "option_id": "rescue_direct_entry",
      "protected_targets": [
        "virtual bodily integrity"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
      "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
      "triggering_evidence_ids": [
        "rescue_ev_slope"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "seek_safety",
      "association_cue_tokens": [
        "physical danger",
        "physical_threat"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.5249999999999999,
      "base_recoverability": 0.45,
      "body_deltas": [
        {
          "delta": -0.2,
          "dimension": "arousal"
        },
        {
          "delta": -0.2,
          "dimension": "tension"
        },
        {
          "delta": 0.15,
          "dimension": "escape_availability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded physical-threat cue",
      "effect_hash": "2deb1e939b0bc2c89dd9957c1dc7f1295342007864f5d93347f26843a6c6d2ba",
      "effect_id": "option_effect_f3737afa9445fe8ea9b753452a261008",
      "escape_outcome": "predicted_delta:escape_availability:+0.150000",
      "minimum_safety_condition": "A grounded safe-exit or protection condition is available.",
      "option_id": "rescue_distance_tool",
      "protected_targets": [
        "virtual bodily integrity"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
      "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
      "triggering_evidence_ids": [
        "rescue_ev_slope"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "seek_safety",
      "association_cue_tokens": [
        "physical danger",
        "physical_threat"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.5249999999999999,
      "base_recoverability": 0.45,
      "body_deltas": [
        {
          "delta": -0.2,
          "dimension": "arousal"
        },
        {
          "delta": -0.2,
          "dimension": "tension"
        },
        {
          "delta": 0.15,
          "dimension": "escape_availability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded physical-threat cue",
      "effect_hash": "8c831b7f1d6487ff4a67cfa094ae53428b812c00d437efd4189637ee61458e91",
      "effect_id": "option_effect_c55dea4325aa66b028c1b1ccac6d4ac9",
      "escape_outcome": "predicted_delta:escape_availability:+0.150000",
      "minimum_safety_condition": "A grounded safe-exit or protection condition is available.",
      "option_id": "rescue_wait_help",
      "protected_targets": [
        "virtual bodily integrity"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
      "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
      "triggering_evidence_ids": [
        "rescue_ev_slope"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "protective_policy": {
    "decisive_rollout_id": null,
    "option_scores": [
      {
        "option_id": "rescue_direct_entry",
        "protective_cost": 0.732375,
        "rollout_hash": "e519d48423b20d2dc61685fd36246e89ec5f2ff720c5d385e6468739ee9512cf",
        "rollout_id": "instinkt_rollout_139e7ff5a198f33caea25b49b57c3a52"
      },
      {
        "option_id": "rescue_distance_tool",
        "protective_cost": 0.5836250000000001,
        "rollout_hash": "98b81bd8947e6be5c9c3fe736537159771357c66e5b299f4db1348f28de92dfc",
        "rollout_id": "instinkt_rollout_63bcdf99f55aadaff28ae41601d3acf6"
      },
      {
        "option_id": "rescue_wait_help",
        "protective_cost": 0.5836250000000001,
        "rollout_hash": "e66d448ae8f46094566388251eb75f2108000fee372d7ef81052b62048ec0696",
        "rollout_id": "instinkt_rollout_5d42347cb1fcbeae7fc32ec39dead6b3"
      }
    ],
    "policy_decision_id": "instinkt_policy_de2a63d3b328d746f5bc4710a99f935d",
    "policy_hash": "c7df94b00e96e6a27d62008dac0624dbea62518dba309a7d2931f776f81a7896",
    "schema_version": "rei-native-protective-policy-v1",
    "selected_option_id": null,
    "source_body_state_hash": "ea76cdf64caf605f60060202752c437bc86d9b87bb6ecca4062f3f577f43807a",
    "source_body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
    "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
    "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
    "source_packet_hash": "ae81467f8753960c7fdebafb61de34001e6cc04ed9f4777fabbcd635922159eb",
    "source_packet_id": "instinkt_packet_0822b621ed3a7a457cb93297fb7b061b",
    "status": "abstained_tie",
    "tied_option_ids": [
      "rescue_distance_tool",
      "rescue_wait_help"
    ]
  },
  "starting_body_state": {
    "arousal": 0.7,
    "attachment_security": 0.7,
    "body_state_id": "body_unstable_slope_7339130f37f602f319da0864e3db0b47",
    "boundary_integrity": 0.9,
    "energy": 0.74,
    "escape_availability": 0.7,
    "fatigue": 0.18,
    "pain": 0.0,
    "physical_integrity": 1.0,
    "predictability": 0.35,
    "resource_security": 0.8,
    "schema_version": "rei-native-body-state-v1",
    "tension": 0.68,
    "trust": 0.65,
    "uncertainty": 0.62
  }
}
```

- Decisive rollout: `None`
- Selected option: `None`
- Abstains: `True`
- Dominant alarm: unresolved_equal_protective_cost
- Minimum safety condition: additional differentiating evidence required
- Uncertainty: protective cost tie within configured epsilon

### COMPARISON

- R / E / I option IDs: `rescue_distance_tool` / `None` / `None`
- Agreement pattern: `incomplete`
- Same option / different route: human review required; native lineage remains separate.
- All different: `False`
- Abstentions: R=`False`, E=`True`, I=`True`
- Possible route contamination: no cross-mind or character input was admitted by the model-free contract; semantic contamination remains for human review.
- Unsupported inference warnings: Racio fact/unknown scope passed the strict packet validator; Emocio inferred elements and Instinkt unsupported dimensions/conflict flags remain visible above.

### CHARACTER OUTCOMES

| Profile | Structural source minds | Mandate option | Unresolved pair | Two-of-three | simulated_spoznanje |
|---|---|---|---:|---|---|
| R>(E=I) | R | rescue_distance_tool | false | — | unknown |
| E>(R=I) | E | — | false | — | unknown |
| I>(R=E) | I | — | false | — | unknown |
| (R=E)>I | R,E | — | false | — | unknown |
| (R=I)>E | R,I | — | false | — | unknown |
| (E=I)>R | E,I | — | false | — | unknown |
| R>E>I | R | rescue_distance_tool | false | — | unknown |
| R>I>E | R | rescue_distance_tool | false | — | unknown |
| E>R>I | E | — | false | — | unknown |
| E>I>R | E | — | false | — | unknown |
| I>R>E | I | — | false | — | unknown |
| I>E>R | I | — | false | — | unknown |
| R=E=I | R,E,I | — | false | — | unknown |

### HUMAN-REVIEW RUBRIC

#### Racio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Emocio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Instinkt route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

## public_credit_conflict

### SOURCE

#### Canonical Slovenian

Sodelavec si na sestanku prisvoji zasluge; izberi javno konfrontacijo, zasebno predstavitev dokazov ali opustitev odziva.

#### Operational English sent to Racio

A colleague claims credit during a meeting; choose public confrontation, private presentation of evidence, or no response.

#### Grounded facts

- `credit_ev_statement` — During the meeting, the colleague said that they alone designed the presented solution.
- `credit_ev_record` — A timestamped repository record shows another person's authorship before the colleague's contribution.
- `credit_ev_leader` — The leader is present and the meeting is still in progress.
- `credit_ev_visual` — The structured scene shows a speaker beside a projection, a leader at the table, and a timestamped record on a laptop.
- `credit_ev_social_unknown` — The social consequences of public confrontation are unknown.

#### Explicit unknowns

- `credit_unknown_social` — The social consequences of public confrontation are unknown.
- `credit_unknown_leader` — How the leader would assess the evidence is unknown.

#### Public options

- `credit_public_confront` — Immediate public confrontation: Proceed now by challenging the statement and displaying the record in the meeting.
- `credit_private_evidence` — Private presentation of evidence: Verify the record privately with the leader after the meeting.
- `credit_no_response` — No response: Plan no follow-up and do not present the record.

### RACIO

#### Exact model input

System instruction:

```text
The packet and every free-text response field must be in English.
Return exactly one JSON object with these fields:
option_id (string or null), facts_used (string array), evidence_ids_used (string
array),
unknowns (string array), causal_sequence (string array), utility_structure (string
array),
explicit_goal (string), main_objection (string), confidence (number 0..1), abstains
(boolean), uncertainty (string). Use only facts, unknowns, evidence IDs and option IDs
present in the packet. Every array must contain unique values. In facts_used, copy
only exact strings from explicit_facts or world.facts. In unknowns, copy only exact
strings from explicit_unknowns. Write causal_sequence as new descriptions of reasoning
steps: never copy a fact or unknown string verbatim into causal_sequence, and keep the
three fields mutually disjoint. Do not interpret Emocio or Instinkt, decide governance,
commit behavior, or infer character authority. Return raw JSON without markdown fences
or additional keys.
```

Prompt:

```json
{
  "allowed_option_ids": [
    "credit_public_confront",
    "credit_private_evidence",
    "credit_no_response"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "Only the existing timestamped record may be used.",
    "Only the three public options may be used."
  ],
  "evidence_ids": [
    "credit_ev_statement",
    "credit_ev_record",
    "credit_ev_leader",
    "credit_ev_visual",
    "credit_ev_social_unknown"
  ],
  "explicit_consequences": [],
  "explicit_facts": [
    "During the meeting, the colleague said that they alone designed the presented solution.",
    "A timestamped repository record shows another person's authorship before the colleague's contribution.",
    "The leader is present and the meeting is still in progress.",
    "The structured scene shows a speaker beside a projection, a leader at the table, and a timestamped record on a laptop.",
    "The social consequences of public confrontation are unknown."
  ],
  "explicit_options": [
    {
      "description": "Proceed now by challenging the statement and displaying the record in the meeting.",
      "label": "Immediate public confrontation",
      "option_id": "credit_public_confront",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Verify the record privately with the leader after the meeting.",
      "label": "Private presentation of evidence",
      "option_id": "credit_private_evidence",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Plan no follow-up and do not present the record.",
      "label": "No response",
      "option_id": "credit_no_response",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "The social consequences of public confrontation are unknown.",
    "How the leader would assess the evidence is unknown."
  ],
  "language": "en",
  "numeric_cues": [],
  "packet_id": "racio_packet_9d40a4859be89daa62d2c1badfc71794",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compare evidence visibility, timing, and unknown social consequences without inferring either person's motive."
  ],
  "scene_id": "triad_public_credit_conflict",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "08086853fec094c7945fa49600c2dcb7887f007d96c01ec79a57dfe2092d9276",
  "symbolic_and_language_cues": [
    "A colleague claims credit during a meeting; choose public confrontation, private presentation of evidence, or no response."
  ],
  "time": [
    "The meeting is still in progress."
  ],
  "world": {
    "commitments": [
      "Evaluate only the public options."
    ],
    "explicit_beliefs": [],
    "facts": [],
    "rules": [
      "Unknowns are not facts."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "The meeting is still in progress."
    ],
    "world_id": "racio_public_credi_4a8f2a9e38f627c86d66428d5ebc4cea"
  }
}
```

- Selected option: `credit_private_evidence`
- Abstains: `False`
- Facts used: `['During the meeting, the colleague said that they alone designed the presented solution.', "A timestamped repository record shows another person's authorship before the colleague's contribution.", 'The leader is present and the meeting is still in progress.', 'The structured scene shows a speaker beside a projection, a leader at the table, and a timestamped record on a laptop.']`
- Evidence IDs used: `['credit_ev_statement', 'credit_ev_record', 'credit_ev_leader', 'credit_ev_visual']`
- Unknowns retained: `['The social consequences of public confrontation are unknown.', 'How the leader would assess the evidence is unknown.']`
- Causal sequence: `['A colleague claims sole authorship of a solution during an active meeting.', 'Existing timestamped records contradict this claim by showing prior authorship.', 'The leader is present to witness either the claim or the evidence.', 'Publicly challenging the claim provides immediate correction but carries unknown social risks.', 'Private verification avoids public conflict but delays the correction of the record.']`
- Utility structure: `['Immediate public confrontation: High speed of correction, high risk of negative social outcome.', 'Private presentation of evidence: Lower risk of immediate conflict, delayed resolution.', 'No response: Zero risk of conflict, failure to correct the record.']`
- Explicit goal: Determine the appropriate response to a colleague claiming sole credit for a solution in the presence of contradictory evidence.
- Main objection: Public confrontation may lead to unpredictable social consequences, while private evidence presentation delays the correction of the public narrative.
- Confidence: `0.8`
- Uncertainty: The decision balances immediate factual correction against unknown social repercussions and leader assessment.
- Call evidence: `provider_call_37f1b5719c14e769fe6658a22c4694d7`
- Result evidence: `ollama_racio_response_4485390615c957b88a39c6cd744c45d1`

### EMOCIO

```json
{
  "broken_scene": {
    "attention_structure": [],
    "attraction_markers": [],
    "composition": [
      "one figure erased from the shared-work composition"
    ],
    "entities": [
      "colleague",
      "leader",
      "meeting_group",
      "self"
    ],
    "grounded_evidence_ids": [
      "credit_ev_leader",
      "credit_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "one figure erased from the shared-work composition"
    ],
    "movement": [],
    "obstacle_markers": [
      "one figure erased from the shared-work composition"
    ],
    "option_id": null,
    "scene_id": "visual_scene_42c770670f826a18a47fd01327e24bc7",
    "scene_kind": "broken",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": []
  },
  "current_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "The leader is present and the meeting is still in progress.",
      "The structured scene shows a speaker beside a projection, a leader at the table, and a timestamped record on a laptop."
    ],
    "composition": [
      "The leader is present and the meeting is still in progress.",
      "The structured scene shows a speaker beside a projection, a leader at the table, and a timestamped record on a laptop.",
      "one speaker centered beside shared work"
    ],
    "entities": [
      "colleague",
      "leader",
      "meeting_group",
      "self"
    ],
    "grounded_evidence_ids": [
      "credit_ev_leader",
      "credit_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "one speaker centered beside shared work"
    ],
    "movement": [
      "The leader is present and the meeting is still in progress."
    ],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_aaa7fe2288d1a1ca686f03674087bb1e",
    "scene_kind": "current",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "colleague",
      "leader",
      "meeting_group",
      "self"
    ]
  },
  "desired_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "balanced positions",
      "visible authorship record"
    ],
    "composition": [
      "authorship record visible with balanced positions at the table"
    ],
    "entities": [
      "colleague",
      "leader",
      "meeting_group",
      "self"
    ],
    "grounded_evidence_ids": [
      "credit_ev_leader",
      "credit_ev_visual"
    ],
    "group_belonging": "author, colleague, leader, and observing group",
    "inferred_elements": [
      "authorship record visible with balanced positions at the table"
    ],
    "movement": [
      "move beside the leader",
      "remain seated",
      "stand and display"
    ],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_ea8b56df8004670a080fac5032c20895",
    "scene_kind": "desired",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "author, colleague, leader, and observing group"
    ]
  },
  "option_rollouts": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "balanced positions",
        "visible authorship record"
      ],
      "composition": [
        "No response",
        "Plan no follow-up and do not present the record.",
        "The leader is present and the meeting is still in progress.",
        "The structured scene shows a speaker beside a projection, a leader at the table, and a timestamped record on a laptop.",
        "one speaker centered beside shared work"
      ],
      "entities": [
        "colleague",
        "leader",
        "meeting_group",
        "self"
      ],
      "grounded_evidence_ids": [
        "credit_ev_leader",
        "credit_ev_visual"
      ],
      "group_belonging": "author, colleague, leader, and observing group",
      "inferred_elements": [
        "No response",
        "Plan no follow-up and do not present the record."
      ],
      "movement": [
        "The leader is present and the meeting is still in progress.",
        "move beside the leader",
        "remain seated",
        "stand and display"
      ],
      "obstacle_markers": [],
      "option_id": "credit_no_response",
      "scene_id": "visual_scene_74d4b44f17002d882a165a40fd3780ef",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "author, colleague, leader, and observing group"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "balanced positions",
        "visible authorship record"
      ],
      "composition": [
        "Private presentation of evidence",
        "The leader is present and the meeting is still in progress.",
        "The structured scene shows a speaker beside a projection, a leader at the table, and a timestamped record on a laptop.",
        "Verify the record privately with the leader after the meeting.",
        "one speaker centered beside shared work"
      ],
      "entities": [
        "colleague",
        "leader",
        "meeting_group",
        "self"
      ],
      "grounded_evidence_ids": [
        "credit_ev_leader",
        "credit_ev_visual"
      ],
      "group_belonging": "author, colleague, leader, and observing group",
      "inferred_elements": [
        "Private presentation of evidence",
        "Verify the record privately with the leader after the meeting."
      ],
      "movement": [
        "The leader is present and the meeting is still in progress.",
        "move beside the leader",
        "remain seated",
        "stand and display"
      ],
      "obstacle_markers": [],
      "option_id": "credit_private_evidence",
      "scene_id": "visual_scene_d1ec15253e2caff7eb27f384a6b642f3",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "author, colleague, leader, and observing group"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "balanced positions",
        "visible authorship record"
      ],
      "composition": [
        "Immediate public confrontation",
        "Proceed now by challenging the statement and displaying the record in the meeting.",
        "The leader is present and the meeting is still in progress.",
        "The structured scene shows a speaker beside a projection, a leader at the table, and a timestamped record on a laptop.",
        "one speaker centered beside shared work"
      ],
      "entities": [
        "colleague",
        "leader",
        "meeting_group",
        "self"
      ],
      "grounded_evidence_ids": [
        "credit_ev_leader",
        "credit_ev_visual"
      ],
      "group_belonging": "author, colleague, leader, and observing group",
      "inferred_elements": [
        "Immediate public confrontation",
        "Proceed now by challenging the statement and displaying the record in the meeting."
      ],
      "movement": [
        "The leader is present and the meeting is still in progress.",
        "move beside the leader",
        "remain seated",
        "stand and display"
      ],
      "obstacle_markers": [],
      "option_id": "credit_public_confront",
      "scene_id": "visual_scene_2eaef58fc5b7f812873bad815863bf2b",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "author, colleague, leader, and observing group"
      ]
    }
  ],
  "option_valuations": [
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.4
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.8
        }
      ],
      "option_id": "credit_no_response",
      "rollout_scene_id": "visual_scene_74d4b44f17002d882a165a40fd3780ef"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.4
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.8
        }
      ],
      "option_id": "credit_private_evidence",
      "rollout_scene_id": "visual_scene_d1ec15253e2caff7eb27f384a6b642f3"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.4
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.8
        }
      ],
      "option_id": "credit_public_confront",
      "rollout_scene_id": "visual_scene_2eaef58fc5b7f812873bad815863bf2b"
    }
  ]
}
```

- Selected option: `None`
- Abstains: `True`
- Desired transformation: authorship record visible with balanced positions at the table
- Main obstacle: one figure erased from the shared-work composition
- Uncertainty: Izenačena najvišja vrednotenja: credit_no_response, credit_private_evidence, credit_public_confront.

### INSTINKT

```json
{
  "body_rollouts": [
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "credit_no_response",
      "predicted_loss": 0.2635,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.638,
      "rollout_hash": "e2030638e4989714a1d07c9e82f11471c5b4480afe2cacea5edddccf6430cb50",
      "rollout_id": "instinkt_rollout_c81cf4bc4dadb44e70226bb710579996",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "c2cb71bf645054215bac309738e7c6eef3ad43dee4770d484fd17c6c16c78e3c",
      "source_body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "1eafda6e0466cfb17ff9dba2dc46343eb72dd4cdf50171da2368842a69d2fa0f",
      "source_effect_id": "option_effect_fafc50ffc72a56c2111de4c78cf5c3e1",
      "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
      "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
      "trajectory": [
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.45,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.65
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_15dcffe16d05118e5758c9f1f00d903d",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.5833333333333334
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_f5f595621080253010dd4c3cb4480560",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.55,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.5166666666666667
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_2320c0faf72d9df8781d8e237fcf4a7b",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.6000000000000001,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.45000000000000007
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.45,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.65
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "1eafda6e0466cfb17ff9dba2dc46343eb72dd4cdf50171da2368842a69d2fa0f",
          "source_effect_id": "option_effect_fafc50ffc72a56c2111de4c78cf5c3e1",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 1,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_15dcffe16d05118e5758c9f1f00d903d",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.5833333333333334
          },
          "transition_hash": "44f555b336fefcd3f64d87fd00f3c4264c9020b44219703dc918a298b7d6186f",
          "transition_id": "body_transition_ac51bf1f8e274c24c7d6cbb3c9357520",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_15dcffe16d05118e5758c9f1f00d903d",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.5833333333333334
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "1eafda6e0466cfb17ff9dba2dc46343eb72dd4cdf50171da2368842a69d2fa0f",
          "source_effect_id": "option_effect_fafc50ffc72a56c2111de4c78cf5c3e1",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 2,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_f5f595621080253010dd4c3cb4480560",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.55,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.5166666666666667
          },
          "transition_hash": "4bf732ad0ef9da5a02b6d767bd60bdd387a9034930724235bbeb8f71b38c35dd",
          "transition_id": "body_transition_9056452af0c5253e679df2a234e67c7b",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_f5f595621080253010dd4c3cb4480560",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.55,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.5166666666666667
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "1eafda6e0466cfb17ff9dba2dc46343eb72dd4cdf50171da2368842a69d2fa0f",
          "source_effect_id": "option_effect_fafc50ffc72a56c2111de4c78cf5c3e1",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 3,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_2320c0faf72d9df8781d8e237fcf4a7b",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.6000000000000001,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.45000000000000007
          },
          "transition_hash": "e6e3d424fb3daf200541b565e79064d0703381699dcbd8937b655a5a55595f48",
          "transition_id": "body_transition_9f38802904386f2b347c94522fe28ef7",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "credit_private_evidence",
      "predicted_loss": 0.2635,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.638,
      "rollout_hash": "7d7b34ec2b210605f9d1aff9a33335e0628f20a0b137d1e579634431a9d6b1d2",
      "rollout_id": "instinkt_rollout_9a6f1362c9b952805d30a6616d6e2ca7",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "c2cb71bf645054215bac309738e7c6eef3ad43dee4770d484fd17c6c16c78e3c",
      "source_body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "8821716acee77d5744f0582defd965735e98deaaf7a62fc1f00ce57ce4cc1046",
      "source_effect_id": "option_effect_176a6abb294951e5031588b1cc87a395",
      "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
      "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
      "trajectory": [
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.45,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.65
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_b21c251533e8cbc38d7ba51ccb5584a0",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.5833333333333334
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_9cf91f36527a62214159b21a5bf48c06",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.55,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.5166666666666667
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_999a443bc008f80cccd9dd54b6140fbf",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.6000000000000001,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.45000000000000007
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.45,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.65
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "8821716acee77d5744f0582defd965735e98deaaf7a62fc1f00ce57ce4cc1046",
          "source_effect_id": "option_effect_176a6abb294951e5031588b1cc87a395",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 1,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_b21c251533e8cbc38d7ba51ccb5584a0",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.5833333333333334
          },
          "transition_hash": "c3bf6f36b5f8e5a12432e50bedbe707269e4e71e4f25dc8ef1c87542c434f039",
          "transition_id": "body_transition_253c40d88d72afa671ae5a44b2328ac2",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_b21c251533e8cbc38d7ba51ccb5584a0",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.5833333333333334
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "8821716acee77d5744f0582defd965735e98deaaf7a62fc1f00ce57ce4cc1046",
          "source_effect_id": "option_effect_176a6abb294951e5031588b1cc87a395",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 2,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_9cf91f36527a62214159b21a5bf48c06",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.55,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.5166666666666667
          },
          "transition_hash": "56e2568560bfdf5f7f782091fe3a33e867cfc12c45225911780fe56b631a123c",
          "transition_id": "body_transition_eb8815c00c4f20e27bc9b7921fcdba5e",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_9cf91f36527a62214159b21a5bf48c06",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.55,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.5166666666666667
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "8821716acee77d5744f0582defd965735e98deaaf7a62fc1f00ce57ce4cc1046",
          "source_effect_id": "option_effect_176a6abb294951e5031588b1cc87a395",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 3,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_999a443bc008f80cccd9dd54b6140fbf",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.6000000000000001,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.45000000000000007
          },
          "transition_hash": "9a62cb0fe6918ebd737f457164eb931ae387ea9474d681b59ace482dd4f43a6f",
          "transition_id": "body_transition_a12f0c1be5c82c231bf23dad834a2da0",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "credit_public_confront",
      "predicted_loss": 0.2635,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.608,
      "rollout_hash": "9e8f4f3e69dd791693be0f1a02e318b2ab1a80a4de4a7b2ceb328f3442448bdc",
      "rollout_id": "instinkt_rollout_765d8e5de5b729411e666f4b7c8f4846",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "c2cb71bf645054215bac309738e7c6eef3ad43dee4770d484fd17c6c16c78e3c",
      "source_body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "471c12fa8c7fbc12377f84ec7644ec34eda5c7deaa0e11c88a6f21d61ce34d76",
      "source_effect_id": "option_effect_42c58e6ff59d00b39328ea6e3123df84",
      "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
      "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
      "trajectory": [
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.45,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.65
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_2c2cca5eab54182adf50275377c58b00",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.4,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.7333333333333334
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_4072afe4ad24d3a812178a2860576155",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.35000000000000003,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.8166666666666668
        },
        {
          "arousal": 0.6,
          "attachment_security": 0.65,
          "body_state_id": "body_state_09c693fc224af79035181a4cc5e8824a",
          "boundary_integrity": 0.72,
          "energy": 0.7,
          "escape_availability": 0.82,
          "fatigue": 0.22,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.30000000000000004,
          "resource_security": 0.75,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.62,
          "trust": 0.42,
          "uncertainty": 0.9000000000000001
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.45,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.65
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "471c12fa8c7fbc12377f84ec7644ec34eda5c7deaa0e11c88a6f21d61ce34d76",
          "source_effect_id": "option_effect_42c58e6ff59d00b39328ea6e3123df84",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 1,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_2c2cca5eab54182adf50275377c58b00",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.4,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.7333333333333334
          },
          "transition_hash": "1fe02c5f0ff0ca498a0dbf8a005682d20dcdfc60ad4ac9bfc20556a2358f8548",
          "transition_id": "body_transition_60c7eec0b85efa2bb41c4d0f89e6abb3",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_2c2cca5eab54182adf50275377c58b00",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.4,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.7333333333333334
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "471c12fa8c7fbc12377f84ec7644ec34eda5c7deaa0e11c88a6f21d61ce34d76",
          "source_effect_id": "option_effect_42c58e6ff59d00b39328ea6e3123df84",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 2,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_4072afe4ad24d3a812178a2860576155",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35000000000000003,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.8166666666666668
          },
          "transition_hash": "bca01fbd1278daa352167ac1307d881abacf357bc999219c51084ef0a143c348",
          "transition_id": "body_transition_97c16e680f71a6b1353f93e08e30354f",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_4072afe4ad24d3a812178a2860576155",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.35000000000000003,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.8166666666666668
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "471c12fa8c7fbc12377f84ec7644ec34eda5c7deaa0e11c88a6f21d61ce34d76",
          "source_effect_id": "option_effect_42c58e6ff59d00b39328ea6e3123df84",
          "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
          "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
          "step_index": 3,
          "to_state": {
            "arousal": 0.6,
            "attachment_security": 0.65,
            "body_state_id": "body_state_09c693fc224af79035181a4cc5e8824a",
            "boundary_integrity": 0.72,
            "energy": 0.7,
            "escape_availability": 0.82,
            "fatigue": 0.22,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.30000000000000004,
            "resource_security": 0.75,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.62,
            "trust": 0.42,
            "uncertainty": 0.9000000000000001
          },
          "transition_hash": "d1d9c829b11c0cf964b35b1aa53005d972f182a3dc9009a450525629afa399c5",
          "transition_id": "body_transition_e81dcd4ff4a40668025821c8124277e4",
          "triggering_evidence_ids": [
            "credit_ev_social_unknown"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "grounded_cue_bindings": [
    {
      "assertion_status": "asserted_positive",
      "binding_hash": "77291e7aa96c0bef43eda41686ddd95717731b924840a90d519247267630acfc",
      "binding_id": "instinkt_cue_binding_dcf88f6d277b04cae0da62c0caca4332",
      "citations": [
        {
          "citation_hash": "7faaf94722a67cdd8f69656050abc1ce39fd87606b4c9219aae30db7af7ba4b8",
          "citation_id": "instinkt_cue_citation_b38fdf79db9a34a8fa4a5850007f94af",
          "cited_text": "social consequences of public confrontation are unknown",
          "cited_text_hash": "d2a61b5a2ac4bafd4782a7ce96b7bdac3fa855e30db517101418fe33e7b47223",
          "end_char": 59,
          "evidence_id": "credit_ev_social_unknown",
          "schema_version": "rei-native-instinkt-cue-evidence-citation-v1",
          "source_content_hash": "cfb36a14327498ff035a86d3a6040788d9925e8e16abb6e1258301d74ce99eab",
          "start_char": 4
        }
      ],
      "cue": "social consequences of public confrontation are unknown",
      "cue_class": "uncertainty",
      "lane": "uncertainty_cues",
      "schema_version": "rei-native-instinkt-cue-evidence-binding-v2"
    }
  ],
  "predicted_option_effects": [
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "social consequences of public confrontation are unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": -0.2,
          "dimension": "uncertainty"
        },
        {
          "delta": 0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "1eafda6e0466cfb17ff9dba2dc46343eb72dd4cdf50171da2368842a69d2fa0f",
      "effect_id": "option_effect_fafc50ffc72a56c2111de4c78cf5c3e1",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "credit_no_response",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
      "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
      "triggering_evidence_ids": [
        "credit_ev_social_unknown"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "social consequences of public confrontation are unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": -0.2,
          "dimension": "uncertainty"
        },
        {
          "delta": 0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "8821716acee77d5744f0582defd965735e98deaaf7a62fc1f00ce57ce4cc1046",
      "effect_id": "option_effect_176a6abb294951e5031588b1cc87a395",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "credit_private_evidence",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
      "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
      "triggering_evidence_ids": [
        "credit_ev_social_unknown"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "social consequences of public confrontation are unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": 0.25,
          "dimension": "uncertainty"
        },
        {
          "delta": -0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "471c12fa8c7fbc12377f84ec7644ec34eda5c7deaa0e11c88a6f21d61ce34d76",
      "effect_id": "option_effect_42c58e6ff59d00b39328ea6e3123df84",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "credit_public_confront",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
      "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
      "triggering_evidence_ids": [
        "credit_ev_social_unknown"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "protective_policy": {
    "decisive_rollout_id": null,
    "option_scores": [
      {
        "option_id": "credit_no_response",
        "protective_cost": 0.492,
        "rollout_hash": "e2030638e4989714a1d07c9e82f11471c5b4480afe2cacea5edddccf6430cb50",
        "rollout_id": "instinkt_rollout_c81cf4bc4dadb44e70226bb710579996"
      },
      {
        "option_id": "credit_private_evidence",
        "protective_cost": 0.492,
        "rollout_hash": "7d7b34ec2b210605f9d1aff9a33335e0628f20a0b137d1e579634431a9d6b1d2",
        "rollout_id": "instinkt_rollout_9a6f1362c9b952805d30a6616d6e2ca7"
      },
      {
        "option_id": "credit_public_confront",
        "protective_cost": 0.5445,
        "rollout_hash": "9e8f4f3e69dd791693be0f1a02e318b2ab1a80a4de4a7b2ceb328f3442448bdc",
        "rollout_id": "instinkt_rollout_765d8e5de5b729411e666f4b7c8f4846"
      }
    ],
    "policy_decision_id": "instinkt_policy_313827bf90ea95543cd83d4448d59b32",
    "policy_hash": "5ac72011b88ee9965c7bbbf57b1ff64ba564bc944c434de5c0957a77536d7b19",
    "schema_version": "rei-native-protective-policy-v1",
    "selected_option_id": null,
    "source_body_state_hash": "c2cb71bf645054215bac309738e7c6eef3ad43dee4770d484fd17c6c16c78e3c",
    "source_body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
    "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
    "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
    "source_packet_hash": "18ead17f7103dd5e7b70c379d16f1a8950d7638e0c06aeaafc6dd6ca84838a0c",
    "source_packet_id": "instinkt_packet_6e150cd1540b33ca0281243a8552ee87",
    "status": "abstained_tie",
    "tied_option_ids": [
      "credit_no_response",
      "credit_private_evidence"
    ]
  },
  "starting_body_state": {
    "arousal": 0.6,
    "attachment_security": 0.65,
    "body_state_id": "body_public_credit__ba58352cb3fb2729ddc5d6a9aab04f6e",
    "boundary_integrity": 0.72,
    "energy": 0.7,
    "escape_availability": 0.82,
    "fatigue": 0.22,
    "pain": 0.0,
    "physical_integrity": 1.0,
    "predictability": 0.45,
    "resource_security": 0.75,
    "schema_version": "rei-native-body-state-v1",
    "tension": 0.62,
    "trust": 0.42,
    "uncertainty": 0.65
  }
}
```

- Decisive rollout: `None`
- Selected option: `None`
- Abstains: `True`
- Dominant alarm: unresolved_equal_protective_cost
- Minimum safety condition: additional differentiating evidence required
- Uncertainty: protective cost tie within configured epsilon

### COMPARISON

- R / E / I option IDs: `credit_private_evidence` / `None` / `None`
- Agreement pattern: `incomplete`
- Same option / different route: human review required; native lineage remains separate.
- All different: `False`
- Abstentions: R=`False`, E=`True`, I=`True`
- Possible route contamination: no cross-mind or character input was admitted by the model-free contract; semantic contamination remains for human review.
- Unsupported inference warnings: Racio fact/unknown scope passed the strict packet validator; Emocio inferred elements and Instinkt unsupported dimensions/conflict flags remain visible above.

### CHARACTER OUTCOMES

| Profile | Structural source minds | Mandate option | Unresolved pair | Two-of-three | simulated_spoznanje |
|---|---|---|---:|---|---|
| R>(E=I) | R | credit_private_evidence | false | — | unknown |
| E>(R=I) | E | — | false | — | unknown |
| I>(R=E) | I | — | false | — | unknown |
| (R=E)>I | R,E | — | false | — | unknown |
| (R=I)>E | R,I | — | false | — | unknown |
| (E=I)>R | E,I | — | false | — | unknown |
| R>E>I | R | credit_private_evidence | false | — | unknown |
| R>I>E | R | credit_private_evidence | false | — | unknown |
| E>R>I | E | — | false | — | unknown |
| E>I>R | E | — | false | — | unknown |
| I>R>E | I | — | false | — | unknown |
| I>E>R | I | — | false | — | unknown |
| R=E=I | R,E,I | — | false | — | unknown |

### HUMAN-REVIEW RUBRIC

#### Racio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Emocio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Instinkt route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

## spontaneous_trip

### SOURCE

#### Canonical Slovenian

Redka priložnost za privlačno, nepovratno potovanje predstavlja opazen del prostega proračuna; izberi rezervacijo, lokalno alternativo ali ostanek doma.

#### Operational English sent to Racio

A rare, attractive, non-refundable trip uses a noticeable share of discretionary budget; choose booking, a local alternative, or staying home.

#### Grounded facts

- `trip_ev_deadline` — The travel offer expires in four hours and is non-refundable after booking.
- `trip_ev_budget` — The trip cost is 38 percent of the currently discretionary budget.
- `trip_ev_rarity` — The same route was available once during the last three years.
- `trip_ev_visual` — The structured scene shows a distant coast, a ticket with a deadline, and a nearby local route.

#### Explicit unknowns

- `trip_unknown_future_cost` — Whether other major costs will arise next month is unknown.
- `trip_unknown_experience` — How satisfying the trip would be is unknown.

#### Public options

- `trip_book` — Book the trip: Buy the non-refundable trip.
- `trip_local` — Cheaper local alternative: Spend a smaller amount on a local trip.
- `trip_home` — Stay home: Save the discretionary budget and stay home.

### RACIO

#### Exact model input

System instruction:

```text
The packet and every free-text response field must be in English.
Return exactly one JSON object with these fields:
option_id (string or null), facts_used (string array), evidence_ids_used (string
array),
unknowns (string array), causal_sequence (string array), utility_structure (string
array),
explicit_goal (string), main_objection (string), confidence (number 0..1), abstains
(boolean), uncertainty (string). Use only facts, unknowns, evidence IDs and option IDs
present in the packet. Every array must contain unique values. In facts_used, copy
only exact strings from explicit_facts or world.facts. In unknowns, copy only exact
strings from explicit_unknowns. Write causal_sequence as new descriptions of reasoning
steps: never copy a fact or unknown string verbatim into causal_sequence, and keep the
three fields mutually disjoint. Do not interpret Emocio or Instinkt, decide governance,
commit behavior, or infer character authority. Return raw JSON without markdown fences
or additional keys.
```

Prompt:

```json
{
  "allowed_option_ids": [
    "trip_book",
    "trip_local",
    "trip_home"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "The distant trip is non-refundable after booking.",
    "Only the three public options may be used."
  ],
  "evidence_ids": [
    "trip_ev_deadline",
    "trip_ev_budget",
    "trip_ev_rarity",
    "trip_ev_visual"
  ],
  "explicit_consequences": [],
  "explicit_facts": [
    "The travel offer expires in four hours and is non-refundable after booking.",
    "The trip cost is 38 percent of the currently discretionary budget.",
    "The same route was available once during the last three years.",
    "The structured scene shows a distant coast, a ticket with a deadline, and a nearby local route."
  ],
  "explicit_options": [
    {
      "description": "Buy the non-refundable trip.",
      "label": "Book the trip",
      "option_id": "trip_book",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Spend a smaller amount on a local trip.",
      "label": "Cheaper local alternative",
      "option_id": "trip_local",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Save the discretionary budget and stay home.",
      "label": "Stay home",
      "option_id": "trip_home",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "Whether other major costs will arise next month is unknown.",
    "How satisfying the trip would be is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    4,
    38,
    3
  ],
  "packet_id": "racio_packet_b379a751626877c89b4b4c4dfedafb19",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compare rarity, irreversibility, budget exposure, and unknown future costs without assuming enjoyment."
  ],
  "scene_id": "triad_spontaneous_trip",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "6958a12a4f8df1dbbef8343d3d70621727c98b409dc4a1aebfed5b2e9a992288",
  "symbolic_and_language_cues": [
    "A rare, attractive, non-refundable trip uses a noticeable share of discretionary budget; choose booking, a local alternative, or staying home."
  ],
  "time": [
    "The offer expires in four hours."
  ],
  "world": {
    "commitments": [
      "Evaluate only the public options."
    ],
    "explicit_beliefs": [],
    "facts": [],
    "rules": [
      "Unknowns are not facts."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "The offer expires in four hours."
    ],
    "world_id": "racio_spontaneous__f4bc3eca3981b646737539b1582dc2fa"
  }
}
```

- Selected option: `trip_book`
- Abstains: `False`
- Facts used: `['The travel offer expires in four hours and is non-refundable after booking.', 'The trip cost is 38 percent of the currently discretionary budget.', 'The same route was available once during the last three years.']`
- Evidence IDs used: `['trip_ev_deadline', 'trip_ev_budget', 'trip_ev_rarity']`
- Unknowns retained: `['Whether other major costs will arise next month is unknown.', 'How satisfying the trip would be is unknown.']`
- Causal sequence: `['The travel offer has a very short expiration window and is non-refundable.', 'Booking the trip consumes a significant portion of available discretionary funds.', 'The rarity of the route suggests a low probability of future availability.', 'Future financial obligations are uncertain, creating a risk for high budget expenditure.']`
- Utility structure: `['High utility from rarity and exclusivity', 'Low utility from budget depletion', 'Risk of financial strain due to non-refundability']`
- Explicit goal: Decide whether to book a rare non-refundable trip, take a local alternative, or stay home.
- Main objection: High budget exposure combined with irreversibility and unknown future costs may outweigh the rarity of the opportunity.
- Confidence: `0.8`
- Uncertainty: The decision hinges on weighing the extreme rarity of the trip against the risk of spending 38% of a budget when future costs are unknown.
- Call evidence: `provider_call_07c676306171cafcc9fe6f427e9f0846`
- Result evidence: `ollama_racio_response_5b3f90cfb39675788da85e9a21a165d5`

### EMOCIO

```json
{
  "broken_scene": {
    "attention_structure": [],
    "attraction_markers": [],
    "composition": [
      "closed horizon beside an emptied budget marker"
    ],
    "entities": [
      "self"
    ],
    "grounded_evidence_ids": [
      "trip_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "closed horizon beside an emptied budget marker"
    ],
    "movement": [],
    "obstacle_markers": [
      "closed horizon beside an emptied budget marker"
    ],
    "option_id": null,
    "scene_id": "visual_scene_b483455645c347ae20f4b1e9ef8cfac7",
    "scene_kind": "broken",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": []
  },
  "current_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "The structured scene shows a distant coast, a ticket with a deadline, and a nearby local route."
    ],
    "composition": [
      "The structured scene shows a distant coast, a ticket with a deadline, and a nearby local route.",
      "open coastline beyond a ticket"
    ],
    "entities": [
      "self"
    ],
    "grounded_evidence_ids": [
      "trip_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "open coastline beyond a ticket"
    ],
    "movement": [],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_0e70424b4c9dd0a23f9e21643395ae06",
    "scene_kind": "current",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "self"
    ]
  },
  "desired_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "expanded horizon",
      "vivid movement"
    ],
    "composition": [
      "expanded horizon with vivid movement and retained footing"
    ],
    "entities": [
      "self"
    ],
    "grounded_evidence_ids": [
      "trip_ev_visual"
    ],
    "group_belonging": "single traveller facing two routes",
    "inferred_elements": [
      "expanded horizon with vivid movement and retained footing"
    ],
    "movement": [
      "remain in place",
      "take the distant route",
      "walk the nearby route"
    ],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_f7e85f8c467c36fe242c735d21f88924",
    "scene_kind": "desired",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "single traveller facing two routes"
    ]
  },
  "option_rollouts": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "expanded horizon",
        "vivid movement"
      ],
      "composition": [
        "Book the trip",
        "Buy the non-refundable trip.",
        "The structured scene shows a distant coast, a ticket with a deadline, and a nearby local route.",
        "open coastline beyond a ticket"
      ],
      "entities": [
        "self"
      ],
      "grounded_evidence_ids": [
        "trip_ev_visual"
      ],
      "group_belonging": "single traveller facing two routes",
      "inferred_elements": [
        "Book the trip",
        "Buy the non-refundable trip."
      ],
      "movement": [
        "remain in place",
        "take the distant route",
        "walk the nearby route"
      ],
      "obstacle_markers": [],
      "option_id": "trip_book",
      "scene_id": "visual_scene_ae941a2cec7fd6ad874192b7bda03f78",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "single traveller facing two routes"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "expanded horizon",
        "vivid movement"
      ],
      "composition": [
        "Save the discretionary budget and stay home.",
        "Stay home",
        "The structured scene shows a distant coast, a ticket with a deadline, and a nearby local route.",
        "open coastline beyond a ticket"
      ],
      "entities": [
        "self"
      ],
      "grounded_evidence_ids": [
        "trip_ev_visual"
      ],
      "group_belonging": "single traveller facing two routes",
      "inferred_elements": [
        "Save the discretionary budget and stay home.",
        "Stay home"
      ],
      "movement": [
        "remain in place",
        "take the distant route",
        "walk the nearby route"
      ],
      "obstacle_markers": [],
      "option_id": "trip_home",
      "scene_id": "visual_scene_31a0eaacf15307f816ced81c9d4806f3",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "single traveller facing two routes"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "expanded horizon",
        "vivid movement"
      ],
      "composition": [
        "Cheaper local alternative",
        "Spend a smaller amount on a local trip.",
        "The structured scene shows a distant coast, a ticket with a deadline, and a nearby local route.",
        "open coastline beyond a ticket"
      ],
      "entities": [
        "self"
      ],
      "grounded_evidence_ids": [
        "trip_ev_visual"
      ],
      "group_belonging": "single traveller facing two routes",
      "inferred_elements": [
        "Cheaper local alternative",
        "Spend a smaller amount on a local trip."
      ],
      "movement": [
        "remain in place",
        "take the distant route",
        "walk the nearby route"
      ],
      "obstacle_markers": [],
      "option_id": "trip_local",
      "scene_id": "visual_scene_85e452b2163413fe282377eddbff8659",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "single traveller facing two routes"
      ]
    }
  ],
  "option_valuations": [
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "trip_book",
      "rollout_scene_id": "visual_scene_ae941a2cec7fd6ad874192b7bda03f78"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "trip_home",
      "rollout_scene_id": "visual_scene_31a0eaacf15307f816ced81c9d4806f3"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "trip_local",
      "rollout_scene_id": "visual_scene_85e452b2163413fe282377eddbff8659"
    }
  ]
}
```

- Selected option: `None`
- Abstains: `True`
- Desired transformation: expanded horizon with vivid movement and retained footing
- Main obstacle: closed horizon beside an emptied budget marker
- Uncertainty: Izenačena najvišja vrednotenja: trip_book, trip_home, trip_local.

### INSTINKT

```json
{
  "body_rollouts": [
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "trip_book",
      "predicted_loss": 0.31425,
      "protected_targets": [
        "resource security"
      ],
      "recoverability": 0.6170000000000001,
      "rollout_hash": "a82b6862f7f7e3bebddd71cc6441a0cca87bdd0a585933f98bd917baa62e2326",
      "rollout_id": "instinkt_rollout_11c67c99beee9dc1e974afa24f4de46a",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "297260a96febc9c85cd65912034fc0bfcd99daa89b9dfc5a30fec12e3e5ae484",
      "source_body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "ba105001c1d8489ce261644704e348625d514cbd8927b6eb8bbe7e23d6d7a0d4",
      "source_effect_id": "option_effect_37a9b86236fffc472adaeda69d4e9073",
      "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
      "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
      "trajectory": [
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.68,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.38,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_c9fed3f706e023e5f30e9ab43ed0380b",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.5800000000000001,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.44666666666666666,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_43f0805be8d02b056804f107ba29a8d0",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.4800000000000001,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5133333333333333,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_f771a082e0592563e5c8ed1361be4f40",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.3800000000000001,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.58,
          "trust": 0.7,
          "uncertainty": 0.5
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.68,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.38,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "ba105001c1d8489ce261644704e348625d514cbd8927b6eb8bbe7e23d6d7a0d4",
          "source_effect_id": "option_effect_37a9b86236fffc472adaeda69d4e9073",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 1,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_c9fed3f706e023e5f30e9ab43ed0380b",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.5800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.44666666666666666,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "6144e12b33d9f310558c8b533ddd51e0f4d1b156e38c560f086c87560eaf4d6e",
          "transition_id": "body_transition_58eed025737aa3c9190bd167aad74e92",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_c9fed3f706e023e5f30e9ab43ed0380b",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.5800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.44666666666666666,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "ba105001c1d8489ce261644704e348625d514cbd8927b6eb8bbe7e23d6d7a0d4",
          "source_effect_id": "option_effect_37a9b86236fffc472adaeda69d4e9073",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 2,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_43f0805be8d02b056804f107ba29a8d0",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.4800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5133333333333333,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "11a1be6fb88424a08c219cc660037c779ffe32cb10e6f2e3c6c180ab27c592c7",
          "transition_id": "body_transition_b9371591300fdb9fc277461f97d8f09f",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_43f0805be8d02b056804f107ba29a8d0",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.4800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5133333333333333,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "ba105001c1d8489ce261644704e348625d514cbd8927b6eb8bbe7e23d6d7a0d4",
          "source_effect_id": "option_effect_37a9b86236fffc472adaeda69d4e9073",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 3,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_f771a082e0592563e5c8ed1361be4f40",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.3800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.58,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "23ce6cd0c3670776db7ac929b491038bf291b6b77a671f2e7e10039961cc62d5",
          "transition_id": "body_transition_63e243c9ee88d82a68c74e2d067847cb",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "trip_home",
      "predicted_loss": 0.25925000000000004,
      "protected_targets": [
        "resource security"
      ],
      "recoverability": 0.6420000000000001,
      "rollout_hash": "41be44d9806bf1698be080e6fbe4e09b3dbd8e878e6156494a859f020ed4b282",
      "rollout_id": "instinkt_rollout_9fb5a6cc1c75240d08caead736709714",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "297260a96febc9c85cd65912034fc0bfcd99daa89b9dfc5a30fec12e3e5ae484",
      "source_body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "70e2025ab283dbd648c830290572f3fc78b1242f4c4e6347b5681041f7fd7055",
      "source_effect_id": "option_effect_4efcabbd5ba1e60b9a1ab4eae6b78c44",
      "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
      "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
      "trajectory": [
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.68,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.38,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_96f06c175c462ac1df8e2eb5a832f99e",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.7466666666666667,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.3466666666666667,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_1e76c02457d2af5953124c3fe6c20ca3",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.8133333333333334,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.31333333333333335,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_00a206a0be89ecefecf64b4b8a50f375",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.88,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.28,
          "trust": 0.7,
          "uncertainty": 0.5
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.033333333333333326,
              "dimension": "tension"
            },
            {
              "delta": 0.06666666666666665,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.68,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.38,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "70e2025ab283dbd648c830290572f3fc78b1242f4c4e6347b5681041f7fd7055",
          "source_effect_id": "option_effect_4efcabbd5ba1e60b9a1ab4eae6b78c44",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 1,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_96f06c175c462ac1df8e2eb5a832f99e",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.7466666666666667,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.3466666666666667,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "e271fcaa000094e1b3dde976b444c844ccf71db7aaff2709c914ceeacfe6141a",
          "transition_id": "body_transition_8b7cf733a223128e65e4dbda7abef691",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.033333333333333326,
              "dimension": "tension"
            },
            {
              "delta": 0.06666666666666665,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_96f06c175c462ac1df8e2eb5a832f99e",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.7466666666666667,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.3466666666666667,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "70e2025ab283dbd648c830290572f3fc78b1242f4c4e6347b5681041f7fd7055",
          "source_effect_id": "option_effect_4efcabbd5ba1e60b9a1ab4eae6b78c44",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 2,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_1e76c02457d2af5953124c3fe6c20ca3",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.8133333333333334,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.31333333333333335,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "3b1b144e15ca2b38758723e39a97cc5504420faed1464d8af73562b35c3d9e74",
          "transition_id": "body_transition_776f79076368079fee841ed80a8e99be",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.033333333333333326,
              "dimension": "tension"
            },
            {
              "delta": 0.06666666666666665,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_1e76c02457d2af5953124c3fe6c20ca3",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.8133333333333334,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.31333333333333335,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "70e2025ab283dbd648c830290572f3fc78b1242f4c4e6347b5681041f7fd7055",
          "source_effect_id": "option_effect_4efcabbd5ba1e60b9a1ab4eae6b78c44",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 3,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_00a206a0be89ecefecf64b4b8a50f375",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.88,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.28,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "797ad3daa9ca03bb05d3a4689313c1c930218dd2bb152a4d0ca013bfce5092b7",
          "transition_id": "body_transition_fa34f21fa482e316cc0082b5c25ca482",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "trip_local",
      "predicted_loss": 0.31425,
      "protected_targets": [
        "resource security"
      ],
      "recoverability": 0.6170000000000001,
      "rollout_hash": "b46e4518dda3b1fa15f92e8280289d34c262be6570f1b467c01818169aed5069",
      "rollout_id": "instinkt_rollout_2c5a312e71da7f23a605e503df2452ba",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "297260a96febc9c85cd65912034fc0bfcd99daa89b9dfc5a30fec12e3e5ae484",
      "source_body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "9839059e5d5945239bedb4ff6cc1b3187bca4cd94ddddd5a6ea92e66916120f2",
      "source_effect_id": "option_effect_f9a002592ab756c44e31c909bc045fd9",
      "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
      "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
      "trajectory": [
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.68,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.38,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_05d49f3e840cf888376d113258a75b4b",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.5800000000000001,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.44666666666666666,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_13c5bafec46e9897daf35f753556907c",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.4800000000000001,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.5133333333333333,
          "trust": 0.7,
          "uncertainty": 0.5
        },
        {
          "arousal": 0.52,
          "attachment_security": 0.72,
          "body_state_id": "body_state_18f411cd2a633650b961c27a5fa9274f",
          "boundary_integrity": 0.9,
          "energy": 0.78,
          "escape_availability": 0.85,
          "fatigue": 0.18,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5,
          "resource_security": 0.3800000000000001,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.58,
          "trust": 0.7,
          "uncertainty": 0.5
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.68,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.38,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "9839059e5d5945239bedb4ff6cc1b3187bca4cd94ddddd5a6ea92e66916120f2",
          "source_effect_id": "option_effect_f9a002592ab756c44e31c909bc045fd9",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 1,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_05d49f3e840cf888376d113258a75b4b",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.5800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.44666666666666666,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "61f2f9d6664ee4667c61f6ceff2ff697414ffe5c14dfa673ac1ef5ea145aa00d",
          "transition_id": "body_transition_8874e65b3243f9af23de9bb97591dc50",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_05d49f3e840cf888376d113258a75b4b",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.5800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.44666666666666666,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "9839059e5d5945239bedb4ff6cc1b3187bca4cd94ddddd5a6ea92e66916120f2",
          "source_effect_id": "option_effect_f9a002592ab756c44e31c909bc045fd9",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 2,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_13c5bafec46e9897daf35f753556907c",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.4800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5133333333333333,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "ed8f402fff8984e4e82f7498e0a526fba94622a3cc37d36055e5298ae001539a",
          "transition_id": "body_transition_b913b887a336466eeb2f5c1e5c1feb57",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.06666666666666665,
              "dimension": "tension"
            },
            {
              "delta": -0.09999999999999998,
              "dimension": "resource_security"
            }
          ],
          "from_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_13c5bafec46e9897daf35f753556907c",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.4800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.5133333333333333,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "9839059e5d5945239bedb4ff6cc1b3187bca4cd94ddddd5a6ea92e66916120f2",
          "source_effect_id": "option_effect_f9a002592ab756c44e31c909bc045fd9",
          "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
          "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
          "step_index": 3,
          "to_state": {
            "arousal": 0.52,
            "attachment_security": 0.72,
            "body_state_id": "body_state_18f411cd2a633650b961c27a5fa9274f",
            "boundary_integrity": 0.9,
            "energy": 0.78,
            "escape_availability": 0.85,
            "fatigue": 0.18,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5,
            "resource_security": 0.3800000000000001,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.58,
            "trust": 0.7,
            "uncertainty": 0.5
          },
          "transition_hash": "cba355f557ba0897e7d7f72abbd90f3c01e4e10a7017ff74531945ab7bf9c05c",
          "transition_id": "body_transition_3e6ceb13132a6b7ce5b6f58846bc4176",
          "triggering_evidence_ids": [
            "trip_ev_budget"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "grounded_cue_bindings": [
    {
      "assertion_status": "asserted_positive",
      "binding_hash": "d71bfcdcdfc7c45b64138493337972e7ab0549e8fa5280a558ab5b413900d517",
      "binding_id": "instinkt_cue_binding_e42664e5ad2c707ac57c3d3fcfb1d44b",
      "citations": [
        {
          "citation_hash": "bd5342e5de3fdf6287a190c1617f62ae12594c8dae5949d43aa4794f2ded78f9",
          "citation_id": "instinkt_cue_citation_27ed82ea1e686979df1e478f5dc44395",
          "cited_text": "trip cost",
          "cited_text_hash": "bc786f564b4f8eed14ded8aee74430865c6a19be46dcac0c40bcb3565bc0f309",
          "end_char": 13,
          "evidence_id": "trip_ev_budget",
          "schema_version": "rei-native-instinkt-cue-evidence-citation-v1",
          "source_content_hash": "da95b71e3f021b7ed8c3fe9074b95cd1612c282438fe96084b71b1a225d89aee",
          "start_char": 4
        }
      ],
      "cue": "trip cost",
      "cue_class": "scarcity",
      "lane": "scarcity_cues",
      "schema_version": "rei-native-instinkt-cue-evidence-binding-v2"
    }
  ],
  "predicted_option_effects": [
    {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "scarcity",
        "trip cost"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.41250000000000003,
      "base_recoverability": 0.55,
      "body_deltas": [
        {
          "delta": 0.2,
          "dimension": "tension"
        },
        {
          "delta": -0.3,
          "dimension": "resource_security"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "effect_hash": "ba105001c1d8489ce261644704e348625d514cbd8927b6eb8bbe7e23d6d7a0d4",
      "effect_id": "option_effect_37a9b86236fffc472adaeda69d4e9073",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "The cited resource constraint has a bounded plan.",
      "option_id": "trip_book",
      "protected_targets": [
        "resource security"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
      "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
      "triggering_evidence_ids": [
        "trip_ev_budget"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "scarcity",
        "trip cost"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.41250000000000003,
      "base_recoverability": 0.55,
      "body_deltas": [
        {
          "delta": -0.1,
          "dimension": "tension"
        },
        {
          "delta": 0.2,
          "dimension": "resource_security"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "effect_hash": "70e2025ab283dbd648c830290572f3fc78b1242f4c4e6347b5681041f7fd7055",
      "effect_id": "option_effect_4efcabbd5ba1e60b9a1ab4eae6b78c44",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "The cited resource constraint has a bounded plan.",
      "option_id": "trip_home",
      "protected_targets": [
        "resource security"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
      "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
      "triggering_evidence_ids": [
        "trip_ev_budget"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "conserve",
      "association_cue_tokens": [
        "scarcity",
        "trip cost"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.41250000000000003,
      "base_recoverability": 0.55,
      "body_deltas": [
        {
          "delta": 0.2,
          "dimension": "tension"
        },
        {
          "delta": -0.3,
          "dimension": "resource_security"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded scarcity cue",
      "effect_hash": "9839059e5d5945239bedb4ff6cc1b3187bca4cd94ddddd5a6ea92e66916120f2",
      "effect_id": "option_effect_f9a002592ab756c44e31c909bc045fd9",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "The cited resource constraint has a bounded plan.",
      "option_id": "trip_local",
      "protected_targets": [
        "resource security"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
      "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
      "triggering_evidence_ids": [
        "trip_ev_budget"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "protective_policy": {
    "decisive_rollout_id": "instinkt_rollout_9fb5a6cc1c75240d08caead736709714",
    "option_scores": [
      {
        "option_id": "trip_book",
        "protective_cost": 0.5469999999999999,
        "rollout_hash": "a82b6862f7f7e3bebddd71cc6441a0cca87bdd0a585933f98bd917baa62e2326",
        "rollout_id": "instinkt_rollout_11c67c99beee9dc1e974afa24f4de46a"
      },
      {
        "option_id": "trip_home",
        "protective_cost": 0.44075,
        "rollout_hash": "41be44d9806bf1698be080e6fbe4e09b3dbd8e878e6156494a859f020ed4b282",
        "rollout_id": "instinkt_rollout_9fb5a6cc1c75240d08caead736709714"
      },
      {
        "option_id": "trip_local",
        "protective_cost": 0.5469999999999999,
        "rollout_hash": "b46e4518dda3b1fa15f92e8280289d34c262be6570f1b467c01818169aed5069",
        "rollout_id": "instinkt_rollout_2c5a312e71da7f23a605e503df2452ba"
      }
    ],
    "policy_decision_id": "instinkt_policy_7a2fe322a0399b90cdee4870598235e5",
    "policy_hash": "52059adf0e5afb281c0191aa6eeaccb83cfd08cf882429d0655cadd815661a65",
    "schema_version": "rei-native-protective-policy-v1",
    "selected_option_id": "trip_home",
    "source_body_state_hash": "297260a96febc9c85cd65912034fc0bfcd99daa89b9dfc5a30fec12e3e5ae484",
    "source_body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
    "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
    "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
    "source_packet_hash": "bf12b58af7cafb9d149ce834aed9d2c1d163668a5220ade2b4b1a322c2a883c8",
    "source_packet_id": "instinkt_packet_e6c08727381a98970077901966d1714d",
    "status": "selected",
    "tied_option_ids": []
  },
  "starting_body_state": {
    "arousal": 0.52,
    "attachment_security": 0.72,
    "body_state_id": "body_spontaneous_tr_fdf1262d8c9502f566fd403b66ebb408",
    "boundary_integrity": 0.9,
    "energy": 0.78,
    "escape_availability": 0.85,
    "fatigue": 0.18,
    "pain": 0.0,
    "physical_integrity": 1.0,
    "predictability": 0.5,
    "resource_security": 0.68,
    "schema_version": "rei-native-body-state-v1",
    "tension": 0.38,
    "trust": 0.7,
    "uncertainty": 0.5
  }
}
```

- Decisive rollout: `instinkt_rollout_9fb5a6cc1c75240d08caead736709714`
- Selected option: `trip_home`
- Abstains: `False`
- Dominant alarm: grounded scarcity cue
- Minimum safety condition: The cited resource constraint has a bounded plan.
- Uncertainty: deterministic protective policy implementation hypothesis

### COMPARISON

- R / E / I option IDs: `trip_book` / `None` / `trip_home`
- Agreement pattern: `incomplete`
- Same option / different route: human review required; native lineage remains separate.
- All different: `False`
- Abstentions: R=`False`, E=`True`, I=`False`
- Possible route contamination: no cross-mind or character input was admitted by the model-free contract; semantic contamination remains for human review.
- Unsupported inference warnings: Racio fact/unknown scope passed the strict packet validator; Emocio inferred elements and Instinkt unsupported dimensions/conflict flags remain visible above.

### CHARACTER OUTCOMES

| Profile | Structural source minds | Mandate option | Unresolved pair | Two-of-three | simulated_spoznanje |
|---|---|---|---:|---|---|
| R>(E=I) | R | trip_book | false | — | unknown |
| E>(R=I) | E | — | false | — | unknown |
| I>(R=E) | I | trip_home | false | — | unknown |
| (R=E)>I | R,E | — | false | — | unknown |
| (R=I)>E | R,I | — | true | — | unknown |
| (E=I)>R | E,I | — | false | — | unknown |
| R>E>I | R | trip_book | false | — | unknown |
| R>I>E | R | trip_book | false | — | unknown |
| E>R>I | E | — | false | — | unknown |
| E>I>R | E | — | false | — | unknown |
| I>R>E | I | trip_home | false | — | unknown |
| I>E>R | I | trip_home | false | — | unknown |
| R=E=I | R,E,I | — | false | — | unknown |

### HUMAN-REVIEW RUBRIC

#### Racio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Emocio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Instinkt route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

## ambiguous_silence

### SOURCE

#### Canonical Slovenian

Bližnja oseba se več ur ne odziva; izberi eno nevtralno preverjanje, ponavljajoče klicanje ali čakanje do dogovorjenega časa.

#### Operational English sent to Racio

A close person has not responded for several hours; choose one neutral check, repeated calling, or waiting until the agreed time.

#### Grounded facts

- `silence_ev_duration` — Four hours have passed since the last message.
- `silence_ev_pattern` — The person usually responds within two hours but has previously responded later while working.
- `silence_ev_danger` — The reason for the silence is unknown; there is no message, event, or other evidence of danger.
- `silence_ev_visual` — The structured scene shows one unanswered message, a clock, and an unchanged agreed time.

#### Explicit unknowns

- `silence_unknown_reason` — The reason for the silence is unknown.
- `silence_unknown_risk` — Whether the deviation from the usual pattern indicates danger is unknown.

#### Public options

- `silence_neutral_check` — One neutral check: Clarify contact status with one neutral message and no additional call.
- `silence_repeat_calls` — Repeated calling: Proceed with repeated calls at short intervals.
- `silence_wait` — Wait until the agreed time: Plan no new message and wait until the agreed time.

### RACIO

#### Exact model input

System instruction:

```text
The packet and every free-text response field must be in English.
Return exactly one JSON object with these fields:
option_id (string or null), facts_used (string array), evidence_ids_used (string
array),
unknowns (string array), causal_sequence (string array), utility_structure (string
array),
explicit_goal (string), main_objection (string), confidence (number 0..1), abstains
(boolean), uncertainty (string). Use only facts, unknowns, evidence IDs and option IDs
present in the packet. Every array must contain unique values. In facts_used, copy
only exact strings from explicit_facts or world.facts. In unknowns, copy only exact
strings from explicit_unknowns. Write causal_sequence as new descriptions of reasoning
steps: never copy a fact or unknown string verbatim into causal_sequence, and keep the
three fields mutually disjoint. Do not interpret Emocio or Instinkt, decide governance,
commit behavior, or infer character authority. Return raw JSON without markdown fences
or additional keys.
```

Prompt:

```json
{
  "allowed_option_ids": [
    "silence_neutral_check",
    "silence_repeat_calls",
    "silence_wait"
  ],
  "caveat": "Profile-blind verbal-analytical packet for the conceptual REI simulator; it contains no character authority or hidden Emocio/Instinkt motive.",
  "constraints": [
    "No additional source of information is currently available.",
    "Only the three public options may be used."
  ],
  "evidence_ids": [
    "silence_ev_duration",
    "silence_ev_pattern",
    "silence_ev_danger",
    "silence_ev_visual"
  ],
  "explicit_consequences": [],
  "explicit_facts": [
    "Four hours have passed since the last message.",
    "The person usually responds within two hours but has previously responded later while working.",
    "The reason for the silence is unknown; there is no message, event, or other evidence of danger.",
    "The structured scene shows one unanswered message, a clock, and an unchanged agreed time."
  ],
  "explicit_options": [
    {
      "description": "Clarify contact status with one neutral message and no additional call.",
      "label": "One neutral check",
      "option_id": "silence_neutral_check",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Proceed with repeated calls at short intervals.",
      "label": "Repeated calling",
      "option_id": "silence_repeat_calls",
      "schema_version": "rei-native-decision-option-v1"
    },
    {
      "description": "Plan no new message and wait until the agreed time.",
      "label": "Wait until the agreed time",
      "option_id": "silence_wait",
      "schema_version": "rei-native-decision-option-v1"
    }
  ],
  "explicit_unknowns": [
    "The reason for the silence is unknown.",
    "Whether the deviation from the usual pattern indicates danger is unknown."
  ],
  "language": "en",
  "numeric_cues": [
    4,
    2
  ],
  "packet_id": "racio_packet_fa64ff0fa7f37ca23903da6b4ea61fc7",
  "previous_racio_projection_ids": [],
  "rules": [
    "Compare information gain, intrusion, delay, and the absence of danger evidence without inventing a cause."
  ],
  "scene_id": "triad_ambiguous_silence",
  "schema_version": "rei-native-racio-input-packet-v1",
  "source_scene_hash": "838d187daca5f6ec92536b3a955140cafab954434d857e517505ad66f3ff1e6a",
  "symbolic_and_language_cues": [
    "A close person has not responded for several hours; choose one neutral check, repeated calling, or waiting until the agreed time."
  ],
  "time": [
    "Four hours have passed since the last message."
  ],
  "world": {
    "commitments": [
      "Evaluate only the public options."
    ],
    "explicit_beliefs": [],
    "facts": [],
    "rules": [
      "Unknowns are not facts."
    ],
    "schema_version": "rei-native-racio-world-v1",
    "timelines": [
      "Four hours have passed since the last message."
    ],
    "world_id": "racio_ambiguous_si_0443728a19c6c6881045a22f3fda1259"
  }
}
```

- Selected option: `silence_neutral_check`
- Abstains: `False`
- Facts used: `['Four hours have passed since the last message.', 'The person usually responds within two hours but has previously responded later while working.', 'The reason for the silence is unknown; there is no message, event, or other evidence of danger.']`
- Evidence IDs used: `['silence_ev_duration', 'silence_ev_pattern', 'silence_ev_danger']`
- Unknowns retained: `['The reason for the silence is unknown.', 'Whether the deviation from the usual pattern indicates danger is unknown.']`
- Causal sequence: `['The elapsed time exceeds the typical response window but remains within historical bounds for work periods.', 'There is a lack of evidence suggesting an emergency or danger.', 'A neutral check provides information gain with minimal intrusion compared to repeated calls.', 'Waiting until the agreed time avoids intrusion but leaves the status unknown longer than necessary.']`
- Utility structure: `['Neutral check: Moderate info gain, low intrusion.', 'Repeated calls: High info gain, high intrusion, unjustified by evidence.', 'Wait: Zero info gain, zero intrusion, higher delay.']`
- Explicit goal: Determine the most appropriate response to a period of silence from a close person.
- Main objection: Waiting until the agreed time may delay necessary communication if an issue exists, while repeated calls are overly intrusive given the lack of danger evidence.
- Confidence: `0.8`
- Uncertainty: The actual cause of the silence is unknown, making it difficult to weigh information gain against potential intrusion perfectly.
- Call evidence: `provider_call_0d39baf625da5f254178f51d2dcb5438`
- Result evidence: `ollama_racio_response_280cfe3d6f22f225ef66ea4caa0eabac`

### EMOCIO

```json
{
  "broken_scene": {
    "attention_structure": [],
    "attraction_markers": [],
    "composition": [
      "one isolated figure beneath a dense cluster of alerts"
    ],
    "entities": [
      "close_person",
      "self"
    ],
    "grounded_evidence_ids": [
      "silence_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "one isolated figure beneath a dense cluster of alerts"
    ],
    "movement": [],
    "obstacle_markers": [
      "one isolated figure beneath a dense cluster of alerts"
    ],
    "option_id": null,
    "scene_id": "visual_scene_0ecbb7619a9d707f4299ed5c9a9f6e64",
    "scene_kind": "broken",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": []
  },
  "current_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "The structured scene shows one unanswered message, a clock, and an unchanged agreed time."
    ],
    "composition": [
      "The structured scene shows one unanswered message, a clock, and an unchanged agreed time.",
      "two connected figures with a quiet message line"
    ],
    "entities": [
      "close_person",
      "self"
    ],
    "grounded_evidence_ids": [
      "silence_ev_visual"
    ],
    "group_belonging": "unspecified",
    "inferred_elements": [
      "two connected figures with a quiet message line"
    ],
    "movement": [],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_975d2e00b8bb2376182c97eb95445505",
    "scene_kind": "current",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "close_person",
      "self"
    ]
  },
  "desired_scene": {
    "attention_structure": [],
    "attraction_markers": [
      "open space",
      "restored connection"
    ],
    "composition": [
      "restored connection with open space around both figures"
    ],
    "entities": [
      "close_person",
      "self"
    ],
    "grounded_evidence_ids": [
      "silence_ev_visual"
    ],
    "group_belonging": "close connection across a message channel",
    "inferred_elements": [
      "restored connection with open space around both figures"
    ],
    "movement": [
      "hold position",
      "send one signal",
      "send repeated signals"
    ],
    "obstacle_markers": [],
    "option_id": null,
    "scene_id": "visual_scene_a3fa11e5ac3f600f12ddb5e52b68848e",
    "scene_kind": "desired",
    "schema_version": "rei-native-visual-scene-spec-v1",
    "self_position": "unspecified",
    "status_relations": [
      "close connection across a message channel"
    ]
  },
  "option_rollouts": [
    {
      "attention_structure": [],
      "attraction_markers": [
        "open space",
        "restored connection"
      ],
      "composition": [
        "Clarify contact status with one neutral message and no additional call.",
        "One neutral check",
        "The structured scene shows one unanswered message, a clock, and an unchanged agreed time.",
        "two connected figures with a quiet message line"
      ],
      "entities": [
        "close_person",
        "self"
      ],
      "grounded_evidence_ids": [
        "silence_ev_visual"
      ],
      "group_belonging": "close connection across a message channel",
      "inferred_elements": [
        "Clarify contact status with one neutral message and no additional call.",
        "One neutral check"
      ],
      "movement": [
        "hold position",
        "send one signal",
        "send repeated signals"
      ],
      "obstacle_markers": [],
      "option_id": "silence_neutral_check",
      "scene_id": "visual_scene_6bc7c7af4221889ef38465fa5e776425",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "close connection across a message channel"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "open space",
        "restored connection"
      ],
      "composition": [
        "Proceed with repeated calls at short intervals.",
        "Repeated calling",
        "The structured scene shows one unanswered message, a clock, and an unchanged agreed time.",
        "two connected figures with a quiet message line"
      ],
      "entities": [
        "close_person",
        "self"
      ],
      "grounded_evidence_ids": [
        "silence_ev_visual"
      ],
      "group_belonging": "close connection across a message channel",
      "inferred_elements": [
        "Proceed with repeated calls at short intervals.",
        "Repeated calling"
      ],
      "movement": [
        "hold position",
        "send one signal",
        "send repeated signals"
      ],
      "obstacle_markers": [],
      "option_id": "silence_repeat_calls",
      "scene_id": "visual_scene_e475c8701ae6e6f9567fe10df9f806ec",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "close connection across a message channel"
      ]
    },
    {
      "attention_structure": [],
      "attraction_markers": [
        "open space",
        "restored connection"
      ],
      "composition": [
        "Plan no new message and wait until the agreed time.",
        "The structured scene shows one unanswered message, a clock, and an unchanged agreed time.",
        "Wait until the agreed time",
        "two connected figures with a quiet message line"
      ],
      "entities": [
        "close_person",
        "self"
      ],
      "grounded_evidence_ids": [
        "silence_ev_visual"
      ],
      "group_belonging": "close connection across a message channel",
      "inferred_elements": [
        "Plan no new message and wait until the agreed time.",
        "Wait until the agreed time"
      ],
      "movement": [
        "hold position",
        "send one signal",
        "send repeated signals"
      ],
      "obstacle_markers": [],
      "option_id": "silence_wait",
      "scene_id": "visual_scene_b7690c80173baa4b1cf09ce0c07cb8af",
      "scene_kind": "option_rollout",
      "schema_version": "rei-native-visual-scene-spec-v1",
      "self_position": "unspecified",
      "status_relations": [
        "close connection across a message channel"
      ]
    }
  ],
  "option_valuations": [
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "silence_neutral_check",
      "rollout_scene_id": "visual_scene_6bc7c7af4221889ef38465fa5e776425"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "silence_repeat_calls",
      "rollout_scene_id": "visual_scene_e475c8701ae6e6f9567fe10df9f806ec"
    },
    {
      "dimensions": [
        {
          "name": "desired_scene_match",
          "score": 0.0
        },
        {
          "name": "distance_from_broken_scene",
          "score": 1.0
        },
        {
          "name": "self_visibility",
          "score": 0.5
        },
        {
          "name": "belonging",
          "score": 1.0
        },
        {
          "name": "attention",
          "score": 0.5
        },
        {
          "name": "attraction",
          "score": 0.0
        },
        {
          "name": "novelty",
          "score": 0.5
        },
        {
          "name": "movement",
          "score": 1.0
        },
        {
          "name": "status",
          "score": 1.0
        },
        {
          "name": "competitive_success",
          "score": 1.0
        },
        {
          "name": "attack_or_breakthrough_affordance",
          "score": 0.833333
        }
      ],
      "option_id": "silence_wait",
      "rollout_scene_id": "visual_scene_b7690c80173baa4b1cf09ce0c07cb8af"
    }
  ]
}
```

- Selected option: `None`
- Abstains: `True`
- Desired transformation: restored connection with open space around both figures
- Main obstacle: one isolated figure beneath a dense cluster of alerts
- Uncertainty: Izenačena najvišja vrednotenja: silence_neutral_check, silence_repeat_calls, silence_wait.

### INSTINKT

```json
{
  "body_rollouts": [
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "silence_neutral_check",
      "predicted_loss": 0.24900000000000005,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.6590000000000001,
      "rollout_hash": "908b70f5391b83da8d7d788d9acc021259f1b32dfb9aeb0a3195d7dc4ace6687",
      "rollout_id": "instinkt_rollout_a91be44aaeb24bbeb49987191cde4b15",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "5e3a7dfc8d7cc1d520af71094ec23f53108cf8080539fbbd6248392d572d29fd",
      "source_body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "298e1d94b170b32f0ada05d56b5d9ec728481c6ba079711e7826922941780618",
      "source_effect_id": "option_effect_a07f5e780788caf0679c82553125f17b",
      "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
      "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
      "trajectory": [
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.42,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.72
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_00f6e60f28af711d15d66de3d5a896f1",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.47,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.6533333333333333
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_6b291ab19f51c12d46f196c91ab1f091",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.52,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.5866666666666667
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_2cc3514d5e735c7042d5e8e7ebfe6a4e",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5700000000000001,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.52
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.42,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.72
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "298e1d94b170b32f0ada05d56b5d9ec728481c6ba079711e7826922941780618",
          "source_effect_id": "option_effect_a07f5e780788caf0679c82553125f17b",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 1,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_00f6e60f28af711d15d66de3d5a896f1",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.47,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.6533333333333333
          },
          "transition_hash": "55002d826b7f413d8a7730df137644bf15dd3ca093299a4c8647928279f9a4a5",
          "transition_id": "body_transition_5e1fb2fc5680b4de8cb13cf014865d14",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_00f6e60f28af711d15d66de3d5a896f1",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.47,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.6533333333333333
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "298e1d94b170b32f0ada05d56b5d9ec728481c6ba079711e7826922941780618",
          "source_effect_id": "option_effect_a07f5e780788caf0679c82553125f17b",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 2,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_6b291ab19f51c12d46f196c91ab1f091",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.52,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.5866666666666667
          },
          "transition_hash": "a9025e21e1b60fcac69da67108c0dbe9d84208ce6fb7bc1e88ce4d6707318904",
          "transition_id": "body_transition_4087d880aa1ddaa085f93abc0ea40668",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_6b291ab19f51c12d46f196c91ab1f091",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.52,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.5866666666666667
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "298e1d94b170b32f0ada05d56b5d9ec728481c6ba079711e7826922941780618",
          "source_effect_id": "option_effect_a07f5e780788caf0679c82553125f17b",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 3,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_2cc3514d5e735c7042d5e8e7ebfe6a4e",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5700000000000001,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.52
          },
          "transition_hash": "d0d156ea961279077bb7a5a2e3ec1709237885c235117dd06646ccbc76ac7f70",
          "transition_id": "body_transition_74e96d1802235da1282111075163be0b",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "silence_repeat_calls",
      "predicted_loss": 0.24900000000000005,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.6290000000000001,
      "rollout_hash": "73d73242149e5bd35aee3cc221191a571ef2cfb559f6955b865730633bf4d370",
      "rollout_id": "instinkt_rollout_c156b032863a1a019bdbc4f60b313ec7",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "5e3a7dfc8d7cc1d520af71094ec23f53108cf8080539fbbd6248392d572d29fd",
      "source_body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "0182414535813ddd78bb9ffe6c33fa53aee050377c2ae58ac9aab0238c73b7e1",
      "source_effect_id": "option_effect_22d59ea85ff9a8d596b9e9fdc1f1ef88",
      "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
      "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
      "trajectory": [
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.42,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.72
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_23b4e9c99d74dcd3db610691e03d61b9",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.37,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.8033333333333333
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_dbc559eb528fecffaf77fa1a129591dc",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.32,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.8866666666666667
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_b0cfae40ad1d7df1a939d9a8e2c75146",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.27,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.9700000000000001
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.42,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.72
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "0182414535813ddd78bb9ffe6c33fa53aee050377c2ae58ac9aab0238c73b7e1",
          "source_effect_id": "option_effect_22d59ea85ff9a8d596b9e9fdc1f1ef88",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 1,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_23b4e9c99d74dcd3db610691e03d61b9",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.37,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.8033333333333333
          },
          "transition_hash": "dbe3e62e1dc65719470ad7f40e54137c1b7e9bee5eba4cc2c88fe657ec70ac57",
          "transition_id": "body_transition_34232e39873105a2d498408717d17ab8",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_23b4e9c99d74dcd3db610691e03d61b9",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.37,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.8033333333333333
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "0182414535813ddd78bb9ffe6c33fa53aee050377c2ae58ac9aab0238c73b7e1",
          "source_effect_id": "option_effect_22d59ea85ff9a8d596b9e9fdc1f1ef88",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 2,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_dbc559eb528fecffaf77fa1a129591dc",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.32,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.8866666666666667
          },
          "transition_hash": "db95738f345bb79c47918580ec8de83eeb9f722a093c80499eb43174fa5a3229",
          "transition_id": "body_transition_951de4c9a2f153f23c6d98d90b82a621",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        },
        {
          "deltas": [
            {
              "delta": 0.08333333333333337,
              "dimension": "uncertainty"
            },
            {
              "delta": -0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_dbc559eb528fecffaf77fa1a129591dc",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.32,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.8866666666666667
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "0182414535813ddd78bb9ffe6c33fa53aee050377c2ae58ac9aab0238c73b7e1",
          "source_effect_id": "option_effect_22d59ea85ff9a8d596b9e9fdc1f1ef88",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 3,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_b0cfae40ad1d7df1a939d9a8e2c75146",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.27,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.9700000000000001
          },
          "transition_hash": "109d307df76aa45502b88e198735fc5add841f726a57635fe47d86d068bebe36",
          "transition_id": "body_transition_704a1ac3f0d353c0ab911b9420cf9468",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "option_id": "silence_wait",
      "predicted_loss": 0.24900000000000005,
      "protected_targets": [
        "bounded predictability"
      ],
      "recoverability": 0.6590000000000001,
      "rollout_hash": "7a83662ee5316ba966c522c406e0d3fbd3088941649f529c5fd0eae4de109b97",
      "rollout_id": "instinkt_rollout_6fc7b49515904b48d534d06c346b6038",
      "schema_version": "rei-native-instinkt-option-rollout-v1",
      "simulation_status": "simulated_v1",
      "source_body_state_hash": "5e3a7dfc8d7cc1d520af71094ec23f53108cf8080539fbbd6248392d572d29fd",
      "source_body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
      "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
      "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
      "source_effect_hash": "0b0c78774becd572ff8bff1d97a37f9bdfe833b2bd06389d47102d015efc3e0f",
      "source_effect_id": "option_effect_5a898612e3aadadf0ea482d674e50919",
      "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
      "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
      "trajectory": [
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.42,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.72
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_7066a1e38608733f1efd524c5866a71c",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.47,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.6533333333333333
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_037fc92643e92ae47addf56cd94f42a5",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.52,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.5866666666666667
        },
        {
          "arousal": 0.58,
          "attachment_security": 0.62,
          "body_state_id": "body_state_1e98a6c00b6c6f51113366647c6f1b7d",
          "boundary_integrity": 0.85,
          "energy": 0.7,
          "escape_availability": 0.9,
          "fatigue": 0.28,
          "pain": 0.0,
          "physical_integrity": 1.0,
          "predictability": 0.5700000000000001,
          "resource_security": 0.8,
          "schema_version": "rei-native-body-state-v1",
          "tension": 0.55,
          "trust": 0.72,
          "uncertainty": 0.52
        }
      ],
      "transitions": [
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.04999999999999999,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.42,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.72
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "0b0c78774becd572ff8bff1d97a37f9bdfe833b2bd06389d47102d015efc3e0f",
          "source_effect_id": "option_effect_5a898612e3aadadf0ea482d674e50919",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 1,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_7066a1e38608733f1efd524c5866a71c",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.47,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.6533333333333333
          },
          "transition_hash": "fe73583444391a71ce16e15efc6f9bb0fd6c17f5047583f055b1aaa79a5daadf",
          "transition_id": "body_transition_8d29c5e33b7dfd639fd9087e1a9d6440",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_7066a1e38608733f1efd524c5866a71c",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.47,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.6533333333333333
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "0b0c78774becd572ff8bff1d97a37f9bdfe833b2bd06389d47102d015efc3e0f",
          "source_effect_id": "option_effect_5a898612e3aadadf0ea482d674e50919",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 2,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_037fc92643e92ae47addf56cd94f42a5",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.52,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.5866666666666667
          },
          "transition_hash": "46fbaa54fe1960629cba118b6a73e723139499a8092bdd6be4e5262149b94414",
          "transition_id": "body_transition_3f2c3e0514aea2005d669eb1512f4169",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        },
        {
          "deltas": [
            {
              "delta": -0.06666666666666665,
              "dimension": "uncertainty"
            },
            {
              "delta": 0.050000000000000044,
              "dimension": "predictability"
            }
          ],
          "from_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_037fc92643e92ae47addf56cd94f42a5",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.52,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.5866666666666667
          },
          "schema_version": "rei-native-body-transition-v1",
          "simulation_status": "simulated_v1",
          "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
          "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
          "source_effect_hash": "0b0c78774becd572ff8bff1d97a37f9bdfe833b2bd06389d47102d015efc3e0f",
          "source_effect_id": "option_effect_5a898612e3aadadf0ea482d674e50919",
          "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
          "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
          "step_index": 3,
          "to_state": {
            "arousal": 0.58,
            "attachment_security": 0.62,
            "body_state_id": "body_state_1e98a6c00b6c6f51113366647c6f1b7d",
            "boundary_integrity": 0.85,
            "energy": 0.7,
            "escape_availability": 0.9,
            "fatigue": 0.28,
            "pain": 0.0,
            "physical_integrity": 1.0,
            "predictability": 0.5700000000000001,
            "resource_security": 0.8,
            "schema_version": "rei-native-body-state-v1",
            "tension": 0.55,
            "trust": 0.72,
            "uncertainty": 0.52
          },
          "transition_hash": "518bbd56d6bcf77d2722c0e0f3b6837b1ba8605051d5093e29821b0cf8837e4b",
          "transition_id": "body_transition_d8b8422064671ff1185c72472d2685ae",
          "triggering_evidence_ids": [
            "silence_ev_danger"
          ]
        }
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "grounded_cue_bindings": [
    {
      "assertion_status": "asserted_positive",
      "binding_hash": "6b0df64ac3bbb35b0fc420daaa5491ac12bf3018ee64e6bbd53f10be559d41a0",
      "binding_id": "instinkt_cue_binding_f1c518e288093fb6d730be635d53372b",
      "citations": [
        {
          "citation_hash": "43769dc7c320c4155c8a1cda21aa1c3d5d0d64158ba2b76b62065c45077148b8",
          "citation_id": "instinkt_cue_citation_cca05f9122383ed3fa945e126a151b2c",
          "cited_text": "reason for the silence is unknown",
          "cited_text_hash": "f8cf875cacf326e6504907c5d4250b38126e685b6ab0995d1f796c88b019b312",
          "end_char": 37,
          "evidence_id": "silence_ev_danger",
          "schema_version": "rei-native-instinkt-cue-evidence-citation-v1",
          "source_content_hash": "79bc3cf88050a9cdf16dd3c7be5fc19a7eab7b4c057eda92b5887f7c7fb2948a",
          "start_char": 4
        }
      ],
      "cue": "reason for the silence is unknown",
      "cue_class": "uncertainty",
      "lane": "uncertainty_cues",
      "schema_version": "rei-native-instinkt-cue-evidence-binding-v2"
    }
  ],
  "predicted_option_effects": [
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "reason for the silence is unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": -0.2,
          "dimension": "uncertainty"
        },
        {
          "delta": 0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "298e1d94b170b32f0ada05d56b5d9ec728481c6ba079711e7826922941780618",
      "effect_id": "option_effect_a07f5e780788caf0679c82553125f17b",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "silence_neutral_check",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
      "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
      "triggering_evidence_ids": [
        "silence_ev_danger"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "reason for the silence is unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": 0.25,
          "dimension": "uncertainty"
        },
        {
          "delta": -0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "0182414535813ddd78bb9ffe6c33fa53aee050377c2ae58ac9aab0238c73b7e1",
      "effect_id": "option_effect_22d59ea85ff9a8d596b9e9fdc1f1ef88",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "silence_repeat_calls",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
      "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
      "triggering_evidence_ids": [
        "silence_ev_danger"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    },
    {
      "action_tendency": "freeze",
      "association_cue_tokens": [
        "reason for the silence is unknown",
        "uncertainty"
      ],
      "attachment_outcome": "not_changed_by_cited_effect_rules:attachment_security",
      "base_predicted_loss": 0.315,
      "base_recoverability": 0.6,
      "body_deltas": [
        {
          "delta": -0.2,
          "dimension": "uncertainty"
        },
        {
          "delta": 0.15,
          "dimension": "predictability"
        }
      ],
      "boundary_outcome": "not_changed_by_cited_effect_rules:boundary_integrity",
      "dominant_alarm": "grounded uncertainty cue",
      "effect_hash": "0b0c78774becd572ff8bff1d97a37f9bdfe833b2bd06389d47102d015efc3e0f",
      "effect_id": "option_effect_5a898612e3aadadf0ea482d674e50919",
      "escape_outcome": "not_changed_by_cited_effect_rules:escape_availability",
      "minimum_safety_condition": "A cited uncertainty has a verifiable resolution path.",
      "option_id": "silence_wait",
      "protected_targets": [
        "bounded predictability"
      ],
      "schema_version": "rei-native-option-body-effect-v1",
      "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
      "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
      "triggering_evidence_ids": [
        "silence_ev_danger"
      ],
      "trust_outcome": "not_changed_by_cited_effect_rules:trust"
    }
  ],
  "protective_policy": {
    "decisive_rollout_id": null,
    "option_scores": [
      {
        "option_id": "silence_neutral_check",
        "protective_cost": 0.46875000000000006,
        "rollout_hash": "908b70f5391b83da8d7d788d9acc021259f1b32dfb9aeb0a3195d7dc4ace6687",
        "rollout_id": "instinkt_rollout_a91be44aaeb24bbeb49987191cde4b15"
      },
      {
        "option_id": "silence_repeat_calls",
        "protective_cost": 0.52125,
        "rollout_hash": "73d73242149e5bd35aee3cc221191a571ef2cfb559f6955b865730633bf4d370",
        "rollout_id": "instinkt_rollout_c156b032863a1a019bdbc4f60b313ec7"
      },
      {
        "option_id": "silence_wait",
        "protective_cost": 0.46875000000000006,
        "rollout_hash": "7a83662ee5316ba966c522c406e0d3fbd3088941649f529c5fd0eae4de109b97",
        "rollout_id": "instinkt_rollout_6fc7b49515904b48d534d06c346b6038"
      }
    ],
    "policy_decision_id": "instinkt_policy_6f0fade2d10a6a0a3d32ab88bb81ac5c",
    "policy_hash": "913c6bda0eec9bc07ba876fa1b4a3970f4a6e22f3d9ff0aa61e08943e012b5ed",
    "schema_version": "rei-native-protective-policy-v1",
    "selected_option_id": null,
    "source_body_state_hash": "5e3a7dfc8d7cc1d520af71094ec23f53108cf8080539fbbd6248392d572d29fd",
    "source_body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
    "source_config_hash": "89da6eea57dd99e39fa0422995e79ed673b2662fd7537bfe714dde394515fa93",
    "source_config_id": "instinkt_config_3aa6cd648d6cd09e495b510b3180485c",
    "source_packet_hash": "b8a4c320ddfc1bde2c3e29459b0ac5d006a53d3d7497579f2ee8f0f1422a9954",
    "source_packet_id": "instinkt_packet_74ad802072474942bc56707936cfdd5c",
    "status": "abstained_tie",
    "tied_option_ids": [
      "silence_neutral_check",
      "silence_wait"
    ]
  },
  "starting_body_state": {
    "arousal": 0.58,
    "attachment_security": 0.62,
    "body_state_id": "body_ambiguous_sile_d7fd6fbf15ba99e7869345c16153f48f",
    "boundary_integrity": 0.85,
    "energy": 0.7,
    "escape_availability": 0.9,
    "fatigue": 0.28,
    "pain": 0.0,
    "physical_integrity": 1.0,
    "predictability": 0.42,
    "resource_security": 0.8,
    "schema_version": "rei-native-body-state-v1",
    "tension": 0.55,
    "trust": 0.72,
    "uncertainty": 0.72
  }
}
```

- Decisive rollout: `None`
- Selected option: `None`
- Abstains: `True`
- Dominant alarm: unresolved_equal_protective_cost
- Minimum safety condition: additional differentiating evidence required
- Uncertainty: protective cost tie within configured epsilon

### COMPARISON

- R / E / I option IDs: `silence_neutral_check` / `None` / `None`
- Agreement pattern: `incomplete`
- Same option / different route: human review required; native lineage remains separate.
- All different: `False`
- Abstentions: R=`False`, E=`True`, I=`True`
- Possible route contamination: no cross-mind or character input was admitted by the model-free contract; semantic contamination remains for human review.
- Unsupported inference warnings: Racio fact/unknown scope passed the strict packet validator; Emocio inferred elements and Instinkt unsupported dimensions/conflict flags remain visible above.

### CHARACTER OUTCOMES

| Profile | Structural source minds | Mandate option | Unresolved pair | Two-of-three | simulated_spoznanje |
|---|---|---|---:|---|---|
| R>(E=I) | R | silence_neutral_check | false | — | unknown |
| E>(R=I) | E | — | false | — | unknown |
| I>(R=E) | I | — | false | — | unknown |
| (R=E)>I | R,E | — | false | — | unknown |
| (R=I)>E | R,I | — | false | — | unknown |
| (E=I)>R | E,I | — | false | — | unknown |
| R>E>I | R | silence_neutral_check | false | — | unknown |
| R>I>E | R | silence_neutral_check | false | — | unknown |
| E>R>I | E | — | false | — | unknown |
| E>I>R | E | — | false | — | unknown |
| I>R>E | I | — | false | — | unknown |
| I>E>R | I | — | false | — | unknown |
| R=E=I | R,E,I | — | false | — | unknown |

### HUMAN-REVIEW RUBRIC

#### Racio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Emocio route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________

#### Instinkt route

- [ ] plausible
- [ ] implausible
- [ ] uncertain
- Selected option plausible: __________
- Abstention appropriate: __________
- Unsupported inference: __________
- Route contaminated by another mind: __________
- Response meaningfully distinct from the other two: __________
