# Independent Private Observer recovery entry — source-only

The existing GitHub five-minute reader and ten-minute watchdog share the same
schedule-delivery failure domain. In the verified 24-hour window ending
2026-10-31T08:41:11Z, only 15 schedule runs were created. Their combined median
gap was 90.46 minutes and maximum gap 201.35 minutes. Three naturally scheduled
chains nevertheless dispatched successfully and captured both Render services:
41174081947 → 41174088807; 41178756687 → 41178763148;
41185606656 → 41185614100. The last pair of database receipts was accepted at
08:41:59Z and independently reread at 08:44:44Z. No rerun of those chains is
needed to establish the already proven broker/OIDC/ingest behavior.

## Finished implementation

The new manual-only `dufynd-private-observer-recovery.yml` entry lives on `main`.
It defaults to `execute=false`. It has no cron, push, workflow_run, repository
dispatch or public endpoint. An independent caller can eventually invoke its
existing GitHub workflow_dispatch API or UI; this draft creates no caller.

The entry runs a standard-library Python guard. It validates repository and
owner IDs, public-repository identity, workflow path/ID, main ref, commit, run
ID and attempt, the original UTC times, and complete bounded recovery history.
All three existing V2 gates must be exactly `1`. The sole possible write is:

```json
{"ref":"scentai-mvp","inputs":{"mode":"render_services_v2","capture_v2":true}}
```

It targets only the existing `dufynd-private-observer.yml` workflow. Neither
provider credentials nor a Google identity leave their current boundaries. The
child continues to obtain its own existing GitHub OIDC token with the pinned
issuer, audience, owner/repository identity and scentai-mvp workflow ref. There
are no changes to Cloud Run revision 00011-vlv, europe-west3, IAM, OIDC trust,
secrets, Supabase DDL, image approval, merchant data or deployments.

## Boundaries and failure behavior

- A recovery rerun (`run_attempt != 1`) cannot dispatch. Concurrency serializes
  the recovery entry without canceling an active attempt.
- Any observer attempt younger than 15 minutes suppresses recovery, including a
  failed attempt. Active observer runs also suppress it. A recently listed
  active run older than 30 minutes blocks for inspection rather than stacking
  additional work. All five active API states are checked separately so old
  queued/waiting runs outside the first history page cannot be missed.
- A final observer reread immediately precedes dispatch. The native scheduler
  can still race after this read: cross-workflow exactly-once execution is not
  claimed. The child retains its existing concurrency, provenance, replay
  rejection and idempotent ingestion boundaries.
- A 15-minute entry cooldown and ceilings of five entries per rolling hour and
  97 entries per rolling day count **all** recovery invocations, including
  dry-run/no-op/failed/unknown attempts. The independent caller must therefore
  invoke no more often than once per 15 minutes. No-op invocations cannot starve
  a caller honoring that contract. Faster callers fail closed.
- Maximum 12 HTTP requests per entry, each with a 15-second timeout and 4 MiB
  response cap. Fixed GitHub origin, no redirects, no token logging. Rate-limit
  headers must prove sufficient budget; Retry-After blocks further work. There
  is no retry or polling loop, especially after POST uncertainty.
- GitHub API version 2026-03-10 returns an exact dispatch run ID and URLs. All
  are validated; the exact returned run is read once. A timeout or ambiguous
  POST failure consumes the attempt and is reported as unknown, never retried.
  A failed child readback preserves the validated dispatch receipt. An accepted
  dispatch never claims a successful capture or restored cadence.
- Bounded JSON receipts are printed into the existing job log and written to
  the ephemeral runner directory. No new artifact uploads or paid resources.
  The child continues to produce its existing provenance-bound database receipts.

## One production activation blocker

**No independently scheduled caller has yet been verified to invoke this entry
through already approved GitHub access at provably zero incremental end-to-end
cost.**

Until that single operational requirement is evidenced, keep this PR unmerged
and do not create/activate any external schedule. A future approved caller must
use the fixed repository/workflow/ref, `execute=true`, at most every 15 minutes;
it must not copy provider tokens, request expanded IAM, or expose a public
endpoint. Existing Cloud Scheduler is disabled; Google-signed OIDC cannot be
substituted for the broker's exclusively GitHub-signed workload identity.

After activation, success requires multiple **natural** caller → recovery →
exact child-run → both V2 database-receipt chains at the documented interval.
One manual run, HTTP 200, or a green recovery job is not that proof. Gmail's
separate revoked credential remains outside this repair.

## Validation

Offline tests cover valid dispatch, dry-run, all gate permutations, malformed
repository/run/history identities, stale and future timestamps, old active
runs, concurrent native arrival, replay/rerun, cooldown and rolling ceilings,
API timeout/rate limits/redirects, exact receipt identity and unchanged workflow
permissions. Normal PR CI must pass on the final draft head. No live dispatcher,
broker run, database write, credential or schedule is used by these tests.

Primary API contract:
https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event

Scheduling limitations:
https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
