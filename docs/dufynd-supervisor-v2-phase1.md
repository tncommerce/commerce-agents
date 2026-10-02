# Jarvis Supervisor V2 — Phase 1

The 2026-10-01 Nightshift stopped after three incomplete research tasks. Its
$2.50 budget window recorded $2.5047. TECH left an `active` lease with both
`released_at` and an expired TTL. Phase 1 extends the existing Supabase tables;
it does not introduce a second task queue.

## Operational behavior

`dufynd_autonomy_tasks.worker_state` records queued, ready, claimed, working,
verifying, done, waiting_external, waiting_human_input, blocked,
failed_retryable, failed_terminal and stale. Existing `status` values remain
compatible with current queue readers. Worker owner, UUID fencing token,
start/heartbeat/progress/checkpoint, retry count, reason and evidence persist
on the same row. All times use database time.

Claims serialize only the short claim transaction, not worker execution.
`resource_scope` lists canonical `repo:`, `db:`, `external:` and `exclusive:`
resources. Repo directories intersect descendants; exact resources intersect
each other. Undeclared scopes default to `exclusive:global`. Separate declared
scopes can execute concurrently. The legacy TECH lease conservatively blocks
repo work. Dependencies must be exact completed task IDs; unresolved historical
blocker labels remain parked for explicit reconciliation.

Leases last 180 seconds; workers heartbeat every 45 seconds. Heartbeats never
advance `last_progress_at`. After 600 seconds without new progress evidence,
the lease cannot renew. A stale or released token cannot mutate the task.
Direct updates to any unreleased V2 lease are rejected. The watchdog records
the stale reason and releases the lease. Known free work retries at most twice;
potentially paid work is quarantined until its outcome/cost is verified.

The `dufynd-supervisor-v2-health` pg_cron job runs every two minutes without a
model call or an external paid worker. It repairs contradictory legacy leases,
recovers stale tasks, recognizes fulfilled task-ID dependencies, and persists
health findings under `jarvis.supervisor_v2.health`. Findings include idle ready
tasks, unclassified human gates, paused budget work, pending/failed/stale inbox
events. Failed or stale inbox entries do not freeze unrelated work. Unknown
inbox outcomes are reported, not blindly retried.

The bounded Python supervisor continues deterministic health passes after
budget gates and task-local errors. Engineering QA still owns its checkout
handoff. Typed owner-decision reasons gate `waiting_human_input`; a model's
completion marker does not independently prove task completion.

## Strict budget boundary and current limitation

The installed Claude SDK's `max_budget_usd` is a stop threshold checked around
model turns. It cannot guarantee an upper bound on the next provider call.
An 80% margin failed in the observed Nightshift and is not a proof of safety.

Phase 1 therefore refuses **all paid SDK execution before provider startup**.
This has no environment-variable bypass. Existing budget approvals remain
unchanged, no new budget is granted, and no test makes paid provider calls.
Free deterministic events and the independent watchdog remain available.
Research/model work is parked with `budget_exhausted` or
`unbounded_provider_cost`, never sent to the owner as a budget decision.

To resume model workers, Phase 2 must add a bounded per-call adapter: known
pricing, bounded input/output/tool payload sizes, atomic budget reservations,
unknown-cost quarantine and settlement. Require
`remaining_budget - reserved_budget - worst_case_next_call_cost >= 0` before
every call, including tool-loop continuations. An SDK session limit alone is
not an acceptable implementation. The pure budget policy rejects missing,
nonfinite, negative, unbounded or insufficient limits.

## Verification

Run `pytest -q`, `ruff check .`, `ruff format --check .` and
`python scripts/check.py`. Run `tests/sql_dufynd_supervisor_v2.sql` in one
database transaction after migration; it always rolls back test fixtures.
It tests actual SQL claims, scope collisions, disjoint claims, fencing,
heartbeat/progress separation, stalled-work recovery, reclaims, typed human
gates, verification and terminal release, the real contradictory TECH lease,
and internal RPC privileges. Python tests cover all twelve requested cases.

Deployment: apply the migration before dispatching the updated Python
supervisor; verify the cron job is active and at least one cron run succeeds.
The migration enables pg_cron if absent. It grants internal RPC execution only
to service_role and retains RLS on the task table.

## Phase 2 priorities

1. Bounded provider adapter and atomic reservations; only then resume paid work.
2. Deterministic GitHub/Render/email observers feeding verified observations
   into the existing inbox. The database watchdog does not access those APIs.
3. Verification handlers for research outputs and engineering PR/CI outcomes;
   recover completed work from independently checked live evidence.
4. Replace historical dependency labels with exact task dependencies and
   declare reviewed per-task resource scopes; keep undeclared work conservative.
5. Review existing mixed human/technical blockers task by task; do not remove
   real publication, spend or owner decisions using text heuristics.

## OPTIMIZATION_CANDIDATE

Problem: Nightshift workers repeatedly read a ~100 KB queue and stop before
finishing task-specific evidence. Manual effort: another chat must reread and
reconstruct the missing work. Proposed automation: server-side paginated task
summaries and task-specific checkpoint pages, with authoritative completion
evidence separate from prose. Benefit: fewer tokens, shorter restart paths and
more completed work. Risk: summaries can omit relevant gates; preserve links
to full evidence. Priority: P1 after bounded execution and deterministic
verification.

Problem: refreshed repo fingerprints can regenerate task status while a worker
owns the row. Proposed automation: CAS-aware repo sync that queues a new revision
instead of replacing active work. Benefit: continuity across concurrent merges.
Risk: incorrect revisions can hide relevant changes. Priority: P1; Phase 1
already rejects conflicting direct writes to an unreleased worker lease.
