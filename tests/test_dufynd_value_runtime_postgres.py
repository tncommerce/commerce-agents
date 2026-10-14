"""Actual PostgreSQL + HTTP Jarvis bridge + isolated Python worker E2E.

Never uses production credentials. Synthetic decisions are created only in the
existing explicitly named localhost content7_test disposable CI database.
"""

import copy
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Barrier, Thread
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_nightshift_value_v2 import sha
from scripts.dufynd_value_runtime_v2 import evaluate, run
from tests.content7_database import ROOT, Database, SqlBridge
from tests.test_dufynd_value_runtime_v2 import manifest

pytestmark = pytest.mark.skipif(
    not os.getenv("DUFYND_CONTENT_TEST_DATABASE_URL"),
    reason="real isolated localhost PostgreSQL required",
)
RPC = {
    "arm_dufynd_value_v2",
    "claim_dufynd_value_v2",
    "commit_dufynd_value_v2",
    "stop_dufynd_value_v2",
}


class Bridge(SqlBridge):
    def _rpc(self, name, payload=None):
        if name not in RPC:
            return super()._rpc(name, payload)
        values = list((payload or {}).values())
        args = [
            f"${i + 1}" + ("::jsonb" if isinstance(v, dict) else "") for i, v in enumerate(values)
        ]
        return self.database.query(
            f"select public.{name}({','.join(args)}) as value",
            [json.dumps(v) if isinstance(v, dict) else v for v in values],
        )[0]["value"]


@pytest.fixture(scope="module")
def database():
    db = Database()
    assert db.connection.info.host in {"127.0.0.1", "localhost", "::1"}
    assert db.connection.info.dbname == "content7_test"
    db.bootstrap()
    # Exercise installation with the actual live precondition: PR775's two hash
    # helpers absent, no need to apply/activate the seven-worker migrations live.
    db.query(
        "drop function public.dufynd_content7_sha_v1(jsonb); drop function public.dufynd_content7_canonical_v1(jsonb)",
        script=True,
    )
    db.query(
        next(
            (ROOT / "supabase/migrations").glob("*_dufynd_nightshift_value_runtime_v2.sql")
        ).read_text(),
        script=True,
    )
    # Sentinel registrations: verifies noninterference, NOT a pg_cron timing test.
    db.query(
        "create schema cron; create table cron.job(jobid int primary key, command text); insert into cron.job select n,'existing-command-'||n from generate_series(1,11) n",
        script=True,
    )
    yield db
    assert (
        db.query("select count(*) n from cron.job where command='existing-command-'||jobid")[0]["n"]
        == 11
    )
    db.query("drop schema cron cascade", script=True)
    db.close()


def arm(db, mutate=None):
    m = manifest()
    m["run_id"] = "dufynd_value_test_" + uuid4().hex
    # Different synthetic measurement/source identity, never live analytics.
    m["sources"]["editorial"]["value"]["round_id"] = m["run_id"]
    if mutate:
        mutate(m)
    m["pins"] = {k: sha(v) for k, v in m["sources"].items()}
    decision = "test_only_" + uuid4().hex
    db.query(
        "insert into dufynd_human_decisions(decision_id,status,action_type,context) values($1,'approved','nightshift_value_v2',$2::jsonb)",
        [decision, json.dumps({"run_id": m["run_id"], "manifest_sha256": sha(m)})],
    )
    result = Bridge(db)._rpc("arm_dufynd_value_v2", {"p_decision": decision, "p_manifest": m})
    return m, result, decision


def claim(b, m):
    return b._rpc(
        "claim_dufynd_value_v2",
        {"p_run": m["run_id"], "p_code_sha": m["code_sha"], "p_token": str(uuid4())},
    )


def receipt(c):
    value = evaluate(c)
    return dict(
        version=2,
        task_id=c["task"]["task_id"],
        handler=c["task"]["durable_payload"]["handler"],
        manifest_sha256=sha(c["manifest"]),
        result=value,
        result_sha256=sha(value),
    )


def commit(b, m, c, value):
    return b._rpc(
        "commit_dufynd_value_v2",
        {
            "p_run": m["run_id"],
            "p_task": c["task"]["task_id"],
            "p_token": c["token"],
            "p_receipt": value,
        },
    )


