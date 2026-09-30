from __future__ import annotations

import argparse
import json
import math
import os
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.report_dufynd_jarvis_budget_ledger import (
    DEFAULT_BUDGET_ID,
    build_budget_ledger,
)

NEAR_CAP_RATIO = 0.8
REPEATED_FAMILY_MIN_RUNS = 3
REPEATED_FAMILY_MIN_SPEND_SHARE = 0.15


def _run_family(run_type: object) -> str:
    value = str(run_type or "unknown")
    if value.startswith("safe_task_failed:"):
        return "safe_task_failed"
    if value.startswith("safe_task_soft_error:"):
        return "safe_task_soft_error"
    if value.startswith("safe_task:"):
        return "safe_task"
    if value.startswith("branch_task_failed:"):
        return "branch_task_failed"
    if value.startswith("branch_task:"):
        return "branch_task"
    return value


def build_pilot_efficiency_report(
    bridge: DufyndJarvisBridge,
    *,
    budget_id: str = DEFAULT_BUDGET_ID,
) -> dict[str, Any]:
    ledger = build_budget_ledger(bridge, budget_id=budget_id)
    rows = list(ledger["ledger"]["rows"])
    total_spent = float(ledger["ledger"]["spent_usd"] or 0.0)
    approved_per_run_cap = ledger["approval"].get("per_run_cap_usd")
    near_cap_threshold = (
        float(approved_per_run_cap) * NEAR_CAP_RATIO
        if approved_per_run_cap is not None
        else None
    )

    by_family: dict[str, dict[str, Any]] = {}
    failed_rows: list[dict[str, Any]] = []
    near_cap_rows: list[dict[str, Any]] = []

    for row in rows:
        cost = float(row.get("cost_usd") or 0.0)
        run_type = str(row.get("run_type") or "unknown")
        family = _run_family(run_type)

        summary = by_family.setdefault(
            family,
            {
                "runs": 0,
                "spent_usd": 0.0,
                "max_run_usd": 0.0,
            },
        )
        summary["runs"] += 1
        summary["spent_usd"] += cost
        summary["max_run_usd"] = max(summary["max_run_usd"], cost)

        if "failed" in run_type or "soft_error" in run_type or "timeout" in run_type:
            failed_rows.append(row)
        if near_cap_threshold is not None and cost >= near_cap_threshold:
            near_cap_rows.append(row)

    family_rows: list[dict[str, Any]] = []
    for family, summary in by_family.items():
        spent = round(float(summary["spent_usd"]), 6)
        runs = int(summary["runs"])
        share = spent / total_spent if total_spent else 0.0
        family_rows.append(
            {
                "family": family,
                "runs": runs,
                "spent_usd": spent,
                "spend_share": round(share, 6),
                "average_run_usd": round(spent / runs, 6) if runs else 0.0,
                "max_run_usd": round(float(summary["max_run_usd"]), 6),
            }
        )
    family_rows.sort(key=lambda row: (-row["spent_usd"], row["family"]))

    repeated_cost_centers = [
        row
        for row in family_rows
        if row["runs"] >= REPEATED_FAMILY_MIN_RUNS
        and row["spend_share"] >= REPEATED_FAMILY_MIN_SPEND_SHARE
    ]

    failed_spend = round(
        sum(float(row.get("cost_usd") or 0.0) for row in failed_rows),
        6,
    )
    failed_share = failed_spend / total_spent if total_spent else 0.0

    remaining_usd = float(ledger["remaining"].get("usd") or 0.0)
    average_run_usd = float(ledger["ledger"].get("average_run_usd") or 0.0)
    observed_average_run_capacity = (
        min(
            int(ledger["remaining"].get("runs") or 0),
            math.floor(remaining_usd / average_run_usd),
        )
        if average_run_usd > 0
        else 0
    )

    signals: list[dict[str, Any]] = []
    if failed_rows:
        signals.append(
            {
                "code": "failed_run_spend_present",
                "severity": "attention",
                "run_count": len(failed_rows),
                "spent_usd": failed_spend,
                "spend_share": round(failed_share, 6),
            }
        )
    if near_cap_rows:
        signals.append(
            {
                "code": "near_per_run_cap_activity",
                "severity": "attention",
                "threshold_usd": round(near_cap_threshold or 0.0, 6),
                "run_count": len(near_cap_rows),
                "run_ids": [row.get("id") for row in near_cap_rows],
            }
        )
    if repeated_cost_centers:
        signals.append(
            {
                "code": "repeated_cost_centers",
                "severity": "info",
                "families": [row["family"] for row in repeated_cost_centers],
            }
        )

    return {
        "status": "attention" if any(s["severity"] == "attention" for s in signals) else "ok",
        "budget_id": budget_id,
        "ledger_status": ledger["status"],
        "totals": {
            "runs": int(ledger["ledger"]["runs"]),
            "spent_usd": total_spent,
            "average_run_usd": round(average_run_usd, 6),
            "failed_runs": len(failed_rows),
            "failed_spend_usd": failed_spend,
            "failed_spend_share": round(failed_share, 6),
        },
        "families": family_rows,
        "repeated_cost_centers": repeated_cost_centers,
        "near_cap": {
            "ratio": NEAR_CAP_RATIO,
            "threshold_usd": (
                round(near_cap_threshold, 6)
                if near_cap_threshold is not None
                else None
            ),
            "runs": [
                {
                    "id": row.get("id"),
                    "run_type": row.get("run_type"),
                    "cost_usd": row.get("cost_usd"),
                }
                for row in near_cap_rows
            ],
        },
        "remaining": {
            "usd": ledger["remaining"].get("usd"),
            "runs": ledger["remaining"].get("runs"),
            "max_future_spend_usd": ledger["remaining"].get("max_future_spend_usd"),
            "observed_average_run_capacity": observed_average_run_capacity,
            "capacity_note": (
                "Observed-average capacity is descriptive only; future model cost can vary."
            ),
        },
        "signals": signals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only DUFYND Jarvis pilot cost-efficiency report."
    )
    parser.add_argument(
        "--budget-id",
        default=os.getenv("DUFYND_JARVIS_BUDGET_ID", DEFAULT_BUDGET_ID),
    )
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--fail-on-attention", action="store_true")
    args = parser.parse_args()

    report = build_pilot_efficiency_report(
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
