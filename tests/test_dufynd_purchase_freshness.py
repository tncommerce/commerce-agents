from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from examples.retail.api.merchant_offers import MerchantOffer, rank_offers
from examples.retail.api.purchase_freshness import TARGET_OFFER, apply_evidence, evidence_for


def row():
    return next(
        r
        for r in json.loads(Path("examples/retail/data/merchant_offers.json").read_text())["offers"]
        if r["offer_id"] == TARGET_OFFER
    )


def evidence(r):
    return {
        "source": "certified_purchase_verification",
        "max_age_hours": 72,
        "offer_contract": {k: v for k, v in r.items() if k != "last_updated_at"},
        "verified_at": datetime.now(UTC).isoformat(),
        "decision": "safe_evidence_refresh",
    }


def test_safe_evidence_refresh_changes_timestamp_only():
    r = row()
    e = evidence(r)
    result = apply_evidence(r, e)
    assert result["last_updated_at"] == e["verified_at"]
    assert {k: v for k, v in result.items() if k != "last_updated_at"} == e["offer_contract"]


@pytest.mark.parametrize(
    "field", ["price", "product_url", "merchant_product_id", "variant_label", "affiliate_url"]
)
def test_changed_contract_never_refreshes(field):
    r = row()
    e = evidence(r)
    e["offer_contract"][field] = "changed"
    assert apply_evidence(r, e) == r


@pytest.mark.parametrize(
    "decision",
    [
        "price_review_required",
        "stock_unverified_or_changed",
        "gtin_mismatch",
        "route_contract_mismatch",
        "transport_unverified",
    ],
)
def test_unsafe_verification_does_not_present_old_offer_as_healthy(decision):
    r = row()
    e = evidence(r)
    e["decision"] = decision
    result = apply_evidence(r, e)
    assert result["last_updated_at"] == r["last_updated_at"]
    assert not result["in_stock"]
    assert not rank_offers([MerchantOffer.model_validate(result)])


def test_todays_72_hour_exclusion_and_verified_recovery():
    r = row()
    r["last_updated_at"] = (datetime.now(UTC) - timedelta(hours=72, seconds=1)).isoformat()
    assert not rank_offers([MerchantOffer.model_validate(r)])
    assert rank_offers([MerchantOffer.model_validate(apply_evidence(r, evidence(r)))])


@pytest.mark.parametrize("hours", [-1, 73])
def test_future_or_expired_evidence_does_not_bump_date(hours):
    r = row()
    e = evidence(r)
    e["verified_at"] = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    assert apply_evidence(r, e) == r


def test_outage_keeps_original_gate(monkeypatch):
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert evidence_for(TARGET_OFFER) is None
    r = row()
    assert apply_evidence(r, None) == r


def test_unrelated_offer_has_no_external_read():
    assert evidence_for("unrelated") is None
