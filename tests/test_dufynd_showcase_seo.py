"""Keep the internal DUFYND/ACME showcase out of search indexes."""

from pathlib import Path

SHOWCASE_LAYOUT = Path("examples/retail/storefront-web/app/showcase/layout.tsx")
SHOWCASE_PAGE = Path("examples/retail/storefront-web/app/showcase/page.tsx")


def test_showcase_is_explicitly_noindex() -> None:
    layout = SHOWCASE_LAYOUT.read_text(encoding="utf-8")
    page = SHOWCASE_PAGE.read_text(encoding="utf-8")

    assert "index: false" in layout
    assert "follow: false" in layout
    assert "nocache: true" in layout
    assert "fixture data" in page
