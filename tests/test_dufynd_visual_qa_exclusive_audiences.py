from pathlib import Path

VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_visual_qa_covers_exclusive_audience_filters() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'const audienceKeys = ["men", "women", "unisex"];' in source
    assert 'if (groups.has("unisex")) return "unisex";' in source
    assert 'if (groups.has("men") && groups.has("women")) return "unisex";' in source
    assert "const expectedAudienceRoutes = Object.fromEntries(" in source
    assert 'baseUrl + "/duft?zielgruppe=" + audience' in source
    assert '"catalog-audience-exclusive"' in source
    assert "catalog audience overlap detected" in source


def test_visual_qa_matches_audience_routes_to_visible_source_catalog() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert "!hasValidationBlockers(product)" in source
    assert "exclusiveAudience(product) === audience" in source
    assert "seenAudienceByRoute.size !== expectedFragranceCount" in source


def test_home_browser_qa_uses_source_derived_exclusive_audience_counts() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'a[data-dufynd-home-audience-card][href="/duft?zielgruppe=${audience}"]' in source
    assert "const expectedCount = expectedAudienceRoutes[audience].length;" in source
    assert '"1 Duft im aktuellen Katalog"' in source
    assert '" Düfte im aktuellen Katalog"' in source
    assert '"home-audience-visible-counts"' in source
