from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_jarvis_freshness import evaluate_freshness

DATA_DIR = Path("examples/retail/data")
DEFAULT_REPO_STATUS_PATH = DATA_DIR / "scentai_jarvis_master_status.json"
DEFAULT_CONTRACT_PATH = DATA_DIR / "dufynd_jarvis_contract.json"
CHECKPOINT_PREFIX = "continuity.checkpoint."
VALID_DOMAINS = ("tech", "content", "jarvis", "business", "global")
QUEUE_BUCKETS = (
    "safe_to_execute",
    "in_progress",
    "waiting_human_input",
    "waiting_external",
    "approval_required",
    "done_recent",
)
DOMAIN_TASKS = {
    "tech": {"engineering", "platform"},
    "content": {"content", "creative", "creative_ops"},
    "jarvis": {"jarvis"},
    "business": {"commerce", "product", "affiliate", "finance", "business"},
    "global": set(),
}
FORBIDDEN_CHECKPOINT_FIELDS = {
    "password",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "credential",
    "credentials",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _domain_matches(logical_domain: str, task_domain: object) -> bool:
    if logical_domain == "global":
        return True
    return str(task_domain or "").strip() in DOMAIN_TASKS[logical_domain]


def _queue_tasks(queue: dict[str, Any], logical_domain: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    tasks: list[dict[str, Any]] = []
    for bucket in QUEUE_BUCKETS:
        rows = queue.get(bucket) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or not _domain_matches(logical_domain, row.get("domain")):
                continue
            task_id = str(row.get("task_id") or "").strip()
            key = task_id or json.dumps(row, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            item = dict(row)
            item["queue_bucket"] = bucket
            tasks.append(item)
    return tasks


def _task_rank(task: dict[str, Any]) -> tuple[int, int]:
    status = str(task.get("status") or "")
    status_rank = {
        "in_progress": 5,
        "ready": 4,
        "planned": 3,
        "waiting_human_input": 2,
        "waiting_external": 1,
        "approval_required": 0,
        "blocked": 0,
        "done": -1,
    }.get(status, 0)
    return status_rank, int(task.get("priority") or 0)


def _next_safe_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        task
        for task in tasks
        if str(task.get("status") or "") in {"ready", "in_progress", "planned"}
        and not bool(task.get("requires_human_approval"))
    ]
    if not candidates:
        return None
    return max(candidates, key=_task_rank)


def _find_master_row(master_status: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for row in master_status:
        if isinstance(row, dict) and row.get("key") == key:
            return row
    return None


def _checkpoint_view(
    master_status: list[dict[str, Any]],
    logical_domain: str,
    repo_fingerprint: str,
    repo_head: str | None,
) -> dict[str, Any] | None:
    row = _find_master_row(master_status, f"{CHECKPOINT_PREFIX}{logical_domain}")
    if row is None:
        return None
    value = row.get("value") if isinstance(row.get("value"), dict) else {}
    checkpoint_fingerprint = str(value.get("source_fingerprint_sha256") or "").strip()
    checkpoint_head = str(value.get("repo_head") or "").strip()
    current_head = str(repo_head or "").strip()
    fingerprint_fresh = bool(repo_fingerprint and checkpoint_fingerprint == repo_fingerprint)
    head_fresh = bool(current_head and checkpoint_head == current_head)
    return {
        "fresh": fingerprint_fresh and head_fresh,
        "fingerprint_fresh": fingerprint_fresh,
        "head_fresh": head_fresh,
        "last_verified_at": row.get("last_verified_at"),
        "value": value,
    }


def _repo_domain_state(repo_status: dict[str, Any], logical_domain: str) -> dict[str, Any] | None:
    domains = repo_status.get("domains") or {}
    if not isinstance(domains, dict):
        return None
    mapping = {"content": "content", "business": "commerce"}
    key = mapping.get(logical_domain)
    if key is None:
        return None
    value = domains.get(key)
    return value if isinstance(value, dict) else None


def _compact_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        key: task.get(key)
        for key in (
            "task_id",
            "domain",
            "title",
            "status",
            "priority",
            "requires_human_approval",
            "dependencies",
            "evidence",
            "queue_bucket",
            "updated_at",
        )
        if task.get(key) not in (None, [], "")
    }


def _checkpoint_next_safe_action(checkpoint: dict[str, Any] | None) -> dict[str, Any] | None:
    if not checkpoint or not bool(checkpoint.get("fresh")):
        return None
    value = checkpoint.get("value")
    if not isinstance(value, dict):
        return None
    action = value.get("next_safe_action")
    if action in (None, "", [], {}):
        return None
    return {
        "source": "checkpoint",
        "action": action,
        "checkpointed_at": value.get("checkpointed_at") or checkpoint.get("last_verified_at"),
    }


def build_bootstrap_context(
    *,
    logical_domain: str,
    repo_status: dict[str, Any],
    contract: dict[str, Any],
    live_context: dict[str, Any] | None = None,
    autonomy_queue: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
    pending_decisions: list[dict[str, Any]] | None = None,
    repo_branch: str = "scentai-mvp",
    repo_head: str | None = None,
) -> dict[str, Any]:
    if logical_domain not in VALID_DOMAINS:
        raise ValueError(f"Unsupported continuity domain: {logical_domain}")

    live_context = live_context or {}
    autonomy_queue = autonomy_queue or {}
    health = health or {}
    pending_decisions = pending_decisions or []
    master_status = live_context.get("master_status") or []
    if not isinstance(master_status, list):
        master_status = []

    if live_context:
        freshness = evaluate_freshness(repo_status, live_context)
    else:
        freshness = {
            "stale": True,
            "safe_to_use_autonomy_queue": False,
            "reasons": ["live_control_plane_not_loaded"],
            "repo_source_fingerprint_sha256": repo_status.get("source_fingerprint_sha256"),
            "supabase_source_fingerprint_sha256": None,
        }

    repo_fingerprint = str(repo_status.get("source_fingerprint_sha256") or "").strip()
    checkpoint = _checkpoint_view(
        master_status,
        logical_domain,
        repo_fingerprint,
        repo_head,
    )
    tasks = _queue_tasks(autonomy_queue, logical_domain)
    next_task = _next_safe_task(tasks) if freshness.get("safe_to_use_autonomy_queue") else None

    active = [
        _compact_task(task)
        for task in tasks
        if str(task.get("status") or "") in {"ready", "in_progress", "planned"}
    ][:10]
    blocked = [
        _compact_task(task)
        for task in tasks
        if str(task.get("status") or "")
        in {"blocked", "waiting_human_input", "waiting_external", "approval_required"}
    ][:10]
    recent = [_compact_task(task) for task in tasks if str(task.get("status") or "") == "done"][:5]

    decisions = [row for row in pending_decisions if isinstance(row, dict)][:10]
    live_git_required = True
    work_allowed = bool(freshness.get("safe_to_use_autonomy_queue"))
    next_safe_action = _compact_task(next_task) if next_task else None
    if work_allowed and next_safe_action is None:
        next_safe_action = _checkpoint_next_safe_action(checkpoint)

    return {
        "version": 1,
        "system": "DUFYND",
        "purpose": "Cold-start project continuity context for replaceable chat/agent sessions.",
        "domain": logical_domain,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "repository": {
            "full_name": "tncommerce/commerce-agents",
            "target_branch": "scentai-mvp",
            "reported_branch": repo_branch,
            "reported_head": repo_head,
            "live_git_verification_required": live_git_required,
            "main_branch_allowed": False,
        },
        "canonical_sources": [
            "live GitHub branch/HEAD/PR/CI",
            "examples/retail/data/scentai_jarvis_master_status.json",
            "Supabase dufynd_master_status jarvis.repo_state_snapshot",
            "Supabase get_dufynd_autonomy_queue()",
            "Supabase get_dufynd_pending_decisions()",
            "Supabase get_dufynd_jarvis_health()",
            f"Supabase {CHECKPOINT_PREFIX}{logical_domain} when fingerprint-current",
        ],
        "freshness": freshness,
        "work_allowed_after_live_git_check": work_allowed,
        "repo_domain_state": _repo_domain_state(repo_status, logical_domain),
        "checkpoint": checkpoint,
        "active_tasks": active,
        "blocked_or_waiting": blocked,
        "recent_completed": recent,
        "pending_decisions": decisions,
        "next_safe_action": next_safe_action,
        "health_summary": {
            "state": health.get("state"),
            "inbox": health.get("inbox"),
            "usage": health.get("usage"),
            "next_autonomous_action": health.get("next_autonomous_action"),
        },
        "jarvis_contract_version": contract.get("version"),
        "cold_start_rules": [
            "Verify live scentai-mvp HEAD, open PRs and CI before material work.",
            "Refuse to continue from a stale repo/Supabase fingerprint; sync first.",
            "Prefer the domain checkpoint only when both repo fingerprint and Git HEAD match.",
            "Treat chat history as advisory, never as the canonical project state.",
            "Do not expose secrets or credentials in bootstrap or checkpoint payloads.",
        ],
    }


def _walk_forbidden_fields(value: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_path = f"{path}.{key}" if path else str(key)
            if any(
                token == normalized or token in normalized for token in FORBIDDEN_CHECKPOINT_FIELDS
            ):
                hits.append(child_path)
            hits.extend(_walk_forbidden_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_walk_forbidden_fields(child, f"{path}[{index}]"))
    return hits


def build_checkpoint_row(
    *,
    logical_domain: str,
    repo_status: dict[str, Any],
    checkpoint: dict[str, Any],
    repo_head: str,
    verified_at: str | None = None,
) -> dict[str, Any]:
    if logical_domain not in VALID_DOMAINS or logical_domain == "global":
        raise ValueError("Checkpoints require one concrete domain: tech/content/jarvis/business")
    resolved_repo_head = str(repo_head or "").strip()
    if not resolved_repo_head:
        raise ValueError("Checkpoint requires the verified current GitHub HEAD")

    forbidden = _walk_forbidden_fields(checkpoint)
    if forbidden:
        raise ValueError(
            f"Checkpoint contains forbidden secret-like fields: {', '.join(forbidden)}"
        )

    required = (
        "summary",
        "completed",
        "in_progress",
        "blocked",
        "waiting_approval",
        "next_safe_action",
    )
    missing = [key for key in required if key not in checkpoint]
    if missing:
        raise ValueError(f"Checkpoint missing required fields: {', '.join(missing)}")

    timestamp = verified_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    value = dict(checkpoint)
    value.update(
        {
            "domain": logical_domain,
            "source_fingerprint_sha256": repo_status.get("source_fingerprint_sha256"),
            "repo_generated_at": repo_status.get("generated_at"),
            "repo_head": resolved_repo_head,
            "checkpointed_at": timestamp,
        }
    )
    return {
        "key": f"{CHECKPOINT_PREFIX}{logical_domain}",
        "category": "continuity",
        "value": value,
        "priority": 100,
        "last_verified_at": timestamp,
    }


def render_markdown(context: dict[str, Any]) -> str:
    repo = context["repository"]
    freshness = context["freshness"]
    next_action = context.get("next_safe_action") or {}
    checkpoint = context.get("checkpoint") or {}
    lines = [
        f"# DUFYND {str(context['domain']).upper()} CONTINUITY",
        "",
        f"- Target branch: `{repo['target_branch']}`",
        f"- Reported HEAD: `{repo.get('reported_head') or 'verify-live'}`",
        f"- Fingerprint fresh: `{not bool(freshness.get('stale'))}`",
        f"- Live Git verification required: `{repo['live_git_verification_required']}`",
        f"- Jarvis contract: `{context.get('jarvis_contract_version')}`",
        "",
        "## Current checkpoint",
        json.dumps(checkpoint.get("value") or {}, ensure_ascii=False, indent=2),
        "",
        "## Next safe action",
        json.dumps(next_action, ensure_ascii=False, indent=2),
        "",
        "## Active tasks",
        json.dumps(context.get("active_tasks") or [], ensure_ascii=False, indent=2),
        "",
        "## Blocked / waiting",
        json.dumps(context.get("blocked_or_waiting") or [], ensure_ascii=False, indent=2),
        "",
        "## Cold-start rule",
        "Verify live GitHub HEAD/PR/CI first. If the repo/Supabase fingerprint is stale, sync before material work.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def bootstrap_instruction(logical_domain: str) -> str:
    if logical_domain not in VALID_DOMAINS:
        raise ValueError(f"Unsupported continuity domain: {logical_domain}")
    label = logical_domain.upper()
    return "\n".join(
        [
            f"DUFYND {label} fortsetzen.",
            "Repository `tncommerce/commerce-agents`, Zielbranch `scentai-mvp`; `main` nicht anfassen.",
            f"Verifiziere zuerst den Live-HEAD/PR/CI und lade den kanonischen Continuity-Kontext für `{logical_domain}`.",
            "Arbeite nur vom fingerprint-frischen GitHub/Supabase-State weiter; bei Drift zuerst synchronisieren.",
        ]
    )


def _load_live() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    bridge = DufyndJarvisBridge()
    context = bridge.load_context()
    queue = bridge.load_autonomy_queue()
    health = bridge.load_health()
    decisions = bridge.load_pending_decisions()
    return context, queue, health, decisions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DUFYND project continuity and cold-start handoff CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Build a domain-specific cold-start context")
    bootstrap.add_argument("--domain", choices=VALID_DOMAINS, required=True)
    bootstrap.add_argument("--repo-status", type=Path, default=DEFAULT_REPO_STATUS_PATH)
    bootstrap.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    bootstrap.add_argument("--repo-head", default=os.getenv("GITHUB_SHA"))
    bootstrap.add_argument("--repo-branch", default=os.getenv("GITHUB_REF_NAME") or "scentai-mvp")
    bootstrap.add_argument("--live", action="store_true")
    bootstrap.add_argument("--format", choices=("json", "markdown"), default="json")

    checkpoint = sub.add_parser("checkpoint", help="Validate or persist one domain checkpoint")
    checkpoint.add_argument("--domain", choices=VALID_DOMAINS, required=True)
    checkpoint.add_argument("--repo-status", type=Path, default=DEFAULT_REPO_STATUS_PATH)
    checkpoint.add_argument("--checkpoint-json", type=Path, required=True)
    checkpoint.add_argument("--repo-head", default=os.getenv("GITHUB_SHA"))
    checkpoint.add_argument("--write", action="store_true")

    instruction = sub.add_parser(
        "instruction", help="Print the minimal new-chat bootstrap instruction"
    )
    instruction.add_argument("--domain", choices=VALID_DOMAINS, required=True)

    args = parser.parse_args()

    if args.command == "instruction":
        print(bootstrap_instruction(args.domain))
        return 0

    repo_status = load_json(args.repo_status)

    if args.command == "checkpoint":
        payload = load_json(args.checkpoint_json)
        row = build_checkpoint_row(
            logical_domain=args.domain,
            repo_status=repo_status,
            checkpoint=payload,
            repo_head=args.repo_head,
        )
        if args.write:
            DufyndJarvisBridge().upsert_master_status(**row)
        print(
            json.dumps(
                {"dry_run": not args.write, "row": row},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    contract = load_json(args.contract)
    live_context: dict[str, Any] = {}
    queue: dict[str, Any] = {}
    health: dict[str, Any] = {}
    decisions: list[dict[str, Any]] = []
    if args.live:
        live_context, queue, health, decisions = _load_live()

    context = build_bootstrap_context(
        logical_domain=args.domain,
        repo_status=repo_status,
        contract=contract,
        live_context=live_context,
        autonomy_queue=queue,
        health=health,
        pending_decisions=decisions,
        repo_branch=args.repo_branch,
        repo_head=args.repo_head,
    )
    if args.format == "markdown":
        print(render_markdown(context), end="")
    else:
        print(json.dumps(context, ensure_ascii=False, indent=2))
    return 20 if context["freshness"].get("stale") else 0


if __name__ == "__main__":
    raise SystemExit(main())
