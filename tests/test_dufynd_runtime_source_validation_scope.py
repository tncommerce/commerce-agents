"""Keep unresolved DUFYND source-validation blockers out of customer runtimes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PRODUCTS = Path("examples/retail/data/scentai_products.json")
FRAGRANCE_CATALOG = Path("examples/retail/storefront-web/lib/fragranceCatalog.ts")
MOCK_RETAIL = Path("examples/retail/api/mock_retail.py")
SEO_GENERATOR = Path("examples/retail/storefront-web/scripts/generate-launch-seo.mjs")


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


def test_offer_runtime_reuses_customer_visibility_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from examples.retail.api import main as retail_api

    product_id = "SC-RABANNE-1-MILLION-EDT-100"
    customer_visible = retail_api.backend._customer_visible_product
    assert customer_visible(retail_api.backend.product(product_id)) is True

    def forbidden_evidence_read(_product_id):
        raise AssertionError("catalog scope must not perform merchant evidence I/O")

    monkeypatch.setattr(retail_api.offer_store, "offers_for", forbidden_evidence_read)
    assert retail_api._live_dufynd_offer_product(product_id) is True

    # The same otherwise eligible raw catalog item must disappear when the
    # shared customer policy hides it. A separate raw-catalog check is insufficient.
    def hide_customer_product(product):
        return customer_visible(product) and product.product_id != product_id

    monkeypatch.setattr(retail_api.backend, "_customer_visible_product", hide_customer_product)
    assert retail_api._live_dufynd_offer_product(product_id) is False


def test_sitemap_excludes_source_blocked_fragrances() -> None:
    source = SEO_GENERATOR.read_text(encoding="utf-8")

    assert "sourceProduct?.validation?.blockers" in source
    assert '!blockers.some((blocker) => String(blocker || "").trim())' in source
