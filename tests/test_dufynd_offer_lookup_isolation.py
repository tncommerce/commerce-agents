"""An unrelated merchant evidence outage must not delay another purchase path."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from retail.api import purchase_freshness
from retail.api.merchant_offers import MerchantOfferStore

DATA = Path("examples/retail/data/merchant_offers.json")


def offer_row(offer_id):
    return next(r for r in json.loads(DATA.read_text())["offers"] if r["offer_id"] == offer_id)


def verified_at(row):
    return datetime.fromisoformat(row["last_updated_at"].replace("Z", "+00:00"))


@pytest.mark.parametrize(
    "lookup,identity",
    [
        ("product", "SC-YSL-LIBRE-EDP-90"),
        ("offer", "notino-ysl-libre-edp-90"),
        ("product", "missing-product"),
        ("offer", "missing-offer"),
    ],
)
def test_unrelated_evidence_is_not_requested(monkeypatch, lookup, identity):
    requested = []

    def evidence(offer_id):
        requested.append(offer_id)
        if offer_id == purchase_freshness.TARGET_OFFER:
            raise AssertionError("unrelated network dependency reached")
        return None

    monkeypatch.setattr(purchase_freshness, "evidence_for", evidence)
    store = MerchantOfferStore(DATA)
    # Isolation is independent of a legitimate later source-data refresh.
    now = verified_at(offer_row("notino-ysl-libre-edp-90")) + timedelta(hours=1)
    if lookup == "product":
        result = store.offers_for(identity, now=now)
        assert all(offer.product_id == identity for offer in result)
    else:
        result = store.eligible_offer(identity, now=now)
        assert result is None or result.offer_id == identity
    assert bool(result) == (not identity.startswith("missing"))
    if identity.startswith("missing"):
        assert requested == []


@pytest.mark.parametrize("lookup", ["product", "offer"])
def test_requested_negative_evidence_still_blocks_offer(monkeypatch, lookup):
    row = offer_row(purchase_freshness.TARGET_OFFER)
    now = verified_at(row) + timedelta(hours=1)
    store = MerchantOfferStore(DATA)
    monkeypatch.setattr(purchase_freshness, "evidence_for", lambda _: None)
    assert store.eligible_offer(row["offer_id"], now=now) is not None
    requested = []

    def evidence(offer_id):
        requested.append(offer_id)
        return {
            "source": "certified_purchase_verification",
            "max_age_hours": 72,
            "offer_contract": {k: v for k, v in row.items() if k != "last_updated_at"},
            "decision": "transport_unverified",
        }

    monkeypatch.setattr(purchase_freshness, "evidence_for", evidence)
    result = (
        store.offers_for(row["product_id"], now=now)
        if lookup == "product"
        else store.eligible_offer(row["offer_id"], now=now)
    )
    assert not result
    assert purchase_freshness.TARGET_OFFER in requested


def test_selected_offer_keeps_variant_price_and_expiry(monkeypatch):
    monkeypatch.setattr(purchase_freshness, "evidence_for", lambda _: None)
    store = MerchantOfferStore(DATA)
    now = verified_at(offer_row("notino-ysl-libre-edp-90")) + timedelta(hours=1)
    offers = store.offers_for("SC-YSL-LIBRE-EDP-90", now=now)
    offer = store.eligible_offer("notino-ysl-libre-edp-90", now=now)
    assert offers == [offer]
    assert offer.price == 132
    assert offer.variant_label == "90 ml · Eau de Parfum · nachfüllbarer Flakon"
    expired = offer.last_updated_at + timedelta(hours=72, seconds=1)
    assert store.offers_for(offer.product_id, now=expired) == []
    assert store.eligible_offer(offer.offer_id, now=expired) is None
