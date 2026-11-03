"""Adversarial end-to-end client boundaries for two independent Render services."""

from __future__ import annotations

import copy
import json
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import yaml
from private_broker import render_service_read as reader
from private_broker.render_service_contract import (
    ARTIFACT_FILE,
    MAX_ARTIFACT_BYTES,
    MAX_RESPONSE_BYTES,
    SCOPE_ID,
    SERVICE_IDS,
    RenderServiceError,
    timestamp,
    validate_artifact,
    validate_observation,
)
from scripts import dufynd_private_render_services_ingest as ingest_module
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from tests.test_dufynd_private_observer_ingest import source

API, STOREFRONT = SERVICE_IDS


def observation(service_id=API, *, observed_at="2026-10-29T17:00:01Z"):
    return {
        "version": 2,
        "scope_id": SCOPE_ID,
        "service_id": service_id,
        "observed_at": observed_at,
        "deployments": [
            {
                "deployment_id": "dep-live",
                "service_id": service_id,
                "commit_sha": "b" * 40,
                "status": "live",
                "timestamps": {
                    k: None for k in ("createdAt", "updatedAt", "startedAt", "finishedAt")
                },
            }
        ],
    }


def artifact():
    return {
        "_meta": source(),
        "version": 2,
        "services": {
            API: observation(),
            STOREFRONT: observation(STOREFRONT, observed_at="2026-10-29T17:00:02Z"),
        },
        "failures": {},
    }


def receipt(src, obs, *, reused=False):
    observed = timestamp(obs["observed_at"])
    return {
        "version": 2,
        "mode": SCOPE_ID,
        "scope_id": SCOPE_ID,
        "source": copy.deepcopy(src),
        "service_id": obs["service_id"],
        "observer_id": "render:" + obs["service_id"],
        "observed_at": observed.isoformat(),
        "captured_at": (observed + timedelta(seconds=1)).isoformat(),
        "evidence_sha256": "c" * 64,
        "accepted": True,
        "reused": reused,
        "render_captures": 0 if reused else 1,
        "gmail_captures": 0,
        "acks": 0,
        "activation_changed": False,
        "business_success": False,
        "full_chain_complete": False,
    }


class Bridge:
    def __init__(self, callback=None):
        self.calls = []
        self.callback = callback

    def capture_render_service_read(self, *, source, observation):
        self.calls.append((copy.deepcopy(source), copy.deepcopy(observation)))
        if self.callback:
            return self.callback(source, observation)
        return receipt(source, observation)


def write_artifact(tmp_path, payload=None):
    path = tmp_path / ARTIFACT_FILE
    path.write_text(json.dumps(artifact() if payload is None else payload), encoding="utf-8")
    return path


def ingest(bridge, path, **changes):
    expected = {
        "expected_run_id": source()["run_id"],
        "expected_sha": source()["sha"],
        "expected_run_attempt": source()["run_attempt"],
        **changes,
    }
    return ingest_module.ingest_artifact(bridge, path, **expected)


def configure_reader(monkeypatch, tmp_path, responses=None, *, flag="1"):
    monkeypatch.chdir(tmp_path)
    for key, value in {
        "DUFYND_PRIVATE_RENDER_SERVICES_V2_ENABLED": flag,
        "BROKER_ORIGIN": "https://broker.example",
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example/token",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-secret-canary",
        **{
            "GITHUB_" + k.upper(): v
            for k, v in source().items()
            if k not in {"version", "event_name"}
        },
        "GITHUB_EVENT_NAME": "workflow_dispatch",
    }.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    calls, options = [], []
    responses = {} if responses is None else responses

    def handler(request):
        calls.append(request)
        if request.url.host == "oidc.example":
            reply = responses.get(
                "identity", httpx.Response(200, json={"value": "oidc-secret-canary"})
            )
        else:
            service_id = request.url.path.split("/")[-2]
            reply = responses.get(
                service_id, httpx.Response(200, json=artifact()["services"][service_id])
            )
        if isinstance(reply, Exception):
            raise reply
        return reply

    real_client = httpx.Client

    def client(**kwargs):
        options.append(kwargs)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(reader.httpx, "Client", client)
    return calls, options


