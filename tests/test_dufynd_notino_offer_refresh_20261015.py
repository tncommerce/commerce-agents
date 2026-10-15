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


@pytest.mark.parametrize("verified", EVIDENCE["products"], ids=lambda row: row["offer_id"])
def test_exact_notino_offer_is_eligible_then_expires(verified: dict) -> None:
    store = MerchantOfferStore(DATA / "merchant_offers.json")
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
