from __future__ import annotations


def test_slovenian_is_canonical_and_english_is_only_an_operational_gloss(
    families, family_fixtures
):
    for family in families:
        assert family["canonical_input_sl"].strip()
        assert family["sl_paraphrase"].strip()
        assert family["title_sl"].strip()
        assert family["operational_gloss_en"].strip()
        assert family["grounded_scene"]["language"] == "sl"
        assert all(
            locator["excerpt_summary_sl"].strip()
            for locator in family["source_locators"]
        )

        variants = {
            variant["mode"]: variant
            for variant in family_fixtures[family["family_id"]]["variants"]
        }
        assert variants["sl_canonical"]["language"] == "sl"
        assert variants["sl_canonical"]["input_text"] == family["canonical_input_sl"]
        assert variants["sl_paraphrase"]["language"] == "sl"
        assert variants["sl_paraphrase"]["input_text"] == family["sl_paraphrase"]
        assert variants["en_operational_gloss"]["language"] == "en"
        assert variants["en_operational_gloss"]["input_text"] == family[
            "operational_gloss_en"
        ]