def expire(db, c):
    db.query(
        "begin; select set_config('dufynd.worker_write','supervisor',true); update dufynd_autonomy_tasks set lease_expires_at=clock_timestamp()-interval '1 second' where task_id='"
        + c["task"]["task_id"]
        + "'; commit",
        script=True,
    )


@contextmanager
def http_bridge(drop_commit=False):
    """Minimal transport adapter routes genuine production bridge HTTP into SQL.

    SQL functions remain REAL and every request gets a separate PG connection.
    No mock claim, finish, lock or result storage implementation exists here.
    """
    errors = []
    dropped = []

    class Server(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            name = self.path.rsplit("/", 1)[-1]
            if name not in RPC:
                self.send_error(403)
                return
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            db = Database()
            try:
                result = Bridge(db)._rpc(name, data)
                if drop_commit and name == "commit_dufynd_value_v2" and not dropped:
                    dropped.append(True)
                    self.close_connection = True
                    return
                self.reply(result)
            except Exception as e:
                errors.append(type(e).__name__)
                self.send_error(409)
            finally:
                db.close()

        def do_GET(self):
            u = urlsplit(self.path)
            table = u.path.rsplit("/", 1)[-1]
            key = {"dufynd_master_status": "key", "dufynd_autonomy_tasks": "task_id"}.get(table)
            if not key:
                self.send_error(403)
                return
            value = parse_qs(u.query)[key][0]
            if not value.startswith("eq."):
                self.send_error(403)
                return
            db = Database()
            try:
                self.reply(db.query(f"select * from public.{table} where {key}=$1", [value[3:]]))
            finally:
                db.close()

        def reply(self, result):
            data = json.dumps(result, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Server)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    bridge = DufyndJarvisBridge(
        supabase_url=f"http://127.0.0.1:{server.server_port}", secret_key="synthetic-local-only"
    )
    try:
        yield bridge, errors
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=5)


def test_http_to_real_sql_to_real_child_and_lost_response(database):
    m, r, _ = arm(database)
    with http_bridge(drop_commit=True) as (b, errors):
        result = run(b, m["run_id"], m["code_sha"])
        assert [x["state"] for x in result["results"]] == [
            "INTERNAL_ACTION_RECEIPT",
            "INTERNAL_EDITORIAL_HANDOFF",
        ]
        assert run(b, m["run_id"], m["code_sha"])["results"] == []
        assert not errors
    saved = Bridge(database).load_master_status_entry("jarvis.value_v2.run." + m["run_id"])["value"]
    assert saved["state"] == "completed" and not saved["active"]
    assert sorted(saved["attempts"].values()) == [1, 1]
    for tid in r["task_ids"]:
        assert Bridge(database).load_autonomy_task(tid)["status"] == "done"
        assert Bridge(database).load_master_status_entry("jarvis.value_v2.result." + tid)


def test_concurrent_connections_cannot_claim_same_task(database):
    m, _, _ = arm(database)
    barrier = Barrier(4)

    def race(_):
        db = Database()
        try:
            barrier.wait()
            return claim(Bridge(db), m)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(race, range(4)))
    got = [c for c in results if c]
    assert len(got) == 2 and len({c["task"]["task_id"] for c in got}) == 2
    Bridge(database)._rpc("stop_dufynd_value_v2", {"p_run": m["run_id"], "p_reason": "owner_stop"})


