# Native DUFYND Nightshift v1 — activation decision, not activation

Development continuation of PR779 / `ops.work_ceo_nightshift_20261012`.
Python/SQLite remains an unchanged reference, not the production consumer.
No new server, queue table, model, external request, cron job or live migration.

## Existing execution path, verified 2026-10-13

Supabase project `bqsdxaagklpkxioaqdqa`, database/cron role `postgres`, PostgreSQL17.6,
pg_cron1.6.4, Free organization. Existing job11 `dufynd-ceo-v2-growth-loop` is active,
`*/10 * * * *`, currently `select public.run_dufynd_ceo_with_missions_v1();`.
All eleven existing job IDs, names, schedules, commands and enabled flags were read;
none was changed. `cron.use_background_workers=off`. Global configuration-file
`statement_timeout=120000ms`, reset value also120000, was read; postgres has no
role/database timeout override. Each native claim/finish nevertheless checks the
effective session timeout and refuses zero or more than120000ms.

The live content mission `autonomy_acceptance_20261010` already completed both
real handlers and retained both receipts. Existing claim/update/reconcile RPCs,
worker fencing, shared resource collision checks and handler contracts are reused.

### Why a top-level procedure is necessary

Calling a new function inside the existing single SELECT cannot durably reserve an
attempt before a backend dies: PostgreSQL rolls back that entire transaction.
`dufynd_ns_v1_cycle()` instead calls the unchanged legacy CEO/mission entry first,
commits it, claims exactly one native task and commits the attempt, then evaluates
and commits result+task completion+mission checkpoint together. It requires a
**top-level CALL**, not a function wrapper or an explicit transaction. This uses
the SAME job, role, database and cadence. No daemon and no twelfth timer.

PostgreSQL transaction-control reference:
https://www.postgresql.org/docs/17/plpgsql-transactions.html

The original eleven workers' function definitions are not replaced. New mission
states are prefixed `native_` so the old mission selector cannot consume them.
New `durable_payload.kind=native_nightshift_v1` cannot be dispatched as an existing
Python/external handler. Generic Supervisor V2 remains responsible for expired
leases; native persisted attempt counts cannot reset or exceed3 even if a lease
is repeatedly lost. Nothing claims to provide exactly-once arbitrary external
side effects: this contract permits only pure evaluation plus transactional SQL.

## Exact bounded pilot

Two tasks, one per existing ten-minute cycle, no more than3 attempts per task and
6 total, an explicitly dated window of at most1 hour. The first approval should
use45 minutes, starting at the next agreed ten-minute boundary in Europe/Berlin
(store timezone-aware UTC instants). No automatic renewal or following-night
enqueue. After a process death the next existing cycle retries only after the
180-second lease expires; an older token cannot publish a result.

1. `nightshift_measurement_qa` version1 checks the existing
   `jarvis.first_money_measurement_v1` snapshot's traffic separation, numeric count
   fields and clickout-is-not-sale guard. It does not generate a fresh visitor
   report or repeat the measurement worker. Observed source is dated2026-10-10;
   this is explicitly archived-evidence QA, **not current business analytics**.
2. `nightshift_receipt_qa` version1 checks the existing archived content receipt
   `jarvis.mission_result.v1:autonomy_acceptance_20261010:2`, its artifact checksum,
   lease-release evidence and no-generation/no-publication gates. It grants no
   new rights to the content, images or publication.

Awin original-transaction evidence stays an explicit `OWNER_HOLD`. Revenue and
commission remain `UNKNOWN`. No merchant clicks, visitor events or purchases.
Existing task-level human holds are skipped without changing their approval flags.
Terminal queue status includes done/held/failed counts; terminal does not mean all
business work succeeded or that a hold was resolved.

The read-only manifest accepts dates only. It selects two exact database keys,
projects a fixed field allowlist, rejects missing/non-object/over16KiB records,
and captures original-record hash and timestamp. It accepts **no uploaded file,
SQL, URL, repository content or arbitrary handler parameters**. SHA256 binds the
manifest, fixed code definitions, handler contract and evaluated input. Task IDs
derive from semantic input+handler/version/contract rather than the night/date:
identical inputs on another night reuse the original verified receipt. Refreshing
only an observation timestamp cannot create new work. Record/definition/result
triggers prevent ordinary edits/deletion; administrator disabling of triggers is
outside this trust boundary and tested as corruption, not called cryptographic
protection against the database owner.

## Migration and permissions — require separate Owner approval

Only `supabase/migrations/20261013054836_dufynd_native_nightshift_v1.sql` is new.
Its filename was generated with `supabase migration new`. It adds one constrained
attempt column to the EXISTING task table, internal functions/procedure, narrowly
scoped guards, two **disabled** contracts and a **disabled/stopped** config record.
It creates no queue table and performs no `cron.schedule`/`cron.alter_job` call.

Functions/procedure are SECURITY INVOKER, executable only by the existing postgres
role. PUBLIC/anon/authenticated/service_role are explicitly denied. No SECURITY
DEFINER escalation, new JWT credential or new role. Direct admin SQL is therefore
required for the scoped activation; generic service-role workers cannot self-start
it. Table ownership remains trusted. Existing owner-decision records must already
contain a genuine exact approval, not a fabricated decision from this migration.

