# OPERATIONS-06 — development receipt

Base: scentai-mvp `8647495e5619d1acfaa1346949d586e3b27c4fab`, read-only.
No production deployment, migration, scheduling, posts, credentials or Nightshift changes.

## Reproduced P0 gap

2026-10-13 readback: today's Instagram Dufttester is PUBLISHED; today's TikTok
18:00 and tomorrow's Instagram 10:00 / TikTok 18:00 Waschmittel are PENDING.
All four have autoPublish=false; Instagram's nested flag is also false.
The three creative families queried (Dufttester, Waschmittel, Torwart) have no
matching content-asset rows. The existing dispatch ledger deduplicates only
its own reservations; independent manual/planner observations are not consumed.
This proves a remaining technical gap, not the historical cause of the duplicate
Instagram post. No historical cause or account-wide protection is invented.

In an isolated PostgreSQL WASM engine, the original dispatch DDL accepted a new
automatic reservation for a recorded MANUAL_PUBLISHED creative. After the proposed
guard it rejects that same INSERT. Real multi-connection PostgreSQL tests run in
the existing CI service, in a separately created disposable database; WASM results
are not presented as concurrency tests.

## Narrow fix and boundaries

`record_manual_delivery` binds an existing frozen creative's content ID and hash
to exact planner ID, UUID, platform and manual provider readback. It imports only
an exclusion from automation, never publication permission, audio or rights QA.
Unknown provider outcomes become MANUAL_UNKNOWN. SQL persists these receipts in
the existing master-status table; no new queue, scheduler or task service.
MANUAL_PUBLISHED never regresses. Aliases/conflicting identities require review.

`docs/sql/dufynd_manual_publication_guard.sql` is an **unapplied SQL proposal**,
deliberately outside automatic migration discovery. A shared transactional lock
serializes manual receipts with the existing dispatch ledger's reservation and
invocation claim. The trigger rejects matching content IDs, asset hashes, or
canonical release IDs, including corrupt/unknown manual states. Post-call provider
receipts remain recordable. Existing ledger rows and approvals are preserved.

Manual evidence arriving after a publisher has claimed its external invocation
cannot retroactively cancel that provider call. The receipt marks reconciliation
required; neither SQL nor this tool changes Metricool posts. Register a manual
handoff BEFORE native posting, and reconcile any existing automatic reservation
before proceeding. Direct Metricool/UI calls outside the guarded adapter remain
outside this protection. Hashes cannot identify an edited/re-encoded copy without
the canonical content binding. No heuristic caption/image match is trusted.

Before production: review/generate the migration through the existing migration
workflow; approve its application and adapter deployment; privately reconcile and
import current manual handoffs using fresh readback. Do not treat this source PR
as a live fix. Disable the executor before rollback; retaining manual receipts is
safe. Do not drop the guard while automatic publishing remains enabled.

## P1: existing manual distribution, no new asset

The already approved frozen files and existing manual planner entries suffice;
no re-export, changed caption or duplicate packet/media upload is needed. The
private mobile handoff records exact existing entries, integrity references and
native audio/disclosure checks. Today's published Instagram is excluded.

Use the completed FUNNEL-01 measurements only: four session keys, ten events,
zero clickouts in its recorded window; independently external visitors and Awin
revenue remain UNKNOWN. No new analytics audit or artificial traffic was run.
The previously verified Instagram profile link reaches the Rabanne landing page.
TikTok's actual website destination remains UNKNOWN. A static meme caption alone
does not establish a usable outbound link. Do not silently edit approved captions,
profiles or campaign tags, and do not attribute the old profile campaign to the
new meme without evidence. Highest leverage: verify the real mobile TikTok website
destination before claiming today's manual post has a measurable shop path.

## P2: private typed Jarvis design, not activated

Reuse the existing authenticated Control Room, `JarvisTruthReader.inspect`,
`JarvisSafeActionRunner`, owner decisions, autonomy tasks and durable receipts.
No model calls, no new task queue, no voice connection or scheduler.

1. Owner types ordinary German, e.g. “Wie steht DUFYND da?” or “Was kannst du
   jetzt sicher erledigen?”. Resolve only bounded supported intents. Unrecognized,
   mixed or protected requests produce a clarification/OWNER_HOLD, never a guessed
   tool call. “Veröffentliche das” cannot map to the safe-action endpoint.
2. Read live truth through the existing owner-only truth route. Reply with observed
   time, verified state, blocker and next useful step. Unknown remains unknown.
3. “Mach die nächste sichere Aufgabe” produces a confirmation card: one existing
   certified free cycle, maximum one task, zero paid calls, no publication or gate
   override. Confirmation is a separate authenticated/CSRF-protected action; merely
   typing a sentence or reloading must never execute work.
4. **Remaining integration prerequisite:** current `/internal/jarvis/safe-action`
   accepts only `{action: advance_next_safe_work}` and has no durable client-request
   ID. A text UI must not pretend this provides request idempotency. Bind the new
   confirmation to an existing persisted owner-decision record and resulting task/
   execution receipt via a separately reviewed bounded RPC before enabling a button.
   Do not introduce a second task ledger. Draft remains read-only until this exists.
5. On interruption, read that same decision/task/execution receipt. Show completed
   only with durable completion evidence. Timeout after submission means outcome
   unknown and reconciliation, not automatic retry with a new ID. Rejected, expired
   or changed confirmations require a new exact review.
6. Reuse current owner authentication, origin/CSRF checks, no-store/noindex headers,
   server-side secrets and bounded payloads. Voice stays disabled in this proposal.
   German style: concise chief-of-staff language. Occasional dry humor only outside
   money/security/errors (e.g. “Der Plan steht. Die Glaskugel bleibt ausgeschaltet.”).

Acceptance matrix for later UI integration: unauthenticated/CSRF-denied; read-only
status; protected/mixed request HOLD; one exact confirmed safe task; repeat confirm
same receipt; process restart; lost HTTP response; revoked decision; UNKNOWN result;
no model/voice network calls. None is falsely claimed as a shipped conversational UI.
