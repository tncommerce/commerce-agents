from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from scripts.build_scentai_catalog_staging import (
    build_staging_payload,
    validate_existing_public_feed_image,
)

DATA = Path("examples/retail/data")


def inputs():
    candidates = json.loads((DATA / "dufynd_approved_feed_image_candidates.json").read_text())
    rights = json.loads((DATA / "dufynd_affiliate_feed_image_rights.json").read_text())
    public = json.loads((DATA / "scentai_products.json").read_text())["products"]
    candidate = next(
        row
        for row in candidates["candidates"]
        if row.get("application_scope") == "existing_public_profile"
    )
    return candidate, candidates, rights, public


def test_public_photo_approvals_leave_staging_and_all_ten_public_originals_unchanged():
    _, candidates, rights, public = inputs()
    before = deepcopy(public)
    updates = [
        row
        for row in candidates["candidates"]
        if row.get("application_scope") == "existing_public_profile"
    ]
    assert len(updates) == 6
    for candidate in updates:
        validate_existing_public_feed_image(candidate, candidates, rights, public)
    assert public == before
    assert build_staging_payload() == json.loads(
        (DATA / "scentai_catalog_staging.json").read_text()
    )
    assert len(candidates["candidates"]) == 9  # nine feed originals plus licensed Lancome
    assert len([p for p in public if not p.get("validation", {}).get("blockers")]) == 37
    assert not {
        "SC-MONTBLANC-EXPLORER-100",
        "SC-CREED-AVENTUS-100",
        "SC-PRADA-LHOMME-100",
        "SC-XERJOFF-NAXOS-100",
    } & {x["product_id"] for x in candidates["candidates"]}


@pytest.mark.parametrize(
    "field,value",
    [
        ("product_id", "SC-UNKNOWN-100"),
        ("volume_ml", 50),
        ("concentration", "Extrait de Parfum"),
        ("brand", "Wrong"),
        ("image_url", "https://www.topparfuemerie.de/media/catalog/product/0/0/wrong.png"),
        ("image_sha256", "0" * 64),
        ("source_feed_download_sha256", "0" * 64),
        ("source_run_id", 1),
        ("feed_checked_at", "2026-10-25T00:00:00Z"),
        ("visual_approval_basis", ""),
    ],
)
def test_public_candidate_identity_bytes_source_and_visual_approval_cannot_drift(field, value):
    candidate, candidates, rights, public = inputs()
    candidate[field] = value
    with pytest.raises(ValueError):
        validate_existing_public_feed_image(candidate, candidates, rights, public)


@pytest.mark.parametrize(
    "field,value",
    [
        ("fidelity_status", "pending_review"),
        ("exact_variant_verified", False),
        ("image_sha256", "0" * 64),
    ],
)
def test_public_visual_must_match_approved_candidate(field, value):
    candidate, candidates, rights, public = inputs()
    product = next(x for x in public if x["product_id"] == candidate["product_id"])
    product["visuals"][0][field] = value
    with pytest.raises(ValueError, match="evidence_mismatch"):
        validate_existing_public_feed_image(candidate, candidates, rights, public)


def test_public_scope_retains_program_membership_and_rights_guards():
    candidate, candidates, rights, public = inputs()
    rights["entries"][1]["program_status"] = "revoked"
    with pytest.raises(ValueError, match="not_approved"):
        validate_existing_public_feed_image(candidate, candidates, rights, public)
    candidate, candidates, rights, public = inputs()
    candidates["additional_feed_reviews"][0]["feed_provenance"]["joined"] = False
    with pytest.raises(ValueError, match="provenance_required"):
        validate_existing_public_feed_image(candidate, candidates, rights, public)


def test_unknown_scopes_and_unscoped_unknown_candidates_are_not_silently_skipped(monkeypatch):
    from scripts import build_scentai_catalog_staging as builder

    original = builder.load_json
    candidate, candidates, _, _ = inputs()
    candidate["application_scope"] = "unknown"

    def load(path):
        return (
            deepcopy(candidates)
            if path.name == "dufynd_approved_feed_image_candidates.json"
            else original(path)
        )

    monkeypatch.setattr(builder, "load_json", load)
    with pytest.raises(ValueError, match="unknown_application_scope"):
        builder.build_staging_payload()
    candidate.pop("application_scope")
    with pytest.raises(ValueError, match="identity_mismatch"):
        builder.build_staging_payload()
