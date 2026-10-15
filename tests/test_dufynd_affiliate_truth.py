from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from scripts.dufynd_affiliate_truth import EVIDENCE_KEY, build_partner_truth, context_partner_truth
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_jarvis_context_pages import context_page

NOW = datetime(2026, 10, 15, 20, tzinfo=UTC)
GTIN = "3349666007921"


def fact(status, **kwargs):
    return {
        "merchant_id": "merchant-a",
        "status": status,
        "verified_at": (NOW - timedelta(hours=1)).isoformat(),
        "source_kind": "network",
        "evidence_ref": "network:verified-receipt",
        **kwargs,
    }


def ready_records():
    exact = {"product_id": "PRODUCT-100", "gtin": GTIN}
    return [
        fact("APPROVED"),
        fact(
            "TRACKING_READY", **exact, tracking_strategy="product_deeplink", landing_verified=True
        ),
        fact(
            "PRODUCT_READY",
            **exact,
            public_page_verified=True,
            release_approved=True,
            image_used=False,
        ),
        fact(
            "OFFER_CURRENT",
            **exact,
            price_eur=70.0,
            shipping_eur=5.0,
            in_stock=True,
            public_offer_verified=True,
        ),
    ]


def project(records, legacy="unknown"):
    return build_partner_truth([{"merchant_id": "merchant-a", "status": legacy}], records, now=NOW)


def state(records, legacy="unknown"):
    return project(records, legacy)["partners"][0]["primary_status"]


@pytest.mark.parametrize(
    "legacy", ["approved", "tracking_ready", "feed_ready", "revenue_ready", "unknown"]
)
def test_legacy_positive_flags_are_not_verified_evidence(legacy):
    result = project([], legacy)
    assert result["partners"][0]["primary_status"] == "UNKNOWN"
    assert result["commerce_plan"] == []


@pytest.mark.parametrize("stage", ["APPLIED", "PENDING", "APPROVED"])
def test_explicit_partner_stages(stage):
    assert state([fact(stage)]) == stage


def test_feed_never_implies_approval_and_merchant_letter_is_not_network_approval():
    assert state([fact("FEED_READY")]) == "UNKNOWN"
    assert state([fact("APPROVED", source_kind="merchant_email"), fact("FEED_READY")]) == "UNKNOWN"
    assert state([fact("APPROVED"), fact("FEED_READY")]) == "FEED_READY"


def test_deeplink_can_be_revenue_ready_without_feed_or_image():
    result = project(ready_records())
    partner = result["partners"][0]
    assert partner["primary_status"] == "REVENUE_READY"
    assert partner["products"][0]["revenue_ready"]
    assert not partner["activation_allowed"]
    assert not partner["automatic_application_allowed"]
    assert result["commerce_plan"] == [
        {"merchant_id": "merchant-a", "action": "prepare_evidence_bound_draft"}
    ]


def test_incremental_stages():
    records = ready_records()
    assert state(records[:1]) == "APPROVED"
    assert state(records[:2]) == "TRACKING_READY"
    assert state(records[:3]) == "PRODUCT_READY"
    assert state(records) == "REVENUE_READY"


def test_feed_tracking_requires_a_fresh_feed():
    records = ready_records()
    records[1]["tracking_strategy"] = "feed"
    assert state(records) != "REVENUE_READY"
    assert state(records + [fact("FEED_READY")]) == "REVENUE_READY"
    assert (
        state(records + [fact("FEED_READY", verified_at=(NOW - timedelta(hours=73)).isoformat())])
        != "REVENUE_READY"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("gtin", "9999999999999"),
        ("in_stock", False),
        ("public_offer_verified", False),
        ("shipping_eur", None),
    ],
)
def test_offer_requires_exact_fresh_public_available_product(field, value):
    records = ready_records()
    records[3][field] = value
    assert state(records) == "PRODUCT_READY"


def test_stale_offer_and_expiry_do_not_get_refreshed_by_observation():
    records = ready_records()
    records[3]["verified_at"] = (NOW - timedelta(hours=73)).isoformat()
    result = project(records)
    assert result["partners"][0]["primary_status"] == "PRODUCT_READY"
    offer = next(
        x for x in result["partners"][0]["stage_evidence"] if x["status"] == "OFFER_CURRENT"
    )
    assert offer["stale"] and offer["verified_at"] == records[3]["verified_at"]
    records = ready_records()
    records[3]["expires_at"] = (NOW - timedelta(minutes=1)).isoformat()
    assert state(records) == "PRODUCT_READY"


def test_stale_approval_is_not_rescued_by_fresh_feed():
    records = ready_records() + [fact("FEED_READY")]
    records[0]["verified_at"] = (NOW - timedelta(days=31)).isoformat()
    assert state(records) == "UNKNOWN"


