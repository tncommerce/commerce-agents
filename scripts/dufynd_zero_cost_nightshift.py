"""Bounded local DUFYND offline queue. No provider, network or publication adapter.

An opt-in development process may wait for due tasks. This does not install a
timer, activate a production worker, or keep ChatGPT Work alive after its session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

from scripts import validate_dufynd_catalog_expansion_wave as catalog_validator

REPOSITORY = "tncommerce/commerce-agents"
VERSION = "offline-v1"
CODE_FILES = (Path(__file__), Path(catalog_validator.__file__))


def runtime_digest():
    """Bind the fixed reused validator as well as the queue implementation."""
    return hashlib.sha256(
        b"".join(hashlib.sha256(p.read_bytes()).digest() for p in CODE_FILES)
    ).hexdigest()


RUNNER_SHA = runtime_digest()
ACTIONS = {"json_integrity", "source_intake", "owner_gate", "catalog_wave_audit"}
MAX_FILE_BYTES = 1_000_000
SHA = re.compile(r"[a-f0-9]{64}\Z")
NAME = re.compile(r"[a-zA-Z0-9_-]{1,80}\Z")


class Gate(ValueError):
    """A bounded reason, without input contents or credential material."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def strict_json(raw):
    def invalid_constant(_value):
        raise Gate("invalid_json")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Gate("invalid_json")
            result[key] = value
        return result

    try:
        return json.loads(raw, parse_constant=invalid_constant, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError):
        raise Gate("invalid_json") from None


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.timestamp()
    except (ValueError, TypeError, AttributeError):
        raise Gate("timezone_aware_timestamp_required") from None


def checkout_identity(root):
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(root), *args], stderr=subprocess.DEVNULL, text=True, timeout=5
        ).strip()

    try:
        origin = git("remote", "get-url", "origin").removesuffix(".git")
        if origin not in {
            "https://github.com/" + REPOSITORY,
            "git@github.com:" + REPOSITORY,
        }:
            raise Gate("repository_out_of_scope")
        branch = git("symbolic-ref", "--short", "HEAD")
        if not branch.startswith("dufynd-"):
            raise Gate("development_branch_required")
        return git("rev-parse", "HEAD")
    except (subprocess.SubprocessError, OSError):
        raise Gate("checkout_unavailable") from None


def read_input(root, item):
    path = item.get("path", "")
    if not isinstance(path, str) or not path.endswith(".json"):
        raise Gate("input_path_denied")
    parts = Path(path).parts
    if (
        Path(path).is_absolute()
        or not parts
        or any(p in {"..", "."} or p.startswith(".") for p in parts)
        or not path.startswith(("docs/", "config/", "examples/retail/data/"))
        or not isinstance(item.get("sha256"), str)
        or not SHA.fullmatch(item["sha256"])
    ):
        raise Gate("input_path_denied")
    target = root
    for part in parts:
        target = target / part
        if target.is_symlink():
            raise Gate("input_symlink_denied")
    try:
        with target.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
    except OSError:
        raise Gate("input_unavailable") from None
    if len(raw) > MAX_FILE_BYTES:
        raise Gate("input_too_large")
    if hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise Gate("input_changed")
    return strict_json(raw)


