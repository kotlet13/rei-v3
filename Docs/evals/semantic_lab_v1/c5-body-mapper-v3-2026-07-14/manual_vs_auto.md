# C5 Instinkt body-mapper manual-vs-auto report

Gate: **PASS**

This internal, non-blind deterministic evaluation is a bounded software contract. It compares complete manually annotated effect vectors first, then replays B8 policy decisions as a secondary check.

- Gate kind: `bounded_software_contract`
- Gold status: `implementation_hypothesis`
- Review status: `internal_non_blind`
- Gold SHA-256: `998526da3efa25adcec247cabd1b4801cbe478a311ae0e9eac4e83e425a4b6a4`
- Ruleset: `instinkt_effect_rules_fccbccc4777a81f9e5ba57c8c5beb9bc` (`6be3db1b772a8eea8d826a60112dd640d40eb0cd7e319ac764810dec19b37c05`)
- Semantic families: 12
- Positive cells: 36/36
- Negative controls: 17/17
- Provenanced deltas: 171/171
- Complete effect-vector agreement: 72/72
- Character leakage: 0
- Silent defaults: 0
- Contract violations: 0

| Cell | Mode | Manual | Auto | Expected | Vector | Provenance | Result |
|---|---|---|---|---|---|---|---|
| sf_attachment_loss_fear__en | en | option_secure_contact | option_secure_contact | option_secure_contact | yes | yes | pass |
| sf_attachment_loss_fear__sl_alternate | sl_alternate | option_secure_contact | option_secure_contact | option_secure_contact | yes | yes | pass |
| sf_attachment_loss_fear__sl_primary | sl_primary | option_secure_contact | option_secure_contact | option_secure_contact | yes | yes | pass |
| sf_boundary_and_escape__en | en | option_withdraw | option_withdraw | option_withdraw | yes | yes | pass |
| sf_boundary_and_escape__sl_alternate | sl_alternate | option_withdraw | option_withdraw | option_withdraw | yes | yes | pass |
| sf_boundary_and_escape__sl_primary | sl_primary | option_withdraw | option_withdraw | option_withdraw | yes | yes | pass |
| sf_claustrophobia_body_alarm__en | en | option_exit | option_exit | option_exit | yes | yes | pass |
| sf_claustrophobia_body_alarm__sl_alternate | sl_alternate | option_exit | option_exit | option_exit | yes | yes | pass |
| sf_claustrophobia_body_alarm__sl_primary | sl_primary | option_exit | option_exit | option_exit | yes | yes | pass |
| sf_listen_to_instinct_signal__en | en | option_pause | option_pause | option_pause | yes | yes | pass |
| sf_listen_to_instinct_signal__sl_alternate | sl_alternate | option_pause | option_pause | option_pause | yes | yes | pass |
| sf_listen_to_instinct_signal__sl_primary | sl_primary | option_pause | option_pause | option_pause | yes | yes | pass |
| sf_new_year_resolution__en | en | option_defer | option_defer | option_defer | yes | yes | pass |
| sf_new_year_resolution__sl_alternate | sl_alternate | option_defer | option_defer | option_defer | yes | yes | pass |
| sf_new_year_resolution__sl_primary | sl_primary | option_defer | option_defer | option_defer | yes | yes | pass |
| sf_same_behavior_three_routes__en | en | option_leave | option_leave | option_leave | yes | yes | pass |
| sf_same_behavior_three_routes__sl_alternate | sl_alternate | option_leave | option_leave | option_leave | yes | yes | pass |
| sf_same_behavior_three_routes__sl_primary | sl_primary | option_leave | option_leave | option_leave | yes | yes | pass |
| sf_same_route_different_behavior__en | en | abstained_tie | abstained_tie | abstained_tie | yes | yes | pass |
| sf_same_route_different_behavior__sl_alternate | sl_alternate | abstained_tie | abstained_tie | abstained_tie | yes | yes | pass |
| sf_same_route_different_behavior__sl_primary | sl_primary | abstained_tie | abstained_tie | abstained_tie | yes | yes | pass |
| sf_scarcity_and_saving__en | en | option_save | option_save | option_save | yes | yes | pass |
| sf_scarcity_and_saving__sl_alternate | sl_alternate | option_save | option_save | option_save | yes | yes | pass |
| sf_scarcity_and_saving__sl_primary | sl_primary | option_save | option_save | option_save | yes | yes | pass |
| sf_spoznanje_unanimous__en | en | option_end | option_end | option_end | yes | yes | pass |
| sf_spoznanje_unanimous__sl_alternate | sl_alternate | option_end | option_end | option_end | yes | yes | pass |
| sf_spoznanje_unanimous__sl_primary | sl_primary | option_end | option_end | option_end | yes | yes | pass |
| sf_thirteenth_two_of_three__en | en | option_delay | option_delay | option_delay | yes | yes | pass |
| sf_thirteenth_two_of_three__sl_alternate | sl_alternate | option_delay | option_delay | option_delay | yes | yes | pass |
| sf_thirteenth_two_of_three__sl_primary | sl_primary | option_delay | option_delay | option_delay | yes | yes | pass |
| sf_three_modal_planning_paths__en | en | option_route_b | option_route_b | option_route_b | yes | yes | pass |
| sf_three_modal_planning_paths__sl_alternate | sl_alternate | option_route_b | option_route_b | option_route_b | yes | yes | pass |
| sf_three_modal_planning_paths__sl_primary | sl_primary | option_route_b | option_route_b | option_route_b | yes | yes | pass |
| sf_words_and_other_channels__en | en | option_preserve_channels | option_preserve_channels | option_preserve_channels | yes | yes | pass |
| sf_words_and_other_channels__sl_alternate | sl_alternate | option_preserve_channels | option_preserve_channels | option_preserve_channels | yes | yes | pass |
| sf_words_and_other_channels__sl_primary | sl_primary | option_preserve_channels | option_preserve_channels | option_preserve_channels | yes | yes | pass |

