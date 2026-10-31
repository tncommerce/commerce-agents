"""Bounded manual recovery entry; never implements an independent clock itself."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = "tncommerce/commerce-agents"
REPO_ID = 1367576041
OWNER_ID = 324597697
API = "https://api.github.com"
PREFIX = f"/repos/{REPO}/actions"
READER = "dufynd-private-observer.yml"
RECOVERY = "dufynd-private-observer-recovery.yml"
READER_ID = 373752411
FLAGS = (
    "DUFYND_PRIVATE_BROKER_ENABLED",
    "DUFYND_PRIVATE_RENDER_SERVICES_V2_ENABLED",
    "DUFYND_PRIVATE_RENDER_SERVICES_V2_AUTO_ENABLED",
)
COOLDOWN = timedelta(minutes=15)
ACTIVE_LIMIT = timedelta(minutes=30)
MAX_HOURLY = 5
MAX_DAILY = 97
MAX_BYTES = 4 * 1024 * 1024
MAX_REQUESTS = 12
ACTIVE = {"queued", "in_progress", "waiting", "pending", "requested"}
STATUS = ACTIVE | {"completed"}


class Refused(Exception):
    """Safe fixed reason, never an upstream response or credential."""


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def stamp(value):
    require(isinstance(value, str), "invalid_time")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise Refused("invalid_time") from error
    require(result.tzinfo is not None, "invalid_time")
    return result.astimezone(UTC)


def integer(value):
    return type(value) is int and value > 0


def validate_run(run, workflow, branch, now):
    require(isinstance(run, dict), "invalid_run")
    repository = run.get("repository", {})
    head_repository = run.get("head_repository", {})
    for repo in (repository, head_repository):
        require(
            isinstance(repo, dict) and isinstance(repo.get("owner"), dict),
            "repository_identity_rejected",
        )
        require(
            repo.get("id") == REPO_ID
            and repo.get("full_name") == REPO
            and repo.get("owner", {}).get("id") == OWNER_ID
            and repo.get("private") is False,
            "repository_identity_rejected",
        )
    require(
        integer(run.get("id"))
        and integer(run.get("workflow_id"))
        and run.get("path") == f".github/workflows/{workflow}"
        and run.get("head_branch") == branch
        and run.get("event") == "workflow_dispatch"
        and isinstance(run.get("status"), str)
        and run.get("status") in STATUS
        and integer(run.get("run_attempt"))
        and re.fullmatch(r"[a-f0-9]{40}", str(run.get("head_sha", ""))),
        "run_identity_rejected",
    )
    conclusion = run.get("conclusion")
    require(
        (run["status"] in ACTIVE and conclusion is None)
        or (
            run["status"] == "completed"
            and isinstance(conclusion, str)
            and conclusion
            in {
                "success",
                "failure",
                "cancelled",
                "skipped",
                "neutral",
                "timed_out",
                "action_required",
                "startup_failure",
                "stale",
            }
        ),
        "run_result_rejected",
    )
    if workflow == READER:
        require(run["workflow_id"] == READER_ID, "workflow_identity_rejected")
    created, updated = stamp(run.get("created_at")), stamp(run.get("updated_at"))
    require(created <= updated <= now, "run_time_rejected")
    return created


def history(body, workflow, branch, now, *, complete=True):
    require(isinstance(body, dict), "invalid_history")
    runs = body.get("workflow_runs")
    count = body.get("total_count")
    require(type(count) is int and count >= 0 and isinstance(runs, list), "invalid_history")
    require(len(runs) <= 100 and len(runs) == min(count, 100), "truncated_history")
    if complete:
        require(count <= 100, "truncated_history")
    seen = set()
    for run in runs:
        validate_run(run, workflow, branch, now)
        require(run["id"] not in seen, "duplicate_history")
        seen.add(run["id"])
    require(
        runs == sorted(runs, key=lambda run: stamp(run["created_at"]), reverse=True),
        "unordered_history",
    )
    return runs


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    """Fixed origin, no redirects/retries, bounded response and request budget."""

    def __init__(self, token):
        require(bool(token) and "\n" not in token and "\r" not in token, "missing_token")
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())
        self.requests = 0
        self.post_attempted = False
        self.dispatch_receipt = None

    def call(self, method, path, body=None):
        require(path.startswith(PREFIX + "/") and "://" not in path, "path_rejected")
        require(method in {"GET", "POST"}, "method_rejected")
        if method == "POST":
            require(
                path == f"{PREFIX}/workflows/{READER}/dispatches"
                and body
                == {
                    "ref": "scentai-mvp",
                    "inputs": {"mode": "render_services_v2", "capture_v2": True},
                }
                and not self.post_attempted,
                "dispatch_contract_rejected",
            )
            self.post_attempted = True
        self.requests += 1
        require(self.requests <= MAX_REQUESTS, "request_budget_exhausted")
        request = urllib.request.Request(
            API + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
            method=method,
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                require(response.status == 200, "unexpected_http_status")
                if method == "GET":
                    remaining = response.headers.get("X-RateLimit-Remaining", "")
                    require(
                        remaining.isdigit() and int(remaining) >= MAX_REQUESTS,
                        "rate_budget_unverified",
                    )
                    require(not response.headers.get("Retry-After"), "rate_limited")
                raw = response.read(MAX_BYTES + 1)
                require(len(raw) <= MAX_BYTES, "response_too_large")
                return json.loads(raw)
        except Refused:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            raise Refused(
                "dispatch_outcome_unknown" if method == "POST" else "github_read_failed"
            ) from error


def result(status, **values):
    return {
        "version": 1,
        "status": status,
        "capture_verified": False,
        "cadence_restored": False,
        **values,
    }


def reader_state(client, now):
    path = f"{PREFIX}/workflows/{READER}/runs?" + urllib.parse.urlencode(
        {"event": "workflow_dispatch", "branch": "scentai-mvp", "per_page": 100}
    )
    body = client.call("GET", path)
    runs = history(body, READER, "scentai-mvp", now, complete=False)
    require(bool(runs), "observer_history_empty")
    # A fresh/in-flight run proves that another dispatch is unnecessary even if
    # older history is truncated. No freshness/capture claim follows from this.
    for run in runs:
        age = now - stamp(run["created_at"])
        if run["status"] in ACTIVE:
            require(age <= ACTIVE_LIMIT, "observer_stuck_in_flight")
            return "observer_in_flight"
        if age < COOLDOWN:
            return "recent_observer_attempt"
    # For an idle reader, bounded API history alone cannot prove an older active
    # run is absent. Query active states separately, without scanning all history.
    return "needs_active_check"


def recover(client, env, now, clock=None):
    clock = clock or (lambda: datetime.now(UTC))
    require(now.tzinfo is not None, "invalid_clock")
    require(
        env.get("GITHUB_REPOSITORY") == REPO
        and env.get("GITHUB_REPOSITORY_ID") == str(REPO_ID)
        and env.get("GITHUB_REPOSITORY_OWNER_ID") == str(OWNER_ID)
        and env.get("GITHUB_REF") == "refs/heads/main"
        and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and env.get("GITHUB_WORKFLOW_REF") == f"{REPO}/.github/workflows/{RECOVERY}@refs/heads/main"
        and env.get("GITHUB_RUN_ATTEMPT") == "1",
        "execution_identity_rejected",
    )
    if any(env.get(flag) != "1" for flag in FLAGS):
        return result("existing_v2_gates_closed", dispatch_attempted=False)
    require(env.get("RECOVERY_EXECUTE", "false") in {"true", "false"}, "invalid_execute_gate")
    require(re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ID", "")), "invalid_run_id")
    current_id = int(env["GITHUB_RUN_ID"])
    current = client.call("GET", f"{PREFIX}/runs/{current_id}")
    validate_run(current, RECOVERY, "main", now)
    require(
        current["id"] == current_id
        and current["head_sha"] == env.get("GITHUB_SHA")
        and current["run_attempt"] == 1
        and current["status"] == "in_progress"
        and now - stamp(current["created_at"]) < ACTIVE_LIMIT,
        "current_run_rejected",
    )
    since = (now - timedelta(days=1)).isoformat()
    own_path = f"{PREFIX}/workflows/{RECOVERY}/runs?" + urllib.parse.urlencode(
        {"event": "workflow_dispatch", "branch": "main", "created": ">=" + since, "per_page": 100}
    )
    own = history(client.call("GET", own_path), RECOVERY, "main", now)
    require(any(run["id"] == current_id for run in own), "current_run_missing_from_history")
    require(
        all(run["workflow_id"] == current["workflow_id"] for run in own),
        "workflow_identity_rejected",
    )
    require(
        all(now - stamp(run["created_at"]) <= timedelta(days=1) for run in own),
        "history_window_rejected",
    )
    prior = [run for run in own if run["id"] != current_id]
    # Count ALL entry attempts, including failed/unknown/no-op attempts. The
    # external caller must therefore use at most one invocation per 15 minutes.
    if (
        len(prior) >= MAX_DAILY
        or sum(now - stamp(run["created_at"]) < timedelta(hours=1) for run in prior) >= MAX_HOURLY
    ):
        return result("recovery_rate_limit", dispatch_attempted=False)
    if any(now - stamp(run["created_at"]) < COOLDOWN for run in prior):
        return result("recovery_cooldown", dispatch_attempted=False)
    state = reader_state(client, now)
    if state != "needs_active_check":
        return result(state, dispatch_attempted=False)
    # Inspect every active state, including old waiting runs outside page one.
    for state in sorted(ACTIVE):
        path = f"{PREFIX}/workflows/{READER}/runs?" + urllib.parse.urlencode(
            {
                "event": "workflow_dispatch",
                "branch": "scentai-mvp",
                "status": state,
                "per_page": 100,
            }
        )
        active = history(client.call("GET", path), READER, "scentai-mvp", now)
        require(all(run["status"] == state for run in active), "active_filter_rejected")
        if active:
            return result("observer_in_flight", dispatch_attempted=False)
    # Final read narrows (does not eliminate) the race with the native scheduler.
    state = reader_state(client, now)
    if state != "needs_active_check":
        return result(state, dispatch_attempted=False)
    if env.get("RECOVERY_EXECUTE", "false") != "true":
        return result("ready_dry_run", dispatch_attempted=False)
    attempted_at = clock()
    reply = client.call(
        "POST",
        f"{PREFIX}/workflows/{READER}/dispatches",
        {"ref": "scentai-mvp", "inputs": {"mode": "render_services_v2", "capture_v2": True}},
    )
    child_id = reply.get("workflow_run_id") if isinstance(reply, dict) else None
    require(
        integer(child_id)
        and reply.get("run_url") == f"{API}{PREFIX}/runs/{child_id}"
        and reply.get("html_url") == f"https://github.com/{REPO}/actions/runs/{child_id}",
        "dispatch_receipt_unverified",
    )
    # Exact dispatch response is retained even if eventual-consistency readback
    # fails; POST is never retried or correlated by timestamp guesses.
    client.dispatch_receipt = {"child_run_id": child_id, "child_url": reply["html_url"]}
    child = client.call("GET", f"{PREFIX}/runs/{child_id}")
    validate_run(child, READER, "scentai-mvp", clock())
    require(
        stamp(child["created_at"]) >= attempted_at - timedelta(seconds=5), "dispatch_run_rejected"
    )
    require(child["id"] == child_id and child["run_attempt"] == 1, "dispatch_run_rejected")
    return result(
        "dispatched", dispatch_attempted=True, child_run_id=child_id, child_url=reply["html_url"]
    )


def main():
    client = None
    try:
        client = GitHub(os.environ.get("GH_TOKEN", ""))
        receipt = recover(client, os.environ, datetime.now(UTC))
    except Refused as error:
        receipt = result(
            "blocked",
            reason=str(error),
            dispatch_attempted=bool(client and client.post_attempted),
            **((client.dispatch_receipt or {}) if client else {}),
        )
    Path("observer-recovery-receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 2 if receipt["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
