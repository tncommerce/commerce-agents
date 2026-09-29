from __future__ import annotations

from pathlib import Path

CATALOG = Path("examples/retail/storefront-web/lib/fragranceCatalog.ts")
VISUAL = Path("examples/retail/storefront-web/components/FragranceVisual.tsx")
PRODUCT_TILE = Path("examples/retail/storefront-web/components/ProductTile.tsx")
ACQUISITION = Path("examples/retail/storefront-web/components/AcquisitionLanding.tsx")
LIBRARY = Path("examples/retail/storefront-web/components/FragranceLibraryHub.tsx")
DUFT_PAGE = Path("examples/retail/storefront-web/app/duft/page.tsx")
STANDARD = Path("docs/dufynd-storefront-visual-standard-20260929.md")


def test_shared_visual_world_classifier_is_centralized() -> None:
    source = CATALOG.read_text(encoding="utf-8")
    assert 'export type FragranceVisualWorld' in source
    assert 'export function visualWorldFor' in source
    for world in ("amber", "mineral", "ember", "silk", "noir"):
        assert f'"{world}"' in source


def test_fragrance_visual_stage_accepts_world_without_touching_product_truth() -> None:
    source = VISUAL.read_text(encoding="utf-8")
    assert 'world?: FragranceVisualWorld' in source
    assert 'data-dufynd-visual-world={world}' in source
    assert 'WORLD_BACKGROUNDS' in source
    assert 'className="dufynd-product-image"' in source


def test_discovery_surfaces_pass_shared_world_context() -> None:
    assert 'visualWorldFor(fragrance)' in PRODUCT_TILE.read_text(encoding="utf-8")
    assert 'visualWorldFor(fragrance)' in ACQUISITION.read_text(encoding="utf-8")
    assert 'visualWorldFor(fragrance)' in LIBRARY.read_text(encoding="utf-8")
    assert 'visualWorldFor(fragrance)' in DUFT_PAGE.read_text(encoding="utf-8")


def test_visual_standard_keeps_worlds_atmospheric_only() -> None:
    source = STANDARD.read_text(encoding="utf-8")
    assert "Shared visual worlds" in source
    assert "must not recolor, deform or otherwise alter the bottle itself" in source
