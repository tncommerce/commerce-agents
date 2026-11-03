# Independent public API liveness — 28 October 2026

## Why this change

The private observer workflow nominally runs every five minutes, with a ten-minute
GitHub watchdog. The verified 28 October runs had long gaps before run creation.
A fresh public API health observation must not depend on those same schedules.
The private Render observer must nevertheless remain stale when its authenticated
deployment evidence is stale, and the revoked Gmail grant remains blocked.

This change uses the existing Supabase observer poll to enqueue one fixed public
GET through the already installed `pg_net`. It creates no additional cron job,
worker service, table, credential, provider grant, model call or business task.
It does not change the API or require a Render build.

## Narrow contract

- State lives in the existing private `dufynd_master_status` row
  `ops.public_api_health_v1`.
- Installation is **disabled by default**. A configuration timestamp is not a
  successful source observation; initial state has no success time or validity.
- `poll_dufynd_public_api_health_v1()` and
  `read_dufynd_public_api_health_v1()` are `SECURITY INVOKER`, with fixed search
  paths and execution restricted to postgres/owner and `service_role`.
- The only requested URL is
  `https://scentai-api-kxhe.onrender.com/api/health`. Parameters, destination and
  headers cannot be supplied by callers or the status row. No authorization,
  cookies, customer information or provider credentials are sent.
- Only HTTP 200, JSON content type, an accepted body of at most 16 KiB,
  typed `ok: true`, exact `store: "DUFYND"`, and a finite, current response time
  can establish success. Raw body and transport-error text are not copied into
  masterstatus.
- Success is recorded using the database-owned `net._http_response.created`
  timestamp, conservatively treating that time as the observation time. It is
  not replaced by a later polling timestamp. Validity lasts 600 seconds.
- The reader calculates expiry when read, including if the cron stops completely.
  Consumers must use the reader for current health; a stored status is historical.
- The minimum interval between requests is 120 seconds. Actual cadence follows
  the existing cron; this patch creates no independent timer. The HTTP timeout
  is 5 seconds, with at most one tracked request. A still-queued, overdue request
  is retained and reported unavailable so a stopped `pg_net` worker cannot
  accumulate a retry backlog.
- Missing response after queue pickup, invalid payloads and transport failures
  cannot advance success time. Retries back off from two minutes to at most
  thirty minutes. A monitor exception is diagnosed using a fixed error code and
  isolated from the pre-existing observer loop.

The new measurement is **public API liveness only**. It does not establish which
commit Render deployed, replace authenticated Render/Gmail evidence, acknowledge
mailbox cursors, finalize broker acceptance, or claim a completed business action.
Those boundaries are also returned explicitly by the reader.

The accompanying technical-classifier migration adds public API diagnostics to
the existing private-provider findings. The planner selects
`diagnose_public_api_health` only when this monitor is enabled and not healthy.
Public success cannot clear private source, revision or complete-capture gaps;
existing executable work, work already in progress and owner gates keep priority.

## pg_net boundaries

The official [`pg_net` API documentation](https://supabase.com/docs/guides/database/extensions/pg_net)
states that requests start only after transaction commit. An enqueue return value
therefore proves a queued request, not a healthy endpoint. Response records are
temporary and can disappear after a crash or retention expiry; missing records
remain an unavailable observation.

The official [`src/core.c`](https://github.com/supabase/pg_net/blob/master/src/core.c)
enables `CURLOPT_FOLLOWLOCATION`. Its SQL API provides no per-request redirect
pinning switch. This implementation assumes the fixed, operator-controlled
public endpoint is trusted; it **does not prove the final response origin** or
prevent a compromised endpoint from issuing redirects. It sends no sensitive
headers, and its result cannot serve as privileged provider/revision evidence.
The 16 KiB limit bounds accepted JSON processing, not the extension's download
buffer. No `pg_net` global setting is changed.

## Rollout and verification

Apply only after the exact installed poll definition, its ACL, the masterstatus
contract and the `pg_net` response/request signatures have been checked. The
existing `poll_dufynd_observers()` body gains one isolated hook; existing private
provider and GitHub observation logic is retained. Existing schedule count,
provider activation, source evidence and task counts should not change.

After separately verified activation, let the existing cron enqueue and consume
a real public response. Read the new helper and verify that the old private
Render/Gmail statuses remain independently truthful. Combined rollback first
disables the monitor, then restores the exact previous technical-classifier,
planner and observer-poll definitions. Only after those callers are restored may
the new health helpers be removed. A pending public request may complete after
disabling; it cannot establish a new success while disabled.

The native PostgreSQL regression module exercises disabled installation,
caller-supplied target rejection, pending-request deduplication, stopped transport,
typed response validation, bounded failures, real response-time freshness,
expiry without a cron tick, private-evidence isolation, ACLs and migration
reapplication. Its isolated `net` namespace produces no external requests.

Combined native **PostgreSQL 17.11 verification: 61/61 cases passed** — 34 public
monitor cases and 27 technical-planner cases. This covers both isolated source
validation and planner integration; it is not a live HTTP or private broker
acceptance claim.
