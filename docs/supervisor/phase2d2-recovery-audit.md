# Phase 2D.2/2D.3 audit extension

The current watchdog already repairs expired leases, stale heartbeats, stalled
progress and superseded fences; the event processor reevaluates exact internal
and external dependencies. No second recovery algorithm, auditor handler,
scheduler or queue is added.

The existing certified supervisor_state_audit gains a read-only consistency
projection: active/released contradictions, expired leases, stale workers,
completed execution with unreleased matching fence, done task with running
execution, old fence, retryable execution without owner, and unknown states.
Counts are grouped by precise reason; no task prose, tokens, mail or identifiers
are copied to reports. Unknown states prevent a healthy result. Historic completed
executions with a superseded fence are not misclassified as current leases.

The same audit records waiting/blocked tasks eligible under the existing dependency
rules and ready tasks missing dependencies. Human approval, reply review and
freshness rechecks remain gates. The audit performs no wake or repair. The existing
event processor continues to own reevaluation.

The report retains audit_version=1 and adds extension_revision=2. Immutable old
execution reports are untouched; a fresh execution is required to observe the
extension. Existing packet scope/capabilities, checkpoint/finish RPCs and
crash/retry/fencing behavior are unchanged. Completion means findings collected,
not a claim that all findings are healthy. Live free acceptance follows green CI,
merge and migration using the existing certified handler.

Validation adds real PostgreSQL classification, duplicate audit, no-chat and
read-only checks; existing crash/retry tests still cover the reused execution path.
