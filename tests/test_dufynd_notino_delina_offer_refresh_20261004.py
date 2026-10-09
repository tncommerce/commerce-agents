from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from scripts.promote_scentai_catalog import promotion_blockers

DATA = Path("examples/retail/data")
PRODUCT_ID = "SC-PDM-DELINA-EDP-75"
OFFER_ID = "notino-pdm-delina-edp-75"
OBSERVED_AT = "2026-10-04T09:44:49Z"


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_delina_refresh_matches_verified_public_evidence() -> None:
    evidence = load("dufynd_notino_delina_libre_offer_refresh_20261004.json")
    offers = {row["offer_id"]: row for row in load("merchant_offers.json")["offers"]}

    row = next(item for item in evidence["products"] if item["product_id"] == PRODUCT_ID)
    offer = offers[OFFER_ID]

    assert evidence["observed_at"] == OBSERVED_AT
    assert evidence["observation_method"] == "current_public_merchant_catalog_read_only_web"
    assert row["merchant_product_id"] == "PDM0227"
    assert row["exact_variant"] == "Parfums de Marly Delina Eau de Parfum 75 ml"
    assert row["price_eur"] == 285
    assert row["shipping_cost_eur"] == 0
    assert row["availability_observed"] is True

    assert offer["product_id"] == PRODUCT_ID
    assert offer["merchant_product_id"] == row["merchant_product_id"]
    assert offer["variant_label"] == "75 ml · Eau de Parfum"
    assert offer["price"] == row["price_eur"]
    assert offer["shipping_cost"] == row["shipping_cost_eur"]
    assert offer["in_stock"] is row["availability_observed"]
    # The October 4 evidence remains immutable; a later verified refresh may
    # advance freshness while preserving this exact merchant variant.
    assert datetime.fromisoformat(offer["last_updated_at"].replace("Z", "+00:00")) >= (
        datetime.fromisoformat(OBSERVED_AT.replace("Z", "+00:00"))
    )
    assert offer["affiliate_url"].startswith("https://www.jdoqocy.com/click-")


def test_delina_refresh_changes_freshness_only_and_keeps_publication_gated() -> None:
    evidence = load("dufynd_notino_delina_libre_offer_refresh_20261004.json")
    safeguards = evidence["safeguards"]

    assert safeguards == {
        "exact_variant_mapping_unchanged": True,
        "tracked_deep_links_unchanged": True,
        "affiliate_scope_unchanged": True,
        "catalog_publication_authorized": False,
        "image_rights_changed": False,
        "no_commission_ranking_change": True,
    }


def test_delina_refresh_keeps_dynamic_purchase_gate_clear() -> None:
    staging = {row["product_id"]: row for row in load("scentai_catalog_staging.json")["products"]}
    offers = load("merchant_offers.json")["offers"]
    verified_offer = next(row for row in offers if row["offer_id"] == OFFER_ID)
    now = datetime.fromisoformat(verified_offer["last_updated_at"].replace("Z", "+00:00"))

    blockers = promotion_blockers(
        staging[PRODUCT_ID],
        offers,
        now=now,
        max_offer_age_hours=72.0,
    )

    assert "missing_current_purchase_destination" not in blockers
    assert "missing_approved_image" not in blockers
    assert "missing_feed_image_rights_evidence" not in blockers
