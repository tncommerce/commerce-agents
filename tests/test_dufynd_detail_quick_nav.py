"""Keep long DUFYND fragrance detail pages easy to navigate on mobile."""

from pathlib import Path

DETAIL_PAGE = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")


def test_detail_page_has_compact_section_navigation() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert 'aria-label="Schnellnavigation auf der Duftseite"' in source
    assert 'href="#angebote"' in source
    assert 'href="#duftprofil"' in source
    assert 'href="#duftnoten"' in source
    assert 'href="#alternativen"' in source
    assert "Duft-DNA · {fragrance.accords.length} Akkorde" in source
    assert "Duftnoten · {noteCount}" in source


def test_detail_quick_nav_targets_real_scroll_anchors() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert 'id="angebote"' in source
    assert 'id="duftprofil"' in source
    assert 'id="duftnoten"' in source
    assert 'id="alternativen"' in source
    assert "const noteCount = new Set(allNotes).size" in source
