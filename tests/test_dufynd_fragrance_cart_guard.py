"""Keep DUFYND fragrance purchases on verified merchant clickouts."""

from pathlib import Path

API_MAIN = Path("examples/retail/api/main.py")
AGENT_CONFIG = Path("examples/retail/api/agent_config.py")
PRODUCT_TILE = Path("examples/retail/storefront-web/components/ProductTile.tsx")


def test_backend_rejects_dufynd_fragrance_cart_adds() -> None:
    source = API_MAIN.read_text(encoding="utf-8")

    assert 'str(request.product_id).startswith("SC-")' in source
    assert "status_code=409" in source
    assert "verified merchant offers" in source


def test_agent_and_product_cards_keep_fragrances_out_of_internal_cart() -> None:
    agent = AGENT_CONFIG.read_text(encoding="utf-8")
    tile = PRODUCT_TILE.read_text(encoding="utf-8")

    assert "never suggest or execute add-to-cart" in agent
    assert "onAdd && !isDufynd" in tile
