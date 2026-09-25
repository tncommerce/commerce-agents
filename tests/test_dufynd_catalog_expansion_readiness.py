from __future__ import annotations

from collections import Counter

from scripts.report_dufynd_catalog_expansion_readiness import (
    audience_gap_score,
    build_expansion_readiness,
)


def _live_catalog() -> dict:
    return {
        "products": [
            {
                "product_id": "SC-LIVE-MEN-1",
                "category": "fragrance",
                "in_stock": True,
                "attributes": {"target_group": "men"},
            },
            {
                "product_id": "SC-LIVE-MEN-2",
                "category": "fragrance",
                "in_stock": True,
                "attributes": {"target_group": "men"},
            },
            {
                "product_id": "SC-LIVE-WOMEN-1",
                "category": "fragrance",
                "in_stock": True,
                "attributes": {"target_group": "women"},
            },
        ]
    }


def _candidate(
    product_id: str,
    *,
    target_groups: list[str],
    priority: int,
    blockers: list[str],
) -> dict:
    return {
        "priority": priority,
        "product_id": product_id,
        "brand": "Test Brand",
        "name": product_id,
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "target_groups": target_groups,
        "variant_status": "verified_retail_variant",
        "research_state": "official_profile_verified_merchant_evidence_added",
        "evidence": [{"source": "brand", "url": "https://example.com/product"}],
        "product_data": {
            "scent_family": "floral woody",
            "key_notes": ["rose", "cedar"],
            "source_confidence": "high",
            "source_kind": "official_brand",
            "source_url": "https://example.com/product",
        },
        "research_merchant_evidence": [
            {
                "merchant": "merchant-a",
                "url": "https://merchant.example/product",
                "affiliate_state": "application_pending",
            }
        ],
        "validation": {
            "catalog_ready": False,
            "blockers": blockers,
        },
    }


def test_audience_gap_score_favors_underrepresented_live_audience() -> None:
    counts = Counter({"men": 10, "women": 2, "unisex": 5})

    assert audience_gap_score(["women"], counts) == 8.0
    assert audience_gap_score(["men"], counts) == 0.0


def test_expansion_readiness_separates_staging_from_live_blockers() -> None:
    image_and_affiliate_only = _candidate(
        "SC-WOMEN-READY-100",
        target_groups=["women"],
        priority=1,
        blockers=[
            "canonical_gtin_feed_match_pending",
            "verified_affiliate_offer_pending",
            "approved_product_image_pending",
        ],
    )
    source_conflict = _candidate(
        "SC-MEN-BLOCKED-100",
        target_groups=["men"],
        priority=2,
        blockers=[
            "verified_affiliate_offer_pending",
            "approved_product_image_pending",
            "direct_source_or_feed_confirmation_pending",
        ],
    )

    report = build_expansion_readiness(
        {"wave_id": "TEST", "candidates": [source_conflict, image_and_affiliate_only]},
        _live_catalog(),
        {"products": []},
        staging_batch_limit=5,
    )

    assert report["staging_ready_count"] == 1
    assert report["live_ready_count"] == 0
    assert report["recommended_staging_batch"][0]["product_id"] == "SC-WOMEN-READY-100"
    assert report["recommended_staging_batch"][0]["staging_ready"] is True
    assert (
        "approved_product_image_pending" in report["recommended_staging_batch"][0]["live_blockers"]
    )

    blocked = next(row for row in report["rows"] if row["product_id"] == "SC-MEN-BLOCKED-100")
    assert blocked["staging_ready"] is False
    assert "direct_source_or_feed_confirmation_pending" in blocked["staging_blockers"]


def test_expansion_readiness_never_readds_live_or_staged_product() -> None:
    row = _candidate(
        "SC-DUPLICATE-100",
        target_groups=["women"],
        priority=1,
        blockers=["approved_product_image_pending"],
    )

    live = _live_catalog()
    live["products"].append(
        {
            "product_id": "SC-DUPLICATE-100",
            "category": "fragrance",
            "in_stock": True,
            "attributes": {"target_group": "women"},
        }
    )

    report = build_expansion_readiness(
        {"wave_id": "TEST", "candidates": [row]},
        live,
        {"products": []},
    )

    assert report["staging_ready_count"] == 0
    assert "already_live" in report["rows"][0]["staging_blockers"]
