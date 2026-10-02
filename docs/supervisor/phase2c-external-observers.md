# Supervisor V2 Phase 2C

The existing `dufynd_jarvis_inbox` is the event ledger/queue. Its canonical status
also exposes `processing_status`. UUID identities, stable fingerprints and related
Task IDs persist independently of chat. Observer rows contain source configuration,
minimal snapshots, health, asynchronous request identity and cursors; wait rows
bind an existing Task to an exact source, accepted event types and optional pinned
commit. These metadata tables are not additional queues.

## Sources and boundaries

| Source | Collection | Automatic outcome |
| --- | --- | --- |
| GitHub branch | Public API, ETag, registered `scentai-mvp` only | Branch movement reevaluation/freshness gate |
| GitHub PR | Public API, ETag, explicit PR ID and integration base | Open/update/merge/close/base movement evidence |
| GitHub CI/workflow | Public API, ETag, explicit run ID, integration branch | Queued/running/completed evidence; success requires pinned SHA |
| Render | Prepared authenticated API, latest bounded deployment window | Started/live/failed/service commit; live requires pinned SHA |
| Gmail | Prepared OAuth metadata/history API, exact approved thread allowlist | New inbound message/bounce requires review; never rights approval |
| Internal dependencies | Synchronous Task-status trigger | Exact Task-ID dependencies completed → ready |

The existing two-minute Supabase watchdog consumes asynchronous receipts before
issuing at most one new external request per tick. Together with the Phase 2B
external-run poller, the maximum is 60 HTTP requests/hour. ETags avoid repeated
GitHub response bodies; unchanged observations create no new events. Render reads
only the latest 20 deployments, not full history. Gmail history pages use retained
watermarks; history is filtered to registered threads before a metadata-only fetch
of that exact thread. No mail bodies, snippets or unrelated message content enter
the ledger. Fingerprints remain persistent when a bounded 500-message snapshot is
rotated. Restarts cannot reset cursors by re-registering an observer.

No externally exposed unsigned webhook endpoint is introduced. Authenticated
service-role ingress calls `capture_dufynd_observation` with native provider
fixtures; it uses exactly the same normalization and deduplication as polling.
Internal changes are already event-driven. External polling is the initial
fallback, not a claim that Render/Gmail webhooks are configured.

## Activation blockers from live audit, 2026-10-02

No autonomous Render or Gmail credential was present in Supabase Vault. Existing
connected app sessions do not grant the background watchdog a credential. Those
sources must report `blocked_configuration`, not healthy or human-decision gates.
Activation needs narrowly scoped credentials provisioned through an appropriate
secret-management path; never copy connected-app credentials. Fixed references:
`dufynd_observer_render_read_token` and
`dufynd_observer_gmail_read_access_token`. The Gmail transport currently accepts
an access token and reports expiry/401; a certified refresh mechanism is still
required for sustained operation. No approval or token is simulated.

## Safe reevaluation and durable handoff

Success events satisfy an exact pinned dependency; failures cannot satisfy one.
All registered external conditions AND all exact internal Task IDs must be
satisfied. Review/freshness flags prevent durable execution, including direct
existing `prepare_dufynd_execution` calls. Registered replies only prove presence,
not business meaning. Existing real Human-Gates remain intact. Network/rate-limit
errors only change observer health/retry timestamps, never Task human status.

A free Task with a certified existing `durability_probe` payload uses the existing
atomic scope claim, execution ledger, fence and dispatch identity. No new worker
command evaluator exists. Unknown handlers stay ready/parked. Paid Tasks never
receive a free fallback or a budget increase. The existing Actions job may wait
up to 360 seconds for registered free event waiters; it does not own them while
waiting. Existing supervisor recovery continues after that bounded window.

## Tests and acceptance

Real PostgreSQL regressions cover CI success/failure and duplicates, pinned
Render live/failure, known/new/old/foreign mail and bounce, cursor restart/pages,
rate-limit/dead observer health, internal dependency events, existing free durable
handoff and completion, uncertified handler parking and legacy inbox isolation.
Python fake-clock tests verify the bounded existing-worker wait with no chat.
The live receipt belongs in `continuity.checkpoint.jarvis` and a dedicated
`jarvis.external_observer.acceptance` master-status key after autonomous E2E proof.

No paid-model invocation is used. Observer model cost is $0; HTTP/database/Actions
usage consumes existing service quotas, whose remaining allowance must not be
assumed to be unlimited or financially free.

## OPTIMIZATION_CANDIDATE

- GitHub authenticated webhooks can replace source polling after signature and
  delivery-id validation; keep this inbox and fingerprints.
- Render authenticated webhook deployments can eliminate deployment-window gaps
  and metadata polling once background access is provisioned.
- Gmail Pub/Sub watch plus certified token refresh can replace per-thread polling;
  retain the approved-thread filter and review gate.
- Batch compatible GitHub observations and conditional requests to reduce quota
  pressure. Honor rate-limit/backoff before further requests.
- Schedule the existing Actions worker from an authenticated durable wake channel
  to replace the bounded post-push waiting window; no second execution plane.
- Monitor gaps beyond Render's latest 20-deployment window before expanding the
  bounded cursor transport; do not infer success for unobserved deployments.
