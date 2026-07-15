"""Frozen, model-free C4 Stage 1 source, scenes, prompts, seeds and order."""

from __future__ import annotations

import hashlib
from typing import Literal, Self

from pydantic import model_validator

from ..emocio.c4_stage1_editor import (
    C4_STAGE1_CURRENT_SCENE_HASH,
    C4_STAGE1_CURRENT_SCENE_ID,
    C4_STAGE1_OPTION_ORDER,
    C4_STAGE1_PROFILE_HASH,
    C4_STAGE1_SOURCE_ARTIFACT_ID,
    C4_STAGE1_SOURCE_PNG_SHA256,
)
from ..emocio.packets import build_emocio_packet
from ..emocio.prompting import (
    BilingualStructuredScenePromptCompiler,
    VisualPromptProfile,
)
from ..emocio.renderer import derive_scene_seed
from ..emocio.scene_graph import compile_emocio_scenes
from ..ids import content_id
from ..models.common import FrozenArtifactModel, HashDigest, NonEmptyId, NonEmptyText
from ..models.emocio import EmocioWorld, VisualSceneSpec
from ..models.rendering import ImageSourceReference
from ..models.scene import DecisionOption, EvidenceItem, SceneEvent


C4_STAGE1_ROOT_SEED = 424240
C4_STAGE1_PROMPT_BUDGET_POLICY = "c4_editor_compact_v1"
C4_STAGE1_SOURCE_EVENT_HASH = (
    "ba47a978c067e0336950accd5ec3f592e7fb086abdc1ce6010363441e679078c"
)
C4_STAGE1_SOURCE_WORLD_HASH = (
    "8634dcafed24ca453c420774c7fb3c68033edf761a894e3241a09594e9ed527b"
)

_DOCUMENTARY_STYLE_DIRECTIVE = (
    "Documentary cinematic still, restrained natural colors, stable identity "
    "and composition. No text, labels, logos, crowns, weapons, or extra people."
)
_COMPACT_PROMPT_PREFIXES = (
    "evidence_boundary=",
    "language_gloss=",
    "localized_boundary=",
    "style_id=",
    "style_directive=",
    "style_basis=",
    "scene_data_boundary=",
    "PRIMARY IMAGE EDIT[",
    "primary_edit_execution=",
    "desired_scene_boundary=",
    "scene_kind[",
    "option_id[",
    "entities[",
    "composition[",
    "grounded_evidence_ids[",
    "inferred_elements[",
    "final_evidence_boundary=",
)
_PINNED_PROMPTS = {
    "enter_circle": (
        "visual_scene_acbc451d7b30336076e5c1e5bd31e02b",
        "7e9b9f91e0ea2f0504548d178b36ccbf0bbc8664b7e38b8ab4ea4e9be960ea57",
        1_366_714_956_115_613_163,
        "3c046f45c9c66bc35e6c1b4890f24cc021e6c692d5ca6b7288951db6d2c54cba",
        359,
    ),
    "remain_edge": (
        "visual_scene_12e01b7dc48013135871ba28868f8180",
        "48af410ba6f01adf5540044dbbe6d1bad4e3e08ddeb60ef772f7924a49e39272",
        297_232_311_612_386_773,
        "a92224abe970e7deafef346085bc8751d76aea1d484f4268c66131a05c25c25e",
        362,
    ),
}


class C4Stage1PromptCompiler(BilingualStructuredScenePromptCompiler):
    """Exact complete-segment prompt budget frozen by the Stage 1 protocol."""

    def compile(self, scene: VisualSceneSpec) -> str:
        full_prompt = super().compile(scene)
        segments = full_prompt.split("; ")
        selected = tuple(
            segment
            for segment in segments
            if segment.startswith(_COMPACT_PROMPT_PREFIXES)
        )
        if len(selected) != len(_COMPACT_PROMPT_PREFIXES):
            raise ValueError("C4 Stage 1 compact prompt is missing a required segment")
        return "; ".join(
            (
                *selected[:-1],
                f"prompt_budget_policy={C4_STAGE1_PROMPT_BUDGET_POLICY}",
                selected[-1],
            )
        )


