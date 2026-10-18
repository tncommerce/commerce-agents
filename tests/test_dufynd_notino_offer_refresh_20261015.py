"""The verified Notino wave restores exact offers without relaxing freshness."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from retail.api.merchant_offers import (
    MerchantOfferStore,
    customer_offer_payload,
    offer_clickout_target,
)

DATA = Path("examples/retail/data")
EVIDENCE = json.loads((DATA / "dufynd_notino_offer_refresh_20261015.json").read_text())
# Immutable copy of the three offers as actually approved on 15 October.
# The mutable live catalog may have later, valid evidence; historical clock tests
# must never travel into the future relative to their original observation.
HISTORICAL_OFFERS = Path("tests/fixtures/dufynd_notino_offer_refresh_20261015.json")
REFRESHED_20261018 = {
    "notino-pdm-delina-edp-75": "2026-10-18T09:38:01.133371+00:00",
    "notino-ysl-black-opium-edp-90": "2026-10-18T09:38:01.134527+00:00",
    "notino-ysl-libre-edp-90": "2026-10-18T09:38:01.135135+00:00",
}


@pytest.mark.parametrize("verified", EVIDENCE["products"], ids=lambda row: row["offer_id"])
def test_exact_notino_offer_is_eligible_then_expires(verified: dict) -> None:
    store = MerchantOfferStore(HISTORICAL_OFFERS)
    observed = datetime.fromisoformat(EVIDENCE["observed_at"].replace("Z", "+00:00"))
    expiry = datetime.fromisoformat(EVIDENCE["expires_at"].replace("Z", "+00:00"))

    offers = store.offers_for(verified["product_id"], now=observed)
    assert [offer.offer_id for offer in offers] == [verified["offer_id"]]
    offer = offers[0]
    public = customer_offer_payload(offer)
    assert public["merchant_product_id"] == verified["merchant_product_id"]
    assert public["price"] == verified["price_eur"]
    assert public["shipping_cost"] == verified["shipping_cost_eur"]
    assert public["in_stock"] is True
    assert public["affiliate_link"] is True

    # Construct and inspect locally: never visit a tracking or clickout URL.
    target = urlparse(offer_clickout_target(offer))
    assert target.netloc == "www.jdoqocy.com"
    assert target.path == "/click-101884613-12260695"
    assert parse_qs(target.query)["url"] == [verified["source_url"]]
    assert store.eligible_offer(offer.offer_id, now=expiry) is not None
    assert store.eligible_offer(offer.offer_id, now=expiry + timedelta(seconds=1)) is None
    assert store.offers_for(offer.product_id, now=expiry + timedelta(seconds=1)) == []


@pytest.mark.parametrize("verified", EVIDENCE["products"], ids=lambda row: row["offer_id"])
def test_october_18_refresh_preserves_exact_offers_and_freshness(verified: dict) -> None:
    """Match Work47's original read-only HTTP evidence without weakening age guards."""
    historical = json.loads(HISTORICAL_OFFERS.read_text(encoding="utf-8"))["offers"]
    current = json.loads((DATA / "merchant_offers.json").read_text(encoding="utf-8"))["offers"]
    old = [row for row in historical if row["offer_id"] == verified["offer_id"]]
    new = [row for row in current if row["offer_id"] == verified["offer_id"]]
    assert len(old) == len(new) == 1

    # Timestamp-only approval: variant, merchant ID, price, stock, shipping,
    # affiliate tracking destination and all other fields are unchanged.
    assert new[0] == {
        **old[0],
        "last_updated_at": REFRESHED_20261018[verified["offer_id"]],
    }
    assert new[0]["product_url"] == verified["source_url"]
    assert new[0]["merchant_product_id"] == verified["merchant_product_id"]

    checked = datetime.fromisoformat(REFRESHED_20261018[verified["offer_id"]])
    store = MerchantOfferStore(DATA / "merchant_offers.json")
    assert store.eligible_offer(verified["offer_id"], now=checked - timedelta(minutes=6)) is None
    assert [offer.offer_id for offer in store.offers_for(verified["product_id"], now=checked)] == [
        verified["offer_id"]
    ]
    assert store.eligible_offer(verified["offer_id"], now=checked + timedelta(hours=72)) is not None
    assert store.eligible_offer(
        verified["offer_id"], now=checked + timedelta(hours=72, seconds=1)
    ) is None
