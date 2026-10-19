"""Current primary Notino observations update only exact price and conservative freshness.

Offline acceptance: no affiliate clickouts, external requests or synthetic purchases.
The 15/18 October evidence remains historical and immutable.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from retail.api.merchant_offers import MerchantOfferStore, customer_offer_payload, offer_clickout_target

DATA = Path("examples/retail/data")
EVIDENCE = json.loads((DATA / "dufynd_notino_offer_refresh_20261019.json").read_text(encoding="utf-8"))
PREVIOUS = json.loads(Path("tests/fixtures/dufynd_notino_offer_refresh_20261018.json").read_text(encoding="utf-8"))["offers"]
CURRENT = json.loads((DATA / "merchant_offers.json").read_text(encoding="utf-8"))["offers"]


@pytest.mark.parametrize("proof", EVIDENCE["products"], ids=lambda row: row["offer_id"])
def test_exact_variant_price_and_cj_contract_are_grounded(proof: dict) -> None:
    old = [row for row in PREVIOUS if row["offer_id"] == proof["offer_id"]]
    new = [row for row in CURRENT if row["offer_id"] == proof["offer_id"]]
    assert len(old) == len(new) == 1
    before, after = old[0], new[0]
    assert before["price"] == proof["prior_price_eur"]
    assert after == {
        **before,
        "price": proof["price_eur"],
        "last_updated_at": EVIDENCE["freshness_at"],
    }
    assert proof["source_url"] == after["product_url"]
    assert proof["merchant_product_id"] == after["merchant_product_id"]
    assert proof["variant_label"] == after["variant_label"]
    assert proof["availability_observed"] is True
    assert after["shipping_cost"] == proof["shipping_cost_eur"] == 0
    assert after["in_stock"] is True
    assert proof["affiliate_url_unchanged"] is True
    assert before["affiliate_url"] == after["affiliate_url"]

    # Parse local URL only; never follow the merchant or CJ click redirect.
    target = urlparse(offer_clickout_target(MerchantOfferStore(DATA / "merchant_offers.json").eligible_offer(
        proof["offer_id"],
        now=datetime.fromisoformat(EVIDENCE["freshness_at"].replace("Z", "+00:00")),
    )))
    assert target.hostname == "www.jdoqocy.com"
    assert target.path == "/click-101884613-12260695"
    assert parse_qs(target.query)["url"] == [proof["source_url"]]


@pytest.mark.parametrize("proof", EVIDENCE["products"], ids=lambda row: row["offer_id"])
def test_exact_72_hour_eligibility_with_conservative_date(proof: dict) -> None:
    verified = datetime.fromisoformat(EVIDENCE["freshness_at"].replace("Z", "+00:00"))
    expiry = datetime.fromisoformat(EVIDENCE["expires_at"].replace("Z", "+00:00"))
    assert verified.tzinfo == UTC
    assert expiry - verified == timedelta(hours=72)
    store = MerchantOfferStore(DATA / "merchant_offers.json")
    assert store.eligible_offer(proof["offer_id"], now=verified - timedelta(minutes=6)) is None
    eligible = store.eligible_offer(proof["offer_id"], now=verified)
    assert eligible is not None
    displayed = customer_offer_payload(eligible)
    assert displayed["price"] == proof["price_eur"]
    assert displayed["total_price"] == proof["price_eur"]
    assert displayed["in_stock"] is True
    assert store.eligible_offer(proof["offer_id"], now=expiry) is not None
    assert store.eligible_offer(proof["offer_id"], now=expiry + timedelta(microseconds=1)) is None
    assert store.offers_for(proof["product_id"], now=expiry + timedelta(seconds=1)) == []


def test_observation_scope_has_only_three_preapproved_skus() -> None:
    approved = {
        "notino-pdm-delina-edp-75": ("PDM0227", 285),
        "notino-ysl-black-opium-edp-90": ("YSL2377", 116),
        "notino-ysl-libre-edp-90": ("VZR11010", 130),
    }
    assert {row["offer_id"]: (row["merchant_product_id"], row["price_eur"]) for row in EVIDENCE["products"]} == approved
    assert set(row["offer_id"] for row in EVIDENCE["products"]) == set(row["offer_id"] for row in PREVIOUS)
    assert EVIDENCE["source_freshness_date"] == "2026-10-19"
    assert EVIDENCE["freshness_at"] == "2026-10-19T00:00:00Z"
    assert EVIDENCE["safeguards"]["cj_tracking_links_unchanged"] is True
    assert EVIDENCE["safeguards"]["no_clickouts"] is True
