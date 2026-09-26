"""Keep DUFYND catalog sort wording aligned with its data signal."""

from pathlib import Path

CATALOG_BROWSER = Path(
    "examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx"
)


def test_popular_sort_is_labeled_as_community_activity() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert '{ value: "popular", label: "Community-Aktivität" }' in source
    assert '{ value: "popular", label: "Beliebtheit" }' not in source
