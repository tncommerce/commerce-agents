"""New-input acceptance on the real prepared RPCs, never production credentials."""

import copy
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from scripts.dufynd_content7_activation import (
    build_activation_plan,
    commission_free_inputs,
    ready_content_tasks,
    run_free_content_tick,
)
from scripts.dufynd_seven_content_dispatch import SupabaseSevenWorkerDispatch, result_key, task_id
from scripts.dufynd_seven_content_workers import ROLE_ORDER, WorkerInputError, digest
from tests.content7_database import Database, SqlBridge
from tests.test_dufynd_seven_content_dispatch import editorial_fixture

SQL = pytest.mark.skipif(
    not (os.getenv("DUFYND_PGLITE_MODULE") or os.getenv("DUFYND_CONTENT_TEST_DATABASE_URL")),
    reason="isolated SQL database required",
)


def fresh_input():
    source = editorial_fixture()
    uid = uuid4().hex
    source.update(
        round_id="dufynd_editorial_readiness_" + uid,
        input_version=2,
        source_key="content.seven_worker_new_input_" + uid,
        provenance={
            "producer": "work_editorial",
            "cost_eur": 0,
            "provider_requests": 0,
            "autonomous_generation": False,
        },
    )
    for i, idea in enumerate(source["W2"]["ideas"]):
        idea["title"] = f"Independent new scenario {uid} {i}"
    frozen = {"title": "An immutable Owner final"}
    existing = {
        "snapshot_verified": True,
        "observed_at": datetime.now(UTC).isoformat(),
        "frozen_refs": {"content.test_final": {"record_sha256": digest(frozen)}},
    }
    return source, existing


def test_free_commission_reads_existing_components_and_reports_missing_generator():
    class Reader:
        def _rpc(self, name):
            assert name.startswith("read_dufynd_")
            if name.endswith("reuse_audit_v1"):
                raise RuntimeError("unavailable")
            return {"existing": "source"}

    result = commission_free_inputs(Reader())
    assert result["state"] == "WAITING_EDITORIAL_INPUT"
    assert result["provider_requests"] == result["cost_eur"] == 0
    assert not result["autonomous_creative_generation"]
    assert [r["state"] for r in result["evidence"].values()].count("HOLD") == 1


