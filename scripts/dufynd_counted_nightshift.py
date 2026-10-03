"""Explicit manual start / free preflight. Never creates a budget or owner approval."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.dufynd_anthropic_counted import (
    CONTRACT_ID,
    MAX_OUTPUT,
    MAX_REQUEST_USD,
    canonical,
    pricing,
    resolve_budget,
)
from scripts.dufynd_bounded_provider import BudgetGate
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_jarvis_nightshift import run_nightshift, write_morning_report


def build_preflight_report(bridge, *, started_at: datetime) -> dict:
    """Read-only current-run evidence. Never enters a worker/provider/reservation path."""
    contract = pricing()
    digest = hashlib.sha256(canonical(contract)).hexdigest()
    state = bridge._rpc("get_dufynd_counted_preflight_state", {})
    required = {
        "resolve_dufynd_nightshift_budget",
        "reserve_dufynd_model_call",
        "dispatch_dufynd_counted_call",
        "settle_dufynd_counted_call",
        "reconcile_dufynd_budget_reservations",
    }
    if not required <= set(state["functions"]):
        raise BudgetGate("preflight_functions_missing")
    live = state["provider_contract"]
    if (
        not live
        or live.get("enabled") is not True
        or live.get("dry_run") is not False
        or live["evidence"].get("pricing_digest") != digest
        or live["model"] != contract["model"]
        or datetime.fromisoformat(live["expires_at"]) <= datetime.now(UTC)
    ):
        raise BudgetGate("provider_contract_unverified_or_expired")
    resolved = bridge._rpc(
        "resolve_dufynd_nightshift_budget",
        {
            "p_contract_id": CONTRACT_ID,
            "p_pricing_digest": digest,
        },
    )
    if not isinstance(resolved, dict) or not isinstance(resolved.get("allowed"), bool):
        raise BudgetGate("malformed_budget_response")
    reason = resolved.get("reason")
    if not resolved["allowed"] and reason != "no_usable_approved_budget":
        raise BudgetGate(str(reason or "malformed_budget_response"))
    queue = bridge.load_autonomy_queue()
    tasks = queue.get("safe_to_execute") or []
    if any(not isinstance(task, dict) for task in tasks):
        raise ValueError("Malformed queue candidates")
    return {
        "run_type": "nightshift_bounded_preflight",
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "head_sha": os.getenv("GITHUB_SHA"),
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(UTC).isoformat(),
        "supabase_reachable": True,
        "provider_contract": live,
        "pricing": contract,
        "cost_guard_loaded": True,
        "max_request_usd": str(MAX_REQUEST_USD),
        "max_output_tokens": MAX_OUTPUT,
        "functions": state["functions"],
        "budget_gate": {
            "status": "AVAILABLE_REQUIRES_OWNER_START"
            if resolved["allowed"]
            else "BLOCKED_AS_EXPECTED",
            "reason": reason,
            "resolver": resolved,
        },
        "current_budget": resolved.get("budget") if resolved["allowed"] else None,
        "budget_id": (resolved.get("budget") or {}).get("budget_id")
        if resolved["allowed"]
        else None,
        "queue": {
            "counts": {k: len(v) for k, v in queue.items() if isinstance(v, list)},
            "safe_candidates": [
                {k: t.get(k) for k in ("task_id", "title", "domain", "resource_scope")}
                for t in tasks
            ],
        },
        "leases": state["leases"],
        "observer_health": state["observer_health"],
        "historical_context": {"pilot_budget": state["historical_pilot_budget"]},
        "worker_session_started": False,
        "paid_requests": 0,
        "reservations_created": 0,
        "new_spend_usd": 0,
        "current_preflight_cost_usd": 0,
        "reservation_snapshot": state["reservation_snapshot"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--max-tasks", type=int, default=3)
    args = parser.parse_args()
    bridge = DufyndJarvisBridge()
    os.environ["DUFYND_JARVIS_PROVIDER_PATH"] = "anthropic-counted-v1"
    output = Path("jarvis-nightshift-report")
    output.mkdir(exist_ok=True)
    status = "provider_or_budget_gate"
    session_started = False
    session = None
    budget_id = None
    preflight = None
    started_at = datetime.now(UTC)
    stop_reason = status
    try:
        if args.preflight:
            preflight = build_preflight_report(bridge, started_at=started_at)
            status = "preflight_only"
            stop_reason = preflight["budget_gate"]["reason"] or status
            print(json.dumps(preflight))
            return 0
        pricing()
        budget_id, _resolved = resolve_budget(bridge)
        os.environ["DUFYND_JARVIS_BUDGET_ID"] = budget_id
        if (
            args.approval_token != "GO-JARVIS-NIGHTSHIFT"
            or os.getenv("GITHUB_REF") != "refs/heads/scentai-mvp"
            or os.getenv("DUFYND_JARVIS_ACTIVE") != "1"
            or os.getenv("DUFYND_JARVIS_AUTONOMOUS") != "1"
        ):
            raise BudgetGate("explicit_start_or_integration_ref_missing")
        session_started = True
        session = asyncio.run(
            run_nightshift(
                bridge,
                max_tasks=max(1, min(args.max_tasks, 20)),
                max_events=0,
                max_retries=0,
                worker_timeout_seconds=120,
                deadline_at=started_at + timedelta(minutes=60),
            )
        )
        status = session["status"]
        stop_reason = session.get("stop_reason", status)
        return 0 if status == "completed" else 2
    except Exception as error:
        status = type(error).__name__
        stop_reason = str(error) if isinstance(error, BudgetGate) else status
        print(
            json.dumps(
                {
                    "ready": False,
                    "stop_reason": str(error) if isinstance(error, BudgetGate) else status,
                }
            )
        )
        return 2
    finally:
        # Standalone fallback survives a DB/report failure without exposing exception/credentials.
        terminal = {
            "status": status,
            "preflight_only": args.preflight,
            "budget_id": budget_id,
            "github_run_id": os.getenv("GITHUB_RUN_ID"),
            "paid_requests": 0 if args.preflight or not session_started else None,
            "reservations_created": 0 if args.preflight or not session_started else None,
            "new_spend_usd": 0 if args.preflight or not session_started else None,
            "worker_session_started": session_started,
            "started_at": started_at.isoformat(),
            "ended_at": datetime.now(UTC).isoformat(),
            "stop_reason": stop_reason,
            "head": os.getenv("GITHUB_SHA"),
        }
        (output / "counted-terminal.json").write_text(json.dumps(terminal) + "\n")
        if args.preflight:
            report = preflight or {
                **terminal,
                "run_type": "nightshift_bounded_preflight",
                "head_sha": os.getenv("GITHUB_SHA"),
                "current_budget": None,
                "technical_error": stop_reason,
            }
            (output / "preflight-report.json").write_text(json.dumps(report, indent=2) + "\n")
            (output / "preflight-report.md").write_text(
                "# DUFYND CURRENT PREFLIGHT\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n"
            )
        elif session is not None:
            try:
                write_morning_report(
                    bridge,
                    output_dir=output,
                    qa_status=status,
                    pr_url=None,
                    expected_session=session,
                )
            except Exception as error:
                terminal["morning_report_error_type"] = type(error).__name__
                (output / "counted-terminal.json").write_text(json.dumps(terminal) + "\n")
        with suppress(Exception):
            bridge.upsert_master_status(
                key="jarvis.counted_nightshift.terminal", category="jarvis", value=terminal
            )


if __name__ == "__main__":
    raise SystemExit(main())
