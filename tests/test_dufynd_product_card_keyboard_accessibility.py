"""Guard keyboard activation for DUFYND homepage product cards."""

from pathlib import Path

PRODUCT_TILE = Path("examples/retail/storefront-web/components/ProductTile.tsx")
HOME_VIEW = Path("examples/retail/storefront-web/components/views/HomeView.tsx")


def test_custom_product_controls_support_enter_and_space() -> None:
    source = PRODUCT_TILE.read_text(encoding="utf-8")

    assert 'event.key !== "Enter" && event.key !== " "' in source
    assert "event.preventDefault()" in source
    assert source.count("activateOnKeyboard(event, openProduct)") == 2


def test_dufynd_home_uses_both_keyboard_guarded_card_variants() -> None:
    source = HOME_VIEW.read_text(encoding="utf-8")

    assert "<ProductRow" in source
    assert "<ProductTile" in source
    assert source.count("onOpen={(item) =>") >= 2
