# Independent public storefront liveness — 29 October 2026

## Purpose and evidence boundary

The existing public API monitor does not establish that the public storefront
serves the DUFYND homepage. This migration adds that separate observation to the
existing two-minute `poll_dufynd_observers()` cron. It adds no cron, infrastructure,
credential, model call, business task, browser session or storefront code change.

The monitor requests only `https://dufynd.de/`, without a query string, using
`Accept: text/html` and `User-Agent: DUFYND-Public-Storefront-Health/1`. It executes
no JavaScript, follows no page links and loads no assets. The verified public
homepage on 29 October returned HTTP 200, `text/html; charset=utf-8`, and 32,522
UTF-8 body bytes. Its canonical is exactly `https://dufynd.de` without a trailing
slash. The chosen homepage markers already exist in `HomeView.tsx`; the accepted
design and page output are unchanged.

Success means **public storefront HTML liveness only**. It does not prove a Render
deployment SHA, API readiness, interactive navigation, accessibility, private
provider access, conversion, a purchase, or a completed business action. The
reader returns this boundary explicitly; private Render/Gmail evidence remains
independent.

## Stored and returned contract

State is stored in the existing private masterstatus key
`ops.public_storefront_health_v1`. Installation is disabled, idempotent and has no
successful source timestamp. Both new functions are `SECURITY INVOKER`, use fixed
`pg_catalog, public` search paths and restrict execution to `postgres` and
`service_role`. The verified masterstatus RLS and existing grants stay unchanged.

`poll_dufynd_public_storefront_health_v1()` accepts a successful observation only
when all of the following hold:

- Exactly one receipt belongs to the tracked request ID. A bounded, single
  snapshot reads at most two matching rows and rejects ambiguity.
- The request timestamp is finite, present and not in the future. The receipt's
  real `created` time is finite, at or after that request, at or before the clock
  read after receipt selection, and no more than 600 seconds old.
- The response has HTTP 200, no transport error/timeout, HTML content type and a
  non-null body of at most 131,072 UTF-8 bytes. A visible 3xx response or a
  case-insensitive `Location` header is rejected.
- The bounded document has a doctype, one HTML/head/body opening, closing document
  structure, one DUFYND title, one exact homepage canonical, the existing homepage
  section marker and the `/duft` link. Comments, scripts and style blocks cannot
  supply those signals. This is a limited markup identity check, not a DOM,
  browser-visibility or complete HTML-validity assessment.

The stored success time is the actual `net._http_response.created`, never a later
cron/check timestamp. `valid_until` is exactly 600 seconds later. Success metadata
contains `last_status_code: 200`, `html_contract: "dufynd_home_v1"`, and numeric
`last_response_bytes` in the accepted range. Only timestamps, counts and fixed
error codes are copied into masterstatus; response bodies, headers and raw
transport errors are not copied into durable reports. The existing temporary
`pg_net` response table still holds its own receipt data.

`read_dufynd_public_storefront_health_v1()` recalculates expiry whenever read.
Consumers must call this helper instead of treating a stored `healthy` string as
current evidence. The returned scope is `public_storefront_liveness_only`;
`private_observer_evidence`, `full_chain_complete`, `deployment_revision_verified`,
`redirect_chain_verified`, `final_origin_verified`, and `javascript_executed` are
always false.

## Pending, failures and cadence

There is at most one tracked request. A valid short pending interval can retain
an already verified recent success; it cannot create a first success. The reader
allows the existing consumer cadence through 180 seconds and then fails closed.
The poller retains an overdue request still present in the queue instead of
accumulating retries. A malformed saved request ID/time is also held unavailable
for explicit state repair; silently forgetting it could orphan a queued request.

Once a request has left the queue without a receipt, or a receipt is rejected,
the monitor records a fixed diagnostic and backs off by 120, 240, 480, 960 and at
most 1,800 seconds. It does not enqueue a replacement in that failing invocation.
An advisory lock plus the masterstatus row lock serialize polling. Exceptions are
isolated from the existing observers and use fixed redacted diagnostics.

The 120-second interval is a scheduling minimum, not a promise of an observation
every two minutes. Actual enqueue, response and consumption timing follow the
existing cron and asynchronous transport. The response time remains visible in
the reader. At the observed body size, even a request every 120 seconds for 30
days would transfer approximately 0.70 GB of uncompressed HTML, excluding headers
and redirects. This is a planning bound for that observed size, not a quota
guarantee; there are no image, script or stylesheet requests. Activation must use
the existing verified resource allowance without a paid-plan change.

## Transport limitations

The official [pg_net API documentation](https://supabase.com/docs/guides/database/extensions/pg_net)
states that HTTP dispatch starts after transaction commit. A request ID therefore
proves enqueueing only. The installed transport's temporary receipt storage is
not a durable uptime log.

The upstream [pg_net source](https://github.com/supabase/pg_net/blob/master/src/core.c)
enables `CURLOPT_FOLLOWLOCATION`; the SQL request API has no redirect-pinning
switch. This implementation fixes the initial trusted URL and rejects redirects
visible in the final receipt, but cannot attest the hidden redirect chain or
final origin. It sends no credentials or sensitive headers. The reader exposes
`redirect_behavior: "pg_net_follows_redirects"` together with false origin/chain
verification flags. The 128 KiB threshold limits accepted HTML processing; it
does **not** cap pg_net's network download or response buffer. No global pg_net
setting is changed.

## Existing API receipt defect and hook preservation

The production API poller used a non-strict `SELECT INTO` for `net._http_response`,
whose live ID has no uniqueness constraint. Two local reproductions on its exact
verified source accepted duplicate receipts as healthy: two 200 responses, and
one 200 plus one 503 response. The narrow correction reads cardinality and the
candidate receipt in the same bounded snapshot, rejects duplicates as
`ambiguous_api_receipt`, and does not retain an arbitrary status code. Existing
API payload, time, pending, backoff and reader contracts remain unchanged.

The observer hook is copied from the current #847 migration
`20261029090152_dufynd_github_observer_receipt_freshness.sql`. Its body is identical
after removing the single isolated storefront call. This preserves the current
GitHub receipt guards; it does not restore the older 28 October implementation.

## Focused verification and rollout

Native PostgreSQL 17.11: **71/71 focused cases passed**, comprising 64 storefront
cases and seven API cases, with zero external network attempts. Coverage includes
the old API defect versus the corrected function, genuine source timestamps,
future/non-finite/duplicate receipts, HTTP 200 error pages, exact canonical and
homepage identity, accepted-byte boundaries, private-evidence isolation, pending
grace, queued/malformed ownership, retry/backoff, expiry when cron stops, ACLs,
idempotent installation, and exact preservation of the existing hook body.
The API cases reuse five adjacent existing contracts on the corrected function.
Tests use a local `net` fixture and do not claim a live monitor observation.

The migration remains disabled until the combined CI and migration checks are
complete. Verify the exact pre-existing function definitions/ACLs and existing
masterstatus privacy boundary before applying it. After separate activation,
allow the existing cron to enqueue and consume an actual homepage response, then
verify its timestamp, scope, failure diagnostics and independent private-provider
status through the readers. Do not infer health from the migration, cron return
value, queued request or synthetic test result.

Rollback first disables the row. Restore callers to their exact previous
definitions before removing the new helpers. A pending request can finish after
disabling; it cannot establish a new storefront success while disabled. The
separately proven API cardinality correction can remain in place.
