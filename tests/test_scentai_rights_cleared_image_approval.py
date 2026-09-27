from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.approve_scentai_rights_cleared_image import (
    apply_approval,
    approval_plan,
)

PRODUCT_ID = "SC-TEST-100"
IMAGE_URL = "/products/test-owned.jpg"
STATE_MACHINE = Path("examples/retail/data/scentai_image_approval_state_machine.json")


def staging_payload(
    *,
    image_url=None,
    image_status="pending_approved_feed_or_manufacturer_image",
) -> dict:
    return {
        "products": [
            {
                "product_id": PRODUCT_ID,
                "media": {
                    "image_url": image_url,
                    "image_status": image_status,
                },
            }
        ]
    }


def candidates_payload(
    *,
    review_status="pending_review",
    source_class="dufynd_owned_original_photography",
    proposed_image_status="approved_licensed_image",
    exact_variant_verified=True,
    rights_status="verified_for_publisher_service",
    commercial_use_allowed=True,
    public_distribution_allowed=True,
    license_name=None,
    license_url=None,
    attribution_text=None,
    share_alike_required=None,
) -> dict:
    return {
        "status": "review_only_not_live",
        "candidates": [
            {
                "product_id": PRODUCT_ID,
                "image_url": IMAGE_URL,
                "review_status": review_status,
                "source_class": source_class,
                "proposed_image_status": proposed_image_status,
                "exact_variant_verified": exact_variant_verified,
                "rights_evidence": {
                    "rights_basis_id": "dufynd_owned_photo_test_001",
                    "rights_status": rights_status,
                    "rights_checked_at": "2026-09-27",
                    "commercial_use_allowed": commercial_use_allowed,
                    "public_distribution_allowed": public_distribution_allowed,
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
        ],
    }


def plan_for(
    *,
    staging=None,
    candidates=None,
    image_url=IMAGE_URL,
    replace_approved_image=False,
) -> dict:
    return approval_plan(
        staging or staging_payload(),
        candidates or candidates_payload(),
        product_id=PRODUCT_ID,
        image_url=image_url,
        replace_approved_image=replace_approved_image,
    )


def test_owned_original_can_be_prepared_for_manual_review() -> None:
    plan = plan_for()

    assert plan["source_class"] == "dufynd_owned_original_photography"
    assert plan["proposed_image_status"] == "approved_licensed_image"
    assert plan["candidate_status"] == "pending_review"
    assert plan["rights_status"] == "verified_for_publisher_service"
    assert plan["will_change"] is True


def test_written_manufacturer_permission_uses_manufacturer_status() -> None:
    plan = plan_for(
        candidates=candidates_payload(
            source_class="written_manufacturer_permission",
            proposed_image_status="approved_manufacturer_image",
        )
    )

    assert plan["source_class"] == "written_manufacturer_permission"
    assert plan["proposed_image_status"] == "approved_manufacturer_image"


def test_licensed_provider_requires_attribution_metadata() -> None:
    candidates = candidates_payload(
        source_class="licensed_asset_provider",
        license_name="CC BY-SA 3.0",
        license_url="https://creativecommons.org/licenses/by-sa/3.0/",
        attribution_text="Open Beauty Facts contributors",
        share_alike_required=True,
    )
    plan = plan_for(candidates=candidates)

    assert plan["license_name"] == "CC BY-SA 3.0"
    assert plan["license_url"] == "https://creativecommons.org/licenses/by-sa/3.0/"
    assert plan["attribution_text"] == "Open Beauty Facts contributors"
    assert plan["share_alike_required"] is True

    with pytest.raises(ValueError, match="candidate_license_metadata_incomplete"):
        plan_for(candidates=candidates_payload(source_class="licensed_asset_provider"))


def test_unknown_candidate_is_rejected() -> None:
    with pytest.raises(ValueError, match="review_candidate_not_found"):
        plan_for(image_url="/products/other.jpg")


def test_candidate_requires_exact_variant_verification() -> None:
    with pytest.raises(ValueError, match="candidate_exact_variant_not_verified"):
        plan_for(candidates=candidates_payload(exact_variant_verified=False))


def test_candidate_source_class_must_be_approvable() -> None:
    with pytest.raises(ValueError, match="candidate_source_class_not_approvable"):
        plan_for(candidates=candidates_payload(source_class="public_product_page"))


def test_rights_must_allow_commercial_public_use() -> None:
    with pytest.raises(ValueError, match="candidate_commercial_use_not_allowed"):
        plan_for(candidates=candidates_payload(commercial_use_allowed=False))

    with pytest.raises(ValueError, match="candidate_public_distribution_not_allowed"):
        plan_for(candidates=candidates_payload(public_distribution_allowed=False))


def test_rights_status_must_be_verified() -> None:
    with pytest.raises(ValueError, match="candidate_rights_not_verified"):
        plan_for(candidates=candidates_payload(rights_status="pending"))


def test_unsafe_image_targets_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="image_target_must_be_https_or_safe_root_relative_path",
    ):
        plan_for(image_url="javascript:alert(1)")

    with pytest.raises(
        ValueError,
        match="image_target_must_be_https_or_safe_root_relative_path",
    ):
        plan_for(image_url="/products/../secret.jpg")


def test_existing_approved_image_requires_explicit_replace() -> None:
    with pytest.raises(
        ValueError,
        match="approved_image_already_exists_use_replace_flag",
    ):
        plan_for(
            staging=staging_payload(
                image_url="/products/current.jpg",
                image_status="approved_licensed_image",
            )
        )


def test_apply_approval_requires_prior_human_visual_approval() -> None:
    with pytest.raises(ValueError, match="final_visual_approval_required"):
        apply_approval(
            staging_payload(),
            candidates_payload(),
            product_id=PRODUCT_ID,
            image_url=IMAGE_URL,
            reviewed_at="2026-09-27T14:30:00+00:00",
            proposed_image_status="approved_licensed_image",
            source_class="dufynd_owned_original_photography",
            rights_basis_id="dufynd_owned_photo_test_001",
            rights_checked_at="2026-09-27",
        )


def test_apply_approval_persists_rights_and_source_metadata() -> None:
    staging = staging_payload()
    candidates = candidates_payload(review_status="approved")

    apply_approval(
        staging,
        candidates,
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
        reviewed_at="2026-09-27T14:30:00+00:00",
        proposed_image_status="approved_licensed_image",
        source_class="dufynd_owned_original_photography",
        rights_basis_id="dufynd_owned_photo_test_001",
        rights_checked_at="2026-09-27",
    )

    media = staging["products"][0]["media"]
    assert media["image_url"] == IMAGE_URL
    assert media["image_status"] == "approved_licensed_image"
    assert media["image_source_class"] == "dufynd_owned_original_photography"
    assert media["image_rights_basis_id"] == "dufynd_owned_photo_test_001"
    assert media["image_rights_checked_at"] == "2026-09-27"

    candidate = candidates["candidates"][0]
    assert candidate["review_status"] == "approved"
    assert candidate["rights_status"] == "verified_for_publisher_service"


def test_apply_approval_persists_licensed_provider_attribution() -> None:
    staging = staging_payload()
    candidates = candidates_payload(
        review_status="approved",
        source_class="licensed_asset_provider",
        license_name="CC BY-SA 3.0",
        license_url="https://creativecommons.org/licenses/by-sa/3.0/",
        attribution_text="Open Beauty Facts contributors",
        share_alike_required=True,
    )

    plan = approval_plan(
        staging,
        candidates,
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
    )
    apply_approval(
        staging,
        candidates,
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
        reviewed_at="2026-09-27T14:30:00+00:00",
        proposed_image_status=plan["proposed_image_status"],
        source_class=plan["source_class"],
        rights_basis_id=plan["rights_basis_id"],
        rights_checked_at=plan["rights_checked_at"],
        license_name=plan["license_name"],
        license_url=plan["license_url"],
        attribution_text=plan["attribution_text"],
        share_alike_required=plan["share_alike_required"],
    )

    media = staging["products"][0]["media"]
    assert media["image_license_name"] == "CC BY-SA 3.0"
    assert media["image_license_url"] == "https://creativecommons.org/licenses/by-sa/3.0/"
    assert media["image_attribution_text"] == "Open Beauty Facts contributors"
    assert media["image_share_alike_required"] is True


def test_state_machine_recognizes_rights_cleared_non_feed_sources() -> None:
    machine = json.loads(STATE_MACHINE.read_text(encoding="utf-8"))
    source_classes = set(machine["candidate_source_classes"])

    assert {
        "dufynd_owned_original_photography",
        "licensed_asset_provider",
        "written_asset_permission",
        "written_manufacturer_permission",
    } <= source_classes
    assert machine["states"]["approved_licensed_image"]["approved"] is True
    assert machine["states"]["approved_manufacturer_image"]["approved"] is True
    assert "rights_cleared_non_feed" in machine["rights_rules"]
