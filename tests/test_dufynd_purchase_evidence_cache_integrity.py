"""Offline regressions for the existing Rabanne evidence reader, not new offers."""

from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from threading import Event, Thread

import httpx
import pytest

from retail.api import purchase_freshness as reader

PROJECT = "https://bqsdxaagklpkxioaqdqa.supabase.co"
KEY = "fixture-only-not-a-real-server-key"


@pytest.fixture(autouse=True)
def isolated_reader(monkeypatch):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("No real DNS, socket or merchant access is permitted")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setenv("SUPABASE_URL", PROJECT)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", KEY)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    reader._cache.clear()
    for name, value in (
        ("_cache_identity", None),
        ("_identity_epoch", 0),
        ("_request_generation", 0),
    ):
        monkeypatch.setattr(reader, name, value, raising=False)
    yield
    reader._cache.clear()


def client_stub(monkeypatch, callback):
    calls = []

    class Client:
        def __init__(self, *, timeout, follow_redirects):
            assert timeout == 2
            assert follow_redirects is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, headers, json):
            assert url == f"{PROJECT}/rest/v1/rpc/read_dufynd_purchase_evidence"
            assert json == {"p_offer_id": reader.TARGET_OFFER}
            calls.append(dict(headers))
            return callback(len(calls), headers)

    monkeypatch.setattr(reader.httpx, "Client", Client)
    return calls


def response(data, status=200):
    return httpx.Response(
        status,
        json=data,
        request=httpx.Request("POST", f"{PROJECT}/rest/v1/rpc/read_dufynd_purchase_evidence"),
    )


@pytest.mark.parametrize("change", ["remove_key", "wrong_project", "remove_project"])
def test_cached_evidence_never_survives_invalid_configuration(monkeypatch, change):
    value = {"decision": "safe_evidence_refresh", "fixture": True}
    calls = client_stub(monkeypatch, lambda *_: response(value))
    assert reader.evidence_for(reader.TARGET_OFFER) == value
    if change == "remove_key":
        monkeypatch.delenv("SUPABASE_SECRET_KEY")
    elif change == "wrong_project":
        monkeypatch.setenv("SUPABASE_URL", "https://invalid-project.example")
    else:
        monkeypatch.delenv("SUPABASE_URL")
    assert reader.evidence_for(reader.TARGET_OFFER) is None
    assert len(calls) == 1


@pytest.mark.parametrize("legacy_key", [False, True])
def test_key_rotation_requires_a_new_read(monkeypatch, legacy_key):
    old, new = {"fixture": "old"}, {"fixture": "new"}
    calls = client_stub(monkeypatch, lambda n, _: response(old if n == 1 else new))
    assert reader.evidence_for(reader.TARGET_OFFER) == old
    if legacy_key:
        monkeypatch.delenv("SUPABASE_SECRET_KEY")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "eyJ.fixture-only-new-key")
    else:
        monkeypatch.setenv("SUPABASE_SECRET_KEY", "fixture-only-rotated-key")
    assert reader.evidence_for(reader.TARGET_OFFER) == new
    assert len(calls) == 2
    if legacy_key:
        assert calls[-1]["Authorization"] == "Bearer eyJ.fixture-only-new-key"
    else:
        assert "Authorization" not in calls[-1]
    assert KEY not in repr(reader._cache)


def test_unchanged_configuration_retains_the_existing_cache(monkeypatch):
    value = {"fixture": "unchanged"}
    calls = client_stub(monkeypatch, lambda *_: response(value))
    assert reader.evidence_for(reader.TARGET_OFFER) == value
    assert reader.evidence_for(reader.TARGET_OFFER) == value
    assert len(calls) == 1


@pytest.mark.parametrize("newer", ["hold", "outage", "invalid_shape"])
def test_slow_old_positive_cannot_replace_newer_verdict(monkeypatch, newer):
    entered, release = Event(), Event()
    old = {"decision": "safe_evidence_refresh", "fixture": "old"}
    expected = {"decision": "hold", "fixture": "new"} if newer == "hold" else None

    def callback(number, _):
        if number == 1:
            entered.set()
            assert release.wait(3)
            return response(old)
        if newer == "outage":
            return response({"fixture": "unavailable"}, status=503)
        return response(expected if newer == "hold" else ["invalid"])

    calls = client_stub(monkeypatch, callback)
    outcomes, errors = [], []

    def slower():
        try:
            outcomes.append(reader.evidence_for(reader.TARGET_OFFER))
        except BaseException as exc:
            errors.append(exc)

    thread = Thread(target=slower)
    thread.start()
    try:
        assert entered.wait(3)
        assert reader.evidence_for(reader.TARGET_OFFER) == expected
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive()
    assert not errors
    assert outcomes == [expected]
    assert reader.evidence_for(reader.TARGET_OFFER) == expected
    assert len(calls) == 2


