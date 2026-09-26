"""Keep DUFYND transform compositor hints scoped away from touch-first devices."""

from pathlib import Path

CSS = Path("examples/retail/storefront-web/app/globals.css")


def _block(source: str, selector: str) -> str:
    return source.split(f"\n{selector}", 1)[1].split("}", 1)[0]


def test_transform_will_change_is_not_permanent_on_visual_base_rules() -> None:
    source = CSS.read_text(encoding="utf-8")

    for selector in (
        ".dufynd-product-object {",
        ".dufynd-product-image {",
        ".dufynd-editorial-media > img {",
        ".dufynd-editorial-depth-object {",
    ):
        assert "will-change" not in _block(source, selector)


def test_transform_will_change_is_scoped_to_fine_pointer_hover_media() -> None:
    source = CSS.read_text(encoding="utf-8")

    media = source.split("@media (hover: hover) and (pointer: fine) {", 1)[1]
    for selector in (
        ".dufynd-product-object,",
        ".dufynd-product-image,",
        ".dufynd-editorial-media > img,",
        ".dufynd-editorial-depth-object {",
    ):
        assert selector in media
    assert "will-change: transform;" in media
