"""Keep DUFYND catalog sort wording aligned with its data signal."""

from pathlib import Path

CATALOG_BROWSER = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")


def test_discovery_sort_does_not_claim_unlicensed_community_activity() -> None:
    source = CATALOG_BROWSER.read_text(encoding="utf-8")

    assert '{ value: "popular", label: "Entdecken" }' in source
    assert 'label: "Community-Aktivität"' not in source
    assert '{ value: "popular", label: "Beliebtheit" }' not in source
