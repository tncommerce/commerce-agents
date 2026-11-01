"""Bound private Awin DE product review to current public release approvals."""

from __future__ import annotations

import copy
import json

import pytest
from scripts import review_dufynd_perfumetrader_catalog as review


@pytest.fixture
def sources() -> tuple[dict, dict, dict, dict]:
    return (
        json.loads(review.CATALOG.read_text(encoding="utf-8")),
        json.loads(review.RELEASED.read_text(encoding="utf-8")),
        json.loads(review.AUTHORIZATIONS.read_text(encoding="utf-8")),
        json.loads(review.PRIVATE_WAVE2.read_text(encoding="utf-8")),
    )


def test_57_review_scope_is_exact_37_plus_20_without_wave_two(
    sources: tuple[dict, dict, dict, dict],
) -> None:
    catalog, released, authorizations, held = sources
    profiles = review.public_profiles(*sources)
    original_ids = {
        p["product_id"]
        for p in catalog["products"]
        if p.get("validation", {}).get("catalog_ready") is True
        and not any(str(v).strip() for v in p.get("validation", {}).get("blockers", []))
    }
    released_ids = {p["product_id"] for p in released["profiles"]}
    held_ids = {p["product_id"] for p in held["profiles"]}
    assert len(original_ids) == 37
    assert len(released_ids) == 20
    assert len(held_ids) == 21
    assert {p["product_id"] for p in profiles} == original_ids | released_ids
    assert not {p["product_id"] for p in profiles} & held_ids
    assert {p["product_id"] for p in authorizations["approvals"]} == released_ids


@pytest.mark.parametrize(
    "change",
    [
        "approval_disabled",
        "wrong_size",
        "path_mismatch",
        "duplicate_id",
        "missing_approval",
        "released_id_overlap",
        "unexpected_publication",
        "unexpected_indexing",
        "scope_status_changed",
        "missing_original",
    ],
)
def test_any_release_or_identity_drift_fails_closed(
    sources: tuple[dict, dict, dict, dict], change: str
) -> None:
    catalog, released, authorizations, held = copy.deepcopy(sources)
    if change == "approval_disabled":
        authorizations["approvals"][0]["publication_approved"] = False
    elif change == "wrong_size":
        released["profiles"][0]["volume_ml"] = 0
    elif change == "path_mismatch":
        released["profiles"][0]["seo"]["public_path"] = "/duft/not-approved"
    elif change == "duplicate_id":
        released["profiles"][1]["product_id"] = released["profiles"][0]["product_id"]
    elif change == "missing_approval":
        authorizations["approvals"].pop()
    elif change == "released_id_overlap":
        held["profiles"][0]["product_id"] = released["profiles"][0]["product_id"]
    elif change == "unexpected_publication":
        held["profiles"][0]["publication_authorized"] = True
    elif change == "unexpected_indexing":
        held["profiles"][0]["indexing_approved"] = True
    elif change == "scope_status_changed":
        held["status"] = "PUBLISHED"
    elif change == "missing_original":
        catalog["products"] = [
            p for p in catalog["products"]
            if p["product_id"] != "SC-RABANNE-1-MILLION-EDT-100"
        ]
    with pytest.raises(ValueError):
        review.public_profiles(catalog, released, authorizations, held)


def test_encrypted_feed_review_safely_holds_all_products_without_schema(
    sources: tuple[dict, dict, dict, dict]
) -> None:
    profiles = review.public_profiles(*sources)
    metadata = {
        "advertiser_id": review.ADVERTISER,
        "feed_id": review.FEED,
        "joined": True,
        "primary_region": "DE",
        "language": "German",
    }
    report = review.review_rows(
        profiles,
        {"mappings": []},
        [],
        metadata,
        "synthetic-only-test-secret",
        review.datetime(2026, 11, 1, tzinfo=review.UTC),
    )
    assert len(report["profiles"]) == 57
    assert {p["status"] for p in report["profiles"]} == {"BLOCKED"}
    assert not report["offer_activation_allowed"]
    assert not report["image_publication_allowed"]
    assert report["affiliate_clicks"] == 0
    assert not report["raw_feed_exported"]
