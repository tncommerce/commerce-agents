# DUFYND technical, security and Jarvis delta — 28 October 2026

## Scope and production boundary

Production baseline: `36cc84c34791284e4245ab4504ae020434dca89e` on
`tncommerce/commerce-agents:scentai-mvp`. No merge, Render deployment, paid
service, AI-provider activation, merchant clickout, email, social post or price
refresh was performed. Existing successful CI/QA runs were reused.

The operational monitoring reconciliation below **was applied** after independent
review, four real PostgreSQL regression cases and an immediate GitHub production
SHA check. All application/workflow and SQL-function changes in this draft remain
**undeployed**. Operational correctness is not equivalent to a successful business
action or a recovered Gmail connection.

## Applied: bounded monitoring metadata correction

Applied at **2026-10-28T08:15:50.206067Z** to the existing Supabase project.

- Retired observers `github_pr:623`, `github_pr:625`,
  `github_ci:37016647384`, `github_ci:37033948872`.
  Each has a terminal source snapshot and no active dependent work. Historical
  snapshots, cursors and success times are preserved.
- Registered current PR observers **802, 823, 837, 840** through the existing
  registration function. Each begins `initializing`, without an invented success
  time or source cursor. The polling interval is 1,200 seconds, with staggered
  first requests. Repeating the correction does not delay an existing observer.
- Corrected the Render observer from `healthy` to `stale`. Its original last
  successful capture remains **2026-10-22T19:22:47.420333Z**, with the original
  deployment and SHA. The current production release is independently verified
  through Render; it was not fabricated as a private-broker capture.
- No task, execution, credential, cron definition, database schema, price or
  production branch was changed.

The SQL uses the existing supervisor advisory lock and aborts atomically if the
production baseline or terminal/consumer guards fail. See
[reconcile-monitoring.sql](reconcile-monitoring.sql). New PR observations are
verified through the existing natural cron, not through a forced success write.
Final readback confirms **all four** new observers healthy at the expected exact
PR heads: #840 at 08:20 UTC, #823 at 08:22, #837 at 08:26 and #802 at 08:30.
These are successful PR reads, not successful worker/business actions. The
operational readback still shows zero executable/active tasks, 14 external waits,
three blocked Gmail observers and zero executions since the production release.
All 12 existing cron schedules remain active with no failed cron execution in
the inspected period. The live planner still uses its prior classification until
the draft migration is explicitly released.

## Draft: independent Render recovery after Gmail failure

### Confirmed failure

The private observer reader obtained Render deployment evidence, then failed on
a revoked Gmail credential before persisting the health/evidence artifact.
Consequently, a successful Render read was discarded. The all-provider acceptance
chain correctly refused to claim full success, but Render monitoring stopped
advancing as a side effect.

### Proposed behavior

1. Keep the original failed read and failure receipt.
2. If bounded Render evidence is already available, perform one health read and
   save a strictly validated Render-only recovery artifact.
3. On the failure-report path, validate repository, workflow, production ref,
   run ID, source SHA and the **actual run attempt** before any projection.
4. Project bounded credential health without changing activation, then call the
   existing recurring-capture RPC. It still requires an already active Render
   credential, the fixed allowed service and fresh health.
5. Record exactly one Render capture, zero Gmail captures, zero acknowledgements,
   no activation change and `full_chain_complete=false`.

The original read/ingest/ack/finalize dependency chain remains unchanged. A Gmail
failure still makes the full workflow fail. Recovery cannot authorize first-time
activation, read a new mailbox/thread, acknowledge Gmail, or count a business
action.

The reader and ingester both reject extra payload fields, wrong resource IDs,
unbounded lists, invalid metadata/status/timestamps, foreign provenance and stale
attempts. Old local artifact files are removed before a new attempt. Artifact
names include run ID and attempt. The existing failure artifact is reused;
there is no additional scheduled workflow or artifact count.

## Draft: persist private-observer staleness truth

`20261028081434_jarvis_private_observer_stale_truth.sql` changes only the
source-type predicate of the exact live `poll_dufynd_observers()` function.
The existing age check is extended from GitHub to Render/Gmail. A successful cron
does not make old provider evidence fresh. Existing credential blocking,
private-broker-only access, signatures, permissions and capture behavior remain
unchanged.

The live metadata correction alone does not install this durable fix.

## Draft: technical work remains visible to the planner and Jarvis

The stable read-only classifier in
`20261028082303_jarvis_planner_technical_blockers.sql` reads actual private-observer
freshness, blocking, production revision agreement and acceptance/finalization
evidence. A recent cron or begun acceptance cannot satisfy these checks.

