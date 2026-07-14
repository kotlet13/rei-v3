from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.governance.fixtures import load_governance_fixture
from app.backend.rei.governance.profiles import (
    derive_effective_authority,
    parse_character_profile,
)
from app.backend.rei.governance.resolver import resolve_governance
from app.backend.rei.models.governance import (
    MindOption,
    PairConflict,
    PairNegotiationRound,
    TaskDelegation,
)
from governance_test_helpers import make_functional_override, make_native_bundle


PROFILE_CONTRACTS = {
    "R>(E=I)": (("R",), ("E", "I"), "single_top"),
    "E>(R=I)": (("E",), ("R", "I"), "single_top"),
    "I>(R=E)": (("I",), ("R", "E"), "single_top"),
    "(R=E)>I": (("R", "E"), ("I",), "joint_top"),
    "(R=I)>E": (("R", "I"), ("E",), "joint_top"),
    "(E=I)>R": (("E", "I"), ("R",), "joint_top"),
    "R>E>I": (("R",), ("E",), ("I",), "ordered_top"),
    "R>I>E": (("R",), ("I",), ("E",), "ordered_top"),
    "E>R>I": (("E",), ("R",), ("I",), "ordered_top"),
    "E>I>R": (("E",), ("I",), ("R",), "ordered_top"),
    "I>R>E": (("I",), ("R",), ("E",), "ordered_top"),
    "I>E>R": (("I",), ("E",), ("R",), "ordered_top"),
    "R=E=I": (("R", "E", "I"), "two_of_three"),
}
PROFILE_IDS = tuple(PROFILE_CONTRACTS)

FIXTURE_NAMES = (
    "job_abroad.json",
    "public_speaking.json",
    "harmful_relationship.json",
    "boundary_violation.json",
    "expensive_purchase.json",
    "creative_project.json",
    "grief_and_work.json",
    "moral_disclosure.json",
    "family_loyalty.json",
    "immediate_physical_danger.json",
    "two_top_minds_conflict.json",
    "all_three_same_spoznanje.json",
)
FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "native_bundles"

PATTERN_OPTIONS = {
    "all_different": {"R": "option_a", "E": "option_b", "I": "option_c"},
    "r_e_agree": {"R": "option_a", "E": "option_a", "I": "option_c"},
    "r_i_agree": {"R": "option_a", "E": "option_b", "I": "option_a"},
    "e_i_agree": {"R": "option_c", "E": "option_a", "I": "option_a"},
    "all_same": {"R": "option_a", "E": "option_a", "I": "option_a"},
}


@dataclass(frozen=True)
class GoldOutcome:
    status: str
    option_id: str | None
    structural_top_minds: tuple[str, ...]
    effective_source_minds: tuple[str, ...]
    spoznanje_status: str
    pair_status: str | None = None


def _gold(
    status: str,
    option_id: str | None,
    top: tuple[str, ...],
    source: tuple[str, ...],
    spoznanje: str,
    pair: str | None = None,
) -> GoldOutcome:
    return GoldOutcome(status, option_id, top, source, spoznanje, pair)


