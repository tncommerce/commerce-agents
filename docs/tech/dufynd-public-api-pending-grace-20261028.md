# Public API pending grace — 28 October 2026

## Observed production defect

After release #844 and authorized monitor activation, the existing cron enqueued
request `21791` at **13:42:00 UTC**. Its real response was HTTP 200 with 177 bytes,
recorded by pg_net at **13:42:00.118791 UTC**. The read-only status check at
13:43:49 UTC incorrectly reported `unavailable / request_overdue`: the reader's
60-second pending deadline elapsed before the normal two-minute consumer tick.

The natural 13:44 cron then consumed the response and established health using
the actual response timestamp. Request `21792` also obtained HTTP 200. This was
a startup/recovery diagnostic defect, not a demonstrated HTTP transport outage.

## Narrow correction

An additive migration changes **only the reader's pending grace from 60 to 180
seconds**: one normal 120-second consumer cycle plus 60 seconds of scheduling
slack. The already applied original migration is unchanged.

During that grace the status remains `pending` and `healthy` remains false.
Success still requires the poller to consume a valid response. A pending request
older than 180 seconds is still reported unavailable when no consumer runs.

The poller's 60-second missing-response/queue check, 5-second HTTP timeout,
120-second minimum request interval and 600-second successful-observation
freshness are unchanged. The replacement retains the existing function owner
and ACL. No queue, status row, success timestamp, cron, provider evidence, private
capture or business action is rewritten by the migration.

## Regression proof

The native PostgreSQL regression restores the original 60-second reader and
demonstrates the false alarm at both 90 and 120 seconds, with an already available
valid HTTP response. It then applies the additive reader and verifies pending
without inventing success. The subsequent real fixture consumer must preserve
the response's original timestamp. Additional assertions cover the 181-second
deadline, frozen-cron expiry of a formerly healthy observation after 600 seconds,
and unchanged execution privileges.

Targeted verification on the existing isolated native PostgreSQL 17.11 baseline:
**64/64 passed** — 37 public-monitor cases and 27 affected technical-planner
cases. Ruff and `git diff --check` also passed. The earlier complete 305-case
PostgreSQL isolation run for #844 remains applicable; it was not repeated for
this single reader deadline change. The new candidate's required CI will provide
the complete suite result for its own exact head.

No extra live request or manual source-time refresh is required to verify the
correction after deployment: read the next naturally pending/consumed cycle.
