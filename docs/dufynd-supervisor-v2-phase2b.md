# Supervisor V2 Phase 2B: durable execution plane

## Supported boundary

A persisted, certified **free deterministic durability probe** can execute in
GitHub Actions without a ChatGPT process, browser session or previous conversation.
The existing autonomy task is the queue and resource lock. The new execution row
is its identity, fenced attempt/checkpoint and external-run audit, not another queue.
No arbitrary command/instruction, engineering patch or model is executed by this
handler. Additional handlers must be certified and explicitly registered before
use. Paid SDK/provider gates, budget and owner approvals are unchanged.

`prepare_dufynd_execution` atomically persists the task and execution, validates
the handler, dependencies, free budget class and scope, and uses the existing
`claim_dufynd_worker_v2` resource lock. A matching repeated idempotency key returns
the existing execution, including its final result. Changed content is rejected.
An unbound task remains dispatch_pending with a bounded 15-minute queue lease.

The existing `dufynd-jarvis-manual.yml` gains a free durable mode and a push
trigger on **scentai-mvp only**. Its isolated job uses only Supabase credentials,
read-only repository permissions, and no Anthropic/model key. The legacy paid
manual modes are not run on push. Checkout changes never enter main or PR #1.
`take_dufynd_execution` binds execution to Actions run/job/attempt atomically;
only one worker wins. A repeated trigger cannot take an already dispatched task.
Two conflict-free scopes may have separate executions. The worker reads the
persisted checkpoint, persists heartbeat at most ten seconds apart while waiting,
advances an idempotent sequential checkpoint, verifies the recipe result, completes
and releases the existing task lease. No credential/fence is printed in logs.

## Autonomous observer and recovery

The existing two-minute pg_cron entry point is extended, preserving Phase 1 worker
and Phase 2A reservation reconciliation. pg_net reads the public repository's
GitHub run endpoint, with no GitHub credential or mutation. At most one request
per tick (30/hour) and no idle traffic. Observations are persisted with source,
HTTP status and timestamp. Throttling, transport errors, malformed JSON and
unrecognized run identity are **unknown**, never success/missing. A valid 404 is
missing; completed success still does not prove the task's result. Binding is to
the exact run ID, integration branch and existing workflow path.

| State observed | Deterministic action |
| --- | --- |
| Healthy running/queued external run | Keep existing worker; no new dispatch |
| Persisted verified recipe checkpoint, finalization missing | Finalize from stored proof and release lease |
| Failed/missing run, expired lease, stale heartbeat/progress | Rotate both task/execution fence; preserve checkpoint; retryable |
| External success with no verified result | Recover; never infer work completion from exit code |
| Unknown external state | Do not treat as proof; ordinary bounded lease/progress rules still apply |
| Retryable certified free probe | Existing SQL supervisor takes a new attempt and resumes stored cursor |
| Three exhausted attempts or superseded task fence | failed_terminal with evidence; no invented human gate |

The **probe-only** deterministic supervisor fallback removes the need for a chat
or authenticated GitHub dispatcher during recovery. It advances the same certified
SQL-computable recipe, not arbitrary code. Its progress occurs on watchdog ticks,
so recovery can be slower than the Actions worker. Prior external IDs/workers and
checkpoint are retained in evidence; recovered attempts are fenced against the old
worker. Human/external waiting states and future worker types are modeled, but no
intelligent durability classifier or business observer is introduced.

Finalization requires the persisted complete sequential checkpoint and the
SQL-derived sum `n*(n+1)/2`. It cannot be forged by success prose or a bare GitHub
conclusion. Stale worker mutation fails; only the supervisor may finalize an
already verified result after expiry. Task/ledger mutations are guarded; legacy
worker RPCs cannot independently finalize an active durable task.

## Interfaces and remaining dependencies

- Command: call the service-only `prepare_dufynd_execution` RPC with explicit task,
  idempotency key, canonical resource array, scope, payload and durability policy.
- Wake: an authorized push/PR merge to scentai-mvp or manual **durable-execution**
  mode starts the existing worker. There is no secret GitHub write token in SQL.
- Inspect: read `dufynd_execution_runs` joined to `dufynd_autonomy_tasks` and the
  bound GitHub Actions run; `python -m scripts.dufynd_durable_execution status
  --execution-id ...` is an authenticated read-only CLI. No chat history needed.
- Current policies: interactive, durable, condition_watch. Future worker types:
  github_actions, render_worker, deterministic_supervisor, bounded_ai_worker.

GitHub availability/runner capacity, Supabase availability/cron, Actions' existing
Supabase service credential and the certified handler remain real dependencies.
Creation/planning of new arbitrary engineering tasks is still a command-interface
responsibility; those tasks are **not** executable merely because a ledger exists.
The probe is autonomous even without a wake: after its bounded dispatch lease,
the same watchdog recovers it with the deterministic handler. A general engineering
handler needs a durable authenticated wake/dispatch channel and independent
verification before activation. No new permanent Render worker is introduced.

## Verification and acceptance

Unit tests exercise checkpoint resume, heartbeat/progress distinction, duplicate
consume, fence loss, finalization crash, handler rejection and credential-isolated
workflow. The existing PostgreSQL CI job additionally tests actual concurrent SQL
claims/idempotency, external binding, chat-origin absence, success/release,
retryable failure, stale lease/fence, checkpoint resume, finalization crash,
conflict-free/scoped tasks, missing/failed/success-without-proof external states,
legacy/direct mutation protection and complete state reconstruction.

After migration, green CI and merge, create a fresh free probe, then wake the
existing Actions job via a reviewed integration-branch change. The live probe
uses enough timed steps to observe `running` plus external_run_id. Record origin
logically detached in the continuity checkpoint, perform no task heartbeat or
progress writes from this chat, and reconstruct completion solely from Supabase
and GitHub. Re-send the identical command and verify reuse/no second dispatch.
Acceptance results and exact IDs belong in the persistent Jarvis checkpoint.

## OPTIMIZATION_CANDIDATE

- Register additional deterministic handlers with explicit verification and bounded
  retries; keep arbitrary shell and paid handlers disabled until certified.
- A general authenticated outbox/dispatch channel is necessary before arbitrary
  engineering work can recover without a push/manual wake. A GitHub App with
  narrow Actions permissions is preferable to a broad personal token.
- Add retained per-attempt rows if recovery histories outgrow the bounded recipe
  evidence. Existing execution ID and checkpoints must remain canonical.
- Phase 2C typed external observers should extend this ledger and existing
  condition_watch policy; do not conflate business events with worker heartbeats.
- Public GitHub observation is rate-limited and optional evidence; authenticated
  narrow reads may be useful if the repository later becomes private.

References: [GitHub workflow triggers](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows),
[Supabase pg_net](https://supabase.com/docs/guides/database/extensions/pg_net),
[Supabase scheduled functions](https://supabase.com/docs/guides/functions/schedule-functions).

STOP after live acceptance and checkpoint. No paid canary: provider certification
and a fresh explicit owner budget remain prerequisites.
