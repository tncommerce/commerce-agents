from pathlib import Path

from examples.retail.api.analytics import AnalyticsEventRequest, FirstPartyAnalyticsTracker


def test_qa_marker_survives_hash_and_cannot_be_overridden_by_normal_source():
    tracker = FirstPartyAnalyticsTracker(Path("/tmp/unused-qa-test.jsonl"))
    for kwargs in (
        dict(internal_qa=True),
        dict(campaign_id="smoke_campaign"),
        dict(surface="internal_qa"),
        dict(session_id="qa-session"),
    ):
        args = dict(session_id="opaque-real-looking-session", event="page_view", source="instagram")
        args.update(kwargs)
        row = tracker._row(**args)
        assert row["traffic_class"] == "internal_qa"
        assert not row["session_key"].startswith("qa")
    assert (
        tracker._row(session_id="ordinary-session", event="page_view")["traffic_class"] == "visitor"
    )
    assert AnalyticsEventRequest(event="product_open", internal_qa=True).internal_qa
