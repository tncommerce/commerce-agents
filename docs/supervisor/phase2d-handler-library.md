# Phase 2D candidate audit

| Priority | Candidate | Benefit | Resource/capabilities | Risk/blocker |
| --- | --- | --- | --- | --- |
| P0 | Supervisor state/freshness audit | Persist bounded operational findings from authoritative tables; avoids repeating chat reconstructions | exact supervisor health resource; supabase.task_state, supabase.execution_state | read-only findings; completion must not mean all findings healthy |
| P1 | Exact CI/PR verification | Existing observer already captures pinned run success/failure | github.ci.observe, github.read | reuse Phase2C adapter; no second polling library |
| P1 | Deterministic acceptance receipt projection | Prevent armed-state drift seen in Phase2C | exact acceptance/execution keys | establish recipe-specific success contract, never generic exit-code success |
| P1 | Existing stale lease recovery audit | Verify current reconciler output | narrow state read | no new repair algorithm or double lease owner |
| P2 | Render pinned deployment verification | Existing observer prepared | render.observe | autonomous read credential missing; do not export connector session |
| P2 | Known external response reconciliation | Existing metadata observer prepared | gmail.read_known_threads | scoped credential/refresh missing; semantic reply requires human review |
| P3 | Commerce/content snapshot audit | Useful real work | explicit read scopes | foreign strand owners; catalog activation forbidden |

First expansion should be a deterministic supervisor state audit. No universal
shell/engineering handler, third-party code, paid AI or broader credentials.

## First staged handler: supervisor_state_audit v1

The contract requires supabase.task_state and supabase.execution_state. Its exact
resource is db:jarvis.supervisor_v2.health, scope supervisor, cost free, risk low,
durability durable. It uses the existing fenced checkpoint/finish tools. The fixed
payload is one step with a two-second interval; arbitrary SQL or payload fields are
not accepted. Checkpoint computes aggregate live metadata inside PostgreSQL and
persists the report/hash. Completion verifies that report, its hash and the existing
recipe; it means audit collected, never all services healthy or problems repaired.
The report has fresh source-health status, stale lease/stalled execution counts,
unclassified human-gate counts, observer-health counts and failed/stale inbox counts.
It contains no task prose, mail, secrets or historical chat.

The handler is staged for one exact acceptance Task only. Ordinary Tasks remain
ineligible until certify_dufynd_state_audit observes that exact execution completed,
its report hash valid and its task released. This separates the live test from
general registry admission. Recovery retains the immutable packet and obtains a new
current audit from authoritative state if the checkpoint had not yet completed.
Retries cannot repair another task or expand resources.

No recurring schedule is added. Existing events/Tasks can request this certified
handler; the empty queue remains free of model calls. Broader Render/Gmail handlers
remain blocked by autonomous credentials/refresh. Existing CI and lease observer
implementations should be reused rather than duplicated. Before third-party or
arbitrary worker admission, the task-scoped credential boundary needs an explicit
security design and owner decision; the current trusted Actions service-role runner
is not an untrusted code sandbox.


## Automatic acceptance receipt projection

The existing watchdog projects terminal execution facts into the three phase
acceptance keys. An armed receipt becomes live_execution_verified only after the
execution checkpoint is verified, the Task done and lease released. Failed/recovery
states remain technical, never human escalations. A repeated projection is a no-op
and cannot create an execution. Already recorded live_accepted remains accepted;
the projector never infers CI/deployment/event acceptance from a worker exit code.
This closes the observed Phase2C armed-status drift with no additional HTTP calls,
queue, model or periodic runner. Further sources retain their credential blockers.
