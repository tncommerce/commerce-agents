"""Keep DUFYND alternative recommendations visibly evidence-based."""

from pathlib import Path

DETAIL_PAGE = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")


def test_related_fragrances_surface_shared_accord_evidence() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert "function sharedAccordLabels(" in source
    assert "right.accords.map" in source
    assert ".slice(0, limit)" in source
    assert ".map(accordLabel)" in source
    assert "Gemeinsame Akkorde" in source
    assert "sharedAccords.map" in source


def test_shared_accord_evidence_uses_existing_fragrance_records() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert "sharedAccordLabels(" in source
    assert "fragrance," in source
    assert "item.fragrance," in source
