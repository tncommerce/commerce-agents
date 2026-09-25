"""Guard DUFYND product-truth visual selection and surface usage."""

from pathlib import Path

CATALOG_ADAPTER = Path("examples/retail/storefront-web/lib/fragranceCatalog.ts")

SURFACES = [
    Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx"),
    Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx"),
    Path("examples/retail/storefront-web/components/FragranceComparisonPicker.tsx"),
    Path("examples/retail/storefront-web/components/FragranceLibraryHub.tsx"),
    Path("examples/retail/storefront-web/components/ProductTile.tsx"),
    Path("examples/retail/storefront-web/components/views/HomeView.tsx"),
    Path("examples/retail/storefront-web/app/vergleich/[pair]/page.tsx"),
]


def test_preferred_visual_priority_is_product_truth_first() -> None:
    source = CATALOG_ADAPTER.read_text(encoding="utf-8")

    primary = source.index("const verifiedPrimary")
    cutout = source.index("const verifiedCutout")
    editorial = source.index("const editorial =")

    assert primary < cutout < editorial
    assert 'visual.fidelity_status === "verified"' in source
    assert 'visual.role === "primary"' in source
    assert 'visual.role === "cutout"' in source


def test_customer_facing_product_surfaces_use_preferred_visual() -> None:
    missing = [
        str(path) for path in SURFACES if "preferred_visual" not in path.read_text(encoding="utf-8")
    ]

    assert not missing, "DUFYND surfaces bypassed the structured preferred visual: " + ", ".join(
        missing
    )


def test_only_verified_primary_or_cutout_count_as_product_truth() -> None:
    source = CATALOG_ADAPTER.read_text(encoding="utf-8")

    assert "isVerifiedProductTruthVisual" in source
    assert 'visual.fidelity_status === "verified"' in source
    assert '(visual.role === "primary" || visual.role === "cutout")' in source


def test_pending_or_rejected_visuals_never_reach_public_surfaces() -> None:
    source = CATALOG_ADAPTER.read_text(encoding="utf-8")

    assert 'visual.fidelity_status !== "rejected"' in source
    assert 'visual.fidelity_status !== "pending_review"' in source
