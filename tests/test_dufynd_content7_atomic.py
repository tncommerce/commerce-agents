"""Actual migrations/RPCs on isolated PostgreSQL. Synthetic data only in CI.

Local PGlite covers transactions but not parallel connections; PostgreSQL CI
additionally runs the real two-connection contention test.
"""

import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from scripts.dufynd_seven_content_dispatch import (
    OWNER,
    SupabaseSevenWorkerDispatch,
    result_key,
    task_id,
    task_manifest,
)
from scripts.dufynd_seven_content_workers import DEPENDENCIES, HANDLERS, ROLE_ORDER, digest
from tests.content7_database import Database, SqlBridge
from tests.test_dufynd_seven_content_dispatch import editorial_fixture

pytestmark = pytest.mark.skipif(
    not (os.getenv("DUFYND_PGLITE_MODULE") or os.getenv("DUFYND_CONTENT_TEST_DATABASE_URL")),
    reason="requires isolated local PostgreSQL; never uses production credentials",
)


@pytest.fixture(scope="module")
def database():
    db = Database()
    db.bootstrap()
    yield db
    db.close()


def prepare(database, source=None, existing=None):
    """TEST-ONLY activation in ephemeral DB; not an activation entry point."""
    source = copy.deepcopy(source or editorial_fixture())
    source.setdefault("round_id", "dufynd_editorial_sql_" + uuid4().hex)
    existing = copy.deepcopy(existing or {"reserved": {"2026-10-12": "Torwart"}})
    context = {"round": source["round_id"], "pilot": source, "existing": existing}
    database.query(
        "insert into public.dufynd_master_status(key,value) values($1,$2::jsonb)",
        ["content.seven_workers.runtime.source." + source["round_id"], json.dumps(context)],
    )
    for row in task_manifest(source["round_id"], source, existing):
        row.update(status="ready", worker_state="ready")
        columns = list(row)
        args = [
            f"${i + 1}" + ("::jsonb" if isinstance(row[k], (dict, list)) else "")
            for i, k in enumerate(columns)
        ]
        database.query(
            f"insert into public.dufynd_autonomy_tasks({','.join(columns)}) values({','.join(args)})",
            [json.dumps(row[k]) if isinstance(row[k], (dict, list)) else row[k] for k in columns],
        )
    database.query(
        "update public.dufynd_handler_contracts set enabled=true, "
        'contract=contract||\'{"certification_status":"certified"}\'::jsonb '
        "where handler_id like 'seven_content_%'"
    )
    bridge = SqlBridge(database)
    return bridge, SupabaseSevenWorkerDispatch(bridge, source=source, existing=existing)


def claim_packet(bridge, dispatch, role="W1"):
    tid = task_id(dispatch.round_id, role)
    assert bridge.claim_worker(tid, OWNER)
    bridge.update_worker(tid, "working")
    prior = {r: dispatch._read_saved(r) for r in DEPENDENCIES[role]}
    result = HANDLERS[role](dispatch.source[role], prior, dispatch.existing)
    value = dict(
        schema_version=1,
        role_version=1,
        round_id=dispatch.round_id,
        role=role,
        task_id=tid,
        source_sha256=dispatch.source_sha,
        packet_sha256=digest(result),
        packet=result,
        predecessor_sha256={r: digest(prior[r]) for r in prior},
        cost_eur=0,
        approved_for_publication=False,
        visual_quality_verified=False,
    )
    return dict(p_task_id=tid, p_token=bridge.worker_tokens[tid], p_value=value)


def commit(bridge, payload):
    return bridge._rpc("commit_dufynd_content7_result_v1", payload)


def test_default_migration_contracts_disabled(database):
    rows = database.query(
        "select enabled,contract from public.dufynd_handler_contracts "
        "where handler_id like 'seven_content_%'"
    )
    assert len(rows) == 7
    assert all(not r["enabled"] for r in rows)
    assert all(r["contract"]["certification_status"] == "pending_activation_review" for r in rows)


