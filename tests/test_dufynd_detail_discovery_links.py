"""Keep DUFYND detail-to-catalog discovery links functional and shareable."""

from pathlib import Path

CATALOG_BROWSER = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")
DETAIL_PAGE = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")


def test_catalog_accepts_a_q_deep_link_once() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert 'params.get("q")?.trim()' in source
    assert "initialSearchAppliedRef.current" in source
    assert "setSearch(initialSearch.slice(0, 80))" in source


def test_detail_accords_and_notes_link_back_to_discovery() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert "/duft?q=" in source
    assert "encodeURIComponent(noteLabel(note))" in source
    assert "encodeURIComponent(accordLabel(accord))" in source
    assert "Weitere Düfte mit" in source


def test_visual_qa_accepts_interactive_note_chips() -> None:
    source = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs").read_text(
        encoding="utf-8"
    )

    assert 'document.querySelectorAll("span, a")' in source
    assert 'replace("→", "").trim() === note' in source