def test_reader_real_http_boundary_keeps_actual_service_times_and_no_global_health(
    monkeypatch, tmp_path
):
    calls, options = configure_reader(monkeypatch, tmp_path)
    reader.main()
    saved = json.loads((tmp_path / ARTIFACT_FILE).read_text())
    assert saved == artifact()
    assert [str(r.url).split("?")[0] for r in calls] == [
        "https://oidc.example/token",
        f"https://broker.example/v2/render/services/{API}/deployments",
        f"https://broker.example/v2/render/services/{STOREFRONT}/deployments",
    ]
    assert options == [{"trust_env": False, "timeout": 30, "follow_redirects": False}]
    assert calls[1].headers["Authorization"] == "Bearer oidc-secret-canary"
    assert "secret-canary" not in json.dumps(saved)
    assert set(p.name for p in tmp_path.iterdir()) == {ARTIFACT_FILE}


@pytest.mark.parametrize("failed_service", SERVICE_IDS)
@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(503, json={"error": "provider_outage"}),
        httpx.Response(302, headers={"Location": "https://leak.example"}),
        httpx.ConnectError("provider-secret-canary"),
        httpx.Response(200, json={"secret": "provider-secret-canary"}),
    ],
)
def test_partial_read_keeps_valid_peer_but_fails_run(
    monkeypatch, tmp_path, failed_service, failure
):
    calls, _ = configure_reader(monkeypatch, tmp_path, {failed_service: failure})
    with pytest.raises(SystemExit, match="read incomplete"):
        reader.main()
    saved = json.loads((tmp_path / ARTIFACT_FILE).read_text())
    validate_artifact(saved)
    assert len(calls) == 3
    assert set(saved["services"]) == set(SERVICE_IDS) - {failed_service}
    assert set(saved["failures"]) == {failed_service}
    assert "secret-canary" not in json.dumps(saved)
    bridge = Bridge()
    result = ingest(bridge, tmp_path / ARTIFACT_FILE)
    assert len(bridge.calls) == 1 and result["render_captures"] == 1
    assert result["all_requested_services_captured"] is False
    assert result["business_success"] is False and result["full_chain_complete"] is False


@pytest.mark.parametrize(
    "raw",
    [
        b'{"version":2,"version":2}',
        b'{"observed_at":NaN}',
        b"\xff",
        b"{" * 2000,
        b"x" * (MAX_RESPONSE_BYTES + 1),
    ],
)
def test_malformed_bounded_http_json_is_never_saved_as_observation(monkeypatch, tmp_path, raw):
    configure_reader(monkeypatch, tmp_path, {API: httpx.Response(200, content=raw)})
    with pytest.raises(SystemExit, match="read incomplete"):
        reader.main()
    saved = json.loads((tmp_path / ARTIFACT_FILE).read_text())
    assert saved["failures"] == {API: "invalid_response"}
    assert set(saved["services"]) == {STOREFRONT}


@pytest.mark.parametrize("failed_stage", ["identity", API, STOREFRONT])
def test_stream_overrun_stops_at_first_oversized_chunk_and_closes(
    monkeypatch, tmp_path, failed_stage
):
    events = []

    class Overrun(httpx.SyncByteStream):
        def __iter__(self):
            events.append("first")
            yield b"x" * (MAX_RESPONSE_BYTES + 1)
            events.append("must-not-read-second")
            yield b"second-secret-canary"
            events.append("must-not-read-third")
            yield b"third-secret-canary"

        def close(self):
            events.append("closed")

    calls, _ = configure_reader(
        monkeypatch,
        tmp_path,
        {
            failed_stage: httpx.Response(200, stream=Overrun()),
        },
    )
    with pytest.raises(SystemExit):
        reader.main()
    assert events == ["first", "closed"]
    assert all(r.headers["accept-encoding"] == "identity" for r in calls)
    if failed_stage == "identity":
        assert len(calls) == 1 and not (tmp_path / ARTIFACT_FILE).exists()
    else:
        assert len(calls) == 3
        saved = json.loads((tmp_path / ARTIFACT_FILE).read_text())
        assert saved["failures"] == {failed_stage: "invalid_response"}
        assert set(saved["services"]) == set(SERVICE_IDS) - {failed_stage}
        assert "secret-canary" not in json.dumps(saved)


@pytest.mark.parametrize("failed_stage", ["identity", API])
def test_unexpected_compression_rejected_before_any_body_decode(
    monkeypatch, tmp_path, failed_stage
):
    events = []

    class Unread(httpx.SyncByteStream):
        def __iter__(self):
            events.append("must-not-read")
            yield b"compression-canary"

        def close(self):
            events.append("closed")

    configure_reader(
        monkeypatch,
        tmp_path,
        {
            failed_stage: httpx.Response(
                200, headers={"content-encoding": "gzip"}, stream=Unread()
            ),
        },
    )
    with pytest.raises(SystemExit):
        reader.main()
    assert events == ["closed"]


