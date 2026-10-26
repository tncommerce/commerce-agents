from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from examples.retail.api.merchant_offers import (
    MerchantOfferStore,
    customer_offer_payload,
    offer_clickout_target,
)

PACKET = Path("artifacts/dufynd-libre-recovery-20261026")
OFFERS = Path("examples/retail/data/merchant_offers.json")


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def test_libre_static_refresh_is_bound_to_real_observation_and_original_identity() -> None:
    source = read(PACKET / "source-observation.json")
    before = read(PACKET / "canonical-before.json")["canonical_offer"]
    integration = read(PACKET / "development-integration.json")
    actual = next(x for x in read(OFFERS)["offers"] if x["offer_id"] == before["offer_id"])
    assert actual == {**before, "last_updated_at": source["observed_at"]}
    assert source["selected_variant"]["price_eur"] == actual["price"] == 130
    assert source["selected_variant"]["shipping_cost_eur"] == actual["shipping_cost"] == 0
    assert source["selected_variant"]["gtin13"] == "3614272648425"
    assert source["selected_variant"]["volume_ml"] == 90
    assert integration["changed_fields"] == ["last_updated_at"]
    assert (
        integration["source_observation_sha256"]
        == hashlib.sha256((PACKET / "source-observation.json").read_bytes()).hexdigest()
    )


def test_libre_normal_static_payload_is_130_eur_and_expires_without_database(monkeypatch) -> None:
    monkeypatch.delenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", raising=False)
    source = read(PACKET / "source-observation.json")
    checked = datetime.fromisoformat(source["observed_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(source["expires_at"])
    store = MerchantOfferStore(OFFERS)
    offer = next(
        x
        for x in store.offers_for(source["product_id"], now=checked)
        if x.offer_id == source["offer_id"]
    )
    payload = customer_offer_payload(offer)
    assert payload["price"] == payload["total_price"] == 130
    assert payload["shipping_cost"] == 0 and payload["in_stock"] is True
    assert payload["variant_label"] == "90 ml · Eau de Parfum · nachfüllbarer Flakon"
    assert (
        offer_clickout_target(offer)
        == read(PACKET / "canonical-before.json")["canonical_offer"]["affiliate_url"]
    )
    assert store.eligible_offer(offer.offer_id, now=expires) is not None
    assert store.eligible_offer(offer.offer_id, now=expires + timedelta(milliseconds=1)) is None