def validate_plan(plan):
    if (
        not isinstance(plan, dict)
        or plan.get("repository") != REPOSITORY
        or plan.get("schema_version") != 1
        or plan.get("max_external_cost_eur") != 0
        or type(plan.get("max_external_cost_eur")) not in {int, float}
        or plan.get("production_activation") is not False
        or type(plan.get("enabled")) is not bool
        or not isinstance(plan.get("plan_id"), str)
        or not NAME.fullmatch(plan["plan_id"])
        or not re.fullmatch(r"[a-f0-9]{40}", str(plan.get("checkout_sha", "")))
        or not SHA.fullmatch(str(plan.get("runner_sha256", "")))
    ):
        raise Gate("plan_scope_denied")
    start, end = timestamp(plan.get("starts_at")), timestamp(plan.get("ends_at"))
    if not 0 < end - start <= 8 * 3600:
        raise Gate("window_limit")
    for key, limit in (("max_attempts", 40), ("max_tasks_per_tick", 10)):
        if type(plan.get(key)) is not int or not 1 <= plan[key] <= limit:
            raise Gate("invalid_limit")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 100:
        raise Gate("bounded_queue_required")
    ids = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise Gate("invalid_task")
        tid = task.get("task_id")
        if not isinstance(tid, str) or not NAME.fullmatch(tid) or tid in ids:
            raise Gate("duplicate_or_invalid_task")
        ids.add(tid)
        if task.get("action") not in ACTIONS:
            raise Gate("action_denied")
        if not start <= timestamp(task.get("due_at")) < end:
            raise Gate("task_outside_window")
        if type(task.get("max_attempts")) is not int or not 1 <= task["max_attempts"] <= 2:
            raise Gate("invalid_task_attempt_limit")
        deps = task.get("depends_on", [])
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            raise Gate("invalid_dependencies")
        inputs = task.get("inputs", [])
        if not isinstance(inputs, list) or len(inputs) > 10:
            raise Gate("bounded_inputs_required")
        if task["action"] != "owner_gate" and not inputs:
            raise Gate("inputs_required")
        if task["action"] == "owner_gate" and task.get("hold_reason") not in {
            "owner_authorization",
            "external_login",
            "source_report_missing",
            "unknown_cost",
        }:
            raise Gate("bounded_hold_reason_required")
        if any(not isinstance(i, dict) or set(i) != {"path", "sha256"} for i in inputs):
            raise Gate("invalid_input")
    graph = {t["task_id"]: t.get("depends_on", []) for t in tasks}
    visited = set()

    def visit(tid, stack):
        if tid not in graph or tid in stack:
            raise Gate("unknown_or_cyclic_dependency")
        if tid in visited:
            return
        for dep in graph[tid]:
            visit(dep, stack | {tid})
        visited.add(tid)

    for tid in ids:
        visit(tid, set())
    return plan


def execute_offline(action, inputs):
    """Pure, fixed handlers. No arbitrary command, plugin, URL or model selection."""
    if action == "json_integrity":
        return {"valid_json_documents": len(inputs)}
    if action == "catalog_wave_audit":
        if len(inputs) != 3 or any(not isinstance(x, dict) for x in inputs):
            raise Gate("catalog_inputs_required")
        # Reuse the existing pure pre-intake validator. An audit can complete
        # with findings; that never makes a historical wave release-ready.
        errors = catalog_validator.validate_wave(*inputs)
        return {
            "candidate_count": len(inputs[0].get("candidates", [])),
            "finding_count": len(errors),
            "intake_valid": not errors,
            "publication_authorized": False,
            "source_truth_verified_by_runner": False,
        }
    if action != "source_intake":
        raise Gate("action_denied")
    count = 0
    for data in inputs:
        if (
            not isinstance(data, dict)
            or data.get("facts_only") is not True
            or data.get("community_data_included") is not False
            or data.get("publication_authorized") is not False
        ):
            raise Gate("unsafe_source_intake")
        rows = data.get("products")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
            raise Gate("invalid_source_intake")
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("candidate_id"), str):
                raise Gate("invalid_source_intake")
            if row["candidate_id"] in ids:
                raise Gate("duplicate_source_candidate")
            ids.add(row["candidate_id"])
            if (
                type(row.get("volume_ml")) is not int
                or row["volume_ml"] <= 0
                or any(
                    not row.get(k)
                    for k in (
                        "brand",
                        "name",
                        "concentration",
                        "manufacturer_reference",
                        "variant_evidence",
                    )
                )
                or not str(row.get("source_url", "")).startswith("https://")
                or not isinstance(row.get("notes"), dict)
                or not row["notes"]
                or any(
                    k not in {"top", "heart", "base", "key"}
                    or not isinstance(v, list)
                    or not v
                    or any(not isinstance(n, str) or not n.strip() for n in v)
                    for k, v in row["notes"].items()
                )
                or {"gtin", "price", "rating", "affiliate_url", "image_url"} & row.keys()
            ):
                raise Gate("invalid_source_intake")
        count += len(rows)
    return {
        "structurally_valid_candidates": count,
        "source_truth_verified_by_runner": False,
        "publication_authorized": False,
    }


