"""Wave 1 must be 20 source-bound editorial pages and zero merchant activations."""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path("examples/retail/data")
FRONT = Path("examples/retail/storefront-web")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_wave1_release_candidate_exactly_matches_source_bound_review() -> None:
    packet = _json(DATA / "dufynd_facts_wave_01_review.json")["profiles"]
    generated = _json(FRONT / "lib/generated/released-profiles.json")["profiles"]
    staged = {
        row["product_id"]: row
        for row in _json(DATA / "scentai_catalog_staging.json")["products"]
    }
    assert len(generated) == len(packet) == 20
    assert [row["product_id"] for row in generated] == [row["product_id"] for row in packet]
    assert len({row["slug"] for row in generated}) == 20

    for row, original in zip(generated, packet, strict=True):
        for field in (
            "product_id",
            "slug",
            "brand",
            "name",
            "concentration",
            "volume_ml",
            "summary_de",
            "editorial_description_de",
            "notes",
            "seo",
        ):
            assert row[field] == original[field]
        assert row["target_groups"] == staged[row["product_id"]]["classification"]["target_groups"]
        assert row["indexing_approved"] is False


def test_wave1_public_candidate_has_no_offer_price_image_or_tracking() -> None:
    generated = _json(FRONT / "lib/generated/released-profiles.json")["profiles"]
    forbidden = {
        "price",
        "shipping_cost",
        "in_stock",
        "affiliate_url",
        "product_url",
        "image_url",
        "original_photo",
        "merchant_id",
        "commission_rate",
    }
    for row in generated:
        assert not forbidden.intersection(row.keys())
        assert row["indexing_approved"] is False
        assert row["seo"]["public_path"] == "/duft/" + row["slug"]
        assert row["notes"]


def test_public_pages_use_documented_descriptions_and_consistent_home_counts() -> None:
    detail = (FRONT / "components/FragranceDetailPage.tsx").read_text(encoding="utf-8")
    qualified = (FRONT / "components/QualifiedProductPage.tsx").read_text(encoding="utf-8")
    catalog = (FRONT / "lib/releasedProfileCatalog.ts").read_text(encoding="utf-8")
    home = (FRONT / "components/views/HomeView.tsx").read_text(encoding="utf-8")
    assert "editorialDescription={released.editorial_description_de}" in detail
    assert "publicMode && editorialDescription ? editorialDescription : fact.summary_de" in qualified
    assert "f.editorial_description_de||f.summary_de" in catalog
    assert "target_groups:f.target_groups||[]" in catalog
    assert "const scentCount = LIVE_FRAGRANCES.length;" in home
    assert "const audienceCounts = LIVE_FRAGRANCES.reduce(" in home


def test_only_review_waves_41_and_first_twenty_is_runtime_candidate() -> None:
    first = _json(DATA / "dufynd_facts_wave_01_review.json")["profiles"]
    second = _json(DATA / "dufynd_facts_wave_02_review.json")["profiles"]
    active = _json(FRONT / "lib/generated/released-profiles.json")["profiles"]
    assert len(first) + len(second) == 41
    assert not set(row["product_id"] for row in first).intersection(
        row["product_id"] for row in second
    )
    assert set(row["product_id"] for row in active) == {
        row["product_id"] for row in first
    }
