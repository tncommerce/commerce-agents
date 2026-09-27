"""Keep licensed-image acquisition distinct from product identity verification."""

from __future__ import annotations

from scripts.build_scentai_release_gate_status import build_release_gate_status


def test_licensed_source_required_preserves_verified_image_identity() -> None:
    manifest = {
        "release_id": "SCENTAI-RELEASE-TEST",
        "product_ids": ["SC-TEST-100"],
    }
    staging = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "candidate_id": "TEST",
                "brand": "Brand",
                "name": "Test",
                "community": {"provisional": False},
            }
        ]
    }
    mappings = {
        "mappings": [
            {
                "product_id": "SC-TEST-100",
                "merchant": "merchant",
                "merchant_product_id": "merchant-100",
            }
        ]
    }
    images = {
        "items": [
            {
                "product_id": "SC-TEST-100",
                "image_state": "licensed_source_required",
            }
        ]
    }

    status = build_release_gate_status(
        manifest,
        staging,
        mappings,
        {"offers": []},
        images,
        {"programs": []},
        generated_at="2026-09-27T12:00:00+00:00",
    )

    assert status["summary"]["image_identity_source_verified"] == 1
    assert status["summary"]["approved_images"] == 0
    assert status["products"][0]["image_state"] == "licensed_source_required"
    assert status["products"][0]["gates"]["approved_product_image"] is False
