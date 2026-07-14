"""Validated bridge from a C5 prediction to the established B8 effect contract."""

from __future__ import annotations

from ..models.instinkt import (
    BodyState,
    InstinktAssociation,
    InstinktInputPacket,
    InstinktWorld,
    OptionBodyEffect,
)
from ..models.instinkt_effects import (
    InstinktEffectRuleSet,
    OptionBodyEffectCompilation,
    OptionBodyEffectPrediction,
    derive_compiled_option_body_effect,
)
from ..models.scene import DecisionOption, SceneEvent


EFFECT_COMPILER_ID = "rei.instinkt.option_body_effect_compiler"
EFFECT_COMPILER_REVISION = "c5-v2"


class EffectCompilationAbstainedError(ValueError):
    """An abstaining prediction cannot be converted into an implicit effect."""


def compile_prediction_to_option_body_effect(
    *,
    prediction: OptionBodyEffectPrediction,
    scene: SceneEvent,
    packet: InstinktInputPacket,
    world: InstinktWorld,
    body: BodyState,
    option: DecisionOption,
    ruleset: InstinktEffectRuleSet,
    association_records: tuple[InstinktAssociation, ...] = (),
) -> OptionBodyEffectCompilation:
    """Validate complete lineage, then compile only semantics cited by evidence."""

    prediction.validate_against(
        scene=scene,
        packet=packet,
        world=world,
        body=body,
        option=option,
        ruleset=ruleset,
        association_records=association_records,
    )
    if prediction.abstains:
        raise EffectCompilationAbstainedError(
            "Abstaining body-effect prediction has no effect to compile"
        )
    effect = derive_compiled_option_body_effect(
        prediction=prediction,
        packet=packet,
        ruleset=ruleset,
    )
    compilation = OptionBodyEffectCompilation.create(
        prediction=prediction,
        ruleset=ruleset,
        compiler_id=EFFECT_COMPILER_ID,
        compiler_revision=EFFECT_COMPILER_REVISION,
        option_body_effect=effect,
    )
    return compilation.validate_against(
        prediction=prediction,
        ruleset=ruleset,
        packet=packet,
    )


def compile_option_body_effect(**kwargs) -> OptionBodyEffect:
    """Convenience view for B8 callers while preserving compilation separately."""

    return compile_prediction_to_option_body_effect(**kwargs).option_body_effect


__all__ = [
    "EFFECT_COMPILER_ID",
    "EFFECT_COMPILER_REVISION",
    "EffectCompilationAbstainedError",
    "compile_option_body_effect",
    "compile_prediction_to_option_body_effect",
]
