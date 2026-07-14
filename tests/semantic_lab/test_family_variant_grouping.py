from __future__ import annotations

from scripts.build_semantic_lab_fixtures import VARIANT_MODES


def test_lab_has_twenty_four_families_with_eight_grouped_variants(
    families, family_fixtures, fixture_manifest
):
    assert len(families) == 24
    assert len(family_fixtures) == 24
    assert fixture_manifest["family_count"] == 24
    assert fixture_manifest["variant_count"] == 192

    for family in families:
        assert tuple(family["variant_modes"]) == VARIANT_MODES
        fixture = family_fixtures[family["family_id"]]
        assert fixture["family_id"] == family["family_id"]
        assert len(fixture["variants"]) == 8
        assert {variant["mode"] for variant in fixture["variants"]} == set(
            VARIANT_MODES
        )
        assert all(
            variant["variant_id"].startswith(f"{family['family_id']}__")
            for variant in fixture["variants"]
        )


def test_variant_axes_are_present_in_every_family(families):
    for family in families:
        assert len(family["person_world_variants"]) >= 2
        assert len(family["current_state_variants"]) >= 2
        assert family["acceptance_variants"] == ["accepting", "mixed", "conflicted"]
        assert family["language_variants"] == ["sl", "en"]
