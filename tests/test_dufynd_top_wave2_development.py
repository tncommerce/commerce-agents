"""Offline source-to-buyer checks for four additive official Top feed routes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from examples.retail.api import purchase_freshness, runtime_offer_snapshots
from examples.retail.api.merchant_offers import (
    MerchantOfferStore,
    customer_offer_payload,
    offer_clickout_target,
)
from examples.retail.api.runtime_offer_snapshots import approved_affiliate_route
from scripts.prepare_dufynd_runtime_offer_batch import (
    prepare_batch,
    restore_direct_merchant_browser_evidence,
)

DATA = Path("examples/retail/data")
PACKET = Path("artifacts/dufynd-top-wave2-offers-20261026")
NOW = datetime(2026, 10, 26, 15, 25, tzinfo=UTC)
EXACT = {
    "SC-MONTBLANC-EXPLORER-100": ("849457", "3386460101035", 113),
    "SC-CREED-AVENTUS-100": ("827407", "3508441001114", 354),
    "SC-PRADA-LHOMME-100": ("815682", "8435137749607", 117.95),
    "SC-XERJOFF-NAXOS-100": ("836129", "8033488155070", 242),
}


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_four_real_browser_observations_are_bound_to_original_feed_and_gtin_sources() -> None:
    feed = read(PACKET / "current-feed-evidence.json")
    browser = read(PACKET / "merchant-browser-observations.json")
    observations = {r["product_id"]: r for r in browser["observations"]}
    source_rows = {r["merchant_product_id"]: r for r in feed["rows"]}
    identities = {
        r["product_id"]: r for r in read(PACKET / "identifier-corroboration.json")["products"]
    }
    offers = read(PACKET / "proposed-offers.json")["offers"]
    evidence = read(PACKET / "batch-input.json")["offers"]
    assert len(offers) == len(evidence) == len(source_rows) == 4
    assert {r["product_id"] for r in offers} == set(EXACT)
    assert feed["feed"]["joined"] is True and feed["feed"]["membership_status"] == "active"
    for offer, item in zip(offers, evidence, strict=True):
        pid = offer["product_id"]
        sku, gtin, price = EXACT[pid]
        observed = observations[pid]
        raw = source_rows[sku]
        fields = raw["fields"]
        assert offer["merchant_product_id"] == sku == observed["merchant_product_id"]
        assert item["ean"] == identities[pid]["gtin"] == gtin
        assert observed["volume_ml"] == item["volume_ml"] == identities[pid]["volume_ml"] == 100
        assert (
            observed["concentration"] == item["concentration"] == identities[pid]["concentration"]
        )
        assert offer["price"] == observed["price"] == float(fields["search_price"]) == price
        assert offer["shipping_cost"] == 0 and price >= 49.95
        assert observed["purchase_button_visible"] and observed["purchase_button_enabled"]
        assert offer["in_stock"] is True and observed["in_stock"] is True
        assert offer["affiliate_url"] == fields["aw_deep_link"]
        assert offer["product_url"] == fields["merchant_deep_link"] == observed["url"]
        assert offer["last_updated_at"] == item["verified_at"] == observed["checked_at"]
        assert offer["last_updated_at"] != fields["last_updated"]
        assert item["evidence"]["source_row_sha256"] == raw["source_row_canonical_json_sha256"]
        assert (
            item["evidence"]["browser_observation_sha256"]
            == hashlib.sha256(
                (PACKET / "merchant-browser-observations.json").read_bytes()
            ).hexdigest()
        )
        if sku == "836129":
            assert offer["variant_label"] == "100 ml · Eau de Parfum · Geschenkbox"
            assert "Gift Box" in fields["product_name"]
        else:
            assert "Beim Händler 100 ml auswählen" in offer["variant_label"]
    assert browser["affiliate_clickouts"] == browser["cart_actions"] == 0


def test_additive_wave_preserves_every_prior_offer_mapping_and_route() -> None:
    proof = read(PACKET / "development-integration.json")
    ids, products = set(proof["offer_ids"]), set(proof["product_ids"])
    assert products == set(EXACT) and len(ids) == 4
    for filename, key in (
        ("merchant_offers.json", "offers"),
        ("merchant_product_mappings.json", "mappings"),
        ("merchant_partners.json", "partners"),
    ):
        rows = read(DATA / filename)[key]
        if key == "offers":
            preserved = [r for r in rows if r["offer_id"] not in ids]
            assert len(rows) == 63 and len(preserved) == 59
        elif key == "mappings":
            preserved = [
                r
                for r in rows
                if not (r["merchant"] == "top-parfuemerie" and r["product_id"] in products)
            ]
            assert len(rows) == 110 and len(preserved) == 106
        else:
            preserved = [r for r in rows if r["merchant_id"] != "top-parfuemerie"]
            top = next(r for r in rows if r["merchant_id"] == "top-parfuemerie")
            assert top["status"] == "active_product_deeplink_only" and top["affiliate_url"] is None
            assert len(top["verified_product_scope"]) == len(top["verified_feed_routes"]) == 10
            old_routes = [r for r in top["verified_feed_routes"] if r["product_id"] not in products]
            assert digest(old_routes) == proof["previous_top_routes_sha256"]
        assert digest(preserved) == proof["preservation"][filename]["preserved_rows_sha256"]


@pytest.mark.parametrize("product_id", list(EXACT))
def test_real_development_store_customer_payload_and_pure_target(product_id, monkeypatch) -> None:
    monkeypatch.delenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", raising=False)
    monkeypatch.setattr(purchase_freshness, "evidence_for", lambda offer_id: None)
    expected = next(
        r for r in read(PACKET / "proposed-offers.json")["offers"] if r["product_id"] == product_id
    )
    store = MerchantOfferStore(DATA / "merchant_offers.json")
    offer = store.eligible_offer(expected["offer_id"], now=NOW)
    assert offer is not None
    payload = customer_offer_payload(offer)
    assert payload["total_price"] == expected["price"]
    assert payload["variant_label"] == expected["variant_label"]
    # Resolve in memory, never make an HTTP request to the target.
    assert offer_clickout_target(offer) == expected["affiliate_url"]
    expired = datetime.fromisoformat(expected["last_updated_at"].replace("Z", "+00:00"))
    expired += timedelta(hours=72, milliseconds=1)
    assert store.eligible_offer(expected["offer_id"], now=expired) is None


def test_existing_batch_validator_accepts_canonical_data_and_rejects_variant_substitution() -> None:
    offers = read(DATA / "merchant_offers.json")["offers"]
    original = read(PACKET / "batch-input.json")
    with pytest.raises(ValueError, match="^source_per_variant_evidence_kind_required$"):
        prepare_batch(offers, original, now=NOW)
    evidence = restore_direct_merchant_browser_evidence(
        offers, original, evidence_dir=PACKET, now=NOW
    )
    assert original == read(PACKET / "batch-input.json")
    assert [row["verified_at"] for row in evidence["offers"]] == [
        row["verified_at"] for row in original["offers"]
    ]
    assert len(prepare_batch(offers, evidence, now=NOW)) == 4
    evidence["offers"][0]["volume_ml"] = 60
    with pytest.raises(ValueError, match="brand_concentration_or_volume_mismatch"):
        prepare_batch(offers, evidence, now=NOW)
    target = read(PACKET / "proposed-offers.json")["offers"][0]
    target["affiliate_url"] = read(PACKET / "proposed-offers.json")["offers"][1]["affiliate_url"]
    assert not approved_affiliate_route(target, read(DATA / "merchant_partners.json"))


def test_explicit_top_runtime_scope_still_requires_real_database_source(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_MERCHANTS", "top-parfuemerie")
    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", lambda *a, **kw: {})
    monkeypatch.setattr(purchase_freshness, "evidence_for", lambda offer_id: None)
    store = MerchantOfferStore(DATA / "merchant_offers.json")
    for offer in read(PACKET / "proposed-offers.json")["offers"]:
        assert store.eligible_offer(offer["offer_id"], now=NOW) is None
