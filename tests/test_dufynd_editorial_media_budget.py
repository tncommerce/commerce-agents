"""Protect DUFYND public editorial-media performance budgets."""

import json
from pathlib import Path

PILOT_DIR = Path("examples/retail/storefront-web/public/products/pilot")
SOURCE = Path("examples/retail/data/scentai_products.json")
CATALOG = Path("examples/retail/data/catalog.json")

MAX_EDITORIAL_BYTES = 300_000
MAX_PILOT_TOTAL_BYTES = 6_500_000


def _all_strings(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_all_strings(item))
        return result
    if isinstance(value, dict):
        result: set[str] = set()
        for item in value.values():
            result.update(_all_strings(item))
        return result
    return set()


def test_public_editorials_use_webp_and_stay_under_budget() -> None:
    assets = sorted(path for path in PILOT_DIR.iterdir() if path.is_file())

    assert len(assets) == 31
    assert all(path.suffix.lower() == ".webp" for path in assets)

    oversized = {
        path.name: path.stat().st_size
        for path in assets
        if path.stat().st_size > MAX_EDITORIAL_BYTES
    }
    assert not oversized, f"oversized public editorial assets: {oversized}"

    total_bytes = sum(path.stat().st_size for path in assets)
    assert total_bytes <= MAX_PILOT_TOTAL_BYTES


def test_live_product_data_no_longer_references_editorial_pngs() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    references = _all_strings(source) | _all_strings(catalog)
    pilot_refs = {value for value in references if value.startswith("/products/pilot/")}

    assert pilot_refs
    assert all(value.endswith(".webp") for value in pilot_refs)
    assert not any(value.endswith(".png") for value in pilot_refs)
