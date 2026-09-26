"""Keep canonical top Parfümerie identity mappings explicit and non-activating."""

from __future__ import annotations

import json
from pathlib import Path

MAPPINGS = Path("examples/retail/data/merchant_product_mappings.json")

EXPECTED = {
    "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100": "780879",
    "SC-PDM-DELINA-EDP-75": "825869",
    "SC-YSL-BLACK-OPIUM-EDP-90": "787670",
    "SC-YSL-LIBRE-EDP-90": "856448",
    "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100": "924719",
}


def test_top_parfuemerie_mappings_are_unique_and_exact() -> None:
    payload = json.loads(MAPPINGS.read_text(encoding="utf-8"))
    rows = [
        row
        for row in payload["mappings"]
        if row.get("merchant") == "top-parfuemerie"
    ]

    assert len(rows) == len(EXPECTED)
    assert len({row["product_id"] for row in rows}) == len(rows)

    by_product = {row["product_id"]: row for row in rows}
    assert set(by_product) == set(EXPECTED)

    for product_id, merchant_product_id in EXPECTED.items():
        assert by_product[product_id]["merchant_product_id"] == merchant_product_id


def test_hypnotic_poison_is_not_invented_as_top_parfuemerie_mapping() -> None:
    payload = json.loads(MAPPINGS.read_text(encoding="utf-8"))

    assert not any(
        row.get("merchant") == "top-parfuemerie"
        and row.get("product_id") == "SC-DIOR-HYPNOTIC-POISON-EDT-100"
        for row in payload["mappings"]
    )
