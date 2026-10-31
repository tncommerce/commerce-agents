"""Adversarial recovery boundaries; every API operation is an offline fake."""

from __future__ import annotations

import copy
import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

SPEC = importlib.util.spec_from_file_location(
    "dufynd_observer_recovery",
    Path(__file__).parents[1] / "scripts/dufynd_observer_recovery.py",
)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)

NOW = datetime(2026, 10, 31, 12, tzinfo=UTC)
CURRENT_ID = 9001
CHILD_ID = 9002
SHA = "a" * 40


def make_run(run_id, workflow, branch, age=20, status="completed"):
    repository = {
        "id": recovery.REPO_ID,
        "full_name": recovery.REPO,
        "owner": {"id": recovery.OWNER_ID},
        "private": False,
    }
    created = NOW - timedelta(minutes=age)
    return {
        "id": run_id,
        "workflow_id": recovery.READER_ID if workflow == recovery.READER else 8001,
        "path": f".github/workflows/{workflow}",
        "head_branch": branch,
        "head_sha": SHA,
        "event": "workflow_dispatch",
        "status": status,
        "conclusion": "success" if status == "completed" else None,
        "run_attempt": 1,
        "created_at": created.isoformat(),
        "updated_at": created.isoformat(),
        "repository": repository,
        "head_repository": copy.deepcopy(repository),
    }


def environment():
    return {
        "GITHUB_REPOSITORY": recovery.REPO,
        "GITHUB_REPOSITORY_ID": str(recovery.REPO_ID),
        "GITHUB_REPOSITORY_OWNER_ID": str(recovery.OWNER_ID),
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_WORKFLOW_REF": f"{recovery.REPO}/.github/workflows/{recovery.RECOVERY}@refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": str(CURRENT_ID),
        "GITHUB_SHA": SHA,
        "RECOVERY_EXECUTE": "true",
        **dict.fromkeys(recovery.FLAGS, "1"),
    }


class Fake:
    def __init__(self):
        self.current = make_run(CURRENT_ID, recovery.RECOVERY, "main", age=0, status="in_progress")
        self.own = {"total_count": 1, "workflow_runs": [self.current]}
        self.readers = {
            "total_count": 1,
            "workflow_runs": [make_run(8000, recovery.READER, "scentai-mvp")],
        }
        self.child = make_run(CHILD_ID, recovery.READER, "scentai-mvp", age=0, status="queued")
        self.reply = {
            "workflow_run_id": CHILD_ID,
            "run_url": f"{recovery.API}{recovery.PREFIX}/runs/{CHILD_ID}",
            "html_url": f"https://github.com/{recovery.REPO}/actions/runs/{CHILD_ID}",
        }
        self.calls = []
        self.posts = []
        self.read_count = 0
        self.race = False
        self.post_error = None
        self.dispatch_receipt = None
        self.post_attempted = False

    def call(self, method, path, body=None):
        self.calls.append((method, path))
        if method == "POST":
            self.posts.append((path, body))
            self.post_attempted = True
            if self.post_error:
                raise recovery.Refused(self.post_error)
            return copy.deepcopy(self.reply)
        parsed = urlsplit(path)
        if parsed.path == f"{recovery.PREFIX}/runs/{CURRENT_ID}":
            return copy.deepcopy(self.current)
        if parsed.path == f"{recovery.PREFIX}/runs/{CHILD_ID}":
            return copy.deepcopy(self.child)
        if parsed.path == f"{recovery.PREFIX}/workflows/{recovery.RECOVERY}/runs":
            return copy.deepcopy(self.own)
        assert parsed.path == f"{recovery.PREFIX}/workflows/{recovery.READER}/runs"
        if "status" in parse_qs(parsed.query):
            return {"total_count": 0, "workflow_runs": []}
        self.read_count += 1
        if self.race and self.read_count == 2:
            return {"total_count": 1, "workflow_runs": [self.child]}
        return copy.deepcopy(self.readers)


def invoke(client, env=None):
    return recovery.recover(client, environment() if env is None else env, NOW, clock=lambda: NOW)


@pytest.mark.parametrize("container", ["repository", "head_repository"])
@pytest.mark.parametrize("bad", [None, [], "wrong", 1])
def test_malformed_repository_container_is_sanitized_and_never_posts(container, bad):
    client = Fake()
    client.current[container] = bad
    with pytest.raises(recovery.Refused):
        invoke(client)
    assert not client.posts


@pytest.mark.parametrize("container", ["repository", "head_repository"])
@pytest.mark.parametrize("bad", [None, [], "wrong", 1])
def test_malformed_owner_container_is_sanitized_and_never_posts(container, bad):
    client = Fake()
    client.current[container]["owner"] = bad
    with pytest.raises(recovery.Refused):
        invoke(client)
    assert not client.posts


def test_absent_execute_flag_stays_dry_run():
    client = Fake()
    env = environment()
    del env["RECOVERY_EXECUTE"]
    assert invoke(client, env)["status"] == "ready_dry_run"
    assert not client.posts


def test_absent_reader_baseline_is_unknown_not_a_license_to_dispatch():
    client = Fake()
    client.readers = {"total_count": 0, "workflow_runs": []}
    with pytest.raises(recovery.Refused):
        invoke(client)
    assert not client.posts


@pytest.mark.parametrize("bad", [None, "not-a-conclusion", {}, False])
def test_completed_reader_requires_valid_conclusion(bad):
    client = Fake()
    client.readers["workflow_runs"][0]["conclusion"] = bad
    with pytest.raises(recovery.Refused):
        invoke(client)
    assert not client.posts


