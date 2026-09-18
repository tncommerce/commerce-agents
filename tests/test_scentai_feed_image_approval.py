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
) -> dict:
    return {
        "candidates": [
            {
                "product_id": PRODUCT_ID,
                "image_url": IMAGE_URL,
                "review_status": review_status,
                "approved_image_status": "approved_feed_image",
            }
        ]
    }


def test_pending_candidate_can_be_approved() -> None:
    plan = approval_plan(
        staging_payload(),
        candidates_payload(),
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
    )

    assert plan["will_change"] is True
    assert plan["already_approved"] is False


def test_unknown_candidate_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="review_candidate_not_found",
    ):
        approval_plan(
            staging_payload(),
            candidates_payload(),
            product_id=PRODUCT_ID,
            image_url="https://cdn.example.com/other.jpg",
        )


def test_existing_approved_image_requires_explicit_replace() -> None:
    with pytest.raises(
        ValueError,
        match="approved_image_already_exists_use_replace_flag",
    ):
        approval_plan(
            staging_payload(
                image_url="https://cdn.example.com/current.jpg",
                image_status="approved_feed_image",
            ),
            candidates_payload(),
            product_id=PRODUCT_ID,
            image_url=IMAGE_URL,
        )


def test_explicit_replace_allows_new_reviewed_image() -> None:
    plan = approval_plan(
        staging_payload(
            image_url="https://cdn.example.com/current.jpg",
            image_status="approved_feed_image",
        ),
        candidates_payload(),
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
        replace_approved_image=True,
    )

    assert plan["will_change"] is True


def test_apply_approval_updates_staging_and_candidate() -> None:
    staging = staging_payload()
    candidates = candidates_payload()

    apply_approval(
        staging,
        candidates,
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
        reviewed_at="2026-09-18T20:00:00+00:00",
    )

    media = staging["products"][0]["media"]
    assert media["image_url"] == IMAGE_URL
    assert media["image_status"] == "approved_feed_image"
    assert media["image_reviewed_at"] == (
        "2026-09-18T20:00:00+00:00"
    )

    candidate = candidates["candidates"][0]
    assert candidate["review_status"] == "approved"
    assert candidate["reviewed_at"] == (
        "2026-09-18T20:00:00+00:00"
    )


def test_same_approved_image_is_idempotent() -> None:
    plan = approval_plan(
        staging_payload(
            image_url=IMAGE_URL,
            image_status="approved_feed_image",
        ),
        candidates_payload(
            review_status="approved",
        ),
        product_id=PRODUCT_ID,
        image_url=IMAGE_URL,
    )

    assert plan["already_approved"] is True
    assert plan["will_change"] is False
