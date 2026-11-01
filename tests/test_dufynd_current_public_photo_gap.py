"""Dynamic 57-page photo-gap inventory must never approve images or offers."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.build_dufynd_current_public_photo_gap import (
    DATA,
    LEGACY,
    WEB,
    build_gap,
)
from scripts.report_dufynd_public_photo_feed_leads import create_review

ROOT = Path(__file__).resolve().parents[1]


def inputs() -> list:
    paths = [
        DATA / "catalog.json",
        DATA / "scentai_products.json",
        WEB / "released-profiles.json",
        DATA / "dufynd_release_authorizations.json",
        WEB / "original-photos.json",
        DATA / "dufynd_facts_wave_02_review.json",
        LEGACY,
    ]
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def test_current_public_snapshot_is_57_minus_10_and_never_reuses_old_33_count() -> None:
    data = inputs()
    gap = build_gap(*data)
    assert gap["status"] == "RIGHTS_SOURCE_ACQUISITION_PENDING_NO_AUTO_APPROVAL"
    assert gap["public_fragrances"] == 57
    assert gap["original_catalog_fragrances"] == 37
    assert gap["owner_released_fact_profiles"] == 20
    assert gap["unpublished_private_wave_two"] == 21
    assert gap["approved_original_photo_variants"] == 10
    assert gap["public_without_photo"] == 47
    assert len(gap["items"]) == 47
    assert len({item["product_id"] for item in gap["items"]}) == 47
    released = {x["product_id"] for x in data[2]["profiles"]}
    held = {x["product_id"] for x in data[5]["profiles"]}
    assert released.issubset({x["product_id"] for x in gap["items"]})
    assert not held.intersection(x["product_id"] for x in gap["items"])
    assert gap["priority_first8_ids"] == data[6]["priority_first8_ids"]
    assert [row["product_id"] for row in gap["items"][:8]] == gap["priority_first8_ids"]
    assert gap["separate_hidden_variants"] == [
        {
            "product_id": "SC-WIDIAN-LONDON-EXTRAIT-50",
            "reason": ["identity_concentration_review_required"],
        }
    ]
    assert "20261011.json" in gap["historical_snapshot_used_for_priority_and_policy"]
    assert gap["new_images_approved"] == 0
    assert gap["merchant_offers_activated"] == 0


def test_review_targets_have_only_existing_exact_product_facts_and_no_sale_claims() -> None:
    gap = build_gap(*inputs())
    assert all(
        row["source_state"] == "NO_EXACT_APPROVED_PHOTO"
        and row["visual_publish_go"] is False
        and row["merchant_offer_activation_go"] is False
        and row["volume_ml"] > 0
        and row["concentration"]
        and row["brand"]
        and row["name"]
        for row in gap["items"]
    )
    serialized = json.dumps(gap).lower()
    for forbidden in (
        "affiliate_url",
        "aw_deep_link",
        "merchant_image_url",
        "search_price",
        "in_stock",
        "merchant_clickout",
        "approved_image_url",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda values: values[3]["approvals"].pop(), "released_approval_set_mismatch"),
        (
            lambda values: values[3]["approvals"][0].update({"publication_approved": False}),
            "unverified_public_release",
        ),
        (
            lambda values: values[2]["profiles"][0].update({"indexing_approved": False}),
            "unverified_public_release",
        ),
        (
            lambda values: values[4][0].update({"volume_ml": 50}),
            "registered_photo_lacks_exact_source_truth",
        ),
        (
            lambda values: values[4][0].update({"url": "https://unapproved.example/image.png"}),
            "registered_photo_lacks_exact_source_truth",
        ),
        (
            lambda values: values[5]["profiles"].append(values[2]["profiles"][0]),
            "private_wave_two_entered_public_catalog",
        ),
    ],
)
def test_identity_rights_and_publication_drift_fails_closed(mutate, match) -> None:
    values = deepcopy(inputs())
    mutate(values)
    with pytest.raises(ValueError, match=match):
        build_gap(*values)


def test_existing_review_feed_parser_accepts_generated_gap_without_promoting() -> None:
    gap = build_gap(*inputs())
    metadata = {
        "source": "awin_product_feed_list",
        "advertiser_id": "31081",
        "feed_id": "91379",
        "joined": True,
        "downloaded": True,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    rights = {
        "entries": [
            {
                "merchant_id": "top-parfuemerie",
                "advertiser_id": "31081",
                "rights_basis_id": "awin_top_parfuemerie_feed_materials_20260928",
                "program_status": "approved",
                "rights_status": "verified_for_publisher_service",
                "asset_scope": "unaltered_advertiser_materials_from_official_awin_product_feed",
            }
        ]
    }
    # Empty current feed fixture: the exact authorized public scope is still
    # 47 gaps and cannot silently become approved images or a shopping link.
    report = create_review(gap, {"mappings": []}, [], metadata, rights)
    assert report["products_reviewed"] == 47
    assert report["total_review_candidates"] == 0
    assert report["approved_new_images"] == 0
    assert report["automated_registration_allowed"] is False
    assert report["product_offer_activation_allowed"] is False
    assert report["merchant_links_included"] is False


def test_cli_writes_review_only_evidence_from_current_registry(tmp_path: Path) -> None:
    out = tmp_path / "photo-gap.json"
    cmd = [
        sys.executable,
        str(ROOT / "scripts/build_dufynd_current_public_photo_gap.py"),
        "--output",
        str(out),
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr + run.stdout
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["public_fragrances"] == 57
    assert result["public_without_photo"] == 47
    assert result["approved_original_photo_variants"] == 10
    assert result["source_commit"] in ("",) or len(result["source_commit"]) == 40
    assert result["generated_at_utc"]


def test_each_image_reviewer_consumes_exact_same_current_gap() -> None:
    text = (ROOT / ".github/workflows/dufynd-awin-feed-revalidation.yml").read_text(
        encoding="utf-8"
    )
    path = "${RUNNER_TEMP}/current-public-photo-gap.json"
    assert text.count("python scripts/prepare_dufynd_catalog_photo_wave.py") == 2
    assert text.count(f'--gaps "{path}"') == 2
    assert text.count(f'--gap "{path}"') == 1
    assert "dufynd-catalog-photo-gap-20261011.json" not in text
    assert text.index("Build current public photo gap") < text.index(
        "Download current top Parfümerie feed"
    )
