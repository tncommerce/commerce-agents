"""Offline acceptance of the six real 2026-10-26 source observations."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from examples.retail.api.merchant_offers import MerchantOffer, customer_offer_payload, rank_offers
from examples.retail.api.runtime_offer_snapshots import approved_affiliate_route
from scripts.prepare_dufynd_runtime_offer_batch import prepare_batch

PACKET = Path("artifacts/dufynd-top-six-offers-20261026")
DATA = Path("examples/retail/data")
NOW = datetime(2026, 10, 26, 12, 49, tzinfo=UTC)


def read(name: str) -> dict:
    return json.loads((PACKET / name).read_text())


def prepare(now: datetime = NOW) -> list[dict]:
    return prepare_batch(
        read("proposed-offers.json")["offers"],
        read("batch-input.json"),
        now=now,
        partners_payload={"partners": [read("proposed-partner.json")]},
        mappings_payload=read("proposed-mappings.json"),
        catalog_payload=json.loads((DATA / "catalog.json").read_text()),
    )


def test_six_exact_live_browser_variants_match_original_feed_and_customer_payloads() -> None:
    feed = read("current-feed-evidence.json")
    browser = read("merchant-browser-observations.json")["rows"]
    offers = read("proposed-offers.json")["offers"]
    inputs = read("batch-input.json")["offers"]
    assert feed["feed"]["joined"] is True and feed["feed"]["membership_status"] == "active"
    assert len(prepare()) == len(offers) == len(browser) == len(feed["rows"]) == 6
    for index, (offer, observed, raw, item) in enumerate(
        zip(offers, browser, feed["rows"], inputs, strict=True)
    ):
        fields = raw["fields"]
        assert offer["merchant_product_id"] == fields["merchant_product_id"]
        assert offer["affiliate_url"] == fields["aw_deep_link"]
        assert offer["product_url"] == fields["merchant_deep_link"] == observed["url"]
        assert offer["price"] == float(fields["search_price"])
        assert (
            f"Artikelnummer: {offer['merchant_product_id']}\nMenge: {item['volume_ml']} ml\n"
            in observed["main"]
        )
        price = f"{offer['price']:.2f}".replace(".", ",")
        assert any(
            line in {f"{price} €", f"{int(offer['price'])},- €"}
            for line in observed["main"].splitlines()
        )
        assert observed["buyVisible"] is True and observed["buyEnabled"] is True
        assert (
            "Sofort versandfertig." in observed["main"]
            or "Lieferzeit 2-5 Tage." in observed["main"]
        )
        assert offer["last_updated_at"] == observed["checked_at"] != fields["last_updated"]
        assert offer["shipping_cost"] == 0 and offer["price"] >= 49.95
        payload = customer_offer_payload(MerchantOffer.model_validate(offer))
        assert payload["total_price"] == offer["price"] and payload["affiliate_link"]
        if index:
            assert f"Beim Händler {item['volume_ml']} ml auswählen" in payload["variant_label"]
            assert item["evidence"]["exact_initial_landing_verified"] is False
        else:
            assert "auswählen" not in payload["variant_label"]
    shipping = json.dumps(read("shipping-browser-observation.json"), ensure_ascii=False)
    assert "49,95" in shipping and "4,99" in shipping and "Deutschland" in shipping


@pytest.mark.parametrize(
    "changed", ["affiliate_url", "product_url", "merchant_product_id", "product_id"]
)
def test_exact_feed_binding_cannot_route_a_different_product(changed: str) -> None:
    offer = read("proposed-offers.json")["offers"][0]
    offer[changed] = read("proposed-offers.json")["offers"][1][changed]
    assert not approved_affiliate_route(offer, {"partners": [read("proposed-partner.json")]})


@pytest.mark.parametrize(
    "query",
    [
        "p=1&a=3099222&m=31081",
        "p=38332629354&a=1&m=31081",
        "p=38332629354&a=3099222&m=1",
        "p=38332629354&a=3099222&m=31081&x=1",
        "p=38332629354&a=3099222&m=31081&A=1",
    ],
)
def test_wrong_network_binding_or_extra_parameters_fail_closed(query: str) -> None:
    offer = read("proposed-offers.json")["offers"][0]
    offer["affiliate_url"] = "https://www.awin1.com/pclick.php?" + query
    assert not approved_affiliate_route(offer, {"partners": [read("proposed-partner.json")]})


def test_missing_sku_and_duplicate_bindings_cannot_supply_exact_identity() -> None:
    offer = read("proposed-offers.json")["offers"][0]
    partner = read("proposed-partner.json")
    partner["verified_feed_routes"].append(copy.deepcopy(partner["verified_feed_routes"][0]))
    assert not approved_affiliate_route(offer, {"partners": [partner]})
    partner = read("proposed-partner.json")
    offer.pop("merchant_product_id")
    partner["verified_feed_routes"][0].pop("merchant_product_id")
    assert not approved_affiliate_route(offer, {"partners": [partner]})


def test_pending_live_partner_cannot_use_proposed_routes_and_expiry_is_real() -> None:
    actual = json.loads((DATA / "merchant_partners.json").read_text())
    for offer in read("proposed-offers.json")["offers"]:
        assert not approved_affiliate_route(offer, actual)
    with pytest.raises(ValueError, match="expired_or_future_source"):
        prepare(NOW + timedelta(hours=72))


def test_existing_notino_and_perfumetrader_routes_and_lower_rabanne_total_are_preserved() -> None:
    actual = json.loads((DATA / "merchant_offers.json").read_text())["offers"]
    partners = json.loads((DATA / "merchant_partners.json").read_text())
    for oid in ("notino-ysl-libre-edp-90", "perfumetrader-rabanne-1-million-edt-100"):
        assert approved_affiliate_route(next(x for x in actual if x["offer_id"] == oid), partners)
    rabanne = next(x for x in actual if x["offer_id"] == "perfumetrader-rabanne-1-million-edt-100")
    # Ranking-only fixture: this is not a refreshed production observation.
    existing = MerchantOffer.model_validate({**rabanne, "last_updated_at": NOW.isoformat()})
    top = MerchantOffer.model_validate(read("proposed-offers.json")["offers"][1])
    assert rank_offers([top, existing], now=NOW)[0].offer_id == existing.offer_id
