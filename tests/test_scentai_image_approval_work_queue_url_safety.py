from __future__ import annotations

import pytest
from scripts.build_scentai_image_approval_work_queue import build_queue

PRODUCT_ID = "SC-TEST-EDP-100"


def staging(*, image_url: str | None = None) -> dict:
    return {
        "products": [
            {
                "product_id": PRODUCT_ID,
                "candidate_id": "TEST-EDP",
                "brand": "Test Brand",
                "name": "Test Fragrance",
                "batch": 1,
                "media": {
                    "image_status": "pending_approved_feed_or_manufacturer_image",
                    "image_url": image_url,
                },
            }
        ]
    }


def releases() -> list[dict]:
    return [
        {
            "release_id": "SCENTAI-RELEASE-TEST",
            "product_ids": [PRODUCT_ID],
            "write_enabled": False,
        }
    ]


def asset_candidates(*, source_page_url: str = "https://brand.example/product") -> dict:
    return {
        "products": [
            {
                "product_id": PRODUCT_ID,
                "image_state": "rights_or_source_check_pending",
                "candidate_source": {
                    "source_class": "manufacturer_official",
                    "source_page_url": source_page_url,
                    "exact_variant_verified": True,
                    "verified_at": "2026-09-28",
                    "evidence_note": "Exact product identity reference.",
                },
            }
        ]
    }


def rights_audit(*, rights_evidence_url: str = "https://brand.example/terms") -> dict:
    return {
        "generated_at": "2026-09-28",
        "products": [
            {
                "product_id": PRODUCT_ID,
                "rights_evidence_status": "official_terms_restrict_commercial_reuse",
                "rights_evidence_url": rights_evidence_url,
                "public_distribution_allowed": False,
                "final_composite_allowed": False,
            }
        ],
    }


def build(**kwargs: object) -> dict:
    return build_queue(
        kwargs.get("staging_payload", staging()),
        releases(),
        generated_at="2026-09-28T14:55:00+00:00",
        asset_candidates=kwargs.get("candidate_payload", asset_candidates()),
        rights_audit=kwargs.get("rights_payload", rights_audit()),
    )


def test_safe_queue_urls_remain_available_for_review() -> None:
    queue = build()
    row = queue["items"][0]

    assert row["candidate_source"]["source_page_url"] == "https://brand.example/product"
    assert row["rights_evidence"]["rights_evidence_url"] == "https://brand.example/terms"


@pytest.mark.parametrize(
    "image_url",
    [
        "/products/test.jpg?token=SECRET",
        "/products/%2e%2e/secret.jpg",
        "https://cdn.example/test.jpg?api_key=SECRET",
    ],
)
def test_queue_rejects_unsafe_current_image_targets_without_echoing_secret(image_url: str) -> None:
    with pytest.raises(ValueError, match=f"current_image_target_invalid:{PRODUCT_ID}") as error:
        build(staging_payload=staging(image_url=image_url))

    assert "SECRET" not in str(error.value)


def test_queue_rejects_secret_bearing_candidate_source_url() -> None:
    with pytest.raises(ValueError, match=f"candidate_source_url_invalid:{PRODUCT_ID}") as error:
        build(candidate_payload=asset_candidates(source_page_url="https://brand.example/product?token=SECRET"))

    assert "SECRET" not in str(error.value)


def test_queue_rejects_secret_bearing_rights_evidence_url() -> None:
    with pytest.raises(ValueError, match=f"rights_evidence_url_invalid:{PRODUCT_ID}") as error:
        build(rights_payload=rights_audit(rights_evidence_url="https://brand.example/terms?api_key=SECRET"))

    assert "SECRET" not in str(error.value)
