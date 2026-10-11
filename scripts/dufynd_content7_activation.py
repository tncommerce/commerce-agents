"""Offline commissioning and bounded existing-Supervisor adapter. No inference.

The plan is inert. Only a separately approved, hash-bound database decision can
activate it; the environment flag merely permits polling already approved work.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.dufynd_seven_content_dispatch import (
    SOURCE_KIND,
    SupabaseSevenWorkerDispatch,
    guard_context,
    load_private_inputs,
)
from scripts.dufynd_seven_content_workers import (
    DEPENDENCIES,
    HANDLERS,
    ROLE_ORDER,
    SUCCESS_STATES,
    WorkerInputError,
    digest,
)

READ_RPC = (
    "read_dufynd_zero_budget_content_queue_v1",
    "read_dufynd_content_performance_learning_v1",
    "read_dufynd_content_reuse_audit_v1",
    "read_dufynd_content_production_packet_v1",
)


def commission_free_inputs(bridge) -> dict:
    """Use existing read-only free components, never silently invent missing copy."""
    evidence = {}
    for name in READ_RPC:
        try:
            value = bridge._rpc(name)
            evidence[name] = {"state": "READ", "sha256": digest(value), "value": value}
        except Exception as error:
            evidence[name] = {"state": "HOLD", "error_type": type(error).__name__}
    return {
        "schema_version": 1,
        "state": "WAITING_EDITORIAL_INPUT",
        "evidence": evidence,
        "required_sections": list(ROLE_ORDER),
        "accepted_producers": ["work_editorial", "human_editorial"],
        "autonomous_creative_generation": False,
        "blocker": "no_certified_zero_cost_creative_provider",
        "provider_requests": 0,
        "cost_eur": 0,
        "publishing_allowed": False,
    }


def build_activation_plan(source: dict, existing: dict, *, now=None) -> dict:
    """Validate newly authored input; return exact bytes to bind Owner decision."""
    now = now or datetime.now(UTC)
    source_sha = guard_context(str(source.get("round_id", "")), source, existing)
    provenance = source.get("provenance", {})
    if (
        source.get("input_version") != 2
        or provenance.get("producer") not in {"work_editorial", "human_editorial"}
        or provenance.get("cost_eur") != 0
        or provenance.get("provider_requests") != 0
        or provenance.get("autonomous_generation") is not False
    ):
        raise WorkerInputError("uncertified_or_unpriced_input_producer")
    try:
        observed = datetime.fromisoformat(existing["observed_at"].replace("Z", "+00:00"))
        fresh = observed.tzinfo and now - timedelta(hours=24) <= observed <= now
    except (KeyError, ValueError, TypeError):
        fresh = False
    if (
        not fresh
        or existing.get("snapshot_verified") is not True
        or not existing.get("frozen_refs")
    ):
        raise WorkerInputError("fresh_freeze_snapshot_required")
    packets = {}
    for role in ROLE_ORDER:
        packets[role] = HANDLERS[role](
            source[role], {r: packets[r] for r in DEPENDENCIES[role]}, existing
        )
        if packets[role]["state"] not in SUCCESS_STATES:
            raise WorkerInputError("invalid_editorial_input:" + role)
    if any(
        "existing_frozen_or_published_creative" in i["review_holds"]
        for i in packets["W2"]["output"]["ideas"]
    ):
        raise WorkerInputError("frozen_or_published_duplicate")
    return {
        "schema_version": 1,
        "context": {"round": source["round_id"], "pilot": source, "existing": existing},
        "source_sha256": source_sha,
        "scope": "content7_validation_handoff_only",
        "spend_cap_eur": 0,
        "max_tasks": 7,
        "max_candidates": 3,
        "provider_execution": False,
        "publication_allowed": False,
    }


def ready_content_tasks(queue: dict) -> list[dict]:
    if os.getenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO") != "1":
        return []
    return [
        row
        for row in queue.get("safe_to_execute", [])
        if isinstance(row, dict)
        and isinstance(row.get("durable_payload"), dict)
        and row["durable_payload"].get("kind") == SOURCE_KIND
        and row["durable_payload"].get("role") in ROLE_ORDER
        and isinstance(row["durable_payload"].get("round_id"), str)
        and row.get("status") == "ready"
    ]


def run_free_content_tick(bridge, *, max_tasks=7, deadline_at=None) -> dict:
    """Finite sequential work on the existing queue; no scheduler or model call."""
    results = []
    if os.getenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO") != "1":
        return {"state": "DISABLED", "results": [], "cost_eur": 0}
    attempted = set()
    for _ in range(max(0, min(max_tasks, 7))):
        if deadline_at is not None and datetime.now(UTC) >= deadline_at:
            break
        bridge.reconcile_control_plane()
        candidates = [
            t
            for t in ready_content_tasks(bridge.load_autonomy_queue())
            if t["task_id"] not in attempted
        ]
        if not candidates:
            break
        task = sorted(
            candidates,
            key=lambda t: (
                t["durable_payload"]["round_id"],
                ROLE_ORDER.index(t["durable_payload"]["role"]),
            ),
        )[0]
        tid = task["task_id"]
        attempted.add(tid)
        rid, role = task["durable_payload"]["round_id"], task["durable_payload"]["role"]
        try:
            allowed = bridge._rpc("dufynd_content7_activation_allowed_v1", {"p_round": rid})
            if allowed is not True:
                results.append({"task_id": tid, "state": "ACTIVATION_HOLD"})
                continue
            source, existing = load_private_inputs(bridge, rid)
            dispatch = SupabaseSevenWorkerDispatch(bridge, source=source, existing=existing)
            result = dispatch.run_role(role)
            results.append({"task_id": tid, **result})
        except Exception as error:
            # An unknown commit outcome is reconciled by reading the immutable
            # receipt on the next tick. Never replace a result or mark it done.
            row = bridge.load_autonomy_task(tid)
            state = "RETRY_AFTER_LEASE_RECOVERY"
            if row and row.get("status") == "done":
                state = "COMMITTED_RESPONSE_LOST"
            elif isinstance(error, WorkerInputError):
                state = "INPUT_HOLD"
                if tid in bridge.worker_tokens:
                    bridge.update_worker(
                        tid,
                        "blocked",
                        evidence="Content input/contract validation failed",
                        reason="verification_pending",
                    )
            results.append({"task_id": tid, "state": state, "error_type": type(error).__name__})
    return {
        "state": "BOUNDED_TICK_COMPLETE",
        "results": results,
        "cost_eur": 0,
        "provider_requests": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a private, inert content7 activation plan"
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--existing", type=Path)
    parser.add_argument(
        "--commission",
        action="store_true",
        help="Read existing free components; no creative generation or database writes",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.commission:
        from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

        args.output.write_text(
            json.dumps(commission_free_inputs(DufyndJarvisBridge()), ensure_ascii=False, indent=2)
        )
        return 0
    if not args.source or not args.existing:
        parser.error("--source and --existing required for an activation plan")
    plan = build_activation_plan(
        json.loads(args.source.read_text()), json.loads(args.existing.read_text())
    )
    args.output.write_text(
        json.dumps({"plan": plan, "plan_sha256": digest(plan)}, ensure_ascii=False, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
