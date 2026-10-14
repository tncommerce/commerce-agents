# DUFYND-20261014-RUNTIME-10

Status: development implemented; native PostgreSQL CI pending. No production activation.
Base: PR #786, 831c4aeadd37f147fd798d5e33a4c5fea13cf941. This is a stacked development change; scentai-mvp and main remain untouched.

## Actual execution path

Existing host: `.github/workflows/dufynd-jarvis-manual.yml`, GitHub Actions standard Ubuntu runner, Python 3.12. Existing durable-execution job last verified successful at run 38385147191 / job 115254966578 on 8647495e5619d1acfaa1346949d586e3b27c4fab. The new mode uses that workflow, not a new scheduler or queue. It accepts only a run ID, never arbitrary code or inline sources. Existing Supabase service credential is confined to the parent. The two pure child handlers have no inherited credentials; network and subprocess creation are denied, CPU/memory/output/wall-time are bounded. No model or publisher is called.

The adapter uses existing dufynd_autonomy_tasks, dufynd_human_decisions, dufynd_handler_contracts, dufynd_master_status and Supervisor V2 claims/update RPCs. Atomic SQL commits persist the output and task transition together. Exact receipt replay handles a lost HTTP response. A killed runner can resume after the existing 180-second lease expires, within the approved window and persisted attempt caps. Generic model selection excludes V2; a database trigger rejects claims outside the adapter and completion without a receipt.

No cron registration is changed. The original CEO stays configured throughout. This is an explicitly dispatched bounded pilot, not an autonomous nightly start. A separate dispatcher/schedule has not been installed or claimed.

## Exact development migration and impact

`supabase/migrations/20261014053444_dufynd_nightshift_value_runtime_v2.sql` contains the complete reviewable SQL. It installs six invoker functions (open, guard, arm, claim, commit, stop), two UPDATE/DELETE guards on existing task/master-status tables, and two initially disabled contracts: first_money_action/2 and editorial_handoff/2. It installs PR775's exact two canonical-hash helpers only if absent; no seven-worker activation or full PR775 migration is needed. PUBLIC/anon/authenticated execution is revoked; service_role/postgres only. Existing service_role table privileges were read-only verified.

No tables/columns/data are dropped, no source payload is installed by the migration, no owner decision is synthesized. Guarded V2 identities, manifests and receipts cannot be edited/deleted through ordinary paths. Other namespaces are untouched. Existing claim_dufynd_worker_v2 invokes the existing global supervisor reconciliation, so normal lease maintenance of other Jarvis tasks can occur, as with existing claims; this is not a new reconciliation implementation.

Risks/gates: privileged service-role code remains trusted; audit hooks constrain these fixed deterministic workers, not arbitrary adversarial Python. A database outage prevents timely state writes. Deadline checks still reject later claims/commits, but SIGKILL with no subsequent invocation does not guarantee an immediate persisted expired marker. Next claim reconciles it. This is not presented as a pg_cron timing test.

Rollback: call stop_dufynd_value_v2 with the exact run ID and owner_stop, verify active=false, noncompleted tasks blocked/released and completed receipts unchanged. Cancel only that workflow run. Do not drop the migration or delete evidence during rollback. No CEO/cron restoration is required because none was changed. Full function/trigger removal would need a separate reviewed migration. Repeated stop returns the same checkpoint; stopped runs cannot rearm.

## Limits and activation gate

Exactly two handlers, two tasks, 3 attempts per task / 6 total, cost_eur=0, provider_calls=0. Approved window at most 45 minutes, Actions job at most 5 minutes, each fixed child at most 10 seconds (5 CPU seconds, 256 MiB, bounded input/output). No production start in this run.

A future Owner-GO must bind: exact tested commit; this migration; full private manifest hash; source envelope hashes; exact start/end; the two deterministic task IDs; an actual decision with action_type=nightshift_value_v2 and exact context {run_id,manifest_sha256}; and one dispatch of the existing workflow mode nightshift-value-v2 at that ref/run ID. No fictional decision ID, merge or default-branch change is implied. Before arming, verify unchanged host permissions, free standard-runner eligibility, current source age/rights and no existing duplicate tasks. If the existing workflow cannot accept dispatch at the reviewed branch, HOLD; do not merge protected branches to work around it.

Arm creates tasks only after that exact approved decision exists. Unknown, stale, corrupted or unapproved inputs produce HOLD. The original content quality floor 9.5/10, rights, visual review and creative approval remain gates. An internal editorial handoff is not a publishing approval.

## Recovered editorial evidence (no duplicated repair)

Read-only recovery of the already repaired private archive DUFYND-7-Worker-Pruefnachweise.zip, Library libfile_e4ac3bdf9c3c81918c3e2e1537e0ebb5, version 1. SHA256.json validates revised-source.json raw SHA256 ad9b6c198c6c731568f5cfed85970dc256f11249fb47cdf1db6dd64c3e8f36e9 and repair-ledger.json 5aeb6c6e7118823823fcdc265265408022b183d05a0ec1d593cfd02cfe3c6f8b. Six affected ideas / seven edges were repaired already on 11 October. Parsed W2 is identical before/after; broken references go from six to zero. The new source allowlist binds the exact archived revision instead of silently editing the old Supabase source. Historical calendar placeholders are not new publication plans. No private source or final is committed to this public repository.

## Evidence / continuation

Local targeted tests initially: 43 passed. Native CI added to the existing content7-postgres job, using disposable localhost PostgreSQL 17 and synthetic decisions only. It exercises real SQL locks/leases/transactions plus the real HTTP bridge and real isolated Python child. The small HTTP test transport is not a claim that a production Supabase API was exercised. Concurrent workers, SIGKILL/restart, lost response, stop/replay, atomic rollback, limits, unknown sources and deadline expiry are covered. Eleven sentinel cron rows test noninterference only, not actual pg_cron scheduling.

Native CI result and final commit/PR are recorded in the completion comment; do not repeat unchanged successful runs. No production SQL writes, protected merge, cron change, V1 restart, provider call, post or synthetic analytics event occurred. Publishing identity and Gmail holds from prior work remain separate.
