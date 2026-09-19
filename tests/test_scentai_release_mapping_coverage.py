from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_release_batch_01_has_redundant_verified_mappings() -> None:
    release = load_json(DATA_DIR / "scentai_release_batch_01.json")
    mappings = load_json(DATA_DIR / "merchant_product_mappings.json")["mappings"]

    by_product: dict[str, list[dict]] = {}
    for mapping in mappings:
        by_product.setdefault(mapping["product_id"], []).append(mapping)

    for product_id in release["product_ids"]:
        rows = by_product.get(product_id, [])
        assert len(rows) >= 2, product_id
        assert all(
            row.get("merchant_product_id")
            or row.get("ean")
            or row.get("gtin")
            for row in rows
        ), product_id


def test_release_batch_01_mapping_pairs_are_unique() -> None:
    mappings = load_json(DATA_DIR / "merchant_product_mappings.json")["mappings"]

    pairs = [
        (row["product_id"], row["merchant"])
        for row in mappings
    ]

    assert len(pairs) == len(set(pairs))


def test_release_batch_01_has_gtin_level_fallbacks() -> None:
    release = load_json(DATA_DIR / "scentai_release_batch_01.json")
    mappings = load_json(DATA_DIR / "merchant_product_mappings.json")["mappings"]

    for product_id in release["product_ids"]:
        rows = [
            row
            for row in mappings
            if row["product_id"] == product_id
        ]
        assert any(
            row.get("ean") and row.get("gtin")
            for row in rows
        ), product_id
