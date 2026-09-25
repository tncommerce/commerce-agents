"""Keep public DUFYND editorial product assets referenced and intentional."""

import json
from pathlib import Path

SOURCE = Path("examples/retail/data/scentai_products.json")
CATALOG = Path("examples/retail/data/catalog.json")
PILOT_DIR = Path("examples/retail/storefront-web/public/products/pilot")


def _collect_strings(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        out: set[str] = set()
        for item in value:
            out.update(_collect_strings(item))
        return out
    if isinstance(value, dict):
        out: set[str] = set()
        for item in value.values():
            out.update(_collect_strings(item))
        return out
    return set()


def test_public_pilot_editorials_are_referenced_by_live_product_data() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    referenced = _collect_strings(source) | _collect_strings(catalog)
    public_assets = {
        f"/products/pilot/{path.name}" for path in PILOT_DIR.iterdir() if path.is_file()
    }

    orphaned = sorted(public_assets - referenced)
    assert not orphaned, f"unreferenced public editorial assets: {orphaned}"
