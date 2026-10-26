"""Fresh primary observations preserve the three existing paths and age guards."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from retail.api.merchant_offers import (
    MerchantOffer,
    MerchantOfferStore,
    customer_offer_payload,
    offer_clickout_target,
)

DATA = Path("examples/retail/data")
EVIDENCE = json.loads((DATA / "dufynd_notino_offer_refresh_20261020.json").read_text())
PREVIOUS = json.loads(Path("tests/fixtures/dufynd_notino_offer_refresh_20261019.json").read_text())
LIBRE_REFRESH = json.loads(
    Path("artifacts/dufynd-libre-recovery-20261026/source-observation.json").read_text()
)


@pytest.mark.parametrize("verified", EVIDENCE["products"], ids=lambda row: row["offer_id"])
def test_current_observation_preserves_exact_path_and_72_hour_boundary(verified):
    before = next(row for row in PREVIOUS["offers"] if row["offer_id"] == verified["offer_id"])
    current = next(
        row
        for row in json.loads((DATA / "merchant_offers.json").read_text())["offers"]
        if row["offer_id"] == verified["offer_id"]
    )
    expected = {
        **before,
        "price": verified["price_eur"],
        "last_updated_at": verified["observed_at"],
    }
    observed_at, expires_at = verified["observed_at"], verified["expires_at"]
    if verified["offer_id"] == LIBRE_REFRESH["offer_id"]:
        # Only Libre has a newer recorded observation. Keep the historical
        # identity, route and price contract; age from the actual source time.
        selected = LIBRE_REFRESH["selected_variant"]
        assert LIBRE_REFRESH["product_id"] == verified["product_id"]
        assert LIBRE_REFRESH["visible_merchant_product_id"] == verified["merchant_product_id"]
        assert LIBRE_REFRESH["source_url"] == verified["product_url"]
        assert selected["volume_ml"] == verified["selected_volume_ml"] == 90
        assert selected["gtin13"] == "3614272648425"
        assert selected["presentation"] == verified["presentation"]
        assert selected["price_eur"] == verified["price_eur"]
        assert selected["shipping_cost_eur"] == verified["shipping_cost_eur"]
        assert selected["in_stock"] is True
        observed_at, expires_at = LIBRE_REFRESH["observed_at"], LIBRE_REFRESH["expires_at"]
        expected["last_updated_at"] = observed_at
    assert current == expected
    assert current["product_id"] == verified["product_id"]
    assert current["merchant_product_id"] == verified["merchant_product_id"]
    assert current["product_url"] == verified["product_url"]
    assert verified["availability_label"] == "Verfügbar"
    assert verified["order_button_enabled"] is True
    assert verified["delivery_country"] == "DE"
    assert verified["presentation"] != "refill"
    checked = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    assert expiry - checked == timedelta(hours=72)
    store = MerchantOfferStore(DATA / "merchant_offers.json")
    offer = store.eligible_offer(verified["offer_id"], now=checked)
    assert offer is not None
    assert store.offers_for(verified["product_id"], now=checked) == [offer]
    public = customer_offer_payload(offer)
    assert public["price"] == verified["price_eur"]
    assert public["shipping_cost"] == verified["shipping_cost_eur"] == 0
    assert public["total_price"] == verified["total_price_eur"] == verified["price_eur"]
    target = urlsplit(offer_clickout_target(offer))
    assert target.hostname == "www.jdoqocy.com"
    assert target.path == "/click-101884613-12260695"
    assert parse_qs(target.query)["url"] == [verified["product_url"]]
    assert store.eligible_offer(offer.offer_id, now=checked - timedelta(minutes=6)) is None
    assert store.eligible_offer(offer.offer_id, now=expiry) is not None
    assert store.eligible_offer(offer.offer_id, now=expiry + timedelta(seconds=1)) is None
    assert store.offers_for(offer.product_id, now=expiry + timedelta(seconds=1)) == []


@pytest.mark.parametrize("verified", EVIDENCE["products"], ids=lambda row: row["offer_id"])
@pytest.mark.parametrize(
    "invalid", ["out_of_stock", "currency", "wrong_product", "missing_timestamp"]
)
def test_invalid_offer_cannot_supply_the_requested_product(tmp_path, verified, invalid):
    row = next(dict(row) for row in PREVIOUS["offers"] if row["offer_id"] == verified["offer_id"])
    row["last_updated_at"] = verified["observed_at"]
    checked = datetime.fromisoformat(verified["observed_at"].replace("Z", "+00:00"))
    if invalid == "out_of_stock":
        row["in_stock"] = False
    elif invalid == "currency":
        row["currency"] = "USD"
    elif invalid == "wrong_product":
        row["product_id"] = "SC-SYNTHETIC-WRONG-PRODUCT"
    else:
        del row["last_updated_at"]
    fixture = tmp_path / "invalid-offer.json"
    fixture.write_text(json.dumps({"offers": [row]}))
    store = MerchantOfferStore(fixture)
    if invalid == "missing_timestamp":
        # The source contract remains invalid; the store now rejects the
        # complete malformed catalog instead of leaking a buyer-facing 500.
        with pytest.raises(ValidationError):
            MerchantOffer.model_validate(row)
        assert store.eligible_offer(verified["offer_id"], now=checked) is None
    assert store.offers_for(verified["product_id"], now=checked) == []
