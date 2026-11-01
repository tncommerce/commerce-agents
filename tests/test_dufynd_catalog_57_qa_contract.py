"""57er-Katalogpfade dürfen die bisherigen mobilen und SEO-Varianten-Gates nicht aufweichen."""

from pathlib import Path

ROOT = Path("examples/retail/storefront-web/scripts")


def test_mobile_selected_variants_are_identity_bound() -> None:
    content = (ROOT / "mobile-discovery-qa.mjs").read_text(encoding="utf-8")
    assert 'assert.equal(await cards.count(), 3' in content
    for label in ('name: "Libre"', 'name: "Black Opium"', 'name: "Y"'):
        assert label in content
    assert '"/duft/ysl-y-edp-100"' in content
    assert "const productLink = blackOpiumCard.locator" in content
    assert 'nested.get("compare").split(",").length, 2' in content
    assert "mode === \"available\" ? 1 : 0" in content
    assert 'a[href*="/api/clickout/"]' in content


def test_variant_negative_search_is_asserted_after_hydration() -> None:
    content = (ROOT / "conversion-search-qa.mjs").read_text(encoding="utf-8")
    assert 'requireNoVariantResults(page, "YSL Libre 50ml")' in content
    assert "requireNoVariantResults(page, query)" in content
    assert "input[type=\"search\"]" in content
    assert "__reactProps$" in content
    assert 'article.dufynd-catalog-card").count(), 0' in content


def test_home_catalog_api_outage_keeps_all_authorized_57_visible() -> None:
    content = (ROOT / "home-catalog-hydration-qa.mjs").read_text(encoding="utf-8")
    assert "dufynd_release_authorizations.json" in content
    assert "released-profiles.json" in content
    assert "assert.equal(released.length, 20" in content
    assert "assert.equal(baseFragrances.length, 37" in content
    assert "eligible.size, released.length" in content
    assert "57-product homepage must not depend" in content
    assert "status: 503" in content
    assert "api/clickout/**" in content
