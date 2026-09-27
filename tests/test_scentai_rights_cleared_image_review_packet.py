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
    source_class: str = "dufynd_owned_original_photography",
    license_name: str | None = None,
    license_url: str | None = None,
    attribution_text: str | None = None,
    share_alike_required: bool | None = None,
) -> dict:
    return {
        "product_id": product_id,
        "brand": brand,
        "name": name,
        "concentration": concentration,
        "volume_ml": volume_ml,
        "image_url": f"/products/{product_id}.jpg",
        "review_status": review_status,
        "source_class": source_class,
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
            **(
                {
                    "license_name": license_name,
                    "license_url": license_url,
                    "attribution_text": attribution_text,
                    "share_alike_required": share_alike_required,
                }
                if license_name is not None
                or license_url is not None
                or attribution_text is not None
                or share_alike_required is not None
                else {}
            ),
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


def test_packet_surfaces_licensed_provider_attribution_metadata() -> None:
    row = candidate(
        "SC-A-50",
        brand="Brand A",
        name="Fragrance A",
        concentration="Eau de Toilette",
        volume_ml=50,
        source_class="licensed_asset_provider",
        license_name="CC BY-SA 3.0",
        license_url="https://creativecommons.org/licenses/by-sa/3.0/",
        attribution_text="Open Beauty Facts contributors",
        share_alike_required=True,
    )
    packet = review_packet(staging_payload(), payload(row))
    item = packet["items"][0]

    assert item["license_name"] == "CC BY-SA 3.0"
    assert item["license_url"] == "https://creativecommons.org/licenses/by-sa/3.0/"
    assert item["attribution_text"] == "Open Beauty Facts contributors"
    assert item["share_alike_required"] is True

    row["rights_evidence"].pop("attribution_text")
    with pytest.raises(ValueError, match="candidate_license_metadata_incomplete:SC-A-50"):
        review_packet(staging_payload(), payload(row))


def test_release01_plan_exposes_review_packet_command() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    intake = plan["rights_cleared_intake"]

    assert intake["review_packet_command"] == (
        "python -m scripts.build_scentai_rights_cleared_image_review_packet"
    )
    assert intake["final_approval_action_class"] == "approval_required"


def test_current_repo_approved_candidate_is_not_requeued_for_visual_review() -> None:
    data_dir = Path("examples/retail/data")
    staging = json.loads((data_dir / "scentai_catalog_staging.json").read_text(encoding="utf-8"))
    candidates = json.loads(
        (data_dir / "dufynd_rights_cleared_image_candidates.json").read_text(encoding="utf-8")
    )

    packet = review_packet(staging, candidates)

    assert packet["status"] == "no_pending_review_candidates"
    assert packet["pending_review_count"] == 0
    assert packet["automatic_approval_allowed"] is False
    assert packet["items"] == []

    candidate = next(
        row
        for row in candidates["candidates"]
        if row["product_id"] == "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100"
    )
    product = next(
        row for row in staging["products"] if row["product_id"] == candidate["product_id"]
    )
    assert candidate["review_status"] == "approved"
    assert candidate["visual_approval_basis"] == "explicit_user_visual_approval_2026-09-27"
    assert product["media"]["image_url"] == candidate["image_url"]
    assert product["media"]["image_status"] == "approved_licensed_image"
    assert product["media"]["image_license_name"] == "CC BY-SA 3.0"
    assert product["media"]["image_attribution_text"] == "Open Beauty Facts contributors"
    assert product["media"]["image_share_alike_required"] is True
