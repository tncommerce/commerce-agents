"""Keep customer-facing DUFYND target-group labels German and centralized."""

from pathlib import Path

LABELS = Path("examples/retail/storefront-web/lib/targetLabels.ts")
SURFACES = [
    Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx"),
    Path("examples/retail/storefront-web/components/FragranceComparisonPicker.tsx"),
    Path("examples/retail/storefront-web/app/vergleich/[pair]/page.tsx"),
    Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx"),
]


def test_shared_target_labels_cover_current_customer_facing_terms() -> None:
    source = LABELS.read_text(encoding="utf-8")

    assert 'men: "Herren"' in source
    assert 'women: "Damen"' in source
    assert 'unisex: "Unisex"' in source


def test_customer_facing_surfaces_use_shared_target_labeler() -> None:
    for path in SURFACES:
        source = path.read_text(encoding="utf-8")
        assert 'from "@/lib/targetLabels"' in source
        assert "const TARGET_LABELS" not in source
        assert "function targetLabel" not in source
