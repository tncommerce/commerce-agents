from __future__ import annotations

from scripts.report_scentai_demand import (
    build_demand_report,
    product_labels,
)


def catalog() -> dict:
    return {
        "products": [
            {
                "product_id": "SC-PRADA-1",
                "brand": "Prada",
                "title": "Prada L'Homme Intense",
                "attributes": {
                    "canonical_name": "L'Homme Intense",
                },
            },
            {
                "product_id": "SC-NAXOS-1",
                "brand": "Xerjoff",
                "title": "Xerjoff Naxos",
                "attributes": {
                    "canonical_name": "Naxos",
                },
            },
        ]
    }


def test_product_labels_prefer_brand_and_canonical_name() -> None:
    labels = product_labels(catalog())

    assert labels["SC-PRADA-1"] == "Prada L'Homme Intense"
    assert labels["SC-NAXOS-1"] == "Xerjoff Naxos"


def test_demand_report_ranks_search_and_gap_signals() -> None:
    report = build_demand_report(
        [
            {
                "search_term": "prada herren",
                "search_events": 8,
                "no_result_events": 1,
                "unique_sessions": 6,
                "avg_result_count": 2.5,
                "last_searched_at": "2026-09-18T20:00:00Z",
            },
            {
                "search_term": "gucci elixir absolu",
                "search_events": 0,
                "no_result_events": 5,
                "unique_sessions": 4,
                "avg_result_count": 0,
                "last_searched_at": "2026-09-18T20:10:00Z",
            },
            {
                "search_term": "naxos",
                "search_events": 4,
                "no_result_events": 0,
                "unique_sessions": 3,
                "avg_result_count": 1,
                "last_searched_at": "2026-09-18T20:20:00Z",
            },
        ],
        [],
        catalog(),
        limit=20,
    )

    assert report["summary"]["total_searches"] == 18
    assert report["summary"]["no_result_events"] == 6

    assert report["top_searches"][0]["search_term"] == "prada herren"
    assert report["top_no_results"][0]["search_term"] == "gucci elixir absolu"
    assert report["weak_coverage"][0]["search_term"] == "gucci elixir absolu"
    assert report["weak_coverage"][0]["no_result_rate"] == 1.0


def test_demand_report_enriches_product_engagement() -> None:
    report = build_demand_report(
        [],
        [
            {
                "product_id": "SC-PRADA-1",
                "product_opens": 12,
                "merchant_clickouts": 3,
                "opening_sessions": 8,
                "clickout_sessions": 2,
                "last_event_at": "2026-09-18T20:00:00Z",
            },
            {
                "product_id": "SC-NAXOS-1",
                "product_opens": 7,
                "merchant_clickouts": 5,
                "opening_sessions": 5,
                "clickout_sessions": 4,
                "last_event_at": "2026-09-18T20:00:00Z",
            },
        ],
        catalog(),
    )

    assert report["summary"]["product_opens"] == 19
    assert report["summary"]["merchant_clickouts"] == 8

    assert report["top_product_opens"][0]["product"] == "Prada L'Homme Intense"
    assert report["top_clickouts"][0]["product"] == "Xerjoff Naxos"


def test_limit_is_applied_to_every_ranked_section() -> None:
    search_rows = [
        {
            "search_term": f"query-{index}",
            "search_events": index + 1,
            "no_result_events": 1,
            "unique_sessions": index + 1,
            "avg_result_count": 0,
        }
        for index in range(5)
    ]

    report = build_demand_report(
        search_rows,
        [],
        catalog(),
        limit=2,
    )

    assert len(report["top_searches"]) == 2
    assert len(report["top_no_results"]) == 2
    assert len(report["weak_coverage"]) == 2
