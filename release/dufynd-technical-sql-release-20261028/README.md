# DUFYND technical SQL release packet — 28 October 2026

## Scope and verification

This packet covers only the two observer/planner migrations:

- `20261028081434_jarvis_private_observer_stale_truth.sql`
- `20261028082303_jarvis_planner_technical_blockers.sql`

It contains no commerce migration, OAuth action, provider invocation, task creation,
cron change, RLS change, Auth setting change, or price update. Production DDL has
not been executed by the preparation agent. Apply only after the release
coordinator has verified the required CI on the selected release revision and
the existing production/cost authorization.

The release coordinator supplied a fresh, successful small live-catalog query.
The three original definitions in `baseline-functions.json` match its exact
`pg_get_functiondef` MD5s, owner, ACL, volatility and `search_path`. The new
technical helper was confirmed absent. The poll definition came from the saved
production response; the two planner definitions were reconstructed from the
committed October 21 migration and canonicalized to the same live fingerprints.

| Existing function | Verified original definition MD5 |
|---|---|
| `poll_dufynd_observers()` | `b16099ccc4633cafb48dcb81044738ad` |
| `read_dufynd_safe_work_exhaustion_v1()` | `9b85321f0afb551ceb44700ab458eff7` |
| `plan_dufynd_free_work_v1()` | `0fb393ff9dcd50376772556c73a6d07d` |

All three original functions are owned by `postgres`, are security invokers,
have `search_path=public`, and permit execution only to `postgres` and
`service_role`: `{postgres=X/postgres,service_role=X/postgres}`.
`expected-functions.json` contains the four exact resulting definitions and
fingerprints. Source migration SHA-256s are in `release-manifest.json`.

## Ordered application

1. Read current catalog state and execute `preflight-guard.sql`. It refuses
   changed definitions, owners, ACLs, volatility, search paths, or an existing
   technical helper. Recheck close to application; a previous pass is not a
   lock across requests.
2. Apply `apply-observer-body.sql` inside the first migration transaction.
   It repeats the relevant guard, uses the existing planner/supervisor advisory
   locks, applies the unchanged observer migration and verifies the result.
3. Apply `apply-planner-body.sql` inside the second migration transaction.
   It requires the verified new observer function and the original two planner
   definitions, then applies the unchanged planner migration and checks all four
   resulting definitions and ACLs.
4. Read the compact results of `postflight-read-only.sql`. Do not execute the
   planner or poller solely to make a test observation. Inspect the next natural
   cron result separately. The diagnostics may correctly remain degraded while
   Render or Gmail evidence is stale, blocked, incomplete, or inconsistent.
5. Recheck security advisors once after the DDL. Compare with the recorded
   baseline: 50 policyless RLS tables, two unchanged Nightshift procedure
   search-path notices, and existing leaked-password protection status. These
   migrations must add no public execution privilege or definer RPC.

The body files require an enclosing migration transaction; their `SET LOCAL`
and advisory locks must remain active through the postcondition checks. They
are prepared for the normal Supabase migration operation. Do not run the body
statements separately with autocommit. Keep migration history consistent with
the exact two applied source migrations.

## Rollback

`rollback.sql` is a complete transaction. It accepts the known original or new
fingerprint for each existing function, so it supports both a partial release
(first migration only) and the complete release. It refuses unknown later
function definitions or changed permissions. It restores the exact three
original definitions, removes only the newly introduced technical helper, and
checks all original fingerprints, permissions and helper absence before commit.
It does not use `CASCADE` or delete migration history. Record a corrective
rollback migration through the release coordinator if rollback is used.

Only function definitions are reverted. Historical observer snapshots, cursors,
success timestamps, tasks, masterstatus rows, cron results and completed business
actions are not rewritten by rollback.

## Additional packet verification

The existing 29 PostgreSQL regressions were not repeated. The new release packet
was checked in a disposable PostgreSQL 16.15 transaction with six focused cases:
original-state preflight, unknown-definition rejection, guarded observer apply,
partial-release rollback, combined guarded apply, and complete rollback. Every
local change was rolled back. Full and partial rollback restored the exact
original MD5s and ACLs. See `release-packet-validation.json`.

Production uses PostgreSQL 17.6.1.166. Matching original canonical fingerprints
supports the definition comparison; local packet checks are not claimed as
production-version CI certification. The preparation agent's own live MCP call
timed out; the successful small live query was performed by the release
coordinator. No fresh advisor result is claimed in this packet.
