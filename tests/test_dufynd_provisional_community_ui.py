"""Keep provisional community data visibly marked across DUFYND surfaces."""

from pathlib import Path

CATALOG_MODEL = Path("examples/retail/storefront-web/lib/fragranceCatalog.ts")
CATALOG_UI = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")
FREE_COMPARE = Path("examples/retail/storefront-web/components/FragranceComparisonPicker.tsx")
DOCUMENTED_COMPARE = Path("examples/retail/storefront-web/app/vergleich/[pair]/page.tsx")
DETAIL = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")


def test_storefront_model_preserves_provisional_community_status() -> None:
    source = CATALOG_MODEL.read_text(encoding="utf-8")

    assert "provisional?: boolean;" in source
    assert "provisional: boolean;" in source
    assert "provisional: source?.community?.provisional === true" in source


def test_customer_facing_ratings_mark_provisional_values() -> None:
    catalog = CATALOG_UI.read_text(encoding="utf-8")
    free_compare = FREE_COMPARE.read_text(encoding="utf-8")
    documented_compare = DOCUMENTED_COMPARE.read_text(encoding="utf-8")
    detail = DETAIL.read_text(encoding="utf-8")

    assert "fragrance.community.provisional" in catalog
    assert "left.community.provisional" in free_compare
    assert "right.community.provisional" in free_compare
    assert "left.community.provisional" in documented_compare
    assert "right.community.provisional" in documented_compare
    assert "fragrance.community.provisional" in detail
    assert "item.fragrance.community.provisional" in detail

    for source in (catalog, free_compare, documented_compare, detail):
        assert "vorläufig" in source


def test_provisional_performance_metrics_are_visibly_marked() -> None:
    free_compare = FREE_COMPARE.read_text(encoding="utf-8")
    documented_compare = DOCUMENTED_COMPARE.read_text(encoding="utf-8")
    detail = DETAIL.read_text(encoding="utf-8")

    for source in (free_compare, documented_compare):
        assert "community.longevity_10" in source
        assert "community.projection_10" in source
        assert "community.provisional" in source
        assert "· vorläufig" in source

    assert detail.count("fragrance.community.provisional ? (") >= 3