def test_image_declaration_is_required_and_rights_are_asset_specific():
    records = ready_records()
    del records[2]["image_used"]
    assert state(records) != "REVENUE_READY"
    records[2].update(image_used=True, asset_ref="asset-a")
    assert state(records) == "RIGHTS_HOLD"
    rights = fact("RIGHTS_APPROVED", product_id="PRODUCT-100", gtin=GTIN, asset_ref="asset-b")
    assert state(records + [rights]) == "RIGHTS_HOLD"
    rights["asset_ref"] = "asset-a"
    assert state(records + [rights]) == "REVENUE_READY"
    hold = fact("RIGHTS_HOLD", product_id="PRODUCT-100", verified_at=NOW.isoformat())
    assert state(records + [rights, hold]) == "RIGHTS_HOLD"


@pytest.mark.parametrize("negative", ["REJECTED", "EXTERNAL_HOLD"])
def test_negative_evidence_suppresses_planning_and_activation(negative):
    records = ready_records() + [fact(negative, verified_at=NOW.isoformat())]
    result = project(records)
    assert result["partners"][0]["primary_status"] == negative
    assert result["commerce_plan"] == []
    assert not result["partners"][0]["products"][0]["revenue_ready"]


def test_old_negative_and_legacy_rejection_do_not_expire_into_approval():
    assert (
        state([fact("REJECTED", verified_at=(NOW - timedelta(days=90)).isoformat())]) == "REJECTED"
    )
    assert state(ready_records(), "rejected") == "REJECTED"
    assert project(ready_records(), "rejected")["commerce_plan"] == []


def test_owner_rejection_is_hold_not_invented_network_status():
    assert (
        state(
            ready_records()
            + [fact("REJECTED", source_kind="owner_report", verified_at=NOW.isoformat())]
        )
        == "EXTERNAL_HOLD"
    )
    assert state([fact("APPROVED", source_kind="owner_report")]) == "UNKNOWN"


def test_new_independent_approval_can_supersede_source_rejection_not_legacy_registry():
    records = ready_records() + [
        fact("REJECTED", verified_at=(NOW - timedelta(days=1)).isoformat())
    ]
    assert state(records) == "REVENUE_READY"
    assert state(records, "rejected") == "REJECTED"


def test_same_time_conflicts_fail_closed_regardless_of_order():
    records = ready_records()
    conflicting = deepcopy(records[3])
    conflicting["price_eur"] = 80.0
    assert (
        state(records + [conflicting])
        == state(list(reversed(records + [conflicting])))
        == "PRODUCT_READY"
    )
    rejections = [fact("REJECTED", source_kind=kind) for kind in ("network", "network_email")]
    assert state(records + rejections) == "REJECTED"


@pytest.mark.parametrize(
    "change",
    [
        {"in_stock": "true"},
        {"price_eur": -1},
        {"verified_at": "2026-10-15T23:00:00Z"},
        {"evidence_ref": "https://example.test/?token=secret"},
        {"unexpected": True},
    ],
)
def test_malformed_or_future_evidence_fails_closed(change):
    records = ready_records()
    records[3].update(change)
    assert state(records) == "UNKNOWN"
    assert project(records)["commerce_plan"] == []


def test_context_missing_duplicate_or_malformed_envelope_is_safe():
    context = {"affiliate_partners": [{"merchant_id": "merchant-a", "status": "approved"}]}
    assert context_partner_truth(context, now=NOW)["partners"][0]["primary_status"] == "UNKNOWN"
    entry = {"key": EVIDENCE_KEY, "value": {"version": 1, "records": ready_records()}}
    context["master_status"] = [entry]
    assert (
        context_partner_truth(context, now=NOW)["partners"][0]["primary_status"] == "REVENUE_READY"
    )
    context["master_status"] = [entry, entry]
    assert context_partner_truth(context, now=NOW)["partners"][0]["primary_status"] == "UNKNOWN"
    context["master_status"] = "malformed"
    assert context_partner_truth(context, now=NOW)["partners"][0]["primary_status"] == "UNKNOWN"


def test_actual_bridge_enriches_existing_context_without_second_request_or_write():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(
            200, json={"affiliate_partners": [{"merchant_id": "merchant-a", "status": "rejected"}]}
        )

    bridge = DufyndJarvisBridge(
        supabase_url="https://test.invalid",
        secret_key="test",
        transport=httpx.MockTransport(handler),
    )
    result = bridge.load_context()
    assert result["affiliate_truth"]["partners"][0]["primary_status"] == "REJECTED"
    assert calls == [("POST", "/rest/v1/rpc/get_dufynd_jarvis_context")]
    assert result["affiliate_truth"]["production_writes"] is False


def test_context_pagination_is_stable_until_evidence_or_freshness_changes():
    context = {
        "affiliate_partners": [{"merchant_id": "merchant-a"}],
        "master_status": [
            {"key": EVIDENCE_KEY, "value": {"version": 1, "records": ready_records()}}
        ],
    }
    first = context_partner_truth(context, now=NOW)
    second = context_partner_truth(context, now=NOW + timedelta(seconds=1))
    assert context_page(first)[0]["sha256"] == context_page(second)[0]["sha256"]
    expired = context_partner_truth(context, now=NOW + timedelta(hours=74))
    assert context_page(first)[0]["sha256"] != context_page(expired)[0]["sha256"]
