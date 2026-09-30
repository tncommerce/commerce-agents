from __future__ import annotations

import argparse
import json
import os
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

DEFAULT_BUDGET_ID = "jarvis_activation_pilot_001"
FLOAT_TOLERANCE = 0.000001
SPEND_RECONCILIATION_TOLERANCE_USD = 0.0001


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _matching_decisions(run: dict[str, Any], budget_id: str) -> list[dict[str, Any]]:
    return [
        decision
        for decision in (run.get("decisions") or [])
        if isinstance(decision, dict) and decision.get("budget_id") == budget_id
    ]


def _approved_per_run_cap(
    bridge: DufyndJarvisBridge,
    budget_window: dict[str, Any],
) -> tuple[float | None, dict[str, Any] | None]:
    decision_id = budget_window.get("approved_decision_id")
    if not decision_id:
        return None, None

    decision_row = bridge.load_human_decision(str(decision_id))
    if not decision_row:
        return None, None

    decision = decision_row.get("decision") or {}
    if not isinstance(decision, dict):
        return None, decision_row

    value = decision.get("per_run_cap_usd")
    if value is None:
        return None, decision_row
    try:
        return float(value), decision_row
    except (TypeError, ValueError):
        return None, decision_row


def build_budget_ledger(
    bridge: DufyndJarvisBridge,
    *,
    budget_id: str = DEFAULT_BUDGET_ID,
) -> dict[str, Any]:
    budget_status = bridge.load_budget_status(budget_id)
    budget_window = bridge.load_budget_window(budget_id)
    if not budget_window:
        raise RuntimeError(f"Jarvis budget window not found: {budget_id}")

    approved_per_run_cap, approval = _approved_per_run_cap(bridge, budget_window)
    since = str(
        budget_window.get("started_at")
        or budget_window.get("created_at")
        or "1970-01-01T00:00:00+00:00"
    )
    runs = bridge.load_agent_runs_since(since)

    ledger_rows: list[dict[str, Any]] = []
    total_spent = 0.0
    for run in runs:
        decisions = _matching_decisions(run, budget_id)
        if not decisions:
            continue

        run_cost = round(sum(_float(item.get("cost_usd")) for item in decisions), 9)
        total_spent += run_cost
        ledger_rows.append(
            {
                "id": run.get("id"),
                "agent_name": run.get("agent_name"),
                "run_type": run.get("run_type"),
                "created_at": run.get("created_at"),
                "cost_usd": run_cost,
                "decision_count": len(decisions),
            }
        )

    total_spent = round(total_spent, 6)
    billed_runs = len(ledger_rows)

    by_run_type: dict[str, dict[str, Any]] = {}
    for row in ledger_rows:
        run_type = str(row.get("run_type") or "unknown")
        summary = by_run_type.setdefault(
            run_type,
            {
                "runs": 0,
                "spent_usd": 0.0,
                "max_single_run_usd": 0.0,
            },
        )
        summary["runs"] += 1
        summary["spent_usd"] += row["cost_usd"]
        summary["max_single_run_usd"] = max(
            summary["max_single_run_usd"],
            row["cost_usd"],
        )

    for summary in by_run_type.values():
        summary["spent_usd"] = round(summary["spent_usd"], 6)
        summary["max_single_run_usd"] = round(summary["max_single_run_usd"], 6)
        summary["average_run_usd"] = round(
            summary["spent_usd"] / summary["runs"],
            6,
        )
    by_run_type = dict(sorted(by_run_type.items()))
    status_spent = round(_float(budget_status.get("spent_usd")), 6)
    status_runs = int(budget_status.get("runs") or 0)

    issues: list[dict[str, Any]] = []
    approval_decision = (approval or {}).get("decision") or {}
    if not isinstance(approval_decision, dict):
        approval_decision = {}
    approval_valid = bool(
        approval
        and str(approval.get("status") or "") == "approved"
        and approval_decision.get("approved") is True
    )
    approved_total_cap = _float(approval_decision.get("cap_usd"), default=-1.0)
    approved_max_runs = int(approval_decision.get("max_runs") or 0)

    if approval is None:
        issues.append(
            {
                "code": "budget_approval_missing",
                "severity": "error",
                "message": "Budget window has no resolvable human approval record.",
            }
        )
    elif not approval_valid:
        issues.append(
            {
                "code": "budget_approval_not_approved",
                "severity": "error",
                "message": "Referenced human decision is not an explicit approved budget decision.",
            }
        )
    elif approved_per_run_cap is None:
        issues.append(
            {
                "code": "per_run_approval_missing",
                "severity": "error",
                "message": "Human approval does not contain a valid per_run_cap_usd.",
            }
        )

    window_cap = _float(budget_window.get("cap_usd"), default=-1.0)
    window_max_runs = int(budget_window.get("max_runs") or 0)
    if approval_valid and (
        window_cap > approved_total_cap + FLOAT_TOLERANCE or window_max_runs > approved_max_runs
    ):
        issues.append(
            {
                "code": "budget_window_exceeds_human_approval",
                "severity": "error",
                "message": "Configured budget window exceeds its referenced human approval.",
                "window_cap_usd": window_cap,
                "approved_cap_usd": approved_total_cap,
                "window_max_runs": window_max_runs,
                "approved_max_runs": approved_max_runs,
            }
        )

    over_cap_rows: list[dict[str, Any]] = []
    if approved_per_run_cap is not None:
        over_cap_rows = [
            row for row in ledger_rows if row["cost_usd"] > approved_per_run_cap + FLOAT_TOLERANCE
        ]
        if over_cap_rows:
            issues.append(
                {
                    "code": "historical_per_run_cap_exceeded",
                    "severity": "warning",
                    "message": (
                        f"{len(over_cap_rows)} audited Jarvis run(s) exceeded the approved "
                        f"per-run cap of USD {approved_per_run_cap:.6f}."
                    ),
                    "run_ids": [row["id"] for row in over_cap_rows],
                }
            )

    if abs(total_spent - status_spent) > SPEND_RECONCILIATION_TOLERANCE_USD:
        issues.append(
            {
                "code": "budget_spend_reconciliation_mismatch",
                "severity": "error",
                "message": (
                    "Audited agent-run spend differs from the authoritative budget status."
                ),
                "ledger_spent_usd": total_spent,
                "budget_status_spent_usd": status_spent,
            }
        )

    if billed_runs != status_runs:
        issues.append(
            {
                "code": "budget_run_count_reconciliation_mismatch",
                "severity": "error",
                "message": "Audited billed-run count differs from the budget status.",
                "ledger_runs": billed_runs,
                "budget_status_runs": status_runs,
            }
        )

    max_run_cost = max((row["cost_usd"] for row in ledger_rows), default=0.0)
    cap_usd = _float(budget_status.get("cap_usd"))
    remaining_usd = _float(budget_status.get("remaining_usd"))
    max_runs = int(budget_status.get("max_runs") or 0)
    remaining_runs = int(budget_status.get("remaining_runs") or 0)
    run_cap_ceiling = (
        remaining_runs * approved_per_run_cap
        if approved_per_run_cap is not None
        else None
    )
    max_future_spend = (
        min(remaining_usd, run_cap_ceiling)
        if run_cap_ceiling is not None
        else remaining_usd
    )

    return {
        "status": "attention" if issues else "ok",
        "budget_id": budget_id,
        "budget_status": budget_status,
        "budget_window": {
            "status": budget_window.get("status"),
            "model": budget_window.get("model"),
            "cap_usd": budget_window.get("cap_usd"),
            "max_runs": budget_window.get("max_runs"),
            "approved_decision_id": budget_window.get("approved_decision_id"),
            "started_at": budget_window.get("started_at"),
        },
        "approval": {
            "decision_id": (approval or {}).get("decision_id"),
            "status": (approval or {}).get("status"),
            "valid": approval_valid,
            "cap_usd": approved_total_cap if approved_total_cap >= 0 else None,
            "max_runs": approved_max_runs or None,
            "per_run_cap_usd": approved_per_run_cap,
        },
        "ledger": {
            "runs": billed_runs,
            "spent_usd": total_spent,
            "max_single_run_usd": round(max_run_cost, 6),
            "average_run_usd": round(total_spent / billed_runs, 6) if billed_runs else 0.0,
            "over_cap_runs": over_cap_rows,
            "by_run_type": by_run_type,
            "rows": ledger_rows,
        },
        "reconciliation": {
            "run_count_matches": billed_runs == status_runs,
            "spend_matches": abs(total_spent - status_spent) <= SPEND_RECONCILIATION_TOLERANCE_USD,
        },
        "remaining": {
            "usd": round(remaining_usd, 6),
            "runs": remaining_runs,
            "budget_cap_usd": round(cap_usd, 6),
            "max_runs": max_runs,
            "run_cap_ceiling_usd": (
                round(run_cap_ceiling, 6) if run_cap_ceiling is not None else None
            ),
            "max_future_spend_usd": round(max_future_spend, 6),
        },
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only audited DUFYND Jarvis model-budget ledger."
    )
    parser.add_argument(
        "--budget-id",
        default=os.getenv("DUFYND_JARVIS_BUDGET_ID", DEFAULT_BUDGET_ID),
    )
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--fail-on-attention", action="store_true")
    args = parser.parse_args()

    report = build_budget_ledger(
        DufyndJarvisBridge(),
        budget_id=args.budget_id,
    )
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=args.pretty,
        )
    )
    return 2 if args.fail_on_attention and report["status"] == "attention" else 0


if __name__ == "__main__":
    raise SystemExit(main())