def test_credentials_removed_during_read_discard_the_response(monkeypatch):
    def callback(*_):
        monkeypatch.delenv("SUPABASE_SECRET_KEY")
        return response({"fixture": "must-not-survive"})

    client_stub(monkeypatch, callback)
    assert reader.evidence_for(reader.TARGET_OFFER) is None


def test_unrelated_offer_does_not_read_private_evidence(monkeypatch):
    calls = client_stub(monkeypatch, lambda *_: pytest.fail("Unexpected private read"))
    assert reader.evidence_for("fixture-unrelated-offer") is None
    assert calls == []


def row_and_evidence():
    now = datetime.now(UTC)
    row = {
        "offer_id": reader.TARGET_OFFER,
        "price": 71.9,
        "shipping_cost": 4.99,
        "in_stock": True,
        "last_updated_at": (now - timedelta(hours=48)).isoformat(),
    }
    evidence = {
        "source": "certified_purchase_verification",
        "max_age_hours": 72,
        "offer_contract": {k: v for k, v in row.items() if k != "last_updated_at"},
        "decision": "safe_evidence_refresh",
        "verified_at": (now - timedelta(hours=1)).isoformat(),
    }
    return row, evidence


@pytest.mark.parametrize("stamp", [None, 123, True, [], {}, "not-a-date"])
def test_malformed_source_timestamp_never_crashes_or_refreshes(stamp):
    row, evidence = row_and_evidence()
    evidence["verified_at"] = stamp
    assert reader.apply_evidence(row, evidence) == row


def test_valid_evidence_only_changes_the_real_source_timestamp():
    row, evidence = row_and_evidence()
    expected = row | {"last_updated_at": evidence["verified_at"]}
    assert reader.apply_evidence(row, evidence) == expected


def test_negative_source_verdict_still_withdraws_the_offer():
    row, evidence = row_and_evidence()
    evidence["decision"] = "hold"
    assert reader.apply_evidence(row, evidence) is None


def test_stale_source_does_not_extend_the_offer():
    row, evidence = row_and_evidence()
    evidence["verified_at"] = (datetime.now(UTC) - timedelta(hours=73)).isoformat()
    assert reader.apply_evidence(row, evidence) == row


def test_mismatched_business_contract_cannot_change_price():
    row, evidence = row_and_evidence()
    evidence["offer_contract"]["price"] = 1.0
    assert reader.apply_evidence(row, evidence) == row


def test_key_round_trip_cannot_resurrect_an_earlier_in_flight_read(monkeypatch):
    entered, release = Event(), Event()

    def callback(number, _):
        if number == 1:
            entered.set()
            assert release.wait(3)
        return response({"fixture": f"read-{number}"})

    calls = client_stub(monkeypatch, callback)
    outcomes, errors = [], []

    def slower():
        try:
            outcomes.append(reader.evidence_for(reader.TARGET_OFFER))
        except BaseException as exc:
            errors.append(exc)

    thread = Thread(target=slower)
    thread.start()
    try:
        assert entered.wait(3)
        monkeypatch.setenv("SUPABASE_SECRET_KEY", "fixture-only-intermediate-key")
        assert reader.evidence_for(reader.TARGET_OFFER) == {"fixture": "read-2"}
        monkeypatch.setenv("SUPABASE_SECRET_KEY", KEY)
        assert reader.evidence_for(reader.TARGET_OFFER) == {"fixture": "read-3"}
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive()
    assert not errors
    assert outcomes == [None]
    assert reader.evidence_for(reader.TARGET_OFFER) == {"fixture": "read-3"}
    assert len(calls) == 3


def test_cache_expiry_still_requires_a_real_new_read(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(reader.time, "monotonic", lambda: clock[0])
    calls = client_stub(monkeypatch, lambda n, _: response({"fixture": n}))
    assert reader.evidence_for(reader.TARGET_OFFER) == {"fixture": 1}
    clock[0] = 159.0
    assert reader.evidence_for(reader.TARGET_OFFER) == {"fixture": 1}
    clock[0] = 160.0
    assert reader.evidence_for(reader.TARGET_OFFER) == {"fixture": 2}
    assert len(calls) == 2