class C4Stage1PromptBinding(FrozenArtifactModel):
    """One exact option scene, compact prompt and root-derived seed."""

    schema_version: Literal["rei-c4-stage1-prompt-binding-v1"] = (
        "rei-c4-stage1-prompt-binding-v1"
    )
    prompt_binding_id: NonEmptyId
    order_index: Literal[0, 1]
    option_id: Literal["enter_circle", "remain_edge"]
    scene: VisualSceneSpec
    scene_hash: HashDigest
    root_seed: Literal[424240] = C4_STAGE1_ROOT_SEED
    derived_seed: int
    prompt: NonEmptyText
    prompt_sha256: HashDigest
    pinned_longcat_token_count: int

    @classmethod
    def create(
        cls,
        *,
        order_index: Literal[0, 1],
        scene: VisualSceneSpec,
        prompt: str,
        pinned_longcat_token_count: int,
    ) -> C4Stage1PromptBinding:
        if scene.option_id not in C4_STAGE1_OPTION_ORDER:
            raise ValueError("C4 Stage 1 prompt scene uses an unknown option")
        payload = {
            "schema_version": "rei-c4-stage1-prompt-binding-v1",
            "order_index": order_index,
            "option_id": scene.option_id,
            "scene": scene,
            "scene_hash": scene.content_hash(),
            "root_seed": C4_STAGE1_ROOT_SEED,
            "derived_seed": derive_scene_seed(C4_STAGE1_ROOT_SEED, scene.scene_id),
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "pinned_longcat_token_count": pinned_longcat_token_count,
        }
        return cls(
            prompt_binding_id=content_id("c4_stage1_prompt_binding", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        if self.scene.option_id != self.option_id:
            raise ValueError("C4 Stage 1 prompt option differs from its scene")
        if self.scene_hash != self.scene.content_hash():
            raise ValueError("C4 Stage 1 prompt scene hash differs")
        if self.derived_seed != derive_scene_seed(self.root_seed, self.scene.scene_id):
            raise ValueError("C4 Stage 1 prompt seed differs from its scene")
        if (
            self.prompt_sha256
            != hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()
        ):
            raise ValueError("C4 Stage 1 prompt hash differs from its bytes")
        pinned = _PINNED_PROMPTS[self.option_id]
        actual = (
            self.scene.scene_id,
            self.scene_hash,
            self.derived_seed,
            self.prompt_sha256,
            self.pinned_longcat_token_count,
        )
        if actual != pinned:
            raise ValueError("C4 Stage 1 prompt binding differs from the frozen pin")
        if self.order_index != C4_STAGE1_OPTION_ORDER.index(self.option_id):
            raise ValueError("C4 Stage 1 prompt binding order differs")
        expected = content_id(
            "c4_stage1_prompt_binding",
            self.model_dump(
                mode="python", round_trip=True, exclude={"prompt_binding_id"}
            ),
        )
        if self.prompt_binding_id != expected:
            raise ValueError("C4 Stage 1 prompt binding ID differs from content")
        return self


class C4Stage1Fixture(FrozenArtifactModel):
    """Complete portable fixture shared identically by both editor families."""

    schema_version: Literal["rei-c4-stage1-fixture-v1"] = "rei-c4-stage1-fixture-v1"
    fixture_id: NonEmptyId
    source_event: SceneEvent
    source_world: EmocioWorld
    current_scene: VisualSceneSpec
    current_scene_hash: HashDigest
    source_image: ImageSourceReference
    root_seed: Literal[424240] = C4_STAGE1_ROOT_SEED
    prompt_profile: VisualPromptProfile
    prompt_profile_hash: HashDigest
    prompt_budget_policy: Literal["c4_editor_compact_v1"] = (
        C4_STAGE1_PROMPT_BUDGET_POLICY
    )
    option_order: tuple[Literal["enter_circle", "remain_edge"], ...]
    prompts: tuple[C4Stage1PromptBinding, ...]
    generated_images_are_external_evidence: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        source_event: SceneEvent,
        source_world: EmocioWorld,
        current_scene: VisualSceneSpec,
        source_image: ImageSourceReference,
        prompt_profile: VisualPromptProfile,
        prompts: tuple[C4Stage1PromptBinding, ...],
    ) -> C4Stage1Fixture:
        payload = {
            "schema_version": "rei-c4-stage1-fixture-v1",
            "source_event": source_event,
            "source_world": source_world,
            "current_scene": current_scene,
            "current_scene_hash": current_scene.content_hash(),
            "source_image": source_image,
            "root_seed": C4_STAGE1_ROOT_SEED,
            "prompt_profile": prompt_profile,
            "prompt_profile_hash": prompt_profile.content_hash(),
            "prompt_budget_policy": C4_STAGE1_PROMPT_BUDGET_POLICY,
            "option_order": C4_STAGE1_OPTION_ORDER,
            "prompts": prompts,
            "generated_images_are_external_evidence": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(fixture_id=content_id("c4_stage1_fixture", payload), **payload)

    @model_validator(mode="after")
    def validate_fixture(self) -> Self:
        if self.source_event.scene_hash() != C4_STAGE1_SOURCE_EVENT_HASH:
            raise ValueError("C4 Stage 1 source event differs from the pin")
        if self.source_world.content_hash() != C4_STAGE1_SOURCE_WORLD_HASH:
            raise ValueError("C4 Stage 1 source world differs from the pin")
        if self.current_scene.scene_id != C4_STAGE1_CURRENT_SCENE_ID:
            raise ValueError("C4 Stage 1 current scene ID differs from the pin")
        if self.current_scene_hash != self.current_scene.content_hash() or (
            self.current_scene_hash != C4_STAGE1_CURRENT_SCENE_HASH
        ):
            raise ValueError("C4 Stage 1 current scene hash differs from the pin")
        source = self.source_image
        if (
            source.image_id != C4_STAGE1_SOURCE_ARTIFACT_ID
            or source.content_sha256 != C4_STAGE1_SOURCE_PNG_SHA256
            or (source.width, source.height) != (1024, 768)
            or source.media_type != "image/png"
            or source.path != f"emocio/images/{C4_STAGE1_SOURCE_ARTIFACT_ID}.png"
            or source.grounded
            or source.originating_scene_spec_id != C4_STAGE1_CURRENT_SCENE_ID
            or source.originating_scene_spec_hash != C4_STAGE1_CURRENT_SCENE_HASH
        ):
            raise ValueError("C4 Stage 1 source image differs from the exact pin")
        if self.prompt_profile.language != "en" or (
            self.prompt_profile.style_id != "documentary_cinematic_v1"
        ):
            raise ValueError("C4 Stage 1 prompt profile differs")
        if self.prompt_profile_hash != self.prompt_profile.content_hash() or (
            self.prompt_profile_hash != C4_STAGE1_PROFILE_HASH
        ):
            raise ValueError("C4 Stage 1 prompt profile hash differs")
        if self.option_order != C4_STAGE1_OPTION_ORDER:
            raise ValueError("C4 Stage 1 option order differs")
        if tuple(item.option_id for item in self.prompts) != self.option_order:
            raise ValueError("C4 Stage 1 prompts differ from canonical option order")
        expected = content_id(
            "c4_stage1_fixture",
            self.model_dump(mode="python", round_trip=True, exclude={"fixture_id"}),
        )
        if self.fixture_id != expected:
            raise ValueError("C4 Stage 1 fixture ID differs from content")
        return self


def _source_event() -> SceneEvent:
    return SceneEvent(
        event_id="c4_real_smoke_scene",
        raw_input=(
            "Self stands at the edge of a small studio gathering and chooses "
            "whether to enter the shared circle or remain at the doorway."
        ),
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="c4_smoke_grounded_visual",
                modality="image",
                content="self at a studio doorway facing a small group",
                grounded=True,
                source_ref="synthetic:c4-smoke-fixture",
                confidence=1.0,
            ),
        ),
        options=(
            DecisionOption(
                option_id="enter_circle",
                label="enter the shared circle",
                description=(
                    "the same central self visibly crosses the threshold and stands "
                    "one meter inside the room among the collaborative group"
                ),
            ),
            DecisionOption(
                option_id="remain_edge",
                label="remain at the doorway",
                description=(
                    "the same central self remains fully visible at the same foreground "
                    "spot with both feet outside and behind the threshold"
                ),
            ),
        ),
        actors=("self", "small_group"),
        constraints=("preserve the same self and studio layout",),
        unknowns=("how the group will respond",),
    )


