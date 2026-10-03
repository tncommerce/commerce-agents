"""Explicit manual start / free preflight. Never creates a budget or owner approval."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.dufynd_anthropic_counted import MAX_REQUEST_USD, pricing, resolve_budget
from scripts.dufynd_bounded_provider import BudgetGate
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_jarvis_nightshift import run_nightshift, write_morning_report


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
    started_at = datetime.now(UTC)
    stop_reason = status
    try:
        contract = pricing()
        budget_id, resolved = resolve_budget(bridge)
        queue = bridge.load_autonomy_queue()
        os.environ["DUFYND_JARVIS_BUDGET_ID"] = budget_id
        preflight = {
            "provider": contract["provider"],
            "model": contract["model"],
            "budget": resolved["budget"],
            "max_request_usd": str(MAX_REQUEST_USD),
            "queue_ready_count": len(queue.get("safe_to_execute", [])),
            "paid_requests": 0,
        }
        if args.preflight:
            print(json.dumps(preflight))
            status = "preflight_only"
            return 0
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
            "budget_id": os.getenv("DUFYND_JARVIS_BUDGET_ID"),
            "worker_session_started": session_started,
            "started_at": started_at.isoformat(),
            "ended_at": datetime.now(UTC).isoformat(),
            "stop_reason": stop_reason,
            "head": os.getenv("GITHUB_SHA"),
        }
        (output / "counted-terminal.json").write_text(json.dumps(terminal) + "\n")
        try:
            write_morning_report(bridge, output_dir=output, qa_status=status, pr_url=None)
        except Exception as error:
            terminal["morning_report_error_type"] = type(error).__name__
            (output / "counted-terminal.json").write_text(json.dumps(terminal) + "\n")
        with suppress(Exception):
            bridge.upsert_master_status(
                key="jarvis.counted_nightshift.terminal", category="jarvis", value=terminal
            )


if __name__ == "__main__":
    raise SystemExit(main())
