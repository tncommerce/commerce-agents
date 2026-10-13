from __future__ import annotations

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.dufynd_zero_cost_nightshift import Queue, canonical, run
from scripts.prepare_dufynd_nightshift_plan import CATALOG, QA, SOURCE, main, prepare

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for path in (SOURCE, *CATALOG, QA):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    for command in (
        ["init", "-b", "dufynd-nightshift-test"],
        ["remote", "add", "origin", "https://github.com/tncommerce/commerce-agents.git"],
        ["add", "."],
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
    ):
        subprocess.run(["git", "-C", str(root), *command], check=True, capture_output=True)
    return root


def plan_for(root, *, start=None):
    start = start or datetime.now(UTC)
    return prepare(
        root, "bounded-trial", start.isoformat(), (start + timedelta(minutes=2)).isoformat()
    )


def test_preparation_is_disabled_and_uses_real_fixed_inputs(checkout):
    plan = plan_for(checkout)
    assert plan["enabled"] is False
    assert plan["production_activation"] is False
    assert plan["max_external_cost_eur"] == 0
    assert len(plan["tasks"]) == 4
    assert plan["tasks"][0]["action"] == "owner_gate"
    assert plan["tasks"][2]["action"] == "catalog_wave_audit"
    assert [i["path"] for i in plan["tasks"][2]["inputs"]] == list(CATALOG)


def test_prepared_queue_runs_offline_and_resumes_without_duplicate(checkout, tmp_path, monkeypatch):
    import socket

    def denied(*args, **kwargs):
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "socket", denied)
    plan = plan_for(checkout, start=datetime.now(UTC) - timedelta(seconds=10))
    plan["enabled"] = True  # Isolated authorized local trial, no scheduler installation.
    path = tmp_path / "queue.sqlite"
    q = Queue(path, initialize=True)
    try:
        first = run(plan, q, checkout, max_seconds=5)
        assert first["attempts"] == 3
        assert [t["status"] for t in first["tasks"]] == ["hold", "done", "done", "done"]
        results = [json.loads(row[0]) for row in q.db.execute("SELECT result FROM completed")]
        audit = next(r for r in results if "finding_count" in r)
        assert audit["finding_count"] > 0  # Historical wave already promoted; never claim ready.
        assert audit["intake_valid"] is False
        assert audit["publication_authorized"] is False
    finally:
        q.db.close()
    q = Queue(path)
    try:
        assert run(plan, q, checkout, max_seconds=5)["attempts"] == 3
    finally:
        q.db.close()


def test_cli_never_overwrites_an_existing_plan(checkout, tmp_path, monkeypatch, capsys):
    now = datetime.now(UTC)
    output = tmp_path / "plan.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare",
            "--root",
            str(checkout),
            "--plan-id",
            "test",
            "--starts-at",
            now.isoformat(),
            "--ends-at",
            (now + timedelta(minutes=1)).isoformat(),
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    saved = output.read_bytes()
    assert json.loads(saved)["enabled"] is False
    assert output.stat().st_mode & 0o777 == 0o600
    assert main() == 2
    assert output.read_bytes() == saved
    capsys.readouterr()


def test_preparation_refuses_symlink(checkout, tmp_path):
    target = checkout / SOURCE
    target.unlink()
    target.symlink_to(tmp_path / "outside.json")
    with pytest.raises(ValueError, match="input_symlink_denied"):
        plan_for(checkout)


@pytest.mark.skipif(os.name != "posix", reason="Linux service signal contract")
def test_real_timer_start_sigterm_checkpoint_and_new_process_resume(checkout, tmp_path):
    plan = plan_for(checkout, start=datetime.now(UTC) + timedelta(seconds=2))
    plan["enabled"] = True
    file = tmp_path / "plan.json"
    file.write_text(canonical(plan))
    state = tmp_path / "queue.sqlite"
    command = [
        sys.executable,
        "-m",
        "scripts.dufynd_zero_cost_nightshift",
        "--root",
        str(checkout),
        "--plan",
        str(file),
        "--state",
        str(state),
        "--max-seconds",
        "15",
    ]
    child = subprocess.Popen(
        command + ["--initialize-state"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # Wait for real durable registration, not an arbitrary sleep before SIGTERM.
        deadline = time.monotonic() + 5
        registered = False
        while time.monotonic() < deadline:
            if state.exists():
                try:
                    with sqlite3.connect(state.as_uri() + "?mode=ro", uri=True) as db:
                        registered = db.execute("SELECT count(*) FROM plans").fetchone()[0] == 1
                except sqlite3.DatabaseError:
                    pass
            if registered:
                break
            time.sleep(0.02)
        assert registered
        child.send_signal(signal.SIGTERM)
        out, err = child.communicate(timeout=5)
        assert child.returncode == 0, err
        report = json.loads(out)
        assert report["stop_reason"] == "STOP_SIGNAL"
        assert report["attempts"] == 0
        with sqlite3.connect(state) as db:
            assert json.loads(db.execute("SELECT report FROM checkpoints").fetchone()[0]) == report
        resumed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=20)
        assert resumed.returncode == 0, resumed.stderr
        final = json.loads(resumed.stdout)
        assert final["attempts"] == 3
        assert [t["status"] for t in final["tasks"]] == ["hold", "done", "done", "done"]
        with sqlite3.connect(state) as db:
            earliest = db.execute("SELECT min(finished) FROM completed").fetchone()[0]
            assert earliest >= datetime.fromisoformat(plan["tasks"][1]["due_at"]).timestamp()
        again = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10)
        assert json.loads(again.stdout)["attempts"] == 3
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
