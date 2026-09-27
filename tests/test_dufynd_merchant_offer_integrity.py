"""Protect committed DUFYND merchant offers from structural data drift."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

OFFERS = Path("examples/retail/data/merchant_offers.json")
SOURCE = Path("examples/retail/data/scentai_products.json")
STAGING = Path("examples/retail/data/scentai_catalog_staging.json")


def _offers() -> list[dict]:
    return json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]


def _valid_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname)


def test_offer_ids_are_unique_and_products_are_known() -> None:
    offers = _offers()
    live = json.loads(SOURCE.read_text(encoding="utf-8"))["products"]
    staged = json.loads(STAGING.read_text(encoding="utf-8"))["products"]
    known_ids = {row["product_id"] for row in live} | {row["product_id"] for row in staged}

    offer_ids = [row["offer_id"] for row in offers]
    assert len(offer_ids) == len(set(offer_ids))

    unknown = sorted(
        {row["product_id"] for row in offers if row["product_id"] not in known_ids}
    )
    assert not unknown, f"merchant offers reference unknown products: {unknown}"


def test_offer_commerce_fields_are_valid() -> None:
    for offer in _offers():
        offer_id = offer["offer_id"]

        assert float(offer["price"]) > 0, offer_id
        assert str(offer["currency"]).strip().upper() == "EUR", offer_id
        assert _valid_https_url(str(offer["product_url"])), offer_id

        affiliate_url = str(offer.get("affiliate_url") or "").strip()
        if affiliate_url:
            assert _valid_https_url(affiliate_url), offer_id


def test_offer_freshness_timestamps_are_parseable() -> None:
    for offer in _offers():
        value = str(offer["last_updated_at"]).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)

        assert parsed.tzinfo is not None, offer["offer_id"]
