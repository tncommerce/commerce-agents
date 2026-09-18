from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from retail.api.analytics import (
    AnalyticsEventRequest,
    FirstPartyAnalyticsTracker,
    sanitize_catalog_search_term,
)


def test_catalog_search_event_request_accepts_search_context() -> None:
    request = AnalyticsEventRequest(
        event="catalog_search",
        search_term="prada herren frisch",
        result_count=3,
        source="catalog_filter",
    )

    assert request.event == "catalog_search"
    assert request.search_term == "prada herren frisch"
    assert request.result_count == 3


def test_catalog_no_results_event_is_supported() -> None:
    request = AnalyticsEventRequest(
        event="catalog_no_results",
        search_term="unbekannter duft",
        result_count=0,
    )

    assert request.event == "catalog_no_results"
    assert request.result_count == 0


def test_tracker_row_contains_search_fields(tmp_path: Path) -> None:
    tracker = FirstPartyAnalyticsTracker(
        tmp_path / "analytics.jsonl"
    )

    row = tracker._row(
        session_id="session-123",
        event="catalog_search",
        product_id=None,
        source="catalog_filter",
        search_term="naxos wuerzig",
        result_count=2,
        now=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
    )

    assert row["event"] == "catalog_search"
    assert row["search_term"] == "naxos wuerzig"
    assert row["result_count"] == 2
    assert row["source"] == "catalog_filter"
    assert row["session_key"] != "session-123"


def test_search_term_sanitizer_normalizes_safe_queries() -> None:
    assert (
        sanitize_catalog_search_term("  Prada   Herren FRISCH ")
        == "prada herren frisch"
    )


def test_search_term_sanitizer_rejects_email_like_input() -> None:
    assert (
        sanitize_catalog_search_term("name@example.com")
        is None
    )


def test_search_term_sanitizer_rejects_long_number_input() -> None:
    assert (
        sanitize_catalog_search_term("+49 171 1234567")
        is None
    )



def test_conversion_event_request_accepts_funnel_context() -> None:
    request = AnalyticsEventRequest(
        event="comparison_start",
        product_id="SC-LEFT",
        related_product_id="SC-RIGHT",
        source="comparison_hub",
        surface="free_comparison",
        item_position=2,
    )

    assert request.event == "comparison_start"
    assert request.product_id == "SC-LEFT"
    assert request.related_product_id == "SC-RIGHT"
    assert request.surface == "free_comparison"
    assert request.item_position == 2


def test_tracker_row_contains_conversion_fields(tmp_path: Path) -> None:
    tracker = FirstPartyAnalyticsTracker(
        tmp_path / "analytics.jsonl"
    )

    row = tracker._row(
        session_id="session-456",
        event="advisor_recommendation_view",
        product_id="SC-TEST-100",
        source="advisor",
        surface="advisor_recommendation",
        item_position=1,
        now=datetime(2026, 9, 18, 21, 0, tzinfo=UTC),
    )

    assert row["event"] == "advisor_recommendation_view"
    assert row["product_id"] == "SC-TEST-100"
    assert row["surface"] == "advisor_recommendation"
    assert row["item_position"] == 1
    assert row["related_product_id"] is None


def test_funnel_item_position_is_bounded() -> None:
    from pydantic import ValidationError

    try:
        AnalyticsEventRequest(
            event="advisor_recommendation_view",
            item_position=101,
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("item_position above 100 must be rejected")



def test_anonymous_analytics_session_id_is_accepted() -> None:
    request = AnalyticsEventRequest(
        event="advisor_recommendation_view",
        product_id="SC-TEST-100",
        analytics_session_id="7c2587c3-6c03-4bdf-ae87-154b93f3ad31",
    )

    assert (
        request.analytics_session_id
        == "7c2587c3-6c03-4bdf-ae87-154b93f3ad31"
    )


def test_anonymous_analytics_session_id_rejects_short_values() -> None:
    from pydantic import ValidationError

    try:
        AnalyticsEventRequest(
            event="page_view",
            analytics_session_id="short",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError(
            "short analytics session IDs must be rejected"
        )
