from __future__ import annotations

from scripts.build_scentai_release_pipeline_status import (
    build_release_pipeline_status,
)


def product(product_id: str) -> dict:
    return {
        "product_id": product_id,
        "candidate_id": product_id,
        "brand": "Brand",
        "name": product_id,
        "community": {"provisional": False},
        "media": {
            "image_url": None,
            "image_status": (
                "pending_approved_feed_or_manufacturer_image"
            ),
        },
    }


def test_release_pipeline_keeps_dependency_and_product_gates_separate() -> None:
    releases = [
        {
            "release_id": "SCENTAI-RELEASE-01",
            "product_ids": ["SC-A"],
            "depends_on_release_ids": [],
            "write_enabled": True,
            "status": "prepared",
            "write_policy": "all-or-nothing",
        },
        {
            "release_id": "SCENTAI-RELEASE-02",
            "product_ids": ["SC-B"],
            "depends_on_release_ids": ["SCENTAI-RELEASE-01"],
            "write_enabled": False,
            "status": "prepared",
            "write_policy": "all-or-nothing",
        },
    ]
    staging = {
        "products": [
            product("SC-A"),
            product("SC-B"),
        ]
    }
    mappings = {
        "mappings": [
            {
                "product_id": "SC-A",
                "merchant": "merchant",
                "merchant_product_id": "a",
            },
            {
                "product_id": "SC-B",
                "merchant": "merchant",
                "merchant_product_id": "b",
            },
        ]
    }
    images = {
        "items": [
            {
                "product_id": "SC-A",
                "image_state": "missing",
            },
            {
                "product_id": "SC-B",
                "image_state": "missing",
            },
        ]
    }
    affiliate = {"programs": []}

    status = build_release_pipeline_status(
        releases,
        staging,
        mappings,
        {"offers": []},
        images,
        affiliate,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert status["current_release_id"] == "SCENTAI-RELEASE-01"
    assert status["pipeline_state"] == "blocked_on_current_release"

    release_01, release_02 = status["releases"]
    assert release_01["dependency_state"] == "not_required"
    assert release_02["dependency_state"] == (
        "pending_prior_release_validation"
    )
    assert release_01["summary"]["mapping_ready"] == 1
    assert release_01["summary"]["approved_images"] == 0
    assert release_02["summary"]["mapping_ready"] == 1
