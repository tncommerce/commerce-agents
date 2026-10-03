from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from scripts.report_dufynd_profitable_growth import build_report, fetch_events

START = datetime(2026, 10, 1, tzinfo=UTC)
END = START + timedelta(days=7)


def event(kind, minute, **updates):
    return {
        "event_id": str(uuid4()),
        "occurred_at": (START + timedelta(minutes=minute)).isoformat(),
        "session_key": "anonymous-session",
        "event": kind,
        "product_id": "product-A",
        "acquisition_source": "tiktok",
        "campaign_id": "growth01",
        "content_id": "one_million_01",
        **updates,
    }


def report(rows, **kwargs):
    return build_report(rows, start=START, end=END, **kwargs)


def test_full_ordered_cohort_deduplicates_events_and_does_not_invent_revenue():
    land, view, click = (
        event("page_view", 0),
        event("fragrance_detail_view", 1),
        event("merchant_clickout", 2),
    )
    result = report([click, view, land, click], complete=True, minimum_sample=1)
    content = result["content"][0]
    assert content["qualified_visits_observed"] == 1
    assert content["qualified_clickout_sessions"] == 1
    assert content["merchant_clickout_events"] == 1
    assert content["qualified_clickout_rate"] == 1
    assert content["sample_and_extract_gate_met"] is True
    assert content["affiliate_revenue_eur"] is None
    assert content["affiliate_conversions"] is None
    assert content["revenue_per_content_piece_eur"] is None
    assert content["revenue_per_1000_qualified_visits_eur"] is None
    assert result["summary"]["duplicate_events_skipped"] == 1
    assert "anonymous-session" not in str(result)
    assert land["event_id"] not in str(result)


@pytest.mark.parametrize(
    "change",
    [
        {"session_key": "other-session"},
        {"campaign_id": "other-campaign"},
        {"content_id": "other-content"},
        {"acquisition_source": "youtube"},
    ],
)
def test_qualification_cannot_borrow_another_cohort_landing(change):
    result = report([event("page_view", 0), event("product_open", 1, **change)])
    assert result["summary"]["qualified_visits_observed"] == 0
    assert all(c["qualified_clickout_rate"] is None for c in result["content"])


def test_click_before_interest_does_not_enter_qualified_clickout_rate():
    result = report(
        [event("page_view", 0), event("merchant_clickout", 1), event("product_open", 2)]
    )
    c = result["content"][0]
    assert c["merchant_clickout_events"] == 1
    assert c["qualified_visits_observed"] == 1
    assert c["qualified_clickout_sessions"] == 0


def test_same_time_does_not_prove_order_or_quality():
    result = report([event("page_view", 0), event("product_open", 0)])
    assert result["summary"]["qualified_visits_observed"] == 0


def test_untagged_qa_invalid_and_window_boundaries_are_explicit():
    rows = [
        event("page_view", 0, content_id=None),
        event("page_view", 1, campaign_id="qa_growth"),
        event("page_view", 2, content_id="bad?identifier"),
        event("page_view", -1),
        event("page_view", 3, occurred_at=END.isoformat()),
        event("page_view", 4, occurred_at="naive-invalid"),
    ]
    r = report(rows)
    assert r["summary"]["unattributed_funnel_events"] == 2
    assert r["summary"]["test_events_excluded"] == 1
    assert r["summary"]["invalid_events_skipped"] == 1
    assert r["content"] == []
    assert r["coverage"]["ingestion_completeness"] == "UNKNOWN"


def test_insufficient_or_incomplete_sample_does_not_pass_sample_gate():
    rows = [event("page_view", 0), event("product_open", 1)]
    assert not report(rows, complete=True)["content"][0]["sample_and_extract_gate_met"]
    assert not report(rows, complete=False, minimum_sample=1)["content"][0][
        "sample_and_extract_gate_met"
    ]
    assert not report(rows, minimum_sample=1)["content"][0]["sample_and_extract_gate_met"]


def test_bounded_get_projection_truncation_and_unknown_count(monkeypatch):
    real_client = httpx.Client
    calls = []
    rows = [event("page_view", 0), event("product_open", 1)]

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.host == "bqsdxaagklpkxioaqdqa.supabase.co"
        assert request.url.params["select"] != "*"
        assert "search_term" not in request.url.params["select"]
        return httpx.Response(206, headers={"content-range": "0-1/20"}, json=rows)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    extracted, complete = fetch_events(key="server-only-key", start=START, end=END, max_events=2)
    assert extracted == rows and complete is False
    assert len(calls) == 1


def test_redirect_and_upstream_error_never_become_zero_metrics(monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(302, headers={"Location": "https://evil.invalid"})
            ),
            **kwargs,
        ),
    )
    with pytest.raises(ValueError, match="Growth source unavailable"):
        fetch_events(key="secret", start=START, end=END, max_events=2)
