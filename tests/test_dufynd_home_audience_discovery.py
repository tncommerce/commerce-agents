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


def test_homepage_renders_visual_audience_discovery_cards() -> None:
    text = source()

    assert 'id="dufynd-audience-discovery-heading"' in text
    assert "const audiencePreviews = audiencePreviewProducts(picks);" in text
    assert "AUDIENCE_DISCOVERY.map((audience) =>" in text
    assert "min-w-[76%]" in text
    assert "snap-x snap-mandatory" in text
    assert "product?.image_url" in text
    assert "audienceCounts[key]" in text


def test_audience_preview_products_avoid_duplicate_visuals_when_possible() -> None:
    text = source()

    assert "const used = new Set<string>();" in text
    assert "!used.has(String(candidate.product_id))" in text
    assert "used.add(String(product.product_id));" in text
