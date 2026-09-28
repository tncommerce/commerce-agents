from __future__ import annotations

import pytest
from scripts.render_scentai_feed_image_review_html import render_html


def payload() -> dict:
    return {
        "version": 1,
        "status": "review_only_not_live",
        "automatic_approval_allowed": False,
        "approval_action_class": "approval_required",
        "feed_provenance": {
            "source": "awin_product_feed_list",
            "advertiser_id": "31081",
            "feed_id": "91379",
            "joined": True,
            "downloaded": True,
            "checked_at": "2026-09-28T12:00:00+00:00",
            "last_imported": "2026-09-28 11:30:00",
        },
        "candidates": [
            {
                "product_id": "SC-PDM-DELINA-EDP-75",
                "brand": "Parfums de Marly",
                "name": "Delina",
                "concentration": "Eau de Parfum",
                "volume_ml": 75,
                "merchant_product_id": "825869",
                "offer_id": "123",
                "image_url": "https://images.example/delina.jpg?x=1&y=2",
                "last_updated_at": "2026-09-28",
                "review_status": "pending_review",
                "proposed_image_status": "approved_feed_image",
                "exact_variant_verified": True,
                "data_source": "approved-affiliate-feed",
                "rights_basis_id": "awin_top_parfuemerie_feed_materials_20260928",
                "rights_status": "verified_for_publisher_service",
                "advertiser_id": "31081",
                "feed_id": "91379",
                "feed_checked_at": "2026-09-28T12:00:00+00:00",
                "approval_action_class": "approval_required",
            }
        ],
    }


def test_renders_exact_pending_candidate_without_approving_it() -> None:
    rendered = render_html(payload())

    assert "Parfums de Marly" in rendered
    assert "Delina" in rendered
    assert "Eau de Parfum" in rendered
    assert "75 ml" in rendered
    assert "825869" in rendered
    assert "awin_top_parfuemerie_feed_materials_20260928" in rendered
    assert "pending_review" in rendered
    assert "Human visual approval required" in rendered
    assert "not approved and is not live" in rendered
    assert "https://images.example/delina.jpg?x=1&amp;y=2" in rendered
    assert "AWIN_DATA_FEED_API_KEY" not in rendered


def test_html_escapes_feed_controlled_text() -> None:
    data = payload()
    data["candidates"][0]["name"] = '<script>alert("x")</script>'

    rendered = render_html(data)

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_non_https_or_credentialed_image_urls_are_rejected() -> None:
    data = payload()
    data["candidates"][0]["image_url"] = "http://images.example/delina.jpg"
    with pytest.raises(ValueError, match="candidate_image_url_must_be_public_https"):
        render_html(data)

    data = payload()
    data["candidates"][0]["image_url"] = "https://user:pass@images.example/delina.jpg"
    with pytest.raises(ValueError, match="candidate_image_url_must_be_public_https"):
        render_html(data)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("review_status", "approved", "candidate_not_pending_review"),
        ("exact_variant_verified", False, "candidate_exact_variant_not_verified"),
        ("data_source", "awin-product-data-feed-preflight", "candidate_data_source_invalid"),
        ("rights_status", "pending", "candidate_rights_not_verified"),
        ("feed_id", "wrong", "candidate_feed_mismatch"),
        ("feed_checked_at", "wrong", "candidate_feed_checked_at_mismatch"),
    ],
)
def test_candidate_review_guards_are_mandatory(field: str, value: object, error: str) -> None:
    data = payload()
    data["candidates"][0][field] = value

    with pytest.raises(ValueError, match=error):
        render_html(data)


def test_payload_cannot_enable_automatic_approval() -> None:
    data = payload()
    data["automatic_approval_allowed"] = True

    with pytest.raises(ValueError, match="candidate_payload_must_disable_automatic_approval"):
        render_html(data)


def test_empty_pending_set_renders_safe_empty_packet() -> None:
    data = payload()
    data["candidates"] = []

    rendered = render_html(data)

    assert "No pending candidates" in rendered
    assert "Pending candidates</strong><span>0</span>" in rendered
