"""Keep browser QA route expectations aligned with customer-visible source validation."""

from pathlib import Path

VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_visual_qa_excludes_source_blocked_products_from_route_count() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert "function hasValidationBlockers(product)" in source
    assert "const expectedFragranceCount = sourceCatalog.products.filter(" in source
    assert "!hasValidationBlockers(product)" in source
    assert "const blockedFragranceRoutes = new Set(" in source
    assert "const routes = coreRoutes.filter(" in source
    assert "!blockedFragranceRoutes.has(route)" in source
    assert "detailRoutes.length !== expectedFragranceCount" in source


def test_visual_qa_redecodes_home_spotlight_after_history_navigation() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'await page.goBack({ waitUntil: "domcontentloaded" });' in source
    assert "await spotlightTruth.first().waitFor({" in source
    assert 'image.loading = "eager";' in source
    assert "await image.decode();" in source


def test_visual_qa_requires_blocked_detail_routes_to_stay_inaccessible() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert "const exposedBlockedRoutes = detailRoutes.filter(" in source
    assert "blockedFragranceRoutes.has(route)" in source
    assert "source-blocked fragrances leaked into the catalog" in source
    assert "response?.status() !== 404" in source
    assert "source-blocked fragrance route returned HTTP" in source


def test_visual_qa_requires_homepage_count_to_match_visible_catalog() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'expectedFragranceCount + " Düfte im Sortiment ansehen"' in source
    assert '"Alle " + expectedFragranceCount + " Düfte im Katalog entdecken"' in source
    assert "homepage fragrance count does not match the visible storefront catalog" in source
