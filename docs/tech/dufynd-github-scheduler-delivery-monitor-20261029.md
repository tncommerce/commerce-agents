# Independent GitHub scheduler delivery observation — 2026-10-29

## Problem and boundary

The successful manual Render-only run `40863831515` proved that its specific
reader/capture path worked. It did not prove recurring GitHub schedule delivery.
Before this change, the GitHub observer polled already known individual run IDs;
the integrity audit's scheduler proxy used recurring Acceptance-session creation
times. Neither identified new `event=schedule` runs on `main` independently of
manual captures or Gmail failures.

The last verified natural runs before this implementation were reader
`40834260621` at 07:15:24 UTC and watchdog `40837134023` at 07:42:16 UTC. Both were
attempt 1, successful workflow runs. Earlier inspection found repeated shared
gaps of several hours. At 11:49 UTC both workflow UIs offered **Disable workflow**;
neither was disabled or changed during that inspection. The new monitor detects
current delivery gaps; it does not repair GitHub's scheduler or erase that history.

This migration creates no cron, task, credentials, infrastructure or workflow run.
It seeds one private masterstatus key, `ops.github_scheduler_delivery_v1`, with
`enabled=false`. Separate integration calls its poller from the existing observer
path and consumes its read-only diagnosis. Activation is an explicit metadata
change performed by the release owner under the existing authorization.

## Fixed public source contract

| Target | Workflow ID | Workflow path |
| --- | --- | --- |
| `reader` | `373752411` | `.github/workflows/dufynd-private-observer.yml` |
| `watchdog` | `377395476` | `.github/workflows/dufynd-private-observer-watchdog.yml` |

Both initial URLs are hardcoded as
`https://api.github.com/repos/tncommerce/commerce-agents/actions/workflows/{ID}/runs?branch=main&event=schedule&per_page=1`.
No returned URL or masterstatus configuration can redirect the request builder.
There is no Authorization header. The JSON must independently confirm the exact
workflow ID/path, `main`, `schedule`, a full SHA, repository ID `1367576041`, owner
ID `324597697`, repository/owner names and `private=false` for both repository
objects. This prevents a same-name replacement or unrelated filtered result from
being accepted. The SHA is observed data, not an assertion that future `main`
remains identical to the historically inspected revision.

