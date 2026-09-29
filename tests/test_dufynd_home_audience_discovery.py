from __future__ import annotations

from pathlib import Path

HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")


def source() -> str:
    return HOME.read_text(encoding="utf-8")


def test_homepage_links_directly_to_audience_filtered_catalog() -> None:
    text = source()

    assert 'aria-label="Zielgruppen im Duftkatalog"' in text
    assert '["women", "Damen", audienceCounts.women]' in text
    assert '["men", "Herren", audienceCounts.men]' in text
    assert '["unisex", "Unisex", audienceCounts.unisex]' in text
    assert "href={`/duft?zielgruppe=${audience}`}" in text


def test_homepage_audience_counts_use_live_fragrance_targets() -> None:
    text = source()

    assert "const audienceCounts = Object.values(catalog).reduce(" in text
    assert "fragrance?.target_groups || []" in text
    assert "{ women: 0, men: 0, unisex: 0 }" in text


def test_featured_homepage_products_accept_verified_product_truth() -> None:
    text = source()

    assert "isVerifiedProductTruthVisual(" in text
    assert "fragrance?.preferred_visual" in text
    assert 'String(product.image_url ?? "").includes("/products/pilot/")' in text
