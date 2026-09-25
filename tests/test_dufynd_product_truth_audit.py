from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_dufynd_product_truth import (
    evaluate_product_truth_coverage,
    load_report,
)

SOURCE = Path("examples/retail/data/scentai_products.json")


def test_current_dufynd_product_truth_coverage_is_consistent() -> None:
    report = load_report()

    assert report["ok"] is True
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    expected_products = sum(
        1
        for row in source["products"]
        if str(row.get("product_id", "")).startswith("SC-")
    )

    assert report["summary"]["products"] == expected_products
    assert report["verified_product_truth_product_ids"] == ["SC-XERJOFF-NAXOS-100"]
    assert report["verified_model_3d_product_ids"] == []
    assert set(report["review_queue_product_ids"]) == {
        "SC-CREED-ABSOLU-AVENTUS-100",
        "SC-ARMANI-SWY-INTENSELY-100",
        "SC-PRADA-LHOMME-100",
        "SC-SOSPIRO-VIBRATO-100",
    }
    assert report["issues"] == []


def test_verified_variant_mismatch_is_a_hard_audit_issue() -> None:
    source = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "brand": "Test",
                "name": "Test",
                "volume_ml": 100,
                "visuals": [
                    {
                        "role": "primary",
                        "url": "/products/test.webp",
                        "fidelity_status": "verified",
                        "variant": "75ml",
                    }
                ],
            }
        ]
    }

    report = evaluate_product_truth_coverage(source, {"items": []})

    assert report["ok"] is False
    assert report["summary"]["verified_product_truth"] == 0
    assert report["products"][0]["invalid_verified_variants"] == ["primary"]
    assert "does not match 100ml variant" in report["issues"][0]


def test_verified_variant_normalization_accepts_spacing_and_case() -> None:
    source = {
        "products": [
            {
                "product_id": "SC-TEST-100",
                "brand": "Test",
                "name": "Test",
                "volume_ml": 100,
                "visuals": [
                    {
                        "role": "cutout",
                        "url": "/products/test.png",
                        "fidelity_status": "verified",
                        "variant": "100 ML",
                    }
                ],
            }
        ]
    }

    report = evaluate_product_truth_coverage(source, {"items": []})

    assert report["ok"] is True
    assert report["verified_product_truth_product_ids"] == ["SC-TEST-100"]