The [GitHub workflow-run REST documentation](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-workflow)
allows public-resource requests without authentication, documents the branch/event
filters, and uses `X-GitHub-Api-Version: 2026-03-10` in its current request example.
The [API version documentation](https://docs.github.com/en/rest/about-the-rest-api/api-versions)
lists that supported version.

## Three independent meanings

`read_dufynd_github_scheduler_delivery_v1()` returns `schedules.reader` and
`schedules.watchdog`, plus an aggregate projection:

| Field | Meaning |
| --- | --- |
| `transport_status` | Valid public REST evidence: `fresh`, `partial`, `stale` or `unknown`. |
| `observed_at` | Oldest accepted receipt time among available validated sources; individual receipt times remain per target. It is not a poll/consume timestamp. |
| `delivery_status` | `available`, `degraded`, `gap` or `unknown`, based on original natural-run creation. |
| `delivery_gap` | `true` only when both sources are fresh and neither has a natural run within 25 minutes; `null` when complete fresh source evidence is absent. |
| `latest_natural_created_at` | Latest validated immutable `created_at`, separate from each latest attempt start. |
| `dispatch_status` | The reported original workflow outcome: `success`, `failed`, `pending` or `unknown`. |
| `dispatch_status_basis` | Always `github_workflow_run_conclusion`; `downstream_dispatch_verified=false`. |
| `healthy` | Both sources fresh, both natural creations within 25 minutes, and both original workflow outcomes reported successful. |

An attempt greater than 1 retains its original creation time and cannot establish
the original dispatch result. `run_started_at` and `updated_at` never reset the
delivery clock. Re-reading the same run does not create another natural delivery.
Retiming an existing run, reverting its attempt, returning older run history or
reusing a consumed request ID is rejected.

A successful workflow conclusion alone is not a job-log proof of its downstream
`gh` dispatch. Nor does a fresh natural run prove future 5-/10-minute cadence.
`cadence_guarantee`, `private_observer_evidence`, `capture_verified`,
`full_chain_complete` and `business_success` remain false. Private Render health,
release intent, public liveness and the paused Gmail condition remain separate.

The technical integration consumes these fixed issue codes:

- `github_scheduler_observation_unavailable`
- `github_scheduler_observation_stale`
- `github_scheduler_delivery_gap`
- `github_scheduler_delivery_degraded`
- `github_scheduler_dispatch_failed`
- `github_scheduler_dispatch_unverified`

Disabled or missing observation remains explicitly unknown/unavailable. It does
not cause network activity and cannot make an unrelated manual capture establish
automatic delivery.

## Bounds, freshness and failure handling

The global gate permits one serial GET no sooner than every 300 seconds; targets
alternate with an additional 600-second gate per target. Thus this monitor issues
at most two requests per ten minutes. With the existing two-minute caller cadence,
actual requests can be spaced about six minutes apart; this is a ceiling on
request volume, not an availability promise. A target with a still-owned pending
queue entry cannot accumulate another request; the other target can progress.

This adds at most 12 public REST requests/hour. GitHub's
[unauthenticated limit](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
is shared by originating IP, including other existing monitors. No separate
quota is assumed. The monitor follows the
[REST rate-limit and serial-request guidance](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api):
valid Retry-After, reset and poll-interval waits apply to the global budget and are
never shortened to the ordinary backoff. Failures back off from 600 to 3600 seconds.
Malformed budget/rate metadata, ambiguous receipts, or a rejected rate-limit
receipt whose required wait is unknowable hold this monitor's budget. A review of
actual request/quota evidence is required before correcting that metadata; a
missing or malformed time is never treated as immediately due.

`net._http_response.created` is the source receipt clock. Each accepted receipt
must be unique, finite, no earlier than its saved request, not in the future and
no more than 1200 seconds old. Clock checks occur after row locks and response
reads. The read-only projection checks the actual wall clock after its SELECT,
so waiting inside a calling planner statement cannot preserve false freshness.
Only HTTP 200 with JSON is accepted; 304 cannot refresh an old delivery.

The SQL reads at most two matching receipt rows, projects at most 65,536 bytes of
body and 8,192 bytes of headers, and keeps only the validated minimal run snapshot.
These are SQL parsing/projection limits, not a cap on pg_net's prior network
download or buffer. Raw provider bodies, errors, URLs and credential values are
not copied into masterstatus.

The [pg_net API](https://supabase.com/docs/guides/database/extensions/pg_net) starts
requests asynchronously after the caller commits. Its upstream implementation
follows redirects. Visible redirects or Location headers are rejected; the
monitor does not claim to attest a hidden redirect chain or final origin. Those
two verification flags remain false, alongside the fixed initial HTTPS origin
and strict returned repository/workflow identity checks.

All four functions are `SECURITY INVOKER`, use a fixed search path and allow only
`postgres`/`service_role` execution. The migration does not modify table grants,
RLS policies, existing provider observations, cron schedules or task rows.
The reader is `VOLATILE` because its wall clock can advance during one calling
statement; this is separate from writing data. Its SELECT-only body is tested
with PostgreSQL `transaction_read_only=on`, in accordance with the
[PostgreSQL volatility contract](https://www.postgresql.org/docs/17/xfunc-volatility.html).
The seed is idempotent and never resets an existing monitor row. Disabling the
monitor stops its requests while preserving its receipts and reporting unknown.

## Local verification and release integration

The focused module `tests/test_dufynd_github_scheduler_delivery_postgres.py` passes
**111 real PostgreSQL cases** on the isolated PG17 instance with SQL queue/receipt
stubs and transaction rollback. No GitHub/merchant/model requests occur in tests.
The suite includes source identity, stale/future/pre-request/duplicate receipts,
immutable run creation across reruns, strict global and per-target gates, rate
limits, missing queue ownership, disabled state, private ACLs, read-only projection
and timezone changes. Five rejected-rate-limit cases and the caller-clock boundary
were first reproduced as failing cases, then verified after the bounded fixes.
The integration suite separately loads this real reader into planner/audit.

At 11:56:35 UTC the release owner retired the already merged PR823/PR840 observers
after exact HEAD/merge/no-consumer/no-pending guards; history fields were preserved.
The separate [guarded retirement audit](../../release/dufynd-scheduler-monitoring-20261029/retire-merged-observers.sql)
records that action. It does not change the fixed monitor source contract here.
The existing `ops.dufynd_monitoring_release_20261029.scheduler_followup` handoff is
the live status reference. First real pg_net receipts and natural-cycle readback
remain release verification, not something the local tests can claim.
