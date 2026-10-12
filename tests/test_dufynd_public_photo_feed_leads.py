"""No image registration may be derived from a missing DUFYND photo-source lead."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from scripts.report_dufynd_public_photo_feed_leads import (
    create_review,
    feed_name_matches,
    safe_feed_image,
)

META = {
    "source": "awin_product_feed_list",
    "advertiser_id": "31081",
    "feed_id": "91379",
    "joined": True,
    "downloaded": True,
    "checked_at": "2026-10-11T18:00:00Z",
}
RIGHTS = {
    "entries": [
        {
            "merchant_id": "top-parfuemerie",
            "advertiser_id": "31081",
            "rights_basis_id": "awin_top_parfuemerie_feed_materials_20260928",
            "program_status": "approved",
            "rights_status": "verified_for_publisher_service",
            "asset_scope": "unaltered_advertiser_materials_from_official_awin_product_feed",
        }
    ]
}
GAP = {
    "status": "RIGHTS_SOURCE_ACQUISITION_PENDING_NO_AUTO_APPROVAL",
    "items": [
        {
            "product_id": "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
            "brand": "Essential Parfums",
            "name": "Bois Impérial",
            "concentration": "Eau de Parfum",
            "volume_ml": 100,
        },
        {
            "product_id": "SC-XERJOFF-NAXOS-100",
            "brand": "Xerjoff",
            "name": "Naxos",
            "concentration": "Eau de Parfum",
            "volume_ml": 100,
        },
        {
            "product_id": "SC-PDM-LAYTON-125",
            "brand": "Parfums de Marly",
            "name": "Layton",
            "concentration": "Eau de Parfum",
            "volume_ml": 125,
        },
    ],
}
MAPPINGS = {
    "mappings": [
        {
            "product_id": "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
            "merchant": "top-parfuemerie",
            "merchant_product_id": "924719",
            "gtin": "3770010614630",
        },
    ]
}
PHOTO_BOIS = "https://www.topparfuemerie.de/media/catalog/product/9/2/924719_3770010614630_051.png"
PHOTO_NAXOS = "https://www.topparfuemerie.de/media/catalog/product/9/8/989001_0000000000000_051.png"


def row(sku: str, name: str, url: str, **kwargs) -> dict:
    return {
        "merchant_product_id": sku,
        "product_name": name,
        "merchant_image_url": url,
        "aw_deep_link": "https://tracking.example.test/?apikey=DO_NOT_EXPOSE",
        "search_price": "99.99",
        "in_stock": "true",
        **kwargs,
    }


def run(rows: list[dict], **kwargs) -> dict:
    return create_review(
        kwargs.get("gap", GAP),
        kwargs.get("mappings", MAPPINGS),
        rows,
        kwargs.get("metadata", META),
        kwargs.get("rights", RIGHTS),
        now=kwargs.get("now", datetime(2026, 10, 11, 19, 0, tzinfo=UTC)),
    )


def test_mapped_sku_and_name_only_leads_are_both_manual_holds() -> None:
    result = run(
        [
            row("924719", "Essential Parfums Bois Imperial EDP 100 ml", PHOTO_BOIS),
            row("989001", "Xerjoff Naxos Eau de Parfum 100 ml", PHOTO_NAXOS),
            row("989002", "Xerjoff Naxos EDP 50 ml", PHOTO_NAXOS),
        ]
    )
    assert result["status"] == "REVIEW_ONLY_NOT_LIVE"
    assert result["products_reviewed"] == 3
    assert result["products_with_leads"] == 2
    assert result["total_review_candidates"] == 2
    rows = {r["product_id"]: r for r in result["items"]}
    assert (
        rows["SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"]["candidates"][0]["match_type"]
        == "mapped_sku_needs_feed_variant_review"
    )
    assert (
        rows["SC-XERJOFF-NAXOS-100"]["candidates"][0]["match_type"]
        == "name_lead_manual_sku_mapping_required"
    )
    assert not rows["SC-PDM-LAYTON-125"]["candidates"]
    assert result["approved_new_images"] == 0
    assert result["automated_registration_allowed"] is False
    assert result["product_offer_activation_allowed"] is False
    assert "DO_NOT_EXPOSE" not in str(result)
    assert "search_price" not in str(result)


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://www.topparfuemerie.de/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de/media/catalog/product/a/1/123.png?key=abc",
        "https://other-merchant.invalid/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de.evil.invalid/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de/media/catalog/product/../private.png",
        "https://www.topparfuemerie.de/media/catalog/product/a/1/123.png#fragment",
        "https://admin@www.topparfuemerie.de/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de:8080/media/catalog/product/a/1/123.png",
        "https://www.topparfuemerie.de:broken/media/catalog/product/a/1/123.png",
        "",
    ],
)
def test_only_public_merchant_image_url_allowed(bad_url: str) -> None:
    assert safe_feed_image(bad_url) is None


def test_invalid_source_or_rights_fail_closed() -> None:
    meta = deepcopy(META)
    meta["joined"] = False
    with pytest.raises(ValueError, match="official_awin"):
        run([], metadata=meta)
    rights = deepcopy(RIGHTS)
    rights["entries"][0]["program_status"] = "pending"
    with pytest.raises(ValueError, match="rights"):
        run([], rights=rights)
    with pytest.raises(ValueError, match="current_awin_feed_timestamp_required"):
        run([], now=datetime(2026, 10, 19, tzinfo=UTC))
    with pytest.raises(ValueError, match="current_awin_feed_timestamp_required"):
        run([], now=datetime(2026, 10, 10, tzinfo=UTC))
    gap = deepcopy(GAP)
    gap["status"] = "approved_for_release"
    with pytest.raises(ValueError, match="unapproved"):
        run([], gap=gap)


def test_duplicate_feed_sku_and_duplicate_targets_are_not_approved() -> None:
    rows = [
        row("924719", "Essential Parfums Bois Imperial EDP 100 ml", PHOTO_BOIS),
        row("924719", "Essential Parfums Bois Imperial EDP 100 ml", PHOTO_BOIS),
    ]
    output = run(rows)
    entry = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert entry["duplicate_pinned_feed_sku_hold"] is True
    assert entry["candidates"] == []
    gap = deepcopy(GAP)
    gap["items"].append(gap["items"][0])
    with pytest.raises(ValueError, match="duplicate"):
        run([], gap=gap)


def test_secret_bearing_non_feed_urls_and_wrong_concentration_are_excluded() -> None:
    rows = [
        row(
            "989001",
            "Xerjoff Naxos EDP 100 ml",
            "https://www.topparfuemerie.de/media/catalog/product/9/8/abc.png?token=secret",
        ),
        row("989002", "Xerjoff Naxos EDT 100 ml", PHOTO_NAXOS),
        row("989003", "Xerjoff Naxos EDP 125 ml", PHOTO_NAXOS),
    ]
    result = run(rows)
    assert result["total_review_candidates"] == 0


def test_mapped_sku_different_fragrance_name_is_a_hard_hold() -> None:
    output = run([row("924719", "Essential Parfums Fig Infusion EDP 100 ml", PHOTO_BOIS)])
    record = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["pinned_feed_identity_conflict_hold"] is True
    assert record["candidates"] == []
    assert output["approved_new_images"] == 0


def test_mapped_sku_conflicting_official_gtin_is_a_hard_hold() -> None:
    output = run(
        [
            row(
                "924719",
                "Essential Parfums Bois Imperial EDP 100 ml",
                PHOTO_BOIS,
                gtin="0000000000000",
            )
        ]
    )
    record = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["pinned_feed_identity_conflict_hold"] is True
    assert record["candidates"] == []


def test_mapped_sku_matching_gtin_only_enters_manual_review() -> None:
    output = run(
        [
            row(
                "924719",
                "Essential Parfums Bois Imperial EDP 100 ml",
                PHOTO_BOIS,
                gtin="3770010614630",
            )
        ]
    )
    record = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["pinned_feed_identity_conflict_hold"] is False
    assert record["candidates"][0]["status"] == "HUMAN_SOURCE_VARIANT_IMAGE_REVIEW_REQUIRED"
    assert record["candidates"][0]["registered"] is False
    assert record["candidates"][0]["published"] is False


def test_missing_volume_in_mapped_feed_title_cannot_claim_verified_size() -> None:
    output = run([row("924719", "Essential Parfums Bois Imperial EDP", PHOTO_BOIS)])
    record = next(x for x in output["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["candidates"][0]["feed_explicit_size_match"] is False
    assert record["candidates"][0]["status"] == "HUMAN_SOURCE_VARIANT_IMAGE_REVIEW_REQUIRED"


@pytest.mark.parametrize("variant", ["Intense", "Elixir", "Extrait", "Edition", "Parfum"])
def test_variant_words_are_required_in_both_directions(variant: str) -> None:
    base = {"brand": "Example", "name": "Scent", "concentration": "EDP", "volume_ml": 100}
    flanker = {**base, "name": f"Scent {variant}"}
    plain = {"product_name": "Example Scent EDP 100 ml"}
    named = {"product_name": f"Example Scent {variant} Eau de Parfum 100 ml"}
    assert feed_name_matches(base, plain)
    assert feed_name_matches(flanker, named)
    assert not feed_name_matches(base, named)
    assert not feed_name_matches(flanker, plain)


@pytest.mark.parametrize(
    "name,concentration,title",
    [
        ("Bois Impérial", "Eau de Parfum", "Essential Parfums Bois Imperial EdP Nat. Spray 100 ml"),
        ("Bois Impérial", "Eau de Parfum", "Essential Parfums Bois Impérial EDP 100,0 ml"),
        ("Marwa Extrait", "Extrait de Parfum", "Essential Parfums Marwa Extrait de Parfum 100 ml"),
        ("Le Parfum", "Eau de Parfum", "Essential Parfums Le Parfum EdP 100 ml"),
        ("Collector's Edition", "Parfum", "Essential Parfums Collector’s Edition Parfum 100 ml"),
        ("Scent", "Eau de Toilette", "Essential Parfums Scent EDT 100 ml"),
        ("Scent", "Extrait de Parfum", "Essential Parfums Scent Extrait 100 ml"),
    ],
)
def test_exact_aliases_preserve_identity(name: str, concentration: str, title: str) -> None:
    item = {**GAP["items"][0], "name": name, "concentration": concentration}
    assert feed_name_matches(item, {"product_name": title})


@pytest.mark.parametrize("expected", ["EDP", "EDT", "Parfum", "Extrait de Parfum"])
@pytest.mark.parametrize("actual", ["EDP", "EDT", "Parfum", "Extrait de Parfum"])
def test_concentrations_are_distinct(expected: str, actual: str) -> None:
    item = {**GAP["items"][0], "concentration": expected}
    row = {"product_name": f"Essential Parfums Bois Imperial {actual} 100 ml"}
    assert feed_name_matches(item, row) is (expected == actual)


@pytest.mark.parametrize(
    "suffix",
    [
        "50 ml",
        "1000 ml",
        "100.5 ml",
        "10 ml + 100 ml",
        "100 ml + 5 ml",
        "100 ml 100 ml",
        "100/10 ml",
        "100 + 10 ml",
        "2x100 ml",
        "2 × 100 ml",
        "100 ml x 2",
        "100 ml Geschenkset",
        "100 ml Gift Set",
        "100 ml Coffret",
        "100 ml Duo",
        "100 ml Refill",
        "100 ml Nachfüllung",
        "100 ml Body Lotion",
        "100 ml Shower Gel",
        "100 ml Hair Mist",
        "100 ml EDT",
        "100 ml Edition 2026",
    ],
)
def test_sets_other_sizes_and_non_bottle_variants_never_become_mapped_leads(suffix: str) -> None:
    result = run(
        [
            row(
                "924719",
                f"Essential Parfums Bois Imperial EDP {suffix}",
                PHOTO_BOIS,
                gtin="3770010614630",
            ),
            row("989009", f"Essential Parfums Bois Imperial EDP {suffix}", PHOTO_BOIS),
        ]
    )
    record = next(x for x in result["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert record["pinned_feed_identity_conflict_hold"] is True
    assert record["candidates"] == []
    assert result["approved_new_images"] == 0


@pytest.mark.parametrize(
    "title",
    [
        "Other Essential Bois Imperial EDP 100 ml",
        "Essential Bois Imperial EDP 100 ml Intense",
        "Essential Parfums Bois Imperial 100 ml",
        "Essential Parfums Bois Imperial Elixir 100 ml",
    ],
)
def test_incomplete_brand_or_concentration_is_not_an_exact_lead(title: str) -> None:
    assert not feed_name_matches(GAP["items"][0], {"product_name": title})


def test_full_brand_and_gender_and_numbered_editions_remain_distinct() -> None:
    item = {
        "brand": "Parfums de Marly",
        "name": "Scent Pour Homme II",
        "concentration": "EDP",
        "volume_ml": 100,
    }
    assert feed_name_matches(
        item, {"product_name": "Parfums de Marly Scent Pour Homme II EDP 100 ml"}
    )
    for title in [
        "Marly Scent Pour Homme II EDP 100 ml",
        "Parfums de Marly Scent Pour Femme II EDP 100 ml",
        "Parfums de Marly Scent Pour Homme III EDP 100 ml",
    ]:
        assert not feed_name_matches(item, {"product_name": title})


def test_observed_bois_perfumer_credit_is_bounded_to_the_exact_product() -> None:
    title = "ESSENTIAL PARFUMS BOIS IMPERIAL by Quentin Bisch EdP Nat. Spray (nachfüllbar)"
    result = run([row("924719", title, PHOTO_BOIS, gtin="3770010614630")])
    candidate = next(x for x in result["items"] if x["product_id"].endswith("IMPERIAL-100"))
    assert len(candidate["candidates"]) == 1
    assert candidate["candidates"][0]["feed_explicit_size_match"] is False
    assert result["approved_new_images"] == 0
    for suffix in [" Extrait", " Flüssigseife", " Reisegröße", " Refill", " 100 ml + 10 ml"]:
        assert not feed_name_matches(GAP["items"][0], {"product_name": title + suffix})
    assert not feed_name_matches(
        {**GAP["items"][0], "product_id": "ANOTHER-PRODUCT"}, {"product_name": title}
    )


def test_observed_armani_brand_alias_does_not_erase_flankers() -> None:
    item = {
        "brand": "Giorgio Armani",
        "name": "Stronger With You Intensely",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
    }
    title = "Giorgio Armani Emporio Armani Stronger with You Intensely EdP Nat. Spray"
    assert feed_name_matches(item, {"product_name": title})
    assert not feed_name_matches(item, {"product_name": title.replace("Intensely", "Absolutely")})
    assert not feed_name_matches(item, {"product_name": title + " Parfum"})
