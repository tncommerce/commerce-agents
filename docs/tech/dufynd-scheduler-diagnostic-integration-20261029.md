# Natural scheduler delivery in the existing technical diagnosis

## Correct the source of the diagnosis

The integrity audit previously assigned `max(created_at)` from recurring broker
acceptance sessions to `last_private_broker_capture_at` and used that timestamp
to report `private_broker_scheduler_gap`. An acceptance start is neither a
completed capture nor evidence that GitHub delivered a scheduled event. A manual
Render-only read also cannot establish natural schedule delivery.

This integration consumes the independent
`read_dufynd_github_scheduler_delivery_v1()` projection. Its public GitHub API
receipts validate the two fixed default-branch workflows and `event=schedule`.
The source reader keeps receipt freshness, original run creation and dispatch
outcome separate. Rerun attempts cannot renew original delivery time or establish
that the first dispatch attempt succeeded.

## Existing consumers, one source

The current `poll_dufynd_observers()` gains one isolated call to
`poll_dufynd_github_scheduler_delivery_v1()`. Its existing API, storefront, GitHub,
private-provider and credential logic is otherwise identical. No cron, task,
provider activation, Gmail retry, purchase action or paid infrastructure is added.

`read_dufynd_technical_work_blockers_v1()` exposes the source projection as
`github_scheduler_delivery` and preserves its specific observation, delivery and
dispatch issue codes. Missing or disabled monitoring yields
`github_scheduler_observation_unavailable`; it cannot support a globally healthy
or exhausted technical state. This is a diagnostic, not an outage claim or an
instruction to activate a provider. Unknown/stale observations keep delivery
unknown instead of converting absent evidence into a proven schedule gap.

The planner retains existing real-work and owner gates. After those, its current
technical priorities are public API, public storefront, scheduler delivery, then
the existing private-observer fallback. The scheduler action is
`diagnose_private_scheduler_delivery`. It writes the existing diagnostic report;
it does not manufacture or dispatch a task.

The integrity audit reuses the same technical projection within the invocation:

| Field | Meaning after the correction |
|---|---|
| `last_private_broker_acceptance_started_at` | Latest eligible recurring acceptance session start |
| `private_broker_acceptance_gap` | Existing acceptance freshness diagnosis |
| `last_private_broker_capture_at` | Existing strictly validated complete capture time, or null |
| `private_broker_scheduler_gap` | Source-reader delivery gap; null while evidence is unknown, stale or disabled |
| `private_broker_scheduler_observation_status` | Freshness/completeness of the actual scheduler API observation |
| `github_scheduler_delivery` | Full bounded source projection, including separate dispatch outcome |

The existing capture timestamp field remains a nullable timestamp, but no longer
mislabels a start as a capture. The scheduler gap field remains available and now
permits null rather than asserting success or failure without evidence. The
legacy `expected_private_broker_schedule_minutes` value is retained for report
compatibility; it is not an observation or the new reader's delivery deadline.
Specific scheduler issues use the same `github_scheduler_*` codes in reader,
planner evidence and audit.

A current technical diagnosis can still explain an empty queue. Its existing
source freshness and current-blocker checks remain intact; stale diagnosis
markers cannot conceal actual planner starvation. Schedule availability cannot
clear missing complete broker capture, revoked Gmail credentials, paused Gmail
recovery, private release-evidence gaps, or incomplete business work.

## Integration and rollout boundary

Forward migration `20261029115545_dufynd_scheduler_delivery_diagnostics.sql`
follows the monitor-core migration. The four production function bodies from
`760d3a352b2b344e6a9b75abb69b576af1f84d19` are preserved apart from the stated
integration changes. Existing owners, execute ACLs, search paths, volatility and
security modes are retained, including the existing security-definer audit.

The core installs disabled. This integration reports the missing observation
without issuing a request or changing activation. A later enabled poll must
obtain genuine GitHub receipts before current schedule delivery can be asserted;
manual captures or acceptance timestamps cannot substitute for that evidence.

## Verified integration

The dedicated PostgreSQL 17.11 integration module passed **28/28 cases** against
the exact frozen monitor core, with zero external network attempts. Healthy and
gap cases use the real poller and two local `pg_net` receipts through the shared
core fixtures. Existing historical migration suites keep their original
contracts; no healthy assertions were weakened to accommodate the new source.

The regressions reproduce both old false inferences: a recent acceptance hiding
a proven natural delivery gap, and an old acceptance incorrectly marking fresh
natural delivery as a scheduler gap. They also cover missing/disabled and partial
observations, expiry, dispatch failures/pending/reruns, genuine complete capture,
public endpoint priorities, existing work/owner gates, stale or resolved diagnosis
markers, the real paused-Gmail audit wrapper, hook isolation/request deduplication,
and unchanged owners, ACLs, security modes and function properties. The newer
core reader is read-only but `VOLATILE`, so source freshness uses the actual clock
after a potentially delayed calling statement.