A complete private chain requires `activated`, an ordered/plausible
`finalized_at`, the current verified production SHA and coverage of every enabled
private observer. The existing finalization RPC requires the Gmail acknowledgement
proof before setting that status. An absent acceptance is described as an
**acceptance gap**, not proof that the scheduler stopped running.

Business work exhaustion is now separate from remaining technical work. With an
otherwise empty queue and technical blockers, the proposed planner returns
`technical_remediation_required`, `operational_state=degraded` and
`technical_repair_executed=false`. Existing runnable work, active leases and
owner gates keep priority. No task is invented to make the queue look busy.

The existing Operator/Dashboard consumer recognizes this state and displays
**TECHNIKARBEIT OFFEN**. Its recommendation does not claim current execution or a
completed repair. Actual active/ready work also keeps precedence in the displayed
recommendation. No visual design was changed.

See [the planner and operations handoff](../../docs/tech/jarvis-technical-blocker-truth-20261028.md).

## Security and privacy integration

| Existing PR | Exact head | Reused evidence |
|---|---|---|
| [#840](https://github.com/tncommerce/commerce-agents/pull/840) | `833feefcd6e4c525ef83fcd0a3a3f9f9b72629f3` | [CI 40496435977](https://github.com/tncommerce/commerce-agents/actions/runs/40496435977), six required jobs successful |
| [#823](https://github.com/tncommerce/commerce-agents/pull/823) | `a9a8220d503d7db2bacfe1f4319188ca813878fa` | [QA 40645190771](https://github.com/tncommerce/commerce-agents/actions/runs/40645190771), 178 responsive checks; eight changed source blobs match |
| [#837](https://github.com/tncommerce/commerce-agents/pull/837) | `43b2793c754f18b47c335fef0f7348b77f22029e` | [CI 40591804637](https://github.com/tncommerce/commerce-agents/actions/runs/40591804637), 163 Python/PostgreSQL checks; nine source/SQL/test blobs match |

The two website patches share the current production base and have disjoint file
changes. The remaining integration question was tested locally against their
**combined** application tree `2dc1be16bed72993b437f9fbde513299d1e5d46a`:

- Clean dependency install; resolved Next.js 16.4.3, Sharp 0.35.5,
  librsvg 2.63.2 and source-map-js 1.2.2.
- Production compile/typecheck and 105-page static export.
- Export privacy gates and **55 metadata checks** passed.
- **21 real Chromium cases** passed: four late-consent/withdraw/regrant widths,
  two cases without IntersectionObserver, and 15 conversion/search cases.
- Zero external requests sent, zero merchant clickouts, zero page errors.
  288 external attempts were blocked. Images were not redownloaded or visually
  recertified. API data was an isolated local fixture.

See [the full integration evidence](../../artifacts/dufynd-security-privacy-integration-20261028/README.md).
The prior 178-page suite and successful remote CI were not rerun. Local combined
verification does not replace required checks on a future chosen release SHA.

The production storefront is a static export; the checked deployment has no
Next.js image-optimization server endpoint. The dependency update is appropriate,
but this audit does not establish a demonstrated live exploitation path.

[#802](https://github.com/tncommerce/commerce-agents/pull/802) remains the separate,
default-off Gmail credential-refresh proposal. It has no file overlap with this
failure-isolation change. Neither proposal proves a completed Gmail ingest/ack/
finalize recovery. No OAuth recovery loop was started.

## Supabase exposure audit

The current advisors report 50 policyless RLS tables, two mutable search paths,
and disabled leaked-password protection.

### Policyless RLS

All 50 reported tables have RLS enabled. Eleven retain broad SQL grants for
`anon`/`authenticated`, but those roles are neither superusers nor BYPASSRLS
roles. With no applicable policy, RLS denies row access. The audit found no
publicly callable SECURITY DEFINER function or non-invoker public view that
bypasses this boundary, and neither public role can CREATE in the public schema.

No blanket policy creation or opening of private tables is justified. Unused
broad grants can be considered separately as defense in depth. No RLS, grant or
Auth setting was changed.
[Advisor explanation](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).

### Nightshift procedures

`public.dufynd_ns_v1_cycle()` and `public.dufynd_ns_v1_pilot_abort()` are
SECURITY INVOKER **procedures**, executable only by `postgres`
(`{postgres=X/postgres}`). Public API roles cannot execute them. Called helpers
are schema-qualified. Both procedures use transaction control.

Attaching a procedure-level `SET search_path` is not a safe mechanical repair:
PostgreSQL prohibits transaction control from a procedure with a SET clause.
A disposable native PostgreSQL reproduction confirmed that the same procedure
could COMMIT before the SET clause, and raised **SQLSTATE 2D000** afterwards.
No production procedure was altered. A future change must preserve transaction
boundaries or explicitly retire the obsolete procedure.

Live definition MD5s:
- cycle: `cc158747c58b5a3282da8de8d39859fe`
- pilot_abort: `f9da986d0b8ae6bd9c4a901613d02a70`

[PostgreSQL procedure restrictions](https://www.postgresql.org/docs/current/sql-createprocedure.html).
[Advisor explanation](https://supabase.com/docs/guides/database/database-linter?lint=0011_function_search_path_mutable).

### Password protection

The connected organization is on `free / tier_free`. Supabase leaked-password
protection is a Pro-and-above feature. It remains unavailable under the explicit
zero-extra-cost constraint. No upgrade or unsupported setting change was made.
[Official password-security documentation](https://supabase.com/docs/guides/auth/password-security).

## Render, SEO and evidence limitations

Both live Render services were verified at production SHA `36cc84c3…`:
API deployment `dep-dbg7cgl9fdbs73d0b2p0` and storefront deployment
`dep-dbg7q54s728c73dklukg`, both released on 27 October.
API service: `srv-dakpfrnf3r2c73dr3f20`; storefront service:
`srv-dakpiajl550s73cp4lvg`. Both have preview generation disabled and
`pullRequestPreviewsEnabled=no`.

For the inspected window, 27 October 10:30:34 UTC to 28 October 08:00 UTC:
API HTTP metrics show 58 responses with 200, four with 404, one with 499, and no
5xx. The reviewed error/critical log queries returned no incident; no restart,
out-of-memory or failed deployment was found. Peak API CPU was 0.001772 of 0.5
cores; peak memory was 111,181,820 of 536,870,900 bytes. One instance was running.
Missing static-site and p95 metrics are not interpreted as zero latency/errors.

The API's `healthCheckPath` is empty, leaving a TCP-level readiness check.
`/api/health` returned 200 in the audit. Configuring an HTTP health-check path
is a concrete release action, held behind the deployment/cost authorization
boundary. Both services have commit-based auto-deploy enabled. The API health
payload's 125 backing/demo products is not the 37-profile public catalog count.
The route proves application liveness, not full dependency or worker readiness.

Public robots.txt, sitemap and index were reachable. Two representative product
profiles had consistent indexability/canonicals. Slash variants returning 200
with a slashless canonical are a plausible benign alternative-page pattern,
not proof of which URLs triggered the Search Console notice.

The connected Windsor Search Console source explicitly returned **placeholder
data** because four connected accounts exceed the Free plan's one-account
allowance. Those responses are not genuine traffic, impression, click or sitemap
measurements. No invented zero-traffic conclusion, upgrade, account disconnect
or OAuth attempt was made. The exact URLs behind the 25 October canonical
notice remain unverified.

## Commerce and external dependencies

PR #837 remains a batch proposal for up to 50 offers, without a production
migration or a confirmed Top Parfümerie Enhanced feed. Existing 163-case evidence
was retained. No single-product loop, invented price freshness or merchant
clickout was performed.

The existing feed-request Gmail draft was not sent. The ten historical
Top-Parfümerie offer proofs still expire on **29 October 2026, 13:41–16:19
Europe/Berlin**, unless supported by a new original check. Source age must trigger
the existing safe HOLD behavior; this technical audit does not renew those
proofs. Safe expiry handling in a draft commerce change must not be mistaken for
an already deployed new runtime mechanism.

## Verification and release gates

- 86 focused Python tests passed for reader, ingestion, recovery, failure,
  finalize, acknowledgement, workflow and credential compatibility.
- 10 focused Operator/Dashboard tests passed, including the new technical-state
  projection and preservation of real active/ready work. The isolated existing
  owner-auth denial test also passed with local socket permission. An initial
  broader dashboard attempt stalled at that TestClient boundary in the restricted
  sandbox; no full dashboard-suite success is claimed.
- **29 native PostgreSQL regression tests passed together** on the migrated
  disposable schema: four reconciliation cases, seven private-observer
  freshness/permission cases and 18 planner cases. A referenced budget fixture
  verified compatibility with existing foreign-key evidence.
- Independent reviews found no remaining blocking issue in the recovery,
  staleness, planner and consumer deltas.
- Local PostgreSQL is **16.15**; production is **17.6.1.166**. Local results are
  not described as production-version CI certification.
- Required branch checks remain `web`, `python (3.11)`, `python (3.12)`,
  `no-pypi-fallback`, `budget-postgres`, `private-broker-container`, plus
  resolved review threads. Local evidence does not override branch rules.
- Remote CI is intentionally not dispatched for this draft. Any release must
  select its exact combined SHA, satisfy required checks and obtain explicit
  production/cost authorization before merge or deployment.

The final readback, planner delta and evidence index are recorded alongside this
report and in the existing Supabase master-status table.

