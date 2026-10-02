"""Free replay of the 01/02 October budget failure; no credentials or network."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from scripts import dufynd_jarvis_supervisor as supervisor
from scripts.dufynd_bounded_provider import (
    BoundCertificate,
    BoundedProviderAdapter,
    BudgetGate,
    CallEnvelope,
    FakeBoundedProvider,
)

TASKS = (
    "jarvis_launch_attribution_posttech_audit_20261001",
    "jarvis_content_preview_priority_20261001",
    "jarvis_purchase_freshness_watchlist_20261001",
)


class HistoricalReplay:
    """Exhausted historical budget: admission cannot reach dispatch/settlement."""

    def __init__(self):
        self.paid_paused = []
        self.health_passes = 0
        self.free_events = 0
        self.pending = 0
        self.clock = datetime(2026, 10, 2, tzinfo=UTC)
        self.master = {}

    def reserve_model_call(self, **payload):
        maximum = Decimal(payload["max_usd"])
        assert Decimal("2.50") - Decimal("2.5047") - maximum < 0
        return {"allowed": False, "reason": "budget_exhausted"}

    def dispatch_model_call(self, *args):
        raise AssertionError("exhausted historical budget reached provider dispatch")

    def settle_model_call(self, *args):
        raise AssertionError("no call may be settled in this exhausted replay")

    def update_worker(self, task_id, state, **kwargs):
        assert state == "queued" and kwargs["reason"] == "budget_exhausted"
        self.paid_paused.append(task_id)

    def reconcile_control_plane(self):
        self.health_passes += 1
        return {"version": 2, "findings": []}

    def load_health(self):
        return {"inbox": {"pending": self.pending, "processing": 0, "failed": 0}}

    def load_autonomy_queue(self):
        return {
            "safe_to_execute": [
                {
                    "task_id": t,
                    "domain": "research",
                    "status": "ready",
                    "requires_human_approval": False,
                    "approval_action_type": "auto_allowed",
                }
                for t in TASKS
            ]
        }

    def load_budget_status(self, _budget_id):
        return {
            "can_run": False,
            "cap_usd": "2.50",
            "spent_usd": "2.5047",
            "remaining_usd": "0",
            "runs": 19,
            "remaining_runs": 1,
        }

    def load_master_status_entry(self, key):
        return self.master.get(key)

    def upsert_master_status(self, *, key, value, **kwargs):
        self.master[key] = {"value": value}

    async def sleep(self, seconds):
        self.clock += timedelta(seconds=seconds)
        if self.health_passes == 1:
            self.pending = 1

    async def deterministic_event(self, *args, **kwargs):
        self.free_events += 1
        self.pending = 0
        return {"status": "completed", "stop_reason": "no_safe_work", "task_results": []}


def replay():
    bridge = HistoricalReplay()
    provider = FakeBoundedProvider(
        BoundCertificate("offline-replay-fake", Decimal("0.05")), cost_usd=Decimal("0.01")
    )
    adapter = BoundedProviderAdapter(bridge, provider)
    for task in TASKS:
        with suppress(BudgetGate):
            adapter.execute(
                CallEnvelope("offline control-plane replay"),
                budget_id="jarvis_activation_pilot_001",
                task_id=task,
                worker_owner="offline",
                lease_token="offline",
                idempotency_key=task,
            )
    # Only the autonomous-mode approval check is injected for this credential-free
    # harness. Production paid availability remains the real fail-closed value.
    with (
        patch.object(supervisor, "_require_autonomous_mode", lambda: None),
        patch.dict(os.environ, {"DUFYND_JARVIS_BUDGET_ID": "jarvis_activation_pilot_001"}),
    ):
        state = asyncio.run(
            supervisor.supervise_nightshift(
                bridge,
                max_minutes=1,
                max_cycles=20,
                max_idle_cycles=20,
                idle_seconds=10,
                sleep=bridge.sleep,
                now=lambda: bridge.clock,
                run_once=bridge.deterministic_event,
            )
        )
    assert provider.calls == 0 and len(bridge.paid_paused) == 3
    assert bridge.health_passes >= 3 and bridge.free_events == 1
    assert state["stop_reason"] == "time_horizon_reached"
    return {
        "mode": "free_offline_dry_run",
        "historical_cap_usd": "2.50",
        "historical_spent_usd": "2.5047",
        "new_cost_usd": "0",
        "provider_calls": provider.calls,
        "paid_tasks_queued": bridge.paid_paused,
        "free_health_passes": bridge.health_passes,
        "free_deterministic_events": bridge.free_events,
        "false_human_gates": 0,
        "supervisor_stop_reason": state["stop_reason"],
        "counterfactual": {
            "spent_before_call_usd": "2.334318599999999955",
            "observed_call_cost_lower_bound_usd": "0.1703668",
            "remaining_before_call_usd": "0.165681400000000045",
            "best_possible_admission_margin_usd": "-0.004685399999999955",
            "source_run_id": "b01a0ed3-3a25-4f0d-af21-a05389f29ec0",
            "bound_note": "Observed actual cost is only a lower bound; any certified maximum must be at least this high. Unknown real SDK bound remains fail closed.",
            "admission": "denied",
        },
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
