"""No network: exercise the exact recovery entry and fixed transport contract."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

SPEC = importlib.util.spec_from_file_location(
    "dufynd_observer_recovery",
    Path(__file__).parents[1] / "scripts/dufynd_observer_recovery.py",
)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
CURRENT = 900
CHILD = 901
SHA = "a" * 40


def run(run_id, *, workflow=recovery.READER, minutes=60, status="completed"):
    repository = {
        "id": recovery.REPO_ID,
        "full_name": recovery.REPO,
        "private": False,
        "owner": {"id": recovery.OWNER_ID},
    }
    created = (NOW - timedelta(minutes=minutes)).isoformat()
    return {
        "id": run_id,
        "repository": repository,
        "head_repository": copy.deepcopy(repository),
        "workflow_id": recovery.READER_ID if workflow == recovery.READER else 999,
        "path": ".github/workflows/" + workflow,
        "head_branch": "scentai-mvp" if workflow == recovery.READER else "main",
        "head_sha": SHA,
        "event": "workflow_dispatch",
        "status": status,
        "conclusion": "success" if status == "completed" else None,
        "run_attempt": 1,
        "created_at": created,
        "updated_at": created,
    }


def environment():
    return {
        "GITHUB_REPOSITORY": recovery.REPO,
        "GITHUB_REPOSITORY_ID": str(recovery.REPO_ID),
        "GITHUB_REPOSITORY_OWNER_ID": str(recovery.OWNER_ID),
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": f"{recovery.REPO}/.github/workflows/{recovery.RECOVERY}@refs/heads/main",
        "GITHUB_SHA": SHA,
        "GITHUB_RUN_ID": str(CURRENT),
        "RECOVERY_EXECUTE": "true",
        **dict.fromkeys(recovery.FLAGS, "1"),
    }


def listing(runs):
    return {"total_count": len(runs), "workflow_runs": runs}


class FakeGitHub:
    def __init__(self):
        self.current = run(CURRENT, workflow=recovery.RECOVERY, minutes=1, status="in_progress")
        self.own = [self.current]
        self.reader = [run(100)]
        self.active = {}
        self.calls = []
        self.post_attempted = False
        self.dispatch_receipt = None
        self.child = run(CHILD, minutes=0, status="queued")
        self.late_reader = None

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "POST":
            self.post_attempted = True
            return {
                "workflow_run_id": CHILD,
                "run_url": f"{recovery.API}{recovery.PREFIX}/runs/{CHILD}",
                "html_url": f"https://github.com/{recovery.REPO}/actions/runs/{CHILD}",
            }
        if path == f"{recovery.PREFIX}/runs/{CURRENT}":
            return self.current
        if path == f"{recovery.PREFIX}/runs/{CHILD}":
            return self.child
        if recovery.RECOVERY + "/runs?" in path:
            return listing(self.own)
        if "status=" in path:
            state = recovery.urllib.parse.parse_qs(recovery.urllib.parse.urlsplit(path).query)[
                "status"
            ][0]
            return listing(self.active.get(state, []))
        matches = [
            call
            for call in self.calls
            if recovery.READER + "/runs?" in call[1] and "status=" not in call[1]
        ]
        return listing(
            self.late_reader if len(matches) == 2 and self.late_reader is not None else self.reader
        )


def execute(client=None, env=None):
    return recovery.recover(client or FakeGitHub(), env or environment(), NOW, clock=lambda: NOW)


def test_stale_idle_dispatches_once_with_fixed_scope_and_exact_receipt():
    client = FakeGitHub()
    receipt = execute(client)
    posts = [call for call in client.calls if call[0] == "POST"]
    assert posts == [
        (
            "POST",
            f"{recovery.PREFIX}/workflows/{recovery.READER}/dispatches",
            {
                "ref": "scentai-mvp",
                "inputs": {"mode": "render_services_v2", "capture_v2": True},
                "return_run_details": True,
            },
        )
    ]
    assert receipt["child_run_id"] == CHILD and receipt["status"] == "dispatched"
    assert not receipt["capture_verified"] and not receipt["cadence_restored"]
    assert len(client.calls) <= recovery.MAX_REQUESTS


def test_default_dry_run_does_not_dispatch():
    client, env = FakeGitHub(), environment()
    env["RECOVERY_EXECUTE"] = "false"
    assert execute(client, env)["status"] == "ready_dry_run"
    assert not client.post_attempted


@pytest.mark.parametrize("flag", recovery.FLAGS)
@pytest.mark.parametrize("value", ["", "0", "true", "01", "1 "])
def test_every_existing_gate_must_equal_one_before_any_request(flag, value):
    client, env = FakeGitHub(), environment()
    env[flag] = value
    assert execute(client, env)["status"] == "existing_v2_gates_closed"
    assert client.calls == []


@pytest.mark.parametrize(
    "key,value",
    [
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("GITHUB_REF", "refs/heads/scentai-mvp"),
        ("GITHUB_REPOSITORY_ID", "1"),
        ("GITHUB_REPOSITORY_OWNER_ID", "1"),
        ("GITHUB_EVENT_NAME", "schedule"),
        ("GITHUB_WORKFLOW_REF", "forged"),
    ],
)
def test_identity_mismatch_and_reruns_cannot_write(key, value):
    client, env = FakeGitHub(), environment()
    env[key] = value
    with pytest.raises(recovery.Refused, match="execution_identity"):
        execute(client, env)
    assert client.calls == []


def test_new_or_failed_recent_observer_prevents_duplicate_dispatch():
    client = FakeGitHub()
    client.reader = [run(101, minutes=5)]
    client.reader[0]["conclusion"] = "failure"
    assert execute(client)["status"] == "recent_observer_attempt"
    assert not client.post_attempted


@pytest.mark.parametrize("state", sorted(recovery.ACTIVE))
def test_old_active_runs_outside_first_page_block_a_new_dispatch(state):
    client = FakeGitHub()
    client.active[state] = [run(10, minutes=600, status=state)]
    assert execute(client)["status"] == "observer_in_flight"
    assert not client.post_attempted


def test_new_native_schedule_between_reads_blocks_dispatch():
    client = FakeGitHub()
    client.late_reader = [run(102, minutes=1, status="queued")]
    assert execute(client)["status"] == "observer_in_flight"
    assert not client.post_attempted


def test_previous_entry_in_cooldown_consumes_slot_even_if_failed():
    client = FakeGitHub()
    previous = run(899, workflow=recovery.RECOVERY, minutes=10)
    previous["conclusion"] = "failure"
    client.own.append(previous)
    assert execute(client)["status"] == "recovery_cooldown"
    assert not client.post_attempted


def test_five_recent_entries_block_abusive_caller():
    client = FakeGitHub()
    client.own += [run(800 - i, workflow=recovery.RECOVERY, minutes=16 + i) for i in range(5)]
    assert execute(client)["status"] == "recovery_rate_limit"


def test_quarter_hour_caller_is_not_starved_by_healthy_noop_history():
    client = FakeGitHub()
    client.own += [
        run(800 - i, workflow=recovery.RECOVERY, minutes=15 * (i + 1)) for i in range(95)
    ]
    assert execute(client)["status"] == "dispatched"


def test_post_timeout_is_never_retried():
    client = FakeGitHub()
    original = client.call

    def timeout(method, path, body=None):
        if method == "POST":
            client.post_attempted = True
            client.calls.append((method, path, body))
            raise recovery.Refused("dispatch_outcome_unknown")
        return original(method, path, body)

    client.call = timeout
    with pytest.raises(recovery.Refused, match="dispatch_outcome_unknown"):
        execute(client)
    assert len([call for call in client.calls if call[0] == "POST"]) == 1


class Response(io.BytesIO):
    def __init__(self, body=None, *, status=200, headers=None):
        super().__init__(json.dumps(body or {}).encode())
        self.status = status
        self.headers = headers if headers is not None else {"X-RateLimit-Remaining": "100"}


def test_transport_pins_origin_version_scope_and_refuses_redirects():
    client = recovery.GitHub("private-test-token")
    assert client.opener.handlers
    with patch.object(client.opener, "open", return_value=Response()) as opened:
        client.call("GET", recovery.PREFIX + "/runs/900")
        request = opened.call_args.args[0]
        assert request.full_url == recovery.API + recovery.PREFIX + "/runs/900"
        assert request.get_header("X-github-api-version") == "2026-03-10"
        assert opened.call_args.kwargs["timeout"] == 15
    assert (
        recovery.NoRedirect().redirect_request(None, None, 302, None, None, "https://evil.invalid")
        is None
    )


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-RateLimit-Remaining": "1"}, {"X-RateLimit-Remaining": "100", "Retry-After": "60"}],
)
def test_rate_limit_headers_fail_closed_without_retry(headers):
    client = recovery.GitHub("private-test-token")
    with patch.object(client.opener, "open", return_value=Response(headers=headers)) as opened:
        with pytest.raises(recovery.Refused):
            client.call("GET", recovery.PREFIX + "/runs/900")
        assert opened.call_count == 1


def test_transport_refuses_second_post_and_other_write_paths():
    client = recovery.GitHub("private-test-token")
    body = {
        "ref": "scentai-mvp",
        "inputs": {"mode": "render_services_v2", "capture_v2": True},
        "return_run_details": True,
    }
    with patch.object(client.opener, "open", return_value=Response()):
        client.call("POST", f"{recovery.PREFIX}/workflows/{recovery.READER}/dispatches", body)
    with pytest.raises(recovery.Refused, match="dispatch_contract_rejected"):
        client.call("POST", f"{recovery.PREFIX}/workflows/{recovery.READER}/dispatches", body)


def test_transport_rejects_default_204_dispatch_without_run_details():
    client = recovery.GitHub("private-test-token")
    # GitHub returns 204 and no run ID unless return_run_details=true.
    missing_opt_in = {
        "ref": "scentai-mvp",
        "inputs": {"mode": "render_services_v2", "capture_v2": True},
    }
    with pytest.raises(recovery.Refused, match="dispatch_contract_rejected"):
        client.call("POST", f"{recovery.PREFIX}/workflows/{recovery.READER}/dispatches", missing_opt_in)
    assert not client.post_attempted
    assert client.requests == 0


def test_workflow_has_no_clock_secret_or_oidc_permission():
    path = Path(__file__).parents[1] / ".github/workflows" / recovery.RECOVERY
    content = path.read_text()
    workflow = yaml.load(content, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["on"]["workflow_dispatch"]["inputs"]["execute"]["default"] == "false"
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    job = workflow["jobs"]["recover"]
    assert job["permissions"] == {"contents": "read", "actions": "write"}
    assert "id-token:" not in content and "secrets." not in content
    assert "github.run_attempt == 1" in job["if"]
