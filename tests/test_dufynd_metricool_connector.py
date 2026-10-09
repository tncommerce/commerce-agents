import hashlib
import json
from pathlib import Path

import httpx
import pytest
from scripts.dufynd_metricool_connector import (
    TOOL,
    dispatch_connected_metricool,
    private_draft_arguments,
    unwrap_tool_result,
    verify_hosted_bytes,
    verify_private_draft,
)
from scripts.dufynd_publish_orchestrator import PublishBlocked


def test_connected_tool_cannot_be_called_without_sql_ready_packet():
    class Bridge:
        def _rpc(self, name, args):
            assert name == "read_dufynd_publish_packet_v1"
            return {"ready": False, "reason": "owner_go_missing"}

    with pytest.raises(PublishBlocked, match="owner_go_missing"):
        dispatch_connected_metricool(
            Bridge(),
            call_tool=lambda *a: pytest.fail("public call"),
            ffmpeg="unused",
            asset_id="asset",
            path=Path("unused"),
            decision_id="no-go",
            verify_hosted_media=lambda *a: pytest.fail("not ready"),
        )


def test_real_tool_name_and_url_ingestion_are_bound_after_reservation(monkeypatch):
    from tests.test_dufynd_publish_orchestrator import Bridge, packet, response

    p = packet()
    b = Bridge(p)
    monkeypatch.setattr(
        "scripts.dufynd_publish_orchestrator.audit_media",
        lambda *a, **k: {"asset_sha256": p["asset_sha256"]},
    )

    def call(name, args):
        assert name == TOOL
        assert b.calls[-1][0] == "reserve_dufynd_publish_v1"
        assert "mediaFiles" not in args
        assert json.loads(args["info"])["media"] == [p["uri"]]
        return {"content": [{"type": "text", "text": json.dumps(response(p))}]}

    assert (
        dispatch_connected_metricool(
            b,
            call_tool=call,
            ffmpeg="fixture",
            asset_id="fixture",
            path=Path("unused"),
            decision_id="go",
            verify_hosted_media=lambda *a: True,
        )["publication_verified"]
        is False
    )


@pytest.mark.parametrize(
    "result",
    [{"isError": True}, {"content": []}, {"content": [{"type": "text", "text": "timeout"}]}],
)
def test_missing_or_failed_connector_receipt_is_never_success(result):
    with pytest.raises(PublishBlocked):
        unwrap_tool_result(result)


@pytest.mark.parametrize(
    "change",
    [
        {"draft": False},
        {"autoPublish": True},
        {"instagramData": {"autoPublish": True}},
        {"providers": [{"status": "PUBLISHED", "publicUrl": "https://instagram.com/a"}]},
    ],
)
def test_draft_cannot_be_reported_safe_with_unsafe_provider_flags(change):
    d = {
        "id": 1,
        "draft": True,
        "autoPublish": False,
        "instagramData": {"autoPublish": False},
        **change,
    }
    with pytest.raises(PublishBlocked):
        verify_private_draft({"structuredContent": {"data": d}})


def test_private_import_never_enables_scheduling_or_attaches_url_as_file(monkeypatch):
    monkeypatch.setattr(
        "scripts.dufynd_metricool_connector.audit_media", lambda *a, **k: {"asset_sha256": "a" * 64}
    )
    args = private_draft_arguments(
        path=Path("fixture"),
        ffmpeg="fixture",
        uri="https://dufynd.de/fixture.mp4",
        caption="Fixture",
        date="2099-01-01T18:00:00+01:00",
        verify_hosted_media=lambda *a: True,
    )
    i = json.loads(args["info"])
    assert i["draft"] is True and i["autoPublish"] is False
    assert i["instagramData"]["autoPublish"] is False
    assert "mediaFiles" not in args


def test_host_bytes_and_redirect_origin_are_checked():
    content = b"actual media"
    h = hashlib.sha256(content).hexdigest()
    ok = httpx.MockTransport(lambda r: httpx.Response(200, content=content))
    assert verify_hosted_bytes("https://dufynd.de/video.mp4", h, transport=ok)
    assert not verify_hosted_bytes("https://dufynd.de/video.mp4", "a" * 64, transport=ok)
    assert not verify_hosted_bytes("https://evil.invalid/video.mp4", h, transport=ok)
    redirect = httpx.MockTransport(
        lambda r: httpx.Response(302, headers={"location": "https://evil.invalid"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        verify_hosted_bytes("https://dufynd.de/video.mp4", h, transport=redirect)
