"""No public calls: negative dispatch/receipt tests with an explicit fake provider."""

from copy import deepcopy
from pathlib import Path

import pytest
from scripts.dufynd_publish_orchestrator import (
    PublishBlocked,
    PublishOrchestrator,
    connector_arguments,
    schedule_receipt,
    verify_publication,
)


def packet():
    return {
        "ready": True,
        "publishing_authorized": False,
        "asset_id": "fixture",
        "revision_fingerprint": "b" * 64,
        "asset_sha256": "a" * 64,
        "uri": "https://assets.example.org/" + "a" * 64 + ".mp4",
        "content_id": "fixture-unique",
        "platform": "instagram",
        "brand_id": "7182186",
        "caption": "Test fixture",
        "requested_at": "2099-01-01T10:00:00+01:00",
        "maker_id": "maker",
    }


def response(p):
    import json

    return {"data": {"id": 123, **json.loads(connector_arguments(p)["info"])}}


def test_embedded_connector_keeps_exact_url_sound_and_berlin_time():
    import json

    p = packet()
    args = connector_arguments(p)
    info = json.loads(args["info"])
    assert info["media"] == args["mediaFiles"] == [p["uri"]]
    assert info["publicationDate"] == {
        "dateTime": "2099-01-01T10:00:00",
        "timezone": "Europe/Berlin",
    }
    assert "audioConfiguration" not in info["instagramData"]
    assert info["instagramData"]["type"] == "REEL"
    p["platform"] = "tiktok"
    assert json.loads(connector_arguments(p)["info"])["tiktokData"]["autoAddMusic"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("uri", "http://example.org/file.mp4"),
        ("brand_id", "other"),
        ("requested_at", "2020-01-01T00:00:00Z"),
        ("requested_at", "2099-01-01T00:00:00"),
        ("uri", "https://example.org/mutable.mp4"),
        ("platform", "facebook"),
    ],
)
def test_wrong_target_time_or_mutable_media_block(field, value):
    p = packet()
    p[field] = value
    with pytest.raises(PublishBlocked):
        connector_arguments(p)


@pytest.mark.parametrize(
    "change",
    [
        {"media": []},
        {"media": ["https://cdn.example.org/reencoded.mp4"]},
        {"text": "Changed caption"},
        {"providers": [{"network": "tiktok"}]},
        {"draft": True},
        {"autoPublish": False},
        {"publicationDate": {}},
        {
            "instagramData": {
                "type": "REEL",
                "autoPublish": True,
                "audioConfiguration": {"audioId": "123"},
            }
        },
    ],
)
def test_changed_provider_payload_never_counts_as_verified_schedule(change):
    p = packet()
    reply = response(p)
    reply["data"].update(change)
    with pytest.raises(PublishBlocked):
        schedule_receipt(reply, p)


def test_schedule_is_never_a_publishing_or_ingested_bytes_success():
    result = schedule_receipt(response(packet()), packet())
    assert result["publication_verified"] is False
    assert result["provider_ingested_bytes_verified"] is False
    with pytest.raises(PublishBlocked):
        verify_publication(packet(), {"status": "PENDING", "id": "123"}, {})


class Bridge:
    def __init__(self, p, *, denied=None):
        self.p, self.calls, self.denied = p, [], denied

    def _rpc(self, name, body):
        self.calls.append((name, body))
        if name == "read_dufynd_publish_packet_v1":
            return self.p
        if name == "reserve_dufynd_publish_v1":
            if self.denied:
                return {"reserved": False, "reason": self.denied}
            return {"reserved": True, "dispatch_id": "fixture-reservation", "packet": self.p}
        if name == "record_dufynd_publish_receipt_v1":
            return True
        raise AssertionError(name)


def runner(monkeypatch, bridge, callback):
    monkeypatch.setattr(
        "scripts.dufynd_publish_orchestrator.audit_media",
        lambda *a, **kw: {"asset_sha256": "a" * 64},
    )
    return PublishOrchestrator(bridge, ffmpeg="fixture", metricool_schedule=callback)


