from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_jarvis_control_plane import ACTIVE_STATES, HUMAN_REASONS

DEFAULT_REPO_STATUS_PATH = Path("examples/retail/data/scentai_jarvis_master_status.json")
SNAPSHOT_KEY = "jarvis.repo_state_snapshot"
PRESERVED_SAME_FINGERPRINT_STATUSES = {
    "done",
    "in_progress",
    "blocked",
    "waiting_human_input",
    "waiting_external",
    "approval_required",
    "cancelled",
    "failed_retryable",
    "failed_terminal",
    "stale",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _humanize_action(action: object, domain: str) -> str:
    text = str(action or "").strip()
    if not text:
        return f"Maintain current {domain} state"
    return text.replace("_", " ").strip().capitalize()


def _task_state(domain_state: dict[str, Any]) -> tuple[str, bool]:
    action_class = str(domain_state.get("next_action_class") or "").strip()
    execution_state = str(domain_state.get("execution_state") or "").strip()
    approval_now = bool(domain_state.get("user_approval_required_now"))

    if approval_now or action_class in {"approval_required", "human_approval_required"}:
        return "approval_required", True
    if execution_state == "work_available" and action_class == "auto_allowed":
        return "ready", False
    if execution_state == "waiting_human_input":
        return "waiting_human_input", False
    if execution_state == "manual_step_pending":
        return "waiting_external", False
    if action_class.startswith("manual_"):
        return "waiting_external", False
    if execution_state in {"waiting_external", "blocked_external"}:
        return "waiting_external", False
    if not domain_state.get("next_action"):
        return "done", False
    return "planned", False


def build_sync_plan(repo_status: dict[str, Any]) -> dict[str, Any]:
    generated_at = str(repo_status.get("generated_at") or "").strip()
    fingerprint = str(repo_status.get("source_fingerprint_sha256") or "").strip()
    if not generated_at:
        raise ValueError("repo status generated_at is required")
    if not fingerprint:
        raise ValueError("repo status source_fingerprint_sha256 is required")

    domains = repo_status.get("domains") or {}
    if not isinstance(domains, dict):
        raise ValueError("repo status domains must be a JSON object")

    snapshot = {
        "key": SNAPSHOT_KEY,
        "category": "jarvis",
        "value": repo_status,
        "priority": 100,
        "last_verified_at": generated_at,
    }

    tasks: list[dict[str, Any]] = []
    active_domain = str(repo_status.get("active_domain") or "").strip()

    for domain in sorted(domains):
        raw_state = domains.get(domain) or {}
        if not isinstance(raw_state, dict):
            continue

        status, requires_approval = _task_state(raw_state)
        next_action = raw_state.get("next_action")
        action_class = str(raw_state.get("next_action_class") or "").strip() or None
        blockers = [str(item) for item in (raw_state.get("blockers") or []) if str(item).strip()]
        title = _humanize_action(next_action, domain)
        evidence = (
            f"Derived from repo Jarvis master status generated_at={generated_at}; "
            f"source_fingerprint_sha256={fingerprint}; "
            f"overall_state={raw_state.get('overall_state')}; "
            f"execution_state={raw_state.get('execution_state')}."
        )

        tasks.append(
            {
                "task_id": f"repo_current_{domain}",
                "domain": domain,
                "title": title,
                "instruction": (
                    f"Use the current repository state as source of truth. "
                    f"Execute only the repo-derived {domain} action: "
                    f"{next_action or 'maintain_current_state'}. "
                    "Re-check Jarvis freshness before any material action."
                ),
                "status": status,
                "priority": 100 if domain == active_domain else 90,
                "requires_human_approval": requires_approval,
                "approval_action_type": action_class,
                "dependencies": blockers,
                "evidence": evidence,
                "owner": "human_and_jarvis" if requires_approval else "jarvis",
            }
        )

    return {
        "snapshot": snapshot,
        "tasks": tasks,
        "generated_at": generated_at,
        "source_fingerprint_sha256": fingerprint,
    }


def _evidence_has_fingerprint(evidence: object, fingerprint: str) -> bool:
    text = str(evidence or "")
    return (
        f"source_fingerprint_sha256={fingerprint}" in text or f"fingerprint={fingerprint}" in text
    )


def _preserve_same_fingerprint_state(
    existing: dict[str, Any],
    task: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any] | None:
    """Skip unsafe implicit task transitions; sync is not a per-task owner GO.

    A new repo fingerprint is metadata about source content, not permission to
    reopen completed, blocked, leased or model-budget work. An owner-approved
    task transition uses its own explicit, separately audited lifecycle action.
    """
    if not isinstance(existing, dict):
        raise ValueError("existing_repo_task_must_be_object")
    if existing.get("task_id") not in (None, task["task_id"]):
        raise ValueError("existing_repo_task_identity_mismatch")

    existing_status = str(existing.get("status") or "")
    if not existing_status:
        return None
    # The source generator does not carry this task's budget decision. Unknown
    # cost class and all existing model tasks are immutable through repo sync,
    # even when the fingerprint or source action changes.
    if existing.get("budget_class") != "free" or existing.get("provider_cost_unknown") is True:
        return None
    # Never overwrite a typed owner decision or an active worker lease.
    if (
        existing.get("requires_human_approval") is True
        or existing.get("blocked_reason") in HUMAN_REASONS
        or existing_status in ACTIVE_STATES
        or existing.get("worker_state") in ACTIVE_STATES
        or (
            existing_status == "ready"
            and existing.get("worker_state") in PRESERVED_SAME_FINGERPRINT_STATUSES
        )
    ):
        return None
    # A changed repository hash must not turn historical done/held work into
    # ready tasks. New work needs a distinct ID or a separately gated lifecycle.
    if existing_status in PRESERVED_SAME_FINGERPRINT_STATUSES and not _evidence_has_fingerprint(
        existing.get("evidence"), fingerprint
    ):
        return None
    if (
        existing_status == "waiting_human_input"
        and task.get("status") == "waiting_external"
        and not task.get("requires_human_approval")
        and not existing.get("requires_human_approval")
        and existing.get("blocked_reason") not in HUMAN_REASONS
        and str(task.get("approval_action_type") or "").startswith("manual_")
    ):
        reconciled = dict(task)
        reconciled["evidence"] = (
            str(existing.get("evidence") or task.get("evidence") or "")
            + "\n"
            + str(task.get("evidence") or "")
            + "\nSupervisor V2: technical reconciliation awaits external observations; no explicit owner decision encoded."
        )[-12000:]
        return reconciled
    if existing_status not in PRESERVED_SAME_FINGERPRINT_STATUSES:
        return task
    if not _evidence_has_fingerprint(existing.get("evidence"), fingerprint):
        return task

    preserved = dict(task)
    preserved["status"] = existing_status
    preserved["evidence"] = str(existing.get("evidence") or task.get("evidence") or "")
    return preserved


def apply_sync_plan(
    bridge: DufyndJarvisBridge, plan: dict[str, Any], *, snapshot_only: bool = False
) -> dict[str, int]:
    snapshot = plan["snapshot"]
    if snapshot_only:
        bridge.upsert_master_status(**snapshot)
        return {
            "tasks_written": 0,
            "existing_tasks_protected": 0,
            "missing_tasks_not_created": 0,
        }

    # Read and classify every existing task before the first write. An API
    # failure must not leave a new snapshot with half-reconciled task metadata.
    fingerprint = str(plan["source_fingerprint_sha256"])
    approved_updates: list[dict[str, Any]] = []
    protected_count = 0
    missing_count = 0
    for task in plan["tasks"]:
        existing = bridge.load_autonomy_task(task["task_id"])
        if existing is None:
            # Supabase defaults new tasks to budget_class='model'. A generic
            # source refresh cannot authorize creation of new model work.
            missing_count += 1
            continue
        candidate = _preserve_same_fingerprint_state(existing, task, fingerprint)
        if candidate is None:
            protected_count += 1
        else:
            approved_updates.append(candidate)

    bridge.upsert_master_status(**snapshot)
    for task in approved_updates:
        bridge.upsert_autonomy_task(**task)
    return {
        "tasks_written": len(approved_updates),
        "existing_tasks_protected": protected_count,
        "missing_tasks_not_created": missing_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mirror the current repository Jarvis master status into the internal "
            "Supabase control plane. Dry-run by default."
        )
    )
    parser.add_argument("--repo-status", type=Path, default=DEFAULT_REPO_STATUS_PATH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Update only the canonical control-plane snapshot; never requeue tasks.",
    )
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    repo_status = load_json(args.repo_status)
    plan = build_sync_plan(repo_status)

    effects = {
        "tasks_written": 0,
        "existing_tasks_protected": 0,
        "missing_tasks_not_created": 0,
    }
    if args.write:
        effects = apply_sync_plan(DufyndJarvisBridge(), plan, snapshot_only=args.snapshot_only)

    report = {
        "dry_run": not args.write,
        "wrote": bool(args.write),
        "snapshot_only": bool(args.snapshot_only),
        "tasks_written": effects["tasks_written"],
        "existing_tasks_protected": effects["existing_tasks_protected"],
        "missing_tasks_not_created": effects["missing_tasks_not_created"],
        "snapshot_key": plan["snapshot"]["key"],
        "generated_at": plan["generated_at"],
        "source_fingerprint_sha256": plan["source_fingerprint_sha256"],
        "task_count": len(plan["tasks"]),
        "tasks": [
            {
                "task_id": task["task_id"],
                "domain": task["domain"],
                "status": task["status"],
                "priority": task["priority"],
                "requires_human_approval": task["requires_human_approval"],
            }
            for task in plan["tasks"]
        ],
        "live_catalog_modified": False,
        "affiliate_routing_modified": False,
        "money_spent": False,
        "outbound_message_sent": False,
    }

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "DUFYND Jarvis control-plane sync | "
            f"dry_run={report['dry_run']} | "
            f"tasks={report['task_count']} | "
            f"snapshot={report['snapshot_key']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
