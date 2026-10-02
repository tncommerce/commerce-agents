# Supervisor V2 Phase 2A — atomic cost reservations

The old $2.50 pilot already incurred $2.5047 across 19 historical runs. Phase 2A
preserves that evidence and does not increase, reset, or reactivate its budget.
The unrounded ledger total is $2.504685399999999955; $2.5047 is its previous
four-decimal display, not evidence of new spend.

## Admission and settlement

Every bounded call uses `reserve_dufynd_model_call` before dispatch. PostgreSQL
locks the existing budget row, then reads exact, unrounded legacy spend and the
reservation ledger. Admission requires `cap - spent - reserved - call_max >= 0`
and a remaining call slot. Unknown historical costs deny admission. Calls tagged
with a reservation ID in run audit are counted exclusively through the ledger.
A bound certificate reserves the full fixed contract maximum for the accepted
request envelope, even when the expected price is lower. The database rejects
amounts below that maximum. Max-run accounting conservatively counts each call.

The unique `(budget_id, idempotency_key)` includes task, owner, lease token,
request hash, contract and maximum. Reuse with conflicting inputs is denied.
Dispatch requires a live matching worker lease and wins a single atomic state
transition. An ambiguous reserve/dispatch response never triggers an automatic
provider retry. Separate budgets can proceed independently.

Verified settlement stores actual decimal USD, usage evidence, request ID and
settlement timestamp, releasing the unused portion. A response loss or provider
error is conservatively charged at the maximum. An unstarted expired reservation
is released. A dispatched expired reservation becomes `charged_max`; a late
verified receipt can lower that charge without reopening dispatch. This prevents
late billing and a second worker from consuming the same dollars. Reserving and
charging are not proof that a task is complete; normal deterministic verification
and lease fencing still apply.

The existing two-minute autonomous watchdog reconciles both reservations and
workers. Shared advisory-lock ordering precedes budget and worker locks. The
health record persists the reservation reconciliation result. Budget reductions
cannot invalidate amounts already reserved or charged. All new tables have RLS;
RPCs are service-role-only security-invoker functions with fixed search paths.

## Execution boundary

`BoundedProviderAdapter` is a single-call orchestration layer, verified using a
mechanically bounded, non-network fake. It validates input byte/output-token
limits, reserves, wins dispatch, calls once, and settles. No auto retry, SDK loop,
provider tools, tariff lookup or API credential is involved in these tests.
The existing Claude Agent SDK runtime stays unconditionally fail closed.

All existing budgets default to `reservation_enabled=false`. Migration installs
no enabled provider contracts, approvals, or test budgets. Dry-run contracts must
match dry-run windows. The adapter rejects real transports in Phase 2A. A future
paid transport must have an independently certified, immutable price/request
bound, enforce the same single-call/no-hidden-retry contract, and validate usage.
If any maximum remains unknown, paid execution stays closed. This implementation
is not a claim that the existing SDK acquired a hard cost bound.

Before a real paid canary, the owner must issue a **new** approval specifically
for `supervisor_v2_bounded_canary`, the new budget ID and certified contract ID,
with total cap, per-call cap and call count. Old generic approvals cannot satisfy
the reservation RPC. No canary or budget increase is authorized by Phase 2A.

Budget denial queues only the affected paid task. It creates no human-input gate.
Free deterministic work and Supervisor health ticks continue. Failed persistence
keeps the reservation conservative until the watchdog can settle it.

## Verification and free replay

- Unit tests cover exact boundaries, insufficient budget/no call, idempotency,
  concurrent fake workers, unknown bounds, cheaper settlement, provider failure,
  request limits, and rejected real transports.
- Dedicated CI runs the actual migration against PostgreSQL 17 and uses two
  simultaneous connections for reservation and dispatch races, plus TTL recovery.
- `tests/sql_dufynd_budget_reservations.sql` tests the actual Supabase schema in a
  rollback transaction, including crash reconciliation and private RPC grants.
- `python -m scripts.dufynd_phase2a_replay` runs the actual Supervisor loop and
  adapter offline against the three original paid task IDs and exhausted budget.
  Expected: zero provider calls/new USD, three queued paid tasks, seven free
  health ticks, one free deterministic event, zero invented human gates.
- Counterfactual historical admission, actual run
  `b01a0ed3-3a25-4f0d-af21-a05389f29ec0`: $2.334318599999999955 spent
  left $0.165681400000000045. Observed cost $0.1703668 exceeds that remainder.
  Even a best-case certified maximum equal to actual cost is rejected by
  $0.004685399999999955 before dispatch. Actual cost is a lower bound for a valid
  reservation, not a claim that a real provider price bound is known. The existing historical
  $2.5047 cannot be undone; no further call can be admitted against that window.

## OPTIMIZATION_CANDIDATE

- Add provider-issued receipt reconciliation to replace conservative maximum
  charges after a response loss. This must not release money before verified cost.
- Extend the legacy run writer with validated reservation references to make the
  ledger/audit linkage mandatory when a real transport is later added.
- Replace global worker-claim advisory locking with scoped lock ordering after
  profiling. Keep the per-budget row lock and all concurrency tests.
- Pin the PostgreSQL CI service image by digest for stricter reproducibility.

These candidates do not enable paid calls or delay Phase 2A.
