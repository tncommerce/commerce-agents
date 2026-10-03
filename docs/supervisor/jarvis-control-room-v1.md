# Jarvis Control Room V1 — server read boundary

The current retail Next.js storefront uses `output: "export"`. It has no owner
session verifier. Shipping an internal dashboard there would expose its HTML
publicly, and hiding a URL is not authorization. V1 therefore starts with a
dormant server read layer in `retail.api.jarvis_dashboard`. Nothing is mounted
in the production API or added to the static storefront.

## Completed read layer

`DashboardReader.snapshot()` produces a versioned DTO with Command Center,
Worker Deck, Mission Board, Live Activity, System Health, Budget & Safety,
Decision Center, and System Map sections. It reads the existing DUFYND project
using fixed GET requests, fixed table/column projections, and bounded results.
It does not inherit the command-capable Jarvis bridge. There is no SQL input,
table selector, arbitrary upstream URL, mutation, retry, credential refresh,
paid model call, merge, deploy, publication, or external message.

Master status is projected to specific JSON scalar paths at the database
boundary. Mail content, provider credentials, secret references, lease tokens,
raw evidence, observer snapshots, arbitrary errors, and checkpoint payloads
are excluded. Only the validated branch SHA is extracted from its snapshot;
execution checkpoints project only step, verification boolean, and timestamp.
Allowed free text is length bounded; known key material and recognizable
credential, email and URL strings are suppressed as an additional safeguard.
This is defense in depth, not permission to store secrets in task titles.

The budget ID is selected server-side. If supplied, the existing STABLE
`get_dufynd_jarvis_budget_status` function is called via GET, preserving its
reservation-aware accounting. Missing budget data displays unknown, never zero.
An observed disabled paid-execution flag is shown; an enabled flag alone cannot
prove that all paid runtime/provider gates are open and remains unknown.

Operational reads include all non-done tasks up to 500, active executions up to
200, observers up to 200, and credential health rows up to 50. Counts and any
truncation are explicit. Recent done missions/runs and inbox activity are bounded
history. A partial operational read degrades status rather than showing false
zero/healthy counts. Refresh is not an atomic database snapshot; the DTO states
this and preserves observation timestamps. It never equates read time with a
successful observer wake or an external system check.

Expired/missing worker leases and stale/future heartbeats are not active.
Claims without execution records remain visible. `waiting_external` tasks with
future approval flags are not current owner decisions. Ready tasks with budget
blockers are shown as blocked. Unknown/missing/stale health stays visible.
The checkpoint is shown as an observed summary with a stale marker; it is not
used to claim current completion or execute a proposed next action.

The supervisor's 120-second next-wake estimate is explicitly an estimate based
on a fresh health tick. It does not certify the separate 10-minute private
observer scheduler. The layer cannot fabricate intermediate read/ingest/ack
steps where durable stage evidence is absent; that acceptance timeline needs
the corresponding allowlisted provenance projection after authentication.

## Owner decision required before browser access

Choose the owner authentication method and identity. Recommended implementation:
use the existing Supabase Auth service for an owner session and a server-owned
allowlist containing the approved owner user ID. Verify the current user on the
server for every read. Do not authorize from user-editable metadata, email alone,
an `authenticated` role alone, request headers claiming ownership, a URL token,
the broker owner key, or a service-role key handed to the browser.

After that decision, integrate the verifier with the dormant router adapter,
mount the read route behind it, and build the cinematic worker stations as a
client of that allowlisted DTO. Protect access to the dashboard itself, as well
as every JSON read. The static storefront cannot provide a protected server
page; choose whether the internal shell is served by the existing API or whether
the existing frontend is deliberately migrated to server rendering. Reusing the
existing API for the internal shell avoids a hosting migration and new services.
Do not change current hosting, add a new service, or modify auth settings as
part of this read-layer PR.

`create_dashboard_router(reader)` denies by default before any database access.
A real owner verifier must be explicitly supplied for activation. The route is
GET-only, absent from OpenAPI, and successful/unavailable responses are private
and `no-store`. It is not registered in `main.py`. This is an intentionally
inactive implementation awaiting the owner auth boundary, not a live dashboard.

## Validation

Run `pytest tests/test_jarvis_dashboard.py` plus repo lint/format and CI.
Coverage includes secret/payload exclusion, owner denial before reads, nonowner
denial, GET-only requests, redirect rejection, safe upstream failures, lease
and observation freshness, incomplete counts, precise human gates, and budget
accounting preservation. Live projection replay validates the DTO against
current database rows without copying credentials or publishing them.
