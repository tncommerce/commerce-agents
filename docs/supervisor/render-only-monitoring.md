# Render monitoring without Gmail recovery

## Existing path and remaining coverage

The `main` reader and watchdog dispatch the already trusted
`dufynd-private-observer.yml` on `scentai-mvp` without inputs. Its default is now
`mode: render`. GitHub's [workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
uses configured defaults when inputs are omitted; the harness also defaults to
`render` when its mode environment variable is absent.

This path uses the existing broker, workload OIDC identity and active Render
credential. It makes exactly two broker GETs: the fixed API deployment endpoint
and `/v1/health`. Health reads local Gmail credential metadata; it does not refresh
OAuth, read a Gmail thread or acknowledge a cursor. The successful artifact and
its separate ingestion job contain no Gmail message evidence. The established
full-provider capture/ACK/finalize chain requires an explicit `mode: all`.

The currently allowed private service remains API
`srv-dakpfrnf3r2c73dr3f20`. Storefront `srv-dakpiajl550s73cp4lvg` is still outside the
broker's exact Python/SQL credential allowlist. Public storefront liveness is a
separate signal and cannot certify its deployment SHA. This change neither adds a
private storefront observer nor claims complete private coverage.

Existing GitHub schedule delivery has had multi-hour gaps. A successful new read
proves that run's observation; it does not establish reliable two-minute cadence.
The existing stale thresholds remain unchanged. No new scheduler, paid runner,
Cloud Run deployment, secret, IAM grant or alternative dispatch credential is
introduced.

## Durable observation contract

`capture_dufynd_render_observer_read_v1(source, health, evidence)` is a private,
security-invoker RPC. It uses the existing supervisor advisory lock and capture
normalizer. The workflow's OIDC read job has no Supabase secret; its separate
ingestion job has no OIDC/provider credential.

The function validates exact repository/owner IDs, branch, workflow, event,
source SHA, positive run ID and attempt, bounded filtered evidence and the one
allowed service. Existing activation and provider-health gates remain mandatory.
The existing health projection, API capture and private receipt commit atomically;
a later rejection rolls back the health projection as well.

The broker sets Render `last_health_check` immediately after the actual Render
provider GET. That finite, nonfuture timestamp must be within the existing five
minute credential window. It becomes API `last_success_at`, rather than the
later ingestion time. Gmail's local health timestamp never substitutes for it.
The consumption clock is read after acquiring all required locks.

Only the latest API receipt is retained under
`ops.private_observer.render_capture_v1` in the existing private masterstatus:

- Exact same run, attempt, source and artifact fingerprint: return the original
  `observed_at`, `reused: true` and zero new captures. No credential, observer,
  cursor, event or receipt timestamp changes, even after the receipt becomes stale.
- Same run/attempt with changed evidence, time or source: reject the conflict.
- A later attempt of the same run requires unchanged source identity/SHA and a
  strictly newer actual observation. Earlier attempts are rejected.
- A smaller run ID is conservatively superseded once a larger one is captured,
  including later reruns of that older run. Any observation at or before the
  retained receipt/observer watermark is rejected. This bounded latest-receipt
  rule prevents discarded historical artifacts from renewing freshness.

Successful ingestion reports `render_captures: 1`, `gmail_captures: 0`, `acks: 0`,
`activation_changed: false`, `full_chain_complete: false` and
`business_success: false`. A valid replay reports zero Render captures. The same
atomic capture boundary also protects independent Render recovery evidence from
an explicitly selected all-provider run that fails at Gmail; that workflow still
fails and does not become a successful full-provider run.

## Release and verification

Install additive migration
`20261029104500_dufynd_render_only_observer_capture.sql` before the first new
ingestion. It creates only the private function and its restricted execute grant;
it seeds no receipt or observation. If an automatic post-merge run reaches
ingestion before installation, the missing RPC fails closed. Keep `render` as the
default when resolving an operational failure; reverting to automatic Gmail reads
would violate the recorded recovery pause.

Local evidence: 49 focused PostgreSQL cases passed in the rollback fixture plus
one separate committed capture/second-connection retry case. The latter creates
and removes its own disposable database on the existing local test cluster.
Seventy-four related Python/harness/workflow tests passed, including omitted
input, revoked/missing/expired Gmail metadata, failed Render reads, provenance,
artifact bounds, existing explicit full-provider behavior and failure recovery.
The native PostgreSQL CI job must include
`tests/test_dufynd_render_only_capture_postgres.py`.

The release still requires one new actual Render-only workflow capture and a
readback of the receipt/provider observation time. Natural subsequent runs are
needed before claiming restored cadence. Gmail recovery, missing private
storefront deployment coverage and delayed schedule delivery remain independent
conditions.