def test_actual_parent_process_kill_persists_claim_and_restart(database):
    m, _, _ = arm(database)
    with http_bridge() as (b, errors):
        code = "import os,signal; from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge; import scripts.dufynd_value_runtime_v2 as v; v.evaluate=lambda c: os.kill(os.getpid(),signal.SIGKILL); v.run(DufyndJarvisBridge(),os.environ['TEST_RUN'],'a'*40)"
        p = subprocess.run(
            [sys.executable, "-c", code],
            env={
                **os.environ,
                "SUPABASE_URL": b.supabase_url,
                "SUPABASE_SECRET_KEY": "synthetic-local-only",
                "TEST_RUN": m["run_id"],
            },
            capture_output=True,
        )
        assert p.returncode == -9
        row = database.query(
            "select * from dufynd_autonomy_tasks where durable_payload->>'run_id'=$1 and status='in_progress'",
            [m["run_id"]],
        )[0]
        old = {"task": row, "token": str(row["lease_token"])}
        expire(database, old)  # Explicit simulated elapsed lease, not fake wall-clock proof.
        assert len(run(b, m["run_id"], m["code_sha"])["results"]) == 2
        assert not errors
    attempts = Bridge(database).load_master_status_entry("jarvis.value_v2.run." + m["run_id"])[
        "value"
    ]["attempts"]
    assert sorted(attempts.values()) == [1, 2]


def test_hold_independent_and_unknown_sources_never_infer(database):
    def bad(m):
        m["sources"]["editorial"]["key"] = "unknown-unapproved-input"

    m, r, _ = arm(database, bad)
    result = run(Bridge(database), m["run_id"], m["code_sha"])
    assert [x["state"] for x in result["results"]] == ["INTERNAL_ACTION_RECEIPT", "OWNER_HOLD"]
    assert Bridge(database).load_autonomy_task(r["task_ids"][1])["status"] == "blocked"


def test_expired_token_fenced_and_new_claim_can_commit(database):
    m, _, _ = arm(database)
    b = Bridge(database)
    first = claim(b, m)
    val = receipt(first)
    expire(database, first)
    next_claim = claim(b, m)
    assert first["task"]["task_id"] == next_claim["task"]["task_id"]
    assert not commit(b, m, first, val)
    assert commit(b, m, next_claim, receipt(next_claim))


def test_hard_attempt_caps_survive_lease_losses(database):
    m, _, _ = arm(database)
    b = Bridge(database)
    for _ in range(6):
        c = claim(b, m)
        assert c
        expire(database, c)
    assert claim(b, m) is None
    saved = b.load_master_status_entry("jarvis.value_v2.run." + m["run_id"])["value"]
    assert sorted(saved["attempts"].values()) == [3, 3]


@pytest.mark.parametrize(
    "field,value",
    [
        ("cost_eur", 1),
        ("provider_calls", 1),
        ("max_tasks", 3),
        ("max_attempts", 4),
        ("max_total_attempts", 7),
    ],
)
def test_unapproved_budget_or_bounds_rejected(database, field, value):
    with pytest.raises(Exception, match="invalid_bounded_value_manifest"):
        arm(database, lambda m: m.update({field: value}))


def test_source_hash_wrong_decision_and_code_drift(database):
    m = manifest()
    b = Bridge(database)
    with pytest.raises(Exception, match="exact_owner_value_go_required"):
        b._rpc("arm_dufynd_value_v2", {"p_decision": "nonexistent-test-only", "p_manifest": m})
    m, r, d = arm(database)
    assert (
        b._rpc(
            "claim_dufynd_value_v2",
            {"p_run": m["run_id"], "p_code_sha": "b" * 40, "p_token": str(uuid4())},
        )
        is None
    )
    changed = copy.deepcopy(m)
    changed["sources"]["measurement"]["value"]["events"] = 99
    with pytest.raises(Exception, match="source_binding_invalid"):
        b._rpc("arm_dufynd_value_v2", {"p_decision": d, "p_manifest": changed})


def test_atomic_rollback_no_receipt_if_task_finish_fails(database):
    m, _, _ = arm(database)
    b = Bridge(database)
    c = claim(b, m)
    v = receipt(c)
    database.query(
        "create function test_value_fail() returns trigger language plpgsql as $$ begin if new.task_id='"
        + c["task"]["task_id"]
        + "' and new.worker_state='done' then raise exception 'injected_finish_failure'; end if; return new; end $$; create trigger zz_test_value_fail before update on dufynd_autonomy_tasks for each row execute function test_value_fail()",
        script=True,
    )
    try:
        with pytest.raises(Exception, match="injected_finish_failure"):
            commit(b, m, c, v)
        assert not b.load_master_status_entry("jarvis.value_v2.result." + c["task"]["task_id"])
        assert b.load_autonomy_task(c["task"]["task_id"])["worker_state"] == "claimed"
    finally:
        database.query(
            "drop trigger zz_test_value_fail on dufynd_autonomy_tasks; drop function test_value_fail()",
            script=True,
        )
    assert commit(b, m, c, v)
    assert commit(b, m, c, v)