@pytest.mark.parametrize("flag", [None, "0", "true", "api-storefront-v2"])
def test_disabled_read_clears_stale_artifacts_before_any_identity_call(monkeypatch, tmp_path, flag):
    calls, _ = configure_reader(monkeypatch, tmp_path, flag=flag)
    (tmp_path / ARTIFACT_FILE).write_text("old secret canary")
    (tmp_path / (ARTIFACT_FILE + ".tmp")).write_text("old secret canary")
    with pytest.raises(SystemExit, match="disabled"):
        reader.main()
    assert calls == [] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "origin",
    [
        "http://broker.example",
        "https://user:secret@broker.example",
        "https://broker.example/",
        "https://broker.example?secret=x",
        "https://broker.example#x",
        "https://broker.example:1234",
        "https://broker.example\n",
        "https://broker.example\\evil",
        "",
    ],
)
def test_wrong_origin_rejected_before_oidc(monkeypatch, tmp_path, origin):
    calls, _ = configure_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("BROKER_ORIGIN", origin)
    with pytest.raises(SystemExit, match="configuration or provenance invalid"):
        reader.main()
    assert calls == [] and not (tmp_path / ARTIFACT_FILE).exists()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(403, json={"error": "oidc-secret-canary"}),
        httpx.Response(200, json={"value": ""}),
        httpx.Response(200, content=b'{"value":"secret","value":"other"}'),
        httpx.ConnectError("oidc-secret-canary"),
    ],
)
def test_identity_failure_never_reads_services_or_publishes_old_file(
    monkeypatch, tmp_path, response
):
    calls, _ = configure_reader(monkeypatch, tmp_path, {"identity": response})
    (tmp_path / ARTIFACT_FILE).write_text("stale")
    with pytest.raises(SystemExit, match="identity or transport failed") as exc:
        reader.main()
    assert "secret-canary" not in str(exc.value)
    assert len(calls) == 1 and not (tmp_path / ARTIFACT_FILE).exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 2.0),
        ("scope_id", "render_deploy_broker"),
        ("service_id", STOREFRONT),
        ("observed_at", "2026-10-29T17:00:00"),
        ("observed_at", "infinity"),
        ("observed_at", "2026-99-29T17:00:00Z"),
        ("observed_at", "2026-10-29T17:00:00.1234567Z"),
        ("deployments", []),
        ("secret", "provider-secret-canary"),
    ],
)
def test_observation_rejects_scope_types_timestamp_and_secret_fields(field, value):
    payload = observation()
    payload[field] = value
    with pytest.raises(RenderServiceError):
        validate_observation(payload, service_id=API)


@pytest.mark.parametrize(
    "field,value",
    [
        ("service_id", STOREFRONT),
        ("commit_sha", "x" * 40),
        ("deployment_id", 1),
        ("status", "healthy"),
        ("timestamps", {"secret": "canary"}),
        ("secret", "canary"),
    ],
)
def test_deployment_binding_rejects_cross_service_or_unknown_data(field, value):
    payload = observation()
    payload["deployments"][0][field] = value
    with pytest.raises(RenderServiceError):
        validate_observation(payload, service_id=API)


def test_duplicate_deployment_evidence_is_ambiguous():
    payload = observation()
    payload["deployments"] *= 2
    with pytest.raises(RenderServiceError):
        validate_observation(payload, service_id=API)


def test_ingest_two_actual_timestamps_same_run_are_independent():
    payload = artifact()
    assert payload["services"][API]["observed_at"] != payload["services"][STOREFRONT]["observed_at"]
    assert timestamp("2026-10-29T17:00:01Z") == timestamp("2026-10-29T18:00:01+01:00")


