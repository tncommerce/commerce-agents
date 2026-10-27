"""Fail-closed, no-network DUFYND staging preview tests."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts.prepare_dufynd_staging_photo_preview import (
    DATA,
    MANIFEST,
    PUBLIC,
    _image_source,
    build_private_review,
    render_html,
)

NOW = datetime(2026, 10, 27, 10, 30, tzinfo=UTC)


def data():
    def read(path):
        return json.loads(path.read_text(encoding="utf-8-sig"))

    return [
        read(MANIFEST),
        read(DATA / "scentai_catalog_staging.json"),
        read(PUBLIC / "public-fragrances.json"),
        read(DATA / "merchant_product_mappings.json"),
        read(PUBLIC / "original-photos.json"),
        read(DATA / "merchant_partners.json"),
        read(DATA / "dufynd_affiliate_feed_image_rights.json"),
    ]


def run(parts=None, *, now=NOW):
    return build_private_review(*(parts or data()), now=now)


def test_four_original_bottles_private_with_no_price_or_clickout():
    report = run()
    assert report["totals"] == {
        "source_verified_originals": 4,
        "approved_public_images": 0,
        "new_purchasable_offers": 0,
        "new_public_profiles": 0,
        "affiliate_clickouts": 0,
    }
    ids = {x["product_id"] for x in report["items"]}
    assert ids == {
        "SC-JPG-LE-MALE-LE-PARFUM-125",
        "SC-NARCISO-RODRIGUEZ-PURE-MUSC-EDP-100",
        "SC-HUGO-BOSS-BOTTLED-ABSOLU-100",
        "SC-AMOUAGE-GUIDANCE-46-EXTRAIT-100",
    }
    for item in report["items"]:
        assert item["price_eur"] is None
        assert item["stock_confirmed"] is False
        assert item["photo_publication_allowed"] is False
        assert item["merchant_clickout_enabled"] is False
        assert len(item["image_sha256"]) == 64
        assert item["key_notes"]


def test_html_is_unpublished_and_never_links_to_merchants():
    page = render_html(run())
    assert page.count('<article class="card">') == 4
    assert page.count("<img ") == 4
    assert page.count(" disabled>") == 4
    assert 'name="robots" content="noindex,nofollow"' in page
    assert "awin1.com" not in page
    assert "jdoqocy" not in page
    assert "<a " not in page
    assert "fetch(" not in page
    assert "€" not in page


@pytest.mark.parametrize(
    "change, error",
    [
        (lambda x: x[0]["source"].update({"active": False}), "source_provenance"),
        (lambda x: x[0]["source"].update({"feed_id": "0"}), "source_provenance"),
        (lambda x: x[0]["source"].update({"feed_sha256": "x"}), "source_provenance"),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"].append(
                copy.deepcopy(x[0]["newly_selected_for_visual_and_byte_qa"][0])
            ),
            "exact_four",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][1].update(
                {"product_id": "SC-JPG-LE-MALE-LE-PARFUM-125"}
            ),
            "staging_only",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][0]["product"].update(
                {"volume_ml": 75}
            ),
            "unverified_staging",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][0]["product"].update(
                {"name": "Le Male Elixir"}
            ),
            "unverified_staging",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][0]["official_feed"].update(
                {"merchant_sku": "999"}
            ),
            "image_sku_gtin",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][0]["official_feed"].update(
                {"original_feed_deeplink": "https://example.com/tracker"}
            ),
            "unexpected_awin",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][0]["review_gates"].update(
                {"source_image_download_verified": False}
            ),
            "source_bytes",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][0]["review_gates"].update(
                {"owner_visual_acceptance": True}
            ),
            "source_bytes",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][0]["review_gates"].update(
                {"new_affiliate_offer_activated": True}
            ),
            "source_bytes",
        ),
        (
            lambda x: x[0]["newly_selected_for_visual_and_byte_qa"][0]["review_gates"].update(
                {"source_image_bytes_sha256": "not-a-hash"}
            ),
            "source_bytes",
        ),
        (
            lambda x: x[2]["products"].append({"product_id": "SC-JPG-LE-MALE-LE-PARFUM-125"}),
            "staging_only",
        ),
        (
            lambda x: x[4].append({"product_id": "SC-NARCISO-RODRIGUEZ-PURE-MUSC-EDP-100"}),
            "staging_only",
        ),
        (lambda x: x[6]["entries"][1].update({"program_status": "pending"}), "active_official"),
        (
            lambda x: x[3]["mappings"].append(
                {"product_id": "SC-JPG-LE-MALE-LE-PARFUM-125", "ean": "9999999999999"}
            ),
            "contradictory",
        ),
    ],
)
def test_no_auto_approval_when_provenance_or_variant_changes(change, error):
    parts = data()
    change(parts)
    with pytest.raises(ValueError, match=error):
        run(parts)


def test_expired_source_requires_real_refresh():
    with pytest.raises(ValueError, match="expired"):
        run(now=NOW + timedelta(days=8))


def test_reject_image_url_variant_host_and_query():
    good = data()[0]["newly_selected_for_visual_and_byte_qa"][0]
    url = good["official_feed"]["image_url"]
    sku = good["official_feed"]["merchant_sku"]
    gtin = good["product"]["canonical_historical_gtin"]
    _image_source(url, sku, gtin)
    for bad in (
        url.replace("www.topparfuemerie.de", "other.example"),
        url.replace("https://", "http://"),
        url.replace(".png", ".png?size=100"),
        url.replace(sku + "_", "12345_"),
    ):
        with pytest.raises(ValueError):
            _image_source(bad, sku, gtin)
