# Jarvis source-change deduplication — development only

Production base: `7b793cf7ce1223967e66d768fcb7930ecdfc0e40`.

Current release handoff: [guarded migration and rollback packet](../release/dufynd-jarvis-source-dedupe-20261026/README.md).
The original migration is unchanged. Native PostgreSQL verification subsequently
passed in [CI run 40303294857](https://github.com/tncommerce/commerce-agents/actions/runs/40303294857)
(233 PostgreSQL tests, including the 31 assertions below). The continuation adds
only the release packet and 28 offline release/rollback assertions; it does not
repeat the scheduler implementation or the successful native CI.

The live business planner uses an hourly `bizplan:social-truth:YYYYMMDDHH24`
identity while the existing runtime deliberately reports
`publication_verified=false`. Read-only inspection on 26 October 2026 found
the same audit family created and completed every hour, including 01:00–08:00
UTC. The saved read-only evidence at 08:48:58 UTC contains nine audits that day
and the eight latest exact task IDs/timestamps. These rows prove hourly task
creation, not an unchanged external-event history across all eight hours.
The newer external-signal planner already reports waiting for a merchant
clickout; it does not remove this lower-level task generator. Existing planner
branches/migrations were inspected before creating this isolated delta.

The proposed migration replaces only the business planner and adds one private
source-projection helper. A fingerprint of cumulative launch-attributed buyer
events, material merchant facts, exact-content platform observations and
publication proof fields is compared with the last queued audit in the existing
master-status table. The original runtime, event filters, safety/freshness
handlers, publication truth and permissions stay intact. No task is marked done
or revived by deduplication.

Clock phases, the current observation time, merchant refresh timestamps and
workflow bookkeeping do not trigger another audit. Canonical array ordering
prevents equal-time events or provider ordering from generating work. Unknown
partial publication proofs remain unknown. New real source changes queue the
existing certified audit; chaining the previous task ID also preserves A→B→A
changes. The existing advisory transaction lock makes task insertion and the
checkpoint atomic. First installation performs one bounded baseline audit.
Failed/blocked work continues through existing retry and gate mechanisms.

The certified `supervisor_state_audit` payload is unchanged: only `kind`,
`steps=1` and `interval_seconds=2`. Existing independent daily creative-recovery
planning remains unchanged. The analogous funnel audit uses the same dedupe
rule, so a later verified publication cannot merely move the hourly loop.

## Verification

- **31 SQL assertions passed** in local PostgreSQL 17.5 compiled to WASM
  (`@electric-sql/pglite@0.3.14`), using the original supervisor and content
  workflow migrations/constraints. The migration was applied twice to the
  disposable fixture. No production connection was used.
- Actual SQL execution covers 24 polls with changed observation-time inputs
  (not 24 elapsed hours; PostgreSQL `now()` remains fixed inside the test
  transaction), unchanged checkpoint bytes,
  completed-task preservation, buyer changes/replay, merchant price and stock
  changes, identical merchant refreshes, A→B→A, publication proofs, workflow
  bookkeeping, platform transitions, owner/active-work gates, zero-spend
  fields, ACL/invoker rights, partial JSON proofs, stable array ordering and
  rollback of task insertion when checkpoint persistence fails.
- Existing focused Python checks: **8 passed**. **19 native PostgreSQL tests
  skipped locally** because a native test service is unavailable. This is not
  native multi-connection PostgreSQL or full CI evidence. The new SQL suite is
  wired into the existing PostgreSQL test module, with no workflow expansion.
- Ruff check/format and `git diff --check` passed.

Reproduce the offline SQL suite after installing the pinned package into a
temporary directory:

```sh
NODE_PATH=/path/to/temp/node_modules node scripts/test_dufynd_business_source_dedupe.cjs
```

Native verification uses the existing `budget-postgres` workflow invocation
including `tests/test_dufynd_planner_external_evidence_postgres.py`; its added
test executes the exact same SQL suite against the migrated native fixture.

## Release boundary

No production SQL, migration, cron, queue rewrite, publication, merchant
activation, deployment or merge was performed. The successful shared CI reports
zero billable runner milliseconds. Applying the migration still requires separate
Owner approval. Production remains unchanged until that action. The release
packet captures the exact live planner definition and ACL for rollback; do not
replay an entire historical migration with operational writes or cron setup.
The private helper/checkpoint remain inert during rollback; historical tasks are
retained. Existing remote/local migration-version differences rule out a generic
repository-wide `db push`; the packet specifies one tracked Supabase
`apply_migration` call and explicit readback of its actual generated version.