def test_ingest_two_services_calls_only_v2_capture_and_accepts_pg_normalized_times(tmp_path):
    bridge = Bridge()
    result = ingest(bridge, write_artifact(tmp_path))
    assert [obs["service_id"] for _, obs in bridge.calls] == list(SERVICE_IDS)
    assert result["render_captures"] == 2 and result["all_requested_services_captured"] is True
    assert result["gmail_captures"] == result["acks"] == 0
    assert (
        result["business_success"]
        is result["full_chain_complete"]
        is result["activation_changed"]
        is False
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_run_id": "999"},
        {"expected_run_attempt": "2"},
        {"expected_sha": "f" * 40},
    ],
)
def test_ingest_requires_exact_run_attempt_and_sha_before_any_db_call(tmp_path, changes):
    bridge = Bridge()
    with pytest.raises(RenderServiceError, match="invalid_source"):
        ingest(bridge, write_artifact(tmp_path), **changes)
    assert bridge.calls == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(secret="canary"),
        lambda p: p["services"][STOREFRONT].update(secret="canary"),
        lambda p: p["failures"].update({API: "transport_error"}),
        lambda p: p["services"].pop(STOREFRONT),
        lambda p: p["services"].update({"srv-other": observation()}),
        lambda p: p["_meta"].update(version=True),
        lambda p: p["_meta"].update(run_id="0"),
        lambda p: p["_meta"].update(run_attempt="01"),
        lambda p: p["_meta"].update(repository="foreign/repo"),
        lambda p: p["_meta"].update(event_name=["workflow_dispatch"]),
        lambda p: p.update(version=True),
    ],
)
def test_entire_artifact_validates_before_any_partial_capture(tmp_path, mutate):
    payload = artifact()
    mutate(payload)
    bridge = Bridge()
    with pytest.raises(RenderServiceError):
        ingest(bridge, write_artifact(tmp_path, payload))
    assert bridge.calls == []


@pytest.mark.parametrize(
    "raw",
    [
        b'{"version":2,"version":2}',
        b'{"version":Infinity}',
        b"x" * (MAX_ARTIFACT_BYTES + 1),
        b"\xff",
    ],
)
def test_invalid_raw_artifact_never_reaches_db(tmp_path, raw):
    path = tmp_path / ARTIFACT_FILE
    path.write_bytes(raw)
    bridge = Bridge()
    with pytest.raises(RenderServiceError):
        ingest(bridge, path)
    assert bridge.calls == []


@pytest.mark.parametrize("fail_service", SERVICE_IDS)
@pytest.mark.parametrize("failure", ["exception", "rejection", "malformed_receipt"])
def test_independent_db_failure_keeps_other_capture_and_fails_summary(
    tmp_path, fail_service, failure
):
    def respond(src, obs):
        if obs["service_id"] != fail_service:
            return receipt(src, obs)
        if failure == "exception":
            raise RuntimeError("database-secret-canary")
        if failure == "rejection":
            return {"accepted": False, "reason": "render_scope_unverified"}
        return {"accepted": True, "secret": "database-secret-canary"}

    bridge = Bridge(respond)
    result = ingest(bridge, write_artifact(tmp_path))
    assert len(bridge.calls) == 2 and result["render_captures"] == 1
    assert result["all_requested_services_captured"] is False
    assert set(result["receipts"]) == set(SERVICE_IDS) - {fail_service}
    assert set(result["failures"]) == {fail_service}
    assert "secret-canary" not in json.dumps(result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", {"secret": "canary"}),
        ("service_id", STOREFRONT),
        ("observer_id", "render:" + STOREFRONT),
        ("observed_at", "2026-10-29T17:00:03Z"),
        ("captured_at", "2026-10-29T16:00:00Z"),
        ("business_success", True),
        ("full_chain_complete", True),
        ("activation_changed", True),
        ("gmail_captures", 1),
        ("acks", 1),
        ("render_captures", True),
        ("reused", 1),
        ("version", 2.0),
        ("scope_id", "render_deploy_broker"),
        ("evidence_sha256", "foreign"),
        ("secret", "canary"),
    ],
)
def test_receipt_cannot_claim_different_service_time_or_business_result(field, value):
    obs, src = observation(), source()
    response = receipt(src, obs)
    response[field] = value
    with pytest.raises(RenderServiceError):
        ingest_module.validate_receipt(response, source=src, observation=obs)


def test_exact_replays_are_accepted_without_counting_new_captures(tmp_path):
    result = ingest(
        Bridge(lambda src, obs: receipt(src, obs, reused=True)), write_artifact(tmp_path)
    )
    assert result["render_captures"] == 0 and result["all_requested_services_captured"] is True
    assert all(r["reused"] is True for r in result["receipts"].values())