def test_full_seven_workers_exact_receipts_and_no_duplicate_claim(database, monkeypatch):
    import httpx

    def forbidden(*args, **kwargs):
        raise AssertionError("No HTTP/provider in local E2E")

    monkeypatch.setattr(httpx.Client, "request", forbidden)
    bridge, dispatch = prepare(database)
    statuses = dispatch.run_all()
    assert len(statuses) == 7
    assert all(r["state"] in {"DONE", "DONE_WITH_HOLDS"} for r in statuses)
    for role in ROLE_ORDER:
        task = bridge.load_autonomy_task(task_id(dispatch.round_id, role))
        value = bridge.load_master_status_entry(result_key(dispatch.round_id, role))["value"]
        assert task["worker_state"] == task["status"] == "done"
        assert task["released_at"] is not None
        assert not value["approved_for_publication"]
        assert not value["visual_quality_verified"]
        assert value["packet_sha256"] == digest(value["packet"])
        assert commit(
            bridge, dict(p_task_id=task["task_id"], p_token=str(task["lease_token"]), p_value=value)
        )
    assert all(r["state"] == "ALREADY_DONE" for r in dispatch.run_all())
    assert len(dispatch.build_editor_review_bundle()["candidates"]) == 3


@pytest.mark.parametrize(
    "mutation",
    ["wrong_token", "expired", "disabled", "source", "hash", "cost", "publication", "predecessor"],
)
def test_fail_closed_no_result_or_done(database, mutation):
    bridge, dispatch = prepare(database)
    payload = claim_packet(bridge, dispatch)
    tid = payload["p_task_id"]
    if mutation == "wrong_token":
        payload["p_token"] = str(uuid4())
    elif mutation == "expired":
        database.query(
            "begin; select set_config('dufynd.worker_write','supervisor',true); "
            "update public.dufynd_autonomy_tasks set lease_expires_at=clock_timestamp()-interval '1 second' "
            f"where task_id='{tid}'; commit;",
            script=True,
        )
    elif mutation == "disabled":
        database.query(
            "update public.dufynd_handler_contracts set enabled=false where handler_id='seven_content_w1_v1'"
        )
    elif mutation == "source":
        database.query(
            "update public.dufynd_master_status set value=value||'{\"tampered\":true}'::jsonb where key=$1",
            ["content.seven_workers.runtime.source." + dispatch.round_id],
        )
    else:
        key, value = {
            "hash": ("packet_sha256", "0" * 64),
            "cost": ("cost_eur", 1),
            "publication": ("approved_for_publication", True),
            "predecessor": ("predecessor_sha256", {"W7": "fake"}),
        }[mutation]
        payload["p_value"][key] = value
    try:
        assert commit(bridge, payload) is False
    except Exception as error:
        assert any(s in str(error) for s in ("mismatch", "invalid_result"))
    assert bridge.load_master_status_entry(result_key(dispatch.round_id, "W1")) is None
    assert bridge.load_autonomy_task(tid)["status"] != "done"


def test_failure_after_insert_rolls_back_result_and_task(database):
    bridge, dispatch = prepare(database)
    payload = claim_packet(bridge, dispatch)
    database.query(
        """create function public.test_reject_done() returns trigger language plpgsql as $$
      begin if new.worker_state='done' then raise exception 'injected_final_update_failure'; end if;
      return new; end $$;
      create trigger test_reject_done before update on public.dufynd_autonomy_tasks
      for each row execute function public.test_reject_done();""",
        script=True,
    )
    try:
        with pytest.raises(Exception, match="injected_final_update_failure"):
            commit(bridge, payload)
        assert bridge.load_master_status_entry(result_key(dispatch.round_id, "W1")) is None
        assert bridge.load_autonomy_task(payload["p_task_id"])["worker_state"] == "working"
    finally:
        database.query(
            "drop trigger test_reject_done on public.dufynd_autonomy_tasks; "
            "drop function public.test_reject_done();",
            script=True,
        )
    assert commit(bridge, payload)


def test_receipt_immutable_and_wrong_token_cannot_replay(database):
    bridge, dispatch = prepare(database)
    payload = claim_packet(bridge, dispatch)
    assert commit(bridge, payload)
    modified = copy.deepcopy(payload)
    modified["p_value"]["packet"]["output"]["voice"] = "Changed after commit"
    modified["p_value"]["packet_sha256"] = digest(modified["p_value"]["packet"])
    with pytest.raises(Exception, match="immutable_result_conflict"):
        commit(bridge, modified)
    modified = copy.deepcopy(payload)
    modified["p_token"] = str(uuid4())
    assert commit(bridge, modified) is False


