"""Synthetic private handoffs only. No live source, provider or database writes."""

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.dufynd_metricool_connector import (
    MANUAL_MANIFEST_KEY,
    _private_digest,
    dispatch_connected_metricool,
    dispatch_connected_release,
    sync_connected_manual_deliveries,
)
from scripts.dufynd_publish_orchestrator import PublishBlocked

from tests import test_dufynd_release_orchestrator as release_tests

NOW = datetime(2026, 10, 13, 16, tzinfo=UTC)


@pytest.fixture
def release_setup(monkeypatch):
    return release_tests.setup.__wrapped__(monkeypatch)


class Bridge:
    def __init__(self):
        self.binding = dict(
            content_id="synthetic",
            asset_sha256="a" * 64,
            platform="instagram",
            provider_post_id="123",
            provider_uuid="-456",
        )
        self.source = {
            "content_id": "synthetic",
            "asset_sha256": "a" * 64,
            "metricool_delivery": {"instagram": {"id": 123, "uuid": "-456"}},
            "asset": {"metricool_media": "https://media.invalid/synthetic.jpg"},
        }
        self.manifest = {
            "schema_version": 1,
            "brand_id": "7182186",
            "from_date": "2026-10-13T00:00:00+02:00",
            "to_date": "2026-10-15T00:00:00+02:00",
            "bindings": [
                {
                    "source_key": "content.synthetic",
                    "source_sha256": _private_digest(self.source),
                    "binding": self.binding,
                }
            ],
        }
        self.post = {
            "id": 123,
            "uuid": "-456",
            "autoPublish": False,
            "instagramData": {"autoPublish": False},
            "providers": [{"network": "instagram", "status": "PUBLISHED"}],
            "media": ["https://media.invalid/synthetic.jpg"],
        }
        self.rows, self.calls, self.receipts = [self.post], [], {}
        self.ready, self.lose_reply, self.conflict = True, False, False

    def load_master_status_entry(self, key):
        return {"value": deepcopy(self.manifest if key == MANUAL_MANIFEST_KEY else self.source)}

    def call_tool(self, name, args):
        assert name == "mcp__codex_apps__metricool_getscheduledposts"
        assert args["brandId"] == "7182186" and args["extendedRange"] is False
        self.calls.append(name)
        return {"structuredContent": {"data": deepcopy(self.rows)}}

    def _rpc(self, name, args):
        self.calls.append(name)
        if name == "dufynd_manual_guard_ready_v1":
            return self.ready
        assert name == "record_dufynd_manual_delivery_v1"
        previous = self.receipts.get(args["p_content_id"], {})
        state = args["p_state"]
        if previous.get("state") == "MANUAL_PUBLISHED":
            state = "MANUAL_PUBLISHED"
        receipt = {
            "recorded": True,
            "state": state,
            "auto_publish_allowed": False,
            "existing_dispatch_requires_reconciliation": self.conflict,
        }
        self.receipts[args["p_content_id"]] = receipt
        if self.lose_reply:
            raise TimeoutError("secret upstream message must not escape")
        return receipt

    def sync(self):
        return sync_connected_manual_deliveries(
            self, call_tool=self.call_tool, manifest_sha256=_private_digest(self.manifest), now=NOW
        )


@pytest.mark.parametrize(
    "status,state",
    [
        ("PENDING", "MANUAL_PENDING"),
        ("PUBLISHED", "MANUAL_PUBLISHED"),
        ("FAILED", "MANUAL_UNKNOWN"),
        (None, "MANUAL_UNKNOWN"),
    ],
)
def test_current_readback_reaches_existing_guard_without_provider_write(status, state):
    b = Bridge()
    b.post["providers"][0]["status"] = status
    assert b.sync()["provider_writes"] == 0
    assert b.receipts["synthetic"]["state"] == state
    assert b.calls == [
        "dufynd_manual_guard_ready_v1",
        "mcp__codex_apps__metricool_getscheduledposts",
        "record_dufynd_manual_delivery_v1",
    ]


@pytest.mark.parametrize(
    "case",
    [
        "empty",
        "duplicate_binding",
        "missing_source_id",
        "source_hash",
        "source_provider",
        "source_media",
        "guard",
        "missing_post",
        "duplicate_post",
        "extra_post",
        "provider_hash_media",
        "provider_id",
        "provider_uuid",
        "auto",
        "unaware",
        "expired",
        "long",
    ],
)
def test_uncertain_bindings_and_inventory_hold_without_exclusion_write(case):
    b = Bridge()
    if case == "empty":
        b.manifest["bindings"] = []
    elif case == "duplicate_binding":
        b.manifest["bindings"] *= 2
    elif case == "missing_source_id":
        b.source.pop("content_id")
    elif case == "source_hash":
        b.source["asset_sha256"] = "b" * 64
    elif case == "source_provider":
        b.source["metricool_delivery"] = {}
    elif case == "source_media":
        b.source["asset"] = {}
    elif case == "guard":
        b.ready = False
    elif case == "missing_post":
        b.rows = []
    elif case == "duplicate_post":
        b.rows *= 2
    elif case == "extra_post":
        b.rows.append({"id": 999})
    elif case == "provider_hash_media":
        b.post["media"] = ["https://media.invalid/other"]
    elif case == "provider_id":
        b.post["id"] = 999
    elif case == "provider_uuid":
        b.post["uuid"] = "999"
    elif case == "auto":
        b.post["autoPublish"] = True
    elif case == "unaware":
        b.manifest["from_date"] = "2026-10-13T00:00:00"
    elif case == "expired":
        b.manifest["to_date"] = "2026-10-13T00:00:00+02:00"
    else:
        b.manifest["to_date"] = "2026-11-01T00:00:00+02:00"
    # Test semantic binding, not just digest mismatch, for edited source cases.
    if b.manifest["bindings"]:
        b.manifest["bindings"][0]["source_sha256"] = _private_digest(b.source)
    with pytest.raises(PublishBlocked, match="manual_delivery_preflight_hold"):
        b.sync()
    assert b.receipts == {}