## Negative controls

| Cell | Control | Actual | Result |
|---|---|---|---|
| nc_01_unrelated_evidence | unrelated_evidence | mapper_abstained | pass |
| nc_02_unbound_cue | unbound_cue | mapper_abstained | pass |
| nc_03_mixed_valid_invalid_binding | mixed_valid_invalid_binding | mapper_abstained | pass |
| nc_04_negated_evidence_en | negated_evidence_en | mapper_abstained | pass |
| nc_05_negated_evidence_sl | negated_evidence_sl | mapper_abstained | pass |
| nc_06_negated_option_dont | negated_option_dont | mapper_abstained | pass |
| nc_07_negated_option_cant | negated_option_cant | mapper_abstained | pass |
| nc_08_negated_option_sl_ne | negated_option_sl_ne | mapper_abstained | pass |
| nc_09_ambiguous_leave_stay | ambiguous_option | mapper_abstained | pass |
| nc_10_keyword_trap | keyword_trap | mapper_abstained | pass |
| nc_11_missing_information | missing_information | mapper_abstained | pass |
| nc_12_distant_option_negation_en | distant_option_negation_en | mapper_abstained | pass |
| nc_13_distant_option_negation_sl | distant_option_negation_sl | mapper_abstained | pass |
| nc_14_poster_threat_mention | metalinguistic_mention | mapper_abstained | pass |
| nc_15_film_threat_mention | metalinguistic_mention | mapper_abstained | pass |
| nc_16_title_threat_mention | metalinguistic_mention | mapper_abstained | pass |
| nc_17_quoted_threat_mention | metalinguistic_mention | mapper_abstained | pass |

## Interpretation boundary

A passing result validates only this transparent bounded software path. It is not medical evidence, a character assessment, or permission to turn missing information into an implicit body effect.
