from __future__ import annotations

from scripts.prioritize_scentai_candidates import (
    aggregate_candidate_demand,
    build_candidate_priority,
    demand_adjusted_selection_score,
    demand_points,
    query_matches_candidate,
)


def candidate(
    candidate_id: str,
    *,
    brand: str,
    name: str,
    priority: int = 1,
    components: dict | None = None,
) -> dict:
    row = {
        "candidate_id": candidate_id,
        "brand": brand,
        "canonical_name": name,
        "concentration": "Eau de Parfum",
        "target_group": "unisex",
        "segment": "test",
        "priority": priority,
    }
    if components is not None:
        row["selection_score_components"] = components
    return row


def search_row(
    term: str,
    *,
    success: int = 0,
    no_results: int = 0,
    sessions: int = 0,
) -> dict:
    return {
        "search_term": term,
        "search_events": success,
        "no_result_events": no_results,
        "unique_sessions": sessions,
        "avg_result_count": 0,
    }


def test_brand_alias_matches_candidate() -> None:
    ysl = candidate(
        "YSL-MYSLF-EDP",
        brand="Yves Saint Laurent",
        name="MYSLF",
    )
    jpg = candidate(
        "JPG-LE-MALE-ELIXIR",
        brand="Jean Paul Gaultier",
        name="Le Male Elixir",
    )
    pdm = candidate(
        "PDM-VALAYA-EDP",
        brand="Parfums de Marly",
        name="Valaya",
    )

    assert query_matches_candidate("ysl myslf", ysl)
    assert query_matches_candidate("jpg le male elixir", jpg)
    assert query_matches_candidate("pdm valaya", pdm)


def test_short_single_letter_name_does_not_match_loose_query() -> None:
    y = candidate(
        "YSL-Y-EDP",
        brand="Yves Saint Laurent",
        name="Y",
    )

    assert not query_matches_candidate(
        "suesser duft fuer party",
        y,
    )
    assert query_matches_candidate(
        "yves saint laurent y",
        y,
    )


def test_demand_points_are_bounded_to_ten() -> None:
    assert (
        demand_points(
            total_searches=0,
            unique_sessions=0,
            no_result_events=0,
        )
        == 0
    )

    assert (
        demand_points(
            total_searches=20,
            unique_sessions=10,
            no_result_events=7,
        )
        == 10
    )

    assert (
        demand_points(
            total_searches=999,
            unique_sessions=999,
            no_result_events=999,
        )
        == 10
    )


def test_candidate_demand_aggregates_matching_terms() -> None:
    row = candidate(
        "PRADA-PARADIGME-EDP",
        brand="Prada",
        name="Paradigme",
    )

    result = aggregate_candidate_demand(
        row,
        [
            search_row(
                "prada paradigme",
                success=4,
                no_results=1,
                sessions=4,
            ),
            search_row(
                "paradigme herren",
                success=0,
                no_results=3,
                sessions=3,
            ),
            search_row(
                "lattafa khamrah",
                success=10,
                sessions=5,
            ),
        ],
    )

    assert result["total_searches"] == 8
    assert result["no_result_events"] == 4
    assert result["unique_sessions_proxy"] == 4
    assert result["demand_score_10"] == 5
    assert result["matched_search_terms"] == [
        "paradigme herren",
        "prada paradigme",
    ]


def test_staged_candidates_are_excluded_from_research_queue() -> None:
    candidates = {
        "products": [
            candidate(
                "STAGED",
                brand="Brand",
                name="Already Staged",
            ),
            candidate(
                "OPEN",
                brand="Brand",
                name="Open Candidate",
            ),
        ]
    }
    staging = {"products": [{"candidate_id": "STAGED"}]}

    report = build_candidate_priority(
        candidates,
        staging,
        [
            search_row(
                "already staged",
                no_results=20,
                sessions=10,
            ),
            search_row(
                "open candidate",
                no_results=2,
                sessions=2,
            ),
        ],
    )

    assert report["candidate_count"] == 2
    assert report["staged_excluded_count"] == 1
    assert report["research_candidate_count"] == 1
    assert report["rows"][0]["candidate_id"] == "OPEN"


def test_unmatched_search_terms_surface_new_research_opportunity() -> None:
    report = build_candidate_priority(
        {
            "products": [
                candidate(
                    "KNOWN",
                    brand="Prada",
                    name="Paradigme",
                )
            ]
        },
        {"products": []},
        [
            search_row(
                "gucci elixir absolu",
                no_results=7,
                sessions=6,
            )
        ],
    )

    assert report["candidates_with_demand"] == 0
    assert len(report["unmatched_demand_terms"]) == 1
    assert report["unmatched_demand_terms"][0]["search_term"] == "gucci elixir absolu"


def test_demand_only_uses_existing_trend_momentum_weight() -> None:
    row = candidate(
        "SCORED",
        brand="Brand",
        name="Scored",
        components={
            "retailer_demand": 28,
            "community_strength": 24,
            "cross_merchant_coverage": 10,
            "trend_momentum": 3,
            "portfolio_fit": 8,
        },
    )

    assert (
        demand_adjusted_selection_score(
            row,
            demand_score=7,
        )
        == 77
    )

    assert (
        demand_adjusted_selection_score(
            row,
            demand_score=10,
        )
        == 80
    )


def test_demand_does_not_overwrite_stronger_existing_trend_score() -> None:
    row = candidate(
        "SCORED",
        brand="Brand",
        name="Scored",
        components={
            "retailer_demand": 30,
            "community_strength": 25,
            "cross_merchant_coverage": 12,
            "trend_momentum": 9,
            "portfolio_fit": 8,
        },
    )

    assert (
        demand_adjusted_selection_score(
            row,
            demand_score=4,
        )
        == 84
    )
