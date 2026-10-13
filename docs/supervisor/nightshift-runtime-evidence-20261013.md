# DUFYND Nightshift runtime evidence — 2026-10-13

Scope: tncommerce/commerce-agents only. Read-only infrastructure observations
around 05:04–05:13 UTC. No resources, credentials, database objects, workflows,
schedules or production branches changed. New runner activation: **NO**.

## Observed resources and limits

| Existing resource | Live evidence | Suitability / unresolved prerequisite |
| --- | --- | --- |
| GitHub commerce-agents | Public repository; default branch `main`; PR779 at aa786f79762173e8ad3ae4a19cfdd72f31b78bd5; CI38303832113 success. Standard ubuntu-latest jobs exist. | Standard public Actions compute is free per current official policy. Account artifact/cache usage is UNKNOWN through this connector. No new cache/artifact storage proposed. |
| GitHub timing | Existing main dispatch bootstrap is manual/guarded issue_comment, includes model-backed modes. Manual registration stub requires scentai-mvp. | No suitable existing zero-cost timed Python consumer found. New native Actions schedule would require the protected default branch. No main change, paid mode or dispatch initiated. Ephemeral runner files are not authoritative queue storage. |
| Render scentai srv-dakpiajl550s73cp4lvg | Static site, production branch scentai-mvp; buildPlan starter is a build setting. | Static hosting cannot run the Python timer. Build/bandwidth quota remaining UNKNOWN; no new build requested. |
| Render scentai-api srv-dakpfrnf3r2c73dr3f20 | One Python web instance, plan 0.5c-512mb, 0.5 CPU and 536870900-byte memory limit returned by metrics. Start command is the storefront API. No persistent disk present in service details. | Existing allocated compute is confirmed, spare capacity and durable local state are not. Render documents ordinary filesystem loss on restart/redeploy. No SQLite runtime approval on this service; no new disk/service. |
| Supabase DUFYND bqsdxaagklpkxioaqdqa | ACTIVE_HEALTHY, Postgres17.6, organization xqennwyzpddgilckmgne explicitly Free/tier_free; pg_cron1.6.4 and pg_net0.20.4 installed. | Existing durable SQL execution is verified. It is not a Python process or SQLite volume. Existing certified SQL handlers and task leases must remain authoritative. |
| Supabase capacity | Current DB38120595 bytes; all cluster databases53402421 bytes at05:10:14.878920UTC. Official Free database quota500MB; project not read-only. max_connections60, observed13; cron.max_running_jobs32; statement_timeout120000ms for observed session. | Database usage is below the documented quota; roughly53.4MB total, not WAL/disk or monthly egress. Remaining egress/storage/API quotas UNKNOWN. Free inactivity pausing is possible, so no always-on SLA claimed. |
| Supabase real timer | Eleven existing DUFYND jobs active. Last-hour runs all succeeded, maximum duration0.796983s, measured peak overlap8. | Autonomous clock execution outside Work is proven. Official recommendation is at most8 concurrent jobs and10min/job. Reuse an existing serialized cycle after review; do not add a twelfth coincident job. Success means SQL returned, not that every business task was eligible/completed. |

## Compatibility with existing Jarvis

The live task table already has task_id, resource_scope, budget_class,
provider_cost_unknown, dependencies, durable_payload, lease_token/expiry,
worker_state, retry_count and owner/freshness gates. Twelve enabled contracts
were observed; eleven explicitly certified free, while durability_probe lacked
that certification field. No uncertified handler is promoted by this evidence.

The existing Python durable consumer and `PacketTools` admit only durability_probe,
supervisor_state_audit, purchase_destination_freshness_audit and ci_pr_verifier.
None admits PR779's local JSON/source/catalog actions. Its existing workflow
runs only on scentai-mvp. Do not insert the offline queue into the production task
table, invent an accepted payload, borrow another handler identity or mark Jarvis
tasks done from local SQLite results.

The existing native `start_dufynd_mission_v1`/`tick_dufynd_mission_v1` SQL path
already provides advisory locks, existing worker resource leases and transactional
results/checkpoints for its fixed two-step content-preparation mission. The
existing CEO cron routes through it. Rebuilding that queue would duplicate work.
It has no contract for PR779's pinned files, dated plan, SQLite state or local
validator. SQL pg_cron cannot execute this Python implementation unchanged.

## Exact runtime decision / OWNER_HOLD

**Existing Supabase SQL orchestration: verified. Complete production operating
path for PR779 Python runner: BLOCKED, not certified operational.**

A supported choice is still required before activation:

1. An already-funded, independently available Linux runtime with persistent private
   storage, exact unprivileged account/checkout/state paths and a reviewed dated
   plan plus unit installation approval. No such host/volume was verified among
   the listed DUFYND resources; this Work scratch directory is not one.
2. A separately scoped native integration into the EXISTING Supabase mission/task
   plane, with an exact fixed handler contract, resource scopes, source/result
   binding and PostgreSQL contention/recovery tests. Installing it would require
   an explicitly approved production migration/activation, which is forbidden in
   this request. It must not serialize SQLite into status rows or reuse an
   unrelated certified handler. The native SQL clock/storage are available;
   the Python adapter and its acceptance proof are absent.

No integration is called ready merely because a Free tariff or passing local
simulation exists. Account billing/egress/backup dashboards were not exposed by
these resource tools; UNKNOWN is retained. No login or alternate credential path
was attempted. Existing successful CI on774/775/776/778 was not rerun.

## Evidence and next concrete work

The prepared offline queue uses the existing source packet, existing catalog
pre-intake validator and archived QA JSON. Three deterministic local checks plus
one source-report hold; at most six attempts and three checks per tick. Never
produce visitor events, merchant clicks, image claims, sales or commissions.

61 targeted tests passed. Real child process waits for due time, receives SIGTERM,
persists STOP_SIGNAL, restarts using the same SQLite state, skips Awin hold,
completes three checks and retains attempts=3 on the next invocation. Existing
real-process-death regression covers crash recovery through lease expiry.
Corrupt/missing files and now missing task/results/counters stop without repair.

Next runtime work after selecting the permitted operating route: implement only
that exact adapter and acceptance test; then request separate, bounded activation
approval. Until then retain the disabled plan and all results in PR779. Do not
replace missing host proof with an unbounded Work session or production trial.

Official policy references read on2026-10-13:
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://render.com/docs/disks
- https://supabase.com/docs/guides/cron
- https://supabase.com/docs/guides/platform/database-size
- https://supabase.com/docs/guides/platform/free-project-pausing
- https://supabase.com/changelog?types=breaking-change (cron direct-table mutation change noted; no such mutation performed)
