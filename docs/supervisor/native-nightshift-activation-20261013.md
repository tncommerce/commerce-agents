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
`dufynd_ns_v1_cycle()` first checks the pilot deadline/stop gates and commits a
durable stop when necessary, then restores job11 and commits that transaction.
It next calls the unchanged legacy CEO/mission entry, commits it, claims exactly
one native task (only while armed) and commits the attempt, then evaluates
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
6 total. The pilot arming function requires exactly45 minutes (the lower-level
development manifest still accepts up to1 hour). Start at an agreed ten-minute boundary in Europe/Berlin
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
It creates no queue table and executes no `cron.schedule`/`cron.alter_job` call
when applied. Dormant arming/restore functions use only `cron.alter_job` at runtime.
This still-unapplied migration is amended in PR779; do not apply the superseded
64ebb0ef version and then try to replay the new version as an incremental upgrade.

Functions/procedure are SECURITY INVOKER, executable only by the existing postgres
role. PUBLIC/anon/authenticated/service_role are explicitly denied. No SECURITY
DEFINER escalation, new JWT credential or new role. Direct admin SQL is therefore
required for the scoped activation; generic service-role workers cannot self-start
it. Table ownership remains trusted. Existing owner-decision records must already
contain a genuine exact approval, not a fabricated decision from this migration.

Live permission readback06:52UTC found `postgres` has EXECUTE on
`cron.alter_job(bigint,text,text,text,text,boolean)` but NO UPDATE on `cron.job`
(owner `supabase_admin`). Consequently no direct table DML, write lock or
SELECT FOR UPDATE on cron tables is used. Command changes use the existing
extension API inside SERIALIZABLE transactions; concurrent foreign changes abort
the transaction rather than being silently overwritten. No grant or ownership
change is required. CI reproduces this boundary with a non-superuser job owner,
SELECT-only cron-table access and the real C API, including automatic expiry.

After code+CI review, the **separately approved** operator procedure is:

1. Read current eleven registrations, existing mission state and cron-role timeout;
   abort on drift. Apply only the reviewed new migration through the normal
   migration path. Do not replay earlier migrations or merge unrelated PRs.
2. Keep both contracts and global config disabled while reviewing the preview.
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
6. In one dedicated admin transaction, run `BEGIN ISOLATION LEVEL SERIALIZABLE;`,
   `select public.dufynd_ns_v1_pilot_arm(:pilot_id);`, then `COMMIT;`. Arming atomically captures the
   immutable rollback checkpoint, compares all eleven registrations to the
   approved manifest, enables exactly the two contracts/config, and replaces only
   job11's command via `cron.alter_job`. Failure rolls the whole arm transaction
   back. Do not edit config/cron separately or add another schedule. Repeating
   arm with the same ID returns its receipt; it never renews a completed pilot.
   A serialization failure requires fresh baseline/approval review, not blind retry.
7. Await existing clock execution. No extra dispatch or manual production test.
   Read cron history, source/result hashes, task lease/attempt fields and mission
   summary. Verify the other ten jobs continue and legacy CEO/mission work occurs.
   A returned SQL success alone is not proof of task success. Native claims and
   finishes reject the deadline immediately. The first available existing tick
   after the deadline durably stops native work, disables both contracts and
   restores the original command automatically, before invoking the legacy CEO.
   Inspect the pilot receipt `state=restored` AND `all_eleven_exact=true`, plus
   the next successful cron history entry with the original SELECT command.

Owner authorization must explicitly cover **that reviewed migration/code commit,
two disabled-to-enabled contracts, one bounded manifest hash/decision/window,
job11's command-only replacement and its restoration**. No blanket release,
production migration or scheduler activation is inferred from development consent.

## Stop, rollback and reuse

