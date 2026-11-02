"""Adversarial checks for native GitHub observer dispatch deduplication."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "dufynd_native_observer_dedupe",
    ROOT / "scripts/dufynd_native_observer_dispatch_dedupe.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load dedupe helper")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
NOW = datetime(2026, 11, 2, 20, 33, tzinfo=UTC)


def time_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def repository_identity() -> dict:
    return {
        "id": MODULE.REPO_ID,
        "full_name": MODULE.REPO,
        "private": False,
        "owner": {"id": MODULE.OWNER_ID, "login": "tncommerce"},
    }


def run(age: int, *, run_id: int = 12345, **changes) -> dict:
    created = NOW - timedelta(seconds=age)
    result = {
        "id": run_id,
        "workflow_id": MODULE.TARGET_WORKFLOW_ID,
        "path": MODULE.TARGET_PATH,
        "head_branch": MODULE.TARGET_BRANCH,
        "event": "workflow_dispatch",
        "status": "completed",
        "run_attempt": 1,
        "head_sha": "a" * 40,
        "created_at": time_text(created),
        "updated_at": time_text(created + timedelta(seconds=1)),
        "repository": repository_identity(),
        "head_repository": repository_identity(),
    }
    result.update(changes)
    return result


def history(*rows: dict) -> dict:
    return {"total_count": len(rows), "workflow_runs": list(rows)}


def trusted_env(workflow: str = "dufynd-private-observer.yml") -> dict[str, str]:
    return {
        "GITHUB_REPOSITORY": MODULE.REPO,
        "GITHUB_REPOSITORY_ID": str(MODULE.REPO_ID),
        "GITHUB_REPOSITORY_OWNER_ID": str(MODULE.OWNER_ID),
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": (
            f"{MODULE.REPO}/.github/workflows/{workflow}@refs/heads/main"
        ),
        "GH_TOKEN": "test-token-with-enough-length",
    }


def test_near_simultaneous_reader_watchdog_runs_deduplicated() -> None:
    result = MODULE.inspect_history(history(run(33)), now=NOW)
    assert result["dispatch"] is False
    assert result["status"] == "skip_recent_observer_attempt"
    assert result["recent_run_age_seconds"] == 33


@pytest.mark.parametrize("age", [0, 1, 30, 120, 179])
@pytest.mark.parametrize("status", ["completed", "queued", "in_progress"])
def test_any_recent_attempt_blocks_duplicate_dispatch(age: int, status: str) -> None:
    assert (
        MODULE.inspect_history(history(run(age, status=status)), now=NOW)["dispatch"]
        is False
    )


def test_stale_or_empty_history_allows_only_normal_dispatch() -> None:
    assert MODULE.inspect_history(history(run(180)), now=NOW)["dispatch"] is True
    assert MODULE.inspect_history(history(), now=NOW)["dispatch"] is True
    assert (
        MODULE.inspect_history(history(run(240), run(350, run_id=12346)), now=NOW)[
            "dispatch"
        ]
        is True
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("workflow_id", 11, "target_run_identity_rejected"),
        ("path", ".github/workflows/another.yml", "target_run_identity_rejected"),
        ("head_branch", "main", "target_run_identity_rejected"),
        ("event", "schedule", "target_run_identity_rejected"),
        ("run_attempt", 0, "target_run_identity_rejected"),
        ("head_sha", "bad", "target_run_identity_rejected"),
        ("id", 0, "target_run_identity_rejected"),
        ("status", "unknown", "target_run_identity_rejected"),
        ("repository", {}, "target_repository_identity_rejected"),
        ("head_repository", {}, "target_repository_identity_rejected"),
        ("created_at", "not-date", "run_timestamp_invalid"),
        (
            "created_at",
            time_text(NOW + timedelta(seconds=30)),
            "target_run_clock_rejected",
        ),
        (
            "updated_at",
            time_text(NOW + timedelta(seconds=30)),
            "target_run_clock_rejected",
        ),
    ],
)
def test_run_identity_and_clock_fail_closed(field, value, reason) -> None:
    item = run(50)
    item[field] = value
    with pytest.raises(MODULE.Refused, match=reason):
        MODULE.inspect_history(history(item), now=NOW)


def test_duplicate_and_unsorted_run_histories_are_rejected() -> None:
    with pytest.raises(MODULE.Refused, match="target_run_identity_rejected"):
        MODULE.inspect_history(history(run(50), run(60)), now=NOW)
    with pytest.raises(MODULE.Refused, match="github_history_unordered"):
        MODULE.inspect_history(history(run(200), run(35, run_id=2)), now=NOW)


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({}, "github_history_truncated"),
        ({"total_count": 2, "workflow_runs": []}, "github_history_truncated"),
        ({"total_count": True, "workflow_runs": []}, "github_history_truncated"),
        ({"total_count": -1, "workflow_runs": []}, "github_history_truncated"),
    ],
)
def test_missing_or_truncated_history_cannot_authorize_dispatch(payload, reason) -> None:
    with pytest.raises(MODULE.Refused, match=reason):
        MODULE.inspect_history(payload, now=NOW)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("GITHUB_REPOSITORY", "attacker/commerce-agents"),
        ("GITHUB_REPOSITORY_ID", "13"),
        ("GITHUB_REPOSITORY_OWNER_ID", "2"),
        ("GITHUB_REF", "refs/heads/scentai-mvp"),
        ("GITHUB_EVENT_NAME", "pull_request"),
        ("GITHUB_RUN_ATTEMPT", "2"),
    ],
)
def test_untrusted_invocation_fails_identity_gate(field, value) -> None:
    env = trusted_env()
    env[field] = value
    with pytest.raises(MODULE.Refused, match="source_execution_identity_rejected"):
        MODULE.validate_execution_identity(env)


def test_only_approved_main_workflow_files_can_call_dedupe() -> None:
    MODULE.validate_execution_identity(trusted_env())
    MODULE.validate_execution_identity(
        trusted_env("dufynd-private-observer-watchdog.yml")
    )
    with pytest.raises(MODULE.Refused, match="source_workflow_identity_rejected"):
        MODULE.validate_execution_identity(trusted_env("untrusted.yml"))


class FakeResponse:
    def __init__(
        self, data: bytes, *, status: int = 200, remaining: str = "100", retry: str = ""
    ):
        self.data = data
        self.status = status
        self.headers = {"X-RateLimit-Remaining": remaining, "Retry-After": retry}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit):
        return self.data[:limit]


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append(
            (request.full_url, request.get_method(), timeout, request.get_header("Authorization"))
        )
        return self.response


def test_fixed_origin_read_only_one_get_uses_existing_token() -> None:
    opener = FakeOpener(FakeResponse(json.dumps(history(run(40))).encode()))
    result = MODULE.evaluate(trusted_env(), now=NOW, opener=opener)
    assert result["dispatch"] is False
    assert opener.calls == [
        (MODULE.API_URL, "GET", 15, "Bearer test-token-with-enough-length")
    ]


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (FakeResponse(b"{}", status=500), "github_history_http_status_invalid"),
        (FakeResponse(b"{}", remaining="3"), "github_rate_budget_unverified"),
        (FakeResponse(b"{}", remaining="unknown"), "github_rate_budget_unverified"),
        (FakeResponse(b"{}", retry="60"), "github_rate_limited"),
        (FakeResponse(b"x" * (MODULE.MAX_BYTES + 1)), "github_history_too_large"),
        (FakeResponse(b"not-json"), "github_history_read_failed"),
    ],
)
def test_provider_failure_and_unknown_budget_never_dispatch(response, error) -> None:
    opener = FakeOpener(response)
    with pytest.raises(MODULE.Refused, match=error):
        MODULE.get_history("test-token-with-enough-length", opener=opener)
    assert len(opener.calls) == 1


def test_missing_or_control_character_token_refused() -> None:
    for token in ("", "abc\nHTTP\n"):
        with pytest.raises(MODULE.Refused, match="github_token_missing_or_invalid"):
            MODULE.get_history(token)


@pytest.mark.parametrize(("dispatch", "word"), [(True, "true"), (False, "false")])
def test_output_only_written_after_successful_check(monkeypatch, tmp_path, dispatch, word):
    path = tmp_path / "gate-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    monkeypatch.setattr(
        MODULE, "evaluate", lambda *_args: {"dispatch": dispatch, "status": "fixture"}
    )
    assert MODULE.main() == 0
    assert path.read_text(encoding="utf-8") == f"dispatch={word}\n"


def test_refusal_never_emits_positive_output(monkeypatch, tmp_path) -> None:
    output = tmp_path / "gate-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def reject(*_args):
        raise MODULE.Refused("target_repository_identity_rejected")

    monkeypatch.setattr(MODULE, "evaluate", reject)
    assert MODULE.main() == 20
    assert not output.exists()


def test_both_scheduled_workflows_use_shared_serial_guard() -> None:
    targets = [
        (".github/workflows/dufynd-private-observer.yml", "scheduled-dispatch"),
        (".github/workflows/dufynd-private-observer-watchdog.yml", "dispatch"),
    ]
    for path, job in targets:
        content = (ROOT / path).read_text(encoding="utf-8")
        wf = yaml.safe_load(content)
        steps = wf["jobs"][job]["steps"]
        guard = next(step for step in steps if step.get("id") == "cooldown")
        i = steps.index(guard)
        assert i > 0
        assert "checkout@" in steps[i - 1]["uses"]
        assert steps[i - 1]["with"]["persist-credentials"] is False
        assert guarded_token(guard) is True
        assert guard["run"] == "python3 scripts/dufynd_native_observer_dispatch_dedupe.py"
        outgoing = next(step for step in steps if "gh workflow run" in step.get("run", ""))
        assert steps.index(outgoing) > i
        assert outgoing["if"] == "steps.cooldown.outputs.dispatch == 'true'"
        assert "mode=render" in outgoing["run"]
        assert "mode=render_services_v2" in outgoing["run"]

    reader = yaml.safe_load((ROOT / targets[0][0]).read_text(encoding="utf-8"))
    watchdog = yaml.safe_load((ROOT / targets[1][0]).read_text(encoding="utf-8"))
    assert reader["concurrency"]["group"] == (
        "dufynd-private-observer-" + chr(36) + "{{ github.ref_name }}"
    )
    assert watchdog["concurrency"]["group"] == "dufynd-private-observer-main"
    assert reader["concurrency"]["cancel-in-progress"] is False
    assert watchdog["concurrency"]["cancel-in-progress"] is False


def guarded_token(step: dict) -> bool:
    return step["env"]["GH_TOKEN"] == chr(36) + "{{ github.token }}"
