"""Keep DUFYND personal-library surfaces premium, private and visually scannable."""

from pathlib import Path

HUB = Path("examples/retail/storefront-web/components/FragranceLibraryHub.tsx")


def test_library_hero_exposes_live_local_counts() -> None:
    source = HUB.read_text(encoding="utf-8")

    assert 'aria-label="Persönliche Duftübersicht"' in source
    assert "{library.owned.length} in Sammlung" in source
    assert "{library.wishlist.length} auf Merkliste" in source
    assert "Nur auf diesem Gerät" in source


def test_collection_profile_has_clamped_visual_meters() -> None:
    source = HUB.read_text(encoding="utf-8")

    assert 'aria-label="Visuelles Sammlungsprofil"' in source
    assert "Math.max(0, Math.min(100, axis.average * 10))" in source
    assert "style={{ width: `${width}%` }}" in source
