from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from examples.retail.api import purchase_freshness, runtime_offer_snapshots
from examples.retail.api.merchant_offers import (
    MerchantOfferStore,
    customer_offer_payload,
    offer_clickout_target,
)
from examples.retail.api.merchant_partners import MerchantPartnerStore
from scripts.prepare_dufynd_runtime_offer_batch import prepare_batch

DATA = Path("examples/retail/data")
PACKET = Path("artifacts/dufynd-top-six-offers-20261026")
NOW = datetime(2026, 10, 26, 13, 0, tzinfo=UTC)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def test_only_six_exact_routes_are_integrated_and_all_other_rows_are_preserved() -> None:
    integration = read(PACKET / "development-integration.json")
    ids, products = set(integration["offer_ids"]), set(integration["product_ids"])
    # Later additive wave has its own exact four-row preservation/source gate.
    # Remove only that reviewed delta when checking this historical six-row wave.
    wave2 = read(Path("artifacts/dufynd-top-wave2-offers-20261026/development-integration.json"))
    later_ids, later_products = set(wave2["offer_ids"]), set(wave2["product_ids"])
    for name, key in (
        ("merchant_offers.json", "offers"),
        ("merchant_partners.json", "partners"),
        ("merchant_product_mappings.json", "mappings"),
    ):
        rows = read(DATA / name)[key]
        if key == "offers":
            existing_updates = set(integration.get("allowed_existing_offer_updates", []))
            preserved = [x for x in rows if x["offer_id"] not in ids | existing_updates | later_ids]
            assert len([x for x in rows if x["offer_id"] in ids]) == 6
        elif key == "partners":
            preserved = [x for x in rows if x["merchant_id"] != "top-parfuemerie"]
            top = next(x for x in rows if x["merchant_id"] == "top-parfuemerie")
            assert top["status"] == "active_product_deeplink_only" and top["affiliate_url"] is None
            assert set(top["verified_product_scope"]) == products | later_products
            assert len(top["verified_feed_routes"]) == 6 + len(later_ids)
        else:
            preserved = [
                x
                for x in rows
                if not (
                    x["merchant"] == "top-parfuemerie"
                    and x["product_id"] in products | later_products
                )
            ]
            assert len(rows) - len(preserved) == 6 + len(later_ids)
        encoded = json.dumps(
            preserved, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        assert (
            hashlib.sha256(encoded).hexdigest()
            == integration["preservation"][name]["preserved_rows_sha256"]
        )
    assert (
        MerchantPartnerStore(DATA / "merchant_partners.json").eligible("top-parfuemerie", now=NOW)
        is None
    )


@pytest.mark.parametrize("runtime", [False, True])
def test_normal_store_customer_payload_and_pure_resolver_work_without_top_database(
    runtime, monkeypatch
) -> None:
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled" if runtime else "")
    monkeypatch.delenv("DUFYND_RUNTIME_OFFER_MERCHANTS", raising=False)
    requested = []
    monkeypatch.setattr(
        runtime_offer_snapshots,
        "load_runtime_snapshots",
        lambda rows, **kwargs: requested.extend(rows) or {},
    )
    monkeypatch.setattr(purchase_freshness, "evidence_for", lambda offer_id: None)
    store = MerchantOfferStore(DATA / "merchant_offers.json")
    for expected in read(PACKET / "proposed-offers.json")["offers"]:
        offer = next(
            x
            for x in store.offers_for(expected["product_id"], now=NOW)
            if x.offer_id == expected["offer_id"]
        )
        assert customer_offer_payload(offer)["variant_label"] == expected["variant_label"]
        assert customer_offer_payload(offer)["total_price"] == expected["price"]
        # Pure resolver only: no HTTP redirect, affiliate visit or analytics.
        assert offer_clickout_target(offer) == expected["affiliate_url"]
        assert store.eligible_offer(offer.offer_id, now=NOW).offer_id == offer.offer_id
    assert all(x["merchant_id"] != "top-parfuemerie" for x in requested)


def test_existing_importer_accepts_real_development_files_and_missing_runtime_evidence_still_holds(
    monkeypatch,
) -> None:
    offers = read(DATA / "merchant_offers.json")["offers"]
    prepared = prepare_batch(offers, read(PACKET / "batch-input.json"), now=NOW)
    assert len(prepared) == 6
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_MERCHANTS", "top-parfuemerie")
    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", lambda *a, **kw: {})
    monkeypatch.setattr(purchase_freshness, "evidence_for", lambda offer_id: None)
    store = MerchantOfferStore(DATA / "merchant_offers.json")
    for offer in read(PACKET / "proposed-offers.json")["offers"]:
        assert store.eligible_offer(offer["offer_id"], now=NOW) is None
