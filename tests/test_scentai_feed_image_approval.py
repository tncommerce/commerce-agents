from __future__ import annotations

import pytest
from scripts.approve_scentai_feed_image import (
    apply_approval,
    approval_plan,
)

PRODUCT_ID = "SC-TEST-100"
IMAGE_URL = "https://cdn.example.com/test.jpg"


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
    data_source="approved-affiliate-feed",
    network="Awin",
    merchant_id="perfumetrader",
) -> dict:
    return {
        "status": "review_only_not_live",
        "candidates": [
            {
                "product_id": PRODUCT_ID,
                "image_url": IMAGE_URL,
                "review_status": review_status,
                "proposed_image_status": "approved_feed_image",
                "data_source": data_source,
                "network": network,
                "merchant_id": merchant_id,
                "merchant": merchant_id,
            }
        ],
    }


def rights_registry(
    *,
    program_status="approved",
    rights_status="verified_for_publisher_service",
    network="Awin",
    merchant_id="perfumetrader",
) -> dict:
    return {
        "required_candidate_data_source": "approved-affiliate-feed",
        "verified_status": "verified_for_publisher_service",
        "entries": [
            {
                "rights_basis_id": "awin_perfumetrader_feed_materials_20260922",
                "network": network,
                "merchant_id": merchant_id,
                "program_status": program_status,
                "rights_status": rights_status,
                "checked_at": "2026-09-22",
                "publisher_scope": "dufynd_owned_publisher_service",
                "asset_scope": (
                    "unaltered_advertiser_materials_from_official_awin_product_feed"
                ),
            }
        ],
    }


def plan_for(
    staging=None,
    candidates=None,
    rights=None,
    *,
    image_url=IMAGE_URL,
    replace_approved_image=False,
) -> dict:
    return approval_plan(
        staging or staging_payload(),
        candidates or candidates_payload(),
        product_id=PRODUCT_ID,
        image_url=image_url,
        rights_registry=rights if rights is not None else rights_registry(),
        replace_approved_image=replace_approved_image,
    )


def test_pending_candidate_can_be_approved_with_verified_rights() -> None:
    plan = plan_for()

    assert plan["will_change"] is True
    assert plan["already_approved"] is False
    assert plan["rights_status"] == "verified_for_publisher_service"
    assert plan["rights_basis_id"] == (
        "awin_perfumetrader_feed_materials_20260922"
    )


def test_unknown_candidate_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="review_candidate_not_found",
    ):
        plan_for(image_url="https://cdn.example.com/other.jpg")


def test_existing_approved_image_requires_explicit_replace() -> None:
    with pytest.raises(
        ValueError,
        match="approved_image_already_exists_use_replace_flag",
    ):
        plan_for(
            staging=staging_payload(
                image_url="https://cdn.example.com/current.jpg",
                image_status="approved_feed_image",
            )
        )


def test_explicit_replace_allows_new_reviewed_image() -> None:
    plan = plan_for(
        staging=staging_payload(
            image_url="https://cdn.example.com/current.jpg",
            image_status="approved_feed_image",
        ),
        replace_approved_image=True,
    )

    assert plan["will_change"] is True


def test_apply_approval_persists_rights_evidence() -> None:
    staging = staging_payload()
    candidates = candidates_payload()

    apply_approval(
        staging,
        candidates,
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
        reviewed_at="2026-09-18T20:00:00+00:00",
        rights_basis_id="awin_perfumetrader_feed_materials_20260922",
        rights_checked_at="2026-09-22",
    )

    media = staging["products"][0]["media"]
    assert media["image_url"] == IMAGE_URL
    assert media["image_status"] == "approved_feed_image"
    assert media["image_reviewed_at"] == "2026-09-18T20:00:00+00:00"
    assert media["image_rights_basis_id"] == (
        "awin_perfumetrader_feed_materials_20260922"
    )
    assert media["image_rights_checked_at"] == "2026-09-22"

    candidate = candidates["candidates"][0]
    assert candidate["review_status"] == "approved"
    assert candidate["reviewed_at"] == "2026-09-18T20:00:00+00:00"
    assert candidate["rights_status"] == "verified_for_publisher_service"


def test_same_approved_image_is_idempotent() -> None:
    plan = plan_for(
        staging=staging_payload(
            image_url=IMAGE_URL,
            image_status="approved_feed_image",
        ),
        candidates=candidates_payload(review_status="approved"),
    )

    assert plan["already_approved"] is True
    assert plan["will_change"] is False


def test_non_http_image_url_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="image_url_must_be_http_or_https",
    ):
        plan_for(image_url="javascript:alert(1)")


def test_candidate_payload_must_remain_review_only() -> None:
    payload = candidates_payload()
    payload["status"] = "live"

    with pytest.raises(
        ValueError,
        match="candidate_payload_not_review_only",
    ):
        plan_for(candidates=payload)


def test_candidate_requires_explicit_feed_image_proposal() -> None:
    payload = candidates_payload()
    payload["candidates"][0].pop("proposed_image_status")

    with pytest.raises(
        ValueError,
        match="candidate_missing_approved_feed_image_proposal",
    ):
        plan_for(candidates=payload)


def test_candidate_requires_rights_registry() -> None:
    with pytest.raises(
        ValueError,
        match="candidate_rights_not_verified",
    ):
        approval_plan(
            staging_payload(),
            candidates_payload(),
            product_id=PRODUCT_ID,
            image_url=IMAGE_URL,
            rights_registry=None,
        )


def test_candidate_must_come_from_approved_affiliate_feed() -> None:
    with pytest.raises(
        ValueError,
        match="candidate_not_from_approved_affiliate_feed",
    ):
        plan_for(
            candidates=candidates_payload(
                data_source="public-product-page",
            )
        )


def test_candidate_rights_require_approved_program() -> None:
    with pytest.raises(
        ValueError,
        match="candidate_affiliate_program_not_approved",
    ):
        plan_for(rights=rights_registry(program_status="applied"))


def test_candidate_rights_require_network_and_merchant_match() -> None:
    with pytest.raises(
        ValueError,
        match="candidate_rights_not_verified",
    ):
        plan_for(rights=rights_registry(merchant_id="other-merchant"))


def test_candidate_rights_status_must_be_verified() -> None:
    with pytest.raises(
        ValueError,
        match="candidate_rights_not_verified",
    ):
        plan_for(rights=rights_registry(rights_status="pending"))
