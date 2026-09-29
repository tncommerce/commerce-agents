from __future__ import annotations

import json
from pathlib import Path

DATA = Path("examples/retail/data")
STAGING = DATA / "scentai_catalog_staging.json"
MAPPINGS = DATA / "merchant_product_mappings.json"
OFFERS = DATA / "merchant_offers.json"

PRODUCT_ID = "SC-RABANNE-1-MILLION-EDT-100"
GTIN = "3349666007921"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_1_million_staging_matches_verified_commerce_state() -> None:
    staging = load(STAGING)
    rows = staging.get("products") or staging.get("items") or staging.get("candidates") or []
    product = next(row for row in rows if row["product_id"] == PRODUCT_ID)

    assert product["commerce"]["market_status"] == "verified_current_purchase_destination"
    assert product["commerce"]["live_offer_status"] == "verified_current_purchase_destination"
    assert product["media"]["image_url"] == (
        "/products/rabanne-1-million-edt-100-user-contentmaster.webp"
    )
    assert product["media"]["image_status"] == "approved_licensed_image"
    assert product["validation"]["catalog_ready"] is True
    assert product["validation"]["blockers"] == []


def test_1_million_verified_mapping_and_offers_support_staging_state() -> None:
    mappings_payload = load(MAPPINGS)
    mappings = mappings_payload.get("mappings") or mappings_payload.get("items") or mappings_payload
    mapped = [row for row in mappings if row["product_id"] == PRODUCT_ID]

    assert any(
        row.get("merchant") == "perfumetrader"
        and row.get("merchant_product_id") == "16978322"
        and (row.get("gtin") == GTIN or row.get("ean") == GTIN)
        and row.get("mapping_status") == "verified_current_variant"
        for row in mapped
    )

    offers_payload = load(OFFERS)
    offers = offers_payload.get("offers") or offers_payload.get("items") or offers_payload
    current = [row for row in offers if row["product_id"] == PRODUCT_ID and row.get("in_stock")]

    assert any(row.get("merchant_id") == "mueller-de" for row in current)
    assert any(
        row.get("merchant_id") == "perfumetrader"
        and row.get("merchant_product_id") == "16978322"
        and row.get("affiliate_url")
        for row in current
    )
