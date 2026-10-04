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

Operational reads include all non-done tasks up to 500, all nonterminal executions up to
200, observers up to 200, and credential health rows up to 50. Counts and any
truncation are explicit. Recent done missions/runs and inbox activity are bounded
history. A partial operational read degrades status rather than showing false
zero/healthy counts. Refresh is not an atomic database snapshot; the DTO states
this and preserves observation timestamps. It never equates read time with a
successful observer wake or an external system check.

Expired/missing worker leases and stale/future heartbeats are not active.
Claims without execution records remain visible.
Durable pending, retryable, waiting and stale executions remain visible even
outside the recent history window. Numeric checkpoint steps are preserved.
`waiting_external` tasks with future approval flags are not current owner decisions.
Revoked/account-mismatched credentials and invalid-grant health reasons produce
explicit reauthorization decisions; ordinary token expiry does not invent one.
Ready tasks with budget
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
and `no-store`. The protected shell is registered in `main.py` and stays fail-closed until
all owner configuration is supplied. Merely shipping this code does not activate
access or establish live acceptance.

## Validation

Run `pytest tests/test_jarvis_dashboard.py` plus repo lint/format and CI.
Coverage includes secret/payload exclusion, owner denial before reads, nonowner
denial, GET-only requests, redirect rejection, safe upstream failures, lease
and observation freshness, incomplete counts, precise human gates, and budget
accounting preservation. Live projection replay validates the DTO against
current database rows without copying credentials or publishing them.

## Content Factory extension boundary (owner directive, 2026-10-03)

The protected, live Control Room V1 remains the first deliverable. Do not create
fake content workers, additional infrastructure, paid dependencies or publishing
commands to anticipate the factory. The current read model identifies workers
by execution/task identity, worker ID, runtime type and handler. Worker transport
and specialist role are separate concepts: a future research, critic or visual
role may run on an existing runtime. Do not hardcode a closed list of content
roles into the Worker Deck. Add specialist-role metadata only when the execution
plane has an authoritative source for it.

Preserve the operational mission states for scheduling and leases. Future
content workflow stages (plan, research, produce, critique, revise, verify,
owner approval, measure, learn) are a separate allowlisted projection, not new
meanings for `ready`, `waiting_external` or `done`. Extend the versioned DTO
additively with a typed content section; never forward raw task/execution
payloads to implement it. The dashboard must show only roles/stages that exist.

Required future factory contracts:

- Stable `content_id`, `campaign_id`, product identity, merchant/offer identity,
  platform, format and hook identifiers connect revisions, assets, content,
  DUFYND visits, product interest, clickrefs, merchant clickouts and available
  affiliate conversion/revenue evidence. Unknown conversion is unknown, not
  zero; attribution and reporting latency remain explicit.
- Each immutable content/asset revision has evidence provenance and a content
  hash. Critic/verifier results bind to that exact revision, product/variant,
  rights evidence and affiliate destination; editing any of these invalidates
  the old approval. Creator identity cannot be its own final checker identity.
  Independence is enforced by the orchestration/authorization layer, not by
  giving the same worker a different display label.
- Product/variant/bottle mismatches, unsupported facts, unclear asset rights,
  wrong affiliate destinations and missing publication gates are hard failures.
  Numeric quality scores cannot override them. Failure leads to a bounded
  revision and a new independent review; unresolved failures go to the owner.
- The first factory phase ends at `READY FOR OWNER APPROVAL`. No publisher
  handler is enabled. Progression is explicit: owner publishing, independent
  critic/QA with owner approval, bounded preapproved auto-publishing, then
  full exception-based operation. No level is skipped by a successful review.
- Optimize the measurable funnel through affiliate revenue, not views alone.
  Preserve costs per asset/video, qualified visits, clickout and conversion
  rates, revenue by content/product/format/source, successful asset reuse,
  weak-format stop signals and evidence-backed learnings. A learning must link
  to its measurement source and uncertainty before influencing later planning.
- Reuse the existing task/execution/event system and controlled read layer.
  New contracts must reduce owner work, have measurable business impact and
  respect the current cost, rights, security and publishing gates.

After protected V1 live acceptance, measurement/attribution comes first (G0),
then conversion/monetization (G1), then the small Content Factory V1 plan and safe
foundation (G2). See [Growth directive](dufynd-growth-directive.md). The notes
above do not activate that pipeline or change the current mission queue.

## Protected owner shell

`/internal/login` submits directly to the existing API. Supabase Auth validates
the signed token and current user on every dashboard request. A narrow boolean
RPC also validates the live session, expiry, deletion, ban and confirmed user.
The configured owner UUID is the only identity authorized to read Jarvis data;
neither email, user metadata nor a generic authenticated role grant access.

The session cookie is encrypted, Secure, HttpOnly, SameSite=Strict and host-only.
No refresh or provider token is stored. Lifetime is capped by access-token expiry
and one hour. Login and logout enforce the fixed production origin and CSRF.
Logout revokes the local Supabase session and clears the cookie; upstream failure
is reported as unconfirmed. Assets contain only presentation code. CSP blocks
inline execution and framing. Dashboard routes are absent from public OpenAPI.

