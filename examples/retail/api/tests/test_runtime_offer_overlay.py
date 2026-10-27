"""No live network/merchant calls: exact-identity commerce snapshot contract."""

import json
from datetime import UTC, datetime, timedelta

from retail.api.runtime_offer_overlay import (
    accept_snapshot,
    contract_fingerprint,
    runtime_snapshot,
)

NOW = datetime(2026, 10, 24, 8, tzinfo=UTC)
ROW = {
    "offer_id": "notino-ysl-libre-edp-90",
    "product_id": "SC-YSL-LIBRE-EDP-90",
    "merchant_id": "notino",
    "merchant_product_id": "VZR11010",
    "variant_label": "90 ml · Eau de Parfum · nachfüllbarer Flakon",
    "product_url": "https://www.notino.de/yves-saint-laurent/test/",
    "affiliate_url": "https://www.jdoqocy.com/click-101884613-12260695?url=test",
    "network": "CJ Affiliate",
    "currency": "EUR",
    "price": 130.0,
    "shipping_cost": 0.0,
    "shipping_label": "Gratis",
    "in_stock": True,
    "last_updated_at": "2026-10-20T19:53:43.753Z",
}


def receipt(**updates):
    fields = {
        "offer_id": ROW["offer_id"],
        "identity_sha256": contract_fingerprint(ROW),
        "verification_method": "certified_merchant_observation",
        "source_url": ROW["product_url"],
        "evidence_reference": "merchant-read-2026-10-24-123",
        "currency": "EUR",
        "price": 128.5,
        "shipping_cost": 0,
        "shipping_label": "Gratis",
        "in_stock": True,
        "verified_at": "2026-10-24T07:00:00Z",
    }
    return fields | updates


def test_exact_trusted_receipt_replaces_only_volatile_fields():
    result = accept_snapshot(ROW, receipt(), now=NOW)
    assert result is not None
    assert result["price"] == 128.5
    assert result["last_updated_at"] == "2026-10-24T07:00:00+00:00"
    for key in (
        "offer_id",
        "product_id",
        "merchant_id",
        "merchant_product_id",
        "variant_label",
        "product_url",
        "affiliate_url",
        "network",
    ):
        assert result[key] == ROW[key]


def test_unverified_wrong_identity_or_old_price_never_revives():
    failures = (
        {"offer_id": "notino-other"},
        {"identity_sha256": "0" * 64},
        {"verification_method": "unverified"},
        {"source_url": "https://www.notino.de/another"},
        {"evidence_reference": ""},
        {"verified_at": (NOW - timedelta(hours=73)).isoformat()},
        {"verified_at": (NOW + timedelta(hours=1)).isoformat()},
    )
    for mismatch in failures:
        assert accept_snapshot(ROW, receipt(**mismatch), now=NOW) is None


def test_invalid_price_shipping_stock_and_currency_fail_closed():
    for field, bad in (
        ("price", -1),
        ("price", True),
        ("price", "130"),
        ("shipping_cost", -1),
        ("shipping_cost", True),
        ("in_stock", "yes"),
        ("currency", "USD"),
    ):
        assert accept_snapshot(ROW, receipt(**{field: bad}), now=NOW) is None


def test_default_runtime_reader_never_accesses_network(monkeypatch):
    monkeypatch.delenv("DUFYND_RUNTIME_OFFERS_ENABLED", raising=False)
    assert runtime_snapshot(ROW["offer_id"]) is None
    monkeypatch.setenv("DUFYND_RUNTIME_OFFERS_ENABLED", "1")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert runtime_snapshot(ROW["offer_id"]) is None


def test_store_accepts_certified_snapshot_after_static_expiry(tmp_path, monkeypatch):
    """A new verified price can replace an expired Git price, but never bypass gates."""
    from retail.api import purchase_freshness, runtime_offer_overlay
    from retail.api.merchant_offers import MerchantOfferStore

    now = datetime.now(UTC)
    row = ROW | {
        "merchant_name": "NOTINO.de",
        "last_updated_at": (now - timedelta(hours=80)).isoformat(),
    }
    fixture_path = tmp_path / "merchant_offers.json"
    fixture_path.write_text(json.dumps({"offers": [row]}), encoding="utf-8")
    store = MerchantOfferStore(fixture_path)

    # Neither merchant pages nor Supabase nor affiliate redirect routes are called.
    monkeypatch.setattr(purchase_freshness, "evidence_for", lambda _offer_id: None)
    monkeypatch.setattr(runtime_offer_overlay, "runtime_snapshot", lambda _offer_id: None)
    assert store.offers_for(row["product_id"], now=now) == []
    assert store.eligible_offer(row["offer_id"], now=now) is None

    verified = receipt(
        identity_sha256=contract_fingerprint(row),
        verified_at=(now - timedelta(minutes=3)).isoformat(),
    )
    monkeypatch.setattr(runtime_offer_overlay, "runtime_snapshot", lambda _offer_id: verified)
    eligible = store.offers_for(row["product_id"], now=now)
    assert len(eligible) == 1
    assert eligible[0].price == 128.5
    assert eligible[0].shipping_cost == 0
    assert eligible[0].affiliate_url == row["affiliate_url"]
    assert eligible[0].merchant_product_id == row["merchant_product_id"]
    assert eligible[0].product_url == row["product_url"]
    assert store.eligible_offer(row["offer_id"], now=now) is not None

    for invalid in (
        verified | {"identity_sha256": "0" * 64},
        verified | {"verified_at": (now - timedelta(hours=73)).isoformat()},
        verified | {"in_stock": False},
    ):
        monkeypatch.setattr(
            runtime_offer_overlay, "runtime_snapshot", lambda _offer_id, value=invalid: value
        )
        assert store.offers_for(row["product_id"], now=now) == []
        assert store.eligible_offer(row["offer_id"], now=now) is None
