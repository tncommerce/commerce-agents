"""Actual runtime, streaming reader and REST capture payloads against native SQL."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from private_broker import render_service_read as reader
from private_broker.render_service_contract import ARTIFACT_FILE, timestamp
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_private_render_services_ingest import ingest_artifact
from tests.test_dufynd_render_services_v2_postgres import (
    API,
    DSN,
    SERVICES,
    SOURCE,
    STORE,
    database,
    observer,
    seed,
    state,
)
from tests.test_private_broker_render_services_runtime import deployment, make_client

pytestmark = pytest.mark.skipif(not DSN, reason="dedicated disposable PostgreSQL required")


@pytest.mark.parametrize("storefront_fails", [False, True], ids=["both-live", "partial-peer"])
def test_runtime_read_artifact_rest_rpc_and_native_receipts(
    monkeypatch, tmp_path, storefront_fails
):
    provider_calls, authenticated_tokens, rpc_services = [], [], []

    def provider(request):
        assert request.method == "GET" and request.url.host == "api.render.com"
        service = request.url.path.split("/")[-2]
        assert service in SERVICES
        provider_calls.append(service)
        if service == STORE and storefront_fails:
            return httpx.Response(503, text="upstream-secret-canary")
        return httpx.Response(200, json=[{"deploy": deployment(service)}])

    client, vault = make_client(provider, auth=SimpleNamespace(verify=authenticated_tokens.append))
    original_client = httpx.Client

    def reader_transport(request):
        assert request.method == "GET"
        if request.url.host == "oidc.example":
            assert request.headers["authorization"] == "Bearer request-canary"
            assert dict(request.url.params) == {"audience": "https://broker.example"}
            return httpx.Response(200, json={"value": "workload-canary"})
        assert request.url.host == "broker.example"
        reply = client.get(request.url.path, headers=dict(request.headers))
        return httpx.Response(reply.status_code, content=reply.content, headers=reply.headers)

    with database(DSN) as db, client:
        seed(db)
        before = state(db)
        started = db.execute("SELECT clock_timestamp()").fetchone()[0]
        with monkeypatch.context() as scoped:
            scoped.chdir(tmp_path)
            for key, value in {
                "DUFYND_PRIVATE_RENDER_SERVICES_V2_ENABLED": "1",
                "BROKER_ORIGIN": "https://broker.example",
                "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example/token",
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-canary",
                **{
                    "GITHUB_" + key.upper(): value
                    for key, value in SOURCE.items()
                    if key != "version"
                },
            }.items():
                scoped.setenv(key, value)
            scoped.setattr(
                reader.httpx,
                "Client",
                lambda **kwargs: original_client(
                    transport=httpx.MockTransport(reader_transport), **kwargs
                ),
            )
            if storefront_fails:
                with pytest.raises(SystemExit, match="read incomplete"):
                    reader.main()
            else:
                reader.main()
        finished = db.execute("SELECT clock_timestamp()").fetchone()[0]
        artifact_path = tmp_path / ARTIFACT_FILE
        artifact = json.loads(artifact_path.read_text())
        expected = {API} if storefront_fails else set(SERVICES)
        assert set(artifact["services"]) == expected
        assert set(artifact["failures"]) == ({STORE} if storefront_fails else set())
        assert artifact["_meta"] == SOURCE
        assert "canary" not in artifact_path.read_text()
        assert provider_calls == list(SERVICES)
        assert authenticated_tokens == ["workload-canary", "workload-canary"]
        assert vault.calls == []

        def rpc(request):
            assert request.method == "POST"
            assert (
                request.url
                == "https://database.example/rest/v1/rpc/capture_dufynd_render_service_read_v2"
            )
            assert request.headers["apikey"] == "database-canary"
            assert "authorization" not in request.headers
            payload = json.loads(request.content)
            assert set(payload) == {"p_source", "p_observation"}
            rpc_services.append(payload["p_observation"]["service_id"])
            result = db.execute(
                "SELECT public.capture_dufynd_render_service_read_v2(%s::jsonb,%s::jsonb)",
                (json.dumps(payload["p_source"]), json.dumps(payload["p_observation"])),
            ).fetchone()[0]
            return httpx.Response(200, json=result)

        bridge = DufyndJarvisBridge(
            supabase_url="https://database.example",
            secret_key="database-canary",
            transport=httpx.MockTransport(rpc),
        )
        provenance = {
            "expected_run_id": SOURCE["run_id"],
            "expected_sha": SOURCE["sha"],
            "expected_run_attempt": SOURCE["run_attempt"],
        }
        result = ingest_artifact(bridge, artifact_path, **provenance)
        assert set(result["receipts"]) == expected, result
        assert result["render_captures"] == len(expected)
        assert result["all_requested_services_captured"] is (not storefront_fails)
        assert result["failures"] == artifact["failures"]
        assert result["gmail_captures"] == result["acks"] == 0
        assert not any(
            result[key] for key in ("activation_changed", "business_success", "full_chain_complete")
        )
        after = state(db)
        for service, receipt in result["receipts"].items():
            observed = timestamp(artifact["services"][service]["observed_at"])
            assert started - timedelta(seconds=1) <= observed <= finished + timedelta(seconds=1)
            assert timestamp(receipt["observed_at"]) == observed
            assert observer(db, service)["last_success_at"] == receipt["observed_at"]
            assert receipt["source"] == SOURCE and receipt["accepted"] is True
        assert len(after["receipts"]) == len(expected)
        for key in ("credentials", "pause", "sessions", "scopes", "legacy"):
            assert after[key] == before[key]
        if storefront_fails:
            assert observer(db, STORE) == next(
                row for row in before["observers"] if row["source_id"] == STORE
            )
        replay = ingest_artifact(bridge, artifact_path, **provenance)
        assert replay["render_captures"] == 0
        assert all(receipt["reused"] for receipt in replay["receipts"].values())
        assert replay["all_requested_services_captured"] is (not storefront_fails)
        assert state(db) == after
        assert rpc_services == [service for service in SERVICES if service in expected] * 2
        assert vault.calls == []