def test_manifest_pin_and_source_drift_fail_before_provider_read():
    b = Bridge()
    pin = _private_digest(b.manifest)
    b.manifest["bindings"] = []
    with pytest.raises(PublishBlocked):
        sync_connected_manual_deliveries(b, call_tool=b.call_tool, manifest_sha256=pin, now=NOW)
    b = Bridge()
    b.source["content_id"] = "changed"
    with pytest.raises(PublishBlocked):
        b.sync()
    assert b.calls == []


def test_lost_database_reply_holds_then_reobserves_without_new_publication():
    b = Bridge()
    b.lose_reply = True
    with pytest.raises(PublishBlocked) as error:
        b.sync()
    assert "secret" not in str(error.value)
    assert len(b.receipts) == 1
    b.lose_reply = False
    b.post["providers"][0]["status"] = "PENDING"  # late stale provider notification
    b.sync()
    b.sync()
    assert b.receipts["synthetic"]["state"] == "MANUAL_PUBLISHED"
    assert len(b.receipts) == 1


def test_existing_dispatch_requires_hold_even_after_exclusion_is_saved():
    b = Bridge()
    b.conflict = True
    with pytest.raises(PublishBlocked):
        b.sync()
    assert len(b.receipts) == 1


@pytest.mark.parametrize(
    "response", [{"isError": True}, {"structuredContent": {"data": [], "next": "cursor"}}]
)
def test_failed_or_paginated_provider_read_never_reaches_recording(response):
    b = Bridge()
    b.call_tool = lambda *a: response
    with pytest.raises(PublishBlocked):
        b.sync()
    assert b.receipts == {}


def test_interrupted_provider_read_has_no_retry_and_no_exclusion_write():
    b = Bridge()
    calls = []

    def interrupted(*args):
        calls.append(args[0])
        raise TimeoutError("private detail")

    b.call_tool = interrupted
    with pytest.raises(PublishBlocked, match="manual_delivery_preflight_hold"):
        b.sync()
    assert len(calls) == 1 and b.receipts == {}


@pytest.mark.parametrize("release", [False, True])
def test_both_real_entrypoints_default_deny_without_binding(release):
    b = Bridge()
    with pytest.raises(PublishBlocked, match="manual_delivery_preflight_hold"):
        if release:
            dispatch_connected_release(
                b,
                call_tool=b.call_tool,
                ffmpeg="unused",
                release_id="synthetic",
                paths={},
                decisions={},
                verify_hosted_media=None,
            )
        else:
            dispatch_connected_metricool(
                b,
                call_tool=b.call_tool,
                ffmpeg="unused",
                asset_id="synthetic",
                path=Path("unused"),
                decision_id="unused",
                verify_hosted_media=None,
            )
    assert b.calls == []


def test_connected_release_lost_provider_response_never_republishes(release_setup, monkeypatch):
    import scripts.dufynd_metricool_connector as connector

    runner, paths, decisions, _, state, _ = release_setup
    b = Bridge()
    # An unrelated manual creative; same-hash exclusion itself is tested in SQL.
    b.source["asset_sha256"] = b.binding["asset_sha256"] = "f" * 64
    b.manifest["bindings"][0]["source_sha256"] = _private_digest(b.source)
    record_rpc = b._rpc
    b._rpc = lambda name, args: (
        record_rpc(name, args)
        if name in {"dufynd_manual_guard_ready_v1", "record_dufynd_manual_delivery_v1"}
        else runner.bridge._rpc(name, args)
    )
    real_sync = connector.sync_connected_manual_deliveries
    monkeypatch.setattr(
        connector, "sync_connected_manual_deliveries", lambda *a, **k: real_sync(*a, **k, now=NOW)
    )
    writes = []

    def call(name, args):
        if name.endswith("getscheduledposts"):
            return b.call_tool(name, args)
        if name.endswith("getbrandsettings"):
            return {
                "structuredContent": {
                    "data": [
                        {
                            "id": 7182186,
                            "timezone": "Europe/Berlin",
                            "networksData": {
                                "instagramData": "dufynd",
                                "tiktokData": "dufynd",
                                "youtubeData": "UCQooXN4sOeMsEG-43qaH0aA",
                            },
                        }
                    ]
                }
            }
        assert name == connector.TOOL
        assert b.receipts and state["reserved"] and state["claimed"]
        writes.append(args)
        raise TimeoutError("provider accepted, response lost")

    def attempt():
        return dispatch_connected_release(
            b,
            call_tool=call,
            ffmpeg="fixture",
            release_id="synthetic",
            paths=paths,
            decisions=decisions,
            verify_hosted_media=lambda *a: True,
            manual_manifest_sha256=_private_digest(b.manifest),
        )

    with pytest.raises(PublishBlocked, match="release_halted_no_retry"):
        attempt()
    with pytest.raises(PublishBlocked, match="duplicate_or_uncertain"):
        attempt()
    assert len(writes) == 1
    assert state["receipts"][-1]["p_state"] == "outcome_unknown"