@pytest.mark.parametrize(
    "reason",
    [
        "specific_owner_publish_go_required",
        "asset_or_revision_changed",
        "duplicate_or_uncertain_dispatch",
    ],
)
def test_no_connector_call_without_atomic_owner_authorization(monkeypatch, reason):
    calls = []
    b = Bridge(packet(), denied=reason)
    r = runner(monkeypatch, b, lambda args: calls.append(args))
    with pytest.raises(PublishBlocked, match=reason):
        r.dispatch(
            "fixture", Path("fixture.mp4"), "owner-decision", verify_hosted_media=lambda *a: True
        )
    assert not calls


def test_hosted_asset_change_blocks_before_reservation(monkeypatch):
    b = Bridge(packet())
    r = runner(monkeypatch, b, lambda args: pytest.fail("must not send"))
    with pytest.raises(PublishBlocked, match="hosted_asset_bytes_changed"):
        r.dispatch("fixture", Path("fixture.mp4"), "go", verify_hosted_media=lambda *a: False)
    assert [name for name, _ in b.calls] == ["read_dufynd_publish_packet_v1"]


def test_uncertain_provider_call_records_terminal_hold_and_no_retry(monkeypatch):
    b, sends = Bridge(packet()), []

    def timeout(args):
        sends.append(args)
        raise TimeoutError("provider may have accepted")

    r = runner(monkeypatch, b, timeout)
    with pytest.raises(PublishBlocked, match="outcome_unknown_no_retry"):
        r.dispatch("fixture", Path("fixture.mp4"), "go", verify_hosted_media=lambda *a: True)
    assert len(sends) == 1
    assert b.calls[-1][1]["p_state"] == "outcome_unknown"


def test_complete_mock_dispatch_preserves_exact_asset_and_stops_before_playback(monkeypatch):
    p, sends = packet(), []
    b = Bridge(p)

    def schedule(args):
        assert b.calls[-1][0] == "reserve_dufynd_publish_v1"
        sends.append(args)
        return response(p)

    result = runner(monkeypatch, b, schedule).dispatch(
        "fixture", Path("fixture.mp4"), "go", verify_hosted_media=lambda *a: True
    )
    assert len(sends) == 1
    assert result["stage"] == "SCHEDULED_AWAITING_PUBLIC_PLAYBACK"
    assert result["publication_verified"] is False


def public_evidence():
    provider = {
        "network": "instagram",
        "status": "PUBLISHED",
        "id": "123",
        "publicUrl": "https://www.instagram.com/reel/fixture/",
    }
    playback = {
        "source_sha256": "a" * 64,
        "platform_output_sha256": "c" * 64,
        "platform_post_id": "123",
        "public_url": provider["publicUrl"],
        "checker_id": "checker",
        "evidence_ref": "fixture:independent-platform-playback",
        **{
            k: True
            for k in (
                "full_decode_passed",
                "audible_playback_verified",
                "timing_verified",
                "audio_match_verified",
            )
        },
    }
    return provider, playback


@pytest.mark.parametrize(
    "key",
    [
        "full_decode_passed",
        "audible_playback_verified",
        "timing_verified",
        "audio_match_verified",
        "evidence_ref",
        "platform_output_sha256",
    ],
)
def test_every_public_playback_proof_is_required(key):
    provider, playback = public_evidence()
    playback.pop(key)
    with pytest.raises(PublishBlocked):
        verify_publication(packet(), provider, playback)


def test_public_audio_proof_cannot_be_self_approved_or_reused_for_other_post():
    provider, playback = public_evidence()
    assert verify_publication(packet(), provider, playback)["publication_verified"]
    for changes in (
        {"checker_id": "maker"},
        {"platform_post_id": "wrong"},
        {"source_sha256": "d" * 64},
    ):
        with pytest.raises(PublishBlocked):
            verify_publication(packet(), provider, {**deepcopy(playback), **changes})
