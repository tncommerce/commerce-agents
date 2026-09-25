"""Guard DUFYND fragrance-detail SEO against product-truth regressions."""

from pathlib import Path

DETAIL_PAGE = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")


def test_product_schema_is_conservative_and_product_truth_gated() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert '"@type": "Product"' in source
    assert '"@type": "Brand"' in source
    assert 'sku: fragrance.product_id' in source
    assert 'name: "Konzentration"' in source
    assert 'name: "Füllmenge"' in source

    assert "heroIsProductTruth && heroVisual?.url" in source
    assert "verifiedProductImage" in source
    assert "{ image: [verifiedProductImage] }" in source

    # DUFYND does not claim merchant inventory or third-party community scores
    # as Product rich-result truth on the static fragrance page.
    assert '"aggregateRating"' not in source
    assert '"offers"' not in source


def test_product_pages_override_social_metadata() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert 'twitter: {' in source
    assert '"summary_large_image"' in source
    assert 'images: fragrance.preferred_visual?.url' in source
