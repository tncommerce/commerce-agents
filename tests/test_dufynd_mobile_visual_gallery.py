"""Keep DUFYND multi-visual fragrance galleries compact on mobile."""

from pathlib import Path

GALLERY = Path("examples/retail/storefront-web/components/FragranceVisualGallery.tsx")


def test_visual_gallery_uses_mobile_snap_scrolling() -> None:
    source = GALLERY.read_text(encoding="utf-8")

    assert "snap-x snap-mandatory" in source
    assert "overflow-x-auto" in source
    assert 'className="min-w-[82%] snap-start' in source
    assert "sm:grid sm:grid-cols-2" in source
    assert "sm:min-w-0" in source


def test_visual_gallery_explains_mobile_swipe_and_count() -> None:
    source = GALLERY.read_text(encoding="utf-8")

    assert "Seitlich wischen für weitere Ansichten" in source
    assert "{unique.length} Ansichten" in source
    assert "sm:hidden" in source
