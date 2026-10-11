# Seven content workers: activation preparation V2 — 2026-10-11

PR #775 only, base `scentai-mvp`. No production migration, activation, merge,
deployment, publication, paid provider request or modification of Owner finals.
The previously green baseline was `275f31f0f650a17d2995683f8d296152dd49a26f`,
CI `38140109644`. This increment adds the missing integration and activation path.

## Implemented behavior

- The existing nightshift Supervisor recognizes the seven deterministic handlers
  separately from model tasks. Opt-in is off by default. A tick executes at most
  seven tasks, sequentially, honoring its deadline; it uses the existing queue,
  dependency reconciler, 180-second leases, retries and immutable atomic receipts.
- A content tick does not enter a model budget or provider path. The global model
  budget is neither opened nor enlarged. No second cron, queue or agent scheduler.
- Activation requires an **existing approved human decision** of action type
  `content7_atomic_activation`, bound to the exact round, plan SHA256 and context
  SHA256. A creative GO or environment variable is insufficient. The migration
  installs disabled contracts; it does not create tasks or confer approval.
- Activation is one transaction: verify the fresh freeze snapshot, refuse existing
  ideas and reserved cross-round titles, enable the exact free contracts, pin the
  private input, register seven tasks, record the receipt, reconcile dependencies.
  Exact repeat calls return the receipt without adding tasks/results. Changed
  bytes fail. No changes to content finals, assets or publishing tables.
- Result commits re-check the activation receipt and the current Owner decision
  while holding locks. Revocation/pause therefore also blocks an already claimed
  worker from committing. Queue readiness alone is not authorization.
- W7 can reference an exact W2 idea ID. Title, hook and format must match the W2
  output in both Python and SQL. Standalone calendar suggestions remain proposals.
- Chief Editor receives at most three **text** candidates. None is automatically
  an Owner-facing visual candidate: visual score remains null, creative GO false,
  publishing GO false, source verification and media rights remain explicit HOLDs.

## Honest creative-production boundary

`python -m scripts.dufynd_content7_activation --commission --output PRIVATE.json`
reads four existing no-provider components: zero-budget queue, performance
learning, reuse audit and production packet. It records each source hash or HOLD
and requests all seven input sections. It does not impersonate an LLM. Live
read-only calls to these four functions succeeded on 2026-10-11.

The existing production packet supplies old idea copy, directions and QA rules;
its target score and queue rank are **not actual visual QA**. Existing provider
contracts identify paid/uncertified Anthropic/OpenRouter paths and a simulated
fixture. No certified zero-cost creative production endpoint was found in these
existing components. No external free-tier account was opened or inferred.

The functioning free precursor accepts new **Work-authored or human-authored**
editorial packets with explicit provenance (`input_version=2`, no provider calls,
zero incremental spend, `autonomous_generation=false`). Work can prepare new copy
within this authorized session. That is not unattended seven-worker generation.

| Role | Executes independently for €0 | Still needs creative/evidence input |
|---|---|---|
| W1 | Checks strategy, audience and 30-day experiment mix | New strategy authored in Work/by editor |
| W3 | Checks dated HTTPS research leads and hands off evidence | Live source/metric verification; no virality assertion |
| W4 | Builds five traceable fact-review records | Qualified exact-claim clearance; no SKU claims |
| W5 | Validates ten distinct community questions | New question writing |
| W6 | Validates twenty distinct hooks | New hook writing; no measured-success claim |
| W2 | Crosslinks hooks/questions, excludes known frozen/published items, selects ≤3 | New ideas/copy, semantic originality and visual production |
| W7 | Validates 30 dates, reservations, exact W2 links and non-placeholder copy | New calendar proposals; separate scheduling/publishing GO |

## New isolated acceptance run

Round `dufynd_editorial_readiness_20261011_v2` is a new packet, not a replay.
It contains ten new Work-authored ideas, twenty hooks, ten questions and thirty
concrete calendar proposals (2026-11-11 through 2026-12-10). W3/W4 reuse identified
source leads from the prior reviewed packet and retain verification HOLDs.

The private run loaded a fresh read-only live freeze/idea snapshot into a new,
ephemeral PGlite PostgreSQL database. Its `ISOLATED_TEST_APPROVAL_NOT_OWNER_GO`
decision existed **only there**. It invoked the actual prepared activation RPC,
the same bounded tick used by nightshift, actual claims/reconciliation/commit RPCs,
and injected a disconnect before W1 commit. Existing lease recovery retried W1
with a new token and automatically completed the remaining six roles. An extra
tick wrote no results. A repeated activation returned the same receipt.

