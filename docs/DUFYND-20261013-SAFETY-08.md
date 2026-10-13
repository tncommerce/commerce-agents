# DUFYND-20261013-SAFETY-08 — connected manual publication fence

Development only. No migration, publisher activation, profile edit, social post,
paid call or website deployment. Production `scentai-mvp` remains read-only.
PR779, the Nightshift manifest/tasks/decision and Cron11 are untouched.

## Actual paths and remaining boundary

The current repository has two connected-tool entry points in
`scripts/dufynd_metricool_connector.py`: `dispatch_connected_metricool` (legacy
single-asset path, already denied by the current production reservation RPC)
and `dispatch_connected_release` (three-platform preflight/reserve/claim path).
Neither was calling PR783's `record_manual_delivery` method. No caller binding
these functions into a persistent authenticated host was found in scripts,
retail API or workflows. That is a repository finding, not proof that no external
host exists. Historical deployment status describes an adapter entry point, not
a globally enforced Metricool ACL.

Actual manual distribution is independently evidenced by the existing Metricool
entries and LASTMILE-07's completed readback. That inspection was not repeated.
Direct Metricool create/update tools, the planner UI and native social apps are
outside this Python module. A host can also import a low-level orchestrator
directly. Their permissions were not altered; no account-wide protection claim.

Fresh, read-only production checks for this run: manual guard RPC absent, manual
receipt count 0, automatic dispatch ledger count 0, private binding manifest
absent. Existing asset lookup by Dufttester/Waschmittel content name and their
known frozen SHA256 values returned no canonical asset/content identities.
These identities remain UNKNOWN/HOLD; captions or planner IDs are not substitutes.

## New integration

Adapter contract `manual-delivery/1` is mandatory at both existing connected
publisher entry points. Omitting its manifest pin fails before any provider or
publication RPC. Existing atomic reservation, per-platform invocation claim,
Owner GO, uncertain-outcome and late-result paths are preserved.

`sync_connected_manual_deliveries` uses the already authenticated host's read-only
`metricool_getscheduledposts` capability, then PR783's existing exclusion RPC.
It does not create, modify, approve or publish a Metricool post. It requires:

- Private existing master-status path `content.manual_delivery_bindings_v1`,
  SHA256 pinned by trusted host configuration; no second queue/scheduler.
- Exact schema `{schema_version:1, brand_id:"7182186", from_date, to_date, bindings}`.
  A timezone-aware window containing now, at most seven days, and 1–8 bindings.
- Each entry `{source_key, source_sha256, binding}` refers to an existing private
  `content.*` source. Canonical JSON SHA256 uses UTF-8, sorted keys, compact
  separators, ensure_ascii=false, no NaN. The source digest and complete manifest
  digest must match; they pin data, not replace authorization.
- Binding fields only: `content_id`, `asset_sha256`, `platform`,
  `provider_post_id`, `provider_uuid`. Canonical content ID must already exist in
  the source's `content_id`. Source hash comes from its existing root asset hash,
  frozen-asset expected hash or asset source hash. No inferred IDs or hashes.
- Planner ID/UUID must match the source's existing `metricool_delivery` or
  `platform_schedule` entry. Fresh readback must match the exact media URI too.
  The URI is compared, never fetched; this does not certify remote bytes or rights.
- A ready SQL guard, exact one-to-one bounded readback, no unknown pagination,
  extra/missing/duplicate posts, non-manual flags or ambiguous platform identity.
- Successful SQL exclusion receipt with auto_publish_allowed=false. Existing
  dispatch conflict, failed write or lost response stops the automatic caller.

MANUAL_PENDING, MANUAL_PUBLISHED and MANUAL_UNKNOWN are durable exclusions.
Published never regresses. Repeating an observation after a lost DB response is
safe; retrying a provider publication is not. A partially committed exclusion
batch remains safely blocked; it is not deleted to make a retry pass. Current
approved source packets are not modified by this work.

This inventory is bounded to the approved window. It does not certify all-time
provider history, detect a silently omitted external post, cancel an already
claimed call, or intercept future manual publishing outside the host. Operational
quiescence and canonical historical reconciliation remain mandatory before any
automatic publishing permission. A fresh readback cannot close a race with an
uncontrolled external publisher.

## Exact migration and activation package