After code+CI review, the **separately approved** operator procedure is:

1. Read current eleven registrations, existing mission state and cron-role timeout;
   abort on drift. Apply only the reviewed new migration through the normal
   migration path. Do not replay earlier migrations or merge unrelated PRs.
2. Enable only the two named v1 contracts, still leaving global config disabled.
3. Preview `select public.dufynd_ns_v1_manifest(:starts_at,:ends_at);` and
   `select public.dufynd_ns_v1_hash(public.dufynd_ns_v1_manifest(:starts_at,:ends_at));`.
   Inspect both sources and the exact manifest. Fresh code/source changes require
   a new preview/hash and matching approval.
4. Use the existing owner-decision process to record `status='approved'` and a
   `decision` object with exactly the reviewed `scope=dufynd_native_nightshift_v1`,
   timezone-aware `starts_at`, `ends_at`, and `manifest_sha256`. Record its decision
   ID; no automatic approval-creation endpoint is provided here.
5. `select public.dufynd_ns_v1_start(:pilot_id,:actual_approved_decision_id);`.
   This creates at most two tasks in the existing task table and one existing-
   namespace mission checkpoint. Missing or changed approval fails closed.
6. Only now, enable `jarvis.native_nightshift_v1.config` to
   `{"enabled":true,"stop":false}` and change **only job11's command**, using
   `cron.alter_job`, to `CALL public.dufynd_ns_v1_cycle();`. Keep its existing
   schedule, role, database, enabled state and the other ten registrations exact.
   Send CALL alone; do not wrap it in BEGIN or concatenate SET statements.
7. Await existing clock execution. No extra dispatch or manual production test.
   Read cron history, source/result hashes, task lease/attempt fields and mission
   summary. Verify the other ten jobs continue and legacy CEO/mission work occurs.
   A returned SQL success alone is not proof of task success. After the bounded
   pilot, stop configuration and restore the old command unless a new exact
   continuation approval is recorded. The dated manifest cannot run indefinitely.

Owner authorization must explicitly cover **that reviewed migration/code commit,
two disabled-to-enabled contracts, one bounded manifest hash/decision/window,
job11's command-only replacement and its restoration**. No blanket release,
production migration or scheduler activation is inferred from development consent.

## Stop, rollback and reuse

For a graceful stop set config `stop=true` (or `enabled=false`). New claims stop;
finish rechecks the gate between the committed claim and execution. If stop is
committed while a pure evaluation transaction has already started, that bounded
transaction may finish: stop is not an instant backend kill. No external side
effects exist. Retain all task/result/mission rows. To resume within the SAME
approved window, clear stop with the original approval still valid; do not recreate
the mission or reset counters. Expired windows or withdrawn decisions do not resume.

Operational rollback: disable config, then restore exactly
`select public.run_dufynd_ceo_with_missions_v1();` through `cron.alter_job` for job11.
Do not disable the entire job, delete receipts, truncate tasks, drop the attempt
column or destructively down-migrate shared tables. Allow the existing supervisor
to release any expired native lease. Dormant definitions/receipts are retained for
dedupe and audit. Production data never needs to be reconstructed from SQLite.

## Costs, evidence boundaries and remaining gates

No model/API/external-host calls, additional compute subscription, disk or server.
This adds bounded SQL work to already allocated Free compute. It still consumes
CPU, WAL and small durable rows; Free quotas/pausing/retention provide no always-on
SLA. Existing measured DB size ~38.1MB (~53.4MB across databases) is historical
capacity evidence, not a guarantee of remaining monthly usage. Budget0 is enforced
by the fixed contract, not by promising that unlimited future SQL is free.

Work container cannot install a native PostgreSQL service through system package
management (setgroups/setuid permission errors). No permission bypass attempted.
Local PostgreSQL-WASM smoke validates SQL bootstrap, both real lease/result paths
and top-level procedure transaction control, but **does not prove simultaneous
backends or backend termination**. Those tests use the existing CI job's isolated
localhost PostgreSQL17, one disposable database per test, never Supabase. The test
suite rejects non-loopback DSNs and non-test database names. The eleven cron rows
there are registration fixtures; real pg_cron timing is not simulated as a claim
of a live production acceptance. Live clock history remains read-only evidence.

Acceptance suite covers competing independent connections, fencing after lease
expiry, backend death after the committed attempt, result-transaction rollback,
hard attempt/cost/timeout gates, unchanged-input dedupe, typed holds, immutable and
privileged-corrupted/missing state, due-time/top-level CALL, stop/resume and default
deny permissions. Existing budget/worker/mission tests still run in the same
already-existing CI job; no new job or separately rerun successful PR CI.

**Productively activated: NO.** Exact commit/CI results and the next resume point
are recorded in PR779's `ops.work_ceo_nightshift_20261012` checkpoint. Activation is
blocked until the specific migration/pilot/command-only Owner approval above and
successful real PostgreSQL acceptance evidence are both present.