class Queue:
    def __init__(self, path, *, initialize=False):
        path = Path(path)
        if path.is_symlink() or path.parent.is_symlink():
            raise Gate("state_symlink_denied")
        if initialize:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                os.close(fd)
            except FileExistsError:
                raise Gate("state_already_exists") from None
        elif not path.is_file():
            raise Gate("resume_state_missing")
        if path.stat().st_mode & 0o077:
            raise Gate("private_state_required")
        # mode=rw prevents SQLite recreating a file lost after the existence check.
        self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)
        self.db.row_factory = sqlite3.Row
        if not initialize:
            try:
                if self.db.execute("PRAGMA application_id").fetchone()[0] != 1146441284:
                    raise Gate("resume_state_invalid")
                if self.db.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise Gate("resume_state_invalid")
                if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise Gate("resume_state_invalid")
                for table, fields in {
                    "plans": "id,hash,attempts",
                    "tasks": "plan,id,key,status,attempts,lease_until,token,reason",
                    "completed": "key,result,finished",
                    "checkpoints": "plan,report",
                }.items():
                    self.db.execute(f"SELECT {fields} FROM {table} LIMIT 0")
                if self.db.execute("""
                    SELECT 1 FROM tasks t LEFT JOIN plans p ON p.id=t.plan
                    LEFT JOIN completed c ON c.key=t.key
                    WHERE p.id IS NULL OR (t.status='done' AND c.key IS NULL)
                    OR t.status NOT IN ('pending','running','done','hold','failed')
                    OR t.attempts<0 LIMIT 1
                """).fetchone():
                    raise Gate("resume_state_invalid")
            except (sqlite3.DatabaseError, Gate):
                self.db.close()
                raise Gate("resume_state_invalid") from None
            return
        self.db.executescript("""
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS plans (
              id TEXT PRIMARY KEY, hash TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS tasks (
              plan TEXT NOT NULL, id TEXT NOT NULL, key TEXT NOT NULL,
              status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              lease_until REAL, token INTEGER NOT NULL DEFAULT 0, reason TEXT,
              PRIMARY KEY(plan,id));
            CREATE TABLE IF NOT EXISTS completed (
              key TEXT PRIMARY KEY, result TEXT NOT NULL, finished REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS checkpoints (
              plan TEXT PRIMARY KEY, report TEXT NOT NULL);
            PRAGMA application_id = 1146441284;
            PRAGMA user_version = 1;
            COMMIT;
        """)

    def register(self, plan):
        validate_plan(plan)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute(
                "SELECT hash FROM plans WHERE id=?", (plan["plan_id"],)
            ).fetchone()
            if old and old[0] != digest(plan):
                raise Gate("plan_changed_new_id_required")
            if old:
                existing = self.db.execute(
                    "SELECT id,attempts FROM tasks WHERE plan=?", (plan["plan_id"],)
                ).fetchall()
                total = self.db.execute(
                    "SELECT attempts FROM plans WHERE id=?", (plan["plan_id"],)
                ).fetchone()[0]
                if {r["id"] for r in existing} != {t["task_id"] for t in plan["tasks"]} or sum(
                    r["attempts"] for r in existing
                ) != total:
                    raise Gate("resume_state_invalid")
            self.db.execute(
                "INSERT OR IGNORE INTO plans(id,hash) VALUES (?,?)", (plan["plan_id"], digest(plan))
            )
            for task in plan["tasks"]:
                # No date/plan/commit component: unchanged completed input is not
                # repeated simply because another timer slot or PR commit exists.
                key = digest(
                    [
                        REPOSITORY,
                        VERSION,
                        plan["runner_sha256"],
                        task["action"],
                        task.get("inputs", []),
                    ]
                )
                self.db.execute(
                    "INSERT OR IGNORE INTO tasks(plan,id,key,status) VALUES (?,?,?,'pending')",
                    (plan["plan_id"], task["task_id"], key),
                )

    def claim(self, plan, now, check_inputs=None):
        pid = plan["plan_id"]
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            total = self.db.execute("SELECT attempts FROM plans WHERE id=?", (pid,)).fetchone()[0]
            if total >= plan["max_attempts"]:
                return None, "ATTEMPT_LIMIT"
            for task in sorted(plan["tasks"], key=lambda t: (timestamp(t["due_at"]), t["task_id"])):
                row = self.db.execute(
                    "SELECT * FROM tasks WHERE plan=? AND id=?", (pid, task["task_id"])
                ).fetchone()
                if row["status"] in {"done", "hold", "failed"} or timestamp(task["due_at"]) > now:
                    continue
                if row["status"] == "running" and row["lease_until"] > now:
                    continue
                if row["attempts"] >= task["max_attempts"]:
                    self.db.execute(
                        "UPDATE tasks SET status='failed',reason='attempt_limit' WHERE plan=? AND id=?",
                        (pid, task["task_id"]),
                    )
                    continue
                if task["action"] == "owner_gate":
                    self.db.execute(
                        "UPDATE tasks SET status='hold',reason=? WHERE plan=? AND id=?",
                        (task["hold_reason"], pid, task["task_id"]),
                    )
                    continue
                dependencies = [
                    self.db.execute(
                        "SELECT status FROM tasks WHERE plan=? AND id=?", (pid, d)
                    ).fetchone()[0]
                    for d in task.get("depends_on", [])
                ]
                if any(s in {"hold", "failed"} for s in dependencies):
                    self.db.execute(
                        "UPDATE tasks SET status='hold',reason='dependency_hold' WHERE plan=? AND id=?",
                        (pid, task["task_id"]),
                    )
                    continue
                if any(s != "done" for s in dependencies):
                    continue
                if check_inputs:
                    try:
                        check_inputs(task)
                    except Gate as exc:
                        self.db.execute(
                            "UPDATE tasks SET status='hold',reason=? WHERE plan=? AND id=?",
                            (str(exc), pid, task["task_id"]),
                        )
                        continue
                if self.db.execute("SELECT 1 FROM completed WHERE key=?", (row["key"],)).fetchone():
                    self.db.execute(
                        "UPDATE tasks SET status='done',reason='deduplicated' WHERE plan=? AND id=?",
                        (pid, task["task_id"]),
                    )
                    continue
                # Fence equivalent work across plans, not just one task ID.
                if self.db.execute(
                    "SELECT 1 FROM tasks WHERE key=? AND status='running' AND lease_until>?",
                    (row["key"], now),
                ).fetchone():
                    continue
                token = row["token"] + 1
                self.db.execute(
                    "UPDATE tasks SET status='running',attempts=attempts+1,lease_until=?,token=?,reason=NULL WHERE plan=? AND id=?",
                    (now + 30, token, pid, task["task_id"]),
                )
                self.db.execute("UPDATE plans SET attempts=attempts+1 WHERE id=?", (pid,))
                return (task, row["key"], token), "CLAIMED"
        return None, "NO_DUE_WORK"

    def finish(self, plan, claim, now, result=None, reason=None):
        task, key, token = claim
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT * FROM tasks WHERE plan=? AND id=?", (plan["plan_id"], task["task_id"])
            ).fetchone()
            if row["status"] != "running" or row["token"] != token or now >= row["lease_until"]:
                raise Gate("lease_lost")
            if reason is None:
                self.db.execute(
                    "INSERT OR IGNORE INTO completed VALUES (?,?,?)", (key, canonical(result), now)
                )
            self.db.execute(
                "UPDATE tasks SET status=?,reason=?,lease_until=NULL WHERE plan=? AND id=?",
                ("done" if reason is None else "hold", reason, plan["plan_id"], task["task_id"]),
            )

    def snapshot(self, plan):
        rows = [
            dict(r)
            for r in self.db.execute(
                "SELECT id,status,attempts,reason FROM tasks WHERE plan=? ORDER BY id",
                (plan["plan_id"],),
            )
        ]
        attempts = self.db.execute(
            "SELECT attempts FROM plans WHERE id=?", (plan["plan_id"],)
        ).fetchone()[0]
        return {
            "plan_id": plan["plan_id"],
            "tasks": rows,
            "attempts": attempts,
            "all_terminal": all(r["status"] in {"done", "hold", "failed"} for r in rows),
        }

    def save_checkpoint(self, report):
        with self.db:
            self.db.execute(
                "INSERT INTO checkpoints VALUES (?,?) ON CONFLICT(plan) DO UPDATE SET report=excluded.report",
                (report["plan_id"], canonical(report)),
            )