CLI-generated file (Supabase CLI2.120.0 `migration new`, no link/push/apply):
`supabase/migrations/20261013183250_dufynd_manual_publish_guard_adapter_v1.sql`.
SHA256 `f3cf3bd478786b8229354ffc213a8f3003904c6cb461c5834dffbb679b2eb718`.

It packages the exact PR783 guard proposal (SHA256
`397108cec29d40ff400dc9b7db383d1f46b4008276ea8405cb9a3f9b586e7437`), then adds
`dufynd_manual_guard_ready_v1()`. Do NOT separately apply the old proposal first.
The new read-only, security-invoker RPC rejects missing/disabled/wrong trigger
shape and replica mode; public/anon/authenticated execution is revoked. The
readiness check detects installation drift, not hostile concurrent DDL by an
administrator. The two guard functions, trigger and readiness function are the
only schema additions. No table, cron, credential, policy weakening or budget.

Dependency: this isolated branch is stacked on exact PR783 commit
`17b538d3fb5d4799d5856b6dc68183868d121536`; PR783 itself is unchanged. Adapter
source revision is the exact SAFETY-08 commit recorded in its PR/checkpoint.

Activation remains HOLD until all of the following can be quoted in one concrete
Owner decision: exact adapter commit, the above migration/hash, verified existing
authenticated host and exclusive routing plan, reconciled four real identities,
and the resulting private manifest SHA256. A real manifest hash cannot yet be
provided because canonical content IDs are missing. Do not approve placeholders.

Bounded future GO text (scope, not an approval already received):
“Install only the reviewed manual guard migration and adapter manual-delivery/1
at the exact reviewed commit; bind the identified existing host; register only
the four reconciled manual exclusions from the exact private manifest. Keep
automatic publication OFF. No new post, scheduling, website release, new access,
Nightshift change or cost.” Any needed merge has to be named separately; this
document grants none.

Order: quiesce DUFYND publishers → recheck live drift/permissions/ledger → apply
only the exact migration through the authorized path, not a broad db push →
deploy/bind the adapter with automatic execution still off → ingest exclusions
from an exact current readback → verify receipts/trigger/host version → retain
publication HOLD. Do not touch other projects or global connector credentials.

Rollback: quiesce the publisher first. Keep manual receipts/dispatch evidence.
Prefer leaving the guard installed while reverting the host adapter. If a schema
rollback is specifically approved, remove readiness function, the one trigger,
then the two guard functions, with dependency checks and no CASCADE. Never resume
the old host with the guard removed. No data deletion or provider retry.

## Verification

94 targeted local Python tests pass, including both entry-point defaults, pinned
source drift, missing identities, ambiguous readbacks, manual unknown state,
interrupted provider read, committed exclusion with lost reply, late pending
readback, and an interrupted provider publication followed by blocked retry.
Ruff and whitespace checks pass. All test identities are explicitly synthetic.

The exact migration passed local PGlite PostgreSQL-WASM installation/readiness,
disabled-trigger and replica checks. This is NOT native concurrency proof.
The existing CI PostgreSQL17 job runs the same exact migration and four additional
native tests: readiness/permissions, replica denial, two concurrent automatic
reservations with one winner, and the connected readback adapter using committed
multi-connection SQL with lost reply, reconnect, concurrent repeat and late status.
It also retains PR783's original 11 race/late-receipt tests. Final CI is recorded
in the PR and Supabase receipt; no unchanged CI was manually rerun.

Supabase official database-functions documentation was read for invoker rights and
function grants. Changelog markdown retrieval returned unsupported content-type;
no current Supabase feature assumption depends on that failed fetch.

## PR784 release prerequisites

HEAD `1f6adea9c9c64c2fa64cec2161105b1d3902eb7f`, CI38442651701 SUCCESS,
draft/open/mergeable on the unchanged production base. No tests rerun. Its three
files (campaign builder, its tests, LASTMILE report) do not overlap this guard
integration. It is independently reviewable and is not a prerequisite for the
publisher fix. It still needs an exact separate merge/release GO; this request
does not authorize it.

## Resume

Read `ops.DUFYND-20261013-SAFETY-08` first; report an existing completion instead
of rerunning this work. Next concrete measure: reconcile the four manual source
records to authoritative canonical content IDs and pin the private manifest,
without publishing or editing frozen creative originals. This unblocks the
bounded activation decision; another publisher or queue would not.
