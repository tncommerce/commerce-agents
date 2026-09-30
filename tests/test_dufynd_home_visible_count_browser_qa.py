from pathlib import Path

VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_home_browser_qa_uses_visible_catalog_count() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'expectedFragranceCount + " Düfte im Sortiment ansehen"' in source
    assert '"Alle " + expectedFragranceCount + " Düfte im Katalog entdecken"' in source
    assert "homepage assortment count does not match visible catalog" in source
    assert "homepage catalog footer count does not match visible catalog" in source