For immediate orderly abort send `CALL public.dufynd_ns_v1_pilot_abort();` alone,
outside an explicit transaction. It commits stop first, then restoration; it does
not call the CEO or claim a task and is safe to repeat concurrently. Alternatively
set config `stop=true` (or `enabled=false`) for teardown on the next existing tick.
New claims stop;
finish rechecks the gate between the committed claim and execution. If stop is
committed while a pure evaluation transaction has already started, that bounded
transaction may finish: stop is not an instant backend kill. No external side
effects exist. Retain all task/result/mission rows. An automatically stopped or
aborted pilot cannot be rearmed by clearing config or repeating its ID. A future
separately approved pilot can reuse verified task receipts; counters never reset.
Original CEO/Jarvis resumes through its unchanged original command and definitions.

Operational rollback: disable config, then restore exactly
`select public.run_dufynd_ceo_with_missions_v1();` through `cron.alter_job` for job11.
Do not disable the entire job, delete receipts, truncate tasks, drop the attempt
column or destructively down-migrate shared tables. Allow the existing supervisor
to release any expired native lease. Dormant definitions/receipts are retained for
dedupe and audit. Production data never needs to be reconstructed from SQLite.

### Restoration bounds and failure behavior

No twelfth job, no second timer, no open Work session. The existing job11 polls
every ten minutes. **The native work window is45 minutes; command restoration is
on the first available tick afterward, normally within10 minutes plus up to the
existing120-second statement bound. It is not an exact wall-clock45-minute alarm.**
A paused/unavailable database, disabled/deleted job, or revoked postgres permission
cannot repair itself while no permitted executor can run. After availability
returns, the next tick stops/restores before any native claim or legacy action.

Stop is committed separately, so backend death or an error in `cron.alter_job`
cannot undo it. A transient restore error is recorded and retried on the existing
clock, maximum3 committed attempts. Persistent failure gives OWNER_HOLD, keeps
native work disabled, and still calls the original CEO entry once per ordinary
cycle. It never disables job11. A changed job identity/foreign command is not
overwritten. Changes to another job are preserved, with `all_eleven_exact=false`;
that is an investigation gate, never a claim of a clean full restoration.
The top-level abort/cycle procedures start a SERIALIZABLE restoration transaction
after the stop commit and return to ordinary transaction isolation after its
commit. They do not change session defaults or the original CEO function.

An administrator must resolve persistent permission/identity errors and perform
the explicit command-only rollback above; no automatic privilege escalation or
attempt-counter reset exists. A missing/corrupted checkpoint stops native work;
the recovery path uses only the fixed known original command and verifies job11's
name, role, database and active state. It cannot certify a lost baseline.

**STOP unattended activation if the Owner requires restoration exactly at minute45,
if any baseline/permission/clock evidence is missing, or if any restoration test
fails. In that case recommend only an expressly supervised pilot.** Even with
passing tests, approval must explicitly accept the existing clock/availability
bound; do not silently interpret45 minutes as an exact command-switch guarantee.

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
there are registration fixtures. A separate test module now builds the actual
upstream pg_cron v1.6.4 C extension in an ephemeral localhost container inside
the SAME existing CI job. It uses libpq mode, top-level CALLs scheduled by pg_cron,
real `cron.alter_job`, run history and independent backends. Its1-second cadence
accelerates an exactly45-minute manifest whose start lies in the past; it does
not change production cadence or claim a45-minute soak test. Ten peer business
actions are inert sentinel SQL. Extension timing and rollback are real; no live
business handlers or Supabase database are exercised. CI must pass this module
(no skip) before timing support is considered proven. The Python full suite skips
it unless the dedicated localhost:5433 test DSN is explicitly present.

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

## One approval evidence package

The final PR779 checkpoint identifies the one exact code commit, CI run and
private dated manifest evidence. The package must contain: this amended migration,
only `nightshift_measurement_qa/1` and `nightshift_receipt_qa/1`, the full manifest
and SHA256 (including the eleven-job baseline), UTC start/end exactly45 minutes,
0€ additional spend/0paid calls/2tasks/3attempts each/6total, effective timeout
1..120000ms, lease180s, automatic stop/restore receipt and real pg_cron test evidence.
Any code/source/baseline/window drift invalidates that package. Do not substitute
a generic approval or another manifest. No new approval is requested for development.
