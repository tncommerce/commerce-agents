from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.approve_scentai_rights_cleared_image import approval_plan
from scripts.register_scentai_rights_cleared_image import (
    apply_registration,
    registration_plan,
)

PRODUCT_ID = "SC-TEST-100"
IMAGE_URL = "/products/release01/test-owned.jpg"
PLAN = Path("examples/retail/data/dufynd_release01_image_acquisition_plan.json")


def staging_payload() -> dict:
    return {
        "products": [
            {
                "product_id": PRODUCT_ID,
                "candidate_id": "TEST-100",
                "brand": "Test Brand",
                "name": "Test Fragrance",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "media": {
                    "image_url": None,
                    "image_status": "pending_approved_feed_or_manufacturer_image",
                },
            }
        ]
    }


def candidates_payload() -> dict:
    return {
        "version": 1,
        "status": "review_only_not_live",
        "candidates": [],
    }


def plan_for(
    *,
    payload=None,
    source_class="dufynd_owned_original_photography",
    exact_variant_verified=True,
    commercial_use_allowed=True,
    public_distribution_allowed=True,
    license_name=None,
    license_url=None,
    attribution_text=None,
    share_alike_required=None,
) -> dict:
    return registration_plan(
        staging_payload(),
        payload or candidates_payload(),
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
        source_class=source_class,
        rights_basis_id="dufynd-photo-session-001",
        rights_checked_at="2026-09-27",
        exact_variant_verified=exact_variant_verified,
        commercial_use_allowed=commercial_use_allowed,
        public_distribution_allowed=public_distribution_allowed,
        evidence_note="Exact bottle photographed by DUFYND.",
        license_name=license_name,
        license_url=license_url,
        attribution_text=attribution_text,
        share_alike_required=share_alike_required,
    )


def test_owned_original_registers_as_pending_licensed_candidate() -> None:
    plan = plan_for()
    candidate = plan["candidate"]

    assert plan["will_change"] is True
    assert plan["already_registered"] is False
    assert candidate["review_status"] == "pending_review"
    assert candidate["source_class"] == "dufynd_owned_original_photography"
    assert candidate["proposed_image_status"] == "approved_licensed_image"
    assert candidate["exact_variant_verified"] is True
    assert candidate["rights_evidence"]["commercial_use_allowed"] is True
    assert candidate["rights_evidence"]["public_distribution_allowed"] is True


def test_licensed_provider_requires_persisted_attribution_metadata() -> None:
    plan = plan_for(
        source_class="licensed_asset_provider",
        license_name="CC BY-SA 3.0",
        license_url="https://creativecommons.org/licenses/by-sa/3.0/",
        attribution_text="Open Beauty Facts contributors",
        share_alike_required=True,
    )

    rights = plan["candidate"]["rights_evidence"]
    assert rights["license_name"] == "CC BY-SA 3.0"
    assert rights["license_url"] == "https://creativecommons.org/licenses/by-sa/3.0/"
    assert rights["attribution_text"] == "Open Beauty Facts contributors"
    assert rights["share_alike_required"] is True

    with pytest.raises(ValueError, match="candidate_license_metadata_incomplete"):
        plan_for(source_class="licensed_asset_provider")


def test_written_manufacturer_permission_targets_manufacturer_status() -> None:
    plan = plan_for(source_class="written_manufacturer_permission")

    assert plan["candidate"]["proposed_image_status"] == "approved_manufacturer_image"


def test_intake_requires_exact_variant_and_explicit_rights() -> None:

    with pytest.raises(ValueError, match="candidate_exact_variant_not_verified"):
        plan_for(exact_variant_verified=False)

    with pytest.raises(ValueError, match="candidate_commercial_use_not_allowed"):
        plan_for(commercial_use_allowed=False)

    with pytest.raises(ValueError, match="candidate_public_distribution_not_allowed"):
        plan_for(public_distribution_allowed=False)


def test_apply_registration_never_auto_approves_candidate() -> None:
    payload = candidates_payload()
    plan = plan_for(payload=payload)

    apply_registration(
        payload,
        plan,
        registered_at="2026-09-27T15:00:00+00:00",
    )

    candidate = payload["candidates"][0]
    assert candidate["review_status"] == "pending_review"
    assert candidate["registered_at"] == "2026-09-27T15:00:00+00:00"
    assert payload["status"] == "review_only_not_live"


def test_repeated_identical_registration_is_idempotent() -> None:
    payload = candidates_payload()
    first = plan_for(payload=payload)
    apply_registration(
        payload,
        first,
        registered_at="2026-09-27T15:00:00+00:00",
    )

    second = plan_for(payload=payload)

    assert second["already_registered"] is True
    assert second["will_change"] is False


def test_conflicting_existing_candidate_is_rejected() -> None:

    payload = candidates_payload()
    first = plan_for(payload=payload)
    apply_registration(
        payload,
        first,
        registered_at="2026-09-27T15:00:00+00:00",
    )
    payload["candidates"][0]["rights_evidence"]["rights_basis_id"] = "other-basis"

    with pytest.raises(
        ValueError,
        match="existing_candidate_conflicts_with_registration",
    ):
        plan_for(payload=payload)


def test_registered_candidate_is_compatible_with_approval_dry_run() -> None:
    payload = candidates_payload()
    intake = plan_for(payload=payload)
    apply_registration(
        payload,
        intake,
        registered_at="2026-09-27T15:00:00+00:00",
    )

    approval = approval_plan(
        staging_payload(),
        payload,
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
    )

    assert approval["candidate_status"] == "pending_review"
    assert approval["rights_status"] == "verified_for_publisher_service"
    assert approval["will_change"] is True


def test_release01_plan_points_to_rights_cleared_intake_workflow() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    intake = plan["rights_cleared_intake"]

    assert intake["candidate_queue"] == "dufynd_rights_cleared_image_candidates.json"
    assert intake["register_command"] == ("python -m scripts.register_scentai_rights_cleared_image")
    assert intake["approval_command"] == ("python -m scripts.approve_scentai_rights_cleared_image")
    assert intake["registration_state"] == "pending_review_only"
    assert intake["final_approval_action_class"] == "approval_required"
    assert "dufynd_rights_cleared_image_candidates.json" in plan["source_refs"]