def _source_world() -> EmocioWorld:
    return EmocioWorld(
        world_id="c4_real_smoke_world",
        visual_memories=("dim studio doorway", "small collaborative group"),
        desired_scenes=(
            "self visibly included in a welcoming collaborative circle",
            "warm shared light",
        ),
        broken_scenes=(
            "self isolated outside the group in shadow",
            "closed social distance",
        ),
        social_identity_motifs=("visible belonging among peers",),
        attraction_patterns=("warm shared light", "open group composition"),
        motor_patterns=("one deliberate step toward the group",),
    )


def build_c4_stage1_fixture() -> C4Stage1Fixture:
    """Rebuild and fail closed against every frozen Stage 1 value."""

    event = _source_event()
    world = _source_world()
    packet = build_emocio_packet(event)
    compiled = compile_emocio_scenes(event, packet, world)
    profile = VisualPromptProfile.create(
        language="en",
        style_id="documentary_cinematic_v1",
        style_directive=_DOCUMENTARY_STYLE_DIRECTIVE,
    )
    compiler = C4Stage1PromptCompiler(profile)
    prompts = tuple(
        C4Stage1PromptBinding.create(
            order_index=index,  # type: ignore[arg-type]
            scene=scene,
            prompt=compiler.compile(scene),
            pinned_longcat_token_count=_PINNED_PROMPTS[scene.option_id][4],
        )
        for index, scene in enumerate(compiled.option_rollouts)
    )
    source_image = ImageSourceReference(
        image_id=C4_STAGE1_SOURCE_ARTIFACT_ID,
        content_sha256=C4_STAGE1_SOURCE_PNG_SHA256,
        media_type="image/png",
        path=f"emocio/images/{C4_STAGE1_SOURCE_ARTIFACT_ID}.png",
        width=1024,
        height=768,
        grounded=False,
        originating_scene_spec_id=C4_STAGE1_CURRENT_SCENE_ID,
        originating_scene_spec_hash=C4_STAGE1_CURRENT_SCENE_HASH,
    )
    return C4Stage1Fixture.create(
        source_event=event,
        source_world=world,
        current_scene=compiled.current_scene,
        source_image=source_image,
        prompt_profile=profile,
        prompts=prompts,
    )


__all__ = [
    "C4_STAGE1_CURRENT_SCENE_HASH",
    "C4_STAGE1_CURRENT_SCENE_ID",
    "C4_STAGE1_OPTION_ORDER",
    "C4_STAGE1_PROFILE_HASH",
    "C4_STAGE1_PROMPT_BUDGET_POLICY",
    "C4_STAGE1_ROOT_SEED",
    "C4_STAGE1_SOURCE_ARTIFACT_ID",
    "C4_STAGE1_SOURCE_EVENT_HASH",
    "C4_STAGE1_SOURCE_PNG_SHA256",
    "C4_STAGE1_SOURCE_WORLD_HASH",
    "C4Stage1Fixture",
    "C4Stage1PromptBinding",
    "C4Stage1PromptCompiler",
    "build_c4_stage1_fixture",
]
