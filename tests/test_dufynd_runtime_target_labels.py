"""Keep DUFYND runtime target-group labels German for customer-facing product data."""

from __future__ import annotations

import json
import re
from pathlib import Path

LIVE = Path("examples/retail/data/scentai_products.json")
STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
MOCK_RETAIL = Path("examples/retail/api/mock_retail.py")

ENTRY = re.compile(r'^\s*"(?P<key>[^"]+)":\s*"(?P<label>[^"]+)",\s*$', re.MULTILINE)


def _targets() -> set[str]:
    live = json.loads(LIVE.read_text(encoding="utf-8"))["products"]
    staged = json.loads(STAGING.read_text(encoding="utf-8"))["products"]
    values: set[str] = set()

    for product in live:
        classification = product.get("classification") or {}
        values.update(
            str(value).strip().lower()
            for value in classification.get("scentai_target_groups", [])
            if str(value).strip()
        )

    for product in staged:
        classification = product.get("classification") or {}
        values.update(
            str(value).strip().lower()
            for value in classification.get("target_groups", [])
            if str(value).strip()
        )

    return values


def _runtime_labels() -> dict[str, str]:
    source = MOCK_RETAIL.read_text(encoding="utf-8")
    block = source.split("target_labels_de = {", 1)[1].split("        }", 1)[0]
    return {match["key"].lower(): match["label"] for match in ENTRY.finditer(block)}


def test_runtime_target_labels_cover_live_and_staged_taxonomy() -> None:
    labels = _runtime_labels()
    required = _targets()

    assert required == {"men", "women", "unisex"}
    assert not (required - labels.keys())
    assert labels["men"] == "Herren"
    assert labels["women"] == "Damen"
    assert labels["unisex"] == "Unisex"


def test_customer_facing_product_translates_target_group_attribute() -> None:
    source = MOCK_RETAIL.read_text(encoding="utf-8")

    assert 'if attributes.get("target_group"):' in source
    assert 'attributes["target_group"] = ", ".join(' in source
