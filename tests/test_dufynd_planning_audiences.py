from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime

from scripts.dufynd_planning_audiences import storefront_gap_score, visible_inventory
from scripts.plan_scentai_promotion_batch import build_batch_plan
from scripts.report_dufynd_catalog_expansion_readiness import build_expansion_readiness


def test_visible_inventory_uses_source_identity_gate_and_exclusive_audiences() -> None:
    catalog = {
        "products": [
            {
                "product_id": product_id,
                "category": "fragrance",
                "attributes": {"target_group": group},
            }
            for product_id, group in [
                ("SC-MEN", "Herren"),
                ("SC-WOMEN", "Damen"),
                ("SC-UNISEX", "men,women,unisex"),
                ("SC-BOTH", "men,women"),
                ("SC-HIDDEN", "women"),
            ]
        ]
    }
    catalog["products"].extend(
        [
            {"product_id": "OTHER", "category": "fragrance"},
            {"product_id": "SC-SOLD", "category": "fragrance", "in_stock": False},
        ]
    )
    source = {
        "products": [
            {
                "product_id": "SC-HIDDEN",
                "validation": {
                    "catalog_ready": True,
                    "blockers": ["identity_concentration_review_required"],
                },
            },
            {"product_id": "SC-MEN", "validation": {"blockers": ["", None, " "]}},
        ]
    }
    before = deepcopy((catalog, source))
    visible, hidden, counts = visible_inventory(catalog, source)
    assert len(visible) == 4
    assert hidden == ["SC-HIDDEN"]
    assert counts == {"men": 1, "women": 1, "unisex": 2}
    assert (catalog, source) == before


def test_unisex_candidate_cannot_borrow_womens_underrepresentation() -> None:
    counts = Counter({"men": 17, "unisex": 16, "women": 1})
    assert storefront_gap_score(["men", "women", "unisex"], counts) == 0.59
    assert storefront_gap_score(["Herren", "Damen"], counts) == 0.59
    assert storefront_gap_score(["Damen"], counts) == 9.41
    assert storefront_gap_score(["unknown"], counts) == 0
    assert storefront_gap_score(["women"], Counter()) == 10


def test_planners_keep_raw_research_counts_but_use_visible_inventory() -> None:
    catalog = {
        "products": [
            {
                "product_id": "SC-UNISEX",
                "category": "fragrance",
                "attributes": {"target_group": "men,women,unisex"},
            },
            {
                "product_id": "SC-HIDDEN",
                "category": "fragrance",
                "attributes": {"target_group": "women"},
            },
        ]
    }
    source = {
        "products": [
            {"product_id": "SC-HIDDEN", "validation": {"blockers": ["identity_review"]}},
        ]
    }
    expansion = build_expansion_readiness(
        {"candidates": []},
        catalog,
        {"products": []},
        source=source,
    )
    promotion = build_batch_plan(
        {"products": []},
        catalog,
        {"offers": []},
        now=datetime(2026, 9, 30, tzinfo=UTC),
        source=source,
    )
    for report in (expansion, promotion):
        assert report["live_audience_counts"] == {"men": 1, "women": 2, "unisex": 1}
        assert report["storefront_audience_counts"] == {"unisex": 1}
        assert report["storefront_fragrance_count"] == 1
        assert report["storefront_blocked_product_ids"] == ["SC-HIDDEN"]


def test_source_classification_takes_precedence_over_old_catalog_tags() -> None:
    catalog = {
        "products": [
            {
                "product_id": "SC-A",
                "category": "fragrance",
                "attributes": {"target_group": "men,women,unisex"},
            }
        ]
    }
    source = {
        "products": [{"product_id": "SC-A", "classification": {"scentai_target_groups": ["women"]}}]
    }
    assert visible_inventory(catalog, source)[2] == {"women": 1}


def test_promotion_ranking_uses_candidate_exclusive_audience() -> None:
    catalog = {
        "products": [
            {
                "product_id": f"SC-{group}-{index}",
                "category": "fragrance",
                "attributes": {"target_group": group},
            }
            for group, count in [("men", 17), ("unisex", 16), ("women", 1)]
            for index in range(count)
        ]
    }
    staging = {
        "products": [
            {
                "product_id": "SC-A-UNISEX",
                "brand": "A",
                "classification": {"target_groups": ["men", "women", "unisex"]},
            },
            {
                "product_id": "SC-Z-WOMEN",
                "brand": "Z",
                "classification": {"target_groups": ["women"]},
            },
        ]
    }
    report = build_batch_plan(
        staging, catalog, {"offers": []}, now=datetime(2026, 9, 30, tzinfo=UTC)
    )
    assert report["selected"][0]["product_id"] == "SC-Z-WOMEN"
    assert report["selected"][0]["audience_gap_score_10"] == 9.41
    assert report["selected"][1]["audience_gap_score_10"] == 0.59
    assert report["ready_count"] == 0
