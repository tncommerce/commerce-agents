"""Verify refreshed Jarvis repository snapshot against current source derivation."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from scripts.refresh_scentai_jarvis_state import refresh_state

DATA = Path("examples/retail/data")
WEB = Path("examples/retail/storefront-web/lib/generated")


def read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_jarvis_snapshot_is_rebuilt_from_current_repository_inputs() -> None:
    committed = read(DATA / "scentai_jarvis_master_status.json")
    assert committed["system"] == "DUFYND"
    assert committed["control_plane"] == "commerce_jarvis_master"
    assert datetime.fromisoformat(committed["generated_at"]).tzinfo is not None
    rebuilt = refresh_state(generated_at=committed["generated_at"])["master_status"]
    assert committed == rebuilt, "Never freshen an inconsistent Jarvis fingerprint"
    assert committed["safety"]["automatic_spend_allowed"] is False
    assert committed["safety"]["automatic_live_catalog_release_allowed"] is False
    assert committed["safety"]["automatic_social_publish_allowed"] is False


def test_snapshot_sync_does_not_change_existing_publication_and_photo_holds() -> None:
    catalog = read(DATA / "catalog.json")["products"]
    source = {p["product_id"]: p for p in read(DATA / "scentai_products.json")["products"]}
    approvals = read(DATA / "dufynd_release_authorizations.json")["approvals"]
    published = read(WEB / "released-profiles.json")["profiles"]
    held = read(DATA / "dufynd_facts_wave_02_review.json")["profiles"]
    originals = read(WEB / "original-photos.json")
    public_base = [
        p for p in catalog
        if p.get("product_id", "").startswith("SC-")
        and p.get("category") == "fragrance"
        and p.get("in_stock") is not False
        and not (source.get(p["product_id"], {}).get("validation", {}).get("blockers") or [])
    ]
    assert len(public_base) == 37
    assert len(published) == len(approvals) == 20
    assert {p["product_id"] for p in published} == {a["product_id"] for a in approvals}
    assert all(a["publication_approved"] is True and a["indexing_approved"] is True for a in approvals)
    assert len(held) == 21
    assert all(p["publication_authorized"] is False for p in held)
    assert len(originals) == 10
    assert not ({p["product_id"] for p in held} & {p["product_id"] for p in published})
