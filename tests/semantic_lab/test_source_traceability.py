from __future__ import annotations

from scripts.build_semantic_lab_fixtures import expected_outputs

from .conftest import REPO_ROOT, SOURCE_ROOT, read_jsonl


def test_every_family_locator_resolves_to_the_canonical_claim_registry(families):
    canonical_claims = {
        item["claim_id"]: item
        for item in read_jsonl(REPO_ROOT / "knowledge" / "canon_v2" / "claims.jsonl")
    }
    source_index = {
        item["claim_id"]: item
        for item in read_jsonl(SOURCE_ROOT / "source_index.jsonl")
    }
    used_claim_ids: set[str] = set()

    for family in families:
        for locator in family["source_locators"]:
            assert (REPO_ROOT / locator["source_file"]).is_file()
            for claim_id in locator["claim_ids"]:
                used_claim_ids.add(claim_id)
                assert claim_id in canonical_claims
                assert claim_id in source_index
                assert canonical_claims[claim_id]["source_file"] == locator["source_file"]
                assert canonical_claims[claim_id]["source_page"] == locator["page"]
                assert source_index[claim_id]["source_file"] == locator["source_file"]

    assert used_claim_ids == set(source_index)
    assert len(used_claim_ids) == 28


def test_every_family_has_a_non_model_canon_approval(families):
    reviews = read_jsonl(SOURCE_ROOT / "review" / "review_log.jsonl")
    by_family = {review["family_id"]: review for review in reviews}

    assert set(by_family) == {family["family_id"] for family in families}
    assert all(review["status"] == "canon_approved" for review in reviews)
    assert all(review["model_generated"] is False for review in reviews)

    # Running the canonical validator exercises claim, page, file, evidence,
    # review and route-reference checks together.
    outputs = expected_outputs(source_root=SOURCE_ROOT, repo_root=REPO_ROOT)
    assert len(outputs) == 25
