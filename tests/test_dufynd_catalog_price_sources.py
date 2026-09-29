"""Keep DUFYND live-card prices labelled by their actual source."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("examples/retail/data/catalog.json")
PRODUCT_TILE = Path("examples/retail/storefront-web/components/ProductTile.tsx")

ALLOWED_SOURCES = {"market_reference", "current_merchant_offer"}


def test_every_live_dufynd_price_has_an_explicit_source() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    fragrances = [
        row
        for row in catalog["products"]
        if str(row.get("product_id", "")).startswith("SC-")
        and row.get("category") == "fragrance"
        and row.get("in_stock") is not False
    ]

    assert fragrances

    for row in fragrances:
        attributes = row.get("attributes") or {}
        source = attributes.get("price_source")
        assert source in ALLOWED_SOURCES, row["product_id"]

        if source == "market_reference":
            assert float(row["price"]) == float(attributes["market_price_eur"])
            assert str(attributes.get("price_checked_at") or "").strip()


def test_legacy_live_catalog_prices_are_market_references() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    legacy = [
        row
        for row in catalog["products"]
        if str(row.get("product_id", "")).startswith("SC-")
        and row.get("category") == "fragrance"
        and not (row.get("attributes") or {}).get("promotion_source")
    ]

    assert legacy
    assert all(
        (row.get("attributes") or {}).get("price_source") == "market_reference" for row in legacy
    )


def test_product_cards_label_market_reference_prices() -> None:
    source = PRODUCT_TILE.read_text(encoding="utf-8")

    assert 'if (source === "market_reference") return `Richtpreis ${base}`;' in source
    assert 'if (source === "current_merchant_offer") return `ab ${base}`;' in source
