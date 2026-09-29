"""Keep the public DUFYND catalog aligned with the fragrance source of truth."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("examples/retail/data/catalog.json")
SOURCE = Path("examples/retail/data/scentai_products.json")


def _live_catalog_rows() -> list[dict]:
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))["products"]
    return [
        row
        for row in rows
        if str(row.get("product_id") or "").startswith("SC-") and row.get("category") == "fragrance"
    ]


def _source_rows() -> list[dict]:
    return json.loads(SOURCE.read_text(encoding="utf-8"))["products"]


def test_live_catalog_and_fragrance_source_have_identical_product_sets() -> None:
    catalog_ids = {row["product_id"] for row in _live_catalog_rows()}
    source_ids = {row["product_id"] for row in _source_rows()}

    assert catalog_ids == source_ids


def test_live_catalog_identity_matches_fragrance_source() -> None:
    source = {row["product_id"]: row for row in _source_rows()}

    for catalog_row in _live_catalog_rows():
        product_id = catalog_row["product_id"]
        source_row = source[product_id]
        attributes = catalog_row["attributes"]

        assert catalog_row["brand"] == source_row["brand"], product_id
        assert attributes["canonical_name"] == source_row["name"], product_id
        assert attributes["concentration"] == source_row["concentration"], product_id
        assert int(attributes["volume_ml"]) == int(source_row["volume_ml"]), product_id


def test_live_catalog_market_reference_matches_fragrance_source() -> None:
    source = {row["product_id"]: row for row in _source_rows()}

    for catalog_row in _live_catalog_rows():
        product_id = catalog_row["product_id"]
        source_row = source[product_id]
        attributes = catalog_row["attributes"]
        market = source_row["market"]

        assert catalog_row["currency"] == "EUR", product_id
        assert attributes["price_source"] in {
            "market_reference",
            "current_merchant_offer",
        }, product_id
        assert float(catalog_row["price"]) == float(market["market_price_eur"]), product_id
        assert float(attributes["market_price_eur"]) == float(market["market_price_eur"]), (
            product_id
        )
        if attributes["price_source"] == "market_reference":
            assert attributes["price_checked_at"] == market["price_checked_at"], product_id
        else:
            assert attributes["price_checked_at"].split("T", 1)[0] == market["price_checked_at"], (
                product_id
            )
        assert int(catalog_row["review_count"]) == int(source_row["community"]["rating_count"]), (
            product_id
        )
