"""Guard staged DUFYND fragrance variants against research-evidence drift."""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path("examples/retail/data")
STAGING = DATA / "scentai_catalog_staging.json"

SOURCES = [
    (
        DATA / "scentai_catalog_batch1_verification.json",
        "products",
        "proposed_product_id",
        "canonical_volume_ml",
    ),
    (
        DATA / "scentai_catalog_batch2_verification.json",
        "products",
        "proposed_product_id",
        "canonical_volume_ml",
    ),
    (
        DATA / "scentai_catalog_batch3_verification.json",
        "products",
        "proposed_product_id",
        "canonical_volume_ml",
    ),
    (DATA / "dufynd_catalog_expansion_next10.json", "candidates", "product_id", "volume_ml"),
    (DATA / "dufynd_catalog_expansion_wave2_batch6.json", "candidates", "product_id", "volume_ml"),
    (
        DATA / "dufynd_catalog_expansion_batch7_research.json",
        "candidates",
        "product_id",
        "volume_ml",
    ),
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence_by_product_id() -> dict[str, dict]:
    rows: dict[str, dict] = {}

    for path, collection_key, product_id_key, volume_key in SOURCES:
        payload = _load(path)
        for item in payload[collection_key]:
            product_id = item[product_id_key]
            assert product_id not in rows, f"Duplicate variant evidence for {product_id}"
            rows[product_id] = {
                "concentration": item["concentration"],
                "volume_ml": item[volume_key],
                "source": path.name,
                "variant_status": item.get("variant_status"),
            }

    return rows


def test_all_staged_variants_match_their_verified_evidence() -> None:
    staging = _load(STAGING)["products"]
    evidence = _evidence_by_product_id()

    assert len(staging) == 50
    assert len(evidence) == 50
    assert {row["product_id"] for row in staging} == set(evidence)

    for product in staging:
        verified = evidence[product["product_id"]]
        assert product["concentration"] == verified["concentration"], (
            product["product_id"],
            verified["source"],
        )
        assert product["volume_ml"] == verified["volume_ml"], (
            product["product_id"],
            verified["source"],
        )


def test_research_waves_keep_retail_variant_verification_explicit() -> None:
    evidence = _evidence_by_product_id()
    staging = _load(STAGING)["products"]

    research_ids = {row["product_id"] for row in staging if int(row["batch"]) >= 4}

    assert len(research_ids) == 20
    for product_id in research_ids:
        assert evidence[product_id]["variant_status"] == "verified_retail_variant"
