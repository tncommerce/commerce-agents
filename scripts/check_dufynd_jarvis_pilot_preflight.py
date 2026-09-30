from __future__ import annotations

import argparse
import json
import os
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.report_dufynd_jarvis_budget_ledger import DEFAULT_BUDGET_ID
from scripts.report_dufynd_jarvis_pilot_retrospective import build_pilot_retrospective

HARD_CONTROL_CODES = {
    "budget_approval_missing",
    "budget_approval_not_approved",
    "per_run_approval_missing",
    "budget_window_exceeds_human_approval",
    "budget_spend_reconciliation_mismatch",
    "budget_run_count_reconciliation_mismatch",
    "retrospective_source_drift",
}


def evaluate_pilot_preflight(retrospective: dict[str, Any]) -> dict[str, Any]:
    controls = retrospective.get("controls") or {}
    remaining = retrospective.get("remaining") or {}
    attention_codes = [
        str(code) for code in (retrospective.get("attention_codes") or []) if code
    ]

    blockers: list[str] = []
    if not controls.get("human_approval_valid"):
        blockers.append("human_approval_invalid")
    if not controls.get("run_count_reconciled"):
        blockers.append("run_count_not_reconciled")
    if not controls.get("spend_reconciled"):
        blockers.append("spend_not_reconciled")
    if not controls.get("source_consistent"):
        blockers.append("report_source_drift")

    remaining_runs = int(remaining.get("runs") or 0)
    remaining_usd = float(remaining.get("usd") or 0.0)
    max_future_spend = float(remaining.get("max_future_spend_usd") or 0.0)

    if remaining_runs <= 0:
        blockers.append("no_remaining_approved_runs")
    if remaining_usd <= 0 or max_future_spend <= 0:
        blockers.append("no_remaining_approved_budget")

    hard_attention = sorted(set(attention_codes).intersection(HARD_CONTROL_CODES))
    blockers.extend(code for code in hard_attention if code not in blockers)

    warnings = sorted(
        code
        for code in set(attention_codes)
        if code not in HARD_CONTROL_CODES
    )

    blockers = sorted(set(blockers))
    return {
        "ready": not blockers,
        "budget_id": retrospective.get("budget_id"),
        "blockers": blockers,
        "warnings": warnings,
        "remaining": {
            "runs": remaining_runs,
            "usd": remaining_usd,
            "max_future_spend_usd": max_future_spend,
        },
        "controls": {
            "human_approval_valid": bool(controls.get("human_approval_valid")),
            "run_count_reconciled": bool(controls.get("run_count_reconciled")),
            "spend_reconciled": bool(controls.get("spend_reconciled")),
            "source_consistent": bool(controls.get("source_consistent")),
        },
    }


def build_pilot_preflight(
    bridge: DufyndJarvisBridge,
    *,
    budget_id: str = DEFAULT_BUDGET_ID,
) -> dict[str, Any]:
    retrospective = build_pilot_retrospective(
        bridge,
        budget_id=budget_id,
    )
    return evaluate_pilot_preflight(retrospective)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only DUFYND Jarvis paid-pilot control preflight."
    )
    parser.add_argument(
        "--budget-id",
        default=os.getenv("DUFYND_JARVIS_BUDGET_ID", DEFAULT_BUDGET_ID),
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = build_pilot_preflight(
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
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