@pytest.mark.parametrize("partial", [False, True])
def test_ingest_cli_exit_status_distinguishes_complete_and_partial_capture(
    monkeypatch, tmp_path, capsys, partial
):
    payload = artifact()
    if partial:
        payload["services"].pop(STOREFRONT)
        payload["failures"][STOREFRONT] = "provider_outage"
    path = write_artifact(tmp_path, payload)
    monkeypatch.setattr(ingest_module, "DufyndJarvisBridge", Bridge)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ingest",
            "--artifact",
            str(path),
            "--expected-run-id",
            source()["run_id"],
            "--expected-sha",
            source()["sha"],
            "--expected-run-attempt",
            "1",
        ],
    )
    assert ingest_module.main() == (1 if partial else 0)
    saved = json.loads(capsys.readouterr().out)
    assert saved["business_success"] is False
    assert saved["all_requested_services_captured"] is (not partial)


def test_bridge_uses_exact_v2_rpc_and_never_calls_health_or_acceptance():
    requests = []
    obs, src = observation(), source()

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=receipt(src, obs))

    bridge = DufyndJarvisBridge(
        supabase_url="https://db.example",
        secret_key="private-db-secret",
        transport=httpx.MockTransport(handler),
    )
    result = bridge.capture_render_service_read(source=src, observation=obs)
    assert len(requests) == 1
    assert (
        str(requests[0].url)
        == "https://db.example/rest/v1/rpc/capture_dufynd_render_service_read_v2"
    )
    assert json.loads(requests[0].content) == {"p_source": src, "p_observation": obs}
    assert result["service_id"] == API


def test_workflow_v2_requires_explicit_flags_and_capture_is_separately_opted_in():
    workflow = yaml.safe_load(Path(".github/workflows/dufynd-private-observer.yml").read_text())
    trigger = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]
    assert trigger["mode"]["default"] == "render"
    assert trigger["mode"]["options"] == ["render", "all", "render_services_v2"]
    assert trigger["capture_v2"]["default"] is False
    assert trigger["capture_v2"]["type"] == "boolean"
    jobs = workflow["jobs"]
    for name in ("read-v2", "ingest-v2"):
        condition = jobs[name]["if"]
        for gate in (
            "github.event_name == 'workflow_dispatch'",
            "github.ref == 'refs/heads/scentai-mvp'",
            "inputs.mode == 'render_services_v2'",
            "vars.DUFYND_PRIVATE_BROKER_ENABLED == '1'",
            "vars.DUFYND_PRIVATE_RENDER_SERVICES_V2_ENABLED == '1'",
        ):
            assert gate in condition
    assert "inputs.capture_v2 == true" in jobs["ingest-v2"]["if"]
    assert "inputs.capture_v2" not in jobs["read-v2"]["if"]
    assert "always() && !cancelled()" in jobs["ingest-v2"]["if"]
    assert "needs['read-v2'].result == 'failure'" in jobs["ingest-v2"]["if"]
    assert jobs["ingest-v2"]["needs"] == "read-v2"
    assert jobs["read-v2"]["permissions"] == {"contents": "read", "id-token": "write"}
    assert jobs["ingest-v2"]["permissions"] == {"contents": "read", "actions": "read"}
    assert "SUPABASE" not in json.dumps(jobs["read-v2"])
    assert "id-token" not in json.dumps(jobs["ingest-v2"])
    assert "inputs.mode != 'render_services_v2'" in jobs["read"]["if"]
    assert "inputs.mode != 'render_services_v2'" in jobs["render-ingest"]["if"]
    assert jobs["ingest"]["if"] == "inputs.mode == 'all'"
    upload = next(s for s in jobs["read-v2"]["steps"] if "upload-artifact" in s.get("uses", ""))
    assert upload["if"] == "always() && !cancelled()"
    assert upload["with"]["path"] == ARTIFACT_FILE
    assert (
        upload["with"]["name"]
        == "private-render-services-v2-${{ github.run_id }}-${{ github.run_attempt }}"
    )
    assert upload["with"]["retention-days"] == 1
    ingest_run = next(
        s["run"]
        for s in jobs["ingest-v2"]["steps"]
        if "private_render_services_ingest" in s.get("run", "")
    )
    assert '--expected-run-id "${GITHUB_RUN_ID}"' in ingest_run
    assert '--expected-sha "${GITHUB_SHA}"' in ingest_run
    assert '--expected-run-attempt "${GITHUB_RUN_ATTEMPT}"' in ingest_run
