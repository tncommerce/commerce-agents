from copy import deepcopy
from unittest.mock import Mock

import pytest
from scripts.dufynd_publish_orchestrator import PublishBlocked, PublishOrchestrator


def fixture():
    binding = dict(
        content_id="creative",
        asset_sha256="a" * 64,
        platform="instagram",
        provider_post_id="123",
        provider_uuid="-456",
    )
    post = dict(
        id=123,
        uuid="-456",
        autoPublish=False,
        instagramData={"autoPublish": False},
        providers=[{"network": "instagram", "status": "PUBLISHED"}],
    )
    return binding, post


@pytest.mark.parametrize(
    "status,expected",
    [
        ("PUBLISHED", "MANUAL_PUBLISHED"),
        ("PENDING", "MANUAL_PENDING"),
        ("FAILED", "MANUAL_UNKNOWN"),
        (None, "MANUAL_UNKNOWN"),
    ],
)
def test_readback_registers_only_exclusion_never_schedules(status, expected):
    binding, post = fixture()
    post["providers"][0]["status"] = status
    bridge, schedule = Mock(), Mock()
    runner = PublishOrchestrator(bridge, ffmpeg="unused", metricool_schedule=schedule)
    runner.record_manual_delivery(binding, post, evidence_ref="fixture:observation")
    name, args = bridge._rpc.call_args.args
    assert name == "record_dufynd_manual_delivery_v1" and args["p_state"] == expected
    assert args["p_content_id"] == "creative"
    assert set(args) == {
        "p_content_id",
        "p_platform",
        "p_asset_sha256",
        "p_state",
        "p_provider_post_id",
        "p_provider_uuid",
        "p_evidence_ref",
    }
    schedule.assert_not_called()


@pytest.mark.parametrize(
    "change",
    ["id", "uuid", "auto", "nested_auto", "network", "duplicate", "missing_provider", "hash"],
)
def test_ambiguous_or_drifted_readback_fails_closed(change):
    binding, post = deepcopy(fixture())
    if change in {"id", "uuid"}:
        post[change] = "other"
    elif change == "auto":
        post["autoPublish"] = True
    elif change == "nested_auto":
        post["instagramData"]["autoPublish"] = True
    elif change == "network":
        post["providers"][0]["network"] = "tiktok"
    elif change == "duplicate":
        post["providers"] *= 2
    elif change == "missing_provider":
        post.pop("providers")
    else:
        binding["asset_sha256"] = "unknown"
    bridge = Mock()
    with pytest.raises(PublishBlocked):
        PublishOrchestrator(bridge, ffmpeg="unused").record_manual_delivery(
            binding, post, evidence_ref="fixture"
        )
    bridge._rpc.assert_not_called()
