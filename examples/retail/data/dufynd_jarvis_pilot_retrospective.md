# DUFYND Jarvis Pilot Retrospective

This is a deterministic, read-only operator checkpoint built on the merged Jarvis
budget ledger and pilot-efficiency reports.

It is intentionally isolated from the Nightshift worker, supervisor, dispatcher,
Morning Report, storefront, catalog, affiliate routing, publishing and 3D pipelines.

## What it summarizes

The retrospective combines:

- human-approval validity;
- budget run-count and spend reconciliation;
- audited pilot run count, spend and average run cost;
- failed-run count, failed-run spend and recorded failed model turns;
- spend/count/average/max attribution by recorded Jarvis runtime;
- repeated cost centers;
- near-per-run-cap activity;
- remaining approved runs and budget headroom;
- maximum additional spend possible under the current approved controls.

The command performs the ledger and efficiency reads independently. If the underlying
agent-run data changes between those reads, it marks
`retrospective_source_drift` instead of presenting the mixed snapshot as clean.

## Checkpoint meanings

`within_controls` means the human approval is valid, run count and spend reconcile,
the two report sources agree, and neither source reports an attention condition.

`attention` means at least one control, reconciliation, historical-cost or
cross-read consistency condition needs operator review. It is not an instruction to
increase budget, stop Jarvis or continue spending.

## Usage

JSON:

```bash
python -m scripts.report_dufynd_jarvis_pilot_retrospective --pretty
```

Operator-readable Markdown:

```bash
python -m scripts.report_dufynd_jarvis_pilot_retrospective \
  --format markdown
```

To exit non-zero when the checkpoint is `attention`:

```bash
python -m scripts.report_dufynd_jarvis_pilot_retrospective \
  --pretty \
  --fail-on-attention
```

Runtime attribution comes from the audited decision metadata recorded with each
billed Jarvis run. Legacy rows without a runtime are shown as `unknown`; a run
containing multiple recorded runtimes is shown as `mixed`.

The report is observational only. It does not mutate budget windows, approvals,
queue state, model runtime, production data or GitHub state.