def run(
    plan,
    queue,
    root,
    *,
    max_seconds=60,
    stop_file=None,
    clock=time.time,
    monotonic=time.monotonic,
    sleep=time.sleep,
    identity=checkout_identity,
    handler=execute_offline,
    should_stop=lambda: False,
):
    validate_plan(plan)
    if not plan["enabled"]:
        return {"stop_reason": "DISABLED", "external_cost_eur": 0}
    if type(max_seconds) is not int or not 1 <= max_seconds <= 900:
        raise Gate("runtime_limit")
    if identity(root) != plan["checkout_sha"]:
        raise Gate("checkout_changed")
    if plan["runner_sha256"] != RUNNER_SHA:
        raise Gate("runner_changed")
    queue.register(plan)
    deadline = monotonic() + max_seconds
    reason = "RUNTIME_LIMIT"
    executed = 0
    while monotonic() < deadline:
        now = clock()
        if should_stop():
            reason = "STOP_SIGNAL"
            break
        if stop_file and Path(stop_file).exists():
            reason = "STOP_FILE"
            break
        if identity(root) != plan["checkout_sha"]:
            reason = "CHECKOUT_CHANGED"
            break
        if runtime_digest() != RUNNER_SHA:
            reason = "RUNNER_CHANGED"
            break
        if now >= timestamp(plan["ends_at"]):
            reason = "WINDOW_CLOSED"
            break
        if now < timestamp(plan["starts_at"]):
            sleep(min(1, max(0, deadline - monotonic())))
            continue
        if queue.snapshot(plan)["all_terminal"]:
            reason = "QUEUE_TERMINAL"
            break
        if executed >= plan["max_tasks_per_tick"]:
            reason = "TICK_LIMIT"
            break
        claim, reason = queue.claim(plan, now, lambda t: [read_input(root, i) for i in t["inputs"]])
        if claim:
            try:
                inputs = [read_input(root, i) for i in claim[0]["inputs"]]
                result = handler(claim[0]["action"], inputs)
                queue.finish(plan, claim, clock(), result=result)
            except Gate as exc:
                if str(exc) == "lease_lost":
                    reason = "LEASE_LOST"
                    break
                queue.finish(plan, claim, clock(), reason=str(exc))
            except Exception:
                queue.finish(plan, claim, clock(), reason="handler_failed")
            executed += 1
            continue
        if reason == "ATTEMPT_LIMIT":
            break
        if queue.snapshot(plan)["all_terminal"]:
            reason = "QUEUE_TERMINAL"
            break
        sleep(min(1, max(0, deadline - monotonic())))
    else:
        reason = "RUNTIME_LIMIT"
    report = {
        **queue.snapshot(plan),
        "stop_reason": reason,
        "external_cost_eur": 0,
        "production_activation": False,
    }
    queue.save_checkpoint(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument(
        "--initialize-state",
        action="store_true",
        help="Create a NEW private state once; never use in timers",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--max-seconds", type=int, default=60)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args()
    try:
        if args.plan.stat().st_size > MAX_FILE_BYTES:
            raise Gate("plan_too_large")
        plan = validate_plan(strict_json(args.plan.read_text()))
        if not plan["enabled"]:
            print(canonical({"stop_reason": "DISABLED", "external_cost_eur": 0}))
            return 0
        queue = Queue(args.state, initialize=args.initialize_state)
        stopping = False

        def request_stop(_signum, _frame):
            nonlocal stopping
            stopping = True  # Never perform SQLite IO inside a signal handler.

        previous = {
            sig: signal.signal(sig, request_stop) for sig in (signal.SIGTERM, signal.SIGINT)
        }
        try:
            report = run(
                plan,
                queue,
                args.root.resolve(),
                max_seconds=args.max_seconds,
                stop_file=args.stop_file,
                should_stop=lambda: stopping,
            )
            print(canonical(report))
        finally:
            for sig, original in previous.items():
                signal.signal(sig, original)
            queue.db.close()
        return 0
    except Gate as exc:
        print(canonical({"stop_reason": str(exc), "external_cost_eur": 0}))
        return 2
    except Exception:
        print(canonical({"stop_reason": "INTERNAL_ERROR", "external_cost_eur": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
