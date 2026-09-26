"""Preserve the canonical image-rights audit trail for the priority live shortlist."""

from pathlib import Path

EVIDENCE = Path("examples/retail/data/dufynd_image_rights_evidence_20260926.md")
SHORTLIST = Path("examples/retail/data/dufynd_staging_live_shortlist_20260926.md")

PRIORITY_PRODUCT_IDS = {
    "SC-YSL-LIBRE-EDP-90",
    "SC-GUERLAIN-MON-GUERLAIN-EDP-100",
    "SC-BURBERRY-GODDESS-EDP-100",
    "SC-PRADA-PARADOXE-EDP-90",
    "SC-PDM-DELINA-EDP-75",
}


def test_priority_image_rights_evidence_covers_all_five_products() -> None:
    source = EVIDENCE.read_text(encoding="utf-8")

    for product_id in PRIORITY_PRODUCT_IDS:
        assert product_id in source

    assert "A public product page alone does not satisfy the image-rights gate." in source
    assert "Licensed affiliate/merchant feed" in source
    assert "DUFYND-owned photography" in source


def test_priority_shortlist_links_to_rights_evidence() -> None:
    source = SHORTLIST.read_text(encoding="utf-8")

    assert "dufynd_image_rights_evidence_20260926.md" in source
