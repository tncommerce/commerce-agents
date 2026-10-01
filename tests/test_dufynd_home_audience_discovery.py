from __future__ import annotations

from pathlib import Path

HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")


def source() -> str:
    return HOME.read_text(encoding="utf-8")


def test_homepage_links_directly_to_audience_filtered_catalog() -> None:
    text = source()

    assert 'aria-labelledby="dufynd-audience-discovery-heading"' in text
    assert '{ key: "women", label: "Damen", eyebrow: "Für sie" }' in text
    assert '{ key: "men", label: "Herren", eyebrow: "Für ihn" }' in text
    assert '{ key: "unisex", label: "Unisex", eyebrow: "Für alle" }' in text
    assert "href={`/duft?zielgruppe=${key}`}" in text


def test_homepage_audience_counts_use_exclusive_catalog_taxonomy() -> None:
    text = source()

    assert "const audienceCounts = Object.values(catalog).reduce(" in text
    assert "catalogAudienceFor(fragrance.target_groups)" in text
    assert "counts[audience] += 1" in text
    assert "{ women: 0, men: 0, unisex: 0 }" in text


def test_homepage_audience_previews_use_exclusive_matching() -> None:
    text = source()

    assert "fragranceMatchesAudience(fragrance, audience)" in text
    assert "fragranceMatchesAudience(fragrance, audience.key)" in text


def test_featured_homepage_products_accept_storefront_presentation() -> None:
    text = source()

    assert "fragrance?.presentation_visual?.url" in text
    assert "fragrance?.preferred_visual?.url" in text
    assert "product.image_url" in text


def test_homepage_renders_visual_audience_discovery_cards() -> None:
    text = source()

    assert 'id="dufynd-audience-discovery-heading"' in text
    assert "const audiencePreviews = audiencePreviewProducts(catalog);" in text
    assert "AUDIENCE_DISCOVERY.map((audience) =>" in text
    assert "min-w-[76%]" in text
    assert "snap-x snap-mandatory" in text
    assert "product?.image_url" in text
    assert "<ProductImage" in text
    assert "product={product}" in text
    assert "audienceCounts[key]" in text


def test_audience_preview_products_avoid_duplicate_visuals_when_possible() -> None:
    text = source()

    assert "const used = new Set<string>();" in text
    assert "!used.has(String(candidate.product_id))" in text
    assert "used.add(String(product.product_id));" in text


def test_homepage_catalog_count_excludes_source_blocked_fragrances() -> None:
    text = source()

    assert "const scentCount = Object.values(catalog).filter(" in text
    assert "getLiveFragranceByProductId(" in text
    assert "Boolean(" in text
    assert 'String(product.product_id).startsWith("SC-")' in text
    assert "product.in_stock !== false" in text


def test_audience_preview_products_search_full_visible_catalog_for_visuals() -> None:
    text = source()

    assert (
        "function audiencePreviewProducts(catalog: Record<string, Product>)" in text
    )
    assert "const matches = Object.values(catalog)" in text
    assert 'product.in_stock === false' in text
    assert "fragrance.presentation_visual?.url" in text
    assert "fragrance.preferred_visual?.url" in text
    assert "product.image_url" in text
