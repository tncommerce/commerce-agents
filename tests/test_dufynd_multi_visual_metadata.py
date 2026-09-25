"""Validate DUFYND structured fragrance visual metadata."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("examples/retail/data/catalog.json")
SOURCE = Path("examples/retail/data/scentai_products.json")

ALLOWED_ROLES = {"primary", "cutout", "editorial", "macro"}
ALLOWED_STATUS = {"verified", "pending_review", "editorial_only", "rejected"}


def test_structured_visual_metadata_is_safe_and_consistent() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))

    catalog_by_id = {
        row["product_id"]: row
        for row in catalog["products"]
        if str(row.get("product_id", "")).startswith("SC-")
    }

    rows_with_visuals = [row for row in source["products"] if row.get("visuals")]
    assert rows_with_visuals, "Expected at least one multi-visual fragrance pilot"

    for row in rows_with_visuals:
        product_id = row["product_id"]
        assert product_id in catalog_by_id

        seen_urls: set[str] = set()
        for visual in row["visuals"]:
            assert visual["role"] in ALLOWED_ROLES
            assert visual["fidelity_status"] in ALLOWED_STATUS
            assert visual["url"].startswith(("/", "https://"))
            assert visual["url"] not in seen_urls, (
                f"{product_id}: duplicate visual URL {visual['url']}"
            )
            seen_urls.add(visual["url"])

            if visual["role"] == "editorial":
                assert visual["fidelity_status"] != "verified", (
                    f"{product_id}: editorial art must not be product truth"
                )


def test_naxos_visual_pilot_matches_legacy_product_layer() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))

    catalog_row = next(
        row for row in catalog["products"] if row["product_id"] == "SC-XERJOFF-NAXOS-100"
    )
    source_row = next(
        row for row in source["products"] if row["product_id"] == "SC-XERJOFF-NAXOS-100"
    )

    visuals = {visual["role"]: visual for visual in source_row["visuals"]}
    assert visuals["cutout"]["fidelity_status"] == "verified"
    assert visuals["cutout"]["url"] == (catalog_row["attributes"]["product_cutout_url"])
    assert visuals["editorial"]["fidelity_status"] == "editorial_only"
    assert visuals["editorial"]["url"] == catalog_row["image_url"]
