from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

DEFAULT_REPO_STATUS_PATH = Path("examples/retail/data/scentai_jarvis_master_status.json")
SNAPSHOT_KEY = "jarvis.repo_state_snapshot"


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
    if execution_state in {"manual_step_pending", "waiting_human_input"}:
        return "waiting_human_input", False
    if action_class.startswith("manual_"):
        return "waiting_human_input", False
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
            f"fingerprint={fingerprint}; "
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
                "approval_action_type": action_class if requires_approval else None,
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


def apply_sync_plan(bridge: DufyndJarvisBridge, plan: dict[str, Any]) -> None:
    snapshot = plan["snapshot"]
    bridge.upsert_master_status(**snapshot)

    for task in plan["tasks"]:
        bridge.upsert_autonomy_task(**task)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mirror the current repository Jarvis master status into the internal "
            "Supabase control plane. Dry-run by default."
        )
    )
    parser.add_argument("--repo-status", type=Path, default=DEFAULT_REPO_STATUS_PATH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    repo_status = load_json(args.repo_status)
    plan = build_sync_plan(repo_status)

    if args.write:
        apply_sync_plan(DufyndJarvisBridge(), plan)

    report = {
        "dry_run": not args.write,
        "wrote": bool(args.write),
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
