"""Prevent Widian London commerce activation while concentration is unresolved."""

from __future__ import annotations

import json
from pathlib import Path

PRODUCTS = Path("examples/retail/data/scentai_products.json")
CATALOG = Path("examples/retail/data/catalog.json")
OFFERS = Path("examples/retail/data/merchant_offers.json")

PRODUCT_ID = "SC-WIDIAN-LONDON-EXTRAIT-50"


def test_widian_london_live_identity_is_consistent_inside_dufynd() -> None:
    source = json.loads(PRODUCTS.read_text(encoding="utf-8"))["products"]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["products"]

    source_row = next(row for row in source if row["product_id"] == PRODUCT_ID)
    catalog_row = next(row for row in catalog if row["product_id"] == PRODUCT_ID)

    assert source_row["concentration"] == "Extrait de Parfum"
    assert source_row["volume_ml"] == 50
    assert catalog_row["attributes"]["concentration"] == "Extrait de Parfum"
    assert catalog_row["attributes"]["volume_ml"] == "50"


def test_widian_london_offer_stays_blocked_until_identity_review() -> None:
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]

    assert all(row["product_id"] != PRODUCT_ID for row in offers)
