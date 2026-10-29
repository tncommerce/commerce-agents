# GitHub observer receipt freshness

The supervisor previously promoted a retained `pg_net` HTTP 200 or 304 to a new
successful observation at consume time. After a consumer delay, an old response
could therefore make an old GitHub revision appear current to the technical
planner. This is a reproducible recovery defect; the change does not claim that a
stale response was consumed in production during the investigation.

## Acceptance boundary

`poll_dufynd_observers()` now reads `net._http_response.created`. A successful
receipt must be unique for its pending request, finite, no earlier than that
request, no later than consumption, and inside the existing freshness window
`greatest(600, interval_seconds * 3)`. Checks use wall time after the advisory lock
and public monitor hook. Timeout/error receipts cannot succeed even when their
HTTP status says 200 or 304. The existing missing-response grace and bounded
retry/backoff remain in place.

Accepted observations retain that response creation time in `last_success_at`;
the next normal poll is due one configured interval after consumption. A 200
still uses the existing source normalizer, bounded capture and event
deduplication. Rejected receipts do not ingest a new SHA or event. Disabled
pending observers cannot become healthy. Consuming a receipt clears its pending
identity and cannot renew success a second time.

A 304 can revalidate only a real conditional GET. The existing GitHub-only
`request_kind` and `pending_cursor` fields bind its ETag, complete retained
snapshot, previous success timestamp, request ID and request start. Timestamp
serialization uses epoch values so session time zones do not change that
binding. Changed or unproven prior state, an unexpected response body, and a
conflicting response ETag fail closed. A missing response ETag is valid when the
conditional request and original snapshot remain proven. A new 200 without an
ETag clears the previous validator.

## Upgrade and rollback scope

The migration replaces only the existing poller function and resets `etag` to
NULL for the four GitHub observer types. This one-time data update is necessary:
the old 200 path could retain a previous ETag when the replacement body had none,
so legacy ETag/snapshot pairing cannot be assumed. The next already-due GET
establishes a new baseline. An already-pending legacy 304 fails closed and uses
the existing bounded retry.

Snapshots, historical success timestamps, task state, retry deadlines, private
observer credentials, grants, RLS, cron configuration and resource limits are
unchanged by the migration. The ETag reset is idempotent for the same stored
state; reapplying after new observations clears only the disposable validator
again. Rolling back the function does not require restoring cached ETags. Any
rollback must retain the truthful observation history; restoring the old poller
also restores its known consume-time freshness defect.

## Verification

`tests/test_dufynd_github_observer_receipt_postgres.py` runs the real SQL poller,
failure handler, normalizer, capture/deduplication and technical planner reader
against disposable PostgreSQL. Only HTTP transport is replaced with a local
queue. It covers delayed and invalid times, successful receipts, conditional
snapshot binding, duplicate IDs, disabled observers, malformed bodies,
reentrancy, time zones, upgrade scope, and retained rate-limit bounds. The file
is included in the existing native PostgreSQL CI job; no additional job or
service is introduced.

Local PostgreSQL 17.11 verification on 2026-10-29 passed all 57 new cases and all
129 cases in the combined observer, private-staleness, technical-planner and
public-monitor run (including one existing schema/bootstrap integration case).
The unchanged production poller failed the five selected freshness regressions
as expected: expired 200/304 at both configured bounds and renewal at consume
time. Ruff lint/format and patch whitespace checks passed. These are local test
results; the existing mandatory PR checks remain the release gate.

The [official pg_net documentation](https://supabase.com/docs/guides/database/extensions/pg_net)
defines response `created` as a database timestamp and documents requests
starting after the caller commits and responses retained for six hours by
default. This timestamp is local response storage evidence, not a timestamp
asserted by the GitHub payload. Neither a cron success nor this correction proves
private GitHub scheduling cadence or Gmail recovery.
