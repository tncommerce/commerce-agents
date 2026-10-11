# DUFYND Seven Content Specialists — DEV-only V0

**Status:** zero-provider-cost executable editorial packet validator, **not yet seven permanently
scheduled Jarvis agents**. This document explicitly separates code-complete offline stages,
licensed inference, private data, and operational release gates. Public posting is prohibited.

## What this development PR actually implements

The code in `scripts/dufynd_seven_content_workers.py` has **seven separately runnable,
role-specific execution contracts**, in this order:

```text
W1 Growth Blueprint
     +--> W3 Audience Magnet ------+
     +--> W4 Authority Builder     |
                        W5 Engagement Loop
                        W6 Emotional Hooks
                        W2 Viral Writer
                        W7 30-Day Calendar
                            |
                            v
                 editorial chief review
                            |
                 owner creative decision
                            |
               *separate* publishing GO
```

W3 and W4 depend only on W1 and can be run independently, after which W5,
W6, W2 and W7 consume **hashed predecessor results**. Every stage has a distinct
handler, dependency set, stored packet, fingerprint, state, and hold reasons.
Local checkpoints are atomic and protected from concurrent local writers by
`flock`. Replaying the same input/round does not fabricate more work. An input
change invalidates the checkpoint rather than reusing old creative approvals.

**Critically:** these are *deterministic free editorial validation/assembly workers*.
They analyze already prepared evidence, ideas and calendar suggestions. They
are **not** seven API-funded generative creators and do **not** invent 10 fresh
ideas, 20 hooks or five verified claims from thin air. Missing inputs fail
closed. Claimed source URLs are **not independently fetched** by the offline
runner: research is marked as unverified and exact fact claims remain on hold.
No real image/mobile score can exist before a media asset has actually been
rendered and inspected.

The ongoing ChatGPT Night Creative routine is separate and remains the
temporary source of privately prepared ideas. This code does not start or
alter that routine.

## Source of truth and safe local execution

Read-only private source in Supabase `bqsdxaagklpkxioaqdqa`:
`public.dufynd_master_status`, key
`content.seven_worker_editorial_pilot_20261011_v1`.
The canonical blueprint is
`content.seven_specialist_worker_blueprint_20261011`, and owner Work mission
is `ops.work_next_seven_specialist_content_runtime_20261011`.

When an authorized environment already has
`SUPABASE_URL` and an existing permitted service-side secret configured,
the runtime can read the specific pilot once via the existing
`DufyndJarvisBridge.load_master_status_entry` read path. This command
**does not write to Supabase**, create a task lease, call an LLM, create
media or contact an external account:

```bash
python -m scripts.dufynd_seven_content_workers \
  --private-source-key content.seven_worker_editorial_pilot_20261011_v1 \
  --output /tmp/dufynd-private/seven-worker-pilot.json
```

To explicitly exercise seven isolated worker entry points against the
same stable input, run the following commands **in order** with the exact
same `--private-source-key` and `--output`:

```text
--role W1
--role W3
--role W4
--role W5
--role W6
--role W2
--role W7
```

Alternatively, for **synthetic-only local integration tests**, use an
approved synthetic JSON payload containing a `round_id`, `pilot` with
W1–W7 source sections, and `existing` frozen/published and reservation
references:

```bash
python -m pytest -q tests/test_dufynd_seven_content_workers.py
python -m scripts.dufynd_seven_content_workers \
  --input /tmp/synthetic_pilot.json \
  --output /tmp/seven-worker-fixture.json
```

Do not add any private pilot dump, unpublished Owner finals, Supabase
credentials or raw research outputs to this public Git repository. Checkpoint
files are for private environments. Tests use **synthetic local inputs only**.

## Per-stage proof required

| Stage | Accepted input | Real work | Truth/QA gate |
| --- | --- | --- | --- |
| W1 | Target/audience/format split | Validate 30-slot test mix and snapshot voice, audience and goals | Hypothesis ≠ causal result |
| W3 | Dated URLs and source-associated mechanisms | Validate URLs/date, deduplicate and attach source evidence | Offline URL ≠ freshly verified trend |
| W4 | Five educational claim candidates with URLs | Check existence/uniqueness and list exact fact review holds | No automatically published unverified claims |
| W5 | Ten real questions | Deduplicate and check specificity | No generic padded questions |
| W6 | Twenty hooks | Deduplicate and qualify input completeness | No invented performance figures |
| W2 | Ten existing candidate ideas | Check linkage to W5/W6 and known owner/published titles | No media, creative approval or publication |
| W7 | Thirty contiguous daily proposals | Ensure unique dates, reject placeholder hooks and preserve reserved Owner slots | NO actual scheduling or publication |

**Live pilot preflight (11 Oct 2026):** all seven input sections exist, but\n21 of the 30 calendar entries still contain generic hook placeholders, and\n6 of 10 idea packages lack exact W5/W6 cross-links. W7 therefore correctly\nreturns BLOCKED on that private pilot until real Owner-original hooks/captions\nare resolved without modifying frozen media. Synthetic integration tests are\nnot a claim that the live private pilot has passed all seven stages.\n\nEnd-of-run `ready_for_owner_creative_review=true` means ONLY that
all seven structured **text/source checks** were completed (some may contain
HOLDs). It is **not** a 9.5/10 visual result, a publication authorization,
or a promise that no license is pending. `ready_for_publication` stays
unconditionally false.

## Protected boundaries

- €0 incremental provider costs; model requests and media generation = 0.
- No new Supabase migrations or writes, no credential reading/logging, no
  model-API dispatch, no cross-tenant external network calls by workers.
- `main`, `scentai-mvp`, Render live deployments, catalog PR #774 and
  existing image/affiliate/owner-final records stay unchanged.
- No auto-posts, schedules, music selection, fake 9.5 ratings, licensed image
  claims, AI label bypasses or owner approvals from a worker result.
- No recurring new automation. Existing Night Creative and First-Money
  workflows remain the only scheduled editorial/analytics procedures.

## Remaining engineering to reach *fully autonomous seven-worker dispatch*

This is deliberately outside V0 until individually reviewed and proven safe:

1. Add the seven contracts to the existing **certified** Supabase worker
   allowlist and task-claim lease/fencing RPC paths via a reviewed, *additive*
   migration, committed and CI-tested before any separate production-migration GO.
   Never create fake production `done` rows or bypass current `dufynd_task_packet.py`
   strict handlers.
2. Provide a bounded producer of **new** copy that costs exactly zero under
   a verified free provider contract, or accept externally/human-prepared
   content packets. Do not substitute paid Claude SDK/Nightshift inference.
3. Add private persisted per-role result records, independent task claims,
   idempotent DAG dispatch, lease-expiry recovery and owner review bundle.
4. Test real end-to-end on a private test round, with the seven stages
   indicating their actual execution rather than relying on planned text.
5. Only after complete owner-reviewed QA can a separate publisher even be
   considered. Exact media, licensed audio and AI disclosures remain gates.

**Acceptance boundary for this branch:** a tested, executable, cost-zero
seven-role *editorial packet worker foundation*, not a false assertion of
24/7 generative autonomy.