Public redacted hashes, timestamps, role results and predecessor edges:
[`evidence/seven-content-readiness-pilot-20261011.json`](evidence/seven-content-readiness-pilot-20261011.json).
Private creative text, live-source snapshots and full SQL receipts stay out of
this repository. PGlite is real isolated SQL, not a productive Supabase run;
parallel-connection contention remains covered by the PostgreSQL CI job.

## Repeatable activation runbook — NOT authorization

1. Review/approve and merge the code separately. Review both pending migrations
   `20261011122730_seven_content_atomic_result.sql` and
   `20261011131709_seven_content_activation.sql`; apply only these reviewed
   migrations after **separate production migration GO**, through the normal
   migration process. Do not use a blanket push of unrelated pending migrations.
2. Read current finals/reservations and idea records again when activating; the
   current packet snapshot expires after 24 hours. Use a new version for edited
   input. Semantic similarity still needs editorial review; exact title/hash
   deduplication is not a semantic plagiarism detector.
3. Prepare locally, without writes:

   ```sh
   python -m scripts.dufynd_content7_activation \
     --source /private/source-v2.json --existing /private/existing-v2.json \
     --output /private/activation-plan-v2.json
   ```

4. The normal human-decision flow must obtain a distinct Owner activation GO.
   Exact `context` of that decision:

   ```json
   {"round_id":"<plan.context.round>","plan_sha256":"<SHA256 of plan>","source_sha256":"<plan.source_sha256>"}
   ```

   Action type: `content7_atomic_activation`; status must genuinely be approved.
   This code never creates or approves human decisions. Do not copy the isolated
   test approval into production. The complete private plan is the review object.
5. An authorized operator invokes the single parameterized RPC; `$1` is the
   approved decision ID, `$2` is the **exact plan object**, not its file wrapper:

   ```sql
   SELECT public.activate_dufynd_content7_v1($1::text, $2::jsonb);
   ```

   Then permit the existing Supervisor adapter using
   `DUFYND_SEVEN_WORKER_ACTIVATION_GO=1` in the approved runtime configuration.
   Do not start a parallel dispatcher or cron. Keep all provider paths closed.
6. Verify the seven immutable result keys and released task leases using SELECTs.
   Hand text candidates to Chief Editor. Owner visual review only follows actual
   visual production, source/rights clearance, mobile QA and honest ≥9.5 review.
   Creative approval never schedules or publishes anything.

## Failure/recovery and stopping

| State | Recovery |
|---|---|
| Dependency not done | Existing reconciler keeps dependents planned; independent W4 can still run when W3 blocks |
| Disconnected before commit | Existing expired-lease recovery retries, capped by existing retry policy; stale token cannot write |
| Response lost after commit | Read done/immutable receipt; no second result write; downstream tasks proceed |
| Invalid input or source facts | HOLD/blocked; repair in a new version, never mutate pinned or saved bytes |
| Unknown provider or nonzero price | Input/activation rejected; no provider call is attempted |
| Owner decision revoked | Activation check refuses work/result commit; operator resolves the decision |
| Exact duplicate round | Return existing receipt; do not create another seven-task batch |
| Reused idea title across rounds/existing ideas | Activation fails atomically; semantic duplicates still require editor review |

An authorized operator can stop a specific exact plan:

```sql
SELECT public.pause_dufynd_content7_v1($1::text, $2::text);
-- $1 = round ID; $2 = exact plan SHA256.
```

This only disables that receipt and blocks its unclaimed queued tasks. It never
deletes results/finals. An in-flight task cannot commit after pause; the ordinary
lease reconciler handles expiry. A paused round cannot silently re-enable itself;
operator review is required. Production schema rollback/dropping functions is
not needed to stop the worker adapter.

## Remaining external gates

Production migration GO, approved runtime integration/deploy, exact packet
activation GO, and a certified zero-cost creative provider (if unattended novel
copy is desired). Current free Work/manual ingestion is executable now. Media
production/rights/actual visual QA and separate publishing GO remain outside this
technical activation. **New published posts: 0. New Owner-ready visual candidates: 0.**