def test_stop_idempotent_fences_inflight_and_preserves_completed(database):
    m, _, _ = arm(database)
    b = Bridge(database)
    a = claim(b, m)
    va = receipt(a)
    assert commit(b, m, a, va)
    c = claim(b, m)
    v = receipt(c)
    stopped = b._rpc("stop_dufynd_value_v2", {"p_run": m["run_id"], "p_reason": "owner_stop"})
    assert (
        b._rpc("stop_dufynd_value_v2", {"p_run": m["run_id"], "p_reason": "owner_stop"}) == stopped
    )
    assert not commit(b, m, c, v)
    assert commit(b, m, a, va)
    assert claim(b, m) is None


def test_generic_claim_and_status_update_cannot_bypass_guard(database):
    m, r, _ = arm(database)
    b = Bridge(database)
    with pytest.raises(Exception, match="value_claim_rpc_required"):
        b.claim_worker(r["task_ids"][0], "generic-model-path")
    c = claim(b, m)
    b.worker_tokens[c["task"]["task_id"]] = c["token"]
    b.update_worker(c["task"]["task_id"], "verifying", evidence="synthetic")
    with pytest.raises(Exception, match="atomic_value_receipt_required"):
        b.update_worker(c["task"]["task_id"], "done", evidence="synthetic")


def test_duplicate_sources_across_runs_and_immutable_checkpoints(database):
    m, r, d = arm(database)
    b = Bridge(database)
    assert b._rpc("arm_dufynd_value_v2", {"p_decision": d, "p_manifest": m}) == r
    other = copy.deepcopy(m)
    other["run_id"] = "dufynd_value_duplicate_" + uuid4().hex
    database.query(
        "insert into dufynd_human_decisions(decision_id,status,action_type,context) values($1,'approved','nightshift_value_v2',$2::jsonb)",
        [other["run_id"], json.dumps({"run_id": other["run_id"], "manifest_sha256": sha(other)})],
    )
    with pytest.raises(Exception, match="duplicate_value_task"):
        b._rpc("arm_dufynd_value_v2", {"p_decision": other["run_id"], "p_manifest": other})
    with pytest.raises(Exception, match="immutable_value_manifest"):
        database.query(
            "update dufynd_master_status set value=jsonb_set(value,'{manifest,max_tasks}','3') where key=$1",
            ["jarvis.value_v2.run." + m["run_id"]],
        )
    c = claim(b, m)
    v = receipt(c)
    assert commit(b, m, c, v)
    with pytest.raises(Exception, match="immutable_value_receipt"):
        database.query(
            "delete from dufynd_master_status where key=$1",
            ["jarvis.value_v2.result." + c["task"]["task_id"]],
        )


def test_public_execute_denied_and_invalid_window(database):
    assert not database.query(
        "select has_function_privilege('anon','public.claim_dufynd_value_v2(text,text,uuid)','EXECUTE') allowed"
    )[0]["allowed"]
    m = manifest()
    m["ends_at"] = m["starts_at"]
    with pytest.raises(Exception, match="invalid_bounded_value_manifest"):
        Bridge(database)._rpc("arm_dufynd_value_v2", {"p_decision": "test-only", "p_manifest": m})


def test_real_deadline_blocks_commit_and_claim_restores_closed_state(database):
    from datetime import UTC, datetime, timedelta

    def short(m):
        m["ends_at"] = (datetime.now(UTC) + timedelta(seconds=1)).isoformat()

    m, _, _ = arm(database, short)
    b = Bridge(database)
    c = claim(b, m)
    value = receipt(c)
    database.query("select pg_sleep(1.1)")
    assert not commit(b, m, c, value)
    assert claim(b, m) is None
    stopped = b.load_master_status_entry("jarvis.value_v2.run." + m["run_id"])["value"]
    assert stopped["state"] == "expired" and stopped["active"] is False
