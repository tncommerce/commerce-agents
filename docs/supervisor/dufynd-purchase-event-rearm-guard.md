# DUFYND supervisor – terminated purchase task replay guard (RESET36)

**Status:** Reviewed development migration only, **NOT APPLIED TO PRODUCTION**.
Repo: `tncommerce/commerce-agents`, PR #799. No new providers, schedulers,
paid calls, new worker or extra purchase evidence.

## Live reproducible finding (2026-10-17)

The real control plane holds four `purchase-freshness:*` rows marked `ready`
although their attempts already finished, have non-null `released_at` and a
completed `dufynd_execution_runs` receipt. The most recent corresponding
execution decisions are `transport_unverified` (not sale or approved prices).
One newer `safe_evidence_refresh` occurred on 17 Oct 14:10 UTC; the current
verification target is not due for recheck. Nonetheless the planner counts
four ready rows and reports `work_available`, obscuring productive planning.

**Root cause:** `process_dufynd_external_events()` takes every external
wait bound to the **same purchase observer ID**, ignoring the event's exact
`related_task_ids`. On a later due event, it rechecks unrelated old generations.
Its broad final dependency sweep also turns previously released/blocked purchase
tasks back into `ready`; only unfinished executions are excluded, not
terminally completed ones. This is a deterministic queue bug, not a missing AI
model or a reason to add another Nightshift.

## Fix and boundaries

The existing processor is replaced **in place** with three narrow conditions:
(1) internal events touch only explicitly named `related_task_ids`,
(2) terminal/cancelled and released purchase attempts cannot be processed again,
(3) the dependency sweep refuses to rearm released purchase attempts.

A one-time idempotent repair changes only the obsolete `ready` purchase task
generations with completed execution receipts and released leases into
`cancelled` (never into `done`). The immutable execution receipts and genuine
commerce evidence remain untouched. New purchase tasks still arise via the
existing scheduled freshness wake with new content-bound task IDs when actually
due. No merchant page, outgoing HTTP, offer price, merchant URL, publishing,
analytics, consent, git-branch protection or production DB is mutated by the
**creation of this migration file**.

Regression tests in the existing disposable PostgreSQL CI fixture verify that a
new internal event wakes only its named task and that a released purchase attempt
cannot be resurrected by the old broad dependency sweep. The fixture rollback
preserves production data. No claim that the live queue is repaired before
a separately approved migration application and subsequent live read verification.

## Acceptance contract

- CI checks on matching exact SHA, including real PostgreSQL tests.
- After separately approved production migration: count of `ready` released
  purchase tasks with completed executions must be **0**, with neither new
  merchant/spend activity nor changed verified purchase timestamp.
- New *legitimate* purchase due events must still create/wake one exact task.
- No false `safe_evidence_refresh`, no fabricated sale or commission.
- Jarvis planning then depends on the refreshed, genuine business state, not
  historical phantom work. Manual Work delegation does not auto-dispatch.
