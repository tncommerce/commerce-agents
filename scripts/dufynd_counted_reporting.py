"""Reservation/settlement reporting scoped to one counted budget and session."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal


def report_counted_costs(bridge, budget_id: str, started_at: str, ended_at: str) -> dict:
    if not budget_id or budget_id == "jarvis_activation_pilot_001":
        raise ValueError("counted_budget_required")
    window = bridge.load_budget_window(budget_id)
    if not window or window.get("provider") != "anthropic":
        raise ValueError("counted_window_provider_mismatch")
    rows = bridge.load_budget_reservations(budget_id)
    start, end = datetime.fromisoformat(started_at), datetime.fromisoformat(ended_at)
    calls = []
    actual = Decimal("0")
    reserved = Decimal("0")
    unknown = False
    for row in rows:
        if row.get("budget_id") != budget_id:
            raise ValueError("mixed_budget_ledger")
        stamp = datetime.fromisoformat(row["created_at"])
        if not start <= stamp <= end:
            continue
        dispatched = bool(row.get("dispatched_at"))
        settled = row.get("status") == "settled"
        value = row.get("actual_usd")
        if settled and value is not None:
            amount = Decimal(str(value))
            if not amount.is_finite() or amount < 0:
                raise ValueError("invalid_settlement_cost")
            actual += amount
        if row.get("status") in {"reserved", "dispatched", "provider_cost_unknown"}:
            reserved += Decimal(str(row["reserved_usd"]))
        unknown |= dispatched and (
            row.get("status") in {"provider_cost_unknown", "charged_max"}
            or (settled and value is None)
        )
        calls.append(
            {
                k: row.get(k)
                for k in (
                    "task_id",
                    "reservation_id",
                    "provider_receipt_id",
                    "status",
                    "actual_usd",
                    "reserved_usd",
                    "created_at",
                    "dispatched_at",
                    "settled_at",
                )
            }
        )
    budget = bridge.load_budget_status(budget_id)
    return {
        "budget_id": budget_id,
        "provider": window["provider"],
        "model": window["model"],
        "calls": sum(bool(r["dispatched_at"]) for r in calls),
        "runs": sum(bool(r["dispatched_at"]) for r in calls),
        "actual_spend_usd": str(actual),
        "reserved_unsettled_usd": str(reserved),
        "remaining_budget_usd": str(budget["remaining_usd"]),
        "remaining_runs": budget["remaining_runs"],
        "provider_cost_unknown": unknown or bool(budget.get("provider_cost_unknown")),
        "cost_report_complete": not unknown
        and not budget.get("provider_cost_unknown")
        and reserved == 0
        and Decimal(str(budget.get("reserved_unsettled_usd", 0))) == 0,
        "ledger": calls,
        "source": "counted_reservations_and_settlements",
        "scope": {"started_at": started_at, "ended_at": ended_at},
    }