Activation requires `DUFYND_CONTROL_ROOM_ENABLED=1`,
`DUFYND_CONTROL_ROOM_OWNER_ID` (confirmed Owner Auth UUID),
`DUFYND_CONTROL_ROOM_AUTH_KEY` (publishable/anon key),
`DUFYND_CONTROL_ROOM_SESSION_KEY` (dedicated Fernet key), and existing server-only
`SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY`. Optional
`DUFYND_JARVIS_BUDGET_ID` selects the existing budget window; absent data stays
unknown. Apply the owner-session migration before enabling. Never send keys or
passwords through chat or embed them in frontend bundles. The owner creates
their own account; do not insert users directly or invent account credentials.

Acceptance: authenticated owner loads the real endpoint; nonowner, missing,
expired, forged and revoked sessions cannot trigger reads; cookie protections,
CSRF and origin tests pass; real worker, task, observer, gate and budget states
match live sources, with stale/incomplete history labeled. On read failure the UI
keeps the last observation with an explicit unavailable warning and unknown
current supervisor status. There are no task, spend, publish or outbound controls.


## CEO Control Room V0.1 (2026-10-04)

Reuses the protected API shell and existing owner session without credential or
Auth configuration changes. Read-only additions: fresh Thin-loop WORKING / WAITING /
OWNER GATE / ERROR, concrete owner action, current execution, last-loop stop reason,
next selection estimate, pending human decisions with scalar reason/risk/cost/benefit
and exact scoped GO token, authoritative loop queue counts, CI bound to observed
branch SHA, smoke bound to that same SHA, leases/reservations, daily provider cost,
First-Money publication observation and exact-content product analytics, and the
four money-product business checkpoint states. There are no approval buttons.

Publication is a stored connector observation with timestamp and stale marker,
not a continuous platform poll. Analytics are unique event-ID counts and distinct
session hashes for the exact 1 Million product/content; hashes and IDs never reach
the browser. Detail views, offer impressions and clickouts are distinct. The first
readiness test may be included; no metric claims organic traffic. The bounded read
shows lower bounds if incomplete. Transactions and commission remain unknown until
a network reporting source exists; purchase verification is not a sale. Business
product states are checkpoint observations, not catalog activation assertions.

Daily costs use the Europe/Berlin calendar day of dispatched provider reservations.
Only settled actual costs are totaled. Unsettled, charged-max or missing settlement
costs remain unknown. The daily number includes earlier activity, not just this
free dashboard task. Open-cost rows are checked separately across dates. Missing
budget window remains unknown. Fixed GET reads run with six concurrent requests;
refresh remains every 10 seconds while visible, with manual refresh and explicit
failure/stale state. Missing/truncated decision or runtime reads cannot claim a
complete healthy overview. Verified completed checkpoints supply the quiet activity
list; no synthetic worker stations or noisy inbox logs are promoted as completed work.

## CEO Control Room V0.6 (2026-10-04)

The original Sentinel scene and CSS core replace generic visual decoration without
external artwork, image generation, WebGL or additional production dependencies.
Desktop separates the central Jarvis state, current execution, First Money and
costs from the workstream orbit, candidate queue, dependencies and verified feed.
Mobile orders status, owner gates, First Money and costs before execution detail.
Only actual pending decisions trigger the sticky red owner alert. Unknown gate
completeness remains amber; external waiting is monitoring, not active execution.

Additive allowlisted DTO fields include workstreams, ready candidates sorted by
actual priority, categorized waiting counts, CEO status, and a verified feed from
completed checkpoints and successful system observations. Candidate order is
explicitly not a handler execution promise. Workstream cards show observed task
counts, not invented completion percentages. Domains without authoritative tasks
show NO DATA. A historical checkpoint is not a live worker or a new completed task.

The service-only STABLE `read_dufynd_first_money_runtime()` GET supplies bounded
scalar phase and purchase-evidence metadata. Its raw object, source breakdowns and
session identifiers never reach the browser. The seven-stage funnel distinguishes
publication, sessions, product details, offer views, clickouts, transactions and
commission. A scheduled post is READY, never a published stage. Analytics can
include readiness tests. Transactions and commission remain UNKNOWN until actual
network evidence is ingested. Missing budget numbers remain UNKNOWN, not zero.

Motion uses CSS orbits, ambient light, reconciled feed entries and short text
transitions, with no animation under prefers-reduced-motion. The visible page
retains the existing bounded 10-second read interval and stops when hidden. Auth,
owner allowlist, encrypted cookies, noindex, CSP and GET-only read boundaries are
unchanged. There are no new write controls, paid calls, scheduling changes,
merchant mappings or catalog changes.

Local validation: 2,879 tests passed (162 environment-dependent tests skipped),
repo consistency, ruff lint/format and JavaScript parse passed. Isolated browser
replay of live allowlisted data passed at 390/430/768/1440 pixels without horizontal
overflow or page errors. Separate browser fixtures validated zero gates, a real
pending-gate shape, working execution, missing data, unavailable reads and reduced
motion. These fixtures never enter production. Browser replay does not certify a
live signed-in owner session; deployment and anonymous route denial are separately
verified against the deployed service.
