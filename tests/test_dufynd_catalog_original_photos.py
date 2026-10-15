"""Catalog photo admission must not inherit generated-art approval."""

import json
from pathlib import Path

DATA = Path("examples/retail/data")


def test_every_catalog_photo_has_exact_existing_rights_and_identity_approval():
    entries = json.loads((DATA / "dufynd_catalog_packshots.json").read_text())["entries"]
    assert len({row["product_id"] for row in entries}) == len(entries)
    for row in entries:
        candidates = json.loads((DATA / row["rights_evidence_file"]).read_text())["candidates"]
        evidence = next(item for item in candidates if item["product_id"] == row["product_id"])
        assert evidence["review_status"] == "approved"
        assert evidence["exact_variant_verified"] is True
        assert evidence["rights_status"] == "verified_for_publisher_service"
        assert row["image_url"] == evidence["image_url"]
        assert row["rights_basis_id"] == evidence["rights_basis_id"]
        assert row["volume_ml"] == evidence["volume_ml"]
        assert row["concentration"] == evidence["concentration"]


def test_audit_covers_every_visible_product_and_holds_generated_bottles():
    products = json.loads((DATA / "scentai_products.json").read_text())["products"]
    visible = {r["product_id"] for r in products if not r.get("validation", {}).get("blockers")}
    audit = json.loads((DATA / "dufynd_catalog_photo_audit_20261010.json").read_text())["entries"]
    assert {r["product_id"] for r in audit} == visible
    admitted = {r["product_id"] for r in audit if r["status"] == "PASS"}
    photos = json.loads((DATA / "dufynd_catalog_packshots.json").read_text())["entries"]
    assert admitted == {r["product_id"] for r in photos}
    assert "SC-XERJOFF-NAXOS-100" not in admitted
    assert all(r["blocker"] and r["source"] is None for r in audit if r["status"] == "HOLD")
