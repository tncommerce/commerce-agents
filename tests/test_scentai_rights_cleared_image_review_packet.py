from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.build_scentai_rights_cleared_image_review_packet import review_packet

PLAN = Path("examples/retail/data/dufynd_release01_image_acquisition_plan.json")


def staging_payload() -> dict:
    return {
        "products": [
            {
                "product_id": "SC-B-100",
                "candidate_id": "B-100",
                "brand": "Brand B",
                "name": "Fragrance B",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
            },
            {
                "product_id": "SC-A-50",
                "candidate_id": "A-50",
                "brand": "Brand A",
                "name": "Fragrance A",
                "concentration": "Eau de Toilette",
                "volume_ml": 50,
            },
        ]
    }


def candidate(
    product_id: str,
    *,
    brand: str,
    name: str,
    concentration: str,
    volume_ml: int,
    review_status: str = "pending_review",
) -> dict:
    return {
        "product_id": product_id,
        "brand": brand,
        "name": name,
        "concentration": concentration,
        "volume_ml": volume_ml,
        "image_url": f"/products/{product_id}.jpg",
        "review_status": review_status,
        "source_class": "dufynd_owned_original_photography",
        "proposed_image_status": "approved_licensed_image",
        "exact_variant_verified": True,
        "registered_at": "2026-09-27T15:00:00+00:00",
        "evidence_note": "DUFYND-owned exact-bottle photo.",
        "rights_evidence": {
            "rights_basis_id": f"owned-photo-{product_id}",
            "rights_status": "verified_for_publisher_service",
            "rights_checked_at": "2026-09-27",
            "commercial_use_allowed": True,
            "public_distribution_allowed": True,
        },
    }


def payload(*rows: dict) -> dict:
    return {
        "version": 1,
        "status": "review_only_not_live",
        "candidates": list(rows),
    }


def test_empty_queue_produces_no_pending_review_packet() -> None:
    packet = review_packet(staging_payload(), payload())

    assert packet["status"] == "no_pending_review_candidates"
    assert packet["pending_review_count"] == 0
    assert packet["automatic_approval_allowed"] is False
    assert packet["items"] == []


def test_packet_contains_only_pending_candidates_in_deterministic_order() -> None:
    packet = review_packet(
        staging_payload(),
        payload(
            candidate(
                "SC-B-100",
                brand="Brand B",
                name="Fragrance B",
                concentration="Eau de Parfum",
                volume_ml=100,
            ),
            candidate(
                "SC-A-50",
                brand="Brand A",
                name="Fragrance A",
                concentration="Eau de Toilette",
                volume_ml=50,
            ),
            candidate(
                "SC-A-50",
                brand="Brand A",
                name="Fragrance A",
                concentration="Eau de Toilette",
                volume_ml=50,
                review_status="approved",
            ),
        ),
    )

    assert packet["status"] == "pending_visual_review"
    assert packet["pending_review_count"] == 2
    assert [row["product_id"] for row in packet["items"]] == [
        "SC-A-50",
        "SC-B-100",
    ]
    assert all(row["approval_action_class"] == "approval_required" for row in packet["items"])
    assert all(row["next_action"] == "human_visual_review" for row in packet["items"])


@pytest.mark.parametrize(
    ("field", "bad_value", "error"),
    [
        ("brand", "Wrong Brand", "candidate_identity_mismatch:SC-A-50:brand"),
        ("name", "Wrong Name", "candidate_identity_mismatch:SC-A-50:name"),
        (
            "concentration",
            "Parfum",
            "candidate_identity_mismatch:SC-A-50:concentration",
        ),
        ("volume_ml", 100, "candidate_identity_mismatch:SC-A-50:volume_ml"),
    ],
)
def test_packet_rejects_identity_mismatch(
    field: str,
    bad_value: object,
    error: str,
) -> None:
    row = candidate(
        "SC-A-50",
        brand="Brand A",
        name="Fragrance A",
        concentration="Eau de Toilette",
        volume_ml=50,
    )
    row[field] = bad_value

    with pytest.raises(ValueError, match=error):
        review_packet(staging_payload(), payload(row))


def test_packet_rejects_incomplete_or_unverified_rights() -> None:
    row = candidate(
        "SC-A-50",
        brand="Brand A",
        name="Fragrance A",
        concentration="Eau de Toilette",
        volume_ml=50,
    )
    row["rights_evidence"]["commercial_use_allowed"] = False

    with pytest.raises(ValueError, match="candidate_commercial_use_not_allowed:SC-A-50"):
        review_packet(staging_payload(), payload(row))


def test_release01_plan_exposes_review_packet_command() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    intake = plan["rights_cleared_intake"]

    assert intake["review_packet_command"] == (
        "python -m scripts.build_scentai_rights_cleared_image_review_packet"
    )
    assert intake["final_approval_action_class"] == "approval_required"
