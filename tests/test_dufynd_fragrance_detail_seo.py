"""Guard DUFYND fragrance-detail SEO against product-truth regressions."""

from pathlib import Path

DETAIL_PAGE = Path("examples/retail/storefront-web/components/FragranceDetailPage.tsx")


def test_static_profile_keeps_breadcrumb_without_unqualified_product_snippet() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert '"@type": "BreadcrumbList"' in source
    assert "__html: breadcrumbJson" in source
    assert "item: canonicalUrl" in source
    assert '"@type": "Product"' not in source
    assert "productStructuredData" not in source
    assert "productJson" not in source

    # Do not manufacture prices or use editorial/third-party community scores
    # to satisfy Google's Product rich-result requirements.
    assert '"aggregateRating"' not in source
    assert '"offers"' not in source


def test_product_pages_override_social_metadata() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")

    assert "twitter: {" in source
    assert '"summary_large_image"' in source
    assert "const shareImage = originalPhotoFor(fragrance)?.url || null;" in source
    assert "images: shareImage ? [shareImage] : undefined" in source
    assert 'card: shareImage ? "summary_large_image" : "summary"' in source


def test_unapproved_rc1_creative_is_not_part_of_release() -> None:
    source = DETAIL_PAGE.read_text(encoding="utf-8")
    assert "editorialSocialCard" not in source
    assert "dufynd-rabanne-1-million-og.png" not in source
    assert "const productTruthVisual = originalPhotoFor(fragrance);" in source
