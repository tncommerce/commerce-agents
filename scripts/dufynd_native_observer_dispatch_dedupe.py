"""Fail-closed best-effort deduplication of native GitHub observer dispatches.

The default-branch reader and watchdog can arrive within seconds of one
another. Never pay for a second *attempt* when the same observer workflow was
recently dispatched. This cannot repair GitHub cron delivery or provide atomic
mutual exclusion; both default-branch jobs must also share concurrency.

Uses only the standard GITHUB_TOKEN and one fixed GitHub REST GET. No model,
merchant, Cloud Run, deployment or Supabase API calls occur here.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = "tncommerce/commerce-agents"
REPO_ID = 1367576041
OWNER_ID = 324597697
SOURCE_WORKFLOWS = frozenset(
    {
        "dufynd-private-observer.yml",
        "dufynd-private-observer-watchdog.yml",
    }
)
TARGET_WORKFLOW_ID = 373752411
TARGET_PATH = ".github/workflows/dufynd-private-observer.yml"
TARGET_BRANCH = "scentai-mvp"
API_URL = (
    "https://api.github.com/repos/tncommerce/commerce-agents/actions/"
    "workflows/373752411/runs?event=workflow_dispatch&branch=scentai-mvp&per_page=3"
)
MAX_BYTES = 512 * 1024
COOLDOWN = timedelta(seconds=180)
MAX_FUTURE_SKEW = timedelta(seconds=10)
STATUS = frozenset(
    {
        "queued",
        "in_progress",
        "waiting",
        "pending",
        "requested",
        "completed",
    }
)


class Refused(Exception):
    """Fixed, non-sensitive failure reason."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise Refused(reason)


def timestamp(value: object) -> datetime:
    require(isinstance(value, str), "run_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refused("run_timestamp_invalid") from exc
    require(parsed.tzinfo is not None, "run_timestamp_unqualified")
    return parsed.astimezone(UTC)


def validate_execution_identity(env: dict[str, str]) -> None:
    """Reject fork, untrusted event, stale rerun or unmatched workflow file."""
    require(
        env.get("GITHUB_REPOSITORY") == REPO
        and env.get("GITHUB_REPOSITORY_ID") == str(REPO_ID)
        and env.get("GITHUB_REPOSITORY_OWNER_ID") == str(OWNER_ID)
        and env.get("GITHUB_REF") == "refs/heads/main"
        and env.get("GITHUB_EVENT_NAME") in {"schedule", "workflow_dispatch"}
        and env.get("GITHUB_RUN_ATTEMPT") == "1",
        "source_execution_identity_rejected",
    )
    ref = env.get("GITHUB_WORKFLOW_REF") or ""
    require(
        any(
            ref == f"{REPO}/.github/workflows/{workflow}@refs/heads/main"
            for workflow in SOURCE_WORKFLOWS
        ),
        "source_workflow_identity_rejected",
    )


def validate_repo(identity: object) -> None:
    require(
        isinstance(identity, dict)
        and isinstance(identity.get("owner"), dict)
        and identity.get("id") == REPO_ID
        and identity.get("full_name") == REPO
        and identity.get("private") is False
        and identity["owner"].get("id") == OWNER_ID
        and identity["owner"].get("login") == "tncommerce",
        "target_repository_identity_rejected",
    )


def inspect_history(body: object, *, now: datetime) -> dict:
    """A recent attempt blocks another call, even when previous attempt failed."""
    require(isinstance(body, dict), "github_history_invalid")
    count = body.get("total_count")
    rows = body.get("workflow_runs")
    require(
        type(count) is int and count >= 0 and isinstance(rows, list) and len(rows) == min(count, 3),
        "github_history_truncated",
    )
    previous: datetime | None = None
    nearest: tuple[int, int, str] | None = None
    seen: set[int] = set()
    for row in rows:
        require(isinstance(row, dict), "target_run_invalid")
        validate_repo(row.get("repository"))
        validate_repo(row.get("head_repository"))
        require(
            type(row.get("id")) is int
            and row["id"] > 0
            and row["id"] not in seen
            and row.get("workflow_id") == TARGET_WORKFLOW_ID
            and row.get("path") == TARGET_PATH
            and row.get("head_branch") == TARGET_BRANCH
            and row.get("event") == "workflow_dispatch"
            and row.get("status") in STATUS
            and type(row.get("run_attempt")) is int
            and row["run_attempt"] >= 1
            and re.fullmatch(r"[0-9a-f]{40}", str(row.get("head_sha") or "")) is not None,
            "target_run_identity_rejected",
        )
        seen.add(row["id"])
        created = timestamp(row.get("created_at"))
        updated = timestamp(row.get("updated_at"))
        require(
            created <= updated
            and created <= now + MAX_FUTURE_SKEW
            and updated <= now + MAX_FUTURE_SKEW,
            "target_run_clock_rejected",
        )
        require(previous is None or created <= previous, "github_history_unordered")
        previous = created
        delta = now - created
        if timedelta(seconds=-10) <= delta < COOLDOWN and nearest is None:
            nearest = (row["id"], int(max(0, delta.total_seconds())), row["status"])

    if nearest is not None:
        return {
            "dispatch": False,
            "status": "skip_recent_observer_attempt",
            "recent_run_id": nearest[0],
            "recent_run_age_seconds": nearest[1],
            "recent_run_status": nearest[2],
            "examined_runs": len(rows),
        }
    return {
        "dispatch": True,
        "status": "eligible_no_recent_observer_attempt",
        "examined_runs": len(rows),
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_history(token: str, *, opener=None) -> dict:
    require(
        isinstance(token, str)
        and 10 <= len(token) <= 8192
        and not any(ch in token for ch in "\r\n"),
        "github_token_missing_or_invalid",
    )
    request = urllib.request.Request(
        API_URL,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        method="GET",
    )
    client = opener or urllib.request.build_opener(NoRedirect())
    try:
        with client.open(request, timeout=15) as response:
            require(response.status == 200, "github_history_http_status_invalid")
            require(not response.headers.get("Location"), "redirect_rejected")
            require(not response.headers.get("Retry-After"), "github_rate_limited")
            remaining = response.headers.get("X-RateLimit-Remaining", "")
            require(
                remaining.isdigit() and int(remaining) >= 10,
                "github_rate_budget_unverified",
            )
            raw = response.read(MAX_BYTES + 1)
            require(len(raw) <= MAX_BYTES, "github_history_too_large")
            return json.loads(raw)
    except Refused:
        raise
    except (OSError, urllib.error.URLError, ValueError, TimeoutError) as exc:
        raise Refused("github_history_read_failed") from exc


def evaluate(
    env: dict[str, str],
    *,
    now: datetime | None = None,
    opener=None,
) -> dict:
    validate_execution_identity(env)
    clock = (now or datetime.now(UTC)).astimezone(UTC)
    response = get_history(env.get("GH_TOKEN", ""), opener=opener)
    return inspect_history(response, now=clock)


def main() -> int:
    try:
        decision = evaluate(dict(os.environ))
        output = os.environ.get("GITHUB_OUTPUT", "")
        require(bool(output), "github_step_output_missing")
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"dispatch={'true' if decision['dispatch'] else 'false'}\n")
        print(json.dumps({"cooldown_seconds": 180, **decision}, sort_keys=True))
        return 0
    except Refused as exc:
        # Never print token, upstream bodies, error strings or the request URL.
        print(json.dumps({"status": "blocked", "reason": str(exc), "dispatch": False}))
        return 20


if __name__ == "__main__":
    sys.exit(main())
