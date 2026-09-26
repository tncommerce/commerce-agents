"""Keep DUFYND pointer-driven visuals aligned with reduced-motion preferences."""

from pathlib import Path

VISUAL = Path("examples/retail/storefront-web/components/FragranceVisual.tsx")
HOME = Path("examples/retail/storefront-web/components/views/HomeView.tsx")
CSS = Path("examples/retail/storefront-web/app/globals.css")


def test_pointer_depth_stops_when_reduced_motion_is_requested() -> None:
    source = VISUAL.read_text(encoding="utf-8")

    assert 'window.matchMedia("(prefers-reduced-motion: reduce)").matches' in source
    assert source.index("prefers-reduced-motion: reduce") < source.index("getBoundingClientRect()")


def test_css_still_disables_product_and_editorial_motion() -> None:
    source = CSS.read_text(encoding="utf-8")

    assert "@media (prefers-reduced-motion: reduce)" in source
    assert ".dufynd-product-object" in source
    assert ".dufynd-editorial-depth-object" in source


def test_homepage_pointer_light_stops_when_reduced_motion_is_requested() -> None:
    source = HOME.read_text(encoding="utf-8")
    handler = source.split("function updateHeroLight", 1)[1].split(
        "function resetHeroLight", 1
    )[0]

    assert 'window.matchMedia("(prefers-reduced-motion: reduce)").matches' in handler
    assert handler.index("prefers-reduced-motion: reduce") < handler.index(
        "getBoundingClientRect()"
    )
