from __future__ import annotations

import argparse
import json
import os
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.report_dufynd_jarvis_budget_ledger import (
    DEFAULT_BUDGET_ID,
    build_budget_ledger,
)
from scripts.report_dufynd_jarvis_pilot_efficiency import (
    build_pilot_efficiency_report,
)


def _attention_codes(payload: dict[str, Any]) -> list[str]:
    return [
        str(item.get("code"))
        for item in (payload.get("issues") or payload.get("signals") or [])
        if isinstance(item, dict)
        and item.get("code")
        and str(item.get("severity") or "attention") != "info"
    ]


def build_pilot_retrospective(
    bridge: DufyndJarvisBridge,
    *,
    budget_id: str = DEFAULT_BUDGET_ID,
) -> dict[str, Any]:
    ledger = build_budget_ledger(bridge, budget_id=budget_id)
    efficiency = build_pilot_efficiency_report(bridge, budget_id=budget_id)

    ledger_codes = _attention_codes(ledger)
    efficiency_codes = _attention_codes(efficiency)
    attention_codes = sorted(set(ledger_codes + efficiency_codes))

    ledger_totals = ledger.get("ledger") or {}
    efficiency_totals = efficiency.get("totals") or {}
    source_consistent = bool(
        int(ledger_totals.get("runs") or 0) == int(efficiency_totals.get("runs") or 0)
        and abs(
            float(ledger_totals.get("spent_usd") or 0.0)
            - float(efficiency_totals.get("spent_usd") or 0.0)
        )
        <= 0.000001
    )
    if not source_consistent:
        attention_codes = sorted(set(attention_codes + ["retrospective_source_drift"]))

    ledger_reconciliation = ledger.get("reconciliation") or {}
    approval = ledger.get("approval") or {}
    remaining = ledger.get("remaining") or {}
    totals = efficiency.get("totals") or {}

    controls_ok = bool(
        approval.get("valid")
        and ledger_reconciliation.get("run_count_matches")
        and ledger_reconciliation.get("spend_matches")
    )
    historical_attention = bool(
        ledger.get("ledger", {}).get("over_cap_runs") or totals.get("failed_runs")
    )

    controls_ok = controls_ok and source_consistent
    checkpoint = "attention" if attention_codes or not controls_ok else "within_controls"

    return {
        "checkpoint": checkpoint,
        "budget_id": budget_id,
        "controls": {
            "human_approval_valid": bool(approval.get("valid")),
            "run_count_reconciled": bool(ledger_reconciliation.get("run_count_matches")),
            "spend_reconciled": bool(ledger_reconciliation.get("spend_matches")),
            "source_consistent": source_consistent,
            "controls_ok": controls_ok,
        },
        "pilot": {
            "runs": int(ledger.get("ledger", {}).get("runs") or 0),
            "spent_usd": float(ledger.get("ledger", {}).get("spent_usd") or 0.0),
            "average_run_usd": float(ledger.get("ledger", {}).get("average_run_usd") or 0.0),
            "failed_runs": int(totals.get("failed_runs") or 0),
            "failed_spend_usd": float(totals.get("failed_spend_usd") or 0.0),
            "failed_model_turns": int(totals.get("failed_model_turns") or 0),
            "failed_model_turn_runs": int(totals.get("failed_model_turn_runs") or 0),
            "historical_attention": historical_attention,
        },
        "remaining": {
            "runs": int(remaining.get("runs") or 0),
            "usd": float(remaining.get("usd") or 0.0),
            "max_future_spend_usd": float(remaining.get("max_future_spend_usd") or 0.0),
        },
        "cost_centers": efficiency.get("repeated_cost_centers") or [],
        "runtimes": efficiency.get("runtimes") or [],
        "near_cap": efficiency.get("near_cap") or {},
        "attention_codes": attention_codes,
        "source_status": {
            "budget_ledger": ledger.get("status"),
            "pilot_efficiency": efficiency.get("status"),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    controls = report["controls"]
    pilot = report["pilot"]
    remaining = report["remaining"]
    near_cap = report.get("near_cap") or {}
    cost_centers = report.get("cost_centers") or []
    runtimes = report.get("runtimes") or []
    attention_codes = report.get("attention_codes") or []

    lines = [
        "# DUFYND Jarvis Pilot Retrospective",
        "",
        f"Checkpoint: **{report['checkpoint']}**",
        "",
        "## Controls",
        f"- Human approval valid: {'yes' if controls['human_approval_valid'] else 'no'}",
        f"- Run count reconciled: {'yes' if controls['run_count_reconciled'] else 'no'}",
        f"- Spend reconciled: {'yes' if controls['spend_reconciled'] else 'no'}",
        f"- Report sources consistent: {'yes' if controls['source_consistent'] else 'no'}",
        "",
        "## Pilot",
        f"- Runs: {pilot['runs']}",
        f"- Spend: USD {pilot['spent_usd']:.6f}",
        f"- Average run: USD {pilot['average_run_usd']:.6f}",
        f"- Failed runs: {pilot['failed_runs']}",
        f"- Failed-run spend: USD {pilot['failed_spend_usd']:.6f}",
        f"- Failed model turns: {pilot['failed_model_turns']}",
        f"- Runs with failed model turns: {pilot['failed_model_turn_runs']}",
        "",
        "## Runtime cost attribution",
    ]

    if runtimes:
        for item in runtimes:
            lines.append(
                "- "
                f"{item.get('runtime')}: {item.get('runs')} runs, "
                f"USD {float(item.get('spent_usd') or 0):.6f}, "
                f"{float(item.get('spend_share') or 0) * 100:.2f}% of audited spend, "
                f"{item.get('failed_model_turns')} failed model turns"
            )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Remaining approved headroom",
            f"- Runs: {remaining['runs']}",
            f"- Budget: USD {remaining['usd']:.6f}",
            f"- Maximum additional spend under current controls: USD {remaining['max_future_spend_usd']:.6f}",
            "",
            "## Near-cap activity",
            f"- Threshold: {near_cap.get('threshold_usd')}",
            f"- Runs: {len(near_cap.get('runs') or [])}",
            "",
            "## Repeated cost centers",
        ]
    )

    if cost_centers:
        for item in cost_centers:
            lines.append(
                "- "
                f"{item.get('family')}: {item.get('runs')} runs, "
                f"USD {float(item.get('spent_usd') or 0):.6f}, "
                f"{float(item.get('spend_share') or 0) * 100:.2f}% of audited spend"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Attention codes"])
    if attention_codes:
        lines.extend(f"- {code}" for code in attention_codes)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "_Read-only retrospective. No budget, model, queue, publishing or production state is changed._",
        ]
    )
    return "\n".join(lines) + "\n"

def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only DUFYND Jarvis pilot retrospective.")
    parser.add_argument(
        "--budget-id",
        default=os.getenv("DUFYND_JARVIS_BUDGET_ID", DEFAULT_BUDGET_ID),
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--fail-on-attention", action="store_true")
    args = parser.parse_args()

    report = build_pilot_retrospective(
        DufyndJarvisBridge(),
        budget_id=args.budget_id,
    )
    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                sort_keys=args.pretty,
            )
        )

    return 2 if args.fail_on_attention and report["checkpoint"] == "attention" else 0


if __name__ == "__main__":
    raise SystemExit(main())
