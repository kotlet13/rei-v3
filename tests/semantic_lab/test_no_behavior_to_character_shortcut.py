from __future__ import annotations


FORBIDDEN_PROFILE_KEYS = {
    "authority_tier",
    "authority_tiers",
    "character_profile",
    "expected_character",
    "profile_id",
    "profile_weight",
}


def _keys(value):
    if isinstance(value, dict):
        yield from value
        for nested in value.values():
            yield from _keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _keys(nested)


def test_behavior_never_maps_directly_to_character(families, family_fixtures):
    for family in families:
        assert "behavior_to_character" in family["forbidden_shortcuts"]
        assert not (set(_keys(family)) & FORBIDDEN_PROFILE_KEYS)
        fixture = family_fixtures[family["family_id"]]
        assert not (set(_keys(fixture)) & FORBIDDEN_PROFILE_KEYS)


def test_same_behavior_keeps_three_distinct_native_routes(family_fixtures):
    fixture = family_fixtures["sf_same_behavior_three_routes"]
    for variant in fixture["variants"]:
        routes = variant["expected_routes"]
        assert {route["mind"] for route in routes} == {"R", "E", "I"}
        assert {route["option_id"] for route in routes} == {"option_leave"}
        assert len({route["decisive_representation"] for route in routes}) == 3


def test_same_route_survives_a_surface_behavior_change(family_fixtures):
    fixture = family_fixtures["sf_same_route_different_behavior"]
    variants = {variant["mode"]: variant for variant in fixture["variants"]}
    canonical = variants["sl_canonical"]["expected_routes"]
    perturbed = variants["same_route_different_behavior"]

    assert perturbed["perturbation"]["kind"] == "same_route_different_behavior"
    assert [route["mind"] for route in perturbed["expected_routes"]] == [
        route["mind"] for route in canonical
    ]
    assert [route["route_tags"] for route in perturbed["expected_routes"]] == [
        route["route_tags"] for route in canonical
    ]