@pytest.mark.parametrize("bad", [None, "not-a-status", {}, []])
def test_status_shape_is_rejected_without_unsanitized_exception(bad):
    client = Fake()
    client.readers["workflow_runs"][0]["status"] = bad
    with pytest.raises(recovery.Refused):
        invoke(client)
    assert not client.posts


def test_active_reader_cannot_have_a_terminal_conclusion():
    client = Fake()
    run = client.readers["workflow_runs"][0]
    run["status"] = "in_progress"
    run["conclusion"] = "success"
    with pytest.raises(recovery.Refused):
        invoke(client)
    assert not client.posts


@pytest.mark.parametrize(
    "field,value", [("run_attempt", True), ("id", True), ("workflow_id", True)]
)
def test_boolean_ids_are_rejected(field, value):
    client = Fake()
    client.current[field] = value
    with pytest.raises(recovery.Refused):
        invoke(client)
    assert not client.posts


@pytest.mark.parametrize(
    "field,value", [("head_branch", "main"), ("event", "push"), ("workflow_id", 1)]
)
def test_reader_cross_scope_identity_is_rejected(field, value):
    client = Fake()
    client.readers["workflow_runs"][0][field] = value
    with pytest.raises(recovery.Refused):
        invoke(client)
    assert not client.posts


def test_future_original_timestamp_is_rejected():
    client = Fake()
    run = client.readers["workflow_runs"][0]
    run["created_at"] = run["updated_at"] = (NOW + timedelta(minutes=1)).isoformat()
    with pytest.raises(recovery.Refused, match="run_time_rejected"):
        invoke(client)
    assert not client.posts


def test_completed_run_rerun_attempt_is_refused_before_network():
    client = Fake()
    env = environment()
    env["GITHUB_RUN_ATTEMPT"] = "2"
    with pytest.raises(recovery.Refused, match="execution_identity_rejected"):
        invoke(client, env)
    assert not client.calls


def test_race_with_real_scheduler_is_suppressed_by_second_read():
    client = Fake()
    client.race = True
    assert invoke(client)["status"] == "observer_in_flight"
    assert not client.posts


@pytest.mark.parametrize("reason", ["dispatch_outcome_unknown", "unexpected_http_status"])
def test_unknown_or_rejected_dispatch_is_never_retried(reason):
    client = Fake()
    client.post_error = reason
    with pytest.raises(recovery.Refused, match=reason):
        invoke(client)
    assert len(client.posts) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("workflow_run_id", True),
        ("run_url", "https://attacker.example/steal"),
        ("html_url", "https://github.com/other/repo/actions/runs/9002"),
    ],
)
def test_dispatch_receipt_identity_is_not_guessed(field, value):
    client = Fake()
    client.reply[field] = value
    with pytest.raises(recovery.Refused, match="dispatch_receipt_unverified"):
        invoke(client)
    assert len(client.posts) == 1
    assert not client.dispatch_receipt


def test_fresh_attempt_does_not_claim_capture_or_restored_cadence():
    client = Fake()
    client.readers = {
        "total_count": 1,
        "workflow_runs": [make_run(8000, recovery.READER, "scentai-mvp", age=2)],
    }
    result = invoke(client)
    assert result["status"] == "recent_observer_attempt"
    assert result["capture_verified"] is False
    assert result["cadence_restored"] is False
    assert not client.posts


def test_failed_and_unknown_prior_invocations_consume_daily_budget():
    client = Fake()
    prior = [make_run(7000 + i, recovery.RECOVERY, "main", age=120 + i) for i in range(97)]
    for run in prior:
        run["conclusion"] = "failure"
    client.own = {"total_count": 98, "workflow_runs": [client.current, *prior]}
    assert invoke(client)["status"] == "recovery_rate_limit"
    assert not client.posts


def test_recovery_history_must_not_be_truncated():
    client = Fake()
    client.own["total_count"] = 101
    with pytest.raises(recovery.Refused, match="truncated_history"):
        invoke(client)
    assert not client.posts


def test_boolean_history_count_is_not_integer_evidence():
    client = Fake()
    client.own["total_count"] = True
    with pytest.raises(recovery.Refused, match="invalid_history"):
        invoke(client)
    assert not client.posts


def test_duplicate_own_history_cannot_bypass_budget():
    client = Fake()
    client.own = {"total_count": 2, "workflow_runs": [client.current, client.current]}
    with pytest.raises(recovery.Refused, match="duplicate_history"):
        invoke(client)
    assert not client.posts


def test_recovery_run_from_other_workflow_id_cannot_enter_budget_history():
    client = Fake()
    prior = make_run(7999, recovery.RECOVERY, "main", age=60)
    prior["workflow_id"] = 8002
    client.own = {"total_count": 2, "workflow_runs": [client.current, prior]}
    with pytest.raises(recovery.Refused, match="workflow_identity_rejected"):
        invoke(client)
    assert not client.posts


def test_exact_child_readback_failure_retains_response_identity_without_retry():
    client = Fake()
    client.child["repository"]["id"] = 123
    with pytest.raises(recovery.Refused, match="repository_identity_rejected"):
        invoke(client)
    assert len(client.posts) == 1
    assert client.dispatch_receipt == {
        "child_run_id": CHILD_ID,
        "child_url": f"https://github.com/{recovery.REPO}/actions/runs/{CHILD_ID}",
    }
