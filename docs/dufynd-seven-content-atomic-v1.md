# Seven content workers: atomic result review

Development continuation of Draft PR #775, based on `f8464a8` and its successful
CI 38138522334. No PR #774/catalogue change, production migration, activation,
model request, media creation, scheduling, publication, merge or deployment.

## What changed

- W2 rejects any exact W5 question/W6 hook mismatch; affected ideas cannot become
  successful worker results. Frozen/published/overlap-held ideas are not shortlisted.
- W7 rejects generic placeholder hooks, missing copy, duplicate dates and broken
  sequences. An immutable source reservation is a separate `FROZEN_REFERENCE_ONLY`
  type with a source-record SHA-256, empty hook and explicit original-copy HOLD.
  It is not a finished post. No rewritten frozen copy is permitted in that type.
- Offline completion means editorial **text** review, never owner creative readiness.
- An independent W4 can still finish if W3 fails. Dependants report waiting.
- The dispatcher writes through one mandatory `commit_dufynd_content7_result_v1`
  RPC. There is no REST-upsert or two-transaction completion fallback.
- Execution requires an approved pinned round snapshot (`--round`); previewing
  the old source or setting an environment flag cannot activate production.

## Database transaction and security

Prepared migration: `20261011122730_seven_content_atomic_result.sql`.
**Not applied to production.** It adds four functions and seven individually
named, disabled handler contracts. It creates no second queue, task, cron,
source record, generative provider or publication capability.

The invoker RPC follows the existing supervisor advisory-lock order, locks the
task and checks the exact role contract, task ID, owner, source snapshot hash,
version, dependency IDs/digests, zero budget, false approval flags and lease.
It inserts one immutable result, advances through existing verifying/done RPC
states and releases the lease in one transaction. A failed final transition
rolls back the insert too. Expiry uses wall-clock time. An exact receipt replay
with the original token returns success without another write; different bytes
or another token cannot replace it. Global claim serialization is inherited from
the existing supervisor, not an additional orchestration mechanism.

Server checks also reject fabricated visual grades, publishing/scheduling flags,
wrong W2 crosslinks and altered or placeholder W7 slots. JSON hashes are computed
in PostgreSQL from compact canonical UTF-8 JSON, matching the bounded Python
packet format. Exotic numeric serialization mismatches fail closed.

All four functions revoke PUBLIC/anon/authenticated execution; only existing
server roles service_role/postgres receive execute. Existing table RLS/permissions
are unchanged. Service-role credentials must never reach a browser. A service
role already has broader table access; this RPC does not claim to revoke that.

## Evidence and reproduction

`tests/test_dufynd_content7_atomic.py` applies actual control-plane migrations
and this migration in a disposable database. It tests all seven handlers,
source/dependency fingerprints, result replay, token/expiry/disabled-contract
rejection, deliberate rollback after result insertion, old-owner fencing after
lease recovery, immutable receipts, source/visual/calendar gates and public-role
denial. CI `content7-postgres` uses PostgreSQL 17 and two independent connections
to prove only one claim and one result exist during concurrent retry.

```bash
# Disposable, empty, local database only; never a production URL.
DUFYND_CONTENT_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/content7_test \
  pytest -q tests/test_dufynd_content7_atomic.py
pytest -q tests/test_dufynd_seven_content_workers.py \
  tests/test_dufynd_seven_content_dispatch.py tests/test_dufynd_content7_editorial_gates.py
```

Optional local PGlite runs the same SQL/functions, including rollback; it cannot
prove two-connection contention. `DUFYND_PGLITE_MODULE` may point to an already
installed PGlite module (tested 0.3.14). The concurrency test explicitly skips in
that mode. The test-only `prepare()` helper enables synthetic contracts in an
ephemeral DB; it is not a production activation script.

The real private pilot was separately processed through actual local SQL RPCs,
with HTTP/provider calls prohibited. Original input: W2 BLOCKED, W7 waiting.
Corrected derivative: W1/W5/W6 DONE; W3/W4/W2/W7 DONE_WITH_HOLDS. Each result has
source, packet and predecessor hashes, timestamps, claimed/released task proof.
An immediate replay yielded seven ALREADY_DONE receipts and no duplicate results.
Private source/creative text is excluded from the public repository and CI.

Private editorial repair: six affected ideas contained seven broken edges.
All are now exact. The 21 placeholders became **11 concrete new draft hooks and
10 immutable source reservations**. There are 20 concrete draft hooks overall,
not 30 completed posts. Zero posts are newly approved, scheduled or published.
Metric-dependent/real-comment-dependent slots retain their evidence HOLDs.
The original Supabase pilot and all Owner finals remain unchanged.

## Operational readiness by role

| Role | Free unattended operation on prepared inputs | Remaining creative/evidence gate |
| --- | --- | --- |
| W1 Growth Blueprint | Validate audience, voice and test mix | New strategy requires editorial input; no measured growth claim |
| W2 Viral Writer | Assemble 10 ideas, exact links, dedupe, shortlist at most 3 | Novel writing needs approved input producer; visual/Owner review |
| W3 Audience Analyzer | Validate supplied discussion records and source dates | No live collection/virality proof; source re-verification |
| W4 Authority Builder | Assemble five attributed claims with HOLDs | Exact claim verification; no automatic facts clearance |
| W5 Engagement Loop | Validate 10 distinct questions | New questions need editorial input; no fabricated replies |
| W6 Hook Generator | Validate 20 distinct supplied hooks | New hook generation requires approved provider/input producer |
| W7 Calendar | Validate/assemble 30 consecutive review slots | Frozen original copy, evidence, assets and exact publishing GO |

No certified zero-incremental-cost generative backend is present in these
contracts. The existing generic runtime imports the Claude SDK; specialist tasks
remain excluded from that paid/countable path. Prepared Work/manual editorial
packets remain the interim input. The existing Night Creative workflow is not
modified or duplicated. These are seven deterministic workers, not seven 24/7
autonomous creators. Production currently has zero new content7 tasks.

## Next exact activation decision

1. Review the additive migration and new CI evidence; approve production DDL
   separately if desired. Applying DDL alone leaves all seven contracts disabled.
2. Review the private corrected source and current freeze/published snapshot.
   Approve one pinned round/version and its immutable context hash. Store that
   full private context at `content.seven_workers.runtime.source.<round>` only
   in a separately reviewed activation transaction. Do not mutate a pinned round
   or prior result; use a reviewed revision identifier for later changes.
3. Separately certify/enable exactly the seven contracts, insert only the exact
   seven manifest tasks and explicitly release them. No activation SQL runs in
   this PR. The script must use that pinned round plus the existing opt-in flag.
4. Inspect the chief-editor text bundle (maximum three candidates). Unverified
   sources and uncreated visuals remain HOLD. Creative approval, migration GO,
   worker activation and publication GO are four distinct decisions.

Do not resume by rerunning old successful CI, replacing Owner media, rewriting
the raw pilot, or reusing a legacy result with a nonterminal task. The latter is
an explicit `non_atomic_legacy_result_requires_review` stop, not auto-recovery.
