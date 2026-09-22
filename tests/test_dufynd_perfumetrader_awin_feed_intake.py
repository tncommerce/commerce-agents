from __future__ import annotations

from scripts.check_dufynd_perfumetrader_awin_feed import (
    build_perfumetrader_intake_report,
)

from retail.api.merchant_import import MerchantProductMapping
from retail.api.merchant_providers import MappedMerchantFeedAdapter

RELEASE_IDS = [
    "SC-DIOR-HYPNOTIC-POISON-EDT-100",
    "SC-RELEASE-2",
    "SC-RELEASE-3",
    "SC-RELEASE-4",
    "SC-RELEASE-5",
]


def config() -> dict:
    return {
        "provider_name": "awin-perfumetrader-de",
        "field_map": {
            "offer_id": "aw_product_id",
            "merchant_product_id": "merchant_product_id",
            "ean": "ean",
            "gtin": "product_GTIN",
            "price": "search_price",
            "shipping_cost": "delivery_cost",
            "in_stock": "in_stock",
            "variant_label": "product_name",
            "product_url": "merchant_deep_link",
            "affiliate_url": "aw_deep_link",
            "last_updated_at": "last_updated",
            "image_url": "merchant_image_url",
        },
        "constants": {
            "merchant": "perfumetrader",
            "merchant_id": "perfumetrader",
            "merchant_name": "Perfumetrader",
            "currency": "EUR",
            "network": "Awin",
            "data_source": "approved-affiliate-feed",
        },
    }


def adapter() -> MappedMerchantFeedAdapter:
    cfg = config()
    return MappedMerchantFeedAdapter(
        provider_name=cfg["provider_name"],
        field_map=cfg["field_map"],
        constants=cfg["constants"],
    )


def mappings() -> list[MerchantProductMapping]:
    return [
        MerchantProductMapping(
            product_id="SC-DIOR-HYPNOTIC-POISON-EDT-100",
            merchant="perfumetrader",
            merchant_product_id="33204791",
            ean="3348900425309",
            gtin="3348900425309",
        )
    ]


def exact_hypnotic_row() -> dict:
    return {
        "aw_product_id": "AW-33204791",
        "merchant_product_id": "33204791",
        "ean": "3348900425309",
        "product_GTIN": "3348900425309",
        "search_price": "89.95",
        "delivery_cost": "0.00",
        "in_stock": "1",
        "product_name": "Dior Hypnotic Poison Eau de Toilette 100 ml",
        "merchant_deep_link": "https://www.perfumetrader.de/product/33204791",
        "aw_deep_link": "https://www.awin1.com/cread.php?example=1",
        "last_updated": "2026-09-22T07:00:00Z",
        "merchant_image_url": "https://cdn.example.com/hypnotic-poison.jpg",
    }


def test_realistic_row_runs_full_release_dry_run_without_writes() -> None:
    report = build_perfumetrader_intake_report(
        raw_rows=[exact_hypnotic_row()],
        config=config(),
        adapter=adapter(),
        release_product_ids=RELEASE_IDS,
        mappings=mappings(),
    )

    assert report["status"] == "review"
    assert report["writes_performed"] is False
    assert report["schema"]["import_schema_ready"] is True
    assert report["schema"]["missing_required_columns"] == []
    assert report["schema"]["present_identifier_columns"] == [
        "ean",
        "merchant_product_id",
        "product_GTIN",
    ]
    assert report["release"]["release_mapped_product_count"] == 1
    assert report["release"]["release_trackable_offer_product_count"] == 1
    assert report["release"]["release_feed_image_product_count"] == 1


def test_missing_required_price_column_blocks_before_release_mapping() -> None:
    row = exact_hypnotic_row()
    row.pop("search_price")

    report = build_perfumetrader_intake_report(
        raw_rows=[row],
        config=config(),
        adapter=adapter(),
        release_product_ids=RELEASE_IDS,
        mappings=mappings(),
    )

    assert report["status"] == "blocked_schema"
    assert report["release"] is None
    assert report["writes_performed"] is False
    assert "search_price" in report["schema"]["missing_required_columns"]
    assert "required_feed_columns_missing" in report["schema"]["blockers"]


def test_missing_all_identifier_columns_blocks_schema() -> None:
    row = exact_hypnotic_row()
    row.pop("merchant_product_id")
    row.pop("ean")
    row.pop("product_GTIN")

    report = build_perfumetrader_intake_report(
        raw_rows=[row],
        config=config(),
        adapter=adapter(),
        release_product_ids=RELEASE_IDS,
        mappings=mappings(),
    )

    assert report["status"] == "blocked_schema"
    assert report["release"] is None
    assert report["schema"]["present_identifier_columns"] == []
    assert "product_identifier_column_missing" in report["schema"]["blockers"]


def test_missing_image_column_is_reported_but_does_not_fake_schema_failure() -> None:
    row = exact_hypnotic_row()
    row.pop("merchant_image_url")

    report = build_perfumetrader_intake_report(
        raw_rows=[row],
        config=config(),
        adapter=adapter(),
        release_product_ids=RELEASE_IDS,
        mappings=mappings(),
    )

    assert report["status"] == "review"
    assert report["schema"]["import_schema_ready"] is True
    assert report["schema"]["missing_promotion_fields"] == ["image_url"]
    assert report["release"]["release_feed_image_product_count"] == 0


def test_schema_profile_does_not_emit_raw_feed_values() -> None:
    row = exact_hypnotic_row()

    report = build_perfumetrader_intake_report(
        raw_rows=[row],
        config=config(),
        adapter=adapter(),
        release_product_ids=RELEASE_IDS,
        mappings=mappings(),
    )

    profile_text = str(report["profile"])
    assert "33204791" not in profile_text
    assert "awin1.com" not in profile_text
    assert "perfumetrader.de/product" not in profile_text
