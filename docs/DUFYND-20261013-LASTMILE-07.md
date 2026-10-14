# DUFYND-20261013-LASTMILE-07

Development/read-only evidence, 2026-10-13, observations around 16:07–16:10 UTC.
Production base remains `8647495e5619d1acfaa1346949d586e3b27c4fab`.
No deployment, migration, publication, profile edit, tracking event or paid call.
Nightshift #779, its tasks/manifest/decision and Cron 11 were not changed.

## Deduplication and actual profile targets

No LASTMILE status row, local matching checkpoint, remote lastmile branch or
newer related PR existed at intake. Earlier conversation evidence concerned
OPERATIONS-06 / PR783, not a completed LASTMILE run. The exact status key was
claimed with INSERT ON CONFLICT DO NOTHING before continuing.

Metricool brand settings identify TikTok `dufynd` and YouTube channel
`UCQooXN4sOeMsEG-43qaH0aA`. Search did not expose the profile targets (TikTok
robots restriction; YouTube fetch DisabledError). A bounded public browser
inspection succeeded without login. No outbound shop link was followed.

| Source observed in rendered public UI | Decoded target (no request made) |
| --- | --- |
| `https://www.tiktok.com/@dufynd` bio | `https://dufynd.de/duft?src=tiktok&cmp=tt_bio_launch_20261011&content=profile_bio` |
| `https://www.youtube.com/channel/UCQooXN4sOeMsEG-43qaH0aA/about` Links, “1 Million Preise vergleichen” | `https://dufynd.de/duft/rabanne-1-million?src=youtube&cmp=yt_1million_v8DlVXi-Fj8_p1&content=one_million_example61_01` |

TikTok wraps the URL in `/link/v2?…&target=…`; YouTube in `/redirect?…&q=…`.
Transient redirect tokens are intentionally not stored. All three attribution
fields are present and accepted by the existing offline link builder. TikTok
lands on discovery, YouTube on Rabanne. These are profile-level labels, not proof
that a visitor watched any specific post. Redirect execution, real visitor
identity, checkout and Awin revenue were not tested or inferred. No repeat of
FUNNEL-01 or GROWTH-02.

## PR783: bounded activation plan, NOT activated

Verified draft HEAD `17b538d3fb5d4799d5856b6dc68183868d121536`;
CI `38401365162` remains SUCCESS, not rerun. Existing successful tests are not
new LASTMILE tests. The reviewed SQL proposal is
`docs/sql/dufynd_manual_publication_guard.sql`, SHA256
`397108cec29d40ff400dc9b7db383d1f46b4008276ea8405cb9a3f9b586e7437`.

Live read-only catalog/ledger evidence: no manual-delivery RPC, no user trigger
on `dufynd_publish_dispatches`, no manual-delivery receipts, zero dispatch rows
for brand 7182186. This snapshot does not cover independent Metricool schedules
or in-flight calls outside this ledger.

Current Metricool readback: both Dufttester entries are PUBLISHED; both tomorrow's
Waschmittel entries remain PENDING; all four have autoPublish=false. Exact
planner ID/UUID, frozen-source keys/hashes and observations are retained privately
under `ops.DUFYND-20261013-LASTMILE-07`, not copied into public Git. PUBLISHED is
a planner/provider status, not independent native audio or public-URL evidence.
The older source packets still say pending; do not use those stale statuses to
requeue content. Their approved originals were not edited.

Activation sequence requiring a separate, narrowly scoped Owner GO:

1. Quiesce only DUFYND automatic publishing entry points. Inventory any host
   invoking `mcp__codex_apps__metricool_createscheduledpost`, updates that can
   activate drafts, and direct UI actions. Do not alter shared permissions,
   Nightshift or other projects. If an uncontrolled publisher remains, HOLD.
2. Recheck exact PR783 HEAD/SQL hash and live table/RPC contracts. Generate a
   reviewed migration from that exact SQL through the existing migration path;
   apply only the two functions, trigger and existing-role grants. No migration
   is created/applied by this LASTMILE run. No table, scheduler or new credential.
3. Bind the existing authenticated host to
   `PublishOrchestrator.record_manual_delivery` for manual handoffs/readbacks,
   and `dispatch_connected_release` for any separately authorized automatic
   release. A library method is not a deployed host integration. The stored
   October 9 runtime-adapter flag is historical, not current deployment proof;
   an exact host/version and call-path receipt remain prerequisites.
4. Reconcile canonical frozen content IDs against existing assets, hashes,
   planner IDs and UUIDs. Record exactly the four current manual observations
   via the new service-role RPC (not hand-written master-status substitutes).
   Register pending manual handoffs BEFORE native publication. Refresh statuses
   immediately before ingestion; unknown/conflicting identities stay HOLD.
5. Re-read the dispatch ledger while publishers are quiescent. Any existing
   reservation/claimed call or uncertain provider outcome requires reconciliation,
   not deletion, retry or replacement. In-flight calls cannot be canceled by this
   trigger. Missing native URLs/audio evidence never justify republishing.
6. Verify migration/hash, enabled trigger, service-role-only execution, exact
   four exclusion receipts and host binding with NO provider write. Reuse the
   already successful isolated SQL race/claim regressions. Do not inject synthetic
   production reservations. Keep automatic publication disabled: guard rollout
   does not grant content, schedule or publication permission.

Rollback: first stop/quiesce the DUFYND publisher host and reconcile uncertain
calls; retain all manual receipts and existing dispatch evidence. Prefer leaving
the fail-closed guard installed. If database rollback is separately approved,
drop only `dufynd_manual_delivery_dispatch_guard`, then
`guard_dufynd_manual_delivery_v1()` and
`record_dufynd_manual_delivery_v1(text,text,text,text,text,text,text)` after
dependency checks; no CASCADE, no data deletion. Never resume automation with
the guard removed. Rollback SQL was not executed in production.

Requested future decision: approve only the exact PR783 guard migration,
identified existing host/adapter deployment, and four reconciled exclusion
receipts for brand 7182186; keep automatic publishing OFF. No website release,
new post, rescheduling, direct Metricool write or Nightshift change included.
Until host binding and out-of-band publisher exclusion are evidenced, the
activation package remains OWNER_HOLD, not globally duplicate-proof.

## Independent P2: existing campaign builder defect

Reproduced locally: base `https://dufynd.de/duft` plus landing
`/duft/rabanne-1-million` generated `/duft/duft/rabanne-1-million` despite the
function's HTTPS-origin contract. A padded base produced a space path segment
because validation used stripped input but URL joining did not.

Small isolated correction: normalize the base once, reject non-origin path,
params, query and fragment. Valid origin callers and current profile targets
retain identical URLs. This is a development input-contract defect, NOT a claim
that today's live profiles are broken. No new pipeline or public route change.

Before: new suite 6 failed / 7 passed. After: campaign suite 13 passed, dependent
content-review suite 48 passed, launch-exporter suite 2 passed (63 targeted total).
Ruff and diff whitespace checks pass. CI belongs to the new code commit only;
its final run/commit/PR are recorded in the PR and exact Supabase completion key.

## Resume / next action

Read `ops.DUFYND-20261013-LASTMILE-07` first. On completed=true, report the saved
receipt only; do not rerun profile inspection, CI, dispatch or old audits.
Next concrete priority: approve and bind the bounded PR783 exclusion-guard
rollout before the next manual handoff; do not create another publishing queue.
