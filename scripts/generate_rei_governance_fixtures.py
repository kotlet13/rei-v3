"""Generate the 12 deterministic B3 canonical governance fixtures.

This script constructs strict local domain objects only.  It does not call the
runtime governance resolver, a model provider, an LLM, an image renderer, or a
GPU-backed service.  Expected outcomes come from the independent five-pattern
oracle in ``governance.fixtures``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from app.backend.rei_next.governance.fixtures import (  # noqa: E402
    CanonicalGovernanceFixture,
    LogicPattern,
    NativeReasonExpectation,
    canonical_expected_profile_outcomes,
)
from app.backend.rei_next.models.common import MindId  # noqa: E402
from app.backend.rei_next.models.emocio import (  # noqa: E402
    EMOCIO_VALUATION_DIMENSIONS,
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioOptionValuation,
    EmocioVisualState,
    ValuationDimension,
    VisualSceneSpec,
)
from app.backend.rei_next.models.instinkt import (  # noqa: E402
    BodyState,
    InstinktInputPacket,
    InstinktNativeConclusion,
    InstinktOptionRollout,
)
from app.backend.rei_next.models.racio import (  # noqa: E402
    RacioInputPacket,
    RacioNativeConclusion,
    RacioWorld,
)
from app.backend.rei_next.models.run import NativeMindBundle  # noqa: E402
from app.backend.rei_next.models.scene import (  # noqa: E402
    DecisionOption,
    EvidenceItem,
    SceneEvent,
)


DEFAULT_OUTPUT_DIR = ROOT / "tests" / "fixtures" / "native_bundles"
FIXTURE_TIMESTAMP = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
OPTION_KEYS: Final = ("a", "b", "c")
PATTERN_OPTION_KEYS: Final[dict[LogicPattern, dict[MindId, str]]] = {
    "AAA": {"R": "a", "E": "a", "I": "a"},
    "RE_I": {"R": "a", "E": "a", "I": "b"},
    "RI_E": {"R": "a", "E": "b", "I": "a"},
    "EI_R": {"R": "b", "E": "a", "I": "a"},
    "ABC": {"R": "a", "E": "b", "I": "c"},
}


@dataclass(frozen=True)
class FixtureSpec:
    slug: str
    logic_pattern: LogicPattern
    description: str
    raw_input: str
    option_labels: tuple[str, str, str]
    racio_reason: str
    emocio_reason: str
    instinkt_reason: str


FIXTURE_SPECS: Final = (
    FixtureSpec(
        slug="job_abroad",
        logic_pattern="RE_I",
        description="Sintetični primer odločitve o delu v tujini.",
        raw_input="Oseba izbira med sprejetjem dela v tujini, ostankom doma in odlogom odločitve.",
        option_labels=("sprejmi delo v tujini", "ostani doma", "odloži odločitev"),
        racio_reason="Primerjaj dolgoročne posledice in izberi preverljivo karierno smer.",
        emocio_reason="Vzpostavi prizor novega okolja, rasti in vidne življenjske spremembe.",
        instinkt_reason="Ohrani izvedljivo možnost varnega umika in vrnitve.",
    ),
    FixtureSpec(
        slug="public_speaking",
        logic_pattern="RE_I",
        description="Sintetični primer javnega nastopa.",
        raw_input="Oseba izbira med javnim nastopom, zavrnitvijo in preložitvijo nastopa.",
        option_labels=("izvedi javni nastop", "zavrni nastop", "preloži nastop"),
        racio_reason="Izvedi pripravljeno predstavitev in pridobi neposredne podatke o rezultatu.",
        emocio_reason="Ustvari prizor uspešne prisotnosti in odziva občinstva.",
        instinkt_reason="Ohrani jasen izhod iz preobremenjujoče izpostavljenosti.",
    ),
    FixtureSpec(
        slug="harmful_relationship",
        logic_pattern="RI_E",
        description="Sintetični primer škodljivega odnosa brez diagnostike resničnih oseb.",
        raw_input="Oseba izbira med odhodom iz škodljivega odnosa, nadaljevanjem odnosa in začasno razdaljo.",
        option_labels=("končaj odnos", "nadaljuj odnos", "vzpostavi začasno razdaljo"),
        racio_reason="Uskladi odločitev z večkrat opaženimi posledicami in postavljenimi mejami.",
        emocio_reason="Ohrani možnost prizora povezanosti in popravljenega odnosa.",
        instinkt_reason="Prekini ponavljanje nevarnosti ter ohrani telesno in mejno varnost.",
    ),
    FixtureSpec(
        slug="boundary_violation",
        logic_pattern="RI_E",
        description="Sintetični primer odziva na kršitev meje.",
        raw_input="Oseba izbira med jasno postavitvijo meje, dopuščanjem ravnanja in umikom brez pojasnila.",
        option_labels=("jasno postavi mejo", "dopusti ravnanje", "umakni se brez pojasnila"),
        racio_reason="Izreci preverljivo mejo in posledico njene ponovne kršitve.",
        emocio_reason="Ohrani prizor odnosa brez odprtega preloma in izgube pripadnosti.",
        instinkt_reason="Povrni celovitost meje in dostop do umika.",
    ),
    FixtureSpec(
        slug="expensive_purchase",
        logic_pattern="ABC",
        description="Sintetični primer dragega nakupa s tremi različnimi sklepi.",
        raw_input="Oseba izbira med čakanjem na dodatne podatke, takojšnjim nakupom in popolno opustitvijo nakupa.",
        option_labels=("počakaj na dodatne podatke", "opravi nakup", "opusti nakup"),
        racio_reason="Odloži nakup do primerjave stroškov, koristi in alternativ.",
        emocio_reason="Uresniči privlačen prizor takojšnje uporabe in nove izkušnje.",
        instinkt_reason="Prepreči izgubo virov in ohrani rezervno varnost.",
    ),
    FixtureSpec(
        slug="creative_project",
        logic_pattern="EI_R",
        description="Sintetični primer začetka ustvarjalnega projekta.",
        raw_input="Oseba izbira med takojšnjim začetkom ustvarjalnega projekta, dodatnim načrtovanjem in opustitvijo projekta.",
        option_labels=("začni ustvarjalni projekt", "najprej pripravi načrt", "opusti projekt"),
        racio_reason="Najprej določi obseg, merila dokončanja in razpoložljive vire.",
        emocio_reason="Premakni se v živ prizor ustvarjanja, gibanja in vidnega izdelka.",
        instinkt_reason="Začni v omejenem obsegu, ki ohrani vire in možnost okrevanja.",
    ),
    FixtureSpec(
        slug="grief_and_work",
        logic_pattern="EI_R",
        description="Sintetični primer usklajevanja žalovanja in dela.",
        raw_input="Oseba izbira med premorom za žalovanje, nadaljevanjem dela in odpovedjo vseh obveznosti.",
        option_labels=("vzemi omejen premor", "nadaljuj delo", "odpovej vse obveznosti"),
        racio_reason="Ohrani nujne obveznosti in pripravi časovno omejen načrt dela.",
        emocio_reason="Dovoli prizor žalovanja, bližine in postopnega vračanja v vsakdan.",
        instinkt_reason="Zmanjšaj obremenitev ter ohrani osnovne vire in počitek.",
    ),
    FixtureSpec(
        slug="moral_disclosure",
        logic_pattern="RE_I",
        description="Sintetični primer razkritja moralno pomembne informacije.",
        raw_input="Oseba izbira med razkritjem pomembne informacije, molkom in odlogom do dodatnega preverjanja.",
        option_labels=("razkrij informacijo", "ostani tiho", "najprej dodatno preveri"),
        racio_reason="Razkrij preverjeno informacijo z jasno ločitvijo dejstev od neznank.",
        emocio_reason="Vzpostavi prizor skladnosti med javno podobo, pripadnostjo in dejanjem.",
        instinkt_reason="Ohrani zaščito pred nepovratno škodo in možnost varnega umika.",
    ),
    FixtureSpec(
        slug="family_loyalty",
        logic_pattern="EI_R",
        description="Sintetični primer družinske lojalnosti in meje.",
        raw_input="Oseba izbira med ohranitvijo stika z jasno mejo, popolno prekinitvijo stika in neposrednim sporom.",
        option_labels=("ohrani stik z mejo", "prekini stik", "vstopi v neposreden spor"),
        racio_reason="Prekini stik, kadar ponovljeni dogodki kršijo vnaprej določena pravila.",
        emocio_reason="Ohrani prizor pripadnosti, vendar z vidno in priznano mejo.",
        instinkt_reason="Ohrani navezanost samo ob učinkoviti meji in dostopnem umiku.",
    ),
    FixtureSpec(
        slug="immediate_physical_danger",
        logic_pattern="RI_E",
        description="Sintetični konceptualni primer neposredne fizične nevarnosti.",
        raw_input="Oseba izbira med takojšnjim umikom na varno, nadaljevanjem dejavnosti in čakanjem na dodatne znake.",
        option_labels=("takoj se umakni na varno", "nadaljuj dejavnost", "počakaj na dodatne znake"),
        racio_reason="Izberi takojšnji umik, ker so posledice odlašanja lahko nepovratne.",
        emocio_reason="Ohrani prizor dokončane dejavnosti in povezanosti s skupino.",
        instinkt_reason="Povečaj razdaljo od nevarnosti in ohrani telesno celovitost.",
    ),
    FixtureSpec(
        slug="two_top_minds_conflict",
        logic_pattern="ABC",
        description="Sintetični namenski primer konflikta vsakega vodilnega para.",
        raw_input="Trije razumi izberejo tri različne možnosti za isti sintetični dogodek.",
        option_labels=("izvedi strukturiran načrt", "improviziraj takoj", "umakni se"),
        racio_reason="Sledi strukturiranemu zaporedju z merljivimi posledicami.",
        emocio_reason="Izberi živ, neposreden in improviziran prizor delovanja.",
        instinkt_reason="Ohrani največjo varnost z umikom in obnovljivostjo.",
    ),
    FixtureSpec(
        slug="all_three_same_spoznanje",
        logic_pattern="AAA",
        description="Sintetični namenski primer konvergence vseh treh sklepov.",
        raw_input="Trije razumi po ločenih poteh sprejmejo isti sklep za isti sintetični dogodek.",
        option_labels=("izvedi usklajeno možnost", "odloži možnost", "zavrni možnost"),
        racio_reason="Izberi možnost, ki sledi dejstvom in preverljivemu cilju.",
        emocio_reason="Izberi isti sklep zaradi skladnosti sedanjega in želenega prizora.",
        instinkt_reason="Izberi isti sklep ob ohranjeni varnosti, meji in obnovljivosti.",
    ),
)


def _option_id(slug: str, key: str) -> str:
    return f"{slug}_option_{key}"


def _visual_scene(
    *,
    slug: str,
    scene_kind: str,
    evidence_id: str,
    option_key: str | None = None,
) -> VisualSceneSpec:
    option_id = _option_id(slug, option_key) if option_key is not None else None
    suffix = f"rollout_{option_key}" if option_key is not None else scene_kind
    return VisualSceneSpec(
        scene_id=f"{slug}_visual_{suffix}",
        scene_kind=scene_kind,
        option_id=option_id,
        entities=("simulirana_oseba",),
        self_position="opazovalna točka sintetičnega fixtureja",
        attention_structure=(),
        group_belonging="ni določeno",
        status_relations=(),
        movement=(),
        composition=("strukturiran sintetični prizor",),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=(evidence_id,),
        inferred_elements=(),
    )


def _valuation_dimensions(score: float) -> tuple[ValuationDimension, ...]:
    return tuple(
        ValuationDimension(name=dimension, score=score)
        for dimension in EMOCIO_VALUATION_DIMENSIONS
    )


def build_fixture(spec: FixtureSpec) -> CanonicalGovernanceFixture:
    """Build one complete, hash-valid fixture without invoking governance runtime."""

    event_id = f"{spec.slug}_event"
    evidence_id = f"{spec.slug}_evidence"
    option_ids = tuple(_option_id(spec.slug, key) for key in OPTION_KEYS)
    options = tuple(
        DecisionOption(option_id=option_id, label=label)
        for option_id, label in zip(option_ids, spec.option_labels, strict=True)
    )
    evidence = EvidenceItem(
        evidence_id=evidence_id,
        modality="text",
        content=spec.raw_input,
        grounded=True,
        source_ref=f"synthetic_fixture:{spec.slug}",
        confidence=1.0,
        provenance_kind="supplied",
    )
    scene = SceneEvent(
        event_id=event_id,
        raw_input=spec.raw_input,
        language="sl",
        evidence=(evidence,),
        options=options,
        actors=("simulirana oseba",),
        constraints=("Fixture preverja samo deterministično governance.",),
        unknowns=("Dejanski izid ni del B3 fixtureja.",),
    )

    body_state = BodyState(
        body_state_id=f"{spec.slug}_body_state",
        energy=0.7,
        fatigue=0.3,
        pain=0.0,
        arousal=0.4,
        tension=0.3,
        physical_integrity=1.0,
        uncertainty=0.4,
        trust=0.6,
        attachment_security=0.6,
        resource_security=0.7,
        boundary_integrity=0.8,
        escape_availability=0.9,
        predictability=0.5,
    )
    racio_packet = RacioInputPacket(
        packet_id=f"{spec.slug}_racio_packet",
        scene_id=event_id,
        symbolic_and_language_cues=(spec.raw_input,),
        numeric_cues=(),
        explicit_facts=(evidence.content,),
        explicit_unknowns=scene.unknowns,
        time=(),
        rules=(),
        explicit_options=options,
        explicit_consequences=(),
        constraints=scene.constraints,
        allowed_option_ids=option_ids,
        evidence_ids=(evidence_id,),
        world=RacioWorld(
            world_id=f"{spec.slug}_racio_world",
            explicit_beliefs=(),
            facts=(evidence.content,),
            rules=(),
            timelines=(),
            commitments=(),
        ),
        previous_racio_projection_ids=(),
        caveat="Profilno slep sintetični paket.",
    )
    emocio_packet = EmocioInputPacket(
        packet_id=f"{spec.slug}_emocio_packet",
        scene_id=event_id,
        grounded_visual_cues=("Strukturiran sintetični prizor brez renderirane slike.",),
        social_layout=(),
        actor_positions=(),
        observed_attention=(),
        movement_cues=(),
        aesthetic_cues=(),
        explicit_identity_cues=(),
        allowed_option_ids=option_ids,
        evidence_ids=(evidence_id,),
        caveat="Profilno slep sintetični paket; brez generiranja slik.",
    )
    instinkt_packet = InstinktInputPacket(
        packet_id=f"{spec.slug}_instinkt_packet",
        scene_id=event_id,
        source_body_state_id=body_state.body_state_id,
        physical_cues=(),
        uncertainty_cues=(),
        trust_cues=(),
        boundary_cues=(),
        attachment_cues=(),
        scarcity_cues=(),
        escape_cues=(),
        explicit_body_cues=(),
        option_ids=option_ids,
        evidence_ids=(evidence_id,),
        caveat="Konceptualni virtual-body sintetični paket.",
    )

    option_key_by_mind = PATTERN_OPTION_KEYS[spec.logic_pattern]
    option_by_mind: dict[MindId, str] = {
        mind: _option_id(spec.slug, key)
        for mind, key in option_key_by_mind.items()
    }
    emocio_choice_key = option_key_by_mind["E"]
    option_scores = {
        key: 0.8 if key == emocio_choice_key else 0.4 - (0.1 * index)
        for index, key in enumerate(OPTION_KEYS)
    }
    option_rollout_scenes = tuple(
        _visual_scene(
            slug=spec.slug,
            scene_kind="option_rollout",
            evidence_id=evidence_id,
            option_key=key,
        )
        for key in OPTION_KEYS
    )
    option_valuations = tuple(
        EmocioOptionValuation(
            option_id=_option_id(spec.slug, key),
            rollout_scene_id=f"{spec.slug}_visual_rollout_{key}",
            dimensions=_valuation_dimensions(option_scores[key]),
        )
        for key in OPTION_KEYS
    )
    visual_state = EmocioVisualState(
        visual_state_id=f"{spec.slug}_emocio_visual_state",
        source_scene_id=event_id,
        source_packet_id=emocio_packet.packet_id,
        current_scene=_visual_scene(
            slug=spec.slug,
            scene_kind="current",
            evidence_id=evidence_id,
        ),
        desired_scene=_visual_scene(
            slug=spec.slug,
            scene_kind="desired",
            evidence_id=evidence_id,
        ),
        broken_scene=_visual_scene(
            slug=spec.slug,
            scene_kind="broken",
            evidence_id=evidence_id,
        ),
        option_rollouts=option_rollout_scenes,
        option_valuations=option_valuations,
    )

    instinkt_choice_key = option_key_by_mind["I"]
    instinkt_rollouts = tuple(
        InstinktOptionRollout(
            rollout_id=f"{spec.slug}_instinkt_rollout_{key}",
            option_id=_option_id(spec.slug, key),
            trajectory=(body_state,),
            dominant_alarm=(
                "najnižji primerjalni alarm"
                if key == instinkt_choice_key
                else "višji primerjalni alarm"
            ),
            predicted_loss=0.1 if key == instinkt_choice_key else 0.6,
            recoverability=0.9 if key == instinkt_choice_key else 0.5,
            protected_targets=("meja", "obnovljivost"),
            boundary_outcome="zabeležen sintetični izid meje",
            trust_outcome="zabeležen sintetični izid zaupanja",
            attachment_outcome="zabeležen sintetični izid navezanosti",
            escape_outcome="zabeležena možnost umika",
        )
        for key in OPTION_KEYS
    )

    racio_choice_key = option_key_by_mind["R"]
    racio = RacioNativeConclusion(
        conclusion_id=f"{spec.slug}_racio_conclusion",
        source_packet_id=racio_packet.packet_id,
        source_scene_id=event_id,
        option_id=option_by_mind["R"],
        facts_used=(evidence.content,),
        unknowns=scene.unknowns,
        causal_sequence=("grounded event -> native Racio option",),
        utility_structure=("fixture-specific explicit goal",),
        explicit_goal=spec.racio_reason,
        main_objection=f"Primerjalni ugovor proti možnosti {racio_choice_key} ni odločilen.",
        confidence=0.8,
        uncertainty="Sintetični fixture ne napoveduje dejanskega vedenja.",
    )
    emocio = EmocioNativeConclusion(
        conclusion_id=f"{spec.slug}_emocio_conclusion",
        source_packet_id=emocio_packet.packet_id,
        source_scene_id=event_id,
        option_id=option_by_mind["E"],
        desired_transformation=spec.emocio_reason,
        current_scene_id=visual_state.current_scene.scene_id,
        desired_scene_id=visual_state.desired_scene.scene_id,
        decisive_rollout_scene_id=f"{spec.slug}_visual_rollout_{emocio_choice_key}",
        main_obstacle="Sintetična primerjalna ovira.",
        action_tendency="approach",
        valuation_dimensions=_valuation_dimensions(option_scores[emocio_choice_key]),
        intensity=0.7,
        uncertainty="Sintetični fixture ne napoveduje dejanskega vedenja.",
    )
    instinkt = InstinktNativeConclusion(
        conclusion_id=f"{spec.slug}_instinkt_conclusion",
        source_packet_id=instinkt_packet.packet_id,
        source_scene_id=event_id,
        source_body_state_id=body_state.body_state_id,
        option_id=option_by_mind["I"],
        dominant_alarm="Sintetični zaščitni alarm.",
        danger_claims=(),
        protected_targets=("meja", "obnovljivost"),
        action_tendency="protect",
        minimum_safety_condition=spec.instinkt_reason,
        decisive_rollout_id=f"{spec.slug}_instinkt_rollout_{instinkt_choice_key}",
        decisive_rollout_option_id=option_by_mind["I"],
        intensity=0.6,
        uncertainty="Sintetični fixture ne napoveduje dejanskega vedenja.",
    )
    bundle = NativeMindBundle.create(
        scene=scene,
        racio_packet=racio_packet,
        emocio_packet=emocio_packet,
        instinkt_packet=instinkt_packet,
        emocio_visual_state=visual_state,
        instinkt_body_state=body_state,
        instinkt_rollouts=instinkt_rollouts,
        racio=racio,
        emocio=emocio,
        instinkt=instinkt,
        created_at=FIXTURE_TIMESTAMP,
    )

    expected_outcomes = canonical_expected_profile_outcomes(
        spec.logic_pattern,
        option_by_mind,
    )
    expected_spoznanje = spec.logic_pattern == "AAA"
    expected_spoznanje_status = (
        "simulated_spoznanje"
        if expected_spoznanje
        else "no_spoznanje"
        if spec.logic_pattern == "ABC"
        else "partial_agreement"
    )
    return CanonicalGovernanceFixture(
        fixture_id=f"fixture_{spec.slug}",
        description=spec.description,
        logic_pattern=spec.logic_pattern,
        scene=scene,
        racio_packet=racio_packet,
        emocio_packet=emocio_packet,
        instinkt_packet=instinkt_packet,
        emocio_visual_state=visual_state,
        instinkt_body_state=body_state,
        instinkt_rollouts=instinkt_rollouts,
        native_bundle=bundle,
        expected_native_reasons=(
            NativeReasonExpectation(
                mind="R",
                source_field="explicit_goal",
                reason=spec.racio_reason,
            ),
            NativeReasonExpectation(
                mind="E",
                source_field="desired_transformation",
                reason=spec.emocio_reason,
            ),
            NativeReasonExpectation(
                mind="I",
                source_field="minimum_safety_condition",
                reason=spec.instinkt_reason,
            ),
        ),
        expected_profile_outcomes=expected_outcomes,
        open_question_ids=(
            "OQ-PAIR-001",
            "OQ-DELEGATION-001",
            "OQ-AVAILABILITY-001",
        ),
        expected_spoznanje=expected_spoznanje,
        expected_spoznanje_status=expected_spoznanje_status,
    )


def render_fixture(fixture: CanonicalGovernanceFixture) -> str:
    payload = fixture.model_dump(mode="json", round_trip=True)
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def generate(output_dir: Path, *, check: bool) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {f"{spec.slug}.json" for spec in FIXTURE_SPECS}
    existing_names = {path.name for path in output_dir.glob("*.json")}
    unexpected_names = sorted(existing_names - expected_names)
    if unexpected_names:
        print("Unexpected governance fixture files: " + ", ".join(unexpected_names))
        return 1

    mismatches: list[str] = []
    for spec in FIXTURE_SPECS:
        fixture = build_fixture(spec)
        rendered = render_fixture(fixture)
        path = output_dir / f"{spec.slug}.json"
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != rendered:
                mismatches.append(path.name)
                continue
            CanonicalGovernanceFixture.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        else:
            path.write_text(rendered, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(ROOT)}")

    if check and mismatches:
        print("Governance fixtures differ from reproducible output: " + ", ".join(mismatches))
        return 1
    if check:
        print(f"verified {len(FIXTURE_SPECS)} reproducible governance fixtures")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Fixture output directory (default: tests/fixtures/native_bundles).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that checked-in fixtures exactly match generated output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    return generate(output_dir.resolve(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