# This is an explicit independent oracle.  It is intentionally not generated
# from the profile parser or resolver under test.
GOLD_65: dict[str, dict[str, GoldOutcome]] = {
    "R>(E=I)": {
        "all_different": _gold("resolved", "option_a", ("R",), ("R",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_a", ("R",), ("R",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_a", ("R",), ("R",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_c", ("R",), ("R",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("R",), ("R",), "simulated_spoznanje"),
    },
    "E>(R=I)": {
        "all_different": _gold("resolved", "option_b", ("E",), ("E",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_a", ("E",), ("E",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_b", ("E",), ("E",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_a", ("E",), ("E",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("E",), ("E",), "simulated_spoznanje"),
    },
    "I>(R=E)": {
        "all_different": _gold("resolved", "option_c", ("I",), ("I",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_c", ("I",), ("I",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_a", ("I",), ("I",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_a", ("I",), ("I",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("I",), ("I",), "simulated_spoznanje"),
    },
    "(R=E)>I": {
        "all_different": _gold("unresolved", None, ("R", "E"), ("R", "E"), "no_spoznanje", "unresolved"),
        "r_e_agree": _gold("resolved", "option_a", ("R", "E"), ("R", "E"), "partial_agreement", "resolved"),
        "r_i_agree": _gold("unresolved", None, ("R", "E"), ("R", "E"), "partial_agreement", "unresolved"),
        "e_i_agree": _gold("unresolved", None, ("R", "E"), ("R", "E"), "partial_agreement", "unresolved"),
        "all_same": _gold("resolved", "option_a", ("R", "E"), ("R", "E"), "simulated_spoznanje", "resolved"),
    },
    "(R=I)>E": {
        "all_different": _gold("unresolved", None, ("R", "I"), ("R", "I"), "no_spoznanje", "unresolved"),
        "r_e_agree": _gold("unresolved", None, ("R", "I"), ("R", "I"), "partial_agreement", "unresolved"),
        "r_i_agree": _gold("resolved", "option_a", ("R", "I"), ("R", "I"), "partial_agreement", "resolved"),
        "e_i_agree": _gold("unresolved", None, ("R", "I"), ("R", "I"), "partial_agreement", "unresolved"),
        "all_same": _gold("resolved", "option_a", ("R", "I"), ("R", "I"), "simulated_spoznanje", "resolved"),
    },
    "(E=I)>R": {
        "all_different": _gold("unresolved", None, ("E", "I"), ("E", "I"), "no_spoznanje", "unresolved"),
        "r_e_agree": _gold("unresolved", None, ("E", "I"), ("E", "I"), "partial_agreement", "unresolved"),
        "r_i_agree": _gold("unresolved", None, ("E", "I"), ("E", "I"), "partial_agreement", "unresolved"),
        "e_i_agree": _gold("resolved", "option_a", ("E", "I"), ("E", "I"), "partial_agreement", "resolved"),
        "all_same": _gold("resolved", "option_a", ("E", "I"), ("E", "I"), "simulated_spoznanje", "resolved"),
    },
    "R>E>I": {
        "all_different": _gold("resolved", "option_a", ("R",), ("R",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_a", ("R",), ("R",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_a", ("R",), ("R",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_c", ("R",), ("R",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("R",), ("R",), "simulated_spoznanje"),
    },
    "R>I>E": {
        "all_different": _gold("resolved", "option_a", ("R",), ("R",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_a", ("R",), ("R",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_a", ("R",), ("R",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_c", ("R",), ("R",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("R",), ("R",), "simulated_spoznanje"),
    },
    "E>R>I": {
        "all_different": _gold("resolved", "option_b", ("E",), ("E",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_a", ("E",), ("E",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_b", ("E",), ("E",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_a", ("E",), ("E",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("E",), ("E",), "simulated_spoznanje"),
    },
    "E>I>R": {
        "all_different": _gold("resolved", "option_b", ("E",), ("E",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_a", ("E",), ("E",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_b", ("E",), ("E",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_a", ("E",), ("E",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("E",), ("E",), "simulated_spoznanje"),
    },
    "I>R>E": {
        "all_different": _gold("resolved", "option_c", ("I",), ("I",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_c", ("I",), ("I",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_a", ("I",), ("I",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_a", ("I",), ("I",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("I",), ("I",), "simulated_spoznanje"),
    },
    "I>E>R": {
        "all_different": _gold("resolved", "option_c", ("I",), ("I",), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_c", ("I",), ("I",), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_a", ("I",), ("I",), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_a", ("I",), ("I",), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("I",), ("I",), "simulated_spoznanje"),
    },
    "R=E=I": {
        "all_different": _gold("unresolved", None, ("R", "E", "I"), ("R", "E", "I"), "no_spoznanje"),
        "r_e_agree": _gold("resolved", "option_a", ("R", "E", "I"), ("R", "E"), "partial_agreement"),
        "r_i_agree": _gold("resolved", "option_a", ("R", "E", "I"), ("R", "I"), "partial_agreement"),
        "e_i_agree": _gold("resolved", "option_a", ("R", "E", "I"), ("E", "I"), "partial_agreement"),
        "all_same": _gold("resolved", "option_a", ("R", "E", "I"), ("R", "E", "I"), "simulated_spoznanje"),
    },
}

GOLD_CASES = tuple(
    (profile_id, pattern_id, GOLD_65[profile_id][pattern_id])
    for profile_id, pattern_id in product(PROFILE_IDS, PATTERN_OPTIONS)
)


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_all_13_profiles_parse_to_the_exact_canonical_contract(profile_id: str) -> None:
    parsed = parse_character_profile(profile_id)
    *expected_tiers, expected_rule = PROFILE_CONTRACTS[profile_id]

    assert parsed.profile_id == profile_id
    assert parsed.authority_tiers == tuple(expected_tiers)
    assert parsed.rule == expected_rule
    assert parse_character_profile(profile_id) == parsed


@pytest.mark.parametrize(
    "malformed",
    (
        "",
        "R",
        "R>E",
        "R>E>R",
        "r>e>i",
        " R>E>I",
        "R>E>I ",
        "R = E = I",
        "R=I>E",
        "R=E>I",
        "R>E=I",
        "(R=E=I)",
        "R>(E>I)",
        "(R=E)>I>R",
        "R=E=I=R",
    ),
)
def test_profile_parser_rejects_noncanonical_or_malformed_notation(malformed: str) -> None:
    with pytest.raises((TypeError, ValueError, ValidationError)):
        parse_character_profile(malformed)


def test_profile_parser_preserves_an_explicit_character_id() -> None:
    parsed = parse_character_profile("R>E>I", character_id="character_explicit")

    assert parsed.character_id == "character_explicit"


@pytest.mark.parametrize(
    ("profile_id", "pattern_id", "gold"),
    GOLD_CASES,
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_explicit_65_cell_governance_truth_table(
    profile_id: str,
    pattern_id: str,
    gold: GoldOutcome,
) -> None:
    bundle = make_native_bundle(PATTERN_OPTIONS[pattern_id])
    structural = parse_character_profile(profile_id)

    resolution = resolve_governance(bundle, structural)

    assert resolution.mandate.status == gold.status
    assert resolution.mandate.option_id == gold.option_id
    assert resolution.structural_top_minds == gold.structural_top_minds
    assert resolution.effective_source_minds == gold.effective_source_minds
    assert resolution.agreement_pattern.spoznanje_status == gold.spoznanje_status
    if gold.pair_status is None:
        assert resolution.pair_conflict is None
    else:
        assert resolution.pair_conflict is not None
        assert resolution.pair_conflict.status == gold.pair_status


def test_the_explicit_gold_table_has_exactly_65_unique_cells() -> None:
    assert len(GOLD_CASES) == 65
    assert len({(profile_id, pattern_id) for profile_id, pattern_id, _ in GOLD_CASES}) == 65


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_all_three_same_is_simulated_spoznanje_for_every_profile(
    profile_id: str,
) -> None:
    bundle = make_native_bundle(PATTERN_OPTIONS["all_same"])

    resolution = resolve_governance(bundle, parse_character_profile(profile_id))

    assert resolution.agreement_pattern.agreement_kind == "unanimous"
    assert resolution.spoznanje_status == "simulated_spoznanje"
    assert resolution.agreement_pattern.agreeing_minds == ("R", "E", "I")


@pytest.mark.parametrize(
    ("options", "expected_kind", "expected_spoznanje"),
    (
        (PATTERN_OPTIONS["r_e_agree"], "majority", "partial_agreement"),
        (PATTERN_OPTIONS["r_i_agree"], "majority", "partial_agreement"),
        (PATTERN_OPTIONS["e_i_agree"], "majority", "partial_agreement"),
        (PATTERN_OPTIONS["all_different"], "all_different", "no_spoznanje"),
    ),
)
def test_spoznanje_classification_is_profile_independent(
    options: dict[str, str],
    expected_kind: str,
    expected_spoznanje: str,
) -> None:
    bundle = make_native_bundle(options)
    statuses = set()

    for profile_id in PROFILE_IDS:
        resolution = resolve_governance(bundle, parse_character_profile(profile_id))
        assert resolution.agreement_pattern.agreement_kind == expected_kind
        statuses.add(resolution.spoznanje_status)

    assert statuses == {expected_spoznanje}


@pytest.mark.parametrize(
    "options",
    (
        {"R": "option_a", "E": "option_b", "I": "option_a"},
        {"R": "option_a", "E": "option_b", "I": "option_b"},
    ),
)
def test_subordinate_never_tiebreaks_a_disagreeing_joint_top_pair(
    options: dict[str, str],
) -> None:
    structural = parse_character_profile("(R=E)>I")

    resolution = resolve_governance(make_native_bundle(options), structural)

    assert resolution.pair_conflict is not None
    assert resolution.pair_conflict.top_minds == ("R", "E")
    assert resolution.pair_conflict.status == "unresolved"
    assert resolution.mandate.status == "unresolved"
    assert resolution.mandate.option_id is None


def test_racio_has_no_extra_vote_in_joint_top_conflict_or_two_of_three() -> None:
    bundle = make_native_bundle(
        {"R": "option_b", "E": "option_b", "I": "option_c"}
    )

    joint = resolve_governance(bundle, parse_character_profile("(E=I)>R"))
    equal = resolve_governance(bundle, parse_character_profile("R=E=I"))

    assert joint.pair_conflict is not None
    assert joint.pair_conflict.status == "unresolved"
    assert joint.mandate.option_id is None
    assert equal.mandate.option_id == "option_b"
    assert equal.effective_source_minds == ("R", "E")


@pytest.mark.parametrize(
    ("profile_id", "options", "expected_option", "expected_status"),
    (
        (
            "R>E>I",
            {"R": "option_a", "E": "option_b", "I": "option_c"},
            "option_a",
            "resolved",
        ),
        (
            "(R=E)>I",
            {"R": "option_a", "E": "option_b", "I": "option_a"},
            None,
            "unresolved",
        ),
        (
            "R=E=I",
            {"R": "option_c", "E": "option_a", "I": "option_a"},
            "option_a",
            "resolved",
        ),
    ),
)
def test_confidence_and_intensity_never_change_ordinal_governance(
    profile_id: str,
    options: dict[str, str],
    expected_option: str | None,
    expected_status: str,
) -> None:
    low_racio = make_native_bundle(
        options,
        racio_confidence=0.0,
        emocio_intensity=1.0,
        instinkt_intensity=1.0,
    )
    high_racio = make_native_bundle(
        options,
        racio_confidence=1.0,
        emocio_intensity=0.0,
        instinkt_intensity=0.0,
    )
    structural = parse_character_profile(profile_id)

    low_resolution = resolve_governance(low_racio, structural)
    high_resolution = resolve_governance(high_racio, structural)

    for resolution in (low_resolution, high_resolution):
        assert resolution.mandate.status == expected_status
        assert resolution.mandate.option_id == expected_option
        assert resolution.mandate.structural_source_minds == (
            low_resolution.mandate.structural_source_minds
        )
    assert low_resolution.structural_top_minds == high_resolution.structural_top_minds
    assert low_resolution.effective_source_minds == high_resolution.effective_source_minds
    assert low_resolution.agreement_pattern.agreement_kind == (
        high_resolution.agreement_pattern.agreement_kind
    )


def test_explicit_functional_override_changes_effective_not_structural_authority() -> None:
    structural = parse_character_profile("R>E>I")
    original_tiers = structural.authority_tiers
    override = make_functional_override(
        structural,
        ("R",),
        unavailable_score=0.95,
    )
    effective = derive_effective_authority(structural, override)
    bundle = make_native_bundle(PATTERN_OPTIONS["all_different"])

    resolution = resolve_governance(
        bundle,
        structural,
        functional_override=override,
    )

    assert structural.authority_tiers == original_tiers == (("R",), ("E",), ("I",))
    assert effective.structural_profile == structural
    assert effective.effective_tiers == (("E",), ("I",))
    assert resolution.structural_top_minds == ("R",)
    assert resolution.effective_source_minds == ("E",)
    assert resolution.mandate.status == "functionally_overridden"
    assert resolution.mandate.option_id == "option_b"
    assert resolution.effective_authority_id == effective.effective_authority_id


def test_availability_score_is_never_inferred_as_an_override_threshold() -> None:
    structural = parse_character_profile("R>E>I")
    no_override = derive_effective_authority(structural)
    explicitly_removed_despite_high_score = derive_effective_authority(
        structural,
        make_functional_override(
            structural,
            ("R",),
            unavailable_score=0.95,
        ),
    )

    assert no_override.effective_tiers == structural.authority_tiers
    assert no_override.functional_override is None
    assert explicitly_removed_despite_high_score.effective_tiers == (("E",), ("I",))


def test_all_processors_unavailable_is_explicitly_unresolvable() -> None:
    structural = parse_character_profile("R=E=I")
    override = make_functional_override(structural, ("R", "E", "I"))
    effective = derive_effective_authority(structural, override)

    assert effective.effective_tiers == ()
    with pytest.raises(ValueError, match="every mind is unavailable"):
        resolve_governance(
            make_native_bundle(PATTERN_OPTIONS["all_same"]),
            structural,
            functional_override=override,
        )


@pytest.mark.parametrize(
    (
        "profile_id",
        "unavailable_minds",
        "expected_effective_tiers",
        "expected_source_minds",
        "expected_status",
        "expected_option",
        "expected_pair_status",
    ),
    (
        (
            "R>(E=I)",
            ("R",),
            (("E", "I"),),
            ("E", "I"),
            "unresolved",
            None,
            "unresolved",
        ),
        (
            "(R=E)>I",
            ("R",),
            (("E",), ("I",)),
            ("E",),
            "functionally_overridden",
            "option_b",
            None,
        ),
        (
            "R=E=I",
            ("R",),
            (("E", "I"),),
            ("E", "I"),
            "unresolved",
            None,
            "unresolved",
        ),
        (
            "R=E=I",
            ("R", "E"),
            (("I",),),
            ("I",),
            "functionally_overridden",
            "option_c",
            None,
        ),
        (
            "R>E>I",
            ("I",),
            (("R",), ("E",)),
            ("R",),
            "functionally_overridden",
            "option_a",
            None,
        ),
    ),
)
def test_functional_override_projects_every_effective_top_tier_shape_without_mutation(
    profile_id: str,
    unavailable_minds: tuple[str, ...],
    expected_effective_tiers: tuple[tuple[str, ...], ...],
    expected_source_minds: tuple[str, ...],
    expected_status: str,
    expected_option: str | None,
    expected_pair_status: str | None,
) -> None:
    structural = parse_character_profile(profile_id)
    structural_tiers_before = structural.authority_tiers
    override = make_functional_override(structural, unavailable_minds)
    effective = derive_effective_authority(structural, override)

    resolution = resolve_governance(
        make_native_bundle(PATTERN_OPTIONS["all_different"]),
        structural,
        functional_override=override,
    )

    assert structural.authority_tiers == structural_tiers_before
    assert effective.structural_profile == structural
    assert effective.effective_tiers == expected_effective_tiers
    assert resolution.structural_top_minds == structural_tiers_before[0]
    assert resolution.effective_source_minds == expected_source_minds
    assert resolution.mandate.status == expected_status
    assert resolution.mandate.option_id == expected_option
    assert resolution.effective_authority_id == effective.effective_authority_id
    if expected_pair_status is None:
        assert resolution.pair_conflict is None
    else:
        assert resolution.pair_conflict is not None
        assert resolution.pair_conflict.status == expected_pair_status


def test_valid_delegation_preserves_structural_and_effective_tiers() -> None:
    structural = parse_character_profile("R>E>I")
    effective_before = derive_effective_authority(structural)
    delegation = TaskDelegation(
        delegation_id="delegation_resolved_top_to_second",
        delegating_minds=("R",),
        delegate_mind="E",
        task="Execute the already selected option.",
        option_id="option_a",
        rationale="Explicit operational handoff.",
    )

    resolution = resolve_governance(
        make_native_bundle(PATTERN_OPTIONS["r_e_agree"]),
        structural,
        delegation=delegation,
    )

    assert resolution.mandate.status == "delegated"
    assert resolution.mandate.option_id == "option_a"
    assert resolution.mandate.delegation == delegation
    assert resolution.structural_top_minds == ("R",)
    assert resolution.effective_source_minds == ("R",)
    assert structural.authority_tiers == (("R",), ("E",), ("I",))
    assert resolution.effective_authority_id == effective_before.effective_authority_id


def test_explicit_delegation_can_preserve_an_unresolved_pair_without_tiebreaking() -> None:
    structural = parse_character_profile("(R=E)>I")
    delegation = TaskDelegation(
        delegation_id="delegation_unresolved_pair_to_subordinate",
        delegating_minds=("R", "E"),
        delegate_mind="I",
        task="Collect one further operational observation.",
        option_id="option_c",
        rationale="The pair remains structurally unresolved.",
    )

    resolution = resolve_governance(
        make_native_bundle(PATTERN_OPTIONS["all_different"]),
        structural,
        delegation=delegation,
    )

    assert resolution.pair_conflict is not None
    assert resolution.pair_conflict.status == "unresolved"
    assert resolution.mandate.status == "delegated"
    assert resolution.mandate.option_id == "option_c"
    assert resolution.structural_top_minds == ("R", "E")
    assert resolution.effective_source_minds == ("R", "E")
    assert structural.authority_tiers == (("R", "E"), ("I",))


@pytest.mark.parametrize(
    "delegation",
    (
        TaskDelegation(
            delegation_id="delegation_wrong_source",
            delegating_minds=("E",),
            delegate_mind="I",
            task="Invalid source handoff.",
        ),
        TaskDelegation(
            delegation_id="delegation_replaces_resolved_option",
            delegating_minds=("R",),
            delegate_mind="E",
            task="Invalid replacement with the delegate's different option.",
            option_id="option_b",
        ),
        TaskDelegation(
            delegation_id="delegation_uses_non_delegate_option",
            delegating_minds=("R",),
            delegate_mind="E",
            task="Invalid option not held by the delegate.",
            option_id="option_c",
        ),
    ),
)
def test_invalid_delegation_cannot_replace_authority_or_selected_option(
    delegation: TaskDelegation,
) -> None:
    with pytest.raises(ValueError):
        resolve_governance(
            make_native_bundle(PATTERN_OPTIONS["all_different"]),
            parse_character_profile("R>E>I"),
            delegation=delegation,
        )


def test_delegation_with_correct_source_still_requires_an_explicit_option() -> None:
    delegation = TaskDelegation(
        delegation_id="delegation_missing_explicit_option",
        delegating_minds=("R",),
        delegate_mind="E",
        task="Missing operational option.",
    )

    with pytest.raises(ValueError, match="requires an explicit option"):
        resolve_governance(
            make_native_bundle(PATTERN_OPTIONS["r_e_agree"]),
            parse_character_profile("R>E>I"),
            delegation=delegation,
        )


def test_delegation_with_correct_source_rejects_an_out_of_bundle_option() -> None:
    delegation = TaskDelegation(
        delegation_id="delegation_outside_bundle_scope",
        delegating_minds=("R",),
        delegate_mind="E",
        task="Attempt an out-of-scope option.",
        option_id="option_outside_bundle",
    )

    with pytest.raises(ValueError, match="inside the native bundle scope"):
        resolve_governance(
            make_native_bundle(PATTERN_OPTIONS["r_e_agree"]),
            parse_character_profile("R>E>I"),
            delegation=delegation,
        )


def test_delegation_and_functional_override_cannot_be_conflated() -> None:
    structural = parse_character_profile("R>E>I")
    override = make_functional_override(structural, ("R",))
    delegation = TaskDelegation(
        delegation_id="delegation_during_override",
        delegating_minds=("E",),
        delegate_mind="I",
        task="Invalid conflation.",
    )

    with pytest.raises(ValueError, match="cannot share one resolution"):
        resolve_governance(
            make_native_bundle(PATTERN_OPTIONS["all_different"]),
            structural,
            functional_override=override,
            delegation=delegation,
        )


def _pair_options(
    r_option: str,
    e_option: str,
) -> tuple[MindOption, MindOption]:
    return (
        MindOption(mind="R", option_id=r_option),
        MindOption(mind="E", option_id=e_option),
    )


def test_pair_conflict_model_rejects_a_round_after_pair_convergence() -> None:
    round_one = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_a"),
        new_information_ids=("pair_converged_here",),
    )
    forbidden_round_two = PairNegotiationRound.create(
        round_number=2,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_a"),
        new_rollout_ids=("pair_should_already_have_stopped",),
    )

    with pytest.raises(ValidationError, match="stop once the top pair agrees"):
        PairConflict(
            pair_conflict_id="invalid_history_after_convergence",
            top_minds=("R", "E"),
            initial_option_by_mind=_pair_options("option_a", "option_b"),
            option_by_mind=_pair_options("option_a", "option_a"),
            status="resolved",
            negotiation_rounds=2,
            negotiation_history=(round_one, forbidden_round_two),
        )


def test_governance_resolution_rejects_unrelated_or_option_mismatched_resolved_pair() -> None:
    resolution = resolve_governance(
        make_native_bundle(PATTERN_OPTIONS["r_e_agree"]),
        parse_character_profile("(R=E)>I"),
    )
    unrelated_top_pair = PairConflict(
        pair_conflict_id="unrelated_resolved_pair",
        top_minds=("R", "I"),
        option_by_mind=(
            MindOption(mind="R", option_id="option_a"),
            MindOption(mind="I", option_id="option_a"),
        ),
        status="resolved",
    )
    mismatched_option_pair = PairConflict(
        pair_conflict_id="option_mismatched_resolved_pair",
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_b", "option_b"),
        status="resolved",
    )

    unrelated = resolution.model_copy(update={"pair_conflict": unrelated_top_pair})
    with pytest.raises(ValidationError, match="top minds must equal"):
        type(resolution).model_validate_json(unrelated.model_dump_json())

    option_mismatched = resolution.model_copy(
        update={"pair_conflict": mismatched_option_pair}
    )
    with pytest.raises(ValidationError, match="option must equal the mandate option"):
        type(resolution).model_validate_json(option_mismatched.model_dump_json())


def test_bounded_pair_negotiation_records_provenance_and_can_converge() -> None:
    round_one = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_information_ids=("new_information_1",),
    )
    round_two = PairNegotiationRound.create(
        round_number=2,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_a"),
        new_rollout_ids=("new_rollout_2",),
    )

    resolution = resolve_governance(
        make_native_bundle(PATTERN_OPTIONS["all_different"]),
        parse_character_profile("(R=E)>I"),
        negotiation_rounds=(round_one, round_two),
    )

    assert resolution.pair_conflict is not None
    assert resolution.pair_conflict.status == "resolved"
    assert resolution.pair_conflict.negotiation_rounds == 2
    assert resolution.pair_conflict.negotiation_history == (round_one, round_two)
    assert resolution.pair_conflict.initial_option_by_mind == _pair_options(
        "option_a", "option_b"
    )
    assert resolution.mandate.status == "resolved"
    assert resolution.mandate.option_id == "option_a"


def test_negotiation_round_ids_are_deterministic_and_rounds_are_frozen() -> None:
    first = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_information_ids=("new_information_1",),
    )
    replay = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_information_ids=("new_information_1",),
    )

    assert replay == first
    assert replay.round_id == first.round_id
    with pytest.raises(ValidationError):
        first.round_number = 2  # type: ignore[misc]


def test_pair_negotiation_is_capped_at_two_information_bearing_rounds() -> None:
    with pytest.raises(ValidationError):
        PairNegotiationRound.create(
            round_number=3,
            top_minds=("R", "E"),
            option_by_mind=_pair_options("option_a", "option_b"),
            new_information_ids=("new_information_3",),
        )
    with pytest.raises(ValidationError, match="requires new information or rollout"):
        PairNegotiationRound.create(
            round_number=1,
            top_minds=("R", "E"),
            option_by_mind=_pair_options("option_a", "option_b"),
        )


def test_pair_negotiation_is_rejected_for_a_single_top_profile() -> None:
    round_one = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_information_ids=("single_top_irrelevant_information",),
    )

    with pytest.raises(ValueError, match="only for an equal top pair"):
        resolve_governance(
            make_native_bundle(PATTERN_OPTIONS["all_different"]),
            parse_character_profile("R>E>I"),
            negotiation_rounds=(round_one,),
        )


def test_pair_negotiation_cannot_replace_the_thirteenth_profile_two_of_three_rule() -> None:
    round_one = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_information_ids=("thirteenth_profile_irrelevant_information",),
    )

    with pytest.raises(ValueError, match="cannot replace the two-of-three rule"):
        resolve_governance(
            make_native_bundle(PATTERN_OPTIONS["r_e_agree"]),
            parse_character_profile("R=E=I"),
            negotiation_rounds=(round_one,),
        )


def test_incomplete_joint_top_pair_cannot_enter_option_negotiation() -> None:
    round_one = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_information_ids=("incomplete_pair_irrelevant_information",),
    )

    with pytest.raises(ValueError, match="incomplete top pair"):
        resolve_governance(
            make_native_bundle({"R": None, "E": "option_a", "I": "option_b"}),
            parse_character_profile("(R=E)>I"),
            negotiation_rounds=(round_one,),
        )


def test_pair_negotiation_rejects_reused_or_noncontiguous_provenance() -> None:
    round_one = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_information_ids=("same_provenance",),
    )
    repeated_provenance = PairNegotiationRound.create(
        round_number=2,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_rollout_ids=("same_provenance",),
    )
    starts_at_two = PairNegotiationRound.create(
        round_number=2,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_b"),
        new_information_ids=("new_information_2",),
    )
    bundle = make_native_bundle(PATTERN_OPTIONS["all_different"])
    structural = parse_character_profile("(R=E)>I")

    with pytest.raises(ValueError, match="new provenance"):
        resolve_governance(
            bundle,
            structural,
            negotiation_rounds=(round_one, repeated_provenance),
        )
    with pytest.raises(ValueError, match="contiguous from one"):
        resolve_governance(bundle, structural, negotiation_rounds=(starts_at_two,))


def test_negotiation_stops_immediately_after_pair_convergence() -> None:
    converged = PairNegotiationRound.create(
        round_number=1,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_a"),
        new_information_ids=("converging_information",),
    )
    forbidden_extra_round = PairNegotiationRound.create(
        round_number=2,
        top_minds=("R", "E"),
        option_by_mind=_pair_options("option_a", "option_a"),
        new_rollout_ids=("unnecessary_rollout",),
    )

    with pytest.raises(ValueError, match="stop once the top pair agrees"):
        resolve_governance(
            make_native_bundle(PATTERN_OPTIONS["all_different"]),
            parse_character_profile("(R=E)>I"),
            negotiation_rounds=(converged, forbidden_extra_round),
        )


@pytest.mark.parametrize(
    ("profile_id", "options"),
    (
        ("R>E>I", {"R": None, "E": "option_a", "I": "option_a"}),
        ("(R=E)>I", {"R": None, "E": "option_a", "I": "option_a"}),
        ("R=E=I", {"R": None, "E": "option_a", "I": "option_a"}),
        ("R=E=I", {"R": None, "E": None, "I": None}),
    ),
)
def test_abstention_is_unknown_and_never_becomes_a_vote_or_unavailability(
    profile_id: str,
    options: dict[str, str | None],
) -> None:
    structural = parse_character_profile(profile_id)

    resolution = resolve_governance(make_native_bundle(options), structural)

    assert resolution.agreement_pattern.agreement_kind == "incomplete"
    assert resolution.spoznanje_status == "unknown"
    assert resolution.agreement_pattern.winning_option_id is None
    assert resolution.agreement_pattern.agreeing_minds == ()
    assert resolution.mandate.status == "unresolved"
    assert resolution.mandate.option_id is None
    assert resolution.effective_authority_id == derive_effective_authority(
        structural
    ).effective_authority_id


def test_resolution_replay_ids_hash_and_json_are_deterministic() -> None:
    bundle = make_native_bundle(PATTERN_OPTIONS["r_e_agree"])
    structural = parse_character_profile("R=E=I")

    first = resolve_governance(bundle, structural)
    replay = resolve_governance(bundle, structural)
    restored = type(first).model_validate_json(first.model_dump_json())

    assert replay == first
    assert replay.resolution_id == first.resolution_id
    assert replay.resolution_hash == first.resolution_hash
    assert replay.agreement_pattern.agreement_pattern_id == (
        first.agreement_pattern.agreement_pattern_id
    )
    assert replay.agreement_pattern.agreement_hash == first.agreement_pattern.agreement_hash
    assert restored == first
    with pytest.raises(ValidationError):
        first.resolution_id = "tampered"  # type: ignore[misc]


def test_exact_canonical_fixture_inventory_is_checked_in() -> None:
    actual_names = tuple(sorted(path.name for path in FIXTURE_ROOT.glob("*.json")))

    assert actual_names == tuple(sorted(FIXTURE_NAMES))


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_canonical_fixture_closes_native_lineage_and_gold_contract(
    fixture_name: str,
) -> None:
    fixture = load_governance_fixture(FIXTURE_ROOT / fixture_name)

    fixture.native_bundle.validate_native_lineage(
        scene=fixture.scene,
        racio_packet=fixture.racio_packet,
        emocio_packet=fixture.emocio_packet,
        instinkt_packet=fixture.instinkt_packet,
        emocio_visual_state=fixture.emocio_visual_state,
        instinkt_body_state=fixture.instinkt_body_state,
        instinkt_rollouts=fixture.instinkt_rollouts,
    )
    assert tuple(item.profile_id for item in fixture.expected_profile_outcomes) == PROFILE_IDS
    assert len(fixture.expected_profile_outcomes) == 13
    assert tuple(item.mind for item in fixture.expected_native_reasons) == (
        "R",
        "E",
        "I",
    )
    assert len({item.reason for item in fixture.expected_native_reasons}) == 3
    assert fixture.open_question_ids
    assert all(question_id.startswith("OQ-") for question_id in fixture.open_question_ids)
    assert fixture.expected_spoznanje == (
        fixture.expected_spoznanje_status == "simulated_spoznanje"
    )


FIXTURE_MATRIX_CASES = tuple(product(FIXTURE_NAMES, PROFILE_IDS))


@pytest.mark.parametrize(
    ("fixture_name", "profile_id"),
    FIXTURE_MATRIX_CASES,
)
def test_exact_12_by_13_canonical_fixture_matrix(
    fixture_name: str,
    profile_id: str,
) -> None:
    fixture = load_governance_fixture(FIXTURE_ROOT / fixture_name)
    expected_by_profile = {
        item.profile_id: item for item in fixture.expected_profile_outcomes
    }
    expected = expected_by_profile[profile_id]
    bundle_id_before = fixture.native_bundle.bundle_id
    bundle_hash_before = fixture.native_bundle.immutable_hash

    resolution = resolve_governance(
        fixture.native_bundle,
        parse_character_profile(profile_id),
    )

    assert resolution.mandate.status == expected.status
    assert resolution.mandate.option_id == expected.option_id
    assert resolution.effective_source_minds == expected.source_minds
    assert resolution.spoznanje_status == fixture.expected_spoznanje_status
    assert resolution.native_bundle_id == bundle_id_before
    assert resolution.native_bundle_hash == bundle_hash_before
    assert fixture.native_bundle.bundle_id == bundle_id_before
    assert fixture.native_bundle.immutable_hash == bundle_hash_before
    if expected.pair_status is None:
        assert resolution.pair_conflict is None
    else:
        assert resolution.pair_conflict is not None
        assert resolution.pair_conflict.status == expected.pair_status


def test_fixture_matrix_has_exactly_156_unique_cells() -> None:
    assert len(FIXTURE_MATRIX_CASES) == 156
    assert len(set(FIXTURE_MATRIX_CASES)) == 156
