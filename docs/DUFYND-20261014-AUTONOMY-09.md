# DUFYND-20261014-AUTONOMY-09 — development completion / resume checkpoint

Status: IMPLEMENTED_PRIVATE_PREPARATION; production activation NOT READY.
This file plus the associated Draft PR and its latest CI comment are the durable
run checkpoint. Do not repeat P0/P1 or the completed V1 pilot on resume.

## Dedupe and unchanged boundaries

At start, the exact ops run key and matching GitHub PR search were empty.
Read ops.dufynd_work_approval_friction_policy_20261013. No SQL writes were made.
Production scentai-mvp was 8647495e5619d1acfaa1346949d586e3b27c4fab.
PR785 was f649bcaefede67cfdca6289d5b2824c9e483a5f0, with previously
successful CI38448298452 (not rerun). PR783/784 and their existing work retained.
This branch is stacked on PR775 at 289fba7cf059cca3fa54b1417010b8e5888685ee:
it imports the existing seven handlers and private atomic writer, not copies.
No main/scentai-mvp changes, migrations, cron writes, provider calls,
affiliate clickouts, posts, credentials or paid services. V1 commit df790a2,
its manifest, completed pilot, decisions and eleven cron registrations untouched.

## P0: publishing identities — precise HOLD, no manufactured manifest

Read current Metricool brand7182186 planner entries for 13–14 October:
Dufttester IG/TikTok are PUBLISHED; Waschmittel IG/TikTok are PENDING.
Exactly four existing entries; all autoPublish=false. This is a planner read,
not native-platform/audio verification. Provider IDs and asset hashes are in
the private evidence file, never substituted for canonical content IDs.

Source packages:
- content.dufttester_chaos_v2_growth_release_packet_20261011
- content.dufttester_chaos_v2_owner_final_20261011
- content.waschmittel_manual_release_20261014
- content.waschmittel_180eur_owner_final_20261011
- content.dufttester_tiktok_owner_manual_post_report_20261013
- content.seven_worker_editorial_pilot_20261011_v1

Seven matching content records had no root content_id/asset_id. Recursive
content_id inspection of release/worker/manual-report packets found none.
Asset-registry lookup by the two exact frozen asset hashes and recorded
source idea found no binding. An editorial idea ID is NOT a canonical ID.
Therefore no usable PR785 activation manifest was fabricated.

Remaining prerequisite: authoritative content registry -> frozen asset hash ->
four provider entries binding, followed by PR785's exact reviewed production
migration/adapter GO. Independent external/direct publisher calls remain
outside the guard until the real host is bound. This run does not claim
complete protection or change any manual post.

## P1: NEW evidence, not a repeated funnel audit

Read-only incremental window:
2026-10-13T08:07:59.799160Z < occurred_at <= 2026-10-14T05:03:11.753581Z.

31 unique events; 22 session keys; 7 product views; 1 offer-section view;
0 merchant clickouts; 0 campaign-tagged social sessions. Stored classes are
visitor for all22; no marked QA/bot sessions. These are NOT 22 proven humans:
unmarked owner/QA/bots and unknown provenance remain possible. Rabanne has
one product and one offer view in the window. No reproducible CTA/UI defect
was established, so no speculative frontend patch was made.
Revenue and commissions remain UNKNOWN without the original Awin report.

Action receipt selects VERIFY_ONE_APPROVED_SOCIAL_ENTRY: at the next already
approved manual distribution, make one existing shop entrance attributable,
then measure genuine tagged sessions -> product -> offer -> clickout.
This is an internal recommendation, not permission to edit a profile or post.

## P2: implemented bounded, inert value preparation

New code:
- scripts/dufynd_first_money_value_v2.sql: parameterized read-only aggregate;
  historical known QA/owner/bots excluded from eligible funnel counts;
  unknowns retained, no raw session identifiers in the result.
- scripts/dufynd_nightshift_value_v2.py: exactly two versioned proposals,
  first_money_action/2 and editorial_handoff/2. No enqueue, DB write,
  scheduler, provider/model API, creative generation or publication.
- Explicit source envelopes plus independently supplied SHA256 pins, <=6h
  acquisition and measurement freshness, bounded <=7-day measurement window,
  strict types/count partitions and event deduplication; corrupt inputs HOLD.
