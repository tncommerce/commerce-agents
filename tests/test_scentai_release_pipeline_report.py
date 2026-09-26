from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.report_scentai_release_pipeline import (
    build_release_pipeline_report,
)

NOW = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)


def staged_product() -> dict:
    return {
        "product_id": "SC-TEST-100",
        "candidate_id": "TEST",
        "brand": "Test",
        "name": "Test",
        "classification": {"target_groups": ["unisex"]},
        "fragrance_profile": {
            "recommendation_profile": {
                "scores": {
                    "freshness": 5,
                    "sweetness": 5,
                    "woodiness": 5,
                    "spiciness": 5,
                }
            }
        },
        "community": {
            "rating_10": 8.0,
            "rating_count": 100,
            "provisional": False,
        },
        "media": {
            "image_url": "/products/test.png",
            "image_status": "approved_feed_image",
        },
    }


def current_offer() -> dict:
    return {
        "product_id": "SC-TEST-100",
        "merchant_name": "Merchant",
        "price": 50.0,
        "currency": "EUR",
        "shipping_cost": 0.0,
        "in_stock": True,
        "product_url": "https://example.test/product",
        "affiliate_url": "https://example.test/click",
        "last_updated_at": "2026-09-19T09:00:00Z",
    }


def write_manifest(
    path: Path,
    *,
    write_enabled: bool,
) -> tuple[Path, dict]:
    payload = {
        "release_id": "SCENTAI-TEST-RELEASE",
        "product_ids": ["SC-TEST-100"],
        "write_enabled": write_enabled,
    }
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return path, payload


def mappings() -> dict:
    return {
        "mappings": [
            {
                "product_id": "SC-TEST-100",
                "merchant": "merchant-a",
                "merchant_product_id": "A-1",
                "ean": "1234567890123",
                "gtin": "1234567890123",
            },
            {
                "product_id": "SC-TEST-100",
                "merchant": "merchant-b",
                "merchant_product_id": "B-1",
                "ean": "1234567890123",
                "gtin": "1234567890123",
            },
        ]
    }


def test_pipeline_distinguishes_product_ready_from_write_ready(
    tmp_path: Path,
) -> None:
    release = write_manifest(
        tmp_path / "release.json",
        write_enabled=False,
    )

    report = build_release_pipeline_report(
        [release],
        {"products": [staged_product()]},
        {"offers": [current_offer()]},
        mappings(),
        now=NOW,
    )

    row = report["releases"][0]
    assert row["all_products_ready"] is True
    assert row["purchase_offer_product_count"] == 1
    assert row["write_enabled"] is False
    assert row["write_ready"] is False
    assert "manifest_write_locked" in row["release_blockers"]


def test_pipeline_marks_missing_mapping_as_blocker(
    tmp_path: Path,
) -> None:
    release = write_manifest(
        tmp_path / "release.json",
        write_enabled=True,
    )

    report = build_release_pipeline_report(
        [release],
        {"products": [staged_product()]},
        {"offers": [current_offer()]},
        {"mappings": []},
        now=NOW,
    )

    product = report["releases"][0]["products"][0]
    assert product["ready"] is False
    assert "missing_merchant_mapping" in product["blockers"]
    assert "missing_gtin_fallback" in product["blockers"]


def test_pipeline_counts_mapped_staging_products_once(
    tmp_path: Path,
) -> None:
    release = write_manifest(
        tmp_path / "release.json",
        write_enabled=True,
    )

    report = build_release_pipeline_report(
        [release],
        {"products": [staged_product()]},
        {"offers": [current_offer()]},
        mappings(),
        now=NOW,
    )

    assert report["mapped_staged_product_count"] == 1
    assert report["unmapped_staged_product_count"] == 0
