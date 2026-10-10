import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from retail.api import analytics, main


def test_lost_write_response_retry_is_one_qa_event(monkeypatch, tmp_path):
    stored, requests = {}, []

    def transport(request):
        row = json.loads(request.content)
        requests.append(row)
        assert request.url.params["on_conflict"] == "event_id"
        assert "resolution=ignore-duplicates" in request.headers["Prefer"]
        stored.setdefault(row["event_id"], row)
        if len(requests) == 1:
            raise httpx.ReadTimeout("write committed, response lost", request=request)
        return httpx.Response(201)

    client = httpx.AsyncClient
    monkeypatch.setattr(
        analytics.httpx,
        "AsyncClient",
        lambda **kw: client(**kw, transport=httpx.MockTransport(transport)),
    )
    tracker = analytics.FirstPartyAnalyticsTracker(
        tmp_path / "fallback.jsonl",
        supabase_url="https://supabase.test",
        supabase_service_role_key="test-key",
    )
    monkeypatch.setattr(main, "analytics_tracker", tracker)
    payload = analytics.AnalyticsEventRequest(
        event="fragrance_detail_view",
        event_id=uuid4(),
        internal_qa=True,
        analytics_session_id="qa-stable-funnel-123456789",
        product_id="SC-TEST",
    )

    async def run():
        first = await main.analytics_event(payload, SimpleNamespace(session_id="old-transport"))
        second = await main.analytics_event(payload, SimpleNamespace(session_id="new-transport"))
        assert first["storage"] == "local_fallback"
        assert second["storage"] == "supabase"
        assert first["event_id"] == second["event_id"]
        assert len(stored) == 1
        assert next(iter(stored.values()))["traffic_class"] == "internal_qa"
        # Reusing a client key in a different funnel cannot collide with it.
        other = payload.model_copy(update={"analytics_session_id": "qa-other-funnel-123456789"})
        await main.analytics_event(other, SimpleNamespace(session_id="third-transport"))
        assert len(stored) == 2

    asyncio.run(run())


def test_malformed_client_id_is_rejected():
    with pytest.raises(ValidationError):
        analytics.AnalyticsEventRequest(event="page_view", event_id="not-an-id")