def test_public_roles_cannot_execute(database):
    for role in ("anon", "authenticated"):
        assert (
            database.query(
                "select has_function_privilege($1, "
                "'public.commit_dufynd_content7_result_v1(text,uuid,jsonb)', 'EXECUTE') as allowed",
                [role],
            )[0]["allowed"]
            is False
        )


@pytest.mark.parametrize(
    "role,mutation",
    [("W2", "crosslink"), ("W2", "visual"), ("W7", "placeholder"), ("W7", "schedule")],
)
def test_sql_gates_cannot_be_bypassed_by_forged_packet(database, role, mutation):
    bridge, dispatch = prepare(database)
    for predecessor in ROLE_ORDER:
        if predecessor == role:
            break
        dispatch.run_role(predecessor)
    payload = claim_packet(bridge, dispatch, role)
    output = payload["p_value"]["packet"]["output"]
    if mutation == "crosslink":
        output["ideas"][0]["hook"] = "Unregistered hook"
    elif mutation == "visual":
        output["ideas"][0]["visual_score"] = 9.5
    elif mutation == "placeholder":
        output["slots"][0]["hook"] = "TBD"
    else:
        output["slots"][0]["scheduled"] = True
    payload["p_value"]["packet_sha256"] = digest(payload["p_value"]["packet"])
    with pytest.raises(Exception, match="invalid_writer|calendar_source|invalid_calendar"):
        commit(bridge, payload)
    assert bridge.load_master_status_entry(result_key(dispatch.round_id, role)) is None


def test_expired_claim_recovery_fences_old_owner(database):
    bridge, dispatch = prepare(database)
    old = claim_packet(bridge, dispatch)
    tid = old["p_task_id"]
    database.query(
        "begin; select set_config('dufynd.worker_write','supervisor',true); "
        "update public.dufynd_autonomy_tasks set lease_expires_at=clock_timestamp()-interval '1 second' "
        f"where task_id='{tid}'; commit;",
        script=True,
    )
    replacement = SqlBridge(database)
    assert replacement.claim_worker(tid, OWNER)
    assert replacement.worker_tokens[tid] != old["p_token"]
    assert commit(bridge, old) is False
    old["p_token"] = replacement.worker_tokens[tid]
    assert commit(replacement, old)


@pytest.mark.skipif(
    bool(os.getenv("DUFYND_PGLITE_MODULE")), reason="requires two native PostgreSQL connections"
)
def test_concurrent_claim_and_identical_commit_have_single_result(database):
    bridge, dispatch = prepare(database)
    tid = task_id(dispatch.round_id, "W1")
    barrier = Barrier(2)

    def claim():
        db = Database()
        b = SqlBridge(db)
        try:
            barrier.wait(timeout=10)
            result = b.claim_worker(tid, OWNER)
            return b.worker_tokens.get(tid) if result else None
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        tokens = list(pool.map(lambda _: claim(), range(2)))
    assert len([t for t in tokens if t]) == 1
    bridge.worker_tokens[tid] = next(t for t in tokens if t)
    # Construct the same deterministic envelope without claiming twice.
    result = HANDLERS["W1"](dispatch.source["W1"], {}, dispatch.existing)
    value = dict(
        schema_version=1,
        role_version=1,
        round_id=dispatch.round_id,
        role="W1",
        task_id=tid,
        source_sha256=dispatch.source_sha,
        packet_sha256=digest(result),
        packet=result,
        predecessor_sha256={},
        cost_eur=0,
        approved_for_publication=False,
        visual_quality_verified=False,
    )
    payload = dict(p_task_id=tid, p_token=bridge.worker_tokens[tid], p_value=value)
    barrier = Barrier(2)

    def finish():
        db = Database()
        try:
            barrier.wait(timeout=10)
            return commit(SqlBridge(db), payload)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: finish(), range(2))) == [True, True]
    assert (
        database.query(
            "select count(*) as n from public.dufynd_master_status where key=$1",
            [result_key(dispatch.round_id, "W1")],
        )[0]["n"]
        == 1
    )
