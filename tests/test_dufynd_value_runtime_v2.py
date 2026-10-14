"""Actual isolated Python child, never provider/production traffic."""

import copy
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from scripts.dufynd_nightshift_value_v2 import EDITORIAL_ARCHIVE_KEY, checked_source, sha
from scripts.dufynd_value_runtime_v2 import CHILD, evaluate
from tests.test_dufynd_nightshift_value_v2 import inputs


def manifest():
    sources, _ = inputs()
    now = datetime.now(UTC)
    for s in sources.values():
        s["read_at"] = now.isoformat()
    sources["measurement"]["value"]["window_end"] = now.isoformat()
    sources["measurement"]["value"]["window_start"] = (now - timedelta(hours=1)).isoformat()
    return dict(
        version=2,
        run_id="dufynd_value_test_runtime",
        code_sha="a" * 40,
        starts_at=(now - timedelta(seconds=1)).isoformat(),
        ends_at=(now + timedelta(minutes=44)).isoformat(),
        sources=sources,
        pins={k: sha(v) for k, v in sources.items()},
        max_tasks=2,
        max_attempts=3,
        max_total_attempts=6,
        cost_eur=0,
        provider_calls=0,
    )


def claim(handler="first_money_action/2"):
    return {"manifest": manifest(), "task": {"durable_payload": {"handler": handler}}}


@pytest.mark.parametrize(
    "handler,state",
    [
        ("first_money_action/2", "INTERNAL_ACTION_RECEIPT"),
        ("editorial_handoff/2", "INTERNAL_EDITORIAL_HANDOFF"),
        ("unknown/2", "OWNER_HOLD"),
    ],
)
def test_real_python_child(handler, state):
    assert evaluate(claim(handler))["state"] == state


def test_child_denies_external_network_and_subprocess():
    # Same installed audit hook in a real child; no HTTP request ever leaves it.
    for action in ["import socket; socket.socket()", 'import subprocess; subprocess.run(["true"])']:
        script = (
            "from scripts.dufynd_value_worker_v2 import deny_external\nimport sys\nsys.addaudithook(deny_external)\n"
            + action
        )
        p = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        assert p.returncode != 0 and "zero_cost_external_execution_denied" in p.stderr


def test_credentials_not_inherited(monkeypatch):
    original = subprocess.run
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-secret-never-forward")

    def inspect(*args, **kwargs):
        assert set(kwargs["env"]) == {"PATH", "LANG"}
        assert all("synthetic-secret" not in v for v in kwargs["env"].values())
        return original(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", inspect)
    assert evaluate(claim())["state"] == "INTERNAL_ACTION_RECEIPT"


def test_timeout_unknown_input_and_stale_evidence_hold(monkeypatch):
    c = claim()
    c["manifest"]["pins"]["measurement"] = "0" * 64
    assert evaluate(c)["state"] == "OWNER_HOLD"
    c = claim()
    c["manifest"]["ends_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    assert evaluate(c)["reason"] == "deadline_reached"

    def timeout(*a, **kw):
        assert 0 < kw["timeout"] <= 10
        raise subprocess.TimeoutExpired("fixed_worker", kw["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    assert evaluate(claim())["reason"] == "isolated_worker_failed_or_timed_out"


def test_worker_rejects_oversize_without_echoing_input():
    p = subprocess.run(
        [sys.executable, "-I", str(CHILD)],
        input="SECRET" + ("x" * 250000),
        text=True,
        capture_output=True,
        env={"PATH": os.defpath},
    )
    assert p.returncode and "SECRET" not in p.stderr and not p.stdout


def test_existing_archive_source_identity_explicitly_preserved():
    s = copy.deepcopy(manifest()["sources"]["editorial"])
    s["key"] = EDITORIAL_ARCHIVE_KEY
    assert checked_source(s, name="editorial", pin=sha(s), now=datetime.now(UTC)) == s["value"]
    s["key"] = "private:unverified-copy"
    with pytest.raises(ValueError, match="identity"):
        checked_source(s, name="editorial", pin=sha(s), now=datetime.now(UTC))


def test_no_publisher_model_or_new_schedule_in_value_workflow():
    from pathlib import Path

    text = Path(".github/workflows/dufynd-jarvis-manual.yml").read_text()
    job = text.split("\n  nightshift-value-v2:")[1].split("\n  durable-execution:")[0]
    assert "timeout-minutes: 5" in job and "contents: read" in job
    assert "ANTHROPIC" not in job and "schedule:" not in job and "upload-artifact" not in job
    assert "persist-credentials: false" in job
