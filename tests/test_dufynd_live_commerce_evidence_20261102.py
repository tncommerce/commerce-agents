"""Adversarial 57-page and exact-merchant-source evidence regression."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.validate_dufynd_live_commerce_evidence import validate_evidence

DATA = Path("examples/retail/data")
WEB = Path("examples/retail/storefront-web/lib/generated")
OBSERVATION = datetime(2026, 11, 2, 17, 20, 51, tzinfo=UTC)


def sources() -> tuple:
    return (
        json.loads((DATA / "dufynd_live_commerce_evidence_20261102.json").read_text()),
        json.loads((WEB / "public-fragrances.json").read_text()),
        json.loads((WEB / "released-profiles.json").read_text()),
        json.loads((DATA / "dufynd_facts_wave_02_review.json").read_text()),
        json.loads((WEB / "original-photos.json").read_text()),
        json.loads((DATA / "merchant_product_mappings.json").read_text()),
    )


def report(snapshot: dict, *, now: datetime = OBSERVATION) -> dict:
    _, legacy, released, held, originals, mappings = sources()
    return validate_evidence(
        snapshot, legacy, released, held, originals, mappings, now=now
    )


def test_actual_live_evidence_has_complete_57_page_and_photo_partition() -> None:
    evidence, *_ = sources()
    result = report(evidence, now=OBSERVATION + timedelta(hours=1))
    assert result["status"] == "PASS"
    assert result["verified_live_urls"] == 57
    assert result["approved_photos"] == 10
    assert result["public_missing_original"] == 47
    assert result["merchant_pages_examined"] == 5
    assert result["top_gallery_leads_held"] == 4
    assert result["wrong_og_preview_variants_blocked"] == 3
    assert result["giftbox_photos_held"] == 1
    assert result["merchant_in_stock_history"] == 1
    assert result["merchant_out_of_stock_history"] == 4
    assert result["merchant_observations_fresh_for_private_review"] is True
    assert result["merchant_offers_activated"] == 0
    assert result["affiliate_clickouts"] == 0
    assert result["database_writes"] == 0
    assert result["source_html_downloads"] == 0


def test_expired_stock_history_cannot_be_presented_as_fresh() -> None:
    evidence, *_ = sources()
    assert report(evidence, now=OBSERVATION + timedelta(hours=25))[
        "merchant_observations_fresh_for_private_review"
    ] is False
    assert report(evidence, now=OBSERVATION + timedelta(minutes=6))[
        "merchant_observations_fresh_for_private_review"
    ] is True
    assert report(evidence, now=OBSERVATION - timedelta(minutes=6))[
        "merchant_observations_fresh_for_private_review"
    ] is False


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (
            lambda d: d["public_crawl"]["records"][0].update(
                {"canonical": "https://dufynd.de/duft/another-variant"}
            ),
            "public_html_proof_missing",
        ),
        (
            lambda d: d["public_crawl"]["records"][0].update({"http_status": 404}),
            "public_html_proof_missing",
        ),
        (
            lambda d: d["public_crawl"]["records"][0].update({"html_sha256": "none"}),
            "public_html_proof_missing",
        ),
        (
            lambda d: d["public_crawl"]["records"][0].update(
                {"photo_state": "VERIFIED_ORIGINAL"}
            ),
            "original_rights_state_inaccurate",
        ),
        (
            lambda d: d["public_crawl"]["records"][0].update(
                {"affiliate_url": "https://www.awin1.com/cread.php"}
            ),
            "unexpected_public_evidence_fields",
        ),
        (
            lambda d: d["public_crawl"]["records"].pop(),
            "public_exact_scope_mismatch",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"gtin": "0000000000000"}
            ),
            "merchant_exact_variant_proof_missing",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"merchant_article": "70727123"}
            ),
            "merchant_exact_variant_proof_missing",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"volume_ml": 50}
            ),
            "merchant_exact_variant_proof_missing",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"source_page_url": "https://awin1.com/cread.php?affiliate=123"}
            ),
            "merchant_source_not_direct_https",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"source_page_url": "https://www.perfumetrader.de/de/fake?src=tracking"}
            ),
            "merchant_source_not_direct_https",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"price": 71.90}
            ),
            "unexpected_merchant_evidence_fields",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"merchant_offer_activated": True}
            ),
            "merchant_evidence_wrongly_promoted",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"image_rights_granted": True}
            ),
            "merchant_evidence_wrongly_promoted",
        ),
        (
            lambda d: d["perfumetrader_crawl"]["merchant_source_pages"][0].update(
                {"tracked_link_currently_verified": True}
            ),
            "merchant_evidence_wrongly_promoted",
        ),
        (
            lambda d: d["perfumetrader_crawl"].update(
                {"product_csv_schema_verified": True}
            ),
            "unauthorized_product_feed_assertion",
        ),
        (
            lambda d: d["safety"].update({"no_affiliate_tracking_link_generated": False}),
            "unsafe_source_claim",
        ),
    ],
)
def test_evidence_remains_fail_closed_under_source_and_rights_mutation(
    mutation, error: str
) -> None:
    base, *_ = sources()
    changed = copy.deepcopy(base)
    mutation(changed)
    with pytest.raises(ValueError, match=error):
        report(changed)


def test_private_wave_two_cannot_be_smuggled_into_live_page_manifest() -> None:
    evidence, *_ = sources()
    changed = copy.deepcopy(evidence)
    changed["public_crawl"]["records"][0]["product_id"] = (
        "SC-TOM-FORD-OUD-WOOD-EDP-100"
    )
    with pytest.raises(ValueError, match="public_exact_scope_mismatch"):
        report(changed)


def test_private_merchant_source_is_not_a_runtime_offer_registry() -> None:
    evidence, *_ = sources()
    text = json.dumps(evidence).lower()
    for forbidden in [
        '"affiliate_url"',
        '"merchant_image_url"',
        '"price_eur"',
        '"search_price"',
        '"merchant_deep_link"',
        '"aw_deep_link"',
        '"feed_row"',
        '"customer_email"',
    ]:
        assert forbidden not in text
    assert evidence["perfumetrader_crawl"]["product_csv_schema_verified"] is False
    assert evidence["perfumetrader_crawl"]["stock_observations_expire_after_hours"] == 24
    assert all(
        item["merchant_offer_activated"] is False
        for item in evidence["perfumetrader_crawl"]["merchant_source_pages"]
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("merchant_product_id", "849413", "top_gallery_exact_identity_mismatch"),
        ("gtin", "0000000000000", "top_gallery_exact_identity_mismatch"),
        (
            "variant_gallery_image_url",
            "https://www.topparfuemerie.de/media/catalog/product/cache/"
            "d2ab279b21a5d94cbebd5a4e62d42d56/8/4/849413_3386460101059_051.png",
            "top_gallery_exact_image_url_missing",
        ),
        ("og_preview_exact_variant", True, "top_og_preview_variant_mismatch_not_reported"),
        ("source_image_bytes_downloaded", True, "top_gallery_wrongly_promoted"),
        ("source_image_sha256", "a" * 64, "top_gallery_wrongly_promoted"),
        ("exact_front_photo_visually_verified", True, "top_gallery_wrongly_promoted"),
        ("merchant_image_rights_final_approved", True, "top_gallery_wrongly_promoted"),
        ("owner_visual_approved", True, "top_gallery_wrongly_promoted"),
        ("public_photo_activation", True, "top_gallery_wrongly_promoted"),
        ("merchant_offer_activation", True, "top_gallery_wrongly_promoted"),
        ("affiliate_url", "https://awin1.com/cread.php", "top_gallery_unexpected_fields"),
    ],
)
def test_top_gallery_never_promotes_wrong_or_unlicensed_image(
    field: str, value: object, reason: str
) -> None:
    base, *_ = sources()
    changed = copy.deepcopy(base)
    changed["top_parfuemerie_gallery_crawl"]["records"][0][field] = value
    with pytest.raises(ValueError, match=reason):
        report(changed)


def test_top_gallery_missing_and_giftbox_mismatch_remain_held() -> None:
    base, *_ = sources()
    changed = copy.deepcopy(base)
    changed["top_parfuemerie_gallery_crawl"]["records"].pop()
    with pytest.raises(ValueError, match="top_gallery_scope_changed"):
        report(changed)
    changed = copy.deepcopy(base)
    giftbox = next(
        item for item in changed["top_parfuemerie_gallery_crawl"]["records"]
        if item["product_id"] == "SC-XERJOFF-NAXOS-100"
    )
    giftbox["gift_box_source"] = False
    with pytest.raises(ValueError, match="top_giftbox_not_held"):
        report(changed)


def test_three_wrong_og_size_variants_are_not_stored_as_approved_photos() -> None:
    source, *_ = sources()
    items = source["top_parfuemerie_gallery_crawl"]["records"]
    mismatches = [item for item in items if not item["og_preview_exact_variant"]]
    assert len(mismatches) == 3
    assert {item["product_id"] for item in mismatches} == {
        "SC-MONTBLANC-EXPLORER-100",
        "SC-CREED-AVENTUS-100",
        "SC-PRADA-LHOMME-100",
    }
    assert all(item["source_image_sha256"] is None for item in items)
    assert all(item["public_photo_activation"] is False for item in items)
    assert all(item["merchant_offer_activation"] is False for item in items)
