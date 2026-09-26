"""Keep the documented fragrance comparison semantic for assistive technology."""

from pathlib import Path

COMPARISON = Path("examples/retail/storefront-web/app/vergleich/[pair]/page.tsx")
FREE_COMPARISON = Path("examples/retail/storefront-web/components/FragranceComparisonPicker.tsx")


def test_documented_comparison_exposes_table_semantics() -> None:
    source = COMPARISON.read_text(encoding="utf-8")

    assert 'role="table"' in source
    assert 'role="row"' in source
    assert 'role="columnheader"' in source
    assert 'role="rowheader"' in source
    assert 'role="cell"' in source
    assert "Duftvergleich" in source
    assert "aria-label={" in source


def test_free_comparison_exposes_table_semantics() -> None:
    source = FREE_COMPARISON.read_text(encoding="utf-8")

    assert 'role="table"' in source
    assert 'role="row"' in source
    assert 'role="columnheader"' in source
    assert 'role="rowheader"' in source
    assert 'role="cell"' in source
    assert "Freier Duftvergleich" in source
