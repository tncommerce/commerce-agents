"""Twenty-plus-twenty-one fact-only batches must remain separate from commerce."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from scripts.build_dufynd_facts_only_waves import (
    DATA,
    WAVE_NAMES,
    build_review_waves,
    editorial_description,
    review_record,
)


def test_two_real_review_waves_exactly_cover_existing_source_pool() -> None:
    waves = build_review_waves()
    assert [wave["profile_count"] for wave in waves] == [20, 21]
    assert {wave["status"] for wave in waves} == {"REVIEW_ONLY_NOT_PUBLISHED"}
    combined = [row for wave in waves for row in wave["profiles"]]
    assert len(combined) == len({row["product_id"] for row in combined}) == 41
    assert len({row["slug"] for row in combined}) == 41
    assert sum(row["notes_display_kind"] == "documented_pyramid" for row in combined) == 22
    assert sum(row["notes_display_kind"] == "documented_notes_only" for row in combined) == 19


def test_all_review_packets_equal_committed_sources_not_generated_in_runtime() -> None:
    for filename, result in zip(WAVE_NAMES, build_review_waves(), strict=True):
        stored = json.loads((DATA / filename).read_text(encoding="utf-8"))
        assert stored == result


def test_no_offer_photo_approval_indexing_or_publication_slips_into_review() -> None:
    forbidden_fields = {
        "price",
        "shipping_cost",
        "stock",
        "affiliate_url",
        "merchant_url",
        "in_stock",
        "commission",
    }
    for wave in build_review_waves():
        assert wave["public_release_authorized"] is False
        assert wave["merchant_offer_activation"] is False
        assert wave["new_public_profiles"] == 0
        assert wave["new_images_published"] is False
        assert wave["prices_or_tracking_links_added"] is False
        for row in wave["profiles"]:
            assert not forbidden_fields & set(row)
            assert row["publication_authorized"] is False
            assert row["indexing_approved"] is False
            assert row["commerce_mode"] == "no_merchant_offer_no_price"
            assert row["visual_mode"] == "neutral_studio_card_no_packshot"
            assert row["identity"]["source_url"].startswith("https://")
            assert row["notes_source_url"].startswith("https://")
            assert len(row["evidence_sha256"]) == 64
            assert len(row["editorial_description_de"]) > len(row["summary_de"])


def _first_existing_source_pair() -> tuple[dict, dict]:
    facts = json.loads((DATA / "dufynd_discovery_qualification.json").read_text())[
        "products"
    ]
    pilots = json.loads((DATA / "dufynd_release_pilots.json").read_text())["pilots"]
    return facts[0], next(row for row in pilots if row["product_id"] == facts[0]["product_id"])


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("fact", "volume_ml", 50),
        ("fact", "name", "Different"),
        ("pilot", "owner_release_approved", True),
        ("fact", "publication_authorized", True),
        ("fact", "summary_de", "Unverified rewritten claim."),
    ],
)
def test_source_or_owner_release_changes_fail_closed(
    target: str, field: str, value: object
) -> None:
    fact, pilot = deepcopy(_first_existing_source_pair())
    if target == "fact":
        fact[field] = value
    else:
        pilot[field] = value
    with pytest.raises(ValueError, match="source_or_owner_gate_not_ready"):
        review_record(fact, pilot)


def test_note_only_records_never_claim_invented_top_heart_base() -> None:
    fact, pilot = _first_existing_source_pair()
    assert fact["notes"].get("key")
    assert not fact["notes"].get("top")
    detail, kind = editorial_description(fact)
    assert kind == "documented_notes_only"
    assert "Kopfnoten:" not in detail
    assert "Duftpyramide" in detail
    assert review_record(fact, pilot)["notes_display_kind"] == kind


def test_review_uses_verified_source_variant_and_canonical_page() -> None:
    fact, pilot = _first_existing_source_pair()
    row = review_record(fact, pilot)
    assert row["volume_ml"] == fact["volume_ml"]
    assert row["concentration"] == fact["concentration"]
    assert row["slug"] == pilot["slug"]
    assert row["seo"]["public_path"] == f"/duft/{pilot['slug']}"
    assert row["facts_checked_at"] == fact["checked_at"]
    assert row["summary_de"] == fact["summary_de"]
