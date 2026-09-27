"""Keep browser QA route expectations aligned with customer-visible source validation."""

from pathlib import Path

VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_visual_qa_excludes_source_blocked_products_from_route_count() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert "const expectedFragranceCount = sourceCatalog.products.filter((product) => {" in source
    assert "product?.validation?.blockers" in source
    assert '!blockers.some((blocker) => String(blocker || "").trim())' in source
    assert "detailRoutes.length !== expectedFragranceCount" in source
