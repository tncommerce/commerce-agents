"""Real SQL adapters shared by the acceptance tests and reproducible local pilot."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

ROOT = Path(__file__).resolve().parents[1]


class Database:
    def __init__(self):
        self.process = None
        self.connection = None
        if os.getenv("DUFYND_PGLITE_MODULE"):
            self.process = subprocess.Popen(
                ["node", str(ROOT / "tests/content7_pglite.mjs")],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            )
        else:
            import psycopg

            self.connection = psycopg.connect(
                os.environ["DUFYND_CONTENT_TEST_DATABASE_URL"], autocommit=True
            )

    def query(self, sql, params=(), *, script=False):
        if self.process:
            self.process.stdin.write(
                json.dumps({"sql": sql, "params": params, "exec": script}) + "\n"
            )
            self.process.stdin.flush()
            result = json.loads(self.process.stdout.readline())
            if "error" in result:
                raise ValueError(result["error"])
            return [] if script else list(result["result"]["rows"])
        # The tests use a tiny numbered-placeholder subset, not user-built SQL.
        import re

        from psycopg.rows import dict_row

        sql = re.sub(r"\$\d+", "%s", sql)
        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, params if params else None)
            return cursor.fetchall() if cursor.description else []

    def bootstrap(self):
        schema = (ROOT / "tests/dufynd_budget_schema_fixture.sql").read_text()
        if self.connection:
            # CI modules share a dedicated disposable service, unlike PGlite's
            # separate processes. Never reset a remote or generically named DB.
            if (
                self.connection.info.host not in {"localhost", "127.0.0.1", "::1"}
                or self.connection.info.dbname != "content7_test"
            ):
                raise ValueError("fixture reset only allowed on local content7_test")
            self.query("drop schema public cascade; create schema public;", script=True)
            for role, options in (
                ("anon", ""),
                ("authenticated", ""),
                ("service_role", " bypassrls"),
            ):
                statement = f"create role {role}{options};"
                schema = schema.replace(
                    statement,
                    f"do $$ begin {statement} exception when duplicate_object then null; end $$;",
                )
        self.query(schema, script=True)
        self.query(
            "alter table public.dufynd_autonomy_tasks add column approval_action_type text default 'auto_allowed'",
            script=True,
        )
        self.query(
            "alter table public.dufynd_human_decisions add column action_type text, add column context jsonb; "
            "create table public.dufynd_content_ideas(id text primary key,title text,status text);",
            script=True,
        )
        migrations = ROOT / "supabase/migrations"
        for suffix, boundary in (
            ("supervisor_v2_phase1.sql", "-- No model and no paid runner:"),
            ("durable_executions.sql", "-- Hosted observer extension;"),
            ("external_events.sql", None),
            ("capability_packets.sql", None),
            ("seven_content_atomic_result.sql", None),
            ("seven_content_activation.sql", None),
        ):
            sql = next(migrations.glob("*" + suffix)).read_text()
            self.query(sql.split(boundary)[0] if boundary else sql, script=True)
        # Install the actual queue view, not a mocked approximation.
        self.query(
            (migrations / "20260930061000_dufynd_approval_queue_hygiene.sql").read_text(),
            script=True,
        )

    def close(self):
        if self.process:
            self.process.stdin.close()
            self.process.wait(timeout=10)
        if self.connection:
            self.connection.close()


class SqlBridge(DufyndJarvisBridge):
    def __init__(self, database):
        self.database = database
        self.worker_tokens = {}

    def _rpc(self, name, payload=None):
        allow = {
            "claim_dufynd_worker_v2",
            "commit_dufynd_content7_result_v1",
            "update_dufynd_worker_v2",
            "reconcile_dufynd_supervisor_v2",
            "get_dufynd_autonomy_queue",
            "dufynd_content7_activation_allowed_v1",
            "activate_dufynd_content7_v1",
            "pause_dufynd_content7_v1",
        }
        if name not in allow:
            raise ValueError("test RPC outside fixed allowlist")
        values = list((payload or {}).values())
        args = []
        for i, value in enumerate(values):
            args.append(f"${i + 1}" + ("::jsonb" if isinstance(value, dict) else ""))
        values = [json.dumps(v) if isinstance(v, dict) else v for v in values]
        return self.database.query(f"select public.{name}({','.join(args)}) as value", values)[0][
            "value"
        ]

    def load_master_status_entry(self, key):
        rows = self.database.query("select * from public.dufynd_master_status where key=$1", [key])
        return rows[0] if rows else None

    def load_autonomy_task(self, task_id):
        rows = self.database.query(
            "select * from public.dufynd_autonomy_tasks where task_id=$1", [task_id]
        )
        # Match the production REST transport's UUID/timestamp string encoding.
        return json.loads(json.dumps(rows[0], default=str)) if rows else None
