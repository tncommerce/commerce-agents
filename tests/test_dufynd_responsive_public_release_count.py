"""Responsive QA must count source and authorized public release, never 37 forever."""

from pathlib import Path

SOURCE = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_responsive_sweep_binds_both_gated_public_catalog_cohorts() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    assert "released-profiles.json" in content
    assert "dufynd_release_authorizations.json" in content
    assert "const sourceQualifiedProducts =" in content
    assert "const publishedRoutes = [" in content
    assert "const expectedFragranceCount = publishedRoutes.length;" in content
    assert "sourceQualifiedRoutes" in content
    assert "approvedProductIds.has(p.product_id)" in content
    assert "p.indexing_approved !== true" in content
    assert "new Set(publishedRoutes).size !== publishedRoutes.length" in content
    assert "const expectedFragranceCount = sourceCatalog.products.filter(" not in content


def test_audience_qa_counts_and_routes_include_released_profiles() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    assert "function audienceForGroups(values)" in content
    assert "sourceQualifiedProducts" in content
    assert "releasedProfiles" in content
    assert "audienceForGroups(row.target_groups) === audience" in content
    assert "row.seo.public_path" in content
    assert "if (seenAudienceByRoute.size !== expectedFragranceCount)" in content
    assert "if (detailRoutes.length !== expectedFragranceCount)" in content
    assert "catalog sweep expected" in content
    assert "source-blocked fragrances leaked" in content
