"""Contact sheets are isolated human-review artifacts, never photo approvals."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.render_dufynd_public_photo_review_html import render_review_html

PHOTO = "https://www.topparfuemerie.de/media/catalog/product/9/2/924719_3770010614630_051.png"


def packet() -> dict:
    return {
        "schema": "dufynd_licensed_feed_photo_review_v1",
        "status": "REVIEW_ONLY_NOT_LIVE",
        "automated_registration_allowed": False,
        "product_offer_activation_allowed": False,
        "approved_new_images": 0,
        "source_rights_basis_id": "awin_top_parfuemerie_feed_materials_20260928",
        "feed_provenance": {
            "source": "awin_product_feed_list",
            "advertiser_id": "31081",
            "feed_id": "91379",
            "checked_at": "2026-10-11T19:20:00Z",
            "last_imported": "2026-10-11T19:00:00Z",
        },
        "products_reviewed": 3,
        "products_with_leads": 1,
        "total_review_candidates": 1,
        "items": [
            {
                "product_id": "SC-XERJOFF-NAXOS-100",
                "brand": "Xerjoff",
                "name": "Naxos",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "candidates": [],
            },
            {
                "product_id": "SC-RABANNE-1-MILLION-EDT-100",
                "brand": "Rabanne",
                "name": "1 Million",
                "concentration": "Eau de Toilette",
                "volume_ml": 100,
                "candidates": [],
            },
            {
                "product_id": "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
                "brand": "Essential Parfums",
                "name": "Bois Impérial",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "candidates": [
                    {
                        "merchant_product_id": "924719",
                        "merchant_product_name": "Essential Parfums Bois Imperial 100 ml",
                        "feed_image_url": PHOTO,
                        "match_type": "mapped_sku_needs_feed_variant_review",
                        "feed_explicit_size_match": True,
                        "status": "HUMAN_SOURCE_VARIANT_IMAGE_REVIEW_REQUIRED",
                        "registered": False,
                        "published": False,
                    }
                ],
            },
        ],
    }


def test_review_page_preserves_holds_and_only_shows_feed_originals() -> None:
    html = render_review_html(packet())
    assert "0 neue Bildfreigaben" in html
    assert "3 offene Profile" in html
    assert "1 Profile mit Kandidaten" in html
    assert PHOTO in html
    assert 'referrerpolicy="no-referrer"' in html
    assert "Keine automatische" in html
    assert "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100" in html
    assert "SC-RABANNE-1-MILLION-EDT-100" in html


def test_untrusted_feed_labels_are_escaped_and_sensitive_fields_ignored() -> None:
    data = packet()
    data["items"][2]["name"] = '<script>alert("x")</script>'
    data["items"][2]["candidates"][0]["merchant_product_name"] = '<img src=x onerror="boom">'
    data["items"][2]["candidates"][0]["aw_deep_link"] = "https://secrets.invalid?token=SECRET"
    data["items"][2]["candidates"][0]["search_price"] = "999999"
    html = render_review_html(data)
    assert "<script>" not in html
    assert '<img src=x onerror="boom">' not in html
    assert "&lt;script&gt;" in html
    assert "SECRET" not in html
    assert "999999" not in html


@pytest.mark.parametrize(
    "change",
    [
        ("status", "PUBLISHED"),
        ("approved_new_images", 1),
        ("automated_registration_allowed", True),
        ("product_offer_activation_allowed", True),
        ("source_rights_basis_id", "arbitrary-license"),
    ],
)
def test_nonreview_metadata_fails_closed(change: tuple[str, object]) -> None:
    data = packet()
    key, value = change
    data[key] = value
    with pytest.raises(ValueError):
        render_review_html(data)


def test_untrusted_offsite_image_rejected_even_when_claimed_feed_image() -> None:
    data = packet()
    data["items"][2]["candidates"][0]["feed_image_url"] = (
        "https://www.topparfuemerie.de.evil.invalid/media/catalog/product/9/2/a.png"
    )
    with pytest.raises(ValueError, match="unsafe"):
        render_review_html(data)


def test_candidate_counts_and_duplicate_ids_fail_closed() -> None:
    data = packet()
    data["total_review_candidates"] = 2
    with pytest.raises(ValueError, match="count"):
        render_review_html(data)
    data = packet()
    data["items"][1] = deepcopy(data["items"][0])
    with pytest.raises(ValueError, match="duplicate"):
        render_review_html(data)


def test_first_money_and_mapped_showcase_candidates_sort_before_other_leads() -> None:
    data = packet()
    data["items"][0]["candidates"] = deepcopy(data["items"][2]["candidates"])
    data["products_with_leads"] = 2
    data["total_review_candidates"] = 2
    html = render_review_html(data)
    assert html.index('class="card"') < html.index("SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100")
    assert html.index("SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100") < html.index(
        "SC-XERJOFF-NAXOS-100"
    )
