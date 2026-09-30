# DUFYND Jarvis Observability Runbook

This runbook is the operator entry point for the read-only Jarvis observability
tools already present on `scentai-mvp`.

It does not start Jarvis, call a model, consume model budget, mutate queue state,
change approvals, publish content, deploy code, alter affiliate routing or touch
production data.

## Recommended order

### 1. Control-plane audit

Use this to inspect database/runtime drift, stale Nightshift state, failed inbox
events and lease anomalies:

```bash
python -m scripts.audit_dufynd_jarvis_control_plane --pretty
```

Treat this as the broad infrastructure/control-plane view.

### 2. Budget ledger

Use this for the authoritative audited budget reconciliation:

```bash
python -m scripts.report_dufynd_jarvis_budget_ledger --pretty
```

It reconciles billed Jarvis agent runs with the approved budget window and human
approval, including per-run-cap checks and remaining headroom.

### 3. Pilot efficiency

Use this to understand where paid pilot spend went:

```bash
python -m scripts.report_dufynd_jarvis_pilot_efficiency --pretty
```

It highlights failed-run spend, near-cap runs and repeated cost centers. These
signals are observational only and do not authorize budget or runtime changes.

### 4. Pilot retrospective

Use this for a compact operator checkpoint that combines control validity, audited
pilot spend, failed-run history, repeated cost centers and remaining headroom:

```bash
python -m scripts.report_dufynd_jarvis_pilot_retrospective --format markdown
```

A historical warning can make the retrospective report `attention` even when the
currently approved pilot controls are still valid.

### 5. Paid-pilot preflight

Use this immediately before an already approved paid pilot execution:

```bash
python -m scripts.check_dufynd_jarvis_pilot_preflight --pretty
```

The preflight separates hard control blockers from historical warnings. It does not
start the pilot.

## Interpretation rules

- Database-backed audited spend is authoritative over stale cached health values.
- Total-budget compliance and per-run-cap compliance are separate controls.
- Historical failed or over-cap activity should remain visible even after runtime
  hardening; do not rewrite history to make a later report green.
- Informational cost concentration is not a reason to expand budget automatically.
- A read-only report may be rerun freely, but paid model execution remains governed
  by the existing approval, run limit and spend limit.
- No report in this runbook grants merge, publishing, credential, contract,
  subscription or production-data authority.

## Current pilot example

At the time this runbook was introduced, the approved activation pilot was still
bounded by its existing human-approved controls. Exact live values must always be
read from the current reports instead of copied from this document.

## Failure handling

If a report disagrees with another report:

1. rerun the budget ledger;
2. check the control-plane audit for stale state or drift;
3. use the retrospective source-consistency signal;
4. do not increase budget or bypass a gate to make the discrepancy disappear.

If the preflight returns a hard blocker, paid pilot execution should remain stopped
until the underlying control condition is understood and corrected through the
normal human-gated path.

## Scope

This document is operational guidance only. It intentionally does not modify the
Nightshift supervisor, dispatcher, Morning Report, approval queue, storefront,
catalog, affiliate, 3D, deployment or publishing paths.
