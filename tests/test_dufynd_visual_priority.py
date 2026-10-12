"""Guard DUFYND product-truth visual selection and surface usage."""

from pathlib import Path

CATALOG_ADAPTER = Path("examples/retail/storefront-web/lib/fragranceCatalog.ts")

SURFACES = [
    Path("examples/retail/storefront-web/components/FragranceDetailPage.tsx"),
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


def test_customer_facing_image_cards_use_exact_original_registry() -> None:
    # The owner requested a single neutral studio look, not unlicensed scene art.
    photo_cards = [
        Path("examples/retail/storefront-web/components/FragranceComparisonPicker.tsx"),
        Path("examples/retail/storefront-web/components/FragranceLibraryHub.tsx"),
        Path("examples/retail/storefront-web/app/vergleich/[pair]/page.tsx"),
    ]
    for path in photo_cards:
        source = path.read_text(encoding="utf-8")
        assert "originalPhotoFor(fragrance)" in source, str(path)
        assert "fragrance.presentation_visual || productTruthVisual" not in source, str(path)
    # Commerce hero and product-tile images must come from the exact original
    # registry; homepage audience discovery remains distinct from product truth.
    for path in (
        Path("examples/retail/storefront-web/components/FragranceDetailPage.tsx"),
        Path("examples/retail/storefront-web/components/ProductTile.tsx"),
    ):
        assert "originalPhotoFor(fragrance)" in path.read_text(encoding="utf-8"), str(path)
    home = Path("examples/retail/storefront-web/components/views/HomeView.tsx")
    assert "preferred_visual" in home.read_text(encoding="utf-8")


def test_catalog_requires_original_photo_or_honest_studio_source_hold() -> None:
    source = Path(
        "examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx"
    ).read_text(encoding="utf-8")

    # The catalogue deliberately excludes editorial bottle scenes, even where
    # the legacy preferred-visual resolver would have accepted them.
    assert "originalPhotoFor(fragrance)" in source
    assert "<ScentArtwork" not in source
    assert "dufynd-catalog-photo-pending" in source
    assert "Originalfoto in Prüfung" in source
    assert 'data-dufynd-visual-state="missing"' in source
    assert "fragrance.preferred_visual" not in source
    assert "fragrance.presentation_visual" not in source


def test_only_verified_primary_or_cutout_count_as_product_truth() -> None:
    source = CATALOG_ADAPTER.read_text(encoding="utf-8")

    assert "isVerifiedProductTruthVisual" in source
    assert 'visual.fidelity_status === "verified"' in source
    assert '(visual.role === "primary" || visual.role === "cutout")' in source


def test_pending_or_rejected_visuals_never_reach_public_surfaces() -> None:
    source = CATALOG_ADAPTER.read_text(encoding="utf-8")

    assert 'visual.fidelity_status !== "rejected"' in source
    assert 'visual.fidelity_status !== "pending_review"' in source


def test_legacy_visual_fallbacks_never_claim_product_truth() -> None:
    source = CATALOG_ADAPTER.read_text(encoding="utf-8")

    editorial_fallback = source.split("const editorialUrl =", 1)[1].split(
        "const legacyCutoutUrl =", 1
    )[0]
    assert 'role: "editorial"' in editorial_fallback
    assert 'provenance: "legacy_catalog"' in editorial_fallback
    assert 'fidelity_status: "editorial_only"' in editorial_fallback

    legacy_cutout_fallback = source.split("const legacyCutoutUrl =", 1)[1].split("return null;", 1)[
        0
    ]
    assert 'role: "cutout"' in legacy_cutout_fallback
    assert 'provenance: "legacy_catalog"' in legacy_cutout_fallback
    assert 'fidelity_status: "pending_review"' in legacy_cutout_fallback
