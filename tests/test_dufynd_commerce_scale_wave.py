"""Review-wave gates, no network calls or artificial offer/image activation."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.dufynd_commerce_gates import approved_affiliate_route
from scripts.report_dufynd_commerce_scale_wave import build_commerce_wave

NOW = datetime(2026, 10, 24, 9, tzinfo=UTC)
DATA = Path("examples/retail/data")


def _fixtures():
    staging = {
        "products": [
            {
                "product_id": f"SC-REVIEW-{i:02d}",
                "brand": "Test Brand",
                "name": f"Fragrance {i}",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "validation": {"catalog_ready": False},
            }
            for i in range(20)
        ]
    }
    return staging, {"products": []}, [], {"offers": []}, {"partners": []}


def _run(staging, public, images, offers, partners, **kwargs):
    return build_commerce_wave(
        staging, public, images, offers, partners, now=NOW, batch_size=10, **kwargs
    )


def test_twenty_product_batch_does_not_publish_or_activate():
    staging, public, images, offers, partners = _fixtures()
    report = build_commerce_wave(staging, public, images, offers, partners, now=NOW, batch_size=20)
    assert report["batch_size"] == 20
    assert report["automatic_image_approval_allowed"] is False
    assert report["automatic_offer_activation_allowed"] is False
    assert report["automatic_profile_publication_allowed"] is False
    assert report["network_requests"] == 0
    assert report["database_writes"] == 0
    assert all(row["profile_gate"] == "REVIEW_ONLY" for row in report["items"])
    assert all(row["original_image_gate"] == "NO_APPROVED_ORIGINAL" for row in report["items"])


def test_source_photo_candidate_never_becomes_approved_original():
    staging, public, images, offers, partners = _fixtures()
    pid = staging["products"][0]["product_id"]
    wave = {
        "status": "REVIEW_ONLY_NOT_LIVE",
        "current_feed": {
            "advertiser_id": "31081",
            "feed_id": "91379",
            "checked_at": NOW.isoformat(),
        },
        "rights_basis_id": "rights-verified",
        "automatic_image_approval_allowed": False,
        "items": [
            {
                "product_id": pid,
                "status": "SOURCE_IMAGE_REVIEW_REQUIRED",
                "rights_basis_id": "rights-verified",
            }
        ],
    }
    result = _run(staging, public, images, offers, partners, photo_review=wave)
    assert result["items"][0]["original_image_gate"] == "SOURCE_IMAGE_REVIEW_REQUIRED"
    assert result["items"][0]["public_release_authorized_by_this_report"] is False

    wave["current_feed"]["checked_at"] = (NOW - timedelta(days=8)).isoformat()
    stale = _run(staging, public, images, offers, partners, photo_review=wave)
    assert stale["items"][0]["original_image_gate"] == "NO_APPROVED_ORIGINAL"


def test_approved_registry_reused_only_for_exact_volume_and_rights():
    staging, public, images, offers, partners = _fixtures()
    pid = staging["products"][0]["product_id"]
    images.append(
        {
            "product_id": pid,
            "volume_ml": 100,
            "rights_basis_id": "approved-original",
            "url": "https://cdn.example.com/verified.png",
        }
    )
    result = _run(staging, public, images, offers, partners)
    assert result["items"][0]["original_image_gate"] == "REUSE_ALREADY_APPROVED_ORIGINAL"
    images[0]["volume_ml"] = 50
    result = _run(staging, public, images, offers, partners)
    assert result["items"][0]["original_image_gate"] == "NO_APPROVED_ORIGINAL"


def test_expected_72h_offer_expiry_never_triggers_critical_incident():
    staging, public, images, offers, partners = _fixtures()
    pid = staging["products"][0]["product_id"]
    base = json.loads((DATA / "merchant_offers.json").read_text(encoding="utf-8"))
    real = next(row for row in base["offers"] if row["offer_id"] == "notino-ysl-libre-edp-90")
    real["product_id"] = pid
    real["last_updated_at"] = (NOW - timedelta(hours=73)).isoformat()
    offers["offers"] = [real]
    partners["partners"] = [
        {
            "merchant_id": "notino",
            "status": "active_product_deeplink_only",
            "live_routing_allowed": True,
            "verified_product_scope": [pid],
        }
    ]
    report = _run(staging, public, images, offers, partners)
    assert report["items"][0]["offer_gate"] == "EXPECTED_72H_EXPIRY"
    assert report["items"][0]["normal_expired_offer_rows"] == 1
    assert report["critical_software_api_incident"] is False

    outage = _run(staging, public, images, offers, partners, api_status="unavailable")
    assert outage["critical_software_api_incident"] is True
    assert outage["normal_expiry_is_software_incident"] is False


def test_partner_scope_and_affiliate_required_for_verified_offer():
    base = json.loads((DATA / "merchant_offers.json").read_text(encoding="utf-8"))
    real = next(row for row in base["offers"] if row["offer_id"] == "notino-ysl-libre-edp-90")
    partner = {
        "partners": [
            {
                "merchant_id": "notino",
                "status": "active_product_deeplink_only",
                "verified_product_scope": [real["product_id"]],
                "live_routing_allowed": True,
            }
        ]
    }
    assert approved_affiliate_route(real, partner)
    assert not approved_affiliate_route(real, {"partners": []})
    assert not approved_affiliate_route(
        real, {"partners": [partner["partners"][0] | {"verified_product_scope": []}]}
    )
    assert not approved_affiliate_route(real | {"affiliate_url": None}, partner)


def test_batch_size_and_unknown_id_are_fail_closed():
    staging, public, images, offers, partners = _fixtures()
    with pytest.raises(ValueError, match="batch_size"):
        build_commerce_wave(staging, public, images, offers, partners, now=NOW, batch_size=9)
    with pytest.raises(ValueError, match="unique_products"):
        _run(
            staging,
            public,
            images,
            offers,
            partners,
            product_ids=[staging["products"][0]["product_id"]] * 10,
        )
    with pytest.raises(ValueError, match="unknown"):
        _run(
            staging,
            public,
            images,
            offers,
            partners,
            product_ids=[f"SC-REVIEW-{i:02d}" for i in range(9)] + ["SC-NOT-KNOWN"],
        )


def test_affiliate_route_requires_exact_approved_destination_and_program() -> None:
    offers = json.loads((DATA / "merchant_offers.json").read_text(encoding="utf-8"))["offers"]
    notino = next(row for row in offers if row["offer_id"] == "notino-ysl-libre-edp-90")
    notino_partner = {
        "partners": [
            {
                "merchant_id": "notino",
                "status": "active_product_deeplink_only",
                "verified_product_scope": [notino["product_id"]],
                "live_routing_allowed": True,
            }
        ]
    }
    assert approved_affiliate_route(notino, notino_partner)
    bad_tracking = notino["affiliate_url"].replace("/click-101884613-12260695", "/click-evil")
    wrong_destination = notino["affiliate_url"].replace("p-15968532", "p-12345678")
    for replacement in (bad_tracking, wrong_destination):
        assert not approved_affiliate_route(notino | {"affiliate_url": replacement}, notino_partner)

    awin = next(
        row for row in offers if row["offer_id"] == "perfumetrader-rabanne-1-million-edt-100"
    )
    perfumetrader_partner = {"partners": [{"merchant_id": "perfumetrader", "status": "active"}]}
    assert approved_affiliate_route(awin, perfumetrader_partner)
    bad_advertiser = awin["affiliate_url"].replace("awinmid=11672", "awinmid=999")
    assert not approved_affiliate_route(
        awin | {"affiliate_url": bad_advertiser}, perfumetrader_partner
    )
