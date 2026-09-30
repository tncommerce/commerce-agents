from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

DEFAULT_REPOSITORY = "tncommerce/commerce-agents"


def iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _github_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "DUFYND-Jarvis-Decision-Reconciler",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_pull_request(
    repository: str,
    pr_number: int,
    *,
    token: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    with httpx.Client(timeout=10.0, transport=transport) as client:
        response = client.get(
            f"https://api.github.com/repos/{repository}/pulls/{pr_number}",
            headers=_github_headers(token),
        )
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, dict):
        raise ValueError("GitHub pull-request lookup must return a JSON object")
    return payload


def build_merge_decision_reconciliation(
    decision: dict[str, Any],
    pull_request: dict[str, Any],
    *,
    resolved_at: str,
) -> dict[str, Any] | None:
    if str(decision.get("status") or "") != "pending":
        return None
    if str(decision.get("action_type") or "") != "merge_production_code":
        return None

    context = decision.get("context") or {}
    if not isinstance(context, dict):
        return None

    raw_pr_number = context.get("pr_number")
    try:
        expected_pr_number = int(raw_pr_number)
    except (TypeError, ValueError):
        return None

    try:
        actual_pr_number = int(pull_request.get("number"))
    except (TypeError, ValueError):
        return None
    if expected_pr_number != actual_pr_number:
        return None

    expected_head = str(context.get("head_sha") or "").strip()
    actual_head = str((pull_request.get("head") or {}).get("sha") or "").strip()
    if expected_head and actual_head != expected_head:
        return None

    expected_base = str(context.get("base_branch") or "").strip()
    actual_base = str((pull_request.get("base") or {}).get("ref") or "").strip()
    if expected_base and actual_base != expected_base:
        return None

    merged_at = pull_request.get("merged_at")
    state = str(pull_request.get("state") or "").lower()
    if merged_at:
        resolution = "already_merged"
    elif state == "closed":
        resolution = "superseded"
    else:
        return None

    payload = {
        "resolution": resolution,
        "reconciled": True,
        "reconciled_by": "jarvis_control_plane",
        "source": "github_pull_request_state",
        "resolved_at": resolved_at,
        "pr_number": actual_pr_number,
        "pr_url": pull_request.get("html_url"),
        "head_sha": actual_head or None,
        "base_branch": actual_base or None,
        "merge_commit_sha": pull_request.get("merge_commit_sha") if merged_at else None,
        "merged_at": merged_at,
        "closed_at": pull_request.get("closed_at"),
    }
    return {
        "decision_id": str(decision.get("decision_id") or ""),
        "resolution": resolution,
        "decision": payload,
        "resolved_at": resolved_at,
    }


def _task_references_pr(task: dict[str, Any], pr_number: int) -> bool:
    pattern = re.compile(rf"\\bPR\\s*#\\s*{pr_number}\\b")
    values: list[object] = [
        task.get("title"),
        task.get("instruction"),
        task.get("evidence"),
    ]
    dependencies = task.get("dependencies") or []
    if isinstance(dependencies, list):
        values.extend(dependencies)
    return any(pattern.search(str(value or "")) is not None for value in values)


def _approval_task_actions(
    queue: dict[str, Any],
    *,
    pr_number: int,
    resolution: str,
    resolved_at: str,
) -> list[dict[str, Any]]:
    target_status = "done" if resolution == "already_merged" else "cancelled"
    actions: list[dict[str, Any]] = []
    for task in queue.get("approval_required") or []:
        if not isinstance(task, dict):
            continue
        if str(task.get("status") or "") != "approval_required":
            continue
        if str(task.get("approval_action_type") or "") != "merge_production_code":
            continue
        if not _task_references_pr(task, pr_number):
            continue

        existing = str(task.get("evidence") or "").strip()
        note = (
            f"Jarvis deterministic reconciliation at {resolved_at}: "
            f"referenced PR #{pr_number} resolved as {resolution}; "
            f"approval task moved to {target_status} without granting approval."
        )
        evidence = f"{existing}\n{note}".strip()
        actions.append(
            {
                "task_id": str(task.get("task_id") or ""),
                "title": task.get("title"),
                "from_status": "approval_required",
                "to_status": target_status,
                "evidence": evidence,
                "write_applied": False,
            }
        )
    return actions


def reconcile_pending_merge_decisions(
    bridge: DufyndJarvisBridge,
    *,
    repository: str,
    write: bool,
    fetch_pr: Callable[[str, int], dict[str, Any]],
    resolved_at: str | None = None,
) -> dict[str, Any]:
    timestamp = resolved_at or iso_now()
    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    queue = bridge.load_autonomy_queue()

    for decision in bridge.load_pending_decisions():
        if not isinstance(decision, dict):
            continue
        if str(decision.get("action_type") or "") != "merge_production_code":
            continue

        context = decision.get("context") or {}
        raw_pr_number = context.get("pr_number") if isinstance(context, dict) else None
        try:
            pr_number = int(raw_pr_number)
        except (TypeError, ValueError):
            skipped.append(
                {
                    "decision_id": decision.get("decision_id"),
                    "reason": "missing_or_invalid_pr_number",
                }
            )
            continue

        try:
            pull_request = fetch_pr(repository, pr_number)
        except Exception as error:
            errors.append(
                {
                    "decision_id": decision.get("decision_id"),
                    "pr_number": pr_number,
                    "error": f"{type(error).__name__}: {str(error)[:1000]}",
                }
            )
            continue

        action = build_merge_decision_reconciliation(
            decision,
            pull_request,
            resolved_at=timestamp,
        )
        if action is None:
            skipped.append(
                {
                    "decision_id": decision.get("decision_id"),
                    "pr_number": pr_number,
                    "reason": "still_actionable_or_identity_mismatch",
                }
            )
            continue

        task_actions = _approval_task_actions(
            queue,
            pr_number=pr_number,
            resolution=action["resolution"],
            resolved_at=timestamp,
        )
        action["task_actions"] = task_actions

        if write:
            for task_action in task_actions:
                task_row = bridge.complete_pending_autonomy_task_reconciliation(
                    task_id=task_action["task_id"],
                    status=task_action["to_status"],
                    evidence=task_action["evidence"],
                )
                task_action["write_applied"] = task_row is not None

            row = bridge.complete_pending_human_decision_reconciliation(
                decision_id=action["decision_id"],
                decision=action["decision"],
                resolved_at=timestamp,
            )
            action["write_applied"] = row is not None
        else:
            action["write_applied"] = False
        actions.append(action)

    return {
        "repository": repository,
        "dry_run": not write,
        "reconciled": len(actions),
        "actions": actions,
        "skipped": skipped,
        "errors": errors,
        "granted_new_approval": False,
        "merged_pull_request": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile stale pending DUFYND merge decisions from GitHub PR state. "
            "Dry-run by default. This tool never grants approval and never merges a PR."
        )
    )
    parser.add_argument(
        "--repository",
        default=os.getenv("GITHUB_REPOSITORY", DEFAULT_REPOSITORY),
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    bridge = DufyndJarvisBridge()
    report = reconcile_pending_merge_decisions(
        bridge,
        repository=args.repository,
        write=bool(args.write),
        fetch_pr=lambda repository, pr_number: fetch_pull_request(
            repository,
            pr_number,
            token=token,
        ),
    )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False, default=str))
    else:
        print(
            "DUFYND decision reconciliation | "
            f"dry_run={report['dry_run']} | "
            f"reconciled={report['reconciled']} | "
            f"errors={len(report['errors'])}"
        )
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
