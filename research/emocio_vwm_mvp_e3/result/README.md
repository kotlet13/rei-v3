# E3 result — positive control failed

The official Sketchy 128 checkpoint loaded and the unmodified pinned LPWM completed its forward inference. The frozen E3 diagnostic adapter then failed while reshaping an `obj_on` tensor that was already time-shaped (`[1, 21, 64, 1]`). Therefore the required particle/mask/rollout evidence could not be sealed.

Per the frozen stop rule, E3 stops as `positive_control_failed`. Target construction and target training were not started; optimizer-step count is zero. This is an adapter/diagnostic-pipeline failure, not an E3 target model-fit failure, and it makes no negative claim about LPWM objectness or visual world models in general.

No social model-fit or dynamics gate was started, and the active REI runtime was not modified.
