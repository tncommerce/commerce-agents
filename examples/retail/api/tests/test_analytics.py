from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from retail.api.analytics import (
    AnalyticsEventRequest,
    FirstPartyAnalyticsTracker,
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
