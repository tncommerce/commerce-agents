"""A provider is never called unless the complete frozen release is reserved."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from scripts import dufynd_publish_orchestrator as mod


@pytest.fixture
def setup(monkeypatch):
    packets = {
        p: dict(
            platform=p,
            brand_id="7182186",
            asset_sha256="a" * 64,
            uri="https://dufynd.de/" + "a" * 64 + ".mp4",
            requested_at="2099-01-01T12:00:00Z",
            caption="KI-gestützte Inszenierung",
            title="Fixture Short",
            ai_generated=True,
            revision_fingerprint="fixture:" + p,
        )
        for p in ("instagram", "tiktok", "youtube")
    }
    paths = {p: Path("fixture.mp4") for p in packets}
    decisions = {p: "go:" + p for p in packets}
    bridge = Mock()
    state = {"reserved": False, "claimed": [], "receipts": [], "ready": True}

    def rpc(name, args):
        if name == "preflight_dufynd_release_v1":
            return {
                "ready": state["ready"],
                "platforms": {p: {"packet": x, "reason": None} for p, x in packets.items()},
            }
        if name == "reserve_dufynd_release_v1":
            if state["reserved"]:
                return {"reserved": False, "reason": "duplicate_or_uncertain_dispatch"}
            state["reserved"] = True
            return {
                "reserved": True,
                "platforms": {p: {"dispatch_id": p, "packet": x} for p, x in packets.items()},
            }
        if name == "claim_dufynd_release_dispatch_v1":
            state["claimed"].append(args["p_dispatch_id"])
            return True
        if name == "record_dufynd_publish_receipt_v1":
            state["receipts"].append(args)
            return True
        raise AssertionError(name)

    bridge._rpc.side_effect = rpc
    monkeypatch.setattr(mod, "audit_media", Mock(return_value={"asset_sha256": "a" * 64}))

    def provider(args):
        assert state["reserved"]
        return {"data": {"id": "planner-123", **json.loads(args["info"])}}

    schedule = Mock(side_effect=provider)
    runner = mod.ReleaseOrchestrator(bridge, ffmpeg="fixture", metricool_schedule=schedule)
    return runner, paths, decisions, schedule, state, packets


def dispatch(setup):
    runner, paths, decisions, *_ = setup
    return runner.dispatch_release(
        "fixture-release", paths, decisions, verify_hosted_media=lambda *x: True
    )


def test_all_three_scheduled_is_not_published_or_audio_verified(setup):
    result = dispatch(setup)
    assert set(result["platforms"]) == {"youtube", "instagram", "tiktok"}
    assert result["publication_verified"] is result["audio_verified"] is False
    assert setup[3].call_count == 3
    with pytest.raises(mod.PublishBlocked, match="duplicate"):
        dispatch(setup)
    assert setup[3].call_count == 3


@pytest.mark.parametrize("platform", ["youtube", "instagram", "tiktok"])
def test_missing_platform_or_local_hash_blocks_every_call(setup, platform):
    del setup[1][platform]
    with pytest.raises(mod.PublishBlocked, match="all_three"):
        dispatch(setup)
    setup[3].assert_not_called()


def test_pending_owner_go_blocks_all(setup):
    setup[4]["ready"] = False
    with pytest.raises(mod.PublishBlocked):
        dispatch(setup)
    setup[3].assert_not_called()
    assert not setup[4]["reserved"]


def test_all_local_files_checked_before_provider_call(setup, monkeypatch):
    audit = Mock(
        side_effect=[
            mod.PublishBlocked("bad_file"),
            {"asset_sha256": "a" * 64},
            {"asset_sha256": "b" * 64},
        ]
    )
    monkeypatch.setattr(mod, "audit_media", audit)
    with pytest.raises(mod.PublishBlocked, match="bad_file"):
        dispatch(setup)
    assert audit.call_count == 3
    setup[3].assert_not_called()


def test_partial_failure_stops_third_and_retry(setup):
    normal = setup[3].side_effect
    calls = []

    def partial(args):
        calls.append(args)
        if len(calls) == 2:
            raise TimeoutError("provider may have accepted")
        return normal(args)

    setup[3].side_effect = partial
    with pytest.raises(mod.PublishBlocked, match="release_halted_no_retry:tiktok"):
        dispatch(setup)
    assert len(calls) == 2
    assert setup[4]["receipts"][-1]["p_state"] == "outcome_unknown"
    with pytest.raises(mod.PublishBlocked, match="duplicate"):
        dispatch(setup)
    assert len(calls) == 2


def test_youtube_ai_title_echo_required(setup):
    packet = setup[5]["youtube"]
    data = {"id": 123, **json.loads(mod.connector_arguments(packet)["info"])}
    data["youtubeData"]["isAiGeneratedContent"] = False
    with pytest.raises(mod.PublishBlocked, match="youtube_configuration"):
        mod.schedule_receipt({"data": data}, packet)
