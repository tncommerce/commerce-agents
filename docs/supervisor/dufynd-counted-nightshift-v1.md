# Anthropic counted Nightshift V1

This path is disabled until a **new, separate** Owner-approved active window exists.
It neither resets nor reuses `jarvis_activation_pilot_001`. No paid validation is
required. The historical budget, main dispatcher and protected PRs are untouched.

## Request policy

`anthropic-sonnet5-counted-margin-v1` uses the official Claude Platform Sonnet 5
standard global tariff: input $2/MTok, output $10/MTok. Cache read $0.20,
5-minute write $2.50 and 1-hour write $4 are recorded but caching is disabled.
The immutable pricing artifact contains sources, verification time and a
24-hour expiry. After expiry, official verification and a reviewed synchronized
artifact/database contract refresh are required; no automatic renewal.

Only one text-only request per selected task is permitted. No server/client
model tools, prompt caching, priority/fast/batch tier, US routing, beta headers,
SDK retries, publication, messages, shell commands, code changes or final
self-approval. Repository context is a fixed bounded public allowlist, with
hashes and explicit truncation; it is not live product/social/revenue evidence.
Research/content drafts require independent review and remain blocked afterward.

Before generation, the free `/v1/messages/count_tokens` endpoint receives the
same model/system/messages/thinking payload. Its result is an **estimate**:

- conservative input = `ceil(estimate × 1.25) + 128`, at most 8,192 tokens;
- output cap = min(2,048, floor((reservation − input cost) / $0.000010));
- maximum policy reservation = **$0.036864** per request/task;
- exact serialized generation payload and count payload hashes are recorded;
- proof expires after 120 seconds; atomic dispatch rechecks approval, contract,
  window, lease, run/cost totals and uniqueness immediately before transport.

The reservation/estimate policy is not a mathematically guaranteed provider
invoice ceiling. A finite safety margin cannot prove an absolute input-token
bound. Owner approval must explicitly accept this estimate policy. Taxes and
account-level charges are outside the token tariff. If absolute external
billing enforcement is required, the provider account spending limit must be
verified separately before approval; do not claim this application supplies it.

Provider usage is retained without clamping, including cache fields when
present. Thinking is part of output-token billing, never added again. A receipt
ID can settle only one reservation. A margin breach or unknown usage pauses
the window; timeout/crash never initiates a retry. Ambiguous dispatched requests
are conservatively accounted at the reservation until real evidence resolves
them, and the window is paused. This accounting is not a fabricated actual bill.

## Approval and window

Suggested ID: `jarvis_nightshift_v1_20261003_001` (not created/activated).
Owner chooses `cap_usd` and `max_runs` explicitly. Recommended first canary:
**3 runs maximum**, one request each, no retries; this is a run recommendation,
not authorization or a chosen total budget. Technical session limit is 20 tasks,
0 events, 0 retries, 120-second worker timeout and 60-minute deadline.

A new window must reference an approved human decision with matching:
`approved=true`, `scope=supervisor_v2_bounded_canary`, `provider=anthropic`,
`model=claude-sonnet-5`, `contract_id=anthropic-sonnet5-counted-margin-v1`,
`cost_policy=estimate_margin_v1`, `accept_estimate_margin=true`, `budget_id`,
`cap_usd`, `max_runs`, `per_call_cap_usd=0.036864`.
Window fields: provider/model, cap/max_runs, approval reference, active status,
started_at, optional ended_at, reservation_enabled=true,
reservation_dry_run=false. No window is created by this implementation.
The resolver requires **exactly one usable explicitly approved active window**;
none, ambiguity, expiry, insufficient reservation funds or exhausted runs stops
before any paid request. Ledger reservations supply spend, held amount and
remaining totals. Owner-controlled changes remain auditable in approval/ledger.

## Start after explicit approval only

No main update is required. Use the existing manual workflow at integration ref:

```sh
gh workflow run dufynd-jarvis-manual.yml --repo tncommerce/commerce-agents \
  --ref scentai-mvp -f mode=nightshift-bounded-preflight
```

After the free preflight and a separate explicit start authorization:

```sh
gh workflow run dufynd-jarvis-manual.yml --repo tncommerce/commerce-agents \
  --ref scentai-mvp -f mode=nightshift-bounded \
  -f approval_token=GO-JARVIS-NIGHTSHIFT -f nightshift_max_tasks=3
```

These commands are documentation, not an executed start. The legacy automatic
main dispatcher remains on its exhausted pilot path; it must not be used for
the new window. The integration manual path resolves the window centrally.

Empty queue stops without generation. Budget/provider/approval/collision/external
blockers wait or stop. Only eligible research/content tasks are selected; existing
resource-scope fencing protects other strands. Optional stale observers do not
authorize or prevent unrelated tasks; dependent tasks remain waiting.
Morning/session records use the existing implementation. A standalone terminal
artifact is written in `finally`, and also persisted to Control Plane when
available. If database persistence fails, the workflow artifact survives; no
implementation can guarantee database writes during a database outage.

## Free validation

HTTP mocks test exact input matching, estimation/margin, bounded output,
absent/exhausted budget, run limit, immutable payload, unknown billing, duplicate
request, timeout and unclamped usage. PostgreSQL tests cover atomic reservation,
last permitted dispatch, approval/contract/window failure, lease fences,
reconciliation, idempotency and concurrent workers. Existing Nightshift tests
cover empty queue, external blockers, errors and terminal reporting.
