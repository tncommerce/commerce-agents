from __future__ import annotations

from scripts.report_scentai_research_triggers import (
    build_trigger_report,
    classify_term,
    trigger_level,
)


def test_trigger_thresholds() -> None:
    assert trigger_level(
        no_result_events=0,
        no_result_sessions=0,
    ) is None
    assert trigger_level(
        no_result_events=1,
        no_result_sessions=1,
    ) == "watch"
    assert trigger_level(
        no_result_events=3,
        no_result_sessions=2,
    ) == "research"
    assert trigger_level(
        no_result_events=7,
        no_result_sessions=4,
    ) == "high"


def test_classifies_live_before_backlog() -> None:
    result = classify_term(
        "creed aventus",
        live_rows=[
            {
                "product_id": "SC-CREED-AVENTUS-100",
                "brand": "Creed",
                "canonical_name": "Aventus",
            }
        ],
        staged_rows=[],
        candidate_rows=[
            {
                "candidate_id": "DUPLICATE",
                "brand": "Creed",
                "canonical_name": "Aventus",
            }
        ],
    )

    assert result["kind"] == "live_catalog"
    assert result["matched_id"] == "SC-CREED-AVENTUS-100"


def test_classifies_staged_candidate() -> None:
    result = classify_term(
        "burberry goddess",
        live_rows=[],
        staged_rows=[
            {
                "candidate_id": "BURBERRY-GODDESS-EDP",
                "product_id": "SC-BURBERRY-GODDESS-EDP-100",
                "brand": "Burberry",
                "canonical_name": "Goddess",
            }
        ],
        candidate_rows=[],
    )

    assert result["kind"] == "verified_staging"


def test_classifies_research_backlog_candidate() -> None:
    result = classify_term(
        "jpg le male elixir",
        live_rows=[],
        staged_rows=[],
        candidate_rows=[
            {
                "candidate_id": "JPG-LE-MALE-ELIXIR",
                "brand": "Jean Paul Gaultier",
                "canonical_name": "Le Male Elixir",
            }
        ],
    )

    assert result["kind"] == "research_backlog"


def test_unmatched_term_is_new_research_opportunity() -> None:
    result = classify_term(
        "gucci elixir absolu",
        live_rows=[],
        staged_rows=[],
        candidate_rows=[],
    )

    assert result["kind"] == "new_research_opportunity"
    assert result["matched_id"] is None


def test_report_only_marks_research_and_high_as_actionable() -> None:
    report = build_trigger_report(
        [
            {
                "search_term": "gucci elixir absolu",
                "search_events": 0,
                "no_result_events": 7,
                "unique_sessions": 5,
                "no_result_sessions": 4,
                "last_searched_at": "2026-09-18T20:00:00Z",
            },
            {
                "search_term": "prada paradigme",
                "search_events": 1,
                "no_result_events": 3,
                "unique_sessions": 3,
                "no_result_sessions": 2,
                "last_searched_at": "2026-09-18T20:00:00Z",
            },
            {
                "search_term": "random watch term",
                "search_events": 0,
                "no_result_events": 1,
                "unique_sessions": 1,
                "no_result_sessions": 1,
                "last_searched_at": "2026-09-18T20:00:00Z",
            },
        ],
        {
            "products": [
                {
                    "candidate_id": "PRADA-PARADIGME-EDP",
                    "brand": "Prada",
                    "canonical_name": "Paradigme",
                }
            ]
        },
        {"products": []},
        {"products": []},
    )

    assert report["trigger_count"] == 3
    assert report["actionable_count"] == 2
    assert report["counts_by_level"] == {
        "high": 1,
        "research": 1,
        "watch": 1,
    }

    assert report["triggers"][0]["level"] == "high"
    assert (
        report["triggers"][0]["kind"]
        == "new_research_opportunity"
    )
    assert report["triggers"][1]["level"] == "research"
    assert (
        report["triggers"][1]["kind"]
        == "research_backlog"
    )


def test_live_zero_result_trigger_points_to_search_relevance() -> None:
    report = build_trigger_report(
        [
            {
                "search_term": "creed aventus",
                "search_events": 0,
                "no_result_events": 4,
                "unique_sessions": 3,
                "no_result_sessions": 2,
            }
        ],
        {"products": []},
        {"products": []},
        {
            "products": [
                {
                    "product_id": "SC-CREED-AVENTUS-100",
                    "brand": "Creed",
                    "title": "Creed Aventus Eau de Parfum 100 ml",
                    "attributes": {
                        "canonical_name": "Aventus",
                    },
                }
            ]
        },
    )

    row = report["triggers"][0]
    assert row["kind"] == "live_catalog"
    assert (
        row["recommended_action"]
        == "investigate_search_relevance_or_filtering"
    )
