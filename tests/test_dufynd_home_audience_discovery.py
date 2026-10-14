from __future__ import annotations

from pathlib import Path

HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")


def source() -> str:
    return HOME.read_text(encoding="utf-8")


def test_homepage_links_directly_to_audience_filtered_catalog() -> None:
    text = source()

    assert 'aria-labelledby="dufynd-audience-discovery-heading"' in text
    assert '{ key: "women", label: "Damen", world: "silk" }' in text
    assert '{ key: "men", label: "Herren", world: "mineral" }' in text
    assert '{ key: "unisex", label: "Unisex", world: "amber" }' in text
    assert "href={`/duft?zielgruppe=${key}`}" in text


def test_homepage_audience_counts_use_exclusive_catalog_taxonomy() -> None:
    text = source()

    assert "const audienceCounts = Object.values(catalog).reduce(" in text
    assert "catalogAudienceFor(fragrance.target_groups)" in text
    assert "counts[audience] += 1" in text
    assert "{ women: 0, men: 0, unisex: 0 }" in text


# WOW23 removes audience product previews and the duplicate product row.
# Their visual selection/deduplication contracts no longer apply. The existing
# browser hydration and navigation suites retain counts, taxonomy, all audience
# destinations and acquisition attribution; catalog image rights remain covered.


def test_homepage_catalog_count_excludes_source_blocked_fragrances() -> None:
    text = source()

    assert "const scentCount = Object.values(catalog).filter(" in text
    assert "getLiveFragranceByProductId(" in text
    assert "Boolean(" in text
    assert 'String(product.product_id).startsWith("SC-")' in text
    assert "product.in_stock !== false" in text
