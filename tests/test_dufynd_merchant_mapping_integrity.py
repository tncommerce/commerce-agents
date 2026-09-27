"""Protect canonical DUFYND merchant mappings from identity corruption."""

from __future__ import annotations

import json
from pathlib import Path

MAPPINGS = Path("examples/retail/data/merchant_product_mappings.json")
STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
SOURCE = Path("examples/retail/data/scentai_products.json")

GTIN_LENGTHS = {8, 12, 13, 14}


def _gtin_valid(value: str) -> bool:
    digits = [int(char) for char in value]
    if len(digits) not in GTIN_LENGTHS:
        return False

    check = digits.pop()
    total = 0
    for offset, digit in enumerate(reversed(digits)):
        total += digit * (3 if offset % 2 == 0 else 1)

    return (10 - total % 10) % 10 == check


def test_mapping_identifiers_are_internally_consistent() -> None:
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]

    for row in rows:
        ean = str(row.get("ean") or "").strip()
        gtin = str(row.get("gtin") or "").strip()

        if ean:
            assert ean.isdigit(), row
            assert _gtin_valid(ean), row
        if gtin:
            assert gtin.isdigit(), row
            assert _gtin_valid(gtin), row
        if ean and gtin:
            assert ean == gtin, row


def test_mapping_product_ids_belong_to_known_dufynd_products() -> None:
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]
    staged = json.loads(STAGING.read_text(encoding="utf-8"))["products"]
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["products"]
    known_ids = {row["product_id"] for row in staged} | {row["product_id"] for row in source}

    unknown = sorted(
        {str(row.get("product_id") or "") for row in rows if row.get("product_id") not in known_ids}
    )
    assert not unknown, f"merchant mappings reference unknown products: {unknown}"


def test_merchant_product_ids_are_not_reused_across_dufynd_products() -> None:
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]
    seen: dict[tuple[str, str], str] = {}

    for row in rows:
        merchant_product_id = str(row.get("merchant_product_id") or "").strip()
        if not merchant_product_id:
            continue

        key = (str(row.get("merchant") or "").strip(), merchant_product_id)
        product_id = str(row.get("product_id") or "")
        previous = seen.setdefault(key, product_id)
        assert previous == product_id, (
            f"{key[0]} product ID {key[1]} maps to both {previous} and {product_id}"
        )


def test_gtins_are_not_reused_across_dufynd_products() -> None:
    rows = json.loads(MAPPINGS.read_text(encoding="utf-8"))["mappings"]
    seen: dict[str, str] = {}

    for row in rows:
        gtin = str(row.get("gtin") or row.get("ean") or "").strip()
        if not gtin:
            continue

        product_id = str(row.get("product_id") or "")
        previous = seen.setdefault(gtin, product_id)
        assert previous == product_id, f"GTIN {gtin} maps to both {previous} and {product_id}"
