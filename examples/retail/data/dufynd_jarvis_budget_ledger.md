# DUFYND Jarvis Budget Ledger

This is a deterministic, read-only audit of Jarvis model spend.

It intentionally lives outside the Nightshift worker and does not change budgets,
tasks, approvals, storefront state, affiliate routing, content, deployments or
publishing.

## What it reconciles

The ledger reads:

- the authoritative database budget status;
- the configured budget window;
- the human approval referenced by that budget window;
- audited Jarvis agent runs created after the budget window started.

It then checks:

- audited spend versus the budget RPC's `spent_usd`;
- audited billed-run count versus the budget RPC's `runs`;
- the maximum single-run cost;
- whether any historical run exceeded the human-approved `per_run_cap_usd`;
- whether the budget still has a resolvable approval containing a per-run cap.

A historical per-run breach is reported as attention even if total spend remains
under the overall budget. This is deliberate: total-budget compliance and
per-run-cap compliance are separate controls.

## Usage

```bash
python -m scripts.report_dufynd_jarvis_budget_ledger --pretty
```

To use another approved budget window:

```bash
python -m scripts.report_dufynd_jarvis_budget_ledger \
  --budget-id <budget-id> \
  --pretty
```

For automation that should fail when reconciliation or policy attention is needed:

```bash
python -m scripts.report_dufynd_jarvis_budget_ledger \
  --pretty \
  --fail-on-attention
```

The command performs no writes and no model calls.
