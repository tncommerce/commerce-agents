"""Keep unresolved DUFYND source-validation blockers out of customer runtimes."""

from __future__ import annotations

import json
from pathlib import Path

PRODUCTS = Path("examples/retail/data/scentai_products.json")
FRAGRANCE_CATALOG = Path("examples/retail/storefront-web/lib/fragranceCatalog.ts")
MOCK_RETAIL = Path("examples/retail/api/mock_retail.py")
API_MAIN = Path("examples/retail/api/main.py")


def test_source_data_has_a_real_blocked_product_fixture() -> None:
    products = json.loads(PRODUCTS.read_text(encoding="utf-8"))["products"]

    blocked = {
        row["product_id"]: row.get("validation", {}).get("blockers", [])
        for row in products
        if row.get("validation", {}).get("blockers")
    }

    assert blocked["SC-WIDIAN-LONDON-EXTRAIT-50"] == ["identity_concentration_review_required"]


def test_static_fragrance_runtime_excludes_source_blockers() -> None:
    source = FRAGRANCE_CATALOG.read_text(encoding="utf-8")

    assert "validation?: {" in source
    assert "blockers?: string[];" in source
    assert "function hasSourceValidationBlockers(productId: string): boolean" in source
    assert "!hasSourceValidationBlockers(product.product_id)" in source


def test_backend_search_and_details_exclude_source_blockers() -> None:
    source = MOCK_RETAIL.read_text(encoding="utf-8")

    assert "self._blocked_dufynd_product_ids" in source
    assert 'data_dir / "scentai_products.json"' in source
    assert "def _customer_visible_product(" in source
    assert "if self._customer_visible_product(product)" in source
    assert "if not self._customer_visible_product(product):" in source


def test_offer_runtime_reuses_customer_visibility_gate() -> None:
    source = API_MAIN.read_text(encoding="utf-8")

    helper = source.split(
        "def _live_dufynd_offer_product(product_id: str) -> bool:",
        1,
    )[1].split("\n\n", 1)[0]

    assert "backend.customer_product(product_id)" in helper
    assert "backend.product(product_id)" not in helper
