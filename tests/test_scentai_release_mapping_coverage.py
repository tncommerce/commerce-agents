from __future__ import annotations

import json
from pathlib import Path

from scripts.promote_scentai_catalog import release_manifest_write_enabled

DATA_DIR = Path("examples/retail/data")
RELEASE_MANIFESTS = (
    DATA_DIR / "scentai_release_batch_01.json",
    DATA_DIR / "scentai_release_batch_02.json",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def release_payloads() -> list[dict]:
    return [load_json(path) for path in RELEASE_MANIFESTS]


def test_all_prepared_release_batches_have_redundant_verified_mappings() -> None:
    mappings = load_json(DATA_DIR / "merchant_product_mappings.json")["mappings"]

    by_product: dict[str, list[dict]] = {}
    for mapping in mappings:
        by_product.setdefault(mapping["product_id"], []).append(mapping)

    for release in release_payloads():
        for product_id in release["product_ids"]:
            rows = by_product.get(product_id, [])
            assert len(rows) >= 2, (
                release["release_id"],
                product_id,
            )
            assert all(
                row.get("merchant_product_id")
                or row.get("ean")
                or row.get("gtin")
                for row in rows
            ), (release["release_id"], product_id)


def test_merchant_product_mapping_pairs_are_unique() -> None:
    mappings = load_json(DATA_DIR / "merchant_product_mappings.json")["mappings"]

    pairs = [
        (row["product_id"], row["merchant"])
        for row in mappings
    ]

    assert len(pairs) == len(set(pairs))


def test_all_prepared_release_batches_have_gtin_fallbacks() -> None:
    mappings = load_json(DATA_DIR / "merchant_product_mappings.json")["mappings"]

    for release in release_payloads():
        for product_id in release["product_ids"]:
            rows = [
                row
                for row in mappings
                if row["product_id"] == product_id
            ]
            assert any(
                row.get("ean") and row.get("gtin")
                for row in rows
            ), (release["release_id"], product_id)


def test_release_batch_product_ids_do_not_overlap() -> None:
    seen: set[str] = set()

    for release in release_payloads():
        current = set(release["product_ids"])
        assert not seen.intersection(current), release["release_id"]
        seen.update(current)


def test_release_02_is_write_locked_until_release_01_is_validated() -> None:
    release_01 = RELEASE_MANIFESTS[0]
    release_02 = RELEASE_MANIFESTS[1]

    assert release_manifest_write_enabled(release_01) is True
    assert release_manifest_write_enabled(release_02) is False

    payload = load_json(release_02)
    assert "Release 01" in payload["write_guard_reason"]
