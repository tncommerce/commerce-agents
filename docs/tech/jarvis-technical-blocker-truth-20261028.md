# Jarvis technical blocker truth and operations evidence — 2026-10-28

## Scope and resulting behavior

The planner previously inferred global exhaustion from completed commerce/content
work. That inference could hide stale Render evidence, expired Gmail credentials
and an incomplete private observer execution chain. The draft migration keeps the
reviewed commerce logic and adds a stable, read-only technical classifier. A
commerce wait remains `waiting_market_signal` only when the technical evidence is
also current. Otherwise the planner records `technical_remediation_required`,
`operational_state=degraded` and `technical_repair_executed=false`.

Existing ready work, active leases and owner gates retain precedence. No synthetic
task, new schedule, network call, OAuth attempt or paid execution is introduced.
The helper does not call the writing integrity audit, avoiding recursion back into
the exhaustion reader. An inbox `idle` state and successful cron invocation remain
distinct from operational readiness and verified business outcomes.

The classifier uses enabled private observer status and successful-read freshness,
a fresh GitHub production revision, observed Render revision agreement, and
broker acceptance evidence. An acceptance session is a complete capture only when
activated, finalized at a valid timestamp, bound to the current production source
revision, and covering every enabled Render/Gmail observer. `captured`, partial,
failed, unfinalized and wrong-revision receipts cannot prove completion.

`last_acceptance_started_at` and `private_broker_acceptance_gap` describe acceptance
records only. A failed reader can execute without creating one, so this code does
not infer a scheduler outage from missing acceptance rows. The independent capture
completion gap remains visible even when acceptance starts repeatedly.

## Verification

The new module `test_dufynd_planner_technical_blockers_postgres.py` executes the real
migration in disposable local PostgreSQL. It covers healthy wait preservation,
stale-success despite a healthy label, expired configuration, Render revision
mismatch, missing/stale/future evidence, acceptance gaps, failed/partial/unfinalized
captures, wrong source revisions, existing-work precedence, ACL preservation and
idempotent reapplication. All fixtures and function replacements roll back.

## Read-only Render evidence

Observed 28 October 2026 at approximately 08:00 UTC (09:00 Berlin), queried from
27 October 10:30:34 UTC through 28 October 08:00 UTC. Workspace `TNCommerce`;
request-scoped ID `tea-dakp99gu01pc73fvp6f0`.

| Service | ID | Current live deployment |
| --- | --- | --- |
| API | `srv-dakpfrnf3r2c73dr3f20` | `dep-dbg7cgl9fdbs73d0b2p0` |
| Storefront | `srv-dakpiajl550s73cp4lvg` | `dep-dbg7q54s728c73dklukg` |

Both live deployments use `36cc84c34791284e4245ab4504ae020434dca89e`. No new
failure/restart/OOM event was returned after the successful release. Both services
use `autoDeploy=commit` for `scentai-mvp`; preview generation is `off` and
`pullRequestPreviewsEnabled=no`. Branch publication outside production does not
change the linked production branch.

API resource samples (15-minute resolution): maximum CPU 0.001772 cores against
0.5 available; maximum memory 111,181,820 bytes against 536,870,900 bytes; one
instance throughout. Sampled memory uses about 20.7% of the limit. No capacity
upgrade is justified by these readings. HTTP counts: 58 responses 200, four 404,
one 499, no 5xx. These are requests, not visitors or commercial conversions.
Error/critical logs and filtered 5xx logs returned empty, with no additional page.
The static site's HTTP metrics and API latency quantiles returned no data;
therefore no frontend error rate or p95 claim is made.

The API's configured `healthCheckPath` is empty, leaving TCP-only platform checks.
`GET /api/health` was verified HTTP 200 in 0.194 seconds from the audit host. It is
an application liveness endpoint, not proof of all dependencies or worker success.
Its `products=125` counts the backing demo catalog, not the 37 public fragrance
profiles. No Render manifest exists in this repository; the future configuration
change `healthCheckPath=/api/health` must be reviewed/applied to this existing
service with the release authorization. No live setting was changed here.

Service evidence: [API dashboard](https://dashboard.render.com/web/srv-dakpfrnf3r2c73dr3f20),
[storefront dashboard](https://dashboard.render.com/static/srv-dakpiajl550s73cp4lvg).
Platform behavior verified against [health checks](https://render.com/docs/health-checks)
and [deployments](https://render.com/docs/deploys).

## Bounded SEO delta and actual Search Console access

Read-only GETs of `https://dufynd.de/robots.txt`, `sitemap.xml`, the homepage and
two representative fragrance profiles returned 200 with consistent apex HTTPS
canonicals. `www` and HTTP requests redirect to HTTPS apex. The trailing-slash
Rabanne profile also returns 200 and names the slashless URL as canonical. This
is a valid alternate-URL candidate, not confirmation that it is among the URLs
in the 25 October Search Console notice. Product JSON-LD for the checked profiles
contains identity/brand/variant information without inventing Offer prices or
ratings. No merchant clickout or browser analytics event was generated.

Windsor discovers connected Search Console account `sc-domain:dufynd.de`, but both
Search Analytics (25–27 October) and Sitemaps reads are blocked by account limits:
four accounts are connected while its Free plan supports one. The provider
returns placeholder zero-valued rows explicitly marked “not your real numbers.”
These are not traffic or indexing metrics and must not be ingested as valid
measurements. No plan upgrade, account disconnection or OAuth flow was performed.
Affected canonical-warning URLs remain unverified pending an original GSC export
or an already-authorized direct access path.
