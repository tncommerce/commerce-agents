from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import httpx

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

DEFAULT_REPOSITORY = "tncommerce/commerce-agents"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    if expected_head and actual_head and expected_head != actual_head:
        return None

    expected_base = str(context.get("base_branch") or "").strip()
    actual_base = str((pull_request.get("base") or {}).get("ref") or "").strip()
    if expected_base and actual_base and expected_base != actual_base:
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

        if write:
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