- Stable task-key proposals depend on source VALUES, not a fresh read time.
  Pins bind evidence integrity, NOT Owner authorization.
- Reuses all seven PR775 roles; carries every source/rights HOLD forward.
  Frozen/published/rejected inventory is required. Exact text exclusion is
  NOT semantic originality approval. Never reschedules historical W7 dates.
- Private result hash, file lock, existing atomic writer, immutable resume;
  identical saved result returns ALREADY_PREPARED. Corrupt/different result
  cannot overwrite a checkpoint. One held handler does not block the other.

Real private preparation yielded:
A INTERNAL_ACTION_RECEIPT, the action above.
B OWNER_HOLD, no candidate cleared; six exact W2 source pointers have broken
W5/W6 crosslinks. The handoff identifies each failed linkage and asks for a
NEW semantically reviewed source version, not edits to frozen originals.
W3/W4 source/claim holds, actual visual >=9.5 and Owner creative/publication
gates remain. No fake visual score or new creative is presented.

Private result SHA256:
357199c6e5c0d5e1537e268d35be809c5ccd0f8d6fc036714557d03a8f2ad714

Private deliverable: DUFYND-AUTONOMY-09-Private-Evidence.json.
Full unpublished inputs stay outside this repository. It contains source
envelopes, value receipts, source pointers, frozen hashes and provider IDs.
No secret/API token/raw analytics feed is included.

## Tests and precise limits of proof

Local Python3.12:
57 passed, 5 PostgreSQL tests skipped, 5 subtests passed.
Target suite: new value tests plus existing content7 output, resume integrity
and seven-worker tests. Ruff0.16.3 check/format and git diff --check passed.
The five new native PostgreSQL tests are appended to the existing isolated
PostgreSQL17 CI job (no new job, schedule, permissions or production secret).
CI result and exact commit/run are recorded in the PR completion comment.

Covered: invalid/stale/tampered sources; duplicate events and task keys;
independent HOLD; nonzero worker cost; no third task; unsafe output;
concurrent private writers; interruption before atomic replace; unchanged
resume; corrupt checkpoint refusal; rights/visual gates; exact broken-link
handoff. Native DB tests cover historical QA/bot exclusion, duplicate/null
identities, interval boundaries, unknown classes, empty data, read-only reuse.
All synthetic analytics exist ONLY in disposable localhost test databases.

This proves deterministic local preparation and file-level process recovery.
It does NOT prove SQL/native V2 scheduling, host availability, power-loss
durability, distributed task execution or V2 lease recovery.
The proposed 2 tasks / 6 total attempts / 45min / zero-cost contract is inert
metadata here; enforcement remains the responsibility of the reviewed V1
execution adapter. It is not represented as implemented runtime enforcement.

## Activation decision: NO V2 pilot yet

V1 natively accepts only its two SQL QA handlers. PR775 roles are Python.
There is no verified existing persistent runtime adapter connecting these
new pure functions to V1 task claim/result commit. Do not call the Python
CLI a cron integration; do not widen V1's allowlist without separate review.

Smallest next development step: bind these two reviewed result handlers to
the EXISTING Jarvis execution host, or implement equivalent bounded native
handlers only after proving compatibility. Reuse V1 leases, immutable
input/result commit, shared dedupe, stop/deadline/budget/attempt limits and
automatic restoration of all11 jobs. Add genuine concurrent PostgreSQL and
crash/restart tests of THAT binding; no second queue/scheduler.

Before a first pilot, require: exact versioned adapter/migration review;
current authoritative source hashes (not today's stale replay), repaired
editorial source quality or explicit HOLD; precise two-task manifest; verified
zero-cost host/caps; new narrow Owner decision and time window; V1-equivalent
stop/restore and original CEO resumption evidence. Do not reuse the old GO.
Any future rollback must disable/restore only the newly authorized integration
and preserve task/results and the original CEO command; no unreviewed rollback
SQL is supplied here because no production integration has been implemented.

## Resume

P0/P1 complete with evidence; private V2 preparation implemented and tested.
Check the associated Draft PR's latest CI/completion comment before doing
anything. If successful, do not rerun unchanged CI. Remaining actionable
work is the existing-runtime V2 adapter above; identity binding, source/visual
review and any productive activation remain exact gates, not blanket asks.
Gmail revoked OAuth remains separate OWNER_HOLD; no retry attempted.