@pytest.mark.parametrize(
    "mutation", ["provider", "cost", "stale", "duplicate", "hook", "calendar_link"]
)
def test_input_preparation_fails_closed(mutation):
    source, existing = fresh_input()
    if mutation == "provider":
        source["provenance"]["producer"] = "allegedly_free_llm"
    elif mutation == "cost":
        source["provenance"]["cost_eur"] = 1
    elif mutation == "stale":
        existing["observed_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    elif mutation == "duplicate":
        existing["published_titles"] = [source["W2"]["ideas"][0]["title"]]
    elif mutation == "hook":
        source["W2"]["ideas"][0]["hook"] = "Unlinked hook"
    else:
        source["W7"]["calendar"][0]["writer_idea_id"] = source["W2"]["ideas"][0]["id"]
    with pytest.raises(WorkerInputError):
        build_activation_plan(source, existing)


def test_environment_flag_is_not_an_activation_and_defaults_off(monkeypatch):
    monkeypatch.delenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO", raising=False)
    assert ready_content_tasks({"safe_to_execute": [{"status": "ready"}]}) == []
    assert run_free_content_tick(None)["state"] == "DISABLED"


def test_nightshift_runs_free_roles_before_and_without_model_budget(monkeypatch):
    import asyncio

    from scripts import dufynd_content7_activation as activation
    from scripts import dufynd_jarvis_nightshift as nightshift
    from tests.test_dufynd_jarvis_nightshift import FakeBridge

    monkeypatch.setenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO", "1")
    monkeypatch.setattr(nightshift, "_require_autonomous_mode", lambda: None)
    monkeypatch.setattr(
        nightshift, "_require_budget_window", lambda b: pytest.fail("No paid budget entry")
    )
    monkeypatch.setattr(
        activation,
        "run_free_content_tick",
        lambda b, **k: {"results": [{"state": "DONE"}], "cost_eur": 0},
    )
    result = asyncio.run(nightshift.run_nightshift(FakeBridge(), max_events=0))
    assert result["stop_reason"] == "free_content_complete"
    assert result["free_content"]["cost_eur"] == 0


def test_supervisor_selects_free_roles_while_provider_is_parked(monkeypatch):
    from scripts import dufynd_jarvis_supervisor as supervisor
    from scripts.dufynd_seven_content_dispatch import task_manifest
    from tests.test_dufynd_jarvis_supervisor import FakeBridge

    source, existing = fresh_input()
    task = task_manifest(source["round_id"], source, existing)[0]
    task["status"] = "ready"
    monkeypatch.setenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO", "1")
    preflight = supervisor._preflight(FakeBridge([task]))
    assert preflight["potential_work"]
    assert preflight["free_content_task_count"] == 1
    assert preflight["safe_task_count"] == 0
    assert preflight["model_execution_available"] is False


@pytest.fixture(scope="module")
def database():
    db = Database()
    db.bootstrap()
    db.query(
        "insert into public.dufynd_master_status(key,value) values('content.test_final',$1::jsonb)",
        [json.dumps({"title": "An immutable Owner final"})],
    )
    yield db
    db.close()


def approval(db, plan, *, status="approved", action="content7_atomic_activation"):
    did = "test_decision_" + uuid4().hex
    context = {
        "round_id": plan["context"]["round"],
        "source_sha256": plan["source_sha256"],
        "plan_sha256": digest(plan),
    }
    db.query(
        "insert into public.dufynd_human_decisions(decision_id,status,action_type,context) values($1,$2,$3,$4::jsonb)",
        [did, status, action, json.dumps(context)],
    )
    return did


def activate(db, source=None, existing=None):
    if source is None:
        source, existing = fresh_input()
    plan = build_activation_plan(source, existing)
    did = approval(db, plan)
    bridge = SqlBridge(db)
    receipt = bridge._rpc("activate_dufynd_content7_v1", {"p_decision_id": did, "p_plan": plan})
    return bridge, source, existing, plan, receipt


@SQL
def test_new_input_automatic_seven_role_handoff_and_idempotent_activation(database, monkeypatch):
    import httpx

    monkeypatch.setenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO", "1")
    monkeypatch.setattr(
        httpx.Client, "request", lambda *a, **k: pytest.fail("No HTTP/provider permitted")
    )
    bridge, source, existing, plan, receipt = activate(database)
    assert (
        bridge._rpc(
            "activate_dufynd_content7_v1", {"p_decision_id": receipt["decision_id"], "p_plan": plan}
        )
        == receipt
    )
    assert [
        t["durable_payload"]["role"]
        for t in bridge.load_autonomy_queue()["safe_to_execute"]
        if t["task_id"].startswith("content7:" + source["round_id"])
    ] == ["W1"]
    # Queue dependency readiness, leases, activation and result RPCs are real SQL.
    run = run_free_content_tick(bridge)
    assert [r["role"] for r in run["results"]] == list(ROLE_ORDER)
    assert all(r["state"] in {"DONE", "DONE_WITH_HOLDS"} for r in run["results"])
    assert run_free_content_tick(bridge)["results"] == []
    dispatch = SupabaseSevenWorkerDispatch(bridge, source=source, existing=existing)
    bundle = dispatch.build_editor_review_bundle()
    assert len(bundle["candidates"]) == 3 and bundle["visual_score"] is None
    assert not bundle["creative_go"] and not bundle["publish_go"]
    for role in ROLE_ORDER:
        value = bridge.load_master_status_entry(result_key(source["round_id"], role))["value"]
        assert value["packet_sha256"] == digest(value["packet"])
        assert bridge.load_autonomy_task(task_id(source["round_id"], role))["released_at"]


@SQL
@pytest.mark.parametrize(
    "mutation", ["pending", "creative_go", "plan_changed", "stale", "freeze_changed", "paid"]
)
def test_activation_rejects_without_partial_tasks(database, mutation):
    source, existing = fresh_input()
    plan = build_activation_plan(source, existing)
    if mutation == "stale":
        plan["context"]["existing"]["observed_at"] = "2020-01-01T00:00:00Z"
    if mutation == "freeze_changed":
        plan["context"]["existing"]["frozen_refs"]["content.test_final"]["record_sha256"] = "0" * 64
    if mutation == "paid":
        plan["context"]["pilot"]["provenance"]["cost_eur"] = 1
    plan["source_sha256"] = digest(plan["context"])
    did = approval(
        database,
        plan,
        status="pending" if mutation == "pending" else "approved",
        action="content_candidate_review"
        if mutation == "creative_go"
        else "content7_atomic_activation",
    )
    if mutation == "plan_changed":
        plan["context"]["pilot"]["W1"]["voice"] = "changed after GO"
        plan["source_sha256"] = digest(plan["context"])
    with pytest.raises(Exception, match="required|changed|invalid_activation"):
        SqlBridge(database)._rpc(
            "activate_dufynd_content7_v1", {"p_decision_id": did, "p_plan": plan}
        )
    assert (
        database.query(
            "select count(*) as n from public.dufynd_autonomy_tasks where task_id like $1",
            ["content7:" + source["round_id"] + ":%"],
        )[0]["n"]
        == 0
    )


@SQL
def test_cross_round_duplicate_and_live_existing_idea_rejected(database):
    bridge, source, existing, _, _ = activate(database)
    clone = copy.deepcopy(source)
    clone["round_id"] += "_copy"
    clone["W2"]["ideas"][0]["id"] = "new-id-does-not-evade-duplicate"
    plan = build_activation_plan(clone, existing)
    with pytest.raises(Exception, match="existing_content_duplicate"):
        bridge._rpc(
            "activate_dufynd_content7_v1",
            {"p_decision_id": approval(database, plan), "p_plan": plan},
        )
    # Pause so subsequent tests have no unrelated ready work.
    receipt = bridge.load_master_status_entry(
        "content.seven_workers.activation." + source["round_id"]
    )["value"]
    bridge._rpc(
        "pause_dufynd_content7_v1",
        {"p_round": source["round_id"], "p_plan_sha256": receipt["plan_sha256"]},
    )
    source, existing = fresh_input()
    database.query(
        "insert into public.dufynd_content_ideas(id,title,status) values($1,$2,'published')",
        [uuid4().hex, source["W2"]["ideas"][0]["title"]],
    )
    plan = build_activation_plan(source, existing)
    with pytest.raises(Exception, match="existing_content_duplicate"):
        bridge._rpc(
            "activate_dufynd_content7_v1",
            {"p_decision_id": approval(database, plan), "p_plan": plan},
        )


@SQL
def test_revocation_blocks_commit_even_after_claim(database):
    from tests.test_dufynd_content7_atomic import claim_packet

    bridge, source, existing, _, receipt = activate(database)
    dispatch = SupabaseSevenWorkerDispatch(bridge, source=source, existing=existing)
    payload = claim_packet(bridge, dispatch)
    database.query(
        "update public.dufynd_human_decisions set status='revoked' where decision_id=$1",
        [receipt["decision_id"]],
    )
    assert bridge._rpc("commit_dufynd_content7_result_v1", payload) is False
    assert bridge.load_master_status_entry(result_key(source["round_id"], "W1")) is None


@SQL
def test_crash_before_commit_recovers_existing_expired_lease(database, monkeypatch):
    monkeypatch.setenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO", "1")
    bridge, source, existing, _, _ = activate(database)
    # Filter unrelated test rounds, equivalent to queue ordering in a clean pilot DB.
    real_queue = bridge.load_autonomy_queue
    bridge.load_autonomy_queue = lambda: {
        "safe_to_execute": [
            r
            for r in real_queue()["safe_to_execute"]
            if r["durable_payload"]["round_id"] == source["round_id"]
        ]
    }
    original_rpc = bridge._rpc

    def crash(name, payload=None):
        if name == "commit_dufynd_content7_result_v1":
            raise ConnectionError("simulated disconnected response")
        return original_rpc(name, payload)

    monkeypatch.setattr(bridge, "_rpc", crash)
    failed = run_free_content_tick(bridge, max_tasks=1)
    assert failed["results"][0]["state"] == "RETRY_AFTER_LEASE_RECOVERY"
    tid = task_id(source["round_id"], "W1")
    old_token = bridge.worker_tokens[tid]
    database.query(
        "begin; select set_config('dufynd.worker_write','supervisor',true); update public.dufynd_autonomy_tasks set lease_expires_at=clock_timestamp()-interval '1 second' where task_id='"
        + tid
        + "'; commit;",
        script=True,
    )
    monkeypatch.setattr(bridge, "_rpc", original_rpc)
    recovered = run_free_content_tick(bridge)
    assert len(recovered["results"]) == 7
    assert all(r["state"] in {"DONE", "DONE_WITH_HOLDS"} for r in recovered["results"])
    assert bridge.load_autonomy_task(tid)["lease_token"] != old_token
    assert (
        len(
            SupabaseSevenWorkerDispatch(
                bridge, source=source, existing=existing
            ).build_editor_review_bundle()["candidates"]
        )
        == 3
    )


@SQL
def test_activation_rpc_private_grants(database):
    for role in ("anon", "authenticated"):
        for signature in (
            "activate_dufynd_content7_v1(text,jsonb)",
            "pause_dufynd_content7_v1(text,text)",
            "dufynd_content7_activation_allowed_v1(text)",
        ):
            assert (
                database.query(
                    "select has_function_privilege($1,$2,'EXECUTE') as allowed",
                    [role, "public." + signature],
                )[0]["allowed"]
                is False
            )


@SQL
def test_lost_commit_response_reads_done_receipt_without_duplicate(database, monkeypatch):
    monkeypatch.setenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO", "1")
    bridge, source, _, _, _ = activate(database)
    real_queue = bridge.load_autonomy_queue
    bridge.load_autonomy_queue = lambda: {
        "safe_to_execute": [
            r
            for r in real_queue()["safe_to_execute"]
            if r["durable_payload"]["round_id"] == source["round_id"]
        ]
    }
    real_rpc = bridge._rpc

    def lost_response(name, payload=None):
        result = real_rpc(name, payload)
        if name == "commit_dufynd_content7_result_v1":
            raise ConnectionError("response lost AFTER transaction committed")
        return result

    monkeypatch.setattr(bridge, "_rpc", lost_response)
    run = run_free_content_tick(bridge)
    assert len(run["results"]) == 7
    assert all(r["state"] == "COMMITTED_RESPONSE_LOST" for r in run["results"])
    assert run_free_content_tick(bridge)["results"] == []
    assert (
        database.query(
            "select count(*) as n from public.dufynd_master_status where key like $1",
            ["content.seven_workers.runtime." + source["round_id"] + ".W%"],
        )[0]["n"]
        == 7
    )


@SQL
def test_blocked_research_does_not_block_independent_authority_worker(database, monkeypatch):
    from scripts.dufynd_seven_content_workers import HANDLERS, packet

    monkeypatch.setenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO", "1")
    bridge, source, _, _, _ = activate(database)
    real_queue = bridge.load_autonomy_queue
    bridge.load_autonomy_queue = lambda: {
        "safe_to_execute": [
            r
            for r in real_queue()["safe_to_execute"]
            if r["durable_payload"]["round_id"] == source["round_id"]
        ]
    }
    monkeypatch.setitem(HANDLERS, "W3", lambda *args: packet("BLOCKED", {}, ["source_unavailable"]))
    run = run_free_content_tick(bridge)
    assert [(r["role"], r["state"]) for r in run["results"]] == [
        ("W1", "DONE"),
        ("W3", "BLOCKED"),
        ("W4", "DONE_WITH_HOLDS"),
    ]
    assert bridge.load_autonomy_task(task_id(source["round_id"], "W5"))["status"] == "planned"
