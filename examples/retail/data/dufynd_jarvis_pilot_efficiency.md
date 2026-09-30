# DUFYND Jarvis Pilot Efficiency Report

This report is a deterministic, read-only companion to the Jarvis budget ledger.

It does not run Jarvis, consume model budget, mutate queue state, change approvals,
publish content, alter affiliate routing, deploy code or touch storefront data.

## Purpose

The budget ledger answers "what did Jarvis spend and was it inside the approved
controls?"

This efficiency report adds "where did that spend go?"

It groups audited model runs into cost families and reports:

- total runs, total spend and observed average run cost;
- failed/error/timeout run count and spend;
- runs at or above 80% of the approved per-run cap;
- spend concentration by run family;
- repeated cost centers (at least 3 runs and at least 15% of audited spend);
- remaining approved spend/run headroom;
- how many additional runs the remaining budget would cover if the historical
  average cost repeated.

The observed-average capacity is descriptive only. It is not a promise, budget
increase or prediction of future provider charges.

## Usage

```bash
python -m scripts.report_dufynd_jarvis_pilot_efficiency --pretty
```

Use another existing budget window with:

```bash
python -m scripts.report_dufynd_jarvis_pilot_efficiency \
  --budget-id <budget-id> \
  --pretty
```

For an automation that should exit non-zero when failed or near-cap activity is
present:

```bash
python -m scripts.report_dufynd_jarvis_pilot_efficiency \
  --pretty \
  --fail-on-attention
```

Repeated cost centers are informational, not an instruction to spend more or to
change the event policy automatically. Any production behavior or budget change
remains separately human-gated.
