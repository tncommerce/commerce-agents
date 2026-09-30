# DUFYND Jarvis Control-Plane Audit

This audit is a deterministic, read-only companion to the Jarvis Nightshift.

It is intentionally separate from the Nightshift worker, storefront, catalog,
affiliate routing, content publishing and 3D/visual pipelines so it can be used
without colliding with active production work.

## What it checks

The command reads the current Jarvis control plane and reports:

- the direct database budget status for the configured Jarvis budget window;
- drift between that authoritative budget status and the embedded health snapshot;
- the current autonomy boundary (safe work, in-progress work, owner review,
  external waits or idle);
- stale Nightshift sessions that still claim to be active after their heartbeat
  exceeded the configured threshold;
- autonomy tasks that remain `in_progress` beyond the configured task-age threshold;
- TECH continuity leases that are still labelled active after expiry;
- failed Jarvis inbox events.

No rows are updated and no GitHub, Render, affiliate, social, catalog or publishing
action is performed.

## Usage

```bash
python -m scripts.audit_dufynd_jarvis_control_plane --pretty
```

The default stale-session threshold is 45 minutes and the default stale
`in_progress` task threshold is 24 hours. Override either with:

```bash
python -m scripts.audit_dufynd_jarvis_control_plane \
  --stale-after-minutes 30 \
  --stale-task-hours 12 \
  --pretty
```

For deterministic automation that should fail when operational attention is
required, add `--fail-on-attention`. Without that flag, the command reports
attention states in JSON but exits successfully.

The direct budget status returned by the budget RPC is always treated as
authoritative. An older embedded `runtime_state.pilot` health snapshot is evidence
of control-plane drift, not evidence that spend or remaining-run counts changed.

The autonomy boundary counts only rows whose current status actually matches the
queue bucket. Old completed rows that still appear in an approval bucket are not
treated as pending approvals. Long-lived `in_progress` rows are reported separately
so stale legacy work does not masquerade as active execution.
